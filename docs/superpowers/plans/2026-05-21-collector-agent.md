# Collector Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the general-purpose web content collection agent that fetches RSS feeds, extracts articles, consolidates related content into topics via LLM reasoning, translates/summarizes to Chinese, and writes structured output to S3.

**Architecture:** LLM-driven Strands agent with `BedrockAgentCoreApp` entrypoint. The agent receives a task payload, uses `@tool`-decorated Python functions for I/O (RSS fetch, content extraction, S3 read/write), and uses its own reasoning for creative work (topic consolidation, translation, summarization). System prompt guides it through the 6-step pipeline.

**Tech Stack:** Python 3.11, strands-agents SDK, bedrock-agentcore runtime, feedparser, trafilatura, httpx, boto3

---

## File Structure

```
agents/collector/
├── CLAUDE.md                    # Already exists (spec)
├── src/
│   ├── __init__.py
│   ├── main.py                  # BedrockAgentCoreApp entrypoint
│   ├── agent.py                 # Agent creation (system prompt, tools, model)
│   ├── config.py                # Configuration constants
│   └── tools/
│       ├── __init__.py
│       ├── rss_fetcher.py       # fetch_rss tool
│       ├── webpage_fetcher.py   # fetch_webpage tool
│       ├── content_extractor.py # extract_content tool
│       ├── dedup.py             # get_dedup_context tool
│       └── s3_writer.py         # write_to_s3 tool
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Shared fixtures
│   ├── test_rss_fetcher.py
│   ├── test_webpage_fetcher.py
│   ├── test_content_extractor.py
│   ├── test_dedup.py
│   ├── test_s3_writer.py
│   └── test_agent_e2e.py
├── Dockerfile
└── requirements.txt
```

---

## Task 1: Project Scaffolding

**Files:**
- Create: `agents/collector/src/__init__.py`
- Create: `agents/collector/src/tools/__init__.py`
- Create: `agents/collector/src/config.py`
- Create: `agents/collector/tests/__init__.py`
- Create: `agents/collector/tests/conftest.py`
- Create: `agents/collector/requirements.txt`
- Create: `agents/collector/Dockerfile`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p agents/collector/src/tools
mkdir -p agents/collector/tests
```

- [ ] **Step 2: Create requirements.txt**

```
strands-agents>=0.1.0
bedrock-agentcore>=0.1.0
feedparser>=6.0.0
trafilatura>=1.6.0
httpx>=0.27.0
boto3>=1.34.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
moto[s3]>=5.0.0
```

- [ ] **Step 3: Create config.py**

```python
MODEL_ID = "us.anthropic.claude-sonnet-4-20250514-v1:0"
EXTRACTION_TIMEOUT_SECONDS = 10
DEFAULT_SUMMARY_WORD_COUNT = 200
```

- [ ] **Step 4: Create package init files**

`agents/collector/src/__init__.py` — empty file

`agents/collector/src/tools/__init__.py`:
```python
from .rss_fetcher import fetch_rss
from .webpage_fetcher import fetch_webpage
from .content_extractor import extract_content
from .dedup import get_dedup_context
from .s3_writer import write_to_s3
```

`agents/collector/tests/__init__.py` — empty file

- [ ] **Step 5: Create conftest.py with shared fixtures**

```python
import pytest


@pytest.fixture
def sample_rss_xml():
    return """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>NRK Nyheter</title>
    <item>
      <title>Stortinget vedtar ny lov</title>
      <link>https://nrk.no/article/123</link>
      <pubDate>Wed, 21 May 2026 09:30:00 +0200</pubDate>
      <description>Stortinget har vedtatt en ny lov om digitalisering.</description>
    </item>
    <item>
      <title>Vær: Regn i hele Sør-Norge</title>
      <link>https://nrk.no/article/124</link>
      <pubDate>Wed, 21 May 2026 08:00:00 +0200</pubDate>
      <description>Meteorologisk institutt varsler kraftig regn.</description>
    </item>
  </channel>
</rss>"""


@pytest.fixture
def sample_article_html():
    return """<!DOCTYPE html>
<html>
<head><title>Stortinget vedtar ny lov</title></head>
<body>
<article>
<h1>Stortinget vedtar ny lov om digitalisering</h1>
<p>Stortinget har i dag vedtatt en ny lov som skal fremme digitalisering
i offentlig sektor. Loven ble vedtatt med bredt flertall etter en lengre
debatt i salen.</p>
<p>Statsminister Jonas Gahr Støre sa at loven er et viktig skritt for å
modernisere Norge.</p>
</article>
</body>
</html>"""


