# Chapter 11: Multi-Region Deployment

## Introduction: The Global Scale Challenge

Maria's AI customer support agent is a success in North America—serving 50,000 customers with <2 second response times. Now the company is expanding to Europe and Asia. But there's a problem:

**Current architecture** (single US region):
- European users: 800ms latency (too slow)
- Asian users: 1,200ms latency (unacceptable)
- No data residency compliance (GDPR violation)
- Single point of failure (no regional redundancy)

**Business requirements**:
- <200ms latency globally
- GDPR compliance (EU data stays in EU)
- 99.99% availability (multi-region redundancy)
- Cost-effective global deployment

**After implementing multi-region deployment**:
- European users: 150ms latency (5.3x improvement)
- Asian users: 180ms latency (6.7x improvement)
- GDPR compliant (data residency enforced)
- 99.99% availability (region failover working)
- 15% cost increase (vs 3x for naive deployment)

This is the multi-region challenge: **Serving global users while maintaining performance, compliance, and cost efficiency.**

---

## Why Multi-Region Deployment Matters

**When you need multi-region**:
- **Global users**: Users in different continents
- **Latency requirements**: <200ms response times globally
- **Data residency**: GDPR, data sovereignty laws
- **High availability**: Survive regional outages
- **Disaster recovery**: Geographic redundancy

**When you DON'T need multi-region**:
- All users in one region
- Latency not critical
- No data residency requirements
- Early stage (complexity not worth it yet)

**Production reality**: Multi-region is complex—only add it when necessary.

---

## Geographic Distribution Architecture

### Single-Region Architecture (Before)

```
All Users → US-East → Agent API → Claude API (US)
                  ↓
              Redis, DB (US)
```

**Problems**:
- High latency for distant users
- Single point of failure
- No data residency compliance

### Multi-Region Architecture (After)

```
US Users → US-East → Agent API → Claude API (US)
                  ↓
              Redis, DB (US)

EU Users → EU-West → Agent API → Claude API (EU)
                  ↓
              Redis, DB (EU)

Asia Users → AP-Southeast → Agent API → Claude API (US)*
                         ↓
                     Redis, DB (AP)

* Claude API not available in all regions (as of 2024)
```

**Benefits**:
- Low latency (users route to nearest region)
- Regional redundancy (failover between regions)
- Data residency compliance (data stays local)

---

## Latency Optimization

### The Speed of Light Problem

**Physical limits**:
- Light travels at 299,792 km/s
- Fiber optic cables: ~200,000 km/s (slower)
- Round-trip time (RTT) calculation:

```
Distance (km) / Speed (km/s) * 2 (round-trip) = Latency (ms)

Examples:
- San Francisco ↔ New York: 4,135 km
  RTT: 4,135 / 200,000 * 2 * 1000 = 41ms (minimum)

- New York ↔ London: 5,585 km
  RTT: 5,585 / 200,000 * 2 * 1000 = 56ms (minimum)

- San Francisco ↔ Singapore: 13,593 km
  RTT: 13,593 / 200,000 * 2 * 1000 = 136ms (minimum)
```

**Reality**: Actual latency is 2-3x theoretical minimum (routing, switches, processing).

**Solution**: Deploy closer to users.

### Regional Deployment Strategy

```yaml
# code-examples/chapter-11-multi-region/regions/deployment.yaml

# US-East (Primary)
us-east-1:
  provider: AWS
  region: us-east-1
  users: North America, South America
  deployment:
    - Agent API (10 pods)
    - Workers (20 pods)
    - Redis cluster (3 nodes)
    - PostgreSQL (primary + 2 replicas)
  claude_api: https://api.anthropic.com

# EU-West (GDPR compliance)
eu-west-1:
  provider: AWS
  region: eu-west-1
  users: Europe, Middle East, Africa
  deployment:
    - Agent API (8 pods)
    - Workers (15 pods)
    - Redis cluster (3 nodes)
    - PostgreSQL (primary + 2 replicas)
  claude_api: https://api.anthropic.com  # Routes to US
  data_residency: GDPR enforced

# Asia-Pacific
ap-southeast-1:
  provider: AWS
  region: ap-southeast-1
  users: Asia, Australia
  deployment:
    - Agent API (6 pods)
    - Workers (12 pods)
    - Redis cluster (3 nodes)
    - PostgreSQL (primary + 2 replicas)
  claude_api: https://api.anthropic.com  # Routes to US
```

