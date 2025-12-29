"""
Configuration for secure agent.

Loads all configuration from environment variables for security.
Never hardcode secrets!
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class SecurityConfig:
    """Security-related configuration."""

    # Input validation
    max_user_input_length: int = 10_000
    max_tool_input_length: int = 1_000

    # Prompt injection detection
    injection_detection_threshold: float = 0.5
    block_suspicious_inputs: bool = True

    # Rate limiting
    max_requests_per_hour: int = 100
    enable_rate_limiting: bool = True

    # Audit logging
    audit_log_file: str = "audit.log"
    audit_integrity_key: Optional[str] = None  # Set from env
    enable_audit_logging: bool = True

    # Output filtering
    filter_secrets: bool = True
    filter_pii: bool = True

    # Content moderation (would be enabled in production)
    enable_content_moderation: bool = False  # Disabled for demo


@dataclass
class AgentConfig:
    """Agent configuration."""

    # API configuration
    anthropic_api_key: str
    model: str = "claude-3-5-sonnet-20241022"
    max_tokens: int = 1024

    # Agent behavior
    max_iterations: int = 10

    # Security
    security: SecurityConfig = None

    def __post_init__(self):
        if self.security is None:
            self.security = SecurityConfig()


def load_config_from_env() -> AgentConfig:
    """
    Load configuration from environment variables.

    Required environment variables:
    - ANTHROPIC_API_KEY

    Optional environment variables:
    - MODEL
    - MAX_TOKENS
    - MAX_ITERATIONS
    - MAX_REQUESTS_PER_HOUR
    - AUDIT_INTEGRITY_KEY
    - BLOCK_SUSPICIOUS_INPUTS
    - FILTER_SECRETS
    - FILTER_PII

    Returns:
        AgentConfig with values from environment

    Raises:
        ValueError: If required environment variables are missing
    """
    # Required
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is required")

    # Optional agent config
    model = os.getenv("MODEL", "claude-3-5-sonnet-20241022")
    max_tokens = int(os.getenv("MAX_TOKENS", "1024"))
    max_iterations = int(os.getenv("MAX_ITERATIONS", "10"))

    # Security config
    security = SecurityConfig(
        max_requests_per_hour=int(os.getenv("MAX_REQUESTS_PER_HOUR", "100")),
        injection_detection_threshold=float(os.getenv("INJECTION_THRESHOLD", "0.5")),
        block_suspicious_inputs=os.getenv("BLOCK_SUSPICIOUS_INPUTS", "true").lower() == "true",
        audit_integrity_key=os.getenv("AUDIT_INTEGRITY_KEY"),  # Optional
        filter_secrets=os.getenv("FILTER_SECRETS", "true").lower() == "true",
        filter_pii=os.getenv("FILTER_PII", "true").lower() == "true",
        enable_content_moderation=os.getenv("ENABLE_CONTENT_MODERATION", "false").lower() == "true",
    )

    return AgentConfig(
        anthropic_api_key=api_key,
        model=model,
        max_tokens=max_tokens,
        max_iterations=max_iterations,
        security=security
    )


# Example usage
if __name__ == "__main__":
    from dotenv import load_dotenv

    # Load .env file
    load_dotenv()

    try:
        config = load_config_from_env()
        print("✅ Configuration loaded successfully!")
        print(f"Model: {config.model}")
        print(f"Max tokens: {config.max_tokens}")
        print(f"Security enabled: {config.security.block_suspicious_inputs}")
        print(f"Rate limiting: {config.security.max_requests_per_hour} req/hour")
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