@pytest.fixture
def sample_task_config():
    return {
        "task": {
            "task_id": "test-task-001",
            "sources": [
                {
                    "url": "https://nrk.no/rss/nyheter",
                    "type": "rss",
                    "label": "NRK Norge",
                    "category": "domestic",
                }
            ],
            "filters": {
                "time_window_hours": 6,
                "dedup_source": {"type": "none"},
            },
            "processing": {
                "extract_full_content": True,
                "consolidate_topics": True,
                "summarize": True,
                "summary_word_count": 200,
                "translate_to": ["zh"],
                "preserve_original_names": True,
            },
            "output": {
                "s3_bucket": "news-agent-data",
                "s3_key_prefix": "collections/2026-05-21/",
                "format": "json",
            },
        }
    }
```

- [ ] **Step 6: Create Dockerfile**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

CMD ["python", "-m", "src.main"]
```

- [ ] **Step 7: Commit**

```bash
git add agents/collector/src/ agents/collector/tests/ agents/collector/requirements.txt agents/collector/Dockerfile
git commit -m "feat(collector): scaffold project structure with config and fixtures"
```

---

## Task 2: RSS Fetcher Tool

**Files:**
- Create: `agents/collector/src/tools/rss_fetcher.py`
- Create: `agents/collector/tests/test_rss_fetcher.py`

- [ ] **Step 1: Write the failing test**

`agents/collector/tests/test_rss_fetcher.py`:
```python
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

import pytest


def test_fetch_rss_returns_articles_within_time_window(sample_rss_xml):
    from src.tools.rss_fetcher import fetch_rss

    now = datetime(2026, 5, 21, 10, 0, 0, tzinfo=timezone.utc)

    with patch("src.tools.rss_fetcher.httpx") as mock_httpx:
        mock_response = MagicMock()
        mock_response.text = sample_rss_xml
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_response

        with patch("src.tools.rss_fetcher._now", return_value=now):
            result = fetch_rss(
                url="https://nrk.no/rss/nyheter", time_window_hours=6
            )

    assert result["status"] == "success"
    assert len(result["articles"]) == 2
    assert result["articles"][0]["url"] == "https://nrk.no/article/123"
    assert result["articles"][0]["title"] == "Stortinget vedtar ny lov"
    assert "published_at" in result["articles"][0]


def test_fetch_rss_filters_old_articles(sample_rss_xml):
    from src.tools.rss_fetcher import fetch_rss

    now = datetime(2026, 5, 21, 10, 0, 0, tzinfo=timezone.utc)

    with patch("src.tools.rss_fetcher.httpx") as mock_httpx:
        mock_response = MagicMock()
        mock_response.text = sample_rss_xml
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_response

        # Set time window to 1 hour - only the 09:30 article should pass
        with patch("src.tools.rss_fetcher._now", return_value=now):
            result = fetch_rss(
                url="https://nrk.no/rss/nyheter", time_window_hours=1
            )

    assert result["status"] == "success"
    assert len(result["articles"]) == 1
    assert result["articles"][0]["url"] == "https://nrk.no/article/123"


def test_fetch_rss_handles_http_error():
    from src.tools.rss_fetcher import fetch_rss

    with patch("src.tools.rss_fetcher.httpx") as mock_httpx:
        mock_httpx.get.side_effect = Exception("Connection refused")

        result = fetch_rss(
            url="https://nrk.no/rss/nyheter", time_window_hours=6
        )

    assert result["status"] == "error"
    assert "Connection refused" in result["error"]
    assert result["articles"] == []


def test_fetch_rss_handles_empty_feed():
    from src.tools.rss_fetcher import fetch_rss

    empty_rss = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Empty</title></channel></rss>"""

    with patch("src.tools.rss_fetcher.httpx") as mock_httpx:
        mock_response = MagicMock()
        mock_response.text = empty_rss
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_response

        result = fetch_rss(
            url="https://nrk.no/rss/nyheter", time_window_hours=6
        )

    assert result["status"] == "success"
    assert result["articles"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd agents/collector && python -m pytest tests/test_rss_fetcher.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.tools.rss_fetcher'`

- [ ] **Step 3: Write minimal implementation**