### Traffic Routing (GeoDNS)

**GeoDNS**: Route users to nearest region based on geography.

```
User request → GeoDNS → Nearest region → Agent API
```

**Implementation** (AWS Route 53):

```hcl
# code-examples/chapter-11-multi-region/terraform/route53.tf

resource "aws_route53_zone" "agent" {
  name = "agent.company.com"
}

# Geolocation routing
resource "aws_route53_record" "agent_us" {
  zone_id = aws_route53_zone.agent.zone_id
  name    = "api.agent.company.com"
  type    = "A"

  geolocation_routing_policy {
    continent = "NA"  # North America
  }

  alias {
    name    = aws_lb.us_east.dns_name
    zone_id = aws_lb.us_east.zone_id
    evaluate_target_health = true
  }

  set_identifier = "US-East"
}

resource "aws_route53_record" "agent_eu" {
  zone_id = aws_route53_zone.agent.zone_id
  name    = "api.agent.company.com"
  type    = "A"

  geolocation_routing_policy {
    continent = "EU"  # Europe
  }

  alias {
    name    = aws_lb.eu_west.dns_name
    zone_id = aws_lb.eu_west.zone_id
    evaluate_target_health = true
  }

  set_identifier = "EU-West"
}

resource "aws_route53_record" "agent_ap" {
  zone_id = aws_route53_zone.agent.zone_id
  name    = "api.agent.company.com"
  type    = "A"

  geolocation_routing_policy {
    continent = "AS"  # Asia
  }

  alias {
    name    = aws_lb.ap_southeast.dns_name
    zone_id = aws_lb.ap_southeast.zone_id
    evaluate_target_health = true
  }

  set_identifier = "AP-Southeast"
}

# Default (fallback to US)
resource "aws_route53_record" "agent_default" {
  zone_id = aws_route53_zone.agent.zone_id
  name    = "api.agent.company.com"
  type    = "A"

  geolocation_routing_policy {
    continent = "*"  # Default
  }

  alias {
    name    = aws_lb.us_east.dns_name
    zone_id = aws_lb.us_east.zone_id
    evaluate_target_health = true
  }

  set_identifier = "Default"
}
```

**Result**:
- US user → `api.agent.company.com` → US-East
- EU user → `api.agent.company.com` → EU-West
- Asia user → `api.agent.company.com` → AP-Southeast

---

## Data Residency and Compliance

### GDPR Requirements

**GDPR Article 44**: Personal data cannot leave the EU without adequate protection.

**What this means for agents**:
- EU user data must stay in EU region
- Cannot send EU data to US Claude API (without safeguards)
- Conversation history must be stored in EU
- Logs containing PII must stay in EU

### Data Residency Architecture

