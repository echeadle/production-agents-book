# Chapter 9: Deployment Patterns

## Introduction: The Zero-Downtime Challenge

It's Monday morning, and Rachel needs to deploy a critical bug fix to the customer support agent. The fix is ready, tested, and approved. But there's a problem:

**Current deployment process**:
1. Stop the running agent
2. Deploy new version
3. Start the agent
4. **Result**: 5 minutes of downtime, 200 failed customer requests

**Business impact**:
- Lost revenue during downtime
- Frustrated customers
- SLA violations
- Manual deployment process (error-prone)

**What Rachel needs**: Zero-downtime deployment with automatic rollback.

After implementing modern deployment patterns:
- **Downtime**: 0 seconds
- **Deployment time**: 2 minutes (automated)
- **Rollback time**: 30 seconds (automatic)
- **Failed deployments**: Caught by health checks before impacting users

This is the deployment challenge: **Moving from risky, manual deployments to safe, automated, zero-downtime releases.**

---

## Why Deployment Patterns Matter

In production, deployments are your highest-risk operation:

- **Downtime**: Traditional deployments cause service interruption
- **Bugs**: New code can break production
- **Rollback**: Reverting bad deployments must be fast
- **Risk**: Each deployment is a potential incident
- **Frequency**: Modern teams deploy 10-100x per day

**Production reality**: If you can't deploy safely, you can't iterate quickly.

### The Modern Deployment Mindset

**Traditional deployment** (high risk):
- Manual process
- Downtime required
- Deploy all instances at once
- Hope it works
- Slow rollback if it doesn't

**Modern deployment** (low risk):
- Automated process
- Zero downtime
- Gradual rollout
- Automated health checks
- Instant rollback

**Key principle**: Make deployments boring and safe, not exciting and risky.

---

## Containerization with Docker

### Why Containers?

**Problems without containers**:
- "Works on my machine" syndrome
- Dependency conflicts
- Environment inconsistencies
- Difficult to reproduce production locally

**Benefits of containers**:
- **Consistency**: Same environment everywhere (dev, staging, production)
- **Isolation**: Dependencies bundled with application
- **Portability**: Run anywhere (local, cloud, Kubernetes)
- **Reproducibility**: Dockerfile = recipe for exact environment

### Creating a Production Dockerfile

```dockerfile
# code-examples/chapter-09-deployment/docker/Dockerfile

# Multi-stage build for smaller final image
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ============================================
# Final stage (smaller image)
# ============================================
FROM python:3.11-slim

# Create non-root user for security
RUN useradd -m -u 1000 agent && \
    mkdir -p /app && \
    chown -R agent:agent /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Set environment
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=agent:agent . /app/

# Switch to non-root user
USER agent

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health').raise_for_status()"

# Expose port
EXPOSE 8000

# Run application
CMD ["python", "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Best Practices

**1. Multi-stage builds** (smaller images):
```dockerfile
# Build stage: Install dependencies
FROM python:3.11 as builder
RUN pip install ...

# Runtime stage: Only what's needed
FROM python:3.11-slim
COPY --from=builder /opt/venv /opt/venv
```

**2. Non-root user** (security):
```dockerfile
RUN useradd -m agent
USER agent
```

**3. Health checks** (container orchestration):
```dockerfile
HEALTHCHECK CMD curl --fail http://localhost:8000/health || exit 1
```

**4. Layer caching** (faster builds):
```dockerfile
# Copy requirements first (changes less often)
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy code last (changes more often)
COPY . .
```

### Docker Compose for Local Development

```yaml
# code-examples/chapter-09-deployment/docker/docker-compose.yml

version: '3.8'

services:
  # Redis for state and caching
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3

  # API server
  api:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - REDIS_HOST=redis
      - REDIS_PORT=6379
    depends_on:
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 3s
      retries: 3

  # Background workers
  worker:
    build:
      context: .
      dockerfile: Dockerfile
    command: python worker.py
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - REDIS_HOST=redis
      - REDIS_PORT=6379
    depends_on:
      redis:
        condition: service_healthy
    deploy:
      replicas: 3  # Run 3 worker instances

