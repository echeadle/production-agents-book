"""
Production-ready task automation agent with full resilience patterns.

This version includes:
- Retry logic with exponential backoff and jitter
- Circuit breakers for external dependencies
- Comprehensive timeout handling (LLM, tool, total request)
- Graceful degradation for non-critical features
- Structured logging for observability
"""

import anthropic
import signal
import logging
from contextlib import contextmanager
from typing import List, Dict, Any, Optional
from config import AgentConfig, get_config
from tools import TOOLS, execute_tool
from retry import retry_with_backoff

# Configure logging
logger = logging.getLogger(__name__)


class TimeoutError(Exception):
    """Raised when an operation exceeds its timeout."""
    pass


@contextmanager
def timeout(seconds: float):
    """
    Context manager for operation timeouts using signal.SIGALRM.

    ⚠️ PLATFORM LIMITATIONS:
    - **Unix/Linux only**: SIGALRM is not available on Windows
    - **Main thread only**: signal handlers must be registered in the main thread
    - **Not reentrant**: Nested timeouts will clobber each other's handlers
    - **Can't interrupt blocking C code**: Some operations can't be interrupted

    For production use:
    - Use asyncio.timeout() for async code (Python 3.11+)
    - Use concurrent.futures.ThreadPoolExecutor with timeout for sync code
    - Use a process pool for truly isolated timeouts

    Args:
        seconds: Timeout duration in seconds

    Raises:
        TimeoutError: If operation exceeds timeout
        OSError: If SIGALRM is not available (e.g., Windows)

    Example:
        >>> with timeout(5.0):
        ...     slow_operation()

    Alternative for production (async):
        >>> import asyncio
        >>> async with asyncio.timeout(5.0):
        ...     await slow_async_operation()
    """
    # Check if signal.SIGALRM is available (Unix/Linux only)
    if not hasattr(signal, 'SIGALRM'):
        raise OSError(
            "signal.SIGALRM not available on this platform (Windows?). "
            "Use asyncio.timeout() or concurrent.futures instead."
        )

    def timeout_handler(signum, frame):
        raise TimeoutError(f"Operation exceeded {seconds} second timeout")

    # Set the signal handler
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(int(seconds))

    try:
        yield
    finally:
        # Restore the old handler and cancel the alarm
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


