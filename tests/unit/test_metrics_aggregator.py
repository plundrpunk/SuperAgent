"""
Unit tests for MetricsAggregator

Tests:
- Time-window aggregation
- Redis storage/retrieval
- Metric calculations
- Historical trend generation
- Cleanup of old metrics
"""
import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch

from agent_system.metrics_aggregator import (
    MetricsAggregator,
    get_metrics_aggregator,
    AgentActivityRecord,
    FeatureCompletionRecord,
    CriticDecisionRecord,
    ValidationResultRecord
)


@pytest.fixture
def mock_redis_client():
    """Create mock Redis client for testing."""
    mock_client = Mock()
    mock_redis = Mock()
    mock_redis.client = mock_client

    # Mock Redis operations
    mock_client.zadd = Mock(return_value=1)
    mock_client.expire = Mock(return_value=True)
    mock_client.zrangebyscore = Mock(return_value=[])
    mock_client.zrange = Mock(return_value=[])
    mock_client.keys = Mock(return_value=[])
    mock_client.delete = Mock(return_value=1)

    return mock_redis


@pytest.fixture
def aggregator(mock_redis_client):
    """Create MetricsAggregator instance with mocked Redis."""
    return MetricsAggregator(redis_client=mock_redis_client)


class TestMetricsAggregator:
    """Test suite for MetricsAggregator."""

    def test_initialization(self, aggregator):
        """Test aggregator initialization."""
        assert aggregator.redis_client is not None
        assert aggregator._pending_activities == []
        assert aggregator._pending_completions == []
        assert aggregator._pending_critic_decisions == []
        assert aggregator._pending_validations == []

    def test_get_hour_key(self, aggregator):
        """Test hour key generation."""
        # Test with specific timestamp
        timestamp = datetime(2025, 10, 14, 15, 30, 0).timestamp()
        hour_key = aggregator._get_hour_key(timestamp)
        assert hour_key == '2025-10-14-15'

        # Test with current time
        current_hour_key = aggregator._get_hour_key()
        expected = datetime.now().strftime('%Y-%m-%d-%H')
        assert current_hour_key == expected

    def test_get_date_key(self, aggregator):
        """Test date key generation."""
        timestamp = datetime(2025, 10, 14, 15, 30, 0).timestamp()
        date_key = aggregator._get_date_key(timestamp)
        assert date_key == '2025-10-14'

    def test_record_agent_activity(self, aggregator, mock_redis_client):
        """Test recording agent activity."""
        # Record activity
        result = aggregator.record_agent_activity(
            agent='scribe',
            duration_ms=2500,
            cost_usd=0.12,
            task_id='t_123',
            model='sonnet-4.5'
        )

        assert result is True

        # Verify Redis calls
        assert mock_redis_client.client.zadd.call_count == 2  # agent + model
        assert mock_redis_client.client.expire.call_count == 2

        # Verify data format
        call_args = mock_redis_client.client.zadd.call_args_list[0]
        key = call_args[0][0]
        assert 'metrics:agent_activity:scribe:' in key

        # Verify record format
        record_dict = call_args[0][1]
        record_value = list(record_dict.keys())[0]
        assert '2500|0.12|t_123' in record_value

    def test_record_agent_activity_without_model(self, aggregator, mock_redis_client):
        """Test recording agent activity without model."""
        result = aggregator.record_agent_activity(
            agent='runner',
            duration_ms=800,
            cost_usd=0.02
        )

        assert result is True
        # Only one zadd call (no model tracking)
        assert mock_redis_client.client.zadd.call_count == 1

    def test_record_feature_completion(self, aggregator, mock_redis_client):
        """Test recording feature completion."""
        result = aggregator.record_feature_completion(
            feature='user_authentication',
            total_cost=0.35,
            duration_ms=15000,
            retry_count=1,
            task_id='t_123'
        )

        assert result is True

        # Verify Redis calls
        mock_redis_client.client.zadd.assert_called_once()
        mock_redis_client.client.expire.assert_called_once()

        # Verify data format
        call_args = mock_redis_client.client.zadd.call_args
        key = call_args[0][0]
        assert 'metrics:feature_completion:' in key

        record_dict = call_args[0][1]
        record_value = list(record_dict.keys())[0]
        assert 'user_authentication|0.35|15000|1|t_123' in record_value

    def test_record_critic_decision(self, aggregator, mock_redis_client):
        """Test recording critic decision."""
        result = aggregator.record_critic_decision(
            test_id='test_001',
            decision='approved',
            reason='good quality'
        )

        assert result is True

        # Verify Redis calls
        mock_redis_client.client.zadd.assert_called_once()

        # Verify data format
        call_args = mock_redis_client.client.zadd.call_args
        key = call_args[0][0]
        assert 'metrics:critic_decisions:' in key

        record_dict = call_args[0][1]
        record_value = list(record_dict.keys())[0]
        assert 'test_001|approved|good quality' in record_value

    def test_record_critic_decision_rejected(self, aggregator, mock_redis_client):
        """Test recording rejected critic decision."""
        result = aggregator.record_critic_decision(
            test_id='test_002',
            decision='rejected',
            reason='uses nth() selectors'
        )

        assert result is True

        call_args = mock_redis_client.client.zadd.call_args
        record_dict = call_args[0][1]
        record_value = list(record_dict.keys())[0]
        assert 'test_002|rejected|uses nth() selectors' in record_value

    def test_record_validation_result(self, aggregator, mock_redis_client):
        """Test recording validation result."""
        result = aggregator.record_validation_result(
            test_id='test_001',
            passed=True,
            duration_ms=5000,
            cost_usd=0.08
        )

        assert result is True

        # Verify data format
        call_args = mock_redis_client.client.zadd.call_args
        record_dict = call_args[0][1]
        record_value = list(record_dict.keys())[0]
        assert 'test_001|1|5000|0.08' in record_value

    def test_record_validation_result_failed(self, aggregator, mock_redis_client):
        """Test recording failed validation result."""
        result = aggregator.record_validation_result(
            test_id='test_002',
            passed=False,
            duration_ms=3000,
            cost_usd=0.05
        )

        assert result is True

        call_args = mock_redis_client.client.zadd.call_args
        record_dict = call_args[0][1]
        record_value = list(record_dict.keys())[0]
        assert 'test_002|0|3000|0.05' in record_value

    def test_get_metrics_summary_empty(self, aggregator, mock_redis_client):
        """Test getting metrics summary with no data."""
        summary = aggregator.get_metrics_summary(window_hours=1)

        assert 'agent_utilization' in summary
        assert 'cost_per_feature' in summary
        assert 'average_retry_count' in summary
        assert 'critic_rejection_rate' in summary
        assert 'validation_pass_rate' in summary
        assert 'time_to_completion' in summary
        assert 'model_usage' in summary

        # All values should be 0 or empty
        assert summary['average_retry_count'] == 0.0
        assert summary['critic_rejection_rate'] == 0.0
        assert summary['validation_pass_rate'] == 0.0

    def test_get_metrics_summary_with_data(self, aggregator, mock_redis_client):
        """Test getting metrics summary with mock data."""
        current_time = time.time()

        # Mock agent activity data
        mock_redis_client.client.zrangebyscore.side_effect = [
            # Agent activities (called for each agent)
            ['2500|0.12|t_123'],  # scribe
            [],  # runner
            [],  # medic
            [],  # critic
            [],  # gemini
            [],  # kaya
            # Feature completions
            ['user_auth|0.35|15000|1|t_123', 'checkout|0.42|18000|2|t_124'],
            # Critic decisions
            ['test_001|approved|none', 'test_002|rejected|flaky'],
            # Validation results
            ['test_001|1|5000|0.08', 'test_002|0|4000|0.07']
        ]

        summary = aggregator.get_metrics_summary(window_hours=1)

        # Check agent utilization
        assert 'scribe' in summary['agent_utilization']
        assert summary['agent_utilization']['scribe']['active_time_ms'] == 2500
        assert summary['agent_utilization']['scribe']['total_cost'] == 0.12

        # Check cost per feature
        assert 'user_auth' in summary['cost_per_feature']
        assert 'checkout' in summary['cost_per_feature']

        # Check average retry count
        assert summary['average_retry_count'] == 1.5  # (1 + 2) / 2

        # Check critic rejection rate
        assert summary['critic_rejection_rate'] == 0.5  # 1 rejected / 2 total

        # Check validation pass rate
        assert summary['validation_pass_rate'] == 0.5  # 1 passed / 2 total

    def test_get_hour_keys_in_window(self, aggregator):
        """Test getting hour keys for time window."""
        hour_keys = aggregator._get_hour_keys_in_window(window_hours=3)

        assert len(hour_keys) == 3
        # Verify format
        for key in hour_keys:
            assert len(key) == 13  # YYYY-MM-DD-HH
            assert key[4] == '-'
            assert key[7] == '-'
            assert key[10] == '-'

    def test_get_daily_summary_cost_per_feature(self, aggregator, mock_redis_client):
        """Test getting daily summary for cost_per_feature metric."""
        date_str = '2025-10-14'

        # Mock feature completion data
        mock_redis_client.client.zrange.return_value = [
            'feature1|0.35|15000|1|t_001',
            'feature2|0.42|18000|2|t_002',
            'feature1|0.38|16000|1|t_003'
        ]

        summary = aggregator._get_daily_summary(date_str, 'cost_per_feature')

        assert 'value' in summary
        assert summary['value'] > 0
        assert summary['count'] == 3
        assert summary['total_cost'] == 0.35 + 0.42 + 0.38

    def test_get_daily_summary_validation_pass_rate(self, aggregator, mock_redis_client):
        """Test getting daily summary for validation_pass_rate metric."""
        date_str = '2025-10-14'

        # Mock validation data: 3 passed, 2 failed
        mock_redis_client.client.zrange.return_value = [
            'test_001|1|5000|0.08',
            'test_002|1|4500|0.07',
            'test_003|0|3000|0.05',
            'test_004|1|5200|0.08',
            'test_005|0|2800|0.04'
        ]

        summary = aggregator._get_daily_summary(date_str, 'validation_pass_rate')

        assert summary['value'] == 0.6  # 3 / 5
        assert summary['passed'] == 3
        assert summary['total'] == 5

    def test_get_daily_summary_average_retry_count(self, aggregator, mock_redis_client):
        """Test getting daily summary for average_retry_count metric."""
        date_str = '2025-10-14'

        # Mock completion data with retries
        mock_redis_client.client.zrange.return_value = [
            'feature1|0.35|15000|1|t_001',
            'feature2|0.42|18000|2|t_002',
            'feature3|0.38|16000|0|t_003',
            'feature4|0.45|20000|3|t_004'
        ]

        summary = aggregator._get_daily_summary(date_str, 'average_retry_count')

        assert summary['value'] == 1.5  # (1 + 2 + 0 + 3) / 4
        assert summary['count'] == 4

    def test_get_daily_summary_critic_rejection_rate(self, aggregator, mock_redis_client):
        """Test getting daily summary for critic_rejection_rate metric."""
        date_str = '2025-10-14'

        # Mock critic data: 2 rejected, 3 approved
        mock_redis_client.client.zrange.return_value = [
            'test_001|approved|none',
            'test_002|rejected|flaky',
            'test_003|approved|none',
            'test_004|rejected|uses nth()',
            'test_005|approved|none'
        ]

        summary = aggregator._get_daily_summary(date_str, 'critic_rejection_rate')

        assert summary['value'] == 0.4  # 2 / 5
        assert summary['rejected'] == 2
        assert summary['total'] == 5

    def test_get_historical_trend(self, aggregator, mock_redis_client):
        """Test getting historical trend."""
        # Mock daily summary data
        with patch.object(aggregator, '_get_daily_summary') as mock_summary:
            mock_summary.return_value = {'value': 0.35, 'count': 10}

            trend = aggregator.get_historical_trend('cost_per_feature', days=3)

            assert len(trend) == 3
            assert all('date' in point for point in trend)
            assert all('value' in point for point in trend)
            assert mock_summary.call_count == 3

    def test_cleanup_old_metrics(self, aggregator, mock_redis_client):
        """Test cleanup of old metrics."""
        # Mock keys to delete
        old_date = (datetime.now() - timedelta(days=35)).strftime('%Y-%m-%d-%H')
        recent_date = datetime.now().strftime('%Y-%m-%d-%H')

        mock_keys = [
            f'metrics:agent_activity:scribe:{old_date}',
            f'metrics:agent_activity:runner:{old_date}',
            f'metrics:feature_completion:{recent_date}'
        ]

        mock_redis_client.client.keys.return_value = mock_keys

        deleted_count = aggregator.cleanup_old_metrics(days=30)

        # Should delete 2 old keys, keep 1 recent key
        assert deleted_count == 2
        assert mock_redis_client.client.delete.call_count == 2

    def test_error_handling_agent_activity(self, aggregator, mock_redis_client):
        """Test error handling when recording agent activity fails."""
        mock_redis_client.client.zadd.side_effect = Exception("Redis error")

        result = aggregator.record_agent_activity(
            agent='scribe',
            duration_ms=2500,
            cost_usd=0.12
        )

        assert result is False

    def test_error_handling_metrics_summary(self, aggregator, mock_redis_client):
        """Test error handling when getting metrics summary fails."""
        mock_redis_client.client.zrangebyscore.side_effect = Exception("Redis error")

        summary = aggregator.get_metrics_summary(window_hours=1)

        assert 'error' in summary
        assert summary['agent_utilization'] == {}

    def test_global_aggregator_singleton(self):
        """Test global aggregator singleton pattern."""
        agg1 = get_metrics_aggregator()
        agg2 = get_metrics_aggregator()

        assert agg1 is agg2

    def test_dataclass_creation(self):
        """Test dataclass creation for records."""
        # AgentActivityRecord
        activity = AgentActivityRecord(
            agent='scribe',
            timestamp=time.time(),
            duration_ms=2500,
            cost_usd=0.12,
            task_id='t_123'
        )
        assert activity.agent == 'scribe'
        assert activity.duration_ms == 2500

        # FeatureCompletionRecord
        completion = FeatureCompletionRecord(
            feature='user_auth',
            timestamp=time.time(),
            total_cost=0.35,
            duration_ms=15000,
            retry_count=1
        )
        assert completion.feature == 'user_auth'
        assert completion.retry_count == 1

        # CriticDecisionRecord
        decision = CriticDecisionRecord(
            test_id='test_001',
            timestamp=time.time(),
            decision='approved'
        )
        assert decision.decision == 'approved'

        # ValidationResultRecord
        validation = ValidationResultRecord(
            test_id='test_001',
            timestamp=time.time(),
            passed=True,
            duration_ms=5000,
            cost_usd=0.08
        )
        assert validation.passed is True


