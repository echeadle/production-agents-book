# code-examples/chapter-05-cost-optimization/with-cost-tracking/agent.py

import anthropic
import structlog
import uuid
from typing import List, Dict, Optional
from cost_tracker import CostTracker

logger = structlog.get_logger()


class CostAwareAgent:
    """
    Reference agent with comprehensive cost tracking.
    """

    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.cost_tracker = CostTracker()

        # System prompt
        self.system_prompt = """You are a helpful task automation assistant.
You can search the web, perform calculations, save notes, and check weather.
Be concise and helpful."""

    def run_conversation(
        self,
        user_message: str,
        conversation_id: Optional[str] = None,
        max_turns: int = 10,
    ) -> str:
        """
        Run a conversation with cost tracking.
        """
        # Generate conversation ID if not provided
        if conversation_id is None:
            conversation_id = str(uuid.uuid4())

        logger.info(
            "conversation_started",
            conversation_id=conversation_id,
            user_message=user_message,
        )

        # Initialize conversation history
        messages = [{"role": "user", "content": user_message}]

        for turn in range(max_turns):
            # Call Claude API
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=self.system_prompt,
                messages=messages,
                tools=self._get_tools(),
            )

            # Track token usage
            self.cost_tracker.track_usage(
                conversation_id=conversation_id,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                model=self.model,
                metadata={"turn": str(turn)},
            )

            # Log turn completion
            logger.info(
                "conversation_turn",
                conversation_id=conversation_id,
                turn=turn,
                stop_reason=response.stop_reason,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )

            # Check stop reason
            if response.stop_reason == "end_turn":
                # Extract final response
                final_text = next(
                    (block.text for block in response.content if hasattr(block, "text")),
                    ""
                )

                # Log conversation summary
                summary = self.cost_tracker.get_conversation_summary(conversation_id)
                logger.info("conversation_completed", **summary)

                return final_text

            # Handle tool calls
            if response.stop_reason == "tool_use":
                # Add assistant message to history
                messages.append({"role": "assistant", "content": response.content})

                # Execute tools and collect results
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = self._execute_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })

                # Add tool results to history
                messages.append({"role": "user", "content": tool_results})
            else:
                logger.warning(
                    "unexpected_stop_reason",
                    conversation_id=conversation_id,
                    stop_reason=response.stop_reason,
                )
                break

        logger.error(
            "conversation_max_turns",
            conversation_id=conversation_id,
            max_turns=max_turns,
        )
        return "Maximum turns reached. Please start a new conversation."

    def _get_tools(self) -> List[Dict]:
        """Tool definitions for the agent."""
        return [
            {
                "name": "search_web",
                "description": "Search the web for information",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "calculate",
                "description": "Perform a mathematical calculation",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "expression": {"type": "string", "description": "Math expression"},
                    },
                    "required": ["expression"],
                },
            },
            {
                "name": "save_note",
                "description": "Save a note to file",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["title", "content"],
                },
            },
        ]

    def _execute_tool(self, tool_name: str, tool_input: Dict) -> str:
        """Execute a tool (mock implementations for this example)."""
        if tool_name == "search_web":
            return f"Search results for: {tool_input['query']}"
        elif tool_name == "calculate":
            try:
                result = eval(tool_input["expression"])
                return str(result)
            except Exception as e:
                return f"Calculation error: {e}"
        elif tool_name == "save_note":
            return f"Note '{tool_input['title']}' saved successfully"
        else:
            return f"Unknown tool: {tool_name}"

    def get_cost_summary(self) -> Dict:
        """Get overall cost summary."""
        return self.cost_tracker.get_daily_summary()

    def export_costs(self, filepath: str = "costs.json"):
        """Export cost data to JSON."""
        self.cost_tracker.export_to_json(filepath)


# Example usage
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()

    # Configure structured logging
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
    )

    agent = CostAwareAgent(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # Run a few conversations
    agent.run_conversation("What is 15 * 24?")
    agent.run_conversation("Search for the latest AI news and summarize it")
    agent.run_conversation("Save a note about my meeting tomorrow at 2pm")

    # Print cost summary
    summary = agent.get_cost_summary()
    print("\n=== Cost Summary ===")
    print(f"Total conversations: {summary['total_conversations']}")
    print(f"Total cost: ${summary['total_cost_usd']}")
    print(f"Total tokens: {summary['total_tokens']:,}")
    print(f"Avg cost per conversation: ${summary['avg_cost_per_conversation']}")

    # Export detailed costs
    agent.export_costs("costs.json")
