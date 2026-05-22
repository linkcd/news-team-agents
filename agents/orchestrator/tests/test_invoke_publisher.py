import json
from unittest.mock import MagicMock

import pytest

from tools import a2a_client


@pytest.fixture(autouse=True)
def client():
    mock = MagicMock()
    a2a_client._publisher_client = mock
    return mock


class TestInvokePublisher:
    def test_sends_a2a_message_to_publisher_runtime(self, client):
        from tools.invoke_publisher import invoke_publisher

        client.invoke_agent_runtime.return_value = {
            "response": MagicMock(read=MagicMock(return_value=json.dumps({
                "result": {"status": {"state": "completed"}, "artifacts": [{"parts": [{"data": {"status": "success"}}]}]},
            }).encode()))
        }

        task_config = {"task_id": "test", "type": "publish_new"}
        invoke_publisher(task_config)

        client.invoke_agent_runtime.assert_called_once()
        call_kwargs = client.invoke_agent_runtime.call_args[1]
        payload = json.loads(call_kwargs["payload"])
        assert payload["method"] == "message/send"
        assert payload["params"]["message"]["parts"][0]["data"] == {"task": task_config}
        assert call_kwargs["runtimeUserId"] == "orchestrator"

    def test_returns_parsed_success_response(self, client):
        from tools.invoke_publisher import invoke_publisher

        data = {"status": "success", "result": {"commit_sha": "abc123"}}
        client.invoke_agent_runtime.return_value = {
            "response": MagicMock(read=MagicMock(return_value=json.dumps({
                "result": {"status": {"state": "completed"}, "artifacts": [{"parts": [{"data": data}]}]},
            }).encode()))
        }

        result = invoke_publisher({"task_id": "test"})
        assert result["status"] == "success"
        assert result["result"]["commit_sha"] == "abc123"

    def test_returns_error_on_failed_task(self, client):
        from tools.invoke_publisher import invoke_publisher

        client.invoke_agent_runtime.return_value = {
            "response": MagicMock(read=MagicMock(return_value=json.dumps({
                "result": {"status": {"state": "failed", "message": {"parts": [{"text": "Git push rejected"}]}}, "artifacts": []},
            }).encode()))
        }

        result = invoke_publisher({"task_id": "test"})
        assert result["status"] == "error"
        assert "Git push rejected" in result["error"]

    def test_returns_error_on_boto3_exception(self, client):
        from tools.invoke_publisher import invoke_publisher

        client.invoke_agent_runtime.side_effect = Exception("Timeout")

        result = invoke_publisher({"task_id": "test"})
        assert result["status"] == "error"
        assert "Timeout" in result["error"]

    def test_uses_publisher_runtime_arn_from_config(self, client):
        from tools.invoke_publisher import invoke_publisher

        client.invoke_agent_runtime.return_value = {
            "response": MagicMock(read=MagicMock(return_value=json.dumps({
                "result": {"status": {"state": "completed"}, "artifacts": [{"parts": [{"data": {"status": "success"}}]}]},
            }).encode()))
        }

        invoke_publisher({"task_id": "test"})
        call_kwargs = client.invoke_agent_runtime.call_args[1]
        assert "runtime" in call_kwargs["agentRuntimeArn"]
