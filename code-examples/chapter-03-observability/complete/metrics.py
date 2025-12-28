"""
Prometheus metrics for agent monitoring.

Implements RED metrics (Rate, Errors, Duration) for:
- Agent requests
- LLM API calls
- Tool executions
- Circuit breaker states

Also tracks:
- Token usage and costs
- Active requests (gauge)
- Circuit breaker state
"""

from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    Enum,
    Info,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
from typing import Optional
import time
from contextlib import contextmanager

# Create a registry for all metrics
REGISTRY = CollectorRegistry()

# -------------------------------------------------------------------
# Agent Request Metrics (RED)
# -------------------------------------------------------------------

# Rate: Requests per second
agent_requests_total = Counter(
    "agent_requests_total",
    "Total number of agent requests",
    ["status", "user_id"],  # Labels for segmentation
    registry=REGISTRY,
)

# Errors: Failed requests
agent_errors_total = Counter(
    "agent_errors_total",
    "Total number of failed agent requests",
    ["error_type", "user_id"],
    registry=REGISTRY,
)

# Duration: Request latency distribution
agent_request_duration_seconds = Histogram(
    "agent_request_duration_seconds",
    "Agent request duration in seconds",
    ["status"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],  # Custom buckets
    registry=REGISTRY,
)

# Active requests (current load)
agent_requests_active = Gauge(
    "agent_requests_active",
    "Number of agent requests currently being processed",
    registry=REGISTRY,
)

# -------------------------------------------------------------------
# LLM API Metrics
# -------------------------------------------------------------------

# LLM API calls
llm_requests_total = Counter(
    "llm_requests_total",
    "Total number of LLM API calls",
    ["model", "status"],
    registry=REGISTRY,
)

# LLM API duration
llm_request_duration_seconds = Histogram(
    "llm_request_duration_seconds",
    "LLM API call duration in seconds",
    ["model", "status"],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0],
    registry=REGISTRY,
)

# Token usage
llm_tokens_total = Counter(
    "llm_tokens_total",
    "Total number of tokens used",
    ["model", "token_type"],  # token_type: input, output
    registry=REGISTRY,
)

# Estimated cost (in USD)
llm_cost_usd_total = Counter(
    "llm_cost_usd_total",
    "Total estimated cost in USD",
    ["model"],
    registry=REGISTRY,
)

# -------------------------------------------------------------------
# Tool Execution Metrics
# -------------------------------------------------------------------

# Tool calls
tool_calls_total = Counter(
    "tool_calls_total",
    "Total number of tool calls",
    ["tool_name", "status"],
    registry=REGISTRY,
)

# Tool duration
tool_duration_seconds = Histogram(
    "tool_duration_seconds",
    "Tool execution duration in seconds",
    ["tool_name", "status"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0],
    registry=REGISTRY,
)

# -------------------------------------------------------------------
# Circuit Breaker Metrics
# -------------------------------------------------------------------

# Circuit breaker state
circuit_breaker_state = Enum(
    "circuit_breaker_state",
    "Current state of circuit breaker",
    ["name"],
    states=["closed", "open", "half_open"],
    registry=REGISTRY,
)

# Circuit breaker failures
circuit_breaker_failures_total = Counter(
    "circuit_breaker_failures_total",
    "Total number of circuit breaker failures",
    ["name"],
    registry=REGISTRY,
)

# Circuit breaker trips
circuit_breaker_trips_total = Counter(
    "circuit_breaker_trips_total",
    "Total number of times circuit breaker has opened",
    ["name"],
    registry=REGISTRY,
)

# -------------------------------------------------------------------
# System Metrics
# -------------------------------------------------------------------

# Application info
app_info = Info(
    "app",
    "Application information",
    registry=REGISTRY,
)

# Set app info
app_info.info({
    "name": "task_automation_agent",
    "version": "0.1.0",
    "environment": "production",
})

# -------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------


@contextmanager
def track_request(user_id: Optional[str] = None):
    """
    Context manager to track agent request metrics.

    Automatically tracks:
    - Request count
    - Request duration
    - Active requests
    - Success/failure

    Example:
        >>> with track_request(user_id="user_123"):
        ...     result = agent.process(user_input)
    """
    agent_requests_active.inc()
    start_time = time.time()
    status = "success"

    try:
        yield
    except Exception as e:
        status = "error"
        error_type = type(e).__name__
        agent_errors_total.labels(
            error_type=error_type,
            user_id=user_id or "unknown"
        ).inc()
        raise
    finally:
        duration = time.time() - start_time
        agent_requests_active.dec()
        agent_requests_total.labels(
            status=status,
            user_id=user_id or "unknown"
        ).inc()
        agent_request_duration_seconds.labels(status=status).observe(duration)


