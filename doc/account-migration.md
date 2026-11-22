# AWS account migration: <AWS_ACCOUNT_ID> → <AWS_ACCOUNT_ID>

## Current checkpoint

The `github-token` Identity provider is verified in account <AWS_ACCOUNT_ID>.
**Migration cutover is complete, verified at 2026-11-22 16:03:08 UTC.**
All five stacks are in successful CREATE_COMPLETE or UPDATE_COMPLETE states.
All three AgentCore runtimes are `READY`. The scheduler Lambda is `Active`, targets
the new Orchestrator, and the new EventBridge rule is verified `ENABLED`.
The old schedule was disabled at **2026-11-22 15:44:02 UTC** after a successful
dry run and confirmation that the old 11:00 run had completed. The old rule remains
`DISABLED`. Both `scheduleEnabled` and `publishingEnabled` are true in deployment
configuration. Publisher is READY on version 2 with `PUBLISHING_ENABLED=true`, and
controlled live publication succeeded.

| Agent | New-account runtime ID | Status |
| --- | --- | --- |
| Collector | `<RUNTIME_ID>` | READY v3; quoted update-summary repair deployed |
| Publisher | `<RUNTIME_ID>` | READY v2; live publishing enabled and verified |
| Orchestrator | `<RUNTIME_ID>` | READY v2; new downstream ARNs, bucket and GitHub target verified |

Runtime ARNs use `arn:aws:bedrock-agentcore:eu-west-1:<AWS_ACCOUNT_ID>:runtime/` followed by the ID.

Verified bucket settings:

- Bootstrap asset bucket: `cdk-hnb659fds-assets-<AWS_ACCOUNT_ID>-eu-west-1`.
- News data bucket: `news-agent-data-example`.
- Both use automatic S3-managed `AES256` (SSE-S3) encryption; SSE-C is blocked.
- Both have all four public-access blocks enabled.
- News data versioning is enabled, HTTPS is required, and current/noncurrent
  versions have seven-day lifecycle expiration rules. A noncurrent version expires
  seven days after becoming noncurrent, not necessarily seven days after creation.

Next: observe scheduled runs for 24–48 hours before retiring old resources. The
schedule remains 05:00, 11:00, 17:00 and 23:00 UTC; at cutover the next automatic run
was 2026-11-22 17:00 UTC. Old resources are retained for rollback. Live validation
already passed; do not repeat the live invocation blindly.

Track scheduled-run verification and deferred work in [migration follow-ups](migration-followups.md).

Successful live run:

- Scheduler Lambda invoked with `time=2026-11-22T15:49:00Z`.
- Runtime session: `schedule-<SESSION_ID>`.
- Lambda returned `submission_uncertain` after its short connection timeout;
  runtime logs confirmed continued execution and eventual success.
- Collection: `collections/2026-11-22/norway-news-2026-11-22-1549.json`.
- Result: 20 new topics, 2 updated topics, 40 total topics.
- Source commit: `5f5493bbbe8ee9c0049cb7c7d56f9efb475f5210` at 15:56:11 UTC.
- GitHub deploy workflow `45041018417`: completed successfully.
- Public page verified: https://news.example.com/2026/11/22/20261122-norway/
- All 20 original titles and source URLs retained, original post date preserved,
  no duplicate titles, one source footer. Public page shows 40 topics and 15:56 UTC update time.
- EventBridge's permission to invoke the new Lambda was verified in its resource policy.

Successful dry run:

- Session: `<SESSION_ID>`, completed at 15:42:11 UTC.
- Collection: `collections/2026-11-22/norway-news-2026-11-22-1536.json`.
- Result: success, dry_run=true; 17 new topics, 1 updated topic, 37 topics in preview.
- Publisher executed clone, S3 read, prepare_post, read_local_file, update_summary,
  and the dry-run commit tool. No Git push occurred.
- Existing post blob SHA remained `23c10acd4e9c861055392c0e0ebcd8d89deee836`.
- Latest pre-cutover source commit: `2e1bc6112389bebd5443c90b6cf721c505557767`.

### End-to-end validation findings

