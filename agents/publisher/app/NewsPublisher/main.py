from strands.multiagent.a2a import StrandsA2AExecutor
from bedrock_agentcore.runtime import serve_a2a

from agent import create_agent

agent = create_agent()

if __name__ == "__main__":
    serve_a2a(StrandsA2AExecutor(agent, enable_a2a_compliant_streaming=True))
