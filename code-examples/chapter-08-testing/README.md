# Chapter 8: Testing Production Systems - Code Examples

This directory contains comprehensive testing examples for production AI agent systems.

## Overview

Testing production AI agents requires multiple testing strategies:

1. **unit-tests/** - Fast, isolated component tests
2. **integration-tests/** - Test components working together
3. **load-tests/** - Performance and scalability tests
4. **chaos-tests/** - Failure scenario tests
5. **canary/** - Gradual deployment configuration
6. **smoke-tests/** - Post-deployment verification

## Testing Pyramid

```
         ▲
        / \
       / E2E\        Few (expensive, slow)
      /______\
     / Inte-  \
    / gration  \     Some (moderate cost)
   /___________\
  /  Unit Tests \
 /______________\    Many (cheap, fast)
```

## Quick Start

### Prerequisites

```bash
# Install testing dependencies
pip install pytest pytest-cov pytest-mock locust httpx

# Start Redis (for integration tests)
docker run -d -p 6379:6379 redis:7-alpine

# Set environment variables
export ANTHROPIC_API_KEY=your-key-here
```

## Example 1: Unit Tests

**Location**: `unit-tests/`

**What it tests**:
- Individual functions and methods
- Error handling logic
- Prompt building
- Tool execution
- Business logic

**Run unit tests**:
```bash
cd unit-tests
pytest test_agent.py -v

# With coverage
pytest test_agent.py -v --cov=agent --cov-report=html

# Fast tests only
pytest test_agent.py -v -m "not slow"
```

**Expected output**:
```
test_agent.py::TestToolExecutor::test_calculate_tool_success PASSED
test_agent.py::TestToolExecutor::test_calculate_tool_invalid_expression PASSED
test_agent.py::TestToolExecutor::test_search_web_mock PASSED
test_agent.py::TestAgent::test_chat_simple_response PASSED
test_agent.py::TestAgent::test_chat_with_tool_use PASSED
test_agent.py::TestAgent::test_error_handling_api_failure PASSED

========== 12 passed in 0.43s ==========
Coverage: 85%
```

**Key patterns**:
```python
# Mock external API
with patch('anthropic.Anthropic') as mock:
    mock.return_value.messages.create.return_value = mock_response
    result = agent.chat("user", "Hello")

# Verify interactions
mock.messages.create.assert_called_once()

# Test error handling
mock.side_effect = anthropic.APIError("Error")
with pytest.raises(anthropic.APIError):
    agent.chat("user", "Hello")
```

## Example 2: Integration Tests

**Location**: `integration-tests/`

**What it tests**:
- Agent + Redis (real connection)
- Agent + Database (real queries)
- Queue + Worker (end-to-end flow)
- External API integrations

**Run integration tests**:
```bash
cd integration-tests

# Requires Redis running
pytest test_integration.py -v

# Skip slow tests
pytest test_integration.py -v -m "not slow"
```

**Key patterns**:
```python
@pytest.fixture(scope="module")
def redis_client():
    """Real Redis for integration tests."""
    client = redis.Redis(host="localhost")
    client.ping()  # Verify available
    yield client
    client.flushdb()  # Cleanup

def test_conversation_persistence(redis_client):
    """Test Redis integration."""
    agent = Agent(redis_client=redis_client)
    agent.chat("user1", "My name is Alice")

    # Should persist in Redis
    assert redis_client.exists("conv:user1")
```

## Example 3: Load Tests

**Location**: `load-tests/`

**What it tests**:
- Performance under load
- Scalability
- Resource usage
- Throughput limits

**Run load tests**:
```bash
cd load-tests

# Start Locust web UI
locust -f locustfile.py --host=http://localhost:8000

# Visit http://localhost:8089 to configure test

# Or run headless
locust -f locustfile.py --host=http://localhost:8000 \
  --users 100 --spawn-rate 10 --run-time 5m --headless
```

**Test scenarios**:

1. **Baseline** (expected traffic):
   ```bash
   locust --users 100 --spawn-rate 10 --run-time 5m
   ```

2. **Spike** (sudden 10x traffic):
   ```bash
   locust --users 1000 --spawn-rate 100 --run-time 2m
   ```

3. **Stress** (find breaking point):
   ```bash
   locust --users 5000 --spawn-rate 50 --run-time 10m
   ```

4. **Soak** (sustained load):
   ```bash
   locust --users 500 --spawn-rate 10 --run-time 1h
   ```

**Metrics to monitor**:
- **RPS** (requests per second)
- **Response time**: p50, p95, p99
- **Error rate**: % failed requests
- **Resource usage**: CPU, memory, connections

**Good results**:
- ✅ p95 latency < 2s
- ✅ Error rate < 0.1%
- ✅ Linear scaling with workers
- ✅ Stable memory usage

**Bad results**:
- 🚨 Latency increasing with load
- 🚨 Error rate > 1%
- 🚨 Memory leaks (growing usage)
- 🚨 Queue depth growing unbounded

## Example 4: Chaos Tests

**Location**: `chaos-tests/`

**What it tests**:
- API failures and timeouts
- Database connection loss
- Redis unavailability
- Worker crashes
- Network partitions

**Run chaos tests**:
```bash
cd chaos-tests
pytest test_chaos.py -v
```

**Failure scenarios**:
```python
def test_api_timeout():
    """Verify graceful timeout handling."""
    with patch.object(client, 'create', side_effect=TimeoutError()):
        response = agent.chat_with_retry("user", "Hello")
        # Should retry and eventually succeed or fail gracefully

def test_redis_down():
    """Verify fallback when Redis unavailable."""
    with patch.object(redis, 'get', side_effect=ConnectionError()):
        response = agent.chat("user", "Hello")
        # Should work without cache

def test_circuit_breaker():
    """Verify circuit breaker opens after failures."""
    # Simulate 5 failures
    for _ in range(5):
        try:
            call_failing_service()
        except:
            pass

    # Circuit should be open
    assert breaker.state == "open"
```

## Example 5: Canary Deployment

**Location**: `canary/`

**What it provides**:
- Kubernetes manifests for canary deployment
- Metrics comparison scripts
- Automated promotion/rollback

**Deploy canary**:
```bash
# Deploy canary (5% traffic)
kubectl apply -f canary/deployment.yaml

# Monitor canary metrics
python canary/monitor.py --duration 10m

# If healthy, promote canary
kubectl apply -f canary/promote.yaml

# If unhealthy, rollback
kubectl rollout undo deployment/agent-canary
```

**Canary strategy**:
1. Deploy to 5% of traffic
2. Monitor for 10 minutes
3. Compare metrics (errors, latency)
4. If healthy → 25% → 50% → 100%
5. If unhealthy → rollback

## Example 6: Smoke Tests

**Location**: `smoke-tests/`

**What it tests**:
- Basic functionality after deployment
- Critical endpoints working
- System health

**Run smoke tests**:
```bash
# After deployment
python smoke_test.py https://agent.production.com

# Expected output:
# Test 1: Health check... ✅ PASS
# Test 2: Simple chat... ✅ PASS
# Test 3: Metrics endpoint... ✅ PASS
#
# Smoke test results: 3 passed, 0 failed
```

**Integrate with CI/CD**:
```yaml
# .github/workflows/deploy.yml
- name: Deploy to production
  run: kubectl apply -f deployment.yaml

- name: Wait for rollout
  run: kubectl rollout status deployment/agent

- name: Run smoke tests
  run: python smoke_test.py ${{ secrets.PROD_URL }}

- name: Rollback if smoke tests fail
  if: failure()
  run: kubectl rollout undo deployment/agent
```

## Testing Workflow

### 1. Development

```bash
# Write code
vim agent.py

# Run unit tests (fast feedback)
pytest unit-tests/ -v

# Run integration tests
pytest integration-tests/ -v
```

### 2. Pre-commit

```bash
# Pre-commit hook runs unit tests
git commit -m "Add feature"
# → Unit tests run automatically
```

### 3. CI Pipeline

```yaml
# .github/workflows/test.yml
- name: Unit tests
  run: pytest unit-tests/ -v --cov

- name: Integration tests
  run: pytest integration-tests/ -v

- name: Load tests (baseline)
  run: locust --headless --users 100 --run-time 2m
```

### 4. Pre-deployment

```bash
# Load test staging
locust -f load-tests/locustfile.py \
  --host=https://staging.agent.com \
  --users 1000 --spawn-rate 50 --run-time 10m

# Chaos test staging
pytest chaos-tests/ -v
```

### 5. Deployment

```bash
# Canary deployment
kubectl apply -f canary/deployment.yaml

# Monitor canary
python canary/monitor.py --duration 10m

# If healthy, promote
kubectl apply -f canary/promote.yaml
```

### 6. Post-deployment

```bash
# Smoke tests
python smoke-tests/smoke_test.py https://agent.production.com

# Monitor production metrics
# → Grafana dashboards
# → Alert on regressions
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Test and Deploy

on: [push]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.11

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Unit tests
        run: pytest unit-tests/ -v --cov --cov-fail-under=80

      - name: Start Redis
        run: docker run -d -p 6379:6379 redis:7-alpine

      - name: Integration tests
        run: pytest integration-tests/ -v

      - name: Load tests (baseline)
        run: |
          locust -f load-tests/locustfile.py \
            --host=https://staging.com \
            --users 100 --spawn-rate 10 \
            --run-time 2m --headless

  deploy:
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - name: Deploy canary
        run: kubectl apply -f canary/deployment.yaml

      - name: Wait for rollout
        run: kubectl rollout status deployment/agent-canary

      - name: Smoke tests
        run: python smoke-tests/smoke_test.py ${{ secrets.PROD_URL }}

      - name: Monitor canary
        run: python canary/monitor.py --duration 10m

      - name: Promote or rollback
        run: |
          if [ $? -eq 0 ]; then
            kubectl apply -f canary/promote.yaml
          else
            kubectl rollout undo deployment/agent-canary
          fi
```

## Monitoring Test Results

### Test Coverage

```bash
# Generate coverage report
pytest --cov=agent --cov-report=html

# View report
open htmlcov/index.html

# Enforce minimum coverage
pytest --cov=agent --cov-fail-under=80
```

### Test Trends

Track test metrics over time:
- Number of tests
- Test execution time
- Coverage percentage
- Flaky tests (intermittent failures)

### Load Test Results

Track in Grafana:
- RPS over time
- Response time (p50, p95, p99)
- Error rate
- Resource usage (CPU, memory)

## Troubleshooting

### Tests timing out

**Problem**: Tests take too long or hang

**Solutions**:
- Add timeouts to HTTP calls
- Use pytest `-x` flag (stop on first failure)
- Mark slow tests with `@pytest.mark.slow`
- Run fast tests first

### Flaky tests

**Problem**: Tests pass sometimes, fail others

**Causes**:
- Race conditions
- External dependencies
- Time-dependent logic

**Solutions**:
- Add retries for external calls
- Use deterministic test data
- Mock time-dependent code
- Increase timeouts

### Load tests showing poor performance

**Problem**: High latency or errors under load

**Solutions**:
1. Profile to find bottlenecks
2. Add caching
3. Optimize database queries
4. Scale horizontally
5. Review Chapter 7 (Performance Optimization)

## Testing Checklist

Before production deployment:

- [ ] Unit test coverage > 80%
- [ ] All integration tests passing
- [ ] Load tested at 10x expected traffic
- [ ] Chaos tests passing
- [ ] Canary deployment configured
- [ ] Smoke tests automated
- [ ] CI/CD pipeline configured
- [ ] Monitoring alerts set up
- [ ] Rollback procedure tested

## Best Practices

1. **Write tests first** (TDD when possible)
2. **Test the unhappy path** (errors, timeouts, failures)
3. **Keep tests fast** (mock expensive operations)
4. **Run tests automatically** (CI/CD integration)
5. **Monitor test trends** (coverage, execution time)
6. **Load test regularly** (weekly or before major releases)
7. **Fix flaky tests immediately** (they erode confidence)

## Resources

- [Pytest documentation](https://docs.pytest.org/)
- [Locust load testing](https://locust.io/)
- [Chaos Engineering principles](https://principlesofchaos.org/)
- [Testing best practices](https://martinfowler.com/testing/)

## Next Steps

1. Review existing test coverage
2. Add missing unit tests
3. Set up integration test environment
4. Run baseline load test
5. Configure canary deployment
6. Integrate with CI/CD
7. Move to Chapter 9 (Deployment Patterns)

**Remember**: Tests are insurance against regressions. Invest in them!
