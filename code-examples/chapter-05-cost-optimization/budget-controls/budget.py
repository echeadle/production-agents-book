# code-examples/chapter-05-cost-optimization/budget-controls/budget.py

import anthropic
import structlog
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
import os
from dotenv import load_dotenv
import sys

# Add parent directory to path to import router
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from model_routing.router import ModelRouter

logger = structlog.get_logger()


@dataclass
class Budget:
    """Budget configuration."""

    # Daily budget
    daily_limit_usd: float

    # Per-conversation budget
    conversation_limit_usd: Optional[float] = None

    # Per-user budget
    user_limit_usd: Optional[float] = None

    # Budget period
    period_start: datetime = None

    def __post_init__(self):
        if self.period_start is None:
            self.period_start = datetime.utcnow()


class BudgetEnforcer:
    """
    Enforce budget limits across different dimensions.

    In production, this would integrate with your cost tracking database.
    """

    def __init__(self, budget: Budget):
        self.budget = budget

        # Track spending (in production, use database)
        self.daily_spend = 0.0
        self.conversation_spend = {}  # conversation_id -> spend
        self.user_spend = {}  # user_id -> spend

        # Track budget violations
        self.violations = []

    def check_budget(
        self,
        cost_usd: float,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> bool:
        """
        Check if a proposed cost would exceed budget.

        Returns: True if within budget, False if would exceed
        """
        # Reset daily budget if period has expired
        self._reset_if_needed()

        # Check daily budget
        if self.daily_spend + cost_usd > self.budget.daily_limit_usd:
            self._log_violation(
                "daily_budget_exceeded",
                current=self.daily_spend,
                limit=self.budget.daily_limit_usd,
                proposed_cost=cost_usd,
            )
            return False

        # Check conversation budget
        if conversation_id and self.budget.conversation_limit_usd:
            conv_spend = self.conversation_spend.get(conversation_id, 0.0)
            if conv_spend + cost_usd > self.budget.conversation_limit_usd:
                self._log_violation(
                    "conversation_budget_exceeded",
                    conversation_id=conversation_id,
                    current=conv_spend,
                    limit=self.budget.conversation_limit_usd,
                    proposed_cost=cost_usd,
                )
                return False

        # Check user budget
        if user_id and self.budget.user_limit_usd:
            user_spend = self.user_spend.get(user_id, 0.0)
            if user_spend + cost_usd > self.budget.user_limit_usd:
                self._log_violation(
                    "user_budget_exceeded",
                    user_id=user_id,
                    current=user_spend,
                    limit=self.budget.user_limit_usd,
                    proposed_cost=cost_usd,
                )
                return False

        # All checks passed
        return True

    def record_spend(
        self,
        cost_usd: float,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ):
        """Record actual spend after API call."""
        self.daily_spend += cost_usd

        if conversation_id:
            self.conversation_spend[conversation_id] = (
                self.conversation_spend.get(conversation_id, 0.0) + cost_usd
            )

        if user_id:
            self.user_spend[user_id] = (
                self.user_spend.get(user_id, 0.0) + cost_usd
            )

        logger.info(
            "spend_recorded",
            cost_usd=cost_usd,
            daily_total=self.daily_spend,
            daily_remaining=self.budget.daily_limit_usd - self.daily_spend,
            conversation_id=conversation_id,
            user_id=user_id,
        )

    def _reset_if_needed(self):
        """Reset daily budget if period has expired."""
        now = datetime.utcnow()
        period_end = self.budget.period_start + timedelta(days=1)

        if now >= period_end:
            logger.info(
                "budget_period_reset",
                previous_spend=self.daily_spend,
                period_start=self.budget.period_start,
                period_end=period_end,
            )

            self.daily_spend = 0.0
            self.conversation_spend = {}
            self.user_spend = {}
            self.budget.period_start = now

    def _log_violation(self, violation_type: str, **kwargs):
        """Log budget violation."""
        logger.error(violation_type, **kwargs)
        self.violations.append({
            "type": violation_type,
            "timestamp": datetime.utcnow(),
            **kwargs,
        })

    def get_budget_status(self) -> dict:
        """Get current budget status."""
        return {
            "daily_limit_usd": self.budget.daily_limit_usd,
            "daily_spend_usd": self.daily_spend,
            "daily_remaining_usd": self.budget.daily_limit_usd - self.daily_spend,
            "daily_utilization_pct": (
                self.daily_spend / self.budget.daily_limit_usd * 100
                if self.budget.daily_limit_usd > 0
                else 0
            ),
            "period_start": self.budget.period_start,
            "violations": len(self.violations),
        }


class BudgetControlledAgent:
    """Agent with budget enforcement."""

    def __init__(self, api_key: str, budget: Budget):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.budget_enforcer = BudgetEnforcer(budget)
        self.router = ModelRouter()

    def run_task(
        self,
        task: str,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> str:
        """
        Execute task with budget enforcement.
        """
        # Select model
        model, complexity = self.router.select_model(task)

        # Estimate cost (rough estimate before API call)
        estimated_cost = self.router.estimate_cost(
            model=model,
            input_tokens=500,  # Rough estimate
            output_tokens=200,  # Rough estimate
        )

        # Check budget BEFORE making API call
        if not self.budget_enforcer.check_budget(
            cost_usd=estimated_cost,
            conversation_id=conversation_id,
            user_id=user_id,
        ):
            raise BudgetExceededError(
                f"Budget limit reached. Status: {self.budget_enforcer.get_budget_status()}"
            )

        # Make API call
        response = self.client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user", "content": task}],
        )

        # Calculate actual cost
        actual_cost = self.router.estimate_cost(
            model=model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

        # Record actual spend
        self.budget_enforcer.record_spend(
            cost_usd=actual_cost,
            conversation_id=conversation_id,
            user_id=user_id,
        )

        # Extract response
        response_text = next(
            (block.text for block in response.content if hasattr(block, "text")),
            ""
        )

        return response_text

    def get_budget_status(self) -> dict:
        """Get budget status."""
        return self.budget_enforcer.get_budget_status()


class BudgetExceededError(Exception):
    """Raised when budget limit is exceeded."""
    pass


# Example usage
if __name__ == "__main__":
    load_dotenv()

    # Configure structured logging
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
    )

    # Configure budget
    budget = Budget(
        daily_limit_usd=10.00,  # $10/day max
        conversation_limit_usd=1.00,  # $1/conversation max
        user_limit_usd=5.00,  # $5/user/day max
    )

    agent = BudgetControlledAgent(
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        budget=budget,
    )

    try:
        # Run tasks
        for i in range(100):
            response = agent.run_task(
                f"Task {i}: What is {i} * 2?",
                conversation_id=f"conv-{i % 10}",  # 10 conversations
                user_id="user-123",
            )
            print(f"Task {i} completed: {response}")

    except BudgetExceededError as e:
        print(f"\nBudget exceeded: {e}")

    # Print final budget status
    status = agent.get_budget_status()
    print("\n=== Budget Status ===")
    print(f"Daily limit: ${status['daily_limit_usd']}")
    print(f"Daily spend: ${status['daily_spend_usd']:.4f}")
    print(f"Remaining: ${status['daily_remaining_usd']:.4f}")
    print(f"Utilization: {status['daily_utilization_pct']:.1f}%")
    print(f"Violations: {status['violations']}")
