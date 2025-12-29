"""
Quota Management System for Multi-Tenant Agent Platform
Chapter 12: Building an Agent Platform

Enforces resource quotas across multiple dimensions:
- Request rate limits
- Token quotas
- Spend budgets
- Concurrent agent limits
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
import redis
import structlog

logger = structlog.get_logger()


@dataclass
class Quota:
    """Tenant resource quotas."""

    requests_per_hour: int
    tokens_per_month: int
    max_spend_per_month: float  # dollars
    max_concurrent_agents: int


@dataclass
class Usage:
    """Current tenant usage."""

    requests_this_hour: int
    tokens_this_month: int
    spend_this_month: float  # dollars
    concurrent_agents: int


class QuotaManager:
    """
    Manages and enforces resource quotas for multi-tenant platform.

    Uses Redis for fast quota checking and tracking.
    """

    def __init__(self, redis_client: redis.Redis, database):
        """
        Initialize quota manager.

        Args:
            redis_client: Redis connection for fast quota tracking
            database: Database connection for persistent usage records
        """
        self.redis = redis_client
        self.db = database

    def check_quota(self, tenant_id: str, quota: Quota) -> tuple[bool, Optional[str]]:
        """
        Check if tenant is within quota before allowing request.

        Args:
            tenant_id: Tenant identifier
            quota: Tenant's quota limits

        Returns:
            Tuple of (can_proceed, violation_reason)

        Examples:
            >>> manager = QuotaManager(redis_client, db)
            >>> quota = Quota(requests_per_hour=1000, tokens_per_month=1000000, ...)
            >>> can_proceed, reason = manager.check_quota("tenant_123", quota)
            >>> if not can_proceed:
            ...     return {"error": reason}, 429  # Too Many Requests
        """
        usage = self.get_current_usage(tenant_id)

        # Check request rate limit
        if usage.requests_this_hour >= quota.requests_per_hour:
            logger.warning(
                "quota_exceeded_requests",
                tenant_id=tenant_id,
                requests_this_hour=usage.requests_this_hour,
                limit=quota.requests_per_hour,
            )
            return (
                False,
                f"Request rate limit exceeded. Limit: {quota.requests_per_hour}/hour",
            )

        # Check token quota
        if usage.tokens_this_month >= quota.tokens_per_month:
            logger.warning(
                "quota_exceeded_tokens",
                tenant_id=tenant_id,
                tokens_this_month=usage.tokens_this_month,
                limit=quota.tokens_per_month,
            )
            return (
                False,
                f"Token quota exceeded. Limit: {quota.tokens_per_month:,} tokens/month",
            )

        # Check spend budget
        if usage.spend_this_month >= quota.max_spend_per_month:
            logger.warning(
                "quota_exceeded_spend",
                tenant_id=tenant_id,
                spend_this_month=usage.spend_this_month,
                limit=quota.max_spend_per_month,
            )
            return (
                False,
                f"Monthly budget exceeded. Limit: ${quota.max_spend_per_month:.2f}/month",
            )

        # Check concurrent agents
        if usage.concurrent_agents >= quota.max_concurrent_agents:
            logger.warning(
                "quota_exceeded_concurrent",
                tenant_id=tenant_id,
                concurrent_agents=usage.concurrent_agents,
                limit=quota.max_concurrent_agents,
            )
            return (
                False,
                f"Concurrent agent limit exceeded. Limit: {quota.max_concurrent_agents}",
            )

        # All checks passed
        return True, None

    def record_usage(
        self,
        tenant_id: str,
        tokens_used: int = 0,
        cost: float = 0.0,
    ):
        """
        Record usage for a tenant request.

        Args:
            tenant_id: Tenant identifier
            tokens_used: Number of tokens consumed
            cost: Cost in dollars
        """
        now = datetime.now()

        # Increment request counter (expires after 1 hour)
        requests_key = self._get_requests_key(tenant_id, now)
        self.redis.incr(requests_key)
        self.redis.expire(requests_key, 3600)  # 1 hour TTL

        # Increment token counter (expires end of month)
        tokens_key = self._get_tokens_key(tenant_id, now)
        self.redis.incrby(tokens_key, tokens_used)
        self.redis.expireat(tokens_key, self._end_of_month(now))

        # Increment spend counter (expires end of month)
        spend_key = self._get_spend_key(tenant_id, now)
        self.redis.incrbyfloat(spend_key, cost)
        self.redis.expireat(spend_key, self._end_of_month(now))

        # Also record in database for permanent tracking and billing
        self._persist_usage(tenant_id, tokens_used, cost)

        logger.info(
            "usage_recorded",
            tenant_id=tenant_id,
            tokens=tokens_used,
            cost=cost,
        )

    def get_current_usage(self, tenant_id: str) -> Usage:
        """
        Get current usage for a tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            Usage object with current usage
        """
        now = datetime.now()

        # Get requests this hour
        requests_key = self._get_requests_key(tenant_id, now)
        requests_this_hour = int(self.redis.get(requests_key) or 0)

        # Get tokens this month
        tokens_key = self._get_tokens_key(tenant_id, now)
        tokens_this_month = int(self.redis.get(tokens_key) or 0)

        # Get spend this month
        spend_key = self._get_spend_key(tenant_id, now)
        spend_this_month = float(self.redis.get(spend_key) or 0)

        # Get concurrent agents
        concurrent_key = f"tenant:{tenant_id}:concurrent_agents"
        concurrent_agents = int(self.redis.get(concurrent_key) or 0)

        return Usage(
            requests_this_hour=requests_this_hour,
            tokens_this_month=tokens_this_month,
            spend_this_month=spend_this_month,
            concurrent_agents=concurrent_agents,
        )

    def increment_concurrent_agents(self, tenant_id: str):
        """Increment concurrent agent counter."""
        key = f"tenant:{tenant_id}:concurrent_agents"
        self.redis.incr(key)

    def decrement_concurrent_agents(self, tenant_id: str):
        """Decrement concurrent agent counter."""
        key = f"tenant:{tenant_id}:concurrent_agents"
        self.redis.decr(key)

    # =====================================================================
    # Helper Methods
    # =====================================================================

    def _get_requests_key(self, tenant_id: str, dt: datetime) -> str:
        """Get Redis key for hourly request counter."""
        hour_str = dt.strftime("%Y-%m-%d-%H")
        return f"tenant:{tenant_id}:requests:{hour_str}"

    def _get_tokens_key(self, tenant_id: str, dt: datetime) -> str:
        """Get Redis key for monthly token counter."""
        month_str = dt.strftime("%Y-%m")
        return f"tenant:{tenant_id}:tokens:{month_str}"

    def _get_spend_key(self, tenant_id: str, dt: datetime) -> str:
        """Get Redis key for monthly spend counter."""
        month_str = dt.strftime("%Y-%m")
        return f"tenant:{tenant_id}:spend:{month_str}"

    def _end_of_month(self, dt: datetime) -> int:
        """Get Unix timestamp for end of month."""
        # Go to first day of next month, then subtract 1 second
        if dt.month == 12:
            next_month = dt.replace(year=dt.year + 1, month=1, day=1)
        else:
            next_month = dt.replace(month=dt.month + 1, day=1)

        end_of_month = next_month - timedelta(seconds=1)
        return int(end_of_month.timestamp())

    def _persist_usage(self, tenant_id: str, tokens: int, cost: float):
        """
        Persist usage to database for billing and analytics.

        Args:
            tenant_id: Tenant identifier
            tokens: Tokens used
            cost: Cost in dollars
        """
        try:
            # This would insert into a usage_records table
            # Simplified example - implement based on your DB schema
            self.db.execute(
                """
                INSERT INTO usage_records (tenant_id, timestamp, tokens, cost)
                VALUES (%s, %s, %s, %s)
                """,
                (tenant_id, datetime.now(), tokens, cost),
            )
            self.db.commit()

        except Exception as e:
            logger.error(
                "failed_to_persist_usage",
                tenant_id=tenant_id,
                error=str(e),
            )
            # Don't fail the request if DB write fails
            # Redis usage tracking is still recorded


# =========================================================================
# Example Usage
# =========================================================================


def main():
    """Example usage of quota manager."""

    # Mock Redis and database
    class MockRedis:
        def __init__(self):
            self.data = {}

        def get(self, key):
            return self.data.get(key)

        def incr(self, key):
            self.data[key] = self.data.get(key, 0) + 1

        def incrby(self, key, amount):
            self.data[key] = self.data.get(key, 0) + amount

        def incrbyfloat(self, key, amount):
            self.data[key] = self.data.get(key, 0.0) + amount

        def decr(self, key):
            self.data[key] = max(0, self.data.get(key, 0) - 1)

        def expire(self, key, seconds):
            pass

        def expireat(self, key, timestamp):
            pass

    class MockDB:
        def execute(self, query, params):
            pass

        def commit(self):
            pass

    # Initialize manager
    redis_client = MockRedis()
    db = MockDB()
    manager = QuotaManager(redis_client, db)

    # Define tenant quota
    quota = Quota(
        requests_per_hour=1000,
        tokens_per_month=1_000_000,
        max_spend_per_month=100.0,
        max_concurrent_agents=5,
    )

    # Simulate usage
    tenant_id = "tenant_abc123"

    # Check quota (should pass initially)
    can_proceed, reason = manager.check_quota(tenant_id, quota)
    print(f"Quota check: {can_proceed} ({reason})")

    # Record some usage
    manager.record_usage(tenant_id, tokens_used=1000, cost=0.05)
    manager.record_usage(tenant_id, tokens_used=2000, cost=0.10)

    # Check current usage
    usage = manager.get_current_usage(tenant_id)
    print(f"\nCurrent usage:")
    print(f"  Requests this hour: {usage.requests_this_hour}")
    print(f"  Tokens this month: {usage.tokens_this_month:,}")
    print(f"  Spend this month: ${usage.spend_this_month:.2f}")
    print(f"  Concurrent agents: {usage.concurrent_agents}")

    # Simulate hitting quota
    for _ in range(1000):
        manager.record_usage(tenant_id, tokens_used=1000, cost=0.05)

    # Check quota again (should fail)
    can_proceed, reason = manager.check_quota(tenant_id, quota)
    print(f"\nQuota check after hitting limit: {can_proceed}")
    if not can_proceed:
        print(f"  Reason: {reason}")


if __name__ == "__main__":
    main()
