# Production Agent with Full Observability

This is the **complete observability implementation** from Chapter 3, demonstrating the three pillars of observability:

1. **Logs**: Structured logging with correlation IDs (structlog)
2. **Metrics**: RED metrics with Prometheus
3. **Traces**: Distributed tracing with OpenTelemetry

## Features

✅ **Structured Logging**
- JSON output for production, human-readable for development
- Correlation IDs for request tracking across logs
- Contextual fields (user_id, tool_name, tokens, etc.)
- Proper log levels (DEBUG, INFO, WARNING, ERROR)

✅ **Prometheus Metrics**
- RED metrics (Rate, Errors, Duration)
- Request tracking (total, active, duration, errors)
- LLM API metrics (calls, tokens, cost)
- Tool execution metrics
- Circuit breaker state monitoring

✅ **Distributed Tracing**
- OpenTelemetry spans for all operations
- Request-level tracing (agent → LLM → tools)
- Span attributes and events
- OTLP export to Jaeger/Zipkin

✅ **Health Checks**
- Liveness probe (`/health/live`)
- Readiness probe (`/health/ready`)
- Prometheus metrics endpoint (`/metrics`)

✅ **SLO-Based Alerting**
- Availability SLO (99.9% uptime)
- Latency SLO (p95 < 5s)
- Error budget burn rate alerts
- Pre-computed recording rules

## Prerequisites

- Python 3.11+
- `uv` package manager
- Docker (optional, for Prometheus/Grafana)

## Quick Start

### 1. Install Dependencies

```bash
uv sync
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### 3. Run the Agent

```bash
# Development mode (human-readable logs)
LOG_LEVEL=DEBUG JSON_LOGS=false uv run python agent.py
```

### 4. Run Health Check Server (in separate terminal)

```bash
uv run python health.py
```

The server will start on `http://localhost:8080` with:
- `/health/live` - Liveness probe
- `/health/ready` - Readiness probe
- `/metrics` - Prometheus metrics

### 5. Test the Agent

```bash
You: What is 15 multiplied by 23?
Agent: 15 multiplied by 23 equals 345.
```

Check the logs - you'll see structured output with correlation IDs!

## The Three Pillars in Action

### Logs: What Happened

```json
{
  "event": "agent.request_received",
  "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "user_id": "cli_user",
  "input_length": 28,
  "timestamp": "2024-01-15T10:30:45.123Z",
  "level": "info"
}
{
  "event": "llm.call_completed",
  "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "input_tokens": 150,
  "output_tokens": 50,
  "stop_reason": "tool_use",
  "timestamp": "2024-01-15T10:30:46.456Z",
  "level": "info"
}
{
  "event": "tool.executing",
  "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "tool_name": "calculator",
  "tool_input": {"expression": "15 * 23"},
  "timestamp": "2024-01-15T10:30:46.789Z",
  "level": "info"
}
```

**Use logs to answer**: "What happened during request `a1b2c3d4`?"

### Metrics: How Much/How Often

```bash
curl http://localhost:8080/metrics
```

```prometheus
# Request rate
agent_requests_total{status="success",user_id="cli_user"} 42

# Request duration (histogram)
agent_request_duration_seconds_bucket{status="success",le="1.0"} 38
agent_request_duration_seconds_bucket{status="success",le="5.0"} 42

# Token usage
llm_tokens_total{model="claude-3-5-sonnet-20241022",token_type="input"} 4500
llm_tokens_total{model="claude-3-5-sonnet-20241022",token_type="output"} 1200

# Estimated cost
llm_cost_usd_total{model="claude-3-5-sonnet-20241022"} 0.0315
```

**Use metrics to answer**: "What's our request rate? Error rate? Token usage?"

### Traces: Where Was Time Spent

```
Trace ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
Duration: 1.234s

├─ agent.process (1.234s)
   ├─ llm.call (0.456s)
   │  └─ input_tokens=150, output_tokens=50
   ├─ tool.calculator (0.012s)
   │  └─ tool_input="15 * 23", result="345"
   └─ llm.call (0.756s)
      └─ input_tokens=200, output_tokens=75
```

**Use traces to answer**: "Why was this request slow? Where did the time go?"

## Running with Full Observability Stack

### Using Docker Compose (Recommended)

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  # Prometheus - Metrics collection
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - ./alerts.yml:/etc/prometheus/alerts.yml
      - prometheus-data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'

  # Grafana - Visualization
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana-data:/var/lib/grafana
    depends_on:
      - prometheus

  # Jaeger - Distributed tracing
  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "16686:16686"  # Jaeger UI
      - "4317:4317"    # OTLP gRPC
      - "4318:4318"    # OTLP HTTP
    environment:
      - COLLECTOR_OTLP_ENABLED=true

