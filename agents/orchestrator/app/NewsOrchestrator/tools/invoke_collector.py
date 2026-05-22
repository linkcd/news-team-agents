from strands import tool

from config import COLLECTOR_RUNTIME_ARN
from tools.a2a_client import get_collector_client, invoke_a2a


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
    return invoke_a2a(
        client=get_collector_client(),
        runtime_arn=COLLECTOR_RUNTIME_ARN,
        session_prefix="collector-session",
        message_parts=[{"data": {"task": task_config}}],
    )
