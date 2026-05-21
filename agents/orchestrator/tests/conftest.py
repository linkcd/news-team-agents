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

# Stub out bedrock_agentcore for testing
agentcore_mock = MagicMock()
sys.modules["bedrock_agentcore"] = agentcore_mock
sys.modules["bedrock_agentcore.runtime"] = agentcore_mock.runtime

# Stub out boto3 for testing (not installed in test env)
boto3_mock = MagicMock()
sys.modules["boto3"] = boto3_mock

import pytest
