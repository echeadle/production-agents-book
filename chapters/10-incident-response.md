# Chapter 10: Incident Response

## Introduction: The 3 AM Page

It's 3 AM when Alex's phone buzzes with an urgent alert:

```
🚨 CRITICAL: Agent error rate 45%
   Normal: <0.1%
   Current: 45% (450 errors/min)
   Started: 2 minutes ago
```

Half-asleep, Alex opens the laptop. The agent is failing spectacularly:
- **Error rate**: 45% and climbing
- **Affected users**: 1,500 in last 2 minutes
- **Root cause**: Unknown

**What Alex needs right now**:
- Clear diagnostic steps
- Quick way to identify the issue
- Fast rollback procedure
- Communication templates

**What Alex has**:
- Panic
- Incomplete logs
- No clear runbook
- Pressure to fix it fast

**30 minutes later**, after frantic debugging:
- Root cause: New deployment broke authentication
- Fix: Rollback to previous version
- Impact: 3,000 failed customer requests
- Lesson: Need better incident response process

This is the incident response challenge: **When production breaks at 3 AM, you need a system, not improvisation.**

---

## Why Incident Response Matters

In production, incidents are inevitable:

- **Hardware fails**: Servers crash, networks partition
- **Software fails**: Bugs in production, memory leaks
- **External failures**: APIs go down, rate limits hit
- **Human error**: Bad deployments, config mistakes
- **Unexpected load**: Traffic spikes, attack patterns

**Production reality**: It's not if incidents happen, it's when.

### The Incident Response Mindset

**Bad incident response**:
- Panic and improvise
- Make changes blindly
- No coordination
- Forget to communicate
- Don't learn from incidents

**Good incident response**:
- Stay calm, follow runbook
- Methodical debugging
- Clear roles and communication
- Focus on mitigation first, root cause later
- Learn and improve

**Key principle**: Incidents are learning opportunities, not failures.

---

## On-Call Procedures

### Setting Up On-Call

**On-call rotation**:
- Primary on-call (first responder)
- Secondary on-call (backup)
- Escalation to engineering lead
- Rotate weekly (avoid burnout)

**On-call responsibilities**:
1. Respond to alerts within 5 minutes
2. Acknowledge incident
3. Assess severity
4. Mitigate or escalate
5. Document incident
6. Hand off or resolve

### On-Call Playbook

```markdown
# On-Call Playbook

## When You Get Paged

1. **Acknowledge alert** (within 5 minutes)
   - PagerDuty/Opsgenie: Click "Acknowledge"
   - Stops escalation to secondary

2. **Assess severity** (SEV1-4)
   - SEV1: Complete outage (all users affected)
   - SEV2: Major degradation (>10% users affected)
   - SEV3: Minor issue (<10% users affected)
   - SEV4: Non-urgent (no user impact)

3. **Check dashboard**
   - Open main monitoring dashboard
   - Look for anomalies (errors, latency, traffic)
   - Check recent deployments

4. **Mitigate immediately** (if obvious)
   - If recent deployment: rollback
   - If resource issue: scale up
   - If external API down: enable circuit breaker

5. **Escalate if needed** (within 15 minutes)
   - Can't fix quickly
   - Need domain expertise
   - SEV1 incident

6. **Communicate**
   - Update status page
   - Post in incident Slack channel
   - Notify stakeholders

7. **Document**
   - Timeline of events
   - Actions taken
   - Current status
```

### On-Call Tools

**Essential tools**:
- **PagerDuty/Opsgenie**: Alert routing
- **Grafana**: Metrics dashboard
- **Kibana/Datadog**: Log aggregation
- **Kubectl**: Kubernetes management
- **Runbooks**: Step-by-step guides

**On-call checklist** (before your shift):
- [ ] Laptop charged and ready
- [ ] VPN configured
- [ ] Access to all systems verified
- [ ] Runbooks bookmarked
- [ ] Secondary on-call contact saved
- [ ] Escalation path known

---

