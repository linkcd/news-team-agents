from strands import Agent
from strands.models import BedrockModel

from config import MODEL_ID

# TODO: Import tools once implemented
# from tools import read_from_s3, read_repo_file, format_post, merge_posts, git_clone, git_commit_and_push

SYSTEM_PROMPT = """You are an editorial and publishing agent. You receive publishing tasks and execute them.

Your capabilities will be defined when tools are implemented.
"""


def create_agent() -> Agent:
    model = BedrockModel(model_id=MODEL_ID)
    return Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[],
    )
