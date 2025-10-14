"""
Comprehensive Metrics Aggregation System for SuperAgent

Tracks performance metrics across all agents to measure system health and optimize costs.
Stores metrics in Redis using sorted sets for efficient time-series operations.

Metrics Tracked:
- agent_utilization: Time each agent spends active vs idle
- cost_per_feature: Total cost for each completed feature
- average_retry_count: Mean retries before success
- critic_rejection_rate: % of tests rejected by Critic
- validation_pass_rate: % of tests passing Gemini validation
- time_to_completion: End-to-end time per feature
- model_usage: Haiku vs Sonnet usage ratio

Usage:
    from agent_system.metrics_aggregator import get_metrics_aggregator

    # Record agent activity
    aggregator = get_metrics_aggregator()
    aggregator.record_agent_activity('scribe', duration_ms=2500, cost_usd=0.12)

    # Record feature completion
    aggregator.record_feature_completion(
        feature='user_authentication',
        total_cost=0.35,
        duration_ms=15000,
        retry_count=1
    )

    # Get metrics summary
    summary = aggregator.get_metrics_summary(window_hours=1)
    print(summary)

    # Get historical trend
    trend = aggregator.get_historical_trend('cost_per_feature', days=7)
"""
import time
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict
from dataclasses import dataclass, field

from agent_system.state.redis_client import RedisClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class AgentActivityRecord:
    """Record of agent activity for utilization tracking."""
    agent: str
    timestamp: float
    duration_ms: int
    cost_usd: float
    task_id: Optional[str] = None


@dataclass
class FeatureCompletionRecord:
    """Record of completed feature for cost and retry tracking."""
    feature: str
    timestamp: float
    total_cost: float
    duration_ms: int
    retry_count: int
    task_id: Optional[str] = None


@dataclass
class CriticDecisionRecord:
    """Record of critic decision for rejection rate tracking."""
    test_id: str
    timestamp: float
    decision: str  # 'approved' or 'rejected'
    reason: Optional[str] = None


@dataclass
class ValidationResultRecord:
    """Record of validation result for pass rate tracking."""
    test_id: str
    timestamp: float
    passed: bool
    duration_ms: int
    cost_usd: float


