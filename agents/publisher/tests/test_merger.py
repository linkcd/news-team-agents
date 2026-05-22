import json

import pytest


def test_merge_posts_appends_new_items_to_correct_section():
    from tools.merger import merge_posts

    existing_content = """---
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

### 1. 议会通过新法案
**来源**: NRK Norge | **最早报道**: 2026-05-21T09:30:00Z

挪威议会通过了新法案。

原文链接: [NRK Norge](https://nrk.no/article/123)

---

## 国际新闻

### 2. 北欧合作会议召开
**来源**: NRK Urix | **最早报道**: 2026-05-21T08:00:00Z

北欧国家召开了合作会议。

原文链接: [NRK Urix](https://nrk.no/article/200)

---

## 财经新闻

---
*新闻来源: NRK Norge, NRK Urix*
*最后更新: 05:00 UTC*
"""

    new_items = json.dumps([
        {
            "title_zh": "奥斯陆新地铁线路开工",
            "category": "domestic",
            "summary_zh": "奥斯陆市政府宣布新地铁线路正式开工建设。",
            "sources": [
                {
                    "url": "https://nrk.no/article/300",
                    "source_label": "NRK Oslo",
                    "published_at": "2026-05-21T11:00:00Z",
                    "title_original": "Ny T-bane linje",
                }
            ],
        }
    ])

    updated_items = json.dumps([])

    strategy = json.dumps({
        "new_items": "append_per_section",
        "updated_items": "replace_summary_and_add_source",
        "renumber": True,
        "regenerate_day_summary": False,
    })

    result = merge_posts(
        existing_content=existing_content,
        new_items=new_items,
        updated_items=updated_items,
        strategy=strategy,
    )

    result = json.loads(result)
    assert result["status"] == "success"
    content = result["content"]
    # New domestic item appended after existing domestic items
    assert "奥斯陆新地铁线路开工" in content
    assert "NRK Oslo" in content
    # Renumbered: existing domestic=1, new domestic=2, international=3
    assert "### 1. 议会通过新法案" in content
    assert "### 2. 奥斯陆新地铁线路开工" in content
    assert "### 3. 北欧合作会议召开" in content
    assert result["new_items_added"] == 1
    assert result["existing_items_updated"] == 0
    assert result["total_items"] == 3


def test_merge_posts_updates_existing_item():
    from tools.merger import merge_posts

    existing_content = """---
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

### 1. 议会通过新移民法案
**来源**: NRK Norge | **最早报道**: 2026-05-21T09:30:00Z

挪威议会通过了新的移民法案。

原文链接: [NRK Norge](https://nrk.no/article/123)

---

## 国际新闻

---

## 财经新闻

---
*新闻来源: NRK Norge*
*最后更新: 05:00 UTC*
"""

    new_items = json.dumps([])
    updated_items = json.dumps([
        {
            "match_title_zh": "议会通过新移民法案",
            "new_source": {
                "url": "https://vg.no/article/456",
                "source_label": "VG",
                "published_at": "2026-05-21T10:15:00Z",
                "title_original": "Innvandringslov vedtatt",
            },
            "updated_summary_zh": "挪威议会以压倒性多数通过了新的移民法案，反对党表示将继续抗争。",
            "changelog": "更新于 11:00 UTC: 新增来自VG的反对党反应",
        }
    ])

    strategy = json.dumps({
        "new_items": "append_per_section",
        "updated_items": "replace_summary_and_add_source",
        "renumber": True,
        "regenerate_day_summary": False,
    })

    result = merge_posts(
        existing_content=existing_content,
        new_items=new_items,
        updated_items=updated_items,
        strategy=strategy,
    )

    result = json.loads(result)
    assert result["status"] == "success"
    content = result["content"]
    # Summary replaced
    assert "反对党表示将继续抗争" in content
    # New source added
    assert "VG" in content
    assert "https://vg.no/article/456" in content
    # Changelog present
    assert "更新于 11:00 UTC" in content
    # Original source preserved
    assert "https://nrk.no/article/123" in content
    assert result["new_items_added"] == 0
    assert result["existing_items_updated"] == 1


def test_merge_posts_handles_empty_existing_content():
    from tools.merger import merge_posts

    new_items = json.dumps([
        {
            "title_zh": "测试新闻",
            "category": "domestic",
            "summary_zh": "这是一条测试新闻。",
            "sources": [
                {
                    "url": "https://nrk.no/article/1",
                    "source_label": "NRK",
                    "published_at": "2026-05-21T09:00:00Z",
                    "title_original": "Test",
                }
            ],
        }
    ])

    raw = merge_posts(
        existing_content="",
        new_items=new_items,
        updated_items="[]",
        strategy='{"new_items": "append_per_section", "updated_items": "replace_summary_and_add_source", "renumber": true, "regenerate_day_summary": false}',
    )
    result = json.loads(raw)

    assert result["status"] == "error"
    assert "existing content" in result["error"].lower()
