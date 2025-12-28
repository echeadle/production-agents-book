# Chapter 3: Observability and Debugging

## Introduction: The Mystery of the Slow Agent

It's 2:15 PM on a Tuesday. Your agent has been running in production for two weeks. Everything *seems* fine—until your manager Slacks you:

> "Hey, users are saying the agent is slow today. Can you check?"

You open your monitoring dashboard. **It's empty.** No graphs. No metrics. Just your reference agent humming away, processing requests, completely opaque.

You SSH into the server and grep the logs:

```bash
$ grep "error" agent.log
(no output)
```

No errors. You check response times:

```bash
$ grep "response" agent.log
Agent: The result is 345.
Agent: I've saved your note.
Agent: The weather in Seattle is...
```

Just output. No timing information. No request IDs. No way to tell which requests are slow.

You have **no visibility into what's happening inside your agent.**

**The questions you can't answer:**
- Which requests are slow?
- What's the P95 latency? P99?
- Are retries happening? How often?
- Is the circuit breaker tripping?
- Which tools are slowest?
- What's causing the slowness?

**You're flying blind.**

You spend the next 3 hours adding print statements, redeploying, SSH-ing in, grepping logs, trying to understand what's happening. By 5 PM, you finally discover: the web search tool is timing out 30% of the time, causing retries, which cascade into slow requests.

**3 hours of debugging for a 30-second fix** (increase the timeout).

**This is the cost of no observability.**

## The Three Pillars of Observability

In Chapter 2, we made the agent **reliable**—it handles failures gracefully. But we still can't **see** what's happening inside. We can't answer:

- **What happened?** (logs)
- **How often is it happening?** (metrics)
- **Why is it happening?** (traces)

These are the **three pillars of observability:**

### Pillar 1: Logs

**Logs** tell you **what happened**.

```
2025-01-28 14:32:15 INFO  Request started: request_id=abc123
2025-01-28 14:32:16 INFO  Tool executed: tool=calculator, duration=0.05s
2025-01-28 14:32:17 INFO  Request completed: request_id=abc123, duration=2.1s
```

Logs are **events** that happened at specific times. They tell the story of what your agent did.

**Use logs for:**
- Understanding what happened during a specific request
- Debugging errors and failures
- Auditing (who did what, when)
- Root cause analysis

**Logs answer:** "What happened to request abc123?"

### Pillar 2: Metrics

**Metrics** tell you **how often** things are happening.

```
agent_requests_total: 1,523
agent_requests_failed: 12
agent_request_duration_p95: 2.3s
circuit_breaker_trips_total: 3
```

Metrics are **aggregated numbers** over time. They show trends, patterns, and anomalies.

**Use metrics for:**
- Monitoring system health (dashboards)
- Alerting on SLO violations
- Capacity planning
- Performance analysis

**Metrics answer:** "How many requests are failing right now?"

### Pillar 3: Traces

**Traces** tell you **why** something is slow.

```
Request abc123 (total: 5.2s)
  ├─ LLM call #1: 1.2s
  ├─ Tool: web_search: 3.5s ⚠️ SLOW!
  │   ├─ HTTP request: 3.4s
  │   └─ Parse results: 0.1s
  └─ LLM call #2: 0.5s
```

Traces show the **flow of a request** through your system, with timing for each step.

**Use traces for:**
- Understanding where time is spent
- Finding performance bottlenecks
- Debugging slow requests
- Understanding dependencies

**Traces answer:** "Why is this request slow?"

## Why All Three Matter

You need **all three pillars** to effectively operate in production:

**Example scenario:** Agent is slow.

1. **Metrics** tell you it's slow:
   - P95 latency jumped from 2s to 8s
   - Alert fires: "P95 latency > 5s"

2. **Traces** show you where the time is spent:
   - web_search tool taking 7 seconds (should be 1s)

3. **Logs** explain what's happening:
   - `web_search` is timing out and retrying
   - External API returning 503 errors

**With all three, you diagnose in 30 seconds instead of 3 hours.**

