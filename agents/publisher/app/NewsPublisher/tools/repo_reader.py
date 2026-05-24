import httpx
from bedrock_agentcore.identity import requires_api_key
from strands import tool


@requires_api_key(provider_name="github-token", into="api_key")
def _read_file_with_token(repo: str, branch: str, path: str, api_key: str = "") -> dict:
    """Read a file using the injected GitHub token for private repos."""
    url = f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"
    headers = {"Authorization": f"token {api_key}"} if api_key else {}
    response = httpx.get(url, timeout=15, follow_redirects=True, headers=headers)
    response.raise_for_status()
    return {"status": "success", "content": response.text}


@tool
def read_repo_file(repo: str, branch: str, path: str) -> dict:
    """Read a file from a GitHub repository (supports private repos via AgentCore Identity).

    Args:
        repo: Repository in "owner/repo" format
        branch: Branch name (e.g. "main")
        path: File path within the repository

    Returns:
        Dict with status ("success", "not_found", or "error"), content string, and error if any
    """
    try:
        return _read_file_with_token(repo=repo, branch=branch, path=path)
    except Exception as e:
        if "404" in str(e):
            return {"status": "success", "content": "", "found": False}
        return {"status": "error", "error": str(e), "content": ""}
