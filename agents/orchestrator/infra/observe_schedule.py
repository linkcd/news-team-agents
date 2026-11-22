#!/usr/bin/env python3
# Copyright 2026 news-agent contributors
# SPDX-License-Identifier: Apache-2.0
"""Read-only scheduled-run observation. Detailed reports stay git-ignored."""
import argparse
import base64
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
import time
from urllib.request import Request, urlopen

import boto3
from botocore.config import Config

ROOT = Path(__file__).resolve().parents[3]
RULE = "news-agent-6h-schedule"
HOURS = (5, 11, 17, 23)


def utc(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Timestamps must include a timezone")
    return result.astimezone(timezone.utc)


def scheduled_slots(start, end):
    day = start.replace(hour=0, minute=0, second=0, microsecond=0)
    slots = []
    while day <= end:
        slots.extend(day.replace(hour=h) for h in HOURS if start < day.replace(hour=h) <= end)
        day += timedelta(days=1)
    return slots


def belongs_to_slot(value, slot):
    return utc(value).replace(second=0, microsecond=0) == slot


def completed_result(messages, slot):
    clean = [m for m in messages if "GET /ping" not in m]
    for text in ("".join(clean), "\n".join(clean)):
        candidates = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
        candidates.append(text.strip())
        for candidate in reversed(candidates):
            try:
                value = json.loads(candidate)
                if (isinstance(value, dict) and value.get("status") in {"success", "error", "failure", "failed"}
                        and isinstance(value.get("run_time"), str)
                        and belongs_to_slot(value["run_time"], slot.replace(second=0, microsecond=0))):
                    return value
            except (ValueError, TypeError):
                recovered = recover_truncated_result(candidate, slot)
                if recovered:
                    return recovered
    return None


def recover_truncated_result(text, slot):
    """Recover intact fields only; observe() still verifies S3, Git and the site."""
    if re.findall(r'"status"\s*:\s*"([^"]+)"', text) != ["success"]:
        return None
    if re.search(r'"dry_run"\s*:\s*true', text):
        return None
    run_time = re.search(r'"run_time"\s*:\s*"([^"]+)"', text)
    new = re.search(r'"new_topics"\s*:\s*(\d+)\s*[,}]', text)
    updated = re.search(r'"updated_topics"\s*:\s*(\d+)\s*[,}]', text)
    publication = re.search(r'"publish"\s*:\s*', text)
    if not all((run_time, new, updated, publication)):
        return None
    try:
        if not belongs_to_slot(run_time[1], slot.replace(second=0, microsecond=0)):
            return None
        publish, _ = json.JSONDecoder().raw_decode(text[publication.end():].lstrip())
        if publish is not None and not isinstance(publish, dict):
            return None
        if isinstance(publish, dict) and publish.get("dry_run"):
            return None
    except (ValueError, TypeError):
        return None
    return {"status": "success", "run_time": run_time[1], "log_reconstructed": True,
            "collection": {"new_topics": int(new[1]), "updated_topics": int(updated[1]),
                           "data_key": f"collections/{slot:%Y-%m-%d}/norway-news-{slot:%Y-%m-%d}-{slot:%H%M}.json"},
            "publish": publish}


def validate_result(result, collection):
    if result.get("status") != "success" or result.get("dry_run"):
        raise ValueError("Workflow did not report successful live execution")
    summary = result.get("collection") or {}
    new, updated = len(collection["new_items"]), len(collection["updated_items"])
    if summary.get("new_topics") != new or summary.get("updated_topics") != updated:
        raise ValueError("Workflow counts do not match the stored collection")
    publish = result.get("publish")
    if new or updated:
        if not publish or publish.get("dry_run") or not re.fullmatch(r"[0-9a-f]{40}", publish.get("commit_sha") or ""):
            raise ValueError("New content has no confirmed live source commit")


def validate_commit(commit, expected_path, slot):
    committed = utc(commit["commit"]["committer"]["date"])
    if not slot <= committed <= slot + timedelta(minutes=30):
        raise ValueError("Source commit falls outside the scheduled run window")
    if expected_path not in {item["filename"] for item in commit.get("files", [])}:
        raise ValueError("Source commit does not change the expected daily post")


def page_topic_count(html):
    class Topics(HTMLParser):
        def __init__(self):
            super().__init__()
            self.active = False
            self.text = ""
            self.count = 0

        def handle_starttag(self, tag, attrs):
            if tag == "h3":
                self.active, self.text = True, ""

        def handle_data(self, data):
            if self.active:
                self.text += data

        def handle_endtag(self, tag):
            if tag == "h3" and self.active:
                self.count += bool(re.match(r"\s*\d+\.\s+", self.text))
                self.active = False

    parser = Topics()
    parser.feed(html)
    return parser.count


def safe_error(error):
    text = re.sub(r"https://[^\s@]+@github\.com", "https://[REDACTED]@github.com", str(error))
    return re.sub(r"(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]+", "[REDACTED]", text)[:1000]


class Observer:
    def __init__(self, configuration, profile, old_profile, site_url):
        self.config = configuration
        self.session = boto3.Session(profile_name=profile, region_name=configuration["region"])
        self.old = boto3.Session(profile_name=old_profile, region_name=configuration["region"])
        self.site_url = site_url.rstrip("/")
        if not self.site_url.startswith("https://"):
            raise ValueError("The site URL must use HTTPS")
        self.clients = {}

    def client(self, service):
        if service not in self.clients:
            self.clients[service] = self.session.client(service, config=Config(
                connect_timeout=10, read_timeout=20, retries={"total_max_attempts": 2}))
        return self.clients[service]

    def preflight(self):
        if self.client("sts").get_caller_identity()["Account"] != self.config["account"]:
            raise ValueError("CLI identity does not match private deployment configuration")
        if self.old.client("sts").get_caller_identity()["Account"] == self.config["account"]:
            raise ValueError("Old and new profiles must refer to different accounts")
        if self.client("events").describe_rule(Name=RULE)["State"] != "ENABLED":
            raise ValueError("New schedule is not enabled")
        if self.old.client("events").describe_rule(Name=RULE)["State"] != "DISABLED":
            raise ValueError("Old schedule is not disabled")

    def messages(self, group, start, end, stream=None):
        kwargs = {"logGroupName": group, "startTime": int(start.timestamp() * 1000),
                  "endTime": int(end.timestamp() * 1000)}
        if stream:
            kwargs.update(logStreamName=stream, startFromHead=True)
            messages, token = [], None
            while True:
                page = self.client("logs").get_log_events(**kwargs)
                messages.extend(e["message"] for e in page["events"])
                next_token = page.get("nextForwardToken")
                if not next_token or next_token == token:
                    return messages
                token = next_token
                kwargs["nextToken"] = token
        return [e["message"] for page in self.client("logs").get_paginator("filter_log_events").paginate(**kwargs)
                for e in page.get("events", [])]

    def github(self, endpoint):
        return json.loads(subprocess.check_output(["gh", "api", endpoint], text=True,
                                                  stderr=subprocess.PIPE, timeout=30))

    def observe(self, slot, now, require_eventbridge=True):
        evidence = {"scheduled_at": slot.isoformat(), "status": "pending"}

        def pending(reason):
            return {**evidence, "status": "missing_evidence" if now >= slot + timedelta(minutes=30) else "pending",
                    "reason": reason}

        if now < slot:
            return {**evidence, "status": "waiting"}
        self.preflight()
        end = min(now, slot + timedelta(minutes=30))
        if require_eventbridge:
            metrics = self.client("cloudwatch").get_metric_statistics(
                Namespace="AWS/Events", MetricName="InvocationAttempts",
                Dimensions=[{"Name": "RuleName", "Value": RULE}],
                StartTime=slot - timedelta(minutes=2), EndTime=end, Period=60, Statistics=["Sum"])
            attempts = sum(point["Sum"] for point in metrics["Datapoints"])
            if not attempts:
                return pending("Waiting for EventBridge invocation evidence")
            evidence["eventbridge_invocation_attempts"] = attempts

        receipts = []
        for message in self.messages("/aws/lambda/news-agent-schedule-invoker", slot, end):
            try:
                receipt = json.loads(message)
                if isinstance(receipt, dict) and receipt.get("session_id") and belongs_to_slot(receipt.get("run_time", ""), slot):
                    receipts.append(receipt)
            except (ValueError, TypeError):
                continue
        if not receipts:
            return pending("Waiting for the Lambda submission receipt")
        evidence.update(session_id=receipts[-1]["session_id"], submission_count=len(receipts))
        runtimes = [r for page in self.client("bedrock-agentcore-control").get_paginator("list_agent_runtimes").paginate()
                    for r in page.get("agentRuntimes", []) if r["agentRuntimeName"] == "newsorchestrator_NewsOrchestrator"]
        if len(runtimes) != 1:
            raise ValueError("Could not uniquely resolve the Orchestrator runtime")
        group = f"/aws/bedrock-agentcore/runtimes/{runtimes[0]['agentRuntimeId']}-DEFAULT"
        result = completed_result(self.messages(group, slot, end, f"runtime-logs-{evidence['session_id']}"), utc(receipts[-1]["run_time"]))
        if result is None:
            return pending("Waiting for the final Orchestrator result")
        if result.get("status") != "success":
            return {**evidence, "status": "failed", "reason": safe_error(result.get("error", "Workflow reported failure"))}
        key = f"collections/{slot:%Y-%m-%d}/norway-news-{slot:%Y-%m-%d}-{slot:%H%M}.json"
        if (result.get("collection") or {}).get("data_key") != key:
            raise ValueError("Unexpected collection key in the workflow result")
        obj = self.client("s3").get_object(Bucket=self.config["bucketName"], Key=key)
        body = obj["Body"]
        try:
            collection = json.loads(body.read())
        finally:
            body.close()
        if obj["LastModified"] < slot or collection.get("task_id") != f"norway-news-{slot:%Y-%m-%d}-{slot:%H%M}":
            raise ValueError("Stale or unrelated collection object")
        validate_result(result, collection)
        evidence.update(data_key=key, new_topics=len(collection["new_items"]), updated_topics=len(collection["updated_items"]),
                        log_reconstructed=result.get("log_reconstructed", False))
        publish = result.get("publish")
        if publish:
            sha = publish["commit_sha"]
            expected_path = f"source/_posts/{slot:%Y%m%d}-norway.md"
            if publish.get("file_path") != expected_path:
                raise ValueError("Unexpected publication path")
            commit = self.github(f"repos/{self.config['blogRepo']}/commits/{sha}")
            validate_commit(commit, expected_path, slot)
            source = self.github(f"repos/{self.config['blogRepo']}/contents/{expected_path}?ref={sha}")
            markdown = base64.b64decode(source["content"]).decode("utf-8")
            source_count = len(re.findall(r"^### \d+\.\s+.+$", markdown, re.M))
            if source_count != publish.get("total_items_in_post"):
                raise ValueError("Reported topic count does not match the committed post")
            runs = self.github(f"repos/{self.config['blogRepo']}/actions/workflows/{self.config['workflowFile']}/runs?head_sha={sha}&per_page=10")["workflow_runs"]
            successful = [r for r in runs if r["status"] == "completed" and r["conclusion"] == "success"]
            if not successful:
                return pending("Waiting for a successful GitHub deployment workflow")
            url = f"{self.site_url}/{slot:%Y/%m/%d}/{slot:%Y%m%d}-norway/"
            with urlopen(Request(url, headers={"User-Agent": "news-agent-observer", "Cache-Control": "no-cache"}), timeout=30) as response:
                count = page_topic_count(response.read().decode("utf-8"))
            expected = publish.get("total_items_in_post", 0)
            if expected <= 0 or count < expected:
                return pending("Waiting for the public page to reflect the published topic count")
            evidence.update(commit_sha=sha, workflow_url=successful[0]["html_url"], website_url=url, page_topics=count)
        return {**evidence, "status": "passed"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--old-profile", required=True)
    parser.add_argument("--site-url", required=True)
    parser.add_argument("--start", help="ISO timestamp; defaults to now, or the existing report's start")
    parser.add_argument("--hours", type=int, default=24, choices=(24, 48))
    parser.add_argument("--report", default=".monitoring/scheduled-runs.json")
    parser.add_argument("--once", action="store_true", help="Check existing evidence once, without waiting")
    args = parser.parse_args()
    report_path = (ROOT / args.report).resolve()
    if not any(report_path.is_relative_to(ROOT / folder) for folder in (".monitoring", ".private")):
        parser.error("Reports must stay under ignored .monitoring/ or .private/")
    config = json.loads(Path(__file__).with_name("deployment.json").read_text())
    observer = Observer(config, args.profile, args.old_profile, args.site_url)
    report = json.loads(report_path.read_text()) if report_path.exists() else {}
    start = utc(args.start or report.get("started_at") or datetime.now(timezone.utc).isoformat())
    end = start + timedelta(hours=args.hours)
    slots = scheduled_slots(start, end)
    report.update(started_at=start.isoformat(), observation_ends_at=end.isoformat())
    report.setdefault("runs", {})
    report_path.parent.mkdir(parents=True, exist_ok=True)
    while True:
        now = datetime.now(timezone.utc)
        for slot in slots:
            key = slot.isoformat()
            previous = report["runs"].get(key)
            if previous and previous["status"] == "passed":
                continue
            try:
                current = observer.observe(slot, now)
            except Exception as exc:
                current = {"scheduled_at": key, "status": "observation_error", "reason": safe_error(exc)}
            report["runs"][key] = current
            if current != previous:
                print(json.dumps({"scheduled_at": key, "status": current["status"]}), flush=True)
        all_passed = all(report["runs"][s.isoformat()]["status"] == "passed" for s in slots)
        report["status"] = ("complete" if all_passed else "needs_attention") if now >= end else "observing"
        report["updated_at"] = now.isoformat()
        temporary = report_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        temporary.replace(report_path)
        if args.once or now >= end:
            return
        time.sleep(60)


if __name__ == "__main__":
    main()
