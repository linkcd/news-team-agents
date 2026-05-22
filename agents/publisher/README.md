# NewsPublisher Agent

General-purpose editorial and publishing agent built on AWS Bedrock AgentCore. Formats content into blog posts, merges new content into existing posts, and pushes to Git repositories.

## Architecture

```
AgentCore Runtime (Container, Python 3.12, eu-west-1)
  ├── Tools
  │   ├── read_from_s3        — Read collected content from S3
  │   ├── read_repo_file      — Read files from public GitHub repos
  │   ├── format_post         — Render Jinja2 templates to markdown
  │   ├── merge_posts         — Deterministic merge into existing posts
  │   ├── git_clone           — Clone repo (auth via AgentCore Identity)
  │   └── git_commit_and_push — Write, commit, push to origin
  └── Templates
      ├── norway_daily.md.j2  — Norwegian daily news post
      └── generic_post.md.j2  — Generic blog post
```

**Model:** Claude Sonnet 4 via Bedrock (`global.anthropic.claude-sonnet-4-6`)

## Task Types

| Type | Description |
|------|-------------|
| `publish_new` | Create a new blog post from collected content |
| `merge_update` | Merge new/updated items into an existing post |
| `rewrite` | Free-form rewrite of an existing page |
| `edit` | Apply structured edits to an existing page |

## Prerequisites

