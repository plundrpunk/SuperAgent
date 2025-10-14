# Observability System Quick Start Guide

## Installation

### 1. Install Dependencies

```bash
# Install required packages
pip install redis websockets

# Or install all project dependencies
pip install -r requirements.txt
```

### 2. Start Redis (for metrics storage)

```bash
# Using Docker
docker run -d -p 6379:6379 redis:latest

# Or using Homebrew (macOS)
brew install redis
brew services start redis

# Or using apt (Linux)
sudo apt-get install redis-server
sudo systemctl start redis
```

### 3. Verify Installation

```bash
# Test Redis connection
python3 -c "import redis; r = redis.Redis(); print('Redis OK' if r.ping() else 'Redis FAIL')"

# Test WebSocket support
python3 -c "import websockets; print('WebSockets OK')"
```

## Basic Usage

### Simple Console Logging

```python
from agent_system.observability import emit_event
import time

# Emit events - they'll appear in the console
emit_event('task_queued', {
    'task_id': 't_001',
    'feature': 'checkout',
    'est_cost': 0.45,
    'timestamp': time.time()
})

emit_event('agent_started', {
    'agent': 'scribe',
    'task_id': 't_001',
    'model': 'claude-sonnet-4.5',
    'tools': ['read', 'write', 'edit']
})

emit_event('agent_completed', {
    'agent': 'scribe',
    'task_id': 't_001',
    'status': 'success',
    'duration_ms': 2500,
    'cost_usd': 0.12
})
```

### Enable WebSocket Streaming

```python
import asyncio
from agent_system.observability import get_emitter, emit_event

async def main():
    # Get the emitter and start WebSocket server
    emitter = get_emitter()
    await emitter.start()

    print("WebSocket server running on ws://localhost:3010")

    # Emit events
    emit_event('task_queued', {
        'task_id': 't_001',
        'feature': 'checkout',
        'est_cost': 0.45,
        'timestamp': time.time()
    })

    # Keep server running
    await asyncio.sleep(3600)  # Run for 1 hour

asyncio.run(main())
```

### Connect WebSocket Client

In a separate terminal or browser:

```python
import asyncio
import websockets
import json

async def listen():
    async with websockets.connect('ws://localhost:3010') as ws:
        print("Connected to event stream!")
        async for message in ws:
            event = json.loads(message)
            print(f"[{event['event_type']}]")
            print(f"  {event['payload']}")

asyncio.run(listen())
```

Or use a browser console:

```javascript
const ws = new WebSocket('ws://localhost:3010');
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log(data.event_type, data.payload);
};
```

## Running Examples

### 1. Run Success Workflow Example

```bash
cd /Users/rutledge/Documents/DevFolder/SuperAgent
python3 examples/event_streaming_example.py
```

This demonstrates a complete task workflow:
- Task queued
- Scribe writes test
- Critic reviews
- Runner executes
- Gemini validates
- Metrics calculated

### 2. Run Failure Workflow Example

```bash
python3 examples/event_streaming_example.py --failure
```

This demonstrates failure handling:
- Task fails
- Medic attempts fixes
- Multiple retries
- HITL escalation
- Budget tracking

### 3. Run WebSocket Client

In one terminal:
```bash
# Start the event server
python3 examples/event_streaming_example.py
```

In another terminal:
```bash
# Connect client to watch events
python3 examples/event_streaming_example.py --client
```

## Integration with Agents

### Example: Scribe Agent Integration

```python
from agent_system.observability import emit_event
import time

class ScribeAgent:
    def __init__(self):
        self.agent_name = 'scribe'
        self.model = 'claude-sonnet-4.5'

    def write_test(self, task_id: str, feature: str):
        """Write a Playwright test with event tracking."""
        start_time = time.time()

        # 1. Emit agent started event
        emit_event('agent_started', {
            'agent': self.agent_name,
            'task_id': task_id,
            'model': self.model,
            'tools': ['read', 'write', 'edit', 'grep']
        })

        try:
            # 2. Do the actual work
            test_code = self._generate_test_code(feature)
            self._write_test_file(task_id, test_code)

            # 3. Calculate metrics
            duration_ms = int((time.time() - start_time) * 1000)
            cost = self._calculate_cost(duration_ms)

            # 4. Emit completion event
            emit_event('agent_completed', {
                'agent': self.agent_name,
                'task_id': task_id,
                'status': 'success',
                'duration_ms': duration_ms,
                'cost_usd': cost
            })

            return test_code

        except Exception as e:
            # 5. Emit failure event
            duration_ms = int((time.time() - start_time) * 1000)
            emit_event('agent_completed', {
                'agent': self.agent_name,
                'task_id': task_id,
                'status': 'failed',
                'duration_ms': duration_ms,
                'cost_usd': 0.0
            })
            raise

    def _generate_test_code(self, feature):
        # Implementation...
        return "test code"

    def _write_test_file(self, task_id, code):
        # Implementation...
        pass

    def _calculate_cost(self, duration_ms):
        # Simple cost estimation based on model and duration
        return 0.12  # Example
```

### Example: Critic Agent Integration

```python
from agent_system.observability import emit_event, get_emitter
import time

class CriticAgent:
    def review_test(self, task_id: str, test_path: str):
        """Review test quality and emit events."""
        start_time = time.time()

        # Emit started
        emit_event('agent_started', {
            'agent': 'critic',
            'task_id': task_id,
            'model': 'claude-haiku',
            'tools': ['read', 'grep']
        })

        # Review the test
        approved = self._check_test_quality(test_path)

        # Record decision for metrics
        emitter = get_emitter()
        emitter.record_critic_decision(rejected=not approved)

        # Emit completion
        duration_ms = int((time.time() - start_time) * 1000)
        emit_event('agent_completed', {
            'agent': 'critic',
            'task_id': task_id,
            'status': 'approved' if approved else 'rejected',
            'duration_ms': duration_ms,
            'cost_usd': 0.02
        })

        return approved
```

