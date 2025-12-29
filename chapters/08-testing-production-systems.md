# Chapter 8: Testing Production Systems

## Introduction: The Deployment That Broke Everything

It was a Friday afternoon when Sarah deployed what seemed like a simple update: adding a new tool to the customer support agent. The code looked good, unit tests passed, and it worked perfectly in development.

**5 minutes after deployment**:
- Customer conversations started failing
- Error rate spiked to 15%
- Support tickets flooding in
- Emergency rollback initiated

**What went wrong?**

The new tool had a dependency conflict that only manifested in production. The tool worked in isolation (unit tests passed) but broke when integrated with the production system. There were no integration tests, no load tests, and no canary deployment to catch the issue.

**The cost**:
- 2 hours of downtime
- 500 failed customer interactions
- Emergency weekend work
- Loss of customer trust

**What should have happened**: Comprehensive testing at every level would have caught this before it reached production.

This is the testing challenge: **Code that works in development can fail catastrophically in production without proper testing.**

---

## Why Testing Matters in Production

Production AI agents are complex systems with many failure modes:

- **LLM API failures**: Rate limits, timeouts, model errors
- **Tool execution failures**: External APIs down, database errors
- **Integration issues**: Components that work alone but fail together
- **Scale issues**: Works with 10 users, breaks with 1,000
- **Data issues**: Edge cases in real user data
- **Performance degradation**: Slow responses under load

**Production reality**: You can't test everything, but you must test the critical paths.

### The Testing Pyramid for AI Agents

```
         ▲
        / \
       /   \
      / E2E \        Few, slow, expensive
     /-------\       Test critical user journeys
    /  Inte-  \
   / gration   \     Moderate number
  /-------------\    Test component interactions
 /   Unit Tests  \
/─────────────────\  Many, fast, cheap
                     Test individual functions
```

**Testing strategy**:
1. **Many unit tests**: Fast, cheap, test individual components
2. **Some integration tests**: Test components working together
3. **Few end-to-end tests**: Test complete user journeys
4. **Load tests**: Verify performance at scale
5. **Chaos tests**: Verify resilience under failure

---

## Unit Testing with Mocks

### Principle 1: Test Components in Isolation

**What to unit test**:
- Tool execution logic
- Prompt building
- Response parsing
- Error handling
- Business logic

**What NOT to unit test**:
- LLM behavior (non-deterministic)
- External API responses
- Database queries (use integration tests)

### Implementation: Unit Testing Agent Components

