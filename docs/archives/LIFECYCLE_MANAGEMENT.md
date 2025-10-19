# Lifecycle Management and Graceful Shutdown

This document describes SuperAgent's lifecycle management system for graceful startup, health monitoring, and shutdown.

## Overview

The `ServiceLifecycle` class manages the complete lifecycle of SuperAgent, ensuring:
- Clean startup with connection registration
- Health status monitoring
- Graceful shutdown on SIGTERM/SIGINT
- Active task completion tracking
- Resource cleanup (Redis, Vector DB, WebSocket)
- Orphaned task detection and recovery

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  ServiceLifecycle                        │
├─────────────────────────────────────────────────────────┤
│  Signal Handlers (SIGTERM, SIGINT)                       │
│  ├── Stop accepting new tasks                            │
│  ├── Wait for active tasks (timeout: 30s)                │
│  ├── Call shutdown callbacks                             │
│  ├── Close connections (Redis, Vector DB, WebSocket)     │
│  └── Flush logs                                           │
├─────────────────────────────────────────────────────────┤
│  Active Task Tracking                                    │
│  ├── add_active_task()                                   │
│  ├── remove_active_task()                                │
│  └── is_shutting_down()                                  │
├─────────────────────────────────────────────────────────┤
│  Connection Registry                                     │
│  ├── register_connection()                               │
│  ├── unregister_connection()                             │
│  └── close() all on shutdown                             │
├─────────────────────────────────────────────────────────┤
│  Health Monitoring                                       │
│  ├── get_health_status()                                 │
│  ├── check_orphaned_tasks()                              │
│  └── recover_orphaned_tasks()                            │
└─────────────────────────────────────────────────────────┘
```

## Usage

### Basic Setup

```python
from agent_system.lifecycle import setup_lifecycle

# Set up lifecycle with signal handlers
lifecycle = setup_lifecycle()

# Register connections
lifecycle.register_connection("redis", redis_client)
lifecycle.register_connection("vector_db", vector_client)

# Mark service as started
lifecycle.mark_started()

# Your application code...
```

### Tracking Active Tasks

```python
# Before starting a task
if not lifecycle.can_accept_tasks():
    return AgentResult(
        success=False,
        error="Service is shutting down"
    )

# Track the task
task_id = "task_123"
lifecycle.add_active_task(
    task_id,
    agent="scribe",
    feature="login"
)

try:
    # Do work...
    pass
finally:
    # Always remove task when done
    lifecycle.remove_active_task(task_id)
```

### Shutdown Callbacks

```python
def on_shutdown():
    print("Performing cleanup...")
    # Custom cleanup logic

lifecycle.add_shutdown_callback(on_shutdown)
```

### Health Check

```python
# Get current health status
health = lifecycle.get_health_status()

print(f"Status: {health['status']}")
print(f"Active Tasks: {health['active_tasks']}")
print(f"Uptime: {health['uptime_seconds']}s")

# Check connections
for name, status in health['connections']['status'].items():
    print(f"{name}: {'✓' if status['healthy'] else '✗'}")
```

## CLI Commands

### Health Check

```bash
# Show service health and connection status
python agent_system/cli.py health
```

Output:
```
✓ Service Health Status

Status: HEALTHY
Uptime: 125.45s
Active Tasks: 2
Can Accept Tasks: Yes

Connections (3):
  ✓ redis: healthy
  ✓ vector_db: healthy
  ✓ websocket: healthy
```

### Status

```bash
# Show system components and capabilities
python agent_system/cli.py status
```

## Docker Integration

### Docker Compose Configuration

The `docker-compose.yml` includes graceful shutdown settings:

```yaml
superagent:
  # Graceful shutdown configuration
  stop_signal: SIGTERM
  stop_grace_period: 45s
```

This gives SuperAgent 45 seconds to:
1. Stop accepting new tasks
2. Complete active tasks
3. Close connections
4. Flush logs

### Testing Docker Shutdown

```bash
# Start services
docker compose up -d

# Watch logs in real-time
docker compose logs -f superagent

# Trigger graceful shutdown
docker compose down

