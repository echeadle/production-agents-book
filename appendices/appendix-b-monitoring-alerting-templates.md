# Appendix B: Monitoring and Alerting Templates

Complete templates for monitoring and alerting your AI agent system.

## Overview

This appendix provides copy-paste templates for:
- Prometheus alert rules
- Grafana dashboard JSON
- Prometheus recording rules
- Alert notification templates
- SLO definitions

---

## 1. Prometheus Alert Rules

### Critical Alerts (Page On-Call)

```yaml
# alerts/critical.yml
groups:
  - name: critical_alerts
    interval: 30s
    rules:
      # Agent is down
      - alert: AgentDown
        expr: up{job="agent"} == 0
        for: 1m
        labels:
          severity: critical
          component: agent
          team: platform
        annotations:
          summary: "Agent instance {{ $labels.instance }} is down"
          description: |
            Agent has been down for more than 1 minute.

            Impact: Users cannot make requests

            Runbook: https://wiki.example.com/runbooks/agent-down

            Steps:
            1. Check pod status: kubectl get pods -n production-agents
            2. Check logs: kubectl logs -f deployment/agent-deployment
            3. Check recent deployments: kubectl rollout history deployment/agent-deployment
          dashboard: "https://grafana.example.com/d/agent-overview"

      # High error rate
      - alert: HighErrorRate
        expr: |
          (
            rate(agent_errors_total[5m])
            /
            rate(agent_requests_total[5m])
          ) > 0.05
        for: 5m
        labels:
          severity: critical
          component: agent
          team: platform
        annotations:
          summary: "High error rate: {{ $value | humanizePercentage }}"
          description: |
            Error rate is {{ $value | humanizePercentage }} (threshold: 5%)

            Current error rate: {{ $value | humanizePercentage }}
            Request rate: {{ printf "%.2f" (rate(agent_requests_total[5m])) }}/s
            Error count: {{ printf "%.0f" (rate(agent_errors_total[5m]) * 300) }} in last 5min

            Impact: Users experiencing failures

            Runbook: https://wiki.example.com/runbooks/high-error-rate

      # Very high latency
      - alert: VeryHighLatency
        expr: |
          histogram_quantile(0.99,
            rate(agent_request_duration_seconds_bucket[5m])
          ) > 60
        for: 2m
        labels:
          severity: critical
          component: agent
        annotations:
          summary: "Very high latency: P99 {{ $value }}s"
          description: |
            P99 latency is {{ printf "%.2f" $value }}s (threshold: 60s)

            Current latencies:
            - P50: {{ printf "%.2f" (histogram_quantile(0.50, rate(agent_request_duration_seconds_bucket[5m]))) }}s
            - P95: {{ printf "%.2f" (histogram_quantile(0.95, rate(agent_request_duration_seconds_bucket[5m]))) }}s
            - P99: {{ printf "%.2f" $value }}s

            Impact: Severe user experience degradation

            Runbook: https://wiki.example.com/runbooks/high-latency

      # Daily budget exceeded
      - alert: DailyBudgetExceeded
        expr: |
          sum(increase(agent_tokens_used_total[24h])) > 10000000
        labels:
          severity: critical
          component: cost
          team: platform
        annotations:
          summary: "Daily token budget exceeded"
          description: |
            Used {{ $value }} tokens in last 24h (budget: 10M)

            Current cost: ${{ printf "%.2f" (sum(increase(agent_cost_dollars_total[24h]))) }}
            Projected monthly: ${{ printf "%.2f" (sum(increase(agent_cost_dollars_total[24h])) * 30) }}

            Impact: Budget overrun

            Action: Review token usage, enable rate limiting

      # Redis down
      - alert: RedisDown
        expr: up{job="redis"} == 0
        for: 1m
        labels:
          severity: critical
          component: redis
        annotations:
          summary: "Redis is down"
          description: |
            Redis has been down for more than 1 minute

            Impact: Agent cannot cache or maintain state

            Runbook: https://wiki.example.com/runbooks/redis-down

      # Anthropic API high error rate
      - alert: AnthropicAPIHighErrorRate
        expr: |
          (
            rate(agent_anthropic_api_errors_total[5m])
            /
            rate(agent_anthropic_api_requests_total[5m])
          ) > 0.1
        for: 5m
        labels:
          severity: critical
          component: external_api
        annotations:
          summary: "Anthropic API error rate: {{ $value | humanizePercentage }}"
          description: |
            More than 10% of Anthropic API calls are failing

            Error rate: {{ $value | humanizePercentage }}

            Check:
            - Anthropic status: https://status.anthropic.com
            - API key validity
            - Rate limits

            Runbook: https://wiki.example.com/runbooks/api-errors
```

