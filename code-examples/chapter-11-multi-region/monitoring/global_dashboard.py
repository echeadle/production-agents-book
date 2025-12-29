"""
Global Multi-Region Monitoring Dashboard
Chapter 11: Multi-Region Deployment

Aggregates metrics from all regional Prometheus instances
to provide a global view of agent health across regions.
"""

from typing import Dict, List
from dataclasses import dataclass
from enum import Enum
import requests
from prometheus_client import Gauge, Counter
import structlog

logger = structlog.get_logger()


class HealthStatus(Enum):
    """Regional health status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class RegionMetrics:
    """Metrics from a single region."""

    region: str
    health: HealthStatus
    latency_p95: float  # seconds
    error_rate: float  # percentage (0.0-1.0)
    requests_per_second: float
    availability: float  # percentage (0.0-1.0)


# Prometheus metrics for global dashboard
region_health_gauge = Gauge(
    "agent_region_health",
    "Health status of each region (0=unhealthy, 1=degraded, 2=healthy)",
    ["region"],
)

region_latency_gauge = Gauge(
    "agent_region_latency_p95_seconds",
    "P95 latency by region",
    ["region"],
)

region_error_rate_gauge = Gauge(
    "agent_region_error_rate",
    "Error rate by region",
    ["region"],
)

region_traffic_counter = Counter(
    "agent_region_requests_total",
    "Total requests by region",
    ["region"],
)


class GlobalMonitor:
    """
    Monitor agent health across all regions.
    """

    def __init__(self, region_prometheus_urls: Dict[str, str]):
        """
        Initialize global monitor.

        Args:
            region_prometheus_urls: Map of region name to Prometheus URL
                Example: {
                    "us-east-1": "https://prometheus-us.company.com",
                    "eu-west-1": "https://prometheus-eu.company.com",
                    "ap-southeast-1": "https://prometheus-ap.company.com"
                }
        """
        self.region_urls = region_prometheus_urls

    def collect_metrics(self) -> List[RegionMetrics]:
        """
        Collect metrics from all regions.

        Returns:
            List of RegionMetrics for each region
        """
        all_metrics = []

        for region, prom_url in self.region_urls.items():
            try:
                metrics = self._query_region(region, prom_url)
                all_metrics.append(metrics)

                # Update Prometheus metrics
                self._update_metrics(metrics)

            except Exception as e:
                logger.error(
                    "failed_to_collect_region_metrics",
                    region=region,
                    error=str(e),
                )

                # Mark region as unhealthy
                region_health_gauge.labels(region=region).set(0)

        return all_metrics

    def _query_region(self, region: str, prom_url: str) -> RegionMetrics:
        """
        Query metrics from a single region's Prometheus.

        Args:
            region: Region name
            prom_url: Prometheus URL for the region

        Returns:
            RegionMetrics for the region
        """
        # Query p95 latency
        latency_query = 'histogram_quantile(0.95, rate(agent_response_seconds_bucket[5m]))'
        latency = self._prometheus_query(prom_url, latency_query)

        # Query error rate
        error_query = """
            (
              sum(rate(agent_errors_total[5m]))
              /
              sum(rate(agent_requests_total[5m]))
            )
        """
        error_rate = self._prometheus_query(prom_url, error_query)

        # Query request rate
        requests_query = 'sum(rate(agent_requests_total[5m]))'
        requests_per_second = self._prometheus_query(prom_url, requests_query)

        # Query availability (from health check metric)
        availability_query = 'avg_over_time(up{job="agent-api"}[5m])'
        availability = self._prometheus_query(prom_url, availability_query)

        # Determine health status
        health = self._determine_health(error_rate, latency, availability)

        logger.info(
            "region_metrics_collected",
            region=region,
            health=health.value,
            latency_p95=latency,
            error_rate=error_rate,
        )

        return RegionMetrics(
            region=region,
            health=health,
            latency_p95=latency,
            error_rate=error_rate,
            requests_per_second=requests_per_second,
            availability=availability,
        )

    def _prometheus_query(self, prom_url: str, query: str) -> float:
        """
        Execute Prometheus query and return scalar result.

        Args:
            prom_url: Prometheus base URL
            query: PromQL query

        Returns:
            Query result as float
        """
        response = requests.get(
            f"{prom_url}/api/v1/query",
            params={"query": query},
            timeout=10,
        )
        response.raise_for_status()

        data = response.json()

        if data["status"] != "success":
            raise ValueError(f"Prometheus query failed: {data}")

        result = data["data"]["result"]

        if not result:
            return 0.0

        # Extract value from result
        value = float(result[0]["value"][1])
        return value

    def _determine_health(
        self, error_rate: float, latency: float, availability: float
    ) -> HealthStatus:
        """
        Determine health status based on metrics.

        Args:
            error_rate: Error rate (0.0-1.0)
            latency: P95 latency in seconds
            availability: Availability (0.0-1.0)

        Returns:
            HealthStatus
        """
        # Unhealthy: High error rate or unavailable
        if error_rate > 0.10 or availability < 0.95:
            return HealthStatus.UNHEALTHY

        # Degraded: Elevated error rate or high latency
        if error_rate > 0.05 or latency > 10.0:
            return HealthStatus.DEGRADED

        # Healthy
        return HealthStatus.HEALTHY

    def _update_metrics(self, metrics: RegionMetrics):
        """
        Update Prometheus metrics for the region.

        Args:
            metrics: RegionMetrics to export
        """
        # Health status (0=unhealthy, 1=degraded, 2=healthy)
        health_value = {
            HealthStatus.UNHEALTHY: 0,
            HealthStatus.DEGRADED: 1,
            HealthStatus.HEALTHY: 2,
        }[metrics.health]

        region_health_gauge.labels(region=metrics.region).set(health_value)
        region_latency_gauge.labels(region=metrics.region).set(metrics.latency_p95)
        region_error_rate_gauge.labels(region=metrics.region).set(metrics.error_rate)

    def check_regional_health(self) -> Dict[str, bool]:
        """
        Check if each region is healthy (for failover decisions).

        Returns:
            Map of region to health status (True = healthy)
        """
        metrics = self.collect_metrics()

        health_status = {}
        for m in metrics:
            health_status[m.region] = m.health == HealthStatus.HEALTHY

        return health_status

    def get_healthiest_region(self) -> str:
        """
        Get the healthiest region (for routing decisions).

        Returns:
            Region name of healthiest region
        """
        metrics = self.collect_metrics()

        # Sort by health (healthy > degraded > unhealthy), then by latency
        sorted_regions = sorted(
            metrics,
            key=lambda m: (
                {
                    HealthStatus.HEALTHY: 2,
                    HealthStatus.DEGRADED: 1,
                    HealthStatus.UNHEALTHY: 0,
                }[m.health],
                -m.latency_p95,  # Lower latency is better (negate for desc sort)
            ),
            reverse=True,
        )

        if sorted_regions:
            return sorted_regions[0].region

        return "us-east-1"  # Default fallback


# =========================================================================
# Example Usage
# =========================================================================


def main():
    """Example usage of global monitor."""

    # Regional Prometheus URLs
    region_urls = {
        "us-east-1": "http://prometheus-us.company.com",
        "eu-west-1": "http://prometheus-eu.company.com",
        "ap-southeast-1": "http://prometheus-ap.company.com",
    }

    # Initialize monitor
    monitor = GlobalMonitor(region_urls)

    # Collect metrics from all regions
    print("Collecting metrics from all regions...\n")
    metrics = monitor.collect_metrics()

    # Display results
    print("=" * 80)
    print("GLOBAL AGENT HEALTH DASHBOARD")
    print("=" * 80)

    for m in metrics:
        print(f"\nRegion: {m.region}")
        print(f"  Health: {m.health.value.upper()}")
        print(f"  P95 Latency: {m.latency_p95:.2f}s")
        print(f"  Error Rate: {m.error_rate * 100:.2f}%")
        print(f"  Requests/sec: {m.requests_per_second:.0f}")
        print(f"  Availability: {m.availability * 100:.2f}%")

    print("\n" + "=" * 80)

    # Check regional health
    health_status = monitor.check_regional_health()
    print("\nREGIONAL HEALTH STATUS:")
    for region, is_healthy in health_status.items():
        status = "✅ HEALTHY" if is_healthy else "❌ UNHEALTHY"
        print(f"  {region}: {status}")

    # Get healthiest region
    healthiest = monitor.get_healthiest_region()
    print(f"\nHealthiest region: {healthiest}")


if __name__ == "__main__":
    main()
