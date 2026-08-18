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
from strands import tool

from config import EXTRACTION_TIMEOUT_SECONDS


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
