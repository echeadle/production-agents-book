"""
Alert Router for Production Incidents
Chapter 10: Incident Response

Routes alerts to appropriate channels based on severity:
- CRITICAL: Page on-call immediately + Slack #incidents
- WARNING: Page during business hours, Slack otherwise
- INFO: Slack notification only

Integration:
- PagerDuty API for paging
- Slack API for notifications
- Prometheus Alertmanager webhook receiver
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
import structlog

logger = structlog.get_logger()


class Severity(Enum):
    """Alert severity levels."""

    CRITICAL = "critical"  # Page immediately (SEV1)
    WARNING = "warning"  # Page during business hours (SEV2-3)
    INFO = "info"  # Slack notification only (SEV4)


@dataclass
class Alert:
    """Alert information from Prometheus."""

    name: str
    severity: Severity
    description: str
    runbook_url: str
    dashboard_url: str
    value: float
    impact: Optional[str] = None
    action: Optional[str] = None


class AlertRouter:
    """
    Route alerts to appropriate channels based on severity.

    This class integrates with:
    - PagerDuty for paging on-call engineers
    - Slack for team notifications
    - Prometheus Alertmanager as webhook receiver
    """

    def __init__(self, pagerduty_client, slack_client):
        """
        Initialize alert router.

        Args:
            pagerduty_client: PagerDuty API client
            slack_client: Slack API client
        """
        self.pagerduty = pagerduty_client
        self.slack = slack_client

    def handle_alert(self, alert: Alert):
        """
        Route alert to appropriate destination based on severity.

        Args:
            alert: Alert to route
        """
        logger.info(
            "alert_received",
            alert=alert.name,
            severity=alert.severity.value,
            value=alert.value,
        )

        if alert.severity == Severity.CRITICAL:
            # SEV1: Page on-call immediately
            self._page_oncall(alert)
            self._post_to_slack(alert, channel="#incidents", urgent=True)

        elif alert.severity == Severity.WARNING:
            # SEV2-3: Page during business hours, slack otherwise
            if self._is_business_hours():
                self._page_oncall(alert)
            else:
                self._post_to_slack(alert, channel="#on-call", urgent=False)

        elif alert.severity == Severity.INFO:
            # SEV4: Slack notification only
            self._post_to_slack(alert, channel="#alerts", urgent=False)

    def _page_oncall(self, alert: Alert):
        """
        Send page to on-call engineer via PagerDuty.

        Args:
            alert: Alert to page about
        """
        try:
            self.pagerduty.trigger_incident(
                title=f"[{alert.severity.value.upper()}] {alert.name}",
                description=alert.description,
                severity=alert.severity.value,
                custom_details={
                    "runbook": alert.runbook_url,
                    "dashboard": alert.dashboard_url,
                    "value": alert.value,
                    "impact": alert.impact,
                    "action": alert.action,
                },
            )

            logger.info("oncall_paged", alert=alert.name)

        except Exception as e:
            logger.error("pagerduty_error", alert=alert.name, error=str(e))
            # Fall back to Slack if PagerDuty fails
            self._post_to_slack(
                alert,
                channel="#incidents",
                urgent=True,
                note="⚠️ PagerDuty failed - manual page required!",
            )

    def _post_to_slack(
        self,
        alert: Alert,
        channel: str,
        urgent: bool = False,
        note: Optional[str] = None,
    ):
        """
        Post alert to Slack channel.

        Args:
            alert: Alert to post
            channel: Slack channel (#incidents, #on-call, #alerts)
            urgent: Whether to mention @here (for urgent alerts)
            note: Optional additional note to include
        """
        try:
            # Determine emoji and mention based on urgency
            if urgent:
                emoji = "🚨"
                mention = "<!here> "
            else:
                emoji = "⚠️"
                mention = ""

            # Build message blocks
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"{emoji} {alert.name}",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{mention}*{alert.description}*",
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Severity:*\n{alert.severity.value.upper()}",
                        },
                        {"type": "mrkdwn", "text": f"*Value:*\n{alert.value:.2f}"},
                    ],
                },
            ]

            # Add impact and action if available
            if alert.impact:
                blocks.append(
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": f"*Impact:*\n{alert.impact}"},
                    }
                )

            if alert.action:
                blocks.append(
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Immediate Action:*\n{alert.action}",
                        },
                    }
                )

            # Add note if provided
            if note:
                blocks.append(
                    {"type": "section", "text": {"type": "mrkdwn", "text": note}}
                )

            # Add action buttons
            blocks.append(
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "📖 Runbook"},
                            "url": alert.runbook_url,
                            "style": "primary",
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "📊 Dashboard"},
                            "url": alert.dashboard_url,
                        },
                    ],
                }
            )

            # Post to Slack
            self.slack.post_message(channel=channel, blocks=blocks)

            logger.info("slack_posted", alert=alert.name, channel=channel)

        except Exception as e:
            logger.error("slack_error", alert=alert.name, channel=channel, error=str(e))

    def _is_business_hours(self) -> bool:
        """
        Check if current time is business hours.

        Business hours: 9am-5pm Monday-Friday (local time)

        Returns:
            True if business hours, False otherwise
        """
        now = datetime.now()

        # Monday=0, Friday=4, Saturday=5, Sunday=6
        is_weekday = now.weekday() < 5

        # 9am-5pm
        is_business_time = 9 <= now.hour < 17

        return is_weekday and is_business_time


# =========================================================================
# Alertmanager Webhook Receiver
# =========================================================================


def parse_alertmanager_webhook(payload: dict) -> list[Alert]:
    """
    Parse Alertmanager webhook payload into Alert objects.

    Args:
        payload: Alertmanager webhook JSON payload

    Returns:
        List of Alert objects

    Example payload:
    {
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "AgentHighErrorRate",
                    "severity": "critical"
                },
                "annotations": {
                    "summary": "Agent error rate >10%",
                    "description": "Error rate is 15.2%",
                    "runbook": "https://...",
                    "dashboard": "https://..."
                },
                "value": 0.152
            }
        ]
    }
    """
    alerts = []

    for alert_data in payload.get("alerts", []):
        # Only process firing alerts
        if alert_data.get("status") != "firing":
            continue

        labels = alert_data.get("labels", {})
        annotations = alert_data.get("annotations", {})

        # Parse severity
        severity_str = labels.get("severity", "info")
        try:
            severity = Severity(severity_str)
        except ValueError:
            logger.warning("unknown_severity", severity=severity_str)
            severity = Severity.INFO

        # Create Alert object
        alert = Alert(
            name=labels.get("alertname", "Unknown"),
            severity=severity,
            description=annotations.get("description", annotations.get("summary", "")),
            runbook_url=annotations.get("runbook", "#"),
            dashboard_url=annotations.get("dashboard", "#"),
            value=float(alert_data.get("value", 0)),
            impact=annotations.get("impact"),
            action=annotations.get("action"),
        )

        alerts.append(alert)

    return alerts


# =========================================================================
# Example Usage
# =========================================================================


def main():
    """Example usage of AlertRouter."""
    import sys

    # Mock clients for demonstration
    class MockPagerDuty:
        def trigger_incident(self, **kwargs):
            print(f"📟 PagerDuty incident triggered: {kwargs['title']}")

    class MockSlack:
        def post_message(self, channel, blocks):
            print(f"💬 Slack message to {channel}: {blocks[0]['text']['text']}")

    # Initialize router
    router = AlertRouter(
        pagerduty_client=MockPagerDuty(), slack_client=MockSlack()
    )

    # Example: Critical alert
    critical_alert = Alert(
        name="AgentHighErrorRate",
        severity=Severity.CRITICAL,
        description="Error rate is 15.2% (threshold: 10%)",
        runbook_url="https://wiki.company.com/runbooks/high-error-rate",
        dashboard_url="https://grafana.company.com/agent-errors",
        value=0.152,
        impact="Major user impact. >10% of requests failing.",
        action="1. Check error logs, 2. Check recent deployments, 3. Check external API status",
    )

    router.handle_alert(critical_alert)


if __name__ == "__main__":
    main()
