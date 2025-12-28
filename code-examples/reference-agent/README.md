# Reference Agent

A simple task automation agent that serves as the baseline for **Production AI Agent Systems**.

## Overview

This is the reference agent introduced in **Chapter 1: The Production Mindset**. It's a functional agent that can:

- 🔍 **Search the web** for information
- 🧮 **Perform calculations** (basic arithmetic and math functions)
- 📝 **Save notes** to text files
- 🌤️ **Get weather** information for locations

### Current State: Functional, Not Production-Ready

This agent works well for demonstration and learning, but it's **not yet ready for production**. Throughout the book, we'll progressively harden it by adding:

- ✅ Retry logic and exponential backoff (Chapter 2)
- ✅ Circuit breakers for resilience (Chapter 2)
- ✅ Comprehensive error handling (Chapter 2)
- ✅ Structured logging (Chapter 3)
- ✅ Metrics collection with Prometheus (Chapter 3)
- ✅ Distributed tracing with OpenTelemetry (Chapter 3)
- ✅ Input validation and sanitization (Chapter 4)
- ✅ Security and rate limiting (Chapter 4)
- ✅ Cost tracking and optimization (Chapter 5)
- ✅ Horizontal scaling patterns (Chapter 6)
- ✅ Performance optimizations (Chapter 7)
- ✅ Comprehensive testing (Chapter 8)
- ✅ Docker and Kubernetes deployment (Chapter 9)
- ✅ Incident response procedures (Chapter 10)

By the end of the book, this ~200 line agent becomes a production-grade system.

## Why uv and python-dotenv?

This project uses specific tools that represent **production best practices**, not just convenience choices.

### uv: Modern Package Management

We use **`uv`** instead of `pip` because:

- **⚡ Speed**: 10-100x faster than pip (written in Rust)
- **🔒 Reliability**: Deterministic installs with lockfile support
- **🎯 Better Resolution**: Smarter dependency conflict resolution
- **🏭 Production Ready**: Built for production workflows

**Why this matters**: In production, you need identical environments across development, staging, and production. `uv` guarantees this with its lockfile mechanism. When your CI/CD pipeline installs dependencies, you want it fast and deterministic—not "works on my machine" surprises.

**Install uv:**
```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or via pip
pip install uv
```

### python-dotenv: Security First

We use **`python-dotenv`** to manage API keys securely. Here's why this matters:

**The Problem**: Hardcoding API keys in code is a security disaster waiting to happen:
```python
# ❌ NEVER DO THIS
api_key = "sk-ant-api03-your-actual-key"  # Will be leaked when committed to git
```

**The Solution**: The `.env` pattern:

1. **`.env.example`** (committed to git) - Template with placeholders
   ```
   ANTHROPIC_API_KEY=your-api-key-here
   ```

2. **`.env`** (in `.gitignore`, local only) - Your real secrets
   ```
   ANTHROPIC_API_KEY=sk-ant-api03-actual-secret-key
   ```

3. **`config.py`** - Loads secrets at runtime
   ```python
   from dotenv import load_dotenv
   load_dotenv()  # Reads .env
   api_key = os.getenv("ANTHROPIC_API_KEY")
   ```

**Why this matters**:
- ✅ Secrets never committed to version control
- ✅ Different keys for dev/staging/production
- ✅ Easy to rotate keys without changing code
- ✅ GitHub automatically scans for leaked keys and revokes them

**Real-world impact**: If you accidentally commit a real API key to a public repo, GitHub will:
1. Detect it within minutes
2. Notify Anthropic
3. Anthropic will **revoke your key**
4. You'll get a security alert

Don't learn this the hard way—use `python-dotenv` from day one.

## Setup

### Prerequisites

