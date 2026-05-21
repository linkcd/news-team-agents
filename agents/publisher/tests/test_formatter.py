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

    result = format_post(
        items=items,
        template="norway_daily",
        editorial_config=editorial_config,
        date="2026-05-21",
        time="05:00:00",
    )

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

    result = format_post(
        items="[]",
        template="generic_post",
        editorial_config=editorial_config,
        date="2026-05-21",
        time="05:00:00",
    )

    assert result["status"] == "success"
    content = result["content"]
    assert "title: 关于本站" in content
    assert "这是一个关于挪威新闻的博客" in content


def test_format_post_unknown_template_returns_error():
    from tools.formatter import format_post

    result = format_post(
        items="[]",
        template="nonexistent_template",
        editorial_config="{}",
        date="2026-05-21",
        time="05:00:00",
    )

    assert result["status"] == "error"
    assert "template" in result["error"].lower()