The first direct A2A dry run found that invoking the runtime ARN alone was
insufficient: AgentCore also authorizes the `/runtime-endpoint/DEFAULT` resource.
Specific DEFAULT endpoint grants were added for Orchestrator's downstream calls
and the scheduler Lambda's Orchestrator call, with regression coverage.

The next dry run reached the sources and wrote a collection to
`collections/2026-11-22/norway-news-2026-11-22-1516.json`, but Collector returned a
Markdown report instead of structured JSON on both attempts. Orchestrator therefore
misclassified successful collection as failure. Its invocation tool now recovers
a metadata-only receipt from S3 for that specific response-format error, checking
task ID, item-list shape and S3 LastModified freshness. Its S3 permission is scoped
to `collections/*`; bulk content stays inside Python, outside the LLM context.
Collector also computes collection time and item counts in code before writing,
rather than trusting model-generated metadata.

The live run recovered from malformed JSON containing an unescaped quote in
`updated_summary_zh`. That field was then added to the existing JSON repair helper,
covered by a failing-then-passing regression test and deployed as Collector v3.
Current checked suites total 149 Python tests (44 Collector, 65 Publisher,
40 Orchestrator) plus 9 infrastructure tests. Startup checks used frozen real SDK
dependencies in isolated environments.

The old account's 11:00 run completed and published at 11:05 UTC, producing 20
topics. Its successful GitHub deploy run was `45015552520`. Both VG feeds returned
404 in that old run too; that warning is not specific to the new deployment.

### SDK startup compatibility

The first Collector/Publisher deployment built successfully but exited at startup
because Strands 1.52.0 no longer exposes `Agent._invocation_lock`. All three
entrypoints now register public `BeforeInvocationEvent` / `AfterInvocationEvent`
hooks to track active invocations and report `HEALTHY_BUSY`. Regression checks run
the actual entrypoints and A2A executor constructors in a clean subprocess with
the frozen SDK dependencies and offline credentials. All 142 Python tests passed
under those environments before the successful redeployment.

Collector and Publisher were deployed together. The local CDK command did not
return promptly even after both AWS stacks completed; confirm actual status using
CloudFormation and AgentCore APIs instead of assuming an attached CLI is evidence
that a deployment is still running. Publisher completed at 14:51:20 UTC on 2026-11-22.

### Encryption and versioning decisions

The initial standard bootstrap attempted to set SSE-KMS bucket encryption and was
denied by SCP `<POLICY_ID>` (`s3:PutEncryptionConfiguration`). The account administrator
explicitly requested using the existing S3 defaults instead. `src/bootstrap.ts`
generates a custom bootstrap variant that omits `BucketEncryption`, prevents
selecting/creating a KMS key, and preserves the standard IAM, public-access, TLS,
versioning, lifecycle and retention definitions. The SCP remains enforced.

The failed bootstrap's retained asset bucket was verified empty (including object
versions, delete markers and multipart uploads), then removed along with the
rolled-back stack record before recreating bootstrap. The subsequent foundation
attempt was rejected by Control Tower hook `CT.S3.PR.11`, which requires versioning.
Versioning and noncurrent-version expiration were added, the failed stack record
was removed, and foundation deployment succeeded.

Always use the custom bootstrap template below for bootstrap creation/upgrades.
Its distinct `BootstrapVariant` protects it from accidental standard-template
replacement. The deprecated `FileAssetKeyArn` output retains the CLI sentinel
`AWS_MANAGED_KEY`; the actual bucket encryption is SSE-S3 as verified by
`get-bucket-encryption`.

| Setting | Value |
| --- | --- |
| Old AWS CLI profile/account | `default` / `<AWS_ACCOUNT_ID>` |
| New AWS CLI profile/account | `your-profile` / `<AWS_ACCOUNT_ID>` |
| Region | `eu-west-1` |
| New data bucket | `news-agent-data-example` |
| Source repository | `example/blog`, branch `main` (private) |
| Build workflow | `.github/workflows/deploy.yml` in the source repo |
| Generated site | `example/blog-site`, branch `main` |
| Website | https://news.example.com |

