# Copyright 2026 news-agent contributors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

import pytest


def test_fetch_rss_returns_articles_within_time_window(sample_rss_xml):
    from tools.rss_fetcher import fetch_rss

    now = datetime(2026, 5, 21, 10, 0, 0, tzinfo=timezone.utc)

    with patch("tools.rss_fetcher.httpx") as mock_httpx:
        mock_response = MagicMock()
        mock_response.text = sample_rss_xml
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_response

        with patch("tools.rss_fetcher._now", return_value=now):
            result = fetch_rss(
                url="https://nrk.no/rss/nyheter", time_window_hours=6
            )

    assert result["status"] == "success"
    assert len(result["articles"]) == 2
    assert result["articles"][0]["url"] == "https://nrk.no/article/123"
    assert result["articles"][0]["title"] == "Stortinget vedtar ny lov"
    assert "published_at" in result["articles"][0]


def test_fetch_rss_filters_old_articles(sample_rss_xml):
    from tools.rss_fetcher import fetch_rss

    # 09:30 +0200 is 07:30 UTC; 08:00 +0200 is 06:00 UTC.
    now = datetime(2026, 5, 21, 8, 0, 0, tzinfo=timezone.utc)

    with patch("tools.rss_fetcher.httpx") as mock_httpx:
        mock_response = MagicMock()
        mock_response.text = sample_rss_xml
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_response

        with patch("tools.rss_fetcher._now", return_value=now):
            result = fetch_rss(
                url="https://nrk.no/rss/nyheter", time_window_hours=1
            )

    assert result["status"] == "success"
    assert len(result["articles"]) == 1
    assert result["articles"][0]["url"] == "https://nrk.no/article/123"


def test_fetch_rss_handles_http_error():
    from tools.rss_fetcher import fetch_rss

    with patch("tools.rss_fetcher.httpx") as mock_httpx:
        mock_httpx.get.side_effect = Exception("Connection refused")

        result = fetch_rss(
            url="https://nrk.no/rss/nyheter", time_window_hours=6
        )

    assert result["status"] == "error"
    assert "Connection refused" in result["error"]
    assert result["articles"] == []


def test_fetch_rss_handles_empty_feed():
    from tools.rss_fetcher import fetch_rss

    empty_rss = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Empty</title></channel></rss>"""

    with patch("tools.rss_fetcher.httpx") as mock_httpx:
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
