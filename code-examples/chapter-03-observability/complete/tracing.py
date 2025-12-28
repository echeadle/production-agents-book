"""
Distributed tracing configuration using OpenTelemetry.

This module sets up distributed tracing to track requests across:
- Agent entry point
- LLM API calls
- Tool executions
- External services

Traces are exported to a collector (Jaeger, Zipkin, etc.) for
visualization and analysis.
"""

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
)
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.trace import Status, StatusCode
from typing import Optional, Dict, Any
from contextlib import contextmanager
import time

# Try to import OTLP exporter (optional)
try:
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    OTLP_AVAILABLE = True
except ImportError:
    OTLP_AVAILABLE = False


def configure_tracing(
    service_name: str = "task-automation-agent",
    environment: str = "production",
    otlp_endpoint: Optional[str] = None,
    console_export: bool = False,
):
    """
    Configure OpenTelemetry tracing.

    Args:
        service_name: Name of the service
        environment: Environment (production, staging, dev)
        otlp_endpoint: OTLP collector endpoint (e.g., "http://localhost:4317")
        console_export: If True, also export to console (for debugging)

    Example:
        >>> configure_tracing(
        ...     service_name="task-agent",
        ...     environment="production",
        ...     otlp_endpoint="http://jaeger:4317"
        ... )
    """
    # Create resource with service information
    resource = Resource.create({
        SERVICE_NAME: service_name,
        "environment": environment,
        "service.version": "0.1.0",
    })

    # Create tracer provider
    provider = TracerProvider(resource=resource)

    # Add exporters
    if otlp_endpoint and OTLP_AVAILABLE:
        # Export to OTLP collector (Jaeger, Zipkin, etc.)
        otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

    if console_export:
        # Export to console (for debugging)
        console_exporter = ConsoleSpanExporter()
        provider.add_span_processor(BatchSpanProcessor(console_exporter))

    # Set as global tracer provider
    trace.set_tracer_provider(provider)


def get_tracer(name: str = __name__) -> trace.Tracer:
    """
    Get a tracer instance.

    Args:
        name: Tracer name (typically __name__)

    Returns:
        Tracer instance
    """
    return trace.get_tracer(name)


@contextmanager
def trace_operation(
    operation_name: str,
    attributes: Optional[Dict[str, Any]] = None,
    tracer_name: str = "agent",
):
    """
    Context manager to trace an operation.

    Creates a span for the operation and automatically:
    - Sets attributes
    - Records exceptions
    - Sets status

    Args:
        operation_name: Name of the operation (e.g., "agent.process")
        attributes: Optional attributes to set on the span
        tracer_name: Tracer name

    Example:
        >>> with trace_operation("agent.process", {"user_id": "123"}):
        ...     result = agent.process(user_input)
    """
    tracer = get_tracer(tracer_name)
    with tracer.start_as_current_span(operation_name) as span:
        # Set attributes
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)

        try:
            yield span
        except Exception as e:
            # Record exception in span
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            raise
        else:
            # Mark as successful
            span.set_status(Status(StatusCode.OK))


class TracedAgent:
    """
    Mixin class to add tracing to agent operations.

    Example:
        >>> class MyAgent(TracedAgent):
        ...     def process(self, user_input: str) -> str:
        ...         with self.trace("process", {"input_length": len(user_input)}):
        ...             # ... agent logic
        ...             return result
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tracer = get_tracer(self.__class__.__name__)

    @contextmanager
    def trace(
        self,
        operation: str,
        attributes: Optional[Dict[str, Any]] = None
    ):
        """
        Trace an operation within this agent.

        Args:
            operation: Operation name
            attributes: Optional attributes

        Example:
            >>> with self.trace("llm_call", {"model": "sonnet"}):
            ...     response = self._call_llm(messages)
        """
        span_name = f"{self.__class__.__name__}.{operation}"
        with trace_operation(span_name, attributes, self.tracer.instrumentation_scope.name) as span:
            yield span


def add_span_event(name: str, attributes: Optional[Dict[str, Any]] = None):
    """
    Add an event to the current span.

    Events are timestamped points within a span, useful for marking
    significant moments (e.g., "tool_started", "llm_responded").

    Args:
        name: Event name
        attributes: Optional attributes for the event

    Example:
        >>> with trace_operation("agent.process"):
        ...     add_span_event("llm_call_started", {"model": "sonnet"})
        ...     response = call_llm()
        ...     add_span_event("llm_call_completed", {"tokens": 150})
    """
    span = trace.get_current_span()
    if span.is_recording():
        span.add_event(name, attributes or {})


def set_span_attributes(**attributes):
    """
    Set attributes on the current span.

    Args:
        **attributes: Attributes to set

    Example:
        >>> with trace_operation("agent.process"):
        ...     set_span_attributes(user_id="123", model="sonnet")
        ...     result = process()
        ...     set_span_attributes(tokens=result.tokens)
    """
    span = trace.get_current_span()
    if span.is_recording():
        for key, value in attributes.items():
            span.set_attribute(key, value)


# Example usage
if __name__ == "__main__":
    import structlog

    # Configure logging
    from logging_config import configure_logging
    configure_logging(json_logs=False)
    log = structlog.get_logger()

    # Configure tracing (console export for demo)
    configure_tracing(
        service_name="demo-agent",
        environment="development",
        console_export=True
    )

    print("Tracing demo - spans will be exported to console\n")

    # Simulate an agent request
    with trace_operation(
        "agent.process",
        attributes={
            "user_id": "user_123",
            "correlation_id": "req_abc123",
        }
    ):
        log.info("Agent processing request")

        # Simulate LLM call
        with trace_operation(
            "llm.call",
            attributes={
                "model": "claude-3-5-sonnet-20241022",
                "max_tokens": 1024,
            }
        ):
            add_span_event("llm_request_sent")
            time.sleep(0.1)  # Simulate API latency
            set_span_attributes(
                input_tokens=150,
                output_tokens=50,
                finish_reason="end_turn",
            )
            add_span_event("llm_response_received")
            log.info("LLM call completed", tokens=200)

        # Simulate tool execution
        with trace_operation(
            "tool.execute",
            attributes={
                "tool_name": "calculator",
                "tool_input": "15 * 23",
            }
        ):
            add_span_event("tool_started")
            time.sleep(0.05)  # Simulate tool execution
            set_span_attributes(tool_result="345")
            add_span_event("tool_completed")
            log.info("Tool executed", tool="calculator", result="345")

        # Simulate another LLM call
        with trace_operation(
            "llm.call",
            attributes={
                "model": "claude-3-5-sonnet-20241022",
                "max_tokens": 1024,
            }
        ):
            add_span_event("llm_request_sent")
            time.sleep(0.1)
            set_span_attributes(
                input_tokens=200,
                output_tokens=75,
                finish_reason="end_turn",
            )
            add_span_event("llm_response_received")
            log.info("LLM call completed", tokens=275)

        log.info("Agent request completed")

    print("\n✅ Trace completed!")
    print("In production, this would be sent to Jaeger/Zipkin for visualization")
