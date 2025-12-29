# Kubernetes Deployment Guide

Production-ready Kubernetes deployment for AI agent systems with autoscaling, monitoring, and high availability.

## What's Included

This Kubernetes configuration provides:

- **Agent Deployment**: Scalable agent pods with health checks
- **Redis StatefulSet**: State management and caching with persistence
- **Horizontal Pod Autoscaler**: Automatic scaling based on CPU, memory, and custom metrics
- **Service Discovery**: ClusterIP services for internal communication
- **RBAC**: Least-privilege service accounts and roles
- **Network Policies**: Secure network segmentation
- **Persistent Storage**: PVCs for data persistence
- **Prometheus Integration**: ServiceMonitors for metrics collection
- **Resource Limits**: CPU and memory limits for stability
- **Rolling Updates**: Zero-downtime deployments

## Prerequisites

- Kubernetes cluster (1.24+)
- `kubectl` configured to access your cluster
- Storage provisioner (for PVCs)
- Metrics server (for HPA)
- Prometheus Operator (optional, for ServiceMonitors)
- 8GB+ RAM available across nodes
- 50GB+ storage available

## Quick Start

### 1. Prepare Secrets

```bash
# Create the secret for API keys
kubectl create secret generic agent-secrets \
  --from-literal=anthropic-api-key=your_api_key_here \
  --from-literal=redis-password=your_redis_password \
  --namespace=production-agents --dry-run=client -o yaml | kubectl apply -f -
```

**IMPORTANT**: Never commit secrets to version control!

### 2. Deploy with Kustomize

```bash
# Deploy everything
kubectl apply -k .

# Watch the rollout
kubectl rollout status deployment/agent-deployment -n production-agents

# Check all resources
kubectl get all -n production-agents
```

### 3. Deploy Manually (without Kustomize)

```bash
# Apply in order
kubectl apply -f namespace.yaml
kubectl apply -f configmap.yaml
kubectl apply -f secret.yaml  # Create from template first!
kubectl apply -f rbac.yaml
kubectl apply -f pvc.yaml
kubectl apply -f redis-statefulset.yaml
kubectl apply -f service.yaml
kubectl apply -f deployment.yaml
kubectl apply -f hpa.yaml
kubectl apply -f networkpolicy.yaml
kubectl apply -f servicemonitor.yaml  # If using Prometheus Operator
```

### 4. Verify Deployment

```bash
# Check pods are running
kubectl get pods -n production-agents

# Check services
kubectl get svc -n production-agents

# Check HPA status
kubectl get hpa -n production-agents

# View agent logs
kubectl logs -f deployment/agent-deployment -n production-agents

# Check Redis
kubectl exec -it redis-0 -n production-agents -- redis-cli ping
```

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Kubernetes Cluster                             │
│                                                 │
│  ┌────────────────────────────────────────┐    │
│  │  production-agents namespace           │    │
│  │                                        │    │
│  │  ┌──────────────────────────────────┐ │    │
│  │  │  Agent Deployment (3-10 pods)    │ │    │
│  │  │  ┌─────┐ ┌─────┐ ┌─────┐        │ │    │
│  │  │  │ Pod │ │ Pod │ │ Pod │ ...    │ │    │
│  │  │  └─────┘ └─────┘ └─────┘        │ │    │
│  │  └──────────────────────────────────┘ │    │
│  │           ↓ Metrics                   │    │
│  │  ┌──────────────────────────────────┐ │    │
│  │  │  Agent Service (ClusterIP)       │ │    │
│  │  └──────────────────────────────────┘ │    │
│  │           ↓                           │    │
│  │  ┌──────────────────────────────────┐ │    │
│  │  │  Redis StatefulSet               │ │    │
│  │  │  ┌─────┐                         │ │    │
│  │  │  │Redis│ + PVC                   │ │    │
│  │  │  └─────┘                         │ │    │
│  │  └──────────────────────────────────┘ │    │
│  │                                        │    │
│  │  ┌──────────────────────────────────┐ │    │
│  │  │  HPA (3-10 replicas)             │ │    │
│  │  └──────────────────────────────────┘ │    │
│  └────────────────────────────────────────┘    │
│                 ↓ Metrics                      │
│  ┌────────────────────────────────────────┐    │
│  │  Prometheus (scrapes ServiceMonitors)  │    │
│  └────────────────────────────────────────┘    │
└─────────────────────────────────────────────────┘
```

## Configuration

### Environment Variables

Configure the agent in `configmap.yaml`:

```yaml
data:
  LOG_LEVEL: "INFO"
  ENVIRONMENT: "production"
  MAX_RETRIES: "3"
  CIRCUIT_BREAKER_THRESHOLD: "5"
  TOKEN_BUDGET_PER_REQUEST: "10000"
