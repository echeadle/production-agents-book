# Chapter 7: Performance Optimization

## Introduction: The Timeout Crisis

Marcus's agent was handling customer support conversations successfully—but users were complaining. The agent worked perfectly, but response times were unacceptable:

- **Average response time**: 12 seconds
- **95th percentile**: 25 seconds
- **User feedback**: "Too slow, I'll just call support"
- **Abandonment rate**: 40% (users gave up waiting)

**The problem**: The agent was architecturally sound (stateless, scalable) but performance-optimized it was not.

After a week of optimization:
- **Average response time**: 2.8 seconds (4.3x improvement)
- **95th percentile**: 4.5 seconds (5.6x improvement)
- **User feedback**: "Fast and helpful!"
- **Abandonment rate**: 8% (5x improvement)

**What changed**: Caching, async patterns, connection pooling, and smart concurrency.

This is the performance challenge: **Scalability gets you to many users; performance keeps them happy.**

---

## Why Performance Matters

In production, performance directly impacts:

- **User experience**: Fast agents feel magical, slow ones feel broken
- **Conversion rate**: Each second of delay = 7% drop in conversions
- **Cost**: Slower agents require more infrastructure
- **Scalability**: High latency = low throughput = need more instances
- **Competitive advantage**: Speed is a feature

**Production reality**: Users will tolerate bugs, but they won't tolerate slow.

### The Performance Mindset

Performance optimization is about **eliminating waste**:

- **Measure everything**: You can't optimize what you don't measure
- **Find bottlenecks**: 80% of time is spent in 20% of code
- **Optimize hot paths**: Focus on frequent operations
- **Parallelize**: Do multiple things concurrently when possible
- **Cache aggressively**: Don't recompute what you already know
- **Profile first**: Intuition about performance is usually wrong

**Key principle**: Make the common case fast.

---

## Understanding Latency Components

### Anatomy of an Agent Request

```
Total Latency = Network + Queue + Processing + I/O

Processing = Prompt_Build + API_Call + Tool_Execution + Response_Parse
```

**Typical breakdown** (12-second request):
- Network latency: 100ms (0.8%)
- Queue wait time: 0ms (not queued)
- Prompt building: 50ms (0.4%)
- API call to Claude: 8,000ms (66.7%)
- Tool execution: 3,500ms (29.2%)
  - Database query: 1,200ms
  - External API call: 2,000ms
  - File I/O: 300ms
- Response parsing: 350ms (2.9%)

**Optimization opportunities**:
1. Parallelize tool execution (save 2,000ms)
2. Cache database queries (save 1,000ms)
3. Stream API responses (perceived latency improvement)
4. Pre-warm connections (save 100ms on external APIs)

**Result**: 12s → 6.9s (43% improvement)

---

## Caching Strategies

### Principle 1: Cache Everything You Can

**What to cache**:
- Expensive computations
- External API calls
- Database queries
- Search results
- Embeddings
- Frequently accessed data

**What NOT to cache**:
- User-specific realtime data
- Rapidly changing information
- Large objects (> 1MB)
- Sensitive data (PII, secrets)

### Multi-Layer Caching Architecture

```
Request
  │
  ▼
┌─────────────┐
│ In-Memory   │  <-- Fastest (microseconds)
│ (LRU Cache) │
└──────┬──────┘
       │ miss
       ▼
┌─────────────┐
│   Redis     │  <-- Fast (milliseconds)
│ (Distributed)│
└──────┬──────┘
       │ miss
       ▼
┌─────────────┐
│  Database   │  <-- Slow (tens of milliseconds)
│ (PostgreSQL)│
└──────┬──────┘
       │ miss
       ▼
┌─────────────┐
│ Recompute   │  <-- Slowest (seconds)
└─────────────┘
```

### Implementation: Multi-Layer Cache

