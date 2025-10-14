"""
Alerting System for SuperAgent Observability

Monitors metrics and sends notifications when thresholds are exceeded.
Supports multiple notification channels with rate limiting.

Configuration loaded from .claude/observability.yaml:
- Alert conditions with thresholds
- Notification actions (notify_admin, warn_user)
- Rate limiting to prevent alert fatigue

Usage:
    from agent_system.observability import AlertManager

    # Create alert manager
    alert_manager = AlertManager()

    # Check metrics and trigger alerts
    metrics = emitter.get_metrics()
    alert_manager.check_alerts(metrics)
"""
import os
import time
import yaml
import smtplib
import requests
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


class AlertAction(Enum):
    """Alert action types."""
    NOTIFY_ADMIN = 'notify_admin'
    WARN_USER = 'warn_user'


class NotificationChannel(Enum):
    """Available notification channels."""
    CONSOLE = 'console'
    WEBHOOK = 'webhook'
    EMAIL = 'email'


@dataclass
class AlertCondition:
    """
    Represents a single alert condition.

    Attributes:
        metric: Name of metric to monitor (e.g., 'critic_rejection_rate')
        operator: Comparison operator ('>', '<', '>=', '<=', '==', '!=')
        threshold: Threshold value to compare against
        action: Action to take when condition is met (notify_admin, warn_user)
        message: Alert message to send
    """
    metric: str
    operator: str
    threshold: float
    action: str
    message: str

    def check(self, value: float) -> bool:
        """
        Check if metric value meets alert condition.

        Args:
            value: Current metric value

        Returns:
            True if condition is met, False otherwise
        """
        operators = {
            '>': lambda a, b: a > b,
            '<': lambda a, b: a < b,
            '>=': lambda a, b: a >= b,
            '<=': lambda a, b: a <= b,
            '==': lambda a, b: a == b,
            '!=': lambda a, b: a != b
        }

        op_func = operators.get(self.operator)
        if not op_func:
            raise ValueError(f"Invalid operator: {self.operator}")

        return op_func(value, self.threshold)


