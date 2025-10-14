# Event Streaming & Observability System

Real-time event streaming infrastructure for SuperAgent system monitoring and debugging.

## Features

- **Multi-Destination Events**: Emit to WebSocket, console, and JSONL files simultaneously
- **Real-Time Streaming**: WebSocket server for live event monitoring
- **Metrics Aggregation**: Automatic tracking of key performance indicators
- **Pretty Console Output**: Color-coded event logging for development
- **JSONL Logging**: Structured logging for analysis and replay
- **Zero Configuration**: Works out of the box with sensible defaults

## Quick Start

### Basic Usage

```python
from agent_system.observability import emit_event
import time

# Emit a task queued event
emit_event('task_queued', {
    'task_id': 't_123',
    'feature': 'user_authentication',
    'est_cost': 0.35,
    'timestamp': time.time()
})

# Emit agent started event
emit_event('agent_started', {
    'agent': 'scribe',
    'task_id': 't_123',
    'model': 'claude-sonnet-4.5',
    'tools': ['read', 'write', 'edit', 'grep']
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

### Starting the WebSocket Server

```python
import asyncio
from agent_system.observability import get_emitter

async def main():
    emitter = get_emitter()
    await emitter.start()

    # Emit events...
    emit_event('task_queued', {...})

    # Keep server running
    await asyncio.sleep(3600)  # Run for 1 hour

    # Cleanup
    await emitter.stop()

asyncio.run(main())
```

### Listening to Events (WebSocket Client)

```python
import asyncio
import websockets
import json

async def listen():
    async with websockets.connect('ws://localhost:3010') as ws:
        async for message in ws:
            event = json.loads(message)
            print(f"Event: {event['event_type']}")
            print(f"Payload: {event['payload']}")

asyncio.run(listen())
```

## Supported Event Types

### 1. task_queued
Emitted when a new task enters the queue.

```python
emit_event('task_queued', {
    'task_id': str,       # Unique task identifier
    'feature': str,       # Feature being tested
    'est_cost': float,    # Estimated cost in USD
    'timestamp': float    # Unix timestamp
})
```

### 2. agent_started
Emitted when an agent begins work on a task.

```python
emit_event('agent_started', {
    'agent': str,        # Agent name (scribe/runner/medic/critic/gemini)
    'task_id': str,      # Task identifier
    'model': str,        # Model being used
    'tools': List[str]   # List of tool names
})
```

### 3. agent_completed
Emitted when an agent finishes work.

```python
emit_event('agent_completed', {
    'agent': str,         # Agent name
    'task_id': str,       # Task identifier
    'status': str,        # success/failed/approved/rejected
    'duration_ms': int,   # Duration in milliseconds
    'cost_usd': float     # Actual cost in USD
})
```

### 4. validation_complete
Emitted when Gemini validation completes.

```python
emit_event('validation_complete', {
    'task_id': str,
    'result': {
        'browser_launched': bool,
        'test_executed': bool,
        'test_passed': bool,
        'screenshots': List[str],
        'execution_time_ms': int,
        'console_errors': List[str],
        'network_failures': List[str]
    },
    'cost': float,
    'duration_ms': int,
    'screenshots': int
})
```

### 5. hitl_escalated
Emitted when a task is escalated to human-in-the-loop.

```python
emit_event('hitl_escalated', {
    'task_id': str,      # Task identifier
    'attempts': int,     # Number of retry attempts
    'last_error': str,   # Last error message
    'priority': str      # low/medium/high
})
```

### 6. budget_warning
Emitted when approaching budget limit (80% threshold).

```python
emit_event('budget_warning', {
    'current_spend': float,  # Current spend in USD
    'limit': float,          # Budget limit
    'remaining': float       # Remaining budget
})
```

### 7. budget_exceeded
Emitted when budget limit is exceeded.

```python
emit_event('budget_exceeded', {
    'current_spend': float,  # Current spend in USD
    'limit': float,          # Budget limit
    'tasks_blocked': int     # Number of tasks blocked
})
```

## Metrics Tracking

The system automatically tracks these metrics:

- **agent_utilization**: Percentage of time agents are active
- **cost_per_feature**: Average cost per completed feature
- **average_retry_count**: Average number of retries per task
- **critic_rejection_rate**: Percentage of tests rejected by Critic
- **validation_pass_rate**: Percentage of validations that pass
- **time_to_completion**: Average time from queue to completion

### Accessing Metrics

```python
from agent_system.observability import get_emitter

emitter = get_emitter()
metrics = emitter.get_metrics()

print(f"Validation pass rate: {metrics['validation_pass_rate']:.2%}")
print(f"Average cost: ${metrics['cost_per_feature']:.2f}")
```

### Metrics Storage

Metrics are stored in Redis with time buckets:

- **Hourly**: `metrics:hourly:2025-10-14T14:00:00` (kept for 7 days)
- **Daily**: `metrics:daily:2025-10-14` (kept for 30 days)

## Configuration

### Environment Variables

```bash
# Redis configuration (for metrics storage)
export REDIS_HOST=localhost
export REDIS_PORT=6379
export REDIS_PASSWORD=your_password
export REDIS_DB=0

# Observability configuration
export OBSERVABILITY_WEBSOCKET_PORT=3010
export OBSERVABILITY_LOG_PATH=logs/agent-events.jsonl
export OBSERVABILITY_CONSOLE_LEVEL=INFO
```

### Custom Configuration

```python
from agent_system.observability.event_stream import EventEmitter, LogLevel

