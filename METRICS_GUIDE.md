# Metrics Aggregation System Guide

## Overview

The SuperAgent metrics aggregation system tracks performance metrics across all agents to measure system health, optimize costs, and monitor quality. All metrics are stored in Redis using sorted sets for efficient time-series operations with 30-day retention.

## Architecture

### Components

- **MetricsAggregator** (`agent_system/metrics_aggregator.py`): Core aggregation engine with Redis backend
- **Kaya Integration**: Automatic metrics recording during pipeline execution
- **CLI Interface**: Command-line tools for viewing metrics
- **Observability Dashboard**: Real-time metrics streaming via WebSocket

### Redis Storage Pattern

Metrics are stored in Redis sorted sets with the following key structure:

```
metrics:agent_activity:{agent}:{YYYY-MM-DD-HH} -> sorted set (timestamp -> duration_ms|cost|task_id)
metrics:feature_completion:{YYYY-MM-DD-HH} -> sorted set (timestamp -> feature|cost|duration|retries)
metrics:critic_decisions:{YYYY-MM-DD-HH} -> sorted set (timestamp -> test_id|decision|reason)
metrics:validation_results:{YYYY-MM-DD-HH} -> sorted set (timestamp -> test_id|passed|duration|cost)
metrics:model_usage:{model}:{YYYY-MM-DD-HH} -> sorted set (timestamp -> duration_ms|cost|agent)
```

All keys have a 30-day TTL for automatic cleanup.

## Tracked Metrics

### 1. Agent Utilization

Measures how much time each agent spends active vs idle.

**Calculation**: `(active_time_ms / window_time_ms) * 100`

**CLI Usage**:
```bash
python agent_system/cli.py metrics agent-utilization --window 1
python agent_system/cli.py metrics agent-utilization --window 24
```

**Example Output**:
```
Agent Utilization (Last 1 Hour)
  scribe               15.50% (active: 558.0s, cost: $0.3500)
  runner                8.20% (active: 295.2s, cost: $0.0800)
  critic                3.10% (active: 111.6s, cost: $0.0300)
  gemini               25.00% (active: 900.0s, cost: $0.2400)
```

### 2. Cost Per Feature

Total cost for each completed feature (end-to-end pipeline).

**CLI Usage**:
```bash
python agent_system/cli.py metrics cost-per-feature --window 1
python agent_system/cli.py metrics cost-per-feature --window 24
```

**Example Output**:
```
Cost Per Feature (Last 1 Hour)
  user_authentication
    Average Cost:   $0.3500
    Total Cost:     $1.0500
    Count:          3

  checkout_flow
    Average Cost:   $0.4200
    Total Cost:     $0.8400
    Count:          2
```

### 3. Average Retry Count

Mean number of retries before success (includes Medic fixes).

**CLI Usage**:
```bash
python agent_system/cli.py metrics retry-count --window 1
```

**Example Output**:
```
Average Retry Count (Last 1 Hour)
  Average Retries: 1.25
```

**Target**: ≤ 1.5 retries per feature (per CLAUDE.md KPIs)

### 4. Critic Rejection Rate

Percentage of tests rejected by Critic pre-validation.

**CLI Usage**:
```bash
python agent_system/cli.py metrics rejection-rate --window 1
```

**Example Output**:
```
Critic Rejection Rate (Last 1 Hour)
  Rejection Rate: 22.5%
```

**Target**: 15-30% rejection rate (per CLAUDE.md KPIs)

### 5. Validation Pass Rate

Percentage of tests passing Gemini validation in real browser.

**CLI Usage**:
```bash
python agent_system/cli.py metrics validation-rate --window 1
```

**Example Output**:
```
Validation Pass Rate (Last 1 Hour)
  Pass Rate: 87.5%
```

**Target**: ≥ 95% pass rate (flake-adjusted, per CLAUDE.md KPIs)

### 6. Time to Completion

End-to-end time from task queue to feature completion.

**CLI Usage**:
```bash
python agent_system/cli.py metrics summary --window 1
```

**Target**: < 10 minutes per feature (per CLAUDE.md KPIs)

### 7. Model Usage

Haiku vs Sonnet usage ratio for cost optimization.

**CLI Usage**:
```bash
python agent_system/cli.py metrics model-usage --window 1
python agent_system/cli.py metrics model-usage --window 24
```

