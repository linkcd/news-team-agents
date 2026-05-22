import httpx
import trafilatura
from strands import tool

from config import EXTRACTION_TIMEOUT_SECONDS


@tool
def fetch_and_extract(url: str) -> dict:
    """Fetch a webpage and extract its article text in one step.

    Args:
        url: The webpage URL to fetch and extract content from

    Returns:
        Dict with status, extracted text, url, and error if any
    """
    try:
        response = httpx.get(
            url, timeout=EXTRACTION_TIMEOUT_SECONDS, follow_redirects=True
        )
        response.raise_for_status()
    except Exception as e:
        return {"status": "error", "text": "", "url": url, "error": f"Fetch failed: {e}"}

    try:
        text = trafilatura.extract(
            response.text, include_comments=False, include_tables=False
        )
    except Exception as e:
        return {"status": "error", "text": "", "url": url, "error": f"Extraction failed: {e}"}

    if not text:
        return {"status": "error", "text": "", "url": url, "error": "No content extracted"}

    return {"status": "success", "text": text, "url": url}
