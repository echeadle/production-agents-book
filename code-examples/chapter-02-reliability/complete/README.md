# Production-Ready Agent - Complete

This is the **complete production-ready version** of the task automation agent with all reliability patterns from Chapter 2 integrated.

## ⚠️ Platform Requirements

**Synchronous version** (`agent.py`):
- **Unix/Linux only** (uses signal.SIGALRM for timeouts)
- Python 3.12+
- Main thread only (signal limitations)

**Asynchronous version** (`agent_async.py`) - **RECOMMENDED FOR PRODUCTION**:
- ✅ **Cross-platform** (Windows, Linux, macOS)
- ✅ **Thread-safe**
- ✅ **Reentrant timeouts**
- Python 3.11+ required

**Use the async version for production deployments.**

## Features

This version includes:

✅ **Retry Logic** (with structured logging)
- Exponential backoff (1s, 2s, 4s, 8s...)
- Jitter to prevent thundering herd
- Selective retries on transient errors only
- Structured logging with context

✅ **Thread-Safe Circuit Breakers**
- Protects web_search and get_weather APIs
- Thread-safe with proper locking
- Fails fast after 5 consecutive failures
- Auto-recovery testing after 60 seconds (configurable)
- Configurable success threshold

✅ **Comprehensive Timeouts**
- LLM timeout: 30 seconds per API call
- Tool timeout: 10 seconds per tool execution
- Total timeout: 120 seconds per user request
- Platform warnings and async alternative provided

✅ **Graceful Degradation**
- Critical tools (calculator, save_note) must succeed
- Optional tools (web_search, get_weather) fail gracefully
- Partial success > complete failure

✅ **Cost-Effective Health Checks**
- Liveness probe: `/health/live`
- Readiness probe: `/health/ready` (no billable API calls!)
- Kubernetes-ready

✅ **Structured Logging**
- Uses Python `logging` module instead of print()
- Structured context with `extra` fields
- Configurable log levels
- Production-ready observability foundation

## Setup

### 1. Install Dependencies

```bash
uv sync
```

### 2. Configure API Key

```bash
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### 3. Run the Agent

```bash
uv run python agent.py
```

### 4. Run Health Check Server (Optional)

In a separate terminal:

```bash
uv run python health.py
```

Then test:

```bash
# Test liveness
curl http://localhost:8080/health/live

# Test readiness
curl http://localhost:8080/health/ready
```

## Example Usage

```
You: What is 15 multiplied by 23?

Agent: Using tool: calculator
Agent: Tool input: {'expression': '15 * 23'}
Agent: Tool result: 15 * 23 = 345

Agent: 15 multiplied by 23 equals 345.
```

## Testing Resilience Patterns

### Test Retry Logic

Modify `agent.py` to inject failures:

```python
# In _call_llm, before the API call:
import random
if random.random() < 0.3:  # 30% failure rate
    raise anthropic.RateLimitError("Simulated rate limit")
```

You'll see:
```
[Retry] Attempt 1/3 failed for _call_llm: Simulated rate limit
[Retry] Retrying in 1.23 seconds...
Success!
```

### Test Circuit Breaker

Modify `tools.py` to make web_search fail:

```python
def web_search(query: str) -> str:
    raise Exception("Service down!")
```

Run 10 searches. After 5 failures, the circuit trips:

```
[CircuitBreaker:web_search] Failure 1/5: Service down!
[CircuitBreaker:web_search] Failure 2/5: Service down!
...
[CircuitBreaker:web_search] OPEN after 5 failures. Will retry in 60s
```

Next request fails immediately:
```
[Tool 'web_search' is temporarily unavailable - circuit breaker is open...]
```

### Test Graceful Degradation

Ask: "What's the weather in Seattle and what's 15 * 23?"

If weather API fails (circuit open), you get:

```
I couldn't fetch the weather for Seattle (weather service is temporarily
unavailable), but I can tell you that 15 * 23 = 345.
```

The calculator works even though weather failed (graceful degradation).

### Test Timeouts

Modify a tool to sleep:

```python
def save_note(content: str, filename: str = None) -> str:
    import time
    time.sleep(15)  # Exceeds 10s tool timeout
    ...
```

You'll see:
```
[Agent] Tool timeout: Operation exceeded 10.0 second timeout
```

## Architecture

### Retry Flow

```
User Request
    ↓
