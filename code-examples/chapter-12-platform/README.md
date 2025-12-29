# Chapter 12: Platform Architecture - Code Examples

This directory contains production-ready code for building a multi-tenant AI agent platform.

## Overview

Learn how to build platforms that allow multiple teams or customers to deploy AI agents:

1. **platform/** - Multi-tenant platform implementation
2. **quota-management/** - Resource quotas and enforcement
3. **billing/** - Usage tracking and billing
4. **api/** - RESTful API and authentication
5. **sdk/** - Python SDK for developers
6. **portal/** - Self-service developer portal (React)
7. **database/** - Multi-tenant database with row-level security

## Architecture Patterns

### Pattern 1: Pool Model (Shared Infrastructure)

**When to use**: Early-stage, internal platforms, cost-sensitive

```
All tenants → Shared infrastructure → Logical isolation
```

**Pros**: Cost-efficient, simple to deploy
**Cons**: Noisy neighbor problem, complex isolation logic

### Pattern 2: Silo Model (Dedicated Infrastructure)

**When to use**: Enterprise customers, regulated industries

```
Tenant A → Dedicated infrastructure A
Tenant B → Dedicated infrastructure B
Tenant C → Dedicated infrastructure C
```

**Pros**: Perfect isolation, simpler security
**Cons**: Expensive, resource inefficiency

### Pattern 3: Hybrid Model (Best of Both)

**When to use**: Mature platforms with varied customer sizes

```
Small tenants → Shared pool
Large tenants → Dedicated silos
```

**Pros**: Cost-efficient for small, isolated for large
**Cons**: Most complex to implement

## Example 1: Multi-Tenant Platform

**Location**: `platform/`

**What it provides**:
- Pool model runtime with tenant isolation
- Resource limiting per tenant
- Namespace-based data isolation
- Usage tracking for billing

**Architecture**:

```python
class MultiTenantRuntime:
    async def execute_agent(
        tenant_id: str,
        agent_id: str,
        message: str
    ):
        # 1. Check quota
        if not quota_manager.check_quota(tenant_id):
            raise QuotaExceededError()

        # 2. Load tenant-isolated data
        data = db.get_data(tenant_id=tenant_id)

        # 3. Execute with resource limits
        with resource_limiter.enforce(tenant_id):
            response = agent.run(message)

        # 4. Track usage
        quota_manager.record_usage(tenant_id, tokens=response.tokens)

        return response
```

**Run the platform**:

```bash
cd platform

# Install dependencies
uv sync

# Start platform
uv run python platform_server.py

# Test with multiple tenants
uv run python test_multi_tenant.py
```

**Expected output**:

```
Platform starting on port 8000
Tenant isolation: enabled
Quota enforcement: enabled
Billing: enabled

Tenant A: Agent executed (tokens: 1,234)
Tenant B: Agent executed (tokens: 567)
Tenant C: Quota exceeded (429)
```

## Example 2: Quota Management

**Location**: `quota-management/`

**What it provides**:
- Request rate limiting (per hour)
- Token quotas (per month)
- Spend budgets (per month)
- Concurrent agent limits
- Storage quotas

**Quota types**:

| Quota Type | Scope | Example |
|------------|-------|---------|
| Request Rate | Hourly | 1,000 req/hour |
| Tokens | Monthly | 1M tokens/month |
| Spend | Monthly | $500/month |
| Concurrent Agents | Real-time | 10 concurrent |
| Storage | Total | 100MB |

**Usage**:

```python
from quota_manager import QuotaManager, Quota

# Define quota
quota = Quota(
    tenant_id="acme-corp",
    max_requests_per_hour=1000,
    max_tokens_per_month=1_000_000,
    max_spend_per_month=500.0,
    max_concurrent_agents=10,
    max_storage_mb=100
)

# Check quota before operation
allowed, reason = await quota_manager.check_quota(
    tenant_id="acme-corp",
    operation="execute_agent"
)

if not allowed:
    raise HTTPException(status_code=429, detail=reason)

# Record usage after operation
await quota_manager.record_usage(
    tenant_id="acme-corp",
    tokens=1234,
    cost=0.05
)
```

**Test quota enforcement**:

```bash
cd quota-management

# Run quota tests
uv run pytest test_quota.py -v

# Test rate limiting
uv run python test_rate_limit.py
# Sends 1,100 requests (100 over limit)
# Expected: First 1,000 succeed, next 100 fail with 429
```

## Example 3: Billing System

**Location**: `billing/`

**What it provides**:
- Usage tracking (tokens, requests, cost)
- Tiered pricing (Starter, Professional, Enterprise)
- Overage calculation
- Invoice generation

**Pricing tiers**:

```python
PRICING = {
    "starter": {
        "base_fee": 29.0,              # $29/month
        "included_tokens": 100_000,    # 100K included
        "overage_per_1k": 0.01         # $0.01 per 1K over
    },
    "professional": {
        "base_fee": 99.0,
        "included_tokens": 1_000_000,
        "overage_per_1k": 0.008
    },
    "enterprise": {
        "base_fee": 499.0,
        "included_tokens": 10_000_000,
        "overage_per_1k": 0.005
    }
}
```

**Calculate bill**:

```python
from billing_calculator import BillingCalculator

calculator = BillingCalculator()

bill = calculator.calculate_bill(
    tenant_id="acme-corp",
    tier="professional",
    tokens_used=1_500_000  # 500K over included
)

# Result:
# {
#   "base_fee": 99.0,
#   "overage_tokens": 500_000,
#   "overage_fee": 4.0,
#   "total": 103.0
# }
```

**Generate invoices**:

```bash
cd billing

# Generate invoices for all tenants
uv run python generate_invoices.py --month 2024-03

# Output: invoices/2024-03/
# - acme-corp.pdf
# - startup-xyz.pdf
# - enterprise-co.pdf
```

## Example 4: Platform API

**Location**: `api/`

**What it provides**:
- RESTful API for agent management
- API key authentication
- Rate limiting middleware
- Quota enforcement
- Usage tracking

**API endpoints**:

```
POST   /agents                  Create agent
GET    /agents                  List agents
POST   /agents/{id}/execute     Execute agent
GET    /usage                   Get current usage
POST   /api-keys                Generate API key
```

**Start API server**:

```bash
cd api

# Start server
uv run uvicorn main:app --reload --port 8000

# Server running at http://localhost:8000
# Docs at http://localhost:8000/docs
```

**Example requests**:

```bash
# Create agent
curl -X POST http://localhost:8000/agents \
  -H "Authorization: Bearer pk_live_..." \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Support Agent",
    "system_prompt": "You are a helpful support agent.",
    "tools": ["search_kb", "create_ticket"]
  }'

# Response:
# {
#   "agent_id": "agent-abc123",
#   "name": "Support Agent",
#   "status": "active"
# }

# Execute agent
curl -X POST http://localhost:8000/agents/agent-abc123/execute \
  -H "Authorization: Bearer pk_live_..." \
  -H "Content-Type: application/json" \
  -d '{
    "message": "How do I reset my password?"
  }'

# Response:
# {
#   "conversation_id": "conv-xyz789",
#   "message": "To reset your password, go to...",
#   "tokens_used": 234,
#   "cost": 0.012
# }

# Check usage
curl http://localhost:8000/usage \
  -H "Authorization: Bearer pk_live_..."

# Response:
# {
#   "tenant_id": "acme-corp",
#   "quota": {
#     "max_tokens_per_month": 1000000
#   },
#   "usage": {
#     "tokens_this_month": 450000,
#     "remaining_tokens": 550000
#   }
# }
```

## Example 5: Python SDK

**Location**: `sdk/`

**What it provides**:
- Simple Python client for platform API
- Async/sync support
- Error handling with retries
- Type hints

**Installation**:

```bash
pip install agent-platform-sdk
```

**Usage**:

```python
from agent_platform import AgentPlatformClient

# Initialize client
client = AgentPlatformClient(api_key="pk_live_...")

# Create agent
agent = await client.create_agent(
    name="Support Agent",
    system_prompt="You are helpful.",
    tools=["search"]
)

# Execute agent
response = await client.execute_agent(
    agent_id=agent["agent_id"],
    message="Hello!"
)

print(response["message"])
print(f"Tokens: {response['tokens_used']}")

# Check usage
usage = await client.get_usage()
print(f"Remaining: {usage['usage']['remaining_tokens']} tokens")
```

**Run examples**:

```bash
cd sdk

# Basic usage
uv run python examples/basic_usage.py

# Streaming responses
uv run python examples/streaming.py

# Error handling
uv run python examples/error_handling.py
```

## Example 6: Developer Portal

**Location**: `portal/`

**What it provides**:
- React-based web portal
- API key management
- Usage dashboard
- Agent management UI
- Billing and invoices

**Features**:

1. **Dashboard**: Real-time usage graphs
2. **API Keys**: Generate, revoke, rotate keys
3. **Agents**: Create, edit, delete agents
4. **Logs**: View execution logs and debugging info
5. **Billing**: View invoices and payment history

**Run portal**:

```bash
cd portal

# Install dependencies
npm install

# Start dev server
npm run dev

# Open http://localhost:3000
```

**Screenshots**:

Dashboard shows:
- Token usage (progress bar)
- Budget usage (progress bar)
- Requests this hour
- Active agents
- Recent executions

## Example 7: Multi-Tenant Database

**Location**: `database/`

**What it provides**:
- PostgreSQL with row-level security
- Automatic tenant isolation
- Migration scripts
- Seed data for testing

**Setup row-level security**:

```sql
-- Enable RLS on conversations table
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only access their tenant's data
CREATE POLICY tenant_isolation ON conversations
    FOR ALL
    TO authenticated_users
    USING (tenant_id = current_setting('app.current_tenant')::uuid);

-- Set tenant context before queries
SET app.current_tenant = 'tenant-abc-123';

-- All queries now automatically filtered
SELECT * FROM conversations;
-- WHERE tenant_id = 'tenant-abc-123' (automatic!)
```

**Run migrations**:

```bash
cd database

# Run migrations
psql -U postgres -d agent_platform < migrations/001_create_tables.sql
psql -U postgres -d agent_platform < migrations/002_enable_rls.sql

# Seed test data
psql -U postgres -d agent_platform < seeds/tenants.sql
```

**Test isolation**:

```bash
# Test that tenant A cannot see tenant B's data
uv run python test_isolation.py

# Expected output:
# ✅ Tenant A can see their own data (50 rows)
# ✅ Tenant A cannot see Tenant B's data (0 rows)
# ✅ Tenant B can see their own data (30 rows)
# ✅ Tenant B cannot see Tenant A's data (0 rows)
```

## Multi-Tenant Platform Workflow

### 1. Tenant Onboarding

```bash
# New customer signs up
curl -X POST http://localhost:8000/signup \
  -d '{"email": "user@acme.com", "tier": "professional"}'

# Response:
# {
#   "tenant_id": "acme-corp",
#   "api_key": "pk_live_abc123...",  # Shown once
#   "tier": "professional",
#   "quota": {...}
# }
```

### 2. Create Agent

```python
# Customer creates agent via SDK
client = AgentPlatformClient(api_key="pk_live_abc123...")

agent = await client.create_agent(
    name="Support Bot",
    system_prompt="Help customers.",
    tools=["search_kb"]
)
```

### 3. Execute Agent

```python
# Customer executes agent
response = await client.execute_agent(
    agent_id=agent["agent_id"],
    message="How do I cancel?"
)
```

### 4. Track Usage

Platform automatically:
- Tracks tokens used
- Calculates cost
- Enforces quotas
- Records for billing

```python
# Automatic usage tracking (platform code)
await quota_manager.record_usage(
    tenant_id="acme-corp",
    tokens=1234,
    cost=0.062
)
```

### 5. Generate Invoice

```bash
# End of month: Generate invoices
uv run python billing/generate_invoices.py --month 2024-03

# Email invoices to customers
uv run python billing/send_invoices.py --month 2024-03
```

## Security: Tenant Isolation

### Network Isolation

```yaml
# Kubernetes NetworkPolicy (silo model)
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: tenant-isolation
  namespace: tenant-a
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          tenant: tenant-a
```

### Data Isolation

```python
# Row-level security (pool model)
# All queries automatically filtered by tenant_id

# Application sets tenant context
await db.execute(
    "SET app.current_tenant = $1",
    [tenant_id]
)

# Now queries are isolated
conversations = await db.fetch(
    "SELECT * FROM conversations"
)
# Only returns tenant's conversations
```

### API Key Security

```python
# NEVER store plaintext API keys
import hashlib

def store_api_key(tenant_id: str, api_key: str):
    # Hash before storing
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    db.insert(
        "INSERT INTO api_keys (tenant_id, key_hash) VALUES ($1, $2)",
        [tenant_id, key_hash]
    )

def verify_api_key(api_key: str) -> Optional[str]:
    # Hash provided key
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    # Look up hashed version
    result = db.fetchone(
        "SELECT tenant_id FROM api_keys WHERE key_hash = $1",
        [key_hash]
    )

    return result["tenant_id"] if result else None
```

## Platform Metrics

### Prometheus Metrics

```python
from prometheus_client import Counter, Histogram, Gauge

# Per-tenant metrics
tenant_requests = Counter(
    "platform_tenant_requests_total",
    "Requests by tenant",
    ["tenant_id", "status"]
)

tenant_tokens = Counter(
    "platform_tenant_tokens_total",
    "Tokens used by tenant",
    ["tenant_id"]
)

tenant_spend = Counter(
    "platform_tenant_spend_dollars_total",
    "Spend by tenant",
    ["tenant_id"]
)

# Platform-wide metrics
active_tenants = Gauge(
    "platform_active_tenants",
    "Active tenants"
)

active_agents = Gauge(
    "platform_active_agents",
    "Active agents across all tenants"
)
```

### Grafana Dashboard

**Key panels**:

1. **Platform Overview**:
   - Total requests/sec
   - Error rate
   - p95 latency
   - Active tenants

2. **Top Tenants**:
   - Top 10 by requests
   - Top 10 by tokens
   - Top 10 by spend

3. **Quota Violations**:
   - Violations by type
   - Violations by tenant
   - Trends over time

4. **Revenue**:
   - MRR (Monthly Recurring Revenue)
   - Total spend this month
   - Average revenue per tenant

## Cost Analysis

### Pool Model vs Silo Model

**Scenario**: 100 tenants, average 10K requests/day

**Pool Model** (shared infrastructure):

```
Infrastructure:
- 10 API pods (shared)
- 1 database (row-level security)
- 1 Redis cluster (namespace isolation)

Total cost: $2,000/month
Cost per tenant: $20/month
```

**Silo Model** (dedicated infrastructure):

```
Infrastructure (per tenant):
- 1 API pod
- 1 database
- 1 Redis instance

Total cost: $150,000/month (100 tenants * $1,500)
Cost per tenant: $1,500/month
```

**Hybrid Model** (smart approach):

```
Small tenants (90): Pool model
- Cost: $1,800/month ($20/tenant)

Large tenants (10): Silo model
- Cost: $15,000/month ($1,500/tenant)

Total cost: $16,800/month
Cost per tenant (avg): $168/month

Savings vs full silo: $133,200/month (89% reduction)
```

## Testing Multi-Tenancy

### Isolation Tests

```python
# test_isolation.py
import pytest

async def test_tenant_isolation():
    """Verify tenant A cannot access tenant B's data."""

    # Create data for tenant A
    await create_conversation(tenant_id="tenant-a", message="Secret A")

    # Create data for tenant B
    await create_conversation(tenant_id="tenant-b", message="Secret B")

    # Set context to tenant A
    await db.set_tenant("tenant-a")

    # Query (should only see tenant A's data)
    conversations = await db.fetch("SELECT * FROM conversations")

    assert len(conversations) == 1
    assert conversations[0]["message"] == "Secret A"
    assert "Secret B" not in str(conversations)  # Tenant B's data not visible

async def test_quota_enforcement():
    """Verify quota limits are enforced."""

    tenant_id = "test-tenant"

    # Set quota: 100 requests/hour
    await quota_manager.set_quota(
        tenant_id=tenant_id,
        max_requests_per_hour=100
    )

    # Make 100 requests (should succeed)
    for i in range(100):
        allowed, _ = await quota_manager.check_quota(tenant_id)
        assert allowed is True

    # 101st request (should fail)
    allowed, reason = await quota_manager.check_quota(tenant_id)
    assert allowed is False
    assert "rate limit" in reason.lower()
```

### Load Testing

```python
# load_test.py
from locust import HttpUser, task, between

class PlatformUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        # Each user is a different tenant
        self.api_key = generate_test_api_key()

    @task
    def execute_agent(self):
        self.client.post(
            "/agents/test-agent/execute",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"message": "Hello"}
        )

# Run load test
# locust -f load_test.py --users 1000 --spawn-rate 50
```

## Production Platform Checklist

Before launching:

### Architecture
- [ ] Multi-tenancy pattern chosen
- [ ] Resource isolation implemented
- [ ] Quota enforcement working
- [ ] Billing system integrated
- [ ] API gateway deployed

### Security
- [ ] Row-level security enabled
- [ ] API keys hashed (never plaintext)
- [ ] Network isolation configured
- [ ] Audit logging enabled
- [ ] Penetration testing completed

### Observability
- [ ] Per-tenant metrics tracked
- [ ] Platform dashboard deployed
- [ ] Quota violation alerts configured
- [ ] Usage data stored for billing
- [ ] Logs aggregated (ELK/Datadog)

### Developer Experience
- [ ] API documentation published
- [ ] SDK released (Python, JS)
- [ ] Self-service portal live
- [ ] Examples and tutorials available
- [ ] Support channels established

### Operations
- [ ] Auto-scaling configured
- [ ] Backup and DR tested
- [ ] Incident runbooks created
- [ ] On-call rotation established
- [ ] SLA defined (e.g., 99.9% uptime)

## Troubleshooting

### Issue: One tenant affecting others (noisy neighbor)

**Symptoms**: All tenants slow when one tenant has spike

**Diagnosis**:

```bash
# Check per-tenant resource usage
kubectl top pods --selector=app=agent-runtime

# Check which tenant is using most resources
curl http://prometheus:9090/api/v1/query?query=rate(platform_tenant_tokens_total[5m])
```

**Solution**:

```yaml
# Add resource limits per tenant
resources:
  limits:
    memory: "1Gi"
    cpu: "1000m"
  requests:
    memory: "512Mi"
    cpu: "500m"

# Or move heavy tenant to dedicated silo
```

### Issue: Quota not enforced

**Symptoms**: Tenant exceeds quota without 429 errors

**Diagnosis**:

```bash
# Check Redis (quota storage)
redis-cli GET "usage:tenant-123:requests:2024-03-15-14"

# Check quota enforcement code
grep -r "check_quota" api/
```

**Solution**:

```python
# Ensure check_quota is called BEFORE operation
allowed, reason = await quota_manager.check_quota(tenant_id)
if not allowed:
    raise HTTPException(status_code=429, detail=reason)

# Then execute operation
response = await execute_agent(...)
```

### Issue: Tenant data leakage

**Symptoms**: Tenant A sees tenant B's data

**Diagnosis**:

```bash
# Check row-level security policies
psql -c "\d+ conversations"

# Test isolation manually
psql -c "SET app.current_tenant = 'tenant-a'; SELECT * FROM conversations;"
```

**Solution**:

```sql
-- Ensure RLS is enabled
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;

-- Verify policy exists
SELECT * FROM pg_policies WHERE tablename = 'conversations';

-- Ensure app sets tenant context
-- (Every query must SET app.current_tenant first)
```

## Best Practices

1. **Start with pool model**, add silos for enterprise customers later
2. **Enforce quotas at multiple layers** (API gateway, runtime, database)
3. **Hash API keys**, never store plaintext
4. **Track metrics per tenant** for debugging and billing
5. **Test isolation thoroughly** (one tenant should never see another's data)
6. **Provide great DX** (SDK, docs, portal) to differentiate
7. **Bill transparently** (show usage in real-time)
8. **Plan for noisy neighbors** (resource limits, circuit breakers)

## Resources

- [AWS Multi-Tenant SaaS](https://aws.amazon.com/solutions/implementations/saas-identity-and-isolation-with-amazon-cognito/)
- [PostgreSQL Row-Level Security](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
- [Stripe API Design](https://stripe.com/docs/api)
- [Microsoft Multi-Tenant Guide](https://learn.microsoft.com/en-us/azure/architecture/guide/multitenant/overview)

## Next Steps

1. Choose multi-tenancy pattern (pool, silo, hybrid)
2. Implement quota enforcement
3. Set up row-level security
4. Build platform API
5. Create SDK for developers
6. Deploy developer portal
7. Load test with multiple tenants
8. Launch!

**Congratulations!** You've completed the final chapter of "Production AI Agent Systems."

You now have all the knowledge to build reliable, scalable, secure, and cost-effective AI agent systems—from single agents to multi-tenant platforms.

**Go build production-grade agents. The world needs them.**
