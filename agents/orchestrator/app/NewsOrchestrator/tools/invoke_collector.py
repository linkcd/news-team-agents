import json
import uuid

import boto3
from strands import tool

from config import COLLECTOR_RUNTIME_ARN, AWS_REGION


@tool
def invoke_collector(task_config: dict) -> dict:
    """Invoke the Collector agent via A2A protocol.

    Sends a message/send JSON-RPC request to the Collector runtime with the
    given task configuration. Returns the parsed result or error.

    Args:
        task_config: Collection task configuration (sources, filters, processing, output).

    Returns:
        Dict with 'status' ('success'/'error') and either the collection result or error message.
    """
    client = boto3.client("bedrock-agentcore", region_name=AWS_REGION)
    session_id = f"collector-session-{uuid.uuid4().hex}"

    a2a_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "message/send",
        "params": {
            "message": {
                "messageId": f"msg-{uuid.uuid4().hex[:12]}",
                "role": "user",
                "parts": [{"data": {"task": task_config}}],
            }
        },
    }

    try:
        response = client.invoke_agent_runtime(
            agentRuntimeArn=COLLECTOR_RUNTIME_ARN,
            runtimeSessionId=session_id,
            payload=json.dumps(a2a_payload),
        )
        body = json.loads(response["response"].read())
    except Exception as e:
        return {"status": "error", "error": str(e)}

    if "error" in body:
        return {"status": "error", "error": body["error"].get("message", str(body["error"]))}

    result = body.get("result", {})
    status = result.get("status", {})

    if status.get("state") == "failed":
        error_msg = _extract_status_message(status)
        return {"status": "error", "error": error_msg}

    artifacts = result.get("artifacts", [])
    if artifacts:
        for part in artifacts[0].get("parts", []):
            if "data" in part:
                return part["data"]

    return {"status": "error", "error": "No artifact data in response"}


def _extract_status_message(status: dict) -> str:
    message = status.get("message", {})
    parts = message.get("parts", [])
    for part in parts:
        if "text" in part:
            return part["text"]
    return "Unknown error"
