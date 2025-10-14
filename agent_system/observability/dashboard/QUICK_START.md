# SuperAgent Observability Dashboard - Quick Start Guide

## Overview

The SuperAgent Observability Dashboard provides real-time monitoring of the multi-agent testing system through WebSocket event streaming. Monitor agent activity, cost tracking, test metrics, and system events in a modern, responsive web interface.

## Features

- **Real-Time WebSocket Updates**: Live streaming of agent events
- **Cost Tracking**: Current spend, budget, remaining balance with visual progress bar
- **Agent Status Cards**: Monitor all 6 agents (Kaya, Scribe, Runner, Medic, Critic, Gemini)
- **Active Tasks**: Track tasks in progress with status and cost
- **System Metrics**: Test pass rate, critic rejection rate, HITL queue depth, etc.
- **Event Timeline**: Scrolling timeline of recent events (up to 50)
- **Auto-Reconnection**: Automatic WebSocket reconnection on disconnect
- **Responsive Design**: Works on desktop, tablet, and mobile

## Quick Start

### Prerequisites

1. Python 3.10+ with SuperAgent installed
2. WebSocket server running (event_stream.py)
3. Modern web browser (Chrome, Firefox, Safari, Edge)

### Step 1: Start the WebSocket Event Server

Run the WebSocket event streaming server:

```bash
# From the SuperAgent root directory
python -m agent_system.observability.event_stream
```

You should see:
```
WebSocket server started on ws://localhost:3010/agent-events
```

The server:
- Listens on `ws://localhost:3010/agent-events`
- Emits events to console, file (`logs/agent-events.jsonl`), and WebSocket clients
- Automatically handles client connections/disconnections

### Step 2: Open the Dashboard

Open the dashboard in your web browser:

```bash
# Option 1: Open directly in browser
open agent_system/observability/dashboard/index.html

# Option 2: Serve via Python HTTP server
cd agent_system/observability/dashboard
python -m http.server 8080
# Then open: http://localhost:8080
```

The dashboard will:
1. Automatically connect to `ws://localhost:3010/agent-events`
2. Display connection status (green = connected, red = disconnected)
3. Start receiving and displaying events in real-time

### Step 3: Generate Test Events

To see the dashboard in action, generate some test events:

```bash
# Run the example event generator
python agent_system/observability/event_stream.py
```

This will emit sample events:
- Task queued
- Agent started (Scribe)
- Agent completed
- Validation complete
- Budget warning

Watch the dashboard update in real-time as events are received!

## Dashboard Sections

### 1. Cost Tracking

**Location**: Top section
**Updates**: Real-time on cost events

Displays:
- **Current Spend**: Total accumulated cost ($)
- **Budget**: Cost limit ($)
- **Remaining**: Budget - Current Spend ($)
- **% Used**: Visual progress bar showing budget consumption

Color coding:
- Green (0-70%): Healthy
- Yellow (70-90%): Warning zone
- Red (90-100%): Critical

### 2. Agent Status Cards

**Location**: Second section
**Updates**: Real-time on agent events

Shows for each agent:
- **Status Badge**: Idle (green) or Active (orange with pulse animation)
- **Model**: AI model used (Haiku, Sonnet 4.5, Gemini 2.5 Pro)
- **Tasks**: Total tasks completed
- **Cost**: Accumulated cost for this agent

Agents:
- **Kaya** (Purple): Router/Orchestrator
- **Scribe** (Blue): Test Writer
- **Runner** (Green): Test Executor
- **Medic** (Red): Bug Fixer
- **Critic** (Orange): Pre-Validator
- **Gemini** (Purple): Validator

### 3. Active Tasks

**Location**: Third section
**Updates**: Real-time on task events

Displays currently running tasks:
- **Task ID**: Unique identifier
- **Feature**: Feature being tested
- **Status**: queued → running → passed/failed/escalated
- **Agent**: Which agent is handling it
- **Cost**: Actual cost incurred
- **Est. Cost**: Estimated cost
- **Duration**: Time since task started

Status colors:
- Blue: Queued
- Green: Running/Passed
- Red: Failed
- Orange: Escalated to HITL

### 4. Metrics

**Location**: Fourth section
**Updates**: Every 5 seconds (auto-refresh)

Key metrics:
- **Test Pass Rate**: % of tests passing validation
- **Critic Rejection Rate**: % of tests rejected by Critic
- **Avg Completion Time**: Average time from queue to completion
- **Avg Retry Count**: Average number of retries per task
- **HITL Queue Depth**: Number of tasks awaiting human review
- **Agent Utilization**: % of time agents are active

### 5. Event Timeline

**Location**: Bottom section
**Updates**: Real-time on any event

Scrolling timeline showing last 50 events:
- **Event Type**: Formatted event name
- **Timestamp**: Time event occurred
- **Details**: All event payload fields

Event types (color-coded):
- **Task Queued** (Blue): New task added
- **Agent Started** (Green): Agent begins work
- **Agent Completed** (Blue): Agent finishes
- **Validation Complete** (Purple): Gemini validation result
- **HITL Escalated** (Orange): Task needs human review
- **Budget Warning/Exceeded** (Red): Cost alerts

Controls:
- **Clear Events**: Remove all events from timeline

## Integration with Your Agents

To emit events from your agent code:

