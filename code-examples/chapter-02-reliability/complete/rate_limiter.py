"""
Rate limiting to prevent overwhelming APIs.

Implements the Token Bucket algorithm for client-side rate limiting.
Works in conjunction with retries and circuit breakers to prevent
thundering herd problems.
"""

import time
import threading
import logging
from typing import Optional
from functools import wraps

logger = logging.getLogger(__name__)


class TokenBucket:
    """
    Thread-safe token bucket for rate limiting.

    The token bucket algorithm:
    - Tokens are added to the bucket at a fixed rate
    - Each request consumes one token
    - If no tokens available, request must wait or be rejected
    - Bucket has a maximum capacity (allows bursts)

    Example:
        - rate=10 tokens/second, capacity=20
        - Allows sustained 10 req/s
        - Allows bursts up to 20 req/s (then throttles)
    """

    def __init__(
        self,
        rate: float,
        capacity: Optional[float] = None,
        initial_tokens: Optional[float] = None
    ):
        """
        Initialize token bucket.

        Args:
            rate: Tokens added per second (requests per second)
            capacity: Maximum tokens in bucket (allows bursts). Defaults to rate.
            initial_tokens: Starting tokens. Defaults to capacity.
        """
        self.rate = rate
        self.capacity = capacity or rate
        self.tokens = initial_tokens if initial_tokens is not None else self.capacity
        self.last_update = time.time()
        self._lock = threading.Lock()

    def _refill(self):
        """Refill tokens based on time elapsed (called with lock held)."""
        now = time.time()
        elapsed = now - self.last_update

        # Add tokens based on elapsed time
        new_tokens = elapsed * self.rate
        self.tokens = min(self.capacity, self.tokens + new_tokens)
        self.last_update = now

    def consume(self, tokens: float = 1.0, block: bool = True, timeout: Optional[float] = None) -> bool:
        """
        Consume tokens from the bucket.

        Args:
            tokens: Number of tokens to consume (default: 1)
            block: If True, wait for tokens to become available
            timeout: Max seconds to wait (only if block=True)

        Returns:
            True if tokens were consumed, False if rejected

        Example:
            >>> bucket = TokenBucket(rate=10, capacity=20)
            >>> bucket.consume()  # Consumes 1 token
            True
            >>> bucket.consume(tokens=5)  # Consumes 5 tokens
            True
        """
        start_time = time.time()

        while True:
            with self._lock:
                self._refill()

                if self.tokens >= tokens:
                    # Tokens available - consume them
                    self.tokens -= tokens
                    logger.debug(
                        f"Rate limit: consumed {tokens} tokens, {self.tokens:.2f} remaining",
                        extra={
                            "tokens_consumed": tokens,
                            "tokens_remaining": self.tokens,
                            "capacity": self.capacity
                        }
                    )
                    return True

                if not block:
                    # Non-blocking mode - reject immediately
                    logger.warning(
                        f"Rate limit: rejected (no tokens available)",
                        extra={
                            "tokens_needed": tokens,
                            "tokens_available": self.tokens
                        }
                    )
                    return False

            # Blocking mode - wait for tokens
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    logger.warning(
                        f"Rate limit: timeout waiting for tokens",
                        extra={
                            "tokens_needed": tokens,
                            "timeout": timeout
                        }
                    )
                    return False

            # Calculate how long to wait for next token
            wait_time = (tokens - self.tokens) / self.rate
            # Don't wait too long (check frequently in case rate changes)
            wait_time = min(wait_time, 0.1)

            logger.debug(
                f"Rate limit: waiting {wait_time:.2f}s for tokens",
                extra={
                    "wait_seconds": wait_time,
                    "tokens_needed": tokens,
                    "tokens_available": self.tokens
                }
            )
            time.sleep(wait_time)

    def get_available_tokens(self) -> float:
        """Get number of tokens currently available."""
        with self._lock:
            self._refill()
            return self.tokens


class RateLimiter:
    """
    Rate limiter decorator using token bucket algorithm.

    Thread-safe rate limiting for functions.
    """

    def __init__(
        self,
        rate: float,
        capacity: Optional[float] = None,
        block: bool = True,
        timeout: Optional[float] = None
    ):
        """
        Initialize rate limiter.

        Args:
            rate: Max calls per second
            capacity: Burst capacity. Defaults to rate.
            block: If True, wait for rate limit. If False, raise exception.
            timeout: Max wait time in seconds (only if block=True)
        """
        self.bucket = TokenBucket(rate=rate, capacity=capacity)
        self.block = block
        self.timeout = timeout

    def __call__(self, func):
        """Decorate a function with rate limiting."""
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not self.bucket.consume(block=self.block, timeout=self.timeout):
                raise RateLimitExceeded(
                    f"Rate limit exceeded for {func.__name__}. "
                    f"Max rate: {self.bucket.rate}/s"
                )
            return func(*args, **kwargs)
        return wrapper


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded in non-blocking mode."""
    pass


def rate_limit(rate: float, capacity: Optional[float] = None, block: bool = True, timeout: Optional[float] = None):
    """
    Decorator to add rate limiting to a function.

    Args:
        rate: Maximum calls per second
        capacity: Burst capacity. Defaults to rate.
        block: If True, wait for rate limit. If False, raise RateLimitExceeded.
        timeout: Max wait time in seconds (only if block=True)

    Example:
        >>> @rate_limit(rate=10, capacity=20)
        ... def call_api():
        ...     return requests.get("https://api.example.com")

        >>> # Sustained: 10 req/s, Burst: up to 20 req/s

    Example with retries:
        >>> @retry_with_backoff(max_retries=3)
        ... @rate_limit(rate=10)
        ... def call_api():
        ...     return requests.get("https://api.example.com")

        >>> # Rate limiting happens BEFORE retries
        >>> # Prevents retry storms from exceeding rate limits
    """
    return RateLimiter(rate=rate, capacity=capacity, block=block, timeout=timeout)


# Example usage
if __name__ == "__main__":
    import random

    # Configure logging
    logging.basicConfig(level=logging.INFO)

    @rate_limit(rate=5, capacity=10)  # 5 req/s sustained, 10 req/s burst
    def api_call(request_id: int):
        """Simulated API call."""
        print(f"Request {request_id}: Processing...")
        time.sleep(0.1)  # Simulate work
        return f"Response {request_id}"

    print("Making 20 requests (rate limit: 5/s, burst: 10)...")
    print("First 10 should be fast (burst), then throttled to 5/s\n")

    start = time.time()
    for i in range(20):
        result = api_call(i)
        elapsed = time.time() - start
        print(f"{elapsed:.2f}s - {result}")

    print(f"\nTotal time: {time.time() - start:.2f}s")
    print("Expected: ~2 seconds (burst of 10, then 10 more at 5/s = 2s)")
