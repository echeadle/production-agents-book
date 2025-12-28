"""
Production agent with full observability stack.

This agent includes:
- Structured logging with correlation IDs (structlog)
- Prometheus metrics (RED metrics)
- Distributed tracing (OpenTelemetry)
- All reliability patterns from Chapter 2

The three pillars work together:
- Logs: What happened (structured, queryable)
- Metrics: How much/how often (counters, histograms)
- Traces: Where time was spent (distributed timeline)
"""

import os
import sys
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

import anthropic
from anthropic.types import Message, TextBlock, ToolUseBlock
import structlog

# Import observability components
from logging_config import configure_logging, set_correlation_id, get_correlation_id
from metrics import (
    track_request,
    track_llm_call,
    track_tool_call,
    track_tokens,
    track_cost,
)
from tracing import configure_tracing, trace_operation, add_span_event, set_span_attributes

# Import reliability components from Chapter 2
from config import Config
from tools import TOOLS, execute_tool
from retry import retry_with_backoff
from circuit_breaker import circuit_breaker, CircuitBreakerError

# Get structured logger
log = structlog.get_logger()


@dataclass
class AgentConfig:
    """Agent configuration."""
    anthropic_api_key: str
    model: str = "claude-3-5-sonnet-20241022"
    max_tokens: int = 1024
    max_iterations: int = 10
    llm_timeout: float = 30.0
    tool_timeout: float = 10.0


