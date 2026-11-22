# Account migration runbook

Deployment-specific values are private. Account IDs, runtime ARNs/IDs, bucket
names, CLI profile names, repository destinations, website URLs and execution
evidence must not be committed to this public repository.

## Configuration

The maintained CDK app is in `agents/orchestrator/infra/`. It creates a foundation
bucket and separately deployable Collector, Publisher and Orchestrator stacks.
All stacks take their account, region and application settings from one ignored
local file:

```bash
cd agents/orchestrator/infra
cp deployment.example.json deployment.json
```

Fill in `deployment.json` locally. It is git-ignored. Keep any private migration
notes, runtime outputs and deployment evidence under the ignored `.private/`
directory. Do not overwrite an existing production configuration with the example.

The example starts with publishing and scheduling disabled. Before every change,
confirm the actual caller identity and review the private configuration:

```bash
export AWS_PROFILE=your-profile
export AWS_REGION=eu-west-1
aws sts get-caller-identity --profile "$AWS_PROFILE"
```

The public per-agent `aws-targets.example.json` files are examples only. If the
AgentCore CLI requires targets locally, copy them to ignored `aws-targets.json`
files and supply the appropriate account. The maintained CDK app does not depend
on those legacy CLI targets. CLI-generated CDK directories and `.cli` state are
also local-only; use the maintained app for infrastructure changes.

## Credentials

Use the existing account-local AgentCore Identity provider or provision one with
the hidden-prompt helper:

```bash
uv run --no-project --python 3.12 --with boto3 -- \
  python agents/orchestrator/infra/configure_github.py --profile "$AWS_PROFILE"
```

The helper checks the account against private configuration before prompting. It
does not persist the token in a source file or print it. The token needs access
to the configured source repository. Any credential used by the source repo's
GitHub Actions deployment remains separate from the AWS-side credential.

## Build and deploy

From `agents/orchestrator/infra/`:

```bash
npm ci
npm test
npm run synth -- --profile "$AWS_PROFILE" --quiet
```

The deployment uses S3's automatic SSE-S3 defaults without managing bucket
encryption settings. Public-access blocks and HTTPS requirements are retained.
The data bucket has versioning and current/noncurrent expiration rules. When
bootstrapping, use the tested custom variant:

```bash
npm run bootstrap:template
ACCOUNT_ID=$(aws sts get-caller-identity --profile "$AWS_PROFILE" --query Account --output text)
npx cdk bootstrap "aws://${ACCOUNT_ID}/${AWS_REGION}" --profile "$AWS_PROFILE" \
  --template dist/bootstrap-s3-default.yaml --no-bootstrap-customer-key
npm run deploy -- NewsAgent-Foundation --profile "$AWS_PROFILE"
npm run deploy -- NewsAgent-Collector NewsAgent-Publisher --profile "$AWS_PROFILE"
npm run deploy -- NewsAgent-Orchestrator --profile "$AWS_PROFILE"
```

Retain CDK change approval prompts. The custom bootstrap variant prevents
accidental replacement with the standard encryption-managed template. Keep real
CloudFormation outputs private. Runtime ARNs are connected through stack
references rather than copied into public source.

## Validation and cutover

1. Verify all runtimes are READY and the new schedule is disabled.
2. Run an end-to-end preview with publishing disabled. Check S3 data, successful
   create/merge behavior and preservation of existing topics, URLs and dates.
3. Confirm the existing source post is unchanged by the preview.
4. Disable the old schedule and wait for old work and retries to finish.
5. Enable publishing in private configuration and deploy Publisher.
6. Invoke the new scheduler Lambda once and follow its runtime session to completion.
7. Verify the source commit, successful deployment workflow and public page.
8. Enable the new schedule in private configuration and deploy Orchestrator.
9. Verify that exactly the intended schedule is enabled and observe automatic runs.

A Lambda connection timeout is recorded as `submission_uncertain`; it is not
proof of either failure or successful publication. Inspect runtime completion
before retrying. Record actual session IDs and commit evidence only in private notes.

## Rollback and observation

Observe scheduled runs for 24–48 hours before retiring old resources. To roll
back, disable and drain the new deployment first, inspect any published changes,
then resume the old deployment. Preserve valid GitHub content and reconcile any
missed collection window. Do not delete shared resources during cleanup.

Track remaining work in [migration follow-ups](migration-followups.md).
