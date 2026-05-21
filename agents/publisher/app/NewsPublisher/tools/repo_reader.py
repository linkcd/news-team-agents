import httpx
from strands import tool


@tool
def read_repo_file(repo: str, branch: str, path: str) -> dict:
    """Read a file from a public GitHub repository.

    Args:
        repo: Repository in "owner/repo" format
        branch: Branch name (e.g. "main")
        path: File path within the repository

    Returns:
        Dict with status ("success", "not_found", or "error"), content string, and error if any
    """
    url = f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"
    try:
        response = httpx.get(url, timeout=15, follow_redirects=True)
        response.raise_for_status()
        return {"status": "success", "content": response.text}
    except Exception as e:
        if "404" in str(e):
            return {"status": "not_found", "content": ""}
        return {"status": "error", "error": str(e), "content": ""}