```python
# code-examples/chapter-07-performance/caching/cache.py

from functools import wraps
import redis
import json
import hashlib
from typing import Any, Optional, Callable
from cachetools import LRUCache
import structlog

logger = structlog.get_logger()


class MultiLayerCache:
    """
    Multi-layer cache with L1 (in-memory) and L2 (Redis).

    L1: Fast, local, limited size (LRU eviction)
    L2: Shared across instances, larger, slightly slower
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        l1_maxsize: int = 1000,
        default_ttl: int = 300,
    ):
        self.redis = redis_client
        self.l1_cache = LRUCache(maxsize=l1_maxsize)
        self.default_ttl = default_ttl

        # Cache hit/miss tracking
        self.hits = {"l1": 0, "l2": 0}
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache (L1 first, then L2).
        """
        # Try L1 (in-memory)
        if key in self.l1_cache:
            self.hits["l1"] += 1
            logger.debug("cache_hit", layer="l1", key=key)
            return self.l1_cache[key]

        # Try L2 (Redis)
        value = self.redis.get(f"cache:{key}")
        if value:
            self.hits["l2"] += 1
            logger.debug("cache_hit", layer="l2", key=key)

            # Promote to L1
            deserialized = json.loads(value)
            self.l1_cache[key] = deserialized
            return deserialized

        # Cache miss
        self.misses += 1
        logger.debug("cache_miss", key=key)
        return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """
        Set value in both L1 and L2 caches.
        """
        ttl = ttl or self.default_ttl

        # Set in L1
        self.l1_cache[key] = value

        # Set in L2
        serialized = json.dumps(value)
        self.redis.set(f"cache:{key}", serialized, ex=ttl)

        logger.debug("cache_set", key=key, ttl=ttl)

    def delete(self, key: str):
        """Delete from both caches."""
        if key in self.l1_cache:
            del self.l1_cache[key]

        self.redis.delete(f"cache:{key}")

        logger.debug("cache_delete", key=key)

    def get_stats(self) -> dict:
        """Get cache performance statistics."""
        total_requests = sum(self.hits.values()) + self.misses
        hit_rate = (
            sum(self.hits.values()) / total_requests
            if total_requests > 0
            else 0
        )

        return {
            "l1_hits": self.hits["l1"],
            "l2_hits": self.hits["l2"],
            "misses": self.misses,
            "total_requests": total_requests,
            "hit_rate": hit_rate,
        }


def cached(
    cache: MultiLayerCache,
    ttl: Optional[int] = None,
    key_func: Optional[Callable] = None,
):
    """
    Decorator to cache function results.

    Usage:
        @cached(cache, ttl=300)
        def expensive_function(arg1, arg2):
            # ... expensive computation
            return result
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default: hash function name + arguments
                key_data = f"{func.__name__}:{args}:{kwargs}"
                cache_key = hashlib.md5(key_data.encode()).hexdigest()

            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result

            # Cache miss - compute result
            result = func(*args, **kwargs)

            # Store in cache
            cache.set(cache_key, result, ttl=ttl)

            return result

        return wrapper
    return decorator


# Example usage
if __name__ == "__main__":
    import time

    redis_client = redis.Redis(host="localhost", decode_responses=True)
    cache = MultiLayerCache(redis_client)

    @cached(cache, ttl=300)
    def expensive_computation(n: int) -> int:
        """Simulate expensive computation."""
        time.sleep(2)  # Simulate 2-second computation
        return n * n

    # First call - cache miss (2 seconds)
    print("First call...")
    start = time.time()
    result = expensive_computation(42)
    print(f"Result: {result}, Time: {time.time() - start:.3f}s")

    # Second call - L1 hit (microseconds)
    print("\nSecond call (L1 hit)...")
    start = time.time()
    result = expensive_computation(42)
    print(f"Result: {result}, Time: {time.time() - start:.6f}s")

    # Clear L1, keep L2
    cache.l1_cache.clear()

    # Third call - L2 hit (milliseconds)
    print("\nThird call (L2 hit)...")
    start = time.time()
    result = expensive_computation(42)
    print(f"Result: {result}, Time: {time.time() - start:.6f}s")

    # Print cache stats
    print("\nCache statistics:")
    print(cache.get_stats())
```

### Caching Agent Outputs

