# Appendix E: Incident Response Runbooks

Step-by-step guides for responding to common production incidents.

## Overview

These runbooks provide structured responses to common incidents. Each runbook follows the same format:
- **Symptoms** - How to identify the issue
- **Impact** - What's affected
- **Investigation** - How to diagnose
- **Resolution** - How to fix
- **Prevention** - How to avoid in future

**General Incident Response Process:**
1. Acknowledge the incident
2. Assess severity and impact
3. Communicate with stakeholders
4. Investigate and diagnose
5. Implement fix
6. Verify resolution
7. Document and create postmortem

---

## Runbook 1: Agent Down

### Symptoms
- [ ] Alert: `AgentDown` firing
- [ ] Health check endpoint returning 503/404
- [ ] No requests being processed
- [ ] Users reporting "service unavailable"

### Impact
**Severity: CRITICAL**
- Users cannot make requests
- Complete service outage
- Revenue impact if usage-based billing

### Investigation

```bash
# 1. Check pod status
kubectl get pods -n production-agents
# Look for: CrashLoopBackOff, Error, ImagePullBackOff

# 2. Check recent events
kubectl get events -n production-agents --sort-by='.lastTimestamp' | head -20

# 3. Check pod logs
POD=$(kubectl get pods -n production-agents -l app=production-agent -o jsonpath='{.items[0].metadata.name}')
kubectl logs -f $POD -n production-agents --tail=100

# 4. Check pod describe for errors
kubectl describe pod $POD -n production-agents

# 5. Check recent deployments
kubectl rollout history deployment/agent-deployment -n production-agents

# 6. Check resource usage
kubectl top pods -n production-agents
```

### Common Causes & Resolutions

#### Cause 1: Out of Memory (OOM)

**Symptoms:**
```
OOMKilled
exit code: 137
```

**Resolution:**
```bash
# Immediate: Increase memory limit
kubectl patch deployment agent-deployment -n production-agents \
  --patch '{"spec":{"template":{"spec":{"containers":[{"name":"agent","resources":{"limits":{"memory":"4Gi"}}}]}}}}'

# Long-term: Optimize memory usage or add more replicas
```

#### Cause 2: Image Pull Failure

**Symptoms:**
```
ImagePullBackOff
Failed to pull image: manifest unknown
```

**Resolution:**
```bash
# Check image exists
docker pull ghcr.io/your-org/agent:tag

# If doesn't exist, rollback deployment
kubectl rollout undo deployment/agent-deployment -n production-agents

# Fix image tag in deployment
kubectl set image deployment/agent-deployment \
  agent=ghcr.io/your-org/agent:working-tag \
  -n production-agents
```

#### Cause 3: Configuration Error

**Symptoms:**
```
Error: Missing required environment variable
Configuration validation failed
```

**Resolution:**
```bash
# Check ConfigMap
kubectl get configmap agent-config -n production-agents -o yaml

# Check Secrets
kubectl get secret agent-secrets -n production-agents

# Fix and restart
kubectl rollout restart deployment/agent-deployment -n production-agents
```

#### Cause 4: API Key Invalid

**Symptoms:**
```
401 Unauthorized from Anthropic API
Invalid API key
```

**Resolution:**
```bash
# Update secret
kubectl create secret generic agent-secrets \
  --from-literal=anthropic-api-key=NEW_KEY \
  --dry-run=client -o yaml | kubectl apply -f -

# Restart pods to pick up new secret
kubectl rollout restart deployment/agent-deployment -n production-agents
```

### Communication Template

```
INCIDENT: Agent service down
SEVERITY: Critical
IMPACT: All users unable to make requests
STATUS: Investigating
ETA: 15 minutes

We are aware of the issue and actively working on resolution.
Updates every 10 minutes.

- Incident Commander: @engineer-name
```

### Postmortem Template

See dedicated postmortem template at end of appendix.

---

## Runbook 2: High Error Rate

### Symptoms
- [ ] Alert: `HighErrorRate` firing
- [ ] Error rate > 5%
- [ ] Users reporting failures
- [ ] Increased 500 errors in logs

### Impact
**Severity: CRITICAL**
- Users experiencing failures
- Degraded service quality
- Potential data loss

