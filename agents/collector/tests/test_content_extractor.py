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

from unittest.mock import patch

import pytest


def test_extract_content_returns_article_text(sample_article_html):
    from tools.content_extractor import extract_content

    result = extract_content(html=sample_article_html, url="https://nrk.no/article/123")

    assert result["status"] == "success"
    assert "digitalisering" in result["text"]
    assert result["url"] == "https://nrk.no/article/123"


def test_extract_content_handles_empty_html():
    from tools.content_extractor import extract_content

    result = extract_content(html="", url="https://example.com")

    assert result["status"] == "error"
    assert result["text"] == ""


def test_extract_content_handles_non_article_html():
    from tools.content_extractor import extract_content

    html = "<html><body><nav>Menu</nav><footer>Footer</footer></body></html>"
    result = extract_content(html=html, url="https://example.com")

    assert result["url"] == "https://example.com"
    assert result["status"] in ("success", "error")


def test_extract_content_handles_trafilatura_failure():
    from tools.content_extractor import extract_content

    with patch("tools.content_extractor.trafilatura.extract", return_value=None):
        result = extract_content(
            html="<html><body>content</body></html>", url="https://example.com"
        )

    assert result["status"] == "error"
    assert result["text"] == ""
