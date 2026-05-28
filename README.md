# News Team Agents

Multi-agent news collection and publishing system built on AWS Bedrock AgentCore. Automatically collects news from RSS feeds, translates and summarizes content, and publishes to Git-based blogs (Hexo, Jekyll, etc.).

## Overview

This system demonstrates a microservices-based agent architecture where each agent is:
- **Independent**: Separately deployable and testable
- **Reusable**: General-purpose interfaces for use by other workflows
- **Specialized**: Focused on a single responsibility

The system can be configured to run on any schedule via AWS EventBridge, collecting stories from configurable time windows, consolidating related articles into topics, and publishing summarized content.

## Architecture

Three independent AgentCore runtimes communicate via AWS A2A protocol:

### 1. Collector Agent (`agents/collector/`)
General-purpose web content collection. Given URLs and configuration, fetches content from RSS feeds, extracts articles, processes them (translate/summarize), and writes structured output to S3.

**Key Features:**
- RSS feed parsing with time-window filtering
- Article extraction using trafilatura
- URL-based deduplication
- Topic consolidation via LLM semantic matching
- S3 output for bulk data transfer

### 2. Publisher Agent (`agents/publisher/`)
General-purpose editorial and publishing agent. Formats content into blog posts, rewrites pages, merges new content into existing posts, and pushes to Git.

**Key Features:**
- Jinja2 template-based post formatting
- Deterministic multi-run merge (preserves existing content)
- Git operations (clone, commit, push)
- Daily summary generation (300-word overview)
- Topic-based content organization

### 3. Orchestrator Agent (`agents/orchestrator/`)
Domain-specific workflow coordinator. Invokes Collector and Publisher with the right parameters, handles retry logic, and makes run-level decisions. Can be customized for different news sources and workflows.

**Key Features:**
- A2A protocol client for agent invocation
- EventBridge-triggered execution (fire-and-forget Lambda)
- Cross-cutting infrastructure management
- Run coordination and error handling

### Communication Flow

```
EventBridge (cron) → Lambda → Orchestrator
                                    ↓
                              A2A Protocol
                            ↙              ↘
                    Collector              Publisher
                        ↓                      ↓
                       S3  ←─────────────────→ S3
                                               ↓
                                          Git Push
                                               ↓
                                      GitHub Action (CI/CD deploy)
```

## Tech Stack

- **Runtime**: Python 3.12, AWS Bedrock AgentCore
- **AI Model**: Claude Sonnet 4 (`global.anthropic.claude-sonnet-4-6`)
- **Agent Framework**: Strands Agents SDK with A2A protocol
- **Infrastructure**: AWS CDK (TypeScript), EventBridge, Lambda, S3, IAM
- **Libraries**: feedparser, trafilatura, httpx, gitpython
- **Testing**: pytest with mocked external dependencies
- **Region**: `eu-west-1` (all AWS resources)

## Project Structure

```
news-agent/
├── agents/
│   ├── collector/              # Web content collection agent
│   │   ├── agentcore/          # CLI project config + CDK
│   │   ├── app/NewsCollector/  # Agent source code
│   │   └── tests/              # Unit tests
│   ├── publisher/              # Editorial and publishing agent
│   │   ├── agentcore/          # CLI project config + CDK
│   │   ├── app/NewsPublisher/  # Agent source code
│   │   └── tests/              # Unit tests
│   └── orchestrator/           # Workflow coordination agent
│       ├── agentcore/          # CLI project config + CDK
│       ├── app/NewsOrchestrator/ # Agent source code
│       └── tests/              # Unit tests
├── tests/                      # Integration tests (cross-agent)
├── doc/
│   ├── architecture.md         # Detailed system design
│   ├── background.md           # Migration context
│   └── implementation-phases.md # Development roadmap
└── CLAUDE.md                   # Full project documentation
```

## Development

### Prerequisites

- AWS CLI configured with appropriate credentials
- Python 3.12+
- `agentcore` CLI tool
- `uv` for Python dependency management

### Environment Setup

