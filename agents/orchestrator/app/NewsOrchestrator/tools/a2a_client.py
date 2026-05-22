import json
import logging
import re
from typing import Optional
from uuid import uuid4

import boto3
import httpx
from a2a.client import ClientConfig
from bedrock_agentcore.runtime import build_runtime_url
from botocore.config import Config as BotoConfig
from strands.agent.a2a_agent import A2AAgent

from config import AWS_REGION
from tools.sigv4_auth import SigV4HTTPXAuth

logger = logging.getLogger(__name__)

DISCOVERY_CONFIG = BotoConfig(read_timeout=120, connect_timeout=10)

_discovery_client = None


def get_discovery_client():
    """Get a boto3 client for fast discovery pings (blocking, not streaming)."""
    global _discovery_client
    if _discovery_client is None:
        _discovery_client = boto3.client("bedrock-agentcore", region_name=AWS_REGION, config=DISCOVERY_CONFIG)
    return _discovery_client


_STREAMING_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0)


def invoke_a2a(runtime_arn: str, task_config: dict, *, runtime_user_id: Optional[str] = None) -> dict:
    """Invoke a remote agent via A2A streaming and return the result."""
    endpoint = build_runtime_url(runtime_arn, AWS_REGION)
    session_id = str(uuid4())

    boto_session = boto3.Session()
    credentials = boto_session.get_credentials().get_frozen_credentials()
    auth = SigV4HTTPXAuth(credentials, "bedrock-agentcore", AWS_REGION)

    headers = {"X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id}
    if runtime_user_id:
        headers["X-Amzn-Bedrock-AgentCore-Runtime-User-Id"] = runtime_user_id

    client_config = ClientConfig(
        httpx_client=httpx.AsyncClient(
            auth=auth,
            timeout=_STREAMING_TIMEOUT,
            headers=headers,
        ),
    )
    agent = A2AAgent(endpoint=endpoint, client_config=client_config)

    prompt = json.dumps({"task": task_config})

    try:
        result = agent(prompt)
    except Exception as e:
        logger.error("A2A invocation failed: %s", e)
        return {"status": "error", "error": str(e)}

    return _parse_agent_result(result)


def _parse_agent_result(result) -> dict:
    """Extract the JSON result from AgentResult message content."""
    content = result.message.get("content", [])

    # First pass: check each content block individually
    for block in content:
        text = block.get("text", "")
        if not text:
            continue
        parsed = _extract_json(text)
        if parsed and "status" in parsed:
            return parsed

    # Second pass: concatenate all text blocks (streaming may split across chunks)
    all_text = " ".join(block.get("text", "") for block in content if block.get("text"))
    if all_text:
        parsed = _extract_json(all_text)
        if parsed and "status" in parsed:
            return parsed

    # Last resort: try str(result) which includes the full agent output
    result_str = str(result)
    if result_str:
        parsed = _extract_json(result_str)
        if parsed and "status" in parsed:
            return parsed

    return {"status": "error", "error": "No structured result in agent response"}


def _extract_json(text: str) -> Optional[dict]:
    """Extract JSON dict from text (fenced or raw)."""
    json_match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        return json.loads(text[start:end])
    except (ValueError, json.JSONDecodeError):
        return None
