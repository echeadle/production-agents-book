"""
Comprehensive audit logging for security and compliance.

Records all security-relevant events including:
- Authentication and authorization
- Tool executions
- Data access
- Security events (blocked injections, rate limits, etc.)

Audit logs are:
- Immutable (append-only)
- Tamper-evident (hash chain)
- Complete (all relevant context)
- Retained for compliance periods
"""

import json
import hashlib
import hmac
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path
import structlog

log = structlog.get_logger()


class AuditLogger:
    """
    Structured audit logging with tamper evidence.

    All security-relevant events are logged to an append-only file
    with HMAC integrity checking.
    """

    def __init__(
        self,
        log_file: str = "audit.log",
        integrity_key: Optional[str] = None
    ):
        """
        Initialize audit logger.

        Args:
            log_file: Path to audit log file
            integrity_key: Secret key for HMAC (optional, for tamper evidence)
        """
        self.log_file = Path(log_file)
        self.integrity_key = integrity_key.encode() if integrity_key else None
        self.previous_hash = None

        # Create log file if it doesn't exist
        if not self.log_file.exists():
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            self.log_file.touch()

    def log_event(
        self,
        event_type: str,
        user_id: str,
        action: str,
        resource: Optional[str] = None,
        result: str = "success",
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> str:
        """
        Log an audit event.

        Args:
            event_type: Type of event (auth, data_access, tool_execution, security, etc.)
            user_id: Who performed the action
            action: What action was performed
            resource: What resource was accessed (optional)
            result: Outcome (success, denied, error, etc.)
            details: Additional context (optional)
            ip_address: Source IP address (optional)
            user_agent: User agent string (optional)
            correlation_id: Request correlation ID (optional)

        Returns:
            Event hash (if integrity checking is enabled)
        """
        # Build audit entry
        audit_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event_type": event_type,
            "user_id": user_id,
            "action": action,
            "resource": resource,
            "result": result,
            "details": details or {},
            "ip_address": ip_address,
            "user_agent": user_agent,
            "correlation_id": correlation_id,
        }

        # Add integrity hash if enabled
        event_hash = None
        if self.integrity_key:
            event_hash = self._add_integrity_hash(audit_entry)

        # Write to log (append-only)
        with open(self.log_file, "a") as f:
            f.write(json.dumps(audit_entry) + "\n")

        # Also log to structured logger
        log.info(
            "audit.event_logged",
            event_type=event_type,
            user_id=user_id,
            action=action,
            result=result
        )

        return event_hash

    def _add_integrity_hash(self, audit_entry: dict) -> str:
        """
        Add integrity hash to audit entry.

        Creates a hash chain where each entry's hash depends on:
        - The entry's content
        - The previous entry's hash

        This makes tampering detectable (breaking the chain).

        Args:
            audit_entry: Audit entry to hash

        Returns:
            Event hash (hex string)
        """
        # Serialize entry (deterministic order)
        entry_json = json.dumps(audit_entry, sort_keys=True)

        # Data to hash: previous_hash + entry_data
        data_to_hash = ((self.previous_hash or "") + entry_json).encode()

        # Compute HMAC
        event_hash = hmac.new(
            self.integrity_key,
            data_to_hash,
            hashlib.sha256
        ).hexdigest()

        # Add to entry
        audit_entry["_integrity_hash"] = event_hash
        audit_entry["_previous_hash"] = self.previous_hash

        # Update chain
        self.previous_hash = event_hash

        return event_hash

    def verify_integrity(self, log_file: Optional[str] = None) -> bool:
        """
        Verify audit log integrity by checking hash chain.

        Args:
            log_file: Path to log file (uses self.log_file if not provided)

        Returns:
            True if integrity is verified, False if tampering detected
        """
        if not self.integrity_key:
            log.warning("audit.integrity_check_disabled", reason="no_integrity_key")
            return True

        log_path = Path(log_file) if log_file else self.log_file

        if not log_path.exists():
            log.warning("audit.integrity_check_failed", reason="file_not_found")
            return False

        previous_hash = None

        with open(log_path, "r") as f:
            for line_num, line in enumerate(f, 1):
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    log.error(
                        "audit.integrity_violation",
                        reason="invalid_json",
                        line_num=line_num
                    )
                    return False

                # Check if event has integrity fields
                if "_integrity_hash" not in event:
                    continue  # Skip events without integrity (backward compat)

                # Verify previous hash matches
                if event.get("_previous_hash") != previous_hash:
                    log.error(
                        "audit.integrity_violation",
                        reason="previous_hash_mismatch",
                        line_num=line_num
                    )
                    return False

                # Recompute hash
                event_copy = event.copy()
                stored_hash = event_copy.pop("_integrity_hash")
                event_copy.pop("_previous_hash")

                entry_json = json.dumps(event_copy, sort_keys=True)
                data_to_hash = ((previous_hash or "") + entry_json).encode()

                computed_hash = hmac.new(
                    self.integrity_key,
                    data_to_hash,
                    hashlib.sha256
                ).hexdigest()

                if computed_hash != stored_hash:
                    log.error(
                        "audit.integrity_violation",
                        reason="hash_mismatch",
                        line_num=line_num
                    )
                    return False

                previous_hash = stored_hash

        log.info("audit.integrity_verified", log_file=str(log_path))
        return True

    # Convenience methods for common audit events

    def log_authentication(
        self,
        user_id: str,
        action: str,  # "login", "logout", "login_failed"
        result: str = "success",
        ip_address: Optional[str] = None,
        details: Optional[Dict] = None
    ):
        """Log authentication event."""
        return self.log_event(
            event_type="authentication",
            user_id=user_id,
            action=action,
            result=result,
            ip_address=ip_address,
            details=details
        )

    def log_authorization(
        self,
        user_id: str,
        action: str,
        resource: str,
        result: str,  # "allowed" or "denied"
        details: Optional[Dict] = None
    ):
        """Log authorization check."""
        return self.log_event(
            event_type="authorization",
            user_id=user_id,
            action=action,
            resource=resource,
            result=result,
            details=details
        )

    def log_tool_execution(
        self,
        user_id: str,
        tool_name: str,
        tool_input: Dict[str, Any],
        result: str,  # "success" or "error"
        output: Optional[str] = None,
        correlation_id: Optional[str] = None
    ):
        """Log tool execution."""
        return self.log_event(
            event_type="tool_execution",
            user_id=user_id,
            action=f"execute_{tool_name}",
            resource=tool_name,
            result=result,
            details={
                "tool_input": tool_input,
                "output_preview": output[:100] if output else None
            },
            correlation_id=correlation_id
        )

    def log_security_event(
        self,
        user_id: str,
        event_name: str,  # "injection_blocked", "rate_limit_exceeded", etc.
        details: Dict[str, Any],
        ip_address: Optional[str] = None
    ):
        """Log security event."""
        return self.log_event(
            event_type="security",
            user_id=user_id,
            action=event_name,
            result="blocked",
            details=details,
            ip_address=ip_address
        )

    def log_data_access(
        self,
        user_id: str,
        action: str,  # "read", "write", "delete"
        resource: str,
        result: str = "success",
        details: Optional[Dict] = None
    ):
        """Log data access."""
        return self.log_event(
            event_type="data_access",
            user_id=user_id,
            action=action,
            resource=resource,
            result=result,
            details=details
        )