**Example Output**:
```
Model Usage (Last 1 Hour)
  haiku
    Count:          45
    Total Duration: 1250.0s
    Total Cost:     $0.1200

  sonnet-4.5
    Count:          12
    Total Duration: 980.0s
    Total Cost:     $0.3500

  gemini-2.5-pro
    Count:          8
    Total Duration: 720.0s
    Total Cost:     $0.2400
```

**Target**: 70% Haiku usage (per CLAUDE.md cost optimization)

## CLI Commands

### Full Summary

```bash
python agent_system/cli.py metrics summary --window 1
```

Shows all metrics in one view:
- Agent utilization (all agents)
- Cost per feature (all features)
- Retry & rejection metrics
- Model usage statistics

### Individual Metrics

```bash
# Agent utilization
python agent_system/cli.py metrics agent-utilization --window 1

# Cost per feature
python agent_system/cli.py metrics cost-per-feature --window 1

# Rejection rate
python agent_system/cli.py metrics rejection-rate --window 1

# Validation pass rate
python agent_system/cli.py metrics validation-rate --window 1

# Average retry count
python agent_system/cli.py metrics retry-count --window 1

# Model usage
python agent_system/cli.py metrics model-usage --window 1
```

### Historical Trends

```bash
# 7-day trend (default)
python agent_system/cli.py metrics trend --days 7

# 30-day trend
python agent_system/cli.py metrics trend --days 30
```

### Time Windows

All metrics support custom time windows:

```bash
# Last 1 hour (default)
--window 1

# Last 6 hours
--window 6

# Last 24 hours
--window 24

# Last 7 days (168 hours)
--window 168
```

## Python API

### Recording Metrics

```python
from agent_system.metrics_aggregator import get_metrics_aggregator

aggregator = get_metrics_aggregator()

# Record agent activity
aggregator.record_agent_activity(
    agent='scribe',
    duration_ms=2500,
    cost_usd=0.12,
    task_id='t_123',
    model='sonnet-4.5'
)

# Record feature completion
aggregator.record_feature_completion(
    feature='user_authentication',
    total_cost=0.35,
    duration_ms=15000,
    retry_count=1,
    task_id='t_123'
)

# Record critic decision
aggregator.record_critic_decision(
    test_id='test_001',
    decision='approved',  # or 'rejected'
    reason='good quality'
)

# Record validation result
aggregator.record_validation_result(
    test_id='test_001',
    passed=True,
    duration_ms=5000,
    cost_usd=0.08
)
```

### Retrieving Metrics

```python
from agent_system.metrics_aggregator import get_metrics_aggregator

aggregator = get_metrics_aggregator()

# Get metrics summary
summary = aggregator.get_metrics_summary(window_hours=1)
print(f"Agent Utilization: {summary['agent_utilization']}")
print(f"Cost Per Feature: {summary['cost_per_feature']}")
print(f"Avg Retry Count: {summary['average_retry_count']}")
print(f"Critic Rejection Rate: {summary['critic_rejection_rate']}")
print(f"Validation Pass Rate: {summary['validation_pass_rate']}")
print(f"Model Usage: {summary['model_usage']}")

# Get historical trend
trend = aggregator.get_historical_trend('cost_per_feature', days=7)
for data_point in trend:
    print(f"{data_point['date']}: ${data_point['value']:.4f} (count: {data_point['count']})")
```

## Integration with Kaya

The metrics aggregator is automatically integrated into Kaya's pipeline execution. Metrics are recorded at each step:

1. **Scribe** - Agent activity recorded after test creation
2. **Critic** - Decision and agent activity recorded after pre-validation
3. **Runner** - Agent activity recorded after test execution
4. **Medic** - Agent activity recorded after bug fix (if needed)
5. **Gemini** - Validation result and agent activity recorded after browser validation
6. **Pipeline Complete** - Feature completion recorded with total cost, duration, and retry count

No manual instrumentation needed - metrics are captured automatically during pipeline execution.

## Observability Dashboard Integration

Metrics are emitted to the observability dashboard via WebSocket events. The dashboard displays real-time metrics and historical trends.

