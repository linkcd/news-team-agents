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

from config import COLLECTOR_RUNTIME_ARN
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
    return a2a_client.invoke_a2a(COLLECTOR_RUNTIME_ARN, task_config)
