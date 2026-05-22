# NewsCollector Agent

General-purpose web content collection agent built on AWS Bedrock AgentCore. Fetches content from RSS feeds and webpages, deduplicates against previously seen URLs, consolidates related articles into topics via LLM, translates/summarizes to Chinese, and writes structured output to S3.

## Architecture

```
AgentCore Runtime (Container, Python 3.12, eu-west-1)
  └── Tools
      ├── fetch_rss           — Parse RSS feeds, filter by time window
      ├── fetch_webpage       — Fetch single webpage HTML
      ├── extract_content     — Extract article text (trafilatura)
      ├── get_dedup_context   — Read known URLs + existing topics for dedup
      └── write_to_s3         — Write JSON output to S3
```

**Model:** Claude Sonnet 4 via Bedrock (`global.anthropic.claude-sonnet-4-6`)

## Processing Pipeline

```
1. Read dedup source → known_urls + existing_topics
2. Fetch RSS feeds → filter by time window (e.g. last 6h)
3. URL dedup → remove already-seen URLs
4. Extract full content → trafilatura, 10s timeout, skip failures
5. Consolidate topics (LLM) → group related articles, match to existing
6. Translate + summarize (LLM) → Chinese titles + ~200-word summaries
7. Write to S3 → structured JSON with new_items + updated_items
```

## Prerequisites

