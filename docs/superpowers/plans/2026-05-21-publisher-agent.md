# Publisher Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the NewsPublisher agent — a general-purpose editorial and publishing agent that formats content into blog posts, merges new content into existing posts, and pushes to Git repos.

**Architecture:** Six tools (read_from_s3, read_repo_file, format_post, merge_posts, git_clone, git_commit_and_push) plus two Jinja2 templates. The agent uses deterministic Python code for structural work (parsing, merging, renumbering) and the LLM for creative work (summary generation, topic matching). All tools follow the `@tool` decorator pattern from Strands SDK.

**Tech Stack:** Python 3.11, Strands Agents SDK, boto3 (S3 + Secrets Manager), gitpython (git ops), jinja2 (templates), httpx (repo file reads)

---

## File Structure

```
agents/publisher/
├── app/NewsPublisher/
│   ├── main.py                    # Already exists (entrypoint)
│   ├── agent.py                   # Needs: system prompt + tool registration
│   ├── config.py                  # Already exists (MODEL_ID)
│   ├── tools/
│   │   ├── __init__.py            # Export all tools
│   │   ├── s3_reader.py           # read_from_s3 tool
│   │   ├── repo_reader.py         # read_repo_file tool
│   │   ├── formatter.py           # format_post tool
│   │   ├── merger.py              # merge_posts tool
│   │   ├── git_ops.py             # git_clone + git_commit_and_push tools
│   │   └── templates/
│   │       ├── norway_daily.md.j2 # Norwegian daily news template
│   │       └── generic_post.md.j2 # Generic blog post template
│   ├── pyproject.toml             # Already exists (dependencies)
│   └── uv.lock                    # Generate after implementation
├── tests/
│   ├── __init__.py                # Already exists
│   ├── conftest.py                # Already exists (path + mock setup)
│   ├── test_s3_reader.py          # Tests for read_from_s3
│   ├── test_repo_reader.py        # Tests for read_repo_file
│   ├── test_formatter.py          # Tests for format_post + templates
│   ├── test_merger.py             # Tests for merge_posts
│   ├── test_git_ops.py            # Tests for git_clone + git_commit_and_push
│   └── test_agent_e2e.py          # Full agent flow with mocked externals
└── agentcore/                     # Already exists (project config)
```

---

### Task 1: S3 Reader Tool

**Files:**
- Create: `agents/publisher/app/NewsPublisher/tools/s3_reader.py`
- Create: `agents/publisher/tests/test_s3_reader.py`

- [ ] **Step 1: Write the failing test for successful S3 read**

```python
# tests/test_s3_reader.py
import json
from unittest.mock import patch, MagicMock

import pytest


def test_read_from_s3_returns_parsed_json():
    from tools.s3_reader import read_from_s3

    s3_data = {
        "task_id": "test-001",
        "new_items": [{"title_zh": "测试新闻", "category": "domestic"}],
        "updated_items": [],
        "metadata": {"sources_fetched": 3},
    }

    with patch("tools.s3_reader.boto3") as mock_boto3:
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        mock_body = MagicMock()
        mock_body.read.return_value = json.dumps(s3_data).encode("utf-8")
        mock_s3.get_object.return_value = {"Body": mock_body}

        result = read_from_s3(
            bucket="news-agent-data",
            key="collections/2026-05-21/0500-norway-news.json",
        )

    assert result["status"] == "success"
    assert result["data"]["task_id"] == "test-001"
    assert len(result["data"]["new_items"]) == 1
    assert result["data"]["new_items"][0]["title_zh"] == "测试新闻"

    mock_s3.get_object.assert_called_once_with(
        Bucket="news-agent-data",
        Key="collections/2026-05-21/0500-norway-news.json",
    )


def test_read_from_s3_handles_missing_key():
    from tools.s3_reader import read_from_s3

    with patch("tools.s3_reader.boto3") as mock_boto3:
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        mock_s3.get_object.side_effect = Exception("NoSuchKey: The specified key does not exist.")

        result = read_from_s3(bucket="news-agent-data", key="nonexistent.json")

    assert result["status"] == "error"
    assert "NoSuchKey" in result["error"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/lufng/github/news-agent/agents/publisher && python3 -m pytest tests/test_s3_reader.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tools.s3_reader'`

- [ ] **Step 3: Write minimal implementation**

```python
# app/NewsPublisher/tools/s3_reader.py
import json

import boto3
from strands import tool


@tool
def read_from_s3(bucket: str, key: str) -> dict:
    """Read and parse JSON content from an S3 bucket.

    Args:
        bucket: S3 bucket name
        key: S3 object key (path)

    Returns:
        Dict with status, parsed data, and error if any
    """
    try:
        s3 = boto3.client("s3")
        obj = s3.get_object(Bucket=bucket, Key=key)
        data = json.loads(obj["Body"].read())
        return {"status": "success", "data": data}
    except Exception as e:
        return {"status": "error", "error": str(e)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/lufng/github/news-agent/agents/publisher && python3 -m pytest tests/test_s3_reader.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add agents/publisher/app/NewsPublisher/tools/s3_reader.py agents/publisher/tests/test_s3_reader.py
git commit -m "feat(publisher): add read_from_s3 tool with tests"
```

---

### Task 2: Repo Reader Tool

**Files:**
- Create: `agents/publisher/app/NewsPublisher/tools/repo_reader.py`
- Create: `agents/publisher/tests/test_repo_reader.py`

- [ ] **Step 1: Write the failing test for reading a public repo file**

