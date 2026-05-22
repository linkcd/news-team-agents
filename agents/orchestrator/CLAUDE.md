# Orchestrator Agent

Workflow coordination agent for the Norwegian news collection and publishing pipeline. Manages the Collector and Publisher agents via A2A protocol to produce daily news blog posts.

## Purpose

Domain-specific orchestration agent. Coordinates the news collection workflow by invoking the Collector and Publisher agents with the correct parameters for Norwegian news. Handles retry logic and run-level decisions.

This agent is NOT general-purpose — it encodes the specific business logic for the Norwegian news pipeline (sources, schedule awareness, quality decisions).

## Deployment

- **Runtime ID**: `newsorchestrator_NewsOrchestrator-255wUd9gwc`
- **ARN**: `arn:aws:bedrock-agentcore:eu-west-1:548129671048:runtime/newsorchestrator_NewsOrchestrator-255wUd9gwc`
- **Protocol**: A2A (Agent-to-Agent) via `serve_a2a(StrandsA2AExecutor(agent, enable_a2a_compliant_streaming=True))`
- **Region**: eu-west-1

## Interface

Receives A2A `message/send` requests (JSON-RPC 2.0). The trigger event is passed as a `data` Part. Returns an A2A task with artifacts containing the run result.

### Input (trigger event delivered via A2A message Part, from Lambda)

```json
{
  "trigger": "scheduled",
  "run_time": "2026-05-21T11:00:00Z"
}
```

### Output (returned to Lambda)

Success with publish:
```json
{
  "status": "success",
  "run_time": "2026-05-21T11:00:00Z",
  "collection": {
    "new_topics": 3,
    "updated_topics": 1,
    "data_key": "collections/2026-05-21/1100-norway-news.json"
  },
  "publish": {
    "action": "merge_update",
    "file_path": "source/_posts/20260521-norway.md",
    "commit_sha": "abc123",
    "total_items_in_post": 8
  }
}
```

Success without publish (nothing new):
```json
{
  "status": "success",
  "run_time": "2026-05-21T23:00:00Z",
  "collection": {
    "new_topics": 0,
    "updated_topics": 0
  },
  "publish": null
}
```

Failure (after retry):
```json
{
  "status": "failed",
  "run_time": "2026-05-21T11:00:00Z",
  "error": "Collector failed after 1 retry: timeout",
  "collection": null,
  "publish": null
}
```

## Workflow Logic

```
1. Determine run parameters:
   - date = today (UTC)
   - run_time = current time
   - post_path = source/_posts/YYYYMMDD-norway.md
   - Determine if today's post already exists (for publish_new vs merge_update decision)

2. Build Collector task config:
   - task_id: "norway-news-{date}-{HHMM}"
   - sources: 11 Norwegian RSS feeds (from config)
   - filters:
     - time_window_hours: 6
     - dedup_source: github_file (blog post for today, if exists)
   - processing:
     - extract_full_content: true
     - consolidate_topics: true
     - summarize: true, 200 words
     - translate_to: ["zh"]
     - preserve_original_names: true
   - output: s3_bucket + key prefix

3. Invoke Collector:
   - On error: retry once. On second error: report failure, done.
   - On success: check new_topics + updated_topics count.

4. Decide publish:
   - If new_topics == 0 AND updated_topics == 0: done (nothing to publish)
   - If new_topics > 0 OR updated_topics > 0: proceed to publish

5. Build Publisher task config:
   - If first run of day (no existing post): type = "publish_new"
   - If post exists: type = "merge_update"
   - source: S3 data_key from Collector result
   - template: "norway_daily"
   - merge_strategy: append new, replace+changelog for updates, renumber, regenerate summary
   - editorial: 300-word day summary

6. Invoke Publisher:
   - On error: report failure (no retry for Publisher — git state may be inconsistent)
   - On success: return run summary

7. Return result.
```

## Configuration

Norwegian news sources (hardcoded in this agent's config):

| Source | Feed URL | Category |
|--------|----------|----------|
| NRK Norge | https://www.nrk.no/norge/toppsaker.rss | domestic |
| NRK Oslo | https://www.nrk.no/stor-oslo/toppsaker.rss | domestic |
| VG Innenriks | https://www.vg.no/rss/feed/?categories=1069 | domestic |
| TV2 Innenriks | https://www.tv2.no/rss/nyheter/innenriks | domestic |
| Dagbladet | https://www.dagbladet.no/?lab_viewport=rss | domestic |
| Aftenposten | https://www.aftenposten.no/rss/ | domestic |
| Dagsavisen | https://www.dagsavisen.no/rss | domestic |
| NRK Urix | https://www.nrk.no/urix/toppsaker.rss | international |
| VG Utenriks | https://www.vg.no/rss/feed/?categories=1070 | international |
| TV2 Utenriks | https://www.tv2.no/rss/nyheter/utenriks | international |
| E24 | http://e24.no/rss2/ | business |

Blog target:
- Repo: `claw-lu/hexo-blog` (public)
- Post path: `source/_posts/YYYYMMDD-norway.md`
- S3 bucket: `news-agent-data`

## Tools

| Tool | Purpose |
|------|---------|
| `invoke_collector(task_config)` | Invokes Collector via strands `A2AAgent` with SSE streaming and SigV4 auth. Parses JSON result from agent response text. |
| `invoke_publisher(task_config)` | Invokes Publisher via strands `A2AAgent` with SSE streaming, SigV4 auth, and `runtime_user_id="orchestrator"` (required for AgentCore Identity). |
| `verify_agents()` | Lightweight reachability check via boto3 `invoke_agent_runtime` (non-streaming ping). |

Both invoke tools use the shared `a2a_client.invoke_a2a()` which:
1. Builds the runtime URL via `bedrock_agentcore.runtime.build_runtime_url`
2. Signs requests with `SigV4HTTPXAuth` (custom `httpx.Auth` in `tools/sigv4_auth.py`)
3. Sends the task config as a prompt to `A2AAgent` with SSE streaming
4. Parses the structured JSON result from the agent's text response

## Environment Variables

- `COLLECTOR_RUNTIME_ARN` - ARN of the Collector AgentCore runtime
- `PUBLISHER_RUNTIME_ARN` - ARN of the Publisher AgentCore runtime
- `S3_BUCKET` - Name of the intermediate data bucket
- `AWS_REGION` - AWS region (default: eu-west-1)
- `MODEL_ID` - Bedrock model ID (default: global.anthropic.claude-sonnet-4-6)

## IAM Permissions Required

- `bedrock-agentcore:InvokeAgentRuntime` on Collector and Publisher
- `bedrock:InvokeModel` (for reasoning/decisions)

## Timeout Policy

- HTTP read timeout: 120s per SSE event (streaming resets this on each event, so long-running tasks stay alive)
- On error: retry once for Collector, no retry for Publisher (git state may be inconsistent)

## Development

```bash
agentcore dev                    # local development (requires Collector + Publisher to be deployed)
python3 -m pytest tests/ -v      # run unit tests (20 tests)
agentcore deploy -y              # deploy to AWS
agentcore invoke '{"trigger": "scheduled", "run_time": "2026-05-21T11:00:00Z"}' --stream  # invoke
```

## What This Agent Does NOT Do

- Does not fetch RSS feeds (Collector's job)
- Does not extract or consolidate articles (Collector's job)
- Does not format blog posts (Publisher's job)
- Does not handle hexo deploy (GitHub Action's job)
- Does not store secrets (Publisher reads them)
- Does not pass bulk article data through its context (S3 handles data flow)
- Does not match topics or determine content similarity (Collector's job)
