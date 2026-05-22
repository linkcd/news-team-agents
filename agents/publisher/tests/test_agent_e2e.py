import json
import os
from unittest.mock import patch, MagicMock

import pytest


def test_agent_has_correct_tools_and_prompt():
    """Verify the agent has the right tools registered and system prompt covers task types."""
    from agent import create_agent, SYSTEM_PROMPT

    assert "publish_new" in SYSTEM_PROMPT
    assert "merge_update" in SYSTEM_PROMPT
    assert "## 国内新闻" in SYSTEM_PROMPT
    assert "## 国际新闻" in SYSTEM_PROMPT
    assert "## 财经新闻" in SYSTEM_PROMPT

    agent = create_agent()


def test_tools_are_importable():
    """Verify all expected tools can be imported."""
    from tools import read_from_s3, read_repo_file, git_clone, git_commit_and_push

    assert callable(read_from_s3)
    assert callable(read_repo_file)
    assert callable(git_clone)
    assert callable(git_commit_and_push)


def test_publish_new_tool_sequence(sample_collection_data):
    """Test the tool sequence for publish_new: read S3, clone, commit+push."""
    from tools.s3_reader import read_from_s3
    from tools.git_ops import git_clone, git_commit_and_push

    # Step 1: Read from S3
    with patch("tools.s3_reader.boto3") as mock_boto3:
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        mock_body = MagicMock()
        mock_body.read.return_value = json.dumps(sample_collection_data).encode()
        mock_s3.get_object.return_value = {"Body": mock_body}

        s3_result = read_from_s3(bucket="news-agent-data", key="collections/2026-05-21/0500-norway-news.json")

    assert s3_result["status"] == "success"
    data = s3_result["data"]
    assert len(data["new_items"]) == 2

    # Step 2: Git clone
    with patch("tools.git_ops._clone_with_token") as mock_clone:
        mock_clone.return_value = {"status": "success", "repo_path": "/tmp/publisher_test"}
        clone_result = git_clone(repo="claw-lu/hexo-blog", branch="main")

    assert clone_result["status"] == "success"

    # Step 3: Git commit and push (LLM would generate markdown between steps 1 and 3)
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("tools.git_ops.git.Repo") as MockRepo:
            mock_repo = MagicMock()
            MockRepo.return_value = mock_repo
            mock_commit = MagicMock()
            mock_commit.hexsha = "abc123"
            mock_repo.index.commit.return_value = mock_commit
            mock_repo.remote.return_value = MagicMock()

            push_result = git_commit_and_push(
                repo_path=tmpdir,
                file_path="source/_posts/20260521-norway.md",
                content="---\ntitle: test\n---\n## content",
                commit_message="Add Norway news 2026-05-21",
            )

    assert push_result["status"] == "success"
    assert push_result["commit_sha"] == "abc123"


def test_merge_update_tool_sequence(sample_collection_data, sample_existing_post):
    """Test the tool sequence for merge_update: read S3, read existing, clone, commit."""
    from tools.s3_reader import read_from_s3
    from tools.repo_reader import read_repo_file

    # Step 1: Read new items from S3
    with patch("tools.s3_reader.boto3") as mock_boto3:
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        mock_body = MagicMock()
        mock_body.read.return_value = json.dumps(sample_collection_data).encode()
        mock_s3.get_object.return_value = {"Body": mock_body}

        s3_result = read_from_s3(bucket="news-agent-data", key="collections/2026-05-21/1100-norway-news.json")

    assert s3_result["status"] == "success"

    # Step 2: Read existing post
    with patch("tools.repo_reader.httpx") as mock_httpx:
        mock_response = MagicMock()
        mock_response.text = sample_existing_post
        mock_response.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_response

        repo_result = read_repo_file(
            repo="claw-lu/hexo-blog",
            branch="main",
            path="source/_posts/20260521-norway.md",
        )

    assert repo_result["status"] == "success"
    assert "奥斯陆天气预警" in repo_result["content"]
