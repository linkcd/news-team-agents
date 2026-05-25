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
def write_new_post(repo_path: str, file_path: str, content: str) -> dict:
    """Write content to a new file in the cloned repo.

    Used by publish_new to write the LLM-generated markdown to disk before committing.

    Args:
        repo_path: Local path to the cloned repository
        file_path: Path within the repo to write (e.g. "source/_posts/20260521-norway.md")
        content: Full file content to write

    Returns:
        Dict with status and error if any
    """
    try:
        full_path = os.path.join(repo_path, file_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@tool
def git_commit_and_push(repo_path: str, file_path: str, commit_message: str) -> dict:
    """Commit the file at repo_path/file_path and push to remote.

    The file must already exist on disk (written by merge_posts, update_summary,
    or write_new_post). This tool does NOT write content — it only commits and pushes.

    Args:
        repo_path: Local path to the cloned repository
        file_path: Path within the repo to commit (e.g. "source/_posts/20260521-norway.md")
        commit_message: Git commit message

    Returns:
        Dict with status, commit_sha, and error if any
    """
    try:
        repo = git.Repo(repo_path)
        repo.index.add([file_path])
        commit = repo.index.commit(commit_message)
        repo.remote("origin").push()
        return {"status": "success", "commit_sha": commit.hexsha}
    except Exception as e:
        return {"status": "error", "error": str(e), "commit_sha": ""}


@tool
def update_summary(repo_path: str, file_path: str, new_summary: str) -> dict:
    """Replace the day summary section in a blog post file on disk.

    Updates the text between "## 今日综述" and "<!-- more -->" with new_summary.
    Also updates the frontmatter "updated:" field and the "*最后更新:" line to current UTC time.

    Args:
        repo_path: Local path to the cloned repository
        file_path: Path within the repo to the blog post
        new_summary: The new day summary text (Chinese, ~300 words)

    Returns:
        Dict with status and error if any
    """
    import re
    import datetime

    full_path = os.path.join(repo_path, file_path)

    if not os.path.exists(full_path):
        return {"status": "error", "error": f"File not found: {file_path}"}

    with open(full_path, "r", encoding="utf-8") as f:
        content = f.read()

    summary_pattern = r"(## 今日综述\n).*?(\n<!-- more -->)"
    if not re.search(summary_pattern, content, re.DOTALL):
        return {"status": "error", "error": "No summary section found (## 今日综述 ... <!-- more -->)"}

    now = datetime.datetime.now(datetime.timezone.utc)
    time_str = now.strftime("%H:%M")
    updated_str = now.strftime("%Y-%m-%d %H:%M:%S")

    content = re.sub(
        summary_pattern,
        rf"\g<1>{new_summary}\n\2",
        content,
        flags=re.DOTALL,
    )

    content = re.sub(
        r"(updated:\s*).+",
        rf"\g<1>{updated_str}",
        content,
    )

    content = re.sub(
        r"\*最后更新:\s*.+?\s*UTC\*",
        f"*最后更新: {time_str} UTC*",
        content,
    )

    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)

    return {"status": "success"}
