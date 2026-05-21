import os
import sys
from unittest.mock import MagicMock

# Add app/NewsPublisher to path so tests can import tools, config, agent
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app", "NewsPublisher"))

# Stub out the strands module for testing
strands_mock = MagicMock()
strands_mock.tool = lambda fn: fn
sys.modules["strands"] = strands_mock
sys.modules["strands.models"] = MagicMock()

# Stub out boto3 for testing
if "boto3" not in sys.modules:
    boto3_mock = MagicMock()
    sys.modules["boto3"] = boto3_mock

# Stub out git (gitpython) for testing — per-test patches override this
if "git" not in sys.modules:
    git_mock = MagicMock()
    sys.modules["git"] = git_mock

# Stub out bedrock_agentcore for testing
# The @requires_api_key decorator injects an api_key kwarg — in tests we make it a no-op
def _passthrough_decorator(**kwargs):
    def decorator(func):
        return func
    return decorator

bedrock_agentcore_mock = MagicMock()
bedrock_agentcore_identity_mock = MagicMock()
bedrock_agentcore_identity_mock.requires_api_key = _passthrough_decorator
sys.modules["bedrock_agentcore"] = bedrock_agentcore_mock
sys.modules["bedrock_agentcore.identity"] = bedrock_agentcore_identity_mock
sys.modules["bedrock_agentcore.runtime"] = MagicMock()

import pytest


@pytest.fixture
def sample_collection_data():
    """Sample Collector output (S3 JSON) for publisher tests."""
    return {
        "task_id": "collect-norway-2026-05-21-1100",
        "collected_at": "2026-05-21T11:00:00Z",
        "new_items": [
            {
                "title_zh": "议会通过新移民法案",
                "category": "domestic",
                "summary_zh": "挪威议会今天以压倒性多数通过了一项新的移民法案。该法案将加强对移民的语言和就业要求。",
                "sources": [
                    {
                        "url": "https://nrk.no/article/123",
                        "source_label": "NRK Norge",
                        "published_at": "2026-05-21T09:30:00Z",
                        "title_original": "Stortinget vedtar ny innvandringslov",
                    },
                    {
                        "url": "https://vg.no/article/456",
                        "source_label": "VG",
                        "published_at": "2026-05-21T09:45:00Z",
                        "title_original": "Ny lov vedtatt med bredt flertall",
                    },
                ],
            },
            {
                "title_zh": "石油基金创历史新高",
                "category": "business",
                "summary_zh": "挪威政府养老基金今天公布了创纪录的回报率，总资产突破18万亿克朗。",
                "sources": [
                    {
                        "url": "https://e24.no/article/789",
                        "source_label": "E24",
                        "published_at": "2026-05-21T10:00:00Z",
                        "title_original": "Oljefondet med ny rekord",
                    },
                ],
            },
        ],
        "updated_items": [],
        "metadata": {
            "sources_fetched": 11,
            "items_in_rss": 45,
            "after_time_filter": 20,
            "new_urls_found": 8,
            "grouped_into_new_topics": 2,
            "matched_to_existing_topics": 0,
            "skipped_no_new_info": 0,
            "skipped_already_seen_urls": 12,
        },
    }


@pytest.fixture
def sample_existing_post():
    """Sample existing blog post markdown for merge tests."""
    return """---
title: 挪威新闻速递 2026-05-21
date: 2026-05-21 05:00:00
updated: 2026-05-21 05:00:00
tags: [挪威, 新闻]
categories: [每日新闻, 挪威]
---

## 今日综述
早间新闻概述。

<!-- more -->

## 国内新闻

### 1. 奥斯陆天气预警
**来源**: NRK Oslo | **最早报道**: 2026-05-21T06:00:00Z

气象研究所发布了暴风雨警告。

原文链接: [NRK Oslo](https://nrk.no/article/050)

---

## 国际新闻

---

## 财经新闻

---
*新闻来源: NRK Oslo*
*最后更新: 05:00 UTC*
"""
