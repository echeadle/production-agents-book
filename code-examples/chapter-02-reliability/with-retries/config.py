"""
Agent configuration management.

Loads configuration from environment variables using python-dotenv.
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class AgentConfig:
    """Configuration for the task automation agent."""

    api_key: str
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    temperature: float = 1.0
    max_iterations: int = 10  # Prevent infinite loops
    system_prompt: str = (
        "You are a helpful task automation assistant. You can search the web, "
        "perform calculations, save notes to files, and get weather information. "
        "Use the available tools to help users accomplish their tasks efficiently."
    )

    @classmethod
    def from_env(cls) -> "AgentConfig":
        """
        Load configuration from environment variables.

        Returns:
            AgentConfig instance with values from environment

        Raises:
            ValueError: If ANTHROPIC_API_KEY is not set
        """
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable not found. "
                "Please set it in your .env file or environment."
            )

        return cls(
            api_key=api_key,
            model=os.getenv("MODEL", "claude-sonnet-4-20250514"),
            max_tokens=int(os.getenv("MAX_TOKENS", "4096")),
            temperature=float(os.getenv("TEMPERATURE", "1.0")),
            max_iterations=int(os.getenv("MAX_ITERATIONS", "10")),
        )


def get_config() -> AgentConfig:
    """Get agent configuration from environment."""
    return AgentConfig.from_env()
