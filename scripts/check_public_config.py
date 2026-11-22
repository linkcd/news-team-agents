#!/usr/bin/env python3
# Copyright 2026 news-agent contributors
# SPDX-License-Identifier: Apache-2.0
"""Check public files and optional HEAD history without printing matched values."""
import argparse
from pathlib import Path
import re
import subprocess


PATTERNS = {
    "account_id": re.compile(rb"\b[0-9]{12}\b"),
    "runtime_id": re.compile(rb"news(?:collector_NewsCollector|publisher_NewsPublisher|orchestrator_NewsOrchestrator)-[A-Za-z0-9]{10}\b"),
    "access_key": re.compile(rb"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "github_token": re.compile(rb"\b(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]{30,}\b"),
    "private_key": re.compile(rb"-----BEGIN (?:[A-Z ]+)?PRIVATE KEY-----"),
    "user_path": re.compile(rb"/(?:Users|home)/[A-Za-z][^/\s\"']+"),
}


def categories(data):
    return [name for name, pattern in PATTERNS.items() if pattern.search(data)]


def private_path(name):
    return (name.startswith((".private/", ".monitoring/")) or "/.cli/" in name
            or name.endswith("/aws-targets.json")
            or name == "agents/orchestrator/infra/deployment.json"
            or bool(re.match(r"agents/[^/]+/agentcore/cdk/", name))
            or (Path(name).name.startswith(".env") and not name.endswith(".example")))


def safe_label(label):
    data = label.encode()
    for pattern in PATTERNS.values():
        data = pattern.sub(b"<REDACTED>", data)
    return data.decode(errors="replace")


def check_tree(root):
    names = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode().split("\0")
    failures = []
    for name in filter(None, names):
        if private_path(name):
            failures.append((name, ["private_file"]))
        path = root / name
        if path.is_file() and (found := categories(path.read_bytes())):
            failures.append((name, found))
    return failures


def check_history(root):
    objects = subprocess.check_output(["git", "rev-list", "--objects", "HEAD"], cwd=root).splitlines()
    failures = []
    process = subprocess.Popen(["git", "cat-file", "--batch"], cwd=root,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    try:
        for entry in objects:
            oid, _, path = entry.partition(b" ")
            process.stdin.write(oid + b"\n")
            process.stdin.flush()
            header = process.stdout.readline().split()
            if len(header) != 3:
                raise RuntimeError("Unable to inspect a history object")
            kind, size = header[1], int(header[2])
            data = process.stdout.read(size)
            process.stdout.read(1)
            label = path.decode(errors="replace") or f"{kind.decode()}:{oid[:12].decode()}"
            if kind == b"blob" and private_path(label):
                failures.append((label, ["private_file_in_history"]))
            if kind in (b"blob", b"commit") and (found := categories(data)):
                failures.append((label, found))
    finally:
        process.stdin.close()
        process.stdout.close()
        process.wait(timeout=30)
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", action="store_true", help="Also check every object reachable from HEAD")
    args = parser.parse_args()
    root = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"]).decode().strip())
    failures = check_tree(root)
    if args.history:
        failures += check_history(root)
    for label, found in failures:
        print(f"FAIL {safe_label(label)}: {', '.join(found)}")
    if failures:
        raise SystemExit(1)
    print("PASS: no deployment identifiers or private configuration found" + (" in HEAD history" if args.history else ""))


if __name__ == "__main__":
    main()
