# Chapter 11: Multi-Region Deployment - Code Examples

This directory contains examples for deploying AI agents across multiple geographic regions.

## Overview

Multi-region deployment strategies for global scale:

1. **regions/** - Regional deployment configurations
2. **compliance/** - Data residency enforcement (GDPR)
3. **failover/** - Health checks and failover strategies
4. **monitoring/** - Global health monitoring
5. **terraform/** - Infrastructure as code

## When to Use Multi-Region

**✅ Deploy multi-region when**:
- Users in multiple continents (>500ms latency)
- Data residency requirements (GDPR, etc.)
- Need 99.99%+ availability
- Global scale (millions of users)

**❌ Don't deploy multi-region when**:
- All users in one region
- Early stage (complexity not worth it)
- Latency not critical
- No compliance requirements

## Latency Improvements

**Before multi-region** (single US region):
- US users: 50ms ✅
- EU users: 800ms ❌
- Asia users: 1,200ms ❌

**After multi-region**:
- US users → US region: 50ms ✅
- EU users → EU region: 150ms ✅ (5.3x improvement)
- Asia users → AP region: 180ms ✅ (6.7x improvement)

## Architecture

### Single Region (Before)

```
All Users → US-East-1
            ↓
         Agent API
            ↓
       Redis + DB
```

### Multi-Region (After)

```
US Users → US-East-1 → Agent API → Redis + DB (US)
EU Users → EU-West-1 → Agent API → Redis + DB (EU)
AP Users → AP-Southeast-1 → Agent API → Redis + DB (AP)

GeoDNS routes users to nearest region
```

## Example 1: Regional Deployment

**Location**: `regions/`

**Regional configuration**:
```yaml
# US-East (Primary, 60% traffic)
us-east-1:
  api_pods: 10
  worker_pods: 20
  db_size: db.r5.xlarge
  redis_nodes: 3

# EU-West (Secondary, 30% traffic)
eu-west-1:
  api_pods: 6
  worker_pods: 12
  db_size: db.r5.large
  redis_nodes: 3
  data_residency: GDPR  # EU data stays in EU

# AP-Southeast (Tertiary, 10% traffic)
ap-southeast-1:
  api_pods: 4
  worker_pods: 8
  db_size: db.r5.large
  redis_nodes: 3
```

**Deploy to multiple regions**:
```bash
# Deploy to US
kubectl --context=us-east-1 apply -f regions/us-deployment.yaml

# Deploy to EU
kubectl --context=eu-west-1 apply -f regions/eu-deployment.yaml

# Deploy to AP
kubectl --context=ap-southeast-1 apply -f regions/ap-deployment.yaml
```

## Example 2: Data Residency (GDPR Compliance)

**Location**: `compliance/`

**What it provides**:
- GDPR compliance enforcement
- EU data stays in EU
- Automatic region routing based on user country
- Compliance validation

**Usage**:
```python
from compliance.data_residency import ComplianceEnforcer, Region

# Enforce GDPR in EU region
enforcer = ComplianceEnforcer(region=Region.EU_WEST)

# Validate request (returns False if violates residency)
if not enforcer.validate_request(user_country="DE"):  # Germany
    raise HTTPException(status_code=451, detail="Data residency violation")

# Get compliant storage location
storage_region = enforcer.get_storage_location(user_country="DE")
# Returns: "eu-west-1" (EU data stays in EU)
```

**GDPR rules**:
- EU/GB users → Must use EU region
- US/CA users → Can use any region
- Other users → No restrictions

## Example 3: GeoDNS Routing

**Location**: `terraform/`

**What it provides**:
- Route 53 geolocation routing
- Automatic failover
- Health checks

**Deploy GeoDNS**:
```bash
cd terraform

# Initialize Terraform
terraform init

# Plan deployment
terraform plan

# Deploy
terraform apply

# Result: api.agent.company.com routes to nearest region
```

**How it works**:
```
User in New York → api.agent.company.com → US-East-1
User in London → api.agent.company.com → EU-West-1
User in Singapore → api.agent.company.com → AP-Southeast-1
```

## Example 4: Failover

**Location**: `failover/`

**Failover strategies**:

**Active-Active** (all regions serve traffic):
```yaml
routing:
  us-east-1:
    weight: 60  # 60% of traffic
    health_check: enabled
  eu-west-1:
    weight: 30  # 30% of traffic
    health_check: enabled
  ap-southeast-1:
    weight: 10  # 10% of traffic
    health_check: enabled
```

**Active-Passive** (primary + standby):
```yaml
routing:
  us-east-1:
    weight: 100  # Primary (100% traffic)
    health_check: enabled
    failover_to: eu-west-1

  eu-west-1:
    weight: 0  # Standby (0% traffic normally)
    health_check: enabled
    # Only receives traffic if us-east-1 fails
```

**Test failover**:
```bash
# Simulate US region failure
kubectl --context=us-east-1 scale deployment/agent-api --replicas=0

# Watch Route 53 detect failure
aws route53 get-health-check-status --health-check-id <id>

# Traffic automatically fails over to EU
# Verify EU receiving 100% traffic
watch 'curl -s https://api.agent.company.com/metrics | grep region'
```

## Example 5: Global Monitoring

**Location**: `monitoring/`

**What it monitors**:
- Health status by region
- Latency by region
- Error rate by region
- Traffic distribution

**Deploy monitoring**:
```bash
cd monitoring

# Deploy global Prometheus federation
kubectl apply -f global-prometheus.yaml

# Deploy Grafana dashboard
kubectl apply -f global-dashboard.yaml

# Access dashboard
kubectl port-forward service/grafana 3000:3000
open http://localhost:3000
```

**Metrics collected**:
```prometheus
# Regional health (1=healthy, 0=unhealthy)
agent_region_health{region="us-east-1"} 1
agent_region_health{region="eu-west-1"} 1
agent_region_health{region="ap-southeast-1"} 1

# Regional latency (p95)
agent_region_latency_seconds{region="us-east-1"} 0.05
agent_region_latency_seconds{region="eu-west-1"} 0.15
agent_region_latency_seconds{region="ap-southeast-1"} 0.18

# Traffic distribution
agent_region_requests_total{region="us-east-1"} 600000
agent_region_requests_total{region="eu-west-1"} 300000
agent_region_requests_total{region="ap-southeast-1"} 100000
```

## Cost Analysis

### Naive Multi-Region (3x cost)

```
Single region: $5,000/month

Multi-region (full deployment everywhere):
- US: $5,000
- EU: $5,000
- AP: $5,000
Total: $15,000/month (3x increase)
```

### Optimized Multi-Region (1.7x cost)

```
Multi-region (right-sized by traffic):
- US (60% traffic): $5,000 (full deployment)
- EU (30% traffic): $2,500 (80% capacity)
- AP (10% traffic): $1,000 (40% capacity)
Total: $8,500/month (1.7x increase)

Savings: $6,500/month vs naive approach
```

## Deployment Workflow

### 1. Deploy to Primary Region (US)

```bash
# Deploy full stack to US
terraform apply -target=module.us_east_1

# Verify deployment
kubectl --context=us-east-1 get all

# Run smoke tests
python smoke_test.py https://us-api.agent.company.com
```

### 2. Deploy to Secondary Region (EU)

```bash
# Deploy to EU
terraform apply -target=module.eu_west_1

# Verify deployment
kubectl --context=eu-west-1 get all

# Verify GDPR compliance
python compliance/test_gdpr.py
```

### 3. Deploy to Tertiary Region (AP)

```bash
# Deploy to AP
terraform apply -target=module.ap_southeast_1

# Verify deployment
kubectl --context=ap-southeast-1 get all
```

### 4. Configure GeoDNS

```bash
# Apply Route 53 configuration
terraform apply -target=aws_route53_record.agent_us
terraform apply -target=aws_route53_record.agent_eu
terraform apply -target=aws_route53_record.agent_ap

# Verify routing
dig api.agent.company.com  # Should return nearest region
```

### 5. Test Global Deployment

```bash
# Test from different locations
curl https://api.agent.company.com/health  # From US
curl https://api.agent.company.com/health  # From EU
curl https://api.agent.company.com/health  # From AP

# Each should route to nearest region
```

## Testing Multi-Region

### Latency Test

```bash
# Test latency from different regions
for region in us eu ap; do
  echo "Testing from $region:"
  time curl -s https://api.agent.company.com/health
done

# Expected:
# US: <100ms
# EU: <200ms
# AP: <250ms
```

### Failover Test

```bash
# 1. Simulate primary region failure
kubectl --context=us-east-1 scale deployment/agent-api --replicas=0

# 2. Watch health check fail
aws route53 get-health-check-status --health-check-id <us-id>
# Status: Unhealthy

# 3. Verify automatic failover
curl https://api.agent.company.com/health
# Should route to EU (failover region)

# 4. Restore primary
kubectl --context=us-east-1 scale deployment/agent-api --replicas=10

# 5. Watch traffic return to primary
```

### Data Residency Test

```bash
# Test GDPR enforcement
python compliance/test_gdpr.py

# Expected results:
# ✅ EU user data stored in EU region
# ✅ US user data can be stored anywhere
# ❌ EU user data rejected in US region (HTTP 451)
```

## Troubleshooting

### High latency in one region

**Problem**: EU users experiencing high latency

**Diagnosis**:
```bash
# Check EU region health
kubectl --context=eu-west-1 get pods

# Check resource usage
kubectl --context=eu-west-1 top pods

# Check metrics
curl https://eu-prometheus.company.com/api/v1/query?query=agent_response_seconds
```

**Solutions**:
- Scale up EU region
- Check network between EU and Claude API
- Verify EU region not routing to US

### Failover not working

**Problem**: Traffic not failing over to standby region

**Diagnosis**:
```bash
# Check health check status
aws route53 get-health-check-status --health-check-id <id>

# Check Route 53 routing policy
aws route53 list-resource-record-sets --hosted-zone-id <zone>
```

**Solutions**:
- Verify health check endpoint returning 200
- Check health check interval and threshold
- Verify failover routing policy configured

### Data residency violation

**Problem**: EU data found in US region

**Diagnosis**:
```bash
# Check where EU user data is stored
python compliance/audit_data.py --user-country=DE

# Check logs for cross-region access
grep "data_residency_violation" logs/*.log
```

**Solutions**:
- Enforce compliance at API layer
- Audit storage locations
- Update routing rules

## Multi-Region Checklist

Before going live:

### Architecture
- [ ] All regions deployed
- [ ] GeoDNS configured
- [ ] Health checks configured
- [ ] Failover tested
- [ ] Data residency enforced

### Compliance
- [ ] GDPR compliance verified
- [ ] Data residency audited
- [ ] Privacy policy updated
- [ ] DPAs signed with vendors
- [ ] Audit logging configured

### Performance
- [ ] Latency tested from all regions
- [ ] Load tested regionally
- [ ] Capacity right-sized by traffic
- [ ] CDN configured for static assets

### Monitoring
- [ ] Global dashboard deployed
- [ ] Regional metrics tracked
- [ ] Failover alerts configured
- [ ] Latency alerts by region

### Cost
- [ ] Regional sizing optimized
- [ ] Reserved instances purchased
- [ ] Data transfer costs estimated
- [ ] Monthly budget set

## Best Practices

1. **Start with one region**, expand as needed
2. **Right-size by traffic** (don't deploy identically everywhere)
3. **Test failover regularly** (monthly drills)
4. **Monitor globally**, act regionally
5. **Respect data residency** (compliance is not optional)
6. **Optimize costs** (reserved instances, right-sizing)
7. **Document regional differences** (timezones, regulations)

## Resources

- [AWS Multi-Region Architecture](https://aws.amazon.com/solutions/implementations/multi-region-infrastructure/)
- [GDPR Overview](https://gdpr.eu/)
- [Route 53 Geolocation Routing](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/routing-policy-geo.html)
- [Global Application Architecture](https://aws.amazon.com/architecture/global-network/)

## Next Steps

1. Assess if you need multi-region
2. Plan regional deployment (US, EU, AP)
3. Implement data residency rules
4. Deploy to primary region
5. Expand to secondary regions
6. Configure GeoDNS
7. Test failover
8. Move to Chapter 12 (Platform Architecture)

**Remember**: Multi-region adds complexity. Only use it when you need it!