### Warning Alerts (Create Ticket)

```yaml
# alerts/warning.yml
groups:
  - name: warning_alerts
    interval: 1m
    rules:
      # Elevated error rate
      - alert: ElevatedErrorRate
        expr: |
          (
            rate(agent_errors_total[5m])
            /
            rate(agent_requests_total[5m])
          ) > 0.01
        for: 10m
        labels:
          severity: warning
          component: agent
        annotations:
          summary: "Elevated error rate: {{ $value | humanizePercentage }}"
          description: "Error rate above 1% for 10 minutes"

      # High latency
      - alert: HighLatency
        expr: |
          histogram_quantile(0.95,
            rate(agent_request_duration_seconds_bucket[5m])
          ) > 30
        for: 5m
        labels:
          severity: warning
          component: agent
        annotations:
          summary: "High latency: P95 {{ $value }}s"
          description: "P95 latency above 30s"

      # Circuit breaker open
      - alert: CircuitBreakerOpen
        expr: agent_circuit_breaker_state{state="open"} == 1
        for: 2m
        labels:
          severity: warning
          component: resilience
        annotations:
          summary: "Circuit breaker open: {{ $labels.circuit }}"
          description: |
            Circuit breaker has been open for 2 minutes
            Circuit: {{ $labels.circuit }}
            Requests are being rejected

      # High retry rate
      - alert: HighRetryRate
        expr: |
          (
            rate(agent_retries_total[5m])
            /
            rate(agent_requests_total[5m])
          ) > 0.2
        for: 5m
        labels:
          severity: warning
          component: resilience
        annotations:
          summary: "High retry rate: {{ $value | humanizePercentage }}"
          description: "More than 20% of requests are being retried"

      # High token usage
      - alert: HighTokenUsage
        expr: rate(agent_tokens_used_total[5m]) > 100000
        for: 5m
        labels:
          severity: warning
          component: cost
        annotations:
          summary: "High token usage: {{ $value }}/s"
          description: |
            Token usage rate is unusually high
            Current rate: {{ printf "%.0f" $value }}/s
            Hourly projection: {{ printf "%.0f" ($value * 3600) }}

      # Redis high memory
      - alert: RedisHighMemory
        expr: |
          redis_memory_used_bytes / redis_memory_max_bytes > 0.9
        for: 5m
        labels:
          severity: warning
          component: redis
        annotations:
          summary: "Redis memory high: {{ $value | humanizePercentage }}"
          description: "Redis using {{ $value | humanizePercentage }} of max memory"

      # Low cache hit rate
      - alert: LowCacheHitRate
        expr: |
          (
            rate(redis_keyspace_hits_total[5m])
            /
            (rate(redis_keyspace_hits_total[5m]) + rate(redis_keyspace_misses_total[5m]))
          ) < 0.5
        for: 10m
        labels:
          severity: warning
          component: redis
        annotations:
          summary: "Low cache hit rate: {{ $value | humanizePercentage }}"
          description: "Cache hit rate below 50%"

      # High CPU usage
      - alert: HighCPUUsage
        expr: |
          rate(container_cpu_usage_seconds_total{pod=~"agent-.*"}[5m]) > 0.8
        for: 10m
        labels:
          severity: warning
          component: resources
        annotations:
          summary: "High CPU on {{ $labels.pod }}: {{ $value | humanizePercentage }}"
          description: "CPU usage above 80% for 10 minutes"

      # High memory usage
      - alert: HighMemoryUsage
        expr: |
          (
            container_memory_working_set_bytes{pod=~"agent-.*"}
            /
            container_spec_memory_limit_bytes{pod=~"agent-.*"}
          ) > 0.9
        for: 5m
        labels:
          severity: warning
          component: resources
        annotations:
          summary: "High memory on {{ $labels.pod }}: {{ $value | humanizePercentage }}"
          description: "Memory usage above 90%, may OOM soon"
```

