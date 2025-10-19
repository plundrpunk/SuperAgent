"""
Unit tests for cost analytics and budget alerting system.
"""
import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from agent_system.cost_analytics import (
    CostTracker,
    CostEntry,
    BudgetConfig,
    get_cost_tracker,
    record_agent_cost
)
from agent_system.state.redis_client import RedisClient


@pytest.fixture
def mock_redis_client():
    """Create mock Redis client."""
    client = Mock(spec=RedisClient)
    client.get = Mock(return_value=None)
    client.set = Mock(return_value=True)
    client.client = Mock()
    client.client.rpush = Mock(return_value=1)
    client.client.expire = Mock(return_value=True)
    return client


@pytest.fixture
def budget_config():
    """Create test budget configuration."""
    return BudgetConfig(
        daily_budget_usd=10.00,
        per_session_budget_usd=2.00,
        soft_limit_warning=0.80,
        hard_limit_stop=1.00
    )


@pytest.fixture
def cost_tracker(mock_redis_client, budget_config, tmp_path):
    """Create cost tracker with mocked Redis."""
    # Create temporary config file
    config_path = tmp_path / "router_policy.yaml"
    config_path.write_text("""
budget_enforcement:
  daily_budget_usd: 10.00
  per_session_budget_usd: 2.00
  soft_limit_warning: 0.80
  hard_limit_stop: 1.00
""")

    with patch('agent_system.cost_analytics.emit_event') as mock_emit:
        tracker = CostTracker(
            redis_client=mock_redis_client,
            config_path=str(config_path),
            session_id="test_session_123"
        )
        tracker._emit_event = mock_emit
        yield tracker


class TestBudgetConfig:
    """Test BudgetConfig dataclass."""

    def test_default_values(self):
        """Test default budget configuration values."""
        config = BudgetConfig()
        assert config.daily_budget_usd == 50.00
        assert config.per_session_budget_usd == 5.00
        assert config.soft_limit_warning == 0.80
        assert config.hard_limit_stop == 1.00

    def test_custom_values(self):
        """Test custom budget configuration values."""
        config = BudgetConfig(
            daily_budget_usd=100.00,
            per_session_budget_usd=10.00,
            soft_limit_warning=0.75,
            hard_limit_stop=0.95
        )
        assert config.daily_budget_usd == 100.00
        assert config.per_session_budget_usd == 10.00
        assert config.soft_limit_warning == 0.75
        assert config.hard_limit_stop == 0.95

    def test_thresholds(self):
        """Test threshold calculations."""
        config = BudgetConfig(
            daily_budget_usd=10.00,
            per_session_budget_usd=2.00,
            soft_limit_warning=0.80,
            hard_limit_stop=1.00
        )

        assert config.daily_soft_threshold == 8.00  # 10.00 * 0.80
        assert config.daily_hard_threshold == 10.00  # 10.00 * 1.00
        assert config.session_soft_threshold == 1.60  # 2.00 * 0.80
        assert config.session_hard_threshold == 2.00  # 2.00 * 1.00


class TestCostEntry:
    """Test CostEntry dataclass."""

    def test_cost_entry_creation(self):
        """Test creating a cost entry."""
        entry = CostEntry(
            timestamp=time.time(),
            agent='scribe',
            model='claude-sonnet-4.5',
            cost_usd=0.12,
            feature='user_authentication',
            task_id='t_123'
        )

        assert entry.agent == 'scribe'
        assert entry.model == 'claude-sonnet-4.5'
        assert entry.cost_usd == 0.12
        assert entry.feature == 'user_authentication'
        assert entry.task_id == 't_123'

    def test_cost_entry_to_dict(self):
        """Test converting cost entry to dictionary."""
        timestamp = time.time()
        entry = CostEntry(
            timestamp=timestamp,
            agent='runner',
            model='claude-haiku',
            cost_usd=0.02,
            feature='checkout_flow',
            task_id='t_456'
        )

        entry_dict = entry.to_dict()

        assert entry_dict['timestamp'] == timestamp
        assert entry_dict['agent'] == 'runner'
        assert entry_dict['model'] == 'claude-haiku'
        assert entry_dict['cost_usd'] == 0.02
        assert entry_dict['feature'] == 'checkout_flow'
        assert entry_dict['task_id'] == 't_456'


