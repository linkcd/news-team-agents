import os

MODEL_ID = os.environ.get("MODEL_ID", "global.anthropic.claude-sonnet-4-6")

COLLECTOR_RUNTIME_ARN = os.environ.get(
    "COLLECTOR_RUNTIME_ARN",
    "arn:aws:bedrock-agentcore:eu-west-1:<AWS_ACCOUNT_ID>:runtime/<RUNTIME_ID>",
)
PUBLISHER_RUNTIME_ARN = os.environ.get("PUBLISHER_RUNTIME_ARN", "")

S3_BUCKET = os.environ.get("S3_BUCKET", "news-agent-data-example")
