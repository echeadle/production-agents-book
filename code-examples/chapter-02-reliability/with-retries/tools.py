"""
Tool definitions for the task automation agent.

Each tool is implemented as a Python function and has a corresponding
schema definition for the Claude API.
"""

import os
import math
from datetime import datetime
from typing import Any, Dict


def web_search(query: str) -> str:
    """
    Search the web for information (mocked for demo).

    In production, this would call a real search API like Google, Bing, or Brave.

    Args:
        query: The search query

    Returns:
        Formatted search results as a string
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

    Uses Python's eval with restricted globals for basic safety.
    In production, use a proper math expression parser.

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
    Save a note to a text file.

    Args:
        content: The note content to save
        filename: Optional filename (auto-generated if not provided)

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
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"note_{timestamp}.txt"

        # Ensure filename has .txt extension
        if not filename.endswith(".txt"):
            filename = f"{filename}.txt"

        # Write the file
        filepath = os.path.join(notes_dir, filename)
        with open(filepath, "w") as f:
            f.write(content)

        return f"Note saved to {filepath}"

    except Exception as e:
        raise Exception(f"Failed to save note: {str(e)}")


def get_weather(location: str) -> str:
    """
    Get current weather information (mocked for demo).

    In production, this would call a real weather API like OpenWeatherMap.

    Args:
        location: Location to get weather for

    Returns:
        Formatted weather information

    Raises:
        Exception: If weather data cannot be retrieved
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
    Execute a tool by name with the given input.

    Args:
        tool_name: Name of the tool to execute
        tool_input: Dictionary of input parameters

    Returns:
        Tool execution result as a string

    Raises:
        Exception: If tool execution fails
    """
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