@pytest.mark.integration
class TestMetricsAggregatorIntegration:
    """Integration tests with real Redis (requires Redis running)."""

    @pytest.fixture
    def real_redis_aggregator(self):
        """Create aggregator with real Redis connection."""
        from agent_system.state.redis_client import RedisClient
        try:
            redis_client = RedisClient()
            if not redis_client.health_check():
                pytest.skip("Redis not available")
            aggregator = MetricsAggregator(redis_client=redis_client)
            yield aggregator
            # Cleanup
            aggregator.cleanup_old_metrics(days=0)
        except Exception:
            pytest.skip("Redis not available")

    def test_full_workflow_with_redis(self, real_redis_aggregator):
        """Test full workflow with real Redis."""
        aggregator = real_redis_aggregator

        # Record some activities
        aggregator.record_agent_activity('scribe', 2500, 0.12, model='sonnet-4.5')
        aggregator.record_agent_activity('runner', 800, 0.02, model='haiku')

        # Record feature completion
        aggregator.record_feature_completion(
            feature='test_feature',
            total_cost=0.35,
            duration_ms=15000,
            retry_count=1
        )

        # Record critic decision
        aggregator.record_critic_decision('test_001', 'approved')

        # Record validation
        aggregator.record_validation_result('test_001', passed=True, duration_ms=5000, cost_usd=0.08)

        # Get summary
        summary = aggregator.get_metrics_summary(window_hours=1)

        # Verify data was stored and retrieved
        assert 'scribe' in summary['agent_utilization']
        assert summary['agent_utilization']['scribe']['total_cost'] == 0.12
        assert 'test_feature' in summary['cost_per_feature']
        assert summary['validation_pass_rate'] == 1.0