```python
# code-examples/chapter-07-performance/caching/cached_agent.py

import anthropic
from cache import MultiLayerCache, cached
import hashlib


class CachedAgent:
    """
    Agent with aggressive caching for performance.

    Caches:
    - LLM responses for identical inputs
    - Tool execution results
    - Search results
    - Database queries
    """

    def __init__(self, api_key: str, cache: MultiLayerCache):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.cache = cache

    def chat(self, user_id: str, message: str) -> str:
        """
        Process chat message with caching.
        """
        # Check if we've seen this exact message before
        cache_key = self._message_cache_key(message)
        cached_response = self.cache.get(cache_key)

        if cached_response:
            logger.info(
                "cached_response_served",
                user_id=user_id,
                message_hash=cache_key[:8],
            )
            return cached_response

        # Not cached - call LLM
        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            messages=[{"role": "user", "content": message}],
        )

        response_text = next(
            (block.text for block in response.content if hasattr(block, "text")),
            ""
        )

        # Cache response (5-minute TTL for most queries)
        self.cache.set(cache_key, response_text, ttl=300)

        return response_text

    def _message_cache_key(self, message: str) -> str:
        """Generate cache key from message."""
        return hashlib.md5(message.encode()).hexdigest()

    @cached(cache, ttl=3600)  # Cache for 1 hour
    def search_knowledge_base(self, query: str) -> list[str]:
        """
        Search knowledge base (cached).

        Identical queries return cached results.
        """
        # Simulate knowledge base search
        results = perform_search(query)  # Expensive operation
        return results

    @cached(cache, ttl=600)  # Cache for 10 minutes
    def get_user_context(self, user_id: str) -> dict:
        """
        Get user context from database (cached).
        """
        # Simulate database query
        context = fetch_user_from_db(user_id)  # Slow database query
        return context
```

### Cache Invalidation

**Strategies**:

1. **Time-based (TTL)**: Cache expires after N seconds
   ```python
   cache.set(key, value, ttl=300)  # 5-minute TTL
   ```

2. **Event-based**: Invalidate when data changes
   ```python
   def update_user(user_id: str, data: dict):
       # Update database
       db.update_user(user_id, data)

       # Invalidate cache
       cache.delete(f"user:{user_id}")
   ```

3. **LRU eviction**: Automatically evict least recently used
   ```python
   cache = LRUCache(maxsize=1000)  # Keep 1000 items max
   ```

**Production wisdom**: "There are only two hard problems in computer science: cache invalidation and naming things." —Phil Karlton

---

## Async/Await Patterns

### Principle 2: Don't Wait When You Don't Have To

**Synchronous (sequential)**:
```python
def handle_request(user_id: str):
    user = get_user(user_id)           # 50ms
    preferences = get_preferences(user_id)  # 50ms
    history = get_history(user_id)     # 100ms
    # Total: 200ms
```

**Asynchronous (parallel)**:
```python
async def handle_request(user_id: str):
    user, preferences, history = await asyncio.gather(
        get_user(user_id),           # 50ms \
        get_preferences(user_id),    # 50ms  } parallel
        get_history(user_id),        # 100ms/
    )
    # Total: 100ms (time of slowest operation)
```

**Improvement**: 2x faster!

### Implementation: Async Agent