@dataclass
class Alert:
    """
    Represents a triggered alert.

    Attributes:
        condition: Alert condition that was triggered
        metric_value: Current value of the metric
        timestamp: When alert was triggered
        message: Alert message
    """
    condition: AlertCondition
    metric_value: float
    timestamp: float
    message: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary."""
        return {
            'metric': self.condition.metric,
            'operator': self.condition.operator,
            'threshold': self.condition.threshold,
            'current_value': self.metric_value,
            'action': self.condition.action,
            'message': self.message,
            'timestamp': self.timestamp,
            'timestamp_iso': datetime.fromtimestamp(self.timestamp).isoformat()
        }


class AlertManager:
    """
    Manages alert checking and notification delivery.

    Features:
    - Loads alert conditions from observability.yaml
    - Checks metrics against configured thresholds
    - Sends notifications via multiple channels
    - Rate limits alerts (max 1 per condition per 10 minutes)
    - Integrates with MetricsAggregator

    Usage:
        manager = AlertManager()
        metrics = emitter.get_metrics()
        triggered_alerts = manager.check_alerts(metrics)
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        console_enabled: bool = True,
        webhook_url: Optional[str] = None,
        webhook_enabled: bool = False,
        email_enabled: bool = False,
        smtp_host: Optional[str] = None,
        smtp_port: int = 587,
        smtp_username: Optional[str] = None,
        smtp_password: Optional[str] = None,
        email_from: Optional[str] = None,
        email_to: Optional[List[str]] = None,
        rate_limit_seconds: int = 600  # 10 minutes
    ):
        """
        Initialize AlertManager.

        Args:
            config_path: Path to observability.yaml config file
            console_enabled: Enable console notifications
            webhook_url: URL for webhook notifications
            webhook_enabled: Enable webhook notifications
            email_enabled: Enable email notifications
            smtp_host: SMTP server host
            smtp_port: SMTP server port
            smtp_username: SMTP username
            smtp_password: SMTP password
            email_from: Sender email address
            email_to: List of recipient email addresses
            rate_limit_seconds: Minimum seconds between alerts for same condition
        """
        # Load configuration
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(__file__),
                '../../.claude/observability.yaml'
            )

        self.config_path = Path(config_path)
        self.conditions = self._load_conditions()

        # Notification channels
        self.console_enabled = console_enabled
        self.webhook_enabled = webhook_enabled
        self.webhook_url = webhook_url or os.getenv('ALERT_WEBHOOK_URL')
        self.email_enabled = email_enabled

        # Email configuration
        self.smtp_host = smtp_host or os.getenv('SMTP_HOST')
        self.smtp_port = smtp_port
        self.smtp_username = smtp_username or os.getenv('SMTP_USERNAME')
        self.smtp_password = smtp_password or os.getenv('SMTP_PASSWORD')
        self.email_from = email_from or os.getenv('ALERT_EMAIL_FROM')
        self.email_to = email_to or (
            os.getenv('ALERT_EMAIL_TO', '').split(',') if os.getenv('ALERT_EMAIL_TO') else []
        )

        # Rate limiting
        self.rate_limit_seconds = rate_limit_seconds
        self._last_alert_times: Dict[str, float] = {}

        # Alert history
        self.alert_history: List[Alert] = []

    def _load_conditions(self) -> List[AlertCondition]:
        """
        Load alert conditions from observability.yaml.

        Returns:
            List of AlertCondition objects
        """
        if not self.config_path.exists():
            print(f"Warning: Config file not found at {self.config_path}")
            return []

        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)

            alerts_config = config.get('alerts', [])
            conditions = []

            for alert_config in alerts_config:
                # Parse condition string (e.g., "critic_rejection_rate > 0.50")
                condition_str = alert_config.get('condition', '')
                action = alert_config.get('action', '')
                message = alert_config.get('message', '')

                # Parse condition
                parts = condition_str.split()
                if len(parts) != 3:
                    print(f"Warning: Invalid condition format: {condition_str}")
                    continue

                metric, operator, threshold_str = parts
                try:
                    threshold = float(threshold_str)
                except ValueError:
                    print(f"Warning: Invalid threshold value: {threshold_str}")
                    continue

                conditions.append(AlertCondition(
                    metric=metric,
                    operator=operator,
                    threshold=threshold,
                    action=action,
                    message=message
                ))

            return conditions

        except Exception as e:
            print(f"Error loading alert conditions: {e}")
            return []

    def check_alerts(self, metrics: Dict[str, float]) -> List[Alert]:
        """
        Check all alert conditions against current metrics.

        Args:
            metrics: Dictionary of metric name -> value

        Returns:
            List of triggered alerts
        """
        triggered_alerts = []

        for condition in self.conditions:
            # Get metric value
            metric_value = metrics.get(condition.metric)
            if metric_value is None:
                continue

            # Check if condition is met
            if not condition.check(metric_value):
                continue

            # Check rate limit
            condition_key = f"{condition.metric}:{condition.operator}:{condition.threshold}"
            last_alert_time = self._last_alert_times.get(condition_key, 0)
            current_time = time.time()

            if current_time - last_alert_time < self.rate_limit_seconds:
                # Rate limited, skip
                continue

            # Create alert
            alert = Alert(
                condition=condition,
                metric_value=metric_value,
                timestamp=current_time,
                message=condition.message
            )

            # Send notifications
            self._send_notifications(alert)

            # Update rate limit tracker
            self._last_alert_times[condition_key] = current_time

            # Add to history
            self.alert_history.append(alert)
            triggered_alerts.append(alert)

        return triggered_alerts

    def _send_notifications(self, alert: Alert):
        """
        Send alert notifications to all enabled channels.

        Args:
            alert: Alert to send
        """
        # Console notification (always enabled if console_enabled)
        if self.console_enabled:
            self._send_console_notification(alert)

        # Webhook notification
        if self.webhook_enabled and self.webhook_url:
            self._send_webhook_notification(alert)

        # Email notification
        if self.email_enabled and self.smtp_host and self.email_to:
            self._send_email_notification(alert)

    def _send_console_notification(self, alert: Alert):
        """
        Send alert to console with color formatting.

        Args:
            alert: Alert to send
        """
        # Color codes
        RED = '\033[91m'
        YELLOW = '\033[93m'
        BOLD = '\033[1m'
        RESET = '\033[0m'

        # Choose color based on action
        if alert.condition.action == AlertAction.NOTIFY_ADMIN.value:
            color = RED
        else:
            color = YELLOW

        timestamp = datetime.fromtimestamp(alert.timestamp).strftime('%Y-%m-%d %H:%M:%S')

        print(f"\n{color}{BOLD}[ALERT] {timestamp}{RESET}")
        print(f"{color}Metric: {alert.condition.metric}{RESET}")
        print(f"{color}Condition: {alert.condition.operator} {alert.condition.threshold}{RESET}")
        print(f"{color}Current Value: {alert.metric_value:.4f}{RESET}")
        print(f"{color}Action: {alert.condition.action}{RESET}")
        print(f"{color}Message: {alert.message}{RESET}\n")

    def _send_webhook_notification(self, alert: Alert):
        """
        Send alert to webhook endpoint.

        Args:
            alert: Alert to send
        """
        try:
            payload = alert.to_dict()
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
        except Exception as e:
            print(f"Error sending webhook notification: {e}")

    def _send_email_notification(self, alert: Alert):
        """
        Send alert via email using SMTP.

        Args:
            alert: Alert to send
        """
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.email_from
            msg['To'] = ', '.join(self.email_to)
            msg['Subject'] = f"[SuperAgent Alert] {alert.condition.metric}"

            # Email body
            body = f"""
SuperAgent Alert Triggered

Metric: {alert.condition.metric}
Condition: {alert.condition.operator} {alert.condition.threshold}
Current Value: {alert.metric_value:.4f}
Action: {alert.condition.action}
Time: {datetime.fromtimestamp(alert.timestamp).strftime('%Y-%m-%d %H:%M:%S')}

Message: {alert.message}

---
This is an automated alert from SuperAgent Observability System.
            """

            msg.attach(MIMEText(body, 'plain'))

            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                if self.smtp_username and self.smtp_password:
                    server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)

        except Exception as e:
            print(f"Error sending email notification: {e}")

    def get_alert_history(
        self,
        metric: Optional[str] = None,
        since: Optional[float] = None,
        limit: Optional[int] = None
    ) -> List[Alert]:
        """
        Get alert history with optional filtering.

        Args:
            metric: Filter by metric name
            since: Only return alerts after this timestamp
            limit: Maximum number of alerts to return

        Returns:
            List of alerts matching criteria
        """
        filtered = self.alert_history

        if metric:
            filtered = [a for a in filtered if a.condition.metric == metric]

        if since:
            filtered = [a for a in filtered if a.timestamp >= since]

        if limit:
            filtered = filtered[-limit:]

        return filtered

    def reset_rate_limits(self):
        """Reset all rate limit trackers (useful for testing)."""
        self._last_alert_times.clear()

    def get_stats(self) -> Dict[str, Any]:
        """
        Get alert statistics.

        Returns:
            Dictionary with alert stats
        """
        if not self.alert_history:
            return {
                'total_alerts': 0,
                'alerts_by_metric': {},
                'alerts_by_action': {},
                'most_recent': None
            }

        # Count by metric
        by_metric = {}
        for alert in self.alert_history:
            metric = alert.condition.metric
            by_metric[metric] = by_metric.get(metric, 0) + 1

        # Count by action
        by_action = {}
        for alert in self.alert_history:
            action = alert.condition.action
            by_action[action] = by_action.get(action, 0) + 1

        return {
            'total_alerts': len(self.alert_history),
            'alerts_by_metric': by_metric,
            'alerts_by_action': by_action,
            'most_recent': self.alert_history[-1].to_dict() if self.alert_history else None
        }


# Example usage
if __name__ == '__main__':
    # Create alert manager
    manager = AlertManager(
        console_enabled=True,
        webhook_enabled=False
    )

    print(f"Loaded {len(manager.conditions)} alert conditions:\n")
    for condition in manager.conditions:
        print(f"  - {condition.metric} {condition.operator} {condition.threshold}")
        print(f"    Action: {condition.action}")
        print(f"    Message: {condition.message}\n")

    # Test with sample metrics
    print("\nTesting with sample metrics that trigger alerts:\n")

    test_metrics = {
        'critic_rejection_rate': 0.60,  # Should trigger (> 0.50)
        'validation_pass_rate': 0.65,   # Should trigger (< 0.70)
        'cost_per_feature': 1.25,       # Should trigger (> 1.00)
        'average_retry_count': 2.5,     # Should trigger (> 2.0)
        'agent_utilization': 0.75,
        'time_to_completion': 120.0
    }

    triggered = manager.check_alerts(test_metrics)

    print(f"\n{len(triggered)} alerts triggered")

    # Get stats
    print("\nAlert Statistics:")
    stats = manager.get_stats()
    for key, value in stats.items():
        if key != 'most_recent':
            print(f"  {key}: {value}")