```python
# code-examples/chapter-08-testing/unit-tests/test_agent.py

import pytest
from unittest.mock import Mock, patch, MagicMock
from agent import Agent, ToolExecutor
import anthropic


class TestToolExecutor:
    """Unit tests for tool execution logic."""

    def test_calculate_tool_success(self):
        """Test successful calculation."""
        executor = ToolExecutor()
        result = executor.execute("calculate", {"expression": "2 + 2"})

        assert result == "4"

    def test_calculate_tool_invalid_expression(self):
        """Test calculation with invalid expression."""
        executor = ToolExecutor()
        result = executor.execute("calculate", {"expression": "invalid"})

        assert "error" in result.lower()

    def test_search_web_mock(self):
        """Test web search with mocked HTTP client."""
        executor = ToolExecutor()

        # Mock HTTP client
        with patch('httpx.Client.get') as mock_get:
            mock_response = Mock()
            mock_response.text = "Search results for Python"
            mock_get.return_value = mock_response

            result = executor.execute("search_web", {"query": "Python"})

            assert "Search results" in result
            mock_get.assert_called_once()

    def test_unknown_tool(self):
        """Test handling of unknown tool."""
        executor = ToolExecutor()
        result = executor.execute("nonexistent_tool", {})

        assert "unknown" in result.lower() or "not found" in result.lower()


class TestAgent:
    """Unit tests for agent logic."""

    @pytest.fixture
    def mock_anthropic_client(self):
        """Fixture to create mocked Anthropic client."""
        with patch('anthropic.Anthropic') as mock:
            # Mock successful response
            mock_response = Mock()
            mock_response.content = [
                Mock(
                    type="text",
                    text="The answer is 42"
                )
            ]
            mock_response.stop_reason = "end_turn"
            mock_response.usage = Mock(
                input_tokens=100,
                output_tokens=50
            )

            mock.return_value.messages.create.return_value = mock_response
            yield mock

    def test_chat_simple_response(self, mock_anthropic_client):
        """Test simple chat interaction."""
        agent = Agent(api_key="test-key")

        response = agent.chat("user123", "What is 2+2?")

        assert response == "The answer is 42"
        mock_anthropic_client.return_value.messages.create.assert_called_once()

    def test_chat_with_tool_use(self, mock_anthropic_client):
        """Test chat with tool execution."""
        # Mock tool use response
        mock_response = Mock()
        mock_response.content = [
            Mock(
                type="tool_use",
                id="tool_123",
                name="calculate",
                input={"expression": "2+2"}
            )
        ]
        mock_response.stop_reason = "tool_use"

        # Mock final response after tool execution
        mock_final = Mock()
        mock_final.content = [Mock(type="text", text="The result is 4")]
        mock_final.stop_reason = "end_turn"
        mock_final.usage = Mock(input_tokens=100, output_tokens=20)

        mock_anthropic_client.return_value.messages.create.side_effect = [
            mock_response,
            mock_final
        ]

        agent = Agent(api_key="test-key")
        response = agent.chat("user123", "Calculate 2+2")

        assert "result is 4" in response.lower()

    def test_conversation_history_management(self):
        """Test that conversation history is properly trimmed."""
        agent = Agent(api_key="test-key", max_history=5)

        # Simulate 10 messages
        messages = [{"role": "user", "content": f"Message {i}"} for i in range(10)]

        trimmed = agent._trim_history(messages)

        assert len(trimmed) <= 5

    def test_error_handling_api_failure(self, mock_anthropic_client):
        """Test error handling when API fails."""
        mock_anthropic_client.return_value.messages.create.side_effect = \
            anthropic.APIError("API Error")

        agent = Agent(api_key="test-key")

        with pytest.raises(anthropic.APIError):
            agent.chat("user123", "Hello")


class TestPromptBuilder:
    """Unit tests for prompt building logic."""

    def test_build_prompt_with_context(self):
        """Test prompt building with user context."""
        from agent import PromptBuilder

        builder = PromptBuilder()
        prompt = builder.build(
            user_message="What's my order status?",
            user_context={"name": "Alice", "order_id": "12345"}
        )

        assert "Alice" in prompt
        assert "12345" in prompt

    def test_build_prompt_without_context(self):
        """Test prompt building without context."""
        from agent import PromptBuilder

        builder = PromptBuilder()
        prompt = builder.build(user_message="Hello")

        assert "Hello" in prompt
        assert prompt is not None


# Run tests
# pytest test_agent.py -v
```

### Mocking Best Practices

**1. Mock external dependencies, not your code**:
```python
# GOOD: Mock external API
with patch('httpx.Client.get') as mock_get:
    result = my_function()

# BAD: Mock your own function
with patch('my_module.my_function') as mock:
    result = my_function()  # You're testing the mock, not your code!
```

**2. Verify interactions**:
```python
mock_client.messages.create.assert_called_once_with(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello"}]
)
```

**3. Test error paths**:
```python
def test_api_timeout():
    """Verify agent handles timeouts gracefully."""
    with patch('anthropic.Anthropic') as mock:
        mock.return_value.messages.create.side_effect = TimeoutError()

        agent = Agent(api_key="test")
        with pytest.raises(TimeoutError):
            agent.chat("user", "Hello")
```

---

## Integration Testing

### Principle 2: Test Components Working Together

**What to integration test**:
- Agent + Real database
- Agent + Redis cache
- Agent + External APIs (staging)
- Queue + Workers
- Full request flow (API → Queue → Worker → Response)

### Implementation: Integration Tests