volumes:
  prometheus-data:
  grafana-data:
```

Start the stack:

```bash
docker-compose up -d
```

### Run Agent with Full Observability

```bash
# Set environment for tracing
export OTLP_ENDPOINT=http://localhost:4317
export JSON_LOGS=true
export LOG_LEVEL=INFO

# Start health server (terminal 1)
uv run python health.py

# Start agent (terminal 2)
uv run python agent.py
```

### Access the Observability Stack

- **Agent metrics**: http://localhost:8080/metrics
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin)
- **Jaeger**: http://localhost:16686

## Querying Your Observability Data

### Logs: Find Requests by Correlation ID

```bash
# Stream logs and filter by correlation ID
uv run python agent.py 2>&1 | grep "correlation_id.*a1b2c3d4"
```

In production, send logs to aggregation system:
- **Datadog**: `structlog → JSON → Datadog agent`
- **Elasticsearch**: `structlog → JSON → Filebeat → Elasticsearch`
- **CloudWatch**: `structlog → JSON → CloudWatch Logs`

### Metrics: Query in Prometheus

```promql
# Request rate (requests/second)
rate(agent_requests_total[5m])

# Error rate (percentage)
sum(rate(agent_errors_total[5m])) / sum(rate(agent_requests_total[5m]))

# p95 latency
histogram_quantile(0.95, rate(agent_request_duration_seconds_bucket[5m]))

# Tokens per hour
sum(rate(llm_tokens_total[1h])) * 3600

# Cost per day
sum(rate(llm_cost_usd_total[1d])) * 86400
```

### Traces: View in Jaeger

1. Open http://localhost:16686
2. Select service: `task-automation-agent`
3. Click "Find Traces"
4. Click on a trace to see the timeline
5. Drill down into spans to see attributes and events

## Setting Up Grafana Dashboards

1. Open Grafana: http://localhost:3000
2. Add Prometheus data source:
   - Configuration → Data Sources → Add data source
   - Select "Prometheus"
   - URL: `http://prometheus:9090`
   - Save & Test

3. Import dashboard:
   - Create → Import
   - Use the queries from Chapter 3 to build panels:
     - Request rate: `rate(agent_requests_total[5m])`
     - Error rate: `sum(rate(agent_errors_total[5m])) / sum(rate(agent_requests_total[5m]))`
     - p95 latency: `histogram_quantile(0.95, rate(agent_request_duration_seconds_bucket[5m]))`
     - Active requests: `agent_requests_active`

4. Create alerts:
   - Alerting → Alert rules → New alert rule
   - Use Prometheus data source
   - Example: Alert if error rate > 1%

## Debugging Scenarios

### Scenario 1: "Why is this request slow?"

**Step 1**: Find the trace
- Open Jaeger
- Search for traces with duration > 5s
- Look at the waterfall view

**Step 2**: Identify the bottleneck
- Which span took the most time?
- LLM call? Tool execution? Multiple iterations?

**Step 3**: Check the logs
- Get correlation ID from trace
- Search logs for that correlation ID
- See detailed context of what happened

**Step 4**: Check metrics
- Is p95 latency high overall?
- Is this an isolated incident or a trend?

### Scenario 2: "Why are errors spiking?"

**Step 1**: Check metrics
```promql
# Error rate over time
sum(rate(agent_errors_total[5m])) by (error_type)
```

**Step 2**: Identify error type
- `RateLimitError`? API rate limit hit
- `CircuitBreakerError`? Dependency is down
- `TimeoutError`? Operations taking too long

**Step 3**: Check circuit breaker state
```promql
circuit_breaker_state
```

**Step 4**: Find example in logs
```bash
# Find recent errors
grep "level.*error" logs.json | tail -20
```

**Step 5**: Get full context from traces
- Find trace ID from error log
- View full trace in Jaeger
- See what led to the error

### Scenario 3: "Why are costs so high?"

**Step 1**: Check cost metrics
```promql
# Cost per hour by model
sum(rate(llm_cost_usd_total[1h]) * 3600) by (model)

# Top token consumers
topk(5, sum(rate(llm_tokens_total[1h])) by (user_id))
```

**Step 2**: Find expensive requests in logs
```bash
# Find requests with high token usage
grep "output_tokens" logs.json | jq 'select(.output_tokens > 1000)'
```

