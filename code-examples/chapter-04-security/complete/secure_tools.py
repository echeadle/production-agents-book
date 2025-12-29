"""
Secure tools with authorization and validation.

All tools implement:
- Authorization checks (who can use this tool?)
- Input validation (is the input safe?)
- Audit logging (who did what?)
- Error handling (fail securely)
"""

import os
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional, List
import structlog

from input_validator import InputValidator, ToolInput
from audit_logger import AuditLogger

log = structlog.get_logger()


class AuthorizationError(Exception):
    """Raised when user is not authorized for an action."""
    pass


class SecureTool:
    """
    Base class for security-aware tools.

    All tools must:
    1. Check authorization before execution
    2. Validate inputs
    3. Log execution to audit log
    4. Handle errors securely
    """

    def __init__(
        self,
        name: str,
        validator: InputValidator,
        audit_logger: AuditLogger,
        allowed_users: Optional[List[str]] = None
    ):
        """
        Initialize secure tool.

        Args:
            name: Tool name
            validator: Input validator
            audit_logger: Audit logger
            allowed_users: List of user_ids allowed to use this tool (None = all)
        """
        self.name = name
        self.validator = validator
        self.audit = audit_logger
        self.allowed_users = allowed_users

    def check_authorization(self, user_id: str, **kwargs) -> bool:
        """
        Check if user is authorized to use this tool.

        Override in subclass for tool-specific authorization logic.

        Args:
            user_id: User requesting access
            **kwargs: Tool-specific parameters

        Returns:
            True if authorized, False otherwise
        """
        # Default: Check if user in allowed list
        if self.allowed_users is not None:
            return user_id in self.allowed_users

        # Default: Allow all users
        return True

    def execute(
        self,
        user_id: str,
        correlation_id: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Execute tool with security checks.

        Args:
            user_id: User executing the tool
            correlation_id: Request correlation ID
            **kwargs: Tool-specific parameters

        Returns:
            Tool execution result

        Raises:
            AuthorizationError: If user not authorized
            ValidationError: If input validation fails
        """
        # 1. Authorization check
        if not self.check_authorization(user_id, **kwargs):
            self.audit.log_authorization(
                user_id=user_id,
                action=f"execute_{self.name}",
                resource=self.name,
                result="denied"
            )

            log.warning(
                "tool.authorization_denied",
                user_id=user_id,
                tool=self.name
            )

            raise AuthorizationError(
                f"User {user_id} not authorized to use tool '{self.name}'"
            )

        # 2. Input validation
        try:
            validated = self.validator.validate_tool_input(**kwargs)
        except Exception as e:
            self.audit.log_tool_execution(
                user_id=user_id,
                tool_name=self.name,
                tool_input=kwargs,
                result="validation_failed",
                correlation_id=correlation_id
            )
            raise

        # 3. Execute tool
        try:
            result = self._execute_impl(user_id, validated, **kwargs)

            # 4. Audit log success
            self.audit.log_tool_execution(
                user_id=user_id,
                tool_name=self.name,
                tool_input=kwargs,
                result="success",
                output=result,
                correlation_id=correlation_id
            )

            log.info(
                "tool.executed",
                user_id=user_id,
                tool=self.name,
                correlation_id=correlation_id
            )

            return result

        except Exception as e:
            # 4. Audit log failure
            self.audit.log_tool_execution(
                user_id=user_id,
                tool_name=self.name,
                tool_input=kwargs,
                result="error",
                output=str(e),
                correlation_id=correlation_id
            )

            log.error(
                "tool.execution_failed",
                user_id=user_id,
                tool=self.name,
                error=str(e),
                exc_info=True
            )

            # Re-raise
            raise

    def _execute_impl(self, user_id: str, validated: ToolInput, **kwargs) -> str:
        """
        Implement tool logic in subclass.

        Args:
            user_id: User executing the tool
            validated: Validated tool input
            **kwargs: Original tool parameters

        Returns:
            Tool execution result
        """
        raise NotImplementedError


class CalculatorTool(SecureTool):
    """Calculator tool with expression validation."""

    def __init__(self, validator: InputValidator, audit_logger: AuditLogger):
        super().__init__(
            name="calculator",
            validator=validator,
            audit_logger=audit_logger,
            allowed_users=None  # All users can use calculator
        )

    def _execute_impl(self, user_id: str, validated: ToolInput, **kwargs) -> str:
        """Execute calculation."""
        expression = validated.expression

        if not expression:
            raise ValueError("expression is required")

        try:
            # Evaluate (safe because validated)
            result = eval(expression, {"__builtins__": {}}, {})

            return f"{expression} = {result}"

        except Exception as e:
            raise ValueError(f"Invalid expression: {e}")


class SaveNoteTool(SecureTool):
    """
    Save note tool with file path validation and idempotency.

    Uses content hash for filename to ensure idempotency.
    """

    def __init__(
        self,
        validator: InputValidator,
        audit_logger: AuditLogger,
        notes_dir: str = "notes"
    ):
        super().__init__(
            name="save_note",
            validator=validator,
            audit_logger=audit_logger,
            allowed_users=None  # All users can save notes
        )
        self.notes_dir = notes_dir

        # Create notes directory
        os.makedirs(notes_dir, exist_ok=True)

    def _execute_impl(self, user_id: str, validated: ToolInput, **kwargs) -> str:
        """Save note to file."""
        content = validated.content
        filename = validated.filename

        if not content:
            raise ValueError("content is required")

        # If no filename provided, generate from content hash (idempotent)
        if not filename:
            content_hash = hashlib.md5(content.encode()).hexdigest()[:12]
            timestamp = datetime.now().strftime("%Y%m%d")
            filename = f"note_{timestamp}_{content_hash}.txt"

        # Construct safe path (filename already validated)
        filepath = os.path.join(self.notes_dir, filename)

        # Check if file already exists with same content (idempotency check)
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                existing_content = f.read()

            if existing_content == content:
                # Audit log idempotent save
                self.audit.log_data_access(
                    user_id=user_id,
                    action="write",
                    resource=filepath,
                    result="idempotent",
                    details={"reason": "content_unchanged"}
                )

                return f"Note already exists at {filepath} (idempotent)"

        # Save note
        with open(filepath, "w") as f:
            f.write(content)

        # Audit log data access
        self.audit.log_data_access(
            user_id=user_id,
            action="write",
            resource=filepath,
            result="success",
            details={"bytes_written": len(content)}
        )

        return f"Note saved to {filepath}"


class WebSearchTool(SecureTool):
    """
    Web search tool (simulated).

    In production, would call actual search API.
    """

    def __init__(self, validator: InputValidator, audit_logger: AuditLogger):
        super().__init__(
            name="web_search",
            validator=validator,
            audit_logger=audit_logger,
            allowed_users=None  # All users can search
        )

    def _execute_impl(self, user_id: str, validated: ToolInput, **kwargs) -> str:
        """Execute web search (simulated)."""
        query = validated.query

        if not query:
            raise ValueError("query is required")

        # Simulated search (in production, call real API)
        result = f"Search results for: {query}\n\n"
        result += "1. Example result 1\n"
        result += "2. Example result 2\n"
        result += "3. Example result 3"

        return result


class GetWeatherTool(SecureTool):
    """
    Weather tool (simulated).

    In production, would call actual weather API.
    """

    def __init__(self, validator: InputValidator, audit_logger: AuditLogger):
        super().__init__(
            name="get_weather",
            validator=validator,
            audit_logger=audit_logger,
            allowed_users=None  # All users can check weather
        )

    def _execute_impl(self, user_id: str, validated: ToolInput, **kwargs) -> str:
        """Get weather (simulated)."""
        location = validated.location

        if not location:
            raise ValueError("location is required")

        # Simulated weather (in production, call real API)
        return f"Weather in {location}: Sunny, 72°F"


# Tool registry
def create_secure_tools(
    validator: InputValidator,
    audit_logger: AuditLogger
) -> Dict[str, SecureTool]:
    """
    Create all secure tools.

    Args:
        validator: Input validator
        audit_logger: Audit logger

    Returns:
        Dict mapping tool name to tool instance
    """
    return {
        "calculator": CalculatorTool(validator, audit_logger),
        "save_note": SaveNoteTool(validator, audit_logger),
        "web_search": WebSearchTool(validator, audit_logger),
        "get_weather": GetWeatherTool(validator, audit_logger),
    }


# Tool schemas for Claude API
TOOL_SCHEMAS = [
    {
        "name": "calculator",
        "description": "Evaluate a mathematical expression. Supports basic arithmetic and parentheses.",
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "The mathematical expression to evaluate (e.g., '2 + 2', '(10 * 5) / 2')"
                }
            },
            "required": ["expression"]
        }
    },
    {
        "name": "save_note",
        "description": "Save a note to a text file. If no filename is provided, generates one from content hash (idempotent).",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The content to save"
                },
                "filename": {
                    "type": "string",
                    "description": "Optional filename (must be alphanumeric with .txt, .md, or .json extension)"
                }
            },
            "required": ["content"]
        }
    },
    {
        "name": "web_search",
        "description": "Search the web for information (simulated).",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_weather",
        "description": "Get current weather for a location (simulated).",
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "The location to get weather for (e.g., 'Seattle, WA')"
                }
            },
            "required": ["location"]
        }
    }
]


# Example usage
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)

    # Create dependencies
    validator = InputValidator()
    audit = AuditLogger(log_file="test_tools_audit.log")

    # Create tools
    tools = create_secure_tools(validator, audit)

    print("Testing secure tools...\n")

    user_id = "user_123"

    # Test calculator
    print("--- Calculator ---")
    result = tools["calculator"].execute(
        user_id=user_id,
        expression="2 + 2 * 3"
    )
    print(f"Result: {result}")
    print()

    # Test save_note (idempotent)
    print("--- Save Note (First Time) ---")
    result = tools["save_note"].execute(
        user_id=user_id,
        content="Hello, World!"
    )
    print(f"Result: {result}")
    print()

    print("--- Save Note (Idempotent) ---")
    result = tools["save_note"].execute(
        user_id=user_id,
        content="Hello, World!"
    )
    print(f"Result: {result}")
    print()

    # Test with invalid input
    print("--- Invalid Input (Code Injection Attempt) ---")
    try:
        result = tools["calculator"].execute(
            user_id=user_id,
            expression="__import__('os').system('ls')"
        )
        print(f"Result: {result}")
    except Exception as e:
        print(f"❌ Blocked: {e}")
    print()

    # Cleanup
    import shutil
    if os.path.exists("notes"):
        shutil.rmtree("notes")
    if os.path.exists("test_tools_audit.log"):
        os.remove("test_tools_audit.log")

    print("✅ Secure tools working correctly!")