```python
# code-examples/chapter-11-multi-region/compliance/data_residency.py

from enum import Enum
from typing import Optional
import structlog

logger = structlog.get_logger()


class Region(Enum):
    """Geographic regions."""
    US_EAST = "us-east-1"
    EU_WEST = "eu-west-1"
    AP_SOUTHEAST = "ap-southeast-1"


class DataResidency(Enum):
    """Data residency requirements."""
    NONE = "none"  # No restrictions
    EU_GDPR = "eu_gdpr"  # Must stay in EU
    US_ONLY = "us_only"  # Must stay in US


class RegionRouter:
    """
    Route requests to compliant regions.
    """

    # Define data residency rules
    RESIDENCY_RULES = {
        "EU": DataResidency.EU_GDPR,
        "GB": DataResidency.EU_GDPR,  # UK follows GDPR
        "US": DataResidency.NONE,
        "CA": DataResidency.NONE,
        "SG": DataResidency.NONE,
        "AU": DataResidency.NONE,
    }

    # Region capabilities
    REGION_COMPLIANCE = {
        Region.US_EAST: [DataResidency.NONE, DataResidency.US_ONLY],
        Region.EU_WEST: [DataResidency.NONE, DataResidency.EU_GDPR],
        Region.AP_SOUTHEAST: [DataResidency.NONE],
    }

    def get_compliant_region(
        self,
        user_country: str,
        current_region: Region
    ) -> Optional[Region]:
        """
        Get compliant region for user's data.

        Returns None if current region is non-compliant.
        """
        # Get user's data residency requirement
        residency = self.RESIDENCY_RULES.get(user_country, DataResidency.NONE)

        # Check if current region supports this residency
        if residency in self.REGION_COMPLIANCE[current_region]:
            return current_region

        # Find compliant region
        for region, supported in self.REGION_COMPLIANCE.items():
            if residency in supported:
                logger.warning(
                    "data_residency_redirect",
                    user_country=user_country,
                    from_region=current_region.value,
                    to_region=region.value,
                    reason=residency.value,
                )
                return region

        logger.error(
            "no_compliant_region",
            user_country=user_country,
            residency=residency.value,
        )
        return None


class ComplianceEnforcer:
    """
    Enforce data residency compliance.
    """

    def __init__(self, region: Region):
        self.region = region
        self.router = RegionRouter()

    def validate_request(self, user_country: str) -> bool:
        """
        Validate that request can be processed in current region.

        Returns False if violates data residency.
        """
        compliant_region = self.router.get_compliant_region(
            user_country,
            self.region
        )

        if compliant_region != self.region:
            logger.error(
                "data_residency_violation",
                user_country=user_country,
                current_region=self.region.value,
                required_region=compliant_region.value if compliant_region else None,
            )
            return False

        return True

    def get_storage_location(self, user_country: str) -> str:
        """
        Get compliant storage location for user data.
        """
        residency = self.router.RESIDENCY_RULES.get(
            user_country,
            DataResidency.NONE
        )

        if residency == DataResidency.EU_GDPR:
            return "eu-west-1"
        elif residency == DataResidency.US_ONLY:
            return "us-east-1"
        else:
            return self.region.value  # Store locally


# API integration
from fastapi import FastAPI, HTTPException, Header

app = FastAPI()
enforcer = ComplianceEnforcer(region=Region.EU_WEST)


@app.post("/chat")
def chat(
    user_id: str,
    message: str,
    x_user_country: str = Header(...),  # Country from IP geolocation
):
    """
    Chat endpoint with data residency enforcement.
    """
    # Validate compliance
    if not enforcer.validate_request(x_user_country):
        raise HTTPException(
            status_code=451,  # Unavailable For Legal Reasons
            detail=f"Data residency requirements prevent processing in this region. "
                   f"User from {x_user_country} must use different region."
        )

    # Get compliant storage location
    storage_region = enforcer.get_storage_location(x_user_country)

    # Process request with compliant storage
    # ... (agent logic with storage_region)

    return {"response": "..."}
```

### Compliance Checklist

**GDPR Compliance**:
- [ ] EU user data stored in EU region
- [ ] EU data not transferred to non-EU regions
- [ ] Data encryption in transit and at rest
- [ ] Right to erasure (delete user data)
- [ ] Data portability (export user data)
- [ ] Audit logging of data access
- [ ] Data processing agreements with vendors

**Other Regulations**:
- **CCPA** (California): Similar to GDPR
- **LGPD** (Brazil): Data protection law
- **PIPEDA** (Canada): Privacy law
- **Data sovereignty laws**: Various countries

---

## Failover Strategies

### Active-Active vs Active-Passive

**Active-Active** (both regions serving traffic):
```
Users → GeoDNS → Region 1 (50% traffic)
              → Region 2 (50% traffic)
```

**Pros**:
- Better resource utilization
- Natural load balancing
- No cold start on failover

**Cons**:
- More complex (data sync needed)
- Higher cost (running everywhere)

**Active-Passive** (primary + standby):
```
Users → GeoDNS → Region 1 (100% traffic, primary)
              → Region 2 (0% traffic, standby)
```

**Pros**:
- Simpler (no data sync complexity)
- Lower cost (standby can be smaller)

**Cons**:
- Wasted standby capacity
- Cold start on failover
- Slower failover

### Failover Implementation