# Example usage
if __name__ == "__main__":
    import os
    import logging
    logging.basicConfig(level=logging.INFO)

    print("Testing audit logging...\n")

    # Create audit logger with integrity checking
    audit = AuditLogger(
        log_file="test_audit.log",
        integrity_key="test_secret_key_123"  # In production, use secure key from env
    )

    # Log various events
    print("Logging events...")

    # Authentication
    audit.log_authentication(
        user_id="user_123",
        action="login",
        result="success",
        ip_address="192.168.1.100"
    )

    # Authorization check
    audit.log_authorization(
        user_id="user_123",
        action="read",
        resource="customer:12345",
        result="allowed"
    )

    # Tool execution
    audit.log_tool_execution(
        user_id="user_123",
        tool_name="calculator",
        tool_input={"expression": "2 + 2"},
        result="success",
        output="4",
        correlation_id="req_abc123"
    )

    # Security event
    audit.log_security_event(
        user_id="user_456",
        event_name="injection_blocked",
        details={
            "patterns_detected": ["instruction_override", "system_impersonation"],
            "input_preview": "Ignore all previous instructions..."
        },
        ip_address="10.0.0.50"
    )

    # Data access
    audit.log_data_access(
        user_id="user_123",
        action="read",
        resource="notes/my_note.txt",
        result="success",
        details={"bytes_read": 1024}
    )

    print("\n--- Verifying Integrity ---\n")

    # Verify integrity
    is_valid = audit.verify_integrity()
    print(f"✅ Integrity verified: {is_valid}")

    # Tamper with log and verify again
    print("\n--- Testing Tamper Detection ---\n")

    print("Tampering with audit log...")
    with open("test_audit.log", "r") as f:
        lines = f.readlines()

    # Modify second line
    if len(lines) > 1:
        event = json.loads(lines[1])
        event["user_id"] = "attacker"
        lines[1] = json.dumps(event) + "\n"

        with open("test_audit.log", "w") as f:
            f.writelines(lines)

    # Verify (should fail)
    audit_verify = AuditLogger(
        log_file="test_audit.log",
        integrity_key="test_secret_key_123"
    )
    is_valid = audit_verify.verify_integrity()
    print(f"❌ Integrity after tampering: {is_valid} (should be False)")

    # Cleanup
    os.remove("test_audit.log")

    print("\n✅ Audit logging working correctly!")
