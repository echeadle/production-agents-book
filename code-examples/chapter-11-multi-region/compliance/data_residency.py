"""
Data Residency and GDPR Compliance Module
Chapter 11: Multi-Region Deployment

This module enforces data residency requirements for multi-region deployments,
ensuring compliance with GDPR, PDPA, and other data protection regulations.

Key features:
- Route users to compliant regions based on country
- Enforce GDPR data residency for EU users
- Block requests that violate data protection laws
- Track compliance violations for audit
"""

from enum import Enum
from typing import Optional, Dict
from dataclasses import dataclass
import structlog

logger = structlog.get_logger()


class Region(Enum):
    """Available deployment regions."""

    US_EAST = "us-east-1"
    EU_WEST = "eu-west-1"
    AP_SOUTHEAST = "ap-southeast-1"


class DataResidency(Enum):
    """Data residency requirements."""

    EU_GDPR = "eu_gdpr"  # MUST stay in EU (GDPR Article 44)
    US_ONLY = "us_only"  # US data localization
    NONE = "none"  # No specific requirement


@dataclass
class Country:
    """Country information."""

    code: str  # ISO 3166-1 alpha-2 code
    name: str
    residency_requirement: DataResidency


# =========================================================================
# Country-to-Residency Mapping
# =========================================================================

# Countries with strict data residency requirements
COUNTRY_RESIDENCY = {
    # EU countries (GDPR applies)
    "AT": Country("AT", "Austria", DataResidency.EU_GDPR),
    "BE": Country("BE", "Belgium", DataResidency.EU_GDPR),
    "BG": Country("BG", "Bulgaria", DataResidency.EU_GDPR),
    "HR": Country("HR", "Croatia", DataResidency.EU_GDPR),
    "CY": Country("CY", "Cyprus", DataResidency.EU_GDPR),
    "CZ": Country("CZ", "Czech Republic", DataResidency.EU_GDPR),
    "DK": Country("DK", "Denmark", DataResidency.EU_GDPR),
    "EE": Country("EE", "Estonia", DataResidency.EU_GDPR),
    "FI": Country("FI", "Finland", DataResidency.EU_GDPR),
    "FR": Country("FR", "France", DataResidency.EU_GDPR),
    "DE": Country("DE", "Germany", DataResidency.EU_GDPR),
    "GR": Country("GR", "Greece", DataResidency.EU_GDPR),
    "HU": Country("HU", "Hungary", DataResidency.EU_GDPR),
    "IE": Country("IE", "Ireland", DataResidency.EU_GDPR),
    "IT": Country("IT", "Italy", DataResidency.EU_GDPR),
    "LV": Country("LV", "Latvia", DataResidency.EU_GDPR),
    "LT": Country("LT", "Lithuania", DataResidency.EU_GDPR),
    "LU": Country("LU", "Luxembourg", DataResidency.EU_GDPR),
    "MT": Country("MT", "Malta", DataResidency.EU_GDPR),
    "NL": Country("NL", "Netherlands", DataResidency.EU_GDPR),
    "PL": Country("PL", "Poland", DataResidency.EU_GDPR),
    "PT": Country("PT", "Portugal", DataResidency.EU_GDPR),
    "RO": Country("RO", "Romania", DataResidency.EU_GDPR),
    "SK": Country("SK", "Slovakia", DataResidency.EU_GDPR),
    "SI": Country("SI", "Slovenia", DataResidency.EU_GDPR),
    "ES": Country("ES", "Spain", DataResidency.EU_GDPR),
    "SE": Country("SE", "Sweden", DataResidency.EU_GDPR),
    # UK (post-Brexit, but still GDPR-equivalent)
    "GB": Country("GB", "United Kingdom", DataResidency.EU_GDPR),
    # EEA countries (GDPR applies)
    "IS": Country("IS", "Iceland", DataResidency.EU_GDPR),
    "LI": Country("LI", "Liechtenstein", DataResidency.EU_GDPR),
    "NO": Country("NO", "Norway", DataResidency.EU_GDPR),
    # Switzerland (GDPR-equivalent)
    "CH": Country("CH", "Switzerland", DataResidency.EU_GDPR),
    # Non-EU countries (no specific requirement by default)
    "US": Country("US", "United States", DataResidency.NONE),
    "CA": Country("CA", "Canada", DataResidency.NONE),
    "SG": Country("SG", "Singapore", DataResidency.NONE),
    "AU": Country("AU", "Australia", DataResidency.NONE),
    "JP": Country("JP", "Japan", DataResidency.NONE),
    "IN": Country("IN", "India", DataResidency.NONE),
}


