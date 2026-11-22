import sys
from types import SimpleNamespace
from unittest.mock import patch


def test_public_hooks_keep_runtime_busy_until_all_invocations_finish():
    from ping_health import make_agent_ping_handler

    before, after = type("BeforeInvocationEvent", (), {}), type("AfterInvocationEvent", (), {})
    callbacks = {}
    agent = SimpleNamespace(hooks=SimpleNamespace(add_callback=lambda event, callback: callbacks.update({event: callback})))
    with patch.dict(sys.modules, {"strands.hooks": SimpleNamespace(BeforeInvocationEvent=before, AfterInvocationEvent=after)}):
        ping = make_agent_ping_handler(agent)
    assert ping().value == "HEALTHY"
    callbacks[before](None)
    callbacks[before](None)
    callbacks[after](None)
    assert ping().value == "HEALTHY_BUSY"
    callbacks[after](None)
    assert ping().value == "HEALTHY"
