# Appendix D: Cost Optimization Playbook

Comprehensive guide to optimizing costs for AI agent systems.

## Overview

This playbook provides strategies and tactics for reducing costs across all aspects of your AI agent system, from LLM API usage to infrastructure.

**Target Audience:** Engineering and Finance teams
**Update Frequency:** Monthly or when costs increase >20%

---

## Cost Breakdown

### Typical Cost Distribution

```
Total Monthly Cost: $10,000

LLM API Costs:        $7,500  (75%)
Infrastructure:       $1,500  (15%)
  - Compute (EKS):      $800
  - Database/Cache:     $450
  - Networking:         $150
  - Storage:            $100
Data Transfer:          $500  (5%)
Monitoring/Logging:     $300  (3%)
Other Services:         $200  (2%)
```

**Key Insight:** LLM API costs dominate (70-80%), so optimizing token usage has the highest ROI.

---

## 1. Token Optimization Strategies

### 1.1 Prompt Engineering

**Impact: High | Effort: Low**

#### Tactics:
- **Remove unnecessary context**
  ```python
  # Before: 500 tokens
  prompt = f"Here is all conversation history: {full_history}\nUser: {question}"

  # After: 150 tokens
  prompt = f"Context: {relevant_context}\nUser: {question}"
  ```

- **Use structured formats**
  ```python
  # Before: 200 tokens (verbose)
  "Please analyze the following data and provide insights..."

  # After: 50 tokens (structured)
  "Analyze:\n- Metric: {metric}\n- Period: {period}\n- Goal: insights"
  ```

- **Avoid repetition**
  ```python
  # Before: Repeating system prompt every turn
  # After: System prompt once, then continue conversation
  ```

**Expected Savings:** 20-40% reduction in tokens

---

### 1.2 Conversation History Management

**Impact: High | Effort: Medium**

#### Strategies:

1. **Sliding Window**
   ```python
   # Keep only last N messages
   MAX_HISTORY = 10
   conversation_history = conversation_history[-MAX_HISTORY:]
   ```
   **Savings:** 50-70% for long conversations

2. **Summarization**
   ```python
   # Summarize old messages
   if len(history) > 20:
       summary = summarize(history[:-10])
       history = [summary] + history[-10:]
   ```
   **Savings:** 60-80% for very long conversations

3. **Relevance Filtering**
   ```python
   # Keep only relevant messages
   relevant = filter_relevant_messages(history, current_question)
   ```
   **Savings:** 40-60% with good filtering

**Expected Savings:** 30-60% reduction in context costs

---

### 1.3 Prompt Caching

**Impact: Very High | Effort: Medium**

Use Anthropic's prompt caching for repeated context:

```python
# Cache system prompt and long context
response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    system=[
        {
            "type": "text",
            "text": LONG_SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"}  # Cache this
        }
    ],
    messages=messages
)
```

**Cost Reduction:**
- Cache writes: 25% of regular price
- Cache reads: 10% of regular price
- **90% savings on cached content**

**Expected Savings:** 50-70% for queries with repeated context

---

### 1.4 Model Selection

**Impact: Very High | Effort: Low**

Route requests to appropriate models:

| Model | Cost | Use Case | Tokens | Speed |
|-------|------|----------|--------|-------|
| Claude Haiku | $ | Simple tasks, classification | Fast | Very Fast |
| Claude Sonnet | $$ | Complex reasoning, coding | Medium | Fast |
| Claude Opus | $$$$ | Hardest problems only | Slow | Slow |

**Router Example:**
```python
def select_model(task_complexity):
    if task_complexity == "simple":
        return "claude-3-haiku-20240307"  # 80% cheaper
    elif task_complexity == "medium":
        return "claude-3-5-sonnet-20241022"
    else:
        return "claude-opus-4-20250514"

# Classify task complexity
complexity = classify_complexity(user_request)
model = select_model(complexity)
```

**Expected Savings:** 40-60% by routing to cheaper models

---

### 1.5 Output Optimization

**Impact: Medium | Effort: Low**

#### Tactics:

