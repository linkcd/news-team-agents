import os
import sys
from unittest.mock import MagicMock

# Add app/NewsPublisher to path so tests can import tools, config, agent
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app", "NewsPublisher"))

# Stub out the strands module for testing
strands_mock = MagicMock()
strands_mock.tool = lambda fn: fn
sys.modules["strands"] = strands_mock

# Stub out boto3 for testing
if "boto3" not in sys.modules:
    boto3_mock = MagicMock()
    sys.modules["boto3"] = boto3_mock

import pytest
