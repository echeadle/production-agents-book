"""
Configuration for the reference agent.

Handles environment variables and agent settings.

Chapter 1: The Production Mindset
"""

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class AgentConfig:
    """Configuration for the agent."""

    # Anthropic API settings
    api_key: str
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    temperature: float = 1.0

    # Agent behavior settings
    max_iterations: int = 10  # Maximum number of tool calls per request
    system_prompt: str = """You are a helpful task automation assistant. You have access to several tools:

- web_search: Search the web for information
- calculator: Perform mathematical calculations
- save_note: Save notes to files
- get_weather: Get current weather for a location

Use these tools to help users accomplish their tasks. Be concise and helpful."""

    @classmethod
    def from_env(cls) -> "AgentConfig":
        """
        Create configuration from environment variables.

        Returns:
            AgentConfig instance

        Raises:
            ValueError: If ANTHROPIC_API_KEY is not set
        """
        api_key = os.getenv("ANTHROPIC_API_KEY")

        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY not found in environment variables. "
                "Please set it in your .env file or environment."
            )

        # Optional overrides from environment
        model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
        max_tokens = int(os.getenv("MAX_TOKENS", "4096"))
        temperature = float(os.getenv("TEMPERATURE", "1.0"))
        max_iterations = int(os.getenv("MAX_ITERATIONS", "10"))

        return cls(
            api_key=api_key,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            max_iterations=max_iterations,
        )


def get_config() -> AgentConfig:
    """
    Get the agent configuration.

    Returns:
        AgentConfig instance

    Raises:
        ValueError: If configuration is invalid
    """
    return AgentConfig.from_env()
