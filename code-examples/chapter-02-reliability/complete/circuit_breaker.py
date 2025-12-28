"""
Circuit breaker pattern to prevent cascading failures.

A circuit breaker monitors for failures and "trips" after a threshold,
failing fast to give the failing service time to recover.

This implementation is thread-safe using locks to protect shared state.
"""

import time
import threading
import logging
from enum import Enum
from typing import Callable, TypeVar, Optional
from functools import wraps

# Configure logging
logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitState(Enum):
    """States of the circuit breaker."""
    CLOSED = "closed"  # Normal operation - requests pass through
    OPEN = "open"  # Circuit tripped - requests fail immediately
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open."""
    pass


class CircuitBreaker:
    """
    Thread-safe circuit breaker to prevent cascading failures.

    The circuit breaker has three states:
    - CLOSED: Normal operation, requests pass through
    - OPEN: After threshold failures, fail fast without trying
    - HALF_OPEN: After timeout, allow test requests to check recovery

    Thread Safety:
        All state access is protected by a threading.Lock to prevent
        race conditions in multi-threaded environments.
    """

    def __init__(
        self,
        name: str = "unnamed",
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        success_threshold: int = 3,
        expected_exception: type = Exception
    ):
        """
        Initialize circuit breaker.

        Args:
            name: Name for logging/identification
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before testing recovery
            success_threshold: Number of successes to close from half-open
            expected_exception: Exception type that counts as failure
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = CircuitState.CLOSED

        # Thread safety: Lock protects all shared state
        self._lock = threading.Lock()

    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute function with circuit breaker protection (thread-safe).

        Args:
            func: Function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result of func

        Raises:
            CircuitBreakerError: If circuit is open
            Exception: If func raises and circuit closes

        Thread Safety:
            State is checked/updated with lock held, but function execution
            happens outside lock to avoid blocking other threads during I/O.
        """
        # Check state and decide whether to proceed (with lock)
        with self._lock:
            if self.state == CircuitState.OPEN:
                # Check if we should test recovery
                if time.time() - self.last_failure_time >= self.recovery_timeout:
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                    logger.info(
                        f"Circuit breaker '{self.name}' entering HALF_OPEN state "
                        f"for recovery testing"
                    )
                else:
                    time_remaining = self.recovery_timeout - (
                        time.time() - self.last_failure_time
                    )
                    raise CircuitBreakerError(
                        f"Circuit breaker '{self.name}' is OPEN. "
                        f"Retry in {time_remaining:.1f}s"
                    )

        # Execute the function OUTSIDE the lock (don't block other threads during I/O)
        try:
            result = func(*args, **kwargs)

            # Success - update state (with lock)
            with self._lock:
                if self.state == CircuitState.HALF_OPEN:
                    self.success_count += 1
                    # After success_threshold successful requests, close the circuit
                    if self.success_count >= self.success_threshold:
                        logger.info(
                            f"Circuit breaker '{self.name}' recovery confirmed "
                            f"after {self.success_count} successes. State: CLOSED"
                        )
                        self.failure_count = 0
                        self.state = CircuitState.CLOSED
                else:
                    # Circuit is closed, reset failure count on success
                    self.failure_count = 0

            return result

        except self.expected_exception as e:
            # Failure - update state (with lock)
            with self._lock:
                self.failure_count += 1
                self.last_failure_time = time.time()
                self.success_count = 0  # Reset success count

                # Trip circuit if threshold exceeded
                if self.failure_count >= self.failure_threshold:
                    self.state = CircuitState.OPEN
                    logger.warning(
                        f"Circuit breaker '{self.name}' OPEN after "
                        f"{self.failure_count} failures. "
                        f"Will retry in {self.recovery_timeout}s"
                    )
                else:
                    logger.debug(
                        f"Circuit breaker '{self.name}' failure "
                        f"{self.failure_count}/{self.failure_threshold}: {e}"
                    )

            raise

    def reset(self):
        """Manually reset the circuit breaker to CLOSED state (thread-safe)."""
        with self._lock:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            logger.info(f"Circuit breaker '{self.name}' manually reset to CLOSED")


def circuit_breaker(
    name: str = "unnamed",
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    success_threshold: int = 3,
    expected_exception: type = Exception
):
    """
    Decorator to add thread-safe circuit breaker to a function.

    Args:
        name: Name for logging/identification
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Seconds to wait before testing recovery
        success_threshold: Number of successes to close from half-open
        expected_exception: Exception type that counts as failure

    Returns:
        Decorated function with circuit breaker protection

    Example:
        >>> @circuit_breaker(
        ...     name="api",
        ...     failure_threshold=3,
        ...     recovery_timeout=30,
        ...     success_threshold=2
        ... )
        ... def call_api():
        ...     return requests.get("https://api.example.com")
    """
    breaker = CircuitBreaker(
        name=name,
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
        success_threshold=success_threshold,
        expected_exception=expected_exception
    )

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            return breaker.call(func, *args, **kwargs)

        # Expose the breaker instance for manual control
        wrapper.circuit_breaker = breaker
        return wrapper

    return decorator


# Example usage
if __name__ == "__main__":
    import random

    @circuit_breaker(
        name="flaky_service",
        failure_threshold=3,
        recovery_timeout=5.0
    )
    def flaky_function():
        """Simulate a flaky service that fails 70% of the time."""
        if random.random() < 0.7:
            raise Exception("Service failed!")
        return "Success!"

    # Test the circuit breaker
    for i in range(20):
        try:
            result = flaky_function()
            print(f"Request {i+1}: {result}")
        except Exception as e:
            print(f"Request {i+1}: {e}")

        time.sleep(0.5)
