import os
from unittest.mock import patch, MagicMock

import pytest


def test_git_clone_clones_repo_to_temp_dir():
    from tools.git_ops import git_clone

    with patch("tools.git_ops.git.Repo") as MockRepo:
        mock_repo = MagicMock()
        MockRepo.clone_from.return_value = mock_repo

        with patch("tools.git_ops._clone_with_token") as mock_clone:
            mock_clone.return_value = {"status": "success", "repo_path": "/tmp/publisher_abc"}
            result = git_clone(repo="claw-lu/hexo-blog", branch="main")

    assert result["status"] == "success"
    assert result["repo_path"] == "/tmp/publisher_abc"
    mock_clone.assert_called_once_with(repo="claw-lu/hexo-blog", branch="main")


def test_git_clone_handles_clone_failure():
    from tools.git_ops import git_clone

    with patch("tools.git_ops._clone_with_token") as mock_clone:
        mock_clone.side_effect = Exception("Authentication failed")
        result = git_clone(repo="claw-lu/hexo-blog", branch="main")

    assert result["status"] == "error"
    assert "Authentication failed" in result["error"]


def test_clone_with_token_uses_token_in_url():
    from tools.git_ops import _clone_with_token

    with patch("tools.git_ops.git.Repo") as MockRepo:
        MockRepo.clone_from.return_value = MagicMock()

        result = _clone_with_token(repo="claw-lu/hexo-blog", branch="main", api_key="ghp_test123")

    assert result["status"] == "success"
    assert result["repo_path"] != ""
    MockRepo.clone_from.assert_called_once()
    clone_url = MockRepo.clone_from.call_args[0][0]
    assert "ghp_test123" in clone_url
    assert "claw-lu/hexo-blog" in clone_url


def test_git_commit_and_push_commits_and_pushes():
    from tools.git_ops import git_commit_and_push

    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = "source/_posts/20260521-norway.md"
        full_path = os.path.join(tmpdir, file_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w") as f:
            f.write("# Test content")

        with patch("tools.git_ops.git.Repo") as MockRepo:
            mock_repo = MagicMock()
            MockRepo.return_value = mock_repo
            mock_repo.index = MagicMock()
            mock_commit = MagicMock()
            mock_commit.hexsha = "abc123def456"
            mock_repo.index.commit.return_value = mock_commit
            mock_repo.remote.return_value = MagicMock()

            result = git_commit_and_push(
                repo_path=tmpdir,
                file_path=file_path,
                commit_message="Add Norway news 2026-05-21",
            )

    assert result["status"] == "success"
    assert result["commit_sha"] == "abc123def456"
    mock_repo.index.add.assert_called_once_with(["source/_posts/20260521-norway.md"])
    mock_repo.index.commit.assert_called_once_with("Add Norway news 2026-05-21")


def test_git_commit_and_push_does_not_modify_file():
    """git_commit_and_push should only commit; it should not write or overwrite the file."""
    from tools.git_ops import git_commit_and_push

    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = "source/_posts/test.md"
        full_path = os.path.join(tmpdir, file_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w") as f:
            f.write("# Hello")

        with patch("tools.git_ops.git.Repo") as MockRepo:
            mock_repo = MagicMock()
            MockRepo.return_value = mock_repo
            mock_commit = MagicMock()
            mock_commit.hexsha = "abc123"
            mock_repo.index.commit.return_value = mock_commit
            mock_repo.remote.return_value = MagicMock()

            result = git_commit_and_push(
                repo_path=tmpdir,
                file_path=file_path,
                commit_message="test",
            )

        assert result["status"] == "success"
        with open(full_path) as f:
            assert f.read() == "# Hello"
