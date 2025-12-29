# Chapter 7: Performance Optimization - Code Examples

This directory contains production-ready code examples for optimizing AI agent performance.

## Overview

The examples demonstrate:

1. **caching/** - Multi-layer caching (L1 in-memory + L2 Redis)
2. **async-agent/** - Async/await patterns for concurrency
3. **connection-pooling/** - Connection reuse and HTTP/2
4. **streaming/** - Streaming responses for better UX
5. **complete/** - Fully optimized agent with all techniques

## Performance Improvements Demonstrated

| Optimization | Improvement |
|--------------|-------------|
| Multi-layer caching | 10-100x faster for repeated queries |
| Async/await patterns | 2-3x throughput improvement |
| Connection pooling | 50-200ms saved per request |
| Response streaming | 10x better perceived latency |
| **Combined** | **4.3x latency reduction** |

## Prerequisites

- Python 3.11+
- Redis
- Anthropic API key

## Quick Start

### 1. Install Dependencies

```bash
cd caching
python -m venv .venv
source .venv/bin/activate
pip install anthropic redis cachetools structlog python-dotenv httpx
```

### 2. Start Redis

```bash
docker run -d -p 6379:6379 redis:7-alpine
```

### 3. Run Examples

Each directory contains standalone examples you can run directly.

## Example 1: Multi-Layer Caching

**Location**: `caching/`

**What it demonstrates**:
- L1 cache (in-memory LRU)
- L2 cache (Redis distributed)
- Cache decorator for easy adoption
- Cache hit/miss tracking
- Performance statistics

**Run it**:
```bash
cd caching
python cache.py
```

**Expected output**:
```
First call...
Result: 1764, Time: 2.003s  (cache miss)

Second call (L1 hit)...
Result: 1764, Time: 0.000042s  (47,000x faster!)

Third call (L2 hit)...
Result: 1764, Time: 0.002s  (1,000x faster!)

Cache statistics:
{
  'l1_hits': 1,
  'l2_hits': 1,
  'misses': 1,
  'total_requests': 3,
  'hit_rate': 0.6667
}
```

**Production usage**:
```python
from cache import MultiLayerCache, cached

# Initialize cache
cache = MultiLayerCache(redis_client)

# Use decorator to cache function results
@cached(cache, ttl=300)
def expensive_llm_call(prompt: str):
    response = client.messages.create(...)
    return response

# First call: cache miss (slow)
result = expensive_llm_call("What is Python?")

# Subsequent calls: cache hit (fast!)
result = expensive_llm_call("What is Python?")
```

## Example 2: Async Agent

**Location**: `async-agent/`

**What it demonstrates**:
- Async/await for concurrent I/O
- Parallel tool execution
- Concurrent API calls
- Non-blocking operations

**Sequential vs Async**:
```python
# Sequential (slow)
def fetch_data():
    user = get_user()        # 50ms
    prefs = get_prefs()      # 50ms
    history = get_history()  # 100ms
    # Total: 200ms

# Async (fast)
async def fetch_data():
    user, prefs, history = await asyncio.gather(
        get_user(),        # 50ms  \
        get_prefs(),       # 50ms   } parallel
        get_history(),     # 100ms /
    )
    # Total: 100ms (2x faster!)
```

**Run it**:
```bash
cd async-agent
python agent.py
```

**Benefits**:
- **2-3x throughput**: Handle more requests with same hardware
- **Lower latency**: Parallel operations complete faster
- **Better resource usage**: CPU active while waiting for I/O

## Example 3: Connection Pooling

**Location**: `connection-pooling/`

**What it demonstrates**:
- HTTP connection pooling
- HTTP/2 multiplexing
- Connection reuse
- Resource cleanup

**Without pooling**:
```
Request 1: Create connection (100ms) + API call (500ms) = 600ms
Request 2: Create connection (100ms) + API call (500ms) = 600ms
Request 3: Create connection (100ms) + API call (500ms) = 600ms
Total: 1,800ms
```

**With pooling**:
```
Request 1: Create connection (100ms) + API call (500ms) = 600ms
Request 2: Reuse connection (0ms) + API call (500ms) = 500ms
Request 3: Reuse connection (0ms) + API call (500ms) = 500ms
Total: 1,600ms (11% faster)
```

**Configuration**:
```python
client = httpx.Client(
    http2=True,  # Enable HTTP/2
    limits=httpx.Limits(
        max_connections=100,        # Total connections
        max_keepalive_connections=20,  # Persistent connections
    ),
    timeout=httpx.Timeout(10.0),
)
```

## Example 4: Streaming Responses

**Location**: `streaming/`

**What it demonstrates**:
- Server-Sent Events (SSE)
- Token-by-token streaming
- Better perceived performance

**User experience**:

**Without streaming**:
```
User: "Write me a story"
[5 seconds of nothing...]
Agent: [entire story appears at once]
Perceived latency: 5 seconds
```

**With streaming**:
```
User: "Write me a story"
[0.5 seconds...]
Agent: "Once upon a time..."
[tokens appear gradually]
Perceived latency: 0.5 seconds (10x better!)
```

## Performance Benchmarks

### Caching Impact

| Scenario | Without Cache | With Cache | Improvement |
|----------|---------------|------------|-------------|
| Identical query | 3,000ms | 0.05ms | 60,000x |
| Similar query | 3,000ms | 3,000ms | 1x |
| Cache hit rate: 30% | 3,000ms avg | 900ms avg | 3.3x |

### Async Impact

| Concurrent Operations | Sequential | Async | Improvement |
|----------------------|------------|-------|-------------|
| 3 API calls | 900ms | 300ms | 3x |
| 5 database queries | 500ms | 100ms | 5x |
| 10 file reads | 1,000ms | 100ms | 10x |

### Connection Pooling Impact

| Requests | No Pooling | With Pooling | Improvement |
|----------|------------|--------------|-------------|
| 10 | 6,000ms | 5,100ms | 15% |
| 100 | 60,000ms | 51,000ms | 15% |
| 1,000 | 600,000ms | 510,000ms | 15% |

## Profiling Your Agent

### Using cProfile

```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Run your agent
agent.chat("user123", "Hello!")

profiler.disable()

# Print top 10 slowest functions
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(10)
```

### Using py-spy (Production-Safe)

```bash
# Profile running Python process
py-spy record -o profile.svg --pid <PID>

# Profile for 60 seconds
py-spy record -o profile.svg --duration 60 -- python agent.py

# View flame graph
open profile.svg
```

## Load Testing

### With Locust

```python
# locustfile.py
from locust import HttpUser, task, between
import time

class AgentUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def chat(self):
        response = self.client.post("/chat", json={
            "user_id": f"user{self.user_id}",
            "message": "What is the weather?"
        })

# Run load test
# locust -f locustfile.py --host=http://localhost:8000 --users 100 --spawn-rate 10
```

**Metrics to monitor**:
- **RPS** (requests per second)
- **Response time**: p50, p95, p99
- **Error rate**: % of failed requests
- **Throughput**: MB/s

### With Apache Bench

```bash
# Simple load test: 1000 requests, 10 concurrent
ab -n 1000 -c 10 -p request.json -T application/json \
   http://localhost:8000/chat

# Results
# Requests per second: 45.23 [#/sec]
# Time per request: 221.05 [ms] (mean)
# Time per request: 22.11 [ms] (mean, across all concurrent requests)
```

## Optimization Workflow

1. **Measure baseline**
   ```bash
   # Run load test
   locust -f locustfile.py --host=http://localhost:8000

   # Note p95 latency: 5,234ms
   ```

2. **Profile to find bottlenecks**
   ```bash
   py-spy record -o before.svg --duration 60 -- python agent.py
   ```

3. **Implement optimizations**
   - Add caching for expensive operations
   - Make I/O operations async
   - Enable connection pooling

4. **Measure improvement**
   ```bash
   # Run load test again
   locust -f locustfile.py --host=http://localhost:8000

   # Note p95 latency: 1,213ms (4.3x improvement!)
   ```

5. **Profile again**
   ```bash
   py-spy record -o after.svg --duration 60 -- python agent.py

   # Compare flame graphs
   ```

## Production Monitoring

### Key Metrics

```python
from prometheus_client import Histogram, Counter, Gauge

# Response time
response_time = Histogram(
    "agent_response_seconds",
    "Agent response time",
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
)

# Cache hit rate
cache_hits = Counter("agent_cache_hits_total", "Cache hits")
cache_misses = Counter("agent_cache_misses_total", "Cache misses")

# Active connections
active_connections = Gauge("agent_active_connections", "Active HTTP connections")
```

### Grafana Dashboard

**Key panels**:
1. Response time (p50, p95, p99) - line chart
2. Cache hit rate - gauge (target > 80%)
3. Requests per second - line chart
4. Error rate - line chart
5. Active connections - gauge

## Troubleshooting

### Problem: Cache hit rate < 50%

**Symptoms**: Lots of cache misses, slow performance

**Solutions**:
1. Increase cache size (L1 maxsize, Redis memory)
2. Increase TTL for stable data
3. Pre-warm cache with common queries
4. Review cache key generation (ensure consistency)

### Problem: High latency despite caching

**Symptoms**: Cache hit rate good, but still slow

**Check**:
1. Profile to find new bottlenecks
2. Check database query performance
3. Look for N+1 query problems
4. Review tool execution time
5. Check external API latency

**Solutions**:
- Optimize database queries (add indexes)
- Batch database queries
- Make API calls async
- Add more caching layers

### Problem: Memory usage growing

**Symptoms**: Agent using more and more memory

**Causes**:
1. Unbounded cache growth
2. Connection leaks
3. Conversation history accumulation

**Solutions**:
- Set max cache size (LRU eviction)
- Implement connection cleanup
- Trim conversation history
- Monitor memory usage

## Production Checklist

Performance optimization checklist:

- [ ] Implement multi-layer caching
- [ ] Cache hit rate > 80% for common queries
- [ ] Use async/await for I/O operations
- [ ] Enable connection pooling
- [ ] Configure HTTP/2
- [ ] Stream responses for long outputs
- [ ] Profile under realistic load
- [ ] Load test at expected traffic
- [ ] Set performance SLOs (e.g., p95 < 2s)
- [ ] Monitor response times continuously
- [ ] Alert on performance degradation
- [ ] Regular performance regression testing

## Best Practices

1. **Measure before optimizing**
   - Profile to find actual bottlenecks
   - Don't guess where time is spent

2. **Optimize the common case**
   - 80/20 rule: 80% of requests hit 20% of code
   - Focus on hot paths

3. **Cache aggressively, invalidate carefully**
   - Cache everything you can
   - Set appropriate TTLs
   - Invalidate when data changes

4. **Parallelize I/O**
   - Use async/await for all I/O operations
   - Don't wait sequentially when you can wait in parallel

5. **Monitor continuously**
   - Performance degrades over time
   - Regular load testing
   - Alert on regressions

## Performance Targets

**Good production targets**:
- **p50 latency**: < 1 second
- **p95 latency**: < 2 seconds
- **p99 latency**: < 5 seconds
- **Cache hit rate**: > 80%
- **Error rate**: < 0.1%
- **Throughput**: > 10 RPS per worker

## Resources

- [Python asyncio documentation](https://docs.python.org/3/library/asyncio.html)
- [HTTPX documentation](https://www.python-httpx.org/)
- [Redis caching patterns](https://redis.io/docs/manual/patterns/)
- [Locust load testing](https://locust.io/)
- [py-spy profiler](https://github.com/benfred/py-spy)

## Next Steps

1. Profile your current agent
2. Identify top 3 bottlenecks
3. Implement appropriate optimizations
4. Measure improvement
5. Iterate until performance targets met

**Remember**: Premature optimization is bad, but not optimizing production code is worse!
