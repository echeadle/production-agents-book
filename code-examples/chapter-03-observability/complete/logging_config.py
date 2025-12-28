"""
Structured logging configuration using structlog.

This module sets up structured logging with:
- JSON output for production
- Correlation IDs for request tracing
- Contextual information
- Log levels
- Timestamp formatting
"""

import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Any, Dict, Optional

import structlog

# Context variable for correlation ID (thread-safe)
correlation_id_var: ContextVar[Optional[str]] = ContextVar(
    "correlation_id", default=None
)


def set_correlation_id(correlation_id: Optional[str] = None) -> str:
    """
    Set correlation ID for current context.

    Args:
        correlation_id: Optional correlation ID. If None, generates a new one.

    Returns:
        The correlation ID that was set.
    """
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())
    correlation_id_var.set(correlation_id)
    return correlation_id


def get_correlation_id() -> Optional[str]:
    """Get correlation ID for current context."""
    return correlation_id_var.get()


def add_correlation_id(
    logger: Any, method_name: str, event_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Processor to add correlation ID to log entries.

    This is a structlog processor that runs for every log entry.
    """
    correlation_id = get_correlation_id()
    if correlation_id:
        event_dict["correlation_id"] = correlation_id
    return event_dict


def configure_logging(log_level: str = "INFO", json_logs: bool = True):
    """
    Configure structured logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_logs: If True, output JSON. If False, output human-readable format.

    Example:
        >>> configure_logging(log_level="INFO", json_logs=True)
        >>> log = structlog.get_logger()
        >>> log.info("agent.started", user_id="user_123")
        {"event": "agent.started", "user_id": "user_123", "timestamp": "...", ...}
    """
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )

    # Shared processors for all configurations
    shared_processors = [
        # Add log level
        structlog.stdlib.add_log_level,
        # Add logger name
        structlog.stdlib.add_logger_name,
        # Add correlation ID
        add_correlation_id,
        # Add timestamp
        structlog.processors.TimeStamper(fmt="iso"),
        # Add stack info for exceptions
        structlog.processors.StackInfoRenderer(),
        # Format exceptions
        structlog.processors.format_exc_info,
    ]

    if json_logs:
        # Production: JSON output
        processors = shared_processors + [
            # Render as JSON
            structlog.processors.JSONRenderer()
        ]
    else:
        # Development: Human-readable output
        processors = shared_processors + [
            # Add colors and formatting
            structlog.dev.ConsoleRenderer()
        ]

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


# Example usage
if __name__ == "__main__":
    # Configure for development (human-readable)
    configure_logging(log_level="DEBUG", json_logs=False)

    log = structlog.get_logger()

    # Simple log
    log.info("application.started")

    # Log with context
    log.info("user.login", user_id="user_123", ip_address="192.168.1.1")

    # With correlation ID
    correlation_id = set_correlation_id()
    log.info("request.received", correlation_id=correlation_id, path="/api/chat")
    log.info("llm.called", model="claude-3-5-sonnet-20241022", tokens=150)
    log.info("request.completed", status="success", duration_ms=234)

    # Log an error
    try:
        1 / 0
    except Exception as e:
        log.error("calculation.failed", error=str(e), exc_info=True)

    print("\n--- Now with JSON output ---\n")

    # Configure for production (JSON)
    configure_logging(log_level="INFO", json_logs=True)
    log = structlog.get_logger()

    correlation_id = set_correlation_id()
    log.info("request.received", correlation_id=correlation_id, user_id="user_456")
    log.info("llm.called", model="claude-3-5-sonnet-20241022", tokens=250)
    log.info("request.completed", status="success", duration_ms=456)
