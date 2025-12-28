# Security and Safety Skill

## Purpose
Guide writing and reviewing content about security, safety, guardrails, and responsible AI practices for production agent systems.

## When to Use
- Writing chapters on security, safety, or guardrails
- Reviewing code for security vulnerabilities
- Designing safety mechanisms
- Implementing access controls or validation

## Security Principles

### Defense in Depth
Multiple layers of security controls:
1. **Input validation**: Sanitize all inputs
2. **Authentication**: Verify identity
3. **Authorization**: Check permissions
4. **Rate limiting**: Prevent abuse
5. **Encryption**: Protect data in transit and at rest
6. **Audit logging**: Track security events
7. **Monitoring**: Detect anomalies

### Principle of Least Privilege
- Grant minimum necessary permissions
- Use scoped API keys
- Limit tool access per agent
- Restrict data access
- Time-bound credentials

## Common Vulnerabilities

### 1. Prompt Injection
**Threat**: User input manipulates agent behavior

**Vulnerable Code**:
```python
# Bad: User input directly in system prompt
system_prompt = f"You are a helpful assistant. User query: {user_input}"
response = llm.complete(system_prompt)
```

**Secure Code**:
```python
# Good: Clear separation, input validation
system_prompt = "You are a helpful assistant. Process the user query safely."

# Validate and sanitize input
validated_input = validate_user_input(user_input)

response = llm.complete(
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": validated_input}
    ]
)

def validate_user_input(user_input: str) -> str:
    """Validate and sanitize user input"""
    # Check length
    if len(user_input) > MAX_INPUT_LENGTH:
        raise ValidationError("Input too long")

    # Check for prompt injection patterns
    injection_patterns = [
        r"ignore previous instructions",
        r"system:",
        r"<\|im_start\|>",
        # Add more patterns
    ]

    for pattern in injection_patterns:
        if re.search(pattern, user_input, re.IGNORECASE):
            logger.warning(
                "potential_prompt_injection_detected",
                pattern=pattern,
                input_preview=user_input[:100]
            )
            raise SecurityError("Suspicious input detected")

    return user_input
```

### 2. Tool Misuse
**Threat**: Agent uses tools in unintended ways

**Secure Tool Design**:
```python
from typing import Literal
from pydantic import BaseModel, Field

class FileReadTool(BaseModel):
    """Read files with safety constraints"""

    allowed_directories: list[str] = ["/data/public"]
    max_file_size: int = 10_000_000  # 10MB
    allowed_extensions: list[str] = [".txt", ".json", ".csv"]

    def read_file(self, file_path: str) -> str:
        """Safely read file with validation"""
        # Validate path is in allowed directory
        abs_path = os.path.abspath(file_path)
        if not any(abs_path.startswith(d) for d in self.allowed_directories):
            raise SecurityError(f"Access denied: {file_path}")

        # Validate extension
        ext = os.path.splitext(file_path)[1]
        if ext not in self.allowed_extensions:
            raise SecurityError(f"File type not allowed: {ext}")

        # Check file size
        size = os.path.getsize(abs_path)
        if size > self.max_file_size:
            raise SecurityError(f"File too large: {size} bytes")

        # Validate no path traversal
        if ".." in file_path:
            raise SecurityError("Path traversal detected")

        logger.info(
            "file_read_authorized",
            file_path=abs_path,
            size=size
        )

        with open(abs_path, 'r') as f:
            return f.read()
```

### 3. Data Leakage
**Threat**: Sensitive data exposed through logs, errors, or responses

**Secure Practices**:
```python
import re
from typing import Any

class SensitiveDataRedactor:
    """Redact sensitive data from logs and outputs"""

    PATTERNS = {
        'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        'phone': r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
        'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
        'credit_card': r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b',
        'api_key': r'sk-[a-zA-Z0-9]{32,}',
        'jwt': r'eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+',
    }

    @classmethod
    def redact(cls, text: str) -> str:
        """Redact sensitive data from text"""
        redacted = text
        for data_type, pattern in cls.PATTERNS.items():
            redacted = re.sub(
                pattern,
                f"[REDACTED_{data_type.upper()}]",
                redacted
            )
        return redacted

# Use in logging
logger.info(
    "agent_response",
    response=SensitiveDataRedactor.redact(response_text)
)
```