# =========================================================================
# Region Router
# =========================================================================


class RegionRouter:
    """
    Routes requests to appropriate region based on country and compliance.
    """

    def __init__(self):
        """Initialize region router with region capabilities."""
        # Which residency requirements each region can satisfy
        self.region_capabilities: Dict[Region, set[DataResidency]] = {
            Region.US_EAST: {DataResidency.US_ONLY, DataResidency.NONE},
            Region.EU_WEST: {DataResidency.EU_GDPR, DataResidency.NONE},
            Region.AP_SOUTHEAST: {DataResidency.NONE},
        }

    def get_compliant_region(self, country_code: str) -> Optional[Region]:
        """
        Get the compliant region for a given country.

        Args:
            country_code: ISO 3166-1 alpha-2 country code (e.g., "DE", "US")

        Returns:
            Region that satisfies data residency requirements, or None if no region available

        Examples:
            >>> router = RegionRouter()
            >>> router.get_compliant_region("DE")  # Germany → EU
            Region.EU_WEST
            >>> router.get_compliant_region("US")  # US → US
            Region.US_EAST
            >>> router.get_compliant_region("SG")  # Singapore → AP
            Region.AP_SOUTHEAST
        """
        # Get country info
        country = COUNTRY_RESIDENCY.get(country_code.upper())

        if not country:
            # Unknown country - default to US (least restrictive)
            logger.warning(
                "unknown_country_code",
                country_code=country_code,
                fallback="US_EAST",
            )
            return Region.US_EAST

        # Get residency requirement
        residency = country.residency_requirement

        # Find compliant region
        for region, capabilities in self.region_capabilities.items():
            if residency in capabilities:
                logger.info(
                    "region_routed",
                    country=country.name,
                    country_code=country_code,
                    residency=residency.value,
                    region=region.value,
                )
                return region

        # No compliant region found
        logger.error(
            "no_compliant_region",
            country=country.name,
            country_code=country_code,
            residency=residency.value,
        )
        return None

    def can_store_in_region(
        self, country_code: str, target_region: Region
    ) -> bool:
        """
        Check if data from a country can be stored in a target region.

        Args:
            country_code: ISO 3166-1 alpha-2 country code
            target_region: Region to check

        Returns:
            True if compliant, False otherwise

        Examples:
            >>> router = RegionRouter()
            >>> router.can_store_in_region("DE", Region.EU_WEST)  # OK
            True
            >>> router.can_store_in_region("DE", Region.US_EAST)  # GDPR violation!
            False
        """
        country = COUNTRY_RESIDENCY.get(country_code.upper())

        if not country:
            # Unknown country - allow (permissive by default)
            return True

        residency = country.residency_requirement
        capabilities = self.region_capabilities.get(target_region, set())

        return residency in capabilities


# =========================================================================
# Compliance Enforcer
# =========================================================================


class ComplianceEnforcer:
    """
    Enforces data residency compliance for API requests.

    Integrates with FastAPI or Flask to validate requests before processing.
    """

    def __init__(self, current_region: Region):
        """
        Initialize compliance enforcer.

        Args:
            current_region: The region this service is running in
        """
        self.current_region = current_region
        self.router = RegionRouter()

    def validate_request(
        self, country_code: str, user_id: str
    ) -> tuple[bool, Optional[str]]:
        """
        Validate if request can be processed in current region.

        Args:
            country_code: User's country code
            user_id: User ID for logging

        Returns:
            Tuple of (is_valid, error_message)

        Examples:
            >>> enforcer = ComplianceEnforcer(Region.EU_WEST)
            >>> enforcer.validate_request("DE", "user_123")
            (True, None)

            >>> enforcer = ComplianceEnforcer(Region.US_EAST)
            >>> enforcer.validate_request("DE", "user_456")
            (False, "GDPR compliance violation...")
        """
        # Check if current region can store data from this country
        can_process = self.router.can_store_in_region(
            country_code, self.current_region
        )

        if can_process:
            logger.info(
                "request_validated",
                country_code=country_code,
                user_id=user_id,
                region=self.current_region.value,
            )
            return True, None

        # Compliance violation
        correct_region = self.router.get_compliant_region(country_code)

        error_message = (
            f"Data residency compliance violation. "
            f"Users from {country_code} must use region {correct_region.value}. "
            f"Please access the service at: https://api-{correct_region.value.split('-')[0]}.agent.company.com"
        )

        logger.error(
            "compliance_violation",
            country_code=country_code,
            user_id=user_id,
            current_region=self.current_region.value,
            required_region=correct_region.value if correct_region else "unknown",
        )

        return False, error_message


