"""
Async version of the production-ready agent (Python 3.11+).

This version uses asyncio for proper timeout handling that works on all platforms
including Windows, is thread-safe, and supports reentrant timeouts.

Advantages over signal-based timeouts:
- ✅ Cross-platform (Windows, Linux, macOS)
- ✅ Thread-safe
- ✅ Reentrant (nested timeouts work correctly)
- ✅ Can be used in multi-threaded applications
- ✅ Better integration with async libraries
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
import anthropic
from config import AgentConfig, get_config
from tools import TOOLS, execute_tool
from retry import retry_with_backoff

# Configure logging
logger = logging.getLogger(__name__)


class Agent:
    """
    Async production-ready task automation agent.

    Uses asyncio.timeout() for cross-platform, thread-safe timeout handling.
    """

    def __init__(self, config: Optional[AgentConfig] = None):
        """
        Initialize the agent.

        Args:
            config: Optional AgentConfig instance (loaded from env if not provided)
        """
        self.config = config or get_config()
        self.client = anthropic.AsyncAnthropic(api_key=self.config.api_key)
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
    async def _call_llm(self) -> anthropic.types.Message:
        """
        Call the LLM API with retry logic and timeout (async).

        Returns:
            API response message

        Raises:
            Exception: If all retries are exhausted or non-retryable error occurs
        """
        # Note: Anthropic SDK timeout parameter still works with async client
        return await self.client.messages.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            system=self.config.system_prompt,
            tools=TOOLS,
            messages=self.conversation_history,
            timeout=self.config.llm_timeout
        )

    async def _execute_tools(self, content: list) -> list:
        """
        Execute tools with timeout protection (async).

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
                    # Execute tool with asyncio timeout (cross-platform!)
                    async with asyncio.timeout(self.config.tool_timeout):
                        # Note: execute_tool is still synchronous
                        # For fully async, you'd want async tool implementations
                        result = await asyncio.to_thread(
                            execute_tool, tool_name, tool_input
                        )

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

                except asyncio.TimeoutError:
                    logger.warning(
                        f"Tool execution timed out: {tool_name}",
                        extra={
                            "tool_name": tool_name,
                            "timeout_seconds": self.config.tool_timeout
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

    async def _process_internal(self, user_input: str) -> str:
        """
        Internal processing logic for the agentic loop (async).

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
                response = await self._call_llm()

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
                    tool_results = await self._execute_tools(response.content)

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

    async def process(self, user_input: str) -> str:
        """
        Process a user request with total request timeout (async).

        Args:
            user_input: User's request/query

        Returns:
            Agent's response as a string
        """
        try:
            # Total request timeout using asyncio (cross-platform!)
            async with asyncio.timeout(self.config.total_timeout):
                return await self._process_internal(user_input)

        except asyncio.TimeoutError:
            return (
                f"Request exceeded maximum processing time of "
                f"{self.config.total_timeout}s. Please try a simpler request."
            )


async def main():
    """Run the async agent in interactive mode."""
    # Configure logging for interactive mode
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("=" * 60)
    print("Production-Ready Task Automation Agent (Async)")
    print("Cross-platform timeout handling with asyncio!")
    print("=" * 60)
    print("Type 'quit' or 'exit' to end the session\n")

    agent = Agent()

    while True:
        try:
            # Note: input() is blocking - in real async app, use aioconsole
            user_input = input("You: ").strip()

            if user_input.lower() in ["quit", "exit"]:
                print("Goodbye!")
                break

            if not user_input:
                continue

            response = await agent.process(user_input)
            print(f"\nAgent: {response}\n")

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}\n")


if __name__ == "__main__":
    # Python 3.11+ required for asyncio.timeout()
    import sys
    if sys.version_info < (3, 11):
        print("Error: This async version requires Python 3.11+ for asyncio.timeout()")
        print("Use the sync version (agent.py) for older Python versions")
        sys.exit(1)

    asyncio.run(main())