### 4. API Key Exposure
**Threat**: Credentials leaked in code, logs, or errors

**Secure Secrets Management**:
```python
import os
from typing import Optional

class SecretManager:
    """Secure secret management"""

    def __init__(self):
        self._secrets = {}
        self._load_secrets()

    def _load_secrets(self):
        """Load secrets from environment or secret manager"""
        # Option 1: Environment variables
        self._secrets['anthropic_api_key'] = os.getenv('ANTHROPIC_API_KEY')

        # Option 2: Cloud secret manager (AWS, GCP, Azure)
        # self._secrets['anthropic_api_key'] = self._fetch_from_vault('anthropic_key')

        # Validate secrets loaded
        if not self._secrets.get('anthropic_api_key'):
            raise ConfigurationError("ANTHROPIC_API_KEY not configured")

    def get_secret(self, key: str) -> str:
        """Get secret, never log it"""
        secret = self._secrets.get(key)
        if not secret:
            logger.error(f"secret_not_found", secret_key=key)
            raise SecurityError(f"Secret not found: {key}")
        return secret

    def __repr__(self) -> str:
        """Prevent accidental secret exposure in logs"""
        return f"SecretManager(secrets={list(self._secrets.keys())})"

# Good: Use secret manager
secrets = SecretManager()
client = Anthropic(api_key=secrets.get_secret('anthropic_api_key'))

# Bad: Hardcoded
# client = Anthropic(api_key="sk-ant-...")  # NEVER DO THIS
```

## Safety Guardrails

### Content Filtering
```python
from anthropic import Anthropic

class ContentModerator:
    """Filter harmful content in inputs and outputs"""

    BLOCKED_TOPICS = [
        "violence", "hate_speech", "explicit_content",
        "personal_data", "illegal_activities"
    ]

    def __init__(self, llm_client: Anthropic):
        self.llm = llm_client

    async def check_content(self, text: str) -> dict[str, Any]:
        """Check if content is safe"""
        response = await self.llm.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=100,
            messages=[{
                "role": "user",
                "content": f"""Analyze this text for harmful content.
Check for: {', '.join(self.BLOCKED_TOPICS)}

Text: {text}

Respond with JSON:
{{
    "is_safe": true/false,
    "blocked_topics": ["topic1", "topic2"],
    "severity": "low/medium/high"
}}"""
            }]
        )

        result = json.loads(response.content[0].text)

        if not result['is_safe']:
            logger.warning(
                "harmful_content_detected",
                blocked_topics=result['blocked_topics'],
                severity=result['severity']
            )

        return result

    async def moderate_agent_response(
        self,
        response: str
    ) -> tuple[bool, str]:
        """Moderate agent response before returning to user"""
        moderation = await self.check_content(response)

        if not moderation['is_safe']:
            safe_response = "I cannot provide that information."
            logger.warning(
                "response_blocked",
                topics=moderation['blocked_topics']
            )
            return False, safe_response

        return True, response
```

### Rate Limiting and Quotas
```python
from datetime import datetime, timedelta
from collections import defaultdict
import asyncio

class RateLimiter:
    """Token bucket rate limiter"""

    def __init__(
        self,
        requests_per_minute: int = 60,
        burst_size: int = 10
    ):
        self.rate = requests_per_minute
        self.burst = burst_size
        self.tokens = defaultdict(lambda: burst_size)
        self.last_update = defaultdict(lambda: datetime.now())

    async def acquire(self, user_id: str) -> bool:
        """Attempt to acquire rate limit token"""
        now = datetime.now()
        time_passed = (now - self.last_update[user_id]).total_seconds()

        # Refill tokens based on time passed
        self.tokens[user_id] = min(
            self.burst,
            self.tokens[user_id] + (time_passed * self.rate / 60)
        )
        self.last_update[user_id] = now

        # Check if token available
        if self.tokens[user_id] >= 1:
            self.tokens[user_id] -= 1
            return True

        logger.warning(
            "rate_limit_exceeded",
            user_id=user_id,
            tokens_remaining=self.tokens[user_id]
        )
        return False

# Usage
rate_limiter = RateLimiter(requests_per_minute=60)

async def process_user_request(user_id: str, request: str):
    if not await rate_limiter.acquire(user_id):
        raise RateLimitError("Too many requests. Please try again later.")

    return await agent.process(request)
```

