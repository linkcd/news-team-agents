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