```python
from agent_system.observability.event_stream import emit_event
import time

# Task queued
emit_event('task_queued', {
    'task_id': 't_001',
    'feature': 'user_login',
    'est_cost': 0.35,
    'timestamp': time.time()
})

# Agent started
emit_event('agent_started', {
    'agent': 'scribe',
    'task_id': 't_001',
    'model': 'claude-sonnet-4.5',
    'tools': ['read', 'write', 'edit']
})

# Agent completed
emit_event('agent_completed', {
    'agent': 'scribe',
    'task_id': 't_001',
    'status': 'success',
    'duration_ms': 2500,
    'cost_usd': 0.12
})

# Validation complete
emit_event('validation_complete', {
    'task_id': 't_001',
    'result': {
        'browser_launched': True,
        'test_executed': True,
        'test_passed': True
    },
    'cost': 0.08,
    'duration_ms': 5000,
    'screenshots': 2
})

# HITL escalated
emit_event('hitl_escalated', {
    'task_id': 't_001',
    'attempts': 3,
    'last_error': 'Selector timeout',
    'priority': 0.75
})

# Budget warning
emit_event('budget_warning', {
    'current_spend': 0.85,
    'limit': 1.00,
    'remaining': 0.15
})
```

## Configuration

### WebSocket URL

Default: `ws://localhost:3010/agent-events`

To change, edit `app.js`:
```javascript
const WEBSOCKET_URL = 'ws://your-host:your-port/agent-events';
```

### Metrics Refresh Interval

Default: 5 seconds

To change, edit `app.js`:
```javascript
const METRICS_REFRESH_INTERVAL = 10000; // 10 seconds
```

### Max Events Display

Default: 50 events

To change, edit `app.js`:
```javascript
const MAX_EVENTS_DISPLAY = 100; // Show 100 events
```

### Cost Budget

Default: $10.00

The budget is tracked server-side, but you can display a different default in the UI by editing `app.js`:
```javascript
const state = {
    costs: {
        current: 0,
        budget: 50.0, // Change to your budget
        remaining: 50.0
    },
    // ...
};
```

## Troubleshooting

### Dashboard shows "Disconnected"

1. **Check WebSocket server is running**:
   ```bash
   # Should see: WebSocket server started on ws://localhost:3010/agent-events
   python -m agent_system.observability.event_stream
   ```

2. **Check port is available**:
   ```bash
   lsof -i :3010
   ```

3. **Check browser console** (F12 → Console):
   - Look for WebSocket connection errors
   - Check CORS or network issues

4. **Firewall/Security**: Ensure localhost WebSocket connections are allowed

### No events showing

1. **Verify events are being emitted**:
   - Check console output (if `console_enabled=True`)
   - Check log file: `logs/agent-events.jsonl`

2. **Check event format**: Events must match schema in `.claude/observability.yaml`

3. **Browser console**: Look for JavaScript errors processing events

### Metrics not updating

1. **Check auto-refresh**: Metrics update every 5 seconds
2. **Verify events are being received**: Check Event Timeline
3. **Check browser console**: Look for metric calculation errors

### Styling issues

1. **Ensure CSS is loaded**: Check Network tab in browser DevTools
2. **Clear browser cache**: Hard refresh (Ctrl+Shift+R / Cmd+Shift+R)
3. **Check file paths**: CSS must be in same directory as HTML

## File Structure

```
agent_system/observability/dashboard/
├── index.html          # Main dashboard HTML
├── styles.css          # Dashboard styling
├── app.js              # WebSocket client and UI logic
├── QUICK_START.md      # This file
└── README.md           # Detailed documentation (if exists)
```

## Production Deployment

For production use:

1. **Use a proper web server** (nginx, Apache, or Node.js):
   ```bash
   # Example with nginx
   server {
       listen 80;
       server_name monitoring.example.com;
       root /path/to/SuperAgent/agent_system/observability/dashboard;
       index index.html;
   }
   ```

2. **Secure WebSocket connection** (WSS):
   - Use TLS/SSL certificates
   - Update `WEBSOCKET_URL` to `wss://your-domain/agent-events`

3. **Authentication**: Add authentication layer to WebSocket server

4. **Monitoring**: Monitor WebSocket server uptime and performance

5. **Logging**: Configure log rotation and archival

## Advanced Features

### Export Events

Events are logged to `logs/agent-events.jsonl`. Parse with:

```python
import json

with open('logs/agent-events.jsonl', 'r') as f:
    for line in f:
        event = json.loads(line)
        print(event)
```

### Custom Event Types

Add custom event types by:

1. Update `.claude/observability.yaml`
2. Emit events with `emit_event('custom_event_type', {...})`
3. Dashboard will automatically display them

### Metrics API

For advanced integrations, access metrics via Redis:

```python
from agent_system.state.redis_client import RedisClient

redis = RedisClient()
metrics = redis.get('metrics:hourly:2025-10-14T14:00:00')
print(metrics)
```

## Support

For issues or questions:
- Check logs: `logs/agent-events.jsonl`
- Review event_stream.py for server-side issues
- Check browser console for client-side issues
- Refer to `.claude/observability.yaml` for event schema

## Next Steps

1. **Integrate with HITL Dashboard**: Link to HITL queue for human review
2. **Add Alerts**: Configure email/Slack alerts for critical events
3. **Historical Data**: Add time-series charts for metrics over time
4. **Export Reports**: Add PDF/CSV export for metrics and events
5. **Custom Dashboards**: Create role-specific views (QA, DevOps, Management)

---

**Version**: 1.0
**Last Updated**: 2025-10-14
**Maintained by**: SuperAgent Team
