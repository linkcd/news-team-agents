# Migration follow-ups

Deployment targets and execution evidence are kept in ignored private configuration.
See [the migration runbook](account-migration.md) for deployment details and rollback.

## Scheduled-run verification — in progress

The controlled Lambda-triggered live run passed, and the schedule was switched on
2026-11-22. That is not yet proof of an automatic EventBridge-triggered run.

- [x] Verify the first automatic run after cutover (evidence recorded privately).
- [ ] Observe the following scheduled runs for at least 24 hours before retiring old resources.

For each run, record the scheduled time, EventBridge invocation evidence, Lambda
session ID, final Orchestrator result and S3 collection key. When there is new
content, also verify the source commit, successful `deploy.yml` workflow and
updated public page. A successful Lambda response or `submission_uncertain`
alone is not an end-to-end success. A run with no new content may legitimately
finish with `publish: null`.

Expected schedule: **05:00, 11:00, 17:00, 23:00 UTC**.
The new account's rule must stay enabled; the old account's rule must stay disabled.

## Deferred TODOs

### Privacy provider-cache follow-up

- [ ] Repository owner requests provider cleanup of cached copies of the old history.

Current files and reachable main history are sanitized. Provider caches and
existing clones are separate; the cleanup details are in ignored private notes.

### 1. Add end-to-end failure and missed-run alerts

- [ ] Persist or emit a deterministic completion signal for every scheduled run.
- [ ] Alert when a scheduled run fails or no completion signal arrives within the agreed window.
- [ ] Cover Collector/Publisher failures and GitHub deployment failures, not just Lambda errors.
- [ ] Choose the notification destination and test the alert and recovery paths.

Acceptance: a simulated failed or missing run produces an actionable notification;
a successful no-new-content run does not produce a false alarm.

### 2. Repair the two VG RSS feeds

- [ ] Find working official replacements for the VG Innenriks and VG Utenriks URLs.
- [ ] Verify feed parsing, timezone handling and domestic/international categorization.
- [ ] Add regression coverage and deploy the source configuration update.

Current URLs return 404 in both the old and new deployments:

```text
https://www.vg.no/rss/feed/?categories=1069
https://www.vg.no/rss/feed/?categories=1070
```

Acceptance: both feeds fetch successfully and produce correctly categorized
articles when articles exist in the collection window.

### 3. Retire the old news-agent deployment after the rollback window

- [ ] Complete 24–48 hours of successful scheduled-run observation.
- [ ] Inventory dependencies on the old runtime ARNs, data bucket and credential provider.
- [ ] Confirm the new deployment can operate independently and preserve required diagnostic evidence.
- [ ] Remove only obsolete news-agent stacks/resources from the old account.
- [ ] Check retained data buckets, logs, build assets, ECR images and KMS resources for cleanup needs.
- [ ] Preserve shared resources used by other applications in the old account.
- [ ] Update legacy deployment documentation/scaffolding after retirement.

Acceptance: obsolete news-agent resources no longer incur avoidable cost; other
applications, the existing GitHub repositories and the public website remain functional.

Cleanup requires a separate confirmation after the observation window.

### 4. Resolve agent-side deployment-verification errors

- [ ] Investigate HTTP 403 responses from the agent's GitHub Actions verification call.
- [ ] Correct private token permissions or configuration as indicated by the response.
- [ ] Verify both workflow-status reads and the intended fallback dispatch behavior.

The first automatic run published successfully and its real GitHub deployment was
verified independently. The agent-side verification warning still needs attention.

## Read-only observation helper

Use `agents/orchestrator/infra/observe_schedule.py` to observe a 24- or 48-hour
window. It reads EventBridge metrics, Lambda/Orchestrator logs, S3 collections,
GitHub deployment results and the public page. It does not trigger runs, publish
content, change schedules or send alerts.

```bash
uv run --no-project --python 3.12 --with boto3 -- \
  python agents/orchestrator/infra/observe_schedule.py \
  --profile "$AWS_PROFILE" --old-profile "$OLD_AWS_PROFILE" \
  --site-url "$BLOG_SITE_URL" --hours 24 \
  --report .monitoring/scheduled-runs.json
```

Supply the profile names and site URL privately. Reports are restricted to ignored
`.monitoring/` or `.private/` directories because they contain deployment evidence.
The watcher needs this machine to remain available and the CLI sessions to remain
valid. Authentication/network gaps are recorded as observation errors, never as
successful runs. Use `--once` to recheck stored evidence without waiting. Public
documentation should record only completion status, not private run identifiers.

Some runtime stdout lines can be truncated. The observer can reconstruct intact
result fields and the deterministic collection key, but still verifies S3 task
identity/counts, the commit's time and changed file, the committed topic count,
the GitHub deployment, and the public page before reporting success. Such results
are marked `log_reconstructed` in the private report.
