# Copyright 2026 news-agent contributors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import time

import httpx
from bedrock_agentcore.identity import requires_api_key
from strands import tool
from config import publishing_enabled

@requires_api_key(provider_name="github-token", into="api_key")
def _check_and_trigger(commit_sha: str, api_key: str = "") -> dict:
    """Check if deploy triggered for commit; dispatch workflow if not."""
    repo = os.environ.get("BLOG_REPO", "")
    if not repo:
        return {"status": "error", "deploy_triggered": False, "error": "BLOG_REPO is required"}
    api_base = f"https://api.github.com/repos/{repo}"
    workflow = os.environ.get("BLOG_WORKFLOW", "deploy.yml")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # Wait briefly for GitHub to register the push event
    time.sleep(10)

    # Check if any workflow run exists for this commit
    resp = httpx.get(
        f"{api_base}/actions/workflows/{workflow}/runs",
        headers=headers,
        params={"head_sha": commit_sha, "per_page": 5},
        timeout=15,
    )
    if resp.status_code != 200:
        return {"status": "error", "deploy_triggered": False,
                "error": f"Failed to check deploy workflow: HTTP {resp.status_code}"}
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
        f"{api_base}/actions/workflows/{workflow}/dispatches",
        headers=headers,
        json={"ref": os.environ.get("BLOG_BRANCH", "main")},
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
    if not publishing_enabled():
        return {"status": "success", "dry_run": True, "deploy_triggered": False}
    try:
        return _check_and_trigger(commit_sha=commit_sha)
    except Exception as e:
        return {"status": "error", "deploy_triggered": False, "error": str(e)}
