# Cost Analytics - Quick Reference Guide

## Overview

SuperAgent's cost analytics system tracks spending per agent, model, and feature with automated budget enforcement at 80% (warning) and 100% (hard stop).

## Quick Start

### Record a Cost

```python
from agent_system.cost_analytics import record_agent_cost

# Record cost for an operation
record_agent_cost(
    agent='scribe',
    model='claude-sonnet-4.5',
    cost_usd=0.12,
    feature='user_authentication',
    task_id='t_123'
)
```

### Check Budget Before Operation

```python
from agent_system.cost_analytics import get_cost_tracker

tracker = get_cost_tracker()

# Check if budget allows $0.50 spend
can_proceed, reason = tracker.check_budget_available(0.50, budget_type='daily')

if can_proceed:
    # Proceed with operation
    expensive_operation()
else:
    print(f"Budget exceeded: {reason}")
```

### Get Budget Status

```python
tracker = get_cost_tracker()
status = tracker.get_budget_status()

print(f"Daily budget: {status['daily']['status']}")  # 'ok', 'warning', or 'exceeded'
print(f"Used: {status['daily']['percent_used']:.1f}%")
```

## CLI Commands

```bash
# Daily report
python agent_system/cli.py cost daily

# Weekly report
python agent_system/cli.py cost weekly

# Budget status
python agent_system/cli.py cost budget

# Cost by agent
python agent_system/cli.py cost by-agent

# Cost by model
python agent_system/cli.py cost by-model

# Cost by feature
python agent_system/cli.py cost by-feature

# 7-day trend
python agent_system/cli.py cost trend --days 7
```

## Configuration

Edit `.claude/router_policy.yaml`:

```yaml
budget_enforcement:
  soft_limit_warning: 0.80      # Warn at 80%
  hard_limit_stop: 1.00         # Stop at 100%
  daily_budget_usd: 50.00       # $50/day
  per_session_budget_usd: 5.00  # $5/session
```

## Budget Thresholds

| Status | Daily ($50) | Session ($5) | Event |
|--------|-------------|--------------|-------|
| OK | $0 - $39.99 | $0 - $3.99 | None |
| Warning | $40 - $49.99 | $4 - $4.99 | `budget_warning` |
| Exceeded | $50+ | $5+ | `budget_exceeded` |

## API Reference

### CostTracker Methods

```python
tracker = get_cost_tracker()

# Recording
tracker.record_cost(agent, model, cost_usd, feature=None, task_id=None)

# Budget checks
can_proceed, reason = tracker.check_budget_available(estimated_cost, budget_type='daily')

# Current spend
daily_spend = tracker.get_daily_spend()
weekly_spend = tracker.get_weekly_spend()
session_spend = tracker.get_session_spend()

# Reports
daily_report = tracker.get_daily_report()
weekly_report = tracker.get_weekly_report()
budget_status = tracker.get_budget_status()

# Breakdowns
by_agent = tracker.get_cost_by_agent()
by_model = tracker.get_cost_by_model()
by_feature = tracker.get_cost_by_feature()

# Trends
trend = tracker.get_historical_trend(days=7)
```

## Redis Keys

- `cost:daily:{YYYY-MM-DD}` - Daily aggregates (30-day TTL)
- `cost:weekly:{YYYY-WXX}` - Weekly aggregates (90-day TTL)
- `cost:session:{session_id}` - Session aggregates (1-hour TTL)
- `cost:entries:{YYYY-MM-DD}` - Raw cost entries (30-day TTL)
- `cost:last_reset` - Daily reset timestamp

## Events

### budget_warning (80% threshold)

```json
{
  "event_type": "budget_warning",
  "payload": {
    "budget_type": "daily",
    "current_spend": 40.00,
    "limit": 50.00,
    "remaining": 10.00,
    "threshold": "soft_warning",
    "percent_used": 80.0
  }
}
```

### budget_exceeded (100% threshold)

