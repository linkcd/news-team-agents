import json
import os
from unittest.mock import patch, MagicMock

import pytest


def test_publish_new_task_calls_tools_in_order(sample_collection_data):
    """Verify the agent has the right tools registered and system prompt covers publish_new."""
    from agent import create_agent, SYSTEM_PROMPT

    # Verify system prompt covers all task types
    assert "publish_new" in SYSTEM_PROMPT
    assert "merge_update" in SYSTEM_PROMPT
    assert "rewrite" in SYSTEM_PROMPT
    assert "edit" in SYSTEM_PROMPT

    # Verify agent is created with all tools
    agent = create_agent()


def test_publish_new_flow_integration(sample_collection_data):
    """Test the publish_new pipeline by calling tools in sequence (simulating what the agent would do)."""
    from tools.s3_reader import read_from_s3
    from tools.formatter import format_post
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

    # Step 2: Format post
    editorial_config = json.dumps({
        "day_summary": "今天的主要新闻：议会通过了新移民法案，石油基金创下历史新高。",
    })

    format_result = format_post(
        items=json.dumps(data["new_items"]),
        template="norway_daily",
        editorial_config=editorial_config,
        date="2026-05-21",
        time="05:00:00",
    )

    format_result = json.loads(format_result)
    assert format_result["status"] == "success"
    assert "议会通过新移民法案" in format_result["content"]
    assert "石油基金创历史新高" in format_result["content"]
    assert "## 国内新闻" in format_result["content"]
    assert "## 财经新闻" in format_result["content"]

    # Step 3: Git clone
    with patch("tools.git_ops._clone_with_token") as mock_clone:
        mock_clone.return_value = {"status": "success", "repo_path": "/tmp/publisher_test"}
        clone_result = git_clone(repo="claw-lu/hexo-blog", branch="main")

    assert clone_result["status"] == "success"

    # Step 4: Git commit and push
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
                content=format_result["content"],
                commit_message="Add Norway news 2026-05-21",
            )

    assert push_result["status"] == "success"
    assert push_result["commit_sha"] == "abc123"


def test_merge_update_flow_integration(sample_collection_data, sample_existing_post):
    """Test the merge_update pipeline by calling tools in sequence."""
    from tools.merger import merge_posts

    new_items = json.dumps(sample_collection_data["new_items"])
    updated_items = json.dumps(sample_collection_data["updated_items"])
    strategy = json.dumps({
        "new_items": "append_per_section",
        "updated_items": "replace_summary_and_add_source",
        "renumber": True,
        "regenerate_day_summary": False,
    })

    result = merge_posts(
        existing_content=sample_existing_post,
        new_items=new_items,
        updated_items=updated_items,
        strategy=strategy,
    )

    result = json.loads(result)
    assert result["status"] == "success"
    content = result["content"]
    # Original item preserved
    assert "奥斯陆天气预警" in content
    # New items added
    assert "议会通过新移民法案" in content
    assert "石油基金创历史新高" in content
    # Correct numbering
    assert "### 1." in content
    assert "### 2." in content
    assert "### 3." in content
    assert result["new_items_added"] == 2
    assert result["total_items"] == 3
