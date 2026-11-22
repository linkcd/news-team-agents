import importlib
import json
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def collection():
    return {
        "collected_at": "2026-05-21T11:00:00Z",
        "new_items": [{
            "title_zh": "New topic", "summary_zh": "New facts.", "category": "business",
            "sources": [{"source_label": "NRK", "url": "https://example.com/new",
                         "published_at": "2026-05-21T10:00:00Z"}],
        }],
        "updated_items": [],
    }


def test_prepare_post_creates_missing_post_even_after_first_run(tmp_path, collection):
    from tools.post_preparer import prepare_post

    with patch("tools.post_preparer.read_from_s3", return_value={"status": "success", "data": collection}):
        result = prepare_post(str(tmp_path), "posts/today.md", "bucket", "key", "{}")
    assert result["status"] == "success"
    assert result["action"] == "publish_new"
    assert "New topic" in (tmp_path / "posts/today.md").read_text()


def test_prepare_post_merges_existing_post_even_on_first_run(tmp_path, sample_existing_post):
    from tools.post_preparer import prepare_post

    (tmp_path / "today.md").write_text(sample_existing_post)
    with patch("tools.post_preparer.merge_posts", return_value=json.dumps({
        "status": "success", "total_items": 3,
    })) as merge, patch("tools.post_preparer.read_from_s3") as read:
        result = prepare_post(str(tmp_path), "today.md", "bucket", "key", "{}")
    assert result["action"] == "merge_update"
    merge.assert_called_once()
    read.assert_not_called()
    assert (tmp_path / "today.md").read_text() == sample_existing_post


def test_prepare_post_refuses_to_drop_updates_if_target_missing(tmp_path, collection):
    from tools.post_preparer import prepare_post

    collection["updated_items"] = [{"match_title_zh": "Missing topic"}]
    with patch("tools.post_preparer.read_from_s3", return_value={"status": "success", "data": collection}):
        result = prepare_post(str(tmp_path), "today.md", "bucket", "key", "{}")
    assert result["status"] == "error"
    assert not (tmp_path / "today.md").exists()


def test_write_new_post_cannot_overwrite_an_existing_daily_post(tmp_path):
    from tools.git_ops import write_new_post

    target = tmp_path / "today.md"
    target.write_text("Existing news")
    result = write_new_post(str(tmp_path), "today.md", "Replacement")
    assert result["status"] == "error"
    assert target.read_text() == "Existing news"


def test_merge_roundtrips_do_not_accumulate_footer_text(tmp_path, collection):
    from tools.merger import merge_posts
    from tools.formatter import format_post

    content = json.loads(format_post(json.dumps(collection["new_items"]), "norway_daily",
                                     '{"day_summary":"Day summary"}', "2026-05-21", "05:00:00"))["content"]
    target = tmp_path / "today.md"
    target.write_text(content)
    s3 = MagicMock()
    s3.get_object.return_value["Body"].read.return_value = b'{"new_items":[],"updated_items":[]}'
    with patch("tools.merger.boto3.client", return_value=s3):
        for _ in range(3):
            assert json.loads(merge_posts(str(tmp_path), "today.md", "bucket", "key", "{}"))["status"] == "success"
    assert target.read_text().count("*新闻来源:") == 1


def test_dry_run_does_not_commit_or_push(tmp_path, monkeypatch):
    from tools.git_ops import git_commit_and_push

    monkeypatch.setenv("PUBLISHING_ENABLED", "false")
    (tmp_path / "today.md").write_text("Preview")
    with patch("tools.git_ops.git.Repo") as repo:
        result = git_commit_and_push(str(tmp_path), "today.md", "Preview")
    assert result["dry_run"] is True
    repo.assert_not_called()


def test_dry_run_does_not_request_identity_credentials_or_dispatch(monkeypatch):
    module = importlib.import_module("tools.verify_deploy")
    monkeypatch.setenv("PUBLISHING_ENABLED", "false")
    with patch.object(module, "_check_and_trigger") as check:
        result = module.verify_deploy("preview")
    assert result["dry_run"] is True
    check.assert_not_called()


def test_verification_checks_only_the_configured_deploy_workflow(monkeypatch):
    module = importlib.import_module("tools.verify_deploy")
    monkeypatch.setenv("PUBLISHING_ENABLED", "true")
    monkeypatch.setenv("BLOG_REPO", "example/blog")
    with patch.object(module, "time"), patch.object(module, "httpx") as http:
        http.get.return_value = MagicMock(status_code=200, json=lambda: {
            "workflow_runs": [{"id": 42, "status": "in_progress"}],
        })
        result = module._check_and_trigger("abc", api_key="test-only")
    assert result["run_id"] == 42
    assert http.get.call_args.args[0] == "https://api.github.com/repos/example/blog/actions/workflows/deploy.yml/runs"


def test_rejected_push_is_reported_as_failure(monkeypatch):
    from tools.git_ops import git_commit_and_push

    monkeypatch.setenv("PUBLISHING_ENABLED", "true")
    with patch("tools.git_ops.git.Repo") as repo:
        repo.return_value.remote.return_value.push.return_value.raise_if_error.side_effect = RuntimeError("rejected")
        result = git_commit_and_push("/test/repo", "today.md", "Update")
    assert result["status"] == "error"


def test_preparer_consumes_the_real_s3_reader_contract(tmp_path, collection):
    from tools.post_preparer import prepare_post

    s3 = MagicMock()
    s3.get_object.return_value["Body"].read.return_value = json.dumps(collection).encode()
    with patch("tools.s3_reader.boto3.client", return_value=s3):
        result = prepare_post(str(tmp_path), "today.md", "bucket", "key")
    assert result["status"] == "success"
    assert "New topic" in (tmp_path / "today.md").read_text()


def test_agent_registers_the_deterministic_preparer():
    import agent
    from tools.post_preparer import prepare_post

    with patch.object(agent, "Agent") as factory:
        agent.create_agent()
    assert prepare_post in factory.call_args.kwargs["tools"]


def test_failed_workflow_lookup_does_not_dispatch_another_deploy(monkeypatch):
    module = importlib.import_module("tools.verify_deploy")
    monkeypatch.setenv("BLOG_REPO", "example/blog")
    with patch.object(module, "time"), patch.object(module, "httpx") as http:
        http.get.return_value = MagicMock(status_code=403)
        result = module._check_and_trigger("abc", api_key="test-only")
    assert result["status"] == "error"
    http.post.assert_not_called()
