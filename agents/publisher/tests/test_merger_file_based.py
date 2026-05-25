"""Tests for file-based merge_posts tool.

The merge_posts tool should read existing content from disk and write merged
result back to disk, eliminating the need for the LLM to pass large content
as tool arguments.
"""
import json
import os
import tempfile
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


EXISTING_POST = """---
title: 挪威新闻速递 2026-05-21
date: 2026-05-21 05:00:00
updated: 2026-05-21 05:00:00
tags: [挪威, 新闻]
categories: [每日新闻, 挪威]
---

<style>article.article-content, .post-body, .article-entry { font-size: 1.15em; line-height: 1.8; }</style>

*最后更新: 05:00 UTC*

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


class TestMergePostsFileBased:
    """merge_posts should accept repo_path + file_path instead of existing_content."""

    def test_reads_existing_content_from_disk(self):
        from tools.merger import merge_posts

        with tempfile.TemporaryDirectory() as tmpdir:
            post_path = "source/_posts/20260521-norway.md"
            full_path = os.path.join(tmpdir, post_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w") as f:
                f.write(EXISTING_POST)

            strategy = json.dumps({"new_items": "prepend_per_section", "renumber": True})
            mock_s3 = _mock_s3_get([], [])

            with patch("tools.merger.boto3") as mock_boto3:
                mock_boto3.client.return_value = mock_s3
                result = json.loads(merge_posts(
                    repo_path=tmpdir,
                    file_path=post_path,
                    s3_bucket="test-bucket",
                    s3_key="test-key.json",
                    strategy=strategy,
                ))

        assert result["status"] == "success"
        assert result["total_items"] == 2

    def test_writes_merged_content_to_disk(self):
        from tools.merger import merge_posts

        new_items = [{
            "title_zh": "新交通计划公布",
            "category": "domestic",
            "summary_zh": "政府公布新交通基础设施计划。",
            "sources": [{"url": "https://nrk.no/500", "source_label": "NRK", "published_at": "2026-05-21T11:00:00Z", "title_original": "Ny plan"}],
        }]

        with tempfile.TemporaryDirectory() as tmpdir:
            post_path = "source/_posts/20260521-norway.md"
            full_path = os.path.join(tmpdir, post_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w") as f:
                f.write(EXISTING_POST)

            strategy = json.dumps({"new_items": "prepend_per_section", "renumber": True})
            mock_s3 = _mock_s3_get(new_items, [])

            with patch("tools.merger.boto3") as mock_boto3:
                mock_boto3.client.return_value = mock_s3
                result = json.loads(merge_posts(
                    repo_path=tmpdir,
                    file_path=post_path,
                    s3_bucket="test-bucket",
                    s3_key="test-key.json",
                    strategy=strategy,
                ))

            assert result["status"] == "success"
            with open(full_path) as f:
                disk_content = f.read()
            assert "新交通计划公布" in disk_content
            assert "### 1. 新交通计划公布" in disk_content

    def test_does_not_return_content_in_result(self):
        """Result should contain only metadata, not the full post content."""
        from tools.merger import merge_posts

        with tempfile.TemporaryDirectory() as tmpdir:
            post_path = "source/_posts/20260521-norway.md"
            full_path = os.path.join(tmpdir, post_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w") as f:
                f.write(EXISTING_POST)

            strategy = json.dumps({"new_items": "prepend_per_section", "renumber": True})
            mock_s3 = _mock_s3_get([], [])

            with patch("tools.merger.boto3") as mock_boto3:
                mock_boto3.client.return_value = mock_s3
                result = json.loads(merge_posts(
                    repo_path=tmpdir,
                    file_path=post_path,
                    s3_bucket="test-bucket",
                    s3_key="test-key.json",
                    strategy=strategy,
                ))

        assert result["status"] == "success"
        assert "content" not in result

    def test_error_when_file_does_not_exist(self):
        from tools.merger import merge_posts

        with tempfile.TemporaryDirectory() as tmpdir:
            strategy = json.dumps({"new_items": "prepend_per_section", "renumber": True})
            mock_s3 = _mock_s3_get([], [])

            with patch("tools.merger.boto3") as mock_boto3:
                mock_boto3.client.return_value = mock_s3
                result = json.loads(merge_posts(
                    repo_path=tmpdir,
                    file_path="nonexistent.md",
                    s3_bucket="test-bucket",
                    s3_key="test-key.json",
                    strategy=strategy,
                ))

        assert result["status"] == "error"

    def test_prepends_new_items_correctly(self):
        from tools.merger import merge_posts

        new_items = [{
            "title_zh": "新新闻B",
            "category": "domestic",
            "summary_zh": "新新闻B内容。",
            "sources": [{"url": "https://nrk.no/300", "source_label": "NRK Oslo", "published_at": "2026-05-21T11:00:00Z", "title_original": "B"}],
        }]

        with tempfile.TemporaryDirectory() as tmpdir:
            post_path = "source/_posts/20260521-norway.md"
            full_path = os.path.join(tmpdir, post_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w") as f:
                f.write(EXISTING_POST)

            strategy = json.dumps({"new_items": "prepend_per_section", "renumber": True})
            mock_s3 = _mock_s3_get(new_items, [])

            with patch("tools.merger.boto3") as mock_boto3:
                mock_boto3.client.return_value = mock_s3
                result = json.loads(merge_posts(
                    repo_path=tmpdir,
                    file_path=post_path,
                    s3_bucket="test-bucket",
                    s3_key="test-key.json",
                    strategy=strategy,
                ))

            assert result["new_items_added"] == 1
            assert result["total_items"] == 3

            with open(full_path) as f:
                content = f.read()
            assert "### 1. 新新闻B" in content
            assert "### 2. 议会通过新法案" in content

    def test_updates_existing_items(self):
        from tools.merger import merge_posts

        updated_items = [{
            "match_title_zh": "议会通过新法案",
            "new_source": {"url": "https://vg.no/456", "source_label": "VG", "published_at": "2026-05-21T10:15:00Z", "title_original": "Ny lov"},
            "updated_summary_zh": "更新后的内容包含VG的报道。",
            "changelog": "更新于 11:00 UTC: 新增VG报道",
        }]

        with tempfile.TemporaryDirectory() as tmpdir:
            post_path = "source/_posts/20260521-norway.md"
            full_path = os.path.join(tmpdir, post_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w") as f:
                f.write(EXISTING_POST)

            strategy = json.dumps({"new_items": "prepend_per_section", "updated_items": "replace_summary_and_add_source", "renumber": True})
            mock_s3 = _mock_s3_get([], updated_items)

            with patch("tools.merger.boto3") as mock_boto3:
                mock_boto3.client.return_value = mock_s3
                result = json.loads(merge_posts(
                    repo_path=tmpdir,
                    file_path=post_path,
                    s3_bucket="test-bucket",
                    s3_key="test-key.json",
                    strategy=strategy,
                ))

            assert result["existing_items_updated"] == 1

            with open(full_path) as f:
                content = f.read()
            assert "更新后的内容包含VG的报道" in content
            assert "https://vg.no/456" in content