## Incident Detection and Alerting

### Alert Design Principles

**Good alerts**:
- Actionable (you can do something about it)
- Clear symptoms (what's wrong)
- Appropriate urgency (page vs email vs slack)
- Low false positive rate

**Bad alerts**:
- "CPU is high" (so what? is it a problem?)
- "Disk space low" (how low? how urgent?)
- Constant false positives (alert fatigue)

### Alerting Thresholds

```yaml
# code-examples/chapter-10-incident-response/alerts/prometheus-rules.yaml

groups:
  - name: agent_alerts
    interval: 30s
    rules:

      # SEV1: Complete outage
      - alert: AgentCompleteOutage
        expr: up{job="agent-api"} == 0
        for: 2m
        labels:
          severity: critical
          oncall: page
        annotations:
          summary: "Agent API completely down"
          description: "All agent API instances are down for 2+ minutes"
          runbook: "https://wiki.company.com/runbooks/agent-outage"
          dashboard: "https://grafana.company.com/agent-health"

      # SEV1: High error rate
      - alert: AgentHighErrorRate
        expr: |
          (
            sum(rate(agent_errors_total[5m]))
            /
            sum(rate(agent_requests_total[5m]))
          ) > 0.10
        for: 5m
        labels:
          severity: critical
          oncall: page
        annotations:
          summary: "Agent error rate >10%"
          description: "Error rate is {{ $value | humanizePercentage }}"
          runbook: "https://wiki.company.com/runbooks/high-error-rate"

      # SEV2: Elevated latency
      - alert: AgentHighLatency
        expr: |
          histogram_quantile(0.95,
            rate(agent_response_seconds_bucket[5m])
          ) > 5.0
        for: 10m
        labels:
          severity: warning
          oncall: page
        annotations:
          summary: "Agent p95 latency >5s"
          description: "p95 latency is {{ $value }}s (threshold: 5s)"
          runbook: "https://wiki.company.com/runbooks/high-latency"

      # SEV3: Queue depth growing
      - alert: AgentQueueDepthHigh
        expr: agent_queue_depth > 1000
        for: 15m
        labels:
          severity: warning
          oncall: slack
        annotations:
          summary: "Agent queue depth >1000"
          description: "Queue has {{ $value }} jobs waiting"
          runbook: "https://wiki.company.com/runbooks/queue-depth"

      # SEV3: Low cache hit rate
      - alert: AgentLowCacheHitRate
        expr: agent_cache_hit_rate < 0.5
        for: 30m
        labels:
          severity: info
          oncall: slack
        annotations:
          summary: "Cache hit rate <50%"
          description: "Cache hit rate dropped to {{ $value | humanizePercentage }}"
          runbook: "https://wiki.company.com/runbooks/cache-performance"
```

### Alert Routing

```python
# code-examples/chapter-10-incident-response/alerts/alert_router.py

from dataclasses import dataclass
from enum import Enum
import structlog

logger = structlog.get_logger()


class Severity(Enum):
    """Alert severity levels."""
    CRITICAL = "critical"  # Page immediately
    WARNING = "warning"    # Page during business hours
    INFO = "info"          # Slack notification


@dataclass
class Alert:
    """Alert information."""
    name: str
    severity: Severity
    description: str
    runbook_url: str
    dashboard_url: str
    value: float


class AlertRouter:
    """
    Route alerts to appropriate channels based on severity.
    """

    def __init__(self, pagerduty_client, slack_client):
        self.pagerduty = pagerduty_client
        self.slack = slack_client

    def handle_alert(self, alert: Alert):
        """
        Route alert to appropriate destination.
        """
        logger.info(
            "alert_received",
            alert=alert.name,
            severity=alert.severity.value,
            value=alert.value,
        )

        if alert.severity == Severity.CRITICAL:
            # Page on-call immediately
            self._page_oncall(alert)
            self._post_to_slack(alert, channel="#incidents")

        elif alert.severity == Severity.WARNING:
            # Page during business hours, slack otherwise
            if self._is_business_hours():
                self._page_oncall(alert)
            else:
                self._post_to_slack(alert, channel="#on-call")

        elif alert.severity == Severity.INFO:
            # Slack notification only
            self._post_to_slack(alert, channel="#alerts")

    def _page_oncall(self, alert: Alert):
        """Send page to on-call engineer."""
        self.pagerduty.trigger_incident(
            title=f"[{alert.severity.value.upper()}] {alert.name}",
            description=alert.description,
            severity=alert.severity.value,
            custom_details={
                "runbook": alert.runbook_url,
                "dashboard": alert.dashboard_url,
                "value": alert.value,
            }
        )

        logger.info("oncall_paged", alert=alert.name)

    def _post_to_slack(self, alert: Alert, channel: str):
        """Post alert to Slack."""
        self.slack.post_message(
            channel=channel,
            blocks=[
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"🚨 {alert.name}",
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": alert.description,
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Severity:*\n{alert.severity.value}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Value:*\n{alert.value}"
                        }
                    ]
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Runbook"},
                            "url": alert.runbook_url
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Dashboard"},
                            "url": alert.dashboard_url
                        }
                    ]
                }
            ]
        )

    def _is_business_hours(self) -> bool:
        """Check if current time is business hours."""
        from datetime import datetime
        now = datetime.now()
        # Business hours: 9am-5pm Mon-Fri
        return (
            now.weekday() < 5 and  # Monday-Friday
            9 <= now.hour < 17      # 9am-5pm
        )
```

---

## Debugging Runaway Agents

### Common Runaway Scenarios

**1. Infinite loop**:
- Agent stuck in tool-calling loop
- Each response triggers another tool call
- Never reaches end_turn

**2. Memory leak**:
- Conversation history growing unbounded
- Each turn adds more context
- Eventually runs out of memory

**3. Rate limit spiral**:
- Hitting API rate limits
- Retry logic makes it worse
- Cascading failures

**4. Recursive tool calls**:
- Tool A calls Tool B calls Tool A
- Never terminates
- Consumes resources rapidly

### Debugging Runbook

```markdown
# Runbook: Debugging Runaway Agent

## Symptoms
- High error rate
- Extreme latency
- Queue depth growing
- Resource exhaustion

## Step 1: Identify Runaway Jobs

\`\`\`bash
# Check for long-running jobs
kubectl logs -f deployment/agent-worker --tail=100 | grep "job_processing"

# Look for jobs running >60 seconds
redis-cli KEYS "job:*" | while read key; do
  redis-cli GET $key | jq 'select(.status=="processing") | select(.started_at < (now - 60))'
done
\`\`\`

## Step 2: Kill Runaway Jobs

\`\`\`bash
# Kill specific job
redis-cli DEL "job:abc-123-def"

# Kill all processing jobs older than 5 minutes
python scripts/kill_stale_jobs.py --age 300
\`\`\`

## Step 3: Check for Patterns

\`\`\`bash
# What messages trigger runaway?
grep "job_processing" logs/*.log | grep -A 5 "started_at" | grep "message"

# Which tools are being called repeatedly?
grep "tool_use" logs/*.log | sort | uniq -c | sort -rn
\`\`\`

## Step 4: Implement Circuit Breaker

\`\`\`bash
# Temporarily disable problematic tool
kubectl set env deployment/agent-worker DISABLE_SEARCH_TOOL=true

# Or reduce max turns
kubectl set env deployment/agent-worker MAX_TURNS=5
\`\`\`

## Step 5: Monitor Recovery

\`\`\`bash
# Watch error rate decrease
watch -n 5 'curl -s localhost:9090/api/v1/query?query=rate(agent_errors_total[5m]) | jq'

# Watch queue drain
watch -n 5 'redis-cli LLEN queue:priority:1'
\`\`\`
\`\`\`

### Debugging Tools

```python
# code-examples/chapter-10-incident-response/debugging/debug_tools.py

import redis
import json
from datetime import datetime, timedelta
import structlog

logger = structlog.get_logger()


class DebugTools:
    """Tools for debugging production incidents."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    def find_stale_jobs(self, max_age_seconds: int = 300):
        """
        Find jobs that have been processing for too long.

        Args:
            max_age_seconds: Max allowed processing time

        Returns:
            List of stale job IDs
        """
        stale_jobs = []
        cutoff_time = datetime.utcnow() - timedelta(seconds=max_age_seconds)

        # Get all job keys
        for key in self.redis.scan_iter("job:*"):
            job_data = self.redis.get(key)
            if not job_data:
                continue

            job = json.loads(job_data)

            # Check if stuck in processing
            if job.get("status") == "processing":
                started_at = datetime.fromisoformat(job["started_at"])

                if started_at < cutoff_time:
                    stale_jobs.append({
                        "job_id": job["job_id"],
                        "user_id": job["user_id"],
                        "message": job["message"][:100],
                        "started_at": job["started_at"],
                        "age_seconds": (datetime.utcnow() - started_at).total_seconds(),
                    })

        logger.info("stale_jobs_found", count=len(stale_jobs))
        return stale_jobs

    def kill_stale_jobs(self, max_age_seconds: int = 300):
        """
        Kill jobs stuck in processing.
        """
        stale_jobs = self.find_stale_jobs(max_age_seconds)

        for job_info in stale_jobs:
            job_id = job_info["job_id"]

            # Mark job as failed
            job_data = self.redis.get(f"job:{job_id}")
            if job_data:
                job = json.loads(job_data)
                job["status"] = "failed"
                job["error"] = f"Killed: Processing timeout ({max_age_seconds}s)"
                job["failed_at"] = datetime.utcnow().isoformat()

                self.redis.set(f"job:{job_id}", json.dumps(job), ex=3600)

                logger.warning(
                    "stale_job_killed",
                    job_id=job_id,
                    age_seconds=job_info["age_seconds"],
                )

        return len(stale_jobs)

    def analyze_conversation(self, conversation_id: str):
        """
        Analyze a conversation for debugging.

        Returns insights about token usage, tool calls, etc.
        """
        conv_key = f"conv:{conversation_id}"
        history = self.redis.get(conv_key)

        if not history:
            return {"error": "Conversation not found"}

        messages = json.loads(history)

        # Analyze conversation
        analysis = {
            "total_messages": len(messages),
            "user_messages": sum(1 for m in messages if m["role"] == "user"),
            "assistant_messages": sum(1 for m in messages if m["role"] == "assistant"),
            "estimated_tokens": sum(len(m.get("content", "").split()) * 1.3 for m in messages),
            "sample_messages": messages[-5:],  # Last 5 messages
        }

        return analysis

    def get_error_patterns(self, hours: int = 1):
        """
        Analyze error patterns in logs.

        This is a placeholder - in production you'd query your
        logging system (Datadog, Splunk, etc.)
        """
        # Query logging system for errors
        # Group by error type
        # Return top patterns

        return {
            "total_errors": 145,
            "top_errors": [
                {"type": "APITimeoutError", "count": 78, "percentage": 53.8},
                {"type": "RateLimitError", "count": 45, "percentage": 31.0},
                {"type": "ValidationError", "count": 22, "percentage": 15.2},
            ]
        }


# CLI tool for debugging
if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="Debug production issues")
    parser.add_argument("command", choices=["stale-jobs", "kill-stale", "analyze-conv", "errors"])
    parser.add_argument("--age", type=int, default=300, help="Max age in seconds")
    parser.add_argument("--conv-id", help="Conversation ID to analyze")

    args = parser.parse_args()

    redis_client = redis.Redis(host="localhost", decode_responses=True)
    tools = DebugTools(redis_client)

    if args.command == "stale-jobs":
        jobs = tools.find_stale_jobs(args.age)
        print(f"Found {len(jobs)} stale jobs:")
        for job in jobs:
            print(f"  - {job['job_id']}: {job['age_seconds']}s old")

    elif args.command == "kill-stale":
        count = tools.kill_stale_jobs(args.age)
        print(f"Killed {count} stale jobs")

    elif args.command == "analyze-conv":
        if not args.conv_id:
            print("Error: --conv-id required")
            sys.exit(1)

        analysis = tools.analyze_conversation(args.conv_id)
        print(json.dumps(analysis, indent=2))

    elif args.command == "errors":
        patterns = tools.get_error_patterns()
        print(json.dumps(patterns, indent=2))
```

---

## Rollback Strategies

### When to Rollback

**Rollback if**:
- Error rate >10%
- p95 latency >2x normal
- User-facing bugs
- Data corruption risk
- Can't identify root cause quickly

**Don't rollback if**:
- Minor issue (<1% users)
- Root cause known and fixing
- Fix is faster than rollback
- Rollback would cause data loss

### Rollback Procedures

**1. Kubernetes Rolling Update**:
```bash
# Immediate rollback to previous version
kubectl rollout undo deployment/agent-api -n production

# Rollback to specific revision
kubectl rollout history deployment/agent-api
kubectl rollout undo deployment/agent-api --to-revision=3

# Monitor rollback
kubectl rollout status deployment/agent-api
```

**2. Blue-Green Switch**:
```bash
# Switch from green back to blue
kubectl patch service agent-service -p '{
  "spec": {
    "selector": {
      "version": "blue"
    }
  }
}'

# Verify traffic switched
kubectl get endpoints agent-service
```

**3. Feature Flag Disable**:
```bash
# Disable problematic feature instantly
curl -X POST http://localhost:8000/flags/new_feature/disable

# Verify disabled
curl http://localhost:8000/flags/new_feature
```

**4. Database Rollback**:
```bash
# Rollback database migration (if needed)
python manage.py migrate app_name 0004_previous_migration

# Verify schema
python manage.py showmigrations
```

### Post-Rollback

After rolling back:

1. **Verify recovery**
   - Check error rate (should drop)
   - Check latency (should normalize)
   - Monitor for 15 minutes

2. **Communicate**
   - Update status page
   - Notify stakeholders
   - Post in incident channel

3. **Preserve evidence**
   - Save logs
   - Export metrics
   - Screenshot dashboards

4. **Schedule postmortem**
   - Within 24-48 hours
   - Include all participants

---

## Postmortem Process

### Postmortem Template

```markdown
# Incident Postmortem: [Date] - [Brief Description]

## Meta
- **Date**: 2024-01-15
- **Duration**: 37 minutes (03:12 - 03:49 UTC)
- **Severity**: SEV2
- **Responders**: Alex (primary), Jordan (secondary), Sam (escalation)
- **Status Page**: https://status.company.com/incidents/2024-01-15

## Impact
- **Users affected**: ~3,000 users
- **Failed requests**: 4,500
- **Revenue impact**: ~$2,000
- **SLA breach**: Yes (99.9% → 99.7% for the day)

## Timeline (all times UTC)

| Time | Event |
|------|-------|
| 03:10 | Deployment of v1.5.2 begins (rolling update) |
| 03:12 | Error rate starts increasing (5% → 15%) |
| 03:13 | Alert fires: "High error rate" |
| 03:14 | On-call (Alex) acknowledges alert |
| 03:17 | Alex identifies pattern: auth failures |
| 03:20 | Decision made to rollback |
| 03:22 | Rollback initiated |
| 03:27 | Rollback complete, all pods on v1.5.1 |
| 03:30 | Error rate returning to normal |
| 03:35 | Monitoring for regression |
| 03:49 | Incident resolved, error rate <0.1% |

## Root Cause

**What happened**: Deployment v1.5.2 introduced a bug in authentication middleware.

**Why it happened**:
1. Code change updated JWT validation logic
2. Integration tests didn't cover edge case (expired refresh tokens)
3. Canary deployment was only 5% for 5 minutes (not enough)
4. No alerts fired during canary period (affected <10 users)

**Technical details**:
```python
# Bug in v1.5.2
def validate_token(token):
    # BUG: Crashes on expired refresh tokens
    decoded = jwt.decode(token, verify=True)
    return decoded

# Fix in v1.5.3
def validate_token(token):
    try:
        decoded = jwt.decode(token, verify=True)
        return decoded
    except jwt.ExpiredSignatureError:
        logger.warning("expired_token")
        return None  # Graceful handling
```

## What Went Well
- ✅ Alert fired quickly (2 minutes after issue started)
- ✅ On-call responded within 3 minutes
- ✅ Rollback decision made decisively (6 minutes)
- ✅ Rollback was fast and effective (5 minutes)
- ✅ Communication was clear

## What Went Wrong
- ❌ Bug not caught in testing
- ❌ Canary period too short
- ❌ No alerts during canary
- ❌ Integration tests incomplete

## Action Items

| Action | Owner | Due Date | Priority |
|--------|-------|----------|----------|
| Add integration test for expired tokens | Jordan | 2024-01-17 | P0 |
| Extend canary period to 30 minutes | Sam | 2024-01-16 | P0 |
| Add canary-specific alerts | Alex | 2024-01-18 | P1 |
| Review all auth edge cases | Team | 2024-01-22 | P1 |
| Update runbook with auth debugging | Alex | 2024-01-19 | P2 |

## Lessons Learned
1. **Testing**: Integration tests must cover edge cases
2. **Canary**: 5 minutes is too short, need 30+ minutes
3. **Monitoring**: Need alerts during canary period
4. **Rollback**: Fast rollback prevented larger impact

---

**Postmortem prepared by**: Alex
**Reviewed by**: Jordan, Sam, Engineering Manager
**Date**: 2024-01-16
```

### Blameless Culture

**Don't**: Blame individuals
**Do**: Fix systems

**Bad**:
> "Alex deployed broken code and caused an outage."

**Good**:
> "Our testing process didn't catch this edge case. We're adding tests and extending canary period."

**Key principle**: Humans make mistakes. Systems should prevent those mistakes from causing incidents.

---

## Runbooks

### Runbook Template

```markdown
# Runbook: High Error Rate

## When to Use
- Error rate >5%
- Alert: "AgentHighErrorRate"

## Severity Assessment
- >10% error rate: SEV1 (page immediately)
- 5-10% error rate: SEV2 (investigate urgently)
- 1-5% error rate: SEV3 (investigate during business hours)

## Diagnostic Steps

### Step 1: Check Recent Changes
\`\`\`bash
# Check recent deployments
kubectl rollout history deployment/agent-api

# Check recent config changes
kubectl get configmap agent-config -o yaml | grep -A 20 "data:"

# Check recent feature flag changes
redis-cli KEYS "flag:*" | while read key; do
  echo "$key: $(redis-cli GET $key)"
done
\`\`\`

### Step 2: Check Error Patterns
\`\`\`bash
# View recent errors in logs
kubectl logs deployment/agent-api --tail=100 | grep ERROR

# Group by error type
kubectl logs deployment/agent-api --tail=1000 | \
  grep ERROR | \
  cut -d' ' -f5- | \
  sort | uniq -c | sort -rn

# Common patterns:
# - APITimeoutError: Claude API slow/down
# - RateLimitError: Hitting rate limits
# - ValidationError: Bad input data
# - ConnectionError: Redis/database down
\`\`\`

### Step 3: Check Dependencies
\`\`\`bash
# Check Claude API status
curl -I https://api.anthropic.com/

# Check Redis
redis-cli ping

# Check database
kubectl exec -it deployment/agent-api -- python -c "
import redis
import psycopg2
redis.Redis(host='redis-service').ping()
psycopg2.connect('postgresql://...').cursor().execute('SELECT 1')
print('All dependencies healthy')
"
\`\`\`

## Mitigation Options

### Option 1: Rollback (if recent deployment)
\`\`\`bash
# Rollback to previous version
kubectl rollout undo deployment/agent-api

# Monitor recovery
watch -n 5 'kubectl get pods'
\`\`\`

### Option 2: Scale Up (if resource exhaustion)
\`\`\`bash
# Scale up workers
kubectl scale deployment/agent-worker --replicas=20

# Monitor queue depth
watch -n 5 'redis-cli LLEN queue:priority:1'
\`\`\`

### Option 3: Disable Feature (if feature flag issue)
\`\`\`bash
# Disable problematic feature
curl -X POST http://localhost:8000/flags/FEATURE_NAME/disable

# Verify disabled
curl http://localhost:8000/flags/FEATURE_NAME
\`\`\`

### Option 4: Circuit Breaker (if external API down)
\`\`\`bash
# Enable circuit breaker for problematic service
kubectl set env deployment/agent-api CIRCUIT_BREAKER_SEARCH=open
\`\`\`

## Escalation
If error rate doesn't improve within 15 minutes:
1. Page secondary on-call
2. Post in #engineering-urgent
3. Escalate to engineering manager

## Post-Incident
- Update status page
- Schedule postmortem
- Document in incident log
```

### Common Runbooks

Production runbooks to create:

1. **High Error Rate**: Troubleshoot elevated errors
2. **High Latency**: Debug slow responses
3. **Queue Depth Growing**: Handle backlog
4. **Database Issues**: Connection/query problems
5. **Redis Down**: Handle cache failure
6. **API Rate Limits**: Handle rate limiting
7. **Memory Leak**: Identify and fix leaks
8. **Deployment Rollback**: Safe rollback procedure
9. **Certificate Expiry**: Renew certificates
10. **Disk Space Full**: Clean up disk

---

## Incident Response Checklist

During an incident:

### Detection (0-5 minutes)
- [ ] Alert received and acknowledged
- [ ] Severity assessed (SEV1-4)
- [ ] Dashboard opened
- [ ] Recent changes checked

### Mitigation (5-15 minutes)
- [ ] Obvious fix attempted (rollback, scale, etc.)
- [ ] Mitigation confirmed working
- [ ] OR escalation triggered

### Communication (continuous)
- [ ] Status page updated
- [ ] Incident channel created/updated
- [ ] Stakeholders notified
- [ ] Regular updates posted (every 15-30 min)

### Resolution (variable)
- [ ] Root cause identified
- [ ] Permanent fix deployed
- [ ] Monitoring confirms resolution
- [ ] Incident declared resolved

### Follow-up (24-48 hours)
- [ ] Postmortem scheduled
- [ ] Action items created
- [ ] Runbooks updated
- [ ] Lessons shared with team

---

## Key Takeaways

1. **Be prepared**: Runbooks, tools, and processes before incidents
2. **Stay calm**: Follow the runbook, don't improvise
3. **Mitigate first**: Fix it fast, understand it later
4. **Communicate clearly**: Keep stakeholders informed
5. **Learn from incidents**: Blameless postmortems
6. **Improve continuously**: Every incident makes you better
7. **Practice**: Run incident simulations regularly

**Production wisdom**: "Hope is not a strategy. Preparation is."

---

## Part III: Complete! 🎉

You've completed **Part III: Operations and Deployment**:

✅ **Chapter 8**: Testing Production Systems
✅ **Chapter 9**: Deployment Patterns
✅ **Chapter 10**: Incident Response

Your production agent systems are now:
- **Reliable** (Chapters 2, 8)
- **Observable** (Chapter 3)
- **Secure** (Chapter 4)
- **Cost-effective** (Chapter 5)
- **Scalable** (Chapter 6)
- **Fast** (Chapter 7)
- **Well-tested** (Chapter 8)
- **Safely deployed** (Chapter 9)
- **Incident-ready** (Chapter 10)

**Next**: Part IV: Advanced Topics (Multi-region deployment, Agent platforms)