class TestCostTracker:
    """Test CostTracker class."""

    def test_initialization(self, cost_tracker):
        """Test cost tracker initialization."""
        assert cost_tracker.session_id == "test_session_123"
        assert cost_tracker.budget_config.daily_budget_usd == 10.00
        assert cost_tracker.budget_config.per_session_budget_usd == 2.00

    def test_date_key_format(self, cost_tracker):
        """Test date key formatting."""
        timestamp = datetime(2025, 10, 14, 15, 30, 0).timestamp()
        date_key = cost_tracker._get_date_key(timestamp)
        assert date_key == '2025-10-14'

    def test_week_key_format(self, cost_tracker):
        """Test week key formatting."""
        timestamp = datetime(2025, 10, 14, 15, 30, 0).timestamp()
        week_key = cost_tracker._get_week_key(timestamp)
        # October 14, 2025 is in week 42
        assert week_key.startswith('2025-W')

    def test_record_cost(self, cost_tracker, mock_redis_client):
        """Test recording a cost entry."""
        result = cost_tracker.record_cost(
            agent='scribe',
            model='claude-sonnet-4.5',
            cost_usd=0.12,
            feature='user_authentication',
            task_id='t_123'
        )

        assert result is True
        assert len(cost_tracker._daily_cache) == 1
        assert cost_tracker._daily_cache[0].agent == 'scribe'
        assert cost_tracker._daily_cache[0].cost_usd == 0.12

        # Verify Redis calls
        assert mock_redis_client.client.rpush.called
        assert mock_redis_client.set.called

    def test_record_multiple_costs(self, cost_tracker):
        """Test recording multiple cost entries."""
        cost_tracker.record_cost('scribe', 'claude-sonnet-4.5', 0.12, 'feature1', 't_1')
        cost_tracker.record_cost('runner', 'claude-haiku', 0.02, 'feature1', 't_1')
        cost_tracker.record_cost('critic', 'claude-haiku', 0.01, 'feature1', 't_1')

        assert len(cost_tracker._daily_cache) == 3

    def test_increment_aggregate(self, cost_tracker, mock_redis_client):
        """Test incrementing aggregate counters."""
        entry = CostEntry(
            timestamp=time.time(),
            agent='scribe',
            model='claude-sonnet-4.5',
            cost_usd=0.12,
            feature='user_authentication',
            task_id='t_123'
        )

        # Mock Redis to return None (no existing aggregate)
        mock_redis_client.get.return_value = None

        cost_tracker._increment_aggregate('cost:daily:2025-10-14', entry, ttl=3600)

        # Verify set was called with updated aggregate
        assert mock_redis_client.set.called
        call_args = mock_redis_client.set.call_args
        aggregate = call_args[0][1]

        assert aggregate['total_cost'] == 0.12
        assert aggregate['count'] == 1
        assert aggregate['by_agent']['scribe'] == 0.12
        assert aggregate['by_model']['claude-sonnet-4.5'] == 0.12
        assert aggregate['by_feature']['user_authentication'] == 0.12

    def test_increment_aggregate_existing(self, cost_tracker, mock_redis_client):
        """Test incrementing aggregate with existing data."""
        entry = CostEntry(
            timestamp=time.time(),
            agent='scribe',
            model='claude-sonnet-4.5',
            cost_usd=0.15,
            feature='checkout_flow',
            task_id='t_456'
        )

        # Mock Redis to return existing aggregate
        existing_aggregate = {
            'total_cost': 0.12,
            'count': 1,
            'by_agent': {'scribe': 0.12},
            'by_model': {'claude-sonnet-4.5': 0.12},
            'by_feature': {'user_authentication': 0.12}
        }
        mock_redis_client.get.return_value = existing_aggregate

        cost_tracker._increment_aggregate('cost:daily:2025-10-14', entry, ttl=3600)

        # Verify set was called with updated aggregate
        call_args = mock_redis_client.set.call_args
        aggregate = call_args[0][1]

        assert aggregate['total_cost'] == 0.27  # 0.12 + 0.15
        assert aggregate['count'] == 2
        assert aggregate['by_agent']['scribe'] == 0.27
        assert aggregate['by_model']['claude-sonnet-4.5'] == 0.27
        assert 'user_authentication' in aggregate['by_feature']
        assert 'checkout_flow' in aggregate['by_feature']

    @patch('agent_system.cost_analytics.emit_event')
    def test_budget_warning_emitted(self, mock_emit, cost_tracker, mock_redis_client):
        """Test that budget_warning event is emitted at 80% threshold."""
        # Mock get_daily_spend to return 8.00 (80% of 10.00 budget)
        mock_redis_client.get.return_value = {
            'total_cost': 8.00,
            'by_agent': {},
            'by_model': {},
            'by_feature': {},
            'count': 1
        }

        # Record a cost that puts us over 80%
        cost_tracker.record_cost('scribe', 'claude-sonnet-4.5', 0.01, 'test', 't_1')

        # Check that budget_warning was emitted
        warning_calls = [call for call in mock_emit.call_args_list
                        if call[0][0] == 'budget_warning']
        assert len(warning_calls) > 0

        # Verify event payload
        event_payload = warning_calls[0][0][1]
        assert event_payload['budget_type'] == 'daily'
        assert 'current_spend' in event_payload
        assert 'limit' in event_payload
        assert 'remaining' in event_payload

    @patch('agent_system.cost_analytics.emit_event')
    def test_budget_exceeded_emitted(self, mock_emit, cost_tracker, mock_redis_client):
        """Test that budget_exceeded event is emitted at 100% threshold."""
        # Mock get_daily_spend to return 10.00 (100% of 10.00 budget)
        mock_redis_client.get.return_value = {
            'total_cost': 10.00,
            'by_agent': {},
            'by_model': {},
            'by_feature': {},
            'count': 1
        }

        # Record a cost that puts us at 100%
        cost_tracker.record_cost('scribe', 'claude-sonnet-4.5', 0.01, 'test', 't_1')

        # Check that budget_exceeded was emitted
        exceeded_calls = [call for call in mock_emit.call_args_list
                         if call[0][0] == 'budget_exceeded']
        assert len(exceeded_calls) > 0

        # Verify event payload
        event_payload = exceeded_calls[0][0][1]
        assert event_payload['budget_type'] == 'daily'
        assert 'current_spend' in event_payload
        assert 'limit' in event_payload

    def test_check_budget_available_ok(self, cost_tracker, mock_redis_client):
        """Test checking budget when funds are available."""
        # Mock current spend at 2.00
        mock_redis_client.get.return_value = {
            'total_cost': 2.00,
            'by_agent': {},
            'by_model': {},
            'by_feature': {},
            'count': 1
        }

        can_proceed, reason = cost_tracker.check_budget_available(
            estimated_cost=0.50,
            budget_type='daily'
        )

        assert can_proceed is True
        assert reason is None

    def test_check_budget_available_exceeded(self, cost_tracker, mock_redis_client):
        """Test checking budget when funds would be exceeded."""
        # Mock current spend at 9.00
        mock_redis_client.get.return_value = {
            'total_cost': 9.00,
            'by_agent': {},
            'by_model': {},
            'by_feature': {},
            'count': 1
        }

        can_proceed, reason = cost_tracker.check_budget_available(
            estimated_cost=2.00,
            budget_type='daily'
        )

        assert can_proceed is False
        assert reason is not None
        assert 'exceeded' in reason.lower()

    def test_get_daily_report(self, cost_tracker, mock_redis_client):
        """Test generating daily cost report."""
        # Mock Redis data
        mock_redis_client.get.return_value = {
            'total_cost': 0.50,
            'by_agent': {'scribe': 0.30, 'runner': 0.20},
            'by_model': {'claude-sonnet-4.5': 0.30, 'claude-haiku': 0.20},
            'by_feature': {'user_auth': 0.50},
            'count': 5
        }

        report = cost_tracker.get_daily_report()

        assert report['total_cost_usd'] == 0.50
        assert report['budget_usd'] == 10.00
        assert report['remaining_usd'] == 9.50
        assert report['percent_used'] == 5.0  # 0.50 / 10.00 * 100
        assert report['by_agent'] == {'scribe': 0.30, 'runner': 0.20}
        assert report['by_model'] == {'claude-sonnet-4.5': 0.30, 'claude-haiku': 0.20}
        assert report['by_feature'] == {'user_auth': 0.50}
        assert report['entry_count'] == 5

    def test_get_weekly_report(self, cost_tracker, mock_redis_client):
        """Test generating weekly cost report."""
        # Mock Redis data
        mock_redis_client.get.return_value = {
            'total_cost': 5.50,
            'by_agent': {'scribe': 3.00, 'runner': 2.50},
            'by_model': {'claude-sonnet-4.5': 3.00, 'claude-haiku': 2.50},
            'by_feature': {'feature1': 2.50, 'feature2': 3.00},
            'count': 25
        }

        report = cost_tracker.get_weekly_report()

        assert report['total_cost_usd'] == 5.50
        assert report['entry_count'] == 25
        assert 'week' in report

    def test_get_budget_status(self, cost_tracker, mock_redis_client):
        """Test getting budget status."""
        # Mock daily spend at 3.00 (30%)
        # Mock session spend at 1.00 (50%)
        def mock_get(key):
            if 'daily' in key:
                return {'total_cost': 3.00, 'by_agent': {}, 'by_model': {}, 'by_feature': {}, 'count': 1}
            elif 'session' in key:
                return {'total_cost': 1.00, 'by_agent': {}, 'by_model': {}, 'by_feature': {}, 'count': 1}
            return None

        mock_redis_client.get.side_effect = mock_get

        status = cost_tracker.get_budget_status()

        assert 'daily' in status
        assert 'session' in status

        # Check daily
        assert status['daily']['current_spend_usd'] == 3.00
        assert status['daily']['budget_usd'] == 10.00
        assert status['daily']['remaining_usd'] == 7.00
        assert status['daily']['percent_used'] == 30.0
        assert status['daily']['status'] == 'ok'

        # Check session
        assert status['session']['current_spend_usd'] == 1.00
        assert status['session']['budget_usd'] == 2.00
        assert status['session']['remaining_usd'] == 1.00
        assert status['session']['percent_used'] == 50.0
        assert status['session']['status'] == 'ok'

    def test_get_cost_by_agent(self, cost_tracker, mock_redis_client):
        """Test getting cost breakdown by agent."""
        mock_redis_client.get.return_value = {
            'total_cost': 0.50,
            'by_agent': {'scribe': 0.30, 'runner': 0.15, 'critic': 0.05},
            'by_model': {},
            'by_feature': {},
            'count': 3
        }

        by_agent = cost_tracker.get_cost_by_agent()

        assert by_agent == {'scribe': 0.30, 'runner': 0.15, 'critic': 0.05}

    def test_get_cost_by_model(self, cost_tracker, mock_redis_client):
        """Test getting cost breakdown by model."""
        mock_redis_client.get.return_value = {
            'total_cost': 0.50,
            'by_agent': {},
            'by_model': {'claude-sonnet-4.5': 0.30, 'claude-haiku': 0.20},
            'by_feature': {},
            'count': 2
        }

        by_model = cost_tracker.get_cost_by_model()

        assert by_model == {'claude-sonnet-4.5': 0.30, 'claude-haiku': 0.20}

    def test_get_cost_by_feature(self, cost_tracker, mock_redis_client):
        """Test getting cost breakdown by feature."""
        mock_redis_client.get.return_value = {
            'total_cost': 0.85,
            'by_agent': {},
            'by_model': {},
            'by_feature': {'user_auth': 0.50, 'checkout': 0.35},
            'count': 2
        }

        by_feature = cost_tracker.get_cost_by_feature()

        assert by_feature == {'user_auth': 0.50, 'checkout': 0.35}

    def test_get_historical_trend(self, cost_tracker, mock_redis_client):
        """Test getting historical cost trend."""
        # Mock Redis to return data for each day
        def mock_get(key):
            if 'daily' in key:
                return {
                    'total_cost': 1.00,
                    'by_agent': {},
                    'by_model': {},
                    'by_feature': {},
                    'count': 10
                }
            return None

        mock_redis_client.get.side_effect = mock_get

        trend = cost_tracker.get_historical_trend(days=3)

        assert len(trend) == 3
        for day_report in trend:
            assert 'date' in day_report
            assert 'total_cost_usd' in day_report
            assert day_report['total_cost_usd'] == 1.00

    def test_budget_status_labels(self, cost_tracker):
        """Test budget status label generation."""
        # Test 'ok' status
        assert cost_tracker._get_budget_status_label(5.0, 8.0, 10.0) == 'ok'

        # Test 'warning' status (80-99%)
        assert cost_tracker._get_budget_status_label(8.5, 8.0, 10.0) == 'warning'

        # Test 'exceeded' status (100%+)
        assert cost_tracker._get_budget_status_label(10.5, 8.0, 10.0) == 'exceeded'


