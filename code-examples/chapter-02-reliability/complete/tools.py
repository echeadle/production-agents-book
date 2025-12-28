"""
Tool definitions with circuit breakers and graceful degradation.

Each tool is protected by a circuit breaker and categorized by criticality
for graceful degradation.
"""

import os
import math
import hashlib
from datetime import datetime
from typing import Any, Dict
from circuit_breaker import circuit_breaker, CircuitBreakerError


# Tool criticality levels
TOOL_CRITICALITY = {
    "calculator": "critical",  # Must always work
    "save_note": "critical",  # Must always work
    "web_search": "optional",  # Can fail gracefully
    "get_weather": "optional",  # Can fail gracefully
}


@circuit_breaker(
    name="web_search",
    failure_threshold=5,
    recovery_timeout=60.0,
    expected_exception=Exception
)
def web_search(query: str) -> str:
    """
    Search the web for information (mocked for demo).

    Protected by circuit breaker - will fail fast after 5 consecutive failures.

    Args:
        query: The search query

    Returns:
        Formatted search results as a string

    Raises:
        CircuitBreakerError: If circuit is open
    """
    # Mock implementation
    return f"""
Search results for: "{query}"

1. Example Result 1
   This is a mock search result for demonstration purposes.
   URL: https://example.com/result1

2. Example Result 2
   Another mock result showing what real search would return.
   URL: https://example.com/result2

3. Example Result 3
   In production, this would call a real search API.
   URL: https://example.com/result3
""".strip()


def calculator(expression: str) -> str:
    """
    Evaluate a mathematical expression.

    Critical tool - failures are not tolerated.

    Args:
        expression: Mathematical expression to evaluate (e.g., "15 * 23")

    Returns:
        Result as a string

    Raises:
        Exception: If expression is invalid or unsafe
    """
    try:
        # Restricted globals - only allow math operations
        allowed_names = {
            "abs": abs,
            "round": round,
            "min": min,
            "max": max,
            "sum": sum,
            "pow": pow,
            # Math module functions
            "sqrt": math.sqrt,
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "log": math.log,
            "pi": math.pi,
            "e": math.e,
        }

        # Evaluate with restricted globals (no access to builtins)
        result = eval(expression, {"__builtins__": {}}, allowed_names)
        return f"{expression} = {result}"

    except Exception as e:
        raise Exception(f"Failed to evaluate expression '{expression}': {str(e)}")


def save_note(content: str, filename: str = None) -> str:
    """
    Save a note to a text file (idempotent).

    Critical tool - failures are not tolerated.

    Idempotency:
        If filename is not provided, uses content hash to generate filename.
        This ensures retries with the same content don't create duplicates.
        Same content + no filename = same file every time = idempotent!

    Args:
        content: The note content to save
        filename: Optional filename (auto-generated from content hash if not provided)

    Returns:
        Success message with filename

    Raises:
        Exception: If file cannot be written
    """
    try:
        # Create notes directory if it doesn't exist
        notes_dir = "notes"
        os.makedirs(notes_dir, exist_ok=True)

        # Generate filename if not provided
        if filename is None:
            # Use content hash for idempotency
            # Same content = same hash = same filename = no duplicates on retry
            content_hash = hashlib.md5(content.encode()).hexdigest()[:12]
            timestamp = datetime.now().strftime("%Y%m%d")
            filename = f"note_{timestamp}_{content_hash}.txt"

        # Ensure filename has .txt extension
        if not filename.endswith(".txt"):
            filename = f"{filename}.txt"

        # Write the file (idempotent - same content overwrites)
        filepath = os.path.join(notes_dir, filename)

        # Check if file already exists with same content (idempotency check)
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                existing_content = f.read()
            if existing_content == content:
                # File already exists with exact same content
                # This is a retry - return success without rewriting
                return f"Note already exists at {filepath} (idempotent)"

        # Write the file
        with open(filepath, "w") as f:
            f.write(content)

        return f"Note saved to {filepath}"

    except Exception as e:
        raise Exception(f"Failed to save note: {str(e)}")


@circuit_breaker(
    name="weather",
    failure_threshold=5,
    recovery_timeout=60.0,
    expected_exception=Exception
)
def get_weather(location: str) -> str:
    """
    Get current weather information (mocked for demo).

    Protected by circuit breaker - will fail fast after 5 consecutive failures.

    Args:
        location: Location to get weather for

    Returns:
        Formatted weather information

    Raises:
        CircuitBreakerError: If circuit is open
    """
    # Mock implementation
    return f"""
Weather for {location}:
- Temperature: 72°F (22°C)
- Conditions: Partly cloudy
- Humidity: 65%
- Wind: 8 mph NW

(This is mock data for demonstration. In production, this would call a real weather API.)
""".strip()


# Tool schemas for Claude API
TOOLS = [
    {
        "name": "web_search",
        "description": "Search the web for information on a given query. Returns formatted search results with titles, snippets, and URLs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to look up on the web"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "calculator",
        "description": "Evaluate a mathematical expression. Supports basic operations (+, -, *, /, **) and common math functions (sqrt, sin, cos, etc.).",
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Mathematical expression to evaluate (e.g., '15 * 23' or 'sqrt(144)')"
                }
            },
            "required": ["expression"]
        }
    },
    {
        "name": "save_note",
        "description": "Save a note to a text file in the notes/ directory. Filename is auto-generated if not provided.",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The content of the note to save"
                },
                "filename": {
                    "type": "string",
                    "description": "Optional filename for the note (auto-generated if not provided)"
                }
            },
            "required": ["content"]
        }
    },
    {
        "name": "get_weather",
        "description": "Get current weather information for a specific location. Returns temperature, conditions, humidity, and wind information.",
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "The location to get weather for (e.g., 'Seattle', 'New York, NY')"
                }
            },
            "required": ["location"]
        }
    }
]


def execute_tool(tool_name: str, tool_input: Dict[str, Any]) -> str:
    """
    Execute a tool with graceful degradation.

    Critical tools (calculator, save_note) must succeed - failures propagate.
    Optional tools (web_search, get_weather) fail gracefully with degraded message.

    Args:
        tool_name: Name of the tool to execute
        tool_input: Dictionary of input parameters

    Returns:
        Tool execution result as a string

    Raises:
        Exception: If a critical tool fails
    """
    criticality = TOOL_CRITICALITY.get(tool_name, "critical")

    try:
        # Execute the tool
        if tool_name == "web_search":
            return web_search(**tool_input)
        elif tool_name == "calculator":
            return calculator(**tool_input)
        elif tool_name == "save_note":
            return save_note(**tool_input)
        elif tool_name == "get_weather":
            return get_weather(**tool_input)
        else:
            raise Exception(f"Unknown tool: {tool_name}")

    except CircuitBreakerError as e:
        # Circuit breaker is open
        if criticality == "critical":
            raise
        else:
            return (
                f"[Tool '{tool_name}' is temporarily unavailable - circuit breaker is open. "
                f"The service is recovering from failures. {str(e)}]"
            )

    except Exception as e:
        # Tool execution failed
        if criticality == "critical":
            # Critical tool failure - propagate the error
            raise
        else:
            # Optional tool failure - return degraded response
            return (
                f"[Tool '{tool_name}' is temporarily unavailable. "
                f"Reason: {str(e)}]"
            )
