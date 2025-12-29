"""
Input validation and sanitization.

Validates all user inputs to prevent injection attacks, data corruption, and abuse.
Uses Pydantic for schema validation and custom validators for security checks.
"""

import re
from typing import Optional
from pydantic import BaseModel, Field, validator, ValidationError
import structlog

log = structlog.get_logger()


class InputLimits:
    """Input length limits for various fields."""

    MAX_USER_INPUT = 10_000  # 10K chars
    MAX_TOOL_INPUT = 1_000
    MAX_FILENAME = 255
    MAX_QUERY = 500
    MAX_EXPRESSION = 200


class UserInput(BaseModel):
    """
    Validated user input schema.

    All user inputs must pass through this validation.
    """

    text: str = Field(
        ...,
        min_length=1,
        max_length=InputLimits.MAX_USER_INPUT,
        description="User input text"
    )

    user_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="User identifier"
    )

    @validator('text')
    def validate_text_content(cls, v):
        """Validate text doesn't contain null bytes or control characters."""
        if '\x00' in v:
            raise ValueError("Input contains null bytes")

        # Remove control characters except newline, tab, carriage return
        cleaned = ''.join(
            char for char in v
            if char in '\n\r\t' or not char.iscntrl()
        )

        return cleaned

    @validator('user_id')
    def validate_user_id(cls, v):
        """Validate user_id is alphanumeric with allowed characters."""
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError(
                "user_id must be alphanumeric with underscores or hyphens"
            )
        return v


class ToolInput(BaseModel):
    """Validated tool input schema."""

    # Calculator input
    expression: Optional[str] = Field(
        None,
        min_length=1,
        max_length=InputLimits.MAX_EXPRESSION,
        description="Mathematical expression"
    )

    # File input
    filename: Optional[str] = Field(
        None,
        min_length=1,
        max_length=InputLimits.MAX_FILENAME,
        description="Filename for note"
    )

    # Content
    content: Optional[str] = Field(
        None,
        min_length=1,
        max_length=InputLimits.MAX_TOOL_INPUT,
        description="Content to save"
    )

    # Search query
    query: Optional[str] = Field(
        None,
        min_length=1,
        max_length=InputLimits.MAX_QUERY,
        description="Search query"
    )

    # Location
    location: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description="Location for weather"
    )

    @validator('expression')
    def validate_expression(cls, v):
        """Validate mathematical expression (prevent code injection)."""
        if v is None:
            return v

        # Only allow numbers, operators, parentheses, spaces, scientific notation
        allowed_chars = set('0123456789+-*/().eE ')
        if not all(c in allowed_chars for c in v):
            raise ValueError(
                f"Expression contains invalid characters. "
                f"Allowed: numbers, +, -, *, /, (), ., e, E, space"
            )

        # Check for dangerous patterns
        dangerous = ['__', 'import', 'exec', 'eval', 'open', 'compile']
        v_lower = v.lower()
        if any(pattern in v_lower for pattern in dangerous):
            raise ValueError(f"Expression contains forbidden pattern")

        # Check for excessive length or complexity
        if v.count('(') > 20 or v.count(')') > 20:
            raise ValueError("Expression too complex")

        return v

    @validator('filename')
    def validate_filename(cls, v):
        """Validate filename (prevent path traversal)."""
        if v is None:
            return v

        # No path separators
        if '/' in v or '\\' in v:
            raise ValueError("Filename cannot contain path separators")

        # No parent directory references
        if '..' in v:
            raise ValueError("Filename cannot contain '..'")

        # No hidden files
        if v.startswith('.'):
            raise ValueError("Filename cannot start with '.'")

        # Only alphanumeric, dash, underscore, dot
        if not re.match(r'^[a-zA-Z0-9_.-]+$', v):
            raise ValueError(
                "Filename must be alphanumeric with dash, underscore, or dot"
            )

        # Must have valid extension
        valid_extensions = ['.txt', '.md', '.json']
        if not any(v.endswith(ext) for ext in valid_extensions):
            raise ValueError(
                f"Filename must have valid extension: {', '.join(valid_extensions)}"
            )

        return v

    @validator('query', 'location')
    def validate_text_field(cls, v):
        """Validate general text fields."""
        if v is None:
            return v

        # No null bytes
        if '\x00' in v:
            raise ValueError("Input contains null bytes")

        # No excessive whitespace
        if len(v.strip()) == 0:
            raise ValueError("Input is only whitespace")

        return v.strip()


