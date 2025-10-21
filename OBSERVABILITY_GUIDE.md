# 📊 SuperAgent Observability & Tracking

## Built-In Monitoring System

SuperAgent has a **comprehensive observability system** already built in! Here's everything that's tracking your overnight build:

## 🎯 Real-Time Event Streaming

### WebSocket Event Stream

**Location:** [agent_system/observability/event_stream.py](agent_system/observability/event_stream.py)

**Features:**
- Real-time WebSocket broadcasting of all agent events
- Daily log rotation (logs/agent-events-YYYY-MM-DD.jsonl)
- Auto-compression of logs older than 7 days (gzip)
- Auto-deletion of logs older than 30 days
- Console output for immediate viewing
- File logging for historical analysis

**Events Tracked:**
```python
- task_queued        # Feature added to build queue
- agent_started      # Scribe/Runner/Medic started
- agent_completed    # Agent finished successfully
- agent_failed       # Agent encountered error
- test_generated     # Scribe created test file
- test_validated     # Runner executed test
- test_fixed         # Medic applied fix
- cost_updated       # API cost incurred
```

**Usage:**
```python
from agent_system.observability import emit_event

# Automatically called by agents - you'll see:
emit_event('test_generated', {
    'agent': 'scribe',
    'task_id': 't_123',
    'test_path': 'tests/board_creation.spec.ts',
    'cost': 0.12,
    'model': 'claude-sonnet-4.5'
})
```

### View Live Events

**Option 1: Console Logs (Running Now)**
```bash
docker compose -f config/docker-compose.yml logs -f superagent
```

**Option 2: Event Log Files**
```bash
# Today's events
cat logs/agent-events-$(date +%Y-%m-%d).jsonl | jq

# Last 10 events
tail -10 logs/agent-events-$(date +%Y-%m-%d).jsonl | jq

# Filter by event type
grep "test_generated" logs/agent-events-*.jsonl | jq

# Filter by agent
grep '"agent":"scribe"' logs/agent-events-*.jsonl | jq
```

**Option 3: WebSocket Client (Real-time Dashboard)**
```bash
# Start event stream server
python agent_system/observability/event_stream.py

# Connect from browser
# WebSocket URL: ws://localhost:8765
```

## 📈 Metrics Aggregation

### Redis Time-Series Metrics

**Location:** [agent_system/metrics_aggregator.py](agent_system/metrics_aggregator.py)

**Metrics Tracked:**
```python
1. agent_utilization      # Time each agent spends active
2. cost_per_feature       # Total cost per feature
3. average_retry_count    # Mean retries before success
4. critic_rejection_rate  # % tests rejected by Critic
5. validation_pass_rate   # % tests passing Runner
6. time_to_completion     # End-to-end time per feature
7. model_usage           # Haiku vs Sonnet ratio
```

**Storage:** Redis sorted sets with 30-day retention

**View Metrics:**
```python
from agent_system.metrics_aggregator import get_metrics_aggregator

aggregator = get_metrics_aggregator()

# Get last hour summary
summary = aggregator.get_metrics_summary(window_hours=1)
print(f"Tests generated: {summary['tests_generated']}")
print(f"Total cost: ${summary['total_cost']:.2f}")
print(f"Pass rate: {summary['pass_rate']:.1%}")

# Get 7-day trend
trend = aggregator.get_historical_trend('cost_per_feature', days=7)
print(trend)
```

### Auto-Recorded Metrics

During your overnight build, these are automatically tracked:

**Per Task:**
- Start/end timestamps
- Duration (ms)
- Cost ($USD)
- Model used (Haiku/Sonnet)
- Retry count
- Success/failure status

**Aggregated:**
- Total tests generated
- Total cost
- Average cost per test
- Pass rate percentage
- Fix attempts per failure
- Time distribution (Scribe vs Runner vs Medic)

## 🚨 Alerting System

### Threshold-Based Alerts

**Location:** [agent_system/observability/alerting.py](agent_system/observability/alerting.py)

**Configuration:** `.claude/observability.yaml`

**Alert Conditions:**
```yaml
alerts:
  - metric: critic_rejection_rate
    operator: '>'
    threshold: 0.30  # Alert if >30% tests rejected
    action: warn_user
    message: "High critic rejection rate detected"

  - metric: cost_per_feature
    operator: '>'
    threshold: 2.00  # Alert if any feature >$2
    action: notify_admin
    message: "Feature cost exceeded budget"

  - metric: validation_pass_rate
    operator: '<'
    threshold: 0.70  # Alert if <70% passing
    action: warn_user
    message: "Low validation pass rate"
```

