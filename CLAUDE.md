# News-Agent

Multi-agent news collection and publishing system built on AWS Bedrock AgentCore. Designed as independent microservices — each agent is reusable, independently deployable, and separately evaluable.

## What This Project Does

Collects Norwegian news from RSS feeds every 6 hours, translates/summarizes to Chinese, and publishes to a Hexo blog at https://claw-blog.feng.lu/. Runs 4 times daily via EventBridge.

## Architecture

Three independent AgentCore runtimes, each a standalone subfolder with its own source, infrastructure, and tests:

1. **Collector** (`agents/collector/`) - General-purpose web content collection. Given URLs + config, fetches content, extracts articles, processes them (translate/summarize), writes structured output to S3. Reusable by any agent for any collection task.

2. **Publisher** (`agents/publisher/`) - General-purpose editorial and publishing agent. Formats content into blog posts, rewrites pages, merges new content into existing posts, pushes to Git. Reusable by any agent for any editorial task.

3. **Orchestrator** (`agents/orchestrator/`) - Domain-specific workflow coordinator for Norwegian news. Invokes Collector and Publisher with the right parameters, handles retry, makes run-level decisions. Also owns cross-cutting infrastructure (EventBridge, S3, IAM).

4. **GitHub Action** (in hexo-blog repo) - Triggers on push, runs hexo deploy to GitHub Pages.

Communication: boto3 `invoke_agent_runtime` for control flow. S3 for bulk data passing between agents.
Scheduling: EventBridge (every 6h: 05:00, 11:00, 17:00, 23:00 UTC) -> Lambda -> Orchestrator.
Model: Claude Sonnet 4 via Amazon Bedrock.

See `doc/architecture.md` for full system design.

## Project Structure

```
news-agent/
├── CLAUDE.md                       # This file (project overview)
├── doc/
│   ├── architecture.md             # Full system architecture
│   ├── background.md               # Context: nanoclaw (source) vs AgentCore (target)
│   └── implementation-phases.md    # Phased implementation plan
├── agents/
│   ├── collector/                  # Standalone agent: web content collection
│   │   ├── CLAUDE.md               # Collector agent spec
│   │   ├── src/                    # Source code
│   │   │   ├── agent.py            # System prompt + tool registration
│   │   │   ├── main.py             # AgentCore runtime entrypoint
│   │   │   ├── tools/              # Tool implementations
│   │   │   └── config.py           # Agent configuration
│   │   ├── infra/                  # CDK infrastructure for this agent
│   │   ├── tests/                  # Agent-specific tests
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── publisher/                  # Standalone agent: editorial + publishing
│   │   ├── CLAUDE.md               # Publisher agent spec
│   │   ├── src/
│   │   │   ├── agent.py
│   │   │   ├── main.py
│   │   │   ├── tools/
│   │   │   └── templates/          # Jinja2 post templates
│   │   ├── infra/                  # CDK infrastructure for this agent
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   └── orchestrator/               # Standalone agent: news workflow coordination
│       ├── CLAUDE.md               # Orchestrator agent spec
│       ├── src/
│       │   ├── agent.py
│       │   ├── main.py
│       │   └── config.py           # Norwegian sources, schedule, thresholds
│       ├── infra/                  # CDK infrastructure (agent + cross-cutting: EventBridge, S3, IAM)
│       │   └── lambda/
│       │       └── eventbridge_invoker/
│       ├── tests/
│       ├── Dockerfile
│       └── requirements.txt
└── tests/                          # Integration tests (cross-agent end-to-end)
```

## Agent Design Principles

- **Collector and Publisher are general-purpose**: Their interfaces accept arbitrary tasks. They know nothing about Norwegian news or this specific workflow.
- **Orchestrator is domain-specific**: It encodes the business logic (which feeds, what schedule, what post format).
- **Each agent subfolder is standalone**: Own `src/` for code, `infra/` for CDK, `tests/` for evaluation. Each can be developed, deployed, and evaluated independently.
- **Cross-cutting infra lives in orchestrator**: EventBridge scheduling, shared S3 bucket, and IAM roles are deployed from the orchestrator's `infra/`.
- **Data flows through S3, not LLM context**: Bulk content never passes through the Orchestrator's context window.
- **Deterministic tools for structural work**: Multi-run merge, dedup, renumbering are Python code. LLM only does creative work (translation, summarization, topic consolidation).
- **Topic-based content model**: Multiple articles about the same event → one consolidated topic. Reduces noise, produces richer summaries with multiple sources.

