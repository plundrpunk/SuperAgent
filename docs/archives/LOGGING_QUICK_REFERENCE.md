# Structured Logging Quick Reference

## Quick Start

### Emit Events (Basic)

```python
from agent_system.observability import emit_event
import time

# Emit a task queued event
emit_event('task_queued', {
    'task_id': 't_123',
    'feature': 'checkout',
    'est_cost': 0.25,
    'timestamp': time.time()
})

# Emit agent started event
emit_event('agent_started', {
    'agent': 'scribe',
    'task_id': 't_123',
    'model': 'claude-sonnet-4.5',
    'tools': ['read', 'write', 'edit']
})

# Emit agent completed event
emit_event('agent_completed', {
    'agent': 'scribe',
    'task_id': 't_123',
    'status': 'success',
    'duration_ms': 2500,
    'cost_usd': 0.12
})
```

### View Logs (CLI)

```bash
# View all logs
python agent_system/observability/view_logs.py

# View last 20 events
python agent_system/observability/view_logs.py --tail 20

# View logs for today
python agent_system/observability/view_logs.py --date 2025-10-14

# View logs for date range
python agent_system/observability/view_logs.py --date-range 2025-10-01 2025-10-14

# Filter by agent
python agent_system/observability/view_logs.py --agent scribe

# Filter by task ID
python agent_system/observability/view_logs.py --task-id t_123

# Filter by status
python agent_system/observability/view_logs.py --status success

# Show statistics
python agent_system/observability/view_logs.py --stats

# Follow logs in real-time
python agent_system/observability/view_logs.py --follow
```

## Log Rotation Settings

### Default Configuration (Recommended)

```python
from agent_system.observability import EventEmitter

emitter = EventEmitter(
    file_enabled=True,
    file_path='logs/agent-events.jsonl',
    enable_log_rotation=True,    # Enable rotation (default)
    compress_after_days=7,        # Compress after 7 days
    delete_after_days=30          # Delete after 30 days
)
```

### Custom Configuration

```python
# Short retention (testing/development)
emitter = EventEmitter(
    file_path='logs/test-events.jsonl',
    enable_log_rotation=True,
    compress_after_days=1,        # Compress after 1 day
    delete_after_days=7           # Delete after 7 days
)

# Long retention (production/compliance)
emitter = EventEmitter(
    file_path='logs/prod-events.jsonl',
    enable_log_rotation=True,
    compress_after_days=30,       # Compress after 30 days
    delete_after_days=365         # Delete after 1 year
)

# No rotation (single file)
emitter = EventEmitter(
    file_path='logs/events.jsonl',
    enable_log_rotation=False     # Single file mode
)
```

## Event Types

### Task Events

```python
# Task queued
emit_event('task_queued', {
    'task_id': 't_123',
    'feature': 'user_login',
    'est_cost': 0.35,
    'timestamp': time.time()
})
```

### Agent Events

```python
# Agent started
emit_event('agent_started', {
    'agent': 'scribe',
    'task_id': 't_123',
    'model': 'claude-sonnet-4.5',
    'tools': ['read', 'write', 'edit', 'grep']
})

# Agent completed
emit_event('agent_completed', {
    'agent': 'scribe',
    'task_id': 't_123',
    'status': 'success',
    'duration_ms': 2500,
    'cost_usd': 0.12
})
```

### Validation Events

```python
# Validation complete
emit_event('validation_complete', {
    'task_id': 't_123',
    'result': {
        'browser_launched': True,
        'test_executed': True,
        'test_passed': True,
        'screenshots': ['screenshot1.png', 'screenshot2.png']
    },
    'cost': 0.08,
    'duration_ms': 5000,
    'screenshots': 2
})
```

### HITL Events

```python
# HITL escalation
emit_event('hitl_escalated', {
    'task_id': 't_123',
    'attempts': 3,
    'last_error': 'Selector timeout',
    'priority': 'high'
})
```

### Budget Events

```python
# Budget warning
emit_event('budget_warning', {
    'current_spend': 0.85,
    'limit': 1.00,
    'remaining': 0.15
})

# Budget exceeded
emit_event('budget_exceeded', {
    'current_spend': 1.05,
    'limit': 1.00,
    'overage': 0.05
})
```

## Log File Structure

```
logs/
├── agent-events-2025-10-14.jsonl      # Today (current)
├── agent-events-2025-10-13.jsonl      # Yesterday
├── agent-events-2025-10-12.jsonl      # 2 days ago
├── agent-events-2025-10-07.jsonl      # 7 days ago
├── agent-events-2025-10-06.jsonl.gz   # 8 days ago (compressed)
├── agent-events-2025-10-05.jsonl.gz   # 9 days ago (compressed)
└── agent-events-2025-09-15.jsonl.gz   # 29 days ago (deleted at 30 days)
```

## Programmatic Log Reading

### Read Events from File

```python
from agent_system.observability.view_logs import read_events_from_file
from pathlib import Path

# Read from uncompressed log
events = read_events_from_file(Path('logs/agent-events-2025-10-14.jsonl'))

# Read from compressed log
events = read_events_from_file(Path('logs/agent-events-2025-10-06.jsonl.gz'))

# Process events
for event in events:
    print(f"{event['event_type']}: {event['payload'].get('task_id')}")
```

### Find Log Files

