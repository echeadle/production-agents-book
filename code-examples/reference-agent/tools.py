"""
Tool definitions for the reference agent.

This module defines the tools that the agent can use:
- web_search: Search the web for information
- calculator: Perform mathematical calculations
- save_note: Save a note to a file
- get_weather: Get current weather for a location

Chapter 1: The Production Mindset
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


def web_search(query: str) -> str:
    """
    Simulate a web search (simplified for demonstration).

    In production, this would call a real search API (Google, Bing, etc.).
    For now, we'll return a mock response.

    Args:
        query: The search query

    Returns:
        Search results as a formatted string
    """
    # Mock search results
    results = {
        "query": query,
        "results": [
            {
                "title": f"Result 1 for '{query}'",
                "snippet": "This is a mock search result. In production, this would be real data from a search API.",
                "url": "https://example.com/result1"
            },
            {
                "title": f"Result 2 for '{query}'",
                "snippet": "Another mock result demonstrating the search functionality.",
                "url": "https://example.com/result2"
            }
        ]
    }

    # Format results
    output = f"Search results for '{query}':\n\n"
    for i, result in enumerate(results["results"], 1):
        output += f"{i}. {result['title']}\n"
        output += f"   {result['snippet']}\n"
        output += f"   {result['url']}\n\n"

    return output


def calculator(expression: str) -> str:
    """
    Evaluate a mathematical expression.

    Args:
        expression: Mathematical expression to evaluate (e.g., "2 + 2", "10 * 5")

    Returns:
        The result of the calculation

    Raises:
        ValueError: If the expression is invalid
    """
    try:
        # Use eval with restricted globals for safety
        # Note: In production, use a proper math parser like py-expression-eval
        allowed_names = {
            "abs": abs,
            "round": round,
            "min": min,
            "max": max,
            "sum": sum,
            "pow": pow,
        }

        result = eval(expression, {"__builtins__": {}}, allowed_names)
        return f"{expression} = {result}"

    except Exception as e:
        raise ValueError(f"Invalid expression: {expression}. Error: {str(e)}")


def save_note(content: str, filename: str = None) -> str:
    """
    Save a note to a file.

    Args:
        content: The note content to save
        filename: Optional filename (defaults to timestamp-based name)

    Returns:
        Confirmation message with the filename
    """
    # Create notes directory if it doesn't exist
    notes_dir = Path("notes")
    notes_dir.mkdir(exist_ok=True)

    # Generate filename if not provided
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"note_{timestamp}.txt"

    # Ensure .txt extension
    if not filename.endswith(".txt"):
        filename += ".txt"

    # Save the note
    filepath = notes_dir / filename
    filepath.write_text(content)

    return f"Note saved to {filepath}"


def get_weather(location: str) -> str:
    """
    Get current weather for a location (simplified/mocked).

    In production, this would call a real weather API (OpenWeatherMap, Weather.gov, etc.).

    Args:
        location: City name or location

    Returns:
        Weather information as a formatted string
    """
    # Mock weather data
    import random

    conditions = ["Sunny", "Partly Cloudy", "Cloudy", "Rainy", "Stormy"]
    temp_f = random.randint(45, 85)
    temp_c = round((temp_f - 32) * 5/9, 1)
    condition = random.choice(conditions)
    humidity = random.randint(30, 90)

    weather_data = {
        "location": location,
        "temperature": {
            "fahrenheit": temp_f,
            "celsius": temp_c
        },
        "condition": condition,
        "humidity": humidity
    }

    # Format output
    output = f"Weather for {location}:\n"
    output += f"Temperature: {temp_f}°F ({temp_c}°C)\n"
    output += f"Condition: {condition}\n"
    output += f"Humidity: {humidity}%\n"

    return output


# Tool definitions for Claude API
TOOLS = [
    {
        "name": "web_search",
        "description": "Search the web for information on a given query. Use this when you need current information or facts from the internet.",
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
        "name": "calculator",
        "description": "Evaluate a mathematical expression. Supports basic arithmetic operations (+, -, *, /), exponents (**), and functions like abs, round, min, max.",
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "The mathematical expression to evaluate (e.g., '2 + 2', '10 * 5', 'pow(2, 8)')"
                }
            },
            "required": ["expression"]
        }
    },
    {
        "name": "save_note",
        "description": "Save a note to a text file. The note will be saved in the 'notes' directory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The content of the note to save"
                },
                "filename": {
                    "type": "string",
                    "description": "Optional filename for the note (will auto-generate if not provided)"
                }
            },
            "required": ["content"]
        }
    },
    {
        "name": "get_weather",
        "description": "Get the current weather for a specific location.",
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "The city or location to get weather for (e.g., 'San Francisco', 'New York')"
                }
            },
            "required": ["location"]
        }
    }
]


# Tool function mapping
TOOL_FUNCTIONS = {
    "web_search": web_search,
    "calculator": calculator,
    "save_note": save_note,
    "get_weather": get_weather,
}


def execute_tool(tool_name: str, tool_input: Dict[str, Any]) -> str:
    """
    Execute a tool by name with the given input.

    Args:
        tool_name: Name of the tool to execute
        tool_input: Dictionary of tool parameters

    Returns:
        Tool execution result as a string

    Raises:
        ValueError: If tool_name is not recognized
    """
    if tool_name not in TOOL_FUNCTIONS:
        raise ValueError(f"Unknown tool: {tool_name}")

    tool_func = TOOL_FUNCTIONS[tool_name]

    try:
        result = tool_func(**tool_input)
        return result
    except Exception as e:
        return f"Error executing {tool_name}: {str(e)}"
