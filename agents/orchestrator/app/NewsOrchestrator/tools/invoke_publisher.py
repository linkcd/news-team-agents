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

from strands import tool

from config import PUBLISHER_RUNTIME_ARN
from tools import a2a_client


@tool
def invoke_publisher(task_config: dict) -> dict:
    """Invoke the Publisher agent via A2A protocol with streaming.

    Sends a task configuration to the Publisher runtime using the strands A2AAgent
    client with SigV4 authentication and SSE streaming.

    Args:
        task_config: Publishing task configuration (type, source, template, output, etc.).

    Returns:
        Dict with 'status' ('success'/'error') and either the publish result or error message.
    """
    return a2a_client.invoke_a2a(PUBLISHER_RUNTIME_ARN, task_config, runtime_user_id="orchestrator")
