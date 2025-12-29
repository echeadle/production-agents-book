"""
Usage-Based Billing Calculator
Chapter 12: Building an Agent Platform

Calculates monthly bills based on:
- Base subscription fee (tier-based)
- Token usage with overage charges
- Tiered pricing model
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict
import structlog

logger = structlog.get_logger()


class Tier(Enum):
    """Pricing tiers."""

    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


@dataclass
class PricingPlan:
    """Pricing plan configuration."""

    name: str
    base_fee: float  # Monthly base fee
    included_tokens: int  # Tokens included in base fee
    overage_price_per_1k: float  # Price per 1,000 tokens over limit


# =========================================================================
# Pricing Plans
# =========================================================================

PRICING_PLANS: Dict[Tier, PricingPlan] = {
    Tier.STARTER: PricingPlan(
        name="Starter",
        base_fee=29.0,
        included_tokens=100_000,
        overage_price_per_1k=0.10,  # $0.10 per 1K tokens
    ),
    Tier.PROFESSIONAL: PricingPlan(
        name="Professional",
        base_fee=99.0,
        included_tokens=500_000,
        overage_price_per_1k=0.08,  # $0.08 per 1K tokens
    ),
    Tier.ENTERPRISE: PricingPlan(
        name="Enterprise",
        base_fee=499.0,
        included_tokens=5_000_000,
        overage_price_per_1k=0.05,  # $0.05 per 1K tokens
    ),
}


@dataclass
class BillBreakdown:
    """Detailed billing breakdown."""

    tenant_id: str
    tier: Tier
    base_fee: float
    included_tokens: int
    tokens_used: int
    overage_tokens: int
    overage_charge: float
    total_amount: float


class BillingCalculator:
    """
    Calculate monthly bills for tenants.
    """

    def calculate_bill(
        self,
        tenant_id: str,
        tier: Tier,
        tokens_used: int,
    ) -> BillBreakdown:
        """
        Calculate monthly bill for a tenant.

        Args:
            tenant_id: Tenant identifier
            tier: Pricing tier
            tokens_used: Total tokens used this month

        Returns:
            Detailed billing breakdown

        Examples:
            >>> calculator = BillingCalculator()
            >>> bill = calculator.calculate_bill("tenant_123", Tier.PROFESSIONAL, 750_000)
            >>> print(f"Total: ${bill.total_amount:.2f}")
            Total: $119.00
        """
        plan = PRICING_PLANS[tier]

        # Calculate overage
        overage_tokens = max(0, tokens_used - plan.included_tokens)
        overage_charge = (overage_tokens / 1000) * plan.overage_price_per_1k

        # Total bill
        total_amount = plan.base_fee + overage_charge

        logger.info(
            "bill_calculated",
            tenant_id=tenant_id,
            tier=tier.value,
            tokens_used=tokens_used,
            overage_tokens=overage_tokens,
            total_amount=total_amount,
        )

        return BillBreakdown(
            tenant_id=tenant_id,
            tier=tier,
            base_fee=plan.base_fee,
            included_tokens=plan.included_tokens,
            tokens_used=tokens_used,
            overage_tokens=overage_tokens,
            overage_charge=overage_charge,
            total_amount=total_amount,
        )

    def format_bill(self, bill: BillBreakdown) -> str:
        """
        Format bill for display/email.

        Args:
            bill: Bill breakdown

        Returns:
            Formatted bill string
        """
        plan = PRICING_PLANS[bill.tier]

        lines = [
            "=" * 60,
            f"MONTHLY INVOICE - {plan.name.upper()} PLAN",
            "=" * 60,
            f"Tenant ID: {bill.tenant_id}",
            "",
            f"Base Fee ({plan.name}):".ljust(40) + f"${bill.base_fee:.2f}",
            f"  - Includes: {bill.included_tokens:,} tokens",
            "",
            f"Token Usage:".ljust(40) + f"{bill.tokens_used:,} tokens",
            "",
        ]

        if bill.overage_tokens > 0:
            lines.extend([
                f"Overage Usage:".ljust(40) + f"{bill.overage_tokens:,} tokens",
                f"Overage Rate:".ljust(40) + f"${plan.overage_price_per_1k:.2f} per 1,000 tokens",
                f"Overage Charge:".ljust(40) + f"${bill.overage_charge:.2f}",
                "",
            ])

        lines.extend([
            "-" * 60,
            f"TOTAL AMOUNT DUE:".ljust(40) + f"${bill.total_amount:.2f}",
            "=" * 60,
        ])

        return "\n".join(lines)


# =========================================================================
# Example Usage
# =========================================================================


def main():
    """Example usage of billing calculator."""

    calculator = BillingCalculator()

    # Test scenarios
    scenarios = [
        ("tenant_starter", Tier.STARTER, 50_000),  # Under limit
        ("tenant_starter_over", Tier.STARTER, 150_000),  # 50K overage
        ("tenant_pro", Tier.PROFESSIONAL, 750_000),  # 250K overage
        ("tenant_enterprise", Tier.ENTERPRISE, 10_000_000),  # 5M overage
    ]

    for tenant_id, tier, tokens in scenarios:
        bill = calculator.calculate_bill(tenant_id, tier, tokens)
        print(calculator.format_bill(bill))
        print("\n")


if __name__ == "__main__":
    main()
