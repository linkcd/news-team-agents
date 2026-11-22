"""Public source must not contain deployment-specific configuration."""
from pathlib import Path
import re
import subprocess
import importlib.util


def test_public_checker_detects_identifiers_without_returning_values():
    root = Path(__file__).parents[3]
    spec = importlib.util.spec_from_file_location("public_checker", root / "scripts/check_public_config.py")
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    assert checker.categories(("7" * 12).encode()) == ["account_id"]
    runtime = ("newscollector_NewsCollector-" + "a" * 10).encode()
    assert checker.categories(runtime) == ["runtime_id"]
    assert checker.categories(b"<AWS_ACCOUNT_ID> example/blog") == []
    assert checker.private_path("agents/collector/agentcore/aws-targets.json")
    assert not checker.private_path("agents/collector/agentcore/aws-targets.example.json")


def test_deployment_configuration_is_not_tracked():
    root = Path(__file__).parents[3]
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode().split("\0")
    forbidden = [p for p in tracked if p.endswith("/aws-targets.json")
                 or p == "agents/orchestrator/infra/deployment.json" or "/.cli/" in p
                 or p.startswith(".private/")]
    assert not forbidden, f"Private configuration is tracked: {forbidden}"


def test_tracked_source_has_no_literal_account_ids_or_deployed_runtime_ids():
    root = Path(__file__).parents[3]
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode().split("\0")
    patterns = [re.compile(rb"\b[0-9]{12}\b"),
                re.compile(rb"news(?:collector_NewsCollector|publisher_NewsPublisher|orchestrator_NewsOrchestrator)-[A-Za-z0-9]{10}\b")]
    violations = []
    for name in tracked:
        path = root / name
        if not name or not path.is_file():
            continue
        data = path.read_bytes()
        if b"\0" not in data and any(pattern.search(data) for pattern in patterns):
            violations.append(name)
    # Report paths only; never reproduce a sensitive value in test output.
    assert not violations, f"Deployment identifiers found in: {violations}"
