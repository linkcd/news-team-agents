"""Test that serve_a2a is called with a ping_handler that reports HEALTHY_BUSY during invocations."""

import ast
import threading
import os


def test_serve_a2a_called_with_ping_handler():
    """main.py must pass a ping_handler to serve_a2a."""
    main_path = os.path.join(
        os.path.dirname(__file__), "..", "app", "NewsPublisher", "main.py"
    )
    with open(main_path) as f:
        source = f.read()

    tree = ast.parse(source)

    found_serve_a2a = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "serve_a2a":
                found_serve_a2a = True
                kwarg_names = [kw.arg for kw in node.keywords]
                assert "ping_handler" in kwarg_names, (
                    "serve_a2a must be called with ping_handler= to signal "
                    "HEALTHY_BUSY during agent invocations"
                )
                break

    assert found_serve_a2a, "serve_a2a call not found in main.py"


def test_ping_handler_returns_healthy_when_idle():
    """When agent is idle, ping_handler should return HEALTHY."""
    from ping_health import make_ping_handler

    lock = threading.Lock()
    ping_handler = make_ping_handler(lock)

    status = ping_handler()
    assert status.value == "HEALTHY"


def test_ping_handler_returns_busy_when_agent_locked():
    """When agent's invocation lock is held, ping_handler should return HEALTHY_BUSY."""
    from ping_health import make_ping_handler

    lock = threading.Lock()
    ping_handler = make_ping_handler(lock)

    lock.acquire()
    try:
        status = ping_handler()
        assert status.value == "HEALTHY_BUSY"
    finally:
        lock.release()


def test_ping_handler_returns_healthy_after_lock_released():
    """After agent finishes processing, ping_handler should return HEALTHY again."""
    from ping_health import make_ping_handler

    lock = threading.Lock()
    ping_handler = make_ping_handler(lock)

    lock.acquire()
    lock.release()

    status = ping_handler()
    assert status.value == "HEALTHY"
