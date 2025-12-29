# Monitoring and Observability Guide

Comprehensive monitoring stack for production AI agent systems using Prometheus, Grafana, and Loki.

## Overview

This monitoring setup provides full observability with the **three pillars**:
- **Metrics** (Prometheus): Request rates, latency, errors, token usage, costs
- **Logs** (Loki + Promtail): Structured logs with correlation IDs
- **Traces** (Optional: Tempo): Distributed tracing across services

## What's Monitored

### Agent Metrics
- Request rate and throughput
- Error rates by type
- Latency percentiles (P50, P95, P99)
- Token usage and costs
- Circuit breaker status
- Retry rates
- API health (Anthropic API)

### System Metrics
- CPU and memory usage
- Disk I/O and space
- Network traffic
- Container metrics

### Redis Metrics
- Cache hit/miss rates
- Memory usage
- Command rates
- Slow queries
- Connection counts

## Quick Start

### Using Docker Compose

The monitoring stack is already included in `../docker/docker-compose.yml`:

```bash
cd ../docker
docker-compose up -d

# Access services
open http://localhost:3000  # Grafana (admin/admin)
open http://localhost:9090  # Prometheus
open http://localhost:3100  # Loki
```

### Using Kubernetes

```bash
# Install Prometheus Operator
kubectl apply -f https://raw.githubusercontent.com/prometheus-operator/prometheus-operator/main/bundle.yaml

# Deploy monitoring stack
kubectl apply -f prometheus-operator.yaml

# Access Grafana
kubectl port-forward -n monitoring svc/grafana 3000:3000
```

## Grafana Dashboards

### Available Dashboards

1. **Agent Overview** (`agent-overview.json`)
   - High-level health and performance
   - Request rates, errors, latency
   - Token usage and costs
   - Resource utilization

2. **Cost Monitoring** (create as needed)
   - Token usage breakdown
   - Cost by endpoint
   - Budget alerts
   - Cost projections

3. **Redis Performance** (create as needed)
   - Cache hit rates
   - Memory usage
   - Command throughput
   - Slow query log

### Importing Dashboards

#### Automatic (Docker Compose)

Dashboards are auto-loaded from the `grafana/dashboards/` directory.

#### Manual Import

1. Open Grafana: http://localhost:3000
2. Login (admin/admin)
3. Navigate to Dashboards → Import
4. Upload JSON file or paste JSON
5. Select data source (Prometheus)
6. Click Import

### Customizing Dashboards

Edit JSON files in `grafana/dashboards/` or:

1. Edit dashboard in Grafana UI
2. Click Save → Export
3. Copy JSON
4. Save to `grafana/dashboards/your-dashboard.json`
5. Restart Grafana to load changes

## Prometheus Configuration

### Scrape Targets

Configured in `prometheus/prometheus.yml`:

- **agent**: Agent metrics on port 8000
- **redis**: Redis metrics via redis_exporter
- **node-exporter**: System metrics
- **cadvisor**: Container metrics

### Alert Rules

Configured in `prometheus/alerts.yml`:

#### Critical Alerts (page on-call)
- Agent down
- High error rate (> 5%)
- Daily budget exceeded
- Redis down

#### Warning Alerts (create ticket)
- High latency (P95 > 30s)
- High token usage
- Circuit breaker open
- Low cache hit rate

#### Info Alerts (log only)
- Low request rate
- Content moderation spike

### Recording Rules

Pre-computed metrics in `prometheus/recording_rules.yml`:

- Request rates (5m, 1h)
- Error ratios
- Latency percentiles
- Token usage rates
- Cost projections
- SLO metrics

### Viewing Alerts

```bash
# In Prometheus UI
open http://localhost:9090/alerts

# Query firing alerts
curl http://localhost:9090/api/v1/alerts | jq '.data.alerts[] | select(.state=="firing")'
```

## Log Aggregation

### Loki + Promtail

Promtail collects logs and sends to Loki for aggregation.

