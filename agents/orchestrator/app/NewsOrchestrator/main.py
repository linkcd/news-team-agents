import json

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from agent import create_agent

app = BedrockAgentCoreApp()
log = app.logger
_agent = None


def get_agent():
    global _agent
    if _agent is None:
        _agent = create_agent()
    return _agent


@app.entrypoint
async def invoke(payload, context=None):
    """AgentCore Runtime entrypoint. Receives trigger event, orchestrates collection and publishing."""
    log.info("Invoking NewsOrchestrator agent...")
    agent = get_agent()

    prompt = f"""Execute the orchestration workflow with the following trigger:

{json.dumps(payload, indent=2)}

Follow your workflow steps and return the result."""

    stream = agent.stream_async(prompt)
    async for event in stream:
        if "data" in event and isinstance(event["data"], str):
            yield event["data"]


if __name__ == "__main__":
    app.run()
