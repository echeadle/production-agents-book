# Chapter 5: Cost Optimization - Code Examples

This directory contains production-ready code examples for implementing cost optimization strategies in AI agent systems.

## Overview

The examples progress from basic cost tracking to comprehensive budget controls and optimization strategies:

1. **with-cost-tracking/** - Basic cost tracking implementation
2. **dynamic-tools/** - Dynamic tool loading to reduce token overhead
3. **history-management/** - Conversation history optimization
4. **with-caching/** - Prompt caching for cost reduction
5. **model-routing/** - Intelligent model selection based on task complexity
6. **budget-controls/** - Budget enforcement and limits
7. **batching/** - Batch processing for efficiency
8. **complete/** - Fully optimized agent with all strategies

## Prerequisites

- Python 3.11+
- Anthropic API key
- `uv` package manager (recommended) or `pip`

## Setup

### 1. Install uv (if not already installed)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Clone and navigate to example directory

```bash
cd code-examples/chapter-05-cost-optimization/with-cost-tracking
```

### 3. Create virtual environment and install dependencies

```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .
```

### 4. Configure environment

```bash
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

## Example 1: Cost Tracking

**Location**: `with-cost-tracking/`

Learn how to track token usage and costs for every API call.

```bash
cd with-cost-tracking
python agent.py
```

**What it demonstrates**:
- Token usage tracking per API call
- Cost calculation based on model pricing
- Per-conversation cost aggregation
- Cost summary and export to JSON

**Key files**:
- `cost_tracker.py` - Core cost tracking logic
- `agent.py` - Agent with cost tracking integration

## Example 2: Model Routing

**Location**: `model-routing/`

Route tasks to appropriate models (Haiku/Sonnet/Opus) based on complexity.

```bash
cd model-routing
python router.py
```

**What it demonstrates**:
- Task complexity classification
- Automatic model selection
- Cost estimation and tracking
- 15-50% cost reduction through smart routing

**Routing strategy**:
- **Simple tasks** → Haiku (12x cheaper)
- **Moderate tasks** → Sonnet (balanced)
- **Complex tasks** → Opus (most capable)

## Example 3: Budget Controls

**Location**: `budget-controls/`

Enforce hard budget limits to prevent runaway costs.

```bash
cd budget-controls
python budget.py
```

**What it demonstrates**:
- Daily budget enforcement
- Per-conversation budget limits
- Per-user budget limits
- Budget violation alerts
- Graceful handling when budget exceeded

**Budget enforcement**:
- Check budget BEFORE making API calls
- Record actual spend after calls
- Alert at 70%, 85%, 95% thresholds
- Hard stop at 100% budget

## Cost Optimization Strategies

### 1. Token Reduction

**System prompt optimization**:
```python
# Before (487 tokens)
system_prompt = """You are an incredibly helpful AI assistant..."""

# After (89 tokens) - 82% reduction
system_prompt = """You are a helpful assistant."""
```

**Savings**: $358/month at 10,000 calls/day

### 2. Dynamic Tool Loading

Only send tools that might be needed:

```python
# Before: Send all 10 tools (1,500 tokens)
# After: Send only 2 relevant tools (300 tokens)
# Savings: 1,200 tokens/call = $1,080/month at 10,000 calls/day
```

### 3. Prompt Caching

Cache static content (system prompt, tools, documents):

```python
system=[
    {
        "type": "text",
        "text": self.system_prompt,
        "cache_control": {"type": "ephemeral"},
    }
]
```

**Savings**: 90% cost reduction on cached tokens

### 4. Model Routing

Use cheaper models for simple tasks:

**Without routing**: $1,350/month (all Sonnet)
**With routing**: $692/month (smart routing)
**Savings**: $658/month (49% reduction)

## Monitoring and Alerting

### Prometheus Metrics

```python
# Token usage
tokens_total = Counter("agent_tokens_total", ["model", "token_type"])

# Cost tracking
cost_total = Counter("agent_cost_usd_total", ["model"])

# Budget utilization
budget_utilization = Gauge("agent_budget_utilization_pct", ["budget_type"])
```

### Grafana Dashboard

Create dashboards to track:
- Real-time cost per hour
- Daily spend vs budget
- Cost breakdown by model
- Cache hit rate
- Budget utilization %

## Testing

Run tests for each example:

```bash
# In each example directory
pytest tests/ -v
```

## Production Deployment

### Docker

```bash
# Build container
docker build -t cost-aware-agent .

# Run with environment variables
docker run -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY cost-aware-agent
```

### Kubernetes

```bash
# Deploy with budget limits
kubectl apply -f deployment.yaml

# Monitor costs
kubectl logs -f deployment/agent -c cost-exporter
```

## Cost Optimization Checklist

Before deploying to production:

- [ ] Implement cost tracking for all API calls
- [ ] Set up daily/conversation/user budget limits
- [ ] Enable prompt caching for static content
- [ ] Implement model routing for task complexity
- [ ] Optimize system prompts (target <100 tokens)
- [ ] Implement dynamic tool loading
- [ ] Set up conversation history trimming
- [ ] Configure Prometheus metrics export
- [ ] Create Grafana dashboards
- [ ] Set up budget alerts (70%, 85%, 95%, 100%)
- [ ] Test budget enforcement with edge cases
- [ ] Document cost per conversation targets

## Common Issues

### High Token Usage

**Problem**: Conversations using 10x expected tokens

**Solutions**:
- Implement history trimming (keep last 10 messages)
- Remove verbose system prompts
- Use dynamic tool loading
- Enable prompt caching

### Budget Exceeded

**Problem**: Hitting daily budget too early

**Solutions**:
- Analyze top cost conversations
- Route more tasks to Haiku
- Implement per-conversation limits
- Review cache hit rate

### Low Cache Hit Rate

**Problem**: Cache hit rate < 50%

**Solutions**:
- Ensure consistent system prompts
- Keep cache warm (calls within 5min TTL)
- Structure prompts for caching (static content first)

## Performance Benchmarks

### Cost per Conversation (10-turn conversation)

| Strategy | Cost | Savings |
|----------|------|---------|
| Baseline (no optimization) | $0.50 | - |
| + Prompt optimization | $0.38 | 24% |
| + Prompt caching | $0.12 | 76% |
| + Model routing | $0.08 | 84% |
| + All optimizations | $0.06 | 88% |

### Monthly Cost (10,000 conversations/day)

| Strategy | Monthly Cost | Annual Savings |
|----------|--------------|----------------|
| Baseline | $150,000 | - |
| Optimized | $18,000 | $1,584,000 |

## Next Steps

1. Review the code examples in order
2. Integrate cost tracking into your agent
3. Set up budget controls
4. Enable prompt caching
5. Implement model routing
6. Monitor and optimize continuously

## Resources

- [Anthropic API Pricing](https://www.anthropic.com/api)
- [Prompt Caching Documentation](https://docs.anthropic.com/claude/docs/prompt-caching)
- [Token Counting Best Practices](https://docs.anthropic.com/claude/docs/token-counting)

## Support

For questions or issues with these examples:
1. Check the chapter text for detailed explanations
2. Review the inline code comments
3. Check the troubleshooting section above
4. Consult the production readiness checklist in Appendix A
