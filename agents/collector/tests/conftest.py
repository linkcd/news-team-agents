import os
import sys
from unittest.mock import MagicMock

# Add app/NewsCollector to path so tests can import tools, config, agent
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app", "NewsCollector"))

# Stub out the strands module for testing (not available on PyPI)
strands_mock = MagicMock()
strands_mock.tool = lambda fn: fn  # @tool decorator is a passthrough
sys.modules["strands"] = strands_mock

# Stub out boto3 for testing (not installed in test environment)
if "boto3" not in sys.modules:
    boto3_mock = MagicMock()
    sys.modules["boto3"] = boto3_mock

import pytest


@pytest.fixture
def sample_rss_xml():
    return """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>NRK Nyheter</title>
    <item>
      <title>Stortinget vedtar ny lov</title>
      <link>https://nrk.no/article/123</link>
      <pubDate>Wed, 21 May 2026 09:30:00 +0200</pubDate>
      <description>Stortinget har vedtatt en ny lov om digitalisering.</description>
    </item>
    <item>
      <title>Vær: Regn i hele Sør-Norge</title>
      <link>https://nrk.no/article/124</link>
      <pubDate>Wed, 21 May 2026 08:00:00 +0200</pubDate>
      <description>Meteorologisk institutt varsler kraftig regn.</description>
    </item>
  </channel>
</rss>"""


@pytest.fixture
def sample_article_html():
    return """<!DOCTYPE html>
<html>
<head><title>Stortinget vedtar ny lov</title></head>
<body>
<article>
<h1>Stortinget vedtar ny lov om digitalisering</h1>
<p>Stortinget har i dag vedtatt en ny lov som skal fremme digitalisering
i offentlig sektor. Loven ble vedtatt med bredt flertall etter en lengre
debatt i salen.</p>
<p>Statsminister Jonas Gahr Støre sa at loven er et viktig skritt for å
modernisere Norge.</p>
</article>
</body>
</html>"""


@pytest.fixture
def sample_task_config():
    return {
        "task": {
            "task_id": "test-task-001",
            "sources": [
                {
                    "url": "https://nrk.no/rss/nyheter",
                    "type": "rss",
                    "label": "NRK Norge",
                    "category": "domestic",
                }
            ],
            "filters": {
                "time_window_hours": 6,
                "dedup_source": {"type": "none"},
            },
            "processing": {
                "extract_full_content": True,
                "consolidate_topics": True,
                "summarize": True,
                "summary_word_count": 200,
                "translate_to": ["zh"],
                "preserve_original_names": True,
            },
            "output": {
                "s3_bucket": "news-agent-data",
                "s3_key_prefix": "collections/2026-05-21/",
                "format": "json",
            },
        }
    }