**Step 3**: Analyze traces
- Are there unnecessary LLM calls?
- Could we cache results?
- Are we hitting max_tokens too often?

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    User Request                          │
│                  (with correlation ID)                   │
└─────────────────────┬───────────────────────────────────┘
                      │
           ┌──────────▼──────────┐
           │   ObservableAgent   │
           │  ┌───────────────┐  │
           │  │   LOGS        │  │ Structured logging
           │  │   METRICS     │  │ Prometheus metrics
           │  │   TRACES      │  │ OpenTelemetry spans
           │  └───────────────┘  │
           └──────────┬──────────┘
                      │
        ┌─────────────┼─────────────┐
        │             │             │
   ┌────▼────┐   ┌───▼────┐   ┌───▼────┐
   │   LLM   │   │  Tool  │   │  Tool  │
   │  Call   │   │  Exec  │   │  Exec  │
   └────┬────┘   └───┬────┘   └───┬────┘
        │            │            │
        └────────────┼────────────┘
                     │
        ┌────────────▼────────────┐
        │   /metrics endpoint     │
        │   (Prometheus scrapes)  │
        └─────────────────────────┘
```

## Production Deployment

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: task-agent
  labels:
    app: task-agent
spec:
  replicas: 3
  selector:
    matchLabels:
      app: task-agent
  template:
    metadata:
      labels:
        app: task-agent
      annotations:
        # Prometheus annotations for auto-discovery
        prometheus.io/scrape: "true"
        prometheus.io/port: "8080"
        prometheus.io/path: "/metrics"
    spec:
      containers:
      - name: agent
        image: task-agent:v1
        ports:
        - containerPort: 8080
          name: metrics

        env:
        - name: ANTHROPIC_API_KEY
          valueFrom:
            secretKeyRef:
              name: agent-secrets
              key: anthropic-api-key
        - name: JSON_LOGS
          value: "true"
        - name: LOG_LEVEL
          value: "INFO"
        - name: OTLP_ENDPOINT
          value: "http://jaeger-collector:4317"

        livenessProbe:
          httpGet:
            path: /health/live
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 30

        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 10

        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
```

## Troubleshooting

### Logs not appearing?

Check log level:
```bash
export LOG_LEVEL=DEBUG
```

Verify JSON mode:
```bash
export JSON_LOGS=true  # For production
export JSON_LOGS=false # For development (human-readable)
```

### Metrics not being scraped?

Test metrics endpoint:
```bash
curl http://localhost:8080/metrics
```

Check Prometheus targets:
- Open http://localhost:9090/targets
- Agent target should be "UP"

### Traces not appearing in Jaeger?

Check OTLP endpoint:
```bash
export OTLP_ENDPOINT=http://localhost:4317
```

Verify Jaeger is running:
```bash
curl http://localhost:16686
```

Enable console export for debugging:
```bash
export TRACE_CONSOLE=true
uv run python agent.py
```

### High cardinality warning?

Prometheus warning about high cardinality (too many unique label combinations)?

**Fix**: Remove high-cardinality labels like `correlation_id` from metrics.
Keep correlation IDs in logs and traces only.

## Key Files

| File | Purpose |
|------|---------|
| `agent.py` | Main agent with full observability |
| `logging_config.py` | Structured logging configuration |
| `metrics.py` | Prometheus metrics definitions |
| `tracing.py` | OpenTelemetry tracing setup |
| `health.py` | Health checks + metrics endpoint |
| `prometheus.yml` | Prometheus configuration |
| `alerts.yml` | Alert rules (SLO-based) |
| `tools.py` | Tools (from Chapter 2) |
| `retry.py` | Retry logic (from Chapter 2) |
| `circuit_breaker.py` | Circuit breaker (from Chapter 2) |

## What's Next?

This agent has:
- ✅ Reliability (Chapter 2)
- ✅ Observability (Chapter 3)

Still needed:
- ⏳ Security (Chapter 4)
- ⏳ Cost optimization (Chapter 5)
- ⏳ Horizontal scaling (Chapter 6)
- ⏳ Deployment automation (Chapter 9)

## Resources

- [Prometheus Docs](https://prometheus.io/docs/)
- [Grafana Tutorials](https://grafana.com/tutorials/)
- [OpenTelemetry Python](https://opentelemetry.io/docs/instrumentation/python/)
- [Structlog Documentation](https://www.structlog.org/)
- [The Site Reliability Workbook](https://sre.google/workbook/table-of-contents/)

---

**You now have full visibility into your agent!** 🔍

Logs tell you *what happened*, metrics tell you *how much*, and traces tell you *where time was spent*.
