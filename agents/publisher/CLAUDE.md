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
      "new_items": "append_per_section",
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
*最后更新: 17:00 UTC*
```

## Tools

| Tool | Purpose |
|------|---------|
| `read_from_s3(bucket, key)` | Read collected items JSON from S3 |
| `read_repo_file(repo, branch, path)` | Read existing file from public GitHub repo (for merge_update) |
| `git_clone(repo, branch)` | Clone repo locally (authenticated via AgentCore Identity) |
| `git_commit_and_push(repo_path, file_path, content, commit_message)` | Write file, commit, and push |

The LLM writes markdown directly from the template format embedded in its system prompt — no Jinja2 rendering or deterministic merge tools. This avoids the LLM re-serializing large data through tool arguments.

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
- httpx (reading files from public repos)

## Development

```bash
agentcore dev                    # local development
python3 -m pytest tests/ -v      # run unit tests (20 tests)
agentcore deploy -y              # deploy to AWS
agentcore invoke '{"task": {...}}' --stream  # invoke
```

## Design Principles

- **LLM writes markdown directly**: No intermediate Jinja2 rendering or tool-based formatting. The LLM reads structured JSON from S3 and produces the final markdown in one pass.
- **Minimal data through tool arguments**: Tools read/write data; the LLM holds the content in context and produces output directly to `git_commit_and_push`.
- **Git as deployment trigger**: Publisher pushes to Git. Deployment (hexo, Jekyll, etc.) is handled by CI/CD in the target repo.
