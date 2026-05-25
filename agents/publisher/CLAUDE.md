# Publisher Agent

A general-purpose editorial and publishing agent. Given content (from S3 or direct input), it can format, rewrite, merge, and publish to a Git-based blog or any target repository. Any agent can invoke it for editorial tasks.

## Deployment

- **Runtime ID**: `newspublisher_NewsPublisher-OZnqGfD4D2`
- **ARN**: `arn:aws:bedrock-agentcore:eu-west-1:548129671048:runtime/newspublisher_NewsPublisher-OZnqGfD4D2`
- **Protocol**: A2A (Agent-to-Agent) via `serve_a2a(StrandsA2AExecutor(agent, enable_a2a_compliant_streaming=False))`
- **Region**: eu-west-1

## Purpose

Standalone, reusable agent for content editing and publishing. Handles: formatting content into blog posts, rewriting/editing existing pages, merging new content into existing posts (including topic updates), and pushing changes to Git repos. Not tied to any specific workflow.

## Interface

Receives A2A `message/send` requests (JSON-RPC 2.0). The task config is passed as a `data` Part in the A2A message. Returns an A2A task with artifacts containing the result.

### Input (task config delivered via A2A message Part)

The agent accepts multiple task types:

#### Task: `publish_new`
Create a new blog post from collected content.

```json
{
  "task": {
    "task_id": "publish-norway-2026-05-21",
    "type": "publish_new",
    "source": {
      "type": "s3",
      "bucket": "news-agent-data",
      "key": "collections/2026-05-21/0500-norway-news.json"
    },
    "template": "norway_daily",
    "output": {
      "repo": "claw-lu/hexo-blog",
      "branch": "main",
      "file_path": "source/_posts/20260521-norway.md",
      "commit_message": "Add Norway news 2026-05-21"
    },
    "editorial": {
      "generate_summary": true,
      "summary_word_count": 300,
      "summary_scope": "all_items"
    }
  }
}
```

#### Task: `merge_update`
Merge new content and topic updates into an existing post.

```json
{
  "task": {
    "task_id": "merge-norway-2026-05-21-1100",
    "type": "merge_update",
    "source": {
      "type": "s3",
      "bucket": "news-agent-data",
      "key": "collections/2026-05-21/1100-norway-news.json"
    },
    "target": {
      "repo": "claw-lu/hexo-blog",
      "branch": "main",
      "file_path": "source/_posts/20260521-norway.md"
    },
    "merge_strategy": {
      "new_items": "prepend_per_section",
      "updated_items": "replace_summary_and_add_source",
      "renumber": true,
      "regenerate_day_summary": true
    },
    "editorial": {
      "generate_summary": true,
      "summary_word_count": 300,
      "summary_scope": "all_items"
    }
  }
}
```

#### Task: `rewrite`
Rewrite or edit an existing page.

```json
{
  "task": {
    "task_id": "rewrite-about-page",
    "type": "rewrite",
    "target": {
      "repo": "claw-lu/hexo-blog",
      "branch": "main",
      "file_path": "source/about/index.md"
    },
    "instructions": "Update the about page to mention the new 6-hourly news collection schedule.",
    "commit_message": "Update about page with new schedule"
  }
}
```

#### Task: `edit`
Make specific edits to an existing page (structured changes, not free-form rewrite).

```json
{
  "task": {
    "task_id": "edit-config",
    "type": "edit",
    "target": {
      "repo": "claw-lu/hexo-blog",
      "branch": "main",
      "file_path": "_config.yml"
    },
    "edits": [
      {"action": "replace", "old": "title: Old Title", "new": "title: New Title"}
    ],
    "commit_message": "Update site title"
  }
}
```

### Output (returned to caller, same structure for all task types)

```json
{
  "status": "success | error",
  "task_id": "string",
  "result": {
    "action": "publish_new | merge_update | rewrite | edit",
    "file_path": "string (path that was modified)",
    "commit_sha": "string",
    "new_items_added": 3,
    "existing_items_updated": 1,
    "total_items_in_post": 7
  },
  "error": "string (only if status=error)"
}
```

## Merge Behavior for Topic Consolidation

When handling `merge_update` with the Collector's consolidated output:

### `new_items` (new topics)
- Append as new entries at end of the matching section (domestic, international, business)
- Each item shows multiple sources if consolidated
- Number sequentially after existing items

### `updated_items` (existing topics with new info)
- Match to existing post items by title similarity (LLM matching, same approach as Collector)
- Replace the summary with `updated_summary_zh` from Collector
- Add the new source to the source list
- Add changelog note below the summary: `(更新于 HH:MM UTC: [changelog text])`

