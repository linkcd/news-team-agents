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
