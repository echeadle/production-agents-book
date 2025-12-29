# code-examples/chapter-06-scaling/queue-architecture/worker.py

import redis
import json
import structlog
import anthropic
import time
import signal
import sys
from typing import Optional
from datetime import datetime
import os
from dotenv import load_dotenv

logger = structlog.get_logger()


class AgentWorker:
    """
    Worker that processes agent jobs from the queue.

    In production, you'd run multiple instances of this worker
    to process jobs in parallel.

    Features:
    - Priority queue processing (high priority first)
    - Graceful shutdown
    - Error handling and retry logic
    - Metrics tracking
    """

    def __init__(
        self,
        api_key: str,
        redis_host: str = "localhost",
        worker_id: Optional[str] = None,
    ):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.redis = redis.Redis(
            host=redis_host,
            port=6379,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
        )

        self.worker_id = worker_id or f"worker-{os.getpid()}"
        self.running = True

        # Priority queues (process high priority first)
        self.queues = [
            "queue:priority:5",  # High priority
            "queue:priority:3",  # Medium priority
            "queue:priority:1",  # Normal priority
        ]

        # Metrics
        self.jobs_processed = 0
        self.jobs_failed = 0

        # Setup graceful shutdown
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        """Handle graceful shutdown."""
        logger.info(
            "shutdown_requested",
            worker_id=self.worker_id,
            signal=signum,
        )
        self.running = False

    def run(self):
        """
        Main worker loop.

        Continuously polls queues and processes jobs until shutdown.
        """
        logger.info("worker_started", worker_id=self.worker_id)

        while self.running:
            try:
                # Try to get a job from highest priority queue first
                job_id = self._get_next_job()

                if job_id:
                    self._process_job(job_id)
                else:
                    # No jobs available, sleep briefly
                    time.sleep(0.1)

            except KeyboardInterrupt:
                logger.info("keyboard_interrupt", worker_id=self.worker_id)
                break
            except Exception as e:
                logger.error(
                    "worker_error",
                    worker_id=self.worker_id,
                    error=str(e),
                )
                time.sleep(1)

        logger.info(
            "worker_stopped",
            worker_id=self.worker_id,
            jobs_processed=self.jobs_processed,
            jobs_failed=self.jobs_failed,
        )

    def _get_next_job(self) -> Optional[str]:
        """Get next job from highest priority queue."""
        for queue in self.queues:
            # Try to pop a job (atomic operation)
            job_id = self.redis.lpop(queue)
            if job_id:
                logger.info(
                    "job_dequeued",
                    worker_id=self.worker_id,
                    job_id=job_id,
                    queue=queue,
                )
                return job_id
        return None

    def _process_job(self, job_id: str):
        """Process a single job."""
        # Load job
        job_data = self.redis.get(f"job:{job_id}")
        if not job_data:
            logger.error(
                "job_not_found",
                worker_id=self.worker_id,
                job_id=job_id,
            )
            return

        job = json.loads(job_data)

        # Update status to processing
        job["status"] = "processing"
        job["started_at"] = datetime.utcnow().isoformat()
        job["worker_id"] = self.worker_id
        self.redis.set(f"job:{job_id}", json.dumps(job), ex=3600)

        logger.info(
            "job_processing_started",
            worker_id=self.worker_id,
            job_id=job_id,
            user_id=job["user_id"],
        )

        try:
            # Load conversation history
            conversation_key = f"conv:{job['user_id']}"
            history = self.redis.get(conversation_key)
            messages = json.loads(history) if history else []

            # Add user message
            messages.append({"role": "user", "content": job["message"]})

            # Call Claude API
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1024,
                messages=messages,
            )

            # Extract response
            response_text = next(
                (block.text for block in response.content if hasattr(block, "text")),
                ""
            )

            # Update conversation history
            messages.append({"role": "assistant", "content": response_text})
            self.redis.set(conversation_key, json.dumps(messages), ex=3600)

            # Mark job as completed
            job["status"] = "completed"
            job["response"] = response_text
            job["completed_at"] = datetime.utcnow().isoformat()
            job["input_tokens"] = response.usage.input_tokens
            job["output_tokens"] = response.usage.output_tokens
            self.redis.set(f"job:{job_id}", json.dumps(job), ex=3600)

            # Update metrics
            self.jobs_processed += 1

            logger.info(
                "job_completed",
                worker_id=self.worker_id,
                job_id=job_id,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                processing_time_ms=(
                    (datetime.fromisoformat(job["completed_at"]) -
                     datetime.fromisoformat(job["started_at"])).total_seconds() * 1000
                ),
            )

        except Exception as e:
            # Mark job as failed
            job["status"] = "failed"
            job["error"] = str(e)
            job["failed_at"] = datetime.utcnow().isoformat()
            self.redis.set(f"job:{job_id}", json.dumps(job), ex=3600)

            # Update metrics
            self.jobs_failed += 1

            logger.error(
                "job_failed",
                worker_id=self.worker_id,
                job_id=job_id,
                error=str(e),
            )


if __name__ == "__main__":
    load_dotenv()

    # Configure structured logging
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
    )

    # Start worker
    worker = AgentWorker(api_key=os.getenv("ANTHROPIC_API_KEY"))

    try:
        worker.run()
    except KeyboardInterrupt:
        logger.info("worker_interrupted")
        sys.exit(0)
