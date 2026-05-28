# Sensitive Information Audit

This document lists files containing sensitive or environment-specific information that users should review before forking or sharing.

## ✅ Fixed in Production Code

These files have been updated to use environment variables instead of hardcoded values:

- `agents/orchestrator/app/NewsOrchestrator/config.py` - Now uses env vars for ARNs, S3 bucket, blog repo
- `agents/orchestrator/app/NewsOrchestrator/agent.py` - Uses placeholders replaced at runtime
- `agents/publisher/app/NewsPublisher/tools/verify_deploy.py` - Uses BLOG_REPO env var

## ⚠️ Documentation Files (Reference Only - Not Deployed)

These files contain example/documentation references to specific deployments. They are NOT deployed to AWS:

### CLAUDE.md Files (Per-Agent Documentation)
- `CLAUDE.md` (root) - Contains deployment examples
- `agents/collector/CLAUDE.md` - Contains runtime ID examples
- `agents/publisher/CLAUDE.md` - Contains runtime ID examples  
- `agents/orchestrator/CLAUDE.md` - Contains runtime ID examples

### Architecture Documentation
- `doc/architecture.md` - Contains S3 bucket examples
- `doc/background.md` - Contains blog URL references
- `doc/implementation-phases.md` - Contains deployment examples
- `doc/plan-reporting-and-self-correction.md` - Contains S3 bucket examples

### Agent-Specific READMEs
- `agents/collector/README.md` - Contains account ID and runtime ID examples
- `agents/publisher/README.md` - Contains runtime ID and repo examples

## ⚠️ Test Files (Local Development Only)

Test files contain hardcoded values for testing but are NOT deployed:

- `tests/test_a2a_e2e.py` - Integration test with ARNs
- `tests/test_publisher_git_integration.py` - Git integration test with ARNs
- `agents/collector/tests/test_dedup.py` - Uses example repo names
- `agents/publisher/tests/*.py` - Multiple test files with example values

## ⚠️ CDK Configuration Files (Infrastructure as Code)

These files are used for deployment and contain account-specific values:

- `agents/collector/agentcore/aws-targets.json` - Account ID (548129671048)
- `agents/publisher/agentcore/aws-targets.json` - Account ID (548129671048)
- `agents/orchestrator/agentcore/aws-targets.json` - Account ID (548129671048)
- `agents/orchestrator/agentcore/cdk/lib/cdk-stack.ts` - Hardcoded ARNs for IAM policies

**Note**: The `aws-targets.json` files contain the AWS account ID where agents are deployed. Users should update these files with their own account ID before deploying.

## 🔒 Sensitive Information Types Found

| Type | Example Values | Where Found |
|------|----------------|-------------|
| AWS Account ID | `548129671048` | aws-targets.json, CDK stacks, docs |
| Runtime IDs | `newscollector_NewsCollector-EhrHzp4oFi` | Multiple docs and config files |
| S3 Bucket Names | `news-agent-data-548129671048` | Config files, docs |
| GitHub Repo | `claw-lu/hexo-blog` | Test files, docs |
| Blog URLs | `claw-blog.feng.lu` | Documentation files |

## ✅ Security Best Practices Implemented

1. **Production code uses environment variables** - No hardcoded credentials or resource names in deployed code
2. **GitHub tokens via AgentCore Identity** - Not stored in code or .env files
3. **IAM roles for AWS permissions** - No long-lived credentials in code
4. **Configuration externalized** - All deployment-specific values in env vars or aws-targets.json

## 📋 User Action Items

If you're forking this repository:

1. ✅ Update `agents/*/agentcore/aws-targets.json` with your AWS account ID
2. ✅ Create `.env` files from `.env.example` templates with your values
3. ✅ Review `agents/orchestrator/agentcore/cdk/lib/cdk-stack.ts` IAM policies
4. ⚠️ Documentation files can be left as-is (they're examples) or updated for your deployment
5. ⚠️ Test files can be left as-is (they use mocks and don't access real resources)

## 🛡️ What's Safe to Share

- All `.env.example` files - contain only placeholders
- README.md - generalized for reusability
- Source code in `app/` directories - uses environment variables
- Test files - use mocks and example data
- Documentation files - contain examples, not active credentials

## 🚫 What Should NOT Be Shared

- Actual `.env` files with real values
- `aws-targets.json` with your account ID (if privacy is a concern)
- Any files containing real AWS access keys or GitHub tokens
- Deployed runtime IDs (if you want to keep them private)
