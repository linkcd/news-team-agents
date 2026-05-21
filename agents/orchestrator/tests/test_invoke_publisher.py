import json
import sys
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_boto3_client():
    """Patch the boto3 mock's client to return a controllable mock client."""
    boto3_mod = sys.modules["boto3"]
    client = MagicMock()
    boto3_mod.client.return_value = client
    yield client
    boto3_mod.reset_mock()


class TestInvokePublisher:
    def test_sends_a2a_message_to_publisher_runtime(self, mock_boto3_client):
        """Tool sends an A2A message/send request to the publisher runtime."""
        from tools.invoke_publisher import invoke_publisher

        mock_boto3_client.invoke_agent_runtime.return_value = {
            "response": MagicMock(
                read=MagicMock(
                    return_value=json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "result": {
                                "id": "task-pub-1",
                                "status": {"state": "completed"},
                                "artifacts": [
                                    {
                                        "parts": [
                                            {
                                                "data": {
                                                    "status": "success",
                                                    "task_id": "publish-norway-2026-05-21",
                                                    "result": {
                                                        "action": "publish_new",
                                                        "file_path": "source/_posts/20260521-norway.md",
                                                        "commit_sha": "abc123def",
                                                        "new_items_added": 3,
                                                        "total_items_in_post": 3,
                                                    },
                                                }
                                            }
                                        ]
                                    }
                                ],
                            },
                        }
                    ).encode()
                )
            )
        }

        task_config = {
            "task_id": "publish-norway-2026-05-21",
            "type": "publish_new",
            "source": {"type": "s3", "bucket": "news-agent-data-548129671048", "key": "collections/2026-05-21/0500.json"},
            "template": "norway_daily",
            "output": {
                "repo": "claw-lu/hexo-blog",
                "branch": "main",
                "file_path": "source/_posts/20260521-norway.md",
            },
        }

        result = invoke_publisher(task_config)

        mock_boto3_client.invoke_agent_runtime.assert_called_once()
        call_kwargs = mock_boto3_client.invoke_agent_runtime.call_args[1]

        payload = json.loads(call_kwargs["payload"])
        assert payload["jsonrpc"] == "2.0"
        assert payload["method"] == "message/send"
        assert payload["params"]["message"]["role"] == "user"
        parts = payload["params"]["message"]["parts"]
        assert any("data" in p and p["data"] == {"task": task_config} for p in parts)

    def test_returns_parsed_success_response(self, mock_boto3_client):
        """On success, returns the structured result from the artifact."""
        from tools.invoke_publisher import invoke_publisher

        publisher_result = {
            "status": "success",
            "task_id": "publish-norway-2026-05-21",
            "result": {
                "action": "merge_update",
                "file_path": "source/_posts/20260521-norway.md",
                "commit_sha": "def456",
                "new_items_added": 2,
                "existing_items_updated": 1,
                "total_items_in_post": 7,
            },
        }
        mock_boto3_client.invoke_agent_runtime.return_value = {
            "response": MagicMock(
                read=MagicMock(
                    return_value=json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "result": {
                                "id": "task-pub-2",
                                "status": {"state": "completed"},
                                "artifacts": [{"parts": [{"data": publisher_result}]}],
                            },
                        }
                    ).encode()
                )
            )
        }

        result = invoke_publisher({"task_id": "test", "type": "merge_update"})

        assert result["status"] == "success"
        assert result["result"]["commit_sha"] == "def456"
        assert result["result"]["total_items_in_post"] == 7

    def test_returns_error_on_failed_task(self, mock_boto3_client):
        """On A2A task failure, returns error status."""
        from tools.invoke_publisher import invoke_publisher

        mock_boto3_client.invoke_agent_runtime.return_value = {
            "response": MagicMock(
                read=MagicMock(
                    return_value=json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "result": {
                                "id": "task-pub-3",
                                "status": {
                                    "state": "failed",
                                    "message": {"parts": [{"text": "Git push rejected"}]},
                                },
                                "artifacts": [],
                            },
                        }
                    ).encode()
                )
            )
        }

        result = invoke_publisher({"task_id": "test", "type": "publish_new"})

        assert result["status"] == "error"
        assert "Git push rejected" in result["error"]

    def test_returns_error_on_boto3_exception(self, mock_boto3_client):
        """On boto3 client exception, returns error status."""
        from tools.invoke_publisher import invoke_publisher

        mock_boto3_client.invoke_agent_runtime.side_effect = Exception("Service unavailable")

        result = invoke_publisher({"task_id": "test", "type": "publish_new"})

        assert result["status"] == "error"
        assert "Service unavailable" in result["error"]

    def test_uses_publisher_runtime_arn_from_config(self, mock_boto3_client):
        """Uses the PUBLISHER_RUNTIME_ARN from config."""
        from tools.invoke_publisher import invoke_publisher

        mock_boto3_client.invoke_agent_runtime.return_value = {
            "response": MagicMock(
                read=MagicMock(
                    return_value=json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "result": {
                                "id": "task-1",
                                "status": {"state": "completed"},
                                "artifacts": [{"parts": [{"data": {"status": "success", "task_id": "t"}}]}],
                            },
                        }
                    ).encode()
                )
            )
        }

        invoke_publisher({"task_id": "test", "type": "publish_new"})

        call_kwargs = mock_boto3_client.invoke_agent_runtime.call_args[1]
        assert "agentRuntimeArn" in call_kwargs
