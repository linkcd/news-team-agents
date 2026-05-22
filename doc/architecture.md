# News-Agent Architecture

## Overview

A multi-agent news collection and publishing system built on AWS Bedrock AgentCore. Three independent agent microservices coordinate to collect Norwegian news from RSS feeds, translate/summarize to Chinese, and publish to a Hexo blog. Each agent is general-purpose and reusable — the domain-specific logic lives only in the Orchestrator.

## System Diagram

```
EventBridge (every 6 hours: 05:00, 11:00, 17:00, 23:00 UTC)
  |
  v
Lambda (eventbridge_invoker)
  |
  v
+----------------------------------------------+
| AgentCore Runtime: ORCHESTRATOR              |
| (Domain-specific: Norwegian news workflow)   |
| - Builds task config for Collector           |
| - Invokes Collector, receives S3 key         |
| - Decides publish_new vs merge_update        |
| - Invokes Publisher with task config         |
| - Retry once on Collector error              |
+----------------------------------------------+
        |                         |
        v                         v
+--------------------+   +---------------------+
| Runtime:           |   | Runtime:            |
| COLLECTOR          |   | PUBLISHER           |
| (General-purpose)  |   | (General-purpose)   |
|                    |   |                     |
| Input: URLs +      |   | Input: S3 key +     |
|   config           |   |   editorial config  |
| Output: S3 file    |   | Output: git push    |
|                    |   |                     |
| - Dedup (GitHub)   |   | - Read from S3      |
| - RSS/web fetch    |   | - Format (Jinja2)   |
| - Extract content  |   | - Merge (code tool) |
| - Consolidate      |   | - Summary (LLM)     |
|   topics (LLM)     |   | - Update existing   |
| - Translate/summ.  |   |   items (LLM match) |
| - Write to S3      |   | - Git push          |
+--------------------+   +---------------------+
        |                         |
        v                         v
  S3 Bucket               GitHub Action
  (intermediate)          (hexo deploy)
                                  |
                                  v
                         claw-blog.feng.lu
                         (GitHub Pages)
```

## Agent Microservice Design

Each agent is:
- **Independently deployable** (own container, own ECR repo, own AgentCore runtime)
- **Independently evaluable** (own test suite, own AgentCore evaluation config)
- **Reusable** (Collector and Publisher accept arbitrary tasks from any caller)

### Separation of Concerns

| Agent | Scope | Knows About |
|-------|-------|-------------|
| Collector | Fetching, extracting, translating web content | URLs, S3, extraction libraries |
| Publisher | Formatting, editing, publishing to Git repos | Templates, Git, S3 |
| Orchestrator | Norwegian news workflow coordination | News sources, schedule, Collector + Publisher ARNs |

The Orchestrator is the only agent that knows about Norwegian news specifically. Collector and Publisher are generic tools.

---

## Data Flow

```
Orchestrator:
  1. Build collection task (sources, filters, processing, output config)

Collector:
  2. Read today's existing blog post from GitHub (public, no token)
     → extract known URLs + existing topic summaries
  3. Fetch RSS feeds, filter to last 6h
  4. Remove already-seen URLs (exact match)
  5. Extract article content (trafilatura, skip failures)
  6. Consolidate topics (LLM):
     - Group new articles about the same event
     - Match against existing topics from blog post
     - Determine if matched articles add new info
     - Skip articles that add nothing new
  7. Translate/summarize consolidated topics to Chinese (LLM)
  8. Write result JSON to S3 (new_items + updated_items)
  9. Return {status, data_key, counts} to Orchestrator

Orchestrator:
  10. If new_topics + updated_topics > 0: build publish task, invoke Publisher
  11. If both == 0: done

Publisher:
  12. Read collected topics from S3 (new_items + updated_items)
  13. Clone/pull blog repo
  14. If today's post exists:
      - Append new_items to correct sections
      - Update existing items with new summaries + sources + changelog
      - Renumber, regenerate day summary
  15. If no post: create fresh from template
  16. Git commit + push
  17. Return {status, commit_sha} to Orchestrator

GitHub Action:
  18. Triggered by push to main
  19. hexo clean && hexo generate && hexo deploy
```

---

## Agent Interfaces

### Collector Interface

**Input**: Task configuration specifying sources, filters, processing, and output location.

Key parameters:
- `sources[]` - List of URLs with type (rss/webpage), label, category
- `filters.time_window_hours` - How far back to look (6h for this workflow)
- `filters.dedup_source` - Where to find already-collected URLs and existing topics (GitHub file, S3 file, URL list, or none)
- `processing.consolidate_topics` - Whether to group related articles into topics
- `processing` - Extract full content? Summarize? Translate to which languages?
- `output` - S3 bucket + key prefix + format

**Output**: Lightweight metadata (status, data_key, counts). Bulk data in S3.

**S3 output contains**:
- `new_items[]` - Newly consolidated topics (may have multiple sources each)
- `updated_items[]` - Updates to existing topics (new source + revised summary + changelog)
- `metadata` - Counts: sources fetched, items found, grouped, matched, skipped

