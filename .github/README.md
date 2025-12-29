# CI/CD Pipelines

Production-grade CI/CD workflows for automated testing, security scanning, building, and deployment.

## Overview

This directory contains GitHub Actions workflows that automate the entire software delivery pipeline:

1. **Test** - Run pytest with coverage across Python versions
2. **Lint** - Code quality checks (black, ruff, mypy, markdown, YAML, Terraform)
3. **Security** - Comprehensive security scanning (dependencies, code, secrets, containers, IaC)
4. **Build** - Build and push Docker images with scanning
5. **Deploy** - Deploy to Kubernetes with canary deployment support

## Workflows

### test.yml - Testing Pipeline

**Triggers:** Push to main/develop, pull requests, manual

**Jobs:**
- `test` - Run pytest on Python 3.10, 3.11, 3.12
- `test-integration` - Integration tests with Redis
- `test-summary` - Aggregate test results

**Features:**
- Matrix testing across Python versions
- Coverage reporting (Codecov)
- Test result artifacts
- Parallel execution

**Required Secrets:**
- `ANTHROPIC_API_KEY_TEST` - Test API key (lower rate limits)

**Example Run:**
```bash
# Runs automatically on PR
# Or trigger manually:
gh workflow run test.yml
```

---

### lint.yml - Code Quality

**Triggers:** Push, pull requests, manual

**Jobs:**
- `lint` - Black, Ruff, mypy
- `format-check` - Verify code formatting
- `markdown-lint` - Lint markdown files
- `yaml-lint` - Lint YAML configs
- `dockerfile-lint` - Hadolint for Dockerfiles
- `terraform-lint` - Terraform fmt and validate

**Features:**
- Fast feedback on code quality
- Auto-comment on PRs if formatting needed
- SARIF upload for security tab integration

**Example Run:**
```bash
# Fix formatting locally
black code-examples/
ruff check --fix code-examples/

# Run all linters
pre-commit run --all-files
```

---

### security.yml - Security Scanning

**Triggers:** Push, pull requests, daily schedule, manual

**Jobs:**
- `dependency-scan` - pip-audit for vulnerable dependencies
- `code-security` - Bandit for security issues
- `secret-scan` - Gitleaks for leaked secrets
- `codeql` - GitHub CodeQL analysis
- `container-scan` - Trivy for container vulnerabilities
- `terraform-security` - tfsec for Terraform issues
- `kubernetes-security` - Kubesec and Polaris for K8s
- `sbom-generation` - Generate Software Bill of Materials

**Features:**
- Multiple layers of security scanning
- SARIF upload for GitHub Security tab
- Daily scheduled scans
- SBOM artifacts for supply chain security

**Critical Findings:**
- Workflow fails on CRITICAL vulnerabilities
- Creates GitHub Security alerts
- Blocks PRs if secrets detected

**Example Run:**
```bash
# Run locally with Docker
trivy image agent:latest --severity CRITICAL,HIGH

# Scan for secrets
gitleaks detect --source . --verbose
```

---

### build.yml - Docker Build & Push

**Triggers:** Push to main, version tags, manual

**Jobs:**
- `build` - Build multi-arch Docker images
- `scan-image` - Scan built image with Trivy
- `test-image` - Smoke tests on built image
- `build-monitoring` - Build Prometheus/Grafana images
- `build-summary` - Aggregate build results

**Features:**
- Multi-architecture builds (amd64, arm64)
- BuildKit cache for fast builds
- Image attestation and provenance
- SBOM generation
- Automated tagging (semver, sha, latest)

**Image Tags:**
```
ghcr.io/user/repo/agent:main-abc1234
ghcr.io/user/repo/agent:v1.2.3
ghcr.io/user/repo/agent:latest
```

**Required Secrets:**
- `GITHUB_TOKEN` - Automatically provided
- `ANTHROPIC_API_KEY_TEST` - For smoke tests

**Example Run:**
```bash
# Build locally
cd infrastructure/docker
docker build -t agent:test -f Dockerfile ../../code-examples/reference-agent/

# Push to registry
docker tag agent:test ghcr.io/user/repo/agent:test
docker push ghcr.io/user/repo/agent:test
```

---

### deploy.yml - Kubernetes Deployment

**Triggers:** Manual, successful builds on main

**Jobs:**
- `deploy` - Deploy to Kubernetes with Kustomize
- `rollback` - Auto-rollback on failure (production only)
- `canary-deploy` - Canary deployment for production
- `deploy-summary` - Deployment status

**Environments:**
- **dev** - Development environment
- **staging** - Staging environment
- **production** - Production with canary deployment

**Features:**
- Environment-specific deployments
- Automated rollback on failure
- Canary deployment with metrics validation
- Smoke tests post-deployment
- Slack notifications

**Required Secrets:**
- `AWS_ROLE_ARN` - IAM role for EKS access
- `AWS_REGION` - AWS region
- `EKS_CLUSTER_NAME` - Cluster name
- `SLACK_WEBHOOK_URL` - Slack notifications

**Example Run:**
```bash
# Deploy to dev
gh workflow run deploy.yml -f environment=dev

# Deploy specific tag to production
gh workflow run deploy.yml \
  -f environment=production \
  -f image_tag=v1.2.3
```

---

## Pre-commit Hooks

Local checks before commit:

**Install:**
```bash
pip install pre-commit
pre-commit install
```

**Run manually:**
```bash
# All files
pre-commit run --all-files

# Specific hook
pre-commit run black --all-files

# Skip hooks (not recommended)
git commit --no-verify
```