### Investigation

```bash
# 1. Check error rate
kubectl exec -n monitoring prometheus-0 -- \
  promtool query instant \
  'rate(agent_errors_total[5m]) / rate(agent_requests_total[5m])'

# 2. Check error types
kubectl logs -n production-agents -l app=production-agent \
  --since=10m | grep ERROR | sort | uniq -c | sort -nr

# 3. Check for patterns
# - All users or specific users?
# - All endpoints or specific endpoints?
# - Started at specific time (deployment?)

# 4. Check external dependencies
# - Anthropic API status: https://status.anthropic.com
# - Redis connectivity: kubectl exec -it redis-0 -n production-agents -- redis-cli ping
# - Network issues: Check security groups, network policies

# 5. Check recent changes
kubectl rollout history deployment/agent-deployment -n production-agents
git log --since="1 hour ago" --oneline
```

### Common Causes & Resolutions

#### Cause 1: Anthropic API Rate Limiting

**Symptoms:**
```
429 Too Many Requests
rate_limit_error
```

**Resolution:**
```bash
# Immediate: Enable rate limiting
kubectl patch configmap agent-config -n production-agents \
  --patch '{"data":{"ENABLE_RATE_LIMITING":"true","RATE_LIMIT_PER_MINUTE":"100"}}'

kubectl rollout restart deployment/agent-deployment -n production-agents

# Long-term: Implement token bucket rate limiter
```

#### Cause 2: Redis Connection Failure

**Symptoms:**
```
ConnectionError: Cannot connect to Redis
ECONNREFUSED redis:6379
```

**Resolution:**
```bash
# Check Redis status
kubectl get pods -n production-agents | grep redis

# If down, check Redis logs
kubectl logs redis-0 -n production-agents

# If Redis is down, see "Redis Failure" runbook

# If network issue, check network policy
kubectl get networkpolicy -n production-agents
```

#### Cause 3: Bad Deployment

**Symptoms:**
- Errors started immediately after deployment
- New code version has bugs

**Resolution:**
```bash
# Rollback immediately
kubectl rollout undo deployment/agent-deployment -n production-agents

# Verify error rate decreases
# Watch for 5-10 minutes

# If resolved, investigate bad deployment in non-prod
```

#### Cause 4: Downstream Service Failure

**Symptoms:**
- Circuit breaker open
- Timeout errors
- External API errors

**Resolution:**
```bash
# Check circuit breaker status
kubectl exec -n monitoring prometheus-0 -- \
  promtool query instant \
  'agent_circuit_breaker_state{state="open"}'

# Enable graceful degradation
kubectl patch configmap agent-config -n production-agents \
  --patch '{"data":{"ENABLE_DEGRADED_MODE":"true"}}'

# Monitor external services
curl -I https://api.anthropic.com
```

---

## Runbook 3: High Latency

### Symptoms
- [ ] Alert: `HighLatency` firing
- [ ] P95 latency > 30s
- [ ] Users reporting slowness
- [ ] Request timeouts increasing

### Impact
**Severity: HIGH**
- Poor user experience
- Potential timeouts
- User frustration

### Investigation

```bash
# 1. Check current latency
kubectl exec -n monitoring prometheus-0 -- \
  promtool query instant \
  'histogram_quantile(0.95, rate(agent_request_duration_seconds_bucket[5m]))'

# 2. Check latency by component
# - LLM API latency
# - Tool execution latency
# - Total request latency

# 3. Check resource utilization
kubectl top pods -n production-agents
kubectl top nodes

# 4. Check for slow queries/operations
kubectl logs -n production-agents -l app=production-agent \
  --since=10m | grep -E "duration|latency" | sort -t'=' -k2 -nr | head -20

# 5. Check external API latency
curl -w "@curl-format.txt" -o /dev/null -s https://api.anthropic.com
```

### Common Causes & Resolutions

#### Cause 1: Anthropic API Slow

**Symptoms:**
- API calls taking 20+ seconds
- Most latency in API call duration

**Resolution:**
```bash
# Check Anthropic status
curl -I https://status.anthropic.com

# If widespread, enable timeout and retry
kubectl patch configmap agent-config -n production-agents \
  --patch '{"data":{"API_TIMEOUT":"15","ENABLE_FAST_FAIL":"true"}}'

# If persistent, contact Anthropic support
```

