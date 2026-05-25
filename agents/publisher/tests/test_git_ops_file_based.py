"""Tests for file-based git_commit_and_push.

The updated git_commit_and_push should commit whatever file is already on disk
at repo_path/file_path, without requiring the content as a parameter.
"""
import os
import tempfile
from unittest.mock import patch, MagicMock

import pytest


class TestGitCommitAndPushFileBased:
    def test_commits_existing_file_on_disk(self):
        from tools.git_ops import git_commit_and_push

        with tempfile.TemporaryDirectory() as tmpdir:
            post_path = "source/_posts/20260521-norway.md"
            full_path = os.path.join(tmpdir, post_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w") as f:
                f.write("# Already on disk")

            with patch("tools.git_ops.git.Repo") as MockRepo:
                mock_repo = MagicMock()
                MockRepo.return_value = mock_repo
                mock_commit = MagicMock()
                mock_commit.hexsha = "abc123"
                mock_repo.index.commit.return_value = mock_commit
                mock_repo.remote.return_value = MagicMock()

                result = git_commit_and_push(
                    repo_path=tmpdir,
                    file_path=post_path,
                    commit_message="Update post",
                )

            assert result["status"] == "success"
            assert result["commit_sha"] == "abc123"
            mock_repo.index.add.assert_called_once_with([post_path])
            mock_repo.index.commit.assert_called_once_with("Update post")
            mock_repo.remote("origin").push.assert_called_once()

    def test_does_not_overwrite_file_on_disk(self):
        """git_commit_and_push should NOT write to the file — it just commits what's there."""
        from tools.git_ops import git_commit_and_push

        with tempfile.TemporaryDirectory() as tmpdir:
            post_path = "source/_posts/20260521-norway.md"
            full_path = os.path.join(tmpdir, post_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w") as f:
                f.write("Original content on disk")

            with patch("tools.git_ops.git.Repo") as MockRepo:
                mock_repo = MagicMock()
                MockRepo.return_value = mock_repo
                mock_commit = MagicMock()
                mock_commit.hexsha = "def456"
                mock_repo.index.commit.return_value = mock_commit
                mock_repo.remote.return_value = MagicMock()

                git_commit_and_push(
                    repo_path=tmpdir,
                    file_path=post_path,
                    commit_message="test",
                )

            with open(full_path) as f:
                assert f.read() == "Original content on disk"

    def test_error_when_push_fails(self):
        from tools.git_ops import git_commit_and_push

        with tempfile.TemporaryDirectory() as tmpdir:
            post_path = "test.md"
            full_path = os.path.join(tmpdir, post_path)
            with open(full_path, "w") as f:
                f.write("content")

            with patch("tools.git_ops.git.Repo") as MockRepo:
                mock_repo = MagicMock()
                MockRepo.return_value = mock_repo
                mock_repo.remote("origin").push.side_effect = Exception("push failed")
                mock_repo.index.commit.return_value = MagicMock(hexsha="x")

                result = git_commit_and_push(
                    repo_path=tmpdir,
                    file_path=post_path,
                    commit_message="test",
                )

        assert result["status"] == "error"
        assert "push failed" in result["error"]
