# Implementation Phases

Each agent is developed, tested, and deployed as an independent microservice.

## Phase 1: Collector Agent

The Collector is implemented first because it's independently testable with real RSS feeds and requires no other agents.

### Tasks
1. Create project scaffolding (`agents/collector/`, pyproject.toml, Dockerfile)
2. Implement `tools/dedup.py` - read existing URLs from dedup source (GitHub public API, S3 file, or explicit list)
3. Implement `tools/rss_fetcher.py` - feedparser-based RSS parsing with configurable time window
4. Implement `tools/webpage_fetcher.py` - fetch single webpage content
5. Implement `tools/content_extractor.py` - trafilatura-based content extraction (10s timeout, skip on failure)
6. Implement `tools/s3_writer.py` - write collection result JSON to S3
7. Write `agent.py` with system prompt and tool registration (general-purpose: accepts any collection task)
8. Write `main.py` AgentCore runtime entrypoint
9. Write `Dockerfile` and `requirements.txt`
10. Write `agents/collector/tests/` unit tests
11. Test locally with `agentcore dev`

### Verification
- Invoke with a Norway news task config and verify structured output in S3
- Invoke with a generic webpage collection task (non-RSS) and verify it works
- Verify dedup: run twice against same blog post, second run returns 0 new stories
- Verify time filter (6h window)
- Verify failed extractions are skipped silently with count in metadata
- Verify translation quality (Chinese summaries, proper nouns preserved)

---

## Phase 2: Publisher Agent

### Tasks
1. Create project scaffolding (`agents/publisher/`, pyproject.toml, Dockerfile)
2. Implement `tools/s3_reader.py` - read collected content from S3
3. Implement `tools/repo_reader.py` - read file from Git repo (for checking existing posts)
4. Implement `tools/git_operations.py` - clone, pull, commit, push using gitpython
5. Implement `tools/formatter.py` - Jinja2 template rendering for posts
6. Implement `tools/merger.py` - deterministic merge tool (parse existing post, dedup by URL, insert, renumber)
7. Create `templates/norway_daily.md.j2` and `templates/generic_post.md.j2`
8. Write `agent.py` with system prompt (general-purpose: accepts publish_new, merge_update, rewrite, edit tasks)
9. Write `main.py` AgentCore runtime entrypoint
10. Write `Dockerfile` and `requirements.txt`
11. Write `agents/publisher/tests/` unit tests
12. Test locally with mock S3 data

### Verification
- Test `publish_new`: pass mock S3 data, verify correct Hexo markdown + git push
- Test `merge_update`: run with pre-existing post, verify dedup + renumber + new summary
- Test `rewrite`: pass rewrite instructions for an existing page, verify output
- Test `edit`: pass structured edits, verify correct replacements
- Verify front-matter is valid YAML
- Verify day summary covers all stories (not just new batch)
- Verify no hexo-cli/nodejs in container

---

## Phase 2.5: GitHub Action for Hexo Deploy

### Tasks
1. Create `.github/workflows/deploy.yml` in `claw-lu/hexo-blog` repo
2. Trigger: push to `main` with path filter `source/_posts/**`
3. Steps: checkout, setup Node.js, npm install, hexo clean && hexo generate && hexo deploy
4. Configure GitHub Pages deploy token/key

### Verification
- Push a test markdown file to `source/_posts/` and verify deploy triggers
- Verify blog is updated at https://claw-blog.feng.lu/
- Verify the action completes in reasonable time (<3 min)

---

## Phase 3: Orchestrator Agent

### Tasks
1. Create project scaffolding (`agents/orchestrator/`, pyproject.toml, Dockerfile)
2. Write `config.py` - Norwegian sources, blog target, S3 bucket, schedule parameters
3. Implement `tools/invoke_agent.py` - boto3 `invoke_agent_runtime` wrapper with timeout
4. Write `agent.py` with orchestration prompt:
   - Build Collector task config (sources, 6h filter, dedup against blog post, translate to Chinese)
   - Invoke Collector, handle result
   - Build Publisher task config (publish_new or merge_update based on whether post exists)
   - Invoke Publisher, handle result
   - Retry once on Collector error, skip on 0 stories
5. Write `main.py` AgentCore runtime entrypoint
6. Write `Dockerfile` and `requirements.txt`
7. Write `agents/orchestrator/tests/` unit tests
8. Test full pipeline (orchestrator -> collector -> publisher -> GitHub Action)

### Verification
- End-to-end: trigger orchestrator, verify blog post appears at claw-blog.feng.lu
- Test retry logic: simulate collector error, verify single retry
- Test zero-stories case: verify orchestrator does NOT invoke publisher
- Verify correct task configs are passed to each agent
- Verify invocation timeout is enforced (10 min collector, 5 min publisher)
- Verify first-run-of-day vs merge-update decision logic

---

## Phase 4: Infrastructure & Deployment

### Tasks
1. Write CDK stack (`infra/news_agent_stack.py`)
   - 3 AgentCore Runtimes (Container build, Python 3.11)
   - 3 ECR Repositories
   - 1 EventBridge Rule: `cron(0 5,11,17,23 * * ? *)`
   - 1 Lambda function (eventbridge_invoker)
   - 1 S3 Bucket (`news-agent-data`) with 7-day lifecycle expiry
   - IAM roles with least-privilege per agent
   - Secrets Manager secret for GitHub token
2. Write Lambda handler (`infra/lambda/eventbridge_invoker/handler.py`)
   - Emit CloudWatch custom metric `NewsAgent/RunCompleted` with `{status}` dimension
3. Create reusable CDK constructs (`infra/constructs/agent_runtime.py`)
4. Deploy: `cdk bootstrap` + `cdk deploy`
5. Verify first scheduled run

### Verification
- `cdk synth` produces valid CloudFormation
- Successful deployment to target AWS account
- EventBridge rule visible and correct schedule
- Manual trigger of Lambda produces correct orchestrator invocation
- S3 bucket exists with lifecycle policy
- IAM roles are least-privilege (Collector can't read secrets, Publisher can't invoke agents)
- First automated run at 05:00 UTC produces blog post
- CloudWatch metric emitted on success/failure

---

## Phase 5: Evaluation & Observability

Each agent gets its own evaluation config, tested independently.

### Tasks
1. Configure online evaluation (100% sampling) on each runtime separately
2. Collector evaluators:
   - LLM-as-Judge: translation quality (natural Chinese, accuracy, proper nouns)
   - Code-based: URL validity (all URLs return 200)
   - Code-based: time window compliance
   - Code-based: dedup correctness (no overlap with existing post)
3. Publisher evaluators:
   - Code-based: format compliance (valid front-matter, correct structure)
   - LLM-as-Judge: summary quality (covers all stories, coherent)
   - Code-based: merge correctness (no duplicates after merge, sequential numbering)
4. Orchestrator evaluators:
   - Code-based: workflow correctness (right task configs, appropriate decisions)
5. Set up simulation tests with recorded RSS responses
6. Verify AgentCore OpenTelemetry traces show full chain
7. Configure CloudWatch alarm on Lambda metric `status=FAILED`
8. Monitor first 5 production runs, tune prompts as needed

### Verification
- Each agent's evaluators fire independently
- Evaluation scores visible per-agent in AgentCore console
- Simulation tests pass consistently for Collector and Publisher in isolation
- Translation quality scores > 4/5 on LLM-as-Judge
- Full trace visible: Lambda → Orchestrator → Collector → S3 → Publisher → Git
- CloudWatch alarm triggers on simulated failure