class ObservableAgent:
    """
    Production agent with full observability.

    Features:
    - Structured logging with correlation IDs
    - Prometheus metrics for monitoring
    - OpenTelemetry traces for debugging
    - Circuit breakers for resilience
    - Retry logic with backoff
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.client = anthropic.Anthropic(api_key=config.anthropic_api_key)
        self.conversation_history: List[Dict[str, Any]] = []

        log.info(
            "agent.initialized",
            model=config.model,
            max_tokens=config.max_tokens,
        )

    def process(
        self,
        user_input: str,
        user_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> str:
        """
        Process user input with full observability.

        This method demonstrates the three pillars in action:
        - LOGS: Structured logging with correlation IDs
        - METRICS: Request tracking, duration, errors
        - TRACES: Distributed trace across all operations

        Args:
            user_input: User's message
            user_id: Optional user identifier
            correlation_id: Optional correlation ID for request tracking

        Returns:
            Agent's response

        Raises:
            Exception: If agent fails after retries
        """
        # Set correlation ID for request tracking
        correlation_id = set_correlation_id(correlation_id)

        # Start observability tracking
        with track_request(user_id=user_id):
            with trace_operation(
                "agent.process",
                attributes={
                    "user_id": user_id or "unknown",
                    "correlation_id": correlation_id,
                    "input_length": len(user_input),
                },
            ) as span:
                log.info(
                    "agent.request_received",
                    user_id=user_id,
                    correlation_id=correlation_id,
                    input_length=len(user_input),
                )

                try:
                    # Add user message to history
                    self.conversation_history.append({
                        "role": "user",
                        "content": user_input,
                    })

                    # Agent loop with observability
                    result = self._agent_loop()

                    # Track success
                    span.set_attribute("status", "success")
                    span.set_attribute("iterations", len(result.get("iterations", [])))

                    log.info(
                        "agent.request_completed",
                        status="success",
                        iterations=result.get("iterations", 0),
                        response_length=len(result.get("response", "")),
                    )

                    return result.get("response", "I encountered an error.")

                except Exception as e:
                    # Track failure
                    span.set_attribute("status", "error")
                    span.set_attribute("error_type", type(e).__name__)

                    log.error(
                        "agent.request_failed",
                        error=str(e),
                        error_type=type(e).__name__,
                        exc_info=True,
                    )
                    raise

    def _agent_loop(self) -> Dict[str, Any]:
        """
        Main agent loop with observability.

        Returns:
            Dict with response and metadata
        """
        with trace_operation("agent.loop") as span:
            iterations = 0

            for i in range(self.config.max_iterations):
                iterations += 1
                add_span_event("iteration.started", {"iteration": i + 1})

                log.debug("agent.iteration_started", iteration=i + 1)

                # Call LLM
                try:
                    message = self._call_llm_with_retry()
                except Exception as e:
                    log.error(
                        "agent.llm_call_failed",
                        iteration=i + 1,
                        error=str(e),
                        exc_info=True,
                    )
                    raise

                # Check if agent is done
                if message.stop_reason == "end_turn":
                    # Extract final response
                    response = self._extract_text_response(message)
                    span.set_attribute("final_iteration", i + 1)
                    add_span_event("iteration.completed", {"reason": "end_turn"})

                    log.info(
                        "agent.loop_completed",
                        reason="end_turn",
                        iterations=iterations,
                    )

                    return {"response": response, "iterations": iterations}

                # Execute tools if present
                if message.stop_reason == "tool_use":
                    try:
                        tool_results = self._execute_tools(message.content)
                        self.conversation_history.append({
                            "role": "user",
                            "content": tool_results,
                        })
                        add_span_event("tools.executed", {"tool_count": len(tool_results)})
                    except Exception as e:
                        log.error(
                            "agent.tool_execution_failed",
                            error=str(e),
                            exc_info=True,
                        )
                        # Continue with error message
                        self.conversation_history.append({
                            "role": "user",
                            "content": [{
                                "type": "tool_result",
                                "tool_use_id": "error",
                                "content": f"Tool execution failed: {str(e)}",
                            }],
                        })

            # Max iterations reached
            span.set_attribute("max_iterations_reached", True)
            log.warning(
                "agent.max_iterations_reached",
                max_iterations=self.config.max_iterations,
            )

            return {
                "response": "I've reached the maximum number of iterations.",
                "iterations": iterations,
            }

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    def _call_llm_with_retry(self) -> Message:
        """
        Call LLM with retry logic and observability.

        Returns:
            Anthropic Message object
        """
        with track_llm_call(model=self.config.model):
            with trace_operation(
                "llm.call",
                attributes={
                    "model": self.config.model,
                    "max_tokens": self.config.max_tokens,
                    "messages_count": len(self.conversation_history),
                },
            ) as span:
                add_span_event("llm.request_sent")

                log.debug(
                    "llm.calling",
                    model=self.config.model,
                    messages_count=len(self.conversation_history),
                )

                try:
                    response = self.client.messages.create(
                        model=self.config.model,
                        max_tokens=self.config.max_tokens,
                        messages=self.conversation_history,
                        tools=TOOLS,
                    )

                    # Track tokens and cost
                    track_tokens(
                        self.config.model,
                        response.usage.input_tokens,
                        "input",
                    )
                    track_tokens(
                        self.config.model,
                        response.usage.output_tokens,
                        "output",
                    )
                    track_cost(
                        self.config.model,
                        response.usage.input_tokens,
                        response.usage.output_tokens,
                    )

                    # Set trace attributes
                    set_span_attributes(
                        input_tokens=response.usage.input_tokens,
                        output_tokens=response.usage.output_tokens,
                        stop_reason=response.stop_reason,
                    )

                    add_span_event("llm.response_received")

                    log.info(
                        "llm.call_completed",
                        input_tokens=response.usage.input_tokens,
                        output_tokens=response.usage.output_tokens,
                        stop_reason=response.stop_reason,
                    )

                    # Add to history
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": response.content,
                    })

                    return response

                except Exception as e:
                    span.set_attribute("error_type", type(e).__name__)
                    add_span_event("llm.call_failed", {"error": str(e)})
                    raise

    def _execute_tools(self, content: List) -> List[Dict[str, Any]]:
        """
        Execute tools with observability.

        Args:
            content: Message content with tool_use blocks

        Returns:
            List of tool results
        """
        results = []

        with trace_operation("tools.execute") as span:
            tool_blocks = [block for block in content if isinstance(block, ToolUseBlock)]
            span.set_attribute("tool_count", len(tool_blocks))

            for block in tool_blocks:
                tool_name = block.name
                tool_input = block.input

                with track_tool_call(tool_name=tool_name):
                    with trace_operation(
                        f"tool.{tool_name}",
                        attributes={
                            "tool_name": tool_name,
                            "tool_use_id": block.id,
                        },
                    ) as tool_span:
                        log.info(
                            "tool.executing",
                            tool_name=tool_name,
                            tool_use_id=block.id,
                            tool_input=tool_input,
                        )

                        try:
                            add_span_event("tool.started")
                            result = execute_tool(tool_name, tool_input)
                            add_span_event("tool.completed", {"result_length": len(str(result))})

                            tool_span.set_attribute("status", "success")
                            tool_span.set_attribute("result_length", len(str(result)))

                            log.info(
                                "tool.execution_completed",
                                tool_name=tool_name,
                                status="success",
                                result_length=len(str(result)),
                            )

                            results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result,
                            })

                        except CircuitBreakerError as e:
                            # Circuit breaker open - graceful degradation
                            error_msg = f"Tool '{tool_name}' is temporarily unavailable: {str(e)}"

                            tool_span.set_attribute("status", "circuit_open")
                            add_span_event("tool.circuit_open")

                            log.warning(
                                "tool.circuit_breaker_open",
                                tool_name=tool_name,
                                error=str(e),
                            )

                            results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": error_msg,
                                "is_error": True,
                            })

                        except Exception as e:
                            # Tool execution failed
                            error_msg = f"Tool '{tool_name}' failed: {str(e)}"

                            tool_span.set_attribute("status", "error")
                            tool_span.set_attribute("error_type", type(e).__name__)
                            add_span_event("tool.failed", {"error": str(e)})

                            log.error(
                                "tool.execution_failed",
                                tool_name=tool_name,
                                error=str(e),
                                error_type=type(e).__name__,
                                exc_info=True,
                            )

                            results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": error_msg,
                                "is_error": True,
                            })

        return results

    def _extract_text_response(self, message: Message) -> str:
        """Extract text content from message."""
        text_blocks = [
            block.text for block in message.content if isinstance(block, TextBlock)
        ]
        return "\n".join(text_blocks) if text_blocks else ""


def main():
    """Main entry point with observability configuration."""
    # Load environment
    from dotenv import load_dotenv
    load_dotenv()

    # Configure observability
    configure_logging(
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        json_logs=os.getenv("JSON_LOGS", "false").lower() == "true",
    )

    configure_tracing(
        service_name="task-automation-agent",
        environment=os.getenv("ENVIRONMENT", "production"),
        otlp_endpoint=os.getenv("OTLP_ENDPOINT"),  # Optional: Jaeger/Zipkin endpoint
        console_export=os.getenv("TRACE_CONSOLE", "false").lower() == "true",
    )

    log.info("application.started", version="0.1.0")

    # Create agent
    config = AgentConfig(
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        model=os.getenv("MODEL", "claude-3-5-sonnet-20241022"),
    )

    agent = ObservableAgent(config)

    print("Observable Agent (Ctrl+C to exit)")
    print("=" * 50)

    # Interactive loop
    try:
        while True:
            user_input = input("\nYou: ").strip()
            if not user_input:
                continue

            if user_input.lower() in ["exit", "quit"]:
                log.info("application.shutdown", reason="user_request")
                break

            try:
                # Process with user_id for tracking
                response = agent.process(
                    user_input=user_input,
                    user_id="cli_user",
                )

                print(f"\nAgent: {response}")

            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"\nError: {e}")
                log.error("request.failed", error=str(e), exc_info=True)

    except KeyboardInterrupt:
        log.info("application.shutdown", reason="keyboard_interrupt")
        print("\n\nGoodbye!")


if __name__ == "__main__":
    main()