1. **Limit output tokens**
   ```python
   response = client.messages.create(
       model=model,
       max_tokens=500,  # Instead of 4096
       messages=messages
   )
   ```
   **Savings:** 50-80% on output costs

2. **Request concise responses**
   ```python
   system_prompt = "Be concise. Maximum 2 paragraphs."
   ```

3. **Use structured output**
   ```python
   # Request JSON instead of prose (fewer tokens)
   "Return as JSON: {result: string, confidence: number}"
   ```

**Expected Savings:** 30-50% reduction in output tokens

---

### 1.6 Batching

**Impact: High | Effort: Medium**

Process multiple requests in one API call:

```python
# Before: 10 separate calls
for item in items:
    result = process(item)

# After: 1 batched call
batch_prompt = f"Process these items:\n" + "\n".join(items)
results = process_batch(batch_prompt)
```

**Considerations:**
- Works best for similar tasks
- Watch for context length limits
- May increase latency

**Expected Savings:** 40-60% through reduced overhead

---

### 1.7 Caching Strategies

**Impact: Very High | Effort: High**

#### Redis Caching

```python
import hashlib
import redis

redis_client = redis.Redis(host='redis', port=6379)

def get_cached_response(prompt, model):
    # Create cache key from prompt + model
    cache_key = hashlib.sha256(
        f"{prompt}:{model}".encode()
    ).hexdigest()

    # Check cache
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    # Call API
    response = call_llm_api(prompt, model)

    # Cache result (24 hour TTL)
    redis_client.setex(
        cache_key,
        86400,
        json.dumps(response)
    )

    return response
```

**Cache Hit Rate Targets:**
- FAQ systems: 70-90%
- General queries: 30-50%
- Unique queries: 10-20%

**Expected Savings:** 30-80% based on hit rate

---

## 2. Infrastructure Optimization

### 2.1 Compute Costs

**Impact: Medium | Effort: Low**

#### EKS/Kubernetes:

1. **Right-size pods**
   ```yaml
   resources:
     requests:
       cpu: "500m"     # Reduce from 1000m
       memory: "1Gi"   # Reduce from 2Gi
     limits:
       cpu: "1000m"
       memory: "2Gi"
   ```
   **Savings:** 40-60% on overprovisioned resources

2. **Use autoscaling**
   ```yaml
   minReplicas: 2    # Down from 5
   maxReplicas: 20
   ```
   **Savings:** 30-50% during low traffic

3. **Spot instances (non-production)**
   ```hcl
   node_capacity_type = "SPOT"  # 70% cheaper
   ```
   **Savings:** 50-70% on dev/staging

4. **Reserved instances (production)**
   - 1-year: 30-40% discount
   - 3-year: 50-60% discount
   **Savings:** 30-60% on stable workloads

---

### 2.2 Database/Cache Costs

**Impact: Medium | Effort: Low**

#### Redis (ElastiCache):

1. **Right-size instances**
   ```hcl
   # Dev: cache.t3.micro instead of cache.t3.medium
   # Prod: cache.r6g.large instead of cache.r6g.xlarge
   ```
   **Savings:** 50-70% by downsizing

2. **Reduce replicas (non-production)**
   ```hcl
   redis_num_replicas = 1  # Instead of 3 in dev
   ```
   **Savings:** 66% on replica costs

3. **Use reserved nodes**
   **Savings:** 30-50% with commitments

---

### 2.3 Networking Costs

**Impact: Low | Effort: Low**

1. **Minimize cross-AZ traffic**
   ```yaml
   # Use topology-aware routing
   service:
     topologyKeys:
       - "kubernetes.io/hostname"
       - "topology.kubernetes.io/zone"
   ```
   **Savings:** 30-50% on data transfer

2. **Enable NAT Gateway optimization**
   ```hcl
   # Single NAT gateway in dev (not multi-AZ)
   single_nat_gateway = true
   ```
   **Savings:** 66% on NAT costs (dev only)

3. **Use CloudFront for static assets**
   **Savings:** 50-70% on bandwidth

---

### 2.4 Storage Costs

