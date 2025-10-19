"""
Unit tests for alerting.py

Tests alert condition parsing, rate limiting, notification channels,
and integration with metrics aggregation.
"""
import pytest
import time
import tempfile
import yaml
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from agent_system.observability.alerting import (
    AlertManager,
    AlertCondition,
    Alert,
    AlertAction,
    NotificationChannel
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def sample_config():
    """Sample observability.yaml config."""
    return {
        'alerts': [
            {
                'condition': 'critic_rejection_rate > 0.50',
                'action': 'notify_admin',
                'message': 'Critic rejecting >50% of tests - check test quality'
            },
            {
                'condition': 'validation_pass_rate < 0.70',
                'action': 'notify_admin',
                'message': 'Validation pass rate <70% - investigate failures'
            },
            {
                'condition': 'cost_per_feature > 1.00',
                'action': 'warn_user',
                'message': 'Cost per feature exceeding $1.00 - review complexity'
            },
            {
                'condition': 'average_retry_count > 2.0',
                'action': 'notify_admin',
                'message': 'High retry rate - check medic effectiveness'
            }
        ]
    }


@pytest.fixture
def temp_config_file(sample_config):
    """Create temporary config file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(sample_config, f)
        return f.name


@pytest.fixture
def alert_manager(temp_config_file):
    """Fresh AlertManager instance with test config."""
    return AlertManager(
        config_path=temp_config_file,
        console_enabled=False,  # Disable console for tests
        rate_limit_seconds=600
    )


@pytest.fixture
def sample_metrics():
    """Sample metrics that are all within normal bounds."""
    return {
        'critic_rejection_rate': 0.30,
        'validation_pass_rate': 0.85,
        'cost_per_feature': 0.50,
        'average_retry_count': 1.5,
        'agent_utilization': 0.70,
        'time_to_completion': 120.0
    }


# ============================================================================
# AlertCondition Tests
# ============================================================================

class TestAlertCondition:
    """Test AlertCondition parsing and checking."""

    def test_greater_than_operator(self):
        """Test > operator."""
        condition = AlertCondition(
            metric='test_metric',
            operator='>',
            threshold=0.50,
            action='notify_admin',
            message='Test message'
        )
        assert condition.check(0.51) is True
        assert condition.check(0.50) is False
        assert condition.check(0.49) is False

    def test_less_than_operator(self):
        """Test < operator."""
        condition = AlertCondition(
            metric='test_metric',
            operator='<',
            threshold=0.70,
            action='notify_admin',
            message='Test message'
        )
        assert condition.check(0.69) is True
        assert condition.check(0.70) is False
        assert condition.check(0.71) is False

    def test_greater_equal_operator(self):
        """Test >= operator."""
        condition = AlertCondition(
            metric='test_metric',
            operator='>=',
            threshold=1.00,
            action='warn_user',
            message='Test message'
        )
        assert condition.check(1.01) is True
        assert condition.check(1.00) is True
        assert condition.check(0.99) is False

    def test_less_equal_operator(self):
        """Test <= operator."""
        condition = AlertCondition(
            metric='test_metric',
            operator='<=',
            threshold=2.0,
            action='notify_admin',
            message='Test message'
        )
        assert condition.check(1.9) is True
        assert condition.check(2.0) is True
        assert condition.check(2.1) is False

    def test_equal_operator(self):
        """Test == operator."""
        condition = AlertCondition(
            metric='test_metric',
            operator='==',
            threshold=1.0,
            action='notify_admin',
            message='Test message'
        )
        assert condition.check(1.0) is True
        assert condition.check(0.9) is False
        assert condition.check(1.1) is False

    def test_not_equal_operator(self):
        """Test != operator."""
        condition = AlertCondition(
            metric='test_metric',
            operator='!=',
            threshold=0.0,
            action='notify_admin',
            message='Test message'
        )
        assert condition.check(0.1) is True
        assert condition.check(0.0) is False

    def test_invalid_operator_raises_error(self):
        """Test that invalid operator raises ValueError."""
        condition = AlertCondition(
            metric='test_metric',
            operator='>>',  # Invalid
            threshold=1.0,
            action='notify_admin',
            message='Test message'
        )
        with pytest.raises(ValueError, match="Invalid operator"):
            condition.check(1.0)


# ============================================================================
# Config Loading Tests
# ============================================================================

class TestConfigLoading:
    """Test configuration loading from YAML."""

    def test_load_conditions_from_file(self, alert_manager):
        """Should load all conditions from config file."""
        assert len(alert_manager.conditions) == 4

    def test_condition_parsing(self, alert_manager):
        """Should correctly parse condition strings."""
        # Check first condition
        cond1 = alert_manager.conditions[0]
        assert cond1.metric == 'critic_rejection_rate'
        assert cond1.operator == '>'
        assert cond1.threshold == 0.50
        assert cond1.action == 'notify_admin'
        assert 'Critic rejecting' in cond1.message

    def test_all_conditions_loaded(self, alert_manager):
        """Should load all 4 configured conditions."""
        metrics = [c.metric for c in alert_manager.conditions]
        assert 'critic_rejection_rate' in metrics
        assert 'validation_pass_rate' in metrics
        assert 'cost_per_feature' in metrics
        assert 'average_retry_count' in metrics

    def test_missing_config_file(self):
        """Should handle missing config file gracefully."""
        manager = AlertManager(config_path='/nonexistent/file.yaml')
        assert len(manager.conditions) == 0

    def test_invalid_condition_format_skipped(self):
        """Should skip conditions with invalid format."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({
                'alerts': [
                    {
                        'condition': 'invalid format',  # Missing operator
                        'action': 'notify_admin',
                        'message': 'Test'
                    }
                ]
            }, f)
            temp_path = f.name

        manager = AlertManager(config_path=temp_path)
        assert len(manager.conditions) == 0

    def test_invalid_threshold_value_skipped(self):
        """Should skip conditions with non-numeric threshold."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({
                'alerts': [
                    {
                        'condition': 'metric > not_a_number',
                        'action': 'notify_admin',
                        'message': 'Test'
                    }
                ]
            }, f)
            temp_path = f.name

        manager = AlertManager(config_path=temp_path)
        assert len(manager.conditions) == 0


# ============================================================================
# Alert Triggering Tests
# ============================================================================

class TestAlertTriggering:
    """Test alert triggering based on metrics."""

    def test_no_alerts_with_good_metrics(self, alert_manager, sample_metrics):
        """Should not trigger any alerts with normal metrics."""
        triggered = alert_manager.check_alerts(sample_metrics)
        assert len(triggered) == 0

    def test_trigger_critic_rejection_alert(self, alert_manager, sample_metrics):
        """Should trigger alert when critic_rejection_rate > 0.50."""
        sample_metrics['critic_rejection_rate'] = 0.60
        triggered = alert_manager.check_alerts(sample_metrics)
        assert len(triggered) == 1
        assert triggered[0].condition.metric == 'critic_rejection_rate'
        assert triggered[0].metric_value == 0.60

    def test_trigger_validation_pass_rate_alert(self, alert_manager, sample_metrics):
        """Should trigger alert when validation_pass_rate < 0.70."""
        sample_metrics['validation_pass_rate'] = 0.65
        triggered = alert_manager.check_alerts(sample_metrics)
        assert len(triggered) == 1
        assert triggered[0].condition.metric == 'validation_pass_rate'
        assert triggered[0].metric_value == 0.65

    def test_trigger_cost_per_feature_alert(self, alert_manager, sample_metrics):
        """Should trigger alert when cost_per_feature > 1.00."""
        sample_metrics['cost_per_feature'] = 1.25
        triggered = alert_manager.check_alerts(sample_metrics)
        assert len(triggered) == 1
        assert triggered[0].condition.metric == 'cost_per_feature'
        assert triggered[0].metric_value == 1.25

    def test_trigger_retry_count_alert(self, alert_manager, sample_metrics):
        """Should trigger alert when average_retry_count > 2.0."""
        sample_metrics['average_retry_count'] = 2.5
        triggered = alert_manager.check_alerts(sample_metrics)
        assert len(triggered) == 1
        assert triggered[0].condition.metric == 'average_retry_count'
        assert triggered[0].metric_value == 2.5

    def test_trigger_multiple_alerts(self, alert_manager, sample_metrics):
        """Should trigger multiple alerts when multiple conditions are met."""
        sample_metrics['critic_rejection_rate'] = 0.60
        sample_metrics['validation_pass_rate'] = 0.65
        sample_metrics['cost_per_feature'] = 1.25
        triggered = alert_manager.check_alerts(sample_metrics)
        assert len(triggered) == 3

    def test_trigger_all_alerts(self, alert_manager, sample_metrics):
        """Should trigger all alerts when all conditions are met."""
        sample_metrics['critic_rejection_rate'] = 0.60
        sample_metrics['validation_pass_rate'] = 0.65
        sample_metrics['cost_per_feature'] = 1.25
        sample_metrics['average_retry_count'] = 2.5
        triggered = alert_manager.check_alerts(sample_metrics)
        assert len(triggered) == 4

    def test_missing_metric_skipped(self, alert_manager):
        """Should skip conditions where metric is missing."""
        metrics = {'critic_rejection_rate': 0.60}  # Missing other metrics
        triggered = alert_manager.check_alerts(metrics)
        assert len(triggered) == 1  # Only critic alert

    def test_boundary_condition_not_triggered(self, alert_manager, sample_metrics):
        """Should not trigger when value equals threshold (for > operator)."""
        sample_metrics['critic_rejection_rate'] = 0.50  # Exactly at threshold
        triggered = alert_manager.check_alerts(sample_metrics)
        assert len(triggered) == 0


# ============================================================================
# Rate Limiting Tests
# ============================================================================

class TestRateLimiting:
    """Test alert rate limiting."""

    def test_rate_limiting_prevents_duplicate_alerts(self, alert_manager, sample_metrics):
        """Should not trigger same alert twice within rate limit period."""
        sample_metrics['critic_rejection_rate'] = 0.60

        # First trigger
        triggered1 = alert_manager.check_alerts(sample_metrics)
        assert len(triggered1) == 1

        # Second trigger immediately after (should be rate limited)
        triggered2 = alert_manager.check_alerts(sample_metrics)
        assert len(triggered2) == 0

    def test_different_alerts_not_rate_limited(self, alert_manager, sample_metrics):
        """Should allow different alerts even if one is rate limited."""
        sample_metrics['critic_rejection_rate'] = 0.60

        # Trigger critic alert
        triggered1 = alert_manager.check_alerts(sample_metrics)
        assert len(triggered1) == 1

        # Add validation alert (different condition)
        sample_metrics['validation_pass_rate'] = 0.65
        triggered2 = alert_manager.check_alerts(sample_metrics)
        assert len(triggered2) == 1  # Only validation alert
        assert triggered2[0].condition.metric == 'validation_pass_rate'

    def test_rate_limit_expires_after_period(self):
        """Should allow alert after rate limit period expires."""
        manager = AlertManager(
            config_path=None,
            console_enabled=False,
            rate_limit_seconds=1  # 1 second for testing
        )

        # Manually add a condition
        manager.conditions = [
            AlertCondition(
                metric='test_metric',
                operator='>',
                threshold=0.5,
                action='notify_admin',
                message='Test alert'
            )
        ]

        metrics = {'test_metric': 0.6}

        # First trigger
        triggered1 = manager.check_alerts(metrics)
        assert len(triggered1) == 1

        # Immediate second trigger (rate limited)
        triggered2 = manager.check_alerts(metrics)
        assert len(triggered2) == 0

        # Wait for rate limit to expire
        time.sleep(1.1)

        # Third trigger (should work)
        triggered3 = manager.check_alerts(metrics)
        assert len(triggered3) == 1

    def test_reset_rate_limits(self, alert_manager, sample_metrics):
        """Should allow alerts after resetting rate limits."""
        sample_metrics['critic_rejection_rate'] = 0.60

        # First trigger
        triggered1 = alert_manager.check_alerts(sample_metrics)
        assert len(triggered1) == 1

        # Second trigger (rate limited)
        triggered2 = alert_manager.check_alerts(sample_metrics)
        assert len(triggered2) == 0

        # Reset rate limits
        alert_manager.reset_rate_limits()

        # Third trigger (should work)
        triggered3 = alert_manager.check_alerts(sample_metrics)
        assert len(triggered3) == 1


# ============================================================================
# Notification Channel Tests
# ============================================================================

class TestNotificationChannels:
    """Test notification delivery to different channels."""

    def test_console_notification_sent(self, alert_manager, sample_metrics, capsys):
        """Should send console notification when enabled."""
        alert_manager.console_enabled = True
        sample_metrics['critic_rejection_rate'] = 0.60

        alert_manager.check_alerts(sample_metrics)
        captured = capsys.readouterr()

        # Check that alert was printed to console
        assert 'ALERT' in captured.out or '[ALERT]' in captured.out
        assert 'critic_rejection_rate' in captured.out

    @patch('requests.post')
    def test_webhook_notification_sent(self, mock_post, temp_config_file, sample_metrics):
        """Should send webhook notification when enabled."""
        mock_post.return_value = Mock(status_code=200)

        manager = AlertManager(
            config_path=temp_config_file,
            console_enabled=False,
            webhook_enabled=True,
            webhook_url='http://example.com/webhook'
        )

        sample_metrics['critic_rejection_rate'] = 0.60
        manager.check_alerts(sample_metrics)

        # Verify webhook was called
        assert mock_post.called
        call_args = mock_post.call_args
        assert call_args[0][0] == 'http://example.com/webhook'

        # Check payload
        payload = call_args[1]['json']
        assert payload['metric'] == 'critic_rejection_rate'
        assert payload['current_value'] == 0.60

    @patch('requests.post')
    def test_webhook_error_handled_gracefully(self, mock_post, temp_config_file, sample_metrics):
        """Should handle webhook errors without crashing."""
        mock_post.side_effect = Exception('Connection failed')

        manager = AlertManager(
            config_path=temp_config_file,
            console_enabled=False,
            webhook_enabled=True,
            webhook_url='http://example.com/webhook'
        )

        sample_metrics['critic_rejection_rate'] = 0.60

        # Should not raise exception
        manager.check_alerts(sample_metrics)

    @patch('smtplib.SMTP')
    def test_email_notification_sent(self, mock_smtp, temp_config_file, sample_metrics):
        """Should send email notification when enabled."""
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        manager = AlertManager(
            config_path=temp_config_file,
            console_enabled=False,
            email_enabled=True,
            smtp_host='smtp.example.com',
            smtp_port=587,
            email_from='alerts@example.com',
            email_to=['admin@example.com']
        )

        sample_metrics['critic_rejection_rate'] = 0.60
        manager.check_alerts(sample_metrics)

        # Verify email was sent
        assert mock_server.send_message.called

    @patch('smtplib.SMTP')
    def test_email_error_handled_gracefully(self, mock_smtp, temp_config_file, sample_metrics):
        """Should handle email errors without crashing."""
        mock_smtp.side_effect = Exception('SMTP connection failed')

        manager = AlertManager(
            config_path=temp_config_file,
            console_enabled=False,
            email_enabled=True,
            smtp_host='smtp.example.com',
            email_to=['admin@example.com']
        )

        sample_metrics['critic_rejection_rate'] = 0.60

        # Should not raise exception
        manager.check_alerts(sample_metrics)


# ============================================================================
# Alert History Tests
# ============================================================================

class TestAlertHistory:
    """Test alert history tracking."""

    def test_alert_added_to_history(self, alert_manager, sample_metrics):
        """Should add triggered alerts to history."""
        assert len(alert_manager.alert_history) == 0

        sample_metrics['critic_rejection_rate'] = 0.60
        alert_manager.check_alerts(sample_metrics)

        assert len(alert_manager.alert_history) == 1
        assert alert_manager.alert_history[0].condition.metric == 'critic_rejection_rate'

    def test_multiple_alerts_in_history(self, alert_manager, sample_metrics):
        """Should track multiple alerts in history."""
        # First check with one alert
        sample_metrics['critic_rejection_rate'] = 0.60
        triggered1 = alert_manager.check_alerts(sample_metrics)
        assert len(triggered1) == 1

        # Reset rate limits so we can trigger new alerts
        alert_manager.reset_rate_limits()

        # Second check with different alert (keep first metric to avoid re-triggering)
        sample_metrics['critic_rejection_rate'] = 0.40  # Below threshold
        sample_metrics['validation_pass_rate'] = 0.65  # Triggers new alert
        triggered2 = alert_manager.check_alerts(sample_metrics)
        assert len(triggered2) == 1

        # Should have 2 alerts in history total
        assert len(alert_manager.alert_history) == 2

    def test_get_alert_history_by_metric(self, alert_manager, sample_metrics):
        """Should filter history by metric name."""
        sample_metrics['critic_rejection_rate'] = 0.60
        sample_metrics['validation_pass_rate'] = 0.65
        alert_manager.check_alerts(sample_metrics)

        critic_alerts = alert_manager.get_alert_history(metric='critic_rejection_rate')
        assert len(critic_alerts) == 1
        assert critic_alerts[0].condition.metric == 'critic_rejection_rate'

    def test_get_alert_history_since_timestamp(self, alert_manager, sample_metrics):
        """Should filter history by timestamp."""
        sample_metrics['critic_rejection_rate'] = 0.60
        alert_manager.check_alerts(sample_metrics)

        # Get alerts after now (should be empty)
        future_time = time.time() + 100
        recent_alerts = alert_manager.get_alert_history(since=future_time)
        assert len(recent_alerts) == 0

        # Get alerts from past (should include alert)
        past_time = time.time() - 100
        past_alerts = alert_manager.get_alert_history(since=past_time)
        assert len(past_alerts) == 1

    def test_get_alert_history_with_limit(self, alert_manager, sample_metrics):
        """Should limit number of returned alerts."""
        # Trigger multiple alerts
        for _ in range(3):
            sample_metrics['critic_rejection_rate'] = 0.60
            alert_manager.check_alerts(sample_metrics)
            alert_manager.reset_rate_limits()

        limited = alert_manager.get_alert_history(limit=2)
        assert len(limited) == 2


# ============================================================================
# Statistics Tests
# ============================================================================

class TestStatistics:
    """Test alert statistics."""

    def test_stats_empty_history(self, alert_manager):
        """Should return correct stats for empty history."""
        stats = alert_manager.get_stats()
        assert stats['total_alerts'] == 0
        assert stats['alerts_by_metric'] == {}
        assert stats['alerts_by_action'] == {}
        assert stats['most_recent'] is None

    def test_stats_with_alerts(self, alert_manager, sample_metrics):
        """Should return correct stats with alerts."""
        sample_metrics['critic_rejection_rate'] = 0.60
        sample_metrics['validation_pass_rate'] = 0.65
        alert_manager.check_alerts(sample_metrics)

        stats = alert_manager.get_stats()
        assert stats['total_alerts'] == 2
        assert stats['alerts_by_metric']['critic_rejection_rate'] == 1
        assert stats['alerts_by_metric']['validation_pass_rate'] == 1
        assert stats['most_recent'] is not None

    def test_stats_count_by_action(self, alert_manager, sample_metrics):
        """Should count alerts by action type."""
        sample_metrics['critic_rejection_rate'] = 0.60  # notify_admin
        sample_metrics['cost_per_feature'] = 1.25  # warn_user
        alert_manager.check_alerts(sample_metrics)

        stats = alert_manager.get_stats()
        assert stats['alerts_by_action']['notify_admin'] == 1
        assert stats['alerts_by_action']['warn_user'] == 1


# ============================================================================
# Alert Object Tests
# ============================================================================

class TestAlertObject:
    """Test Alert dataclass."""

    def test_alert_to_dict(self):
        """Should convert alert to dictionary."""
        condition = AlertCondition(
            metric='test_metric',
            operator='>',
            threshold=0.5,
            action='notify_admin',
            message='Test message'
        )

        alert = Alert(
            condition=condition,
            metric_value=0.6,
            timestamp=1234567890.0,
            message='Test message'
        )

        alert_dict = alert.to_dict()

        assert alert_dict['metric'] == 'test_metric'
        assert alert_dict['operator'] == '>'
        assert alert_dict['threshold'] == 0.5
        assert alert_dict['current_value'] == 0.6
        assert alert_dict['action'] == 'notify_admin'
        assert alert_dict['message'] == 'Test message'
        assert alert_dict['timestamp'] == 1234567890.0
        assert 'timestamp_iso' in alert_dict


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Test integration with MetricsAggregator."""

    def test_end_to_end_flow(self, alert_manager, sample_metrics):
        """Test complete flow from metrics to notification."""
        # Start with good metrics
        triggered = alert_manager.check_alerts(sample_metrics)
        assert len(triggered) == 0

        # Degrade metrics
        sample_metrics['critic_rejection_rate'] = 0.60
        sample_metrics['validation_pass_rate'] = 0.65

        # Check alerts
        triggered = alert_manager.check_alerts(sample_metrics)
        assert len(triggered) == 2

        # Verify history
        assert len(alert_manager.alert_history) == 2

        # Verify stats
        stats = alert_manager.get_stats()
        assert stats['total_alerts'] == 2

    def test_realistic_alert_scenario(self, alert_manager):
        """Test realistic scenario with changing metrics over time."""
        # Simulate metrics worsening over time
        time_series = [
            {'critic_rejection_rate': 0.30, 'validation_pass_rate': 0.85},  # OK
            {'critic_rejection_rate': 0.45, 'validation_pass_rate': 0.75},  # OK
            {'critic_rejection_rate': 0.55, 'validation_pass_rate': 0.65},  # 2 alerts
            {'critic_rejection_rate': 0.60, 'validation_pass_rate': 0.60},  # Rate limited
        ]

        total_triggered = 0
        for metrics in time_series:
            triggered = alert_manager.check_alerts(metrics)
            total_triggered += len(triggered)

        # Should trigger 2 alerts (once each, then rate limited)
        assert total_triggered == 2
        assert len(alert_manager.alert_history) == 2