## Key Requirements

- Norwegian news only (domestic, international, business) from 11 RSS feeds
- Runs every 6 hours (4x/day), collecting stories from the last 6h window
- Collector deduplicates by URL AND consolidates related articles into topics (LLM semantic matching)
- Later runs can update existing topics with new info (regenerated summary + changelog note)
- Articles with no new info beyond existing topic are skipped entirely
- Topics translated to Chinese only (~200-word consolidated summaries)
- Daily post accumulates topics across multiple runs
- Publisher generates 300-word day summary covering all topics
- Hexo deploy handled by GitHub Action (not in agent container)
- Blog repo: `claw-lu/hexo-blog`, deployed to GitHub Pages at claw-blog.feng.lu

## Tech Stack

- Python 3.11, Strands Agents SDK
- AgentCore (Container build type)
- CDK (Python) for infrastructure (per-agent, in each agent's `infra/`)
- Libraries: feedparser, trafilatura, httpx, gitpython, jinja2
- AWS: EventBridge, Lambda, S3, Secrets Manager, IAM
- GitHub Actions for hexo deploy

## Development Methodology: Test-Driven Development (TDD)

All implementation MUST follow TDD. No exceptions.

### The Cycle
1. **Write a failing test first** — define the expected behavior before writing any implementation code
2. **Run the test, confirm it fails** — verify the test is actually testing something
3. **Write the minimum implementation** to make the test pass
4. **Run the test, confirm it passes**
5. **Refactor** if needed (tests must still pass)
6. **Repeat** for the next behavior

### Rules
- Never write implementation code without a failing test that demands it
- Tests go in each agent's `tests/` directory (unit) or the root `tests/` directory (integration)
- Use pytest as the test framework
- Mock external dependencies (S3, GitHub API, RSS feeds, LLM calls) in unit tests
- Each tool gets its own test file (e.g., `tests/test_rss_fetcher.py`)
- Test the interface contract (input → output) not internal implementation details

### Test Structure Per Agent
```
agents/collector/tests/
  test_dedup.py              # Dedup source reading + URL extraction
  test_rss_fetcher.py        # RSS parsing + time filtering (src/tools/)
  test_content_extractor.py  # Article extraction + failure handling (src/tools/)
  test_consolidation.py      # Topic grouping + matching + "new info?" judgment
  test_s3_writer.py          # Output format + S3 write (src/tools/)
  test_agent_e2e.py          # Full agent flow with mocked externals

agents/publisher/tests/
  test_formatter.py          # Jinja2 template rendering (src/templates/)
  test_merger.py             # Deterministic merge logic (src/tools/)
  test_git_operations.py     # Git clone/commit/push (src/tools/)
  test_s3_reader.py          # S3 read + parse (src/tools/)
  test_agent_e2e.py          # Full agent flow with mocked externals

agents/orchestrator/tests/
  test_task_config.py        # Correct config building (src/config.py)
  test_workflow.py           # Retry/skip/publish decisions
  test_agent_e2e.py          # Full orchestration with mocked agent calls
```

## Development Commands

```bash
# Local development (per agent)
cd agents/collector && agentcore dev
cd agents/publisher && agentcore dev
cd agents/orchestrator && agentcore dev

# Deploy agent infrastructure
cd agents/collector/infra && cdk deploy
cd agents/publisher/infra && cdk deploy
cd agents/orchestrator/infra && cdk deploy   # includes shared resources

# Run agent-specific tests
cd agents/collector && pytest tests/
cd agents/publisher && pytest tests/
cd agents/orchestrator && pytest tests/

# Run integration tests
pytest tests/
```

## Implementation Status

See `doc/implementation-phases.md` for the phased plan. Implementation has not started yet — project is in architecture/planning stage.
