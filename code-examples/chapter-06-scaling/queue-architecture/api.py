# code-examples/chapter-06-scaling/queue-architecture/api.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import redis
import uuid
import json
import structlog
from typing import Optional
from datetime import datetime

logger = structlog.get_logger()

app = FastAPI(title="Scalable Agent API")

# Redis client for queue and job storage
redis_client = redis.Redis(
    host="localhost",
    port=6379,
    decode_responses=True,
    socket_timeout=5,
    socket_connect_timeout=5,
)


class ChatRequest(BaseModel):
    user_id: str
    message: str
    priority: Optional[int] = 1  # 1=normal, 3=medium, 5=high


class ChatResponse(BaseModel):
    job_id: str
    status: str  # "queued", "processing", "completed", "failed"
    response: Optional[str] = None
    error: Optional[str] = None
    submitted_at: Optional[str] = None
    completed_at: Optional[str] = None


@app.post("/chat", response_model=ChatResponse, status_code=202)
def submit_chat(request: ChatRequest):
    """
    Submit a chat message for async processing.

    Returns immediately with job ID (202 Accepted).
    Client should poll GET /chat/{job_id} for results.
    """
    # Check queue depth for backpressure
    queue_depth = get_total_queue_depth()
    MAX_QUEUE_DEPTH = 10000

    if queue_depth > MAX_QUEUE_DEPTH:
        logger.error(
            "queue_depth_exceeded",
            queue_depth=queue_depth,
            max_depth=MAX_QUEUE_DEPTH,
        )
        raise HTTPException(
            status_code=503,
            detail=f"System overloaded. Queue depth: {queue_depth}. Please try again later."
        )

    # Generate job ID
    job_id = str(uuid.uuid4())

    # Create job
    job = {
        "job_id": job_id,
        "user_id": request.user_id,
        "message": request.message,
        "priority": request.priority,
        "status": "queued",
        "submitted_at": datetime.utcnow().isoformat(),
    }

    # Store job (1 hour TTL)
    redis_client.set(f"job:{job_id}", json.dumps(job), ex=3600)

    # Add to priority queue
    queue_name = f"queue:priority:{request.priority}"
    redis_client.rpush(queue_name, job_id)

    logger.info(
        "job_queued",
        job_id=job_id,
        user_id=request.user_id,
        priority=request.priority,
        queue_depth=queue_depth + 1,
    )

    return ChatResponse(
        job_id=job_id,
        status="queued",
        submitted_at=job["submitted_at"],
    )


@app.get("/chat/{job_id}", response_model=ChatResponse)
def get_chat_result(job_id: str):
    """
    Get the result of a chat job.

    Poll this endpoint until status is "completed" or "failed".
    """
    # Retrieve job
    job_data = redis_client.get(f"job:{job_id}")

    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found or expired")

    job = json.loads(job_data)

    return ChatResponse(
        job_id=job_id,
        status=job["status"],
        response=job.get("response"),
        error=job.get("error"),
        submitted_at=job.get("submitted_at"),
        completed_at=job.get("completed_at"),
    )


@app.get("/health")
def health_check():
    """Health check endpoint for load balancer."""
    try:
        # Check Redis connectivity
        redis_client.ping()
        return {"status": "healthy"}
    except Exception as e:
        logger.error("health_check_failed", error=str(e))
        raise HTTPException(status_code=503, detail="Unhealthy")


@app.get("/metrics")
def get_metrics():
    """Metrics endpoint for monitoring."""
    queue_depth = get_total_queue_depth()

    # Count jobs by status
    # In production, use Redis sorted sets or dedicated metrics store
    return {
        "queue_depth": queue_depth,
        "timestamp": datetime.utcnow().isoformat(),
    }


def get_total_queue_depth() -> int:
    """Get total number of jobs in all queues."""
    total = 0
    for priority in [1, 3, 5]:
        queue_name = f"queue:priority:{priority}"
        total += redis_client.llen(queue_name)
    return total


if __name__ == "__main__":
    import uvicorn

    # Configure structured logging
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
    )

    # Run API server
    uvicorn.run(app, host="0.0.0.0", port=8000, log_config=None)
