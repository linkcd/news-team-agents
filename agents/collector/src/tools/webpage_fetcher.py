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