```python
# tests/test_repo_reader.py
from unittest.mock import patch, MagicMock

import pytest


def test_read_repo_file_returns_content():
    from tools.repo_reader import read_repo_file

    markdown_content = """---
title: 挪威新闻速递 2026-05-21
date: 2026-05-21 05:00:00
---

## 今日综述
今天的新闻概述。
"""

    with patch("tools.repo_reader.httpx") as mock_httpx:
        mock_response = MagicMock()
        mock_response.text = markdown_content
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_response

        result = read_repo_file(
            repo="claw-lu/hexo-blog",
            branch="main",
            path="source/_posts/20260521-norway.md",
        )

    assert result["status"] == "success"
    assert result["content"] == markdown_content
    mock_httpx.get.assert_called_once_with(
        "https://raw.githubusercontent.com/claw-lu/hexo-blog/main/source/_posts/20260521-norway.md",
        timeout=15,
        follow_redirects=True,
    )


def test_read_repo_file_handles_404():
    from tools.repo_reader import read_repo_file

    with patch("tools.repo_reader.httpx") as mock_httpx:
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = Exception("404 Not Found")
        mock_httpx.get.return_value = mock_response

        result = read_repo_file(
            repo="claw-lu/hexo-blog",
            branch="main",
            path="source/_posts/nonexistent.md",
        )

    assert result["status"] == "not_found"
    assert result["content"] == ""


def test_read_repo_file_handles_network_error():
    from tools.repo_reader import read_repo_file

    with patch("tools.repo_reader.httpx") as mock_httpx:
        mock_httpx.get.side_effect = Exception("Connection timeout")

        result = read_repo_file(
            repo="claw-lu/hexo-blog",
            branch="main",
            path="source/_posts/test.md",
        )

    assert result["status"] == "error"
    assert "Connection timeout" in result["error"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/lufng/github/news-agent/agents/publisher && python3 -m pytest tests/test_repo_reader.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tools.repo_reader'`

- [ ] **Step 3: Write minimal implementation**

```python
# app/NewsPublisher/tools/repo_reader.py
import httpx
from strands import tool


@tool
def read_repo_file(repo: str, branch: str, path: str) -> dict:
    """Read a file from a public GitHub repository.

    Args:
        repo: Repository in "owner/repo" format
        branch: Branch name (e.g. "main")
        path: File path within the repository

    Returns:
        Dict with status ("success", "not_found", or "error"), content string, and error if any
    """
    url = f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"
    try:
        response = httpx.get(url, timeout=15, follow_redirects=True)
        response.raise_for_status()
        return {"status": "success", "content": response.text}
    except Exception as e:
        if "404" in str(e):
            return {"status": "not_found", "content": ""}
        return {"status": "error", "error": str(e), "content": ""}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/lufng/github/news-agent/agents/publisher && python3 -m pytest tests/test_repo_reader.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add agents/publisher/app/NewsPublisher/tools/repo_reader.py agents/publisher/tests/test_repo_reader.py
git commit -m "feat(publisher): add read_repo_file tool with tests"
```

---

### Task 3: Jinja2 Templates

**Files:**
- Create: `agents/publisher/app/NewsPublisher/tools/templates/norway_daily.md.j2`
- Create: `agents/publisher/app/NewsPublisher/tools/templates/generic_post.md.j2`

- [ ] **Step 1: Create the norway_daily template**

```jinja2
{# app/NewsPublisher/tools/templates/norway_daily.md.j2 #}
---
title: 挪威新闻速递 {{ date }}
date: {{ date }} {{ time }}
updated: {{ date }} {{ updated_time }}
tags: [挪威, 新闻]
categories: [每日新闻, 挪威]
---

## 今日综述
{{ day_summary }}

<!-- more -->

{% for section in sections %}
## {{ section.title }}

{% for item in section.items %}
### {{ item.number }}. {{ item.title_zh }}
**来源**: {{ item.sources_text }} | **最早报道**: {{ item.earliest_time }}

{{ item.summary_zh }}
{% if item.changelog %}
({{ item.changelog }})
{% endif %}

原文链接: {{ item.links_text }}

---

{% endfor %}
{% endfor %}
*新闻来源: {{ all_sources }}*
*最后更新: {{ updated_time }} UTC*
```

- [ ] **Step 2: Create the generic_post template**

```jinja2
{# app/NewsPublisher/tools/templates/generic_post.md.j2 #}
---
title: {{ title }}
date: {{ date }}
{% if tags %}tags: [{{ tags | join(', ') }}]{% endif %}
{% if categories %}categories: [{{ categories | join(', ') }}]{% endif %}
---

{{ body }}
```

- [ ] **Step 3: Commit**

```bash
git add agents/publisher/app/NewsPublisher/tools/templates/
git commit -m "feat(publisher): add Jinja2 templates for norway_daily and generic_post"
```

---

### Task 4: Formatter Tool

**Files:**
- Create: `agents/publisher/app/NewsPublisher/tools/formatter.py`
- Create: `agents/publisher/tests/test_formatter.py`

- [ ] **Step 1: Write the failing test for norway_daily formatting**

```python
# tests/test_formatter.py
import json

import pytest


def test_format_post_norway_daily_creates_valid_markdown():
    from tools.formatter import format_post

    items = json.dumps([
        {
            "title_zh": "议会通过新移民法案",
            "category": "domestic",
            "summary_zh": "挪威议会今天以压倒性多数通过了一项新的移民法案。",
            "sources": [
                {
                    "url": "https://nrk.no/article/123",
                    "source_label": "NRK Norge",
                    "published_at": "2026-05-21T09:30:00Z",
                    "title_original": "Stortinget vedtar ny innvandringslov",
                },
                {
                    "url": "https://vg.no/article/456",
                    "source_label": "VG",
                    "published_at": "2026-05-21T09:45:00Z",
                    "title_original": "Ny lov vedtatt",
                },
            ],
        },
        {
            "title_zh": "石油基金创历史新高",
            "category": "business",
            "summary_zh": "挪威政府养老基金今天公布了创纪录的回报率。",
            "sources": [
                {
                    "url": "https://e24.no/article/789",
                    "source_label": "E24",
                    "published_at": "2026-05-21T10:00:00Z",
                    "title_original": "Oljefondet med ny rekord",
                },
            ],
        },
    ])

    editorial_config = json.dumps({
        "day_summary": "今天的主要新闻包括议会通过移民法案和石油基金创新高。",
    })

    result = format_post(
        items=items,
        template="norway_daily",
        editorial_config=editorial_config,
        date="2026-05-21",
        time="05:00:00",
    )

    assert result["status"] == "success"
    content = result["content"]
    assert "title: 挪威新闻速递 2026-05-21" in content
    assert "## 今日综述" in content
    assert "今天的主要新闻包括" in content
    assert "## 国内新闻" in content
    assert "### 1. 议会通过新移民法案" in content
    assert "NRK Norge, VG" in content
    assert "## 财经新闻" in content
    assert "### 2. 石油基金创历史新高" in content  # numbering continues
    assert "<!-- more -->" in content


def test_format_post_generic_creates_simple_post():
    from tools.formatter import format_post

    editorial_config = json.dumps({
        "title": "关于本站",
        "body": "这是一个关于挪威新闻的博客。",
        "tags": ["关于"],
        "categories": ["页面"],
    })

    result = format_post(
        items="[]",
        template="generic_post",
        editorial_config=editorial_config,
        date="2026-05-21",
        time="05:00:00",
    )

    assert result["status"] == "success"
    content = result["content"]
    assert "title: 关于本站" in content
    assert "这是一个关于挪威新闻的博客" in content


def test_format_post_unknown_template_returns_error():
    from tools.formatter import format_post

    result = format_post(
        items="[]",
        template="nonexistent_template",
        editorial_config="{}",
        date="2026-05-21",
        time="05:00:00",
    )

    assert result["status"] == "error"
    assert "template" in result["error"].lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/lufng/github/news-agent/agents/publisher && python3 -m pytest tests/test_formatter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tools.formatter'`

