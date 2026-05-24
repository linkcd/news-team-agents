"""Direct Bedrock API test for merge_update.

Tests whether the model can produce a merged markdown post given:
- The publisher system prompt (merge_update section)
- Real existing post (17 items, ~22KB)
- Real new S3 data (15 new items, ~24KB)

This rules out whether the problem is the model output size/timeout
or something else in the Strands/A2A pipeline.
"""
import json
import time

import boto3

MODEL_ID = "global.anthropic.claude-sonnet-4-6"
EXISTING_POST_PATH = "/tmp/existing_post.md"
NEW_ITEMS_PATH = "/tmp/new_items.json"

SYSTEM_PROMPT = """You are an editorial and publishing agent. You receive a merge_update task.

You are ADDING new content to an existing post, NOT replacing it.

Given:
- EXISTING POST: the full markdown of today's blog post (your BASE document)
- NEW ITEMS: JSON with new_items[] to add

Produce the merged markdown following these STRICT rules:
a. Start from the EXISTING post as your base. Every single existing item MUST appear in your output with its title, summary, sources, and links UNCHANGED.
b. For each item in new_items: INSERT it at the TOP of its matching section (domestic→国内新闻, international→国际新闻, business→财经新闻), BEFORE the existing items.
c. Renumber all ### items sequentially (1, 2, 3...) across all sections.
d. Rewrite ONLY the "## 今日综述" section to cover ALL topics (old + new combined, ~300 words).
e. Update the "updated:" field in frontmatter to 2026-05-25 11:00:00. Do NOT change "date:".
f. Place "*最后更新: 11:00 UTC*" right after the 今日综述 section, BEFORE "<!-- more -->".
g. Keep "*新闻来源: ...*" in the footer (updated to include all sources).

SELF-CHECK: The existing post has N items. new_items has M entries. Your output MUST have N+M items.

Output ONLY the merged markdown. Nothing else."""


def test_bedrock_merge():
    with open(EXISTING_POST_PATH, "r") as f:
        existing_post = f.read()

    with open(NEW_ITEMS_PATH, "r") as f:
        new_data = json.load(f)

    new_items_json = json.dumps(new_data["new_items"], ensure_ascii=False, indent=2)

    user_message = f"""## EXISTING POST (17 items):

{existing_post}

## NEW ITEMS (15 items, JSON):

{new_items_json}

Merge the new items into the existing post following the rules in your system prompt. Output the full merged markdown."""

    print(f"System prompt: {len(SYSTEM_PROMPT)} chars")
    print(f"User message: {len(user_message)} chars")
    print(f"Total input: ~{(len(SYSTEM_PROMPT) + len(user_message)) // 1000}KB")
    print()

    from botocore.config import Config as BotoConfig
    client = boto3.client(
        "bedrock-runtime",
        region_name="eu-west-1",
        config=BotoConfig(read_timeout=600, connect_timeout=10),
    )

    print("Calling Bedrock converse_stream API...")
    start = time.time()

    response = client.converse_stream(
        modelId=MODEL_ID,
        system=[{"text": SYSTEM_PROMPT}],
        messages=[
            {"role": "user", "content": [{"text": user_message}]}
        ],
        inferenceConfig={
            "maxTokens": 32000,
        },
    )

    # Collect streamed output
    output = ""
    usage = {}
    stop_reason = ""
    for event in response["stream"]:
        if "contentBlockDelta" in event:
            output += event["contentBlockDelta"]["delta"].get("text", "")
        elif "metadata" in event:
            usage = event["metadata"].get("usage", {})
        elif "messageStop" in event:
            stop_reason = event["messageStop"].get("stopReason", "")

    elapsed = time.time() - start
    print(f"Response received in {elapsed:.1f}s")

    print(f"Stop reason: {stop_reason}")
    print(f"Input tokens: {usage['inputTokens']}")
    print(f"Output tokens: {usage['outputTokens']}")
    print(f"Output length: {len(output)} chars")
    print()

    # Count items in output
    item_count = output.count("### ")
    print(f"Items in output: {item_count} (expected: 32 = 17 existing + 15 new)")

    if stop_reason == "end_turn" and item_count >= 30:
        print("\n✅ SUCCESS: Model can produce merged output within limits")
    elif stop_reason == "max_tokens":
        print("\n❌ FAILED: Hit max_tokens limit — output too large")
    else:
        print(f"\n⚠️  PARTIAL: stop_reason={stop_reason}, items={item_count}")

    # Save output for inspection
    with open("/tmp/merged_output.md", "w") as f:
        f.write(output)
    print("Output saved to /tmp/merged_output.md")


if __name__ == "__main__":
    test_bedrock_merge()
