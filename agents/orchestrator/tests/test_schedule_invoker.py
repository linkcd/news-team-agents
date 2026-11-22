import importlib.util
import json
from pathlib import Path
import sys
import types
from unittest.mock import MagicMock, patch

import pytest


class ReadTimeoutError(Exception):
    pass


@pytest.fixture
def invoker(monkeypatch):
    monkeypatch.setenv("ORCHESTRATOR_RUNTIME_ARN", "arn:test:orchestrator")
    monkeypatch.setenv("AWS_REGION", "eu-west-1")
    path = Path(__file__).parents[1] / "infra/lambda/invoker.py"
    spec = importlib.util.spec_from_file_location("schedule_invoker", path)
    module = importlib.util.module_from_spec(spec)
    exceptions = types.ModuleType("botocore.exceptions")
    exceptions.ReadTimeoutError = ReadTimeoutError
    with patch.dict(sys.modules, {"botocore.exceptions": exceptions}):
        spec.loader.exec_module(module)
    return module


def test_scheduler_preserves_event_time_and_sends_valid_a2a_data_part(invoker):
    with patch.object(invoker, "boto3") as boto, patch.object(invoker, "Config") as config:
        result = invoker.handler({"time": "2026-05-21T11:00:00Z"}, None)
    request = boto.client.return_value.invoke_agent_runtime.call_args.kwargs
    part = json.loads(request["payload"])["params"]["message"]["parts"][0]
    assert part == {"kind": "data", "data": {"trigger": "scheduled", "run_time": "2026-05-21T11:00:00Z"}}
    assert result["status"] == "submitted"
    assert config.call_args.kwargs["retries"]["total_max_attempts"] == 1


def test_read_timeout_is_uncertain_not_confirmed_success(invoker):
    with patch.object(invoker, "boto3") as boto:
        boto.client.return_value.invoke_agent_runtime.side_effect = ReadTimeoutError()
        assert invoker.handler({}, None)["status"] == "submission_uncertain"


def test_permission_errors_are_not_swallowed(invoker):
    with patch.object(invoker, "boto3") as boto:
        boto.client.return_value.invoke_agent_runtime.side_effect = RuntimeError("AccessDenied")
        with pytest.raises(RuntimeError, match="AccessDenied"):
            invoker.handler({}, None)
