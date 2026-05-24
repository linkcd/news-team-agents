# Plan: Job Reporting + Self-Correction for News-Agent Pipeline

**Status**: Planned (not yet implemented)  
**Created**: 2026-05-23

## Context

The news pipeline runs 4x/day via EventBridge → Lambda → Orchestrator → Collector → Publisher. Today there is **no visibility** into whether runs succeed or fail, and **no feedback loop** — if an RSS feed goes down for days, the system keeps retrying it blindly. This plan addresses:

1. **Reporting**: Use CloudWatch custom metrics + the built-in GenAI/Bedrock dashboard to see success rates at a glance
2. **Self-correction**: Agents report richer errors and track source health over time; errors surface clearly (e.g., "Dagsavisen has not worked for 3 days") but the system still attempts all sources

---

## Design Principles

- **CloudWatch for observability**: Custom metric `NewsAgent/RunCompleted` with `Status` dimension, viewable in the CloudWatch console alongside built-in Bedrock metrics. No email/SNS/Slack.
- **S3 as run log**: Structured run results persisted to S3 for debugging and history.
- **LLM-as-decision-maker**: Tools provide rich error signals; the LLM reasons about retries within a run.
- **Report, don't exclude**: Sources that fail repeatedly are reported in the run result (visible in the error log), but still attempted each run — no auto-exclusion.

---

## Part 1: Job Reporting

### 1.1 Run Result Persistence (S3)

**New S3 key structure:**
```
s3://news-agent-data-548129671048/
  runs/
    2026-05-23/
      0500-result.json
      1100-result.json
      ...
  health/
    source-status.json      ← accumulated source health (consecutive failures)
  collections/              ← (existing, unchanged)
```

**Run result schema** (`runs/{date}/{HHMM}-result.json`):
```json
{
  "run_id": "norway-news-2026-05-23-1100",
  "run_time": "2026-05-23T11:00:00Z",
  "status": "success | partial | failed",
  "duration_seconds": 85,
  "collection": {
    "status": "success | error",
    "new_topics": 3,
    "updated_topics": 1,
    "data_key": "collections/2026-05-23/1100-norway-news.json",
    "source_results": [
      {"label": "NRK Norge", "status": "success", "articles_found": 5},
      {"label": "Dagsavisen", "status": "error", "error_type": "timeout", "error": "Connection timed out after 30s", "consecutive_failures": 12}
    ]
  },
  "publish": {
    "status": "success | error | skipped",
    "action": "merge_update",
    "commit_sha": "abc123",
    "error": null
  }
}
```

Key: `consecutive_failures` in source_results shows how long a source has been broken (e.g., 12 = broken for 3 days / 12 runs).

### 1.2 CloudWatch Custom Metric

**New tool**: `write_run_result` in orchestrator

Emits:
- **Metric**: `NewsAgent/RunCompleted`
  - Dimensions: `Status` (success/partial/failed), `Pipeline` (norway-news)
  - Value: 1 (count)
- **Metric**: `NewsAgent/SourceErrors`
  - Dimensions: `Pipeline` (norway-news)
  - Value: number of sources that failed in this run

These metrics appear in the CloudWatch console under "Custom Namespaces → NewsAgent" and can be added to any dashboard.

### 1.3 Built-in Bedrock Metrics (already available)

AgentCore runtimes automatically emit metrics to `AWS/Bedrock` namespace:
- `Invocations`, `InvocationLatency`, `InvocationClientErrors`, `InvocationServerErrors`
- `InputTokenCount`, `OutputTokenCount`