## Where We Are Now

In Chapter 2, we added **some** observability:
- Structured logging (via `logging` module)
- Log context (via `extra` fields)

But we're missing:
- ❌ **Metrics** - No counters, gauges, histograms
- ❌ **Traces** - No request tracking across steps
- ❌ **Correlation IDs** - Can't follow a request through logs
- ❌ **Dashboards** - No visualization
- ❌ **Alerts** - No proactive notification

Let's add them.

## Structured Logging (Enhanced)

We already use `logging`, but let's enhance it with better structure.

### What We Have (from Chapter 2)

```python
logger.info(
    f"Tool execution successful: {tool_name}",
    extra={
        "tool_name": tool_name,
        "result_preview": result[:100]
    }
)
```

This is good! But we can make it better.

### What We Need

**1. Correlation IDs** - Track a request across all log lines

Every log line for the same request should have the same `request_id`:

```
2025-01-28 14:32:15 INFO  [abc123] Request started
2025-01-28 14:32:16 INFO  [abc123] Tool: calculator
2025-01-28 14:32:17 INFO  [abc123] Request completed
```

Now you can grep for `abc123` and see the full story.

**2. Consistent Fields** - Standard fields across all logs

```python
{
    "timestamp": "2025-01-28T14:32:15Z",
    "level": "INFO",
    "request_id": "abc123",
    "user_id": "user_456",
    "event": "tool_executed",
    "tool_name": "calculator",
    "duration_ms": 50
}
```

**3. JSON Format** - Easy to parse and query

Human-readable logs are great for development. JSON logs are great for production.

```
{"ts":"2025-01-28T14:32:15Z","level":"info","request_id":"abc123","event":"tool_executed","tool":"calculator","duration_ms":50}
```

Now you can pipe logs to tools like `jq`, Elasticsearch, Datadog, etc.

### Implementation: Enhanced Structured Logging

Let's use `structlog` for better structured logging:

```python
# logging_config.py
import structlog
import logging
import sys

def configure_logging(json_logs: bool = True):
    """
    Configure structured logging for production.

    Args:
        json_logs: If True, output JSON. If False, human-readable.
    """
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )

    # Configure structlog
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if json_logs:
        # Production: JSON output
        processors.append(structlog.processors.JSONRenderer())
    else:
        # Development: Human-readable output
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


# Get a logger
logger = structlog.get_logger()
```

### Using Correlation IDs

Add a `request_id` to every log line:

```python
# agent.py
import uuid
import structlog

logger = structlog.get_logger()

class Agent:
    def process(self, user_input: str, user_id: str = None) -> str:
        """Process a user request with correlation ID."""

        # Generate correlation ID
        request_id = str(uuid.uuid4())

        # Bind context to logger (all logs in this request will have this ID)
        log = logger.bind(
            request_id=request_id,
            user_id=user_id
        )

        log.info("request_started", user_input_length=len(user_input))

        try:
            result = self._process_internal(user_input, log)
            log.info("request_completed", result_length=len(result))
            return result

        except Exception as e:
            log.error("request_failed", error=str(e), exc_info=True)
            raise

    def _process_internal(self, user_input: str, log) -> str:
        """Internal processing with bound logger."""
        # ... agent loop ...

        # All logs automatically include request_id!
        log.info("llm_call_started")
        response = self._call_llm()
        log.info("llm_call_completed", stop_reason=response.stop_reason)

        # ...
```

**Output (JSON):**
```json
{"event":"request_started","request_id":"abc123","user_id":"user_456","user_input_length":42,"timestamp":"2025-01-28T14:32:15.123Z","level":"info"}
{"event":"llm_call_started","request_id":"abc123","user_id":"user_456","timestamp":"2025-01-28T14:32:16.456Z","level":"info"}
{"event":"llm_call_completed","request_id":"abc123","user_id":"user_456","stop_reason":"tool_use","timestamp":"2025-01-28T14:32:17.789Z","level":"info"}
{"event":"request_completed","request_id":"abc123","user_id":"user_456","result_length":58,"timestamp":"2025-01-28T14:32:18.012Z","level":"info"}
```