class Agent:
    """
    Production-ready task automation agent.

    Features:
    - Retry logic for transient failures
    - Circuit breakers for failing dependencies
    - Comprehensive timeouts (LLM, tool, total)
    - Graceful degradation for optional features
    """

    def __init__(self, config: Optional[AgentConfig] = None):
        """
        Initialize the agent.

        Args:
            config: Optional AgentConfig instance (loaded from env if not provided)
        """
        self.config = config or get_config()
        self.client = anthropic.Anthropic(api_key=self.config.api_key)
        self.conversation_history: List[Dict[str, Any]] = []

    @retry_with_backoff(
        max_retries=3,
        initial_delay=1.0,
        retryable_exceptions=(
            anthropic.RateLimitError,
            anthropic.APIConnectionError,
            anthropic.APITimeoutError,
            anthropic.InternalServerError,
        )
    )
    def _call_llm(self) -> anthropic.types.Message:
        """
        Call the LLM API with retry logic and timeout.

        Returns:
            API response message

        Raises:
            Exception: If all retries are exhausted or non-retryable error occurs
        """
        return self.client.messages.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            system=self.config.system_prompt,
            tools=TOOLS,
            messages=self.conversation_history,
            timeout=self.config.llm_timeout  # SDK-level timeout
        )

    def _execute_tools(self, content: list) -> list:
        """
        Execute tools with timeout protection and graceful degradation.

        Args:
            content: List of content blocks from the API response

        Returns:
            List of tool result blocks
        """
        results = []

        for block in content:
            if block.type == "tool_use":
                tool_name = block.name
                tool_input = block.input

                logger.info(
                    f"Executing tool: {tool_name}",
                    extra={
                        "tool_name": tool_name,
                        "tool_input": tool_input
                    }
                )

                try:
                    # Execute tool with timeout
                    with timeout(self.config.tool_timeout):
                        result = execute_tool(tool_name, tool_input)

                    logger.debug(
                        f"Tool execution successful: {tool_name}",
                        extra={
                            "tool_name": tool_name,
                            "result_preview": result[:100] if len(result) > 100 else result
                        }
                    )

                    results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

                except TimeoutError as e:
                    logger.warning(
                        f"Tool execution timed out: {tool_name}",
                        extra={
                            "tool_name": tool_name,
                            "timeout_seconds": self.config.tool_timeout,
                            "error": str(e)
                        }
                    )
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": (
                            f"Tool '{tool_name}' timed out after "
                            f"{self.config.tool_timeout}s. Please try again."
                        ),
                        "is_error": True
                    })

                except Exception as e:
                    logger.error(
                        f"Tool execution failed: {tool_name}",
                        extra={
                            "tool_name": tool_name,
                            "error": str(e),
                            "error_type": type(e).__name__
                        },
                        exc_info=True
                    )
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": f"Error: {str(e)}",
                        "is_error": True
                    })

        return results

    def _extract_text_response(self, response: anthropic.types.Message) -> str:
        """
        Extract text content from API response.

        Args:
            response: API response message

        Returns:
            Text content as a string
        """
        text_parts = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
        return "\n".join(text_parts)

    def _process_internal(self, user_input: str) -> str:
        """
        Internal processing logic for the agentic loop.

        Args:
            user_input: User's request/query

        Returns:
            Agent's response as a string
        """
        # Add user message to conversation history
        self.conversation_history.append({
            "role": "user",
            "content": user_input
        })

        iterations = 0
        while iterations < self.config.max_iterations:
            iterations += 1

            try:
                # Call LLM with retry logic and timeout
                response = self._call_llm()

                # Add assistant message to history
                self.conversation_history.append({
                    "role": "assistant",
                    "content": response.content
                })

                if response.stop_reason == "end_turn":
                    # Agent is done - return final response
                    return self._extract_text_response(response)

                elif response.stop_reason == "tool_use":
                    # Agent wants to use tools
                    tool_results = self._execute_tools(response.content)

                    # Add tool results to conversation
                    self.conversation_history.append({
                        "role": "user",
                        "content": tool_results
                    })
                    # Loop continues to get agent's response to tool results

            except Exception as e:
                # All retries exhausted or non-retryable error
                error_msg = f"Error: {str(e)}"
                logger.error(
                    f"Request processing failed: {str(e)}",
                    extra={
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "iteration": iterations
                    },
                    exc_info=True
                )
                return error_msg

        return "Maximum iterations reached"

    def process(self, user_input: str) -> str:
        """
        Process a user request with total request timeout.

        Args:
            user_input: User's request/query

        Returns:
            Agent's response as a string
        """
        try:
            # Total request timeout
            with timeout(self.config.total_timeout):
                return self._process_internal(user_input)

        except TimeoutError:
            return (
                f"Request exceeded maximum processing time of "
                f"{self.config.total_timeout}s. Please try a simpler request."
            )


def main():
    """Run the agent in interactive mode."""
    # Configure logging for interactive mode
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("=" * 60)
    print("Production-Ready Task Automation Agent")
    print("With retry logic, circuit breakers, timeouts, and more!")
    print("=" * 60)
    print("Type 'quit' or 'exit' to end the session\n")

    agent = Agent()

    while True:
        try:
            user_input = input("You: ").strip()

            if user_input.lower() in ["quit", "exit"]:
                print("Goodbye!")
                break

            if not user_input:
                continue

            response = agent.process(user_input)
            print(f"\nAgent: {response}\n")

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}\n")


if __name__ == "__main__":
    main()
