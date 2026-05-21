import json
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

    # 404 means no existing post - return empty (not error)
    assert result["status"] == "success"
    assert result["known_urls"] == []
    assert result["existing_topics"] == []
