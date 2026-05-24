import os
import tempfile

import git
from bedrock_agentcore.identity import requires_api_key
from strands import tool


@requires_api_key(provider_name="github-token", into="api_key")
def _clone_with_token(repo: str, branch: str, api_key: str = "") -> dict:
    """Clone a repo using the injected API key as the GitHub token."""
    clone_url = f"https://{api_key}@github.com/{repo}.git"
    repo_path = tempfile.mkdtemp(prefix="publisher_")
    git.Repo.clone_from(clone_url, repo_path, branch=branch)
    return {"status": "success", "repo_path": repo_path}


@tool
def git_clone(repo: str, branch: str) -> dict:
    """Clone a GitHub repository to a temporary directory.

    Args:
        repo: Repository in "owner/repo" format
        branch: Branch to clone

    Returns:
        Dict with status, repo_path (local path to cloned repo), and error if any
    """
    try:
        return _clone_with_token(repo=repo, branch=branch)
    except Exception as e:
        return {"status": "error", "error": str(e), "repo_path": ""}


@tool
def read_local_file(repo_path: str, file_path: str) -> str:
    """Read a file from a locally cloned repository.

    Args:
        repo_path: Local path to the cloned repository (from git_clone result)
        file_path: Path within the repo to read (e.g. "source/_posts/20260521-norway.md")

    Returns:
        The file content as a string, or empty string if the file does not exist.
    """
    full_path = os.path.join(repo_path, file_path)
    if not os.path.exists(full_path):
        return ""
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read()


@tool
def git_commit_and_push(repo_path: str, file_path: str, content: str, commit_message: str) -> dict:
    """Write content to a file in the repo, commit, and push.

    Args:
        repo_path: Local path to the cloned repository
        file_path: Path within the repo to write (e.g. "source/_posts/20260521-norway.md")
        content: Full file content to write
        commit_message: Git commit message

    Returns:
        Dict with status, commit_sha, and error if any
    """
    try:
        full_path = os.path.join(repo_path, file_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

        repo = git.Repo(repo_path)
        repo.index.add([file_path])
        commit = repo.index.commit(commit_message)
        repo.remote("origin").push()
        return {"status": "success", "commit_sha": commit.hexsha}
    except Exception as e:
        return {"status": "error", "error": str(e), "commit_sha": ""}