Now you can grep for `request_id":"abc123"` and see the entire request flow!

### Log Levels Done Right

Use log levels appropriately:

```python
# DEBUG: Detailed info for debugging (not in production by default)
log.debug("retry_attempt", attempt=2, delay=2.5)

# INFO: Normal operations
log.info("request_started", user_id=user_id)
log.info("tool_executed", tool="calculator", duration_ms=50)

# WARNING: Something unusual but handled
log.warning("retry_exhausted", max_retries=3, error=str(e))
log.warning("circuit_breaker_open", service="web_search")

# ERROR: Something failed
log.error("request_failed", error=str(e), exc_info=True)

# CRITICAL: System is broken
log.critical("database_connection_lost", attempts=5)
```

**Production config:**
- Set level to `INFO` normally
- Set level to `DEBUG` temporarily when debugging
- Never log sensitive data (PII, API keys, passwords)

### What This Solves

**Before:** Logs are unstructured, hard to query, missing context.

**After:** Structured logs with correlation IDs, consistent fields, easy to query.

**Example query:**
```bash
# Find all logs for request abc123
cat logs.json | jq 'select(.request_id == "abc123")'

# Find all failed requests
cat logs.json | jq 'select(.event == "request_failed")'

# Find slow tool executions (> 1s)
cat logs.json | jq 'select(.event == "tool_executed" and .duration_ms > 1000)'
```

## Metrics Collection with Prometheus

Logs tell you **what happened**. Metrics tell you **how often** and **how much**.

### What to Measure

For our agent, we want to track:

**RED Metrics** (Rate, Errors, Duration):
- **Rate**: Requests per second
- **Errors**: Error rate
- **Duration**: Request latency (P50, P95, P99)

**Specific metrics:**
```python
# Counters (always increasing)
agent_requests_total{status="success"}  # Total successful requests
agent_requests_total{status="error"}    # Total failed requests
agent_llm_calls_total                   # Total LLM API calls
agent_tool_calls_total{tool="calculator"}  # Tool usage by type
agent_retries_total{reason="rate_limit"}   # Retries by reason
circuit_breaker_trips_total{service="web_search"}  # Circuit trips

# Gauges (can go up or down)
agent_active_requests  # Current requests being processed
circuit_breaker_state{service="web_search",state="open"}  # 1 if open, 0 if closed

# Histograms (track distributions)
agent_request_duration_seconds  # Request latency distribution
agent_llm_call_duration_seconds  # LLM call latency
agent_tool_duration_seconds{tool="calculator"}  # Tool latency by type
```

### Implementation with Prometheus

```python
# metrics.py
from prometheus_client import Counter, Histogram, Gauge, Enum
import time

# Counters
requests_total = Counter(
    'agent_requests_total',
    'Total requests processed',
    ['status']  # Labels: success, error
)

llm_calls_total = Counter(
    'agent_llm_calls_total',
    'Total LLM API calls'
)

tool_calls_total = Counter(
    'agent_tool_calls_total',
    'Total tool calls',
    ['tool', 'status']
)

retries_total = Counter(
    'agent_retries_total',
    'Total retry attempts',
    ['reason']
)

# Gauges
active_requests = Gauge(
    'agent_active_requests',
    'Currently active requests'
)

# Histograms (with default buckets optimized for latency)
request_duration = Histogram(
    'agent_request_duration_seconds',
    'Request duration in seconds',
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
)

llm_call_duration = Histogram(
    'agent_llm_call_duration_seconds',
    'LLM call duration in seconds'
)

tool_duration = Histogram(
    'agent_tool_duration_seconds',
    'Tool execution duration in seconds',
    ['tool']
)
```

### Instrumenting the Agent