emitter = EventEmitter(
    websocket_enabled=True,
    websocket_port=3010,
    console_enabled=True,
    console_level=LogLevel.INFO,
    file_enabled=True,
    file_path='logs/agent-events.jsonl'
)
```

## Output Examples

### Console Output

```
[14:23:15] TASK_QUEUED
  task_id: t_001
  feature: user_checkout_flow
  est_cost: 0.45
  timestamp: 1697123395.123

[14:23:16] AGENT_STARTED
  agent: scribe
  task_id: t_001
  model: claude-sonnet-4.5
  tools: ['read', 'write', 'edit', 'grep']
```

### JSONL Log File

```jsonl
{"event_type":"task_queued","timestamp":1697123395.123,"payload":{"task_id":"t_001","feature":"user_checkout_flow","est_cost":0.45}}
{"event_type":"agent_started","timestamp":1697123396.234,"payload":{"agent":"scribe","task_id":"t_001","model":"claude-sonnet-4.5","tools":["read","write","edit","grep"]}}
{"event_type":"agent_completed","timestamp":1697123398.567,"payload":{"agent":"scribe","task_id":"t_001","status":"success","duration_ms":2500,"cost_usd":0.12}}
```

## Integration with Agents

### Scribe Agent Example

```python
from agent_system.observability import emit_event
import time

class ScribeAgent:
    def write_test(self, task_id: str, feature: str):
        # Emit start event
        start_time = time.time()
        emit_event('agent_started', {
            'agent': 'scribe',
            'task_id': task_id,
            'model': 'claude-sonnet-4.5',
            'tools': ['read', 'write', 'edit', 'grep']
        })

        try:
            # Write test code...
            test_code = self._generate_test(feature)

            # Emit completion
            duration_ms = (time.time() - start_time) * 1000
            emit_event('agent_completed', {
                'agent': 'scribe',
                'task_id': task_id,
                'status': 'success',
                'duration_ms': duration_ms,
                'cost_usd': 0.12
            })

            return test_code

        except Exception as e:
            # Emit failure
            duration_ms = (time.time() - start_time) * 1000
            emit_event('agent_completed', {
                'agent': 'scribe',
                'task_id': task_id,
                'status': 'failed',
                'duration_ms': duration_ms,
                'cost_usd': 0.05
            })
            raise
```

### Critic Agent Example

```python
from agent_system.observability import emit_event, get_emitter

class CriticAgent:
    def review_test(self, task_id: str, test_path: str):
        start_time = time.time()
        emit_event('agent_started', {
            'agent': 'critic',
            'task_id': task_id,
            'model': 'claude-haiku',
            'tools': ['read', 'grep']
        })

        # Review test...
        approved = self._check_quality(test_path)

        # Record decision for metrics
        emitter = get_emitter()
        emitter.record_critic_decision(rejected=not approved)

        # Emit completion
        duration_ms = (time.time() - start_time) * 1000
        emit_event('agent_completed', {
            'agent': 'critic',
            'task_id': task_id,
            'status': 'approved' if approved else 'rejected',
            'duration_ms': duration_ms,
            'cost_usd': 0.02
        })

        return approved
```

## Running Examples

### Success Workflow
```bash
python examples/event_streaming_example.py
```

### Failure Workflow
```bash
python examples/event_streaming_example.py --failure
```

### WebSocket Client
```bash
python examples/event_streaming_example.py --client
```

## Testing

Run the test suite:

```bash
pytest tests/test_event_stream.py -v
```

## Dependencies

Required:
- `redis` - For metrics storage

Optional:
- `websockets` - For WebSocket server functionality

Install all dependencies:
```bash
pip install redis websockets
```

## Architecture

```
EventEmitter
├── Destinations
│   ├── Console Logger (colored output)
│   ├── File Logger (JSONL)
│   └── WebSocket Server (real-time streaming)
│
├── MetricsAggregator
│   ├── In-memory counters
│   ├── Redis persistence
│   └── Time buckets (hourly/daily)
│
└── Event Processing
    ├── Event validation
    ├── Timestamp injection
    └── Async broadcasting
```

## Performance

- **Console**: <1ms per event
- **File**: <5ms per event (async writes)
- **WebSocket**: <10ms per event (broadcast to all clients)
- **Metrics**: Aggregated in-memory, flushed every 100 events

## Best Practices

1. **Always emit task_queued first** - This starts the completion time tracking
2. **Emit agent_started before work** - Essential for utilization metrics
3. **Emit agent_completed after work** - Include accurate duration and cost
4. **Record critic decisions** - Use `emitter.record_critic_decision()` for tracking
5. **Include all required fields** - Follow the event schema from observability.yaml
6. **Use structured payloads** - Helps with downstream analysis
7. **Emit validation_complete** - Critical for pass rate metrics

## Troubleshooting

### WebSocket server won't start
```bash
pip install websockets
# Or disable WebSocket in config
emitter = EventEmitter(websocket_enabled=False)
```

### Events not appearing in Redis
Check Redis connection:
```python
from agent_system.state.redis_client import RedisClient
client = RedisClient()
print(client.health_check())  # Should return True
```

### High memory usage
Flush metrics more frequently:
```python
emitter.metrics.flush_to_redis()
```

## License

Part of the SuperAgent project.