### Post-merge actions
- Renumber all items sequentially
- Regenerate day summary (LLM) covering all topics
- Update `updated:` field in front-matter
- Update footer timestamp

## Blog Post Format (for news posts)

```markdown
---
title: 挪威新闻速递 2026-05-21
date: 2026-05-21 05:00:00
updated: 2026-05-21 17:00:00
tags: [挪威, 新闻]
categories: [每日新闻, 挪威]
---

<style>article.article-content, .post-body, .article-entry { font-size: 1.15em; line-height: 1.8; }</style>

*最后更新: 17:00 UTC*

## 今日综述
[300-word summary connecting themes across all topics]

<!-- more -->

## 国内新闻

### 1. 议会通过新移民法案
**来源**: NRK Norge, VG, Dagbladet | **最早报道**: 2026-05-21 09:30

[~200 word consolidated summary incorporating all sources]
(更新于 11:00 UTC: 新增来自Dagbladet的议员反应信息)

原文链接: [NRK](https://...) | [VG](https://...) | [Dagbladet](https://...)

---

### 2. 奥斯陆新地铁线路开工
**来源**: NRK Oslo | **最早报道**: 2026-05-21 10:00

[~200 word summary]

原文链接: [NRK](https://...)

---

## 国际新闻
[International topics...]

## 财经新闻
[Business topics from E24...]

---
*新闻来源: NRK, VG, TV2, Dagbladet, Aftenposten, Dagsavisen, E24*
```

## Tools

| Tool | Purpose |
|------|---------|
| `read_from_s3(bucket, key)` | Read collected items JSON from S3 (used by publish_new) |
| `git_clone(repo, branch)` | Clone repo locally (authenticated via AgentCore Identity) |
| `read_local_file(repo_path, file_path)` | Read file from cloned repo |
| `write_new_post(repo_path, file_path, content)` | Write LLM-generated markdown to disk (used by publish_new) |
| `merge_posts(repo_path, file_path, s3_bucket, s3_key, strategy)` | File-based deterministic merge — reads existing post from disk, merges with S3 data, writes result back to disk. Returns only metadata. |
| `update_summary(repo_path, file_path, new_summary)` | Replaces day summary section on disk, updates timestamps. Only tool that needs LLM-generated content. |
| `git_commit_and_push(repo_path, file_path, commit_message)` | Commits file already on disk and pushes |

For `publish_new`: the LLM writes markdown via `write_new_post`, then `git_commit_and_push` commits it.
For `merge_update`: all tools are file-based — `merge_posts` reads/writes disk, `update_summary` patches the summary section, `git_commit_and_push` commits. The LLM only generates the ~300-word day summary (~400 output tokens). This reduced Publisher runtime from ~10 min to ~1 min by eliminating LLM verbatim copying of large content into tool arguments.

## Authentication

Git operations use AgentCore Identity (`@requires_api_key(provider_name="github-token")`) to obtain the GitHub token at runtime. The invoking agent must pass `runtime_user_id` in the A2A request header (`X-Amzn-Bedrock-AgentCore-Runtime-User-Id`) for the token to be issued.

## IAM Permissions Required

- `bedrock:InvokeModel` (for markdown generation, summary writing, content merging)
- `s3:GetObject` on source bucket
- Outbound internet (git push, GitHub raw file reads)
- AgentCore Identity: `github-token` API key provider configured

## Tech Stack

- Python 3.12, Strands Agents SDK (with A2A support)
- bedrock-agentcore[a2a] (A2A runtime serving + Identity for GitHub token)
- gitpython (git operations)
- boto3 (S3 reads)
- httpx (HTTP client)

## Development

```bash
agentcore dev                    # local development
python3 -m pytest tests/ -v      # run unit tests (44 tests)
agentcore deploy -y              # deploy to AWS
agentcore invoke '{"task": {...}}' --stream  # invoke
```

## Design Principles

- **File-based tool I/O**: Tools read from and write to disk. The LLM never passes large content (existing posts, merged output) as tool arguments. This eliminates expensive verbatim token generation — the LLM only produces creative content (~300-word summary).
- **Deterministic merge, creative summary**: `merge_posts` handles structural merge (insert, renumber, preserve) as pure Python. The LLM only writes the day summary via `update_summary`.
- **LLM writes markdown directly for new posts**: For `publish_new`, the LLM reads structured JSON from S3 and produces the full markdown via `write_new_post`.
- **Tools read data from source**: `merge_posts` reads S3 directly (avoiding large JSON serialization through LLM tool arguments).
- **Git clone for private repo access**: Uses `git_clone` + `read_local_file` instead of raw.githubusercontent.com (which fails for private repos).
- **Git as deployment trigger**: Publisher pushes to Git. Deployment (hexo, Jekyll, etc.) is handled by CI/CD in the target repo.
