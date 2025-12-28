# Code Review Skill - Production Systems

## Purpose
Guide code review for production-grade agent systems, ensuring quality, reliability, security, and maintainability.

## When to Use
- Reviewing code examples for chapters
- Validating production patterns
- Checking error handling and edge cases
- Ensuring code meets production standards

## Review Checklist

### 1. Error Handling
**Required**:
- [ ] All external calls have try-except blocks
- [ ] Specific exception types caught (not bare `except`)
- [ ] Errors logged with context
- [ ] Metrics incremented on errors
- [ ] Graceful degradation where possible
- [ ] No swallowed exceptions
- [ ] User-friendly error messages
- [ ] Internal errors don't leak to users

**Good Example**:
```python
async def call_llm(prompt: str) -> str:
    """Call LLM with proper error handling"""
    try:
        response = await llm.create(
            messages=[{"role": "user", "content": prompt}],
            timeout=30.0
        )
        metrics.increment("llm.success")
        return response.content[0].text

    except TimeoutError as e:
        logger.error("llm_timeout", prompt_length=len(prompt), timeout=30.0)
        metrics.increment("llm.timeout")
        raise RetryableError("LLM request timed out") from e

    except RateLimitError as e:
        logger.warning("llm_rate_limited", retry_after=e.retry_after)
        metrics.increment("llm.rate_limited")
        raise RetryableError(f"Rate limited, retry after {e.retry_after}s") from e

    except ValidationError as e:
        logger.error("llm_invalid_response", error=str(e))
        metrics.increment("llm.validation_error")
        raise NonRetryableError("Invalid LLM response") from e

    except Exception as e:
        logger.exception("llm_unexpected_error")
        metrics.increment("llm.error.unexpected")
        raise NonRetryableError("LLM call failed") from e
```

### 2. Logging and Observability
**Required**:
- [ ] Structured logging (JSON/key-value)
- [ ] Appropriate log levels
- [ ] Correlation IDs in logs
- [ ] No sensitive data in logs
- [ ] Metrics for key operations
- [ ] Distributed tracing where applicable
- [ ] Performance timing logged

**Good Example**:
```python
async def process_task(task_id: str, user_id: str) -> Result:
    """Process task with full observability"""
    correlation_id = generate_correlation_id()
    start_time = time.time()

    logger.info(
        "task_processing_started",
        correlation_id=correlation_id,
        task_id=task_id,
        user_id=user_id
    )

    try:
        with metrics.timer("task.processing.duration"):
            result = await _execute_task(task_id)

        duration = time.time() - start_time

        logger.info(
            "task_processing_completed",
            correlation_id=correlation_id,
            task_id=task_id,
            duration_sec=duration,
            result_size=len(result.data)
        )

        metrics.increment("task.success")
        return result

    except Exception as e:
        duration = time.time() - start_time

        logger.error(
            "task_processing_failed",
            correlation_id=correlation_id,
            task_id=task_id,
            duration_sec=duration,
            error_type=type(e).__name__,
            exc_info=True
        )

        metrics.increment("task.error")
        raise
```

### 3. Type Hints and Validation
**Required**:
- [ ] Type hints on all function signatures
- [ ] Return type annotations
- [ ] Pydantic models for data validation
- [ ] Runtime validation at boundaries
- [ ] No `Any` types (or justified)

**Good Example**:
```python
from typing import Optional
from pydantic import BaseModel, Field, validator

class TaskRequest(BaseModel):
    """Validated task request"""
    task_id: str = Field(..., min_length=1, max_length=100)
    user_id: str = Field(..., min_length=1, max_length=100)
    priority: int = Field(default=0, ge=0, le=10)
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    metadata: dict[str, str] = Field(default_factory=dict)

    @validator('metadata')
    def validate_metadata_size(cls, v):
        if len(json.dumps(v)) > 10000:
            raise ValueError("Metadata too large")
        return v

async def process_task_request(request: TaskRequest) -> TaskResult:
    """Process validated task request"""
    # request is guaranteed to be valid
    ...
```