# Expected output:
# ServiceLifecycle: Received signal SIGTERM (15), initiating graceful shutdown
# ServiceLifecycle: Waiting for 2 active task(s) to complete...
# ServiceLifecycle: All active tasks completed successfully
# ServiceLifecycle: Closing 3 connection(s)
# ServiceLifecycle: Service shutdown complete
```

## Orphaned Task Recovery

When SuperAgent crashes or is forcefully terminated, tasks may be left in an incomplete state. The lifecycle system detects and recovers these orphaned tasks.

### Detection

```python
from agent_system.state.redis_client import RedisClient

redis_client = RedisClient()
lifecycle = get_lifecycle()

# Check for orphaned tasks
orphaned = lifecycle.check_orphaned_tasks(redis_client)

if orphaned:
    print(f"Found {len(orphaned)} orphaned task(s)")
    for task in orphaned:
        print(f"  - {task['task_id']}: {task['status']}")
```

### Recovery Options

#### Option 1: Reset to Failed (can be retried)

```python
lifecycle.recover_orphaned_tasks(redis_client, orphaned)
# Tasks are marked as "failed" and can be retried
```

#### Option 2: Clear Completely

```python
lifecycle.clear_orphaned_tasks(redis_client, orphaned)
# Tasks are removed from Redis entirely
```

### Automatic Recovery on Startup

Add to your startup sequence:

```python
# At startup
lifecycle = setup_lifecycle()
lifecycle.mark_started()

# Register connections
redis_client = RedisClient()
lifecycle.register_connection("redis", redis_client)

# Check for orphaned tasks from previous crash
orphaned = lifecycle.check_orphaned_tasks(redis_client)
if orphaned:
    logger.warning(f"Recovering {len(orphaned)} orphaned tasks")
    lifecycle.recover_orphaned_tasks(redis_client, orphaned)
```

## Connection Management

### Supported Close Methods

The lifecycle system supports different close methods for various connection types:

```python
# Redis (default: "close")
lifecycle.register_connection("redis", redis_client)

# Vector DB (default: "close")
lifecycle.register_connection("vector_db", vector_client)

# WebSocket (custom: "stop")
lifecycle.register_connection(
    "websocket",
    websocket_server,
    close_method="stop"
)

# Custom connection (with metadata)
lifecycle.register_connection(
    "custom_service",
    custom_client,
    close_method="shutdown",
    metadata={"type": "api_client", "timeout": 10}
)
```

### Connection Health Checks

Connections are health-checked during status queries:

```python
class MyConnection:
    def health_check(self) -> bool:
        """Return True if connection is healthy."""
        try:
            # Perform health check
            return True
        except Exception:
            return False
```

Supported health check methods (tried in order):
1. `health_check()` - Custom health check method
2. `ping()` - Common for Redis, databases

## Service States

The lifecycle system tracks service through these states:

1. **STARTING** - Initial state, not ready for tasks
2. **HEALTHY** - Started and accepting tasks
3. **DEGRADED** - Running but with issues
4. **SHUTTING_DOWN** - Shutdown in progress
5. **STOPPED** - Shutdown complete

```python
from agent_system.lifecycle import ServiceStatus

lifecycle = ServiceLifecycle()

# Check current state
if lifecycle.status == ServiceStatus.HEALTHY:
    print("Service is healthy")

# Or use convenience methods
if lifecycle.can_accept_tasks():
    # Process new task
    pass
```

## Production Best Practices

### 1. Always Use Signal Handlers

```python
# In main entry point
lifecycle = setup_lifecycle()  # Registers SIGTERM, SIGINT
```

### 2. Track All Long-Running Operations

```python
# Track any operation that takes > 1 second
task_id = generate_task_id()
lifecycle.add_active_task(task_id, agent="scribe", feature=feature_name)

try:
    result = perform_long_operation()
finally:
    lifecycle.remove_active_task(task_id)
```

### 3. Set Appropriate Timeouts

```python
# For most services: 30 seconds
lifecycle.shutdown(timeout=30)

# For long-running tasks: 60+ seconds
lifecycle.shutdown(timeout=60)

# For quick services: 10 seconds
lifecycle.shutdown(timeout=10)
```

### 4. Register All External Connections

```python
# Register every connection that needs cleanup
lifecycle.register_connection("redis", redis_client)
lifecycle.register_connection("vector_db", vector_client)
lifecycle.register_connection("event_stream", event_emitter)
lifecycle.register_connection("api_client", api_client)
```

### 5. Implement Health Checks

```python
# Regular health monitoring
import schedule

def check_health():
    health = lifecycle.get_health_status()
    if health['status'] != 'healthy':
        alert_ops_team(health)