Each agent requires AWS credentials and optional configuration overrides. Create `.env` files from the provided examples:

```bash
# Root level (optional - shared defaults)
cp .env.example .env

# Per-agent configuration
cp agents/collector/.env.example agents/collector/.env
cp agents/publisher/.env.example agents/publisher/.env
cp agents/orchestrator/.env.example agents/orchestrator/.env
```

**Minimum required environment variables:**

| Variable | Purpose | Required By |
|----------|---------|-------------|
| `AWS_ACCESS_KEY_ID` | AWS authentication | All agents |
| `AWS_SECRET_ACCESS_KEY` | AWS authentication | All agents |
| `AWS_REGION` | AWS region (default: eu-west-1) | All agents |
| `COLLECTOR_RUNTIME_ARN` | Collector agent ARN | Orchestrator only |
| `PUBLISHER_RUNTIME_ARN` | Publisher agent ARN | Orchestrator only |
| `S3_BUCKET` | Data storage bucket | Orchestrator only |
| `BLOG_REPO` | Target Git repository (owner/repo) | Orchestrator, Publisher |
| `MODEL_ID` | Claude model ID (optional) | All agents |

**Notes:**
- AWS credentials can also come from AWS CLI profiles (`AWS_PROFILE`), IAM roles, or instance metadata
- GitHub token is managed by AgentCore Identity and does NOT need to be in `.env`
- The orchestrator requires Collector and Publisher to be deployed first (see deployment section)

### Local Development

Each agent can be developed independently:

```bash
# Start local dev server for an agent
cd agents/collector && agentcore dev
cd agents/publisher && agentcore dev
cd agents/orchestrator && agentcore dev
```

### Testing

The project follows strict Test-Driven Development (TDD):

```bash
# Run agent-specific tests
cd agents/collector && python3 -m pytest tests/ -v
cd agents/publisher && python3 -m pytest tests/ -v
cd agents/orchestrator && python3 -m pytest tests/ -v

# Run integration tests
pytest tests/
```

### Deployment

Agents must be deployed in order (Collector and Publisher first, then Orchestrator):

```bash
# Deploy Collector and Publisher
cd agents/collector && agentcore deploy -y
cd agents/publisher && agentcore deploy -y

# Update runtime ARNs in orchestrator config
# Edit: agents/orchestrator/app/NewsOrchestrator/config.py
# Edit: agents/orchestrator/agentcore/cdk/lib/cdk-stack.ts

# Deploy Orchestrator
cd agents/orchestrator && agentcore deploy -y
```

### Manual Invocation

```bash
cd agents/collector && agentcore invoke '{"task": {...}}' --stream
```

## Design Principles

1. **General-purpose agents**: Collector and Publisher accept arbitrary tasks via their interfaces
2. **Domain-specific coordinator**: Orchestrator encodes the business logic for your specific workflow
3. **Data through S3, not context**: Bulk content never passes through LLM context windows
4. **Deterministic structural work**: Multi-run merge, dedup, and renumbering are Python code
5. **LLM for creative work only**: Translation, summarization, topic consolidation
6. **Topic-based consolidation**: Related articles merged into comprehensive topics with multiple sources

## Observability

All agents include CloudWatch observability:

- **Tracing**: X-Ray integration via CloudWatch delivery pipeline
- **Application Logs**: Structured logs at `/aws/vendedlogs/bedrock-agentcore/runtime/APPLICATION_LOGS/{runtimeId}`
- **Retention**: 14 days
- **CLI Access**: `agentcore traces list`, `agentcore logs --since 1h`

## Documentation

- **CLAUDE.md**: Complete project documentation (architecture, conventions, commands)
- **doc/architecture.md**: Detailed system design and data flows
- **doc/background.md**: Migration context from previous system
- **doc/implementation-phases.md**: Phased development plan

## License

[Add license information]

## Contributing

This project follows strict TDD methodology. All changes must:
1. Start with a failing test
2. Implement minimum code to pass
3. Refactor while keeping tests green
4. Never write implementation without a test that demands it
