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

from unittest.mock import patch, MagicMock

import pytest


def test_fetch_webpage_returns_html_content():
    from tools.webpage_fetcher import fetch_webpage

    html = "<html><body><p>Hello world</p></body></html>"

    with patch("tools.webpage_fetcher.httpx") as mock_httpx:
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
    from tools.webpage_fetcher import fetch_webpage

    with patch("tools.webpage_fetcher.httpx") as mock_httpx:
        mock_httpx.get.side_effect = Exception("Timeout")

        result = fetch_webpage(url="https://example.com/slow")

    assert result["status"] == "error"
    assert "Timeout" in result["error"]
    assert result["html"] == ""


def test_fetch_webpage_handles_404():
    from tools.webpage_fetcher import fetch_webpage

    with patch("tools.webpage_fetcher.httpx") as mock_httpx:
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = Exception("404 Not Found")
        mock_httpx.get.return_value = mock_response

        result = fetch_webpage(url="https://example.com/missing")

    assert result["status"] == "error"
    assert "404" in result["error"]