**WebSocket Events**:
- `agent_activity`: Emitted when agent completes work
- `feature_completed`: Emitted when full pipeline completes
- `critic_decision`: Emitted when Critic makes decision
- `validation_result`: Emitted when Gemini validates

**Starting Dashboard**:
```bash
# Start observability dashboard (separate terminal)
cd agent_system/observability
python dashboard/server.py

# Access dashboard
open http://localhost:3010
```

## Maintenance

### Cleanup Old Metrics

Metrics have automatic 30-day TTL, but you can manually cleanup:

```python
from agent_system.metrics_aggregator import get_metrics_aggregator

aggregator = get_metrics_aggregator()

# Delete metrics older than 30 days
deleted_count = aggregator.cleanup_old_metrics(days=30)
print(f"Deleted {deleted_count} old metric keys")
```

### Redis Storage

Metrics are stored in Redis with sorted sets. Each hour gets its own key for efficient time-window queries.

**Storage Overhead**: ~1KB per metric entry
**30-Day Storage**: ~100MB for 100K metrics/month

## Performance Tuning

### Redis Configuration

For optimal performance with time-series data:

```bash
# redis.conf
maxmemory 1gb
maxmemory-policy allkeys-lru
save ""  # Disable RDB snapshots for faster writes
```

### Query Optimization

- Use smaller time windows for faster queries (1-6 hours)
- Historical trends are pre-aggregated by day
- Metrics are indexed by timestamp for O(log N) queries

## Troubleshooting

### No Data in Metrics

1. Check Redis connection:
```bash
python agent_system/cli.py health
```

2. Verify Kaya is recording metrics:
```python
from agent_system.agents.kaya import KayaAgent
kaya = KayaAgent()
print(f"Metrics aggregator: {kaya.metrics}")
```

3. Check Redis keys:
```bash
redis-cli KEYS "metrics:*"
```

### Missing Historical Data

Metrics have 30-day TTL. Data older than 30 days is automatically deleted.

### Incorrect Calculations

Verify time window:
```bash
# Check current time
date

# Verify hour keys
redis-cli KEYS "metrics:*:$(date +%Y-%m-%d-%H)"
```

## KPIs and Targets

From CLAUDE.md Week 2-4 success criteria:

| Metric | Target | Status |
|--------|--------|--------|
| Avg Retry Count | ≤ 1.5 | Tracked |
| Cost Per Feature | ≤ $0.50 | Tracked |
| Validation Pass Rate | ≥ 95% | Tracked |
| Critic Rejection Rate | 15-30% | Tracked |
| Time to Completion | < 10 min | Tracked |
| Model Usage (Haiku) | 70% | Tracked |

Monitor these metrics daily to ensure system health and cost optimization.

## Examples

### Daily Report Script

```bash
#!/bin/bash
# daily_metrics_report.sh

echo "SuperAgent Daily Metrics Report - $(date +%Y-%m-%d)"
echo "================================================"

# Get 24-hour summary
python agent_system/cli.py metrics summary --window 24

# Get historical trend
python agent_system/cli.py metrics trend --days 7

# Get cost breakdown
python agent_system/cli.py cost daily
```

### Alert on High Rejection Rate

```python
from agent_system.metrics_aggregator import get_metrics_aggregator

aggregator = get_metrics_aggregator()
summary = aggregator.get_metrics_summary(window_hours=1)

if summary['critic_rejection_rate'] > 0.30:
    print(f"ALERT: High rejection rate: {summary['critic_rejection_rate']*100:.1f}%")
    # Send alert to monitoring system
```

### Dashboard Integration

```python
from agent_system.metrics_aggregator import get_metrics_aggregator
from agent_system.observability import emit_event

aggregator = get_metrics_aggregator()
summary = aggregator.get_metrics_summary(window_hours=1)

# Emit metrics to dashboard
emit_event('metrics_snapshot', {
    'timestamp': time.time(),
    'agent_utilization': summary['agent_utilization'],
    'cost_per_feature': summary['cost_per_feature'],
    'validation_pass_rate': summary['validation_pass_rate'],
    'critic_rejection_rate': summary['critic_rejection_rate']
})
```

## Next Steps

1. Set up automated daily reports
2. Configure alerting for KPI thresholds
3. Integrate with observability dashboard
4. Add custom metrics for specific features
5. Export metrics to external monitoring tools (Datadog, Grafana, etc.)
