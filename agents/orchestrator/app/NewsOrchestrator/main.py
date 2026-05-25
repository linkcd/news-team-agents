from strands.multiagent.a2a import StrandsA2AExecutor
from bedrock_agentcore.runtime import serve_a2a

from agent import create_agent
from ping_health import make_ping_handler

agent = create_agent()
ping_handler = make_ping_handler(agent._invocation_lock)

if __name__ == "__main__":
    serve_a2a(
        StrandsA2AExecutor(agent, enable_a2a_compliant_streaming=False),
        ping_handler=ping_handler,
    )
