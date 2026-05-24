import json
from unittest.mock import patch, MagicMock

import pytest


def _mock_s3_get(new_items, updated_items):
    """Create a mock S3 response with given items."""
    data = json.dumps({
        "task_id": "test",
        "collected_at": "2026-05-21T11:00:00Z",
        "new_items": new_items,
        "updated_items": updated_items,
        "metadata": {},
    }).encode()

    mock_body = MagicMock()
    mock_body.read.return_value = data

    mock_s3 = MagicMock()
    mock_s3.get_object.return_value = {"Body": mock_body}
    return mock_s3


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
"""

    new_items = [
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
    ]

    strategy = json.dumps({
        "new_items": "append_per_section",
        "updated_items": "replace_summary_and_add_source",
        "renumber": True,
        "regenerate_day_summary": False,
    })

    mock_s3 = _mock_s3_get(new_items, [])
    with patch("tools.merger.boto3") as mock_boto3:
        mock_boto3.client.return_value = mock_s3
        result = merge_posts(
            existing_content=existing_content,
            s3_bucket="test-bucket",
            s3_key="test-key.json",
            strategy=strategy,
        )

    result = json.loads(result)
    assert result["status"] == "success"
    content = result["content"]
    assert "奥斯陆新地铁线路开工" in content
    assert "NRK Oslo" in content
    assert "### 1. 议会通过新法案" in content
    assert "### 2. 奥斯陆新地铁线路开工" in content
    assert "### 3. 北欧合作会议召开" in content
    assert result["new_items_added"] == 1
    assert result["existing_items_updated"] == 0
    assert result["total_items"] == 3


def test_merge_posts_prepends_new_items_when_strategy_says_so():
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

### 1. 旧新闻A
**来源**: NRK Norge | **最早报道**: 2026-05-21T06:00:00Z

旧新闻A内容。

原文链接: [NRK Norge](https://nrk.no/article/001)

---

## 国际新闻

---

## 财经新闻

---
*新闻来源: NRK Norge*
"""

    new_items = [
        {
            "title_zh": "新新闻B",
            "category": "domestic",
            "summary_zh": "新新闻B内容。",
            "sources": [{"url": "https://nrk.no/300", "source_label": "NRK Oslo", "published_at": "2026-05-21T11:00:00Z", "title_original": "B"}],
        }
    ]

    strategy = json.dumps({
        "new_items": "prepend_per_section",
        "updated_items": "replace_summary_and_add_source",
        "renumber": True,
    })

    mock_s3 = _mock_s3_get(new_items, [])
    with patch("tools.merger.boto3") as mock_boto3:
        mock_boto3.client.return_value = mock_s3
        result = merge_posts(
            existing_content=existing_content,
            s3_bucket="test-bucket",
            s3_key="test-key.json",
            strategy=strategy,
        )

    result = json.loads(result)
    assert result["status"] == "success"
    content = result["content"]
    # New item should be first (prepended)
    assert "### 1. 新新闻B" in content
    assert "### 2. 旧新闻A" in content


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
"""

    updated_items = [
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
    ]

    strategy = json.dumps({
        "new_items": "append_per_section",
        "updated_items": "replace_summary_and_add_source",
        "renumber": True,
        "regenerate_day_summary": False,
    })

    mock_s3 = _mock_s3_get([], updated_items)
    with patch("tools.merger.boto3") as mock_boto3:
        mock_boto3.client.return_value = mock_s3
        result = merge_posts(
            existing_content=existing_content,
            s3_bucket="test-bucket",
            s3_key="test-key.json",
            strategy=strategy,
        )

    result = json.loads(result)
    assert result["status"] == "success"
    content = result["content"]
    assert "反对党表示将继续抗争" in content
    assert "VG" in content
    assert "https://vg.no/article/456" in content
    assert "更新于 11:00 UTC" in content
    assert "https://nrk.no/article/123" in content
    assert result["new_items_added"] == 0
    assert result["existing_items_updated"] == 1


def test_merge_posts_handles_empty_existing_content():
    from tools.merger import merge_posts

    strategy = json.dumps({"new_items": "append_per_section", "renumber": True})

    mock_s3 = _mock_s3_get([{"title_zh": "X", "category": "domestic", "summary_zh": "Y", "sources": []}], [])
    with patch("tools.merger.boto3") as mock_boto3:
        mock_boto3.client.return_value = mock_s3
        raw = merge_posts(
            existing_content="",
            s3_bucket="test-bucket",
            s3_key="test-key.json",
            strategy=strategy,
        )

    result = json.loads(raw)
    assert result["status"] == "error"
    assert "existing content" in result["error"].lower()


def test_merge_posts_puts_timestamp_before_more_tag():
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

### 1. 旧新闻
**来源**: NRK | **最早报道**: 2026-05-21T06:00:00Z

内容。

原文链接: [NRK](https://nrk.no/1)

---

## 国际新闻

---

## 财经新闻

---
*新闻来源: NRK*
"""

    strategy = json.dumps({"new_items": "prepend_per_section", "renumber": True})
    mock_s3 = _mock_s3_get([], [])
    with patch("tools.merger.boto3") as mock_boto3:
        mock_boto3.client.return_value = mock_s3
        result = json.loads(merge_posts(
            existing_content=existing_content,
            s3_bucket="b",
            s3_key="k",
            strategy=strategy,
        ))

    assert result["status"] == "success"
    content = result["content"]
    update_pos = content.find("*最后更新:")
    more_pos = content.find("<!-- more -->")
    assert update_pos != -1
    assert more_pos != -1
    assert update_pos < more_pos