```python
# code-examples/chapter-08-testing/integration-tests/test_integration.py

import pytest
import redis
import anthropic
from agent import Agent
from queue_worker import Worker
import time
import os


@pytest.fixture(scope="module")
def redis_client():
    """Real Redis connection for integration tests."""
    client = redis.Redis(host="localhost", port=6379, decode_responses=True)

    # Verify Redis is available
    try:
        client.ping()
    except redis.ConnectionError:
        pytest.skip("Redis not available")

    yield client

    # Cleanup
    client.flushdb()


@pytest.fixture(scope="module")
def anthropic_client():
    """Real Anthropic client for integration tests."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")

    return anthropic.Anthropic(api_key=api_key)


class TestAgentWithRedis:
    """Integration tests for agent + Redis."""

    def test_conversation_persistence(self, redis_client, anthropic_client):
        """Test that conversations are persisted in Redis."""
        agent = Agent(
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            redis_client=redis_client
        )

        # First message
        response1 = agent.chat("user123", "My name is Alice")

        # Check Redis has conversation
        conv_key = "conv:user123"
        assert redis_client.exists(conv_key)

        # Second message (should have context)
        response2 = agent.chat("user123", "What's my name?")

        # Agent should remember the name
        assert "alice" in response2.lower()

    def test_cache_hit_performance(self, redis_client, anthropic_client):
        """Test that caching improves performance."""
        agent = Agent(
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            redis_client=redis_client
        )

        # First call (cache miss)
        start = time.time()
        response1 = agent.chat("user123", "What is 2+2?")
        first_call_time = time.time() - start

        # Second call (cache hit)
        start = time.time()
        response2 = agent.chat("user456", "What is 2+2?")  # Identical query
        second_call_time = time.time() - start

        # Cache hit should be significantly faster
        assert second_call_time < first_call_time * 0.5


class TestQueueWorkerIntegration:
    """Integration tests for queue-based architecture."""

    def test_job_processing_end_to_end(self, redis_client):
        """Test complete job flow: submit → queue → process → result."""
        from api import submit_job
        from worker import Worker

        # Submit job
        job_id = submit_job(
            redis_client,
            user_id="user123",
            message="What is the capital of France?",
            priority=1
        )

        assert job_id is not None

        # Start worker
        worker = Worker(
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            redis_client=redis_client
        )

        # Process one job
        worker.process_next_job()

        # Check job status
        job_data = redis_client.get(f"job:{job_id}")
        assert job_data is not None

        import json
        job = json.loads(job_data)

        assert job["status"] == "completed"
        assert "paris" in job["response"].lower()


class TestExternalAPIIntegration:
    """Integration tests with external APIs."""

    @pytest.mark.slow
    def test_weather_api_integration(self):
        """Test integration with weather API."""
        from tools import WeatherTool

        tool = WeatherTool(api_key=os.getenv("WEATHER_API_KEY"))
        result = tool.get_weather("San Francisco")

        assert result is not None
        assert "temperature" in result.lower() or "weather" in result.lower()

    @pytest.mark.slow
    def test_search_api_integration(self):
        """Test integration with search API."""
        from tools import SearchTool

        tool = SearchTool()
        results = tool.search("Python programming")

        assert len(results) > 0
        assert any("python" in r.lower() for r in results)


# Run integration tests
# pytest test_integration.py -v -m "not slow"  # Skip slow tests
# pytest test_integration.py -v  # Run all including slow tests
```

### Integration Testing Best Practices

1. **Use real dependencies** (Redis, databases, APIs)
2. **Clean up after tests** (flush Redis, delete test data)
3. **Mark slow tests** (`@pytest.mark.slow`)
4. **Use fixtures for setup/teardown**
5. **Test realistic scenarios**, not edge cases

---

## Load Testing

### Principle 3: Test at Scale

**Why load test**:
- Find performance bottlenecks
- Verify scalability
- Test auto-scaling behavior
- Identify resource limits
- Validate SLOs

### Implementation: Load Testing with Locust

```python
# code-examples/chapter-08-testing/load-tests/locustfile.py

from locust import HttpUser, task, between, events
import time
import json


class AgentUser(HttpUser):
    """
    Simulates a user interacting with the agent.

    Locust will spawn multiple instances of this class
    to simulate concurrent users.
    """

    wait_time = between(1, 3)  # Wait 1-3 seconds between requests

    def on_start(self):
        """Called when a simulated user starts."""
        self.user_id = f"user_{self.user_id}"

    @task(3)  # Weight: 3 (runs 3x more often than other tasks)
    def simple_question(self):
        """Ask a simple question."""
        response = self.client.post("/chat", json={
            "user_id": self.user_id,
            "message": "What is 2 + 2?",
        })

        if response.status_code == 202:
            # Async response - poll for result
            job_id = response.json()["job_id"]
            self.poll_for_result(job_id)

    @task(2)  # Weight: 2
    def complex_question(self):
        """Ask a complex question."""
        self.client.post("/chat", json={
            "user_id": self.user_id,
            "message": "Explain quantum computing in simple terms",
        })

    @task(1)  # Weight: 1 (least frequent)
    def search_query(self):
        """Ask a question that requires search."""
        self.client.post("/chat", json={
            "user_id": self.user_id,
            "message": "What are the latest AI developments?",
        })

    def poll_for_result(self, job_id, max_attempts=20):
        """Poll for async job result."""
        for _ in range(max_attempts):
            response = self.client.get(f"/chat/{job_id}")

            if response.status_code == 200:
                result = response.json()
                if result["status"] == "completed":
                    return result["response"]
                elif result["status"] == "failed":
                    return None

            time.sleep(0.5)

        return None


# Custom metrics
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when load test starts."""
    print("Load test starting...")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when load test stops."""
    print(f"Load test complete!")
    print(f"Total requests: {environment.stats.total.num_requests}")
    print(f"Failures: {environment.stats.total.num_failures}")
    print(f"RPS: {environment.stats.total.current_rps}")
    print(f"p95 latency: {environment.stats.total.get_response_time_percentile(0.95)}ms")


# Run load test:
# locust -f locustfile.py --host=http://localhost:8000
# Then visit http://localhost:8089 to configure and start test
```