class MetricsAggregator:
    """
    Comprehensive metrics aggregation system with Redis time-series storage.

    Features:
    - Time-series metrics storage with hourly aggregation
    - Redis sorted sets for efficient time-window queries
    - 30-day retention with automatic cleanup
    - Thread-safe operation
    - Integration with observability event system

    Redis Key Structure:
    - metrics:agent_activity:{agent}:{hour} -> sorted set (timestamp -> duration_ms|cost)
    - metrics:feature_completion:{hour} -> sorted set (timestamp -> feature|cost|duration|retries)
    - metrics:critic_decisions:{hour} -> sorted set (timestamp -> test_id|decision)
    - metrics:validation_results:{hour} -> sorted set (timestamp -> test_id|passed|cost)
    - metrics:model_usage:{model}:{hour} -> sorted set (timestamp -> duration_ms|cost)
    - metrics:hourly_summary:{hour} -> hash with aggregated metrics
    """

    # TTL for metrics (30 days)
    METRICS_TTL = 30 * 24 * 3600

    def __init__(self, redis_client: Optional[RedisClient] = None):
        """
        Initialize metrics aggregator with Redis for time-series storage.

        Args:
            redis_client: Redis client instance (creates new if None)
        """
        self.redis_client = redis_client or RedisClient()
        self._lock = threading.Lock()

        # In-memory cache for pending metrics (flushed periodically)
        self._pending_activities: List[AgentActivityRecord] = []
        self._pending_completions: List[FeatureCompletionRecord] = []
        self._pending_critic_decisions: List[CriticDecisionRecord] = []
        self._pending_validations: List[ValidationResultRecord] = []

        # Cache size threshold for auto-flush
        self._flush_threshold = 10

        logger.info("MetricsAggregator initialized with Redis backend")

    def _get_hour_key(self, timestamp: Optional[float] = None) -> str:
        """
        Get hour key for Redis storage (YYYY-MM-DD-HH format).

        Args:
            timestamp: Unix timestamp (uses current time if None)

        Returns:
            Hour string in YYYY-MM-DD-HH format
        """
        dt = datetime.fromtimestamp(timestamp or time.time())
        return dt.strftime('%Y-%m-%d-%H')

    def _get_date_key(self, timestamp: Optional[float] = None) -> str:
        """
        Get date key for Redis storage (YYYY-MM-DD format).

        Args:
            timestamp: Unix timestamp (uses current time if None)

        Returns:
            Date string in YYYY-MM-DD format
        """
        dt = datetime.fromtimestamp(timestamp or time.time())
        return dt.strftime('%Y-%m-%d')

    def record_agent_activity(
        self,
        agent: str,
        duration_ms: int,
        cost_usd: float,
        task_id: Optional[str] = None,
        model: Optional[str] = None
    ) -> bool:
        """
        Track agent usage for utilization metrics.

        Records how long each agent was active and what it cost.
        Data is stored in Redis sorted sets for efficient time-window queries.

        Args:
            agent: Agent name (scribe, runner, medic, critic, gemini, kaya)
            duration_ms: Duration agent was active in milliseconds
            cost_usd: Cost incurred by agent
            task_id: Optional task identifier
            model: Optional model name (haiku, sonnet, etc.)

        Returns:
            True if recorded successfully
        """
        try:
            timestamp = time.time()
            hour_key = self._get_hour_key(timestamp)

            # Store in sorted set: score=timestamp, value=serialized record
            activity_key = f"metrics:agent_activity:{agent}:{hour_key}"
            record_value = f"{duration_ms}|{cost_usd}|{task_id or 'none'}"

            self.redis_client.client.zadd(activity_key, {record_value: timestamp})
            self.redis_client.client.expire(activity_key, self.METRICS_TTL)

            # Also track model usage if provided
            if model:
                model_key = f"metrics:model_usage:{model}:{hour_key}"
                model_value = f"{duration_ms}|{cost_usd}|{agent}"
                self.redis_client.client.zadd(model_key, {model_value: timestamp})
                self.redis_client.client.expire(model_key, self.METRICS_TTL)

            logger.debug(f"Recorded activity: agent={agent}, duration={duration_ms}ms, cost=${cost_usd:.4f}")
            return True

        except Exception as e:
            logger.error(f"Failed to record agent activity: {e}")
            return False

    def record_feature_completion(
        self,
        feature: str,
        total_cost: float,
        duration_ms: int,
        retry_count: int,
        task_id: Optional[str] = None
    ) -> bool:
        """
        Track feature metrics for cost and retry analysis.

        Records completed features with their total cost, duration, and retry count.

        Args:
            feature: Feature name/description
            total_cost: Total cost for entire feature pipeline
            duration_ms: Total duration from start to completion
            retry_count: Number of retries before success
            task_id: Optional task identifier

        Returns:
            True if recorded successfully
        """
        try:
            timestamp = time.time()
            hour_key = self._get_hour_key(timestamp)

            # Store in sorted set
            completion_key = f"metrics:feature_completion:{hour_key}"
            record_value = f"{feature}|{total_cost}|{duration_ms}|{retry_count}|{task_id or 'none'}"

            self.redis_client.client.zadd(completion_key, {record_value: timestamp})
            self.redis_client.client.expire(completion_key, self.METRICS_TTL)

            logger.debug(f"Recorded completion: feature={feature}, cost=${total_cost:.4f}, retries={retry_count}")
            return True

        except Exception as e:
            logger.error(f"Failed to record feature completion: {e}")
            return False

    def record_critic_decision(
        self,
        test_id: str,
        decision: str,
        reason: Optional[str] = None
    ) -> bool:
        """
        Track critic accept/reject decisions for rejection rate analysis.

        Args:
            test_id: Test identifier
            decision: 'approved' or 'rejected'
            reason: Optional reason for decision

        Returns:
            True if recorded successfully
        """
        try:
            timestamp = time.time()
            hour_key = self._get_hour_key(timestamp)

            # Store in sorted set
            critic_key = f"metrics:critic_decisions:{hour_key}"
            record_value = f"{test_id}|{decision}|{reason or 'none'}"

            self.redis_client.client.zadd(critic_key, {record_value: timestamp})
            self.redis_client.client.expire(critic_key, self.METRICS_TTL)

            logger.debug(f"Recorded critic decision: test={test_id}, decision={decision}")
            return True

        except Exception as e:
            logger.error(f"Failed to record critic decision: {e}")
            return False

    def record_validation_result(
        self,
        test_id: str,
        passed: bool,
        duration_ms: int = 0,
        cost_usd: float = 0.0
    ) -> bool:
        """
        Track Gemini validation results for pass rate analysis.

        Args:
            test_id: Test identifier
            passed: True if validation passed, False otherwise
            duration_ms: Validation duration in milliseconds
            cost_usd: Validation cost

        Returns:
            True if recorded successfully
        """
        try:
            timestamp = time.time()
            hour_key = self._get_hour_key(timestamp)

            # Store in sorted set
            validation_key = f"metrics:validation_results:{hour_key}"
            record_value = f"{test_id}|{1 if passed else 0}|{duration_ms}|{cost_usd}"

            self.redis_client.client.zadd(validation_key, {record_value: timestamp})
            self.redis_client.client.expire(validation_key, self.METRICS_TTL)

            logger.debug(f"Recorded validation: test={test_id}, passed={passed}")
            return True

        except Exception as e:
            logger.error(f"Failed to record validation result: {e}")
            return False

    def get_metrics_summary(self, window_hours: int = 1) -> Dict[str, Any]:
        """
        Get aggregated metrics for time window.

        Computes all key metrics from Redis time-series data within the specified
        time window.

        Args:
            window_hours: Time window in hours (default 1)

        Returns:
            Dictionary with all metrics:
            {
                'agent_utilization': {agent: utilization_percent, ...},
                'cost_per_feature': {feature: avg_cost, ...},
                'average_retry_count': float,
                'critic_rejection_rate': float,
                'validation_pass_rate': float,
                'time_to_completion': {feature: avg_duration_ms, ...},
                'model_usage': {model: {'count': int, 'total_cost': float}, ...}
            }
        """
        try:
            current_time = time.time()
            start_time = current_time - (window_hours * 3600)

            # Calculate metrics for each hour in the window
            metrics = {
                'agent_utilization': {},
                'cost_per_feature': {},
                'average_retry_count': 0.0,
                'critic_rejection_rate': 0.0,
                'validation_pass_rate': 0.0,
                'time_to_completion': {},
                'model_usage': {},
                'window_hours': window_hours,
                'timestamp': current_time
            }

            # Get hour keys for the window
            hour_keys = self._get_hour_keys_in_window(window_hours)

            # 1. Agent Utilization
            agent_durations = defaultdict(float)
            agent_costs = defaultdict(float)

            for agent in ['scribe', 'runner', 'medic', 'critic', 'gemini', 'kaya']:
                for hour_key in hour_keys:
                    activity_key = f"metrics:agent_activity:{agent}:{hour_key}"

                    # Get records in time range
                    records = self.redis_client.client.zrangebyscore(
                        activity_key, start_time, current_time
                    )

                    for record in records:
                        parts = record.split('|')
                        if len(parts) >= 2:
                            duration_ms = float(parts[0])
                            cost_usd = float(parts[1])
                            agent_durations[agent] += duration_ms
                            agent_costs[agent] += cost_usd

            # Calculate utilization percentage (time active / window time)
            window_ms = window_hours * 3600 * 1000
            for agent, total_duration in agent_durations.items():
                utilization = (total_duration / window_ms) * 100 if window_ms > 0 else 0
                metrics['agent_utilization'][agent] = {
                    'utilization_percent': min(utilization, 100.0),
                    'active_time_ms': total_duration,
                    'total_cost': agent_costs[agent]
                }

            # 2. Cost per Feature & Average Retry Count
            feature_costs = defaultdict(list)
            feature_durations = defaultdict(list)
            all_retries = []

            for hour_key in hour_keys:
                completion_key = f"metrics:feature_completion:{hour_key}"
                records = self.redis_client.client.zrangebyscore(
                    completion_key, start_time, current_time
                )

                for record in records:
                    parts = record.split('|')
                    if len(parts) >= 4:
                        feature = parts[0]
                        cost = float(parts[1])
                        duration = int(parts[2])
                        retries = int(parts[3])

                        feature_costs[feature].append(cost)
                        feature_durations[feature].append(duration)
                        all_retries.append(retries)

            # Calculate averages
            for feature, costs in feature_costs.items():
                metrics['cost_per_feature'][feature] = {
                    'average_cost': sum(costs) / len(costs) if costs else 0.0,
                    'total_cost': sum(costs),
                    'count': len(costs)
                }

            for feature, durations in feature_durations.items():
                metrics['time_to_completion'][feature] = {
                    'average_duration_ms': sum(durations) / len(durations) if durations else 0,
                    'count': len(durations)
                }

            metrics['average_retry_count'] = sum(all_retries) / len(all_retries) if all_retries else 0.0

            # 3. Critic Rejection Rate
            total_decisions = 0
            rejected_count = 0

            for hour_key in hour_keys:
                critic_key = f"metrics:critic_decisions:{hour_key}"
                records = self.redis_client.client.zrangebyscore(
                    critic_key, start_time, current_time
                )

                for record in records:
                    parts = record.split('|')
                    if len(parts) >= 2:
                        decision = parts[1]
                        total_decisions += 1
                        if decision == 'rejected':
                            rejected_count += 1

            metrics['critic_rejection_rate'] = (rejected_count / total_decisions) if total_decisions > 0 else 0.0

            # 4. Validation Pass Rate
            total_validations = 0
            passed_count = 0

            for hour_key in hour_keys:
                validation_key = f"metrics:validation_results:{hour_key}"
                records = self.redis_client.client.zrangebyscore(
                    validation_key, start_time, current_time
                )

                for record in records:
                    parts = record.split('|')
                    if len(parts) >= 2:
                        passed = int(parts[1])
                        total_validations += 1
                        if passed == 1:
                            passed_count += 1

            metrics['validation_pass_rate'] = (passed_count / total_validations) if total_validations > 0 else 0.0

            # 5. Model Usage
            model_stats = defaultdict(lambda: {'count': 0, 'total_duration_ms': 0, 'total_cost': 0.0})

            for model in ['haiku', 'sonnet', 'sonnet-4.5', 'gemini-2.5-pro']:
                for hour_key in hour_keys:
                    model_key = f"metrics:model_usage:{model}:{hour_key}"
                    records = self.redis_client.client.zrangebyscore(
                        model_key, start_time, current_time
                    )

                    for record in records:
                        parts = record.split('|')
                        if len(parts) >= 2:
                            duration_ms = float(parts[0])
                            cost_usd = float(parts[1])

                            model_stats[model]['count'] += 1
                            model_stats[model]['total_duration_ms'] += duration_ms
                            model_stats[model]['total_cost'] += cost_usd

            metrics['model_usage'] = dict(model_stats)

            return metrics

        except Exception as e:
            logger.error(f"Failed to get metrics summary: {e}")
            return {
                'error': str(e),
                'agent_utilization': {},
                'cost_per_feature': {},
                'average_retry_count': 0.0,
                'critic_rejection_rate': 0.0,
                'validation_pass_rate': 0.0,
                'time_to_completion': {},
                'model_usage': {}
            }

    def get_historical_trend(
        self,
        metric: str,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Get time-series data for metric over last N days.

        Args:
            metric: Metric name ('cost_per_feature', 'validation_pass_rate', etc.)
            days: Number of days to retrieve (default 7)

        Returns:
            List of data points with date and value:
            [
                {'date': '2025-10-14', 'value': 0.35, ...},
                {'date': '2025-10-15', 'value': 0.42, ...},
                ...
            ]
        """
        try:
            trend_data = []
            current_date = datetime.now()

            for i in range(days - 1, -1, -1):
                date = current_date - timedelta(days=i)
                date_str = date.strftime('%Y-%m-%d')

                # Get metrics for this day (aggregate all hours)
                day_summary = self._get_daily_summary(date_str, metric)
                day_summary['date'] = date_str
                trend_data.append(day_summary)

            return trend_data

        except Exception as e:
            logger.error(f"Failed to get historical trend for {metric}: {e}")
            return []

    def _get_daily_summary(self, date_str: str, metric: str) -> Dict[str, Any]:
        """
        Get daily summary for specific metric.

        Args:
            date_str: Date string in YYYY-MM-DD format
            metric: Metric name

        Returns:
            Dictionary with metric value and metadata
        """
        try:
            # Get all hours for this day
            hours = [f"{date_str}-{h:02d}" for h in range(24)]

            # Calculate metric based on type
            if metric == 'cost_per_feature':
                total_cost = 0.0
                count = 0

                for hour_key in hours:
                    completion_key = f"metrics:feature_completion:{hour_key}"
                    records = self.redis_client.client.zrange(completion_key, 0, -1)

                    for record in records:
                        parts = record.split('|')
                        if len(parts) >= 2:
                            cost = float(parts[1])
                            total_cost += cost
                            count += 1

                avg_cost = total_cost / count if count > 0 else 0.0
                return {
                    'value': avg_cost,
                    'total_cost': total_cost,
                    'count': count
                }

            elif metric == 'validation_pass_rate':
                total = 0
                passed = 0

                for hour_key in hours:
                    validation_key = f"metrics:validation_results:{hour_key}"
                    records = self.redis_client.client.zrange(validation_key, 0, -1)

                    for record in records:
                        parts = record.split('|')
                        if len(parts) >= 2:
                            total += 1
                            if int(parts[1]) == 1:
                                passed += 1

                pass_rate = passed / total if total > 0 else 0.0
                return {
                    'value': pass_rate,
                    'passed': passed,
                    'total': total
                }

            elif metric == 'average_retry_count':
                retries = []

                for hour_key in hours:
                    completion_key = f"metrics:feature_completion:{hour_key}"
                    records = self.redis_client.client.zrange(completion_key, 0, -1)

                    for record in records:
                        parts = record.split('|')
                        if len(parts) >= 4:
                            retries.append(int(parts[3]))

                avg_retries = sum(retries) / len(retries) if retries else 0.0
                return {
                    'value': avg_retries,
                    'count': len(retries)
                }

            elif metric == 'critic_rejection_rate':
                total = 0
                rejected = 0

                for hour_key in hours:
                    critic_key = f"metrics:critic_decisions:{hour_key}"
                    records = self.redis_client.client.zrange(critic_key, 0, -1)

                    for record in records:
                        parts = record.split('|')
                        if len(parts) >= 2:
                            total += 1
                            if parts[1] == 'rejected':
                                rejected += 1

                rejection_rate = rejected / total if total > 0 else 0.0
                return {
                    'value': rejection_rate,
                    'rejected': rejected,
                    'total': total
                }

            else:
                return {'value': 0.0, 'error': f'Unknown metric: {metric}'}

        except Exception as e:
            logger.error(f"Failed to get daily summary for {date_str}, {metric}: {e}")
            return {'value': 0.0, 'error': str(e)}

    def _get_hour_keys_in_window(self, window_hours: int) -> List[str]:
        """
        Get list of hour keys for time window.

        Args:
            window_hours: Number of hours in window

        Returns:
            List of hour keys in YYYY-MM-DD-HH format
        """
        hour_keys = []
        current_time = datetime.now()

        for i in range(window_hours):
            hour = current_time - timedelta(hours=i)
            hour_key = hour.strftime('%Y-%m-%d-%H')
            hour_keys.append(hour_key)

        return hour_keys

    def cleanup_old_metrics(self, days: int = 30):
        """
        Clean up metrics older than specified days.

        Args:
            days: Delete metrics older than this many days

        Returns:
            Number of keys deleted
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            cutoff_hour = cutoff_date.strftime('%Y-%m-%d-%H')

            deleted_count = 0

            # Find all metric keys
            patterns = [
                'metrics:agent_activity:*',
                'metrics:feature_completion:*',
                'metrics:critic_decisions:*',
                'metrics:validation_results:*',
                'metrics:model_usage:*'
            ]

            for pattern in patterns:
                keys = self.redis_client.client.keys(pattern)

                for key in keys:
                    # Extract hour from key
                    try:
                        # Keys are like: metrics:agent_activity:scribe:2025-10-14-15
                        parts = key.split(':')
                        hour_key = parts[-1]

                        if hour_key < cutoff_hour:
                            self.redis_client.client.delete(key)
                            deleted_count += 1
                    except (IndexError, ValueError):
                        continue

            logger.info(f"Cleaned up {deleted_count} old metric keys (older than {days} days)")
            return deleted_count

        except Exception as e:
            logger.error(f"Failed to cleanup old metrics: {e}")
            return 0


# Global aggregator instance
_global_aggregator: Optional[MetricsAggregator] = None
_aggregator_lock = threading.Lock()


def get_metrics_aggregator(redis_client: Optional[RedisClient] = None) -> MetricsAggregator:
    """
    Get or create the global metrics aggregator instance.

    Args:
        redis_client: Optional Redis client

    Returns:
        Global MetricsAggregator instance
    """
    global _global_aggregator

    if _global_aggregator is None:
        with _aggregator_lock:
            if _global_aggregator is None:
                _global_aggregator = MetricsAggregator(redis_client=redis_client)

    return _global_aggregator


# Example usage
if __name__ == '__main__':
    import json

    print("Metrics Aggregation System Demo\n")

    # Create aggregator
    aggregator = MetricsAggregator()

    print("Recording sample metrics...\n")

    # Record agent activities
    aggregator.record_agent_activity('scribe', duration_ms=2500, cost_usd=0.12, model='sonnet-4.5')
    aggregator.record_agent_activity('runner', duration_ms=800, cost_usd=0.02, model='haiku')
    aggregator.record_agent_activity('critic', duration_ms=500, cost_usd=0.01, model='haiku')
    aggregator.record_agent_activity('gemini', duration_ms=5000, cost_usd=0.08, model='gemini-2.5-pro')

    # Record feature completions
    aggregator.record_feature_completion(
        feature='user_authentication',
        total_cost=0.35,
        duration_ms=15000,
        retry_count=1
    )

    aggregator.record_feature_completion(
        feature='checkout_flow',
        total_cost=0.42,
        duration_ms=18000,
        retry_count=2
    )

    # Record critic decisions
    aggregator.record_critic_decision('test_001', 'approved')
    aggregator.record_critic_decision('test_002', 'rejected', reason='uses nth() selectors')
    aggregator.record_critic_decision('test_003', 'approved')

    # Record validation results
    aggregator.record_validation_result('test_001', passed=True, duration_ms=5000, cost_usd=0.08)
    aggregator.record_validation_result('test_003', passed=True, duration_ms=4500, cost_usd=0.07)

    # Get metrics summary
    print("=" * 60)
    print("METRICS SUMMARY (Last 1 Hour)")
    print("=" * 60)
    summary = aggregator.get_metrics_summary(window_hours=1)
    print(json.dumps(summary, indent=2))

    # Get historical trend
    print("\n" + "=" * 60)
    print("HISTORICAL TREND - Cost Per Feature (Last 7 Days)")
    print("=" * 60)
    trend = aggregator.get_historical_trend('cost_per_feature', days=7)
    for data_point in trend:
        print(f"  {data_point['date']}: ${data_point.get('value', 0):.4f} (count: {data_point.get('count', 0)})")
