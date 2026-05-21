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

    assert result["url"] == "https://example.com"
    assert result["status"] in ("success", "error")


def test_extract_content_handles_trafilatura_failure():
    from src.tools.content_extractor import extract_content

    with patch("src.tools.content_extractor.trafilatura.extract", return_value=None):
        result = extract_content(
            html="<html><body>content</body></html>", url="https://example.com"
        )

    assert result["status"] == "error"
    assert result["text"] == ""