**Impact: Low | Effort: Low**

1. **Lifecycle policies**
   ```yaml
   s3_lifecycle_rule:
     transition:
       days: 30
       storage_class: "STANDARD_IA"
     expiration:
       days: 90
   ```
   **Savings:** 40-50% on old data

2. **Compress logs**
   **Savings:** 60-80% on log storage

3. **Reduce snapshot retention**
   ```hcl
   snapshot_retention_limit = 7  # Instead of 30
   ```
   **Savings:** 75% on snapshot costs

---

## 3. Budget Controls

### 3.1 Per-Request Limits

```python
class BudgetEnforcer:
    def __init__(self, max_tokens_per_request=10000):
        self.max_tokens = max_tokens_per_request

    def enforce(self, request):
        estimated_tokens = estimate_tokens(request)

        if estimated_tokens > self.max_tokens:
            raise BudgetExceededError(
                f"Request would use {estimated_tokens} tokens "
                f"(limit: {self.max_tokens})"
            )
```

---

### 3.2 Daily/Monthly Budgets

```python
class DailyBudget:
    def __init__(self, max_daily_cost=100):
        self.max_cost = max_daily_cost
        self.redis = redis.Redis()

    def check_budget(self):
        today = datetime.now().strftime("%Y-%m-%d")
        spent = float(self.redis.get(f"cost:{today}") or 0)

        if spent >= self.max_cost:
            raise BudgetExceededError(
                f"Daily budget exceeded: ${spent:.2f}"
            )

        return self.max_cost - spent

    def record_cost(self, cost):
        today = datetime.now().strftime("%Y-%m-%d")
        self.redis.incrbyfloat(f"cost:{today}", cost)
        self.redis.expire(f"cost:{today}", 86400 * 7)
```

---

### 3.3 User/Tenant Quotas

```python
class TenantQuota:
    def __init__(self, redis_client):
        self.redis = redis_client

    def check_quota(self, tenant_id, tokens):
        key = f"quota:{tenant_id}:{date.today()}"
        used = int(self.redis.get(key) or 0)
        limit = self.get_tenant_limit(tenant_id)

        if used + tokens > limit:
            raise QuotaExceededError(
                f"Tenant {tenant_id} quota exceeded"
            )

        self.redis.incrby(key, tokens)
        self.redis.expire(key, 86400)
```

---

## 4. Monitoring & Alerting

### 4.1 Cost Dashboards

**Key Metrics:**
```promql
# Hourly cost rate
rate(agent_cost_dollars_total[1h])

# Daily cost
increase(agent_cost_dollars_total[24h])

# Cost per request
rate(agent_cost_dollars_total[5m]) / rate(agent_requests_total[5m])

# Tokens per request
rate(agent_tokens_used_total[5m]) / rate(agent_requests_total[5m])

# Monthly projection
rate(agent_cost_dollars_total[1h]) * 24 * 30
```

---

### 4.2 Cost Alerts

```yaml
# Prometheus alerts
- alert: DailyCostBudgetExceeded
  expr: increase(agent_cost_dollars_total[24h]) > 100
  annotations:
    summary: "Daily budget exceeded: ${{ $value }}"

- alert: CostSpike
  expr: |
    rate(agent_cost_dollars_total[5m])
    /
    avg_over_time(rate(agent_cost_dollars_total[5m])[1h:5m])
    > 2
  annotations:
    summary: "Cost spike: 2x higher than average"

- alert: HighCostPerRequest
  expr: |
    rate(agent_cost_dollars_total[5m])
    /
    rate(agent_requests_total[5m])
    > 0.10
  annotations:
    summary: "High cost per request: ${{ $value }}"
```

---

## 5. Optimization Workflow

### Monthly Cost Review Process

1. **Analyze Current Costs** (Week 1)
   - [ ] Download cost reports
   - [ ] Identify top cost drivers
   - [ ] Calculate cost per user/request
   - [ ] Compare to budget

2. **Identify Opportunities** (Week 2)
   - [ ] Review token usage patterns
   - [ ] Analyze cache hit rates
   - [ ] Check infrastructure utilization
   - [ ] Review user quotas

