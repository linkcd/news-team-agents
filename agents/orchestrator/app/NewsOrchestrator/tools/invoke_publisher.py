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
    return a2a_client.invoke_a2a(PUBLISHER_RUNTIME_ARN, task_config)