volumes:
  redis-data:

# Usage:
# docker-compose up -d          # Start all services
# docker-compose logs -f worker # View worker logs
# docker-compose scale worker=5 # Scale to 5 workers
# docker-compose down           # Stop all services
```

---

## Kubernetes Orchestration

### Why Kubernetes?

**What Kubernetes provides**:
- **Auto-scaling**: Add/remove instances based on load
- **Self-healing**: Restart failed containers
- **Load balancing**: Distribute traffic across instances
- **Rolling updates**: Deploy without downtime
- **Service discovery**: Components find each other automatically
- **Configuration management**: Secrets and config maps

### Production Kubernetes Deployment

```yaml
# code-examples/chapter-09-deployment/kubernetes/production-deployment.yaml

---
# ConfigMap for application configuration
apiVersion: v1
kind: ConfigMap
metadata:
  name: agent-config
  namespace: production
data:
  REDIS_HOST: "redis-service"
  REDIS_PORT: "6379"
  LOG_LEVEL: "INFO"
  MAX_WORKERS: "20"

---
# Secret for sensitive data
apiVersion: v1
kind: Secret
metadata:
  name: agent-secrets
  namespace: production
type: Opaque
data:
  # Base64 encoded: echo -n 'your-api-key' | base64
  ANTHROPIC_API_KEY: <base64-encoded-key>

---
# Deployment for API servers
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agent-api
  namespace: production
  labels:
    app: agent
    component: api
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1        # Max 1 extra pod during update
      maxUnavailable: 0  # Keep all current pods running
  selector:
    matchLabels:
      app: agent
      component: api
  template:
    metadata:
      labels:
        app: agent
        component: api
        version: v1.0.0
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8000"
        prometheus.io/path: "/metrics"
    spec:
      # Security context
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000

      containers:
      - name: api
        image: agent-api:1.0.0
        imagePullPolicy: IfNotPresent

        ports:
        - name: http
          containerPort: 8000
          protocol: TCP

        # Environment from ConfigMap and Secret
        envFrom:
        - configMapRef:
            name: agent-config
        - secretRef:
            name: agent-secrets

        # Resource limits and requests
        resources:
          requests:
            cpu: "500m"
            memory: "512Mi"
          limits:
            cpu: "2000m"
            memory: "2Gi"

        # Liveness probe (is container alive?)
        livenessProbe:
          httpGet:
            path: /health
            port: http
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 3
          failureThreshold: 3

        # Readiness probe (can container serve traffic?)
        readinessProbe:
          httpGet:
            path: /ready
            port: http
          initialDelaySeconds: 5
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 2

        # Startup probe (for slow-starting containers)
        startupProbe:
          httpGet:
            path: /health
            port: http
          initialDelaySeconds: 0
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 30  # 30 * 5s = 150s max startup time

      # Graceful shutdown
      terminationGracePeriodSeconds: 30

---
# Service for API (load balancer)
apiVersion: v1
kind: Service
metadata:
  name: agent-api-service
  namespace: production
spec:
  type: LoadBalancer
  selector:
    app: agent
    component: api
  ports:
  - name: http
    port: 80
    targetPort: http
    protocol: TCP
  sessionAffinity: None

---
# Horizontal Pod Autoscaler
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: agent-api-hpa
  namespace: production
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: agent-api
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 25
        periodSeconds: 60

---
# Pod Disruption Budget (maintain availability during updates)
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: agent-api-pdb
  namespace: production
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: agent
      component: api
