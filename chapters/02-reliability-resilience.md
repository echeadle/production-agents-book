# Chapter 2: Reliability and Resilience

## Introduction: The 3 AM Page

It's 3:47 AM when your phone buzzes. You're on-call this week. The alert is simple but terrifying:

```
[CRITICAL] Agent response rate dropped to 23%
Service: task-automation-agent
Duration: 12 minutes
Impact: 2,400+ failed user requests
```

You stumble to your laptop, eyes barely open. The logs tell a brutal story:

```
ERROR: Anthropic API rate limit exceeded (429)
ERROR: Anthropic API rate limit exceeded (429)
ERROR: Anthropic API rate limit exceeded (429)
... 2,400 more lines ...
```

The Anthropic API started rate limiting you at 3:35 AM. Your agent tried each request once, failed immediately, and returned errors to users. No retries. No backoff. No circuit breaker to stop the bleeding.

**Every single request failed for 12 minutes straight.**

Here's what makes it worse: the rate limit was temporary. The API recovered at 3:42 AM. But your agent kept failing because it cached the error state. A simple retry with exponential backoff would have recovered automatically in seconds. Instead, you had to manually restart the service at 4:03 AM.

**Cost of this outage:**
- 2,400 angry users
- 12 support tickets filed
- 1 very tired engineer
- Damage to user trust: immeasurable

**Root cause:** No retry logic.

This is why reliability matters. This is why we need resilience patterns. And this is exactly what we're fixing in this chapter.

## The Reality of Distributed Systems

Here's a truth that took me years to accept: **everything fails, all the time.**

Your agent runs in a distributed system. It depends on:
- The Anthropic API (which has rate limits, outages, and transient errors)
- Your database (which has connection limits and network issues)
- External tools (web search, weather APIs, etc.)
- The network (which drops packets, times out, and goes down)
- Your own infrastructure (which runs out of memory, CPU, and disk)

Each of these fails regularly. Not occasionally—**regularly**. The Anthropic API might:
- Rate limit you during peak hours
- Return 500 errors during a deployment
- Time out on slow requests
- Drop connections unexpectedly

And that's a **well-engineered, production service from a major company**. Imagine the external tools your agent calls: weather APIs, web search, custom integrations. They fail even more frequently.

**The question isn't "will it fail?" It's "how does it fail?"**

A production agent must assume failure is the default state and build resilience to handle it gracefully.

## Failure Modes in AI Agents

Before we fix anything, let's understand exactly how agents fail in production.

### 1. Transient Failures (Temporary)

These failures resolve themselves if you just try again:

**API rate limits**: You hit the Anthropic API too fast, get a 429 response. Wait a few seconds, try again—it works.

**Network timeouts**: A packet gets dropped. Retry immediately—it works.

**Temporary service unavailability**: The API is deploying a new version, returns 503. Wait 10 seconds, retry—it works.

**Database connection pool exhausted**: All connections are in use. Wait for one to free up, retry—it works.

**Solution**: Retry with backoff. Don't fail the user's request just because a temporary issue occurred.

### 2. Persistent Failures (Permanent)

These failures won't resolve no matter how many times you retry:

**Invalid API key**: Your authentication is wrong. Retrying won't help.

**Malformed request**: You sent bad data to the API. Retrying the same request will fail again.

**Resource not found**: You're trying to access something that doesn't exist.

**Quota exceeded**: You've hit your monthly limit. No amount of retrying will help.

**Solution**: Don't retry these. Fail fast, return a clear error to the user, and log for investigation.

### 3. Cascading Failures (Amplified)

These failures start small but get worse as your system tries to cope:

**Thundering herd**: One service goes down. All your workers retry simultaneously, overwhelming it when it comes back up.

**Resource exhaustion**: Slow responses cause request queue buildup. Memory usage grows. Eventually, your service crashes.

**Circuit cascade**: Service A depends on B. B goes down. A's retries make B worse. A falls over too. Now nothing works.

**Solution**: Circuit breakers, rate limiting, backpressure, and graceful degradation.

### 4. Silent Failures (Undetected)

These failures happen without you noticing until it's too late:

**Degraded performance**: Response times slowly increase from 500ms to 5 seconds. Users are unhappy, but nothing "failed."

**Incorrect results**: The LLM starts hallucinating more frequently. No errors, just wrong answers.

**Memory leaks**: Your agent slowly consumes more memory over days. Eventually crashes.

**Cost spirals**: A prompt change increases token usage 3x. Your bill explodes, but the agent "works."

