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


class TestInvokeCollector:
    def test_sends_a2a_message_to_collector_runtime(self, mock_boto3_client):
        """Tool sends an A2A message/send request to the collector runtime."""
        from tools.invoke_collector import invoke_collector

        mock_boto3_client.invoke_agent_runtime.return_value = {
            "response": MagicMock(
                read=MagicMock(
                    return_value=json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "result": {
                                "id": "task-123",
                                "status": {"state": "completed"},
                                "artifacts": [
                                    {
                                        "parts": [
                                            {
                                                "data": {
                                                    "status": "success",
                                                    "task_id": "norway-news-2026-05-21-1100",
                                                    "data_key": "collections/2026-05-21/1100-norway-news.json",
                                                    "summary": {
                                                        "sources_fetched": 11,
                                                        "new_urls_found": 5,
                                                        "grouped_into_new_topics": 3,
                                                        "matched_to_existing_topics": 1,
                                                        "skipped_no_new_info": 1,
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
            "task_id": "norway-news-2026-05-21-1100",
            "sources": [{"url": "https://www.nrk.no/norge/toppsaker.rss", "type": "rss"}],
            "filters": {"time_window_hours": 6},
            "processing": {"consolidate_topics": True, "translate_to": ["zh"]},
            "output": {"s3_bucket": "news-agent-data-548129671048", "s3_key_prefix": "collections/2026-05-21/"},
        }

        result = invoke_collector(task_config)

        mock_boto3_client.invoke_agent_runtime.assert_called_once()
        call_kwargs = mock_boto3_client.invoke_agent_runtime.call_args[1]
        assert "agentRuntimeArn" in call_kwargs
        assert "runtimeSessionId" in call_kwargs

        payload = json.loads(call_kwargs["payload"])
        assert payload["jsonrpc"] == "2.0"
        assert payload["method"] == "message/send"
        assert payload["params"]["message"]["role"] == "user"
        parts = payload["params"]["message"]["parts"]
        assert any("data" in p and p["data"] == {"task": task_config} for p in parts)

    def test_returns_parsed_success_response(self, mock_boto3_client):
        """On success, returns the structured result from the artifact."""
        from tools.invoke_collector import invoke_collector

        collector_result = {
            "status": "success",
            "task_id": "norway-news-2026-05-21-1100",
            "data_key": "collections/2026-05-21/1100-norway-news.json",
            "summary": {
                "sources_fetched": 11,
                "new_urls_found": 5,
                "grouped_into_new_topics": 3,
                "matched_to_existing_topics": 1,
                "skipped_no_new_info": 1,
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
                                "id": "task-123",
                                "status": {"state": "completed"},
                                "artifacts": [{"parts": [{"data": collector_result}]}],
                            },
                        }
                    ).encode()
                )
            )
        }

        result = invoke_collector({"task_id": "test", "sources": []})

        assert result["status"] == "success"
        assert result["data_key"] == "collections/2026-05-21/1100-norway-news.json"
        assert result["summary"]["grouped_into_new_topics"] == 3

    def test_returns_error_on_failed_task(self, mock_boto3_client):
        """On A2A task failure, returns error status."""
        from tools.invoke_collector import invoke_collector

        mock_boto3_client.invoke_agent_runtime.return_value = {
            "response": MagicMock(
                read=MagicMock(
                    return_value=json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "result": {
                                "id": "task-456",
                                "status": {
                                    "state": "failed",
                                    "message": {"parts": [{"text": "RSS fetch timeout"}]},
                                },
                                "artifacts": [],
                            },
                        }
                    ).encode()
                )
            )
        }

        result = invoke_collector({"task_id": "test", "sources": []})

        assert result["status"] == "error"
        assert "RSS fetch timeout" in result["error"]

    def test_returns_error_on_jsonrpc_error(self, mock_boto3_client):
        """On JSON-RPC error response, returns error status."""
        from tools.invoke_collector import invoke_collector

        mock_boto3_client.invoke_agent_runtime.return_value = {
            "response": MagicMock(
                read=MagicMock(
                    return_value=json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "error": {"code": -32000, "message": "Internal error"},
                        }
                    ).encode()
                )
            )
        }

        result = invoke_collector({"task_id": "test", "sources": []})

        assert result["status"] == "error"
        assert "Internal error" in result["error"]

    def test_returns_error_on_boto3_exception(self, mock_boto3_client):
        """On boto3 client exception, returns error status."""
        from tools.invoke_collector import invoke_collector

        mock_boto3_client.invoke_agent_runtime.side_effect = Exception("Connection timeout")

        result = invoke_collector({"task_id": "test", "sources": []})

        assert result["status"] == "error"
        assert "Connection timeout" in result["error"]

    def test_uses_collector_runtime_arn_from_config(self, mock_boto3_client):
        """Uses the COLLECTOR_RUNTIME_ARN from config."""
        from tools.invoke_collector import invoke_collector

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

        invoke_collector({"task_id": "test", "sources": []})

        call_kwargs = mock_boto3_client.invoke_agent_runtime.call_args[1]
        assert "agentRuntimeArn" in call_kwargs
        assert "runtime" in call_kwargs["agentRuntimeArn"]
