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

import json

import pytest


def test_format_post_norway_daily_creates_valid_markdown():
    from tools.formatter import format_post

    items = json.dumps([
        {
            "title_zh": "议会通过新移民法案",
            "category": "domestic",
            "summary_zh": "挪威议会今天以压倒性多数通过了一项新的移民法案。",
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
                    "title_original": "Ny lov vedtatt",
                },
            ],
        },
        {
            "title_zh": "石油基金创历史新高",
            "category": "business",
            "summary_zh": "挪威政府养老基金今天公布了创纪录的回报率。",
            "sources": [
                {
                    "url": "https://e24.no/article/789",
                    "source_label": "E24",
                    "published_at": "2026-05-21T10:00:00Z",
                    "title_original": "Oljefondet med ny rekord",
                },
            ],
        },
    ])

    editorial_config = json.dumps({
        "day_summary": "今天的主要新闻包括议会通过移民法案和石油基金创新高。",
    })

    raw = format_post(
        items=items,
        template="norway_daily",
        editorial_config=editorial_config,
        date="2026-05-21",
        time="05:00:00",
    )
    result = json.loads(raw)

    assert result["status"] == "success"
    content = result["content"]
    assert "title: 挪威新闻速递 2026-05-21" in content
    assert "## 今日综述" in content
    assert "今天的主要新闻包括" in content
    assert "## 国内新闻" in content
    assert "### 1. 议会通过新移民法案" in content
    assert "NRK Norge, VG" in content
    assert "## 财经新闻" in content
    assert "### 2. 石油基金创历史新高" in content
    assert "<!-- more -->" in content


def test_format_post_generic_creates_simple_post():
    from tools.formatter import format_post

    editorial_config = json.dumps({
        "title": "关于本站",
        "body": "这是一个关于挪威新闻的博客。",
        "tags": ["关于"],
        "categories": ["页面"],
    })

    raw = format_post(
        items="[]",
        template="generic_post",
        editorial_config=editorial_config,
        date="2026-05-21",
        time="05:00:00",
    )
    result = json.loads(raw)

    assert result["status"] == "success"
    content = result["content"]
    assert "title: 关于本站" in content
    assert "这是一个关于挪威新闻的博客" in content


def test_format_post_unknown_template_returns_error():
    from tools.formatter import format_post

    raw = format_post(
        items="[]",
        template="nonexistent_template",
        editorial_config="{}",
        date="2026-05-21",
        time="05:00:00",
    )
    result = json.loads(raw)

    assert result["status"] == "error"
    assert "template" in result["error"].lower()


def test_format_post_escapes_untrusted_html():
    from tools.formatter import format_post

    items = json.dumps([
        {
            "title_zh": "<script>alert('title')</script>",
            "category": "domestic",
            "summary_zh": "<img src=x onerror=alert('summary')>",
            "sources": [
                {
                    "url": "https://example.com/?a=1&b=2",
                    "source_label": "<b>Source</b>",
                    "published_at": "2026-05-21T09:30:00Z",
                },
            ],
        },
    ])

    raw = format_post(
        items=items,
        template="norway_daily",
        editorial_config=json.dumps({"day_summary": "<script>alert('summary')</script>"}),
        date="2026-05-21",
        time="05:00:00",
    )
    content = json.loads(raw)["content"]

    assert "<script>" not in content
    assert "<img " not in content
    assert "<b>Source</b>" not in content
    assert "&lt;script&gt;" in content