```

### Resource Limits

Adjust in `deployment.yaml`:

```yaml
resources:
  requests:
    cpu: "500m"      # 0.5 CPU cores
    memory: "1Gi"    # 1 GB RAM
  limits:
    cpu: "2000m"     # 2 CPU cores
    memory: "2Gi"    # 2 GB RAM
```

### Scaling Configuration

Modify HPA in `hpa.yaml`:

```yaml
minReplicas: 3    # Minimum pods
maxReplicas: 10   # Maximum pods
targetCPUUtilizationPercentage: 70  # Scale when CPU > 70%
```

### Storage

Update PVC size in `pvc.yaml`:

```yaml
resources:
  requests:
    storage: 10Gi  # Increase as needed
```

## Monitoring

### View Metrics

If using Prometheus Operator:

```bash
# Check ServiceMonitor
kubectl get servicemonitor -n production-agents

# Check if Prometheus is scraping
kubectl port-forward -n monitoring svc/prometheus 9090:9090

# Open browser: http://localhost:9090/targets
```

### Custom Metrics for HPA

To scale based on custom metrics (e.g., request rate):

1. Install Prometheus Adapter
2. Configure adapter to expose custom metrics
3. Update HPA to use custom metrics (already configured in `hpa.yaml`)

```bash
# Install Prometheus Adapter
helm install prometheus-adapter prometheus-community/prometheus-adapter
```

### Grafana Dashboards

Import dashboards from `../monitoring/grafana/dashboards/`:

1. Port-forward to Grafana: `kubectl port-forward -n monitoring svc/grafana 3000:3000`
2. Open http://localhost:3000
3. Import dashboard JSON files

## Operations

### Scaling Manually

```bash
# Scale to specific number of replicas
kubectl scale deployment agent-deployment --replicas=5 -n production-agents

# Check current scale
kubectl get deployment agent-deployment -n production-agents
```

### Rolling Updates

```bash
# Update image
kubectl set image deployment/agent-deployment \
  agent=your-registry/production-agent:v2.0.0 \
  -n production-agents

# Watch rollout
kubectl rollout status deployment/agent-deployment -n production-agents

# Check rollout history
kubectl rollout history deployment/agent-deployment -n production-agents
```

### Rollback

```bash
# Rollback to previous version
kubectl rollout undo deployment/agent-deployment -n production-agents

# Rollback to specific revision
kubectl rollout undo deployment/agent-deployment --to-revision=2 -n production-agents
```

### Zero-Downtime Updates

The deployment is configured with:

```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 1           # Create 1 new pod first
    maxUnavailable: 0     # Keep all pods running during update
```

This ensures zero downtime during updates.

### Backup and Restore

#### Backup Redis Data

```bash
# Backup Redis RDB file
kubectl exec redis-0 -n production-agents -- redis-cli BGSAVE

# Copy backup to local machine
kubectl cp production-agents/redis-0:/data/dump.rdb ./backup/redis-dump-$(date +%Y%m%d).rdb
```

#### Restore Redis Data

```bash
# Copy backup to pod
kubectl cp ./backup/redis-dump.rdb production-agents/redis-0:/tmp/dump.rdb