### Load Test Scenarios

**1. Baseline test** (current capacity):
```bash
# 100 users, 10/second spawn rate
locust -f locustfile.py --host=http://localhost:8000 \
  --users 100 --spawn-rate 10 --run-time 5m
```

**2. Spike test** (sudden traffic spike):
```bash
# 0 → 1000 users in 10 seconds
locust -f locustfile.py --host=http://localhost:8000 \
  --users 1000 --spawn-rate 100 --run-time 2m
```

**3. Stress test** (find breaking point):
```bash
# Gradually increase load until failure
locust -f locustfile.py --host=http://localhost:8000 \
  --users 10000 --spawn-rate 50 --run-time 10m
```

**4. Soak test** (sustained load):
```bash
# Moderate load for extended period
locust -f locustfile.py --host=http://localhost:8000 \
  --users 500 --spawn-rate 10 --run-time 1h
```

### Interpreting Load Test Results

**Good signs**:
- ✅ p95 latency < 2 seconds
- ✅ Error rate < 0.1%
- ✅ Throughput scales linearly with workers
- ✅ No memory leaks (steady memory usage)

**Red flags**:
- 🚨 Latency increasing with load
- 🚨 Error rate > 1%
- 🚨 Memory usage growing continuously
- 🚨 Queue depth growing unbounded

---

## Chaos Engineering

### Principle 4: Test Failure Scenarios

**What to test**:
- API failures and timeouts
- Database connection loss
- Redis unavailability
- Worker crashes
- Network partitions

### Implementation: Chaos Tests