schedule.every(1).minute.do(check_health)
```

## Testing

### Unit Tests

Run lifecycle tests:

```bash
pytest tests/unit/test_lifecycle.py -v
```

Key test scenarios:
- ✓ Graceful shutdown with active tasks
- ✓ Shutdown timeout behavior
- ✓ Connection cleanup
- ✓ Signal handler registration
- ✓ Orphaned task detection and recovery

### Integration Tests

Test with real services:

```bash
# Start Redis and Vector DB
docker compose up -d redis

# Run integration test
pytest tests/integration/test_lifecycle_integration.py -v
```

### Manual Testing

```bash
# Terminal 1: Start service
python agent_system/cli.py kaya "create test for login"

# Terminal 2: Trigger shutdown while task is running
docker compose down

# Observe:
# - Task completion wait
# - Connection cleanup
# - Clean exit
```

## Troubleshooting

### Issue: Tasks Not Completing During Shutdown

**Symptom**: Shutdown times out waiting for tasks

**Solution**:
1. Check shutdown timeout is sufficient
2. Verify tasks check `lifecycle.is_shutting_down()`
3. Add logging to track task progress

```python
while not lifecycle.is_shutting_down():
    # Perform work in chunks
    process_next_chunk()
```

### Issue: Connections Not Closing

**Symptom**: Resources leak, connections remain open

**Solution**:
1. Verify `close()` method exists on connection object
2. Check close_method parameter matches actual method name
3. Add error handling to close methods

```python
class MyClient:
    def close(self):
        try:
            self.connection.close()
        except Exception as e:
            logger.error(f"Error closing connection: {e}")
```

### Issue: Orphaned Tasks Persist

**Symptom**: Same orphaned tasks detected on every startup

**Solution**:
1. Ensure orphan recovery is called at startup
2. Verify Redis is persisting data
3. Check task status TTL settings

```python
# At startup
orphaned = lifecycle.check_orphaned_tasks(redis_client)
if orphaned:
    lifecycle.clear_orphaned_tasks(redis_client, orphaned)
```

### Issue: Docker Shutdown Takes Full Grace Period

**Symptom**: `docker compose down` always waits 45 seconds

**Solution**:
1. Ensure signal handlers are registered
2. Check that main process handles signals correctly
3. Verify shutdown logic completes

```python
# Ensure signal handlers are set up early
lifecycle = setup_lifecycle()  # Must be called in main()
```

## Monitoring

### Health Endpoint

Expose health status via HTTP (add to observability dashboard):

```python
from fastapi import FastAPI
from agent_system.lifecycle import get_lifecycle

app = FastAPI()

@app.get("/health")
def health_check():
    lifecycle = get_lifecycle()
    return lifecycle.get_health_status()
```

Response:
```json
{
  "status": "healthy",
  "uptime_seconds": 1234.56,
  "active_tasks": 2,
  "connections": {
    "count": 3,
    "status": {
      "redis": {"healthy": true, "registered_at": 1234567890.0},
      "vector_db": {"healthy": true, "registered_at": 1234567890.5}
    }
  },
  "can_accept_tasks": true,
  "shutdown_in_progress": false,
  "timestamp": 1234567890.0
}
```

### Metrics

Track lifecycle metrics:

```python
# In observability system
from agent_system.observability import emit_event

# Emit shutdown event
emit_event('service_shutdown', {
    'active_tasks_at_shutdown': len(lifecycle.active_tasks),
    'shutdown_duration_ms': shutdown_duration,
    'clean_shutdown': True
})
```

## Future Enhancements

Planned improvements:

1. **Readiness Probes**: Separate ready vs alive checks
2. **Graceful Degradation**: Continue with reduced capacity
3. **Shutdown Hooks**: Pre/post shutdown hooks for agents
4. **Task Priority**: Complete high-priority tasks first
5. **Connection Pooling**: Better connection lifecycle management
6. **Distributed Coordination**: Multi-instance shutdown coordination

## References

- Docker stop signal handling: https://docs.docker.com/engine/reference/commandline/stop/
- Python signal handling: https://docs.python.org/3/library/signal.html
- Graceful shutdown patterns: https://cloud.google.com/blog/products/containers-kubernetes/kubernetes-best-practices-terminating-with-grace

---

**Last Updated**: 2025-10-14
**Author**: SuperAgent Team