# Restore in Redis
kubectl exec -it redis-0 -n production-agents -- sh -c "cp /tmp/dump.rdb /data/dump.rdb && redis-cli SHUTDOWN SAVE"

# Redis will restart automatically and load the data
```

## Troubleshooting

### Pods Not Starting

```bash
# Check pod status
kubectl get pods -n production-agents

# View events
kubectl get events -n production-agents --sort-by='.lastTimestamp'

# Describe pod
kubectl describe pod <pod-name> -n production-agents

# Check logs
kubectl logs <pod-name> -n production-agents

# Common issues:
# 1. ImagePullBackOff → Check image name and registry credentials
# 2. CrashLoopBackOff → Check logs for application errors
# 3. Pending → Check resource availability and PVC binding
```

### PVC Not Binding

```bash
# Check PVC status
kubectl get pvc -n production-agents

# Describe PVC
kubectl describe pvc agent-data-pvc -n production-agents

# Check storage class
kubectl get storageclass

# Common issues:
# 1. No storage provisioner installed
# 2. Storage class doesn't exist
# 3. Insufficient storage capacity
```

### HPA Not Scaling

```bash
# Check HPA status
kubectl get hpa -n production-agents

# Describe HPA
kubectl describe hpa agent-hpa -n production-agents

# Check if metrics server is running
kubectl get deployment metrics-server -n kube-system

# View current metrics
kubectl top pods -n production-agents

# Common issues:
# 1. Metrics server not installed
# 2. Pods don't have resource requests set
# 3. Metrics not yet available (wait 1-2 minutes)
```

### Redis Connection Issues

```bash
# Test Redis connectivity from agent pod
kubectl exec -it <agent-pod-name> -n production-agents -- nc -zv redis-service 6379

# Check Redis logs
kubectl logs redis-0 -n production-agents

# Test Redis directly
kubectl exec -it redis-0 -n production-agents -- redis-cli ping

# Common issues:
# 1. Network policy blocking connections
# 2. Redis not ready yet
# 3. Wrong service name in connection string
```

### High Memory Usage

```bash
# Check resource usage
kubectl top pods -n production-agents

# View detailed memory stats
kubectl exec -it <pod-name> -n production-agents -- cat /sys/fs/cgroup/memory/memory.stat

# Solutions:
# 1. Increase memory limits in deployment.yaml
# 2. Reduce agent concurrency
# 3. Enable swap (not recommended)
# 4. Scale horizontally instead
```

### Network Policy Issues

```bash
# Check network policies
kubectl get networkpolicy -n production-agents

# Describe network policy
kubectl describe networkpolicy agent-network-policy -n production-agents

# Test connectivity
kubectl run -it --rm debug --image=nicolaka/netshoot -n production-agents -- /bin/bash
# Inside the debug pod:
$ curl agent-service:8000/health
$ nc -zv redis-service 6379
```

## Security Best Practices

### Secrets Management

**Don't** store secrets in Git:
```bash
# Use external secrets manager
# AWS Secrets Manager
# HashiCorp Vault
# External Secrets Operator
```

**Do** use Kubernetes secrets with RBAC:
```bash
kubectl create secret generic agent-secrets \
  --from-literal=anthropic-api-key=xxx \
  --namespace=production-agents
```

### RBAC

The configuration includes least-privilege RBAC:
- ServiceAccount for agent pods
- Role with minimal permissions
- RoleBinding to connect them

Review and adjust `rbac.yaml` based on your needs.

### Network Policies

Network policies restrict traffic:
- Agent can only talk to Redis and external APIs
- Redis can only receive connections from agent
- Prometheus can scrape metrics endpoints

Enable CNI plugin that supports network policies (Calico, Cilium, etc.).

### Pod Security

The deployment includes security contexts:
- Non-root user (UID 1000)
- Read-only root filesystem (where possible)
- Dropped all capabilities
- No privilege escalation

### Image Security

Scan images for vulnerabilities:

```bash
# Using Trivy
trivy image your-registry/production-agent:latest