See `agents/collector/CLAUDE.md` for full interface spec.

### Publisher Interface

**Input**: Task type + configuration.

Task types:
- `publish_new` - Create a new post from collected content
- `merge_update` - Merge new content into existing post
- `rewrite` - Free-form rewrite of an existing page
- `edit` - Structured edits to an existing page

Key parameters:
- `source` - Where to read content (S3 key with new_items + updated_items)
- `template` - Which Jinja2 template to use
- `output` - Target repo, branch, file path
- `editorial` - Summary generation config
- `merge_strategy.new_items` - How to insert new topics (append/prepend per section)
- `merge_strategy.updated_items` - How to handle topic updates (replace summary + add source + changelog)
- `merge_strategy.regenerate_day_summary` - Whether to regenerate the overall summary

**Output**: Status, commit SHA, new items added, existing items updated, total items in post.

See `agents/publisher/CLAUDE.md` for full interface spec.

### Orchestrator Interface

**Input**: Trigger event from Lambda.

```json
{"trigger": "scheduled", "run_time": "2026-05-21T11:00:00Z"}
```

**Output**: Run summary.

See `agents/orchestrator/CLAUDE.md` for full workflow spec.

---

## Inter-Agent Communication

### Protocol: A2A over SSE Streaming

Orchestrator invokes Collector and Publisher using the strands `A2AAgent` client with Server-Sent Events (SSE) streaming. The topology is fixed (orchestrator knows both ARNs as env vars).

```python
from bedrock_agentcore.runtime import build_runtime_url
from strands.agent.a2a_agent import A2AAgent
from a2a.client import ClientConfig

endpoint = build_runtime_url(runtime_arn, region)
client_config = ClientConfig(
    httpx_client=httpx.AsyncClient(
        auth=SigV4HTTPXAuth(credentials, "bedrock-agentcore", region),
        timeout=httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0),
        headers={"X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id},
    ),
)
agent = A2AAgent(endpoint=endpoint, client_config=client_config)
result = agent(json.dumps({"task": task_config}))
```

Key implementation details:
- **`bedrock_agentcore.runtime.build_runtime_url`** builds the HTTPS invocation URL from an agent ARN
- **`SigV4HTTPXAuth`** (custom `httpx.Auth` subclass in `tools/sigv4_auth.py`) signs each HTTP request with AWS SigV4
- **SSE streaming** keeps the connection alive during long-running agent tasks — each streamed event resets the idle timeout
- **Server-side** uses `StrandsA2AExecutor(agent, enable_a2a_compliant_streaming=True)` for all agents

### Data Flow
Bulk article data passes via S3, not through the Orchestrator's LLM context:
- Collector writes to: `s3://news-agent-data/collections/{date}/{time}-{task_id}.json`
- Orchestrator receives only: `{status, data_key, summary}`
- Publisher reads from S3 using the data_key

**Rationale**: Avoids large payloads in Orchestrator context (token waste, latency, corruption risk). Provides natural audit trail.

### Timeout Policy
- HTTP read timeout: 120s per SSE event (streaming resets this on each event)
- On error: retry once for Collector, no retry for Publisher

---

## GitHub Action (in hexo-blog repo)

**File**: `.github/workflows/deploy.yml`

**Trigger**: Push to `main` branch (path filter: `source/_posts/**`)

**Steps**:
1. Checkout repo
2. Setup Node.js
3. `npm install` (hexo + plugins)
4. `hexo clean && hexo generate && hexo deploy`

**Rationale**: Decouples LLM agent work from build toolchain. Publisher container stays pure Python. Hexo version management lives in the blog repo.

---

## Infrastructure

### AWS Resources (CDK Stack)

| Resource | Purpose |
|----------|---------|
| 3x AgentCore Runtime | One per agent (Container build, Python 3.11) |
| 3x ECR Repository | Docker images for each agent |
| 1x EventBridge Rule | `cron(0 5,11,17,23 * * ? *)` — every 6h |
| 1x Lambda | EventBridge -> invoke orchestrator |
| 1x S3 Bucket | Intermediate data (`news-agent-data`, 7-day lifecycle) |
| 1x Secrets Manager Secret | GitHub bot token (Publisher write access) |
| 3x IAM Role | Per-runtime execution roles |

### IAM Permissions

| Role | Permissions |
|------|-------------|
| Orchestrator | `bedrock-agentcore:InvokeAgentRuntime` on Collector + Publisher, `bedrock:InvokeModel` |
| Collector | `bedrock:InvokeModel`, `s3:PutObject` on data bucket, outbound internet (RSS, GitHub public API) |
| Publisher | `bedrock:InvokeModel`, `s3:GetObject` on data bucket, `secretsmanager:GetSecretValue`, outbound internet (git push) |
| Lambda (invoker) | `bedrock-agentcore:InvokeAgentRuntime` on Orchestrator |

### Secrets

