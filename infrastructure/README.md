# Infrastructure Guide

Production-ready infrastructure for deploying and operating AI agent systems at scale.

## Overview

This directory contains everything you need to deploy AI agents to production:

- **Docker**: Containerized deployment with full monitoring stack
- **Kubernetes**: Orchestrated deployment with autoscaling and high availability
- **Monitoring**: Prometheus, Grafana, and Loki for full observability
- **Terraform**: Infrastructure as Code (optional, for cloud resources)

## Quick Start

Choose your deployment method:

### 1. Docker Compose (Simplest)

**Best for**: Development, small-scale production, single-server deployments

```bash
cd docker
cp .env.example .env
# Edit .env and add your API key
docker-compose up -d
```

[Full Docker Guide →](docker/README.md)

### 2. Kubernetes (Production)

**Best for**: Production at scale, multi-instance, autoscaling

```bash
cd kubernetes
kubectl create secret generic agent-secrets \
  --from-literal=anthropic-api-key=your_key
kubectl apply -k .
```

[Full Kubernetes Guide →](kubernetes/README.md)

## What's Included

### Docker Setup

- Multi-stage Dockerfile for minimal image size
- Docker Compose with full stack:
  - Agent service
  - Redis (state/cache)
  - Prometheus (metrics)
  - Grafana (visualization)
  - Loki (logs)
  - Promtail (log collection)
- Resource limits and health checks
- Development and production configurations

### Kubernetes Setup

- Production-ready manifests:
  - Deployment with rolling updates
  - Services (ClusterIP, LoadBalancer)
  - ConfigMaps for configuration
  - Secrets for API keys
  - PersistentVolumeClaims for data
  - HorizontalPodAutoscaler for scaling
  - NetworkPolicies for security
  - RBAC (ServiceAccount, Roles)
  - ServiceMonitors for Prometheus
- Redis StatefulSet with persistence
- Kustomize configuration for easy deployment
- Examples for multi-region deployment

### Monitoring Stack

- **Prometheus**: Metrics collection and alerting
  - Scrape configurations for all services
  - Alert rules for critical issues
  - Recording rules for performance
- **Grafana**: Visualization and dashboards
  - Pre-built agent monitoring dashboard
  - Cost tracking dashboard
  - Redis performance dashboard
- **Loki**: Log aggregation
  - Structured log parsing
  - Log-based alerts
  - Correlation with metrics
- **Promtail**: Log collection
  - Docker and Kubernetes support
  - JSON log parsing
  - Label extraction

## Directory Structure

```
infrastructure/
├── README.md                     # This file
├── docker/                       # Docker deployment
│   ├── Dockerfile               # Production Dockerfile
│   ├── docker-compose.yml       # Full stack
│   ├── .dockerignore           # Docker ignore rules
│   ├── .env.example            # Environment template
│   └── README.md               # Docker guide
├── kubernetes/                  # Kubernetes deployment
│   ├── namespace.yaml          # Namespace definition
│   ├── configmap.yaml          # Configuration
│   ├── secret.yaml.template    # Secret template
│   ├── deployment.yaml         # Agent deployment
│   ├── service.yaml            # Services
│   ├── hpa.yaml                # Autoscaling
│   ├── pvc.yaml                # Storage
│   ├── redis-statefulset.yaml  # Redis setup
│   ├── rbac.yaml               # Security
│   ├── networkpolicy.yaml      # Network security
│   ├── servicemonitor.yaml     # Prometheus integration
│   ├── kustomization.yaml      # Kustomize config
│   └── README.md               # Kubernetes guide
├── monitoring/                  # Monitoring stack
│   ├── prometheus/
│   │   ├── prometheus.yml      # Prometheus config
│   │   ├── alerts.yml          # Alert rules
│   │   └── recording_rules.yml # Recording rules
│   ├── grafana/
│   │   ├── datasources.yml     # Data sources
│   │   └── dashboards/         # Dashboard JSONs
│   ├── promtail/
│   │   └── promtail-config.yml # Log collection config
│   └── README.md               # Monitoring guide
└── terraform/                   # IaC (optional)
    └── (cloud-specific configs)
```

## Deployment Paths

### Path 1: Development Environment

```bash
# Use Docker Compose
cd docker
docker-compose up

# Access services
open http://localhost:8000  # Agent metrics
open http://localhost:3000  # Grafana
open http://localhost:9090  # Prometheus
```

### Path 2: Production (Single Server)

```bash
# Use Docker Compose with production settings
cd docker
cp .env.example .env
# Edit .env with production values
docker-compose -f docker-compose.yml up -d

# Set up backups
# Set up monitoring alerts
# Configure log rotation
```

### Path 3: Production (Kubernetes Cluster)

