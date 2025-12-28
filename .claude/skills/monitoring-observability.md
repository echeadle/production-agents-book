# Monitoring and Observability Skill

## Purpose
Guide writing and reviewing content about monitoring, logging, tracing, metrics, and debugging production agent systems.

## When to Use
- Writing chapters on observability and debugging
- Adding monitoring to code examples
- Designing instrumentation strategies
- Troubleshooting production issues

## The Three Pillars of Observability

### 1. Logs
**Purpose**: Discrete events with context

**Good Logging Practices**:
```python
import structlog
from datetime import datetime

logger = structlog.get_logger()

# Good: Structured, searchable, contextual
logger.info(
    "agent_request_started",
    agent_id="agent-123",
    user_id="user-456",
    request_id="req-789",
    task_type="web_search",
    timestamp=datetime.utcnow().isoformat()
)

logger.info(
    "llm_call_completed",
    agent_id="agent-123",
    request_id="req-789",
    model="claude-3-5-sonnet-20241022",
    tokens_prompt=150,
    tokens_completion=300,
    tokens_total=450,
    latency_ms=1250,
    cost_usd=0.002
)

# Bad: Unstructured, hard to search
logger.info("Agent 123 processed request")
```

**Log Levels**:
- `DEBUG`: Detailed diagnostic info
- `INFO`: General informational events
- `WARNING`: Potentially harmful situations
- `ERROR`: Error events that still allow continued operation
- `CRITICAL`: Severe errors requiring immediate attention

### 2. Metrics
**Purpose**: Numerical measurements over time

**Key Metrics for Agent Systems**:

**RED Metrics** (Request-focused):
- **Rate**: Requests per second
- **Errors**: Error rate/count
- **Duration**: Response time distribution

**USE Metrics** (Resource-focused):
- **Utilization**: % of resource in use
- **Saturation**: Queue depth, waiting requests
- **Errors**: Resource-related errors

**Agent-Specific Metrics**:
```python
from prometheus_client import Counter, Histogram, Gauge

# Counters (monotonically increasing)
agent_requests = Counter(
    'agent_requests_total',
    'Total agent requests',
    ['agent_type', 'status']
)

llm_tokens = Counter(
    'llm_tokens_total',
    'Total tokens consumed',
    ['model', 'type']  # type: prompt, completion
)

# Histograms (distributions)
request_duration = Histogram(
    'agent_request_duration_seconds',
    'Agent request duration',
    ['agent_type'],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0]
)

# Gauges (point-in-time values)
active_agents = Gauge(
    'active_agents',
    'Currently running agents',
    ['agent_type']
)

agent_queue_depth = Gauge(
    'agent_queue_depth',
    'Tasks waiting for processing'
)
```

### 3. Traces
**Purpose**: Request flow through distributed system

**Distributed Tracing**:
```python
from opentelemetry import trace
from opentelemetry.trace import SpanKind

tracer = trace.get_tracer(__name__)

async def execute_agent_task(task_id: str):
    with tracer.start_as_current_span(
        "execute_agent_task",
        kind=SpanKind.SERVER,
        attributes={
            "task.id": task_id,
            "agent.type": "researcher"
        }
    ) as span:
        try:
            # Sub-operation: planning
            with tracer.start_as_current_span("plan_task") as plan_span:
                plan = await planner.create_plan(task_id)
                plan_span.set_attribute("plan.steps", len(plan.steps))

            # Sub-operation: LLM call
            with tracer.start_as_current_span("llm_call") as llm_span:
                response = await llm.complete(plan.prompt)
                llm_span.set_attribute("llm.tokens", response.usage.total_tokens)
                llm_span.set_attribute("llm.model", response.model)

            span.set_attribute("task.status", "success")
            return response
        except Exception as e:
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise
```

## Instrumentation Patterns

### Decorator-Based Instrumentation
```python
from functools import wraps
import time

def instrument_agent_call(func):
    """Decorator to instrument agent function calls"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        agent_id = kwargs.get('agent_id', 'unknown')

        logger.info(
            "agent_call_started",
            agent_id=agent_id,
            function=func.__name__
        )

        try:
            result = await func(*args, **kwargs)
            duration = time.time() - start_time

            metrics.timing(f"agent.{func.__name__}.duration", duration)
            metrics.increment(f"agent.{func.__name__}.success")

            logger.info(
                "agent_call_completed",
                agent_id=agent_id,
                function=func.__name__,
                duration_sec=duration,
                success=True
            )
            return result
        except Exception as e:
            duration = time.time() - start_time

            metrics.increment(f"agent.{func.__name__}.error")

            logger.error(
                "agent_call_failed",
                agent_id=agent_id,
                function=func.__name__,
                duration_sec=duration,
                error_type=type(e).__name__,
                error_message=str(e),
                exc_info=True
            )
            raise

    return wrapper
```