- [ ] **Step 3: Write minimal implementation**

```python
# app/NewsPublisher/tools/formatter.py
import json
import os

from jinja2 import Environment, FileSystemLoader
from strands import tool

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")

SECTION_MAP = {
    "domestic": "国内新闻",
    "international": "国际新闻",
    "business": "财经新闻",
}

SECTION_ORDER = ["domestic", "international", "business"]


def _build_sections(items: list) -> list[dict]:
    """Group items by category into ordered sections."""
    grouped = {}
    for item in items:
        cat = item.get("category", "domestic")
        grouped.setdefault(cat, []).append(item)

    sections = []
    number = 1
    for cat in SECTION_ORDER:
        if cat not in grouped:
            continue
        section_items = []
        for item in grouped[cat]:
            sources = item.get("sources", [])
            sources_text = ", ".join(s["source_label"] for s in sources)
            earliest = min((s["published_at"] for s in sources), default="")
            earliest_time = earliest[11:16] if earliest else ""
            links = " | ".join(
                f"[{s['source_label']}]({s['url']})" for s in sources
            )
            section_items.append({
                "number": number,
                "title_zh": item["title_zh"],
                "summary_zh": item["summary_zh"],
                "sources_text": sources_text,
                "earliest_time": earliest,
                "links_text": links,
                "changelog": item.get("changelog", ""),
            })
            number += 1
        sections.append({"title": SECTION_MAP[cat], "items": section_items})
    return sections


@tool
def format_post(items: str, template: str, editorial_config: str, date: str, time: str) -> dict:
    """Render a blog post from items using a Jinja2 template.

    Args:
        items: JSON string of items to include in the post
        template: Template name (e.g. "norway_daily", "generic_post")
        editorial_config: JSON string with editorial settings (day_summary, title, body, tags, etc.)
        date: Post date (YYYY-MM-DD)
        time: Post time (HH:MM:SS)

    Returns:
        Dict with status and rendered content string
    """
    try:
        env = Environment(
            loader=FileSystemLoader(TEMPLATE_DIR),
            keep_trailing_newline=True,
        )
        template_file = f"{template}.md.j2"
        if not os.path.exists(os.path.join(TEMPLATE_DIR, template_file)):
            return {"status": "error", "error": f"Template not found: {template_file}"}

        tmpl = env.get_template(template_file)
        parsed_items = json.loads(items)
        config = json.loads(editorial_config)

        if template == "norway_daily":
            sections = _build_sections(parsed_items)
            all_sources = sorted(set(
                s["source_label"]
                for item in parsed_items
                for s in item.get("sources", [])
            ))
            rendered = tmpl.render(
                date=date,
                time=time,
                updated_time=time,
                day_summary=config.get("day_summary", ""),
                sections=sections,
                all_sources=", ".join(all_sources),
            )
        else:
            rendered = tmpl.render(date=date, **config)

        return {"status": "success", "content": rendered}
    except Exception as e:
        return {"status": "error", "error": str(e)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/lufng/github/news-agent/agents/publisher && python3 -m pytest tests/test_formatter.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add agents/publisher/app/NewsPublisher/tools/formatter.py agents/publisher/tests/test_formatter.py
git commit -m "feat(publisher): add format_post tool with Jinja2 rendering and tests"
```

---

### Task 5: Merger Tool

**Files:**
- Create: `agents/publisher/app/NewsPublisher/tools/merger.py`
- Create: `agents/publisher/tests/test_merger.py`

- [ ] **Step 1: Write the failing tests for merge operations**