**Hooks:**
- Black (formatting)
- Ruff (linting)
- mypy (type checking)
- Bandit (security)
- YAML/Markdown linting
- Terraform fmt/validate
- Dockerfile linting (hadolint)
- Secret detection
- Git commit message linting

---

## Setup Guide

### 1. Configure Secrets

In GitHub: Settings → Secrets and variables → Actions

**Required:**
```
ANTHROPIC_API_KEY_TEST    # Test API key
AWS_ROLE_ARN              # IAM role for deployments
AWS_REGION                # AWS region (e.g., us-west-2)
EKS_CLUSTER_NAME          # EKS cluster name
```

**Optional:**
```
CODECOV_TOKEN             # Codecov integration
SLACK_WEBHOOK_URL         # Slack notifications
```

### 2. Enable GitHub Container Registry

```bash
# Login
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin

# Test push
docker tag agent:test ghcr.io/USERNAME/repo/agent:test
docker push ghcr.io/USERNAME/repo/agent:test
```

### 3. Configure AWS OIDC

For secure AWS access without long-lived credentials:

```bash
# Create OIDC provider in AWS
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1

# Create IAM role
# See infrastructure/terraform/aws/iam-github-actions.tf
```

### 4. Enable Branch Protection

Settings → Branches → Add rule for `main`:

- [x] Require pull request before merging
- [x] Require status checks to pass
  - [x] test
  - [x] lint
  - [x] security
- [x] Require conversation resolution before merging
- [x] Do not allow bypassing the above settings

---

## Local Development

### Run Tests Locally

```bash
# All tests
cd code-examples/reference-agent
uv run pytest

# With coverage
uv run pytest --cov=. --cov-report=term-missing

# Integration tests
uv run pytest tests/integration/ -v
```

### Lint Locally

```bash
# Format code
black code-examples/

# Lint
ruff check code-examples/

# Type check
mypy code-examples/reference-agent/

# All checks
pre-commit run --all-files
```

### Build Locally

```bash
# Build Docker image
cd infrastructure/docker
docker build -t agent:local -f Dockerfile ../../code-examples/reference-agent/

# Run locally
docker run -it --rm \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  agent:local
```

### Security Scan Locally

```bash
# Scan dependencies
pip-audit

# Scan code
bandit -r code-examples/

# Scan container
trivy image agent:local

# Scan for secrets
gitleaks detect --source . --verbose
```

---

## Troubleshooting

### Workflow Failed

```bash
# View logs
gh run view --log

# Re-run failed jobs
gh run rerun --failed

# Cancel running workflow
gh run cancel
```

### Build Cache Issues

```bash
# Clear GitHub Actions cache
gh cache delete --all

# Or in Docker
docker builder prune --all
```

### Deployment Stuck

```bash
# Check deployment status
kubectl rollout status deployment/agent-deployment -n production-agents

# View events
kubectl get events -n production-agents --sort-by='.lastTimestamp'

# Rollback manually
kubectl rollout undo deployment/agent-deployment -n production-agents
```

### Secret Scanning False Positive

Add to `.gitignore` or `.gitleaksignore`:

```bash
# .gitleaksignore
code-examples/chapter-04-security/test_data/fake_secrets.py
```

---

## Best Practices

### Commit Messages

Follow Conventional Commits:

```
feat: add retry logic to agent
fix: resolve race condition in circuit breaker
docs: update deployment guide
test: add integration tests for Redis
chore: update dependencies
```

### Pull Requests

1. Create feature branch: `git checkout -b feature/add-retry-logic`
2. Make changes and commit
3. Push: `git push origin feature/add-retry-logic`
4. Create PR with description
5. Wait for CI checks ✅
6. Request review
7. Merge after approval

### Deployment Strategy

**Development:**
- Auto-deploy on merge to `develop` branch
- Deploy to `dev` environment
- Run smoke tests

**Staging:**
- Manual deployment from `main`
- Deploy to `staging` environment
- Run full test suite
- Load testing

**Production:**
- Manual deployment with approval
- Canary deployment (10% traffic)
- Monitor metrics for 10 minutes
- Promote if healthy, rollback if not
- Full deployment if canary successful

---

## Metrics and Monitoring

### CI/CD Metrics

Track in GitHub Insights:
- Workflow success rate
- Average run time
- Deployment frequency
- Lead time for changes
- Mean time to recovery

### Deployment Metrics

Monitor in Grafana:
- Deployment duration
- Rollback frequency
- Canary success rate
- Post-deployment error rate

---

## Cost Optimization

### GitHub Actions Minutes

- Use matrix builds efficiently
- Cache dependencies (uv cache, Docker cache)
- Cancel redundant runs (concurrency groups)
- Use self-hosted runners for frequent builds

### Container Registry Storage

- Set image retention policy (90 days)
- Clean up untagged images
- Use layer caching

### AWS Costs

- Use OIDC instead of access keys (no rotation costs)
- Right-size EKS nodes
- Use Spot instances for dev/staging

---

## Next Steps

- Configure Slack notifications
- Set up deployment approvals for production
- Add performance testing workflow
- Configure automated rollbacks
- Set up deployment dashboard

---

## Additional Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [GitHub Container Registry](https://docs.github.com/en/packages)
- [AWS OIDC Setup](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services)
- [Pre-commit Hooks](https://pre-commit.com/)
- [Conventional Commits](https://www.conventionalcommits.org/)
