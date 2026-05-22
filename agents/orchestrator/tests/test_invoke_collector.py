import json
import importlib
from unittest.mock import MagicMock, patch

import pytest


class TestInvokeCollector:
    """Test that invoke_collector delegates to invoke_a2a with correct args."""

    def test_delegates_to_invoke_a2a_with_collector_arn(self):
        import tools.a2a_client as a2a_mod
        original = a2a_mod.invoke_a2a

        calls = []
        a2a_mod.invoke_a2a = lambda arn, cfg: (calls.append((arn, cfg)) or {"status": "success"})
        try:
            from config import COLLECTOR_RUNTIME_ARN
            result = a2a_mod.invoke_a2a(COLLECTOR_RUNTIME_ARN, {"task_id": "t1", "sources": []})

            assert len(calls) == 1
            assert "newscollector" in calls[0][0]
            assert calls[0][1] == {"task_id": "t1", "sources": []}
            assert result["status"] == "success"
        finally:
            a2a_mod.invoke_a2a = original


class TestInvokeA2A:
    """Tests for the invoke_a2a function (core streaming A2A client logic)."""

    def test_returns_error_on_exception(self):
        with patch("tools.a2a_client.A2AAgent") as mock_cls, \
             patch("tools.a2a_client.boto3"), \
             patch("tools.a2a_client.httpx"), \
             patch("tools.a2a_client.ClientConfig"), \
             patch("tools.a2a_client.SigV4HTTPXAuth"):
            mock_instance = mock_cls.return_value
            mock_instance.side_effect = Exception("Connection timeout")

            from tools.a2a_client import invoke_a2a
            result = invoke_a2a("arn:aws:bedrock-agentcore:eu-west-1:123:runtime/test", {"task_id": "test"})
            assert result["status"] == "error"
            assert "Connection timeout" in result["error"]

    def test_extracts_json_from_fenced_code_block(self):
        from tools.a2a_client import _extract_json
        text_with_fence = '```json\n{"status": "success", "data_key": "collections/x.json"}\n```'
        result = _extract_json(text_with_fence)
        assert result["status"] == "success"
        assert result["data_key"] == "collections/x.json"

    def test_extracts_json_from_raw_text(self):
        from tools.a2a_client import _extract_json
        text = 'Here is the result: {"status": "success", "task_id": "t1"} done.'
        result = _extract_json(text)
        assert result["status"] == "success"

    def test_uses_build_runtime_url_from_agentcore(self):
        from config import AWS_REGION

        with patch("tools.a2a_client.build_runtime_url", return_value="https://example.com/invocations") as mock_url, \
             patch("tools.a2a_client.A2AAgent") as mock_cls, \
             patch("tools.a2a_client.boto3"), \
             patch("tools.a2a_client.httpx"), \
             patch("tools.a2a_client.ClientConfig"), \
             patch("tools.a2a_client.SigV4HTTPXAuth"):
            mock_instance = mock_cls.return_value
            mock_instance.return_value = MagicMock(message={"content": [{"text": '{"status": "success"}'}]})

            from tools.a2a_client import invoke_a2a
            test_arn = "arn:aws:bedrock-agentcore:eu-west-1:123:runtime/test"
            invoke_a2a(test_arn, {"task_id": "test"})
            mock_url.assert_called_once_with(test_arn, AWS_REGION)
