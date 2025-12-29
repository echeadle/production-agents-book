# Chapter 12: Building an Agent Platform

## The Incident: When One Tenant Broke Everyone

**Date**: March 2024
**Company**: SaasBot (fictional, composite of real incidents)
**Impact**: Complete platform outage, 847 customers affected
**Duration**: 2.3 hours
**Root Cause**: No resource isolation between tenants

---

At 2:47 AM, SaasBot's platform went dark. All 847 customers—from solo developers to enterprise teams—couldn't access their AI agents. The on-call engineer's phone erupted with alerts:

```
🚨 CRITICAL: Platform API - 100% Error Rate
🚨 CRITICAL: Database Connection Pool Exhausted
🚨 CRITICAL: Redis Memory at 100%
🚨 WARNING: 847 customers affected
```

The diagnosis came quickly: **One customer's runaway agent was consuming all platform resources.**

A well-intentioned developer had deployed a recursive agent that accidentally created an infinite loop. Instead of processing 100 requests, it spawned 100,000 requests in 10 minutes. The platform had no:

- **Resource quotas** (the agent consumed unlimited CPU/memory)
- **Rate limiting** (unlimited requests per tenant)
- **Circuit breakers** (runaway agent kept running)
- **Tenant isolation** (one tenant's spike affected everyone)

The fix was brutal: **kill all agents and restart the platform.** Every customer experienced downtime because the platform lacked proper multi-tenancy.

**This chapter teaches you how to build an agent platform that isolates tenants, enforces quotas, and provides a great developer experience—without letting one bad actor take down everyone else.**

---

## What Is an Agent Platform?

An **agent platform** is infrastructure that allows multiple teams or customers (tenants) to deploy and run AI agents without building their own production infrastructure.

### Single Agent vs. Platform

| **Single Agent** | **Agent Platform** |
|------------------|-------------------|
| One team, one agent | Many teams, many agents |
| Dedicated infrastructure | Shared infrastructure |
| No resource quotas needed | Must enforce quotas |
| Simple billing | Complex cost allocation |
| Tight coupling OK | Must support extensibility |

### Examples of Agent Platforms

**Internal Platforms** (multiple teams in one company):
- Engineering teams deploy customer support agents
- Sales teams deploy lead qualification agents
- Marketing teams deploy content generation agents

**External Platforms** (SaaS for customers):
- Zapier AI Actions (agents for workflows)
- LangChain Cloud (hosted agent deployments)
- Retool AI (agents in internal tools)

### Why Build a Platform?

**For Internal Teams**:
- Avoid duplicating infrastructure across teams
- Centralize observability and security
- Share best practices and patterns
- Simplify compliance (one audit, all teams compliant)

**For External Customers**:
- Revenue opportunity (SaaS business model)
- Lower barrier to entry for customers
- Control agent quality and safety
- Scale infrastructure efficiently

---

## Platform Architecture

### High-Level Architecture

```
┌──────────────────────────────────────────────────────────┐
│                     API Gateway                          │
│  (Authentication, Rate Limiting, Routing)                │
└────────────────┬──────────────────────────┬──────────────┘
                 │                          │
    ┌────────────▼─────────┐   ┌───────────▼──────────┐
    │   Agent Runtime      │   │  Platform Services   │
    │  (Multi-Tenant)      │   │  - Billing           │
    │  - Tenant A agents   │   │  - Monitoring        │
    │  - Tenant B agents   │   │  - Quota Management  │
    │  - Tenant C agents   │   │  - Audit Logging     │
    └────────────┬─────────┘   └──────────────────────┘
                 │
    ┌────────────▼─────────────────────────────────────┐
    │         Data Layer (Isolated by Tenant)          │
    │  - PostgreSQL (row-level security)               │
    │  - Redis (namespace per tenant)                  │
    │  - S3 (bucket per tenant or prefix isolation)    │
    └──────────────────────────────────────────────────┘
```

### Core Components

1. **API Gateway**: Authentication, rate limiting, routing to agents
2. **Agent Runtime**: Executes agents with resource isolation
3. **Platform Services**: Billing, monitoring, quota enforcement
4. **Data Layer**: Tenant-isolated storage (database, cache, files)

---

## Multi-Tenancy Patterns

### Pattern 1: Pool Model (Shared Infrastructure)

**Architecture**: All tenants share the same infrastructure (pods, database, Redis).

```python
# agent_runtime.py
class MultiTenantRuntime:
    """Shared runtime with logical isolation."""

    def __init__(self, db: Database, redis: Redis):
        self.db = db
        self.redis = redis
        self.resource_manager = ResourceManager()

    async def execute_agent(
        self,
        tenant_id: str,
        agent_id: str,
        user_message: str
    ) -> AgentResponse:
        # 1. Enforce resource quota
        quota = await self.resource_manager.check_quota(tenant_id)
        if quota.exceeded:
            raise QuotaExceededError(f"Tenant {tenant_id} quota exceeded")

        # 2. Load tenant-specific data (isolated by tenant_id)
        conversation = await self.db.get_conversation(
            tenant_id=tenant_id,
            agent_id=agent_id
        )

        # 3. Use tenant-namespaced cache
        cache_key = f"{tenant_id}:{agent_id}:cache"
        cached = await self.redis.get(cache_key)

        # 4. Execute agent with resource limits
        with self.resource_manager.enforce_limits(tenant_id):
            response = await self._run_agent(
                tenant_id, agent_id, user_message, conversation
            )

        # 5. Track usage for billing
        await self.resource_manager.record_usage(
            tenant_id=tenant_id,
            tokens=response.usage.total_tokens,
            cost=response.cost
        )

        return response
```

**Pros**:
- Cost-efficient (shared resources)
- Simple to deploy (one set of infrastructure)
- Easy to scale (auto-scaling applies to all tenants)

**Cons**:
- "Noisy neighbor" problem (one tenant can affect others)
- Complex isolation logic required
- Security risk if isolation fails

**When to Use**: Early-stage platforms, internal platforms, cost-sensitive scenarios.

---

### Pattern 2: Silo Model (Dedicated Infrastructure)

**Architecture**: Each tenant gets dedicated infrastructure (separate pods, database, Redis).

```yaml
# tenant-a-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agent-runtime-tenant-a
  namespace: tenant-a
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: agent-runtime
        image: agent-runtime:1.0.0
        env:
        - name: TENANT_ID
          value: "tenant-a"
        - name: DATABASE_URL
          value: "postgresql://tenant-a-db/agents"
        - name: REDIS_URL
          value: "redis://tenant-a-redis:6379"
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
```

**Pros**:
- Perfect isolation (one tenant's issues don't affect others)
- Simpler security model (physical separation)
- Easier compliance (dedicated environments)

**Cons**:
- Expensive (duplicate infrastructure per tenant)
- Complex to manage (many deployments)
- Resource inefficiency (idle resources per tenant)

**When to Use**: Enterprise customers, regulated industries, high-security requirements.

---

### Pattern 3: Hybrid Model (Best of Both Worlds)

**Architecture**: Pool model for small tenants, silo model for large tenants.

```python
class HybridRuntime:
    """Routes to pool or silo based on tenant tier."""

    def __init__(self):
        self.pool_runtime = PoolRuntime()  # Shared
        self.silo_runtimes = {}  # Dedicated per enterprise tenant

    async def execute_agent(
        self,
        tenant_id: str,
        agent_id: str,
        user_message: str
    ) -> AgentResponse:
        tenant = await self.get_tenant(tenant_id)

        if tenant.tier == TenantTier.ENTERPRISE:
            # Route to dedicated silo
            runtime = self.silo_runtimes[tenant_id]
        else:
            # Route to shared pool
            runtime = self.pool_runtime

        return await runtime.execute_agent(
            tenant_id, agent_id, user_message
        )
```

**Pros**:
- Cost-efficient for small tenants (shared pool)
- Excellent isolation for large tenants (dedicated silos)
- Flexible business model (tiered pricing)

**Cons**:
- Most complex to implement
- Two codebases to maintain (pool + silo)

**When to Use**: Mature platforms with both small and large customers.

---

## Resource Quotas and Enforcement

### Quota Types

| **Quota Type** | **Description** | **Example** |
|----------------|-----------------|-------------|
| **Request Rate** | Max requests per time window | 1,000 req/hour |
| **Token Usage** | Max tokens per month | 1M tokens/month |
| **Spend Budget** | Max $ spend per month | $500/month |
| **Concurrent Agents** | Max running agents | 10 concurrent |
| **Storage** | Max conversation history | 100MB |

### Quota Enforcement Implementation

```python
# quota_manager.py
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
import structlog

logger = structlog.get_logger()

@dataclass
class Quota:
    """Tenant resource quota."""
    tenant_id: str
    max_requests_per_hour: int
    max_tokens_per_month: int
    max_spend_per_month: float
    max_concurrent_agents: int
    max_storage_mb: int

@dataclass
class Usage:
    """Current tenant usage."""
    requests_this_hour: int
    tokens_this_month: int
    spend_this_month: float
    concurrent_agents: int
    storage_mb: float

class QuotaManager:
    """Enforces resource quotas across tenants."""

    def __init__(self, db: Database, redis: Redis):
        self.db = db
        self.redis = redis

    async def check_quota(
        self,
        tenant_id: str,
        operation: str
    ) -> tuple[bool, Optional[str]]:
        """
        Check if tenant can perform operation.

        Returns:
            (allowed: bool, reason: Optional[str])
        """
        quota = await self.get_quota(tenant_id)
        usage = await self.get_usage(tenant_id)

        # Check request rate
        if usage.requests_this_hour >= quota.max_requests_per_hour:
            logger.warning(
                "quota_exceeded",
                tenant_id=tenant_id,
                quota_type="request_rate",
                limit=quota.max_requests_per_hour,
                current=usage.requests_this_hour
            )
            return False, f"Request rate limit exceeded ({quota.max_requests_per_hour}/hour)"

        # Check token quota
        if usage.tokens_this_month >= quota.max_tokens_per_month:
            logger.warning(
                "quota_exceeded",
                tenant_id=tenant_id,
                quota_type="tokens",
                limit=quota.max_tokens_per_month,
                current=usage.tokens_this_month
            )
            return False, f"Monthly token quota exceeded ({quota.max_tokens_per_month} tokens)"

        # Check spend budget
        if usage.spend_this_month >= quota.max_spend_per_month:
            logger.warning(
                "quota_exceeded",
                tenant_id=tenant_id,
                quota_type="spend",
                limit=quota.max_spend_per_month,
                current=usage.spend_this_month
            )
            return False, f"Monthly budget exceeded (${quota.max_spend_per_month})"

        # Check concurrent agents
        if operation == "start_agent":
            if usage.concurrent_agents >= quota.max_concurrent_agents:
                logger.warning(
                    "quota_exceeded",
                    tenant_id=tenant_id,
                    quota_type="concurrent_agents",
                    limit=quota.max_concurrent_agents,
                    current=usage.concurrent_agents
                )
                return False, f"Concurrent agent limit reached ({quota.max_concurrent_agents})"

        return True, None

    async def record_usage(
        self,
        tenant_id: str,
        tokens: int = 0,
        cost: float = 0.0,
        agent_started: bool = False,
        agent_stopped: bool = False
    ):
        """Record resource usage for billing and quota enforcement."""

        # Increment request counter (hourly window)
        request_key = f"usage:{tenant_id}:requests:{self._current_hour()}"
        await self.redis.incr(request_key)
        await self.redis.expire(request_key, 3600)  # Expire after 1 hour

        # Increment token counter (monthly window)
        token_key = f"usage:{tenant_id}:tokens:{self._current_month()}"
        await self.redis.incrby(token_key, tokens)

        # Increment spend (monthly window)
        spend_key = f"usage:{tenant_id}:spend:{self._current_month()}"
        await self.redis.incrbyfloat(spend_key, cost)

        # Track concurrent agents
        if agent_started:
            await self.redis.incr(f"usage:{tenant_id}:concurrent")
        if agent_stopped:
            await self.redis.decr(f"usage:{tenant_id}:concurrent")

        # Store in database for billing
        await self.db.record_usage(
            tenant_id=tenant_id,
            timestamp=datetime.utcnow(),
            tokens=tokens,
            cost=cost
        )

        logger.info(
            "usage_recorded",
            tenant_id=tenant_id,
            tokens=tokens,
            cost=cost
        )

    async def get_usage(self, tenant_id: str) -> Usage:
        """Get current usage for tenant."""
        requests_this_hour = int(
            await self.redis.get(
                f"usage:{tenant_id}:requests:{self._current_hour()}"
            ) or 0
        )

        tokens_this_month = int(
            await self.redis.get(
                f"usage:{tenant_id}:tokens:{self._current_month()}"
            ) or 0
        )

        spend_this_month = float(
            await self.redis.get(
                f"usage:{tenant_id}:spend:{self._current_month()}"
            ) or 0.0
        )

        concurrent_agents = int(
            await self.redis.get(
                f"usage:{tenant_id}:concurrent"
            ) or 0
        )

        # Get storage from database
        storage_mb = await self.db.get_storage_usage(tenant_id)

        return Usage(
            requests_this_hour=requests_this_hour,
            tokens_this_month=tokens_this_month,
            spend_this_month=spend_this_month,
            concurrent_agents=concurrent_agents,
            storage_mb=storage_mb
        )

    def _current_hour(self) -> str:
        """Get current hour as string (for hourly quotas)."""
        return datetime.utcnow().strftime("%Y-%m-%d-%H")

    def _current_month(self) -> str:
        """Get current month as string (for monthly quotas)."""
        return datetime.utcnow().strftime("%Y-%m")
```

### Usage-Based Billing

```python
# billing.py
class BillingCalculator:
    """Calculate bills based on usage."""

    # Pricing tiers
    PRICING = {
        "starter": {
            "base_fee": 29.0,  # $29/month base
            "included_tokens": 100_000,
            "overage_per_1k_tokens": 0.01  # $0.01 per 1K tokens over limit
        },
        "professional": {
            "base_fee": 99.0,
            "included_tokens": 1_000_000,
            "overage_per_1k_tokens": 0.008
        },
        "enterprise": {
            "base_fee": 499.0,
            "included_tokens": 10_000_000,
            "overage_per_1k_tokens": 0.005
        }
    }

    def calculate_bill(
        self,
        tenant_id: str,
        tier: str,
        tokens_used: int
    ) -> dict:
        """Calculate monthly bill for tenant."""
        pricing = self.PRICING[tier]

        base_fee = pricing["base_fee"]
        included = pricing["included_tokens"]
        overage_rate = pricing["overage_per_1k_tokens"]

        # Calculate overage
        if tokens_used <= included:
            overage_tokens = 0
            overage_fee = 0.0
        else:
            overage_tokens = tokens_used - included
            overage_fee = (overage_tokens / 1000) * overage_rate

        total = base_fee + overage_fee

        return {
            "tenant_id": tenant_id,
            "tier": tier,
            "base_fee": base_fee,
            "tokens_included": included,
            "tokens_used": tokens_used,
            "overage_tokens": overage_tokens,
            "overage_fee": round(overage_fee, 2),
            "total": round(total, 2)
        }
```

**Example Bill**:

```python
bill = calculator.calculate_bill(
    tenant_id="acme-corp",
    tier="professional",
    tokens_used=1_500_000
)

# Result:
# {
#   "tenant_id": "acme-corp",
#   "tier": "professional",
#   "base_fee": 99.0,
#   "tokens_included": 1000000,
#   "tokens_used": 1500000,
#   "overage_tokens": 500000,
#   "overage_fee": 4.0,   # (500K / 1K) * $0.008
#   "total": 103.0
# }
```

---

## Platform API Design

### RESTful API for Developers

```python
# platform_api.py
from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel
import structlog

logger = structlog.get_logger()

app = FastAPI(title="Agent Platform API", version="1.0.0")

# Request/Response models
class AgentCreateRequest(BaseModel):
    name: str
    system_prompt: str
    tools: list[str]

class AgentExecuteRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None

class AgentResponse(BaseModel):
    conversation_id: str
    message: str
    tokens_used: int
    cost: float

# Authentication
async def get_tenant_id(authorization: str = Header(...)) -> str:
    """Extract tenant_id from API key."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid auth header")

    api_key = authorization.replace("Bearer ", "")
    tenant_id = await verify_api_key(api_key)

    if not tenant_id:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return tenant_id

# Endpoints
@app.post("/agents", response_model=dict)
async def create_agent(
    request: AgentCreateRequest,
    tenant_id: str = Depends(get_tenant_id)
):
    """Create a new agent."""

    # Check quota
    quota_ok, reason = await quota_manager.check_quota(
        tenant_id, operation="create_agent"
    )
    if not quota_ok:
        raise HTTPException(status_code=429, detail=reason)

    # Create agent
    agent_id = await agent_service.create_agent(
        tenant_id=tenant_id,
        name=request.name,
        system_prompt=request.system_prompt,
        tools=request.tools
    )

    logger.info(
        "agent_created",
        tenant_id=tenant_id,
        agent_id=agent_id,
        name=request.name
    )

    return {
        "agent_id": agent_id,
        "name": request.name,
        "status": "active"
    }

@app.post("/agents/{agent_id}/execute", response_model=AgentResponse)
async def execute_agent(
    agent_id: str,
    request: AgentExecuteRequest,
    tenant_id: str = Depends(get_tenant_id)
):
    """Execute an agent with a user message."""

    # Check quota
    quota_ok, reason = await quota_manager.check_quota(
        tenant_id, operation="execute_agent"
    )
    if not quota_ok:
        raise HTTPException(status_code=429, detail=reason)

    # Verify agent belongs to tenant
    agent = await agent_service.get_agent(agent_id)
    if agent.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Execute agent
    try:
        response = await runtime.execute_agent(
            tenant_id=tenant_id,
            agent_id=agent_id,
            user_message=request.message,
            conversation_id=request.conversation_id
        )

        # Record usage
        await quota_manager.record_usage(
            tenant_id=tenant_id,
            tokens=response.tokens_used,
            cost=response.cost
        )

        return AgentResponse(
            conversation_id=response.conversation_id,
            message=response.message,
            tokens_used=response.tokens_used,
            cost=response.cost
        )

    except QuotaExceededError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except Exception as e:
        logger.error(
            "agent_execution_failed",
            tenant_id=tenant_id,
            agent_id=agent_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Agent execution failed")

@app.get("/usage", response_model=dict)
async def get_usage(tenant_id: str = Depends(get_tenant_id)):
    """Get current usage and quota."""

    quota = await quota_manager.get_quota(tenant_id)
    usage = await quota_manager.get_usage(tenant_id)

    return {
        "tenant_id": tenant_id,
        "quota": {
            "max_requests_per_hour": quota.max_requests_per_hour,
            "max_tokens_per_month": quota.max_tokens_per_month,
            "max_spend_per_month": quota.max_spend_per_month
        },
        "usage": {
            "requests_this_hour": usage.requests_this_hour,
            "tokens_this_month": usage.tokens_this_month,
            "spend_this_month": usage.spend_this_month,
            "remaining_tokens": quota.max_tokens_per_month - usage.tokens_this_month,
            "remaining_budget": quota.max_spend_per_month - usage.spend_this_month
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
```

### Developer Experience: SDK

Provide SDKs in popular languages to simplify integration.

**Python SDK**:

```python
# agent_platform_sdk.py
import httpx
from typing import Optional

class AgentPlatformClient:
    """Python SDK for Agent Platform."""

    def __init__(self, api_key: str, base_url: str = "https://api.agentplatform.com"):
        self.api_key = api_key
        self.base_url = base_url
        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"}
        )

    async def create_agent(
        self,
        name: str,
        system_prompt: str,
        tools: list[str]
    ) -> dict:
        """Create a new agent."""
        response = await self.client.post(
            "/agents",
            json={
                "name": name,
                "system_prompt": system_prompt,
                "tools": tools
            }
        )
        response.raise_for_status()
        return response.json()

    async def execute_agent(
        self,
        agent_id: str,
        message: str,
        conversation_id: Optional[str] = None
    ) -> dict:
        """Execute an agent."""
        response = await self.client.post(
            f"/agents/{agent_id}/execute",
            json={
                "message": message,
                "conversation_id": conversation_id
            }
        )
        response.raise_for_status()
        return response.json()

    async def get_usage(self) -> dict:
        """Get current usage."""
        response = await self.client.get("/usage")
        response.raise_for_status()
        return response.json()

    async def close(self):
        """Close the client."""
        await self.client.aclose()

# Usage
async def main():
    client = AgentPlatformClient(api_key="pk_live_...")

    # Create agent
    agent = await client.create_agent(
        name="Support Agent",
        system_prompt="You are a helpful customer support agent.",
        tools=["search_kb", "create_ticket"]
    )

    # Execute agent
    response = await client.execute_agent(
        agent_id=agent["agent_id"],
        message="How do I reset my password?"
    )

    print(response["message"])
    print(f"Tokens used: {response['tokens_used']}")

    # Check usage
    usage = await client.get_usage()
    print(f"Tokens remaining: {usage['usage']['remaining_tokens']}")

    await client.close()
```

---

## Security in Multi-Tenant Platforms

### Tenant Isolation Layers

| **Layer** | **Isolation Mechanism** | **Example** |
|-----------|-------------------------|-------------|
| **Network** | VPC per tenant (silo) or security groups | AWS VPC, Kubernetes NetworkPolicy |
| **Compute** | Namespace per tenant, resource limits | Kubernetes namespaces, cgroups |
| **Data** | Row-level security, schema per tenant | PostgreSQL RLS, Redis namespaces |
| **API** | API key per tenant, rate limiting | JWT with tenant_id claim |
| **Storage** | Bucket per tenant or prefix isolation | S3 bucket policies |

### Row-Level Security (PostgreSQL)

```sql
-- Enable row-level security
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their tenant's data
CREATE POLICY tenant_isolation ON conversations
    FOR ALL
    TO authenticated_users
    USING (tenant_id = current_setting('app.current_tenant')::uuid);

-- Set tenant context (application sets this)
SET app.current_tenant = '550e8400-e29b-41d4-a716-446655440000';

-- Now queries are automatically filtered by tenant
SELECT * FROM conversations;
-- Only returns conversations WHERE tenant_id = '550e8400...'
```

### API Key Management

```python
# api_keys.py
import secrets
import hashlib
from datetime import datetime, timedelta

class APIKeyManager:
    """Manage tenant API keys."""

    def __init__(self, db: Database):
        self.db = db

    def generate_api_key(self, tenant_id: str) -> str:
        """Generate a new API key for tenant."""

        # Generate secure random key
        key = f"pk_live_{secrets.token_urlsafe(32)}"

        # Hash for storage (never store plaintext!)
        key_hash = hashlib.sha256(key.encode()).hexdigest()

        # Store hashed key
        self.db.insert_api_key(
            tenant_id=tenant_id,
            key_hash=key_hash,
            created_at=datetime.utcnow()
        )

        # Return plaintext key (only shown once)
        return key

    async def verify_api_key(self, api_key: str) -> Optional[str]:
        """Verify API key and return tenant_id."""

        # Hash provided key
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        # Look up in database
        result = await self.db.get_api_key(key_hash)

        if not result:
            return None

        # Check if key is active
        if not result["active"]:
            return None

        return result["tenant_id"]
```

---

## Platform Observability

### Tenant-Level Metrics

```python
# platform_metrics.py
from prometheus_client import Counter, Histogram, Gauge

# Tenant request metrics
tenant_requests_total = Counter(
    "platform_tenant_requests_total",
    "Total requests by tenant",
    ["tenant_id", "endpoint", "status"]
)

# Tenant token usage
tenant_tokens_used = Counter(
    "platform_tenant_tokens_used_total",
    "Total tokens used by tenant",
    ["tenant_id"]
)

# Tenant spend
tenant_spend = Counter(
    "platform_tenant_spend_dollars_total",
    "Total spend by tenant",
    ["tenant_id"]
)

# Tenant quota violations
tenant_quota_violations = Counter(
    "platform_tenant_quota_violations_total",
    "Quota violations by tenant",
    ["tenant_id", "quota_type"]
)

# Platform-wide metrics
platform_active_tenants = Gauge(
    "platform_active_tenants",
    "Number of active tenants"
)

platform_active_agents = Gauge(
    "platform_active_agents",
    "Number of active agents across all tenants"
)

# Track metrics
def track_request(tenant_id: str, endpoint: str, status: int):
    tenant_requests_total.labels(
        tenant_id=tenant_id,
        endpoint=endpoint,
        status=status
    ).inc()

def track_usage(tenant_id: str, tokens: int, cost: float):
    tenant_tokens_used.labels(tenant_id=tenant_id).inc(tokens)
    tenant_spend.labels(tenant_id=tenant_id).inc(cost)

def track_quota_violation(tenant_id: str, quota_type: str):
    tenant_quota_violations.labels(
        tenant_id=tenant_id,
        quota_type=quota_type
    ).inc()
```

### Platform Dashboard (Grafana)

**Key Panels**:

1. **Platform Health**:
   - Total requests/sec (all tenants)
   - Error rate (all tenants)
   - p95 latency (all tenants)

2. **Tenant Activity**:
   - Active tenants (gauge)
   - Top 10 tenants by requests
   - Top 10 tenants by token usage

3. **Resource Usage**:
   - Total tokens/month
   - Total spend/month
   - Quota violations (by type)

4. **Alerts**:
   - Tenant quota exceeded
   - Platform error rate high
   - Individual tenant error spike

---

## Self-Service Developer Portal

### Portal Features

1. **API Key Management**: Generate, revoke, rotate keys
2. **Usage Dashboard**: Real-time usage and quotas
3. **Agent Management**: Create, edit, delete agents
4. **Logs and Debugging**: View agent execution logs
5. **Billing**: View invoices and payment history
6. **Documentation**: API reference, tutorials, examples

### Example: Usage Dashboard

```typescript
// dashboard.tsx (React component)
import React, { useEffect, useState } from 'react';
import { AgentPlatformClient } from './sdk';

export function UsageDashboard() {
  const [usage, setUsage] = useState(null);

  useEffect(() => {
    const client = new AgentPlatformClient(apiKey);

    client.getUsage().then(data => {
      setUsage(data);
    });
  }, []);

  if (!usage) return <div>Loading...</div>;

  const tokenUsagePercent =
    (usage.usage.tokens_this_month / usage.quota.max_tokens_per_month) * 100;

  const budgetUsagePercent =
    (usage.usage.spend_this_month / usage.quota.max_spend_per_month) * 100;

  return (
    <div className="dashboard">
      <h2>Usage This Month</h2>

      <div className="metric">
        <h3>Tokens</h3>
        <div className="progress-bar">
          <div style={{ width: `${tokenUsagePercent}%` }} />
        </div>
        <p>
          {usage.usage.tokens_this_month.toLocaleString()} /
          {usage.quota.max_tokens_per_month.toLocaleString()}
        </p>
      </div>

      <div className="metric">
        <h3>Budget</h3>
        <div className="progress-bar">
          <div style={{ width: `${budgetUsagePercent}%` }} />
        </div>
        <p>
          ${usage.usage.spend_this_month.toFixed(2)} /
          ${usage.quota.max_spend_per_month.toFixed(2)}
        </p>
      </div>

      <div className="metric">
        <h3>Requests (Last Hour)</h3>
        <p>{usage.usage.requests_this_hour}</p>
      </div>
    </div>
  );
}
```

---

## Production Platform Checklist

Before launching a multi-tenant platform:

### Architecture
- [ ] Multi-tenancy pattern chosen (pool, silo, hybrid)
- [ ] Resource isolation implemented
- [ ] Quota enforcement configured
- [ ] Billing system integrated
- [ ] API gateway deployed

### Security
- [ ] Row-level security enabled (database)
- [ ] API key authentication implemented
- [ ] API keys hashed (never plaintext)
- [ ] Network isolation configured
- [ ] Audit logging enabled

### Observability
- [ ] Per-tenant metrics tracked
- [ ] Platform dashboard deployed
- [ ] Alerts configured (quota violations, errors)
- [ ] Usage tracking for billing
- [ ] Logs aggregated and searchable

### Developer Experience
- [ ] API documentation published
- [ ] SDK released (Python, JavaScript, etc.)
- [ ] Self-service portal live
- [ ] Examples and tutorials available
- [ ] Support channels established

### Operations
- [ ] Auto-scaling configured
- [ ] Backup and disaster recovery tested
- [ ] Incident response runbooks created
- [ ] On-call rotation established
- [ ] SLA defined and monitored

---

## Key Takeaways

1. **Multi-tenancy is about isolation**: Prevent one tenant from affecting others (noisy neighbor problem).

2. **Enforce quotas religiously**: Without quotas, one runaway agent can take down your platform.

3. **Security is critical**: In multi-tenant systems, a breach in one tenant can expose all tenants.

4. **Observability per tenant**: Track metrics and logs at the tenant level for debugging and billing.

5. **Developer experience matters**: A great API, SDK, and portal differentiate platforms.

6. **Start simple, add complexity**: Begin with pool model, add silos for enterprise customers.

7. **Bill transparently**: Show usage in real-time so customers aren't surprised by invoices.

---

## Exercises

### Exercise 1: Implement Quota Enforcement

Add quota enforcement to your agent:

1. Define quotas for request rate, tokens, and spend
2. Implement `QuotaManager.check_quota()`
3. Test exceeding each quota type
4. Verify proper error messages

**Expected behavior**:
- Request beyond quota → HTTP 429 with clear message
- Usage tracked accurately in Redis
- Quota resets properly (hourly, monthly)

---

### Exercise 2: Add Row-Level Security

Implement tenant isolation in PostgreSQL:

1. Enable row-level security on conversations table
2. Create tenant isolation policy
3. Test that tenant A cannot see tenant B's data
4. Add tenant context to your agent

**Expected behavior**:
- Queries automatically filtered by tenant_id
- No way to bypass isolation (even with SQL injection)
- Performance impact minimal

---

### Exercise 3: Build a Simple Developer Portal

Create a minimal self-service portal:

1. API key generation endpoint
2. Usage dashboard (tokens, spend, requests)
3. Agent creation form
4. Execution test interface

**Expected behavior**:
- Developers can create API keys
- Real-time usage displayed
- Can create and test agents without code

---

## Conclusion

Building an agent platform is the culmination of everything in this book:

- **Reliability** (Ch 2): Ensure platform stays up even when agents fail
- **Observability** (Ch 3): Monitor across all tenants
- **Security** (Ch 4): Isolate tenants, prevent breaches
- **Cost Optimization** (Ch 5): Track and bill usage accurately
- **Scaling** (Ch 6): Handle thousands of tenants
- **Performance** (Ch 7): Keep latency low for all users
- **Testing** (Ch 8): Test multi-tenant scenarios
- **Deployment** (Ch 9): Deploy updates without downtime
- **Incident Response** (Ch 10): Debug tenant-specific issues
- **Multi-Region** (Ch 11): Serve global customers

A production-grade platform requires all these pieces working together. Start with a simple pool model, add quotas and monitoring, then scale from there.

**The goal**: Developers deploy agents to your platform and never worry about infrastructure, scaling, or reliability—you handle it all.

---

## Resources

- [AWS Multi-Tenant SaaS Architecture](https://aws.amazon.com/solutions/implementations/saas-identity-and-isolation-with-amazon-cognito/)
- [Stripe API Design Best Practices](https://stripe.com/docs/api)
- [PostgreSQL Row-Level Security](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
- [Building Multi-Tenant Applications (Microsoft)](https://learn.microsoft.com/en-us/azure/architecture/guide/multitenant/overview)

---

## You've Completed the Book!

**Congratulations!** You've learned how to build production-grade AI agent systems from the ground up.

**You now know how to**:
- Make agents reliable and resilient
- Observe and debug production issues
- Secure agents and handle threats
- Optimize costs and track budgets
- Scale to millions of requests
- Deploy with zero downtime
- Respond to incidents effectively
- Build multi-region deployments
- Create agent platforms for multiple teams or customers

**What's next?**

1. **Apply these patterns** to your own agents
2. **Share your learnings** with your team
3. **Monitor production** and iterate
4. **Write postmortems** when things break (they will!)
5. **Keep learning** from the SRE community

**Production is a journey, not a destination.** There's always room to improve reliability, reduce costs, or enhance security. Use the checklists and patterns in this book as your guide.

**Go build production-grade agents. The world needs them.**

---

*Thank you for reading "Production AI Agent Systems." Questions or feedback? Reach out to the author.*