| Secret | Used By | Content |
|--------|---------|---------|
| `news-agent/github-token` | Publisher | GitHub bot PAT for git push (write access to claw-lu/hexo-blog) |

### S3 Bucket Structure

```
s3://news-agent-data/
  collections/
    2026-05-21/
      0500-norway-news.json
      1100-norway-news.json
      1700-norway-news.json
      2300-norway-news.json
    2026-05-22/
      ...
```

Objects auto-expire after 7 days (lifecycle policy). Serves as audit trail.

---

## Evaluation Strategy

Each agent is evaluated independently:

### Collector Evaluation

| Evaluator | Type | Checks |
|-----------|------|--------|
| Translation Quality | LLM-as-Judge | Natural Chinese, accurate translation, proper nouns preserved |
| Consolidation Quality | LLM-as-Judge | Related articles correctly grouped, distinct topics not merged |
| URL Validity | Code-based (Lambda) | All source URLs return 200, are article pages not homepages |
| Story Freshness | Code-based (Lambda) | All stories within configured time window |
| Dedup Correctness | Code-based (Lambda) | No duplicate URLs in output vs existing post |
| Update Relevance | LLM-as-Judge | Updated items genuinely add new info vs existing summary |

### Publisher Evaluation

| Evaluator | Type | Checks |
|-----------|------|--------|
| Format Compliance | Code-based (Lambda) | Valid Hexo front-matter, correct markdown structure |
| Summary Quality | LLM-as-Judge | Day summary covers all topics, coherent, correct length |
| Merge Correctness | Code-based (Lambda) | No duplicate topics after merge, correct numbering, changelog present on updates |
| Source Attribution | Code-based (Lambda) | All source URLs from Collector appear in published post |

### Orchestrator Evaluation

| Evaluator | Type | Checks |
|-----------|------|--------|
| Workflow Correctness | Code-based (Lambda) | Correct task configs passed, appropriate retry/skip decisions |

### Online Evaluation
- 100% sampling on all runtimes (only 4 runs/day)
- Built-in evaluators: Correctness, Helpfulness, Completeness

### Simulation Testing
- Pre-recorded RSS feed responses for deterministic testing
- Mock S3 and git operations for isolated agent testing
- Full pipeline smoke test before production deployment

---

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Agent Framework | Strands Agents SDK (Python), with A2A protocol support |
| A2A Client | strands `A2AAgent` + `a2a-sdk` `ClientConfig` + custom SigV4 httpx auth |
| LLM | Claude Sonnet 4 via Amazon Bedrock |
| Infrastructure | AWS CDK (TypeScript, managed by agentcore CLI) |
| Runtime | AgentCore (Container build, Python 3.12) |
| RSS Parsing | feedparser |
| Article Extraction | trafilatura |
| HTTP Client | httpx |
| Git Operations | gitpython |
| Template Engine | Jinja2 |
| Blog Engine | Hexo (in GitHub Action, NOT in agent containers) |
| Scheduling | Amazon EventBridge |
| Data Passing | Amazon S3 |
| Secrets | AWS Secrets Manager |
| Observability | OpenTelemetry (AgentCore built-in) |
| Deploy | GitHub Actions |

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Agent design | Collector + Publisher as general-purpose microservices | Reusable by other agents/workflows; independently deployable and evaluable |
| Content model | Topic-based (consolidated) not article-based | Multiple articles about the same event → one topic. Reduces noise, richer summaries. |
| Topic matching | LLM semantic similarity (no explicit IDs) | Most flexible; handles paraphrased titles, different angles on same event. Non-deterministic but acceptable for editorial use. |
| Topic updates | Regenerate summary + changelog note | Reads naturally; changelog provides transparency on when/what was added |
| Inter-agent comms | strands `A2AAgent` + SSE streaming + SigV4 | Native A2A protocol; SSE streaming avoids idle timeouts on long tasks |
| Data passing | S3 intermediate storage | Avoids large payloads in Orchestrator LLM context; provides audit trail |
| Dedup ownership | Collector reads existing post from GitHub | Collector is self-contained; Orchestrator stays lightweight |
| Hexo deployment | GitHub Action (not in Publisher container) | Decouples LLM work from build toolchain; easier to debug |
| Multi-run merge | Deterministic Python tool + LLM for matching/summary | Structural manipulation (insert, renumber) is code; creative work (matching, summarizing) is LLM |
| Article extraction | trafilatura (browser as future fallback) | Norwegian news sites serve server-rendered HTML; fast and lightweight |
| Failed extraction | Skip silently | 6h window + 4 runs/day gives natural resilience; no hard threshold needed |
| Model | Claude Sonnet 4 | Strong multilingual for Norwegian→Chinese translation + good at semantic similarity |
| Build type | Container (not CodeZip) | Flexibility for libraries; keeps options open |
| Schedule | Every 6h (05:00, 11:00, 17:00, 23:00 UTC) | Aligned with Norwegian news cycle |
| Orchestrator as LLM agent | Yes (over Step Functions) | Learning AgentCore multi-agent patterns is a project goal |
