"""
Health check endpoints for production monitoring.

Provides liveness and readiness probes for container orchestration
(Kubernetes, ECS, etc.).
"""

import os
from fastapi import FastAPI, Response, status
from pydantic import BaseModel
from typing import Dict
import anthropic


app = FastAPI(title="Agent Health Checks")


class LivenessResponse(BaseModel):
    """Response model for liveness probe."""
    status: str


class HealthCheck(BaseModel):
    """Individual health check result."""
    status: str
    message: str = ""


class ReadinessResponse(BaseModel):
    """Response model for readiness probe."""
    status: str
    checks: Dict[str, HealthCheck]


@app.get("/health/live", response_model=LivenessResponse)
def liveness(response: Response):
    """
    Liveness probe: Is the service alive?

    This endpoint should only check if the process is running.
    Kubernetes will restart the container if this fails.

    Returns:
        200: Service is alive
    """
    return {"status": "ok"}


@app.get("/health/ready", response_model=ReadinessResponse)
def readiness(response: Response):
    """
    Readiness probe: Is the service ready to handle traffic?

    This endpoint checks dependencies before reporting ready.
    Kubernetes will stop routing traffic if this fails (but won't restart).

    Returns:
        200: Service is ready
        503: Service is not ready
    """
    checks: Dict[str, HealthCheck] = {}
    overall_status = "ok"

    # Check 1: Validate Anthropic API key (without making billable calls)
    try:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            checks["anthropic_api"] = HealthCheck(
                status="failed",
                message="API key not configured"
            )
            overall_status = "failed"
        elif not api_key.startswith("sk-ant-"):
            # Basic format validation (Anthropic keys start with sk-ant-)
            checks["anthropic_api"] = HealthCheck(
                status="failed",
                message="API key has invalid format"
            )
            overall_status = "failed"
        else:
            # API key is configured and has correct format
            # Note: We don't actually call the API here to avoid billable requests
            # Deep validation would require an actual API call (260k+/month on health checks)
            # For production, monitor actual agent request success/failure rates instead
            checks["anthropic_api"] = HealthCheck(
                status="ok",
                message="API key configured (format valid)"
            )

    except Exception as e:
        checks["anthropic_api"] = HealthCheck(
            status="failed",
            message=f"API key validation failed: {str(e)}"
        )
        overall_status = "failed"

    # Check 2: Disk space for notes/ directory
    try:
        import shutil
        stat = shutil.disk_usage(".")
        free_gb = stat.free / (1024**3)

        if free_gb < 0.1:  # Less than 100 MB free
            checks["disk_space"] = HealthCheck(
                status="failed",
                message=f"Critically low: {free_gb:.2f} GB free"
            )
            overall_status = "failed"
        elif free_gb < 1.0:  # Less than 1 GB free
            checks["disk_space"] = HealthCheck(
                status="degraded",
                message=f"Low: {free_gb:.2f} GB free"
            )
            if overall_status == "ok":
                overall_status = "degraded"
        else:
            checks["disk_space"] = HealthCheck(
                status="ok",
                message=f"{free_gb:.2f} GB free"
            )
    except Exception as e:
        checks["disk_space"] = HealthCheck(
            status="failed",
            message=f"Check failed: {str(e)}"
        )
        overall_status = "failed"

    # Check 3: Can we create the notes directory?
    try:
        os.makedirs("notes", exist_ok=True)
        checks["notes_directory"] = HealthCheck(
            status="ok",
            message="Writable"
        )
    except Exception as e:
        checks["notes_directory"] = HealthCheck(
            status="failed",
            message=f"Cannot create: {str(e)}"
        )
        overall_status = "failed"

    # Set HTTP status code based on overall health
    # Both failed and degraded return 503 to remove pod from load balancer
    if overall_status in ["failed", "degraded"]:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    else:
        response.status_code = status.HTTP_200_OK

    return {
        "status": overall_status,
        "checks": checks
    }


@app.get("/")
def root():
    """Root endpoint with basic info."""
    return {
        "service": "Task Automation Agent",
        "version": "0.1.0",
        "health": {
            "liveness": "/health/live",
            "readiness": "/health/ready"
        }
    }


if __name__ == "__main__":
    import uvicorn

    print("Starting health check server on http://localhost:8080")
    print("Endpoints:")
    print("  - Liveness:  http://localhost:8080/health/live")
    print("  - Readiness: http://localhost:8080/health/ready")

    uvicorn.run(app, host="0.0.0.0", port=8080)