- Python 3.10 or higher
- An Anthropic API key ([Get one here](https://console.anthropic.com/))
- `uv` package manager ([Install uv](https://github.com/astral-sh/uv))

### Installation

1. **Clone or navigate to this directory**

2. **Create a `.env` file from the template:**

```bash
cp .env.example .env
```

3. **Edit `.env` and add your Anthropic API key:**

```bash
ANTHROPIC_API_KEY=your-actual-api-key-here
```

4. **Install dependencies with uv:**

```bash
uv sync
```

This will install:
- `anthropic` - Claude API client
- `python-dotenv` - Environment variable management
- `pytest` (dev) - Testing framework

## Usage

### Interactive Mode

Run the agent in interactive mode:

```bash
uv run python agent.py
```

You'll see:

```
============================================================
Reference Agent - Task Automation Assistant
============================================================

I can help you with:
  • Web searches
  • Mathematical calculations
  • Saving notes
  • Weather information

Type 'quit' or 'exit' to end the session.
Type 'reset' to start a new conversation.
============================================================

You:
```

### Example Interactions

**Web Search:**
```
You: Search for information about Python programming
Agent: [Uses web_search tool and summarizes results]
```

**Calculator:**
```
You: What is 2 raised to the power of 10?
Agent: [Uses calculator tool] 2 ** 10 = 1024
```

**Save Note:**
```
You: Save a note that says "Remember to review Chapter 2"
Agent: [Uses save_note tool] Note saved to notes/note_20250128_143022.txt
```

**Weather:**
```
You: What's the weather in San Francisco?
Agent: [Uses get_weather tool] Weather for San Francisco: Temperature: 65°F (18.3°C)...
```

### Programmatic Usage

You can also import and use the agent in your own code:

```python
from agent import Agent
from config import AgentConfig

# Initialize with default config (loads from .env)
agent = Agent()

# Or with custom config
config = AgentConfig(
    api_key="your-api-key",
    model="claude-sonnet-4-20250514",
    max_tokens=4096
)
agent = Agent(config)

# Process a request
response = agent.process("What is 15 * 23?")
print(response)

# Reset conversation history
agent.reset_conversation()
```

## Running Tests

Run the test suite:

```bash
uv run pytest
```

Run with coverage:

```bash
uv run pytest --cov=. --cov-report=term-missing
```

Run specific test file:

```bash
uv run pytest test_agent.py -v
```

## Project Structure

```
reference-agent/
├── agent.py              # Main agent implementation
├── tools.py              # Tool definitions and implementations
├── config.py             # Configuration management
├── test_agent.py         # Test suite
├── .env.example          # Environment template
├── .env                  # Your secrets (not in git)
├── pyproject.toml        # Dependencies and project metadata
├── README.md             # This file
└── notes/                # Created when you save notes
```

## What's Missing (For Now)

This reference agent is intentionally simple. Here's what we'll add in later chapters:

### Reliability (Chapter 2)
- Retry logic with exponential backoff
- Circuit breakers for external dependencies
- Timeout handling
- Graceful degradation

### Observability (Chapter 3)
- Structured logging with `structlog`
- Prometheus metrics
- OpenTelemetry distributed tracing
- Correlation IDs

### Security (Chapter 4)
- Input validation
- Prompt injection defense
- Output filtering
- Rate limiting
- Audit logging

### Cost Optimization (Chapter 5)
- Token usage tracking
- Prompt caching
- Model routing
- Budget enforcement

### Scaling (Chapter 6)
- Stateless design
- Queue-based architecture
- Worker pools
- Auto-scaling

### Performance (Chapter 7)
- Async/await patterns
- Connection pooling
- Multi-layer caching
- Streaming responses

### And More!
- Comprehensive testing (Chapter 8)
- Docker and Kubernetes (Chapter 9)
- Incident response (Chapter 10)
- Multi-region deployment (Chapter 11)
- Platform engineering (Chapter 12)

## Production Concerns

### Current Limitations

1. **No retry logic** - API failures will fail the request
2. **Basic error handling** - Errors are caught but not handled gracefully
3. **No monitoring** - No metrics, logs, or traces
4. **No security** - No input validation, rate limiting, or auth
5. **No cost tracking** - No visibility into token usage or costs
6. **Single-threaded** - Can't handle concurrent requests
7. **In-memory state** - Conversation history lost on restart
8. **No timeouts** - Operations can hang indefinitely
9. **Print debugging** - Not suitable for production logging
10. **No health checks** - Can't be monitored by orchestrators

These are all addressed in subsequent chapters!

## Contributing

This is example code for the book. If you find issues or have suggestions, please open an issue on the book's repository.

## License

[To be determined]

## Learn More

This reference agent is from **Production AI Agent Systems** by [Author Name].

For more information, see:
- Chapter 1: The Production Mindset
- Book repository: [URL]
- Author website: [URL]