```python
# code-examples/chapter-07-performance/async-agent/agent.py

import anthropic
import asyncio
import httpx
from typing import List, Dict
import structlog

logger = structlog.get_logger()


class AsyncAgent:
    """
    Agent that uses async/await for concurrent I/O operations.

    Benefits:
    - Parallel tool execution
    - Concurrent API calls
    - Non-blocking I/O
    """

    def __init__(self, api_key: str):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.http_client = httpx.AsyncClient()

    async def chat(self, user_id: str, message: str) -> str:
        """
        Process chat message with concurrent operations.
        """
        # Fetch user context in parallel
        user_data, conversation_history = await asyncio.gather(
            self.get_user_context(user_id),
            self.get_conversation_history(user_id),
        )

        # Build messages
        messages = conversation_history + [
            {"role": "user", "content": message}
        ]

        # Call Claude
        response = await self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            messages=messages,
            tools=self.get_tools(),
        )

        # Handle tool calls concurrently if needed
        if response.stop_reason == "tool_use":
            tool_results = await self.execute_tools_parallel(response.content)
            # ... continue conversation with results

        response_text = next(
            (block.text for block in response.content if hasattr(block, "text")),
            ""
        )

        return response_text

    async def execute_tools_parallel(self, content: List) -> List[Dict]:
        """
        Execute multiple tool calls in parallel.

        If agent needs to call 3 tools, execute all 3 concurrently.
        """
        tool_calls = [block for block in content if block.type == "tool_use"]

        if not tool_calls:
            return []

        # Execute all tools in parallel
        results = await asyncio.gather(*[
            self.execute_single_tool(tool_call.name, tool_call.input)
            for tool_call in tool_calls
        ])

        # Format results
        return [
            {
                "type": "tool_result",
                "tool_use_id": tool_call.id,
                "content": result,
            }
            for tool_call, result in zip(tool_calls, results)
        ]

    async def execute_single_tool(self, tool_name: str, tool_input: Dict) -> str:
        """Execute a single tool."""
        if tool_name == "search_web":
            return await self.search_web(tool_input["query"])
        elif tool_name == "get_weather":
            return await self.get_weather(tool_input["location"])
        elif tool_name == "database_query":
            return await self.query_database(tool_input["query"])
        else:
            return f"Unknown tool: {tool_name}"

    async def search_web(self, query: str) -> str:
        """Search web (async HTTP call)."""
        response = await self.http_client.get(
            f"https://api.search.com/search?q={query}"
        )
        return response.text

    async def get_weather(self, location: str) -> str:
        """Get weather (async HTTP call)."""
        response = await self.http_client.get(
            f"https://api.weather.com/weather?location={location}"
        )
        return response.text

    async def query_database(self, query: str) -> str:
        """Query database (async database call)."""
        # Using async database driver (e.g., asyncpg for PostgreSQL)
        result = await db.fetch(query)
        return str(result)

    async def get_user_context(self, user_id: str) -> Dict:
        """Get user context from database."""
        await asyncio.sleep(0.05)  # Simulate 50ms DB query
        return {"user_id": user_id, "name": "Alice"}

    async def get_conversation_history(self, user_id: str) -> List[Dict]:
        """Get conversation history from storage."""
        await asyncio.sleep(0.1)  # Simulate 100ms query
        return []

    def get_tools(self) -> List[Dict]:
        """Tool definitions."""
        return [
            {
                "name": "search_web",
                "description": "Search the web",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "get_weather",
                "description": "Get weather for location",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string"},
                    },
                    "required": ["location"],
                },
            },
        ]


# Example usage
async def main():
    import os
    from dotenv import load_dotenv

    load_dotenv()

    agent = AsyncAgent(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # Process multiple requests concurrently
    requests = [
        agent.chat("user1", "What's the weather in SF?"),
        agent.chat("user2", "Search for Python tutorials"),
        agent.chat("user3", "What's 25 * 17?"),
    ]

    # All three process in parallel
    responses = await asyncio.gather(*requests)

    for i, response in enumerate(responses, 1):
        print(f"Response {i}: {response}")


if __name__ == "__main__":
    asyncio.run(main())
```

### Async Benefits

**Sequential execution** (3 requests):
```
Request 1: ████████ (3s)
Request 2:         ████████ (3s)
Request 3:                 ████████ (3s)
Total: 9 seconds
```

**Parallel execution** (3 requests):
```
Request 1: ████████ (3s)
Request 2: ████████ (3s)
Request 3: ████████ (3s)
Total: 3 seconds
```

**Improvement**: 3x throughput!

---

## Connection Pooling and HTTP/2

### Principle 3: Reuse Expensive Resources

**Problem**: Creating connections is slow.

```python
# BAD: Create new connection for each request
def make_api_call():
    client = httpx.Client()
    response = client.get("https://api.example.com/data")
    client.close()
    # Connection overhead: 50-200ms per call
```

