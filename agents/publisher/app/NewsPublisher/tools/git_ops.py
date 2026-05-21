import os
import tempfile

import boto3
import git
from strands import tool


def _get_github_token() -> str:
    """Retrieve GitHub token from Secrets Manager."""
    client = boto3.client("secretsmanager")
    response = client.get_secret_value(SecretId="news-agent/github-token")
    return response["SecretString"]


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
        token = _get_github_token()
        clone_url = f"https://{token}@github.com/{repo}.git"
        repo_path = tempfile.mkdtemp(prefix="publisher_")
        git.Repo.clone_from(clone_url, repo_path, branch=branch)
        return {"status": "success", "repo_path": repo_path}
    except Exception as e:
        return {"status": "error", "error": str(e), "repo_path": ""}


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