3. **Implement Changes** (Week 3)
   - [ ] Deploy optimization changes
   - [ ] Update budgets and alerts
   - [ ] Test in staging first
   - [ ] Monitor impact

4. **Measure Results** (Week 4)
   - [ ] Calculate savings achieved
   - [ ] Document learnings
   - [ ] Update optimization playbook
   - [ ] Plan next month's initiatives

---

## 6. Quick Wins Checklist

**Implement these for immediate savings:**

- [ ] Enable prompt caching (50-70% savings)
- [ ] Reduce max_tokens to reasonable limits (30-50% savings)
- [ ] Implement Redis caching (30-80% savings based on hit rate)
- [ ] Use Haiku for simple tasks (80% savings on those requests)
- [ ] Limit conversation history (30-60% savings)
- [ ] Set daily budgets with alerts
- [ ] Right-size Kubernetes pods (40-60% savings)
- [ ] Use Spot instances for dev/staging (50-70% savings)
- [ ] Reduce Redis replicas in non-prod (66% savings)
- [ ] Implement S3 lifecycle policies (40-50% savings)

**Expected Total Savings: 40-60% overall**

---

## 7. Cost Optimization ROI

### Example: $10,000/month → $4,000/month

| Strategy | Monthly Savings | Effort | ROI |
|----------|----------------|--------|-----|
| Prompt caching | $3,000 | Medium | Very High |
| Model routing | $1,500 | Low | Very High |
| Redis caching | $800 | High | High |
| History management | $400 | Medium | Medium |
| Right-size infra | $200 | Low | High |
| Spot instances (dev) | $100 | Low | Medium |
| **Total** | **$6,000** | - | - |

**ROI: 60% cost reduction**

---

## 8. Cost Attribution

### Tag Strategy

```python
# Tag all requests for cost attribution
response = client.messages.create(
    model=model,
    messages=messages,
    metadata={
        "user_id": user_id,
        "team": team_name,
        "environment": "production",
        "cost_center": cost_center
    }
)

# Track costs by dimension
track_cost(
    cost=calculate_cost(response),
    user_id=user_id,
    team=team_name,
    environment="production"
)
```

### Cost Allocation Report

```sql
-- Monthly cost by team
SELECT
    team,
    SUM(cost) as total_cost,
    COUNT(*) as requests,
    AVG(cost) as avg_cost_per_request
FROM cost_tracking
WHERE month = '2025-01'
GROUP BY team
ORDER BY total_cost DESC;
```

---

## 9. Cost Governance

### Approval Workflow

```python
class CostApprovalWorkflow:
    LIMITS = {
        "dev": 10,          # $10/day
        "staging": 50,      # $50/day
        "production": 1000  # $1000/day
    }

    def requires_approval(self, environment, daily_cost):
        return daily_cost > self.LIMITS[environment]

    def request_approval(self, cost_projection, requestor):
        # Send to cost approval queue
        approval_request = {
            "requestor": requestor,
            "projected_cost": cost_projection,
            "timestamp": datetime.now()
        }
        # Notify finance team
        send_approval_request(approval_request)
```

---

## 10. Benchmarking

### Industry Benchmarks

| Metric | Good | Average | Poor |
|--------|------|---------|------|
| Cost per request | <$0.01 | $0.01-$0.05 | >$0.05 |
| Cost per user/month | <$5 | $5-$20 | >$20 |
| Cache hit rate | >70% | 40-70% | <40% |
| Tokens per request | <2000 | 2000-5000 | >5000 |
| Infrastructure % | <20% | 20-30% | >30% |

---

## Additional Resources

- [Anthropic Pricing](https://www.anthropic.com/pricing)
- [AWS Cost Calculator](https://calculator.aws)
- [FinOps Foundation](https://www.finops.org/)
- Cost optimization tools: Kubecost, CloudHealth, Spot.io

---

**Document Version:** 1.0
**Last Updated:** 2025-12-29
**Owner:** FinOps Team
**Review Cycle:** Monthly
