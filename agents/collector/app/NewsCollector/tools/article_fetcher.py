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
