# Background: Porting from NanoClaw to AgentCore

## What We're Porting

The existing system is a **nanoclaw news-team** (https://github.com/linkcd/nanoclaw/tree/main/groups/news-team) that:
1. Collects Norwegian news daily from RSS feeds
2. Translates and summarizes articles to Chinese
3. Publishes to a Hexo blog at https://claw-blog.feng.lu/

## About NanoClaw (Source System)

NanoClaw (https://github.com/nanocoai/nanoclaw) is a lightweight personal AI assistant platform:
- Runs Claude agents in isolated Linux containers
- Uses Agent Swarms for multi-agent collaboration
- Communication via `SendMessage` (agent-to-agent) and `mcp__nanoclaw__send_message` (coordinator updates)
- Per-session SQLite databases for message passing
- Credential security via OneCLI's Agent Vault

### Current News-Team Architecture

The existing system uses NanoClaw's Agent Swarm pattern with three roles:

```
Coordinator (news-team group)
  |-> TeamCreate spawns:
      |-> News Collector (subagent)
      |-> Publisher (subagent)
```

**Coordinator**:
- Spawns team, sends instructions to Collector
- Monitors progress (mandatory updates every 2-3 minutes)
- Intervenes on stall (3-min threshold for Collector, 2-min for Publisher)
- Reports final URL when done

**News Collector**:
- Reads RSS feeds via `agent-browser` MCP tool
- Parses RSS XML for metadata (title, pubDate, link, category, description)
- Follows article links for full content
- 24h time filter (strict)
- ~200-word summaries per story
- URL validation (must be specific article pages)
- Saves timestamped markdown to `/workspace/shared/news-team/`
- Sends file path to Publisher via `SendMessage`

**Publisher**:
- Reads collected content file
- 300-word overall summary
- Satirical AI commentary for Norwegian posts ("AI吐槽时间")
- Hexo front-matter generation
- Git commit + push to hexo-blog repo
- `hexo clean && hexo generate && hexo deploy`
- Verifies post is live

### Scheduling (Original)
- Norwegian News: 08:00 UTC daily (once per day)
- Middle East News: 10:00 UTC daily (once per day)

### Quality Mechanisms in Current System
- URL quality enforcement (no homepages, no category pages, no liveblogs)
- Strict 24h time window filter
- Content deduplication by URL
- Publisher acts as editorial quality gate
- Progress monitoring with mandatory updates
- Stall detection and recovery protocol (9-min detection, 27-min force restart)
- Multi-run merge (multiple runs/day deduplicate into single post)

### Translation Rules
- **Norwegian news**: Chinese only. Include original names in parentheses for uncommon entities (e.g., "国王哈拉尔五世 (King Harald V)")

### Blog Details
- Repository: `claw-lu/hexo-blog` (public, source markdown on GitHub)
- Post filename pattern: `source/_posts/YYYYMMDD-norway.md`
- Front-matter: title, date, categories, tags
- Deploy target: GitHub Pages at https://claw-blog.feng.lu/ (custom domain)
- Credentials: `GITHUB_BOT_USERNAME`, `GITHUB_BOT_EMAIL`, `GITHUB_BOT_TOKEN`

---

## About AWS Bedrock AgentCore (Target System)

AgentCore is a **framework-agnostic infrastructure platform** for deploying production AI agents at scale. Key capabilities:

### Core Features
- **Managed runtime**: Serverless on AWS Graviton (ARM64), auto-scaling
- **Framework-agnostic**: Bring any framework (Strands, LangChain, custom) with any model provider
- **Build types**: CodeZip (no Docker) or Container
- **Protocols**: HTTP (port 8080), MCP (port 8000), A2A (port 9000)

### Multi-Agent Orchestration (Strands SDK)
- **Graph Pattern**: Deterministic DAG, parallel/sequential nodes, conditional edges, nested graphs
- **Swarm Pattern**: Autonomous agent delegation via `handoff_to_agent` tool
- **Direct Invocation**: boto3 `invoke_agent_runtime` for calling other runtimes

### Evaluation & Optimization
- **Online evaluation**: Continuous monitoring with configurable sampling
- **On-demand evaluation**: Targeted assessment of specific traces
- **Batch evaluation**: Bulk evaluation with ground truth
- **Evaluator types**: Built-in (Helpfulness, Correctness), Custom LLM-as-Judge, Code-based (Lambda)
- **Simulation**: LLM-backed user actors for multi-turn testing
- **Recommendations** (preview): Prompt and tool description optimization
- **Config Bundles** (preview): Versioned configs for A/B testing

### Gateway (Tool Integration)
- Converts APIs into MCP-compatible tools
- Sources: OpenAPI specs, Lambda, Smithy models, remote MCP servers, built-in integrations
- Semantic tool selection across thousands of tools
- Full auth: IAM SigV4, OAuth JWT inbound; API keys, OAuth outbound

### Memory
- Short-term: turn-by-turn within session
- Long-term: extracts insights across sessions
- Multi-agent: shared memory for synchronized context

### CLI Workflow
```bash
agentcore create    # scaffold project
agentcore dev       # local development
agentcore deploy    # CDK-based production deployment
```

---

## What Changed From Source to Target

| Aspect | NanoClaw (Source) | AgentCore (Target) |
|--------|-------------------|-------------------|
| Scope | Norway + Middle East news | Norway only |
| AI commentary | "AI吐槽时间" section | Removed |
| Schedule | Once daily per region | Every 6 hours (4 runs/day) |
| Time filter | Last 24 hours | Last 6 hours |
| Agent design | Tightly coupled to news workflow | Collector + Publisher are general-purpose microservices |
| Hosting | Self-hosted containers | Managed serverless (AWS) |
| Scaling | Single machine | Auto-scaling |
| Evaluation | Manual quality checks | Per-agent evaluation framework |
| Observability | Custom logging | OpenTelemetry built-in |
| Cost model | Always-on containers | Pay-per-invocation |
| Scheduling | NanoClaw's built-in | EventBridge |
| Security | OneCLI Agent Vault | IAM roles, Secrets Manager |
| Inter-agent data | SQLite/file message passing | S3 intermediate storage |
| Dedup | Publisher checks during merge | Collector checks before fetch (self-contained) |
| Hexo deploy | In Publisher agent | GitHub Action (decoupled) |
| Quality gate | 70% story threshold + retry | Any new stories → publish; retry on error only |
| Article extraction | Browser-based (agent-browser MCP) | trafilatura library (browser as future fallback) |

### Key Architectural Evolution

The biggest shift is from **workflow-coupled agents** (nanoclaw's collector/publisher only work for news) to **general-purpose agent microservices**:

- **Collector** can crawl any website, not just news RSS feeds
- **Publisher** can edit/publish any blog content, not just news posts
- **Orchestrator** is the only domain-specific component

This means the same Collector and Publisher can be reused by future workflows (e.g., a tech blog collector, a documentation publisher) without modification.

### Why AgentCore Over NanoClaw

The key motivations:
1. **Evaluation and optimization** — continuously improve translation quality and workflow reliability via AgentCore's per-agent evaluation framework
2. **Learning AgentCore patterns** — multi-agent orchestration via `invoke_agent_runtime`
3. **Microservice architecture** — general-purpose agents reusable across workflows
4. **Managed infrastructure** — no container management, auto-scaling, built-in observability
