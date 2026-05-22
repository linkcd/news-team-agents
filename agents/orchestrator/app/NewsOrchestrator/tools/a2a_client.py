import json
import re
import uuid
from typing import Optional

import boto3
from botocore.config import Config as BotoConfig

from config import AWS_REGION

DISCOVERY_CONFIG = BotoConfig(read_timeout=120, connect_timeout=10)
COLLECTOR_INVOKE_CONFIG = BotoConfig(read_timeout=600, connect_timeout=10)
PUBLISHER_INVOKE_CONFIG = BotoConfig(read_timeout=300, connect_timeout=10)

_discovery_client = boto3.client("bedrock-agentcore", region_name=AWS_REGION, config=DISCOVERY_CONFIG)
_collector_client = boto3.client("bedrock-agentcore", region_name=AWS_REGION, config=COLLECTOR_INVOKE_CONFIG)
_publisher_client = boto3.client("bedrock-agentcore", region_name=AWS_REGION, config=PUBLISHER_INVOKE_CONFIG)


def get_discovery_client():
    return _discovery_client


def get_collector_client():
    return _collector_client


def get_publisher_client():
    return _publisher_client


def invoke_a2a(client, runtime_arn: str, session_prefix: str, message_parts: list, *, runtime_user_id: Optional[str] = None) -> dict:
    """Send an A2A message/send request and parse the response."""
    session_id = f"{session_prefix}-{uuid.uuid4().hex}"

    a2a_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "message/send",
        "params": {
            "message": {
                "messageId": f"msg-{uuid.uuid4().hex[:12]}",
                "role": "user",
                "parts": message_parts,
            }
        },
    }

    kwargs = {
        "agentRuntimeArn": runtime_arn,
        "runtimeSessionId": session_id,
        "payload": json.dumps(a2a_payload),
    }
    if runtime_user_id:
        kwargs["runtimeUserId"] = runtime_user_id

    try:
        response = client.invoke_agent_runtime(**kwargs)
        body = json.loads(response["response"].read())
    except Exception as e:
        return {"status": "error", "error": str(e)}

    if "error" in body:
        return {"status": "error", "error": body["error"].get("message", str(body["error"]))}

    result = body.get("result", {})
    status = result.get("status", {})

    if status.get("state") == "failed":
        return {"status": "error", "error": _extract_status_message(status)}

    artifacts = result.get("artifacts", [])
    if artifacts:
        for part in artifacts[0].get("parts", []):
            if "data" in part:
                return part["data"]
            if "text" in part:
                return parse_result_from_text(part["text"])

    history = result.get("history", [])
    for message in reversed(history):
        for part in message.get("parts", []):
            if "data" in part:
                return part["data"]
            if "text" in part:
                parsed = parse_result_from_text(part["text"])
                if parsed.get("status") == "success":
                    return parsed

    return {"status": "error", "error": "No artifact data in response"}


def parse_result_from_text(text: str) -> dict:
    """Extract JSON result from the agent's text response."""
    json_match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group(1))
            if "status" in parsed:
                return parsed
        except json.JSONDecodeError:
            pass
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        parsed = json.loads(text[start:end])
        if "status" in parsed:
            return parsed
    except (ValueError, json.JSONDecodeError):
        pass
    return {"status": "error", "error": "Could not parse result from text response"}


def _extract_status_message(status: dict) -> str:
    message = status.get("message", {})
    parts = message.get("parts", [])
    for part in parts:
        if "text" in part:
            return part["text"]
    return "Unknown error"