@contextmanager
def track_llm_call(model: str):
    """
    Context manager to track LLM API call metrics.

    Example:
        >>> with track_llm_call(model="claude-3-5-sonnet-20241022"):
        ...     response = client.messages.create(...)
        ...     # Track tokens
        ...     track_tokens(model, response.usage.input_tokens, "input")
        ...     track_tokens(model, response.usage.output_tokens, "output")
    """
    start_time = time.time()
    status = "success"

    try:
        yield
    except Exception:
        status = "error"
        raise
    finally:
        duration = time.time() - start_time
        llm_requests_total.labels(model=model, status=status).inc()
        llm_request_duration_seconds.labels(model=model, status=status).observe(
            duration
        )


@contextmanager
def track_tool_call(tool_name: str):
    """
    Context manager to track tool execution metrics.

    Example:
        >>> with track_tool_call(tool_name="calculator"):
        ...     result = calculator(expression="15 * 23")
    """
    start_time = time.time()
    status = "success"

    try:
        yield
    except Exception:
        status = "error"
        raise
    finally:
        duration = time.time() - start_time
        tool_calls_total.labels(tool_name=tool_name, status=status).inc()
        tool_duration_seconds.labels(tool_name=tool_name, status=status).observe(
            duration
        )


def track_tokens(model: str, tokens: int, token_type: str):
    """
    Track token usage.

    Args:
        model: Model name (e.g., "claude-3-5-sonnet-20241022")
        tokens: Number of tokens
        token_type: "input" or "output"
    """
    llm_tokens_total.labels(model=model, token_type=token_type).inc(tokens)


def track_cost(model: str, input_tokens: int, output_tokens: int):
    """
    Track estimated API cost.

    Uses approximate pricing:
    - Sonnet: $3/MTok input, $15/MTok output
    - Haiku: $0.25/MTok input, $1.25/MTok output

    Args:
        model: Model name
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
    """
    # Simplified pricing (update with actual pricing)
    if "sonnet" in model.lower():
        cost = (input_tokens / 1_000_000 * 3.0) + (output_tokens / 1_000_000 * 15.0)
    elif "haiku" in model.lower():
        cost = (input_tokens / 1_000_000 * 0.25) + (output_tokens / 1_000_000 * 1.25)
    else:
        cost = 0.0  # Unknown model

    llm_cost_usd_total.labels(model=model).inc(cost)


def update_circuit_breaker_state(name: str, state: str):
    """
    Update circuit breaker state metric.

    Args:
        name: Circuit breaker name
        state: "closed", "open", or "half_open"
    """
    circuit_breaker_state.labels(name=name).state(state)


def track_circuit_breaker_failure(name: str):
    """Track a circuit breaker failure."""
    circuit_breaker_failures_total.labels(name=name).inc()


def track_circuit_breaker_trip(name: str):
    """Track a circuit breaker trip (transition to OPEN)."""
    circuit_breaker_trips_total.labels(name=name).inc()


def get_metrics() -> bytes:
    """
    Get all metrics in Prometheus format.

    Returns:
        Metrics in Prometheus text format (bytes)
    """
    return generate_latest(REGISTRY)


def get_metrics_content_type() -> str:
    """Get the content type for Prometheus metrics."""
    return CONTENT_TYPE_LATEST


# Example usage
if __name__ == "__main__":
    import structlog

    log = structlog.get_logger()

    # Simulate some agent activity
    print("Simulating agent activity...\n")

    # Request 1: Success
    with track_request(user_id="user_123"):
        with track_llm_call(model="claude-3-5-sonnet-20241022"):
            track_tokens("claude-3-5-sonnet-20241022", 150, "input")
            track_tokens("claude-3-5-sonnet-20241022", 50, "output")
            track_cost("claude-3-5-sonnet-20241022", 150, 50)

        with track_tool_call(tool_name="calculator"):
            pass  # Tool executed successfully

    # Request 2: Tool failure
    with track_request(user_id="user_456"):
        with track_llm_call(model="claude-3-5-sonnet-20241022"):
            track_tokens("claude-3-5-sonnet-20241022", 200, "input")
            track_tokens("claude-3-5-sonnet-20241022", 75, "output")
            track_cost("claude-3-5-sonnet-20241022", 200, 75)

        try:
            with track_tool_call(tool_name="web_search"):
                raise Exception("Service unavailable")
        except Exception:
            pass  # Handled gracefully

    # Circuit breaker events
    update_circuit_breaker_state("web_search", "closed")
    track_circuit_breaker_failure("web_search")
    track_circuit_breaker_failure("web_search")
    track_circuit_breaker_trip("web_search")
    update_circuit_breaker_state("web_search", "open")

    # Print metrics
    print("Metrics output:\n")
    print(get_metrics().decode("utf-8"))
