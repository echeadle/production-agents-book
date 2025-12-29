"""
Debug Tools for Production Incidents
Chapter 10: Incident Response

Tools for investigating and resolving production incidents:
- Find stale jobs (stuck in processing)
- Kill runaway agents
- Analyze conversation history
- Identify error patterns

Usage:
    python debug_tools.py stale-jobs --age 300
    python debug_tools.py kill-stale --age 600
    python debug_tools.py analyze-conv --conv-id abc123
    python debug_tools.py errors --hours 1
"""

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import redis
import structlog

logger = structlog.get_logger()


class DebugTools:
    """
    Tools for debugging production incidents.

    Connects to Redis to analyze agent state and identify issues.
    """

    def __init__(self, redis_client: redis.Redis):
        """
        Initialize debug tools.

        Args:
            redis_client: Redis connection
        """
        self.redis = redis_client

    # =====================================================================
    # Stale Job Detection
    # =====================================================================

    def find_stale_jobs(self, max_age_seconds: int = 300) -> List[Dict[str, Any]]:
        """
        Find jobs stuck in processing state longer than max_age.

        Stale jobs indicate:
        - Runaway agents
        - Hung requests
        - Infinite loops
        - Crashed workers

        Args:
            max_age_seconds: Maximum age in seconds (default: 300 = 5 minutes)

        Returns:
            List of stale jobs with metadata:
            [
                {
                    "job_id": "job:123",
                    "user_id": "user_456",
                    "started_at": "2024-01-15T03:15:00Z",
                    "age_seconds": 450,
                    "message_preview": "Calculate the meaning of..."
                }
            ]
        """
        stale_jobs = []
        now = datetime.now()

        # Scan for jobs in processing state
        for key in self.redis.scan_iter("job:*:processing"):
            try:
                # Get job metadata
                job_data = self.redis.hgetall(key)

                if not job_data:
                    continue

                # Parse start time
                started_at_str = job_data.get(b"started_at", b"").decode("utf-8")
                if not started_at_str:
                    continue

                started_at = datetime.fromisoformat(started_at_str)
                age = (now - started_at).total_seconds()

                # Check if stale
                if age > max_age_seconds:
                    job_id = job_data.get(b"job_id", b"").decode("utf-8")
                    user_id = job_data.get(b"user_id", b"").decode("utf-8")
                    message = job_data.get(b"message", b"").decode("utf-8")

                    stale_jobs.append(
                        {
                            "job_id": job_id,
                            "user_id": user_id,
                            "started_at": started_at_str,
                            "age_seconds": int(age),
                            "message_preview": message[:100]
                            + ("..." if len(message) > 100 else ""),
                        }
                    )

                    logger.warning(
                        "stale_job_found",
                        job_id=job_id,
                        user_id=user_id,
                        age_seconds=int(age),
                    )

            except Exception as e:
                logger.error("error_checking_job", key=key, error=str(e))
                continue

        return sorted(stale_jobs, key=lambda x: x["age_seconds"], reverse=True)

    def kill_stale_jobs(self, max_age_seconds: int = 600) -> int:
        """
        Forcefully terminate stale jobs.

        WARNING: This is destructive. Use with caution.

        Args:
            max_age_seconds: Maximum age in seconds (default: 600 = 10 minutes)

        Returns:
            Number of jobs killed
        """
        stale_jobs = self.find_stale_jobs(max_age_seconds)
        killed_count = 0

        for job in stale_jobs:
            job_id = job["job_id"]

            try:
                # Mark job as failed
                self.redis.hset(
                    f"job:{job_id}:processing",
                    "status",
                    "failed_killed",
                )
                self.redis.hset(
                    f"job:{job_id}:processing",
                    "killed_at",
                    datetime.now().isoformat(),
                )

                # Move to failed queue
                self.redis.lpush("queue:failed", job_id)

                # Remove from processing
                self.redis.delete(f"job:{job_id}:processing")

                killed_count += 1

                logger.info(
                    "job_killed",
                    job_id=job_id,
                    age_seconds=job["age_seconds"],
                )

            except Exception as e:
                logger.error("error_killing_job", job_id=job_id, error=str(e))

        logger.info("stale_jobs_killed", count=killed_count)
        return killed_count

    # =====================================================================
    # Conversation Analysis
    # =====================================================================

    def analyze_conversation(self, conversation_id: str) -> Dict[str, Any]:
        """
        Analyze conversation history for debugging.

        Useful for:
        - Understanding agent behavior
        - Identifying infinite loops
        - Checking token usage
        - Finding error patterns

        Args:
            conversation_id: Conversation ID to analyze

        Returns:
            Analysis results:
            {
                "conversation_id": "abc123",
                "message_count": 45,
                "token_estimate": 12000,
                "tool_calls": ["search", "calculate", ...],
                "errors": ["API timeout", ...],
                "samples": [...]
            }
        """
        key = f"conversation:{conversation_id}"

        # Check if conversation exists
        if not self.redis.exists(key):
            return {
                "error": f"Conversation {conversation_id} not found",
                "conversation_id": conversation_id,
            }

        # Get conversation history
        history_json = self.redis.get(key)
        if not history_json:
            return {
                "error": "Empty conversation",
                "conversation_id": conversation_id,
            }

        history = json.loads(history_json)

        # Analyze messages
        message_count = len(history)
        token_estimate = sum(len(json.dumps(msg)) for msg in history) // 4
        tool_calls = []
        errors = []

        for msg in history:
            # Extract tool calls
            if isinstance(msg.get("content"), list):
                for block in msg["content"]:
                    if isinstance(block, dict):
                        if block.get("type") == "tool_use":
                            tool_calls.append(block.get("name", "unknown"))
                        elif block.get("type") == "tool_result":
                            if block.get("is_error"):
                                errors.append(block.get("content", "Unknown error"))

        # Get message samples
        samples = []
        if message_count > 0:
            # First message
            samples.append({"type": "first", "message": history[0]})

            # Last message
            if message_count > 1:
                samples.append({"type": "last", "message": history[-1]})

            # Sample middle messages
            if message_count > 5:
                mid_idx = message_count // 2
                samples.append({"type": "middle", "message": history[mid_idx]})

        return {
            "conversation_id": conversation_id,
            "message_count": message_count,
            "token_estimate": token_estimate,
            "tool_calls": tool_calls,
            "tool_call_counts": dict(Counter(tool_calls)),
            "errors": errors,
            "error_count": len(errors),
            "samples": samples,
        }

    # =====================================================================
    # Error Pattern Analysis
    # =====================================================================

    def get_error_patterns(self, hours: int = 1) -> Dict[str, int]:
        """
        Analyze error patterns from recent logs.

        Args:
            hours: Number of hours to analyze (default: 1)

        Returns:
            Dictionary of error types and counts:
            {
                "APITimeout": 45,
                "RateLimitExceeded": 23,
                "AuthenticationError": 12
            }
        """
        # This would integrate with your logging system
        # For this example, we'll check Redis for recent errors

        errors = Counter()
        cutoff_time = datetime.now() - timedelta(hours=hours)

        # Scan error logs in Redis (assumes errors are logged to Redis)
        for key in self.redis.scan_iter("error:*"):
            try:
                error_data = self.redis.hgetall(key)
                if not error_data:
                    continue

                # Check timestamp
                timestamp_str = error_data.get(b"timestamp", b"").decode("utf-8")
                if timestamp_str:
                    timestamp = datetime.fromisoformat(timestamp_str)
                    if timestamp < cutoff_time:
                        continue

                # Count error type
                error_type = error_data.get(b"type", b"Unknown").decode("utf-8")
                errors[error_type] += 1

            except Exception as e:
                logger.error("error_analyzing_error", key=key, error=str(e))
                continue

        return dict(errors.most_common())

    # =====================================================================
    # Health Check
    # =====================================================================

    def check_system_health(self) -> Dict[str, Any]:
        """
        Check overall system health.

        Returns:
            Health status:
            {
                "redis": "healthy",
                "queue_depth": 45,
                "stale_jobs": 2,
                "error_rate": 0.05,
                "circuit_breakers": {"anthropic": "closed"}
            }
        """
        health = {}

        # Check Redis
        try:
            self.redis.ping()
            health["redis"] = "healthy"
        except Exception as e:
            health["redis"] = f"unhealthy: {str(e)}"

        # Check queue depth
        try:
            queue_depth = self.redis.llen("queue:pending")
            health["queue_depth"] = queue_depth
        except Exception as e:
            health["queue_depth"] = f"error: {str(e)}"

        # Check stale jobs
        try:
            stale_jobs = self.find_stale_jobs(max_age_seconds=300)
            health["stale_jobs"] = len(stale_jobs)
        except Exception as e:
            health["stale_jobs"] = f"error: {str(e)}"

        # Check circuit breakers
        try:
            circuit_breakers = {}
            for key in self.redis.scan_iter("circuit_breaker:*"):
                name = key.decode("utf-8").split(":")[-1]
                state = self.redis.get(key).decode("utf-8")
                circuit_breakers[name] = state
            health["circuit_breakers"] = circuit_breakers
        except Exception as e:
            health["circuit_breakers"] = f"error: {str(e)}"

        return health


