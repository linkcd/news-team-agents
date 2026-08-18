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
