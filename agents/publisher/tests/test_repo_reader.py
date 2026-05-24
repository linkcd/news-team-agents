from unittest.mock import patch, MagicMock

import pytest


def test_read_repo_file_returns_content():
    from tools.repo_reader import read_repo_file

    markdown_content = """---
title: 挪威新闻速递 2026-05-21
date: 2026-05-21 05:00:00
---

## 今日综述
今天的新闻概述。
"""

    with patch("tools.repo_reader.httpx") as mock_httpx:
        mock_response = MagicMock()
        mock_response.text = markdown_content
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_response

        result = read_repo_file(
            repo="claw-lu/hexo-blog",
            branch="main",
            path="source/_posts/20260521-norway.md",
        )

    assert result["status"] == "success"
    assert result["content"] == markdown_content
    mock_httpx.get.assert_called_once_with(
        "https://raw.githubusercontent.com/claw-lu/hexo-blog/main/source/_posts/20260521-norway.md",
        timeout=15,
        follow_redirects=True,
        headers={},
    )


def test_read_repo_file_handles_404():
    from tools.repo_reader import read_repo_file

    with patch("tools.repo_reader.httpx") as mock_httpx:
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = Exception("404 Not Found")
        mock_httpx.get.return_value = mock_response

        result = read_repo_file(
            repo="claw-lu/hexo-blog",
            branch="main",
            path="source/_posts/nonexistent.md",
        )

    assert result["status"] == "success"
    assert result["content"] == ""
    assert result["found"] is False


def test_read_repo_file_handles_network_error():
    from tools.repo_reader import read_repo_file

    with patch("tools.repo_reader.httpx") as mock_httpx:
        mock_httpx.get.side_effect = Exception("Connection timeout")

        result = read_repo_file(
            repo="claw-lu/hexo-blog",
            branch="main",
            path="source/_posts/test.md",
        )

    assert result["status"] == "error"
    assert "Connection timeout" in result["error"]
