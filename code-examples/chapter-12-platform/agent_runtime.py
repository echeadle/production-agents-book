"""
Multi-Tenant Agent Runtime
Chapter 12: Building an Agent Platform

Implements different multi-tenancy patterns:
- Pool Model: Shared runtime with logical isolation
- Silo Model: Dedicated resources per tenant
- Hybrid Model: Mix of pool and silo based on tenant tier
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional
from enum import Enum
import redis
import structlog

from quota_manager import QuotaManager, Quota

logger = structlog.get_logger()


class TenantTier(Enum):
    """Tenant pricing tiers."""

    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


@dataclass
class TenantConfig:
    """Tenant configuration."""

    tenant_id: str
    tier: TenantTier
    quota: Quota
    config: Dict[str, Any]


# =========================================================================
# Pool Model: Shared Runtime with Logical Isolation
# =========================================================================


class MultiTenantRuntime:
    """
    Shared runtime with logical isolation (Pool Model).

    All tenants share the same infrastructure, but data is isolated by tenant_id.
    Cost-effective for small/medium tenants.
    """

    def __init__(self, redis_client: redis.Redis, database, quota_manager: QuotaManager):
        self.redis = redis_client
        self.db = database
        self.quota_manager = quota_manager

    def execute_agent(
        self,
        tenant_id: str,
        agent_config: Dict[str, Any],
        user_input: str,
    ) -> Dict[str, Any]:
        """
        Execute agent with tenant isolation.

        Args:
            tenant_id: Tenant identifier
            agent_config: Agent configuration
            user_input: User's request

        Returns:
            Agent response
        """
        # 1. Check quotas
        tenant = self._load_tenant_config(tenant_id)
        can_proceed, reason = self.quota_manager.check_quota(tenant_id, tenant.quota)

        if not can_proceed:
            return {
                "error": "quota_exceeded",
                "message": reason,
            }

        # 2. Load tenant-specific data (isolated by tenant_id)
        conversation_history = self._load_conversation(tenant_id, agent_config["conversation_id"])

        # 3. Execute agent with resource limits
        try:
            # Increment concurrent agents
            self.quota_manager.increment_concurrent_agents(tenant_id)

            # Execute agent (simplified - actual implementation would use Agent class)
            response = self._run_agent(
                tenant_id=tenant_id,
                agent_config=agent_config,
                user_input=user_input,
                history=conversation_history,
            )

            # 4. Save conversation (tenant-namespaced)
            self._save_conversation(
                tenant_id,
                agent_config["conversation_id"],
                response["history"],
            )

            # 5. Track usage
            self.quota_manager.record_usage(
                tenant_id=tenant_id,
                tokens_used=response["tokens_used"],
                cost=response["cost"],
            )

            return response

        finally:
            # Decrement concurrent agents
            self.quota_manager.decrement_concurrent_agents(tenant_id)

    def _load_tenant_config(self, tenant_id: str) -> TenantConfig:
        """Load tenant configuration from database."""
        # Simplified - would query database
        return TenantConfig(
            tenant_id=tenant_id,
            tier=TenantTier.PROFESSIONAL,
            quota=Quota(
                requests_per_hour=1000,
                tokens_per_month=1_000_000,
                max_spend_per_month=100.0,
                max_concurrent_agents=5,
            ),
            config={},
        )

    def _load_conversation(self, tenant_id: str, conversation_id: str) -> list:
        """Load conversation history (tenant-isolated)."""
        # Use tenant-namespaced Redis key
        key = f"tenant:{tenant_id}:conversation:{conversation_id}"
        history_json = self.redis.get(key)

        if history_json:
            import json
            return json.loads(history_json)

        return []

    def _save_conversation(
        self,
        tenant_id: str,
        conversation_id: str,
        history: list,
    ):
        """Save conversation history (tenant-isolated)."""
        import json

        key = f"tenant:{tenant_id}:conversation:{conversation_id}"
        self.redis.setex(
            key,
            3600 * 24 * 7,  # 7 day TTL
            json.dumps(history),
        )

    def _run_agent(
        self,
        tenant_id: str,
        agent_config: Dict[str, Any],
        user_input: str,
        history: list,
    ) -> Dict[str, Any]:
        """Execute agent (simplified stub)."""
        # In real implementation, this would use the Agent class
        # with the anthropic SDK, tools, etc.

        logger.info(
            "agent_executed",
            tenant_id=tenant_id,
            input_length=len(user_input),
        )

        # Stub response
        return {
            "response": "Agent response here",
            "tokens_used": 1000,
            "cost": 0.05,
            "history": history + [
                {"role": "user", "content": user_input},
                {"role": "assistant", "content": "Agent response here"},
            ],
        }


# =========================================================================
# Hybrid Model: Route Based on Tenant Tier
# =========================================================================


class HybridRuntime:
    """
    Route between pool and silo runtimes based on tenant tier.

    - Enterprise tenants → Dedicated silo
    - Standard tenants → Shared pool
    """

    def __init__(
        self,
        pool_runtime: MultiTenantRuntime,
        silo_runtimes: Dict[str, Any],  # Map of tenant_id → dedicated runtime
    ):
        self.pool_runtime = pool_runtime
        self.silo_runtimes = silo_runtimes

    def execute_agent(
        self,
        tenant_id: str,
        agent_config: Dict[str, Any],
        user_input: str,
    ) -> Dict[str, Any]:
        """
        Route to appropriate runtime based on tenant tier.

        Args:
            tenant_id: Tenant identifier
            agent_config: Agent configuration
            user_input: User's request

        Returns:
            Agent response
        """
        # Check if tenant has dedicated silo
        if tenant_id in self.silo_runtimes:
            logger.info("routing_to_silo", tenant_id=tenant_id)
            runtime = self.silo_runtimes[tenant_id]
        else:
            logger.info("routing_to_pool", tenant_id=tenant_id)
            runtime = self.pool_runtime

        return runtime.execute_agent(tenant_id, agent_config, user_input)


# =========================================================================
# Example Usage
# =========================================================================


def main():
    """Example usage of multi-tenant runtime."""
    from quota_manager import QuotaManager

    # Mock dependencies
    class MockRedis:
        def __init__(self):
            self.data = {}

        def get(self, key):
            return self.data.get(key)

        def setex(self, key, ttl, value):
            self.data[key] = value

        def incr(self, key):
            pass

        def decr(self, key):
            pass

    class MockDB:
        def execute(self, query, params):
            pass

        def commit(self):
            pass

    # Initialize components
    redis_client = MockRedis()
    db = MockDB()
    quota_manager = QuotaManager(redis_client, db)

    # Create pool runtime
    pool_runtime = MultiTenantRuntime(redis_client, db, quota_manager)

    # Execute agent for a tenant
    response = pool_runtime.execute_agent(
        tenant_id="tenant_abc123",
        agent_config={
            "conversation_id": "conv_xyz789",
            "model": "claude-3-5-sonnet-20241022",
        },
        user_input="What is the weather today?",
    )

    print("Agent Response:")
    print(f"  Response: {response['response']}")
    print(f"  Tokens: {response['tokens_used']}")
    print(f"  Cost: ${response['cost']:.4f}")


if __name__ == "__main__":
    main()