# =========================================================================
# CLI Interface
# =========================================================================


def main():
    """Command-line interface for debug tools."""
    parser = argparse.ArgumentParser(description="Production Debug Tools")
    parser.add_argument(
        "command",
        choices=["stale-jobs", "kill-stale", "analyze-conv", "errors", "health"],
        help="Command to execute",
    )
    parser.add_argument(
        "--age", type=int, default=300, help="Max age in seconds (for stale-jobs)"
    )
    parser.add_argument(
        "--conv-id", type=str, help="Conversation ID (for analyze-conv)"
    )
    parser.add_argument("--hours", type=int, default=1, help="Hours to analyze")
    parser.add_argument(
        "--redis-host", default="localhost", help="Redis host (default: localhost)"
    )
    parser.add_argument(
        "--redis-port", type=int, default=6379, help="Redis port (default: 6379)"
    )

    args = parser.parse_args()

    # Connect to Redis
    try:
        redis_client = redis.Redis(
            host=args.redis_host,
            port=args.redis_port,
            decode_responses=False,
        )
        redis_client.ping()
    except Exception as e:
        print(f"Error connecting to Redis: {e}", file=sys.stderr)
        sys.exit(1)

    # Initialize debug tools
    tools = DebugTools(redis_client)

    # Execute command
    if args.command == "stale-jobs":
        stale_jobs = tools.find_stale_jobs(max_age_seconds=args.age)
        print(json.dumps(stale_jobs, indent=2))

    elif args.command == "kill-stale":
        killed = tools.kill_stale_jobs(max_age_seconds=args.age)
        print(f"Killed {killed} stale jobs")

    elif args.command == "analyze-conv":
        if not args.conv_id:
            print("Error: --conv-id required for analyze-conv", file=sys.stderr)
            sys.exit(1)
        analysis = tools.analyze_conversation(args.conv_id)
        print(json.dumps(analysis, indent=2))

    elif args.command == "errors":
        errors = tools.get_error_patterns(hours=args.hours)
        print(json.dumps(errors, indent=2))

    elif args.command == "health":
        health = tools.check_system_health()
        print(json.dumps(health, indent=2))


if __name__ == "__main__":
    main()