### Informational Alerts

```yaml
# alerts/info.yml
groups:
  - name: info_alerts
    interval: 5m
    rules:
      # Deployment event
      - alert: DeploymentEvent
        expr: |
          changes(kube_deployment_status_observed_generation{deployment="agent-deployment"}[5m]) > 0
        labels:
          severity: info
          component: deployment
        annotations:
          summary: "Deployment updated"
          description: "Agent deployment configuration changed"

      # Cost spike
      - alert: CostSpike
        expr: |
          (
            rate(agent_cost_dollars_total[5m])
            /
            avg_over_time(rate(agent_cost_dollars_total[5m])[1h:5m])
          ) > 2
        for: 5m
        labels:
          severity: info
          component: cost
        annotations:
          summary: "Cost spike detected"
          description: "Cost rate 2x higher than 1-hour average"

      # Low request rate
      - alert: LowRequestRate
        expr: rate(agent_requests_total[10m]) < 0.1
        for: 15m
        labels:
          severity: info
          component: agent
        annotations:
          summary: "Unusually low request rate"
          description: "Request rate below 0.1 req/s, may indicate upstream issues"
```

---

## 2. Prometheus Recording Rules

```yaml
# recording_rules/agent_metrics.yml
groups:
  - name: agent_request_metrics
    interval: 30s
    rules:
      # Request rates
      - record: job:agent_requests:rate5m
        expr: rate(agent_requests_total[5m])

      - record: job:agent_requests:rate1h
        expr: rate(agent_requests_total[1h])

      # Error metrics
      - record: job:agent_errors:rate5m
        expr: rate(agent_errors_total[5m])

      - record: job:agent_errors:ratio5m
        expr: |
          rate(agent_errors_total[5m])
          /
          rate(agent_requests_total[5m])

      # Latency percentiles
      - record: job:agent_latency:p50
        expr: |
          histogram_quantile(0.50,
            rate(agent_request_duration_seconds_bucket[5m])
          )

      - record: job:agent_latency:p95
        expr: |
          histogram_quantile(0.95,
            rate(agent_request_duration_seconds_bucket[5m])
          )

      - record: job:agent_latency:p99
        expr: |
          histogram_quantile(0.99,
            rate(agent_request_duration_seconds_bucket[5m])
          )

  - name: agent_cost_metrics
    interval: 1m
    rules:
      # Token usage
      - record: job:agent_tokens:rate5m
        expr: rate(agent_tokens_used_total[5m])

      - record: job:agent_tokens_per_request:avg
        expr: |
          rate(agent_tokens_used_total[5m])
          /
          rate(agent_requests_total[5m])

      # Cost metrics
      - record: job:agent_cost:rate5m
        expr: rate(agent_cost_dollars_total[5m])

      - record: job:agent_cost:daily_projection
        expr: rate(agent_cost_dollars_total[1h]) * 24

      - record: job:agent_cost:monthly_projection
        expr: rate(agent_cost_dollars_total[1h]) * 24 * 30

  - name: agent_slo_metrics
    interval: 5m
    rules:
      # Availability
      - record: job:agent_availability:ratio1h
        expr: avg_over_time(up{job="agent"}[1h])

      # Success rate
      - record: job:agent_success:ratio5m
        expr: |
          1 - (
            rate(agent_errors_total[5m])
            /
            rate(agent_requests_total[5m])
          )

      # Error budget (99.9% SLO)
      - record: job:agent_error_budget:burn_rate5m
        expr: |
          (
            rate(agent_errors_total[5m]) / rate(agent_requests_total[5m])
          )
          /
          (1 - 0.999)
```