```bash
# Use Kubernetes with autoscaling
cd kubernetes

# Create secrets (don't commit!)
kubectl create secret generic agent-secrets \
  --from-literal=anthropic-api-key=xxx

# Deploy with Kustomize
kubectl apply -k .

# Verify deployment
kubectl get pods -n production-agents
kubectl get hpa -n production-agents

# Access Grafana
kubectl port-forward -n production-agents svc/grafana 3000:3000
```

## Security Checklist

Before deploying to production:

- [ ] API keys stored securely (secrets, not env files)
- [ ] Non-root user in containers
- [ ] Resource limits set
- [ ] Network policies configured
- [ ] RBAC with least privilege
- [ ] Images scanned for vulnerabilities
- [ ] TLS/HTTPS enabled
- [ ] Secrets encrypted at rest
- [ ] Audit logging enabled
- [ ] Security updates automated

## Production Readiness Checklist

- [ ] **Deployment**
  - [ ] Containerized with health checks
  - [ ] Rolling update strategy configured
  - [ ] Resource limits set appropriately
  - [ ] Secrets management configured
  - [ ] Multiple replicas for HA

- [ ] **Monitoring**
  - [ ] Metrics exposed and scraped
  - [ ] Logs aggregated and searchable
  - [ ] Dashboards created
  - [ ] Alerts configured
  - [ ] On-call rotation established

- [ ] **Reliability**
  - [ ] Retry logic implemented
  - [ ] Circuit breakers configured
  - [ ] Timeouts set appropriately
  - [ ] Graceful degradation
  - [ ] Health checks working

- [ ] **Security**
  - [ ] API keys secured
  - [ ] Network policies in place
  - [ ] Input validation enabled
  - [ ] Content moderation active
  - [ ] Audit logging configured

- [ ] **Cost Management**
  - [ ] Token tracking enabled
  - [ ] Budget alerts configured
  - [ ] Cost dashboards created
  - [ ] Cache hit rate monitored
  - [ ] Resource utilization optimized

- [ ] **Operations**
  - [ ] Backup strategy implemented
  - [ ] Rollback procedure tested
  - [ ] Runbooks created
  - [ ] Incident response plan
  - [ ] Change management process

## Architecture Patterns

### Single-Instance (Docker Compose)

```
┌────────────────────────────────┐
│  Docker Host                   │
│  ┌──────────┐  ┌────────────┐ │
│  │  Agent   │──│ Prometheus │ │
│  └──────────┘  └────────────┘ │
│       │        ┌────────────┐ │
│  ┌────────┐   │  Grafana   │ │
│  │ Redis  │   └────────────┘ │
│  └────────┘   ┌────────────┐ │
│               │    Loki    │ │
│               └────────────┘ │
└────────────────────────────────┘
```

### Multi-Instance (Kubernetes)

```
┌──────────────────────────────────────────┐
│  Kubernetes Cluster                      │
│  ┌────────────────────────────────────┐  │
│  │  production-agents namespace       │  │
│  │  ┌──────────────────────────────┐  │  │
│  │  │  Agent Pods (3-10 replicas)  │  │  │
│  │  │  ┌─────┐ ┌─────┐ ┌─────┐    │  │  │
│  │  │  │ Pod │ │ Pod │ │ Pod │... │  │  │
│  │  │  └─────┘ └─────┘ └─────┘    │  │  │
│  │  └──────────────────────────────┘  │  │
│  │           │ Load Balancer           │  │
│  │  ┌──────────────────────────────┐  │  │
│  │  │  Redis StatefulSet           │  │  │
│  │  └──────────────────────────────┘  │  │
│  │  ┌──────────────────────────────┐  │  │
│  │  │  HPA (autoscaling)           │  │  │
│  │  └──────────────────────────────┘  │  │
│  └────────────────────────────────────┘  │
│  ┌────────────────────────────────────┐  │
│  │  monitoring namespace              │  │
│  │  ┌─────────────┐ ┌─────────────┐  │  │
│  │  │ Prometheus  │ │   Grafana   │  │  │
│  │  └─────────────┘ └─────────────┘  │  │
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
```

## Key Metrics to Monitor

### Golden Signals (RED)

- **Rate**: Requests per second
- **Errors**: Error rate (percentage)
- **Duration**: Latency (P50, P95, P99)

### Resource Utilization (USE)

- **Utilization**: CPU, memory, disk usage
- **Saturation**: Queue depth, backlog
- **Errors**: System errors, OOMs

### Business Metrics

- **Token usage**: Tokens per second/request
- **Costs**: Dollars per hour/day/month
- **Cache hit rate**: Redis cache effectiveness
- **SLO compliance**: Error budget remaining

## Scaling Strategies

### Vertical Scaling (Single Instance)

```yaml
# Increase resources
resources:
  limits:
    cpu: "4000m"     # 4 CPUs
    memory: "8Gi"    # 8 GB RAM
```

**Pros**: Simple, low latency
**Cons**: Limited scale, single point of failure