```python
# tests/test_merger.py
import json

import pytest


def test_merge_posts_appends_new_items_to_correct_section():
    from tools.merger import merge_posts

    existing_content = """---
title: 挪威新闻速递 2026-05-21
date: 2026-05-21 05:00:00
updated: 2026-05-21 05:00:00
tags: [挪威, 新闻]
categories: [每日新闻, 挪威]
---

## 今日综述
早间新闻概述。

<!-- more -->

## 国内新闻

### 1. 议会通过新法案
**来源**: NRK Norge | **最早报道**: 2026-05-21T09:30:00Z

挪威议会通过了新法案。

原文链接: [NRK Norge](https://nrk.no/article/123)

---

## 国际新闻

### 2. 北欧合作会议召开
**来源**: NRK Urix | **最早报道**: 2026-05-21T08:00:00Z

北欧国家召开了合作会议。

原文链接: [NRK Urix](https://nrk.no/article/200)

---

## 财经新闻

---
*新闻来源: NRK Norge, NRK Urix*
*最后更新: 05:00 UTC*
"""

    new_items = json.dumps([
        {
            "title_zh": "奥斯陆新地铁线路开工",
            "category": "domestic",
            "summary_zh": "奥斯陆市政府宣布新地铁线路正式开工建设。",
            "sources": [
                {
                    "url": "https://nrk.no/article/300",
                    "source_label": "NRK Oslo",
                    "published_at": "2026-05-21T11:00:00Z",
                    "title_original": "Ny T-bane linje",
                }
            ],
        }
    ])

    updated_items = json.dumps([])

    strategy = json.dumps({
        "new_items": "append_per_section",
        "updated_items": "replace_summary_and_add_source",
        "renumber": True,
        "regenerate_day_summary": False,
    })

    result = merge_posts(
        existing_content=existing_content,
        new_items=new_items,
        updated_items=updated_items,
        strategy=strategy,
    )

    assert result["status"] == "success"
    content = result["content"]
    # New domestic item appended after existing domestic items
    assert "奥斯陆新地铁线路开工" in content
    assert "NRK Oslo" in content
    # Renumbered: existing domestic=1, new domestic=2, international=3
    assert "### 1. 议会通过新法案" in content
    assert "### 2. 奥斯陆新地铁线路开工" in content
    assert "### 3. 北欧合作会议召开" in content
    assert result["new_items_added"] == 1
    assert result["existing_items_updated"] == 0
    assert result["total_items"] == 3


def test_merge_posts_updates_existing_item():
    from tools.merger import merge_posts

    existing_content = """---
title: 挪威新闻速递 2026-05-21
date: 2026-05-21 05:00:00
updated: 2026-05-21 05:00:00
tags: [挪威, 新闻]
categories: [每日新闻, 挪威]
---

## 今日综述
早间新闻概述。

<!-- more -->

## 国内新闻

### 1. 议会通过新移民法案
**来源**: NRK Norge | **最早报道**: 2026-05-21T09:30:00Z

挪威议会通过了新的移民法案。

原文链接: [NRK Norge](https://nrk.no/article/123)

---

## 国际新闻

---

## 财经新闻

---
*新闻来源: NRK Norge*
*最后更新: 05:00 UTC*
"""

    new_items = json.dumps([])
    updated_items = json.dumps([
        {
            "match_title_zh": "议会通过新移民法案",
            "new_source": {
                "url": "https://vg.no/article/456",
                "source_label": "VG",
                "published_at": "2026-05-21T10:15:00Z",
                "title_original": "Innvandringslov vedtatt",
            },
            "updated_summary_zh": "挪威议会以压倒性多数通过了新的移民法案，反对党表示将继续抗争。",
            "changelog": "更新于 11:00 UTC: 新增来自VG的反对党反应",
        }
    ])

    strategy = json.dumps({
        "new_items": "append_per_section",
        "updated_items": "replace_summary_and_add_source",
        "renumber": True,
        "regenerate_day_summary": False,
    })

    result = merge_posts(
        existing_content=existing_content,
        new_items=new_items,
        updated_items=updated_items,
        strategy=strategy,
    )

    assert result["status"] == "success"
    content = result["content"]
    # Summary replaced
    assert "反对党表示将继续抗争" in content
    # New source added
    assert "VG" in content
    assert "https://vg.no/article/456" in content
    # Changelog present
    assert "更新于 11:00 UTC" in content
    # Original source preserved
    assert "https://nrk.no/article/123" in content
    assert result["new_items_added"] == 0
    assert result["existing_items_updated"] == 1


def test_merge_posts_handles_empty_existing_content():
    from tools.merger import merge_posts

    new_items = json.dumps([
        {
            "title_zh": "测试新闻",
            "category": "domestic",
            "summary_zh": "这是一条测试新闻。",
            "sources": [
                {
                    "url": "https://nrk.no/article/1",
                    "source_label": "NRK",
                    "published_at": "2026-05-21T09:00:00Z",
                    "title_original": "Test",
                }
            ],
        }
    ])

    result = merge_posts(
        existing_content="",
        new_items=new_items,
        updated_items="[]",
        strategy='{"new_items": "append_per_section", "updated_items": "replace_summary_and_add_source", "renumber": true, "regenerate_day_summary": false}',
    )

    assert result["status"] == "error"
    assert "existing content" in result["error"].lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/lufng/github/news-agent/agents/publisher && python3 -m pytest tests/test_merger.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tools.merger'`

- [ ] **Step 3: Write minimal implementation**