```python
# code-examples/chapter-08-testing/chaos-tests/test_chaos.py

import pytest
import redis
import time
from agent import Agent
from unittest.mock import patch
import anthropic


class TestAPIFailures:
    """Test agent behavior when Anthropic API fails."""

    def test_api_timeout_with_retry(self):
        """Test that agent retries on timeout."""
        agent = Agent(api_key="test-key")

        with patch.object(agent.client.messages, 'create') as mock_create:
            # First call: timeout
            # Second call: success
            mock_create.side_effect = [
                anthropic.APITimeoutError("Timeout"),
                Mock(
                    content=[Mock(type="text", text="Success")],
                    stop_reason="end_turn",
                    usage=Mock(input_tokens=100, output_tokens=50)
                )
            ]

            response = agent.chat_with_retry("user123", "Hello", max_retries=3)

            assert response == "Success"
            assert mock_create.call_count == 2  # Retried once

    def test_api_rate_limit_backoff(self):
        """Test exponential backoff on rate limits."""
        agent = Agent(api_key="test-key")

        with patch.object(agent.client.messages, 'create') as mock_create:
            mock_create.side_effect = anthropic.RateLimitError("Rate limited")

            start = time.time()
            with pytest.raises(anthropic.RateLimitError):
                agent.chat_with_retry("user123", "Hello", max_retries=3)

            elapsed = time.time() - start

            # Should have waited for backoff (1s + 2s + 4s = 7s minimum)
            assert elapsed > 7


class TestDatabaseFailures:
    """Test agent behavior when database fails."""

    def test_redis_connection_loss(self):
        """Test graceful handling of Redis unavailability."""
        # Create agent with Redis
        redis_client = redis.Redis(host="localhost", port=6379)
        agent = Agent(api_key="test-key", redis_client=redis_client)

        # Simulate Redis connection loss
        with patch.object(redis_client, 'get', side_effect=redis.ConnectionError()):
            # Agent should fall back to no-history mode
            response = agent.chat("user123", "Hello")

            # Should still work, just without history
            assert response is not None

    def test_cache_miss_fallback(self):
        """Test that agent works even if cache is down."""
        redis_client = redis.Redis(host="localhost", port=6379)
        agent = Agent(api_key="test-key", redis_client=redis_client)

        with patch.object(redis_client, 'get', side_effect=redis.ConnectionError()):
            # Should fall back to uncached mode
            response = agent.chat("user123", "What is 2+2?")

            assert response is not None


class TestWorkerFailures:
    """Test system behavior when workers crash."""

    def test_job_reprocessing_after_worker_crash(self, redis_client):
        """Test that jobs are reprocessed if worker crashes mid-processing."""
        from worker import Worker

        # Submit job
        job_id = submit_job(redis_client, "user123", "Hello")

        # Start processing but simulate crash
        worker = Worker(api_key="test-key", redis_client=redis_client)

        # Get job
        job = worker.get_next_job()
        assert job is not None

        # Mark as processing
        worker.mark_job_processing(job["job_id"])

        # Simulate crash (worker dies without completing)
        # Job should be marked as stale after timeout

        time.sleep(worker.job_timeout + 1)

        # Another worker should be able to pick it up
        worker2 = Worker(api_key="test-key", redis_client=redis_client)
        reprocessed_job = worker2.get_next_job(include_stale=True)

        assert reprocessed_job["job_id"] == job_id


class TestNetworkPartitions:
    """Test behavior during network issues."""

    def test_circuit_breaker_opens_on_failures(self):
        """Test that circuit breaker opens after threshold failures."""
        from circuit_breaker import CircuitBreaker

        breaker = CircuitBreaker(failure_threshold=3, timeout=60)

        # Simulate 3 failures
        for _ in range(3):
            try:
                with breaker:
                    raise Exception("Service unavailable")
            except:
                pass

        # Circuit should be open now
        assert breaker.state == "open"

        # Further calls should fail fast
        with pytest.raises(Exception, match="Circuit breaker is open"):
            with breaker:
                pass


# Run chaos tests
# pytest test_chaos.py -v
```

---

## Canary Deployments

### Principle 5: Deploy Gradually

**Canary strategy**:
1. Deploy new version to small % of traffic (5%)
2. Monitor metrics (errors, latency, user feedback)
3. If healthy: increase to 25% → 50% → 100%
4. If unhealthy: rollback to previous version

### Implementation: Canary Deployment

```yaml
# code-examples/chapter-08-testing/canary/deployment.yaml

# Stable version (95% of traffic)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agent-stable
spec:
  replicas: 19  # 95% of 20 total replicas
  selector:
    matchLabels:
      app: agent
      version: stable
  template:
    metadata:
      labels:
        app: agent
        version: stable
    spec:
      containers:
      - name: agent
        image: agent:v1.5.0  # Current stable version

---
# Canary version (5% of traffic)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agent-canary
spec:
  replicas: 1  # 5% of 20 total replicas
  selector:
    matchLabels:
      app: agent
      version: canary
  template:
    metadata:
      labels:
        app: agent
        version: canary
    spec:
      containers:
      - name: agent
        image: agent:v1.6.0  # New canary version

---
# Service routes to both stable and canary
apiVersion: v1
kind: Service
metadata:
  name: agent-service
spec:
  selector:
    app: agent  # Routes to both versions
  ports:
  - port: 80
    targetPort: 8000
```

### Canary Metrics to Monitor

```python
# code-examples/chapter-08-testing/canary/metrics.py

from prometheus_client import Counter, Histogram

# Error rate by version
errors_total = Counter(
    "agent_errors_total",
    "Total errors",
    ["version"]  # stable vs canary
)

# Response time by version
response_time = Histogram(
    "agent_response_seconds",
    "Response time",
    ["version"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

# User satisfaction by version
user_satisfaction = Counter(
    "agent_user_satisfaction_total",
    "User satisfaction ratings",
    ["version", "rating"]  # 1-5 stars
)


def compare_canary_to_stable():
    """Compare canary metrics to stable."""
    canary_error_rate = get_error_rate("canary")
    stable_error_rate = get_error_rate("stable")

    canary_p95_latency = get_p95_latency("canary")
    stable_p95_latency = get_p95_latency("stable")

    # Canary should be similar to or better than stable
    if canary_error_rate > stable_error_rate * 1.5:
        return "ROLLBACK"  # 50% more errors

    if canary_p95_latency > stable_p95_latency * 1.2:
        return "ROLLBACK"  # 20% slower

    return "PROMOTE"  # Canary is healthy
```