Plus OpenTelemetry traces via `aws-opentelemetry-distro` (already in all agents' dependencies).

### 1.4 CDK Changes

Add IAM permission for orchestrator runtime: `cloudwatch:PutMetricData`

---

## Part 2: Self-Correction — Individual Agent Level

### 2.1 Enriched Error Returns (All Tools)

Current pattern: `{"status": "error", "error": "some string"}`

New pattern adds classification:
```json
{
  "status": "error",
  "error": "Connection timed out after 30s",
  "error_type": "timeout",
  "retryable": true,
  "url": "https://www.dagsavisen.no/rss",
  "duration_ms": 30012
}
```

**Error type taxonomy:**
| error_type | retryable | When |
|-----------|-----------|------|
| `timeout` | yes | httpx.TimeoutException |
| `http_5xx` | yes | 500/502/503 responses |
| `http_4xx` | no | 404/403 (permanent) |
| `dns` | yes | DNS resolution failure |
| `parse` | no | RSS malformed, extraction empty |
| `auth` | no | 401/403, token expired |
| `unknown` | yes | Unclassified |

**Files to modify:**
- `agents/collector/app/NewsCollector/tools/rss_fetcher.py` — classify httpx errors
- `agents/collector/app/NewsCollector/tools/article_fetcher.py` — classify extraction failures
- `agents/publisher/app/NewsPublisher/tools/git_ops.py` — classify git errors (auth/conflict/network)
- `agents/orchestrator/app/NewsOrchestrator/tools/a2a_client.py` — classify A2A failures

### 2.2 Collector Self-Correction (Prompt Update)

Add to Collector system prompt:
```
When a tool returns status "error":
- If error_type is "timeout" or "http_5xx": you MAY retry ONCE after processing other sources
- If error_type is "http_4xx" or "parse": skip permanently for this run
- If error_type is "dns": skip (transient, will resolve next run)
- Track all per-source results for reporting back to the Orchestrator in your final result
```

### 2.3 Collector Output Enhancement

Add `source_results` field to Collector's return value:
```json
{
  "status": "success",
  "data_key": "...",
  "source_results": [
    {"label": "NRK Norge", "url": "...", "status": "success", "articles_found": 5},
    {"label": "Dagsavisen", "url": "...", "status": "error", "error_type": "timeout"}
  ]
}
```

### 2.4 Publisher Self-Correction (Prompt Update)

Add git-specific retry guidance:
- `auth` error → stop immediately (token issue, can't fix)
- `conflict` error → attempt pull + retry push once
- `network` error → retry push once

---

## Part 3: Self-Correction — Orchestration Level

### 3.1 Source Health Tracking

**New file**: `agents/orchestrator/app/NewsOrchestrator/tools/source_health.py`

```python
@tool
def get_source_health() -> dict:
    """Read accumulated source health status from S3."""

@tool
def update_source_health(source_results: str) -> dict:
    """Update source health after a run. Increments consecutive_failures for failed sources, resets to 0 for successful ones."""
```

**Health file** (`health/source-status.json`):
```json
{
  "sources": {
    "https://www.dagsavisen.no/rss": {
      "consecutive_failures": 12,
      "last_error": "timeout",
      "last_error_time": "2026-05-23T11:00:00Z",
      "last_success_time": "2026-05-20T23:00:00Z"
    }
  },
  "updated_at": "2026-05-23T11:05:00Z"
}
```

### 3.2 Run History Tool

**New file**: `agents/orchestrator/app/NewsOrchestrator/tools/run_history.py`

```python
@tool
def get_run_history(days_back: int = 1) -> dict:
    """Read recent run results from S3 to understand failure patterns."""
```

### 3.3 Orchestrator Prompt: New Steps

**Add Step 0.5** (between "Verify Agents" and "Determine Run Parameters"):
```
### Step 0.5: Check Source Health
Call get_source_health() to understand which sources have been failing.

Include source health information (consecutive_failures count) in the run result
so it's visible in the run log. Still attempt ALL sources every run — do not exclude
any source. The health data is for visibility only.
```

**Add Step 7.5** (after returning result):
```
### Step 7.5: Update Health and Report
1. Call update_source_health with per-source results from Collector
2. Call write_run_result with full structured run result (always, success or failure)
   - Include consecutive_failures from source health in each source_result entry
   - This writes to S3 AND emits CloudWatch metric
```

### 3.4 Orchestrator: New Tools Registration

```python
tools=[verify_agents, invoke_collector, invoke_publisher,
       get_run_history, get_source_health, update_source_health, write_run_result]
```

---

## Implementation Phases

### Phase A: Reporting
1. Create `tools/run_reporter.py` with `write_run_result` — writes S3 + emits CloudWatch metric
2. Create `tools/run_history.py` with `get_run_history`
3. Create `tools/source_health.py` with `get_source_health` + `update_source_health`
4. Update orchestrator prompt: add Steps 0.5 + 7.5
5. Register all new tools in `agent.py` + `tools/__init__.py`
6. Update CDK: IAM for `cloudwatch:PutMetricData`
7. Tests: `test_run_reporter.py`, `test_run_history.py`, `test_source_health.py`

### Phase B: Enriched Error Context
8. Enhance `rss_fetcher.py` — error classification
9. Enhance `article_fetcher.py` — error classification
10. Enhance `a2a_client.py` — error classification
11. Enhance `git_ops.py` — error classification
12. Update Collector prompt — error handling guidance + source_results output
13. Update Publisher prompt — git retry guidance
14. Tests for each modified tool

### Phase C: Deploy
15. `uv lock` in each modified agent's `app/` directory
16. Deploy: Collector → Publisher → Orchestrator (order matters)
17. Manual invocation test: `agentcore invoke` with trigger payload
18. Check CloudWatch console: custom metric appears under `NewsAgent` namespace
19. Check S3: `runs/` and `health/` objects created

---

## Files to Create

| File | Purpose |
|------|---------|
| `agents/orchestrator/app/NewsOrchestrator/tools/run_reporter.py` | `write_run_result` (S3 + CloudWatch metric) |
| `agents/orchestrator/app/NewsOrchestrator/tools/run_history.py` | `get_run_history` |
| `agents/orchestrator/app/NewsOrchestrator/tools/source_health.py` | `get/update_source_health` |
| `agents/orchestrator/tests/test_run_reporter.py` | |
| `agents/orchestrator/tests/test_run_history.py` | |
| `agents/orchestrator/tests/test_source_health.py` | |

## Files to Modify

| File | Change |
|------|--------|
| `agents/orchestrator/app/NewsOrchestrator/agent.py` | New tools, prompt Steps 0.5 + 7.5 |
| `agents/orchestrator/app/NewsOrchestrator/config.py` | Add `CW_NAMESPACE` constant |
| `agents/orchestrator/app/NewsOrchestrator/tools/__init__.py` | Export new tools |
| `agents/orchestrator/agentcore/cdk/lib/cdk-stack.ts` | IAM for `cloudwatch:PutMetricData` |
| `agents/collector/app/NewsCollector/tools/rss_fetcher.py` | Enrich error returns |
| `agents/collector/app/NewsCollector/tools/article_fetcher.py` | Enrich error returns |
| `agents/collector/app/NewsCollector/agent.py` | Error handling prompt + source_results output |
| `agents/publisher/app/NewsPublisher/tools/git_ops.py` | Classify git errors |
| `agents/publisher/app/NewsPublisher/agent.py` | Git retry guidance in prompt |
| `agents/orchestrator/app/NewsOrchestrator/tools/a2a_client.py` | Classify A2A errors |

---

## Verification

1. **Unit tests**: `python3 -m pytest tests/ -v` in each agent
2. **Deployed test**: `agentcore invoke '{"trigger":"scheduled","run_time":"..."}' --stream`
3. **CloudWatch check**: Custom metric `NewsAgent/RunCompleted` visible in console
4. **S3 check**: `runs/{date}/{HHMM}-result.json` and `health/source-status.json` created
5. **Source health visibility**: After a few runs, run result shows `"consecutive_failures": N` for broken sources

---

## Cost

| Resource | Monthly Cost |
|----------|-------------|
| CloudWatch custom metrics (2 metrics × 4 datapoints/day) | Free tier |
| S3 run logs (~4KB/day) | Negligible |
| **Total** | **$0/month** |