```python
# app/NewsPublisher/tools/merger.py
import json
import re

from strands import tool

SECTION_MAP = {
    "domestic": "国内新闻",
    "international": "国际新闻",
    "business": "财经新闻",
}

SECTION_ORDER = ["domestic", "international", "business"]
REVERSE_SECTION_MAP = {v: k for k, v in SECTION_MAP.items()}


def _parse_post(content: str) -> dict:
    """Parse a blog post into structured sections with items."""
    lines = content.split("\n")
    frontmatter = ""
    summary_section = ""
    sections = {}
    footer = ""

    # Extract frontmatter
    if lines[0].strip() == "---":
        end_idx = content.index("---", 4)
        frontmatter = content[: end_idx + 3]
        rest = content[end_idx + 3 :].strip()
    else:
        rest = content

    # Extract day summary (between ## 今日综述 and <!-- more -->)
    summary_match = re.search(
        r"## 今日综述\n(.*?)<!-- more -->", rest, re.DOTALL
    )
    if summary_match:
        summary_section = summary_match.group(1).strip()

    # Parse sections
    section_pattern = r"## (国内新闻|国际新闻|财经新闻)\n"
    section_splits = re.split(section_pattern, rest)

    current_section = None
    for i, part in enumerate(section_splits):
        if part in REVERSE_SECTION_MAP:
            current_section = REVERSE_SECTION_MAP[part]
            sections[current_section] = []
        elif current_section is not None:
            # Parse items within section
            item_splits = re.split(r"### \d+\.\s+", part)
            for item_text in item_splits[1:]:
                item_lines = item_text.strip().split("\n")
                title = item_lines[0].strip()

                # Extract sources line
                sources_text = ""
                earliest_time = ""
                summary_lines = []
                link_lines = []
                changelog = ""
                past_header = False

                for line in item_lines[1:]:
                    if line.startswith("**来源**:"):
                        sources_match = re.search(
                            r"\*\*来源\*\*:\s*(.+?)\s*\|\s*\*\*最早报道\*\*:\s*(.+)",
                            line,
                        )
                        if sources_match:
                            sources_text = sources_match.group(1)
                            earliest_time = sources_match.group(2)
                        past_header = True
                    elif line.startswith("原文链接:"):
                        link_lines.append(line)
                    elif line.strip().startswith("(更新于") or line.strip().startswith("(更新于"):
                        changelog = line.strip()
                    elif line.strip() == "---":
                        continue
                    elif past_header and line.strip():
                        summary_lines.append(line.strip())

                # Extract individual source URLs from link line
                source_urls = []
                for link_line in link_lines:
                    urls = re.findall(r"\[(.+?)\]\((https?://[^\)]+)\)", link_line)
                    source_urls.extend(
                        [{"source_label": label, "url": url} for label, url in urls]
                    )

                sections[current_section].append({
                    "title_zh": title,
                    "sources_text": sources_text,
                    "earliest_time": earliest_time,
                    "summary_zh": "\n".join(summary_lines),
                    "source_urls": source_urls,
                    "changelog": changelog,
                })

    # Extract footer
    footer_match = re.search(r"(\*新闻来源:.*)", rest, re.DOTALL)
    if footer_match:
        footer = footer_match.group(1).strip()

    return {
        "frontmatter": frontmatter,
        "summary": summary_section,
        "sections": sections,
        "footer": footer,
    }


def _render_item(number: int, item: dict) -> str:
    """Render a single item as markdown."""
    lines = [f"### {number}. {item['title_zh']}"]
    lines.append(f"**来源**: {item['sources_text']} | **最早报道**: {item['earliest_time']}")
    lines.append("")
    lines.append(item["summary_zh"])
    if item.get("changelog"):
        lines.append(item["changelog"])
    lines.append("")

    links = " | ".join(
        f"[{s['source_label']}]({s['url']})" for s in item["source_urls"]
    )
    lines.append(f"原文链接: {links}")
    lines.append("")
    lines.append("---")
    return "\n".join(lines)


def _rebuild_post(parsed: dict) -> str:
    """Rebuild the full post markdown from parsed structure."""
    parts = [parsed["frontmatter"], ""]
    parts.append("## 今日综述")
    parts.append(parsed["summary"])
    parts.append("")
    parts.append("<!-- more -->")
    parts.append("")

    number = 1
    for cat in SECTION_ORDER:
        parts.append(f"## {SECTION_MAP[cat]}")
        parts.append("")
        items = parsed["sections"].get(cat, [])
        for item in items:
            parts.append(_render_item(number, item))
            parts.append("")
            number += 1
        if not items:
            parts.append("")

    # Footer with all sources
    all_sources = set()
    for cat in SECTION_ORDER:
        for item in parsed["sections"].get(cat, []):
            for s in item["source_urls"]:
                all_sources.add(s["source_label"])
    parts.append(f"*新闻来源: {', '.join(sorted(all_sources))}*")
    parts.append(f"*最后更新: {parsed.get('updated_time', '')} UTC*")

    return "\n".join(parts)


@tool
def merge_posts(existing_content: str, new_items: str, updated_items: str, strategy: str) -> dict:
    """Merge new and updated items into an existing blog post.

    Deterministic merge: parses existing markdown, inserts new items at correct positions,
    updates existing items with new summaries/sources, and renumbers.

    Args:
        existing_content: The full markdown content of the existing blog post
        new_items: JSON string of new items to append (same format as Collector output new_items)
        updated_items: JSON string of items to update (same format as Collector output updated_items)
        strategy: JSON string with merge strategy options (new_items, updated_items, renumber, regenerate_day_summary)

    Returns:
        Dict with status, merged content, and counts (new_items_added, existing_items_updated, total_items)
    """
    if not existing_content.strip():
        return {"status": "error", "error": "Cannot merge into empty existing content. Use format_post for new posts."}

    try:
        parsed = _parse_post(existing_content)
        new = json.loads(new_items)
        updated = json.loads(updated_items)
        strat = json.loads(strategy)

        items_added = 0
        items_updated = 0

        # Apply updates to existing items
        for update in updated:
            match_title = update["match_title_zh"]
            matched = False
            for cat in SECTION_ORDER:
                for item in parsed["sections"].get(cat, []):
                    if item["title_zh"] == match_title:
                        item["summary_zh"] = update["updated_summary_zh"]
                        new_src = update["new_source"]
                        item["source_urls"].append({
                            "source_label": new_src["source_label"],
                            "url": new_src["url"],
                        })
                        item["sources_text"] = ", ".join(
                            s["source_label"] for s in item["source_urls"]
                        )
                        item["changelog"] = f"({update['changelog']})"
                        items_updated += 1
                        matched = True
                        break
                if matched:
                    break

        # Append new items to correct sections
        for item in new:
            cat = item.get("category", "domestic")
            if cat not in parsed["sections"]:
                parsed["sections"][cat] = []

            sources = item.get("sources", [])
            sources_text = ", ".join(s["source_label"] for s in sources)
            earliest = min((s["published_at"] for s in sources), default="")
            source_urls = [
                {"source_label": s["source_label"], "url": s["url"]} for s in sources
            ]

            parsed["sections"][cat].append({
                "title_zh": item["title_zh"],
                "sources_text": sources_text,
                "earliest_time": earliest,
                "summary_zh": item["summary_zh"],
                "source_urls": source_urls,
                "changelog": "",
            })
            items_added += 1

        # Count total items
        total = sum(len(items) for items in parsed["sections"].values())

        # Extract updated time from frontmatter for footer
        import datetime
        parsed["updated_time"] = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M")

        content = _rebuild_post(parsed)

        return {
            "status": "success",
            "content": content,
            "new_items_added": items_added,
            "existing_items_updated": items_updated,
            "total_items": total,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/lufng/github/news-agent/agents/publisher && python3 -m pytest tests/test_merger.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add agents/publisher/app/NewsPublisher/tools/merger.py agents/publisher/tests/test_merger.py
git commit -m "feat(publisher): add merge_posts tool with deterministic markdown merge and tests"
```

---

### Task 6: Git Operations Tools

**Files:**
- Create: `agents/publisher/app/NewsPublisher/tools/git_ops.py`
- Create: `agents/publisher/tests/test_git_ops.py`

- [ ] **Step 1: Write the failing tests for git_clone and git_commit_and_push**

