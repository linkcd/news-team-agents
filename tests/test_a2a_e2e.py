# Copyright 2026 news-agent contributors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""End-to-end A2A integration tests covering all 3 agents.

Run: cd tests && uv run --with "boto3>=1.43.0" --with "pytest>=8.0" --python 3.12 -- python -m pytest test_a2a_e2e.py -v
"""
import json
import os
import uuid
from datetime import datetime, timezone

import boto3
import pytest

AWS_REGION = os.environ.get("AWS_REGION", "eu-west-1")
COLLECTOR_RUNTIME_ARN = os.environ.get("COLLECTOR_RUNTIME_ARN", "")
PUBLISHER_RUNTIME_ARN = os.environ.get("PUBLISHER_RUNTIME_ARN", "")
ORCHESTRATOR_RUNTIME_ARN = os.environ.get("ORCHESTRATOR_RUNTIME_ARN", "")
pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_TESTS") != "true"
    or not all((COLLECTOR_RUNTIME_ARN, PUBLISHER_RUNTIME_ARN, ORCHESTRATOR_RUNTIME_ARN)),
    reason="Explicit live-test opt-in and private runtime ARN configuration are required",
)


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