---

## 3. Grafana Dashboard JSON Template

```json
{
  "dashboard": {
    "title": "AI Agent - Production Dashboard",
    "tags": ["ai-agent", "production"],
    "timezone": "browser",
    "panels": [
      {
        "title": "Request Rate",
        "targets": [{
          "expr": "sum(rate(agent_requests_total[5m]))",
          "legendFormat": "Requests/sec"
        }],
        "type": "graph"
      },
      {
        "title": "Error Rate",
        "targets": [{
          "expr": "sum(rate(agent_errors_total[5m])) / sum(rate(agent_requests_total[5m]))",
          "legendFormat": "Error Rate"
        }],
        "type": "graph",
        "thresholds": [
          {"value": 0.01, "color": "yellow"},
          {"value": 0.05, "color": "red"}
        ]
      },
      {
        "title": "Latency (Percentiles)",
        "targets": [
          {
            "expr": "histogram_quantile(0.50, sum(rate(agent_request_duration_seconds_bucket[5m])) by (le))",
            "legendFormat": "P50"
          },
          {
            "expr": "histogram_quantile(0.95, sum(rate(agent_request_duration_seconds_bucket[5m])) by (le))",
            "legendFormat": "P95"
          },
          {
            "expr": "histogram_quantile(0.99, sum(rate(agent_request_duration_seconds_bucket[5m])) by (le))",
            "legendFormat": "P99"
          }
        ],
        "type": "graph"
      },
      {
        "title": "Token Usage Rate",
        "targets": [{
          "expr": "sum(rate(agent_tokens_used_total[5m]))",
          "legendFormat": "Tokens/sec"
        }],
        "type": "graph"
      },
      {
        "title": "Cost (Last 24h)",
        "targets": [{
          "expr": "sum(increase(agent_cost_dollars_total[24h]))",
          "legendFormat": "Cost"
        }],
        "type": "stat",
        "format": "currencyUSD"
      },
      {
        "title": "Circuit Breaker Status",
        "targets": [{
          "expr": "agent_circuit_breaker_state",
          "legendFormat": "{{circuit}} - {{state}}"
        }],
        "type": "table"
      }
    ]
  }
}
```

---

## 4. Alert Notification Templates

### Slack Notification Template

```yaml
# alertmanager.yml
route:
  receiver: 'slack-critical'
  group_by: ['alertname', 'severity']
  group_wait: 10s
  group_interval: 5m
  repeat_interval: 4h

  routes:
    - match:
        severity: critical
      receiver: 'slack-critical'
    - match:
        severity: warning
      receiver: 'slack-warning'

receivers:
  - name: 'slack-critical'
    slack_configs:
      - api_url: 'YOUR_SLACK_WEBHOOK_URL'
        channel: '#alerts-critical'
        title: '🚨 {{ .GroupLabels.alertname }}'
        text: |
          *Summary:* {{ .CommonAnnotations.summary }}
          *Description:* {{ .CommonAnnotations.description }}
          *Severity:* {{ .CommonLabels.severity }}
          *Component:* {{ .CommonLabels.component }}
          *Dashboard:* {{ .CommonAnnotations.dashboard }}
          *Runbook:* {{ .CommonAnnotations.runbook }}

  - name: 'slack-warning'
    slack_configs:
      - api_url: 'YOUR_SLACK_WEBHOOK_URL'
        channel: '#alerts-warning'
        title: '⚠️ {{ .GroupLabels.alertname }}'
        text: '{{ .CommonAnnotations.summary }}'
```

### PagerDuty Template