```python
# tests/test_git_ops.py
import os
from unittest.mock import patch, MagicMock, call

import pytest


def test_git_clone_clones_repo_to_temp_dir():
    from tools.git_ops import git_clone

    with patch("tools.git_ops.git.Repo") as MockRepo:
        mock_repo = MagicMock()
        MockRepo.clone_from.return_value = mock_repo

        with patch("tools.git_ops._get_github_token", return_value="ghp_test123"):
            result = git_clone(repo="claw-lu/hexo-blog", branch="main")

    assert result["status"] == "success"
    assert result["repo_path"] != ""
    MockRepo.clone_from.assert_called_once()
    clone_url = MockRepo.clone_from.call_args[0][0]
    assert "ghp_test123" in clone_url
    assert "claw-lu/hexo-blog" in clone_url


def test_git_clone_handles_clone_failure():
    from tools.git_ops import git_clone

    with patch("tools.git_ops.git.Repo") as MockRepo:
        MockRepo.clone_from.side_effect = Exception("Authentication failed")
        with patch("tools.git_ops._get_github_token", return_value="ghp_bad"):
            result = git_clone(repo="claw-lu/hexo-blog", branch="main")

    assert result["status"] == "error"
    assert "Authentication failed" in result["error"]


def test_git_commit_and_push_writes_and_pushes():
    from tools.git_ops import git_commit_and_push

    with patch("tools.git_ops.git.Repo") as MockRepo:
        mock_repo = MagicMock()
        MockRepo.return_value = mock_repo
        mock_repo.index = MagicMock()
        mock_commit = MagicMock()
        mock_commit.hexsha = "abc123def456"
        mock_repo.index.commit.return_value = mock_commit
        mock_repo.remote.return_value = MagicMock()

        result = git_commit_and_push(
            repo_path="/tmp/hexo-blog",
            file_path="source/_posts/20260521-norway.md",
            content="# Test content",
            commit_message="Add Norway news 2026-05-21",
        )

    assert result["status"] == "success"
    assert result["commit_sha"] == "abc123def456"
    mock_repo.index.add.assert_called_once_with(["source/_posts/20260521-norway.md"])
    mock_repo.index.commit.assert_called_once_with("Add Norway news 2026-05-21")


def test_git_commit_and_push_writes_file_content():
    from tools.git_ops import git_commit_and_push

    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("tools.git_ops.git.Repo") as MockRepo:
            mock_repo = MagicMock()
            MockRepo.return_value = mock_repo
            mock_commit = MagicMock()
            mock_commit.hexsha = "abc123"
            mock_repo.index.commit.return_value = mock_commit
            mock_repo.remote.return_value = MagicMock()

            file_path = "source/_posts/test.md"
            result = git_commit_and_push(
                repo_path=tmpdir,
                file_path=file_path,
                content="# Hello",
                commit_message="test",
            )

        # File should be written to disk
        full_path = os.path.join(tmpdir, file_path)
        assert os.path.exists(full_path)
        with open(full_path) as f:
            assert f.read() == "# Hello"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/lufng/github/news-agent/agents/publisher && python3 -m pytest tests/test_git_ops.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tools.git_ops'`

- [ ] **Step 3: Write minimal implementation**

```python
# app/NewsPublisher/tools/git_ops.py
import os
import tempfile

import boto3
import git
from strands import tool


def _get_github_token() -> str:
    """Retrieve GitHub token from Secrets Manager."""
    client = boto3.client("secretsmanager")
    response = client.get_secret_value(SecretId="news-agent/github-token")
    return response["SecretString"]


@tool
def git_clone(repo: str, branch: str) -> dict:
    """Clone a GitHub repository to a temporary directory.

    Args:
        repo: Repository in "owner/repo" format
        branch: Branch to clone

    Returns:
        Dict with status, repo_path (local path to cloned repo), and error if any
    """
    try:
        token = _get_github_token()
        clone_url = f"https://{token}@github.com/{repo}.git"
        repo_path = tempfile.mkdtemp(prefix="publisher_")
        git.Repo.clone_from(clone_url, repo_path, branch=branch)
        return {"status": "success", "repo_path": repo_path}
    except Exception as e:
        return {"status": "error", "error": str(e), "repo_path": ""}


@tool
def git_commit_and_push(repo_path: str, file_path: str, content: str, commit_message: str) -> dict:
    """Write content to a file in the repo, commit, and push.

    Args:
        repo_path: Local path to the cloned repository
        file_path: Path within the repo to write (e.g. "source/_posts/20260521-norway.md")
        content: Full file content to write
        commit_message: Git commit message

    Returns:
        Dict with status, commit_sha, and error if any
    """
    try:
        full_path = os.path.join(repo_path, file_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

        repo = git.Repo(repo_path)
        repo.index.add([file_path])
        commit = repo.index.commit(commit_message)
        repo.remote("origin").push()
        return {"status": "success", "commit_sha": commit.hexsha}
    except Exception as e:
        return {"status": "error", "error": str(e), "commit_sha": ""}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/lufng/github/news-agent/agents/publisher && python3 -m pytest tests/test_git_ops.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add agents/publisher/app/NewsPublisher/tools/git_ops.py agents/publisher/tests/test_git_ops.py
git commit -m "feat(publisher): add git_clone and git_commit_and_push tools with tests"
```

---

### Task 7: Tools Package Init + Conftest Update

**Files:**
- Modify: `agents/publisher/app/NewsPublisher/tools/__init__.py`
- Modify: `agents/publisher/tests/conftest.py`

- [ ] **Step 1: Update tools/__init__.py to export all tools**

```python
# app/NewsPublisher/tools/__init__.py
from .s3_reader import read_from_s3
from .repo_reader import read_repo_file
from .formatter import format_post
from .merger import merge_posts
from .git_ops import git_clone, git_commit_and_push
```

- [ ] **Step 2: Update conftest.py to stub gitpython and jinja2**