`agents/collector/src/tools/rss_fetcher.py`:
```python
from datetime import datetime, timezone, timedelta

import feedparser
import httpx
from strands import tool


def _now():
    return datetime.now(timezone.utc)


@tool
def fetch_rss(url: str, time_window_hours: int = 6) -> dict:
    """Fetch and parse an RSS feed, returning articles published within the time window.

    Args:
        url: RSS feed URL to fetch
        time_window_hours: Only return articles from the last N hours (default: 6)

    Returns:
        Dict with status, articles list (each with url, title, published_at, description), and error if any
    """
    try:
        response = httpx.get(url, timeout=30, follow_redirects=True)
        response.raise_for_status()
    except Exception as e:
        return {"status": "error", "error": str(e), "articles": []}

    feed = feedparser.parse(response.text)
    cutoff = _now() - timedelta(hours=time_window_hours)

    articles = []
    for entry in feed.entries:
        published = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
            published = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)

        if published and published < cutoff:
            continue

        articles.append(
            {
                "url": entry.get("link", ""),
                "title": entry.get("title", ""),
                "published_at": published.isoformat() if published else None,
                "description": entry.get("description", ""),
            }
        )

    return {"status": "success", "articles": articles}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd agents/collector && python -m pytest tests/test_rss_fetcher.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add agents/collector/src/tools/rss_fetcher.py agents/collector/tests/test_rss_fetcher.py
git commit -m "feat(collector): implement fetch_rss tool with time window filtering"
```

---

## Task 3: Webpage Fetcher Tool

**Files:**
- Create: `agents/collector/src/tools/webpage_fetcher.py`
- Create: `agents/collector/tests/test_webpage_fetcher.py`

- [ ] **Step 1: Write the failing test**

`agents/collector/tests/test_webpage_fetcher.py`:
```python
from unittest.mock import patch, MagicMock

import pytest


def test_fetch_webpage_returns_html_content():
    from src.tools.webpage_fetcher import fetch_webpage

    html = "<html><body><p>Hello world</p></body></html>"

    with patch("src.tools.webpage_fetcher.httpx") as mock_httpx:
        mock_response = MagicMock()
        mock_response.text = html
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_response

        result = fetch_webpage(url="https://example.com/article")

    assert result["status"] == "success"
    assert result["html"] == html
    assert result["url"] == "https://example.com/article"


def test_fetch_webpage_handles_timeout():
    from src.tools.webpage_fetcher import fetch_webpage

    with patch("src.tools.webpage_fetcher.httpx") as mock_httpx:
        mock_httpx.get.side_effect = Exception("Timeout")

        result = fetch_webpage(url="https://example.com/slow")

    assert result["status"] == "error"
    assert "Timeout" in result["error"]
    assert result["html"] == ""


def test_fetch_webpage_handles_404():
    from src.tools.webpage_fetcher import fetch_webpage

    with patch("src.tools.webpage_fetcher.httpx") as mock_httpx:
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = Exception("404 Not Found")
        mock_httpx.get.return_value = mock_response

        result = fetch_webpage(url="https://example.com/missing")

    assert result["status"] == "error"
    assert "404" in result["error"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd agents/collector && python -m pytest tests/test_webpage_fetcher.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`agents/collector/src/tools/webpage_fetcher.py`:
```python
import httpx
from strands import tool

from ..config import EXTRACTION_TIMEOUT_SECONDS


@tool
def fetch_webpage(url: str) -> dict:
    """Fetch a single webpage and return its HTML content.

    Args:
        url: The webpage URL to fetch

    Returns:
        Dict with status, html content, url, and error if any
    """
    try:
        response = httpx.get(
            url, timeout=EXTRACTION_TIMEOUT_SECONDS, follow_redirects=True
        )
        response.raise_for_status()
        return {"status": "success", "html": response.text, "url": url}
    except Exception as e:
        return {"status": "error", "error": str(e), "html": "", "url": url}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd agents/collector && python -m pytest tests/test_webpage_fetcher.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add agents/collector/src/tools/webpage_fetcher.py agents/collector/tests/test_webpage_fetcher.py
git commit -m "feat(collector): implement fetch_webpage tool"
```

---

## Task 4: Content Extractor Tool

**Files:**
- Create: `agents/collector/src/tools/content_extractor.py`
- Create: `agents/collector/tests/test_content_extractor.py`

- [ ] **Step 1: Write the failing test**

`agents/collector/tests/test_content_extractor.py`:
```python
from unittest.mock import patch

import pytest


def test_extract_content_returns_article_text(sample_article_html):
    from src.tools.content_extractor import extract_content

    result = extract_content(html=sample_article_html, url="https://nrk.no/article/123")

    assert result["status"] == "success"
    assert "digitalisering" in result["text"]
    assert result["url"] == "https://nrk.no/article/123"


def test_extract_content_handles_empty_html():
    from src.tools.content_extractor import extract_content

    result = extract_content(html="", url="https://example.com")

    assert result["status"] == "error"
    assert result["text"] == ""


def test_extract_content_handles_non_article_html():
    from src.tools.content_extractor import extract_content

    html = "<html><body><nav>Menu</nav><footer>Footer</footer></body></html>"
    result = extract_content(html=html, url="https://example.com")

    # trafilatura may return empty for non-article pages
    assert result["url"] == "https://example.com"
    # Either error or empty text is acceptable
    assert result["status"] in ("success", "error")