```yaml
receivers:
  - name: 'pagerduty-critical'
    pagerduty_configs:
      - service_key: 'YOUR_PAGERDUTY_KEY'
        severity: 'critical'
        description: '{{ .CommonAnnotations.summary }}'
        details:
          summary: '{{ .CommonAnnotations.summary }}'
          description: '{{ .CommonAnnotations.description }}'
          component: '{{ .CommonLabels.component }}'
          runbook: '{{ .CommonAnnotations.runbook }}'
```

---

## 5. SLO Definitions

### Service Level Objectives

```yaml
# SLO Definition Document

slos:
  - name: "Availability SLO"
    objective: 99.9%
    measurement_window: 30d
    error_budget: 0.1%

    indicators:
      - type: availability
        query: 'avg_over_time(up{job="agent"}[30d])'
        target: 0.999

    alerts:
      - name: FastBurn
        expr: 'job:agent_error_budget:burn_rate5m > 14.4'
        for: 5m
        severity: critical

      - name: SlowBurn
        expr: 'job:agent_error_budget:burn_rate1h > 3'
        for: 1h
        severity: warning

  - name: "Latency SLO"
    objective: "P95 < 30s"
    measurement_window: 30d

    indicators:
      - type: latency
        query: 'histogram_quantile(0.95, rate(agent_request_duration_seconds_bucket[5m]))'
        target: 30

    alerts:
      - name: LatencySLOViolation
        expr: 'job:agent_latency:p95 > 30'
        for: 10m
        severity: warning

  - name: "Error Rate SLO"
    objective: "< 1% errors"
    measurement_window: 30d
    error_budget: 1%

    indicators:
      - type: error_rate
        query: 'rate(agent_errors_total[5m]) / rate(agent_requests_total[5m])'
        target: 0.01

    alerts:
      - name: ErrorRateSLOViolation
        expr: 'job:agent_errors:ratio5m > 0.01'
        for: 10m
        severity: warning
```

---

## 6. Quick Reference

### Common Queries

```promql
# Request rate
sum(rate(agent_requests_total[5m]))

# Error rate
sum(rate(agent_errors_total[5m])) / sum(rate(agent_requests_total[5m]))

# P95 latency
histogram_quantile(0.95, rate(agent_request_duration_seconds_bucket[5m]))

# Token usage rate
sum(rate(agent_tokens_used_total[5m]))

# Cost per hour
sum(rate(agent_cost_dollars_total[1h]))

# Cache hit rate
rate(redis_keyspace_hits_total[5m]) / (rate(redis_keyspace_hits_total[5m]) + rate(redis_keyspace_misses_total[5m]))

# Circuit breaker status
agent_circuit_breaker_state{state="open"} == 1

# Pods up
count(up{job="agent"} == 1)

# Error budget remaining (99.9% SLO)
(1 - (sum(increase(agent_errors_total[30d])) / sum(increase(agent_requests_total[30d])))) / 0.001 * 100
```

---

## 7. Implementation Checklist

- [ ] Alert rules deployed to Prometheus
- [ ] Recording rules deployed
- [ ] Alertmanager configured
- [ ] Slack/PagerDuty integration tested
- [ ] Grafana dashboards imported
- [ ] SLOs documented and monitored
- [ ] Runbooks created for each alert
- [ ] On-call team trained
- [ ] Alert thresholds tuned based on baseline
- [ ] Alert fatigue reviewed weekly

---

## Next Steps

1. Copy alert rules to `infrastructure/monitoring/prometheus/alerts.yml`
2. Copy recording rules to `infrastructure/monitoring/prometheus/recording_rules.yml`
3. Import Grafana dashboards
4. Configure Alertmanager with your Slack/PagerDuty credentials
5. Test alerts by triggering test failures
6. Tune thresholds based on your traffic patterns
7. Create runbooks for each critical alert

---

**Last Updated:** 2025-12-29
**Owner:** Platform Team
**Review Cycle:** Quarterly
