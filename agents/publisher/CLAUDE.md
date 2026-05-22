# Publisher Agent

A general-purpose editorial and publishing agent. Given content (from S3 or direct input), it can format, rewrite, merge, and publish to a Git-based blog or any target repository. Any agent can invoke it for editorial tasks.

## Deployment

- **Runtime ID**: `newspublisher_NewsPublisher-jF5YE229x9`
- **ARN**: `arn:aws:bedrock-agentcore:eu-west-1:548129671048:runtime/newspublisher_NewsPublisher-jF5YE229x9`
- **Protocol**: A2A (Agent-to-Agent) via `serve_a2a(StrandsA2AExecutor(agent, enable_a2a_compliant_streaming=True))`
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
| `read_from_s3(bucket, key)` | Read source content from S3 |
| `read_repo_file(repo, branch, path)` | Read existing file from Git repo |
| `format_post(items, template, editorial_config)` | Render Jinja2 template to markdown |
| `merge_posts(existing_content, new_items, updated_items, strategy)` | Deterministic merge: parse, match, insert new, update existing, renumber |
| `git_clone(repo, branch)` | Clone repo locally |
| `git_commit_and_push(repo_path, file_path, message)` | Commit and push changes |

## Templates

Templates are Jinja2 files stored in `templates/`:

| Template | Purpose |
|----------|---------|
| `norway_daily.md.j2` | Norwegian daily news post (sections: domestic, international, business) |
| `generic_post.md.j2` | Generic blog post (title, body, tags) |

New templates can be added for new use cases without changing agent code.

## Merge Strategy Options

| Option | Behavior |
|--------|----------|
| `new_items: "append_per_section"` | Add new topics at end of matching section |
| `new_items: "prepend_per_section"` | Add new topics at start of matching section |
| `updated_items: "replace_summary_and_add_source"` | Replace summary, add new source URL, add changelog |
| `renumber: true` | Renumber all items sequentially after merge |
| `regenerate_day_summary: true` | LLM regenerates the 今日综述 section covering all topics |

## IAM Permissions Required

- `bedrock:InvokeModel` (for summary generation, rewrites, topic matching during merge)
- `s3:GetObject` on source bucket
- `secretsmanager:GetSecretValue` (GitHub token for git push)
- Outbound internet (git push)

## Secrets

| Secret | Purpose |
|--------|---------|
| `news-agent/github-token` | GitHub bot PAT for git push (write access) |

## Tech Stack

- Python 3.12, Strands Agents SDK (with A2A support)
- bedrock-agentcore[a2a] (A2A runtime serving)
- gitpython (git operations)
- jinja2 (template rendering)
- boto3 (S3 reads, Secrets Manager)
- httpx (for reading files from public repos if needed)

## Development

```bash
agentcore dev                    # local development
python3 -m pytest tests/ -v      # run unit tests (19 tests)
agentcore deploy -y              # deploy to AWS
agentcore invoke '{"task": {...}}' --stream  # invoke
```

## Design Principles

- **Deterministic merge for structural work**: Parsing markdown, inserting items, renumbering, adding sources — this is Python code, not LLM reasoning.
- **LLM for creative/matching work**: Summary generation, topic matching (finding which existing item a new article updates), rewrites.
- **Template-driven formatting**: Post structure comes from Jinja2 templates. Ensures consistent output.
- **Git as deployment trigger**: Publisher pushes to Git. Deployment (hexo, Jekyll, etc.) is handled by CI/CD in the target repo.
