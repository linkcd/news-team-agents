from unittest.mock import patch, MagicMock

import pytest


def test_fetch_and_extract_returns_extracted_text(sample_article_html):
    from tools.article_fetcher import fetch_and_extract

    with patch("tools.article_fetcher.httpx") as mock_httpx:
        mock_response = MagicMock()
        mock_response.text = sample_article_html
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_response

        result = fetch_and_extract(url="https://nrk.no/article/123")

    assert result["status"] == "success"
    assert "digitalisering" in result["text"]
    assert result["url"] == "https://nrk.no/article/123"
    # Must NOT contain raw HTML
    assert "<html>" not in result.get("text", "")
    assert "html" not in result  # no html field in response


def test_fetch_and_extract_handles_fetch_timeout():
    from tools.article_fetcher import fetch_and_extract

    with patch("tools.article_fetcher.httpx") as mock_httpx:
        mock_httpx.get.side_effect = Exception("Timeout")

        result = fetch_and_extract(url="https://example.com/slow")

    assert result["status"] == "error"
    assert "Fetch failed" in result["error"]
    assert result["text"] == ""


def test_fetch_and_extract_handles_404():
    from tools.article_fetcher import fetch_and_extract

    with patch("tools.article_fetcher.httpx") as mock_httpx:
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("404 Not Found")
        mock_httpx.get.return_value = mock_response

        result = fetch_and_extract(url="https://example.com/missing")

    assert result["status"] == "error"
    assert "Fetch failed" in result["error"]


def test_fetch_and_extract_handles_extraction_failure():
    from tools.article_fetcher import fetch_and_extract

    with patch("tools.article_fetcher.httpx") as mock_httpx:
        mock_response = MagicMock()
        mock_response.text = "<html><body><nav>Menu</nav></body></html>"
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_response

        with patch("tools.article_fetcher.trafilatura.extract", return_value=None):
            result = fetch_and_extract(url="https://example.com")

    assert result["status"] == "error"
    assert "No content extracted" in result["error"]


def test_fetch_and_extract_handles_trafilatura_exception():
    from tools.article_fetcher import fetch_and_extract

    with patch("tools.article_fetcher.httpx") as mock_httpx:
        mock_response = MagicMock()
        mock_response.text = "<html><body>content</body></html>"
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_response

        with patch(
            "tools.article_fetcher.trafilatura.extract",
            side_effect=Exception("parse error"),
        ):
            result = fetch_and_extract(url="https://example.com")

    assert result["status"] == "error"
    assert "Extraction failed" in result["error"]
