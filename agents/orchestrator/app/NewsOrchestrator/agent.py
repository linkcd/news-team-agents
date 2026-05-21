from strands import Agent
from strands.models import BedrockModel

from config import MODEL_ID

# TODO: Import tools once implemented
# from tools import invoke_collector, invoke_publisher

SYSTEM_PROMPT = """You are a workflow orchestration agent for Norwegian news collection and publishing.

Your capabilities will be defined when tools are implemented.
"""


def create_agent() -> Agent:
    model = BedrockModel(model_id=MODEL_ID)
    return Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[],
    )
