"""
Redis-backed circuit breaker for distributed systems.

Solves the problem: In-memory circuit breakers don't share state across
processes/pods. Each worker has its own circuit state, leading to
inconsistent behavior.

Solution: Use Redis as shared storage for circuit breaker state.
All workers/pods share the same circuit state.

Example:
    Worker 1: Circuit trips → Updates Redis → State = OPEN
    Worker 2: Reads from Redis → State = OPEN → Fails fast
    Worker 3: Reads from Redis → State = OPEN → Fails fast

    Now all workers see the same circuit state!
"""

import time
import logging
from enum import Enum
from typing import Callable, TypeVar, Optional
from functools import wraps

try:
    import redis
except ImportError:
    redis = None

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitState(Enum):
    """States of the circuit breaker."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open."""
    pass


class RedisCircuitBreaker:
    """
    Circuit breaker with shared Redis state.

    State is stored in Redis, shared across all processes/pods.

    Redis keys:
    - {name}:state - Current state (CLOSED/OPEN/HALF_OPEN)
    - {name}:failures - Failure count
    - {name}:last_failure - Timestamp of last failure
    - {name}:successes - Success count (for HALF_OPEN state)
    """

    def __init__(
        self,
        name: str,
        redis_client: "redis.Redis",
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        success_threshold: int = 3,
        expected_exception: type = Exception,
        key_prefix: str = "circuit_breaker"
    ):
        """
        Initialize Redis-backed circuit breaker.

        Args:
            name: Circuit breaker name
            redis_client: Redis client instance
            failure_threshold: Failures before opening circuit
            recovery_timeout: Seconds before testing recovery
            success_threshold: Successes to close from half-open
            expected_exception: Exception type that counts as failure
            key_prefix: Redis key prefix
        """
        if redis is None:
            raise ImportError("redis package required. Install with: pip install redis")

        self.name = name
        self.redis = redis_client
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self.expected_exception = expected_exception

        # Redis keys
        self.key_prefix = f"{key_prefix}:{name}"
        self.state_key = f"{self.key_prefix}:state"
        self.failures_key = f"{self.key_prefix}:failures"
        self.last_failure_key = f"{self.key_prefix}:last_failure"
        self.successes_key = f"{self.key_prefix}:successes"

        # Initialize state if not exists
        if not self.redis.exists(self.state_key):
            self.redis.set(self.state_key, CircuitState.CLOSED.value)
            self.redis.set(self.failures_key, 0)
            self.redis.set(self.successes_key, 0)

    def _get_state(self) -> CircuitState:
        """Get current state from Redis."""
        state_value = self.redis.get(self.state_key)
        if state_value is None:
            return CircuitState.CLOSED
        return CircuitState(state_value.decode())

    def _set_state(self, state: CircuitState):
        """Set state in Redis."""
        self.redis.set(self.state_key, state.value)

    def _get_failures(self) -> int:
        """Get failure count from Redis."""
        count = self.redis.get(self.failures_key)
        return int(count) if count else 0

    def _incr_failures(self) -> int:
        """Increment failure count in Redis."""
        return self.redis.incr(self.failures_key)

    def _reset_failures(self):
        """Reset failure count in Redis."""
        self.redis.set(self.failures_key, 0)

    def _get_successes(self) -> int:
        """Get success count from Redis."""
        count = self.redis.get(self.successes_key)
        return int(count) if count else 0

    def _incr_successes(self) -> int:
        """Increment success count in Redis."""
        return self.redis.incr(self.successes_key)

    def _reset_successes(self):
        """Reset success count in Redis."""
        self.redis.set(self.successes_key, 0)

    def _get_last_failure_time(self) -> Optional[float]:
        """Get last failure timestamp from Redis."""
        timestamp = self.redis.get(self.last_failure_key)
        return float(timestamp) if timestamp else None

    def _set_last_failure_time(self, timestamp: float):
        """Set last failure timestamp in Redis."""
        self.redis.set(self.last_failure_key, timestamp)

    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute function with circuit breaker protection.

        State is read from and written to Redis, so all processes
        see the same circuit state.

        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Result of func

        Raises:
            CircuitBreakerError: If circuit is open
            Exception: If func raises
        """
        state = self._get_state()

        # Check if circuit is open
        if state == CircuitState.OPEN:
            last_failure = self._get_last_failure_time()
            if last_failure and (time.time() - last_failure >= self.recovery_timeout):
                # Transition to HALF_OPEN
                self._set_state(CircuitState.HALF_OPEN)
                self._reset_successes()
                logger.info(
                    f"Circuit breaker '{self.name}' entering HALF_OPEN (shared state)"
                )
            else:
                time_remaining = self.recovery_timeout - (time.time() - last_failure) if last_failure else 0
                raise CircuitBreakerError(
                    f"Circuit breaker '{self.name}' is OPEN. "
                    f"Retry in {time_remaining:.1f}s"
                )

        # Execute function
        try:
            result = func(*args, **kwargs)

            # Success handling
            state = self._get_state()  # Re-read state
            if state == CircuitState.HALF_OPEN:
                successes = self._incr_successes()
                if successes >= self.success_threshold:
                    logger.info(
                        f"Circuit breaker '{self.name}' CLOSED after {successes} "
                        f"successes (shared state)"
                    )
                    self._set_state(CircuitState.CLOSED)
                    self._reset_failures()
            else:
                # Circuit is closed - reset failures on success
                self._reset_failures()

            return result

        except self.expected_exception as e:
            # Failure handling
            failures = self._incr_failures()
            self._set_last_failure_time(time.time())
            self._reset_successes()

            if failures >= self.failure_threshold:
                self._set_state(CircuitState.OPEN)
                logger.warning(
                    f"Circuit breaker '{self.name}' OPEN after {failures} "
                    f"failures (shared state)"
                )
            else:
                logger.debug(
                    f"Circuit breaker '{self.name}' failure {failures}/"
                    f"{self.failure_threshold}"
                )

            raise

    def reset(self):
        """Manually reset circuit breaker to CLOSED state."""
        self._set_state(CircuitState.CLOSED)
        self._reset_failures()
        self._reset_successes()
        logger.info(f"Circuit breaker '{self.name}' manually reset (shared state)")

    def get_stats(self) -> dict:
        """Get circuit breaker statistics from Redis."""
        return {
            "name": self.name,
            "state": self._get_state().value,
            "failures": self._get_failures(),
            "successes": self._get_successes(),
            "last_failure": self._get_last_failure_time(),
        }


def redis_circuit_breaker(
    name: str,
    redis_client: "redis.Redis",
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    success_threshold: int = 3,
    expected_exception: type = Exception
):
    """
    Decorator for Redis-backed circuit breaker.

    Args:
        name: Circuit breaker name
        redis_client: Redis client instance
        failure_threshold: Failures before opening
        recovery_timeout: Seconds before testing recovery
        success_threshold: Successes to close from half-open
        expected_exception: Exception type that counts as failure

    Example:
        >>> import redis
        >>> r = redis.Redis(host='localhost', port=6379, db=0)
        >>>
        >>> @redis_circuit_breaker(
        ...     name="api",
        ...     redis_client=r,
        ...     failure_threshold=3,
        ...     recovery_timeout=30
        ... )
        ... def call_api():
        ...     return requests.get("https://api.example.com")
    """
    breaker = RedisCircuitBreaker(
        name=name,
        redis_client=redis_client,
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
        success_threshold=success_threshold,
        expected_exception=expected_exception
    )

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            return breaker.call(func, *args, **kwargs)

        # Expose breaker instance for manual control
        wrapper.circuit_breaker = breaker
        return wrapper

    return decorator


# Example usage
if __name__ == "__main__":
    if redis is None:
        print("Error: redis package required")
        print("Install with: pip install redis")
        exit(1)

    # Configure logging
    logging.basicConfig(level=logging.INFO)

    # Connect to Redis
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

    # Test Redis connection
    try:
        r.ping()
        print("✅ Connected to Redis")
    except redis.ConnectionError:
        print("❌ Could not connect to Redis. Is Redis running?")
        print("Start Redis with: redis-server")
        exit(1)

    @redis_circuit_breaker(
        name="test_service",
        redis_client=r,
        failure_threshold=3,
        recovery_timeout=5.0
    )
    def flaky_service():
        """Simulated flaky service."""
        import random
        if random.random() < 0.7:
            raise Exception("Service failed!")
        return "Success!"

    print("\nTesting Redis-backed circuit breaker...")
    print("Multiple processes would see the same circuit state!\n")

    for i in range(15):
        try:
            result = flaky_service()
            print(f"Request {i+1}: {result}")
        except Exception as e:
            print(f"Request {i+1}: {e}")

        # Show stats from Redis
        stats = flaky_service.circuit_breaker.get_stats()
        print(f"  State: {stats['state']}, Failures: {stats['failures']}\n")

        time.sleep(0.5)