### 4. Resource Management
**Required**:
- [ ] Context managers for resources (files, connections)
- [ ] Explicit cleanup in finally blocks
- [ ] Connection pooling for databases/APIs
- [ ] Timeouts on all blocking operations
- [ ] Resource limits enforced
- [ ] No resource leaks

**Good Example**:
```python
import asyncio
from contextlib import asynccontextmanager

class LLMClient:
    """LLM client with connection pooling"""

    def __init__(self, max_connections: int = 10):
        self._semaphore = asyncio.Semaphore(max_connections)
        self._client = Anthropic()

    @asynccontextmanager
    async def _get_connection(self):
        """Acquire connection from pool"""
        async with self._semaphore:
            try:
                yield self._client
            finally:
                # Cleanup happens automatically
                pass

    async def complete(
        self,
        prompt: str,
        timeout: float = 30.0
    ) -> str:
        """Complete with resource management"""
        async with self._get_connection() as client:
            try:
                response = await asyncio.wait_for(
                    client.messages.create(
                        model="claude-3-5-sonnet-20241022",
                        max_tokens=1000,
                        messages=[{"role": "user", "content": prompt}]
                    ),
                    timeout=timeout
                )
                return response.content[0].text
            except asyncio.TimeoutError:
                logger.error("llm_timeout", timeout=timeout)
                raise
```

### 5. Testability
**Required**:
- [ ] Functions do one thing
- [ ] Dependencies injected (not hardcoded)
- [ ] Pure functions where possible
- [ ] Side effects isolated
- [ ] Mock points clear
- [ ] Test examples included

**Good Example**:
```python
# Good: Dependency injection
class AgentExecutor:
    def __init__(
        self,
        llm_client: LLMClient,
        memory: Memory,
        logger: Logger
    ):
        self.llm = llm_client
        self.memory = memory
        self.logger = logger

    async def execute(self, task: str) -> str:
        # Easy to test with mocks
        context = await self.memory.get_context()
        response = await self.llm.complete(f"{context}\n{task}")
        await self.memory.save(response)
        return response

# Test
async def test_executor():
    mock_llm = Mock(spec=LLMClient)
    mock_memory = Mock(spec=Memory)
    mock_logger = Mock(spec=Logger)

    executor = AgentExecutor(mock_llm, mock_memory, mock_logger)
    result = await executor.execute("test task")

    assert mock_llm.complete.called
    assert mock_memory.save.called
```

### 6. Performance
**Required**:
- [ ] Async/await for I/O operations
- [ ] Parallel operations where possible
- [ ] Caching for expensive operations
- [ ] Pagination for large datasets
- [ ] Resource limits enforced
- [ ] No N+1 query patterns

**Good Example**:
```python
import asyncio
from functools import lru_cache

class AgentOrchestrator:
    def __init__(self, cache_size: int = 128):
        self._cache = lru_cache(maxsize=cache_size)(self._compute_plan)

    async def process_batch(
        self,
        tasks: list[str],
        max_concurrent: int = 10
    ) -> list[Result]:
        """Process tasks in parallel with concurrency limit"""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_with_limit(task: str) -> Result:
            async with semaphore:
                return await self._process_single(task)

        # Process all tasks concurrently with limit
        results = await asyncio.gather(*[
            process_with_limit(task)
            for task in tasks
        ])

        return results

    @staticmethod
    def _compute_plan(task_hash: str) -> Plan:
        """Cached expensive planning operation"""
        # Expensive computation here
        ...
```

### 7. Security
**Required**:
- [ ] No hardcoded secrets
- [ ] Input validation
- [ ] Output sanitization
- [ ] SQL parameterization
- [ ] Path traversal prevention
- [ ] Rate limiting
- [ ] Authentication/authorization
- [ ] Audit logging

