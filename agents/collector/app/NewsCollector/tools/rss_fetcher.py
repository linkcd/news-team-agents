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

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from typing import Optional

import feedparser
import httpx
from strands import tool

logger = logging.getLogger(__name__)


def _now():
    return datetime.now(timezone.utc)


def _parse_published(entry) -> datetime | None:
    """Parse the published date from an RSS entry.

    Normalize source timestamps to UTC without changing the represented instant.
    """
    raw = entry.get("published", "") or entry.get("updated", "")
    if raw:
        try:
            dt = parsedate_to_datetime(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except (TypeError, ValueError, OverflowError):
            logger.debug("Could not parse RSS date %r", raw, exc_info=True)

    # Fallback to feedparser's parsed struct
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
    elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
        return datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)

    return None


@tool
def fetch_rss(url: str, time_window_hours: int = 6) -> dict:
    """Fetch and parse an RSS feed, returning articles published within the time window.

    Args:
        url: RSS feed URL to fetch
        time_window_hours: Only return articles from the last N hours (default: 6)

    Returns:
        Dict with status, articles list (each with url, title, published_at, description), and error if any
    """
    try:
        response = httpx.get(url, timeout=30, follow_redirects=True)
        response.raise_for_status()
    except Exception as e:
        return {"status": "error", "error": str(e), "articles": []}

    feed = feedparser.parse(response.text)
    cutoff = _now() - timedelta(hours=time_window_hours)

    articles = []
    for entry in feed.entries:
        published = _parse_published(entry)

        if published and published < cutoff:
            continue

        articles.append(
            {
                "url": entry.get("link", ""),
                "title": entry.get("title", ""),
                "published_at": published.isoformat() if published else None,
                "description": entry.get("description", ""),
            }
        )

    return {"status": "success", "articles": articles}
