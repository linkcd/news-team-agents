"""Test that the Publisher uses legacy A2A streaming (not chunked artifacts).

The A2A-compliant streaming mode has a bug where the initial append=False event
is dropped, causing all subsequent artifact chunks to be discarded by the client.
Legacy mode sends one complete artifact at the end, which is reliable.
"""

import ast


def test_executor_uses_legacy_streaming():
    """StrandsA2AExecutor must use enable_a2a_compliant_streaming=False."""
    import os

    main_path = os.path.join(
        os.path.dirname(__file__), "..", "app", "NewsPublisher", "main.py"
    )
    with open(main_path) as f:
        source = f.read()

    tree = ast.parse(source)

    found_call = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "StrandsA2AExecutor":
                found_call = True
                for kw in node.keywords:
                    if kw.arg == "enable_a2a_compliant_streaming":
                        assert isinstance(kw.value, ast.Constant)
                        assert kw.value.value is False, (
                            "enable_a2a_compliant_streaming must be False "
                            "to avoid chunked artifact streaming bug"
                        )
                        break
                else:
                    pass

    assert found_call, "StrandsA2AExecutor call not found in main.py"
