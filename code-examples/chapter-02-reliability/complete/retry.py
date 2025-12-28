"""
Retry logic with exponential backoff and jitter.

This module provides a decorator for retrying failed operations with:
- Exponential backoff: Delays increase exponentially (1s, 2s, 4s, 8s...)
- Jitter: Random variance to prevent thundering herd
- Configurable retry conditions
- Structured logging for observability
"""

import time
import random
import logging
from typing import TypeVar, Callable, Tuple, Type
from functools import wraps

# Configure logging
logger = logging.getLogger(__name__)

T = TypeVar('T')


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Retry a function with exponential backoff and jitter.

    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds (default: 1.0)
        max_delay: Maximum delay in seconds (default: 60.0)
        exponential_base: Base for exponential backoff (default: 2.0)
        jitter: Whether to add random jitter to delays (default: True)
        retryable_exceptions: Tuple of exceptions that should trigger retries

    Returns:
        Decorated function with retry logic

    Example:
        >>> @retry_with_backoff(max_retries=3, initial_delay=1.0)
        ... def call_api():
        ...     return requests.get("https://api.example.com")
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    # Attempt to call the function
                    return func(*args, **kwargs)

                except retryable_exceptions as e:
                    last_exception = e

                    # Don't retry on the last attempt
                    if attempt == max_retries:
                        logger.warning(
                            f"All {max_retries} retries exhausted for {func.__name__}",
                            extra={
                                "function": func.__name__,
                                "max_retries": max_retries,
                                "last_error": str(e)
                            }
                        )
                        break

                    # Calculate delay with exponential backoff
                    delay = min(
                        initial_delay * (exponential_base ** attempt),
                        max_delay
                    )

                    # Add jitter if enabled (randomize between 50% and 100% of delay)
                    if jitter:
                        delay = delay * (0.5 + random.random() * 0.5)

                    logger.info(
                        f"Retry attempt {attempt + 1}/{max_retries} for {func.__name__} "
                        f"after {delay:.2f}s delay",
                        extra={
                            "function": func.__name__,
                            "attempt": attempt + 1,
                            "max_retries": max_retries,
                            "delay_seconds": delay,
                            "error": str(e),
                            "error_type": type(e).__name__
                        }
                    )
                    time.sleep(delay)

                except Exception as e:
                    # Non-retryable exception - fail immediately
                    logger.error(
                        f"Non-retryable error in {func.__name__}: {e}",
                        extra={
                            "function": func.__name__,
                            "error": str(e),
                            "error_type": type(e).__name__
                        },
                        exc_info=True
                    )
                    raise

            # All retries exhausted - raise the last exception
            raise last_exception

        return wrapper
    return decorator


# Example usage
if __name__ == "__main__":
    import requests

    @retry_with_backoff(
        max_retries=3,
        initial_delay=1.0,
        retryable_exceptions=(requests.RequestException,)
    )
    def fetch_data():
        """Example function that might fail transiently."""
        response = requests.get("https://api.example.com/data")
        response.raise_for_status()
        return response.json()

    try:
        data = fetch_data()
        print(f"Success: {data}")
    except Exception as e:
        print(f"Failed after retries: {e}")