#### Cause 2: CPU Throttling

**Symptoms:**
- CPU at limit
- CPU throttling metrics high

**Resolution:**
```bash
# Immediate: Increase CPU limits
kubectl patch deployment agent-deployment -n production-agents \
  --patch '{"spec":{"template":{"spec":{"containers":[{"name":"agent","resources":{"limits":{"cpu":"4000m"}}}]}}}}'

# Or scale horizontally
kubectl scale deployment agent-deployment --replicas=10 -n production-agents
```

#### Cause 3: Redis Slow

**Symptoms:**
- High Redis latency
- Slow query log populated

**Resolution:**
```bash
# Check Redis slow log
kubectl exec -it redis-0 -n production-agents -- \
  redis-cli SLOWLOG GET 10

# Check Redis memory
kubectl exec -it redis-0 -n production-agents -- \
  redis-cli INFO memory

# If memory full, increase maxmemory or flush old keys
kubectl exec -it redis-0 -n production-agents -- \
  redis-cli CONFIG SET maxmemory 2gb
```

#### Cause 4: Large Context Windows

**Symptoms:**
- Latency correlates with conversation length
- Token usage very high

**Resolution:**
```bash
# Enable conversation history truncation
kubectl patch configmap agent-config -n production-agents \
  --patch '{"data":{"MAX_HISTORY_LENGTH":"10","ENABLE_SUMMARIZATION":"true"}}'

kubectl rollout restart deployment/agent-deployment -n production-agents
```

---

## Runbook 4: Cost Spike

### Symptoms
- [ ] Alert: `DailyBudgetExceeded` or `CostSpike` firing
- [ ] Costs 2x+ higher than normal
- [ ] Token usage spike

### Impact
**Severity: HIGH**
- Budget overrun
- Potential account suspension
- Finance escalation

### Investigation

```bash
# 1. Check current cost rate
kubectl exec -n monitoring prometheus-0 -- \
  promtool query instant \
  'rate(agent_cost_dollars_total[1h]) * 24'

# 2. Check token usage
kubectl exec -n monitoring prometheus-0 -- \
  promtool query instant \
  'rate(agent_tokens_used_total[5m])'

# 3. Identify high-cost users/requests
kubectl logs -n production-agents -l app=production-agent \
  --since=1h | grep "cost" | sort -t'=' -k2 -nr | head -20

# 4. Check for unusual patterns
# - Single user making many requests?
# - Very long conversations?
# - Large context windows?

# 5. Check recent changes
# - New feature launch?
# - Marketing campaign?
# - Bot attack?
```

### Common Causes & Resolutions

#### Cause 1: Bot/Abuse

**Symptoms:**
- Single user/IP making thousands of requests
- Automated patterns

**Resolution:**
```bash
# Immediate: Block user/IP
kubectl exec -n production-agents redis-0 -- \
  redis-cli SET "blocked:user:${USER_ID}" 1 EX 3600

# Enable rate limiting
kubectl patch configmap agent-config -n production-agents \
  --patch '{"data":{"RATE_LIMIT_PER_USER":"100"}}'

# Long-term: Implement better authentication, CAPTCHA
```

#### Cause 2: Inefficient Prompts

**Symptoms:**
- Tokens per request very high (>5000)
- Long system prompts being sent repeatedly

**Resolution:**
```bash
# Enable prompt caching
kubectl patch configmap agent-config -n production-agents \
  --patch '{"data":{"ENABLE_PROMPT_CACHING":"true"}}'

# Enable history truncation
kubectl patch configmap agent-config -n production-agents \
  --patch '{"data":{"MAX_HISTORY_TOKENS":"4000"}}'

kubectl rollout restart deployment/agent-deployment -n production-agents
```

#### Cause 3: Model Misconfiguration

**Symptoms:**
- Using expensive model for all requests
- No model routing

**Resolution:**
```bash
# Enable model routing
kubectl patch configmap agent-config -n production-agents \
  --patch '{"data":{"ENABLE_MODEL_ROUTING":"true","DEFAULT_MODEL":"claude-3-haiku-20240307"}}'

kubectl rollout restart deployment/agent-deployment -n production-agents
```