def test_extract_content_handles_trafilatura_failure():
    from src.tools.content_extractor import extract_content

    with patch("src.tools.content_extractor.trafilatura.extract", return_value=None):
        result = extract_content(
            html="<html><body>content</body></html>", url="https://example.com"
        )

    assert result["status"] == "error"
    assert result["text"] == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd agents/collector && python -m pytest tests/test_content_extractor.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`agents/collector/src/tools/content_extractor.py`:
```python
import trafilatura
from strands import tool


@tool
def extract_content(html: str, url: str) -> dict:
    """Extract article text from HTML using trafilatura.

    Args:
        html: Raw HTML content of a webpage
        url: The source URL (passed through for reference)

    Returns:
        Dict with status, extracted text, url, and error if any
    """
    if not html:
        return {"status": "error", "text": "", "url": url, "error": "Empty HTML"}

    try:
        text = trafilatura.extract(html, include_comments=False, include_tables=False)
    except Exception as e:
        return {"status": "error", "text": "", "url": url, "error": str(e)}

    if not text:
        return {"status": "error", "text": "", "url": url, "error": "No content extracted"}

    return {"status": "success", "text": text, "url": url}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd agents/collector && python -m pytest tests/test_content_extractor.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add agents/collector/src/tools/content_extractor.py agents/collector/tests/test_content_extractor.py
git commit -m "feat(collector): implement extract_content tool with trafilatura"
```

---

## Task 5: Dedup Context Tool

**Files:**
- Create: `agents/collector/src/tools/dedup.py`
- Create: `agents/collector/tests/test_dedup.py`

- [ ] **Step 1: Write the failing test**

`agents/collector/tests/test_dedup.py`:
```python
from unittest.mock import patch, MagicMock

import pytest


def test_get_dedup_context_none_type():
    from src.tools.dedup import get_dedup_context

    result = get_dedup_context(dedup_config='{"type": "none"}')

    assert result["status"] == "success"
    assert result["known_urls"] == []
    assert result["existing_topics"] == []


def test_get_dedup_context_url_list():
    from src.tools.dedup import get_dedup_context

    config = '{"type": "url_list", "urls": ["https://nrk.no/1", "https://vg.no/2"]}'
    result = get_dedup_context(dedup_config=config)

    assert result["status"] == "success"
    assert result["known_urls"] == ["https://nrk.no/1", "https://vg.no/2"]
    assert result["existing_topics"] == []


def test_get_dedup_context_github_file():
    from src.tools.dedup import get_dedup_context

    markdown_content = """---
title: 挪威新闻 2026-05-21
---

## 国内新闻

### 1. 议会通过新法律

来源: [NRK](https://nrk.no/article/100), [VG](https://vg.no/article/200)

议会今天通过了一项关于数字化的新法律。

### 2. 奥斯陆天气预警

来源: [NRK](https://nrk.no/article/101)

气象研究所发布了暴风雨警告。
"""

    with patch("src.tools.dedup.httpx") as mock_httpx:
        mock_response = MagicMock()
        mock_response.text = markdown_content
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_response

        config = '{"type": "github_file", "repo": "claw-lu/hexo-blog", "path": "source/_posts/2026-05-21-norway-news.md"}'
        result = get_dedup_context(dedup_config=config)

    assert result["status"] == "success"
    assert "https://nrk.no/article/100" in result["known_urls"]
    assert "https://vg.no/article/200" in result["known_urls"]
    assert "https://nrk.no/article/101" in result["known_urls"]
    assert len(result["existing_topics"]) == 2
    assert result["existing_topics"][0]["title"] == "议会通过新法律"
    assert "数字化" in result["existing_topics"][0]["summary"]


def test_get_dedup_context_s3_file():
    from src.tools.dedup import get_dedup_context

    import json

    s3_data = json.dumps(
        {
            "new_items": [
                {
                    "title_zh": "议会投票",
                    "summary_zh": "议会通过新法律",
                    "sources": [
                        {"url": "https://nrk.no/article/500"},
                        {"url": "https://vg.no/article/501"},
                    ],
                }
            ],
            "updated_items": [],
        }
    )

    with patch("src.tools.dedup.boto3") as mock_boto3:
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        mock_body = MagicMock()
        mock_body.read.return_value = s3_data.encode()
        mock_s3.get_object.return_value = {"Body": mock_body}

        config = '{"type": "s3_file", "bucket": "news-agent-data", "key": "collections/2026-05-21/0500-norway-news.json"}'
        result = get_dedup_context(dedup_config=config)

    assert result["status"] == "success"
    assert "https://nrk.no/article/500" in result["known_urls"]
    assert "https://vg.no/article/501" in result["known_urls"]
    assert len(result["existing_topics"]) == 1
    assert result["existing_topics"][0]["title"] == "议会投票"


def test_get_dedup_context_handles_github_404():
    from src.tools.dedup import get_dedup_context

    with patch("src.tools.dedup.httpx") as mock_httpx:
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = Exception("404 Not Found")
        mock_httpx.get.return_value = mock_response

        config = '{"type": "github_file", "repo": "claw-lu/hexo-blog", "path": "source/_posts/nonexistent.md"}'
        result = get_dedup_context(dedup_config=config)

    # 404 means no existing post — return empty (not error)
    assert result["status"] == "success"
    assert result["known_urls"] == []
    assert result["existing_topics"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd agents/collector && python -m pytest tests/test_dedup.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`agents/collector/src/tools/dedup.py`:
```python
import json
import re