- AWS CLI configured with credentials for account `548129671048`
- Node.js 18+ (for CDK)
- Python 3.11+ (for tests)
- [agentcore CLI](https://docs.hub.amazon.dev/agentcore/) installed globally
- [uv](https://docs.astral.sh/uv/) installed (for Python dependency management)
- S3 bucket `news-agent-data-548129671048` exists in `eu-west-1`

## Project Structure

```
agents/collector/
├── agentcore/
│   ├── agentcore.json        # Runtime definition
│   ├── aws-targets.json      # Deployment target (account, region)
│   └── cdk/                  # CDK stack (TypeScript)
│       ├── lib/cdk-stack.ts  # IAM permissions, runtime config
│       ├── bin/cdk.ts        # CDK app entrypoint
│       └── package.json      # CDK dependencies
├── app/NewsCollector/
│   ├── main.py               # AgentCore runtime entrypoint
│   ├── agent.py              # System prompt + tool registration
│   ├── config.py             # MODEL_ID constant
│   ├── tools/                # @tool implementations
│   │   ├── rss_fetcher.py
│   │   ├── webpage_fetcher.py
│   │   ├── content_extractor.py
│   │   ├── dedup.py
│   │   └── s3_writer.py
│   ├── Dockerfile            # Container image (python:3.12-slim)
│   ├── pyproject.toml        # Python dependencies
│   └── uv.lock              # Locked dependencies
└── tests/                    # Unit + integration tests
```

## Deployment

### 1. Install CDK dependencies

```bash
cd agentcore/cdk
npm install --legacy-peer-deps
cd ../..
```

### 2. Deploy the stack

```bash
agentcore deploy -y
```

This deploys:
- AgentCore Runtime (container image via CodeBuild)
- IAM execution role with permissions for:
  - `bedrock:InvokeModel` (LLM calls for consolidation, translation, summarization)
  - `s3:PutObject` + `s3:GetObject` on `news-agent-data-548129671048/*`
- PUBLIC network mode (outbound internet for RSS feeds and article URLs)

### 3. Verify deployment

```bash
agentcore status
```

Expected: `NewsCollector: Deployed - Runtime: READY`

## Invocation

```bash
agentcore invoke '{
  "task": {
    "task_id": "collect-norway-2026-05-21-0500",
    "sources": [
      {"url": "https://www.nrk.no/toppsaker.rss", "type": "rss", "label": "NRK Norge", "category": "domestic"},
      {"url": "https://www.nrk.no/urix/toppsaker.rss", "type": "rss", "label": "NRK Urix", "category": "international"},
      {"url": "https://e24.no/rss2", "type": "rss", "label": "E24", "category": "business"}
    ],
    "filters": {
      "time_window_hours": 6,
      "dedup_source": {
        "type": "github_file",
        "repo": "claw-lu/hexo-blog",
        "path": "source/_posts/20260521-norway.md"
      }
    },
    "processing": {
      "extract_full_content": true,
      "consolidate_topics": true,
      "summarize": true,
      "summary_word_count": 200,
      "translate_to": ["zh"],
      "preserve_original_names": true
    },
    "output": {
      "s3_bucket": "news-agent-data-548129671048",
      "s3_key_prefix": "collections/2026-05-21/",
      "format": "json"
    }
  }
}' --stream
```

### Output

The agent returns a lightweight summary to the caller:

```json
{
  "status": "success",
  "task_id": "collect-norway-2026-05-21-0500",
  "data_key": "collections/2026-05-21/collect-norway-2026-05-21-0500.json",
  "summary": {
    "sources_fetched": 3,
    "items_in_rss": 45,
    "after_time_filter": 20,
    "new_urls_found": 8,
    "grouped_into_new_topics": 3,
    "matched_to_existing_topics": 1,
    "skipped_no_new_info": 2,
    "skipped_already_seen_urls": 12
  }
}
```

Bulk data is written to S3 at `data_key` (not returned in the response).

## Local Development

### Run tests

```bash
python3 -m pytest tests/ -v
```

### Run locally (requires AWS credentials)

```bash
agentcore dev
```

### Update dependencies

```bash
cd app/NewsCollector
# Edit pyproject.toml, then:
uv lock
```

## Dedup Sources

| Type | Description | Use Case |
|------|-------------|----------|
| `github_file` | Read existing blog post from public GitHub repo | Match against already-published topics |
| `s3_file` | Read previous collection output from S3 | Dedup within same day's runs |
| `url_list` | Explicit list of URLs to skip | Manual exclusions |
| `none` | No dedup | First run, no existing content |

## Processing Modes

| Option | Effect |
|--------|--------|
| `consolidate_topics: true` | Group related articles into topics, match against existing |
| `consolidate_topics: false` | One article = one item, URL dedup only |
| `extract_full_content: true` | Follow URLs, extract full article text |
| `extract_full_content: false` | Use RSS description/snippet only |
| `summarize: true` | Generate ~200-word summaries (LLM) |
| `translate_to: ["zh"]` | Translate titles and summaries to Chinese |

## IAM Permissions (managed by CDK)

| Permission | Resource | Purpose |
|-----------|----------|---------|
| `bedrock:InvokeModel` | `arn:aws:bedrock:*:548129671048:inference-profile/*` | LLM calls |
| `s3:PutObject` | `arn:aws:s3:::news-agent-data-548129671048/*` | Write collection output |
| `s3:GetObject` | `arn:aws:s3:::news-agent-data-548129671048/*` | Read previous collections for dedup |

Network mode is PUBLIC — allows outbound HTTP to RSS feeds, article URLs, and GitHub raw content.

## Deployed Resources

| Resource | Value |
|----------|-------|
| Runtime ID | `newscollector_NewsCollector-EhrHzp4oFi` |
| Region | `eu-west-1` |
| Account | `548129671048` |
| Stack | `AgentCore-newscollector-default` |

## Troubleshooting

**S3 access denied on write:**
Verify the CDK stack's `addToPolicy` includes `s3:PutObject`. Redeploy with `agentcore deploy -y`.

**RSS fetch timeout / no articles:**
The agent filters by `time_window_hours`. If no articles were published in that window, it returns `new_urls_found: 0`. Try increasing the window or check that the RSS feed URL is correct.

**Article extraction failures:**
Extraction uses trafilatura with a 10s timeout. Failures are skipped silently. Check `metadata.extraction_failures` in the S3 output for count.

**View runtime logs:**
```bash
agentcore logs --follow
```