The source repo's GitHub Actions workflow already uses its `DEPLOY_TOKEN` secret to
push the generated site. That GitHub secret is separate from the AWS-side
`github-token` credential used by Collector and Publisher.

## Deployment entrypoint

Use the maintained CDK app in **`agents/orchestrator/infra/`** for this migration.
It uses the supported `@aws/agentcore-cdk` `AgentEnvironment` construct and each
agent's existing runtime spec and Dockerfile. It creates four independent stacks:

1. `NewsAgent-Foundation`: shared private versioned S3 bucket, automatic SSE-S3,
   seven-day current/noncurrent expiry, retained on deletion.
2. `NewsAgent-Collector`: runtime, build resources, Identity/S3 permissions, telemetry.
3. `NewsAgent-Publisher`: runtime, build resources, Identity/S3 permissions, telemetry.
4. `NewsAgent-Orchestrator`: runtime, downstream references/permissions, telemetry,
   scheduler Lambda and disabled-by-default EventBridge rule.

The generated `agents/*/agentcore/cdk/` directories are legacy scaffolding and still
describe old-account permissions. **Do not use `agentcore deploy` for the new
account.** This maintained app supplies environment variables and cross-stack
runtime ARN references automatically. No manual copying of runtime IDs is needed.

Standalone CDK deployment does not populate AgentCore CLI `.cli` state. Inspect
CloudFormation outputs and use explicit AWS runtime ARNs for invocation; an
`agentcore invoke` command requires a separately imported CLI deployment state.

## 1. Select and verify the account

In a dedicated terminal in the migration worktree:

```bash
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_SECURITY_TOKEN
export AWS_PROFILE=your-profile
export AWS_REGION=eu-west-1
export AWS_DEFAULT_REGION=eu-west-1
aws sts get-caller-identity --profile your-profile --region eu-west-1
```

Expect account `<AWS_ACCOUNT_ID>`. If the session expires:

```bash
aws sso login --profile your-profile
```

Preserve the original worktree and its old `.cli` state for rollback. This
migration worktree was based on the original local HEAD, including its unpushed
security commit.

## 2. Configure the GitHub credential

Create a fine-grained GitHub token owned by an identity with access to
`example/blog`. Select that repository and grant **Contents: read/write** and
**Actions: read/write** (metadata read access is automatic). Collector needs to
read the private repo; Publisher needs to clone/push and check or dispatch the
deploy workflow. Existing branch rules must permit the intended bot/user to push.

From the migration worktree root, run:

```bash
uv run --no-project --python 3.12 --with boto3 -- \
  python agents/orchestrator/infra/configure_github.py --profile your-profile
```

Paste the token at the hidden terminal prompt. The helper verifies the account
before asking for the token, then passes it directly to AgentCore Identity. It
does not write a token file, pass the token as a command argument, or overwrite
an existing provider. Both runtimes refer to the account-local provider named
`github-token`.

Confirm metadata only:

```bash
aws bedrock-agentcore-control list-api-key-credential-providers \
  --profile your-profile --region eu-west-1
```

## 3. Build and preview the infrastructure

```bash
cd agents/orchestrator/infra
npm ci
npm test
npm run synth -- --profile your-profile --quiet
```

If the user's default npm cache has permission errors, use a writable cache, e.g.
`npm ci --cache /tmp/news-agent-npm-cache`.

Review `deployment.json`. It contains non-secret deployment settings. Keep both
switches false. Confirm the proposed bucket name is available before deployment;
if a different name is needed, set it here before synthesizing.

The CDK app checks that all three `aws-targets.json` files match the configured
account and region. It also refuses synthesis with a resolved CLI account that
does not match the deployment account.

## 4. Bootstrap and deploy (new account only)

From `agents/orchestrator/infra`:

```bash
npm run bootstrap:template
npx cdk bootstrap aws://<AWS_ACCOUNT_ID>/eu-west-1 --profile your-profile \
  --template dist/bootstrap-s3-default.yaml --no-bootstrap-customer-key
npm run deploy -- NewsAgent-Foundation --profile your-profile
npm run deploy -- NewsAgent-Collector NewsAgent-Publisher --profile your-profile
npm run deploy -- NewsAgent-Orchestrator --profile your-profile
```