class InputValidator:
    """
    Input validation and sanitization service.

    Validates all inputs before processing to prevent:
    - Injection attacks
    - Path traversal
    - DoS via large inputs
    - Data corruption
    """

    def validate_user_input(self, text: str, user_id: str) -> UserInput:
        """
        Validate user input.

        Args:
            text: User input text
            user_id: User identifier

        Returns:
            Validated UserInput

        Raises:
            ValidationError: If validation fails
        """
        try:
            validated = UserInput(text=text, user_id=user_id)

            log.debug(
                "input.validated",
                user_id=user_id,
                input_length=len(text)
            )

            return validated

        except ValidationError as e:
            log.warning(
                "input.validation_failed",
                user_id=user_id,
                errors=e.errors()
            )
            raise

    def validate_tool_input(self, **kwargs) -> ToolInput:
        """
        Validate tool input.

        Args:
            **kwargs: Tool-specific parameters

        Returns:
            Validated ToolInput

        Raises:
            ValidationError: If validation fails
        """
        try:
            validated = ToolInput(**kwargs)

            log.debug(
                "tool_input.validated",
                tool_params=list(kwargs.keys())
            )

            return validated

        except ValidationError as e:
            log.warning(
                "tool_input.validation_failed",
                errors=e.errors()
            )
            raise

    def sanitize_html(self, html: str) -> str:
        """
        Sanitize HTML to prevent XSS.

        Args:
            html: HTML content

        Returns:
            Sanitized HTML
        """
        import bleach

        allowed_tags = ['p', 'br', 'strong', 'em', 'ul', 'ol', 'li', 'code']
        allowed_attributes = {}  # No attributes allowed

        clean = bleach.clean(
            html,
            tags=allowed_tags,
            attributes=allowed_attributes,
            strip=True
        )

        if clean != html:
            log.info("html.sanitized", removed_content=True)

        return clean


# Example usage
if __name__ == "__main__":
    from structlog import configure
    from logging_config import configure_logging

    # Configure logging
    configure_logging(json_logs=False)

    validator = InputValidator()

    print("Testing input validation...\n")

    # Valid input
    try:
        result = validator.validate_user_input(
            text="What is 2 + 2?",
            user_id="user_123"
        )
        print(f"✅ Valid input: {result.text}")
    except ValidationError as e:
        print(f"❌ Validation failed: {e}")

    # Invalid input (too long user_id)
    try:
        result = validator.validate_user_input(
            text="Hello",
            user_id="x" * 200  # Too long
        )
        print(f"✅ Valid input: {result.text}")
    except ValidationError as e:
        print(f"❌ Validation failed: user_id too long")

    # Tool input - valid
    try:
        result = validator.validate_tool_input(
            expression="2 + 2 * 3"
        )
        print(f"✅ Valid expression: {result.expression}")
    except ValidationError as e:
        print(f"❌ Validation failed: {e}")

    # Tool input - code injection attempt
    try:
        result = validator.validate_tool_input(
            expression="__import__('os').system('ls')"
        )
        print(f"✅ Valid expression: {result.expression}")
    except ValidationError as e:
        print(f"❌ Blocked injection: expression contains forbidden pattern")

    # Filename - path traversal attempt
    try:
        result = validator.validate_tool_input(
            filename="../../etc/passwd"
        )
        print(f"✅ Valid filename: {result.filename}")
    except ValidationError as e:
        print(f"❌ Blocked path traversal: {e.errors()[0]['msg']}")

    # Valid filename
    try:
        result = validator.validate_tool_input(
            filename="my_note.txt"
        )
        print(f"✅ Valid filename: {result.filename}")
    except ValidationError as e:
        print(f"❌ Validation failed: {e}")

    print("\n✅ Input validation working correctly!")
