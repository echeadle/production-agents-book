# Production Best Practices Skill

## Purpose
Guide writing and reviewing content about production deployment, scaling, reliability, and operational excellence for AI agent systems.

## When to Use
- Writing chapters on deployment, scaling, or production operations
- Reviewing production-related code examples
- Researching production patterns and best practices
- Designing production architectures

## Production Principles

### Reliability
- **Retries with exponential backoff**: Handle transient failures gracefully
- **Circuit breakers**: Prevent cascade failures
- **Timeouts**: Every external call must have a timeout
- **Fallback strategies**: Graceful degradation when services fail
- **Health checks**: Monitor agent health continuously
- **Idempotency**: Operations should be safely retryable

### Scalability
- **Horizontal scaling**: Design for multiple instances
- **Stateless design**: Externalize state for scalability
- **Load balancing**: Distribute work across instances
- **Rate limiting**: Protect against overload
- **Backpressure**: Handle upstream/downstream speed mismatches
- **Resource pooling**: Connection pools, thread pools

### Observability
- **Structured logging**: JSON logs with context
- **Distributed tracing**: Track requests across services
- **Metrics collection**: Red metrics (Rate, Errors, Duration)
- **Alerting**: Proactive issue detection
- **Dashboards**: Real-time system visibility

### Security
- **API key rotation**: Never hardcode credentials
- **Least privilege**: Minimal necessary permissions
- **Input validation**: Validate all external inputs
- **Output sanitization**: Prevent injection attacks
- **Audit logging**: Track security-relevant events
- **Secrets management**: Use vault services

### Cost Optimization
- **Token budgets**: Set and enforce limits
- **Caching**: Cache expensive operations
- **Batching**: Group requests when possible
- **Model selection**: Use appropriate model sizes
- **Prompt optimization**: Minimize unnecessary tokens
- **Monitoring costs**: Track and alert on spend

## Code Standards for Production

### Error Handling
```python
# Good: Specific, actionable error handling
try:
    response = await agent.execute(task)
except RateLimitError as e:
    logger.warning(f"Rate limited, retrying: {e}")
    await asyncio.sleep(exponential_backoff(attempt))
    return await retry_with_backoff(agent, task, attempt + 1)
except ValidationError as e:
    logger.error(f"Invalid input: {e}")
    raise
except Exception as e:
    logger.exception(f"Unexpected error: {e}")
    metrics.increment("agent.error.unexpected")
    raise
```

### Logging
```python
# Good: Structured, contextual logging
logger.info(
    "Agent execution completed",
    extra={
        "agent_id": agent.id,
        "task_id": task.id,
        "duration_ms": duration,
        "tokens_used": response.usage.total_tokens,
        "success": True
    }
)
```

### Monitoring
```python
# Good: Comprehensive metrics
with metrics.timer("agent.execution.duration"):
    response = await agent.execute(task)
    metrics.increment("agent.execution.count")
    metrics.gauge("agent.tokens.used", response.usage.total_tokens)
    if response.error:
        metrics.increment("agent.execution.error")
```

## Writing Checklist

When writing production-focused content:

- [ ] Include error handling in all examples
- [ ] Show monitoring/logging integration
- [ ] Discuss failure modes and mitigations
- [ ] Cover cost implications
- [ ] Include security considerations
- [ ] Show testing strategies
- [ ] Provide deployment examples
- [ ] Discuss scaling implications
- [ ] Include real-world tradeoffs
- [ ] Show production-ready code, not toys

## Architecture Patterns

### Recommended
- **Queue-based processing**: Decouple producers/consumers
- **Event-driven**: React to state changes
- **CQRS**: Separate read/write models where appropriate
- **Saga pattern**: Manage distributed transactions
- **Bulkhead pattern**: Isolate failures
- **Strangler fig**: Gradual migration strategy

### Avoid
- **God agents**: Single agent doing everything
- **Synchronous chains**: Long blocking call chains
- **Shared mutable state**: Race conditions and bugs
- **Tight coupling**: Changes cascade everywhere
- **No monitoring**: Flying blind in production

## Research Sources

- SRE books (Google, Microsoft)
- Production readiness checklists
- Cloud provider best practices (AWS, GCP, Azure)
- OWASP security guidelines
- Chaos engineering principles
- Cost optimization case studies

## Common Mistakes to Address

1. **No retries**: Transient failures kill the agent
2. **No timeouts**: Hung requests block forever
3. **No logging**: Can't debug production issues
4. **No metrics**: Can't see what's happening
5. **Hardcoded config**: Can't adapt to environments
6. **No rate limiting**: One bad request takes down the system
7. **No testing**: Works locally, fails in prod
8. **No rollback plan**: Stuck with broken deployment

## Key Messages

- Production is not "development with more servers"
- Every agent call can fail - design for it
- Observability is not optional
- Security must be built in, not bolted on
- Cost control requires active management
- Testing in production is inevitable - do it safely
