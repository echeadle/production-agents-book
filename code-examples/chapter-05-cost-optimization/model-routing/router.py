# code-examples/chapter-05-cost-optimization/model-routing/router.py

import anthropic
import structlog
from enum import Enum
from typing import Literal, Tuple, Optional
import os
from dotenv import load_dotenv

logger = structlog.get_logger()


class TaskComplexity(Enum):
    """Task complexity levels."""
    SIMPLE = "simple"      # Classification, extraction, simple Q&A
    MODERATE = "moderate"  # Analysis, summarization, tool use
    COMPLEX = "complex"    # Multi-step reasoning, creative tasks


class ModelRouter:
    """Route tasks to appropriate models based on complexity."""

    # Model pricing (per million tokens)
    PRICING = {
        "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
        "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
        "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    }

    def __init__(self):
        self.model_map = {
            TaskComplexity.SIMPLE: "claude-3-haiku-20240307",
            TaskComplexity.MODERATE: "claude-3-5-sonnet-20241022",
            TaskComplexity.COMPLEX: "claude-3-opus-20240229",
        }

    def select_model(self, task: str) -> Tuple[str, TaskComplexity]:
        """
        Select the appropriate model for a task.

        In production, you might use:
        - A classifier model to determine complexity
        - Rule-based heuristics
        - User preferences (quality vs cost)
        - Historical performance data
        """
        complexity = self._classify_task(task)
        model = self.model_map[complexity]

        logger.info(
            "model_selected",
            task=task[:100],
            complexity=complexity.value,
            model=model,
        )

        return model, complexity

    def _classify_task(self, task: str) -> TaskComplexity:
        """
        Classify task complexity (heuristic-based).

        Simple tasks:
        - Sentiment analysis
        - Entity extraction
        - Classification
        - Simple Q&A

        Moderate tasks:
        - Summarization
        - Tool-based automation
        - Data analysis

        Complex tasks:
        - Creative writing
        - Multi-step reasoning
        - Code generation
        - Strategic planning
        """
        task_lower = task.lower()

        # Simple task indicators
        simple_keywords = [
            "classify", "category", "sentiment", "extract",
            "yes or no", "true or false", "which",
        ]
        if any(kw in task_lower for kw in simple_keywords):
            return TaskComplexity.SIMPLE

        # Complex task indicators
        complex_keywords = [
            "write a", "create a", "design", "plan",
            "analyze deeply", "comprehensive", "explain why",
        ]
        if any(kw in task_lower for kw in complex_keywords):
            return TaskComplexity.COMPLEX

        # Default to moderate
        return TaskComplexity.MODERATE

    def estimate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Estimate cost for a model and token count."""
        pricing = self.PRICING[model]
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost


class RoutedAgent:
    """Agent that routes requests to appropriate models."""

    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.router = ModelRouter()

    def run_task(self, task: str) -> Tuple[str, float]:
        """
        Execute task with optimal model selection.

        Returns: (response, cost_usd)
        """
        # Select model
        model, complexity = self.router.select_model(task)

        # Execute task
        response = self.client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user", "content": task}],
        )

        # Calculate actual cost
        cost = self.router.estimate_cost(
            model=model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

        logger.info(
            "task_completed",
            model=model,
            complexity=complexity.value,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            cost_usd=cost,
        )

        # Extract response text
        response_text = next(
            (block.text for block in response.content if hasattr(block, "text")),
            ""
        )

        return response_text, cost


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

    agent = RoutedAgent(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # Simple task -> Haiku
    print("=== Simple Task (Haiku) ===")
    response, cost = agent.run_task("Is this email spam? Subject: 'You won $1M!'")
    print(f"Response: {response}")
    print(f"Cost: ${cost:.6f}\n")

    # Moderate task -> Sonnet
    print("=== Moderate Task (Sonnet) ===")
    response, cost = agent.run_task("Summarize the key benefits of cloud computing")
    print(f"Response: {response}")
    print(f"Cost: ${cost:.6f}\n")

    # Complex task -> Opus
    print("=== Complex Task (Opus) ===")
    response, cost = agent.run_task(
        "Write a strategic plan for scaling our AI agent platform to 1M users"
    )
    print(f"Response: {response[:200]}...")
    print(f"Cost: ${cost:.6f}\n")