import boto3
import httpx
from strands import tool


def _parse_markdown_topics(markdown: str) -> tuple[list[str], list[dict]]:
    """Parse a blog post markdown to extract URLs and topic summaries."""
    urls = re.findall(r'\[.*?\]\((https?://[^\)]+)\)', markdown)

    topics = []
    sections = re.split(r'###\s+\d+\.\s+', markdown)
    for section in sections[1:]:  # skip content before first ###
        lines = section.strip().split('\n')
        title = lines[0].strip()

        # Collect summary text (lines after source line, before next heading)
        summary_lines = []
        past_source = False
        for line in lines[1:]:
            if line.strip().startswith("来源:") or line.strip().startswith("来源："):
                past_source = True
                continue
            if past_source and line.strip():
                summary_lines.append(line.strip())

        summary = "\n".join(summary_lines)
        source_urls = re.findall(r'\[.*?\]\((https?://[^\)]+)\)', section)

        topics.append(
            {"title": title, "summary": summary, "source_urls": source_urls}
        )

    return urls, topics


def _parse_s3_collection(data: dict) -> tuple[list[str], list[dict]]:
    """Parse a previous S3 collection output to extract URLs and topics."""
    urls = []
    topics = []

    for item in data.get("new_items", []):
        for source in item.get("sources", []):
            urls.append(source["url"])
        topics.append(
            {
                "title": item.get("title_zh", ""),
                "summary": item.get("summary_zh", ""),
                "source_urls": [s["url"] for s in item.get("sources", [])],
            }
        )

    for item in data.get("updated_items", []):
        if "new_source" in item:
            urls.append(item["new_source"]["url"])

    return urls, topics