# Using Docker Scout
docker scout cves your-registry/production-agent:latest
```

## Performance Tuning

### For High Throughput

```yaml
# Increase replicas
minReplicas: 10
maxReplicas: 50

# Increase resources
resources:
  limits:
    cpu: "4000m"
    memory: "4Gi"

# Increase Redis resources
# In redis-statefulset.yaml
resources:
  limits:
    cpu: "2000m"
    memory: "2Gi"
```

### For Low Latency

```yaml
# Use faster storage class
storageClassName: premium-ssd  # Or equivalent

# Ensure pod anti-affinity (already configured)
# Spreads pods across nodes

# Use nodeSelector for faster nodes
nodeSelector:
  node-type: high-performance
```

### Resource Optimization

```bash
# Monitor actual usage
kubectl top pods -n production-agents

# Adjust requests to match actual usage
# Set limits 20-30% higher than typical usage

# Use Vertical Pod Autoscaler (VPA) for recommendations
kubectl describe vpa agent-vpa -n production-agents
```

## Cost Optimization

1. **Right-size resources**: Use VPA or monitoring to find optimal sizes
2. **Use node autoscaling**: Scale cluster nodes based on demand
3. **Use spot instances**: For non-critical workloads
4. **Enable HPA**: Only run pods you need
5. **Set resource requests**: Enables efficient bin-packing
6. **Use namespace resource quotas**: Prevent runaway costs

```yaml
# ResourceQuota example
apiVersion: v1
kind: ResourceQuota
metadata:
  name: agent-quota
  namespace: production-agents
spec:
  hard:
    requests.cpu: "20"
    requests.memory: "40Gi"
    persistentvolumeclaims: "10"
```

## Multi-Cluster / Multi-Region

For multi-region deployment:

1. Deploy to each cluster/region separately
2. Use global load balancer (e.g., AWS Global Accelerator, Google Cloud Load Balancer)
3. Use distributed Redis (Redis Cluster or external service like ElastiCache Global Datastore)
4. Configure cross-region metrics aggregation
5. Set up cross-region tracing

See [Multi-Region Deployment Guide](../../chapters/11-multi-region-deployment.md)

## Production Readiness Checklist

Before going to production:

- [ ] Secrets configured properly (not in Git!)
- [ ] Resource limits set based on load testing
- [ ] HPA configured and tested
- [ ] Health checks working (liveness, readiness, startup)
- [ ] Monitoring and alerting configured
- [ ] Network policies applied and tested
- [ ] RBAC configured with least privilege
- [ ] Backup strategy implemented
- [ ] Disaster recovery plan documented
- [ ] Rollback procedure tested
- [ ] Load testing completed
- [ ] Security scan completed (images, manifests)
- [ ] Documentation updated
- [ ] Runbooks created for common issues
- [ ] On-call rotation established

## Next Steps

- Configure monitoring alerts (see `../monitoring/prometheus/alerts.yml`)
- Set up Grafana dashboards (see `../monitoring/grafana/`)
- Enable distributed tracing with OpenTelemetry
- Set up log aggregation with Loki or ELK
- Configure automated backups
- Set up CI/CD pipeline for deployments
- Implement blue-green deployment strategy
- Configure multi-region deployment

## Related Documentation

- [Docker Deployment](../docker/README.md)
- [Monitoring Guide](../monitoring/README.md)
- [Multi-Region Deployment](../../chapters/11-multi-region-deployment.md)
- [Production Readiness Checklist](../../docs/production-readiness.md)
- [Incident Response Runbooks](../../docs/runbooks/)

## Additional Resources

- [Kubernetes Best Practices](https://kubernetes.io/docs/concepts/configuration/overview/)
- [Prometheus Operator](https://prometheus-operator.dev/)
- [Kubernetes Autoscaling](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)
- [Network Policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
