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

import threading

from bedrock_agentcore.runtime.models import PingStatus


def make_ping_handler(lock: threading.Lock):
    def ping_handler() -> PingStatus:
        if lock.locked():
            return PingStatus.HEALTHY_BUSY
        return PingStatus.HEALTHY

    return ping_handler


def make_agent_ping_handler(agent):
    """Track invocation health through public SDK hooks, not private agent locks."""
    from strands.hooks import BeforeInvocationEvent, AfterInvocationEvent

    state_lock = threading.Lock()
    busy_lock = threading.Lock()
    active = 0

    def started(event):
        nonlocal active
        with state_lock:
            active += 1
            if active == 1:
                busy_lock.acquire()

    def finished(event):
        nonlocal active
        with state_lock:
            active = max(0, active - 1)
            if active == 0 and busy_lock.locked():
                busy_lock.release()

    agent.hooks.add_callback(BeforeInvocationEvent, started)
    agent.hooks.add_callback(AfterInvocationEvent, finished)
    return make_ping_handler(busy_lock)
