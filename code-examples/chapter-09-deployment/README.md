# Chapter 9: Deployment Patterns - Code Examples

This directory contains production-ready deployment configurations and patterns for AI agent systems.

## Overview

Modern deployment strategies for zero-downtime, safe releases:

1. **docker/** - Containerization with Docker
2. **kubernetes/** - Orchestration and auto-scaling
3. **blue-green/** - Zero-downtime deployments
4. **feature-flags/** - Gradual feature rollouts
5. **config/** - Configuration management

## Deployment Strategies Comparison

| Strategy | Downtime | Rollback Speed | Resource Cost | Complexity |
|----------|----------|----------------|---------------|------------|
| **Traditional** | 5-10 min | Slow (redeploy) | Low | Low |
| **Rolling Update** | 0 min | Medium (automatic) | Low | Medium |
| **Blue-Green** | 0 min | Instant (switch) | High (2x) | Medium |
| **Canary** | 0 min | Instant | Low | High |

## Prerequisites

- Docker
- Kubernetes (minikube for local, or cloud cluster)
- kubectl CLI
- Redis

## Example 1: Docker Containerization

**Location**: `docker/`

**What it provides**:
- Production Dockerfile (multi-stage)
- Docker Compose for local development
- Health checks
- Non-root user security
- Layer caching optimization

**Build and run locally**:
```bash
cd docker

# Build image
docker build -t agent-api:1.0.0 .

# Run single container
docker run -d \
  -p 8000:8000 \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  agent-api:1.0.0

# Or use Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f

# Scale workers
docker-compose up -d --scale worker=5

# Stop all
docker-compose down
```

**Image size optimization**:
```bash
# Before (single-stage): 1.2GB
# After (multi-stage): 350MB
# Savings: 71%
```

## Example 2: Kubernetes Deployment

**Location**: `kubernetes/`

**What it provides**:
- Production-ready deployments
- Services (load balancing)
- ConfigMaps and Secrets
- Horizontal Pod Autoscaler (HPA)
- Pod Disruption Budgets
- Resource limits and requests

**Deploy to Kubernetes**:
```bash
cd kubernetes

# Create namespace
kubectl create namespace production

# Create secrets
kubectl create secret generic agent-secrets \
  --from-literal=ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  -n production

# Deploy all resources
kubectl apply -f production-deployment.yaml

# Check status
kubectl get all -n production

# Watch pods come up
kubectl get pods -n production -w

# View logs
kubectl logs -f deployment/agent-api -n production

# Get service URL
kubectl get service agent-api-service -n production
```

**Auto-scaling in action**:
```bash
# Watch HPA
kubectl get hpa -n production -w

# Generate load (triggers scale-up)
kubectl run -it --rm load-generator --image=busybox -n production -- sh
# while true; do wget -O- http://agent-api-service/chat; done

# Observe pods scaling
# 3 pods → 5 pods → 10 pods (as load increases)

# Stop load (pods scale down after 5 minutes)
```

## Example 3: Blue-Green Deployment

**Location**: `blue-green/`

**What it provides**:
- Blue environment (current production)
- Green environment (new version)
- Instant traffic switching
- Fast rollback capability

**Blue-Green deployment process**:

```bash
cd blue-green

# 1. Current state: Blue is live
kubectl apply -f blue-deployment.yaml

# Service points to blue
kubectl get service agent-service -o yaml | grep version
# version: blue

# 2. Deploy Green (new version)
kubectl apply -f green-deployment.yaml

# Both blue and green running
kubectl get deployments
# agent-blue    3/3     3
# agent-green   3/3     3

# 3. Test Green directly
kubectl port-forward deployment/agent-green 8080:8000
curl http://localhost:8080/health

# 4. Switch traffic to Green (instant!)
kubectl patch service agent-service -p '{
  "spec": {
    "selector": {
      "version": "green"
    }
  }
}'

# Traffic now goes to green
# Blue still running (for rollback)

# 5. Monitor for issues
kubectl logs -f deployment/agent-green

# 6a. If healthy: delete blue
kubectl delete deployment agent-blue

# 6b. If issues: rollback to blue (instant!)
kubectl patch service agent-service -p '{
  "spec": {
    "selector": {
      "version": "blue"
    }
  }
}'
```

**Benefits**:
- **Instant switchover**: 0 downtime
- **Instant rollback**: 30 seconds
- **Full testing**: Test green before switching
- **Safe**: Blue available for quick revert

**Trade-off**: 2x resources during deployment

## Example 4: Rolling Updates

**Rolling updates are default** in Kubernetes. No special configuration needed!

```bash
# Update to new version (rolling update automatically)
kubectl set image deployment/agent-api \
  api=agent-api:1.1.0 \
  -n production

# Watch rollout
kubectl rollout status deployment/agent-api -n production

# Rollout process:
# [v1.0] [v1.0] [v1.0]
# [v1.1] [v1.0] [v1.0]  (one pod updated)
# [v1.1] [v1.1] [v1.0]  (two pods updated)
# [v1.1] [v1.1] [v1.1]  (all pods updated)

# If issues detected, rollback
kubectl rollout undo deployment/agent-api -n production

# Pause rollout (for manual verification)
kubectl rollout pause deployment/agent-api -n production

# Resume after verification
kubectl rollout resume deployment/agent-api -n production
```

**Configuration**:
```yaml
spec:
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1        # Max 1 extra pod during update
      maxUnavailable: 0  # Keep all current pods running
```

**Benefits**:
- Zero downtime
- Automatic rollback on failure
- Resource-efficient (no 2x cost)

## Example 5: Feature Flags

**Location**: `feature-flags/`

**What it provides**:
- Redis-backed feature flags
- Percentage rollouts
- User-specific flags
- Instant enable/disable (no deployment)

**Using feature flags**:

```python
from flags import FeatureFlags

flags = FeatureFlags(redis_client)

# Enable for 10% of users
flags.set_flag("new_model", enabled=True, percentage=10)

# Check if enabled for user
if flags.is_enabled("new_model", user_id="user123"):
    model = "claude-3-opus-20240229"  # New model
else:
    model = "claude-3-5-sonnet-20241022"  # Current model
```

**Gradual rollout**:
```bash
# Day 1: Enable for 10% of users
curl -X POST http://localhost:8000/flags/new_model/enable?percentage=10

# Day 2: If healthy, increase to 50%
curl -X POST http://localhost:8000/flags/new_model/enable?percentage=50

# Day 3: Full rollout (100%)
curl -X POST http://localhost:8000/flags/new_model/enable?percentage=100

# If issues at any point: instant disable
curl -X POST http://localhost:8000/flags/new_model/disable
```

**Benefits**:
- Deploy code ≠ Enable feature
- Test in production safely
- Instant rollback (no redeploy)
- A/B testing capability

## Example 6: Configuration Management

**Location**: `config/`

**What it provides**:
- Environment-based configuration
- Type-safe settings with Pydantic
- Secrets from environment variables
- Different configs for dev/staging/prod

**Configuration structure**:

```python
# settings.py
class Settings(BaseSettings):
    anthropic_api_key: str
    redis_host: str = "localhost"
    environment: str = "development"
    log_level: str = "INFO"

    class Config:
        env_file = ".env"

# Load settings
settings = Settings()
```

**Environment files**:

```bash
# .env.development
ENVIRONMENT=development
LOG_LEVEL=DEBUG
REDIS_HOST=localhost

# .env.production
ENVIRONMENT=production
LOG_LEVEL=INFO
REDIS_HOST=redis-cluster.prod.internal
```

**Usage**:
```bash
# Development
export ENV_FILE=.env.development
python app.py

# Production
export ENV_FILE=.env.production
python app.py
```

## Deployment Workflow

### 1. Local Development

```bash
# Use Docker Compose
docker-compose up -d

# Develop and test locally
# Changes reflected immediately (volume mount)
```

### 2. Build and Push

```bash
# Build Docker image
docker build -t agent-api:1.1.0 .

# Tag for registry
docker tag agent-api:1.1.0 your-registry.com/agent-api:1.1.0

# Push to registry
docker push your-registry.com/agent-api:1.1.0
```

### 3. Deploy to Staging

```bash
# Update staging deployment
kubectl set image deployment/agent-api \
  api=your-registry.com/agent-api:1.1.0 \
  -n staging

# Run smoke tests
python smoke_test.py https://staging.agent.com

# Run load tests
locust -f locustfile.py --host=https://staging.agent.com \
  --users 1000 --spawn-rate 50 --run-time 10m --headless
```

### 4. Deploy to Production

**Option A: Blue-Green**
```bash
# Deploy green
kubectl apply -f blue-green/green-deployment.yaml

# Test green
kubectl port-forward deployment/agent-green 8080:8000

# Switch traffic
kubectl patch service agent-service -p '{"spec":{"selector":{"version":"green"}}}'

# Monitor for 10 minutes

# If healthy: delete blue
# If issues: switch back to blue
```

**Option B: Rolling Update**
```bash
# Rolling update (gradual)
kubectl set image deployment/agent-api \
  api=your-registry.com/agent-api:1.1.0 \
  -n production

# Watch rollout
kubectl rollout status deployment/agent-api -n production

# If issues: rollback
kubectl rollout undo deployment/agent-api -n production
```

**Option C: Canary**
```bash
# Deploy canary (see Chapter 8)
kubectl apply -f canary/deployment.yaml

# Monitor metrics for 10 minutes

# If healthy: promote
# If issues: rollback
```

### 5. Post-Deployment

```bash
# Smoke tests
python smoke_test.py https://agent.production.com

# Monitor dashboards
# - Error rate
# - Latency (p50, p95, p99)
# - Throughput

# Check logs for errors
kubectl logs -f deployment/agent-api -n production --tail=100

# Verify metrics
curl https://agent.production.com/metrics
```

## CI/CD Pipeline Example

**GitHub Actions**:
```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Build Docker image
        run: docker build -t agent-api:${{ github.sha }} .

      - name: Push to registry
        run: |
          docker tag agent-api:${{ github.sha }} \
            ${{ secrets.REGISTRY }}/agent-api:${{ github.sha }}
          docker push ${{ secrets.REGISTRY }}/agent-api:${{ github.sha }}

  deploy-staging:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to staging
        run: |
          kubectl set image deployment/agent-api \
            api=${{ secrets.REGISTRY }}/agent-api:${{ github.sha }} \
            -n staging

      - name: Smoke tests
        run: python smoke_test.py ${{ secrets.STAGING_URL }}

  deploy-production:
    needs: deploy-staging
    runs-on: ubuntu-latest
    environment: production
    steps:
      - name: Deploy to production (rolling update)
        run: |
          kubectl set image deployment/agent-api \
            api=${{ secrets.REGISTRY }}/agent-api:${{ github.sha }} \
            -n production

      - name: Wait for rollout
        run: kubectl rollout status deployment/agent-api -n production

      - name: Smoke tests
        run: python smoke_test.py ${{ secrets.PROD_URL }}

      - name: Rollback on failure
        if: failure()
        run: kubectl rollout undo deployment/agent-api -n production
```

## Monitoring Deployments

### Key Metrics

```python
from prometheus_client import Counter, Histogram, Gauge

# Deployment events
deployments_total = Counter(
    "agent_deployments_total",
    "Total deployments",
    ["environment", "status"]  # success/failure
)

# Deployment duration
deployment_duration = Histogram(
    "agent_deployment_duration_seconds",
    "Deployment duration",
    buckets=[30, 60, 120, 300, 600]
)

# Current version
current_version = Gauge(
    "agent_version_info",
    "Current version",
    ["version", "environment"]
)
```

### Grafana Dashboards

**Deployment dashboard**:
- Deployments per day
- Deployment success rate
- Average deployment time
- Rollback frequency

**Health dashboard**:
- Error rate (before/after deployment)
- Latency (before/after deployment)
- Throughput (before/after deployment)

## Troubleshooting

### Deployment stuck

**Problem**: Rollout not progressing

**Check**:
```bash
kubectl rollout status deployment/agent-api
kubectl describe deployment agent-api
kubectl get pods  # Look for ImagePullBackOff, CrashLoopBackOff
kubectl logs deployment/agent-api
```

**Common causes**:
- Image pull errors (check registry access)
- Health check failures
- Resource limits too low
- Configuration errors

### Rollback needed

**Problem**: New version causing issues

**Quick rollback**:
```bash
# Rolling update: undo
kubectl rollout undo deployment/agent-api

# Blue-green: switch back
kubectl patch service agent-service -p '{"spec":{"selector":{"version":"blue"}}}'
```

### Configuration issues

**Problem**: App not reading config

**Check**:
```bash
# View ConfigMap
kubectl get configmap agent-config -o yaml

# View Secret (base64 encoded)
kubectl get secret agent-secrets -o yaml

# Check pod environment
kubectl exec deployment/agent-api -- env | grep ANTHROPIC
```

## Production Deployment Checklist

Before deploying:

- [ ] All tests passing
- [ ] Code reviewed
- [ ] Security scan passed
- [ ] Secrets configured
- [ ] ConfigMaps updated
- [ ] Resource limits set
- [ ] Health checks configured
- [ ] Monitoring dashboards ready
- [ ] Alerts configured
- [ ] Rollback plan documented
- [ ] On-call engineer notified

## Best Practices

1. **Always test in staging first**
2. **Use gradual rollouts** (canary or rolling)
3. **Have instant rollback** capability
4. **Monitor deployments** closely
5. **Automate everything** (CI/CD)
6. **Keep deployments small** (frequent, incremental)
7. **Deploy during low-traffic** periods (when possible)
8. **Document rollback procedures**

## Resources

- [Docker best practices](https://docs.docker.com/develop/dev-best-practices/)
- [Kubernetes deployments](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)
- [The Twelve-Factor App](https://12factor.net/)
- [Feature Flags](https://martinfowler.com/articles/feature-toggles.html)

## Next Steps

1. Containerize your agent
2. Deploy to Kubernetes
3. Set up CI/CD pipeline
4. Implement feature flags
5. Practice rollbacks
6. Move to Chapter 10 (Incident Response)

**Remember**: The best deployment is the one users don't notice!
