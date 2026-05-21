import trafilatura
from strands import tool


@tool
def extract_content(html: str, url: str) -> dict:
    """Extract article text from HTML using trafilatura.

    Args:
        html: Raw HTML content of a webpage
        url: The source URL (passed through for reference)

    Returns:
        Dict with status, extracted text, url, and error if any
    """
    if not html:
        return {"status": "error", "text": "", "url": url, "error": "Empty HTML"}

    try:
        text = trafilatura.extract(html, include_comments=False, include_tables=False)
    except Exception as e:
        return {"status": "error", "text": "", "url": url, "error": str(e)}

    if not text:
        return {"status": "error", "text": "", "url": url, "error": "No content extracted"}

    return {"status": "success", "text": text, "url": url}
