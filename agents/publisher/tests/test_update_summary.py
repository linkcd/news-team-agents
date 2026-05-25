"""Tests for update_summary tool.

The update_summary tool replaces the day summary section in a blog post file
on disk, updates the frontmatter 'updated' field, and updates the last-updated
timestamp line. This is the only part that requires LLM-generated content.
"""
import os
import tempfile

import pytest


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

---

## 财经新闻

---
*新闻来源: NRK Norge*
"""


class TestUpdateSummary:
    def test_replaces_summary_section(self):
        from tools.git_ops import update_summary

        new_summary = "这是新的综述内容，包含了所有最新的新闻主题。"

        with tempfile.TemporaryDirectory() as tmpdir:
            post_path = "source/_posts/20260521-norway.md"
            full_path = os.path.join(tmpdir, post_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w") as f:
                f.write(EXISTING_POST)

            result = update_summary(
                repo_path=tmpdir,
                file_path=post_path,
                new_summary=new_summary,
            )

            assert result["status"] == "success"

            with open(full_path) as f:
                content = f.read()

            assert new_summary in content
            assert "早间新闻概述" not in content

    def test_preserves_content_after_more_tag(self):
        from tools.git_ops import update_summary

        new_summary = "新综述。"

        with tempfile.TemporaryDirectory() as tmpdir:
            post_path = "source/_posts/20260521-norway.md"
            full_path = os.path.join(tmpdir, post_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w") as f:
                f.write(EXISTING_POST)

            update_summary(repo_path=tmpdir, file_path=post_path, new_summary=new_summary)

            with open(full_path) as f:
                content = f.read()

            assert "## 国内新闻" in content
            assert "### 1. 议会通过新法案" in content
            assert "挪威议会通过了新法案" in content
            assert "*新闻来源: NRK Norge*" in content

    def test_preserves_style_tag(self):
        from tools.git_ops import update_summary

        new_summary = "新综述。"

        with tempfile.TemporaryDirectory() as tmpdir:
            post_path = "source/_posts/20260521-norway.md"
            full_path = os.path.join(tmpdir, post_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w") as f:
                f.write(EXISTING_POST)

            update_summary(repo_path=tmpdir, file_path=post_path, new_summary=new_summary)

            with open(full_path) as f:
                content = f.read()

            assert "<style>" in content
            assert "font-size: 1.15em" in content

    def test_updates_frontmatter_updated_field(self):
        from tools.git_ops import update_summary

        new_summary = "新综述。"

        with tempfile.TemporaryDirectory() as tmpdir:
            post_path = "source/_posts/20260521-norway.md"
            full_path = os.path.join(tmpdir, post_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w") as f:
                f.write(EXISTING_POST)

            update_summary(repo_path=tmpdir, file_path=post_path, new_summary=new_summary)

            with open(full_path) as f:
                content = f.read()

            assert "updated: 2026-05-21 05:00:00" not in content
            assert "updated:" in content

    def test_updates_last_updated_line(self):
        from tools.git_ops import update_summary

        new_summary = "新综述。"

        with tempfile.TemporaryDirectory() as tmpdir:
            post_path = "source/_posts/20260521-norway.md"
            full_path = os.path.join(tmpdir, post_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w") as f:
                f.write(EXISTING_POST)

            update_summary(repo_path=tmpdir, file_path=post_path, new_summary=new_summary)

            with open(full_path) as f:
                content = f.read()

            assert "*最后更新: 05:00 UTC*" not in content
            assert "*最后更新:" in content
            assert "UTC*" in content

    def test_preserves_date_field_in_frontmatter(self):
        from tools.git_ops import update_summary

        new_summary = "新综述。"

        with tempfile.TemporaryDirectory() as tmpdir:
            post_path = "source/_posts/20260521-norway.md"
            full_path = os.path.join(tmpdir, post_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w") as f:
                f.write(EXISTING_POST)

            update_summary(repo_path=tmpdir, file_path=post_path, new_summary=new_summary)

            with open(full_path) as f:
                content = f.read()

            assert "date: 2026-05-21 05:00:00" in content

    def test_error_when_file_does_not_exist(self):
        from tools.git_ops import update_summary

        with tempfile.TemporaryDirectory() as tmpdir:
            result = update_summary(
                repo_path=tmpdir,
                file_path="nonexistent.md",
                new_summary="test",
            )

        assert result["status"] == "error"

    def test_error_when_no_summary_section_found(self):
        from tools.git_ops import update_summary

        post_without_summary = """---
title: Test
---

## 国内新闻

Content here.
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            post_path = "test.md"
            full_path = os.path.join(tmpdir, post_path)
            with open(full_path, "w") as f:
                f.write(post_without_summary)

            result = update_summary(
                repo_path=tmpdir,
                file_path=post_path,
                new_summary="新综述。",
            )

        assert result["status"] == "error"