```python
# agent.py
from metrics import (
    requests_total,
    llm_calls_total,
    tool_calls_total,
    active_requests,
    request_duration,
    llm_call_duration,
    tool_duration
)

class Agent:
    def process(self, user_input: str, user_id: str = None) -> str:
        """Process request with metrics."""

        # Track active requests
        active_requests.inc()

        # Track request duration
        start_time = time.time()

        try:
            result = self._process_internal(user_input, user_id)

            # Success metrics
            requests_total.labels(status="success").inc()
            request_duration.observe(time.time() - start_time)

            return result

        except Exception as e:
            # Error metrics
            requests_total.labels(status="error").inc()
            request_duration.observe(time.time() - start_time)
            raise

        finally:
            # Always decrement active requests
            active_requests.dec()

    def _call_llm(self):
        """Call LLM with metrics."""
        start_time = time.time()

        try:
            llm_calls_total.inc()
            response = self.client.messages.create(...)
            llm_call_duration.observe(time.time() - start_time)
            return response

        except Exception as e:
            llm_call_duration.observe(time.time() - start_time)
            raise

    def _execute_tools(self, content):
        """Execute tools with metrics."""
        for block in content:
            if block.type == "tool_use":
                tool_name = block.name
                start_time = time.time()

                try:
                    result = execute_tool(tool_name, block.input)
                    duration = time.time() - start_time

                    tool_calls_total.labels(tool=tool_name, status="success").inc()
                    tool_duration.labels(tool=tool_name).observe(duration)

                except Exception as e:
                    duration = time.time() - start_time

                    tool_calls_total.labels(tool=tool_name, status="error").inc()
                    tool_duration.labels(tool=tool_name).observe(duration)
                    raise
```

### Exposing Metrics

Prometheus scrapes metrics from an HTTP endpoint:

```python
# main.py
from prometheus_client import start_http_server
import logging_config
from agent import Agent

# Start metrics server on port 9090
start_http_server(9090)

# Configure logging
logging_config.configure_logging(json_logs=True)

# Run agent
agent = Agent()
# ... (agent processes requests) ...
```

Now Prometheus can scrape `http://localhost:9090/metrics`:

```
# HELP agent_requests_total Total requests processed
# TYPE agent_requests_total counter
agent_requests_total{status="success"} 1523.0
agent_requests_total{status="error"} 12.0

# HELP agent_request_duration_seconds Request duration in seconds
# TYPE agent_request_duration_seconds histogram
agent_request_duration_seconds_bucket{le="0.1"} 45.0
agent_request_duration_seconds_bucket{le="0.5"} 523.0
agent_request_duration_seconds_bucket{le="1.0"} 1234.0
agent_request_duration_seconds_bucket{le="2.0"} 1489.0
agent_request_duration_seconds_bucket{le="5.0"} 1523.0
agent_request_duration_seconds_bucket{le="+Inf"} 1535.0
agent_request_duration_seconds_sum 3245.6
agent_request_duration_seconds_count 1535
```

### Querying Metrics (PromQL)

**Request rate (requests per second):**
```promql
rate(agent_requests_total[5m])
```

**Error rate:**
```promql
rate(agent_requests_total{status="error"}[5m])
```

**P95 latency:**
```promql
histogram_quantile(0.95, rate(agent_request_duration_seconds_bucket[5m]))
```

**P99 latency:**
```promql
histogram_quantile(0.99, rate(agent_request_duration_seconds_bucket[5m]))
```

**Success rate (percentage):**
```promql
rate(agent_requests_total{status="success"}[5m])
/
rate(agent_requests_total[5m]) * 100
```

**Slowest tools (average duration):**
```promql
rate(agent_tool_duration_seconds_sum[5m])
/
rate(agent_tool_duration_seconds_count[5m])
```

### What This Solves

**Before:** Can't answer "how many?", "how fast?", "how often?"

**After:** Real-time visibility into system behavior. Can answer:
- ✅ Request rate
- ✅ Error rate
- ✅ Latency (P50, P95, P99)
- ✅ Tool usage
- ✅ Retry frequency
- ✅ Circuit breaker state

## Distributed Tracing with OpenTelemetry

