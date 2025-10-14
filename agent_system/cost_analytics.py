"""
Cost Analytics and Budget Alerting System for SuperAgent

Tracks costs per agent, model, and feature. Enforces budget limits from router_policy.yaml.
Emits budget_warning (80% threshold) and budget_exceeded (100% threshold) events.

Usage:
    from agent_system.cost_analytics import CostTracker, get_cost_tracker

    # Record cost for an agent task
    tracker = get_cost_tracker()
    tracker.record_cost(
        agent='scribe',
        model='claude-sonnet-4.5',
        cost_usd=0.12,
        feature='user_authentication',
        task_id='t_123'
    )

    # Check if budget allows new spend
    can_proceed = tracker.check_budget_available(estimated_cost=0.25)

    # Generate cost reports
    daily_report = tracker.get_daily_report()
    agent_report = tracker.get_cost_by_agent()
"""
import os
import yaml
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict, field
from collections import defaultdict

from agent_system.state.redis_client import RedisClient
from agent_system.observability.event_stream import emit_event


@dataclass
class CostEntry:
    """Single cost entry for tracking."""
    timestamp: float
    agent: str
    model: str
    cost_usd: float
    feature: Optional[str] = None
    task_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class BudgetConfig:
    """Budget configuration from router_policy.yaml."""
    daily_budget_usd: float = 50.00
    per_session_budget_usd: float = 5.00
    soft_limit_warning: float = 0.80  # 80%
    hard_limit_stop: float = 1.00  # 100%

    @property
    def daily_soft_threshold(self) -> float:
        """Get daily soft warning threshold."""
        return self.daily_budget_usd * self.soft_limit_warning

    @property
    def daily_hard_threshold(self) -> float:
        """Get daily hard stop threshold."""
        return self.daily_budget_usd * self.hard_limit_stop

    @property
    def session_soft_threshold(self) -> float:
        """Get session soft warning threshold."""
        return self.per_session_budget_usd * self.soft_limit_warning

    @property
    def session_hard_threshold(self) -> float:
        """Get session hard stop threshold."""
        return self.per_session_budget_usd * self.hard_limit_stop