### Log Format

Use **structured logging** (JSON) for best results:

```json
{
  "timestamp": "2025-12-29T10:30:00Z",
  "level": "INFO",
  "message": "Request completed",
  "request_id": "req_abc123",
  "user_id": "user_456",
  "duration_ms": 1250,
  "tokens": 450,
  "cost_dollars": 0.015,
  "status": "success"
}
```

### Querying Logs

In Grafana:

1. Go to Explore
2. Select **Loki** data source
3. Query examples:

```logql
# All agent logs
{job="agent"}

# Error logs only
{job="agent"} |= "ERROR"

# Logs for specific request
{job="agent"} | json | request_id="req_abc123"

# Logs with high costs
{job="agent"} | json | cost_dollars > 1.0

# Error rate
rate({job="agent"} |= "ERROR"[5m])
```

## Alerting

### Alertmanager (Optional)

Configure alert routing in Alertmanager:

```yaml
route:
  receiver: 'slack'
  group_by: ['alertname', 'severity']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  routes:
    - match:
        severity: critical
      receiver: 'pagerduty'
    - match:
        severity: warning
      receiver: 'slack'

receivers:
  - name: 'slack'
    slack_configs:
      - api_url: 'YOUR_SLACK_WEBHOOK_URL'
        channel: '#alerts'

  - name: 'pagerduty'
    pagerduty_configs:
      - service_key: 'YOUR_PAGERDUTY_KEY'
```

### Testing Alerts

```bash
# Trigger high error rate alert
# (Simulate errors in your agent)

# View firing alerts in Prometheus
open http://localhost:9090/alerts

# View alert history
curl http://localhost:9090/api/v1/query?query=ALERTS
```

## Metrics Reference

### Agent Metrics

```promql
# Request metrics
agent_requests_total              # Total requests (counter)
agent_errors_total                # Total errors (counter)
agent_request_duration_seconds    # Request latency (histogram)

# Token and cost metrics
agent_tokens_used_total           # Total tokens used (counter)
agent_cost_dollars_total          # Total cost in dollars (counter)

# Resilience metrics
agent_retries_total               # Retry count (counter)
agent_circuit_breaker_state       # Circuit breaker state (gauge)
agent_circuit_breaker_trips_total # Circuit breaker trips (counter)
agent_timeouts_total              # Timeout count (counter)

# API metrics
agent_anthropic_api_requests_total # Anthropic API requests (counter)
agent_anthropic_api_errors_total   # Anthropic API errors (counter)
agent_anthropic_api_duration_seconds # Anthropic API latency (histogram)

# Security metrics
agent_prompt_injection_blocked_total # Prompt injection attempts (counter)
agent_content_moderated_total        # Content moderation (counter)
```

### Redis Metrics

```promql
redis_up                          # Redis up (gauge)
redis_memory_used_bytes           # Memory usage (gauge)
redis_commands_processed_total    # Commands processed (counter)
redis_keyspace_hits_total         # Cache hits (counter)
redis_keyspace_misses_total       # Cache misses (counter)
redis_slowlog_length              # Slow query count (gauge)
```

### System Metrics

```promql
node_cpu_seconds_total            # CPU usage (counter)
node_memory_MemAvailable_bytes    # Available memory (gauge)
node_filesystem_free_bytes        # Free disk space (gauge)
node_network_receive_bytes_total  # Network RX (counter)
```

## Performance Tuning

### Prometheus

```yaml
# Reduce retention for less disk usage
storage:
  tsdb:
    retention:
      time: 15d    # Keep data for 15 days instead of 30d
      size: 20GB   # Or limit by size

# Reduce scrape frequency
global:
  scrape_interval: 30s   # Instead of 15s
```

### Grafana

```ini
# In grafana.ini
[dashboards]
min_refresh_interval = 30s   # Prevent rapid refreshes

[dataproxy]
timeout = 60                 # Query timeout
```