Logs tell you **what happened**. Metrics tell you **how often**. Traces tell you **why** it's slow.

### The Problem: Where Is the Time Spent?

Your metrics show P95 latency is 8 seconds. But **why**?

- Is it the LLM call?
- Is it a slow tool?
- Is it retries?
- Is it network latency?

**Metrics can't tell you.** You need **distributed tracing**.

### What Is a Trace?

A **trace** is the complete journey of a request through your system:

```
Request abc123 (total: 5.2s)
  ├─ agent.process: 5.2s
  │   ├─ llm_call_1: 1.2s
  │   ├─ tool: web_search: 3.5s  ⚠️ SLOW!
  │   │   ├─ http_request: 3.4s
  │   │   └─ parse_results: 0.1s
  │   └─ llm_call_2: 0.5s
```

Each box is a **span** - a unit of work with:
- Name (what happened)
- Start time
- Duration
- Parent span (what called it)
- Attributes (metadata)

### OpenTelemetry Implementation

OpenTelemetry is the industry standard for tracing.

```python
# tracing.py
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource

def configure_tracing(service_name: str = "task-agent"):
    """Configure OpenTelemetry tracing."""

    # Create a resource identifying this service
    resource = Resource.create({"service.name": service_name})

    # Create tracer provider
    provider = TracerProvider(resource=resource)

    # Add span processor (exports to console for now, use OTLP for production)
    processor = BatchSpanProcessor(ConsoleSpanExporter())
    provider.add_span_processor(processor)

    # Set as global tracer provider
    trace.set_tracer_provider(provider)

# Get tracer
tracer = trace.get_tracer(__name__)
```

### Instrumenting the Agent

```python
# agent.py
from tracing import tracer

class Agent:
    def process(self, user_input: str, user_id: str = None) -> str:
        """Process request with tracing."""

        # Create root span for the request
        with tracer.start_as_current_span(
            "agent.process",
            attributes={
                "user_id": user_id,
                "input_length": len(user_input)
            }
        ) as span:
            try:
                result = self._process_internal(user_input, user_id)

                span.set_attribute("result_length", len(result))
                span.set_attribute("status", "success")

                return result

            except Exception as e:
                span.set_attribute("status", "error")
                span.record_exception(e)
                raise

    def _call_llm(self):
        """Call LLM with tracing."""
        with tracer.start_as_current_span("llm.call") as span:
            span.set_attribute("model", self.config.model)

            response = self.client.messages.create(...)

            span.set_attribute("stop_reason", response.stop_reason)
            span.set_attribute("input_tokens", response.usage.input_tokens)
            span.set_attribute("output_tokens", response.usage.output_tokens)

            return response

    def _execute_tools(self, content):
        """Execute tools with tracing."""
        for block in content:
            if block.type == "tool_use":
                tool_name = block.name

                with tracer.start_as_current_span(
                    f"tool.{tool_name}",
                    attributes={"tool.name": tool_name}
                ) as span:
                    result = execute_tool(tool_name, block.input)
                    span.set_attribute("result_length", len(result))
```

### Trace Output Example

```
Span: agent.process (5.2s)
  Attributes:
    user_id: user_456
    input_length: 42
    status: success

  Span: llm.call (1.2s)
    Attributes:
      model: claude-sonnet-4-20250514
      stop_reason: tool_use
      input_tokens: 523
      output_tokens: 45

  Span: tool.web_search (3.5s) ⚠️
    Attributes:
      tool.name: web_search
      result_length: 1234

  Span: llm.call (0.5s)
    Attributes:
      model: claude-sonnet-4-20250514
      stop_reason: end_turn
      input_tokens: 678
      output_tokens: 123
```

**Now you can see:** `tool.web_search` took 3.5 seconds (67% of total time).

### Trace Context Propagation

In distributed systems, traces span multiple services. OpenTelemetry automatically propagates trace context:

```python
# When calling external services, inject trace context
import requests
from opentelemetry.propagate import inject

headers = {}
inject(headers)  # Adds traceparent header

response = requests.get("https://api.example.com", headers=headers)
```

Now the external service can continue the same trace!

### What This Solves

**Before:** "Request is slow" - but no idea why.

**After:** See exactly where time is spent. Identify bottlenecks immediately.

**Example insights:**
- 70% of time in `tool.web_search` → optimize or cache it
- 50% of time in retries → improve error handling
- LLM calls faster than expected → tools are the bottleneck

## Dashboards with Grafana

Metrics and traces are useless if you can't **see** them. Enter: dashboards.

### The Essential Dashboard

Every production agent needs a dashboard showing:

**1. Request Rate (requests/second)**
```promql
rate(agent_requests_total[5m])
```

**2. Error Rate**
```promql
rate(agent_requests_total{status="error"}[5m])
```

**3. Latency (P50, P95, P99)**
```promql
histogram_quantile(0.50, rate(agent_request_duration_seconds_bucket[5m]))
histogram_quantile(0.95, rate(agent_request_duration_seconds_bucket[5m]))
histogram_quantile(0.99, rate(agent_request_duration_seconds_bucket[5m]))
```

**4. Success Rate (%)**
```promql
rate(agent_requests_total{status="success"}[5m])
/
rate(agent_requests_total[5m]) * 100
```

**5. Active Requests**
```promql
agent_active_requests
```

**6. Tool Performance**
```promql
rate(agent_tool_duration_seconds_sum[5m]) / rate(agent_tool_duration_seconds_count[5m])
```

**7. Circuit Breaker State**
```promql
circuit_breaker_state
```

**8. Retry Rate**
```promql
rate(agent_retries_total[5m])
```

### Dashboard Best Practices

**1. RED Metrics on Top**
- Rate, Errors, Duration should be immediately visible
- Use time series graphs to see trends

**2. Use Color-Coded Thresholds**
- Green: Good (< SLO)
- Yellow: Warning (approaching SLO)
- Red: Bad (exceeding SLO)

**3. Add SLO Lines**
- Show your SLO targets on graphs
- Makes it obvious when you're violating SLOs

**4. Use Multiple Time Ranges**
- Last 5 minutes (real-time)
- Last hour (recent trends)
- Last 24 hours (daily patterns)
- Last 7 days (weekly patterns)

**5. Add Annotations**
- Mark deployments
- Mark incidents
- Mark configuration changes

## Alerting on SLOs

Dashboards are for **humans**. Alerts are for **waking you up** when things break.

### SLO-Based Alerting

Don't alert on symptoms. Alert on **SLO violations**.

**Bad alerts:**
```
❌ LLM call took > 5 seconds (once)
❌ One request failed
❌ Error happened
```

These are **noisy**. You'll get paged for normal transient issues.

**Good alerts:**
```
✅ P95 latency > 5s for 5 minutes
✅ Error rate > 1% for 5 minutes
✅ Success rate < 99% for 10 minutes
```

These indicate **real problems** that violate your SLOs.

### Alert Rules (Prometheus)

```yaml
# alerts.yml
groups:
  - name: agent_slo_alerts
    interval: 30s
    rules:
      # Latency SLO: P95 < 5 seconds
      - alert: HighLatency
        expr: |
          histogram_quantile(0.95,
            rate(agent_request_duration_seconds_bucket[5m])
          ) > 5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Agent P95 latency exceeds SLO"
          description: "P95 latency is {{ $value }}s (SLO: 5s)"

      # Error rate SLO: < 1%
      - alert: HighErrorRate
        expr: |
          rate(agent_requests_total{status="error"}[5m])
          /
          rate(agent_requests_total[5m]) > 0.01
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Agent error rate exceeds SLO"
          description: "Error rate is {{ $value | humanizePercentage }} (SLO: 1%)"

      # Availability SLO: > 99%
      - alert: LowAvailability
        expr: |
          rate(agent_requests_total{status="success"}[10m])
          /
          rate(agent_requests_total[10m]) < 0.99
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: "Agent availability below SLO"
          description: "Availability is {{ $value | humanizePercentage }} (SLO: 99%)"

      # Circuit breaker tripping frequently
      - alert: CircuitBreakerTripping
        expr: rate(circuit_breaker_trips_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Circuit breaker tripping frequently"
          description: "Circuit breaker {{ $labels.service }} tripping at {{ $value }}/s"
```

