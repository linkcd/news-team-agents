"""End-to-end A2A integration tests covering all 3 agents.

Run: cd tests && uv run --with "boto3>=1.43.0" --with "pytest>=8.0" --python 3.12 -- python -m pytest test_a2a_e2e.py -v
"""
import json
import uuid
from datetime import datetime, timezone

import boto3
import pytest

AWS_REGION = "eu-west-1"
COLLECTOR_RUNTIME_ARN = "arn:aws:bedrock-agentcore:eu-west-1:548129671048:runtime/newscollector_NewsCollector-EhrHzp4oFi"
PUBLISHER_RUNTIME_ARN = "arn:aws:bedrock-agentcore:eu-west-1:548129671048:runtime/newspublisher_NewsPublisher-OZnqGfD4D2"
ORCHESTRATOR_RUNTIME_ARN = "arn:aws:bedrock-agentcore:eu-west-1:548129671048:runtime/newsorchestrator_NewsOrchestrator-255wUd9gwc"


@pytest.fixture
def agentcore_client():
    return boto3.client("bedrock-agentcore", region_name=AWS_REGION)


def send_a2a_message(client, runtime_arn, data):
    session_id = f"e2e-test-session-{uuid.uuid4().hex}"
    payload = {
        "jsonrpc": "2.0", "id": 1, "method": "message/send",
        "params": {"message": {"messageId": f"msg-{uuid.uuid4().hex[:12]}", "role": "user", "parts": [{"data": data}]}}
    }
    response = client.invoke_agent_runtime(
        agentRuntimeArn=runtime_arn, runtimeSessionId=session_id, payload=json.dumps(payload),
    )
    return json.loads(response["response"].read())


class TestAgentCardDiscovery:
    def test_collector_agent_card(self, agentcore_client):
        resp = agentcore_client.get_agent_card(agentRuntimeArn=COLLECTOR_RUNTIME_ARN)
        card = resp["agentCard"] if isinstance(resp["agentCard"], dict) else json.loads(resp["agentCard"])
        assert card.get("name") is not None
        assert "skills" in card

    def test_publisher_agent_card(self, agentcore_client):
        resp = agentcore_client.get_agent_card(agentRuntimeArn=PUBLISHER_RUNTIME_ARN)
        card = resp["agentCard"] if isinstance(resp["agentCard"], dict) else json.loads(resp["agentCard"])
        assert card.get("name") is not None

    def test_orchestrator_agent_card(self, agentcore_client):
        resp = agentcore_client.get_agent_card(agentRuntimeArn=ORCHESTRATOR_RUNTIME_ARN)
        card = resp["agentCard"] if isinstance(resp["agentCard"], dict) else json.loads(resp["agentCard"])
        assert card.get("name") is not None


class TestCollectorA2A:
    def test_collector_accepts_a2a_message(self, agentcore_client):
        task_config = {"task": {"task_id": f"e2e-{uuid.uuid4().hex[:8]}", "sources": []}}
        response = send_a2a_message(agentcore_client, COLLECTOR_RUNTIME_ARN, task_config)
        assert response is not None
        if "error" in response:
            assert response["error"].get("code") != -32601

class TestOrchestratorA2A:
    def test_orchestrator_accepts_trigger(self, agentcore_client):
        trigger = {"trigger": "scheduled", "run_time": "2099-12-31T23:00:00Z"}
        response = send_a2a_message(agentcore_client, ORCHESTRATOR_RUNTIME_ARN, trigger)
        assert response is not None
        if "error" in response:
            assert response["error"].get("code") != -32601
