# Observability System - Quick Reference Card

## 🚀 One-Line Integration

```python
from agent_system.observability import emit_event
```

## 📊 Event Types Cheat Sheet

| Event Type | When to Emit | Required Fields |
|------------|--------------|----------------|
| `task_queued` | Task enters queue | task_id, feature, est_cost, timestamp |
| `agent_started` | Agent begins work | agent, task_id, model, tools |
| `agent_completed` | Agent finishes | agent, task_id, status, duration_ms, cost_usd |
| `validation_complete` | Validation done | task_id, result, cost, duration_ms, screenshots |
| `hitl_escalated` | Escalate to human | task_id, attempts, last_error, priority |
| `budget_warning` | 80% budget used | current_spend, limit, remaining |
| `budget_exceeded` | Budget exceeded | current_spend, limit, tasks_blocked |

## 💡 Common Patterns

### Pattern 1: Agent Task Wrapper

```python
def process_task(self, task_id):
    start = time.time()
    emit_event('agent_started', {
        'agent': 'your_agent',
        'task_id': task_id,
        'model': 'claude-sonnet-4.5',
        'tools': ['read', 'write']
    })
    try:
        result = self.do_work()
        emit_event('agent_completed', {
            'agent': 'your_agent',
            'task_id': task_id,
            'status': 'success',
            'duration_ms': int((time.time() - start) * 1000),
            'cost_usd': 0.12
        })
        return result
    except Exception:
        emit_event('agent_completed', {
            'agent': 'your_agent',
            'task_id': task_id,
            'status': 'failed',
            'duration_ms': int((time.time() - start) * 1000),
            'cost_usd': 0.0
        })
        raise
```

### Pattern 2: Critic Decision

```python
from agent_system.observability import get_emitter

def review(self, task_id):
    approved = self.check_quality()
    get_emitter().record_critic_decision(rejected=not approved)
    emit_event('agent_completed', {
        'status': 'approved' if approved else 'rejected',
        ...
    })
```

### Pattern 3: HITL Escalation

```python
if attempts >= 2:
    emit_event('hitl_escalated', {
        'task_id': task_id,
        'attempts': attempts,
        'last_error': str(error),
        'priority': 'high'
    })
```

## 🔧 CLI Commands

```bash
# View all events
python3 agent_system/observability/view_logs.py

# View last 10 events
python3 agent_system/observability/view_logs.py --tail 10

# Follow logs (real-time)
python3 agent_system/observability/view_logs.py --follow

# Filter by type
python3 agent_system/observability/view_logs.py --type task_queued

# Show statistics
python3 agent_system/observability/view_logs.py --stats

# Search logs
python3 agent_system/observability/view_logs.py --search "t_123"
```

## 📈 Viewing Options

| Method | How | Use Case |
|--------|-----|----------|
| Console | Automatic | Development/debugging |
| JSONL file | `logs/agent-events.jsonl` | Analysis/replay |
| WebSocket | `ws://localhost:3010` | Real-time monitoring |
| Dashboard | `dashboard.html` | Visual monitoring |
| CLI tool | `view_logs.py` | Quick inspection |

## 🎯 Metrics Available

```python
from agent_system.observability import get_emitter

metrics = get_emitter().get_metrics()
# Returns:
# {
#   'agent_utilization': 0.75,
#   'cost_per_feature': 0.45,
#   'average_retry_count': 1.2,
#   'critic_rejection_rate': 0.25,
#   'validation_pass_rate': 0.85,
#   'time_to_completion': 12.5
# }
```

## 🔌 WebSocket Quick Start

### Server
```python
import asyncio
from agent_system.observability import get_emitter

async def main():
    emitter = get_emitter()
    await emitter.start()  # Starts WebSocket on port 3010
    # ... emit events ...
    await emitter.stop()

asyncio.run(main())
```

### Client (Browser)
```javascript
const ws = new WebSocket('ws://localhost:3010');
ws.onmessage = (e) => console.log(JSON.parse(e.data));
```

### Client (Python)
```python
import asyncio, websockets, json

async def listen():
    async with websockets.connect('ws://localhost:3010') as ws:
        async for msg in ws:
            print(json.loads(msg))

asyncio.run(listen())
```

## 📁 Log Analysis

```bash
# Count events by type
cat logs/agent-events.jsonl | jq -r '.event_type' | sort | uniq -c

# Find all failed tasks
cat logs/agent-events.jsonl | jq 'select(.payload.status == "failed")'

# Calculate total cost
cat logs/agent-events.jsonl | jq '.payload.cost_usd // 0' | paste -sd+ | bc

# Get validation pass rate
cat logs/agent-events.jsonl | jq 'select(.event_type == "validation_complete") | .payload.result.test_passed' | grep true -c
```

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| Import error | `pip install redis websockets` |
| Redis error | `brew services start redis` or `docker run -d -p 6379:6379 redis` |
| WebSocket won't start | Check port 3010: `lsof -i :3010` |
| No events | Verify emitter enabled: `get_emitter().console_enabled` |
| Log file not created | Check directory exists: `mkdir -p logs` |

## ⚡ Quick Test

```bash
# Test event emission
python3 -c "
from agent_system.observability import emit_event
import time
emit_event('task_queued', {
    'task_id': 't_test',
    'feature': 'test',
    'est_cost': 0.10,
    'timestamp': time.time()
})
print('Event emitted successfully!')
"

# Verify it was logged
tail -1 logs/agent-events.jsonl | jq
```

## 📚 Full Documentation

- **README.md** - Complete API documentation
- **QUICKSTART.md** - Getting started guide
- **dashboard.html** - Visual monitoring interface
- **examples/event_streaming_example.py** - Integration examples

## 🎨 Dashboard Usage

```bash
# Open dashboard in browser
open agent_system/observability/dashboard.html

# Or
python3 -m http.server 8080
# Navigate to: http://localhost:8080/agent_system/observability/dashboard.html
```

## 🔑 Key Files

```
agent_system/observability/
├── event_stream.py      # Core implementation
├── __init__.py          # Exports: emit_event, get_emitter
├── view_logs.py         # CLI log viewer
├── dashboard.html       # Visual dashboard
├── README.md            # Full docs
└── QUICKSTART.md        # Quick start

examples/
└── event_streaming_example.py  # Usage examples

logs/
└── agent-events.jsonl   # Auto-created event log
```

## ⏱️ Performance

- Event emission: <1ms
- Console output: <1ms
- File write: <5ms
- WebSocket broadcast: <10ms
- Metrics calculation: <1ms

## 🎯 Integration Checklist

- [ ] Install dependencies (`pip install redis websockets`)
- [ ] Start Redis (`brew services start redis`)
- [ ] Import in agents (`from agent_system.observability import emit_event`)
- [ ] Add `agent_started` events
- [ ] Add `agent_completed` events
- [ ] Add `task_queued` events (in router)
- [ ] Add `validation_complete` events (in Gemini)
- [ ] Add `hitl_escalated` events (in Medic)
- [ ] Test with examples (`python3 examples/event_streaming_example.py`)
- [ ] Open dashboard (`open dashboard.html`)

## 💾 Redis Storage

```python
from agent_system.state.redis_client import RedisClient

redis = RedisClient()

# Get today's metrics
import datetime
today = datetime.date.today().isoformat()
metrics = redis.get(f"metrics:daily:{today}")
```

## 📞 Support

- Check tests: `python3 tests/test_event_stream_standalone.py`
- View logs: `python3 agent_system/observability/view_logs.py --stats`
- Run example: `python3 examples/event_streaming_example.py`

---

**Need help?** See full documentation in `README.md` or `QUICKSTART.md`
