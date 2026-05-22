from strands import tool

from config import PUBLISHER_RUNTIME_ARN
from tools.a2a_client import get_publisher_client, invoke_a2a


@tool
def invoke_publisher(task_config: dict) -> dict:
    """Invoke the Publisher agent via A2A protocol.

    Sends a message/send JSON-RPC request to the Publisher runtime with the
    given task configuration. Returns the parsed result or error.

    Args:
        task_config: Publishing task configuration (type, source, template, output, etc.).

    Returns:
        Dict with 'status' ('success'/'error') and either the publish result or error message.
    """
    return invoke_a2a(
        client=get_publisher_client(),
        runtime_arn=PUBLISHER_RUNTIME_ARN,
        session_prefix="publisher-session",
        message_parts=[{"data": {"task": task_config}}],
        runtime_user_id="orchestrator",
    )
