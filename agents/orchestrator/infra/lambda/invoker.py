"""Submit one scheduled invocation without automatic duplicate submissions."""
import json
import os
import uuid
from datetime import datetime, timezone

import boto3
from botocore.config import Config
from botocore.exceptions import ReadTimeoutError


def handler(event, context):
    client = boto3.client(
        "bedrock-agentcore", region_name=os.environ["AWS_REGION"],
        config=Config(read_timeout=10, connect_timeout=10, retries={"total_max_attempts": 1}),
    )
    run_time = event.get("time") or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    session = f"schedule-{uuid.uuid4()}"
    payload = {
        "jsonrpc": "2.0", "id": 1, "method": "message/send",
        "params": {"message": {
            "messageId": str(uuid.uuid4()), "role": "user",
            "parts": [{"kind": "data", "data": {"trigger": "scheduled", "run_time": run_time}}],
        }},
    }
    status = "submitted"
    try:
        client.invoke_agent_runtime(
            agentRuntimeArn=os.environ["ORCHESTRATOR_RUNTIME_ARN"],
            runtimeSessionId=session, payload=json.dumps(payload),
        )
    except ReadTimeoutError:
        status = "submission_uncertain"
    result = {"status": status, "run_time": run_time, "session_id": session}
    print(json.dumps(result))
    return result