## Viewing Metrics

### Get Current Metrics

```python
from agent_system.observability import get_emitter

emitter = get_emitter()
metrics = emitter.get_metrics()

print(f"Agent utilization: {metrics['agent_utilization']:.2%}")
print(f"Cost per feature: ${metrics['cost_per_feature']:.2f}")
print(f"Average retries: {metrics['average_retry_count']:.1f}")
print(f"Critic rejection rate: {metrics['critic_rejection_rate']:.2%}")
print(f"Validation pass rate: {metrics['validation_pass_rate']:.2%}")
print(f"Time to completion: {metrics['time_to_completion']:.1f}s")
```

### View Metrics from Redis

```python
from agent_system.state.redis_client import RedisClient
from datetime import datetime

redis_client = RedisClient()

# Get today's metrics
today = datetime.now().strftime('%Y-%m-%d')
daily_metrics = redis_client.get(f"metrics:daily:{today}")

if daily_metrics:
    print("Today's metrics:")
    for key, value in daily_metrics.items():
        print(f"  {key}: {value:.4f}")
```

## Viewing Logs

### Console Output

Events are automatically printed to console with colors:

```
[14:23:15] TASK_QUEUED
  task_id: t_001
  feature: checkout
  est_cost: 0.45

[14:23:16] AGENT_STARTED
  agent: scribe
  task_id: t_001
  model: claude-sonnet-4.5
```

### JSONL Log File

Events are written to `logs/agent-events.jsonl`:

```bash
# View last 10 events
tail -n 10 logs/agent-events.jsonl | jq

# Watch events in real-time
tail -f logs/agent-events.jsonl | jq

# Filter by event type
grep "task_queued" logs/agent-events.jsonl | jq

# Count events by type
cat logs/agent-events.jsonl | jq -r '.event_type' | sort | uniq -c
```

## Testing

### Run Unit Tests

```bash
# Run all tests
pytest tests/test_event_stream.py -v

# Run standalone tests (no dependencies required)
python3 tests/test_event_stream_standalone.py
```

### Manual Testing

```bash
# Test console output
python3 -c "
from agent_system.observability import emit_event
import time

emit_event('task_queued', {
    'task_id': 't_test',
    'feature': 'test',
    'est_cost': 0.10,
    'timestamp': time.time()
})
"

# Test file logging
python3 -c "
from agent_system.observability import emit_event
import time

emit_event('task_queued', {'task_id': 't_test', 'timestamp': time.time()})
" && cat logs/agent-events.jsonl | tail -1 | jq
```

## Configuration

### Environment Variables

```bash
# Redis configuration
export REDIS_HOST=localhost
export REDIS_PORT=6379
export REDIS_PASSWORD=your_password  # Optional
export REDIS_DB=0

# Observability settings
export OBSERVABILITY_WEBSOCKET_PORT=3010
export OBSERVABILITY_LOG_PATH=logs/agent-events.jsonl
```

### Custom Configuration

```python
from agent_system.observability.event_stream import EventEmitter, LogLevel
from agent_system.state.redis_client import RedisClient

# Custom emitter
emitter = EventEmitter(
    websocket_enabled=True,
    websocket_port=3010,
    console_enabled=True,
    console_level=LogLevel.INFO,
    file_enabled=True,
    file_path='logs/custom-events.jsonl',
    redis_client=RedisClient()
)

# Start it
import asyncio
asyncio.run(emitter.start())
```

## Troubleshooting

### WebSocket Server Won't Start

```bash
# Check if websockets is installed
python3 -c "import websockets; print('OK')"

# If not, install it
pip install websockets

# Check if port is in use
lsof -i :3010
```

### Redis Connection Failed

```bash
# Check if Redis is running
redis-cli ping

# Should return "PONG"

# If not running, start it
brew services start redis  # macOS
sudo systemctl start redis  # Linux
```

### Events Not Appearing

```python
# Verify emitter is initialized
from agent_system.observability import get_emitter

emitter = get_emitter()
print(f"Console enabled: {emitter.console_enabled}")
print(f"File enabled: {emitter.file_enabled}")
print(f"WebSocket enabled: {emitter.websocket_enabled}")

# Try emitting a test event
from agent_system.observability import emit_event
import time

emit_event('task_queued', {
    'task_id': 't_debug',
    'feature': 'debug_test',
    'est_cost': 0.01,
    'timestamp': time.time()
})
```

### Import Errors

```bash
# Make sure you're in the project directory
cd /Users/rutledge/Documents/DevFolder/SuperAgent

# Run with correct path
python3 -c "from agent_system.observability import emit_event; print('OK')"

# If still failing, check Python path
python3 -c "import sys; print(sys.path)"
```

## Next Steps

1. **Integrate with your agents**: Add event emission to Scribe, Runner, Medic, Critic, and Gemini
2. **Build a dashboard**: Create a web UI that connects to the WebSocket stream
3. **Set up alerts**: Configure alerts for high rejection rates, budget warnings, etc.
4. **Analyze logs**: Use the JSONL logs for post-mortem analysis and debugging

## Additional Resources

- Full documentation: `agent_system/observability/README.md`
- Event schema: `.claude/observability.yaml`
- Example integrations: `examples/event_streaming_example.py`
- Test suite: `tests/test_event_stream.py`
