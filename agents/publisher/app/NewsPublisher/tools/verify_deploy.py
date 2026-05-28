import time

import httpx
from bedrock_agentcore.identity import requires_api_key
from strands import tool

REPO = "claw-lu/hexo-blog"
WORKFLOW_FILE = "deploy.yml"
API_BASE = f"https://api.github.com/repos/{REPO}"


@requires_api_key(provider_name="github-token", into="api_key")
def _check_and_trigger(commit_sha: str, api_key: str = "") -> dict:
    """Check if deploy triggered for commit; dispatch workflow if not."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # Wait briefly for GitHub to register the push event
    time.sleep(10)

    # Check if any workflow run exists for this commit
    resp = httpx.get(
        f"{API_BASE}/actions/runs",
        headers=headers,
        params={"head_sha": commit_sha, "per_page": 5},
        timeout=15,
    )
    if resp.status_code == 200:
        runs = resp.json().get("workflow_runs", [])
        if runs:
            run = runs[0]
            return {
                "status": "success",
                "deploy_triggered": True,
                "run_id": run["id"],
                "run_status": run["status"],
                "triggered_by": "push",
            }

    # No run found — trigger workflow_dispatch as fallback
    dispatch_resp = httpx.post(
        f"{API_BASE}/actions/workflows/{WORKFLOW_FILE}/dispatches",
        headers=headers,
        json={"ref": "main"},
        timeout=15,
    )
    if dispatch_resp.status_code == 204:
        return {
            "status": "success",
            "deploy_triggered": True,
            "triggered_by": "workflow_dispatch_fallback",
            "reason": "No push-triggered run found for commit; dispatched manually.",
        }

    return {
        "status": "error",
        "deploy_triggered": False,
        "error": f"Failed to trigger deploy: HTTP {dispatch_resp.status_code} {dispatch_resp.text[:200]}",
    }


@tool
def verify_deploy(commit_sha: str) -> dict:
    """Verify that GitHub Actions deploy was triggered for a commit SHA.

    Checks if a workflow run exists for the given commit. If not found,
    triggers the deploy workflow manually via workflow_dispatch.

    Call this AFTER git_commit_and_push succeeds.

    Args:
        commit_sha: The commit SHA that was just pushed.

    Returns:
        Dict with status, deploy_triggered, and how it was triggered.
    """
    try:
        return _check_and_trigger(commit_sha=commit_sha)
    except Exception as e:
        return {"status": "error", "deploy_triggered": False, "error": str(e)}