**Solution**: Connection pooling.

```python
# GOOD: Reuse connections
client = httpx.Client()  # Create once

def make_api_call():
    response = client.get("https://api.example.com/data")
    # Connection overhead: 0ms (connection reused)
```

### HTTP/2 Multiplexing

**HTTP/1.1**: One request per connection
```
Connection 1: Request A ████████
Connection 2: Request B ████████
Connection 3: Request C ████████
```

**HTTP/2**: Multiple requests per connection
```
Connection 1: Request A ████████
              Request B ████████
              Request C ████████
```

**Benefits**:
- Fewer connections
- Lower overhead
- Better performance

### Implementation: Connection Pool

```python
# code-examples/chapter-07-performance/connection-pooling/agent.py

import httpx
import anthropic
from typing import Optional


class PooledAgent:
    """
    Agent with connection pooling for optimal performance.
    """

    def __init__(
        self,
        api_key: str,
        max_connections: int = 100,
        max_keepalive_connections: int = 20,
    ):
        # Anthropic client (already uses connection pooling internally)
        self.claude_client = anthropic.Anthropic(api_key=api_key)

        # HTTP client with connection pooling
        self.http_client = httpx.Client(
            http2=True,  # Enable HTTP/2
            limits=httpx.Limits(
                max_connections=max_connections,
                max_keepalive_connections=max_keepalive_connections,
            ),
            timeout=httpx.Timeout(10.0),
        )

    def chat(self, message: str) -> str:
        """Process message using pooled connections."""
        # Claude API call (uses pooled connection)
        response = self.claude_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            messages=[{"role": "user", "content": message}],
        )

        return next(
            (block.text for block in response.content if hasattr(block, "text")),
            ""
        )

    def call_external_api(self, url: str) -> str:
        """Call external API using pooled HTTP connection."""
        response = self.http_client.get(url)
        return response.text

    def __del__(self):
        """Clean up connections on shutdown."""
        self.http_client.close()
```

---

## Streaming Responses

### Principle 4: Perceived Performance Matters

**Without streaming**:
- User waits 5 seconds
- Response appears all at once
- **Perceived latency**: 5 seconds

**With streaming**:
- User sees first tokens after 0.5 seconds
- Response streams gradually
- **Perceived latency**: 0.5 seconds

**Improvement**: 10x better perceived performance!

### Implementation: Streaming Agent

```python
# code-examples/chapter-07-performance/streaming/agent.py

import anthropic
from typing import Iterator


class StreamingAgent:
    """
    Agent that streams responses for better perceived performance.
    """

    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)

    def chat_stream(self, message: str) -> Iterator[str]:
        """
        Stream chat response token by token.

        Yields response text as it's generated.
        """
        with self.client.messages.stream(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            messages=[{"role": "user", "content": message}],
        ) as stream:
            for text in stream.text_stream:
                yield text


# FastAPI endpoint for streaming
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI()
agent = StreamingAgent(api_key=os.getenv("ANTHROPIC_API_KEY"))


@app.post("/chat/stream")
def chat_stream(message: str):
    """
    Streaming chat endpoint.

    Returns Server-Sent Events (SSE) stream.
    """
    def generate():
        for token in agent.chat_stream(message):
            yield f"data: {token}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
    )


# Client usage (JavaScript)
"""
const eventSource = new EventSource('/chat/stream?message=Hello');

eventSource.onmessage = (event) => {
    document.getElementById('response').textContent += event.data;
};
"""
```

---

## Load Testing and Profiling

### Finding Bottlenecks

**Tools**:
- **cProfile**: Python profiler
- **py-spy**: Sampling profiler (production-safe)
- **Locust**: Load testing
- **Apache Bench (ab)**: Simple HTTP load testing

### Profiling Example

```python
# Profile a function
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Run code to profile
agent.chat("user123", "What is 2 + 2?")

profiler.disable()

# Print statistics
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(10)  # Top 10 slowest functions
```