```

### Key Kubernetes Concepts

**1. Deployments**: Manage replicas and rolling updates
**2. Services**: Load balancing and service discovery
**3. ConfigMaps**: Non-sensitive configuration
**4. Secrets**: Sensitive data (API keys, passwords)
**5. HPA**: Auto-scaling based on metrics
**6. PDB**: Maintain availability during disruptions

---

## Blue-Green Deployment

### Concept

**Two identical environments**:
- **Blue**: Current production (v1.0)
- **Green**: New version (v1.1)

**Deployment process**:
1. Deploy v1.1 to Green environment
2. Test Green thoroughly
3. Switch traffic from Blue to Green (instant)
4. Keep Blue running for quick rollback

**Benefits**:
- Zero downtime
- Instant rollback (switch back to Blue)
- Full testing before switchover
- No partial deployments

### Implementation

```yaml
# code-examples/chapter-09-deployment/blue-green/blue-deployment.yaml

---
# Blue deployment (current production)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agent-blue
  namespace: production
spec:
  replicas: 3
  selector:
    matchLabels:
      app: agent
      version: blue
  template:
    metadata:
      labels:
        app: agent
        version: blue
    spec:
      containers:
      - name: api
        image: agent-api:1.0.0  # Current version
        ports:
        - containerPort: 8000

---
# Green deployment (new version)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agent-green
  namespace: production
spec:
  replicas: 3
  selector:
    matchLabels:
      app: agent
      version: green
  template:
    metadata:
      labels:
        app: agent
        version: green
    spec:
      containers:
      - name: api
        image: agent-api:1.1.0  # New version
        ports:
        - containerPort: 8000

---
# Service (controls which version receives traffic)
apiVersion: v1
kind: Service
metadata:
  name: agent-service
  namespace: production
spec:
  selector:
    app: agent
    version: blue  # Currently pointing to blue
  ports:
  - port: 80
    targetPort: 8000
```

**Switching traffic** (blue → green):
```bash
# Deploy green
kubectl apply -f green-deployment.yaml

# Test green directly
kubectl port-forward deployment/agent-green 8080:8000
curl http://localhost:8080/health

# Switch service to green
kubectl patch service agent-service -p '{"spec":{"selector":{"version":"green"}}}'

# Traffic now goes to green (instant switch)

# If issues occur, rollback to blue
kubectl patch service agent-service -p '{"spec":{"selector":{"version":"blue"}}}'

# After validation, delete blue
kubectl delete deployment agent-blue
```

---

## Rolling Updates

### Concept

**Gradual replacement**:
- Update pods one at a time
- Wait for new pod to be ready before updating next
- Always maintain minimum availability

**Process**:
```
Before: [v1] [v1] [v1]
Step 1: [v2] [v1] [v1]  (one pod updated)
Step 2: [v2] [v2] [v1]  (two pods updated)
Step 3: [v2] [v2] [v2]  (all pods updated)
```

**Benefits**:
- Zero downtime
- Automatic rollback on failure
- Resource-efficient (no duplicate environment)

### Implementation

```yaml
# Rolling update is default in Kubernetes
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agent-api
spec:
  replicas: 10
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 2        # Max 2 extra pods during update
      maxUnavailable: 1  # Max 1 pod can be unavailable
  template:
    spec:
      containers:
      - name: api
        image: agent-api:1.1.0  # New version
```

**Deploy with rolling update**:
```bash
# Update image
kubectl set image deployment/agent-api api=agent-api:1.1.0

# Watch rollout
kubectl rollout status deployment/agent-api

# If issues, rollback
kubectl rollout undo deployment/agent-api

# Pause rollout (for manual verification)
kubectl rollout pause deployment/agent-api

# Resume rollout
kubectl rollout resume deployment/agent-api
```

---

## Feature Flags

### Why Feature Flags?

**Problems without feature flags**:
- Deploy code → Feature live immediately
- Can't test in production without exposing to users
- Rollback requires redeployment

**Benefits with feature flags**:
- Deploy code ≠ Enable feature
- Test in production with small % of users
- Instant enable/disable (no deployment)
- A/B testing
- Gradual rollouts

### Implementation

```python
# code-examples/chapter-09-deployment/feature-flags/flags.py

from typing import Optional
import os
import redis
import json


