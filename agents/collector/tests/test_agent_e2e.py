import json
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

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
    now = datetime(2026, 5, 21, 10, 0, 0, tzinfo=timezone.utc)
    with patch("src.tools.rss_fetcher.httpx") as mock_httpx:
        mock_resp = MagicMock()
        mock_resp.text = mock_rss_response
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_resp

        with patch("src.tools.rss_fetcher._now", return_value=now):
            rss_result = fetch_rss(url="https://nrk.no/rss", time_window_hours=6)

    assert rss_result["status"] == "success"
    assert len(rss_result["articles"]) == 1
    article_url = rss_result["articles"][0]["url"]

    # Step 3: Fetch webpage
    with patch("src.tools.webpage_fetcher.httpx") as mock_httpx:
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

    with patch("src.tools.s3_writer.boto3") as mock_boto3:
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3

        s3_result = write_to_s3(
            bucket="news-agent-data",
            key="collections/2026-05-21/test-001.json",
            data=output_data,
        )

    assert s3_result["status"] == "success"
    assert s3_result["key"] == "collections/2026-05-21/test-001.json"


def test_dedup_filters_known_urls(mock_rss_response):
    """Test that articles with known URLs get filtered in the pipeline."""
    from src.tools.rss_fetcher import fetch_rss
    from src.tools.dedup import get_dedup_context

    # Step 1: Dedup with known URL
    config = '{"type": "url_list", "urls": ["https://nrk.no/article/1"]}'
    dedup_result = get_dedup_context(dedup_config=config)
    known_urls = dedup_result["known_urls"]

    # Step 2: Fetch RSS
    now = datetime(2026, 5, 21, 10, 0, 0, tzinfo=timezone.utc)
    with patch("src.tools.rss_fetcher.httpx") as mock_httpx:
        mock_resp = MagicMock()
        mock_resp.text = mock_rss_response
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_resp

        with patch("src.tools.rss_fetcher._now", return_value=now):
            rss_result = fetch_rss(url="https://nrk.no/rss", time_window_hours=6)

    # Step 3: Filter by known URLs (this is what the agent would do)
    new_articles = [a for a in rss_result["articles"] if a["url"] not in known_urls]
    assert len(new_articles) == 0  # All articles already known
