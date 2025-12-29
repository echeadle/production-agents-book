# Runbook: High Error Rate

## When to Use

This runbook applies when you receive an alert for high agent error rate (>5% of requests failing).

**Alert Name**: `AgentHighErrorRate` or `AgentElevatedErrorRate`

**Severity**: SEV1 (>10%) or SEV2 (>5%)

## Symptoms

- Error rate significantly above baseline (<0.1%)
- Users reporting failures or errors
- Dashboard showing spike in `agent_errors_total` metric

## Quick Actions

**If error rate >10% (SEV1 - Critical)**:
1. Check if there was a recent deployment → Rollback immediately
2. Check if external API is down → Enable circuit breaker
3. Escalate to on-call lead if cause unclear

**If error rate >5% (SEV2 - Warning)**:
1. Follow investigation steps below
2. Prepare to rollback if worsening
3. Page on-call if errors increasing

## Investigation Steps

### 1. Check Recent Changes (2 minutes)

```bash
# Check recent deployments
kubectl rollout history deployment/agent-deployment -n production-agents

# Check when current version was deployed
kubectl get deployment agent-deployment -n production-agents -o jsonpath='{.metadata.annotations.deployment\.kubernetes\.io/revision}'

# Check if rollout is in progress
kubectl rollout status deployment/agent-deployment -n production-agents
```

**What to look for**:
- Was there a deployment in the last 10-30 minutes?
- Is a rollout currently in progress?

**If recent deployment**: Proceed to rollback (Step 5)

---

### 2. Check Error Logs (3 minutes)

```bash
# Get recent error logs
kubectl logs -n production-agents deployment/agent-deployment --tail=100 | grep ERROR

# Or use log aggregation
# Kibana: index:production-agents AND level:ERROR AND @timestamp:>now-5m
# Loki: {namespace="production-agents"} |= "ERROR" [5m]
```

**Common error patterns**:

| Error Pattern | Cause | Action |
|---------------|-------|--------|
| `AuthenticationError: Invalid API key` | Claude API key issue | Check Secrets Manager |
| `RateLimitExceeded` | Hitting rate limits | Enable rate limiter |
| `APITimeoutError` | Claude API slow/down | Check API status |
| `RedisConnectionError` | Redis down | Check Redis health |
| `ValidationError` | Bad user input | May be user error, not systemic |

---

### 3. Check External Dependencies (2 minutes)

```bash
# Check Claude API status
curl https://status.anthropic.com/api/v2/status.json

# Check Redis health
kubectl get pods -n production-agents | grep redis
redis-cli -h redis.production-agents.svc.cluster.local ping

# Check circuit breaker status
curl http://agent-api/health | jq '.circuit_breakers'
```

**If Claude API is down**:
- Enable circuit breaker to fail fast
- Post status update to users
- Wait for API recovery

**If Redis is down**:
- Check Redis pod status
- Check Redis logs
- May need to restart Redis (see Redis failure runbook)

---

### 4. Check Error Distribution (2 minutes)

```bash
# Check error rate by error type (Prometheus)
topk(5,
  sum by (error_type) (
    rate(agent_errors_total[5m])
  )
)

# Check error rate by user (identify if specific user causing issues)
topk(10,
  sum by (user_id) (
    rate(agent_errors_total[5m])
  )
)
```

**What to look for**:
- Is one error type dominating? (Focus on that specific error)
- Is one user causing most errors? (May be abuse or bad input)
- Are errors spread evenly? (System-wide issue)

---

### 5. Rollback (if needed) (5 minutes)

**When to rollback**:
- Recent deployment (< 30 min ago)
- Error rate >10%
- Clear correlation between deployment and errors

**Rollback procedure**:

```bash
# 1. Get previous revision
PREVIOUS_REVISION=$(kubectl rollout history deployment/agent-deployment -n production-agents | tail -n 2 | head -n 1 | awk '{print $1}')

# 2. Rollback
kubectl rollout undo deployment/agent-deployment -n production-agents --to-revision=$PREVIOUS_REVISION

# 3. Monitor rollback progress
kubectl rollout status deployment/agent-deployment -n production-agents

# 4. Verify error rate decreasing
# Check Grafana dashboard: https://grafana.company.com/agent-errors
```

**Expected timeline**:
- Rollback initiated: 0-2 min
- New pods starting: 2-4 min
- Old pods terminating: 4-6 min
- Error rate decreasing: 6-10 min

---

## Resolution Steps

### If Caused by Bad Deployment:
1. Rollback (see above)
2. Block deployment pipeline
3. Investigate what changed in bad deployment
4. Add tests to prevent recurrence
5. Create postmortem

### If Caused by External API (Claude):
1. Enable circuit breaker:
   ```bash
   curl -X POST http://agent-api/admin/circuit-breaker/anthropic/open
   ```
2. Post status update to users
3. Monitor API status page
4. Wait for recovery
5. Re-enable circuit breaker when API recovered

### If Caused by Redis:
1. See Redis failure runbook
2. Restart Redis if needed
3. Verify data integrity
4. Re-enable agent processing

### If Caused by Rate Limiting:
1. Enable rate limiter:
   ```bash
   kubectl set env deployment/agent-deployment ENABLE_RATE_LIMIT=true -n production-agents
   ```
2. Monitor if error rate decreases
3. Adjust rate limits as needed

---

## Communication

### Status Update Template (Slack #incidents)

```
🚨 Incident: High Agent Error Rate

Status: INVESTIGATING / MITIGATING / RESOLVED
Severity: SEV1 / SEV2
Started: HH:MM UTC
Impact: X% of requests failing

Current Actions:
- [Action 1]
- [Action 2]

Next Update: +15 minutes
```

### User-Facing Status (Status Page)

```
We are currently experiencing elevated error rates with our AI agent service.
Our team is actively investigating and working on a resolution.

Impact: Some requests may fail or timeout
Status: Investigating
Updates: Every 15 minutes
```

---

## Post-Incident

### Immediate Actions:
- [ ] Document timeline in incident log
- [ ] Capture relevant logs/metrics
- [ ] Update status page to "Resolved"
- [ ] Post resolution message to #incidents

### Follow-up (within 24 hours):
- [ ] Schedule postmortem meeting
- [ ] Identify root cause
- [ ] Create action items to prevent recurrence
- [ ] Update this runbook if needed

---

## Escalation

**Escalate if**:
- Error rate >10% for >10 minutes
- Unable to identify cause in 15 minutes
- Rollback doesn't resolve issue
- Multiple services affected

**Escalation contacts**:
- Secondary on-call: `@secondary-oncall` in Slack
- Engineering lead: `@engineering-lead` in Slack
- PagerDuty escalation policy will auto-escalate after 15 min

---

## Metrics to Monitor

**During incident**:
- Error rate: `rate(agent_errors_total[1m])`
- Success rate: `rate(agent_requests_total[1m]) - rate(agent_errors_total[1m])`
- P95 latency: `histogram_quantile(0.95, rate(agent_response_seconds_bucket[1m]))`
- Active users affected: `count(rate(agent_errors_total[1m]) by (user_id))`

**Post-incident**:
- Error budget consumed: Calculate based on SLO
- Total requests affected: `increase(agent_errors_total[incident_duration])`
- Revenue impact: Estimate based on failed requests

---

## Related Runbooks

- [Agent Down](./agent-down.md) - Complete outage
- [High Latency](./high-latency.md) - Slow responses
- [Redis Failure](./redis-failure.md) - Redis issues
- [Rollback Procedure](./rollback.md) - Detailed rollback steps

---

**Last Updated**: 2024-01-15
**Owner**: SRE Team
**Version**: 1.2
