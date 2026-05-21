import json
import uuid
from typing import Optional

import boto3
from strands import tool

from config import AWS_REGION, COLLECTOR_RUNTIME_ARN, PUBLISHER_RUNTIME_ARN


def discover_agent(runtime_arn: str) -> Optional[dict]:
    """Fetch an agent's Agent Card via A2A agent/card method.

    Args:
        runtime_arn: The AgentCore runtime ARN to discover.

    Returns:
        The agent card dict if successful, None otherwise.
    """
    client = boto3.client("bedrock-agentcore", region_name=AWS_REGION)

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "agent/card",
    }

    try:
        response = client.invoke_agent_runtime(
            agentRuntimeArn=runtime_arn,
            runtimeSessionId=f"discovery-session-{uuid.uuid4().hex}",
            payload=json.dumps(payload),
        )
        body = response["response"].read()
        return json.loads(body)
    except Exception:
        return None


@tool
def verify_agents() -> dict:
    """Verify that both downstream agents (Collector, Publisher) are discoverable via A2A Agent Card.

    Call this at the start of every workflow run to confirm agents are reachable.

    Returns:
        Dict with 'collector' and 'publisher' keys, each containing
        'available' (bool), 'name', and 'skills' if available.
    """
    result = {}

    for name, arn in [("collector", COLLECTOR_RUNTIME_ARN), ("publisher", PUBLISHER_RUNTIME_ARN)]:
        card = discover_agent(arn)
        if card:
            result[name] = {
                "available": True,
                "name": card.get("name", "Unknown"),
                "skills": card.get("skills", []),
            }
        else:
            result[name] = {"available": False}

    return result
