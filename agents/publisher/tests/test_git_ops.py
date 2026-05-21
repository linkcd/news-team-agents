import os
from unittest.mock import patch, MagicMock

import pytest


def test_git_clone_clones_repo_to_temp_dir():
    from tools.git_ops import git_clone

    with patch("tools.git_ops.git.Repo") as MockRepo:
        mock_repo = MagicMock()
        MockRepo.clone_from.return_value = mock_repo

        with patch("tools.git_ops._get_github_token", return_value="ghp_test123"):
            result = git_clone(repo="claw-lu/hexo-blog", branch="main")

    assert result["status"] == "success"
    assert result["repo_path"] != ""
    MockRepo.clone_from.assert_called_once()
    clone_url = MockRepo.clone_from.call_args[0][0]
    assert "ghp_test123" in clone_url
    assert "claw-lu/hexo-blog" in clone_url


def test_git_clone_handles_clone_failure():
    from tools.git_ops import git_clone

    with patch("tools.git_ops.git.Repo") as MockRepo:
        MockRepo.clone_from.side_effect = Exception("Authentication failed")
        with patch("tools.git_ops._get_github_token", return_value="ghp_bad"):
            result = git_clone(repo="claw-lu/hexo-blog", branch="main")

    assert result["status"] == "error"
    assert "Authentication failed" in result["error"]


def test_git_commit_and_push_writes_and_pushes():
    from tools.git_ops import git_commit_and_push

    with patch("tools.git_ops.git.Repo") as MockRepo:
        mock_repo = MagicMock()
        MockRepo.return_value = mock_repo
        mock_repo.index = MagicMock()
        mock_commit = MagicMock()
        mock_commit.hexsha = "abc123def456"
        mock_repo.index.commit.return_value = mock_commit
        mock_repo.remote.return_value = MagicMock()

        result = git_commit_and_push(
            repo_path="/tmp/hexo-blog",
            file_path="source/_posts/20260521-norway.md",
            content="# Test content",
            commit_message="Add Norway news 2026-05-21",
        )

    assert result["status"] == "success"
    assert result["commit_sha"] == "abc123def456"
    mock_repo.index.add.assert_called_once_with(["source/_posts/20260521-norway.md"])
    mock_repo.index.commit.assert_called_once_with("Add Norway news 2026-05-21")


def test_git_commit_and_push_writes_file_content():
    from tools.git_ops import git_commit_and_push

    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("tools.git_ops.git.Repo") as MockRepo:
            mock_repo = MagicMock()
            MockRepo.return_value = mock_repo
            mock_commit = MagicMock()
            mock_commit.hexsha = "abc123"
            mock_repo.index.commit.return_value = mock_commit
            mock_repo.remote.return_value = MagicMock()

            file_path = "source/_posts/test.md"
            result = git_commit_and_push(
                repo_path=tmpdir,
                file_path=file_path,
                content="# Hello",
                commit_message="test",
            )

        # File should be written to disk
        full_path = os.path.join(tmpdir, file_path)
        assert os.path.exists(full_path)
        with open(full_path) as f:
            assert f.read() == "# Hello"
