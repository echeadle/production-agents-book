# Runbook: Agent Complete Outage

## When to Use

This runbook applies when the agent service is completely down (all instances unavailable).

**Alert Name**: `AgentCompleteOutage`

**Severity**: SEV1 (Critical - Page immediately)

## Symptoms

- All health checks failing
- `up{job="agent-api"} == 0` in Prometheus
- Users unable to access service
- Load balancer showing all backends unhealthy

## Impact

- **100% of users affected**
- **Complete service outage**
- **Revenue loss** (~$X/minute)
- **SLA breach** (99.9% uptime)

## Quick Actions (< 5 minutes)

```bash
# 1. Check pod status
kubectl get pods -n production-agents -l app=agent

# 2. Check recent events
kubectl get events -n production-agents --sort-by='.lastTimestamp' | tail -20

# 3. Check recent deployments
kubectl rollout history deployment/agent-deployment -n production-agents
```

**If recent deployment (< 30 min)**: → **ROLLBACK IMMEDIATELY** (Skip to Rollback section)

**If all pods crashing**: → Follow Pod Crash Loop section

**If no pods running**: → Follow No Pods Running section

---

## Investigation: Pod Crash Loop

### Check Pod Logs

```bash
# Get failing pod name
POD=$(kubectl get pods -n production-agents -l app=agent --field-selector=status.phase!=Running -o jsonpath='{.items[0].metadata.name}')

# Check logs
kubectl logs -n production-agents $POD --tail=100

# Check previous logs if pod restarted
kubectl logs -n production-agents $POD --previous --tail=100
```

**Common crash patterns**:

| Error in Logs | Cause | Action |
|---------------|-------|--------|
| `Failed to connect to Redis` | Redis down | Check Redis (see Redis runbook) |
| `Invalid API key` | Secrets issue | Check Secrets Manager |
| `OOMKilled` in events | Out of memory | Increase memory limits |
| `CrashLoopBackOff` | Startup failure | Check configuration |
| `ImagePullBackOff` | Bad image | Check image tag |

### Check Resource Limits

```bash
# Check if pods are OOMKilled
kubectl get pods -n production-agents -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.containerStatuses[0].lastState.terminated.reason}{"\n"}{end}'

# Check current resource usage
kubectl top pods -n production-agents
```

**If OOMKilled**:
```bash
# Increase memory limits temporarily
kubectl set resources deployment/agent-deployment -n production-agents --limits=memory=2Gi

# Monitor if pods stabilize
watch kubectl get pods -n production-agents
```

---

## Investigation: No Pods Running

### Check Deployment Status

```bash
# Check deployment
kubectl get deployment agent-deployment -n production-agents

# Check replica count
kubectl get deployment agent-deployment -n production-agents -o jsonpath='{.spec.replicas}'

# Check available replicas
kubectl get deployment agent-deployment -n production-agents -o jsonpath='{.status.availableReplicas}'
```

**If replicas = 0**:
```bash
# Scale up
kubectl scale deployment agent-deployment -n production-agents --replicas=3

# Monitor
watch kubectl get pods -n production-agents
```

**If deployment doesn't exist**:
```bash
# Check if deployment was deleted (malicious or accidental)
kubectl get events -n production-agents | grep deployment

# If deleted, need to redeploy from Git
# Alert: This is a CRITICAL incident - escalate immediately
```

---

## Investigation: Node Issues

### Check Node Health

```bash
# Check node status
kubectl get nodes

# Check node conditions
kubectl describe nodes | grep -A 5 Conditions

# Check if agent pods are on unhealthy nodes
kubectl get pods -n production-agents -o wide
```

**If nodes are NotReady**:
- This is likely an infrastructure issue
- Escalate to infrastructure team
- Pods should auto-reschedule to healthy nodes

---

## Rollback Procedure

**Use when**: Recent deployment caused outage

```bash
# 1. Get previous revision number
kubectl rollout history deployment/agent-deployment -n production-agents

# 2. Rollback to previous revision
kubectl rollout undo deployment/agent-deployment -n production-agents

# 3. Monitor rollback progress (should take 2-5 min)
kubectl rollout status deployment/agent-deployment -n production-agents -w

# 4. Check pods coming up
watch kubectl get pods -n production-agents

# 5. Verify health checks passing
kubectl get pods -n production-agents -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.conditions[?(@.type=="Ready")].status}{"\n"}{end}'

# 6. Check if traffic is flowing
curl https://api.company.com/health
```

**Expected timeline**:
- Rollback command: 30 seconds
- New pods starting: 1-2 minutes
- Pods ready: 2-3 minutes
- Traffic restored: 3-5 minutes

---

## Emergency: Fast Recovery

**If rollback is taking too long** or **cause is unclear**:

### Option 1: Scale Up Aggressively

```bash
# Scale to max replicas to increase chance of healthy pods
kubectl scale deployment/agent-deployment -n production-agents --replicas=10

# Some pods may start successfully even if others crash
```

### Option 2: Deploy Known-Good Version