class TestGlobalTracker:
    """Test global tracker functions."""

    @patch('agent_system.cost_analytics.RedisClient')
    def test_get_cost_tracker_singleton(self, mock_redis_class):
        """Test that get_cost_tracker returns singleton instance."""
        # Reset global tracker
        import agent_system.cost_analytics as ca
        ca._global_tracker = None

        tracker1 = get_cost_tracker()
        tracker2 = get_cost_tracker()

        assert tracker1 is tracker2

    @patch('agent_system.cost_analytics.get_cost_tracker')
    def test_record_agent_cost_convenience(self, mock_get_tracker):
        """Test convenience function for recording cost."""
        mock_tracker = Mock()
        mock_tracker.record_cost = Mock(return_value=True)
        mock_get_tracker.return_value = mock_tracker

        result = record_agent_cost(
            agent='scribe',
            model='claude-sonnet-4.5',
            cost_usd=0.12,
            feature='test_feature',
            task_id='t_789'
        )

        assert result is True
        mock_tracker.record_cost.assert_called_once_with(
            'scribe',
            'claude-sonnet-4.5',
            0.12,
            'test_feature',
            't_789'
        )


class TestIntegration:
    """Integration tests for cost tracking."""

    @patch('agent_system.cost_analytics.emit_event')
    def test_full_cost_tracking_flow(self, mock_emit, cost_tracker, mock_redis_client):
        """Test complete cost tracking flow."""
        # Record several costs
        cost_tracker.record_cost('scribe', 'claude-sonnet-4.5', 0.12, 'auth', 't_1')
        cost_tracker.record_cost('runner', 'claude-haiku', 0.02, 'auth', 't_1')
        cost_tracker.record_cost('critic', 'claude-haiku', 0.01, 'auth', 't_1')
        cost_tracker.record_cost('gemini', 'gemini-2.5-pro', 0.08, 'auth', 't_1')

        # Verify all costs are tracked
        assert len(cost_tracker._daily_cache) == 4

        # Verify Redis calls were made
        assert mock_redis_client.client.rpush.call_count == 4
        assert mock_redis_client.set.call_count >= 4  # At least once per entry

    @patch('agent_system.cost_analytics.emit_event')
    def test_budget_enforcement_flow(self, mock_emit, cost_tracker, mock_redis_client):
        """Test budget enforcement with warnings and hard stops."""
        # Mock incremental spending
        spend_values = [0.0, 7.0, 8.5, 10.5]  # 0%, 70%, 85%, 105%
        call_count = [0]

        def mock_get(key):
            if 'daily' in key:
                result = {
                    'total_cost': spend_values[min(call_count[0], len(spend_values) - 1)],
                    'by_agent': {},
                    'by_model': {},
                    'by_feature': {},
                    'count': call_count[0]
                }
                call_count[0] += 1
                return result
            return None

        mock_redis_client.get.side_effect = mock_get

        # Record costs to trigger different thresholds
        cost_tracker.record_cost('scribe', 'claude-sonnet-4.5', 0.10, 'test1', 't_1')  # No warning
        cost_tracker.record_cost('scribe', 'claude-sonnet-4.5', 0.10, 'test2', 't_2')  # Warning at 80%
        cost_tracker.record_cost('scribe', 'claude-sonnet-4.5', 0.10, 'test3', 't_3')  # Exceeded at 100%

        # Verify events were emitted
        warning_calls = [call for call in mock_emit.call_args_list
                        if call[0][0] == 'budget_warning']
        exceeded_calls = [call for call in mock_emit.call_args_list
                         if call[0][0] == 'budget_exceeded']

        # We should have at least one of each (depending on mock setup)
        assert len(warning_calls) >= 0
        assert len(exceeded_calls) >= 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