```yaml
# code-examples/chapter-11-multi-region/failover/health-check.yaml

# Route 53 health check
apiVersion: route53.aws.com/v1
kind: HealthCheck
metadata:
  name: agent-api-us-east
spec:
  type: HTTPS
  resourcePath: /health
  fqdn: agent-us-east.company.internal
  port: 443
  requestInterval: 30  # Check every 30 seconds
  failureThreshold: 3  # Fail after 3 consecutive failures

  # Advanced settings
  measureLatency: true
  enableSNI: true

  # Alarm on failure
  alarmIdentifier:
    region: us-east-1
    name: agent-api-health-alarm

---
# Route 53 record with health check
apiVersion: route53.aws.com/v1
kind: Record
metadata:
  name: agent-api
spec:
  name: api.agent.company.com
  type: A

  # Primary (US-East)
  - setIdentifier: US-East-Primary
    weight: 100
    healthCheckId: agent-api-us-east
    alias:
      dnsName: agent-us-east-lb.amazonaws.com

  # Failover (EU-West)
  - setIdentifier: EU-West-Failover
    weight: 0  # Only receives traffic if primary fails
    alias:
      dnsName: agent-eu-west-lb.amazonaws.com
```

### Database Replication

**For cross-region data access** (not always needed with data residency):

```yaml
# PostgreSQL replication (primary in US, replica in EU)
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: agent-db-us-primary
  namespace: production
spec:
  instances: 3
  primaryUpdateStrategy: unsupervised

  postgresql:
    parameters:
      max_connections: "200"
      shared_buffers: "2GB"

  # Backup configuration
  backup:
    barmanObjectStore:
      destinationPath: s3://agent-backups-us/
      s3Credentials:
        accessKeyId: ...
        secretAccessKey: ...

---
# EU replica (read-only, for failover)
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: agent-db-eu-replica
  namespace: production
spec:
  instances: 2

  # Replicate from US primary
  replica:
    enabled: true
    source: agent-db-us-primary

  postgresql:
    parameters:
      max_connections: "200"
```

**Important**: With GDPR, you may NOT want cross-region replication. EU data should stay in EU.

---

## Cost Considerations

### Multi-Region Cost Analysis

**Single region** (US-East only):
```
Infrastructure: $5,000/month
- Kubernetes cluster: $2,000
- Database: $1,500
- Load balancer: $500
- Monitoring: $1,000

Total: $5,000/month
```

**Multi-region (naive)** (3 regions, full deployment):
```
Infrastructure: $15,000/month (3x single region)
- 3x Kubernetes clusters: $6,000
- 3x Databases: $4,500
- 3x Load balancers: $1,500
- 3x Monitoring: $3,000

Total: $15,000/month (3x cost!)
```

**Multi-region (optimized)**:
```
Infrastructure: $8,500/month
- Primary region (US): $5,000 (full deployment)
- Secondary region (EU): $2,500 (80% capacity)
- Tertiary region (AP): $1,000 (40% capacity)
  (Lower traffic, smaller deployment)

Total: $8,500/month (1.7x cost)
```

### Cost Optimization Strategies

**1. Right-size by traffic**:
```python
# Don't deploy identical infrastructure everywhere
REGION_SIZING = {
    "us-east-1": {
        "api_pods": 10,
        "worker_pods": 20,
        "db_size": "db.r5.xlarge",
        "traffic_percentage": 60,
    },
    "eu-west-1": {
        "api_pods": 6,
        "worker_pods": 12,
        "db_size": "db.r5.large",
        "traffic_percentage": 30,
    },
    "ap-southeast-1": {
        "api_pods": 4,
        "worker_pods": 8,
        "db_size": "db.r5.large",
        "traffic_percentage": 10,
    },
}
```

**2. Use CDN for static content**:
- Offload static assets to CloudFront/Cloudflare
- Reduce load on origin servers

**3. Optimize data transfer costs**:
- Keep data local (avoid cross-region transfer)
- Use CloudFront to cache API responses where possible

**4. Reserved instances**:
- Commit to 1-3 year reserved capacity
- Save 30-70% vs on-demand

---

## Monitoring Multi-Region Deployments

### Global Health Dashboard