#### Cause 4: Feature Launch

**Symptoms:**
- Cost increase correlated with feature release
- Expected but higher than projected

**Resolution:**
```bash
# Set budget limits
kubectl patch configmap agent-config -n production-agents \
  --patch '{"data":{"DAILY_BUDGET_DOLLARS":"500"}}'

# Enable budget enforcement
kubectl patch configmap agent-config -n production-agents \
  --patch '{"data":{"ENFORCE_BUDGET":"true"}}'

kubectl rollout restart deployment/agent-deployment -n production-agents

# Communicate with Finance team
# Adjust budgets if legitimate usage
```

---

## Runbook 5: Redis Failure

### Symptoms
- [ ] Alert: `RedisDown` firing
- [ ] Cannot connect to Redis
- [ ] Cache misses at 100%
- [ ] State persistence failing

### Impact
**Severity: CRITICAL**
- No caching (higher costs, slower)
- State loss
- Potential service degradation

### Investigation

```bash
# 1. Check Redis pod status
kubectl get pods -n production-agents | grep redis

# 2. Check Redis logs
kubectl logs redis-0 -n production-agents --tail=100

# 3. Check Redis events
kubectl describe pod redis-0 -n production-agents

# 4. Check persistence
kubectl exec -it redis-0 -n production-agents -- ls -lh /data/

# 5. Check memory
kubectl exec -it redis-0 -n production-agents -- \
  redis-cli INFO memory
```

### Common Causes & Resolutions

#### Cause 1: Out of Memory

**Symptoms:**
```
OOM Killed
Memory usage at 100%
```

**Resolution:**
```bash
# Immediate: Restart Redis
kubectl delete pod redis-0 -n production-agents
# StatefulSet will recreate it

# If OOM persists, increase memory
kubectl patch statefulset redis -n production-agents \
  --patch '{"spec":{"template":{"spec":{"containers":[{"name":"redis","resources":{"limits":{"memory":"4Gi"}}}]}}}}'

# Or adjust maxmemory policy
kubectl exec -it redis-0 -n production-agents -- \
  redis-cli CONFIG SET maxmemory-policy allkeys-lru
```

#### Cause 2: Disk Full

**Symptoms:**
```
No space left on device
RDB save failed
```

**Resolution:**
```bash
# Check disk usage
kubectl exec -it redis-0 -n production-agents -- df -h

# Increase PVC size (requires downtime)
kubectl edit pvc redis-data-redis-0 -n production-agents
# Change size, then restart pod

# Or reduce snapshot retention
kubectl exec -it redis-0 -n production-agents -- \
  redis-cli CONFIG SET save ""  # Disable RDB snapshots temporarily
```

#### Cause 3: Network Partition

**Symptoms:**
```
Connection refused
Network unreachable
```

**Resolution:**
```bash
# Check network policy
kubectl get networkpolicy -n production-agents

# Check security groups (if AWS)
aws ec2 describe-security-groups --group-ids sg-xxxxx

# Test connectivity from agent pod
kubectl exec -it ${AGENT_POD} -n production-agents -- \
  nc -zv redis-service 6379

# If network policy issue, temporarily allow all
kubectl delete networkpolicy redis-network-policy -n production-agents
# Fix and reapply
```

---

## Runbook 6: Kubernetes Node Failure

### Symptoms
- [ ] Pods evicted or pending
- [ ] Node NotReady status
- [ ] Alerts for pod crashes

### Impact
**Severity: HIGH**
- Reduced capacity
- Potential service degradation
- Pod rescheduling

### Investigation & Resolution

```bash
# 1. Check node status
kubectl get nodes

# 2. Check node events
kubectl describe node ${NODE_NAME}

# 3. Check node logs (if accessible)
ssh ${NODE_NAME}
journalctl -u kubelet -n 100

# 4. Cordon node to prevent new pods
kubectl cordon ${NODE_NAME}

# 5. Drain node gracefully
kubectl drain ${NODE_NAME} \
  --ignore-daemonsets \
  --delete-emptydir-data \
  --timeout=5m

# 6. Replace node (AWS)
# Node will be automatically replaced by ASG

# 7. Verify pods rescheduled
kubectl get pods -n production-agents -o wide
```