### Loki

```yaml
# Limit log retention
limits_config:
  retention_period: 168h  # 7 days

# Limit per-stream rate
ingestion_rate_mb: 4
ingestion_burst_size_mb: 6
```

## Troubleshooting

### Prometheus Not Scraping

```bash
# Check targets
open http://localhost:9090/targets

# Check agent metrics endpoint
curl http://localhost:8000/metrics

# Check Prometheus logs
docker logs prometheus

# Common issues:
# 1. Wrong port in prometheus.yml
# 2. Agent not exposing /metrics
# 3. Network policy blocking access
```

### Grafana Dashboard Empty

```bash
# Check data source
# Grafana → Configuration → Data Sources → Test

# Check Prometheus has data
curl 'http://localhost:9090/api/v1/query?query=up'

# Check time range in dashboard

# Common issues:
# 1. Wrong data source selected
# 2. No data in time range
# 3. Wrong metric names in queries
```

### Logs Not Showing in Loki

```bash
# Check Promtail is running
docker ps | grep promtail

# Check Promtail logs
docker logs promtail

# Test Loki API
curl http://localhost:3100/ready

# Query Loki directly
curl 'http://localhost:3100/loki/api/v1/query?query={job="agent"}'

# Common issues:
# 1. Log path incorrect in promtail-config.yml
# 2. Logs not in JSON format
# 3. Promtail can't read log files (permissions)
```

### High Memory Usage

```bash
# Check Prometheus memory
docker stats prometheus

# Reduce cardinality (fewer label combinations)
# Reduce retention time
# Increase memory limit

# Check Grafana memory
docker stats grafana

# Reduce dashboard refresh rate
# Reduce time range in queries
```

## Cost Optimization

### Monitor These Costs

1. **Token usage**: Primary cost driver
2. **Storage**: Prometheus + Loki data
3. **Compute**: Agent CPU/memory

### Cost Dashboards

Create dashboard panels for:

```promql
# Hourly cost rate
rate(agent_cost_dollars_total[1h])

# Daily cost
increase(agent_cost_dollars_total[24h])

# Monthly projection
rate(agent_cost_dollars_total[1h]) * 24 * 30

# Cost per request
rate(agent_cost_dollars_total[5m]) / rate(agent_requests_total[5m])

# Tokens per request
rate(agent_tokens_used_total[5m]) / rate(agent_requests_total[5m])
```

### Cost Alerts

Set up alerts when:
- Daily budget exceeded
- Cost spike (> 2x average)
- Tokens per request too high

## Production Best Practices

### Monitoring Checklist

- [ ] All metrics endpoints exposed
- [ ] Structured logging enabled
- [ ] Alerts configured and tested
- [ ] Dashboards created for key metrics
- [ ] Alert routing configured (Slack, PagerDuty)
- [ ] On-call runbooks created
- [ ] Log retention policy set
- [ ] Metrics retention policy set
- [ ] Backup strategy for dashboards
- [ ] Cost monitoring enabled
- [ ] SLO dashboards created

### Retention Policies

- **Metrics**: 30 days (or 15 days for cost savings)
- **Logs**: 7 days (increase if needed for compliance)
- **Traces**: 7 days (if using Tempo)

### Alert Fatigue Prevention

1. Set appropriate thresholds
2. Use `for:` duration to avoid flapping
3. Group related alerts
4. Use different severity levels
5. Review and tune alerts weekly

## Next Steps

- Set up Alertmanager for alert routing
- Configure distributed tracing with Tempo
- Create custom dashboards for your use case
- Set up remote write for long-term storage (Cortex, Thanos)
- Implement SLO dashboards
- Set up anomaly detection

## Related Documentation

- [Docker Deployment](../docker/README.md)
- [Kubernetes Deployment](../kubernetes/README.md)
- [Observability Chapter](../../chapters/03-observability-debugging.md)
- [Incident Response](../../chapters/10-incident-response.md)