---

## Smoke Testing

### Principle 6: Verify Basic Functionality

**Smoke tests** run after deployment to verify system is working.

```python
# code-examples/chapter-08-testing/smoke-tests/smoke_test.py

import requests
import time
import sys


def smoke_test(base_url: str) -> bool:
    """
    Run smoke tests against deployed system.

    Returns: True if all tests pass, False otherwise
    """
    tests_passed = 0
    tests_failed = 0

    # Test 1: Health check
    print("Test 1: Health check...", end=" ")
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            print("✅ PASS")
            tests_passed += 1
        else:
            print(f"❌ FAIL (status: {response.status_code})")
            tests_failed += 1
    except Exception as e:
        print(f"❌ FAIL ({e})")
        tests_failed += 1

    # Test 2: Simple chat request
    print("Test 2: Simple chat...", end=" ")
    try:
        response = requests.post(
            f"{base_url}/chat",
            json={"user_id": "smoke-test", "message": "What is 2+2?"},
            timeout=10
        )
        if response.status_code in [200, 202]:
            print("✅ PASS")
            tests_passed += 1
        else:
            print(f"❌ FAIL (status: {response.status_code})")
            tests_failed += 1
    except Exception as e:
        print(f"❌ FAIL ({e})")
        tests_failed += 1

    # Test 3: Metrics endpoint
    print("Test 3: Metrics endpoint...", end=" ")
    try:
        response = requests.get(f"{base_url}/metrics", timeout=5)
        if response.status_code == 200:
            print("✅ PASS")
            tests_passed += 1
        else:
            print(f"❌ FAIL (status: {response.status_code})")
            tests_failed += 1
    except Exception as e:
        print(f"❌ FAIL ({e})")
        tests_failed += 1

    # Summary
    print(f"\nSmoke test results: {tests_passed} passed, {tests_failed} failed")

    return tests_failed == 0


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python smoke_test.py <base_url>")
        sys.exit(1)

    base_url = sys.argv[1]
    success = smoke_test(base_url)

    sys.exit(0 if success else 1)


# Run smoke tests after deployment
# python smoke_test.py https://agent.production.com
```

---

## Testing Checklist

Before deploying to production:

### Unit Tests
- [ ] All components have unit tests
- [ ] Test coverage > 80% for critical paths
- [ ] Mock external dependencies
- [ ] Test error handling
- [ ] Tests run in < 1 minute

### Integration Tests
- [ ] Test with real Redis
- [ ] Test with real database
- [ ] Test queue → worker flow
- [ ] Test external API integrations
- [ ] Clean up test data

### Load Tests
- [ ] Baseline test at expected load
- [ ] Spike test at 10x load
- [ ] Stress test to find breaking point
- [ ] Soak test for 1 hour
- [ ] Verify auto-scaling works

### Chaos Tests
- [ ] Test API timeouts
- [ ] Test database failures
- [ ] Test Redis unavailability
- [ ] Test worker crashes
- [ ] Test circuit breaker

### Deployment Tests
- [ ] Canary deployment configured
- [ ] Smoke tests automated
- [ ] Rollback procedure tested
- [ ] Monitoring alerts configured

---

## Key Takeaways

1. **Test at multiple levels**: Unit → Integration → E2E
2. **Mock wisely**: Mock external dependencies, not your code
3. **Load test regularly**: Find bottlenecks before users do
4. **Embrace chaos**: Test failure scenarios
5. **Deploy gradually**: Canary deployments catch issues early
6. **Automate everything**: Tests should run on every commit
7. **Monitor in production**: Tests can't catch everything

**Production wisdom**: "Testing shows the presence, not the absence of bugs. But it sure helps find a lot of them." —Adapted from Dijkstra

---

## Next Chapter Preview

You've tested your agent thoroughly. Now it's time to **deploy it safely**. In **Chapter 9: Deployment Patterns**, we'll cover:

- Containerization with Docker
- Kubernetes orchestration
- Blue-green deployments
- Rolling updates
- Feature flags
- Configuration management

Let's get your agent into production!
