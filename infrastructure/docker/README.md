# Docker Deployment Guide

Production-ready Docker deployment for AI agent systems with full observability stack.

## What's Included

This Docker setup provides:

- **Agent Service**: Your AI agent running in a secure container
- **Redis**: State management and caching
- **Prometheus**: Metrics collection and alerting
- **Grafana**: Metrics visualization with pre-configured dashboards
- **Loki**: Log aggregation
- **Promtail**: Log collection and forwarding
- **Node Exporter**: Host system metrics (optional)

## Quick Start

### Prerequisites

- Docker 20.10+ and Docker Compose 2.0+
- Anthropic API key
- 4GB+ RAM available
- 10GB+ disk space

### 1. Clone and Configure

```bash
cd infrastructure/docker

# Copy environment template
cp .env.example .env

# Edit .env and add your API key
nano .env
```

### 2. Launch the Stack

```bash
# Development (with logs)
docker-compose up

# Production (detached)
docker-compose up -d
```

### 3. Access Services

- **Agent Metrics**: http://localhost:8000/metrics
- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **Loki**: http://localhost:3100

### 4. Verify Deployment

```bash
# Check all services are running
docker-compose ps

# View agent logs
docker-compose logs -f agent

# Check health status
curl http://localhost:8000/health
```

## Production Deployment

### Security Checklist

Before deploying to production:

- [ ] Change default Grafana password
- [ ] Enable Redis password authentication
- [ ] Use secrets management (not .env files)
- [ ] Enable TLS/HTTPS on all endpoints
- [ ] Configure firewall rules
- [ ] Set up log rotation
- [ ] Enable audit logging
- [ ] Review resource limits
- [ ] Scan images for vulnerabilities

### Using Docker Secrets

For production, use Docker secrets instead of environment variables:

```bash
# Create secrets
echo "your_api_key" | docker secret create anthropic_api_key -
echo "secure_grafana_password" | docker secret create grafana_password -

# Update docker-compose.yml to use secrets
# See: docker-compose.production.yml example
```

### Resource Limits

Adjust resource limits in `docker-compose.yml` based on your workload:

```yaml
deploy:
  resources:
    limits:
      cpus: '4'        # Increase for higher concurrency
      memory: 4G       # Increase for larger models/context
    reservations:
      cpus: '2'
      memory: 2G
```

## Monitoring

### Viewing Metrics

1. Open Grafana: http://localhost:3000
2. Navigate to Dashboards → Agent Monitoring
3. View real-time metrics:
   - Request rate and latency
   - Token usage and costs
   - Error rates and types
   - Circuit breaker status
   - Redis cache hit rates

### Setting Up Alerts

Edit `../monitoring/prometheus/alerts.yml` to configure alerts:

```yaml
- alert: HighErrorRate
  expr: rate(agent_errors_total[5m]) > 0.05
  for: 5m
  annotations:
    summary: "High error rate detected"
```

### Log Analysis

View logs in Grafana:
1. Go to Explore
2. Select Loki data source
3. Query: `{container="production-agent"}`

## Operations

### Scaling

Scale the agent horizontally:

```bash
# Run 3 agent instances
docker-compose up -d --scale agent=3

# Note: You'll need a load balancer in front
```

### Updating

Zero-downtime updates:

```bash
# Pull new image
docker-compose pull agent

# Rolling update
docker-compose up -d --no-deps --scale agent=2 agent
docker-compose up -d --no-deps --scale agent=1 agent
```

### Backup

Backup persistent data:

```bash
# Backup script
docker run --rm \
  -v agent-data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar czf /backup/agent-data-$(date +%Y%m%d).tar.gz /data
```

### Health Checks

The agent container includes a health check:

```bash
# Check health status
docker inspect --format='{{.State.Health.Status}}' production-agent

# View health check logs
docker inspect --format='{{range .State.Health.Log}}{{.Output}}{{end}}' production-agent
```

## Troubleshooting

### Agent Won't Start

```bash
# Check logs
docker-compose logs agent

# Common issues:
# 1. Invalid API key → Check .env file
# 2. Port conflict → Change port in docker-compose.yml
# 3. Out of memory → Increase memory limit
```

### High Memory Usage

```bash
# Check resource usage
docker stats

# View agent memory details
docker exec production-agent ps aux

# Reduce memory:
# - Lower agent concurrency
# - Reduce Redis maxmemory
# - Enable swap (not recommended for production)
```

### Metrics Not Showing in Grafana

```bash
# Check Prometheus targets
curl http://localhost:9090/api/v1/targets

# Verify agent is exposing metrics
curl http://localhost:8000/metrics

# Check Grafana data source
# Grafana → Configuration → Data Sources → Prometheus
```

### Redis Connection Issues

```bash
# Test Redis connectivity
docker exec -it agent-redis redis-cli ping

# Check Redis logs
docker-compose logs redis

# Verify agent can connect
docker exec production-agent nc -zv redis 6379
```

## Advanced Configuration

### Custom Prometheus Scrape Configs

Edit `../monitoring/prometheus/prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'agent'
    static_configs:
      - targets: ['agent:8000']
    scrape_interval: 15s
```

### Custom Grafana Dashboards

Add dashboards to `../monitoring/grafana/dashboards/`:

```bash
# Export dashboard from Grafana UI
# Save as JSON
# Place in dashboards directory
# Restart Grafana to load
```

### Log Retention

Configure Loki retention in `loki-config.yaml`:

```yaml
limits_config:
  retention_period: 168h  # 7 days
```

## Performance Tuning

### For High Throughput

```yaml
# In docker-compose.yml
services:
  agent:
    deploy:
      resources:
        limits:
          cpus: '8'
          memory: 8G
    environment:
      - AGENT_WORKERS=8
      - REDIS_POOL_SIZE=20
```

### For Low Latency

```yaml
services:
  redis:
    command: redis-server --maxmemory 1gb --maxmemory-policy allkeys-lru
```

## Security Best Practices

1. **Run as non-root**: Already configured in Dockerfile
2. **Read-only filesystem**: Enable if agent doesn't need writes
3. **Drop capabilities**: Remove unnecessary Linux capabilities
4. **Network isolation**: Use custom networks
5. **Secrets management**: Use Docker secrets or vault
6. **Image scanning**: Scan with Trivy or Clair
7. **Limit resources**: Prevent DoS from resource exhaustion

## Cost Optimization

Monitor costs in Grafana:
- Token usage dashboard
- API call frequency
- Cache hit rates

Tips:
- Enable Redis caching for repeated queries
- Use prompt caching (see agent configuration)
- Set token budgets per request
- Monitor and alert on cost spikes

## Next Steps

- Configure alerts (see `../monitoring/prometheus/alerts.yml`)
- Set up log rotation
- Configure backups
- Set up TLS certificates
- Deploy to production cluster
- Configure auto-scaling (see `../kubernetes/`)

## Related Documentation

- [Kubernetes Deployment](../kubernetes/README.md)
- [Monitoring Guide](../monitoring/README.md)
- [Security Checklist](../../docs/security-checklist.md)
- [Production Readiness](../../docs/production-readiness.md)
