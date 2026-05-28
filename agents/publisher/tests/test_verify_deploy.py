import importlib
import sys
from unittest.mock import patch, MagicMock

# Import the module directly (not via the package __init__ which re-exports the function)
import importlib.util
import os

_mod_path = os.path.join(os.path.dirname(__file__), "..", "app", "NewsPublisher", "tools", "verify_deploy.py")
_spec = importlib.util.spec_from_file_location("_verify_deploy_mod", _mod_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

_check_and_trigger = _mod._check_and_trigger
_verify_deploy_fn = _mod.verify_deploy


def test_deploy_already_triggered():
    """When GitHub Actions already has a run for the commit, return success with push trigger."""
    with patch.object(_mod, "_check_and_trigger") as mock_check:
        mock_check.return_value = {
            "status": "success",
            "deploy_triggered": True,
            "run_id": 12345,
            "run_status": "in_progress",
            "triggered_by": "push",
        }
        result = _mod.verify_deploy(commit_sha="abc123")
        assert result["status"] == "success"
        assert result["deploy_triggered"] is True
        assert result["triggered_by"] == "push"
        mock_check.assert_called_once_with(commit_sha="abc123")


def test_deploy_fallback_dispatch():
    """When no run found, verify_deploy triggers workflow_dispatch."""
    with patch.object(_mod, "_check_and_trigger") as mock_check:
        mock_check.return_value = {
            "status": "success",
            "deploy_triggered": True,
            "triggered_by": "workflow_dispatch_fallback",
            "reason": "No push-triggered run found for commit; dispatched manually.",
        }
        result = _mod.verify_deploy(commit_sha="def456")
        assert result["status"] == "success"
        assert result["triggered_by"] == "workflow_dispatch_fallback"


def test_deploy_dispatch_fails():
    """When dispatch also fails, return error."""
    with patch.object(_mod, "_check_and_trigger") as mock_check:
        mock_check.return_value = {
            "status": "error",
            "deploy_triggered": False,
            "error": "Failed to trigger deploy: HTTP 403 forbidden",
        }
        result = _mod.verify_deploy(commit_sha="ghi789")
        assert result["status"] == "error"
        assert result["deploy_triggered"] is False


def test_deploy_exception_handling():
    """When an exception is raised, return error gracefully."""
    with patch.object(_mod, "_check_and_trigger") as mock_check:
        mock_check.side_effect = RuntimeError("network timeout")
        result = _mod.verify_deploy(commit_sha="jkl012")
        assert result["status"] == "error"
        assert "network timeout" in result["error"]


def test_check_and_trigger_finds_run():
    """_check_and_trigger finds an existing run and returns it."""
    with patch.object(_mod, "time") as mock_time, \
         patch.object(_mod, "httpx") as mock_httpx:
        mock_time.sleep = MagicMock()
        mock_httpx.get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "workflow_runs": [{"id": 99999, "status": "completed"}]
            },
        )
        result = _mod._check_and_trigger(commit_sha="abc123", api_key="fake-token")
        assert result["triggered_by"] == "push"
        assert result["run_id"] == 99999
        mock_httpx.post.assert_not_called()


def test_check_and_trigger_dispatches_when_no_run():
    """_check_and_trigger dispatches workflow when no run found."""
    with patch.object(_mod, "time") as mock_time, \
         patch.object(_mod, "httpx") as mock_httpx:
        mock_time.sleep = MagicMock()
        mock_httpx.get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"workflow_runs": []},
        )
        mock_httpx.post.return_value = MagicMock(status_code=204)

        result = _mod._check_and_trigger(commit_sha="def456", api_key="fake-token")
        assert result["triggered_by"] == "workflow_dispatch_fallback"
        mock_httpx.post.assert_called_once()