- AWS CLI configured with credentials for account `548129671048`
- Node.js 18+ (for CDK)
- Python 3.11+ (for tests)
- [agentcore CLI](https://docs.hub.amazon.dev/agentcore/) installed globally
- [uv](https://docs.astral.sh/uv/) installed (for Python dependency management)
- S3 bucket `news-agent-data-548129671048` exists in `eu-west-1`

## Project Structure

```
agents/publisher/
├── agentcore/
│   ├── agentcore.json        # Runtime + credential definitions
│   ├── aws-targets.json      # Deployment target (account, region)
│   └── cdk/                  # CDK stack (TypeScript)
│       ├── lib/cdk-stack.ts  # IAM permissions, runtime config
│       ├── bin/cdk.ts        # CDK app entrypoint
│       └── package.json      # CDK dependencies
├── app/NewsPublisher/
│   ├── main.py               # AgentCore runtime entrypoint
│   ├── agent.py              # System prompt + tool registration
│   ├── config.py             # MODEL_ID constant
│   ├── tools/                # @tool implementations
│   │   ├── s3_reader.py
│   │   ├── repo_reader.py
│   │   ├── formatter.py
│   │   ├── merger.py
│   │   ├── git_ops.py
│   │   └── templates/        # Jinja2 templates
│   ├── Dockerfile            # Container image (python:3.12-slim + git)
│   ├── pyproject.toml        # Python dependencies
│   └── uv.lock              # Locked dependencies
└── tests/                    # Unit + integration tests
```

## Deployment

### 1. Install CDK dependencies

```bash
cd agentcore/cdk
npm install --legacy-peer-deps
cd ../..
```

### 2. Deploy the stack

```bash
agentcore deploy -y
```

This deploys:
- AgentCore Runtime (container image via CodeBuild)
- IAM execution role with permissions for:
  - `bedrock:InvokeModel` (LLM calls)
  - `s3:GetObject` on `news-agent-data-548129671048/*`
  - `bedrock-agentcore:GetApiKeyCredential` (AgentCore Identity)
- ApiKeyCredentialProvider `github-token` (AgentCore Identity)

### 3. Store the GitHub token

Generate a GitHub Personal Access Token (fine-grained):

1. Go to https://github.com/settings/tokens?type=beta
2. Click **Generate new token**
3. Set **Token name** (e.g., `news-agent-publisher`)
4. Set **Expiration** (recommended: 90 days)
5. Under **Repository access**, select **Only select repositories** → `claw-lu/hexo-blog`
6. Under **Permissions → Repository permissions**, grant:
   - **Contents**: Read and write (for git push)
   - **Metadata**: Read-only (required by default)
7. Click **Generate token** and copy the value

Then store it as an AgentCore Identity credential:

```bash
agentcore add credential --name github-token --api-key <GITHUB_PAT>
```

### 4. Verify deployment

```bash
agentcore status
```

Expected: `NewsPublisher: Deployed - Runtime: READY`

## Invocation

```bash
# publish_new — create a new post from S3 data
agentcore invoke '{
  "task": {
    "task_id": "publish-norway-2026-05-21",
    "type": "publish_new",
    "source": {
      "type": "s3",
      "bucket": "news-agent-data-548129671048",
      "key": "collections/2026-05-21/0500-norway-news.json"
    },
    "template": "norway_daily",
    "output": {
      "repo": "claw-lu/hexo-blog",
      "branch": "main",
      "file_path": "source/_posts/20260521-norway.md",
      "commit_message": "Add Norway news 2026-05-21"
    },
    "editorial": {
      "generate_summary": true,
      "summary_word_count": 300,
      "summary_scope": "all_items"
    }
  }
}' --stream

# merge_update — merge new items into existing post
agentcore invoke '{
  "task": {
    "task_id": "merge-norway-2026-05-21-1100",
    "type": "merge_update",
    "source": {
      "type": "s3",
      "bucket": "news-agent-data-548129671048",
      "key": "collections/2026-05-21/1100-norway-news.json"
    },
    "target": {
      "repo": "claw-lu/hexo-blog",
      "branch": "main",
      "file_path": "source/_posts/20260521-norway.md"
    },
    "merge_strategy": {
      "new_items": "append_per_section",
      "updated_items": "replace_summary_and_add_source",
      "renumber": true,
      "regenerate_day_summary": true
    },
    "editorial": {
      "generate_summary": true,
      "summary_word_count": 300,
      "summary_scope": "all_items"
    }
  }
}' --stream
```

## Local Development

### Run tests

```bash
python3 -m pytest tests/ -v
```

### Run locally (requires AWS credentials)

```bash
agentcore dev
```

### Update dependencies

```bash
cd app/NewsPublisher
# Edit pyproject.toml, then:
uv lock
```

## IAM Permissions (managed by CDK)

| Permission | Resource | Purpose |
|-----------|----------|---------|
| `bedrock:InvokeModel` | `arn:aws:bedrock:*:548129671048:inference-profile/*` | LLM calls |
| `s3:GetObject` | `arn:aws:s3:::news-agent-data-548129671048/*` | Read collected content |
| `bedrock-agentcore:GetApiKeyCredential` | `arn:*:bedrock-agentcore:*:548129671048:apikeycredentialprovider/*` | Retrieve GitHub token |
| `bedrock-agentcore:GetWorkloadAccessTokenForUserId` | `arn:*:bedrock-agentcore:*:548129671048:workload-identity-directory/*` | Identity token for credential retrieval |

## Deployed Resources

| Resource | Value |
|----------|-------|
| Runtime ID | `newspublisher_NewsPublisher-OZnqGfD4D2` |
| Region | `eu-west-1` |
| Account | `548129671048` |
| Stack | `AgentCore-newspublisher-default` |
| Credential | `github-token` (ApiKeyCredentialProvider) |

## Troubleshooting

**"Bad git executable" error in logs:**
The Dockerfile must include `apt-get install git`. This is already configured.

**S3 access denied:**
Verify the CDK stack's `addToPolicy` statement matches the bucket name. Redeploy with `agentcore deploy -y`.

**Credential not found:**
Run `agentcore add credential --name github-token --api-key <PAT>` to store the token value.

**"Workload access token has not been set":**
Callers must pass `runtimeUserId` when invoking via `invoke_agent_runtime`. This is required for AgentCore Identity to issue a workload token for credential retrieval. Example:
```python
client.invoke_agent_runtime(
    agentRuntimeArn=PUBLISHER_ARN,
    runtimeSessionId=session_id,
    runtimeUserId="orchestrator",  # Required for AgentCore Identity
    payload=json.dumps(payload),
)
```

**"Write access to repository not granted" (HTTP 403):**
The GitHub PAT stored in the credential doesn't have write access to the target repo. Fine-grained tokens targeting a different account require approval from the resource owner (Settings → Personal access tokens → Pending requests).

**View runtime logs:**
```bash
agentcore logs --follow
```