Call LLM (with retry)
    ├─ Success → Continue
    ├─ Rate limit → Retry with backoff
    ├─ Timeout → Retry with backoff
    ├─ Network error → Retry with backoff
    └─ Auth error → Fail immediately (don't retry)
```

### Circuit Breaker States

```
CLOSED (normal)
    ↓ (5 failures)
OPEN (fail fast)
    ↓ (60s timeout)
HALF_OPEN (testing)
    ├─ Success → CLOSED
    └─ Failure → OPEN
```

### Timeout Hierarchy

```
Total Request Timeout (120s)
├── LLM Call Timeout (30s)
│   └── API-level timeout
├── Tool Execution Timeout (10s)
│   └── Signal-based timeout
└── (Multiple iterations possible)
```

## Health Checks

### Liveness Probe

- **Endpoint**: `GET /health/live`
- **Purpose**: Is the process alive?
- **Check**: Process can respond to HTTP
- **Kubernetes action**: Restart if fails

### Readiness Probe

- **Endpoint**: `GET /health/ready`
- **Purpose**: Ready to handle traffic?
- **Checks**:
  - Anthropic API reachable
  - Disk space available
  - Notes directory writable
- **Kubernetes action**: Remove from load balancer if fails

### Kubernetes Example

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: task-agent
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: agent
        image: task-agent:v1
        ports:
        - containerPort: 8080

        livenessProbe:
          httpGet:
            path: /health/live
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 30
          timeoutSeconds: 5
          failureThreshold: 3

        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 2
```

## Key Files

| File | Purpose |
|------|---------|
| `agent.py` | Sync agent (Unix/Linux only) |
| `agent_async.py` | **Async agent (recommended for production)** |
| `retry.py` | Thread-safe retry decorator with structured logging |
| `circuit_breaker.py` | Thread-safe circuit breaker implementation |
| `tools.py` | Tools with circuit breakers and graceful degradation |
| `config.py` | Configuration with timeout settings |
| `health.py` | Cost-effective health check endpoints |

## Production Improvements

### Fixed Critical Issues ✅

1. **Thread-Safe Circuit Breaker** ✅
   - Added `threading.Lock()` to protect shared state
   - Function execution happens outside lock (no blocking during I/O)
   - Configurable success threshold for HALF_OPEN → CLOSED transition
   - File: `circuit_breaker.py`

2. **Timeout Platform Warnings** ✅
   - Signal-based timeout clearly documented with limitations
   - Async alternative provided (`agent_async.py`)
   - Platform check prevents crashes on Windows
   - Files: `agent.py`, `agent_async.py`

3. **Structured Logging** ✅
   - Replaced all `print()` with `logging` module
   - Added structured context via `extra` fields
   - Proper log levels (DEBUG, INFO, WARNING, ERROR)
   - Ready for log aggregation tools
   - Files: `retry.py`, `circuit_breaker.py`, `agent.py`

4. **Cost-Effective Health Checks** ✅
   - Removed billable API call (was 260k+/month!)
   - Now validates API key format only
   - Still catches configuration errors
   - Deep validation via actual agent metrics instead
   - File: `health.py`

### Fixed Major Issues ✅

5. **Idempotent save_note Tool** ✅
   - Uses content hash for filename generation
   - Same content = same hash = same file = no duplicates
   - Retries are now safe and won't create duplicates
   - File: `tools.py`

6. **Health Check HTTP Status** ✅
   - Returns 503 (not 200) when degraded
   - Kubernetes properly removes degraded pods from load balancer
   - File: `health.py`

7. **Rate Limiting Implementation** ✅
   - Token bucket algorithm for client-side rate limiting
   - Thread-safe implementation
   - Prevents thundering herd with retries
   - Works with retries and circuit breakers
   - File: `rate_limiter.py`

8. **Redis-Backed Circuit Breaker** ✅
   - Shared state across all processes/pods
   - Consistent behavior in distributed deployments
   - Lua scripts for atomic operations
   - File: `circuit_breaker_redis.py`

## Production Readiness

**Reliability: ✅ Complete**
- ✅ Retry logic with exponential backoff
- ✅ Circuit breakers for dependencies
- ✅ Comprehensive timeouts
- ✅ Graceful degradation
- ✅ Health checks (liveness, readiness)

**Still Needed:**
- ⏳ Structured logging (Chapter 3)
- ⏳ Metrics collection (Chapter 3)
- ⏳ Distributed tracing (Chapter 3)
- ⏳ Security hardening (Chapter 4)
- ⏳ Cost tracking (Chapter 5)
- ⏳ Horizontal scaling (Chapter 6)

## What's Next

This agent is **production-ready from a reliability perspective**. It handles:
- Transient failures
- Cascading failures
- Resource exhaustion
- Timeout scenarios
- Partial failures

But production needs more than reliability. Next chapters add:
- **Chapter 3**: Observability (logs, metrics, traces)
- **Chapter 4**: Security (input validation, prompt injection defense)
- **Chapter 5**: Cost optimization (token tracking, budgets)
- **Chapter 6**: Scaling (queue-based architecture, auto-scaling)

## Troubleshooting

### Circuit breaker stays open

Check recovery timeout (default 60s). Wait for circuit to enter HALF_OPEN, then send a request.

### Timeouts too aggressive

Adjust in `.env`:
```
LLM_TIMEOUT=60.0
TOOL_TIMEOUT=30.0
TOTAL_TIMEOUT=300.0
```

### Retries exhausted

Check if error is actually transient. Non-retryable errors (auth, validation) fail immediately.

### Health check failing

Run `curl http://localhost:8080/health/ready` to see which check is failing. Common issues:
- Invalid API key
- Low disk space
- Can't create notes/ directory

---

**This agent is ready for production deployment** (from a reliability perspective). Deploy with confidence!