**Notification Channels:**
- Console (enabled by default)
- Webhook (configure URL in observability.yaml)
- Email (configure SMTP in observability.yaml)

**Rate Limiting:**
- Max 1 alert per metric per hour (prevents spam)
- Configurable cooldown periods

## 📊 What You'll See During Overnight Build

### Console Output

```bash
docker compose logs -f superagent
```

**Sample Output:**
```
🏗️  Building feature: board management
📋 Created 4 tasks
🚀 Starting autonomous execution of 4 tasks

📝 Task 1/4: Generate test: board creation
INFO:agent_system.observability:Event emitted: agent_started
  agent: scribe
  model: claude-sonnet-4.5
  task_id: task_1234

INFO:agent_system.agents.scribe:Generation attempt 1/3
INFO:agent_system.observability:Event emitted: test_generated
  test_path: tests/board_creation.spec.ts
  cost: $0.12
  duration: 2500ms

🏃 Runner: Validating test...
INFO:agent_system.observability:Event emitted: test_validated
  status: passed
  duration: 3200ms

✅ Task 1 completed successfully

INFO:agent_system.metrics:Metrics updated
  total_cost: $0.12
  tests_generated: 1
  pass_rate: 100.0%
```

### Event Log Structure

**File:** `logs/agent-events-2025-10-19.jsonl`

```json
{
  "timestamp": "2025-10-19T23:15:42.123Z",
  "event_type": "test_generated",
  "agent": "scribe",
  "task_id": "task_1234",
  "data": {
    "test_path": "tests/board_creation.spec.ts",
    "model": "claude-sonnet-4.5",
    "cost": 0.12,
    "duration_ms": 2500,
    "lines_of_code": 85
  }
}
```

### Metrics Summary (End of Build)

```python
{
  "window_hours": 4,
  "tests_generated": 42,
  "tests_passed": 39,
  "tests_failed": 3,
  "total_cost": 7.80,
  "avg_cost_per_test": 0.19,
  "pass_rate": 0.928,
  "agent_utilization": {
    "scribe": 3420000,  # ms active
    "runner": 1280000,
    "medic": 890000
  },
  "model_usage": {
    "sonnet": 42,  # All tests used Sonnet
    "haiku": 0
  },
  "retry_stats": {
    "avg_retries": 0.43,
    "max_retries": 3,
    "tests_needing_fixes": 15
  }
}
```

## 🔍 Monitoring Your Build

### During the Build

**Terminal 1: Live Logs**
```bash
docker compose -f config/docker-compose.yml logs -f superagent | grep -E "🏗️|📋|✅|❌|Task"
```

**Terminal 2: Status Check**
```bash
watch -n 30 ./check_build_status.sh
```

**Terminal 3: Metrics Dashboard**
```bash
# Every 5 minutes, show updated metrics
watch -n 300 'redis-cli --json ZRANGE superagent:metrics:cost_per_feature -inf +inf BYSCORE'
```

### After the Build

**1. Check Final Summary**
```bash
./check_build_status.sh
```

**2. View Full Event Log**
```bash
cat logs/agent-events-$(date +%Y-%m-%d).jsonl | jq 'select(.event_type == "agent_completed")'
```

**3. Get Cost Breakdown**
```bash
cat logs/agent-events-*.jsonl | jq -s 'map(select(.data.cost)) | map(.data.cost) | add'
```

**4. Calculate Pass Rate**
```bash
cat logs/agent-events-*.jsonl | \
  jq -s 'map(select(.event_type == "test_validated")) |
         group_by(.data.passed) |
         map({status: .[0].data.passed, count: length})'
```

**5. Find Failed Tests**
```bash
cat logs/agent-events-*.jsonl | \
  jq -s 'map(select(.event_type == "test_validated" and .data.passed == false))'
```

## 📊 Built-In Dashboards

### Cost Analytics Dashboard

**Script:** `python agent_system/observability/cost_dashboard.py`

Shows:
- Total spend today/week/month
- Cost per agent
- Cost per feature
- Model usage breakdown
- Projected monthly cost

### Performance Dashboard

**Script:** `python agent_system/observability/performance_dashboard.py`