# ============================================================================
# Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_metrics_dict(self, alert_manager):
        """Should handle empty metrics dict."""
        triggered = alert_manager.check_alerts({})
        assert len(triggered) == 0

    def test_zero_threshold(self):
        """Should handle zero threshold correctly."""
        manager = AlertManager(config_path=None, console_enabled=False)
        manager.conditions = [
            AlertCondition(
                metric='test',
                operator='>',
                threshold=0.0,
                action='notify_admin',
                message='Test'
            )
        ]

        triggered = manager.check_alerts({'test': 0.1})
        assert len(triggered) == 1

        triggered = manager.check_alerts({'test': 0.0})
        assert len(triggered) == 0

    def test_negative_metric_values(self):
        """Should handle negative metric values."""
        manager = AlertManager(config_path=None, console_enabled=False)
        manager.conditions = [
            AlertCondition(
                metric='test',
                operator='<',
                threshold=-0.5,
                action='notify_admin',
                message='Test'
            )
        ]

        triggered = manager.check_alerts({'test': -0.6})
        assert len(triggered) == 1

    def test_very_large_metric_values(self):
        """Should handle very large metric values."""
        manager = AlertManager(config_path=None, console_enabled=False)
        manager.conditions = [
            AlertCondition(
                metric='test',
                operator='>',
                threshold=1000000.0,
                action='notify_admin',
                message='Test'
            )
        ]

        triggered = manager.check_alerts({'test': 1000001.0})
        assert len(triggered) == 1
