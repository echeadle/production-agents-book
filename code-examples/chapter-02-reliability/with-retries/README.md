# Agent with Retry Logic

This is the reference agent enhanced with **retry logic** for resilience against transient failures.

## What's New

This version adds:

- **Exponential backoff**: Delays increase exponentially between retries (1s, 2s, 4s, 8s...)
- **Jitter**: Random variance in delays to prevent thundering herd
- **Selective retries**: Only retries on transient errors (rate limits, timeouts, connection errors)
- **Fail fast**: Non-retryable errors (auth failures, bad requests) fail immediately

## Resilience Improvements

### Before (Reference Agent)
- API rate limit → Immediate failure
- Network timeout → Immediate failure
- Temporary API outage → Immediate failure

### After (With Retries)
- API rate limit → Retry with backoff → Success (most cases)
- Network timeout → Retry immediately → Success (most cases)
- Temporary API outage → Retry with increasing delays → Success when service recovers

## Setup

1. **Install dependencies:**
   ```bash
   uv sync
   ```

2. **Configure API key:**
   ```bash
   cp .env.example .env
   # Edit .env and add your ANTHROPIC_API_KEY
   ```

3. **Run the agent:**
   ```bash
   uv run python agent.py
   ```

## Testing Retry Logic

To see retry logic in action, you can simulate failures:

### Simulate Rate Limit
Modify `agent.py` to temporarily inject a rate limit error:

```python
# In _call_llm method, before the actual API call:
import random
if random.random() < 0.5:  # 50% failure rate
    raise anthropic.RateLimitError("Simulated rate limit")
```

Run the agent and observe:
```
[Retry] Attempt 1/3 failed for _call_llm: Simulated rate limit
[Retry] Retrying in 1.23 seconds...
[Retry] Attempt 2/3 failed for _call_llm: Simulated rate limit
[Retry] Retrying in 2.47 seconds...
Success!
```

## Key Files

- `retry.py` - Retry decorator with exponential backoff and jitter
- `agent.py` - Agent with retry logic on LLM calls
- `config.py` - Configuration management
- `tools.py` - Tool implementations (unchanged from reference agent)

## Limitations

**What this version handles:**
- ✅ Transient API failures (rate limits, timeouts, temporary outages)
- ✅ Network issues
- ✅ Temporary service unavailability

**What this version doesn't handle yet:**
- ❌ No timeouts (operations can hang indefinitely)
- ❌ No circuit breakers (keeps retrying failing dependencies)
- ❌ No graceful degradation (tool failures still fail the request)
- ❌ No health checks (can't be monitored by orchestrators)

These will be added in subsequent versions.

## Next Steps

See:
- `../with-circuit-breaker/` - Adds circuit breakers
- `../with-timeouts/` - Adds comprehensive timeout handling
- `../complete/` - All resilience patterns together

## Production Readiness

**Added:**
- ✅ Retry logic with exponential backoff
- ✅ Jitter to prevent thundering herd
- ✅ Selective retry on transient errors

**Still needed for production:**
- ⏳ Timeouts (next version)
- ⏳ Circuit breakers (next version)
- ⏳ Graceful degradation (next version)
- ⏳ Health checks (next version)
- ⏳ Structured logging (Chapter 3)
- ⏳ Metrics (Chapter 3)
- ⏳ Security hardening (Chapter 4)
