import json
import importlib
from unittest.mock import MagicMock, patch

import pytest


class TestInvokePublisher:
    """Test that invoke_publisher delegates to invoke_a2a with correct args."""

    def test_delegates_to_invoke_a2a_with_publisher_arn(self):
        import tools.a2a_client as a2a_mod
        original = a2a_mod.invoke_a2a

        calls = []
        a2a_mod.invoke_a2a = lambda arn, cfg: (calls.append((arn, cfg)) or {"status": "success"})
        try:
            from config import PUBLISHER_RUNTIME_ARN
            result = a2a_mod.invoke_a2a(PUBLISHER_RUNTIME_ARN, {"task_id": "p1", "type": "publish_new"})

            assert len(calls) == 1
            assert "newspublisher" in calls[0][0]
            assert calls[0][1] == {"task_id": "p1", "type": "publish_new"}
            assert result["status"] == "success"
        finally:
            a2a_mod.invoke_a2a = original
