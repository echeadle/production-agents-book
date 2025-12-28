"""
Reference Agent - A simple task automation agent.

This is the baseline agent we'll progressively harden for production
throughout the book. Current state: functional, but not production-ready.

What's missing (added in later chapters):
- Retry logic and exponential backoff (Chapter 2)
- Circuit breakers (Chapter 2)
- Comprehensive error handling (Chapter 2)
- Structured logging (Chapter 3)
- Metrics collection (Chapter 3)
- Distributed tracing (Chapter 3)
- Input validation (Chapter 4)
- Rate limiting (Chapter 4)
- Cost tracking (Chapter 5)
- And much more...

Chapter 1: The Production Mindset
"""

from typing import List, Dict, Any, Optional
import anthropic

from config import AgentConfig, get_config
from tools import TOOLS, execute_tool


class Agent:
    """
    A simple task automation agent with tool calling capabilities.

    This agent can:
    - Search the web
    - Perform calculations
    - Save notes
    - Get weather information
    """

    def __init__(self, config: Optional[AgentConfig] = None):
        """
        Initialize the agent.

        Args:
            config: Agent configuration (defaults to loading from environment)
        """
        self.config = config or get_config()
        self.client = anthropic.Anthropic(api_key=self.config.api_key)
        self.conversation_history: List[Dict[str, Any]] = []

    def process(self, user_input: str) -> str:
        """
        Process a user request and return the agent's response.

        Args:
            user_input: The user's request

        Returns:
            The agent's response

        Raises:
            Exception: If processing fails
        """
        # Add user message to conversation
        self.conversation_history.append({
            "role": "user",
            "content": user_input
        })

        # Agentic loop: continue until we get a text response or hit max iterations
        iterations = 0

        while iterations < self.config.max_iterations:
            iterations += 1

            # Call Claude API
            response = self.client.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                system=self.config.system_prompt,
                tools=TOOLS,
                messages=self.conversation_history
            )

            # Check stop reason
            if response.stop_reason == "end_turn":
                # Agent is done, extract final text response
                final_response = self._extract_text_response(response)
                self.conversation_history.append({
                    "role": "assistant",
                    "content": response.content
                })
                return final_response

            elif response.stop_reason == "tool_use":
                # Agent wants to use tools
                # Add assistant message to history
                self.conversation_history.append({
                    "role": "assistant",
                    "content": response.content
                })

                # Execute tools and collect results
                tool_results = []

                for content_block in response.content:
                    if content_block.type == "tool_use":
                        tool_name = content_block.name
                        tool_input = content_block.input
                        tool_use_id = content_block.id

                        print(f"[Agent] Using tool: {tool_name}")
                        print(f"[Agent] Tool input: {tool_input}")

                        # Execute the tool
                        try:
                            result = execute_tool(tool_name, tool_input)
                            print(f"[Agent] Tool result: {result[:100]}...")

                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tool_use_id,
                                "content": result
                            })

                        except Exception as e:
                            # Basic error handling - will be improved in Chapter 2
                            error_msg = f"Error: {str(e)}"
                            print(f"[Agent] Tool error: {error_msg}")

                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tool_use_id,
                                "content": error_msg,
                                "is_error": True
                            })

                # Add tool results to conversation
                self.conversation_history.append({
                    "role": "user",
                    "content": tool_results
                })

                # Continue loop to get agent's response to tool results

            elif response.stop_reason == "max_tokens":
                # Hit token limit
                return "I apologize, but my response was cut off due to length. Could you ask for a more specific or concise answer?"

            else:
                # Unexpected stop reason
                return f"Unexpected response from agent. Stop reason: {response.stop_reason}"

        # Hit max iterations
        return f"I apologize, but I've reached my maximum number of steps ({self.config.max_iterations}). The task may be too complex or I may be stuck in a loop."

    def _extract_text_response(self, response) -> str:
        """
        Extract text content from Claude's response.

        Args:
            response: Claude API response

        Returns:
            Extracted text content
        """
        text_parts = []

        for content_block in response.content:
            if hasattr(content_block, "text"):
                text_parts.append(content_block.text)

        return "\n".join(text_parts) if text_parts else ""

    def reset_conversation(self):
        """Reset the conversation history."""
        self.conversation_history = []


def main():
    """
    Run the agent in interactive mode.
    """
    print("=" * 60)
    print("Reference Agent - Task Automation Assistant")
    print("=" * 60)
    print("\nI can help you with:")
    print("  • Web searches")
    print("  • Mathematical calculations")
    print("  • Saving notes")
    print("  • Weather information")
    print("\nType 'quit' or 'exit' to end the session.")
    print("Type 'reset' to start a new conversation.")
    print("=" * 60)
    print()

    # Initialize agent
    try:
        agent = Agent()
    except ValueError as e:
        print(f"Error: {e}")
        print("\nPlease create a .env file with your ANTHROPIC_API_KEY.")
        return

    # Interactive loop
    while True:
        try:
            user_input = input("\nYou: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ["quit", "exit"]:
                print("\nGoodbye!")
                break

            if user_input.lower() == "reset":
                agent.reset_conversation()
                print("\n[Conversation reset]")
                continue

            # Process request
            print("\nAgent: ", end="", flush=True)
            response = agent.process(user_input)
            print(response)

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break

        except Exception as e:
            print(f"\nError: {str(e)}")
            print("Please try again or type 'reset' to start fresh.")


if __name__ == "__main__":
    main()