### Horizontal Scaling (Multiple Instances)

```yaml
# Increase replicas
spec:
  replicas: 10

# Or use HPA
spec:
  minReplicas: 3
  maxReplicas: 20
```

**Pros**: High availability, elastic scaling
**Cons**: Need shared state (Redis), more complex

### Hybrid Scaling

Combine both: Scale vertically per instance, horizontally for replicas.

## Cost Optimization

### Compute Costs

1. **Right-size resources**: Monitor actual usage, adjust limits
2. **Use autoscaling**: Only run what you need
3. **Use spot instances**: For non-critical workloads (K8s)
4. **Share resources**: Multi-tenancy where appropriate

### Token Costs (Primary Driver)

1. **Enable caching**: Redis for repeated queries
2. **Optimize prompts**: Reduce unnecessary tokens
3. **Use smaller models**: Where appropriate
4. **Set token budgets**: Per-request limits
5. **Monitor costs**: Real-time dashboards and alerts

### Storage Costs

1. **Set retention**: Don't keep logs/metrics forever
2. **Compress data**: Enable compression (Loki, Prometheus)
3. **Use tiered storage**: Move old data to cheaper storage

## Disaster Recovery

### Backup Strategy

```bash
# Backup Redis data
kubectl exec redis-0 -n production-agents -- redis-cli BGSAVE
kubectl cp production-agents/redis-0:/data/dump.rdb ./backup/

# Backup Prometheus data
kubectl exec prometheus-0 -n monitoring -- tar czf /tmp/prometheus.tar.gz /prometheus
kubectl cp monitoring/prometheus-0:/tmp/prometheus.tar.gz ./backup/

# Backup Grafana dashboards (automated with provisioning)
```

### Recovery Procedures

See [Incident Response Guide](../chapters/10-incident-response.md)

## Multi-Region Deployment

For global deployments:

1. Deploy to multiple regions
2. Use global load balancer
3. Replicate Redis with Redis Enterprise or ElastiCache Global Datastore
4. Aggregate monitoring centrally
5. Consider data residency requirements

See [Multi-Region Deployment](../chapters/11-multi-region-deployment.md)

## Troubleshooting

### Common Issues

| Issue | Likely Cause | Solution |
|-------|-------------|----------|
| Pods not starting | Resource limits too low | Increase CPU/memory limits |
| High latency | API slowness or overload | Check circuit breakers, scale up |
| High costs | Token usage spike | Check cost dashboard, add budgets |
| Low cache hit rate | TTL too short or cache cold | Adjust TTL, warm cache |
| Metrics not showing | Scrape config wrong | Check ServiceMonitor, /metrics endpoint |

### Debug Commands

```bash
# Check pod status
kubectl get pods -n production-agents

# View logs
kubectl logs -f deployment/agent-deployment -n production-agents

# Check metrics endpoint
kubectl exec -it agent-pod-xxx -n production-agents -- curl localhost:8000/metrics

# Test Redis connection
kubectl exec -it redis-0 -n production-agents -- redis-cli ping

# Check HPA status
kubectl describe hpa agent-hpa -n production-agents

# View events
kubectl get events -n production-agents --sort-by='.lastTimestamp'
```

## Performance Benchmarking

Before going to production, benchmark your setup:

```bash
# Load test with k6 or locust
k6 run load-test.js --vus 100 --duration 5m

# Monitor during load test:
# - Latency (should stay below SLO)
# - Error rate (should stay below 1%)
# - CPU/memory (should not max out)
# - Cost per request
```

## Next Steps

1. Choose your deployment method (Docker or Kubernetes)
2. Follow the specific guide (docker/README.md or kubernetes/README.md)
3. Set up monitoring (monitoring/README.md)
4. Configure alerts and dashboards
5. Test rollback procedures
6. Create runbooks for common issues
7. Load test before production traffic
8. Set up CI/CD pipeline
9. Implement blue-green or canary deployments

## Additional Resources

- [Production Mindset (Chapter 1)](../chapters/01-production-mindset.md)
- [Reliability Patterns (Chapter 2)](../chapters/02-reliability-resilience.md)
- [Observability (Chapter 3)](../chapters/03-observability-debugging.md)
- [Security (Chapter 4)](../chapters/04-security-safety.md)
- [Cost Optimization (Chapter 5)](../chapters/05-cost-optimization.md)
- [Scaling (Chapter 6)](../chapters/06-scaling-agent-systems.md)
- [Deployment Patterns (Chapter 9)](../chapters/09-deployment-patterns.md)
- [Incident Response (Chapter 10)](../chapters/10-incident-response.md)

## Support

For issues:
- Check the troubleshooting guides
- Review logs and metrics
- Consult runbooks
- Escalate to on-call if critical

## Contributing

When adding new infrastructure:
- Document all configurations
- Add monitoring for new services
- Update this README
- Test in staging first
- Create rollback plan