Keep the CDK change approval prompts. Container builds run in CodeBuild using the
existing Dockerfiles and Python lockfiles. The new runtime IDs will differ from
the old account's IDs. The cross-stack references inject the actual ARN outputs
into Orchestrator and its IAM policies.

All five stacks are already complete at the current checkpoint; continue with
dry-run validation rather than recreating the deployment.

Each runtime stack exports a `RuntimeArn` and `RuntimeId` output. For example:

```bash
aws cloudformation describe-stacks --stack-name NewsAgent-Orchestrator \
  --profile your-profile --region eu-west-1 \
  --query 'Stacks[0].Outputs' --output table
aws events describe-rule --name news-agent-6h-schedule \
  --profile your-profile --region eu-west-1
```

The rule must be `DISABLED`. Publisher must have `PUBLISHING_ENABLED=false`.
Model profile metadata was ACTIVE at preflight; actual Bedrock inference access
and organizational policy restrictions still need to be exercised.

## 5. Validate in dry-run mode

Invoke the new Orchestrator with the current UTC run time, using its actual ARN.
Confirm the complete run in application logs/traces:

1. Both downstream agents are reachable and can use AgentCore Identity.
2. Collector reads today's private GitHub post and writes to the new S3 bucket.
3. Publisher clones the same repository and chooses create/merge from file existence.
4. Existing items, dates, links and topic summaries survive the merge.
5. Publisher reports `dry_run=true`; no commit, push or workflow dispatch occurs.

This is a publishing dry run: RSS/GitHub reads, model calls and S3 writes still
occur. The `PUBLISHING_ENABLED` runtime setting is enforced in the Git and deploy
tools, rather than relying on an LLM instruction.

Historical articles stay in GitHub. S3 is transient collection storage. Inventory
any pending/unpublished old-account collection before deciding whether a copy or
replay is needed.

## 6. Cut over

Coordinate between the existing 05:00, 11:00, 17:00 and 23:00 UTC runs.

1. Record the last successful old run, collected time window and GitHub commit.
2. Disable the old rule explicitly using profile `default`:

   ```bash
   aws events disable-rule --name news-agent-6h-schedule \
     --profile default --region eu-west-1
   ```

3. Check for running work and queued retries in the old account. A returned/timed
   out invoker Lambda does not mean the agents have finished. Wait for them to drain.
4. Set `publishingEnabled` to `true` in `deployment.json`, leaving the schedule false.
5. Deploy `NewsAgent-Publisher` and execute one controlled production run.
6. Confirm the source commit, the successful `deploy.yml` run, the generated-site
   update and the published article at the existing custom domain.
7. Set `scheduleEnabled` to `true`, then deploy `NewsAgent-Orchestrator`.
8. Verify the new rule is enabled and the old rule is disabled. Reconcile any
   missed collection window using existing GitHub URLs to avoid duplicates.

Change these switches in the file and deploy; avoid console-only changes that a
later deployment would overwrite. The application refuses to enable scheduling
while publishing is disabled.

The new invoker preserves the scheduled event timestamp and disables automatic
SDK/Lambda/EventBridge retries to avoid duplicate submissions. A read timeout is
logged as `submission_uncertain`, not publication success; investigate the runtime
session before any manual retry.

## 7. Observe and roll back if necessary

Observe 24–48 hours of scheduled runs before retiring old resources.

Rollback order:

1. Disable the new rule with profile `your-profile` and wait for active runs to finish.
2. Set both new deployment switches to false and deploy those settings.
3. Inspect changes already pushed to GitHub; preserve valid new content. Correct
   individual bad changes rather than resetting the entire blog repository.
4. Re-enable the old rule with profile `default` once only the old account can publish.
5. Reconcile any missed window using the current GitHub content.

Keep the old runtime images, configuration and credentials available until the
rollback period ends. Remove old resources only after explicit retirement approval.