class FeatureFlags:
    """
    Feature flag management.

    Flags stored in Redis for instant updates without deployment.
    """

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    def is_enabled(
        self,
        flag_name: str,
        user_id: Optional[str] = None,
        default: bool = False,
    ) -> bool:
        """
        Check if feature flag is enabled.

        Supports:
        - Global flags (on/off for everyone)
        - User-specific flags
        - Percentage rollouts
        """
        # Get flag configuration
        flag_key = f"flag:{flag_name}"
        flag_data = self.redis.get(flag_key)

        if not flag_data:
            return default

        config = json.loads(flag_data)

        # Check if globally enabled
        if config.get("enabled", False):
            # Check percentage rollout
            if "percentage" in config:
                if user_id:
                    # Consistent hashing for same user
                    user_hash = hash(user_id) % 100
                    if user_hash < config["percentage"]:
                        return True
                    return False

            return True

        # Check user-specific override
        if user_id and user_id in config.get("users", []):
            return True

        return False

    def set_flag(
        self,
        flag_name: str,
        enabled: bool = False,
        percentage: Optional[int] = None,
        users: Optional[list] = None,
    ):
        """Set feature flag configuration."""
        config = {
            "enabled": enabled,
        }

        if percentage is not None:
            config["percentage"] = percentage

        if users:
            config["users"] = users

        flag_key = f"flag:{flag_name}"
        self.redis.set(flag_key, json.dumps(config))


# Usage in agent
class Agent:
    def __init__(self, redis_client):
        self.flags = FeatureFlags(redis_client)

    def chat(self, user_id: str, message: str):
        # Check if new feature is enabled for this user
        if self.flags.is_enabled("use_new_model", user_id=user_id):
            # Use new model
            model = "claude-3-opus-20240229"
        else:
            # Use stable model
            model = "claude-3-5-sonnet-20241022"

        response = self.client.messages.create(
            model=model,
            messages=[{"role": "user", "content": message}]
        )

        return response


# Feature flag management API
from fastapi import FastAPI

app = FastAPI()


@app.post("/flags/{flag_name}/enable")
def enable_flag(flag_name: str, percentage: Optional[int] = None):
    """Enable feature flag."""
    flags = FeatureFlags(redis_client)
    flags.set_flag(flag_name, enabled=True, percentage=percentage)
    return {"flag": flag_name, "enabled": True, "percentage": percentage}


@app.post("/flags/{flag_name}/disable")
def disable_flag(flag_name: str):
    """Disable feature flag."""
    flags = FeatureFlags(redis_client)
    flags.set_flag(flag_name, enabled=False)
    return {"flag": flag_name, "enabled": False}


# Enable new feature for 10% of users
# curl -X POST http://localhost:8000/flags/use_new_model/enable?percentage=10

# Disable feature instantly
# curl -X POST http://localhost:8000/flags/use_new_model/disable
```

### Feature Flag Strategies

**1. Boolean flags** (simple on/off):
```python
if flags.is_enabled("new_feature"):
    use_new_feature()
```

**2. Percentage rollouts** (gradual):
```python
# Enable for 10% of users
flags.set_flag("new_feature", enabled=True, percentage=10)

# Increase to 50%
flags.set_flag("new_feature", enabled=True, percentage=50)

# 100% (full rollout)
flags.set_flag("new_feature", enabled=True, percentage=100)
```

**3. User whitelists** (specific users):
```python
# Enable for beta testers
flags.set_flag("beta_feature", users=["alice", "bob", "charlie"])
```

---

## Configuration Management

### The Twelve-Factor App

**Key principles**:
1. **One codebase**, many deploys
2. **Explicit dependencies**
3. **Config in environment** (not code)
4. **Backing services** as attached resources
5. **Separate build and run**
6. **Stateless processes**
7. **Port binding**
8. **Concurrency** via processes
9. **Disposability** (fast startup/shutdown)
10. **Dev/prod parity**
11. **Logs** as event streams
12. **Admin processes**

### Environment-Based Configuration

```python
# code-examples/chapter-09-deployment/config/settings.py