# =========================================================================
# FastAPI Integration
# =========================================================================


def create_fastapi_middleware(current_region: Region):
    """
    Create FastAPI middleware for compliance enforcement.

    Usage:
        app = FastAPI()
        enforcer = create_fastapi_middleware(Region.EU_WEST)

        @app.post("/chat")
        async def chat(request: Request):
            # Enforcement happens automatically via middleware
            ...
    """
    from fastapi import Request, HTTPException, status
    from fastapi.responses import JSONResponse

    enforcer = ComplianceEnforcer(current_region)

    async def compliance_middleware(request: Request, call_next):
        """Middleware to enforce compliance on every request."""

        # Extract country code from request
        # Option 1: From header (if client sends it)
        country_code = request.headers.get("X-User-Country")

        # Option 2: From GeoIP lookup (more reliable)
        if not country_code:
            # In production, use MaxMind GeoIP or similar
            client_ip = request.client.host
            country_code = geoip_lookup(client_ip)  # Implement this

        # Option 3: From user profile (if authenticated)
        if not country_code:
            user_id = request.headers.get("X-User-ID")
            if user_id:
                country_code = get_user_country(user_id)  # Implement this

        # Default to US if unknown
        if not country_code:
            country_code = "US"

        # Validate request
        user_id = request.headers.get("X-User-ID", "anonymous")
        is_valid, error_message = enforcer.validate_request(country_code, user_id)

        if not is_valid:
            # HTTP 451: Unavailable For Legal Reasons
            # https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/451
            return JSONResponse(
                status_code=status.HTTP_451_UNAVAILABLE_FOR_LEGAL_REASONS,
                content={
                    "error": "compliance_violation",
                    "message": error_message,
                    "country": country_code,
                    "current_region": current_region.value,
                },
            )

        # Request is compliant - proceed
        response = await call_next(request)
        return response

    return compliance_middleware


# =========================================================================
# Helper Functions (Stubs - Implement based on your infrastructure)
# =========================================================================


def geoip_lookup(ip_address: str) -> str:
    """
    Lookup country code from IP address.

    Implement using MaxMind GeoIP, ipstack, or similar service.

    Args:
        ip_address: Client IP address

    Returns:
        ISO 3166-1 alpha-2 country code
    """
    # Stub implementation
    # In production, use:
    # import geoip2.database
    # reader = geoip2.database.Reader('/path/to/GeoLite2-Country.mmdb')
    # response = reader.country(ip_address)
    # return response.country.iso_code

    logger.warning("geoip_lookup_not_implemented", ip=ip_address)
    return "US"  # Default


def get_user_country(user_id: str) -> Optional[str]:
    """
    Get user's country from user profile.

    Implement by querying your user database.

    Args:
        user_id: User ID

    Returns:
        ISO 3166-1 alpha-2 country code, or None if not found
    """
    # Stub implementation
    # In production:
    # user = db.query(User).filter(User.id == user_id).first()
    # return user.country_code if user else None

    logger.warning("get_user_country_not_implemented", user_id=user_id)
    return None


# =========================================================================
# Example Usage
# =========================================================================


def main():
    """Example usage of compliance enforcement."""

    # Create enforcer for EU region
    eu_enforcer = ComplianceEnforcer(Region.EU_WEST)

    # Test cases
    test_cases = [
        ("DE", "user_germany"),  # Germany → EU (should pass)
        ("US", "user_usa"),  # US → EU (should fail - US user in EU region)
        ("FR", "user_france"),  # France → EU (should pass)
        ("GB", "user_uk"),  # UK → EU (should pass)
    ]

    for country_code, user_id in test_cases:
        is_valid, error = eu_enforcer.validate_request(country_code, user_id)

        if is_valid:
            print(f"✅ {country_code} user {user_id}: Request allowed in EU region")
        else:
            print(f"❌ {country_code} user {user_id}: {error}")

    print("\n" + "=" * 60 + "\n")

    # Create enforcer for US region
    us_enforcer = ComplianceEnforcer(Region.US_EAST)

    for country_code, user_id in test_cases:
        is_valid, error = us_enforcer.validate_request(country_code, user_id)

        if is_valid:
            print(f"✅ {country_code} user {user_id}: Request allowed in US region")
        else:
            print(f"❌ {country_code} user {user_id}: {error}")


if __name__ == "__main__":
    main()
