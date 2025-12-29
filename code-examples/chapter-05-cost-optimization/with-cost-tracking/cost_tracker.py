# code-examples/chapter-05-cost-optimization/with-cost-tracking/cost_tracker.py

import structlog
from dataclasses import dataclass, field
from typing import Dict, Optional
from datetime import datetime
import json

logger = structlog.get_logger()


@dataclass
class TokenUsage:
    """Track token usage for a single API call."""

    input_tokens: int
    output_tokens: int
    model: str
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def total_tokens(self) -> int:
        """Total tokens used."""
        return self.input_tokens + self.output_tokens

    def cost_usd(self) -> float:
        """Calculate cost in USD based on model pricing."""
        # Pricing as of 2024 (per million tokens)
        pricing = {
            "claude-3-5-sonnet-20241022": {
                "input": 3.00,
                "output": 15.00,
            },
            "claude-3-haiku-20240307": {
                "input": 0.25,
                "output": 1.25,
            },
            "claude-3-opus-20240229": {
                "input": 15.00,
                "output": 75.00,
            },
        }

        if self.model not in pricing:
            logger.warning("unknown_model_for_pricing", model=self.model)
            return 0.0

        input_cost = (self.input_tokens / 1_000_000) * pricing[self.model]["input"]
        output_cost = (self.output_tokens / 1_000_000) * pricing[self.model]["output"]

        return input_cost + output_cost


@dataclass
class ConversationCost:
    """Track cumulative cost for a conversation."""

    conversation_id: str
    api_calls: list[TokenUsage] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)

    def add_usage(self, usage: TokenUsage):
        """Add a new API call to this conversation."""
        self.api_calls.append(usage)

        # Log the incremental cost
        logger.info(
            "token_usage",
            conversation_id=self.conversation_id,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            total_tokens=usage.total_tokens(),
            cost_usd=usage.cost_usd(),
            model=usage.model,
        )

    def total_tokens(self) -> int:
        """Total tokens across all API calls."""
        return sum(call.total_tokens() for call in self.api_calls)

    def total_cost(self) -> float:
        """Total cost in USD."""
        return sum(call.cost_usd() for call in self.api_calls)

    def summary(self) -> Dict:
        """Summary statistics for this conversation."""
        return {
            "conversation_id": self.conversation_id,
            "api_calls": len(self.api_calls),
            "total_tokens": self.total_tokens(),
            "total_cost_usd": round(self.total_cost(), 4),
            "metadata": self.metadata,
        }


class CostTracker:
    """
    Track costs across multiple conversations.

    In production, this would write to a database or metrics system.
    For this example, we'll track in-memory and export to JSON.
    """

    def __init__(self):
        self.conversations: Dict[str, ConversationCost] = {}

    def track_usage(
        self,
        conversation_id: str,
        input_tokens: int,
        output_tokens: int,
        model: str,
        metadata: Optional[Dict[str, str]] = None,
    ):
        """Track token usage for a conversation."""
        # Create conversation if it doesn't exist
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = ConversationCost(
                conversation_id=conversation_id,
                metadata=metadata or {},
            )

        # Add usage
        usage = TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=model,
        )

        self.conversations[conversation_id].add_usage(usage)

        # Check if we're approaching budget limits
        self._check_budget_alerts(conversation_id)

    def _check_budget_alerts(self, conversation_id: str):
        """Alert if conversation is getting expensive."""
        conv = self.conversations[conversation_id]
        cost = conv.total_cost()

        # Alert thresholds
        if cost > 1.0:
            logger.warning(
                "high_cost_conversation",
                conversation_id=conversation_id,
                cost_usd=cost,
                api_calls=len(conv.api_calls),
            )

        if cost > 5.0:
            logger.error(
                "very_high_cost_conversation",
                conversation_id=conversation_id,
                cost_usd=cost,
                api_calls=len(conv.api_calls),
            )

    def get_conversation_summary(self, conversation_id: str) -> Optional[Dict]:
        """Get cost summary for a specific conversation."""
        if conversation_id not in self.conversations:
            return None

        return self.conversations[conversation_id].summary()

    def get_total_cost(self) -> float:
        """Get total cost across all conversations."""
        return sum(conv.total_cost() for conv in self.conversations.values())

    def get_daily_summary(self) -> Dict:
        """Summary of costs for the day."""
        total_conversations = len(self.conversations)
        total_cost = self.get_total_cost()
        total_tokens = sum(conv.total_tokens() for conv in self.conversations.values())

        return {
            "total_conversations": total_conversations,
            "total_cost_usd": round(total_cost, 2),
            "total_tokens": total_tokens,
            "avg_cost_per_conversation": (
                round(total_cost / total_conversations, 4)
                if total_conversations > 0
                else 0.0
            ),
        }

    def export_to_json(self, filepath: str):
        """Export all conversation costs to JSON."""
        data = {
            "summary": self.get_daily_summary(),
            "conversations": [
                conv.summary() for conv in self.conversations.values()
            ],
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)

        logger.info("exported_cost_data", filepath=filepath)
