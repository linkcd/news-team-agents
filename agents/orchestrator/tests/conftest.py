import os
import sys
from unittest.mock import MagicMock

# Add app/NewsOrchestrator to path so tests can import tools, config, agent
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app", "NewsOrchestrator"))

# Stub out the strands module for testing
strands_mock = MagicMock()
strands_mock.tool = lambda fn: fn
strands_mock.a2a = MagicMock()
sys.modules["strands"] = strands_mock
sys.modules["strands.a2a"] = strands_mock.a2a
sys.modules["strands.models"] = MagicMock()
sys.modules["strands.agent"] = MagicMock()
sys.modules["strands.agent.a2a_agent"] = MagicMock()
sys.modules["strands.multiagent"] = MagicMock()
sys.modules["strands.multiagent.a2a"] = MagicMock()

# Stub out bedrock_agentcore for testing
from enum import Enum

class _PingStatus(Enum):
    HEALTHY = "HEALTHY"
    HEALTHY_BUSY = "HEALTHY_BUSY"

agentcore_mock = MagicMock()
agentcore_mock.runtime.build_runtime_url = lambda arn, region=None: f"https://bedrock-agentcore.eu-west-1.amazonaws.com/runtimes/{arn}/invocations"
agentcore_models_mock = MagicMock()
agentcore_models_mock.PingStatus = _PingStatus
sys.modules["bedrock_agentcore"] = agentcore_mock
sys.modules["bedrock_agentcore.runtime"] = agentcore_mock.runtime
sys.modules["bedrock_agentcore.runtime.models"] = agentcore_models_mock

# Stub out boto3 and botocore for testing (not installed in test env)
boto3_mock = MagicMock()
sys.modules["boto3"] = boto3_mock

botocore_mock = MagicMock()
sys.modules["botocore"] = botocore_mock
sys.modules["botocore.config"] = botocore_mock.config
sys.modules["botocore.auth"] = MagicMock()
sys.modules["botocore.awsrequest"] = MagicMock()

# Stub out httpx and a2a.client for testing
httpx_mock = MagicMock()
sys.modules["httpx"] = httpx_mock

a2a_mock = MagicMock()
sys.modules["a2a"] = a2a_mock
sys.modules["a2a.client"] = MagicMock()
sys.modules["a2a.types"] = MagicMock()

import pytest
