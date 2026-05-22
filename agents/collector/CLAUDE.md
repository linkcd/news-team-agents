# Collector Agent

A general-purpose web content collection agent. Given a set of URLs (or RSS feed URLs) and configuration, it fetches content, extracts articles, consolidates related content into topics, and writes structured output to S3.

## Deployment

- **Runtime ID**: `newscollector_NewsCollector-EhrHzp4oFi`
- **ARN**: `arn:aws:bedrock-agentcore:eu-west-1:548129671048:runtime/newscollector_NewsCollector-EhrHzp4oFi`
- **Protocol**: A2A (Agent-to-Agent) via `serve_a2a(StrandsA2AExecutor(agent, enable_a2a_compliant_streaming=True))`
- **Region**: eu-west-1

## Purpose

Standalone, reusable agent for web content collection with intelligent consolidation. Any agent can invoke it with a collection task — not tied to any specific workflow or domain.

## Core Behavior: Topic Consolidation

The Collector does not produce one output item per article. It **consolidates related articles into topics**:

- Multiple articles about the same event/topic → one consolidated item with multiple sources
- New articles matching an existing topic (from a prior run) → update to that topic if new info exists
- New articles with no new info beyond existing topic → skipped entirely

### Matching Logic

The LLM determines topic matches by semantic similarity:
1. Compare new article content against existing topic summaries (from blog post)
2. Compare new articles against each other (group within a batch)
3. If match found: determine whether new article adds unique information
4. If no new info: skip the article (don't even add it as a source)

No explicit topic IDs — matching is purely by content similarity.

### Example Flow

```
Run 1: Articles A1 (NRK) + B1 (VG) both about parliament vote
  → Topic: "Parliament vote" (sources: A1, B1), consolidated summary

Run 2: Article C1 (Dagbladet) also about parliament vote, has reaction quotes
  → Update: "Parliament vote" summary rewritten with reaction info
  → Changelog note: "(更新于 11:00 UTC: 新增来自Dagbladet的议员反应)"

Run 2: Article E1 (Aftenposten) about parliament vote, no new info
  → Skipped entirely
```

## Interface

Receives A2A `message/send` requests (JSON-RPC 2.0). The task config is passed as a `data` Part in the A2A message. Returns an A2A task with artifacts containing the result.

### Input (task config delivered via A2A message Part)

```json
{
  "task": {
    "task_id": "string (caller-defined unique ID)",
    "sources": [
      {
        "url": "string (RSS feed or webpage URL)",
        "type": "rss | webpage",
        "label": "string (human-readable source name)",
        "category": "string (caller-defined grouping, e.g. domestic/international)"
      }
    ],
    "filters": {
      "time_window_hours": 6,
      "dedup_source": {
        "type": "github_file | s3_file | url_list | none",
        "repo": "owner/repo (for github_file)",
        "path": "file path in repo (for github_file)",
        "bucket": "bucket name (for s3_file)",
        "key": "object key (for s3_file)",
        "urls": ["explicit URLs to skip (for url_list)"]
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
      "s3_bucket": "string",
      "s3_key_prefix": "string (e.g. collections/2026-05-21/)",
      "format": "json"
    }
  }
}
```

### Output (returned to caller)

```json
{
  "status": "success | error",
  "task_id": "string (echoed back)",
  "data_key": "string (full S3 key where results are stored)",
  "summary": {
    "sources_fetched": 11,
    "items_in_rss": 45,
    "after_time_filter": 20,
    "new_urls_found": 8,
    "grouped_into_new_topics": 3,
    "matched_to_existing_topics": 1,
    "skipped_no_new_info": 2,
    "skipped_already_seen_urls": 12
  },
  "error": "string (only if status=error)"
}
```

### S3 Output File Format

```json
{
  "task_id": "string",
  "collected_at": "ISO8601 timestamp",
  "new_items": [
    {
      "title_zh": "Consolidated Chinese title",
      "category": "domestic",
      "summary_zh": "~200 word consolidated summary from all sources",
      "sources": [
        {
          "url": "https://nrk.no/article/123",
          "source_label": "NRK Norge",
          "published_at": "2026-05-21T09:30:00Z",
          "title_original": "Original Norwegian title"
        },
        {
          "url": "https://vg.no/article/456",
          "source_label": "VG",
          "published_at": "2026-05-21T09:45:00Z",
          "title_original": "VG's title for same story"
        }
      ]
    }
  ],
  "updated_items": [
    {
      "match_title_zh": "Existing topic title from blog post (used for matching)",
      "new_source": {
        "url": "https://dagbladet.no/article/789",
        "source_label": "Dagbladet",
        "published_at": "2026-05-21T10:15:00Z",
        "title_original": "Dagbladet's angle"
      },
      "updated_summary_zh": "Revised ~200 word summary incorporating new info",
      "changelog": "新增来自Dagbladet的议员反应信息"
    }
  ],
  "metadata": {
    "sources_fetched": 11,
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

## Processing Pipeline

```
1. READ DEDUP SOURCE
   - Read today's existing blog post (or S3 file, or URL list)
   - Extract: known_urls[] + existing_topics[{title, summary, source_urls, category}]

2. FETCH RSS / WEBPAGES
   - Parse all source feeds/pages
   - Filter by time window (e.g. last 6 hours)
   - Remove already-seen URLs (exact match on known_urls)

3. FETCH + EXTRACT CONTENT
   - For remaining URLs: call fetch_and_extract(url) which fetches and extracts in one step
   - Returns only extracted text (raw HTML never enters LLM context)
   - On failure: skip silently

4. CONSOLIDATE (LLM)
   - Group new articles by topic similarity (within this batch)
   - Match each group against existing_topics (from blog post)
   - For matches: determine if new info exists beyond existing summary
   - Produce: new_items (grouped) + updated_items (with new info) + skip count

5. TRANSLATE + SUMMARIZE (LLM)
   - For new_items: generate consolidated title_zh + summary_zh from all source articles
   - For updated_items: regenerate summary_zh incorporating new info, add changelog note

6. WRITE TO S3
   - Write structured JSON to configured S3 location
   - Return lightweight metadata to caller
```

## Tools

| Tool | Purpose |
|------|---------|
| `fetch_rss(url, time_window_hours)` | Parse RSS feed, filter by time window |
| `fetch_and_extract(url)` | Fetch webpage and extract article text in one step (trafilatura, 10s timeout). Returns only extracted text — raw HTML never enters LLM context. |
| `get_dedup_context(dedup_source)` | Read existing URLs + topic summaries from dedup source |
| `write_to_s3(bucket, key, data)` | Write JSON output to S3 |

## Dedup Sources

The agent supports multiple dedup source types:

| Type | Description | What It Provides | Auth |
|------|-------------|-----------------|------|
| `github_file` | Read a markdown file from a public GitHub repo | known_urls + existing topics (parsed from post structure) | None (public repos) |
| `s3_file` | Read a previous collection output from S3 | known_urls + existing topics | IAM role |
| `url_list` | Explicit list of URLs to skip | known_urls only (no topic matching) | None |
| `none` | No dedup, no topic matching | Empty | None |

## Processing Modes

| Mode | Behavior |
|------|----------|
| `consolidate_topics: true` | Group related articles, match to existing topics, dedup by content similarity |
| `consolidate_topics: false` | One article = one item (no grouping, no semantic matching, URL dedup only) |
| `extract_full_content: true` | Follow URLs, extract full article text |
| `extract_full_content: false` | Use RSS description/snippet only |
| `summarize: true` | Generate summary (requires LLM) |
| `summarize: false` | Return raw extracted content |
| `translate_to: ["zh"]` | Translate title + summary to specified languages |
| `translate_to: []` | No translation |

## IAM Permissions Required

- `bedrock:InvokeModel` (for consolidation, translation, summarization)
- `s3:PutObject` on output bucket
- Outbound internet (RSS feeds, article URLs, GitHub public API)

## Tech Stack

- Python 3.12, Strands Agents SDK (with A2A support)
- bedrock-agentcore[a2a] (A2A runtime serving)
- feedparser (RSS parsing)
- trafilatura (article extraction)
- httpx (HTTP client)
- boto3 (S3 writes)

## Development

```bash
agentcore dev                    # local development
python3 -m pytest tests/ -v      # run unit tests (28 tests)
agentcore deploy -y              # deploy to AWS
agentcore invoke '{"task": {...}}' --stream  # invoke
```

## Article Extraction Strategy

- Primary: trafilatura (fast, works for most server-rendered news sites)
- On failure: skip silently, log URL in metadata
- Future: AgentCore browser tool as fallback for JS-heavy sites
- Timeout: 10s per article to prevent one slow site from blocking the run
