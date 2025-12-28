"""
Task automation agent with retry logic.

This version adds exponential backoff retry logic to the reference agent,
making it resilient to transient API failures.
"""

import anthropic
from typing import List, Dict, Any, Optional
from config import AgentConfig, get_config
from tools import TOOLS, execute_tool
from retry import retry_with_backoff


class Agent:
    """Task automation agent with retry resilience."""

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
        Call the LLM API with retry logic.

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
            messages=self.conversation_history
        )

    def _execute_tools(self, content: list) -> list:
        """
        Execute tools requested by the agent.

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

                print(f"[Agent] Using tool: {tool_name}")
                print(f"[Agent] Tool input: {tool_input}")

                try:
                    # Execute the tool
                    result = execute_tool(tool_name, tool_input)
                    print(f"[Agent] Tool result: {result}")

                    results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

                except Exception as e:
                    print(f"[Agent] Tool error: {e}")
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

    def process(self, user_input: str) -> str:
        """
        Process a user request through the agentic loop.

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
                # Call LLM with retry logic
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
                print(f"[Agent] {error_msg}")
                return error_msg

        return "Maximum iterations reached"


def main():
    """Run the agent in interactive mode."""
    print("=" * 60)
    print("Task Automation Agent - With Retry Logic")
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