Shows:
- Agent response times
- Test generation speed
- Fix success rate
- Bottleneck analysis

### Real-Time WebSocket Dashboard

**Script:** `python agent_system/observability/event_stream.py`

**Browser:** Open `http://localhost:8765`

Shows:
- Live event feed
- Agent status indicators
- Running cost counter
- Pass/fail gauge
- Task progress bar

## 🎯 Key Metrics for Overnight Build

### Success Metrics

**Excellent Build:**
```
Tests Generated: 40+
Pass Rate: 95%+
Avg Cost/Test: $0.10-0.20
Total Cost: $5-8
Failed After Fixes: 0-2
Duration: 2-3 hours
```

**Good Build:**
```
Tests Generated: 38+
Pass Rate: 85%+
Avg Cost/Test: $0.15-0.30
Total Cost: $8-12
Failed After Fixes: 3-5
Duration: 3-4 hours
```

**Needs Review:**
```
Tests Generated: <35
Pass Rate: <80%
Avg Cost/Test: >$0.30
Total Cost: >$15
Failed After Fixes: >6
Duration: >5 hours
```

### Alert Triggers

**You'll Get Notified If:**
- Any single test costs >$0.50 (runaway Medic fixes)
- Pass rate drops below 70% (infrastructure issue)
- Build duration exceeds 6 hours (stuck agent)
- Total cost exceeds $20 (budget overrun)

## 🛠️ Observability Tools Available

### 1. Event Stream (Real-Time)
✅ WebSocket broadcasting
✅ Console logging
✅ File logging with rotation
✅ JSON structured events

### 2. Metrics Aggregation (Historical)
✅ Redis time-series storage
✅ 30-day retention
✅ Hourly aggregation
✅ Trend analysis

### 3. Alerting (Proactive)
✅ Threshold-based alerts
✅ Multiple notification channels
✅ Rate limiting
✅ Custom conditions

### 4. Cost Tracking (Budget)
✅ Per-agent cost attribution
✅ Per-feature cost rollup
✅ Model usage breakdown
✅ Budget enforcement

### 5. Performance Monitoring
✅ Agent utilization tracking
✅ Duration metrics
✅ Retry statistics
✅ Bottleneck identification

## 📝 Accessing Observability Data

### Redis Keys

All metrics stored in Redis:
```bash
# List all metric keys
redis-cli KEYS "superagent:*"

# Get cost metrics
redis-cli ZRANGE superagent:metrics:cost_per_feature -inf +inf BYSCORE

# Get agent utilization
redis-cli HGETALL superagent:agent_utilization

# Get validation results
redis-cli LRANGE superagent:validations 0 -1
```

### Log Files

All events logged to disk:
```bash
# Location
logs/agent-events-YYYY-MM-DD.jsonl

# Compressed archives (after 7 days)
logs/agent-events-YYYY-MM-DD.jsonl.gz

# View compressed logs
zcat logs/agent-events-2025-10-12.jsonl.gz | jq
```

## 🚀 Custom Observability

### Add Your Own Events

```python
from agent_system.observability import emit_event

emit_event('custom_event', {
    'my_metric': 123,
    'my_data': 'foo',
    'timestamp': time.time()
})
```

### Add Custom Metrics

```python
from agent_system.metrics_aggregator import get_metrics_aggregator

aggregator = get_metrics_aggregator()
aggregator.record_custom_metric(
    metric_name='my_custom_metric',
    value=42.0,
    timestamp=time.time()
)
```

### Add Custom Alerts

Edit `.claude/observability.yaml`:
```yaml
alerts:
  - metric: my_custom_metric
    operator: '>'
    threshold: 100
    action: notify_admin
    message: "Custom metric exceeded!"
```

## Summary

**Your overnight build is FULLY OBSERVABLE:**

✅ **Real-time monitoring** - WebSocket events + console logs
✅ **Historical metrics** - 30 days in Redis
✅ **Automatic alerting** - Threshold violations
✅ **Cost tracking** - Every penny accounted for
✅ **Performance analytics** - Agent utilization, bottlenecks
✅ **Log rotation** - Automatic compression and cleanup

**You'll be able to see:**
- Every test generated
- Every fix attempted
- Every dollar spent
- Every second elapsed
- Every pass/fail result
- Every agent activity

**All in real-time or historically!** 📊✨

---

See logs in: `logs/agent-events-$(date +%Y-%m-%d).jsonl`