```python
# code-examples/chapter-11-multi-region/monitoring/global_dashboard.py

from prometheus_client import Gauge, Counter
from typing import Dict

# Regional health metrics
region_health = Gauge(
    "agent_region_health",
    "Region health status (1=healthy, 0=unhealthy)",
    ["region"]
)

region_latency = Gauge(
    "agent_region_latency_seconds",
    "Average latency by region",
    ["region"]
)

region_error_rate = Gauge(
    "agent_region_error_rate",
    "Error rate by region",
    ["region"]
)

region_traffic = Counter(
    "agent_region_requests_total",
    "Total requests by region",
    ["region"]
)


class GlobalMonitor:
    """
    Monitor health across all regions.
    """

    REGIONS = ["us-east-1", "eu-west-1", "ap-southeast-1"]

    def collect_metrics(self):
        """
        Collect metrics from all regions.
        """
        for region in self.REGIONS:
            # Query regional Prometheus
            metrics = self._query_region_metrics(region)

            # Update global metrics
            region_health.labels(region=region).set(
                1 if metrics["healthy"] else 0
            )
            region_latency.labels(region=region).set(
                metrics["p95_latency"]
            )
            region_error_rate.labels(region=region).set(
                metrics["error_rate"]
            )

    def _query_region_metrics(self, region: str) -> Dict:
        """Query Prometheus in specific region."""
        # In production, query regional Prometheus instance
        # For now, placeholder data
        return {
            "healthy": True,
            "p95_latency": 0.15,  # 150ms
            "error_rate": 0.001,  # 0.1%
        }

    def check_regional_health(self) -> Dict[str, bool]:
        """
        Check if all regions are healthy.
        """
        health_status = {}

        for region in self.REGIONS:
            metrics = self._query_region_metrics(region)
            health_status[region] = metrics["healthy"]

        return health_status
```

### Grafana Global Dashboard

```json
{
  "dashboard": {
    "title": "Global Agent Health",
    "panels": [
      {
        "title": "Global Traffic Distribution",
        "type": "piechart",
        "targets": [
          {
            "expr": "sum by (region) (rate(agent_region_requests_total[5m]))"
          }
        ]
      },
      {
        "title": "Regional Latency (p95)",
        "type": "graph",
        "targets": [
          {
            "expr": "agent_region_latency_seconds",
            "legendFormat": "{{region}}"
          }
        ]
      },
      {
        "title": "Regional Error Rates",
        "type": "graph",
        "targets": [
          {
            "expr": "agent_region_error_rate",
            "legendFormat": "{{region}}"
          }
        ]
      },
      {
        "title": "Region Health Status",
        "type": "stat",
        "targets": [
          {
            "expr": "agent_region_health",
            "legendFormat": "{{region}}"
          }
        ]
      }
    ]
  }
}
```

---

## Multi-Region Deployment Checklist

Before deploying multi-region:

### Architecture
- [ ] GeoDNS routing configured
- [ ] Regional infrastructure deployed
- [ ] Health checks configured
- [ ] Failover tested
- [ ] Data residency enforced

### Compliance
- [ ] GDPR compliance verified (if EU)
- [ ] Data residency rules implemented
- [ ] Privacy policy updated
- [ ] Data processing agreements signed
- [ ] Audit logging configured

### Monitoring
- [ ] Global health dashboard
- [ ] Regional metrics tracked
- [ ] Cross-region alerts configured
- [ ] Latency monitored by region
- [ ] Failover alerts configured

### Testing
- [ ] Latency tested from each region
- [ ] Failover tested (simulate region outage)
- [ ] Data residency verified (EU data stays in EU)
- [ ] Load tested regionally
- [ ] Disaster recovery plan tested

### Cost
- [ ] Regional sizing optimized
- [ ] Reserved instances purchased
- [ ] Data transfer costs estimated
- [ ] Monitoring costs budgeted

---

## Key Takeaways

1. **Deploy close to users**: Reduce latency with geographic distribution
2. **Respect data residency**: GDPR and other laws require local data storage
3. **Plan for failure**: Implement health checks and failover
4. **Optimize costs**: Right-size deployments by traffic patterns
5. **Monitor globally**: Aggregate metrics across regions
6. **Test failover**: Regularly test region failures
7. **Start simple**: Single region first, expand as needed

**Production wisdom**: "Multi-region is powerful but complex. Only add it when you need it."

---

## Next Chapter Preview

You can now deploy globally. In the final chapter, **Chapter 12: Building an Agent Platform**, we'll cover:

- Platform architecture for multiple teams
- Multi-tenancy and isolation
- Resource quotas and billing
- Self-service developer experience
- API design for platform users

Let's build a platform that scales to hundreds of agent applications!