### Alert Severity Levels

**CRITICAL** (page immediately):
- Service is down
- Error rate > SLO
- Availability < SLO

**WARNING** (notify, but don't page):
- Approaching SLO limits
- Circuit breaker tripping
- High retry rate

**INFO** (log only):
- Deployments
- Configuration changes
- Routine maintenance

### Runbooks

Every alert should have a **runbook** - instructions for responding.

**Example runbook for "HighLatency" alert:**

```markdown
## Alert: HighLatency

**What it means:** P95 request latency > 5 seconds for 5+ minutes

**Impact:** Users experiencing slow responses

**Steps to investigate:**

1. Check dashboard - which component is slow?
   - If LLM calls: Check Anthropic API status
   - If tools: Check external API status
   - If retries: Check error logs

2. Check recent changes:
   - Any deployments in last hour?
   - Any configuration changes?

3. Check resource usage:
   - CPU: `top`
   - Memory: `free -h`
   - Disk: `df -h`

4. Check logs for errors:
   - `grep "ERROR" logs.json | tail -50`

**Quick fixes:**
- If external API slow: Increase timeouts, trip circuit breaker manually
- If LLM slow: Check rate limits, consider model downgrade temporarily
- If resource exhaustion: Scale up workers

**Escalation:** If no improvement in 30 minutes, page SRE on-call
```

## Debugging Production Issues

With observability in place, debugging is systematic.

### Scenario 1: "Agent is slow"

**Step 1: Confirm with metrics**
```promql
# Check P95 latency
histogram_quantile(0.95, rate(agent_request_duration_seconds_bucket[5m]))
```

**Step 2: Find slow requests with traces**
- Filter traces by duration > 5s
- Identify common patterns

**Step 3: Narrow down with logs**
```bash
# Find slow requests
cat logs.json | jq 'select(.duration_ms > 5000)'

# Group by tool
cat logs.json | jq 'select(.event == "tool_executed") | {tool: .tool_name, duration: .duration_ms}' | sort
```

**Step 4: Root cause**
- If specific tool slow → external API issue
- If all requests slow → resource exhaustion
- If random requests slow → retries/timeouts

### Scenario 2: "Errors spiking"

**Step 1: Metrics - what's failing?**
```promql
# Error rate by type
rate(agent_requests_total{status="error"}[5m])
```

**Step 2: Logs - why are they failing?**
```bash
# Recent errors
cat logs.json | jq 'select(.level == "error")' | tail -20

# Group errors by type
cat logs.json | jq 'select(.level == "error") | .error_type' | sort | uniq -c
```

**Step 3: Traces - which component?**
- Look for spans with errors
- Check if errors cluster in specific tools

**Step 4: Root cause**
- If RateLimitError → reduce request rate
- If TimeoutError → increase timeouts or fix slow dependency
- If CircuitBreakerError → dependency is down

### Scenario 3: "Cost spike"

**Step 1: Metrics - what changed?**
```promql
# LLM calls per request (should be ~2-3)
rate(agent_llm_calls_total[1h]) / rate(agent_requests_total[1h])

# Token usage
rate(agent_llm_input_tokens_total[1h])
rate(agent_llm_output_tokens_total[1h])
```

**Step 2: Logs - which requests use lots of tokens?**
```bash
# Find high-token requests
cat logs.json | jq 'select(.output_tokens > 1000)'
```

**Step 3: Traces - why so many LLM calls?**
- Look for requests with many LLM call spans
- Check for retry loops

**Step 4: Root cause**
- If many retries → fix root cause of failures
- If long conversations → limit history length
- If verbose outputs → optimize prompts

## Production Readiness Checklist (Updated)

From Chapter 1, updated with observability:

### Observability (NEW)
- [x] **Structured logging** with correlation IDs
- [x] **JSON log format** for production
- [x] **Metrics collection** (Prometheus)
- [x] **Distributed tracing** (OpenTelemetry)
- [x] **Dashboard** showing RED metrics
- [x] **Alerts** for SLO violations
- [x] **Runbooks** for common incidents

### Reliability (Chapter 2)
- [x] Retry logic with exponential backoff
- [x] Circuit breakers
- [x] Timeouts
- [x] Graceful degradation
- [x] Health checks
- [x] Idempotent operations
- [x] Rate limiting

### Still Needed
- [ ] Security (Chapter 4)
- [ ] Cost tracking (Chapter 5)
- [ ] Horizontal scaling (Chapter 6)

## Exercises

### Exercise 1: Add Correlation IDs

Update the reference agent to use correlation IDs:
1. Install `structlog`
2. Configure JSON logging
3. Add `request_id` to all log lines
4. Test by running agent and grepping for a request ID

### Exercise 2: Add Metrics

Instrument the agent with Prometheus metrics:
1. Install `prometheus-client`
2. Add counters for requests, errors, LLM calls
3. Add histogram for request duration
4. Expose metrics on port 9090
5. Query metrics with `curl localhost:9090/metrics`

### Exercise 3: Add Tracing

Add OpenTelemetry tracing:
1. Install `opentelemetry-api` and `opentelemetry-sdk`
2. Create spans for LLM calls and tool executions
3. Add attributes (model, tokens, tool names)
4. Export to console
5. Find the slowest span in a trace

### Exercise 4: Create a Dashboard

Using the metrics from Exercise 2:
1. Install Prometheus and Grafana locally
2. Configure Prometheus to scrape your agent
3. Create a Grafana dashboard with:
   - Request rate
   - Error rate
   - P95 latency
   - Active requests
4. Set refresh interval to 5 seconds

### Exercise 5: Set Up Alerts

Create alert rules:
1. Alert if P95 latency > 10 seconds for 2 minutes
2. Alert if error rate > 5% for 2 minutes
3. Alert if circuit breaker trips
4. Write a runbook for each alert

### Exercise 6: Debug a Slow Request

Simulate a slow request:
1. Make `web_search` sleep for 5 seconds
2. Process a request that uses web search
3. Use metrics to confirm it's slow
4. Use traces to identify web_search as bottleneck
5. Use logs to see the exact request flow

## Key Takeaways

1. **Observability is not optional in production**
   You can't fix what you can't see. Logs, metrics, and traces are essential.

2. **Use all three pillars together**
   Logs, metrics, and traces complement each other. Metrics alert you, traces show where, logs explain why.

3. **Correlation IDs are critical**
   Without correlation IDs, you can't follow a request through logs. Add them to every log line.

4. **Metrics enable proactive monitoring**
   Dashboards and alerts catch problems before users complain.

5. **Traces reveal performance bottlenecks**
   See exactly where time is spent. Optimize with data, not guesses.

6. **Alert on SLOs, not symptoms**
   One slow request is fine. P95 > SLO for 5 minutes is not. Alert on the latter.

7. **Structured logging > print statements**
   JSON logs are queryable. Print statements are not. Use structlog in production.

8. **Runbooks save time**
   When paged at 3 AM, you don't want to think. You want clear instructions.

## What's Next

In **Chapter 4: Security and Safety**, we'll harden the agent against attacks:

- Threat modeling for AI agents
- Input validation and sanitization
- Prompt injection defense
- Secret management (HashiCorp Vault, AWS Secrets Manager)
- Content moderation
- Audit logging
- Compliance (GDPR, SOC2)

Right now, our agent is reliable and observable. But it's **not secure**. Chapter 4 fixes that.

---

**Code for this chapter**: `code-examples/chapter-03-observability/`
**Next chapter**: Chapter 4 - Security and Safety
