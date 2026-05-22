"""Tests for A2A agent discovery (reachability check)."""

import json
from unittest.mock import MagicMock

import pytest

from tools import a2a_client


@pytest.fixture(autouse=True)
def client():
    mock = MagicMock()
    a2a_client._discovery_client = mock
    return mock


def _a2a_success_response():
    body = {"result": {"status": {"state": "completed"}}}
    return {"response": MagicMock(read=MagicMock(return_value=json.dumps(body).encode()))}


def _a2a_error_response(msg="unsupported"):
    body = {"error": {"code": -32601, "message": msg}}
    return {"response": MagicMock(read=MagicMock(return_value=json.dumps(body).encode()))}


class TestAgentDiscovery:
    def test_discover_agent_returns_available_on_success(self, client):
        """Returns available=True when runtime responds to message/send."""
        from tools.discovery import discover_agent

        client.invoke_agent_runtime.return_value = _a2a_success_response()

        result = discover_agent(
            "arn:aws:bedrock-agentcore:eu-west-1:548129671048:runtime/newscollector_NewsCollector-EhrHzp4oFi"
        )

        assert result["available"] is True

        call_kwargs = client.invoke_agent_runtime.call_args[1]
        payload = json.loads(call_kwargs["payload"])
        assert payload["method"] == "message/send"

    def test_discover_agent_returns_unavailable_on_exception(self, client):
        """Returns available=False with error if invocation raises."""
        from tools.discovery import discover_agent

        client.invoke_agent_runtime.side_effect = Exception("Connection refused")

        result = discover_agent(
            "arn:aws:bedrock-agentcore:eu-west-1:548129671048:runtime/nonexistent"
        )

        assert result["available"] is False
        assert "Connection refused" in result["error"]

    def test_discover_agent_returns_unavailable_on_a2a_error(self, client):
        """Returns available=False if A2A response contains an error."""
        from tools.discovery import discover_agent

        client.invoke_agent_runtime.return_value = _a2a_error_response("method not found")

        result = discover_agent(
            "arn:aws:bedrock-agentcore:eu-west-1:548129671048:runtime/test"
        )

        assert result["available"] is False
        assert "method not found" in result["error"]

    def test_verify_agents_checks_both_downstream_agents(self, client):
        """verify_agents checks both collector and publisher are reachable."""
        from tools.discovery import verify_agents

        client.invoke_agent_runtime.return_value = _a2a_success_response()

        result = verify_agents()

        assert result["collector"]["available"] is True
        assert result["publisher"]["available"] is True

    def test_verify_agents_reports_unavailable_agent(self, client):
        """verify_agents reports agent as unavailable if invocation fails."""
        from tools.discovery import verify_agents
        from config import PUBLISHER_RUNTIME_ARN

        def _side_effect(**kwargs):
            if kwargs.get("agentRuntimeArn") == PUBLISHER_RUNTIME_ARN:
                raise Exception("Publisher not deployed")
            return _a2a_success_response()

        client.invoke_agent_runtime.side_effect = _side_effect

        result = verify_agents()

        assert result["collector"]["available"] is True
        assert result["publisher"]["available"] is False
        assert "Publisher not deployed" in result["publisher"]["error"]
