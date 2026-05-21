"""Tests for A2A Agent Card discovery."""

import json
import sys
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_boto3_client():
    boto3_mod = sys.modules["boto3"]
    client = MagicMock()
    boto3_mod.client.return_value = client
    yield client
    boto3_mod.reset_mock()


class TestAgentDiscovery:
    def test_discover_agent_returns_agent_card(self, mock_boto3_client):
        """Fetches agent card from runtime's /.well-known/agent-card.json endpoint."""
        from tools.discovery import discover_agent

        agent_card = {
            "name": "NewsCollector",
            "description": "General-purpose web content collection agent",
            "version": "0.1.0",
            "capabilities": {"streaming": True},
            "skills": [
                {
                    "id": "content-collection",
                    "name": "Content Collection",
                    "description": "Fetches and consolidates web content",
                }
            ],
        }

        mock_boto3_client.invoke_agent_runtime.return_value = {
            "response": MagicMock(
                read=MagicMock(return_value=json.dumps(agent_card).encode())
            )
        }

        result = discover_agent(
            "arn:aws:bedrock-agentcore:eu-west-1:548129671048:runtime/newscollector_NewsCollector-dVHkI27O5j"
        )

        assert result["name"] == "NewsCollector"
        assert result["capabilities"]["streaming"] is True
        assert len(result["skills"]) == 1

        call_kwargs = mock_boto3_client.invoke_agent_runtime.call_args[1]
        payload = json.loads(call_kwargs["payload"])
        assert payload["method"] == "agent/card"

    def test_discover_agent_returns_none_on_failure(self, mock_boto3_client):
        """Returns None if agent card fetch fails."""
        from tools.discovery import discover_agent

        mock_boto3_client.invoke_agent_runtime.side_effect = Exception("Connection refused")

        result = discover_agent(
            "arn:aws:bedrock-agentcore:eu-west-1:548129671048:runtime/nonexistent"
        )

        assert result is None

    def test_discover_agent_returns_none_on_invalid_response(self, mock_boto3_client):
        """Returns None if response is not valid JSON."""
        from tools.discovery import discover_agent

        mock_boto3_client.invoke_agent_runtime.return_value = {
            "response": MagicMock(
                read=MagicMock(return_value=b"not json")
            )
        }

        result = discover_agent(
            "arn:aws:bedrock-agentcore:eu-west-1:548129671048:runtime/test"
        )

        assert result is None

    def test_verify_agents_checks_both_downstream_agents(self, mock_boto3_client):
        """verify_agents checks both collector and publisher are reachable."""
        from tools.discovery import verify_agents

        collector_card = {
            "name": "NewsCollector",
            "version": "0.1.0",
            "skills": [{"id": "content-collection", "name": "Content Collection"}],
        }
        publisher_card = {
            "name": "NewsPublisher",
            "version": "0.1.0",
            "skills": [{"id": "editorial-publishing", "name": "Editorial Publishing"}],
        }

        mock_boto3_client.invoke_agent_runtime.side_effect = [
            {"response": MagicMock(read=MagicMock(return_value=json.dumps(collector_card).encode()))},
            {"response": MagicMock(read=MagicMock(return_value=json.dumps(publisher_card).encode()))},
        ]

        result = verify_agents()

        assert result["collector"]["available"] is True
        assert result["collector"]["name"] == "NewsCollector"
        assert result["publisher"]["available"] is True
        assert result["publisher"]["name"] == "NewsPublisher"

    def test_verify_agents_reports_unavailable_agent(self, mock_boto3_client):
        """verify_agents reports agent as unavailable if discovery fails."""
        from tools.discovery import verify_agents

        collector_card = {
            "name": "NewsCollector",
            "version": "0.1.0",
            "skills": [],
        }

        mock_boto3_client.invoke_agent_runtime.side_effect = [
            {"response": MagicMock(read=MagicMock(return_value=json.dumps(collector_card).encode()))},
            Exception("Publisher not deployed"),
        ]

        result = verify_agents()

        assert result["collector"]["available"] is True
        assert result["publisher"]["available"] is False