```python
from agent_system.observability.view_logs import find_log_files
from pathlib import Path

log_dir = Path('logs')

# Find logs for specific date
logs = find_log_files(log_dir, date='2025-10-14')

# Find logs in date range
logs = find_log_files(log_dir, start_date='2025-10-01', end_date='2025-10-14')

# Find all logs
logs = find_log_files(log_dir)
```

### Filter Events

```python
from agent_system.observability.view_logs import filter_events, read_events

# Read all events
events = read_events('logs')

# Filter by agent
scribe_events = filter_events(events, agent='scribe')

# Filter by task
task_events = filter_events(events, task_id='t_123')

# Filter by status
success_events = filter_events(events, status='success')

# Combine filters
filtered = filter_events(events, agent='scribe', status='success')
```

## Maintenance

### Manual Maintenance

```python
from agent_system.observability.event_stream import LogRotationManager
from pathlib import Path

# Create manager
manager = LogRotationManager(
    log_dir=Path('logs'),
    base_name='agent-events',
    compress_after_days=7,
    delete_after_days=30
)

# Run maintenance manually
manager.maintain_logs()  # Compress old logs + delete very old logs

# Or run individually
manager.compress_old_logs()  # Just compress
manager.delete_old_logs()    # Just delete
```

### Automatic Maintenance

Maintenance runs automatically once per day when events are emitted:
- Compresses logs older than `compress_after_days`
- Deletes logs older than `delete_after_days`

No manual intervention required!

## Common Patterns

### Agent Integration

```python
from agent_system.observability import emit_event
import time

class MyAgent:
    def process_task(self, task_id):
        start_time = time.time()

        # Emit start event
        emit_event('agent_started', {
            'agent': 'my_agent',
            'task_id': task_id,
            'model': 'claude-sonnet-4.5',
            'tools': ['read', 'write']
        })

        try:
            # Do work...
            result = self.do_work()

            # Emit success event
            duration_ms = int((time.time() - start_time) * 1000)
            emit_event('agent_completed', {
                'agent': 'my_agent',
                'task_id': task_id,
                'status': 'success',
                'duration_ms': duration_ms,
                'cost_usd': 0.12
            })

            return result

        except Exception as e:
            # Emit failure event
            duration_ms = int((time.time() - start_time) * 1000)
            emit_event('agent_completed', {
                'agent': 'my_agent',
                'task_id': task_id,
                'status': 'failed',
                'duration_ms': duration_ms,
                'cost_usd': 0.0,
                'error': str(e)
            })
            raise
```

### Cost Tracking

```python
from agent_system.observability.view_logs import read_events

# Read all events
events = read_events('logs')

# Calculate total cost
total_cost = 0
for event in events:
    if event['event_type'] == 'agent_completed':
        total_cost += event['payload'].get('cost_usd', 0)
    elif event['event_type'] == 'validation_complete':
        total_cost += event['payload'].get('cost', 0)

print(f"Total cost: ${total_cost:.2f}")
```

### Task Timeline

```python
from agent_system.observability.view_logs import read_events, filter_events

# Get all events for a task
task_id = 't_123'
events = read_events('logs')
task_events = filter_events(events, task_id=task_id)

# Build timeline
print(f"Timeline for {task_id}:")
for event in sorted(task_events, key=lambda e: e['timestamp']):
    timestamp = datetime.fromtimestamp(event['timestamp']).strftime('%H:%M:%S')
    event_type = event['event_type']
    print(f"  [{timestamp}] {event_type}")
```

## Troubleshooting

### No logs appearing

```python
# Check if emitter is enabled
from agent_system.observability import get_emitter

emitter = get_emitter()
print(f"File enabled: {emitter.file_enabled}")
print(f"Log rotation: {emitter.enable_log_rotation}")

# Check log directory
if emitter.enable_log_rotation:
    print(f"Log directory: {emitter.log_dir}")
    print(f"Current log: {emitter.rotation_manager.get_current_log_path()}")
else:
    print(f"Log file: {emitter.file_path}")
```

### View all log files

```bash
# List all log files
ls -lh logs/agent-events-*

# List with dates
ls -lt logs/agent-events-*

# Count events per file
for f in logs/agent-events-*.jsonl; do
    echo "$f: $(wc -l < $f) events"
done
```

### Check compressed logs

```bash
# View compressed log contents
zcat logs/agent-events-2025-10-06.jsonl.gz | head -10

# Count events in compressed log
zcat logs/agent-events-2025-10-06.jsonl.gz | wc -l
```

## Performance Tips

1. **Use tail for large logs**: `--tail 100` instead of viewing all
2. **Filter early**: Use `--date` or `--agent` to reduce data
3. **Compressed logs are slower**: Expect 2-3x slower read times
4. **Stats mode is cached**: Use `--stats` for quick overview

## Best Practices

1. **Always include task_id**: Essential for tracking
2. **Use consistent agent names**: Makes filtering easier
3. **Include timestamps**: Already automatic, but verify in payload
4. **Log both start and end**: Track duration and cost
5. **Use structured payloads**: Easier to parse and analyze
6. **Don't log secrets**: Never log API keys or credentials
7. **Use appropriate retention**: Balance disk space vs compliance needs

## Examples

See `/tests/test_log_rotation_simple.py` for complete working examples.