**Output**:
```
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
        1    0.001    0.001    5.234    5.234 agent.py:45(chat)
        1    0.002    0.002    4.850    4.850 anthropic/client.py:120(create)
        3    0.100    0.033    0.350    0.117 database.py:50(query)
        1    0.015    0.015    0.015    0.015 json.py:230(dumps)
```

**Analysis**: API call takes 4.85s (93% of time). Database queries take 0.35s. Focus optimization there.

### Load Testing with Locust

```python
# locustfile.py
from locust import HttpUser, task, between

class AgentUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def chat(self):
        self.client.post("/chat", json={
            "user_id": "user123",
            "message": "What is the weather?"
        })


# Run load test
# locust -f locustfile.py --host=http://localhost:8000
# Visit http://localhost:8089 to start test
```

**Metrics to track**:
- Requests per second (RPS)
- Response time (p50, p95, p99)
- Error rate
- Throughput

---

## Performance Optimization Checklist

Before deploying to production:

### Caching
- [ ] Implement multi-layer caching (L1 + L2)
- [ ] Cache expensive computations
- [ ] Cache external API calls
- [ ] Cache database queries
- [ ] Set appropriate TTLs
- [ ] Monitor cache hit rate (target > 80%)

### Concurrency
- [ ] Use async/await for I/O operations
- [ ] Parallelize independent operations
- [ ] Use connection pooling
- [ ] Enable HTTP/2 where supported

### Latency
- [ ] Profile hot paths
- [ ] Optimize database queries (indexes, query optimization)
- [ ] Reduce payload sizes
- [ ] Enable compression
- [ ] Use CDN for static assets
- [ ] Stream responses when possible

### Monitoring
- [ ] Track response time (p50, p95, p99)
- [ ] Monitor cache hit rate
- [ ] Track database query time
- [ ] Monitor external API latency
- [ ] Set up performance alerts

### Testing
- [ ] Load test at expected traffic
- [ ] Stress test at 10x traffic
- [ ] Profile under load
- [ ] Test cache warming
- [ ] Verify auto-scaling triggers

---

## Performance Incident: The Slow Death

### What Happened

An agent platform was handling 1,000 requests/hour successfully. Over 3 months, response times gradually increased:

- **Month 1**: p95 = 2.0s
- **Month 2**: p95 = 4.5s
- **Month 3**: p95 = 12.0s

**Impact**: User complaints, increased abandonment rate, negative reviews.

**Root cause**: Conversation history accumulation. No history trimming meant agents were processing larger and larger prompts over time.

### The Fix

1. **Immediate**:
   - Implemented conversation history trimming (keep last 10 messages)
   - Cleared old conversation data

2. **Long-term**:
   - Added conversation history summarization
   - Monitored prompt token counts
   - Set max conversation length
   - Implemented cache warming for frequent queries

**Result**: p95 latency dropped from 12s → 2.8s (4.3x improvement).

---

## Key Takeaways

1. **Measure first**: Profile before optimizing
2. **Cache aggressively**: Multi-layer caching for common operations
3. **Parallelize I/O**: Use async/await for concurrent operations
4. **Pool connections**: Reuse expensive resources
5. **Stream responses**: Better perceived performance
6. **Monitor continuously**: Performance degrades over time
7. **Test at scale**: Load test regularly
8. **Optimize hot paths**: 80/20 rule applies

**Production wisdom**: "Premature optimization is the root of all evil, but not optimizing production code is also evil." —Adapted from Donald Knuth

---

## Part II: Complete

Congratulations! You've completed **Part II: Scaling and Performance**:

✅ **Chapter 5**: Cost Optimization (88% cost reduction)
✅ **Chapter 6**: Scaling Agent Systems (20x throughput improvement)
✅ **Chapter 7**: Performance Optimization (4.3x latency improvement)

Your agent is now:
- **Cost-effective**: Comprehensive cost tracking and optimization
- **Scalable**: Horizontally scalable with auto-scaling
- **Fast**: Cached, async, and optimized for performance

**Next**: Part III will cover Operations and Deployment—getting your agent into production safely and keeping it running reliably.
