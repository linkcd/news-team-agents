"""Offline startup check with real installed SDKs in a clean subprocess."""
import importlib.metadata
import os
from pathlib import Path
import subprocess
import sys

import pytest


def test_entrypoint_starts_with_installed_sdks():
    try:
        importlib.metadata.version("strands-agents")
    except importlib.metadata.PackageNotFoundError:
        pytest.skip("Run with the agent's frozen dependencies to exercise real SDK startup")
    app = Path(__file__).parents[1] / "app" / "NewsCollector"
    env = {**os.environ, "AWS_ACCESS_KEY_ID": "offline-test", "AWS_SECRET_ACCESS_KEY": "offline-test",
           "AWS_EC2_METADATA_DISABLED": "true", "AWS_REGION": "eu-west-1", "AWS_DEFAULT_REGION": "eu-west-1"}
    result = subprocess.run([sys.executable, "-c", "import main; from bedrock_agentcore.runtime.models import PingStatus; main.StrandsA2AExecutor(main.agent, enable_a2a_compliant_streaming=False); assert main.ping_handler() == PingStatus.HEALTHY"],
                            cwd=app, env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
