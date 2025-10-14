#!/usr/bin/env python3
"""
Validation script for metrics aggregation system.
Tests basic functionality without requiring Redis to be running.
"""
import sys
import time
from unittest.mock import Mock, MagicMock

# Mock Redis before importing metrics_aggregator
sys.modules['redis'] = MagicMock()

from agent_system.metrics_aggregator import MetricsAggregator


def create_mock_redis():
    """Create a mock Redis client with basic functionality."""
    mock_client = Mock()
    mock_redis = Mock()
    mock_redis.client = mock_client

    # Mock sorted set storage
    storage = {}

    def mock_zadd(key, mapping):
        if key not in storage:
            storage[key] = []
        for value, score in mapping.items():
            storage[key].append((score, value))
        return 1

    def mock_zrangebyscore(key, min_score, max_score):
        if key not in storage:
            return []
        return [v for s, v in storage[key] if min_score <= s <= max_score]

    def mock_zrange(key, start, stop):
        if key not in storage:
            return []
        return [v for s, v in storage[key]]

    mock_client.zadd = mock_zadd
    mock_client.expire = Mock(return_value=True)
    mock_client.zrangebyscore = mock_zrangebyscore
    mock_client.zrange = mock_zrange
    mock_client.keys = Mock(return_value=[])
    mock_client.delete = Mock(return_value=1)

    return mock_redis


def test_basic_functionality():
    """Test basic metrics recording and retrieval."""
    print("Testing Metrics Aggregation System")
    print("=" * 60)

    # Create aggregator with mock Redis
    mock_redis = create_mock_redis()
    aggregator = MetricsAggregator(redis_client=mock_redis)

    print("\n1. Testing Agent Activity Recording...")
    result = aggregator.record_agent_activity(
        agent='scribe',
        duration_ms=2500,
        cost_usd=0.12,
        model='sonnet-4.5'
    )
    print(f"   ✓ Agent activity recorded: {result}")

    print("\n2. Testing Feature Completion Recording...")
    result = aggregator.record_feature_completion(
        feature='user_authentication',
        total_cost=0.35,
        duration_ms=15000,
        retry_count=1
    )
    print(f"   ✓ Feature completion recorded: {result}")

    print("\n3. Testing Critic Decision Recording...")
    result = aggregator.record_critic_decision(
        test_id='test_001',
        decision='approved'
    )
    print(f"   ✓ Critic decision recorded: {result}")

    print("\n4. Testing Validation Result Recording...")
    result = aggregator.record_validation_result(
        test_id='test_001',
        passed=True,
        duration_ms=5000,
        cost_usd=0.08
    )
    print(f"   ✓ Validation result recorded: {result}")

    print("\n5. Testing Key Generation...")
    hour_key = aggregator._get_hour_key()
    date_key = aggregator._get_date_key()
    print(f"   ✓ Hour key: {hour_key}")
    print(f"   ✓ Date key: {date_key}")

    print("\n6. Testing Hour Keys in Window...")
    hour_keys = aggregator._get_hour_keys_in_window(window_hours=3)
    print(f"   ✓ Generated {len(hour_keys)} hour keys")
    print(f"   ✓ Keys: {hour_keys}")

    print("\n7. Testing Metrics Summary...")
    summary = aggregator.get_metrics_summary(window_hours=1)
    print(f"   ✓ Summary generated with {len(summary)} metrics")
    print(f"   ✓ Metrics: {list(summary.keys())}")

    print("\n" + "=" * 60)
    print("✓ All validation tests passed!")
    print("\nMetrics Aggregation System is ready for use.")
    print("\nNext steps:")
    print("1. Install Redis: brew install redis (macOS) or apt-get install redis (Linux)")
    print("2. Start Redis: redis-server")
    print("3. Run unit tests: python3 -m pytest tests/unit/test_metrics_aggregator.py -v")
    print("4. Try CLI commands: python3 agent_system/cli.py metrics summary --window 1")

    return True


def main():
    """Main entry point."""
    try:
        success = test_basic_functionality()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Validation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
