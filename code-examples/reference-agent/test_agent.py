"""
Basic tests for the reference agent.

These are simple tests to verify basic functionality. More comprehensive
testing strategies will be covered in Chapter 8: Testing Production Systems.

Chapter 1: The Production Mindset
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from agent import Agent
from config import AgentConfig
from tools import (
    web_search,
    calculator,
    save_note,
    get_weather,
    execute_tool,
    TOOL_FUNCTIONS
)


# ===== Configuration Tests =====

def test_agent_config_creation():
    """Test that AgentConfig can be created with defaults."""
    config = AgentConfig(api_key="test-key")
    assert config.api_key == "test-key"
    assert config.model == "claude-sonnet-4-20250514"
    assert config.max_tokens == 4096
    assert config.max_iterations == 10


def test_agent_config_from_env():
    """Test configuration loading from environment variables."""
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "env-test-key"}):
        config = AgentConfig.from_env()
        assert config.api_key == "env-test-key"


def test_agent_config_missing_api_key():
    """Test that missing API key raises ValueError."""
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY not found"):
            AgentConfig.from_env()


# ===== Tool Tests =====

def test_web_search():
    """Test that web_search returns formatted results."""
    result = web_search("Python programming")
    assert "Search results for 'Python programming'" in result
    assert "Result 1" in result
    assert "Result 2" in result


def test_calculator_basic():
    """Test basic calculator operations."""
    assert "2 + 2 = 4" in calculator("2 + 2")
    assert "10 * 5 = 50" in calculator("10 * 5")
    assert "100 / 4 = 25" in calculator("100 / 4")


def test_calculator_invalid_expression():
    """Test that invalid expressions raise ValueError."""
    with pytest.raises(ValueError, match="Invalid expression"):
        calculator("invalid expression")


def test_save_note(tmp_path):
    """Test saving a note to a file."""
    # Change to tmp directory for test
    import os
    original_dir = os.getcwd()
    os.chdir(tmp_path)

    try:
        result = save_note("Test note content", "test_note")
        assert "Note saved to" in result
        assert "test_note.txt" in result

        # Verify file was created
        note_file = Path("notes/test_note.txt")
        assert note_file.exists()
        assert note_file.read_text() == "Test note content"

    finally:
        os.chdir(original_dir)


def test_get_weather():
    """Test that get_weather returns formatted weather data."""
    result = get_weather("San Francisco")
    assert "Weather for San Francisco" in result
    assert "Temperature:" in result
    assert "Condition:" in result
    assert "Humidity:" in result


def test_execute_tool():
    """Test tool execution by name."""
    # Test web_search
    result = execute_tool("web_search", {"query": "test"})
    assert "Search results" in result

    # Test calculator
    result = execute_tool("calculator", {"expression": "5 + 5"})
    assert "10" in result


def test_execute_tool_unknown():
    """Test that unknown tool raises ValueError."""
    with pytest.raises(ValueError, match="Unknown tool"):
        execute_tool("unknown_tool", {})


def test_all_tools_registered():
    """Test that all tool functions are registered."""
    assert "web_search" in TOOL_FUNCTIONS
    assert "calculator" in TOOL_FUNCTIONS
    assert "save_note" in TOOL_FUNCTIONS
    assert "get_weather" in TOOL_FUNCTIONS


# ===== Agent Tests =====

def test_agent_initialization():
    """Test that Agent can be initialized with config."""
    config = AgentConfig(api_key="test-key")
    agent = Agent(config)
    assert agent.config == config
    assert len(agent.conversation_history) == 0


def test_agent_reset_conversation():
    """Test that conversation history can be reset."""
    config = AgentConfig(api_key="test-key")
    agent = Agent(config)

    # Add some conversation history
    agent.conversation_history.append({"role": "user", "content": "test"})
    assert len(agent.conversation_history) == 1

    # Reset
    agent.reset_conversation()
    assert len(agent.conversation_history) == 0


@patch("agent.anthropic.Anthropic")
def test_agent_process_simple_response(mock_anthropic_class):
    """Test agent processing a simple response (no tools)."""
    # Setup mock
    mock_client = MagicMock()
    mock_anthropic_class.return_value = mock_client

    mock_response = MagicMock()
    mock_response.stop_reason = "end_turn"
    mock_content = MagicMock()
    mock_content.text = "Hello! I'm ready to help."
    mock_response.content = [mock_content]

    mock_client.messages.create.return_value = mock_response

    # Test
    config = AgentConfig(api_key="test-key")
    agent = Agent(config)
    response = agent.process("Hello")

    assert response == "Hello! I'm ready to help."
    assert len(agent.conversation_history) == 2  # user + assistant


@patch("agent.anthropic.Anthropic")
@patch("agent.execute_tool")
def test_agent_process_with_tool_use(mock_execute_tool, mock_anthropic_class):
    """Test agent processing with tool use."""
    # Setup mocks
    mock_client = MagicMock()
    mock_anthropic_class.return_value = mock_client

    # First response: tool use
    mock_tool_use = MagicMock()
    mock_tool_use.type = "tool_use"
    mock_tool_use.name = "calculator"
    mock_tool_use.input = {"expression": "2 + 2"}
    mock_tool_use.id = "tool_123"

    mock_response_1 = MagicMock()
    mock_response_1.stop_reason = "tool_use"
    mock_response_1.content = [mock_tool_use]

    # Second response: final answer
    mock_text = MagicMock()
    mock_text.text = "The result is 4"

    mock_response_2 = MagicMock()
    mock_response_2.stop_reason = "end_turn"
    mock_response_2.content = [mock_text]

    mock_client.messages.create.side_effect = [mock_response_1, mock_response_2]
    mock_execute_tool.return_value = "2 + 2 = 4"

    # Test
    config = AgentConfig(api_key="test-key")
    agent = Agent(config)
    response = agent.process("What is 2 + 2?")

    assert response == "The result is 4"
    assert mock_execute_tool.called


# ===== Integration Tests =====

def test_tool_definitions_match_functions():
    """Test that all defined tools have corresponding functions."""
    from tools import TOOLS, TOOL_FUNCTIONS

    for tool in TOOLS:
        tool_name = tool["name"]
        assert tool_name in TOOL_FUNCTIONS, f"Tool {tool_name} has no function"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
