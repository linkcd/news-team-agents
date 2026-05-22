import json
from unittest.mock import MagicMock

import pytest

from tools import a2a_client


@pytest.fixture(autouse=True)
def client():
    mock = MagicMock()
    a2a_client._collector_client = mock
    return mock


class TestInvokeCollector:
    def test_sends_a2a_message_to_collector_runtime(self, client):
        from tools.invoke_collector import invoke_collector

        client.invoke_agent_runtime.return_value = {
            "response": MagicMock(read=MagicMock(return_value=json.dumps({
                "result": {"status": {"state": "completed"}, "artifacts": [{"parts": [{"data": {"status": "success"}}]}]},
            }).encode()))
        }

        task_config = {"task_id": "test", "sources": [{"url": "https://nrk.no/rss", "type": "rss"}]}
        invoke_collector(task_config)

        client.invoke_agent_runtime.assert_called_once()
        call_kwargs = client.invoke_agent_runtime.call_args[1]
        payload = json.loads(call_kwargs["payload"])
        assert payload["method"] == "message/send"
        assert payload["params"]["message"]["parts"][0]["data"] == {"task": task_config}

    def test_returns_parsed_success_response(self, client):
        from tools.invoke_collector import invoke_collector

        data = {"status": "success", "task_id": "t1", "data_key": "collections/key.json"}
        client.invoke_agent_runtime.return_value = {
            "response": MagicMock(read=MagicMock(return_value=json.dumps({
                "result": {"status": {"state": "completed"}, "artifacts": [{"parts": [{"data": data}]}]},
            }).encode()))
        }

        result = invoke_collector({"task_id": "test", "sources": []})
        assert result["status"] == "success"
        assert result["data_key"] == "collections/key.json"

    def test_returns_error_on_failed_task(self, client):
        from tools.invoke_collector import invoke_collector

        client.invoke_agent_runtime.return_value = {
            "response": MagicMock(read=MagicMock(return_value=json.dumps({
                "result": {"status": {"state": "failed", "message": {"parts": [{"text": "RSS timeout"}]}}, "artifacts": []},
            }).encode()))
        }

        result = invoke_collector({"task_id": "test", "sources": []})
        assert result["status"] == "error"
        assert "RSS timeout" in result["error"]

    def test_returns_error_on_jsonrpc_error(self, client):
        from tools.invoke_collector import invoke_collector

        client.invoke_agent_runtime.return_value = {
            "response": MagicMock(read=MagicMock(return_value=json.dumps({
                "error": {"code": -32000, "message": "Internal error"},
            }).encode()))
        }

        result = invoke_collector({"task_id": "test", "sources": []})
        assert result["status"] == "error"
        assert "Internal error" in result["error"]

    def test_returns_error_on_boto3_exception(self, client):
        from tools.invoke_collector import invoke_collector

        client.invoke_agent_runtime.side_effect = Exception("Connection timeout")

        result = invoke_collector({"task_id": "test", "sources": []})
        assert result["status"] == "error"
        assert "Connection timeout" in result["error"]

    def test_uses_collector_runtime_arn_from_config(self, client):
        from tools.invoke_collector import invoke_collector

        client.invoke_agent_runtime.return_value = {
            "response": MagicMock(read=MagicMock(return_value=json.dumps({
                "result": {"status": {"state": "completed"}, "artifacts": [{"parts": [{"data": {"status": "success"}}]}]},
            }).encode()))
        }

        invoke_collector({"task_id": "test", "sources": []})
        call_kwargs = client.invoke_agent_runtime.call_args[1]
        assert "runtime" in call_kwargs["agentRuntimeArn"]
