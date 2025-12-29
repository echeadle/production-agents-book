# Chapter 10: Incident Response - Code Examples

This directory contains production-ready incident response tools, runbooks, and templates.

## Overview

Incident response essentials for production AI agents:

1. **alerts/** - Prometheus alerting rules and routing
2. **debugging/** - Tools for diagnosing production issues
3. **runbooks/** - Step-by-step incident response guides
4. **postmortems/** - Postmortem templates and examples

## The Incident Response Cycle

```
Detect → Respond → Mitigate → Communicate → Resolve → Learn
   ↑                                                      ↓
   └──────────────────────────────────────────────────────┘
                     (Continuous Improvement)
```

## Example 1: Alerting Rules

**Location**: `alerts/`

**What it provides**:
- Prometheus alerting rules
- Severity-based routing
- Runbook links in alerts
- Alert templates

**Deploy alerts**:
```bash
cd alerts

# Apply Prometheus rules
kubectl apply -f prometheus-rules.yaml

# Verify rules loaded
curl http://prometheus:9090/api/v1/rules | jq '.data.groups[] | .name'

# Test alert
# (Trigger condition to verify alert fires)
```

**Alert severity levels**:
- **SEV1 (Critical)**: Page immediately - Complete outage or >10% error rate
- **SEV2 (Warning)**: Page during business hours - Degraded performance
- **SEV3 (Info)**: Slack notification - Non-urgent issues

**Alert examples**:
```yaml
# Complete outage (SEV1)
- alert: AgentCompleteOutage
  expr: up{job="agent-api"} == 0
  for: 2m
  labels:
    severity: critical

# High error rate (SEV1)
- alert: AgentHighErrorRate
  expr: (sum(rate(agent_errors_total[5m])) / sum(rate(agent_requests_total[5m]))) > 0.10
  for: 5m
  labels:
    severity: critical

# High latency (SEV2)
- alert: AgentHighLatency
  expr: histogram_quantile(0.95, rate(agent_response_seconds_bucket[5m])) > 5.0
  for: 10m
  labels:
    severity: warning
```

## Example 2: Debugging Tools

**Location**: `debugging/`

**What it provides**:
- Find stale/stuck jobs
- Kill runaway processes
- Analyze conversations
- Error pattern analysis

**Find stale jobs**:
```bash
cd debugging

# Find jobs stuck in processing (>5 minutes)
python debug_tools.py stale-jobs --age 300

# Output:
# Found 3 stale jobs:
#   - abc-123: 450s old
#   - def-456: 380s old
#   - ghi-789: 320s old
```

**Kill stale jobs**:
```bash
# Kill jobs older than 5 minutes
python debug_tools.py kill-stale --age 300

# Output:
# Killed 3 stale jobs
```

**Analyze conversation**:
```bash
# Debug specific conversation
python debug_tools.py analyze-conv --conv-id user123

# Output:
# {
#   "total_messages": 47,
#   "user_messages": 24,
#   "assistant_messages": 23,
#   "estimated_tokens": 15000,
#   "sample_messages": [...]
# }
```

**Error patterns**:
```bash
# Analyze error patterns from last hour
python debug_tools.py errors

# Output:
# {
#   "total_errors": 145,
#   "top_errors": [
#     {"type": "APITimeoutError", "count": 78, "percentage": 53.8},
#     {"type": "RateLimitError", "count": 45, "percentage": 31.0},
#     {"type": "ValidationError", "count": 22, "percentage": 15.2}
#   ]
# }
```

## Example 3: Runbooks

**Location**: `runbooks/`

**What it provides**:
- Step-by-step incident response guides
- Common incident scenarios
- Diagnostic commands
- Mitigation strategies

**Available runbooks**:

1. **high-error-rate.md** - Troubleshoot elevated errors
2. **high-latency.md** - Debug slow responses
3. **queue-depth-growing.md** - Handle job backlog
4. **database-issues.md** - Connection/query problems
5. **redis-down.md** - Cache failure handling
6. **rate-limits.md** - API rate limiting
7. **deployment-rollback.md** - Safe rollback procedure

**Using runbooks during incident**:
```bash
# During incident: Open relevant runbook
cat runbooks/high-error-rate.md

# Follow steps sequentially
# Check recent changes → Check error patterns → Check dependencies → Mitigate

# Example: Check recent deployments
kubectl rollout history deployment/agent-api

# Example: Check error logs
kubectl logs deployment/agent-api --tail=100 | grep ERROR

# Example: Rollback if needed
kubectl rollout undo deployment/agent-api
```

## Example 4: Postmortems

**Location**: `postmortems/`

**What it provides**:
- Postmortem template
- Example postmortems
- Action item tracking

**Create postmortem**:
```bash
cd postmortems

# Copy template
cp template.md 2024-01-15-auth-outage.md

# Fill in:
# - Impact (users, revenue, SLA)
# - Timeline (what happened when)
# - Root cause (why it happened)
# - What went well/wrong
# - Action items (who, what, when)
```

**Postmortem sections**:
- **Meta**: Date, duration, severity, responders
- **Impact**: Users affected, failed requests, revenue impact
- **Timeline**: Chronological events
- **Root Cause**: What happened and why
- **What Went Well**: Effective responses
- **What Went Wrong**: Failures in process
- **Action Items**: Concrete improvements (with owners and dates)
- **Lessons Learned**: Key takeaways

## Incident Response Workflow

### 1. Detection (0-5 minutes)

```bash
# Alert received via PagerDuty
# → Acknowledge within 5 minutes

# Open monitoring dashboard
open https://grafana.company.com/agent-health

# Check recent changes
kubectl rollout history deployment/agent-api
git log --oneline --since="1 hour ago"
```

### 2. Assessment (5-10 minutes)

```bash
# Determine severity
# SEV1: >10% error rate or complete outage
# SEV2: 5-10% error rate or degraded performance
# SEV3: <5% error rate or minor issue

# Check metrics
curl http://prometheus:9090/api/v1/query?query=rate(agent_errors_total[5m])

# Check logs for patterns
kubectl logs deployment/agent-api --tail=100 | grep ERROR | cut -d' ' -f5- | sort | uniq -c
```

### 3. Mitigation (10-20 minutes)

```bash
# Option 1: Rollback recent deployment
kubectl rollout undo deployment/agent-api

# Option 2: Scale up resources
kubectl scale deployment/agent-worker --replicas=20

# Option 3: Disable feature flag
curl -X POST http://localhost:8000/flags/problematic_feature/disable

# Option 4: Enable circuit breaker
kubectl set env deployment/agent-api CIRCUIT_BREAKER_ENABLED=true
```

### 4. Communication (continuous)

```bash
# Update status page
curl -X POST https://status.company.com/api/incidents \
  -d '{"message": "Investigating elevated error rates", "status": "investigating"}'

# Post to Slack
# "🚨 SEV2: Investigating 8% error rate. Recent deployment suspected. Rollback initiated."

# Update every 15-30 minutes
# "Update: Rollback complete. Error rate decreasing. Monitoring for 15 minutes."
```

### 5. Resolution (variable)

```bash
# Verify metrics returned to normal
watch -n 30 'curl -s http://prometheus:9090/api/v1/query?query=rate(agent_errors_total[5m])'

# Monitor for 15-30 minutes to ensure stable

# Declare resolved
curl -X POST https://status.company.com/api/incidents/ID \
  -d '{"status": "resolved", "message": "Issue resolved. Error rates normal."}'
```

### 6. Follow-up (24-48 hours)

```bash
# Schedule postmortem meeting
# - Include all responders
# - Review timeline
# - Identify action items

# Create postmortem document
cp postmortems/template.md postmortems/2024-01-15-incident.md

# Track action items in project management tool
# - Add to sprint backlog
# - Assign owners
# - Set due dates
```

## On-Call Preparation

### Before Your On-Call Shift

```bash
# Test access to all systems
kubectl get pods  # Verify kubectl access
ssh production-server  # Verify SSH access
curl https://grafana.company.com  # Verify dashboard access

# Bookmark key resources
# - Grafana dashboards
# - Runbook repository
# - PagerDuty schedule
# - Status page admin

# Check escalation path
# Who is secondary on-call?
# Who is engineering manager?
# What is the escalation SLA?
```

### On-Call Checklist

- [ ] Laptop charged and ready
- [ ] Phone charged and alerts enabled
- [ ] VPN configured and tested
- [ ] Access to all systems verified
- [ ] Runbooks bookmarked
- [ ] Secondary on-call contact saved
- [ ] PagerDuty app installed and tested
- [ ] Slack mobile notifications enabled
- [ ] Calendar blocked (no conflicts)

## Incident Simulation (Fire Drill)

### Monthly Fire Drill

Practice incident response with simulations:

```bash
# Simulate high error rate
# 1. Deploy intentionally broken version to staging
kubectl set image deployment/agent-api-staging api=agent-api:broken

# 2. Trigger alerts
# 3. Follow runbook
# 4. Practice rollback
kubectl rollout undo deployment/agent-api-staging

# 5. Time the response
# - Detection: < 5 minutes
# - Mitigation: < 15 minutes
# - Resolution: < 30 minutes

# 6. Debrief
# - What went well?
# - What was confusing?
# - Update runbooks
```

## Common Incident Scenarios

### Scenario 1: Deployment Gone Wrong

**Symptoms**:
- Error rate spike after deployment
- Errors all have same type/pattern

**Diagnosis**:
```bash
# Check recent deployments
kubectl rollout history deployment/agent-api

# Check error pattern
kubectl logs deployment/agent-api --tail=100 | grep ERROR
```

**Mitigation**:
```bash
# Rollback immediately
kubectl rollout undo deployment/agent-api

# Monitor recovery
watch -n 5 'kubectl get pods'
```

### Scenario 2: API Rate Limits

**Symptoms**:
- RateLimitError in logs
- Errors during peak hours

**Diagnosis**:
```bash
# Check rate limit errors
kubectl logs deployment/agent-api | grep RateLimitError | wc -l

# Check request rate
curl http://prometheus:9090/api/v1/query?query=rate(anthropic_requests_total[5m])
```

**Mitigation**:
```bash
# Enable request queuing/backoff
kubectl set env deployment/agent-api ENABLE_RATE_LIMITER=true

# Reduce workers temporarily
kubectl scale deployment/agent-worker --replicas=5
```

### Scenario 3: Database Connection Pool Exhausted

**Symptoms**:
- "Too many connections" errors
- Slow queries timing out

**Diagnosis**:
```bash
# Check active connections
kubectl exec -it deployment/agent-api -- python -c "
import psycopg2
conn = psycopg2.connect('...')
cursor = conn.cursor()
cursor.execute('SELECT count(*) FROM pg_stat_activity')
print(f'Active connections: {cursor.fetchone()[0]}')
"
```

**Mitigation**:
```bash
# Restart workers (release connections)
kubectl rollout restart deployment/agent-worker

# Or increase connection pool
kubectl set env deployment/agent-api DB_POOL_SIZE=50
```

### Scenario 4: Redis Down

**Symptoms**:
- ConnectionError to Redis
- All cache operations failing

**Diagnosis**:
```bash
# Check Redis health
redis-cli ping

# Check if Redis pod is running
kubectl get pods -l app=redis
```

**Mitigation**:
```bash
# Agent should gracefully degrade (no cache)
# Verify fallback is working

# If Redis needs restart
kubectl rollout restart deployment/redis

# Monitor recovery
watch -n 5 'redis-cli ping'
```

## Metrics to Monitor During Incident

```prometheus
# Error rate
rate(agent_errors_total[5m])

# Request rate
rate(agent_requests_total[5m])

# Latency
histogram_quantile(0.95, rate(agent_response_seconds_bucket[5m]))

# Queue depth
agent_queue_depth

# Active workers
count(up{job="agent-worker"} == 1)

# Cache hit rate
rate(agent_cache_hits_total[5m]) / (rate(agent_cache_hits_total[5m]) + rate(agent_cache_misses_total[5m]))
```

## Incident Communication Templates

### Initial Notification

```
🚨 [SEV2] Agent Error Rate Elevated

Impact: 8% of requests failing
Status: Investigating
Time: 03:15 UTC

Recent deployment suspected. Rollback initiated.
Next update in 15 minutes.

Dashboard: https://grafana.company.com/agent-health
```

### Progress Update

```
Update: Agent Error Rate Investigation

Rollback complete. Error rate decreasing from 8% → 3%.
Monitoring for stability.

Next update in 15 minutes or when resolved.
```

### Resolution

```
✅ Resolved: Agent Error Rate

Issue: Deployment v1.5.2 introduced auth bug
Mitigation: Rolled back to v1.5.1
Current status: Error rate <0.1% (normal)

Duration: 37 minutes (03:12 - 03:49 UTC)
Impact: ~3,000 users affected

Postmortem: Will be published within 48 hours
```

## Production Incident Checklist

During an incident:

### Detection
- [ ] Alert acknowledged within 5 minutes
- [ ] Severity assessed (SEV1-4)
- [ ] Monitoring dashboard opened
- [ ] Recent changes reviewed

### Response
- [ ] Runbook opened
- [ ] Diagnostic steps followed
- [ ] Mitigation attempt made
- [ ] Secondary paged if needed (>15 min)

### Communication
- [ ] Status page updated
- [ ] Incident channel created (#incident-YYYY-MM-DD)
- [ ] Stakeholders notified
- [ ] Updates every 15-30 minutes

### Resolution
- [ ] Metrics confirmed normal
- [ ] Monitored for 15-30 minutes
- [ ] Status page updated (resolved)
- [ ] Incident timeline documented

### Follow-up
- [ ] Postmortem scheduled (24-48h)
- [ ] Action items created
- [ ] Runbooks updated
- [ ] Lessons shared

## Resources

- [Google SRE Book - Incident Response](https://sre.google/sre-book/managing-incidents/)
- [PagerDuty Incident Response](https://response.pagerduty.com/)
- [Atlassian Incident Handbook](https://www.atlassian.com/incident-management/handbook)
- [Blameless Postmortems](https://sre.google/sre-book/postmortem-culture/)

## Next Steps

1. Set up alerting rules
2. Create your first runbook
3. Run incident simulation
4. Practice using debugging tools
5. Review with your team

**Remember**: Every incident is a learning opportunity. Document, learn, improve!