```bash
# Deploy last known good version from git
cd /path/to/infrastructure/kubernetes
git log --oneline -10  # Find last good deploy commit

# Checkout known-good version
git checkout <commit-hash>

# Apply deployment
kubectl apply -f deployment.yaml -n production-agents

# Monitor
watch kubectl get pods -n production-agents
```

### Option 3: Emergency Maintenance Mode

**Last resort if unable to restore service**:

```bash
# Deploy simple "maintenance mode" service
kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agent-maintenance
  namespace: production-agents
spec:
  replicas: 2
  selector:
    matchLabels:
      app: agent-maintenance
  template:
    metadata:
      labels:
        app: agent-maintenance
    spec:
      containers:
      - name: nginx
        image: nginx:alpine
        ports:
        - containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: agent-service
  namespace: production-agents
spec:
  selector:
    app: agent-maintenance
  ports:
  - port: 80
    targetPort: 80
EOF

# This serves a "service unavailable" page while you debug
```

---

## Resolution Verification

Once pods are healthy:

```bash
# 1. Verify pods are Running and Ready
kubectl get pods -n production-agents
# All pods should show "Running" and "1/1" ready

# 2. Check health endpoint
curl https://api.company.com/health
# Should return 200 OK

# 3. Test end-to-end
curl -X POST https://api.company.com/agent \
  -H "Content-Type: application/json" \
  -d '{"message": "test request"}'
# Should return successful response

# 4. Check metrics recovering
# Grafana: agent_requests_total should be increasing
# Error rate should be < 1%

# 5. Monitor for 5-10 minutes before declaring resolved
```

---

## Communication

### Immediate (when outage detected):

**Slack #incidents**:
```
🚨🚨🚨 SEV1: AGENT COMPLETE OUTAGE

Status: INVESTIGATING
Started: HH:MM UTC
Impact: 100% - All users unable to access service

Responder: @oncall-name
Actions:
- Checking pod status
- Reviewing recent deployments
- Preparing rollback if needed

Next update: +5 minutes
```

**Status Page** (https://status.company.com):
```
🔴 Major Outage

Our AI Agent service is currently unavailable.
We are actively working on restoring service.

Impact: Service is unavailable for all users
Start time: HH:MM UTC
Next update: +10 minutes
```

### During mitigation:

Update every 5-10 minutes with current status.

### Resolution:

**Slack #incidents**:
```
✅ SEV1 RESOLVED: Agent Outage

Resolution: [Rollback to v1.2.3 / Fixed Redis / etc.]
Duration: XX minutes
Impact: ~XXX users, ~XXX failed requests

Service is fully restored. Monitoring for stability.

Postmortem: Will be scheduled within 24 hours
```

**Status Page**:
```
✅ Resolved

The issue has been resolved. Service is fully operational.

Duration: XX minutes
Root cause: [Brief explanation]
Prevention: [Brief prevention plan]
```

---

## Post-Incident Actions

### Immediate (< 1 hour):
- [ ] Document exact timeline of events
- [ ] Capture all relevant logs, metrics, screenshots
- [ ] Identify root cause
- [ ] Update status page to "Resolved"
- [ ] Post resolution to #incidents
- [ ] Notify stakeholders

### Within 24 hours:
- [ ] Schedule postmortem meeting
- [ ] Write postmortem document
- [ ] Calculate impact (users, requests, revenue, SLA)
- [ ] Identify action items to prevent recurrence

### Within 1 week:
- [ ] Complete all P0 action items
- [ ] Update runbooks with learnings
- [ ] Test prevention measures
- [ ] Update monitoring/alerts if needed

---

## Escalation

**Escalate immediately** (don't wait 15 min):
- Complete service outage
- Critical production incident

**Escalation contacts**:
1. Secondary on-call: `@secondary-oncall` (via Slack or PagerDuty)
2. Engineering Manager: `@engineering-manager`
3. VP Engineering: `@vp-engineering` (if outage >30 min)
4. Infrastructure team: `@infra-oncall` (if nodes/cluster issues)

**Page multiple people** - this is SEV1!

---

## Prevention Checklist

After resolution, verify these safeguards:

- [ ] Deployment process includes smoke tests
- [ ] Canary deployment catches issues before full rollout
- [ ] Health checks are comprehensive
- [ ] Resource limits are appropriate
- [ ] Monitoring alerts fired quickly
- [ ] Runbooks were accurate and helpful
- [ ] Rollback process worked smoothly

---

## Related Runbooks

- [High Error Rate](./high-error-rate.md)
- [Redis Failure](./redis-failure.md)
- [Kubernetes Node Failure](./node-failure.md)
- [Rollback Procedure](./rollback.md)

---

## Metrics

**During incident**:
- Availability: 0%
- Error rate: 100%
- P95 latency: N/A (no requests succeeding)

**Recovery targets**:
- First pod healthy: < 5 minutes
- Service partially restored: < 10 minutes
- Full service restored: < 15 minutes

**SLA impact**:
- Availability SLA: 99.9% (43 min downtime/month budget)
- Each minute down: 0.0023% of monthly budget

---

**Last Updated**: 2024-01-15
**Owner**: SRE Team
**Version**: 1.3
**Tested**: 2024-01-10 (chaos engineering drill)