### Context Propagation
```python
import contextvars

# Context variables for request tracking
request_id_var = contextvars.ContextVar('request_id', default=None)
user_id_var = contextvars.ContextVar('user_id', default=None)

class RequestContext:
    """Manage request context across async calls"""

    def __init__(self, request_id: str, user_id: str):
        self.request_id = request_id
        self.user_id = user_id
        self.tokens = {}

    def __enter__(self):
        self.tokens['request_id'] = request_id_var.set(self.request_id)
        self.tokens['user_id'] = user_id_var.set(self.user_id)
        return self

    def __exit__(self, *args):
        for var, token in self.tokens.items():
            if var == 'request_id':
                request_id_var.reset(token)
            elif var == 'user_id':
                user_id_var.reset(token)

# Usage
with RequestContext(request_id="req-123", user_id="user-456"):
    await agent.process_task()  # All logs include context
```

## Alerting Strategy

### Alert Levels
1. **Page**: Wake someone up (production down)
2. **Ticket**: Create work item (degraded performance)
3. **Log**: Informational (unusual but not urgent)

### Good Alert Rules
```yaml
# Agent availability
- alert: AgentSystemDown
  expr: up{job="agent-service"} == 0
  for: 1m
  severity: page
  description: "Agent service is down"

# High error rate
- alert: HighAgentErrorRate
  expr: rate(agent_requests_total{status="error"}[5m]) > 0.1
  for: 5m
  severity: page
  description: "Agent error rate > 10%"

# Elevated latency
- alert: HighAgentLatency
  expr: histogram_quantile(0.95, agent_request_duration_seconds) > 5
  for: 10m
  severity: ticket
  description: "P95 latency > 5s"

# Token budget approaching limit
- alert: TokenBudgetNearLimit
  expr: (token_budget_used / token_budget_limit) > 0.8
  for: 5m
  severity: ticket
  description: "Token usage at 80% of budget"

# Queue depth growing
- alert: AgentQueueBacklog
  expr: agent_queue_depth > 100
  for: 15m
  severity: ticket
  description: "Agent queue has > 100 waiting tasks"
```

## Debugging Patterns

### Correlation IDs
```python
import uuid

def generate_correlation_id() -> str:
    """Generate unique correlation ID for request tracking"""
    return str(uuid.uuid4())

async def process_request(user_input: str):
    correlation_id = generate_correlation_id()

    logger.info(
        "request_received",
        correlation_id=correlation_id,
        user_input_length=len(user_input)
    )

    # Pass correlation_id through entire request chain
    result = await agent.execute(
        user_input,
        metadata={"correlation_id": correlation_id}
    )

    logger.info(
        "request_completed",
        correlation_id=correlation_id,
        success=True
    )

    return result
```

### Sampling for High-Volume Systems
```python
import random

class SamplingLogger:
    """Log only a sample of high-volume events"""

    def __init__(self, sample_rate: float = 0.01):
        self.sample_rate = sample_rate

    def should_log(self) -> bool:
        return random.random() < self.sample_rate

    def debug_sampled(self, message: str, **kwargs):
        if self.should_log():
            logger.debug(message, **kwargs)
```

## Dashboard Design

### Key Dashboard Sections

1. **Overview**
   - Request rate (last 1h, 24h)
   - Error rate
   - P50, P95, P99 latency
   - Active agents

2. **LLM Performance**
   - Tokens per minute
   - Cost per hour/day
   - Model usage distribution
   - Cache hit rate

3. **Resource Usage**
   - CPU utilization
   - Memory usage
   - Queue depth
   - Connection pool usage

4. **Business Metrics**
   - Tasks completed
   - User satisfaction (if tracked)
   - Cost per task
   - Throughput trends

## Writing Checklist

When writing observability content:

- [ ] Show all three pillars (logs, metrics, traces)
- [ ] Include correlation IDs in examples
- [ ] Demonstrate structured logging
- [ ] Show metric collection and alerting
- [ ] Include distributed tracing for multi-step operations
- [ ] Cover sampling strategies for high volume
- [ ] Provide dashboard examples
- [ ] Discuss alert design and on-call implications
- [ ] Show debugging workflows
- [ ] Include cost tracking

## Tools to Cover

- **Logging**: structlog, python-json-logger
- **Metrics**: Prometheus, StatsD, CloudWatch
- **Tracing**: OpenTelemetry, Jaeger, Zipkin
- **APM**: Datadog, New Relic, Grafana
- **Log aggregation**: ELK stack, Splunk, Loki

## Key Messages

- You can't fix what you can't see
- Instrument before you need it
- Context is everything in logs
- Alerts should be actionable
- Observability has a cost - be strategic
- Production debugging is different from development
