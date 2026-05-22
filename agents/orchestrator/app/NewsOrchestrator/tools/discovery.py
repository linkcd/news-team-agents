import json
import uuid
from concurrent.futures import ThreadPoolExecutor

from strands import tool

from config import AWS_REGION, COLLECTOR_RUNTIME_ARN, PUBLISHER_RUNTIME_ARN
from tools.a2a_client import get_discovery_client


def _check_agent_reachable(runtime_arn: str) -> dict:
    """Check if an agent runtime is reachable by sending a lightweight A2A message/send."""
    client = get_discovery_client()

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "message/send",
        "params": {
            "message": {
                "messageId": f"ping-{uuid.uuid4().hex[:12]}",
                "role": "user",
                "parts": [{"data": {"ping": True}}],
            }
        },
    }

    try:
        response = client.invoke_agent_runtime(
            agentRuntimeArn=runtime_arn,
            runtimeSessionId=f"discovery-{uuid.uuid4().hex}",
            payload=json.dumps(payload),
        )
        body = json.loads(response["response"].read())
        if "error" in body:
            return {"available": False, "error": body["error"].get("message", "unknown")}
        return {"available": True}
    except Exception as e:
        return {"available": False, "error": str(e)}


@tool
def discover_agent(runtime_arn: str) -> dict:
    """Check if an agent runtime is reachable via A2A message/send.

    Args:
        runtime_arn: The AgentCore runtime ARN to check.

    Returns:
        Dict with 'available' (bool) and optionally 'error' if unavailable.
    """
    return _check_agent_reachable(runtime_arn)


@tool
def verify_agents() -> dict:
    """Verify that both downstream agents (Collector, Publisher) are reachable.

    Call this at the start of every workflow run to confirm agents are reachable.

    Returns:
        Dict with 'collector' and 'publisher' keys, each containing
        'available' (bool) and optionally 'error'.
    """
    with ThreadPoolExecutor(max_workers=2) as pool:
        fc = pool.submit(_check_agent_reachable, COLLECTOR_RUNTIME_ARN)
        fp = pool.submit(_check_agent_reachable, PUBLISHER_RUNTIME_ARN)
        return {"collector": fc.result(), "publisher": fp.result()}
