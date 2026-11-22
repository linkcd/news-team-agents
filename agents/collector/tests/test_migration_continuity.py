"""Regression contracts needed when resuming publication in another account."""
import json
from unittest.mock import patch

import pytest


def test_dedup_reads_publisher_markdown_without_footer_or_adjacent_section():
    from tools.dedup import get_dedup_context

    post = """## 国内新闻
### 1. Existing topic
**来源**: NRK | **最早报道**: 2026-05-21T07:30:00Z

Facts already published.

原文链接: [NRK](https://example.com/story)
---
## 财经新闻
*新闻来源: NRK*
"""
    with patch("tools.dedup._fetch_github_file", return_value={"content": post}):
        result = get_dedup_context(json.dumps({
            "type": "github_file", "repo": "example/blog", "path": "today.md",
        }))
    assert result["existing_topics"][0]["summary"] == "Facts already published."
    assert result["known_urls"] == ["https://example.com/story"]


def test_rss_preserves_the_instant_when_normalizing_timezones():
    from tools.rss_fetcher import _parse_published

    result = _parse_published({"published": "Thu, 21 May 2026 09:30:00 +0200"})
    assert result.isoformat() == "2026-05-21T07:30:00+00:00"


def test_dedup_credential_failure_is_not_treated_as_an_empty_post():
    from tools.dedup import get_dedup_context

    with patch("tools.dedup._fetch_github_file", side_effect=RuntimeError("Identity access denied")):
        result = get_dedup_context('{"type":"github_file","repo":"example/blog","path":"today.md"}')
    assert result["status"] == "error"


@pytest.mark.parametrize("status", [401, 403, 500])
def test_dedup_http_failures_stop_collection(status):
    import httpx
    from tools.dedup import get_dedup_context

    error = httpx.HTTPStatusError("fetch failed", request=httpx.Request("GET", "https://example.com"),
                                  response=httpx.Response(status))
    with patch("tools.dedup._fetch_github_file", side_effect=error):
        result = get_dedup_context('{"type":"github_file","repo":"example/blog","path":"today.md"}')
    assert result["status"] == "error"


def test_dedup_normalizes_html_entities_in_formatted_source_urls():
    from tools.dedup import get_dedup_context

    post = "### 1. Topic\n**来源**: NRK\nSummary\n原文链接: [NRK](https://example.com/?a=1&amp;b=2)"
    with patch("tools.dedup._fetch_github_file", return_value={"content": post}):
        result = get_dedup_context('{"type":"github_file","repo":"example/blog","path":"today.md"}')
    assert result["known_urls"] == ["https://example.com/?a=1&b=2"]
    assert result["existing_topics"][0]["source_urls"] == result["known_urls"]