@tool
def get_dedup_context(dedup_config: str) -> dict:
    """Read existing URLs and topic summaries from a dedup source.

    This tool reads previously collected content to enable deduplication.
    It supports multiple source types: none, url_list, github_file, s3_file.

    Args:
        dedup_config: JSON string with dedup source configuration. Must include "type" field.

    Returns:
        Dict with status, known_urls list, existing_topics list (each with title, summary, source_urls)
    """
    config = json.loads(dedup_config)
    source_type = config.get("type", "none")

    if source_type == "none":
        return {"status": "success", "known_urls": [], "existing_topics": []}

    if source_type == "url_list":
        return {
            "status": "success",
            "known_urls": config.get("urls", []),
            "existing_topics": [],
        }

    if source_type == "github_file":
        repo = config["repo"]
        path = config["path"]
        raw_url = f"https://raw.githubusercontent.com/{repo}/main/{path}"
        try:
            response = httpx.get(raw_url, timeout=15, follow_redirects=True)
            response.raise_for_status()
        except Exception:
            return {"status": "success", "known_urls": [], "existing_topics": []}

        urls, topics = _parse_markdown_topics(response.text)
        return {"status": "success", "known_urls": urls, "existing_topics": topics}

    if source_type == "s3_file":
        bucket = config["bucket"]
        key = config["key"]
        try:
            s3 = boto3.client("s3")
            obj = s3.get_object(Bucket=bucket, Key=key)
            data = json.loads(obj["Body"].read())
        except Exception as e:
            return {"status": "error", "error": str(e), "known_urls": [], "existing_topics": []}

        urls, topics = _parse_s3_collection(data)
        return {"status": "success", "known_urls": urls, "existing_topics": topics}

    return {
        "status": "error",
        "error": f"Unknown dedup source type: {source_type}",
        "known_urls": [],
        "existing_topics": [],
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd agents/collector && python -m pytest tests/test_dedup.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add agents/collector/src/tools/dedup.py agents/collector/tests/test_dedup.py
git commit -m "feat(collector): implement get_dedup_context tool with github/s3/url_list sources"
```

---

## Task 6: S3 Writer Tool

**Files:**
- Create: `agents/collector/src/tools/s3_writer.py`
- Create: `agents/collector/tests/test_s3_writer.py`

- [ ] **Step 1: Write the failing test**

`agents/collector/tests/test_s3_writer.py`:
```python
import json
from unittest.mock import patch, MagicMock

import pytest


def test_write_to_s3_writes_json():
    from src.tools.s3_writer import write_to_s3

    data = {
        "task_id": "test-001",
        "new_items": [{"title_zh": "测试"}],
        "updated_items": [],
        "metadata": {"sources_fetched": 1},
    }

    with patch("src.tools.s3_writer.boto3") as mock_boto3:
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3

        result = write_to_s3(
            bucket="news-agent-data",
            key="collections/2026-05-21/1100-test.json",
            data=json.dumps(data),
        )

    assert result["status"] == "success"
    assert result["key"] == "collections/2026-05-21/1100-test.json"

    # Verify the actual S3 put call
    mock_s3.put_object.assert_called_once()
    call_kwargs = mock_s3.put_object.call_args[1]
    assert call_kwargs["Bucket"] == "news-agent-data"
    assert call_kwargs["Key"] == "collections/2026-05-21/1100-test.json"
    written_data = json.loads(call_kwargs["Body"])
    assert written_data["task_id"] == "test-001"


def test_write_to_s3_handles_error():
    from src.tools.s3_writer import write_to_s3

    with patch("src.tools.s3_writer.boto3") as mock_boto3:
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        mock_s3.put_object.side_effect = Exception("Access Denied")

        result = write_to_s3(
            bucket="news-agent-data",
            key="collections/test.json",
            data='{"test": true}',
        )

    assert result["status"] == "error"
    assert "Access Denied" in result["error"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd agents/collector && python -m pytest tests/test_s3_writer.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`agents/collector/src/tools/s3_writer.py`:
```python
import json

import boto3
from strands import tool


@tool
def write_to_s3(bucket: str, key: str, data: str) -> dict:
    """Write JSON data to an S3 bucket.

    Args:
        bucket: S3 bucket name
        key: S3 object key (path)
        data: JSON string to write

    Returns:
        Dict with status, key, and error if any
    """
    try:
        s3 = boto3.client("s3")
        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=data,
            ContentType="application/json",
        )
        return {"status": "success", "key": key}
    except Exception as e:
        return {"status": "error", "error": str(e), "key": key}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd agents/collector && python -m pytest tests/test_s3_writer.py -v`
Expected: All 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add agents/collector/src/tools/s3_writer.py agents/collector/tests/test_s3_writer.py
git commit -m "feat(collector): implement write_to_s3 tool"
```

---

## Task 7: Agent Setup (System Prompt + Tool Registration)

**Files:**
- Create: `agents/collector/src/agent.py`

- [ ] **Step 1: Write agent.py**

`agents/collector/src/agent.py`:
```python
from strands import Agent
from strands.models import BedrockModel

from .config import MODEL_ID
from .tools import fetch_rss, fetch_webpage, extract_content, get_dedup_context, write_to_s3

SYSTEM_PROMPT = """You are a web content collection agent. You receive a task configuration and execute a structured pipeline to collect, deduplicate, consolidate, translate, and output web content.

## Your Pipeline

Given a task, execute these steps IN ORDER:

### Step 1: Read Dedup Source
Call get_dedup_context with the task's filters.dedup_source configuration (as JSON string).
This gives you:
- known_urls: URLs already collected (skip these)
- existing_topics: Topics already published (match against these)

### Step 2: Fetch Sources
For each source in the task:
- If type is "rss": call fetch_rss(url, time_window_hours)
- If type is "webpage": call fetch_webpage(url)
Collect all articles from all sources.

### Step 3: URL Deduplication
Remove any articles whose URL appears in known_urls from Step 1.
Track: skipped_already_seen_urls count.

### Step 4: Extract Full Content
If processing.extract_full_content is true:
- For each remaining article, call fetch_webpage(url) then extract_content(html, url)
- If extraction fails, skip that article silently
- Track failed extractions in metadata

### Step 5: Consolidate Topics
If processing.consolidate_topics is true:
- Group the new articles by topic similarity (articles about the same event go together)
- Compare each group against existing_topics from Step 1
- For matches with existing topics: determine if the new article adds unique information
  - If yes: create an updated_item with revised summary and changelog
  - If no: skip entirely (don't include in output)
- For new topics (no match): create a new_item with consolidated summary from all sources in the group
- Track: grouped_into_new_topics, matched_to_existing_topics, skipped_no_new_info

If consolidate_topics is false: treat each article as its own topic (no grouping, no matching).

### Step 6: Translate and Summarize
If processing.summarize is true:
- For each new_item: generate a consolidated summary in the target language(s)
  - Word count target: processing.summary_word_count (default 200)
  - Preserve proper nouns (names, places, organizations) in original form when processing.preserve_original_names is true
- For each updated_item: regenerate the full summary incorporating new info, add a changelog note in the target language

If processing.translate_to contains languages:
- Translate titles and summaries to those languages (e.g., "zh" = Chinese)

### Step 7: Write Output
Construct the output JSON with this structure:
{
  "task_id": (from task config),
  "collected_at": (current ISO8601 timestamp),
  "new_items": [...],
  "updated_items": [...],
  "metadata": {counts from all steps}
}

Call write_to_s3 with the configured bucket and key.
The key should be: {s3_key_prefix}{task_id}.json

### Step 8: Return Result
Return a summary to the caller:
{
  "status": "success",
  "task_id": ...,
  "data_key": (full S3 key),
  "summary": {all counts}
}

## Output Format for new_items

Each new_item:
{
  "title_zh": "Consolidated Chinese title",
  "category": "from source config",
  "summary_zh": "~200 word consolidated summary",
  "sources": [
    {"url": "...", "source_label": "...", "published_at": "...", "title_original": "..."}
  ]
}

## Output Format for updated_items

Each updated_item:
{
  "match_title_zh": "Existing topic title (used for matching)",
  "new_source": {"url": "...", "source_label": "...", "published_at": "...", "title_original": "..."},
  "updated_summary_zh": "Revised summary incorporating new info",
  "changelog": "Chinese description of what was added"
}

## Important Rules
- Skip articles silently on extraction failure (don't error out the whole task)
- Never include an article that adds no new information beyond an existing topic
- Preserve Norwegian proper nouns in translations (person names, place names, organization names)
- Generate changelog notes in Chinese for updated_items (e.g., "新增来自Dagbladet的议员反应信息")
- If ALL sources fail to fetch, return status "error" with description
- If SOME sources fail, continue with successful ones and note failures in metadata
"""


def create_agent() -> Agent:
    model = BedrockModel(model_id=MODEL_ID)
    return Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[fetch_rss, fetch_webpage, extract_content, get_dedup_context, write_to_s3],
    )
```

- [ ] **Step 2: Commit**

```bash
git add agents/collector/src/agent.py
git commit -m "feat(collector): define agent with system prompt and tool registration"
```

---

## Task 8: AgentCore Runtime Entrypoint

**Files:**
- Create: `agents/collector/src/main.py`

- [ ] **Step 1: Write main.py**

`agents/collector/src/main.py`:
```python
import json

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from .agent import create_agent

app = BedrockAgentCoreApp()
_agent = None


def get_agent():
    global _agent
    if _agent is None:
        _agent = create_agent()
    return _agent


@app.entrypoint
async def invoke(payload, context=None):
    """AgentCore Runtime entrypoint. Receives task config, runs collection pipeline."""
    agent = get_agent()

    prompt = f"""Execute the collection task with the following configuration:

{json.dumps(payload, indent=2)}

Follow your pipeline steps and return the result."""

    stream = agent.stream_async(prompt)
    async for event in stream:
        if "data" in event and isinstance(event["data"], str):
            yield event["data"]


if __name__ == "__main__":
    app.run()
```

- [ ] **Step 2: Commit**

```bash
git add agents/collector/src/main.py
git commit -m "feat(collector): add AgentCore runtime entrypoint"
```

---

## Task 9: End-to-End Agent Test

**Files:**
- Create: `agents/collector/tests/test_agent_e2e.py`

- [ ] **Step 1: Write the e2e test**

`agents/collector/tests/test_agent_e2e.py`:
```python
import json
from unittest.mock import patch, MagicMock, AsyncMock

import pytest


@pytest.fixture
def mock_rss_response():
    return """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>NRK</title>
    <item>
      <title>Ny digitaliseringslov vedtatt</title>
      <link>https://nrk.no/article/1</link>
      <pubDate>Wed, 21 May 2026 09:30:00 +0000</pubDate>
      <description>Stortinget vedtok ny lov.</description>
    </item>
  </channel>
</rss>"""


@pytest.fixture
def mock_article_html():
    return """<html><body><article>
<h1>Ny digitaliseringslov vedtatt</h1>
<p>Stortinget har vedtatt en ny lov om digitalisering i offentlig sektor.
Loven ble vedtatt med 95 mot 74 stemmer etter en lang debatt.</p>
</article></body></html>"""


def test_agent_creation():
    """Verify the agent can be created with all tools registered."""
    from src.agent import create_agent

    with patch("src.agent.BedrockModel"):
        agent = create_agent()

    assert agent is not None
    # Verify tools are registered (agent has tools attribute)
    assert len(agent.tools) == 5


def test_tools_are_importable():
    """Verify all tools can be imported from the tools package."""
    from src.tools import fetch_rss, fetch_webpage, extract_content, get_dedup_context, write_to_s3

    assert callable(fetch_rss)
    assert callable(fetch_webpage)
    assert callable(extract_content)
    assert callable(get_dedup_context)
    assert callable(write_to_s3)


def test_full_pipeline_tools_integration(mock_rss_response, mock_article_html):
    """Test that tools work together in the expected pipeline sequence."""
    from src.tools.rss_fetcher import fetch_rss
    from src.tools.webpage_fetcher import fetch_webpage
    from src.tools.content_extractor import extract_content
    from src.tools.dedup import get_dedup_context
    from src.tools.s3_writer import write_to_s3

    # Step 1: Get dedup context (none)
    dedup_result = get_dedup_context(dedup_config='{"type": "none"}')
    assert dedup_result["status"] == "success"
    assert dedup_result["known_urls"] == []

    # Step 2: Fetch RSS
    from datetime import datetime, timezone
    from unittest.mock import patch as p

    now = datetime(2026, 5, 21, 10, 0, 0, tzinfo=timezone.utc)
    with p("src.tools.rss_fetcher.httpx") as mock_httpx:
        mock_resp = MagicMock()
        mock_resp.text = mock_rss_response
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_resp

        with p("src.tools.rss_fetcher._now", return_value=now):
            rss_result = fetch_rss(url="https://nrk.no/rss", time_window_hours=6)

    assert rss_result["status"] == "success"
    assert len(rss_result["articles"]) == 1
    article_url = rss_result["articles"][0]["url"]

    # Step 3: Fetch webpage
    with p("src.tools.webpage_fetcher.httpx") as mock_httpx:
        mock_resp = MagicMock()
        mock_resp.text = mock_article_html
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_resp

        page_result = fetch_webpage(url=article_url)

    assert page_result["status"] == "success"

    # Step 4: Extract content
    extract_result = extract_content(html=page_result["html"], url=article_url)
    assert extract_result["status"] == "success"
    assert "digitalisering" in extract_result["text"]

    # Step 5: Write to S3
    output_data = json.dumps(
        {
            "task_id": "test-001",
            "new_items": [
                {
                    "title_zh": "新数字化法律获得通过",
                    "category": "domestic",
                    "summary_zh": "挪威议会以95票对74票通过了新的数字化法律。",
                    "sources": [{"url": article_url, "source_label": "NRK"}],
                }
            ],
            "updated_items": [],
            "metadata": {"sources_fetched": 1, "new_urls_found": 1},
        }
    )

    with p("src.tools.s3_writer.boto3") as mock_boto3:
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3

        s3_result = write_to_s3(
            bucket="news-agent-data",
            key="collections/2026-05-21/test-001.json",
            data=output_data,
        )

    assert s3_result["status"] == "success"
    assert s3_result["key"] == "collections/2026-05-21/test-001.json"
```

- [ ] **Step 2: Run test to verify it passes**

Run: `cd agents/collector && python -m pytest tests/test_agent_e2e.py -v`
Expected: All 3 tests PASS

- [ ] **Step 3: Commit**

```bash
git add agents/collector/tests/test_agent_e2e.py
git commit -m "test(collector): add end-to-end tool integration tests"
```

---

## Task 10: Run Full Test Suite

- [ ] **Step 1: Run all collector tests**

Run: `cd agents/collector && python -m pytest tests/ -v`
Expected: All tests PASS (approximately 19 tests)

- [ ] **Step 2: Verify imports work correctly**

Run: `cd agents/collector && python -c "from src.tools import fetch_rss, fetch_webpage, extract_content, get_dedup_context, write_to_s3; print('All tools imported successfully')"`
Expected: "All tools imported successfully"

- [ ] **Step 3: Commit any fixes if needed**

---

## Verification

After all tasks are complete:

1. **Run full test suite**: `cd agents/collector && python -m pytest tests/ -v` — all tests pass
2. **Verify tool imports**: `python -c "from src.tools import *"` — no import errors
3. **Verify agent creation**: `python -c "from src.agent import create_agent"` — no errors (model mock needed)
4. **Check structure**: `find agents/collector -type f | sort` — matches planned file structure
5. **Local dev** (requires AWS credentials + model access): `cd agents/collector && agentcore dev` then invoke with sample task config from conftest.py