**Solution**: Comprehensive monitoring, metrics, alerts, and SLOs (we'll cover this in Chapter 3).

## Resilience Patterns for Production Agents

Now let's build the resilience patterns that prevent these failure modes. We'll add them to the reference agent progressively.

### Pattern 1: Retry Logic with Exponential Backoff

**The Problem**: Transient failures (rate limits, network blips) cause user-facing errors even though the underlying service is fine.

**The Solution**: Retry failed requests with increasing delays between attempts.

#### Why Exponential Backoff?

Imagine your API is overloaded and rate limiting you. If you retry immediately, you'll hit the limit again. If everyone retries at the same time, you create a **thundering herd** that makes the problem worse.

**Exponential backoff** solves this:
- **First retry**: Wait 1 second
- **Second retry**: Wait 2 seconds
- **Third retry**: Wait 4 seconds
- **Fourth retry**: Wait 8 seconds

Each failure increases the delay exponentially. This gives the service time to recover and spreads out retry attempts.

#### Adding Jitter

But there's still a problem: if 1,000 clients all failed at the same time, they'll all retry at 1 second, 2 seconds, 4 seconds, etc. **They're still synchronized.**

**Jitter** adds randomness to break the synchronization:
- Instead of waiting exactly 2 seconds, wait 1.5-2.5 seconds
- Instead of exactly 4 seconds, wait 3-5 seconds

Now retries are distributed over time instead of clustered.

#### Implementation

Let's add retry logic to the reference agent. We'll create a reusable retry decorator:

```python
# retry.py
import time
import random
from typing import TypeVar, Callable, Optional, Type
from functools import wraps
import anthropic

T = TypeVar('T')

def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: tuple = (
        anthropic.RateLimitError,
        anthropic.APIConnectionError,
        anthropic.APITimeoutError,
        anthropic.InternalServerError,
    )
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Retry a function with exponential backoff and jitter.

    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds (default 1.0)
        max_delay: Maximum delay in seconds (default 60.0)
        exponential_base: Base for exponential backoff (default 2.0)
        jitter: Whether to add random jitter to delays
        retryable_exceptions: Tuple of exceptions that should trigger retries

    Returns:
        Decorated function with retry logic
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)

                except retryable_exceptions as e:
                    last_exception = e

                    # Don't retry on the last attempt
                    if attempt == max_retries:
                        break

                    # Calculate delay with exponential backoff
                    delay = min(
                        initial_delay * (exponential_base ** attempt),
                        max_delay
                    )

                    # Add jitter if enabled
                    if jitter:
                        delay = delay * (0.5 + random.random())

                    print(f"Attempt {attempt + 1} failed: {e}")
                    print(f"Retrying in {delay:.2f} seconds...")
                    time.sleep(delay)

                except Exception as e:
                    # Non-retryable exception - fail immediately
                    print(f"Non-retryable error: {e}")
                    raise

            # All retries exhausted
            print(f"All {max_retries} retries exhausted")
            raise last_exception

        return wrapper
    return decorator
```

Now let's update the agent to use retry logic on API calls:

```python
# agent.py
from retry import retry_with_backoff
import anthropic

class Agent:
    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or get_config()
        self.client = anthropic.Anthropic(api_key=self.config.api_key)
        self.conversation_history: List[Dict[str, Any]] = []

    @retry_with_backoff(max_retries=3, initial_delay=1.0)
    def _call_llm(self) -> anthropic.types.Message:
        """Call the LLM API with retry logic."""
        return self.client.messages.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            system=self.config.system_prompt,
            tools=TOOLS,
            messages=self.conversation_history
        )

    def process(self, user_input: str) -> str:
        """Process a user request through the agentic loop."""
        self.conversation_history.append({
            "role": "user",
            "content": user_input
        })

        iterations = 0
        while iterations < self.config.max_iterations:
            iterations += 1

            try:
                # Call LLM with retry logic
                response = self._call_llm()

                if response.stop_reason == "end_turn":
                    return self._extract_text_response(response)

                elif response.stop_reason == "tool_use":
                    tool_results = self._execute_tools(response.content)
                    self.conversation_history.append({
                        "role": "user",
                        "content": tool_results
                    })

            except Exception as e:
                # All retries exhausted or non-retryable error
                return f"Error: {str(e)}"

        return "Maximum iterations reached"
```

#### What This Solves

**Before**: A temporary rate limit causes an immediate user-facing failure.

**After**: A temporary rate limit triggers 1-3 automatic retries with backoff. Most transient failures resolve themselves without user impact.

**Cost**: Minimal. Retries add latency (1-15 seconds in worst case), but prevent user-facing failures.

### Pattern 1.5: Making Retries Safe with Idempotency

**The Problem**: Retries can cause duplicate operations if your operations aren't idempotent.

**The Solution**: Make operations idempotent so retries are safe.

#### What is Idempotency?

**Idempotent**: An operation that produces the same result no matter how many times you execute it.

```
f(x) = result
f(f(x)) = result  // Same result!
f(f(f(x))) = result  // Still the same!
```

**Examples:**

✅ **Idempotent operations** (safe to retry):
- `calculator("15 * 23")` → Always returns 345
- `get_weather("Seattle")` → Always returns current weather (read-only)
- `web_search("Python tutorials")` → Always returns search results (read-only)
- `SET user:123:name "John"` → Always sets the same value

❌ **Non-idempotent operations** (dangerous to retry):
- `save_note("Meeting notes")` → Creates a new file each time!
- `INCREMENT counter` → Increments again on each retry!
- `send_email("Welcome!")` → Sends duplicate emails!
- `charge_credit_card($100)` → Charges customer multiple times!

#### The Danger

Without idempotency, a retry can cause:

**Scenario**: User asks to save a note.

```
User: "Save note: Meeting notes for Q1"

Attempt 1:
  - Agent calls save_note("Meeting notes for Q1")
  - Creates notes/note_20250128_153045.txt
  - Response times out (network blip)

Retry (automatic):
  - Agent calls save_note("Meeting notes for Q1") AGAIN
  - Creates notes/note_20250128_153048.txt  // DUPLICATE!
  - Success

Result: TWO identical notes saved
User sees: "Note saved" (but which one??)
```

This is **data corruption through retries**.

#### The Solution: Make Operations Idempotent

**Strategy 1: Use Content Hash for Filenames**

Instead of timestamp-based filenames, use content hash:

```python
import hashlib

def save_note(content: str, filename: str = None) -> str:
    """Save note (idempotent)."""
    if filename is None:
        # Generate filename from content hash
        content_hash = hashlib.md5(content.encode()).hexdigest()[:12]
        date = datetime.now().strftime("%Y%m%d")
        filename = f"note_{date}_{content_hash}.txt"

    filepath = os.path.join("notes", filename)

    # Check if file already exists with same content
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            if f.read() == content:
                # Retry with same content - return success
                return f"Note already exists at {filepath} (idempotent)"

    # Write file
    with open(filepath, "w") as f:
        f.write(content)

    return f"Note saved to {filepath}"
```

**Now retries are safe:**

```
Attempt 1: save_note("Meeting notes")
  → Creates notes/note_20250128_a3b5c7d9e1f2.txt
  → Times out

Retry: save_note("Meeting notes")
  → Same content = same hash = same filename!
  → File exists, content matches → Return success
  → NO DUPLICATE!
```

**Strategy 2: Idempotency Keys (External APIs)**

For external APIs, use idempotency keys:

```python
import uuid

def create_resource_with_retry(data):
    # Generate idempotency key once
    idempotency_key = str(uuid.uuid4())

    @retry_with_backoff(max_retries=3)
    def _create():
        return api.create_resource(
            data=data,
            idempotency_key=idempotency_key  # Same key on all retries!
        )

    return _create()
```

The API sees the same idempotency key on all retries and returns the same result (or detects duplicate).

**Strategy 3: Check-Then-Act Pattern**

For operations that can't be made naturally idempotent:

```python
def increment_counter(counter_id: str):
    """Increment counter (with idempotency check)."""

    # Check: Has this request been processed?
    request_id = get_current_request_id()  # From request context
    if request_log.exists(request_id):
        # Already processed - return cached result
        return request_log.get_result(request_id)

    # Act: Perform the operation
    result = db.increment(counter_id)

    # Record: Save that we processed this request
    request_log.save(request_id, result)

    return result
```

Now retries check the log and skip duplicate processing.

#### Idempotency Checklist

For each operation that might be retried, ask:

1. **Is it naturally idempotent?**
   - Read operations: Usually YES ✅
   - Pure computations: YES ✅
   - Write operations: Usually NO ❌

2. **If not, can I make it idempotent?**
   - Use content hash: ✅
   - Use idempotency keys: ✅
   - Check-then-act: ✅

3. **How do I test it?**
   ```python
   # Call twice with same input
   result1 = operation(input)
   result2 = operation(input)

   # Results should be identical
   assert result1 == result2

   # Side effects should only happen once
   assert db.count_records() == 1  # Not 2!
   ```

#### Real-World Example: Payment Processing

**Bad (not idempotent):**
```python
@retry_with_backoff(max_retries=3)
def charge_customer(amount):
    return stripe.charges.create(
        amount=amount,
        currency="usd",
        customer=customer_id
    )
# Retry = double charge! 😱
```

**Good (idempotent):**
```python
@retry_with_backoff(max_retries=3)
def charge_customer(amount, order_id):
    return stripe.charges.create(
        amount=amount,
        currency="usd",
        customer=customer_id,
        idempotency_key=f"order_{order_id}"  # ✅ Safe to retry
    )
# Retry = same charge, no duplicate!
```

#### What This Solves

**Before**: Retries cause duplicate operations, data corruption, and angry users.

**After**: Retries are safe. Same input = same result, no matter how many times you retry.

**Cost**: Minimal complexity (content hashing, idempotency keys). Huge reliability gain.

**Rule of thumb**: If an operation has side effects AND you retry it, make it idempotent.

### Pattern 2: Timeouts for All Operations

**The Problem**: Operations can hang indefinitely, blocking resources and degrading performance.

**The Solution**: Set maximum execution time for every operation.

#### Why Timeouts Matter

Without timeouts, a slow operation can:
- Block a thread/worker indefinitely
- Exhaust your connection pool
- Cause request queue buildup
- Eventually crash your service with OOM errors

**Real example**: A web search tool makes an HTTP request to a third-party API. The API is having issues and takes 5 minutes to respond (instead of 500ms). Your agent waits 5 minutes. During peak traffic with 100 concurrent users, you now have 100 blocked workers. New requests queue up. Memory usage spikes. Your service dies.

**With timeouts**: That same slow API gets 10 seconds max. After 10 seconds, the operation is cancelled, an error is returned, and the worker is freed for the next request.

#### Implementation

Python makes timeouts easy with the `signal` module (for synchronous code) or `asyncio.timeout` (for async code). The Anthropic SDK also supports native timeouts.

Let's add timeouts to our agent:

```python
# config.py
@dataclass
class AgentConfig:
    api_key: str
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    temperature: float = 1.0
    max_iterations: int = 10

    # NEW: Timeout configurations
    llm_timeout: float = 30.0  # Max 30 seconds for LLM calls
    tool_timeout: float = 10.0  # Max 10 seconds for tool calls
    total_timeout: float = 120.0  # Max 2 minutes for entire request

    system_prompt: str = "You are a helpful task automation assistant..."
```

```python
# agent.py
import signal
from contextlib import contextmanager

class TimeoutError(Exception):
    """Raised when an operation exceeds its timeout."""
    pass

@contextmanager
def timeout(seconds: float):
    """Context manager for operation timeouts."""
    def timeout_handler(signum, frame):
        raise TimeoutError(f"Operation exceeded {seconds} second timeout")

    # Set the signal handler
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(int(seconds))

    try:
        yield
    finally:
        # Restore the old handler and cancel the alarm
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


class Agent:
    @retry_with_backoff(max_retries=3, initial_delay=1.0)
    def _call_llm(self) -> anthropic.types.Message:
        """Call the LLM API with retry logic and timeout."""
        # Anthropic SDK supports timeout parameter
        return self.client.messages.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            system=self.config.system_prompt,
            tools=TOOLS,
            messages=self.conversation_history,
            timeout=self.config.llm_timeout  # NEW: SDK-level timeout
        )

    def _execute_tools(self, content: list) -> list:
        """Execute tools with timeout protection."""
        results = []

        for block in content:
            if block.type == "tool_use":
                tool_name = block.name
                tool_input = block.input

                try:
                    # Execute tool with timeout
                    with timeout(self.config.tool_timeout):
                        result = execute_tool(tool_name, tool_input)

                    results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

                except TimeoutError as e:
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": f"Error: Tool execution timed out after {self.config.tool_timeout}s",
                        "is_error": True
                    })

                except Exception as e:
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": f"Error: {str(e)}",
                        "is_error": True
                    })

        return results

    def process(self, user_input: str) -> str:
        """Process a user request with total request timeout."""
        try:
            # Total request timeout
            with timeout(self.config.total_timeout):
                return self._process_internal(user_input)

        except TimeoutError:
            return f"Request exceeded maximum processing time of {self.config.total_timeout}s"

    def _process_internal(self, user_input: str) -> str:
        """Internal processing logic (same as before)."""
        self.conversation_history.append({
            "role": "user",
            "content": user_input
        })

        iterations = 0
        while iterations < self.config.max_iterations:
            iterations += 1

            try:
                response = self._call_llm()

                if response.stop_reason == "end_turn":
                    return self._extract_text_response(response)

                elif response.stop_reason == "tool_use":
                    tool_results = self._execute_tools(response.content)
                    self.conversation_history.append({
                        "role": "user",
                        "content": tool_results
                    })

            except Exception as e:
                return f"Error: {str(e)}"

        return "Maximum iterations reached"
```

#### Timeout Strategy

Notice we have **three levels of timeouts**:

1. **LLM timeout (30s)**: Maximum time for a single LLM API call
2. **Tool timeout (10s)**: Maximum time for a single tool execution
3. **Total timeout (120s)**: Maximum time for the entire user request

This creates **defense in depth**. If a tool hangs for 15 seconds, the tool timeout catches it. If the agent enters a slow loop, the total timeout catches it.

#### What This Solves

**Before**: A hung operation blocks resources indefinitely.

**After**: All operations have maximum execution time. Slow operations are cancelled, and the user gets a timeout error instead of infinite wait.

**Cost**: Better resource utilization. Workers are freed quickly instead of blocked.

### Pattern 3: Circuit Breakers

**The Problem**: Your agent keeps calling a failing dependency, wasting resources and making the failure worse.

**The Solution**: After a threshold of failures, "trip" the circuit and fail fast instead of retrying.

#### The Circuit Breaker Pattern

Think of an electrical circuit breaker in your house. When there's a short circuit, the breaker "trips" to prevent damage. You don't keep sending electricity through a broken circuit.

Same principle for distributed systems:

**States:**
1. **Closed** (normal): Requests flow through normally
2. **Open** (tripped): All requests fail immediately without trying
3. **Half-Open** (testing): After a timeout, allow a few test requests

**Transition logic:**
- Closed → Open: After N consecutive failures (e.g., 5)
- Open → Half-Open: After timeout period (e.g., 60 seconds)
- Half-Open → Closed: If test requests succeed
- Half-Open → Open: If test requests fail

#### Why Circuit Breakers Matter for AI Agents

Imagine the web search tool API goes down. Without a circuit breaker:

1. User makes request
2. Agent calls web search → fails
3. Retry 1 → fails
4. Retry 2 → fails
5. Retry 3 → fails
6. Return error to user (after 15+ seconds of retries)

Now multiply this by 100 concurrent users. You've just sent **400 doomed requests** to a service that's down. You've wasted:
- Network bandwidth
- CPU cycles
- User wait time
- The API's resources (making it harder for them to recover)

**With a circuit breaker:**

1. First 5 users hit the same failures (circuit still closed)
2. Circuit trips after 5 failures
3. Next 95 users get **immediate** errors (fail fast)
4. After 60 seconds, circuit tests with one request
5. If the API recovered, circuit closes; if not, stays open

You've reduced 400 wasted requests to 5, and users get faster feedback.

#### Implementation

Let's implement a simple circuit breaker:

```python
# circuit_breaker.py
import time
from enum import Enum
from typing import Callable, TypeVar, Optional
from functools import wraps

T = TypeVar('T')

class CircuitState(Enum):
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Circuit tripped, failing fast
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """Circuit breaker to prevent cascading failures."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type = Exception
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before testing recovery
            expected_exception: Exception type that counts as failure
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = CircuitState.CLOSED

    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute function with circuit breaker protection."""

        # If circuit is open, check if we should test recovery
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                print(f"Circuit breaker: Testing recovery (HALF_OPEN)")
            else:
                raise Exception(
                    f"Circuit breaker OPEN: Service unavailable. "
                    f"Retry after {self.recovery_timeout}s"
                )

        try:
            # Execute the function
            result = func(*args, **kwargs)

            # Success - reset failure count
            if self.state == CircuitState.HALF_OPEN:
                print(f"Circuit breaker: Recovery successful (CLOSED)")

            self.failure_count = 0
            self.state = CircuitState.CLOSED
            return result

        except self.expected_exception as e:
            # Failure - increment count
            self.failure_count += 1
            self.last_failure_time = time.time()

            # Trip circuit if threshold exceeded
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                print(
                    f"Circuit breaker: OPEN after {self.failure_count} failures. "
                    f"Will retry in {self.recovery_timeout}s"
                )

            raise


def circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    expected_exception: type = Exception
):
    """Decorator to add circuit breaker to a function."""
    breaker = CircuitBreaker(
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
        expected_exception=expected_exception
    )

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            return breaker.call(func, *args, **kwargs)
        return wrapper
    return decorator
```

Now let's add circuit breakers to our tools:

```python
# tools.py
from circuit_breaker import circuit_breaker

# Circuit breaker for web search (external API)
@circuit_breaker(
    failure_threshold=5,
    recovery_timeout=60.0,
    expected_exception=Exception
)
def web_search(query: str) -> str:
    """Search the web with circuit breaker protection."""
    # Implementation here
    pass


# Circuit breaker for weather API (external API)
@circuit_breaker(
    failure_threshold=5,
    recovery_timeout=60.0,
    expected_exception=Exception
)
def get_weather(location: str) -> str:
    """Get weather with circuit breaker protection."""
    # Implementation here
    pass
```

#### What This Solves

**Before**: Agent hammers failing dependencies with retries, wasting resources.

**After**: After threshold failures, circuit trips and fails fast. Service gets time to recover.

**Cost**: Better resource utilization. Failed requests return immediately instead of wasting retries.

### Pattern 3.5: Rate Limiting (Client-Side)

**The Problem**: Retries + circuit breakers can still cause thundering herds that exceed API rate limits.

**The Solution**: Client-side rate limiting to prevent overwhelming APIs.

#### Why Client-Side Rate Limiting Matters

You've added retries and circuit breakers. Great! But there's still a problem:

**Scenario:**
- Anthropic API has 1,000 requests/minute rate limit
- You have 100 agent workers
- Each request might retry 3 times
- Peak traffic: 500 user requests/minute

**Without rate limiting:**
```
500 requests × 100 workers × 3 retries = 150,000 potential API calls/minute!
API rate limit: 1,000/minute
Result: 149,000 requests get 429 errors → circuit breakers trip → everything fails
```

**The retries made it WORSE, not better!**

#### The Token Bucket Algorithm

The solution is **client-side rate limiting** using the token bucket algorithm:

**Concept:**
- You have a bucket that holds tokens
- Tokens are added at a fixed rate (e.g., 10 tokens/second)
- Each request consumes 1 token
- If no tokens available, request waits or is rejected
- Bucket has max capacity (allows bursts)

**Example:**
- Rate: 10 requests/second
- Capacity: 20 tokens
- **Sustained**: 10 req/s
- **Burst**: Up to 20 req/s (then throttled back to 10 req/s)

#### Implementation

```python
# rate_limiter.py
import time
import threading

class TokenBucket:
    """Thread-safe token bucket for rate limiting."""

    def __init__(self, rate: float, capacity: float = None):
        """
        Initialize token bucket.

        Args:
            rate: Tokens added per second (requests per second)
            capacity: Max tokens (allows bursts). Defaults to rate.
        """
        self.rate = rate
        self.capacity = capacity or rate
        self.tokens = self.capacity
        self.last_update = time.time()
        self._lock = threading.Lock()

    def _refill(self):
        """Refill tokens based on time elapsed."""
        now = time.time()
        elapsed = now - self.last_update

        # Add tokens based on elapsed time
        new_tokens = elapsed * self.rate
        self.tokens = min(self.capacity, self.tokens + new_tokens)
        self.last_update = now

    def consume(self, tokens: float = 1.0, block: bool = True) -> bool:
        """
        Consume tokens from bucket.

        Args:
            tokens: Number of tokens to consume
            block: If True, wait for tokens. If False, reject immediately.

        Returns:
            True if tokens consumed, False if rejected
        """
        while True:
            with self._lock:
                self._refill()

                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return True

                if not block:
                    return False  # Reject immediately

            # Wait for next token
            wait_time = (tokens - self.tokens) / self.rate
            time.sleep(min(wait_time, 0.1))


def rate_limit(rate: float, capacity: float = None):
    """Decorator to add rate limiting to a function."""
    bucket = TokenBucket(rate=rate, capacity=capacity)

    def decorator(func):
        def wrapper(*args, **kwargs):
            bucket.consume()  # Wait for token
            return func(*args, **kwargs)
        return wrapper
    return decorator
```

#### Using Rate Limiting with Retries

**Key insight**: Rate limiting should happen **before** retries:

```python
# CORRECT ORDER:
@retry_with_backoff(max_retries=3)
@rate_limit(rate=10)  # Rate limit INSIDE retry
def call_api():
    return client.messages.create(...)

# Flow:
# 1. Retry decorator enters
# 2. Rate limiter waits for token
# 3. API call happens
# 4. If fails → retry waits, then rate limiter waits again
# This prevents retry storms!
```

**Wrong order:**
```python
# WRONG:
@rate_limit(rate=10)
@retry_with_backoff(max_retries=3)  # Rate limit OUTSIDE retry
def call_api():
    return client.messages.create(...)

# Flow:
# 1. Rate limiter waits for token
# 2. Retry decorator enters
# 3. All 3 retries happen without rate limiting!
# Defeats the purpose!
```

#### Rate Limiting + Circuit Breakers + Retries

These three patterns work together:

```python
from retry import retry_with_backoff
from circuit_breaker import circuit_breaker
from rate_limiter import rate_limit

@circuit_breaker(name="anthropic_api", failure_threshold=5)
@retry_with_backoff(max_retries=3, initial_delay=1.0)
@rate_limit(rate=10, capacity=20)  # 10 req/s sustained, 20 burst
def call_llm(messages):
    return client.messages.create(
        model="claude-sonnet-4-20250514",
        messages=messages
    )
```

**How they interact:**

1. **Circuit breaker** (outermost): If API is down, fail fast immediately
2. **Retry logic**: If transient failure (rate limit, timeout), retry with backoff
3. **Rate limiter** (innermost): Before each attempt, wait for token

**Result:**
- Circuit trips after 5 failures → stop hitting the API
- Retries don't create thundering herd → rate limiter prevents it
- Transient failures recover gracefully → retry with backoff

#### Distributed Rate Limiting

The token bucket above is per-process. In a distributed system with multiple workers, each worker has its own bucket.

**Problem:**
- 100 workers, each with 10 req/s limit
- Total: 1,000 req/s
- But API limit is 100 req/s!

**Solution:** Share the token bucket in Redis:

```python
# rate_limiter_redis.py
import redis
import time

class RedisTokenBucket:
    """Distributed token bucket using Redis."""

    def __init__(self, redis_client, key, rate, capacity):
        self.redis = redis_client
        self.key = key
        self.rate = rate
        self.capacity = capacity

    def consume(self, tokens=1):
        """Consume tokens (Lua script for atomicity)."""
        script = """
        local key = KEYS[1]
        local rate = tonumber(ARGV[1])
        local capacity = tonumber(ARGV[2])
        local tokens_requested = tonumber(ARGV[3])
        local now = tonumber(ARGV[4])

        -- Get current state
        local state = redis.call('HMGET', key, 'tokens', 'last_update')
        local tokens = tonumber(state[1]) or capacity
        local last_update = tonumber(state[2]) or now

        -- Refill tokens
        local elapsed = now - last_update
        tokens = math.min(capacity, tokens + (elapsed * rate))

        -- Try to consume
        if tokens >= tokens_requested then
            tokens = tokens - tokens_requested
            redis.call('HMSET', key, 'tokens', tokens, 'last_update', now)
            return 1  -- Success
        else
            return 0  -- Not enough tokens
        end
        """

        result = self.redis.eval(
            script,
            1,  # Number of keys
            self.key,
            self.rate,
            self.capacity,
            tokens,
            time.time()
        )

        return result == 1
```

Now all workers share the same token bucket in Redis!

#### Practical Rate Limiting Strategy

**For production:**

1. **Know your API limits:**
   - Anthropic: Check current rate limits in docs
   - Set your limit to 80% of API limit (safety margin)

2. **Monitor token availability:**
   ```python
   available = bucket.get_available_tokens()
   if available < 5:
       # Running low on tokens!
       emit_metric("rate_limit_pressure", 1)
   ```

3. **Implement backpressure:**
   ```python
   if not bucket.consume(block=False):
       # No tokens available
       # Return 429 to client or queue request
       raise RateLimitExceeded("Too many requests")
   ```

4. **Use different buckets for different priorities:**
   ```python
   # High priority: More tokens
   high_priority_bucket = TokenBucket(rate=50)

   # Low priority: Fewer tokens
   low_priority_bucket = TokenBucket(rate=10)
   ```

#### What This Solves

**Before**: Retries and circuit breakers can still cause thundering herds that exceed API rate limits.

**After**: Client-side rate limiting prevents overwhelming APIs. Requests are throttled to safe levels.

**Cost**: Minimal. Some requests wait for tokens, but prevents cascading failures and rate limit errors.

**Rule of thumb**: If you retry and have multiple workers, add rate limiting.

### Pattern 4: Graceful Degradation

**The Problem**: When a non-critical feature fails, the entire request fails.

**The Solution**: Degrade functionality instead of failing completely.

#### The Graceful Degradation Philosophy

Not all features are equally critical. Some failures should be **acceptable** if they don't prevent the core function.

**Example**: User asks "What's the weather in Seattle and what's 15 * 23?"

If the weather API is down, should the calculator also fail? No! Return:

```
I couldn't fetch the weather for Seattle (service unavailable),
but I can tell you that 15 * 23 = 345.
```

This is **graceful degradation**: partial success is better than total failure.

#### Implementation Strategy

Mark tools as **critical** vs **optional**:

```python
# tools.py
TOOL_CRITICALITY = {
    "calculator": "critical",  # Always must work
    "save_note": "critical",  # Always must work
    "web_search": "optional",  # Can fail gracefully
    "get_weather": "optional",  # Can fail gracefully
}

def execute_tool(tool_name: str, tool_input: dict) -> str:
    """Execute a tool with criticality awareness."""
    criticality = TOOL_CRITICALITY.get(tool_name, "critical")

    try:
        # Execute the tool
        if tool_name == "calculator":
            return calculator(**tool_input)
        elif tool_name == "save_note":
            return save_note(**tool_input)
        elif tool_name == "web_search":
            return web_search(**tool_input)
        elif tool_name == "get_weather":
            return get_weather(**tool_input)
        else:
            return f"Unknown tool: {tool_name}"

    except Exception as e:
        if criticality == "critical":
            # Critical tool failure - propagate error
            raise
        else:
            # Optional tool failure - return degraded response
            return (
                f"[Tool '{tool_name}' is temporarily unavailable. "
                f"Reason: {str(e)}]"
            )
```

Now the agent can handle partial failures:

```
User: What's the weather in Seattle and what's 15 * 23?

Agent attempts:
1. get_weather("Seattle") → Circuit breaker OPEN → Returns degraded message
2. calculator("15 * 23") → Success → Returns 345

Agent responds:
"I couldn't fetch the current weather for Seattle (weather service
is temporarily unavailable), but I can tell you that 15 * 23 = 345."
```

#### What This Solves

**Before**: One tool failure causes the entire request to fail.

**After**: Optional tool failures degrade gracefully. Users get partial results instead of total failure.

**Cost**: Better user experience. Requests succeed more often.

### Pattern 5: Health Checks

**The Problem**: Orchestrators (Kubernetes, ECS, etc.) can't tell if your agent is healthy and ready to receive traffic.

**The Solution**: Expose health check endpoints that report service status.

#### Two Types of Health Checks

**Liveness probe**: "Is the service alive?"
- If this fails, the orchestrator **restarts** the container
- Should check: Can the process respond?

**Readiness probe**: "Is the service ready for traffic?"
- If this fails, the orchestrator **stops sending traffic** (but doesn't restart)
- Should check: Can the service handle requests? (DB connected, API reachable, etc.)

#### Implementation

Let's add a simple HTTP health check endpoint:

```python
# health.py
from fastapi import FastAPI
from pydantic import BaseModel
import anthropic

app = FastAPI()

class HealthResponse(BaseModel):
    status: str
    checks: dict


class LivenessResponse(BaseModel):
    status: str


@app.get("/health/live", response_model=LivenessResponse)
def liveness():
    """
    Liveness probe: Is the service alive?
    Returns 200 if the process is running.
    """
    return {"status": "ok"}


@app.get("/health/ready", response_model=HealthResponse)
def readiness():
    """
    Readiness probe: Is the service ready for traffic?
    Checks dependencies before reporting ready.
    """
    checks = {}
    overall_status = "ok"

    # Check 1: Can we reach the Anthropic API?
    try:
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        # Simple API call to verify connectivity
        # (We don't need a full completion, just verify auth works)
        client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1,
            messages=[{"role": "user", "content": "test"}],
            timeout=5.0
        )
        checks["anthropic_api"] = "ok"
    except Exception as e:
        checks["anthropic_api"] = f"failed: {str(e)}"
        overall_status = "degraded"

    # Check 2: Can we access the database? (if you have one)
    # try:
    #     db.query("SELECT 1")
    #     checks["database"] = "ok"
    # except Exception as e:
    #     checks["database"] = f"failed: {str(e)}"
    #     overall_status = "degraded"

    # Check 3: Disk space for notes/ directory
    import shutil
    try:
        stat = shutil.disk_usage("./notes")
        free_gb = stat.free / (1024**3)
        if free_gb < 1.0:  # Less than 1 GB free
            checks["disk_space"] = f"low: {free_gb:.2f} GB"
            overall_status = "degraded"
        else:
            checks["disk_space"] = "ok"
    except Exception as e:
        checks["disk_space"] = f"failed: {str(e)}"
        overall_status = "degraded"

    return {
        "status": overall_status,
        "checks": checks
    }
```

#### Running Health Checks

Now you can run the health server alongside your agent:

```bash
# Terminal 1: Run the agent
uv run python agent.py

# Terminal 2: Run the health check server
uv run uvicorn health:app --port 8080

# Test health checks
curl http://localhost:8080/health/live
# {"status":"ok"}

curl http://localhost:8080/health/ready
# {"status":"ok","checks":{"anthropic_api":"ok","disk_space":"ok"}}
```

#### Kubernetes Configuration

Here's how you'd configure Kubernetes to use these health checks:

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: task-agent
spec:
  replicas: 3
  selector:
    matchLabels:
      app: task-agent
  template:
    metadata:
      labels:
        app: task-agent
    spec:
      containers:
      - name: agent
        image: task-agent:v1
        ports:
        - containerPort: 8080

        # Liveness probe: Restart if fails
        livenessProbe:
          httpGet:
            path: /health/live
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 30
          timeoutSeconds: 5
          failureThreshold: 3

        # Readiness probe: Remove from load balancer if fails
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 2
```

**How this works:**
- **Liveness**: Checked every 30s. If it fails 3 times, Kubernetes restarts the container
- **Readiness**: Checked every 10s. If it fails 2 times, Kubernetes stops routing traffic to this pod

#### What This Solves

**Before**: Orchestrators can't tell if your agent is healthy. Unhealthy instances receive traffic.

**After**: Orchestrators automatically detect failures and stop routing traffic to unhealthy instances.

**Cost**: Better availability. Failed instances are automatically replaced.

## Production Reliability Checklist

Let's review what we've added to the reference agent:

- [x] **Retry logic** with exponential backoff and jitter
- [x] **Timeouts** at multiple levels (LLM, tool, total request)
- [x] **Circuit breakers** for external dependencies
- [x] **Graceful degradation** for non-critical features
- [x] **Health checks** (liveness and readiness probes)

Our agent is now **significantly more reliable**. But we're not done yet.

**Still missing:**
- ❌ Structured logging (Chapter 3)
- ❌ Metrics collection (Chapter 3)
- ❌ Distributed tracing (Chapter 3)
- ❌ Security hardening (Chapter 4)
- ❌ Cost tracking (Chapter 5)
- ❌ Horizontal scaling (Chapter 6)

## Real-World Incident: Lessons from Production

Let me share a real incident that taught me the value of these patterns.

### The Infinite Retry Loop

**Date**: March 2024
**Service**: Customer support agent
**Impact**: $12,000 API bill in 6 hours

**What happened:**

A customer support agent had retry logic but no circuit breaker. An external knowledge base API went down at 2 AM. The agent:

1. Tried to call the API → timed out
2. Retried 3 times → all timed out
3. Returned error to user
4. Next user request → same thing

Sounds fine, right? **Wrong.**

The agent processed **8,000 requests** during those 6 hours. Each request:
- Called the LLM 4 times (initial + 3 retries on the knowledge base tool)
- Each LLM call was ~1,500 tokens input + 500 tokens output
- Claude Sonnet pricing: $3/MTok input, $15/MTok output

**Cost calculation:**
```
8,000 requests × 4 LLM calls = 32,000 LLM calls
32,000 calls × (1,500 input tokens + 500 output tokens) =
  48M input tokens + 16M output tokens

Cost:
  Input:  48M tokens × $3/MTok = $144
  Output: 16M tokens × $15/MTok = $240
  Total: $384

Wait, that's not $12,000...
```

**What actually happened:**

The timeout was set to 30 seconds, but the retries happened **inside the agentic loop**. Each failed tool call caused the agent to retry the entire workflow, which called the LLM again, which tried the tool again, which failed again...

It created an **exponential explosion** of LLM calls:
- User request → LLM call → tool call (fails) → retry → LLM call → tool call (fails) → retry → ...

The actual number of LLM calls was closer to **100,000**, not 32,000.

**Cost:** $12,000 in 6 hours.

**What would have prevented this:**

1. **Circuit breaker**: After 5 failures, trip the circuit. Fail fast for next 8,000 requests instead of retrying.
2. **Better timeout strategy**: Timeout the tool call, not the retry loop.
3. **Cost budgets**: Alert when spend exceeds $500/hour (Chapter 5).
4. **Metrics**: Alert on abnormally high LLM call rate (Chapter 3).

**Lesson**: Every resilience pattern matters. Missing even one can be expensive.

## Exercises

### Exercise 1: Implement Retry Logic

Add retry logic to all tools in the reference agent:
1. Implement retry decorator for tools
2. Configure different retry strategies for different tools
3. Add logging to track retry attempts
4. Test with simulated failures

### Exercise 2: Add Comprehensive Timeouts

Add three levels of timeouts to the agent:
1. Individual tool timeouts (5-30s depending on tool)
2. LLM call timeout (30s)
3. Total request timeout (2 minutes)
4. Test with simulated slow operations

### Exercise 3: Build a Circuit Breaker

Implement a circuit breaker for one of the tools:
1. Set failure threshold to 3
2. Set recovery timeout to 30 seconds
3. Add state logging (CLOSED → OPEN → HALF_OPEN)
4. Test the state transitions

### Exercise 4: Implement Graceful Degradation

Categorize tools by criticality:
1. Mark web_search and get_weather as optional
2. Mark calculator and save_note as critical
3. Update error handling to degrade gracefully for optional tools
4. Test partial success scenarios

### Exercise 5: Add Health Checks

Implement health check endpoints:
1. Create /health/live endpoint (simple)
2. Create /health/ready endpoint (check API connectivity)
3. Test both endpoints
4. Write Kubernetes probe configuration

### Exercise 6: Failure Mode Analysis

For each resilience pattern, document:
1. What failure mode does it prevent?
2. What's the user experience without it?
3. What's the user experience with it?
4. What's the cost (latency, complexity)?

### Exercise 7: Chaos Engineering

Deliberately break your agent:
1. Simulate API rate limits (return 429 errors)
2. Simulate network timeouts (sleep 60s in tool)
3. Simulate circuit breaker trips (5 consecutive failures)
4. Simulate resource exhaustion (out of disk space)

Verify each resilience pattern handles the failure correctly.

## Key Takeaways

**Reliability is not optional in production:**

1. **Everything fails, all the time**
   Assume failure is the default state. Build resilience to handle it gracefully.

2. **Retry with exponential backoff and jitter**
   Transient failures resolve themselves. Don't fail users unnecessarily. But be smart about retries to avoid thundering herds.

3. **Timeouts prevent resource exhaustion**
   Never let an operation run indefinitely. Set timeouts at multiple levels for defense in depth.

4. **Circuit breakers stop cascading failures**
   When a dependency fails, fail fast instead of wasting resources on doomed retries.

5. **Graceful degradation > total failure**
   Partial success is better than complete failure. Degrade non-critical features when they fail.

6. **Health checks enable orchestration**
   Liveness and readiness probes let orchestrators automatically manage unhealthy instances.

7. **Every pattern prevents real incidents**
   These aren't over-engineering. Each pattern prevents an actual, expensive failure mode.

8. **Combine patterns for defense in depth**
   Retries + timeouts + circuit breakers + graceful degradation work together. Missing one leaves gaps.

## What's Next

In **Chapter 3: Observability and Debugging**, we'll make the agent **visible**. We'll add:

- Structured logging with correlation IDs
- Prometheus metrics for rate, errors, and latency
- OpenTelemetry distributed tracing
- Dashboards for real-time visibility
- Alerts for SLO violations

Right now, our agent is reliable—but we can't prove it. We can't see what's happening inside. We can't debug production issues effectively.

**Chapter 3 fixes that.** We'll make the agent fully observable so we can understand, debug, and prove its reliability.

Let's continue.

---

**Code for this chapter**: `code-examples/chapter-02-reliability/`
**Next chapter**: Chapter 3 - Observability and Debugging