### Budget Controls
```python
class CostController:
    """Control and track token/cost budgets"""

    def __init__(
        self,
        daily_budget_usd: float = 100.0,
        per_request_max_tokens: int = 4000
    ):
        self.daily_budget = daily_budget_usd
        self.max_tokens = per_request_max_tokens
        self.usage_today = 0.0
        self.usage_date = datetime.now().date()

    def check_budget(self, estimated_cost: float) -> bool:
        """Check if request within budget"""
        # Reset daily counter if new day
        today = datetime.now().date()
        if today != self.usage_date:
            self.usage_today = 0.0
            self.usage_date = today

        if self.usage_today + estimated_cost > self.daily_budget:
            logger.error(
                "budget_exceeded",
                daily_budget=self.daily_budget,
                current_usage=self.usage_today,
                requested=estimated_cost
            )
            return False

        return True

    def track_usage(self, actual_cost: float):
        """Track actual usage"""
        self.usage_today += actual_cost
        logger.info(
            "cost_tracked",
            cost=actual_cost,
            daily_total=self.usage_today,
            budget_remaining=self.daily_budget - self.usage_today
        )
```

## Audit Logging

```python
class AuditLogger:
    """Log security-relevant events"""

    @staticmethod
    def log_authentication(
        user_id: str,
        success: bool,
        method: str,
        ip_address: str
    ):
        logger.info(
            "authentication_attempt",
            event_type="authentication",
            user_id=user_id,
            success=success,
            method=method,
            ip_address=ip_address,
            timestamp=datetime.utcnow().isoformat()
        )

    @staticmethod
    def log_authorization(
        user_id: str,
        resource: str,
        action: str,
        granted: bool
    ):
        logger.info(
            "authorization_check",
            event_type="authorization",
            user_id=user_id,
            resource=resource,
            action=action,
            granted=granted,
            timestamp=datetime.utcnow().isoformat()
        )

    @staticmethod
    def log_sensitive_operation(
        user_id: str,
        operation: str,
        details: dict
    ):
        logger.info(
            "sensitive_operation",
            event_type="sensitive_operation",
            user_id=user_id,
            operation=operation,
            details=details,
            timestamp=datetime.utcnow().isoformat()
        )
```

## Writing Checklist

When writing security/safety content:

- [ ] Show input validation examples
- [ ] Include output sanitization
- [ ] Demonstrate secure secret management
- [ ] Cover authentication and authorization
- [ ] Include rate limiting
- [ ] Show content moderation
- [ ] Demonstrate audit logging
- [ ] Discuss threat models
- [ ] Include security testing strategies
- [ ] Cover compliance considerations (GDPR, SOC2, etc.)
- [ ] Show secure error handling (don't leak info)
- [ ] Include budget/quota controls

## Security Testing

### Penetration Testing Scenarios
1. Prompt injection attempts
2. Tool misuse attempts
3. Rate limit bypass attempts
4. Authentication bypass attempts
5. Data exfiltration attempts
6. Privilege escalation attempts

### Security Code Review Checklist
- [ ] No hardcoded secrets
- [ ] Input validation on all user inputs
- [ ] Output sanitization before display
- [ ] Proper error handling (no info leakage)
- [ ] Secure random generation
- [ ] Safe deserialization
- [ ] SQL injection prevention (parameterized queries)
- [ ] Path traversal prevention
- [ ] CSRF protection
- [ ] XSS prevention

## Compliance Considerations

### GDPR (EU)
- User data rights (access, deletion, portability)
- Consent management
- Data minimization
- Purpose limitation
- Breach notification

### SOC 2
- Access controls
- Change management
- Monitoring and incident response
- Encryption
- Vendor management

### HIPAA (Healthcare)
- PHI protection
- Access logging
- Encryption requirements
- Business associate agreements

## Key Messages

- Security is not a feature, it's a requirement
- Defense in depth - multiple layers
- Validate inputs, sanitize outputs
- Never trust, always verify
- Fail secure (deny by default)
- Log security events for audit
- Regular security reviews and testing
- Compliance is ongoing, not one-time