### 8. Configuration
**Required**:
- [ ] Configuration from environment
- [ ] Sensible defaults
- [ ] Validation on startup
- [ ] No config in code
- [ ] Environment-specific configs
- [ ] Secret management

**Good Example**:
```python
from pydantic import BaseSettings, Field

class AgentConfig(BaseSettings):
    """Agent configuration from environment"""

    # LLM settings
    anthropic_api_key: str = Field(..., env="ANTHROPIC_API_KEY")
    model_name: str = Field(
        default="claude-3-5-sonnet-20241022",
        env="MODEL_NAME"
    )
    max_tokens: int = Field(default=1000, env="MAX_TOKENS", ge=1, le=4096)

    # Performance
    request_timeout: float = Field(default=30.0, env="REQUEST_TIMEOUT", gt=0)
    max_concurrent: int = Field(default=10, env="MAX_CONCURRENT", ge=1, le=100)

    # Rate limiting
    requests_per_minute: int = Field(default=60, env="RATE_LIMIT", ge=1)

    class Config:
        env_file = ".env"
        case_sensitive = False

# Usage
config = AgentConfig()  # Validates on creation
```

### 9. Documentation
**Required**:
- [ ] Docstrings on all public functions
- [ ] Type hints in docstrings if complex
- [ ] Examples in docstrings
- [ ] README for code examples
- [ ] Inline comments for non-obvious logic
- [ ] No commented-out code

**Good Example**:
```python
async def execute_agent_with_retry(
    agent: Agent,
    task: str,
    max_retries: int = 3,
    backoff_factor: float = 2.0
) -> AgentResult:
    """Execute agent with exponential backoff retry logic.

    Retries on transient failures (timeouts, rate limits) but not on
    validation errors or other non-retryable failures.

    Args:
        agent: The agent to execute
        task: Task description to process
        max_retries: Maximum number of retry attempts (default: 3)
        backoff_factor: Multiplier for backoff delay (default: 2.0)

    Returns:
        AgentResult: The result from successful execution

    Raises:
        RetryableError: If all retries exhausted
        NonRetryableError: If non-retryable error occurs

    Example:
        >>> agent = Agent(llm_client)
        >>> result = await execute_agent_with_retry(
        ...     agent,
        ...     "Analyze this text",
        ...     max_retries=5
        ... )
    """
    for attempt in range(max_retries):
        try:
            return await agent.execute(task)
        except RetryableError as e:
            if attempt == max_retries - 1:
                raise
            delay = backoff_factor ** attempt
            logger.info(f"Retrying after {delay}s", attempt=attempt)
            await asyncio.sleep(delay)
        except NonRetryableError:
            raise  # Don't retry
```

## Code Smells to Watch For

### Anti-Patterns
- ❌ Bare `except:` clauses
- ❌ Swallowed exceptions
- ❌ Hardcoded configuration
- ❌ Global mutable state
- ❌ God classes (doing too much)
- ❌ No logging
- ❌ No type hints
- ❌ Synchronous I/O in async code
- ❌ No timeouts on network calls
- ❌ No retry logic

### Red Flags
- 🚩 Functions > 50 lines
- 🚩 Files > 500 lines
- 🚩 Cyclomatic complexity > 10
- 🚩 No error handling
- 🚩 No tests
- 🚩 Magic numbers
- 🚩 Commented-out code
- 🚩 TODO comments in production code

## Review Process

1. **First Pass**: Correctness
   - Does it work?
   - Are there bugs?
   - Edge cases handled?

2. **Second Pass**: Production Readiness
   - Error handling
   - Logging
   - Metrics
   - Security

3. **Third Pass**: Maintainability
   - Code clarity
   - Documentation
   - Tests
   - Simplicity

4. **Fourth Pass**: Performance
   - Async operations
   - Resource usage
   - Scalability

## Key Messages for Book

- Production code is not "development code that works"
- Every line is a maintenance burden
- Explicit is better than clever
- Code is read more than written
- Future you will debug this at 3am
- Make it easy to understand what went wrong