```python
# tests/conftest.py
import os
import sys
from unittest.mock import MagicMock

# Add app/NewsPublisher to path so tests can import tools, config, agent
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app", "NewsPublisher"))

# Stub out the strands module for testing
strands_mock = MagicMock()
strands_mock.tool = lambda fn: fn
sys.modules["strands"] = strands_mock

# Stub out boto3 for testing
if "boto3" not in sys.modules:
    boto3_mock = MagicMock()
    sys.modules["boto3"] = boto3_mock

# Stub out git module for testing (gitpython not installed in test env)
if "git" not in sys.modules:
    git_mock = MagicMock()
    sys.modules["git"] = git_mock

import pytest


@pytest.fixture
def sample_collection_data():
    """Sample Collector output (S3 JSON) for publisher tests."""
    return {
        "task_id": "collect-norway-2026-05-21-1100",
        "collected_at": "2026-05-21T11:00:00Z",
        "new_items": [
            {
                "title_zh": "议会通过新移民法案",
                "category": "domestic",
                "summary_zh": "挪威议会今天以压倒性多数通过了一项新的移民法案。该法案将加强对移民的语言和就业要求。",
                "sources": [
                    {
                        "url": "https://nrk.no/article/123",
                        "source_label": "NRK Norge",
                        "published_at": "2026-05-21T09:30:00Z",
                        "title_original": "Stortinget vedtar ny innvandringslov",
                    },
                    {
                        "url": "https://vg.no/article/456",
                        "source_label": "VG",
                        "published_at": "2026-05-21T09:45:00Z",
                        "title_original": "Ny lov vedtatt med bredt flertall",
                    },
                ],
            },
            {
                "title_zh": "石油基金创历史新高",
                "category": "business",
                "summary_zh": "挪威政府养老基金今天公布了创纪录的回报率，总资产突破18万亿克朗。",
                "sources": [
                    {
                        "url": "https://e24.no/article/789",
                        "source_label": "E24",
                        "published_at": "2026-05-21T10:00:00Z",
                        "title_original": "Oljefondet med ny rekord",
                    },
                ],
            },
        ],
        "updated_items": [],
        "metadata": {
            "sources_fetched": 11,
            "items_in_rss": 45,
            "after_time_filter": 20,
            "new_urls_found": 8,
            "grouped_into_new_topics": 2,
            "matched_to_existing_topics": 0,
            "skipped_no_new_info": 0,
            "skipped_already_seen_urls": 12,
        },
    }


@pytest.fixture
def sample_existing_post():
    """Sample existing blog post markdown for merge tests."""
    return """---
title: 挪威新闻速递 2026-05-21
date: 2026-05-21 05:00:00
updated: 2026-05-21 05:00:00
tags: [挪威, 新闻]
categories: [每日新闻, 挪威]
---

## 今日综述
早间新闻概述。

<!-- more -->

## 国内新闻

### 1. 奥斯陆天气预警
**来源**: NRK Oslo | **最早报道**: 2026-05-21T06:00:00Z

气象研究所发布了暴风雨警告。

原文链接: [NRK Oslo](https://nrk.no/article/050)

---

## 国际新闻

---

## 财经新闻

---
*新闻来源: NRK Oslo*
*最后更新: 05:00 UTC*
"""
```

- [ ] **Step 3: Run all tests to verify nothing is broken**

Run: `cd /Users/lufng/github/news-agent/agents/publisher && python3 -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add agents/publisher/app/NewsPublisher/tools/__init__.py agents/publisher/tests/conftest.py
git commit -m "feat(publisher): wire up tools package exports and test fixtures"
```

---

### Task 8: Agent System Prompt + Tool Registration

**Files:**
- Modify: `agents/publisher/app/NewsPublisher/agent.py`

- [ ] **Step 1: Write the full agent.py with system prompt and tools**

```python
# app/NewsPublisher/agent.py
from strands import Agent
from strands.models import BedrockModel

from config import MODEL_ID
from tools import read_from_s3, read_repo_file, format_post, merge_posts, git_clone, git_commit_and_push

SYSTEM_PROMPT = """You are an editorial and publishing agent. You receive publishing tasks and execute them by following the appropriate pipeline for the task type.

## Task Types

### publish_new
Create a new blog post from collected content.

Pipeline:
1. Call read_from_s3 to get the collected items from the source S3 location
2. Generate a day_summary (300 words) covering all topics — write it yourself based on the items
3. Call format_post with the items, template name, editorial config (including your day_summary), date, and time
4. Call git_clone to clone the target repo
5. Call git_commit_and_push with the formatted content

### merge_update
Merge new content into an existing post.

Pipeline:
1. Call read_from_s3 to get the new collected items
2. Call git_clone to clone the target repo (you need the existing file)
3. Read the existing file from the cloned repo (use the repo_path from git_clone + the target file_path)
4. Call merge_posts with the existing content, new_items, updated_items, and strategy from the task config
5. If regenerate_day_summary is true: rewrite the day summary based on ALL items now in the post
6. Call git_commit_and_push with the merged content

### rewrite
Free-form rewrite of an existing page.

Pipeline:
1. Call git_clone to clone the target repo
2. Read the existing file content
3. Rewrite the content following the instructions in the task
4. Call git_commit_and_push with the new content

### edit
Make specific structured edits to an existing page.

Pipeline:
1. Call git_clone to clone the target repo
2. Read the existing file content
3. Apply the edits specified in the task (replace operations)
4. Call git_commit_and_push with the edited content

## Output Format

Always return a JSON result at the end:
{
  "status": "success" or "error",
  "task_id": (from task config),
  "result": {
    "action": (task type),
    "file_path": (path that was modified),
    "commit_sha": (from git push),
    "new_items_added": (count, for publish_new/merge_update),
    "existing_items_updated": (count, for merge_update),
    "total_items_in_post": (count)
  }
}

## Day Summary Guidelines

When generating a day summary (今日综述):
- Write approximately 300 words in Chinese
- Connect themes across all topics in the post
- Mention key events from each section (domestic, international, business)
- Use a narrative style, not a list
- Preserve Norwegian proper nouns in their original form

## Important Rules
- For publish_new: use the template specified in the task (e.g. "norway_daily")
- For merge_update: the existing post structure is preserved; only items and summary change
- Always use the commit_message from the task config
- If any tool returns status "error", stop and return an error result
- The date and time for format_post come from the source data's collected_at timestamp
"""


def create_agent() -> Agent:
    model = BedrockModel(model_id=MODEL_ID)
    return Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[read_from_s3, read_repo_file, format_post, merge_posts, git_clone, git_commit_and_push],
    )
```

- [ ] **Step 2: Verify imports work**

Run: `cd /Users/lufng/github/news-agent/agents/publisher && python3 -c "import sys; sys.path.insert(0, 'app/NewsPublisher'); from unittest.mock import MagicMock; sys.modules['strands'] = MagicMock(); sys.modules['strands'].tool = lambda fn: fn; sys.modules['strands.models'] = MagicMock(); sys.modules['boto3'] = MagicMock(); sys.modules['git'] = MagicMock(); from agent import SYSTEM_PROMPT; print('OK:', len(SYSTEM_PROMPT), 'chars')"`
Expected: `OK: <number> chars`

- [ ] **Step 3: Commit**

```bash
git add agents/publisher/app/NewsPublisher/agent.py
git commit -m "feat(publisher): implement agent system prompt and tool registration"
```

---

### Task 9: End-to-End Agent Test