```json
{
  "event_type": "budget_exceeded",
  "payload": {
    "budget_type": "daily",
    "current_spend": 50.00,
    "limit": 50.00,
    "threshold": "hard_stop",
    "percent_used": 100.0
  }
}
```

## Testing

```bash
# Run all tests
pytest tests/unit/test_cost_analytics.py -v

# Run specific test class
pytest tests/unit/test_cost_analytics.py::TestCostTracker -v

# Run with coverage
pytest tests/unit/test_cost_analytics.py --cov=agent_system.cost_analytics
```

## Integration Examples

### In Agent Code

```python
from agent_system.cost_analytics import record_agent_cost

class ScribeAgent:
    def write_test(self, feature: str, task_id: str):
        # Check budget first
        tracker = get_cost_tracker()
        can_proceed, reason = tracker.check_budget_available(0.15)

        if not can_proceed:
            raise BudgetExceededError(reason)

        # Do work
        result = self._write_test_code(feature)

        # Record actual cost
        record_agent_cost(
            agent='scribe',
            model='claude-sonnet-4.5',
            cost_usd=0.12,
            feature=feature,
            task_id=task_id
        )

        return result
```

### In Router

```python
from agent_system.cost_analytics import get_cost_tracker
from agent_system.router import Router

router = Router()
tracker = get_cost_tracker()

# Get routing decision
decision = router.route('write_test', description='user login', scope='happy path')

# Check budget before routing
can_proceed, reason = tracker.check_budget_available(
    estimated_cost=decision.max_cost_usd,
    budget_type='daily'
)

if not can_proceed:
    # Handle budget exceeded
    escalate_to_hitl(reason)
else:
    # Proceed with agent
    execute_agent(decision.agent, decision.model)
```

## Troubleshooting

### Budget not resetting daily

Check `cost:last_reset` key in Redis:

```python
from agent_system.state.redis_client import RedisClient
redis = RedisClient()
last_reset = redis.get('cost:last_reset')
print(f"Last reset: {last_reset}")
```

### Events not emitting

Verify observability system is running:

```python
from agent_system.observability.event_stream import get_emitter
emitter = get_emitter()
print(f"Emitter running: {emitter._running}")
```

### Redis connection issues

Check Redis health:

```python
from agent_system.state.redis_client import RedisClient
redis = RedisClient()
print(f"Redis healthy: {redis.health_check()}")
```

## Performance Notes

- **In-memory cache**: O(1) cost recording
- **Redis operations**: O(1) get/set
- **Report generation**: O(1) single-day, O(n) for trends
- **Memory**: ~1KB per cost entry
- **Storage**: ~10KB per day in Redis

## Daily Reset

The system automatically resets daily counters at midnight (based on server timezone):

1. First operation of new day triggers reset check
2. `cost:last_reset` timestamp compared to current date
3. If new day detected:
   - Warning/exceeded flags reset
   - In-memory cache cleared
   - Historical data preserved in Redis

## Cost Breakdown Example

```
DAILY COST REPORT
=================
Date: 2025-10-14
Total: $0.98
Budget: $50.00 (1.96% used)
Status: OK

By Agent:
  scribe    $0.69 (70%)
  gemini    $0.16 (16%)
  runner    $0.10 (10%)
  critic    $0.03 (4%)

By Model:
  claude-sonnet-4.5    $0.69 (70%)
  gemini-2.5-pro       $0.16 (16%)
  claude-haiku         $0.13 (14%)

By Feature:
  user_authentication  $0.46 (47%)
  checkout_flow        $0.34 (35%)
  user_login           $0.18 (18%)
```

## See Also

- [COST_ANALYTICS_IMPLEMENTATION.md](COST_ANALYTICS_IMPLEMENTATION.md) - Full implementation details
- [.claude/router_policy.yaml](.claude/router_policy.yaml) - Budget configuration
- [.claude/observability.yaml](.claude/observability.yaml) - Event definitions
- [tests/unit/test_cost_analytics.py](tests/unit/test_cost_analytics.py) - Test examples
