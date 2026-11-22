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

import json
from datetime import datetime, timezone

import boto3
from strands import tool

from config import COLLECTOR_RUNTIME_ARN, AWS_REGION
from tools import a2a_client


@tool
def invoke_collector(task_config: dict) -> dict:
    """Invoke the Collector agent via A2A protocol with streaming.

    Sends a task configuration to the Collector runtime using the strands A2AAgent
    client with SigV4 authentication and SSE streaming. Each streaming event resets
    the connection idle timeout, allowing long-running collections.

    Args:
        task_config: Collection task configuration (sources, filters, processing, output).

    Returns:
        Dict with 'status' ('success'/'error') and either the collection result or error message.
    """
    started = datetime.now(timezone.utc).replace(microsecond=0)
    result = a2a_client.invoke_a2a(COLLECTOR_RUNTIME_ARN, task_config, runtime_user_id="orchestrator")
    if result.get("error") != "No structured result in agent response":
        return result
    output = task_config.get("output", {})
    if not task_config.get("task_id") or not output.get("s3_bucket") or not output.get("s3_key_prefix"):
        return result

    # A successful collection can be followed by a prose-only LLM response.
    # Recover a verified receipt inside Python; bulk content never enters the
    # Orchestrator model context. Stale or unrelated objects cannot imply success.
    key = f"{output['s3_key_prefix']}{task_config['task_id']}.json"
    try:
        obj = boto3.client("s3", region_name=AWS_REGION).get_object(Bucket=output["s3_bucket"], Key=key)
        body = obj["Body"]
        try:
            data = json.loads(body.read())
        finally:
            body.close()
        if obj["LastModified"] < started or data.get("task_id") != task_config["task_id"]:
            raise ValueError("Collection output is stale or belongs to another task")
        new, updated = data["new_items"], data["updated_items"]
        if not isinstance(new, list) or not isinstance(updated, list):
            raise ValueError("Invalid collection item lists")
        summary = dict(data.get("metadata") or {})
        summary.update({"grouped_into_new_topics": len(new), "matched_to_existing_topics": len(updated)})
        return {"status": "success", "task_id": task_config["task_id"], "data_key": key,
                "summary": summary, "recovered_from_s3": True}
    except Exception as exc:
        return {"status": "error", "error": f"Collection output could not be verified: {exc}"}