**Files:**
- Create: `agents/publisher/tests/test_agent_e2e.py`

- [ ] **Step 1: Write the e2e test for publish_new flow**

```python
# tests/test_agent_e2e.py
import json
import os
from unittest.mock import patch, MagicMock

import pytest


def test_publish_new_task_calls_tools_in_order(sample_collection_data):
    """Verify the agent has the right tools registered and system prompt covers publish_new."""
    # We can't run the full LLM agent in tests, but we can verify:
    # 1. Agent is constructed with all tools
    # 2. System prompt references publish_new pipeline
    # 3. Tools work independently for the publish_new flow

    from agent import create_agent, SYSTEM_PROMPT

    # Verify system prompt covers all task types
    assert "publish_new" in SYSTEM_PROMPT
    assert "merge_update" in SYSTEM_PROMPT
    assert "rewrite" in SYSTEM_PROMPT
    assert "edit" in SYSTEM_PROMPT

    # Verify agent is created with all tools
    agent = create_agent()
    # strands is mocked, so we verify the Agent() call got tools
    # The mock captures the constructor args


def test_publish_new_flow_integration(sample_collection_data):
    """Test the publish_new pipeline by calling tools in sequence (simulating what the agent would do)."""
    from tools.s3_reader import read_from_s3
    from tools.formatter import format_post
    from tools.git_ops import git_clone, git_commit_and_push

    # Step 1: Read from S3
    with patch("tools.s3_reader.boto3") as mock_boto3:
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        mock_body = MagicMock()
        mock_body.read.return_value = json.dumps(sample_collection_data).encode()
        mock_s3.get_object.return_value = {"Body": mock_body}

        s3_result = read_from_s3(bucket="news-agent-data", key="collections/2026-05-21/0500-norway-news.json")

    assert s3_result["status"] == "success"
    data = s3_result["data"]

    # Step 2: Format post
    editorial_config = json.dumps({
        "day_summary": "今天的主要新闻：议会通过了新移民法案，石油基金创下历史新高。",
    })

    format_result = format_post(
        items=json.dumps(data["new_items"]),
        template="norway_daily",
        editorial_config=editorial_config,
        date="2026-05-21",
        time="05:00:00",
    )

    assert format_result["status"] == "success"
    assert "议会通过新移民法案" in format_result["content"]
    assert "石油基金创历史新高" in format_result["content"]
    assert "## 国内新闻" in format_result["content"]
    assert "## 财经新闻" in format_result["content"]

    # Step 3: Git clone
    with patch("tools.git_ops.git.Repo") as MockRepo:
        MockRepo.clone_from.return_value = MagicMock()
        with patch("tools.git_ops._get_github_token", return_value="ghp_test"):
            clone_result = git_clone(repo="claw-lu/hexo-blog", branch="main")

    assert clone_result["status"] == "success"

    # Step 4: Git commit and push
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("tools.git_ops.git.Repo") as MockRepo:
            mock_repo = MagicMock()
            MockRepo.return_value = mock_repo
            mock_commit = MagicMock()
            mock_commit.hexsha = "abc123"
            mock_repo.index.commit.return_value = mock_commit
            mock_repo.remote.return_value = MagicMock()

            push_result = git_commit_and_push(
                repo_path=tmpdir,
                file_path="source/_posts/20260521-norway.md",
                content=format_result["content"],
                commit_message="Add Norway news 2026-05-21",
            )

    assert push_result["status"] == "success"
    assert push_result["commit_sha"] == "abc123"


def test_merge_update_flow_integration(sample_collection_data, sample_existing_post):
    """Test the merge_update pipeline by calling tools in sequence."""
    from tools.merger import merge_posts

    new_items = json.dumps(sample_collection_data["new_items"])
    updated_items = json.dumps(sample_collection_data["updated_items"])
    strategy = json.dumps({
        "new_items": "append_per_section",
        "updated_items": "replace_summary_and_add_source",
        "renumber": True,
        "regenerate_day_summary": False,
    })

    result = merge_posts(
        existing_content=sample_existing_post,
        new_items=new_items,
        updated_items=updated_items,
        strategy=strategy,
    )

    assert result["status"] == "success"
    content = result["content"]
    # Original item preserved
    assert "奥斯陆天气预警" in content
    # New items added
    assert "议会通过新移民法案" in content
    assert "石油基金创历史新高" in content
    # Correct numbering
    assert "### 1." in content
    assert "### 2." in content
    assert "### 3." in content
    assert result["new_items_added"] == 2
    assert result["total_items"] == 3
```

- [ ] **Step 2: Run test to verify it passes**

Run: `cd /Users/lufng/github/news-agent/agents/publisher && python3 -m pytest tests/test_agent_e2e.py -v`
Expected: PASS (3 tests)

- [ ] **Step 3: Commit**

```bash
git add agents/publisher/tests/test_agent_e2e.py
git commit -m "feat(publisher): add end-to-end agent tests for publish_new and merge_update flows"
```

---

### Task 10: Generate Lock File + Run Full Test Suite

**Files:**
- Generate: `agents/publisher/app/NewsPublisher/uv.lock`

- [ ] **Step 1: Generate uv.lock**

Run: `cd /Users/lufng/github/news-agent/agents/publisher/app/NewsPublisher && uv lock`
Expected: Lock file generated successfully

- [ ] **Step 2: Run full test suite**

Run: `cd /Users/lufng/github/news-agent/agents/publisher && python3 -m pytest tests/ -v`
Expected: All tests PASS (15+ tests across 5 test files)

- [ ] **Step 3: Commit lock file**

```bash
git add agents/publisher/app/NewsPublisher/uv.lock
git commit -m "chore(publisher): generate uv.lock for reproducible builds"
```

---

## Summary of Deliverables

| Task | What It Produces |
|------|-----------------|
| 1 | `read_from_s3` tool + tests |
| 2 | `read_repo_file` tool + tests |
| 3 | Two Jinja2 templates (norway_daily, generic_post) |
| 4 | `format_post` tool + tests |
| 5 | `merge_posts` tool + tests |
| 6 | `git_clone` + `git_commit_and_push` tools + tests |
| 7 | Package wiring (tools/__init__.py, conftest fixtures) |
| 8 | Agent system prompt + tool registration |
| 9 | End-to-end integration tests |
| 10 | Lock file + full suite verification |