class CostTracker:
    """
    Tracks costs per agent, model, and feature with budget enforcement.

    Features:
    - Track costs by agent, model, feature
    - Daily/weekly aggregation with Redis storage
    - Budget enforcement with soft warning (80%) and hard stop (100%)
    - Automatic daily reset
    - Cost report generation
    - Integration with observability event system

    Redis Keys:
    - cost:daily:{date} -> daily cost data
    - cost:weekly:{week} -> weekly cost data
    - cost:session:{session_id} -> session cost data
    - cost:entries:{date} -> list of cost entries
    - cost:last_reset -> timestamp of last daily reset
    """

    def __init__(
        self,
        redis_client: Optional[RedisClient] = None,
        config_path: Optional[str] = None,
        session_id: Optional[str] = None
    ):
        """
        Initialize cost tracker.

        Args:
            redis_client: Redis client for storage (creates new if None)
            config_path: Path to router_policy.yaml (defaults to .claude/router_policy.yaml)
            session_id: Session identifier for session-level tracking
        """
        self.redis_client = redis_client or RedisClient()
        self.session_id = session_id or f"session_{int(time.time())}"

        # Load budget config
        if config_path is None:
            config_path = Path(__file__).parent.parent / '.claude' / 'router_policy.yaml'
        self.budget_config = self._load_budget_config(config_path)

        # In-memory cache for current day
        self._daily_cache: List[CostEntry] = []
        self._cache_lock = threading.Lock()

        # Warning flags to prevent duplicate events
        self._daily_warning_emitted = False
        self._daily_exceeded_emitted = False
        self._session_warning_emitted = False
        self._session_exceeded_emitted = False

        # Check for daily reset on initialization
        self._maybe_reset_daily()

    def _load_budget_config(self, config_path: Path) -> BudgetConfig:
        """
        Load budget configuration from router_policy.yaml.

        Args:
            config_path: Path to router_policy.yaml

        Returns:
            BudgetConfig instance
        """
        try:
            with open(config_path, 'r') as f:
                policy = yaml.safe_load(f)

            budget_enforcement = policy.get('budget_enforcement', {})
            return BudgetConfig(
                daily_budget_usd=budget_enforcement.get('daily_budget_usd', 50.00),
                per_session_budget_usd=budget_enforcement.get('per_session_budget_usd', 5.00),
                soft_limit_warning=budget_enforcement.get('soft_limit_warning', 0.80),
                hard_limit_stop=budget_enforcement.get('hard_limit_stop', 1.00)
            )
        except Exception as e:
            print(f"Warning: Failed to load budget config from {config_path}: {e}")
            print("Using default budget configuration")
            return BudgetConfig()

    def _get_date_key(self, timestamp: Optional[float] = None) -> str:
        """
        Get date key for Redis storage.

        Args:
            timestamp: Unix timestamp (uses current time if None)

        Returns:
            Date string in YYYY-MM-DD format
        """
        dt = datetime.fromtimestamp(timestamp or time.time())
        return dt.strftime('%Y-%m-%d')

    def _get_week_key(self, timestamp: Optional[float] = None) -> str:
        """
        Get week key for Redis storage.

        Args:
            timestamp: Unix timestamp (uses current time if None)

        Returns:
            Week string in YYYY-WXX format
        """
        dt = datetime.fromtimestamp(timestamp or time.time())
        year, week, _ = dt.isocalendar()
        return f"{year}-W{week:02d}"

    def _maybe_reset_daily(self):
        """Check if we need to reset daily counters (new day started)."""
        last_reset_key = "cost:last_reset"
        last_reset = self.redis_client.get(last_reset_key)

        current_date = self._get_date_key()

        if last_reset:
            last_reset_date = self._get_date_key(float(last_reset))
            if last_reset_date != current_date:
                # New day started - reset warning flags
                self._daily_warning_emitted = False
                self._daily_exceeded_emitted = False
                self._daily_cache.clear()
                self.redis_client.set(last_reset_key, time.time())
        else:
            # First run - set last reset
            self.redis_client.set(last_reset_key, time.time())

    def record_cost(
        self,
        agent: str,
        model: str,
        cost_usd: float,
        feature: Optional[str] = None,
        task_id: Optional[str] = None,
        timestamp: Optional[float] = None
    ) -> bool:
        """
        Record a cost entry.

        Args:
            agent: Agent name (scribe, runner, medic, critic, gemini, kaya)
            model: Model name (haiku, sonnet, 2.5_pro)
            cost_usd: Cost in USD
            feature: Optional feature name
            task_id: Optional task identifier
            timestamp: Optional timestamp (uses current time if None)

        Returns:
            True if recorded successfully
        """
        timestamp = timestamp or time.time()

        # Create cost entry
        entry = CostEntry(
            timestamp=timestamp,
            agent=agent,
            model=model,
            cost_usd=cost_usd,
            feature=feature,
            task_id=task_id
        )

        # Add to in-memory cache
        with self._cache_lock:
            self._daily_cache.append(entry)

        # Store in Redis
        date_key = self._get_date_key(timestamp)
        week_key = self._get_week_key(timestamp)

        # Add to daily entries list
        entries_key = f"cost:entries:{date_key}"
        self.redis_client.client.rpush(entries_key, str(entry.to_dict()))
        self.redis_client.client.expire(entries_key, 30 * 24 * 3600)  # Keep for 30 days

        # Update daily aggregate
        daily_key = f"cost:daily:{date_key}"
        self._increment_aggregate(daily_key, entry, ttl=30 * 24 * 3600)

        # Update weekly aggregate
        weekly_key = f"cost:weekly:{week_key}"
        self._increment_aggregate(weekly_key, entry, ttl=90 * 24 * 3600)

        # Update session aggregate
        session_key = f"cost:session:{self.session_id}"
        self._increment_aggregate(session_key, entry, ttl=3600)  # 1 hour TTL

        # Check budget and emit events if needed
        self._check_and_emit_budget_events()

        return True

    def _increment_aggregate(self, key: str, entry: CostEntry, ttl: int):
        """
        Increment aggregate counters in Redis.

        Args:
            key: Redis key
            entry: Cost entry
            ttl: Time to live in seconds
        """
        # Get existing aggregate or create new
        aggregate = self.redis_client.get(key) or {
            'total_cost': 0.0,
            'by_agent': {},
            'by_model': {},
            'by_feature': {},
            'count': 0
        }

        # Update totals
        aggregate['total_cost'] += entry.cost_usd
        aggregate['count'] += 1

        # Update by_agent
        if entry.agent not in aggregate['by_agent']:
            aggregate['by_agent'][entry.agent] = 0.0
        aggregate['by_agent'][entry.agent] += entry.cost_usd

        # Update by_model
        if entry.model not in aggregate['by_model']:
            aggregate['by_model'][entry.model] = 0.0
        aggregate['by_model'][entry.model] += entry.cost_usd

        # Update by_feature (if provided)
        if entry.feature:
            if 'by_feature' not in aggregate:
                aggregate['by_feature'] = {}
            if entry.feature not in aggregate['by_feature']:
                aggregate['by_feature'][entry.feature] = 0.0
            aggregate['by_feature'][entry.feature] += entry.cost_usd

        # Store back to Redis
        self.redis_client.set(key, aggregate, ttl=ttl)

    def _check_and_emit_budget_events(self):
        """Check budget thresholds and emit warning/exceeded events."""
        # Get current spend
        daily_spend = self.get_daily_spend()
        session_spend = self.get_session_spend()

        # Check daily budget
        if daily_spend >= self.budget_config.daily_hard_threshold:
            if not self._daily_exceeded_emitted:
                emit_event('budget_exceeded', {
                    'budget_type': 'daily',
                    'current_spend': daily_spend,
                    'limit': self.budget_config.daily_budget_usd,
                    'threshold': 'hard_stop',
                    'percent_used': (daily_spend / self.budget_config.daily_budget_usd) * 100,
                    'timestamp': time.time()
                })
                self._daily_exceeded_emitted = True
        elif daily_spend >= self.budget_config.daily_soft_threshold:
            if not self._daily_warning_emitted:
                emit_event('budget_warning', {
                    'budget_type': 'daily',
                    'current_spend': daily_spend,
                    'limit': self.budget_config.daily_budget_usd,
                    'remaining': self.budget_config.daily_budget_usd - daily_spend,
                    'threshold': 'soft_warning',
                    'percent_used': (daily_spend / self.budget_config.daily_budget_usd) * 100,
                    'timestamp': time.time()
                })
                self._daily_warning_emitted = True

        # Check session budget
        if session_spend >= self.budget_config.session_hard_threshold:
            if not self._session_exceeded_emitted:
                emit_event('budget_exceeded', {
                    'budget_type': 'session',
                    'session_id': self.session_id,
                    'current_spend': session_spend,
                    'limit': self.budget_config.per_session_budget_usd,
                    'threshold': 'hard_stop',
                    'percent_used': (session_spend / self.budget_config.per_session_budget_usd) * 100,
                    'timestamp': time.time()
                })
                self._session_exceeded_emitted = True
        elif session_spend >= self.budget_config.session_soft_threshold:
            if not self._session_warning_emitted:
                emit_event('budget_warning', {
                    'budget_type': 'session',
                    'session_id': self.session_id,
                    'current_spend': session_spend,
                    'limit': self.budget_config.per_session_budget_usd,
                    'remaining': self.budget_config.per_session_budget_usd - session_spend,
                    'threshold': 'soft_warning',
                    'percent_used': (session_spend / self.budget_config.per_session_budget_usd) * 100,
                    'timestamp': time.time()
                })
                self._session_warning_emitted = True

    def check_budget_available(
        self,
        estimated_cost: float,
        budget_type: str = 'daily'
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if budget allows for estimated cost.

        Args:
            estimated_cost: Estimated cost in USD
            budget_type: 'daily' or 'session'

        Returns:
            Tuple of (can_proceed: bool, reason: Optional[str])
        """
        if budget_type == 'daily':
            current_spend = self.get_daily_spend()
            budget = self.budget_config.daily_budget_usd
            hard_threshold = self.budget_config.daily_hard_threshold
        else:  # session
            current_spend = self.get_session_spend()
            budget = self.budget_config.per_session_budget_usd
            hard_threshold = self.budget_config.session_hard_threshold

        projected_spend = current_spend + estimated_cost

        if projected_spend > hard_threshold:
            reason = (
                f"{budget_type.capitalize()} budget exceeded: "
                f"${projected_spend:.2f} > ${hard_threshold:.2f} "
                f"(${current_spend:.2f} + ${estimated_cost:.2f})"
            )
            return False, reason

        return True, None

    def get_daily_spend(self, date: Optional[str] = None) -> float:
        """
        Get total daily spend.

        Args:
            date: Date string in YYYY-MM-DD format (uses today if None)

        Returns:
            Total spend in USD
        """
        date_key = date or self._get_date_key()
        daily_key = f"cost:daily:{date_key}"
        aggregate = self.redis_client.get(daily_key)

        if aggregate:
            return aggregate.get('total_cost', 0.0)
        return 0.0

    def get_weekly_spend(self, week: Optional[str] = None) -> float:
        """
        Get total weekly spend.

        Args:
            week: Week string in YYYY-WXX format (uses current week if None)

        Returns:
            Total spend in USD
        """
        week_key = week or self._get_week_key()
        weekly_key = f"cost:weekly:{week_key}"
        aggregate = self.redis_client.get(weekly_key)

        if aggregate:
            return aggregate.get('total_cost', 0.0)
        return 0.0

    def get_session_spend(self, session_id: Optional[str] = None) -> float:
        """
        Get total session spend.

        Args:
            session_id: Session identifier (uses current session if None)

        Returns:
            Total spend in USD
        """
        sid = session_id or self.session_id
        session_key = f"cost:session:{sid}"
        aggregate = self.redis_client.get(session_key)

        if aggregate:
            return aggregate.get('total_cost', 0.0)
        return 0.0

    def get_daily_report(self, date: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate daily cost report.

        Args:
            date: Date string in YYYY-MM-DD format (uses today if None)

        Returns:
            Dict with daily cost breakdown
        """
        date_key = date or self._get_date_key()
        daily_key = f"cost:daily:{date_key}"
        aggregate = self.redis_client.get(daily_key) or {
            'total_cost': 0.0,
            'by_agent': {},
            'by_model': {},
            'by_feature': {},
            'count': 0
        }

        # Calculate budget status
        total = aggregate['total_cost']
        budget = self.budget_config.daily_budget_usd
        percent_used = (total / budget * 100) if budget > 0 else 0
        remaining = budget - total

        return {
            'date': date_key,
            'total_cost_usd': total,
            'budget_usd': budget,
            'remaining_usd': remaining,
            'percent_used': percent_used,
            'by_agent': aggregate.get('by_agent', {}),
            'by_model': aggregate.get('by_model', {}),
            'by_feature': aggregate.get('by_feature', {}),
            'entry_count': aggregate.get('count', 0)
        }

    def get_weekly_report(self, week: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate weekly cost report.

        Args:
            week: Week string in YYYY-WXX format (uses current week if None)

        Returns:
            Dict with weekly cost breakdown
        """
        week_key = week or self._get_week_key()
        weekly_key = f"cost:weekly:{week_key}"
        aggregate = self.redis_client.get(weekly_key) or {
            'total_cost': 0.0,
            'by_agent': {},
            'by_model': {},
            'by_feature': {},
            'count': 0
        }

        return {
            'week': week_key,
            'total_cost_usd': aggregate['total_cost'],
            'by_agent': aggregate.get('by_agent', {}),
            'by_model': aggregate.get('by_model', {}),
            'by_feature': aggregate.get('by_feature', {}),
            'entry_count': aggregate.get('count', 0)
        }

    def get_cost_by_agent(self, date: Optional[str] = None) -> Dict[str, float]:
        """
        Get cost breakdown by agent.

        Args:
            date: Date string in YYYY-MM-DD format (uses today if None)

        Returns:
            Dict of agent name -> cost in USD
        """
        report = self.get_daily_report(date)
        return report['by_agent']

    def get_cost_by_model(self, date: Optional[str] = None) -> Dict[str, float]:
        """
        Get cost breakdown by model.

        Args:
            date: Date string in YYYY-MM-DD format (uses today if None)

        Returns:
            Dict of model name -> cost in USD
        """
        report = self.get_daily_report(date)
        return report['by_model']

    def get_cost_by_feature(self, date: Optional[str] = None) -> Dict[str, float]:
        """
        Get cost breakdown by feature.

        Args:
            date: Date string in YYYY-MM-DD format (uses today if None)

        Returns:
            Dict of feature name -> cost in USD
        """
        report = self.get_daily_report(date)
        return report['by_feature']

    def get_budget_status(self) -> Dict[str, Any]:
        """
        Get current budget status for daily and session budgets.

        Returns:
            Dict with budget status information
        """
        daily_spend = self.get_daily_spend()
        session_spend = self.get_session_spend()

        return {
            'daily': {
                'current_spend_usd': daily_spend,
                'budget_usd': self.budget_config.daily_budget_usd,
                'remaining_usd': self.budget_config.daily_budget_usd - daily_spend,
                'percent_used': (daily_spend / self.budget_config.daily_budget_usd * 100)
                    if self.budget_config.daily_budget_usd > 0 else 0,
                'status': self._get_budget_status_label(
                    daily_spend,
                    self.budget_config.daily_soft_threshold,
                    self.budget_config.daily_hard_threshold
                )
            },
            'session': {
                'session_id': self.session_id,
                'current_spend_usd': session_spend,
                'budget_usd': self.budget_config.per_session_budget_usd,
                'remaining_usd': self.budget_config.per_session_budget_usd - session_spend,
                'percent_used': (session_spend / self.budget_config.per_session_budget_usd * 100)
                    if self.budget_config.per_session_budget_usd > 0 else 0,
                'status': self._get_budget_status_label(
                    session_spend,
                    self.budget_config.session_soft_threshold,
                    self.budget_config.session_hard_threshold
                )
            }
        }

    def _get_budget_status_label(
        self,
        current: float,
        soft_threshold: float,
        hard_threshold: float
    ) -> str:
        """
        Get budget status label.

        Args:
            current: Current spend
            soft_threshold: Soft warning threshold
            hard_threshold: Hard stop threshold

        Returns:
            Status label: 'ok', 'warning', or 'exceeded'
        """
        if current >= hard_threshold:
            return 'exceeded'
        elif current >= soft_threshold:
            return 'warning'
        else:
            return 'ok'

    def get_historical_trend(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        Get historical cost trend for last N days.

        Args:
            days: Number of days to retrieve (default 7)

        Returns:
            List of daily reports sorted by date (oldest first)
        """
        trend = []
        current_date = datetime.now()

        for i in range(days - 1, -1, -1):
            date = current_date - timedelta(days=i)
            date_key = date.strftime('%Y-%m-%d')
            report = self.get_daily_report(date_key)
            report['date'] = date_key
            trend.append(report)

        return trend


# Global tracker instance
_global_tracker: Optional[CostTracker] = None
_tracker_lock = threading.Lock()


def get_cost_tracker(
    redis_client: Optional[RedisClient] = None,
    session_id: Optional[str] = None
) -> CostTracker:
    """
    Get or create the global cost tracker instance.

    Args:
        redis_client: Optional Redis client
        session_id: Optional session identifier

    Returns:
        Global CostTracker instance
    """
    global _global_tracker

    if _global_tracker is None:
        with _tracker_lock:
            if _global_tracker is None:
                _global_tracker = CostTracker(
                    redis_client=redis_client,
                    session_id=session_id
                )

    return _global_tracker


def record_agent_cost(
    agent: str,
    model: str,
    cost_usd: float,
    feature: Optional[str] = None,
    task_id: Optional[str] = None
) -> bool:
    """
    Convenience function to record cost using global tracker.

    Args:
        agent: Agent name
        model: Model name
        cost_usd: Cost in USD
        feature: Optional feature name
        task_id: Optional task identifier

    Returns:
        True if recorded successfully
    """
    tracker = get_cost_tracker()
    return tracker.record_cost(agent, model, cost_usd, feature, task_id)


# Example usage
if __name__ == '__main__':
    import json

    print("Cost Analytics System Demo\n")

    # Create tracker
    tracker = CostTracker()

    print("Recording some example costs...\n")

    # Record some costs
    tracker.record_cost('scribe', 'claude-sonnet-4.5', 0.12, feature='user_authentication', task_id='t_001')
    tracker.record_cost('runner', 'claude-haiku', 0.02, feature='user_authentication', task_id='t_001')
    tracker.record_cost('critic', 'claude-haiku', 0.01, feature='user_authentication', task_id='t_001')
    tracker.record_cost('gemini', 'gemini-2.5-pro', 0.08, feature='user_authentication', task_id='t_001')
    tracker.record_cost('scribe', 'claude-sonnet-4.5', 0.15, feature='checkout_flow', task_id='t_002')
    tracker.record_cost('runner', 'claude-haiku', 0.02, feature='checkout_flow', task_id='t_002')

    # Print daily report
    print("=" * 60)
    print("DAILY COST REPORT")
    print("=" * 60)
    report = tracker.get_daily_report()
    print(json.dumps(report, indent=2))

    # Print budget status
    print("\n" + "=" * 60)
    print("BUDGET STATUS")
    print("=" * 60)
    status = tracker.get_budget_status()
    print(json.dumps(status, indent=2))

    # Print by agent
    print("\n" + "=" * 60)
    print("COST BY AGENT")
    print("=" * 60)
    by_agent = tracker.get_cost_by_agent()
    for agent, cost in sorted(by_agent.items(), key=lambda x: x[1], reverse=True):
        print(f"  {agent:20s} ${cost:.4f}")

    # Print by model
    print("\n" + "=" * 60)
    print("COST BY MODEL")
    print("=" * 60)
    by_model = tracker.get_cost_by_model()
    for model, cost in sorted(by_model.items(), key=lambda x: x[1], reverse=True):
        print(f"  {model:20s} ${cost:.4f}")

    # Print by feature
    print("\n" + "=" * 60)
    print("COST BY FEATURE")
    print("=" * 60)
    by_feature = tracker.get_cost_by_feature()
    for feature, cost in sorted(by_feature.items(), key=lambda x: x[1], reverse=True):
        print(f"  {feature:30s} ${cost:.4f}")

    # Check if we can spend more
    print("\n" + "=" * 60)
    print("BUDGET CHECKS")
    print("=" * 60)
    can_proceed, reason = tracker.check_budget_available(0.50)
    print(f"Can spend $0.50? {can_proceed}")
    if reason:
        print(f"Reason: {reason}")