---

## General Incident Response Checklist

### Phase 1: Detection & Acknowledgment (0-5 min)
- [ ] Alert received via PagerDuty/Slack
- [ ] Incident acknowledged
- [ ] Incident commander assigned
- [ ] Severity assessed
- [ ] Stakeholders notified

### Phase 2: Investigation (5-15 min)
- [ ] Symptoms documented
- [ ] Logs collected
- [ ] Metrics analyzed
- [ ] Recent changes reviewed
- [ ] Root cause hypothesized

### Phase 3: Mitigation (15-30 min)
- [ ] Immediate mitigation applied
- [ ] Impact minimized
- [ ] Service restored (if possible)
- [ ] Stakeholders updated

### Phase 4: Resolution (30-60 min)
- [ ] Root cause identified
- [ ] Permanent fix applied
- [ ] Service fully restored
- [ ] Verification completed

### Phase 5: Postmortem (24-48 hours)
- [ ] Timeline documented
- [ ] Root cause analysis completed
- [ ] Action items identified
- [ ] Prevention measures defined
- [ ] Postmortem published

---

## Escalation Paths

### Severity Levels

| Severity | Description | Response Time | Escalation |
|----------|-------------|---------------|------------|
| P0 - Critical | Complete outage | 5 min | Immediate page |
| P1 - High | Major degradation | 15 min | Page if not resolved |
| P2 - Medium | Minor degradation | 1 hour | Ticket |
| P3 - Low | No user impact | 24 hours | Ticket |

### Contact List

```
INCIDENT COMMANDER
Primary: @on-call-engineer (PagerDuty)
Secondary: @engineering-lead

ENGINEERING LEADS
Backend: @backend-lead
DevOps: @devops-lead
Security: @security-lead

EXECUTIVES
CTO: @cto (P0 only)
CEO: @ceo (P0 with major impact)

EXTERNAL
Anthropic Support: support@anthropic.com
AWS Support: +1-xxx-xxx-xxxx
```

---

## Postmortem Template

```markdown
# Postmortem: [Incident Title]

**Date:** YYYY-MM-DD
**Duration:** HH:MM
**Severity:** P0/P1/P2
**Status:** [Resolved/Investigating]

## Summary

[2-3 sentence summary of what happened]

## Impact

- **Users affected:** [number or percentage]
- **Duration:** [time]
- **Services impacted:** [list]
- **Revenue impact:** [if applicable]

## Timeline (all times in UTC)

| Time | Event |
|------|-------|
| 14:23 | Alert fired: HighErrorRate |
| 14:25 | Engineer acknowledged incident |
| 14:30 | Root cause identified (Redis failure) |
| 14:35 | Mitigation applied (Redis restart) |
| 14:40 | Service restored |
| 14:45 | Incident resolved |

## Root Cause

[Detailed explanation of what caused the incident]

## Resolution

[What was done to fix it]

## Detection

[How was the incident detected? Alert, user report, etc.]

## What Went Well

- Quick detection via monitoring
- Clear runbook followed
- Effective communication

## What Went Wrong

- [Things that could have been better]

## Action Items

| Action | Owner | Due Date | Priority |
|--------|-------|----------|----------|
| Add Redis memory alerts | @devops | 2025-02-01 | High |
| Update runbook with new info | @engineer | 2025-01-15 | Medium |
| Conduct Redis DR drill | @team | 2025-02-15 | High |

## Lessons Learned

[Key takeaways and preventive measures]

## Prevention

[How to prevent this in the future]

---

**Postmortem Owner:** @engineer-name
**Reviewed By:** @engineering-lead, @devops-lead
**Date:** YYYY-MM-DD
```

---

## Additional Resources

- Incident Management: PagerDuty, Opsgenie
- Status Page: Statuspage.io, Atlassian Statuspage
- Communication: Slack, Microsoft Teams
- Postmortems: Google SRE Book, Atlassian Incident Handbook

---

**Document Version:** 1.0
**Last Updated:** 2025-12-29
**Owner:** On-Call Team
**Review Cycle:** After each major incident
