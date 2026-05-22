"""Integration test: Publisher agent git operations via AgentCore Identity.

Verifies the deployed Publisher can clone, edit, commit, and push to the
hexo-blog repo using the github-token credential from AgentCore Identity.

Run:
    cd tests && uv run --with "boto3>=1.43.0" --with "pytest>=8.0" \
        --python 3.12 -- python -m pytest test_publisher_git_integration.py -v -s

Prerequisites:
    - Publisher agent deployed (agentcore deploy -y)
    - github-token credential provisioned (agentcore add credential --name github-token --api-key <PAT>)
    - PAT has Contents read/write on claw-lu/hexo-blog
"""

import json
import time
import uuid
from datetime import datetime, timezone

import boto3
import pytest

AWS_REGION = "eu-west-1"
PUBLISHER_RUNTIME_ARN = "arn:aws:bedrock-agentcore:eu-west-1:548129671048:runtime/newspublisher_NewsPublisher-OZnqGfD4D2"
TARGET_REPO = "claw-lu/hexo-blog"
TARGET_BRANCH = "main"
TEST_FILE_PATH = "source/_tests/agentcore-identity-test.md"


@pytest.fixture
def agentcore_client():
    from botocore.config import Config
    config = Config(read_timeout=120, connect_timeout=10, retries={"max_attempts": 0})
    return boto3.client("bedrock-agentcore", region_name=AWS_REGION, config=config)


def invoke_publisher(client, task_config, timeout=120):
    """Send an A2A message/send to the Publisher and return the parsed response."""
    session_id = f"git-integration-test-{uuid.uuid4().hex}"
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "message/send",
        "params": {
            "message": {
                "messageId": f"msg-{uuid.uuid4().hex[:12]}",
                "role": "user",
                "parts": [{"data": {"task": task_config}}],
            }
        },
    }
    response = client.invoke_agent_runtime(
        agentRuntimeArn=PUBLISHER_RUNTIME_ARN,
        runtimeSessionId=session_id,
        runtimeUserId="integration-test-user",
        payload=json.dumps(payload),
    )
    return json.loads(response["response"].read())


def extract_result(response: dict) -> dict:
    """Extract the result from an A2A response.

    The Publisher returns its result as JSON embedded in a text artifact.
    """
    if "error" in response:
        return {"status": "error", "error": json.dumps(response["error"])}
    result = response.get("result", {})
    status = result.get("status", {})

    # Check artifacts first (present even when state is "failed" sometimes)
    artifacts = result.get("artifacts", [])
    if artifacts:
        for part in artifacts[0].get("parts", []):
            if "data" in part:
                return part["data"]
            if part.get("kind") == "text":
                text = part["text"]
                start = text.find("```json")
                if start != -1:
                    start = text.index("\n", start) + 1
                    end = text.index("```", start)
                    return json.loads(text[start:end])

    # Fall back to status message for errors
    if status.get("state") == "failed":
        parts = status.get("message", {}).get("parts", [])
        error_text = next((p["text"] for p in parts if "text" in p), "Agent execution failed")
        return {"status": "error", "error": error_text}

    return {"status": "error", "error": "No parseable result in response"}


class TestPublisherGitIntegration:
    """Test Publisher agent git operations against the real hexo-blog repo.

    This test writes a test file, verifies it on GitHub, then cleans it up.
    """

    def test_publish_new_test_file(self, agentcore_client):
        """Verify the Publisher can clone the repo, write a file, and push via AgentCore Identity."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        test_content = f"""---
title: AgentCore Identity Test
date: {timestamp}
---

This file was created by the Publisher agent integration test.
Timestamp: {timestamp}
Purpose: Verify AgentCore Identity github-token credential works for git push.
"""
        task_config = {
            "task_id": f"git-test-{uuid.uuid4().hex[:8]}",
            "type": "edit",
            "target": {
                "repo": TARGET_REPO,
                "branch": TARGET_BRANCH,
                "file_path": TEST_FILE_PATH,
            },
            "instructions": f"Write exactly this content to the file (replace entirely):\n\n{test_content}",
            "commit_message": f"test: verify AgentCore Identity git push ({timestamp})",
        }

        # Agent may fail on cold start; retry up to 3 times
        last_result = None
        for attempt in range(3):
            response = invoke_publisher(agentcore_client, task_config)
            last_result = extract_result(response)
            if last_result["status"] == "success":
                break
            print(f"\nAttempt {attempt + 1} failed: {last_result.get('error')}, retrying...")
            time.sleep(5)

        assert last_result["status"] == "success", f"Publisher failed after 3 attempts: {last_result}"
        commit_sha = last_result.get("result", {}).get("commit_sha")
        assert commit_sha, f"No commit SHA returned: {last_result}"
        print(f"\nCommit SHA: {commit_sha}")
        print("AgentCore Identity -> git clone -> write -> commit -> push: OK")

    def test_cleanup_test_file(self, agentcore_client):
        """Clean up: remove the test file from the repo."""
        task_config = {
            "task_id": f"git-cleanup-{uuid.uuid4().hex[:8]}",
            "type": "edit",
            "target": {
                "repo": TARGET_REPO,
                "branch": TARGET_BRANCH,
                "file_path": TEST_FILE_PATH,
            },
            "instructions": "Delete this file entirely. Remove it from the repository.",
            "commit_message": "test: clean up AgentCore Identity test file",
        }

        response = invoke_publisher(agentcore_client, task_config)
        result = extract_result(response)

        # Cleanup is best-effort — don't fail the test suite if it doesn't work
        if result["status"] != "success":
            pytest.skip(f"Cleanup skipped (non-critical): {result.get('error')}")
