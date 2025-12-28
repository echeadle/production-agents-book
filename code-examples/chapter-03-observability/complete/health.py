"""
Health check server with Prometheus metrics endpoint.

Provides:
- /health/live - Liveness probe (is the process alive?)
- /health/ready - Readiness probe (can it serve traffic?)
- /metrics - Prometheus metrics endpoint

This server runs alongside the agent to provide observability endpoints.
"""

import os
import shutil
from typing import Dict
from enum import Enum

from fastapi import FastAPI, Response, status
from fastapi.responses import PlainTextResponse
import structlog

from metrics import get_metrics, get_metrics_content_type

log = structlog.get_logger()

app = FastAPI(title="Agent Health & Metrics")


class HealthStatus(str, Enum):
    """Health check status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"


class HealthCheck:
    """Individual health check result."""
    def __init__(self, status: HealthStatus, message: str = ""):
        self.status = status
        self.message = message

    def to_dict(self) -> Dict:
        return {"status": self.status.value, "message": self.message}


def check_anthropic_api() -> HealthCheck:
    """
    Check Anthropic API availability.

    NOTE: We don't make a real API call here to avoid costs.
    Instead, we validate the API key format.

    For deeper validation, use actual agent metrics:
    - llm_requests_total (are requests succeeding?)
    - llm_errors_total (error rate)
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        return HealthCheck(
            HealthStatus.FAILED,
            "ANTHROPIC_API_KEY environment variable not set"
        )

    # Basic format validation (no billable API call)
    if not api_key.startswith("sk-ant-"):
        return HealthCheck(
            HealthStatus.FAILED,
            "API key has invalid format"
        )

    return HealthCheck(HealthStatus.HEALTHY, "API key configured")


def check_disk_space(threshold_gb: float = 1.0) -> HealthCheck:
    """
    Check available disk space.

    Args:
        threshold_gb: Minimum required free space in GB

    Returns:
        HealthCheck result
    """
    try:
        stat = shutil.disk_usage("/")
        free_gb = stat.free / (1024 ** 3)

        if free_gb < threshold_gb:
            return HealthCheck(
                HealthStatus.DEGRADED,
                f"Low disk space: {free_gb:.2f}GB available (threshold: {threshold_gb}GB)"
            )

        return HealthCheck(
            HealthStatus.HEALTHY,
            f"Disk space OK: {free_gb:.2f}GB available"
        )
    except Exception as e:
        return HealthCheck(HealthStatus.FAILED, f"Failed to check disk space: {e}")


def check_notes_directory() -> HealthCheck:
    """
    Check if notes directory exists and is writable.

    Returns:
        HealthCheck result
    """
    notes_dir = "notes"

    try:
        if not os.path.exists(notes_dir):
            os.makedirs(notes_dir)

        # Test write
        test_file = os.path.join(notes_dir, ".health_check")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)

        return HealthCheck(HealthStatus.HEALTHY, "Notes directory is writable")

    except Exception as e:
        return HealthCheck(
            HealthStatus.FAILED,
            f"Notes directory not writable: {e}"
        )


@app.get("/health/live")
async def liveness_probe():
    """
    Liveness probe for Kubernetes.

    Returns:
        200 if the process is alive

    Kubernetes will restart the pod if this fails.
    """
    log.debug("health.liveness_check")
    return {"status": "alive"}


@app.get("/health/ready")
async def readiness_probe(response: Response):
    """
    Readiness probe for Kubernetes.

    Checks:
    - Anthropic API key is configured
    - Sufficient disk space
    - Notes directory is writable

    Returns:
        200 if ready to serve traffic
        503 if degraded or failed

    Kubernetes will remove pod from load balancer if this fails.
    """
    log.debug("health.readiness_check")

    checks = {
        "anthropic_api": check_anthropic_api(),
        "disk_space": check_disk_space(threshold_gb=1.0),
        "notes_directory": check_notes_directory(),
    }

    # Determine overall status
    statuses = [check.status for check in checks.values()]

    if HealthStatus.FAILED in statuses:
        overall_status = HealthStatus.FAILED
    elif HealthStatus.DEGRADED in statuses:
        overall_status = HealthStatus.DEGRADED
    else:
        overall_status = HealthStatus.HEALTHY

    # Set HTTP status code
    if overall_status in [HealthStatus.FAILED, HealthStatus.DEGRADED]:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    else:
        response.status_code = status.HTTP_200_OK

    result = {
        "status": overall_status.value,
        "checks": {name: check.to_dict() for name, check in checks.items()},
    }

    log.info(
        "health.readiness_check_completed",
        overall_status=overall_status.value,
        http_status=response.status_code,
    )

    return result


@app.get("/metrics")
async def metrics_endpoint():
    """
    Prometheus metrics endpoint.

    Returns all application metrics in Prometheus format.

    Prometheus will scrape this endpoint at regular intervals
    (configured in prometheus.yml).

    Example prometheus.yml:
        scrape_configs:
          - job_name: 'agent'
            scrape_interval: 15s
            static_configs:
              - targets: ['localhost:8080']
    """
    log.debug("metrics.scraped")

    metrics_data = get_metrics()
    return PlainTextResponse(
        content=metrics_data.decode("utf-8"),
        media_type=get_metrics_content_type(),
    )


@app.get("/")
async def root():
    """Root endpoint with available routes."""
    return {
        "service": "task-automation-agent",
        "version": "0.1.0",
        "endpoints": {
            "/health/live": "Liveness probe",
            "/health/ready": "Readiness probe",
            "/metrics": "Prometheus metrics",
        },
    }


def main():
    """Run health check server."""
    import uvicorn
    from dotenv import load_dotenv
    from logging_config import configure_logging

    load_dotenv()

    # Configure logging
    configure_logging(
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        json_logs=os.getenv("JSON_LOGS", "false").lower() == "true",
    )

    log.info("health_server.starting", port=8080)

    # Run server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
        log_config=None,  # Use our logging config
    )


if __name__ == "__main__":
    main()