from pydantic import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """
    Application settings from environment variables.

    Pydantic validates and type-converts automatically.
    """

    # Anthropic API
    anthropic_api_key: str

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: Optional[str] = None

    # Application
    environment: str = "development"  # development, staging, production
    log_level: str = "INFO"
    max_workers: int = 10

    # Performance
    cache_ttl: int = 300
    request_timeout: int = 30

    # Feature flags
    enable_caching: bool = True
    enable_metrics: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = False


# Load settings
settings = Settings()

# Usage
client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
redis_client = redis.Redis(
    host=settings.redis_host,
    port=settings.redis_port,
    password=settings.redis_password,
)
```

### Environment Files

**.env.development**:
```bash
ANTHROPIC_API_KEY=sk-ant-dev-key
REDIS_HOST=localhost
REDIS_PORT=6379
ENVIRONMENT=development
LOG_LEVEL=DEBUG
MAX_WORKERS=2
```

**.env.production**:
```bash
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}  # From secrets manager
REDIS_HOST=redis-cluster.prod.internal
REDIS_PORT=6379
ENVIRONMENT=production
LOG_LEVEL=INFO
MAX_WORKERS=20
ENABLE_METRICS=true
```

### Secrets Management

**DON'T**: Store secrets in code or version control
**DO**: Use secrets managers

```python
# Using AWS Secrets Manager
import boto3
import json

def get_secret(secret_name: str) -> dict:
    """Get secret from AWS Secrets Manager."""
    client = boto3.client('secretsmanager')

    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])


# Get API key from secrets manager
secrets = get_secret("production/agent/api-keys")
api_key = secrets["ANTHROPIC_API_KEY"]

# Initialize client
client = anthropic.Anthropic(api_key=api_key)
```

**In Kubernetes**:
```yaml
# Create secret from AWS Secrets Manager
apiVersion: v1
kind: Secret
metadata:
  name: agent-secrets
type: Opaque
stringData:
  ANTHROPIC_API_KEY: ${SECRET_FROM_AWS}

# Mount as environment variable
spec:
  containers:
  - name: api
    envFrom:
    - secretRef:
        name: agent-secrets
```

---

## Deployment Checklist

Before deploying to production:

### Pre-Deployment
- [ ] All tests passing (unit, integration, load)
- [ ] Code reviewed and approved
- [ ] Security scan completed
- [ ] Dependencies updated
- [ ] Secrets configured in secrets manager
- [ ] Environment variables set
- [ ] Database migrations tested

### Deployment
- [ ] Deploy to staging first
- [ ] Smoke tests on staging
- [ ] Gradual rollout strategy chosen
- [ ] Monitoring dashboards ready
- [ ] Alerts configured
- [ ] Runbook prepared
- [ ] Rollback plan documented

### Post-Deployment
- [ ] Smoke tests on production
- [ ] Monitor error rates
- [ ] Monitor latency
- [ ] Check logs for issues
- [ ] Verify metrics
- [ ] User acceptance testing
- [ ] Update documentation

---

## Key Takeaways

1. **Containerize everything**: Docker ensures consistency
2. **Orchestrate with Kubernetes**: Auto-scaling, self-healing, zero-downtime
3. **Deploy gradually**: Blue-green or rolling updates
4. **Use feature flags**: Decouple deployment from feature enablement
5. **Manage configuration**: Environment variables, not hard-coded
6. **Secure secrets**: Use secrets managers
7. **Automate deployment**: CI/CD pipelines
8. **Always have rollback**: Fast rollback is critical

**Production wisdom**: "The best deployment is the one users don't notice."

---

## Next Chapter Preview

You can now deploy safely. But what happens when things go wrong? In **Chapter 10: Incident Response**, we'll cover:

- On-call procedures
- Incident detection and alerting
- Debugging runaway agents
- Rollback strategies
- Postmortem process
- Runbooks for common issues

Let's prepare for when production breaks!
