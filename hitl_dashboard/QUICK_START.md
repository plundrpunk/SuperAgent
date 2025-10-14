# HITL Dashboard Quick Start Guide

Get the HITL Dashboard up and running in 5 minutes.

## Prerequisites

1. **Redis** must be running
2. **Python 3.8+** with SuperAgent dependencies
3. **SuperAgent** project properly configured

## Quick Start (3 Steps)

### Step 1: Start Redis

```bash
redis-server
```

Leave this running in a terminal.

### Step 2: Install Dependencies

```bash
cd /Users/rutledge/Documents/DevFolder/SuperAgent
pip install flask flask-cors
```

### Step 3: Start the Dashboard

```bash
cd hitl_dashboard
./start.sh
```

Or manually:
```bash
python server.py
```

Open your browser to: **http://localhost:5001**

## Testing with Sample Data

To populate the queue with sample tasks for testing:

```bash
cd hitl_dashboard
python test_populate.py
```

This adds 4 sample tasks with different priorities and scenarios.

## Basic Usage

### Viewing Tasks

1. Open http://localhost:5001
2. Tasks are sorted by priority (high to low)
3. Click any task card to see details

### Resolving a Task

1. Click on a task to open details
2. Scroll to the "Resolve Task" form
3. Fill in:
   - Root Cause (required)
   - Fix Strategy (required)
   - Severity (required)
   - Human Notes (required)
   - Patch/Diff (optional)
4. Click "Resolve Task"

### Viewing Resolved Tasks

1. Check the "Show Resolved Tasks" checkbox
2. Resolved tasks appear grayed out

## API Quick Reference

### Get Queue
```bash
curl http://localhost:5001/api/queue
```

### Get Task
```bash
curl http://localhost:5001/api/queue/task_001
```

### Resolve Task
```bash
curl -X POST http://localhost:5001/api/queue/task_001/resolve \
  -H "Content-Type: application/json" \
  -d '{
    "root_cause_category": "selector_flaky",
    "fix_strategy": "update_selectors",
    "severity": "medium",
    "human_notes": "Fixed selector to use data-testid"
  }'
```

### Get Stats
```bash
curl http://localhost:5001/api/queue/stats
```

## Troubleshooting

### Redis Connection Error

**Problem**: `Connection refused` error

**Solution**:
```bash
# Start Redis
redis-server

# Test Redis
redis-cli ping
# Should return: PONG
```

### Port Already in Use

**Problem**: Port 5001 already in use

**Solution**: Set custom port
```bash
export HITL_DASHBOARD_PORT=5002
python server.py
```

### No Tasks Showing

**Problem**: Dashboard is empty

**Solutions**:
1. Add test data: `python test_populate.py`
2. Check Redis: `redis-cli ZRANGE hitl:queue 0 -1`
3. Verify Redis connection in `.env`

### Import Errors

**Problem**: `ModuleNotFoundError`

**Solution**: Install dependencies
```bash
pip install -r requirements.txt
```

## File Structure

```
hitl_dashboard/
├── server.py              # Flask backend
├── start.sh               # Startup script
├── test_populate.py       # Test data generator
├── requirements.txt       # Python dependencies
├── README.md              # Full documentation
├── QUICK_START.md         # This file
└── static/
    ├── index.html         # Dashboard UI
    ├── styles.css         # Styles
    └── app.js             # Frontend logic
```

## Next Steps

1. **Read Full Docs**: See `README.md` for complete documentation
2. **Configure Production**: Set up proper WSGI server for production
3. **Integrate with Workflow**: Connect to Medic agent escalation flow
4. **Customize**: Modify UI/fields as needed

## Key Features

- Priority-based task sorting
- Real-time queue statistics
- Detailed task inspection
- Structured annotation system
- Screenshot viewing support
- Attempt history tracking
- Vector DB integration for learning

## Common Workflows

### Review High Priority Tasks

1. Open dashboard
2. High priority tasks (red badge) appear first
3. Focus on critical and high severity items

### Analyze Failure Patterns

1. Click on task to see details
2. Review "Attempt History" section
3. Check "AI Diagnosis" for insights
4. Review "Error Message" and "Code Changes"

### Provide Feedback for Learning

1. Resolve task with detailed notes
2. Include specific fix strategy
3. Add code patch if applicable
4. Annotation saved to vector DB for agent learning

## Integration Points

### With Medic Agent

Medic automatically escalates tasks when:
- Max retries exceeded (3 attempts)
- Regression detected
- AI confidence < 0.7

See `MEDIC_HITL_ESCALATION.md` for details.

### With Vector DB

Resolved annotations are stored for:
- Future pattern matching
- Fix strategy suggestions
- Root cause analysis

## Support

For issues:
1. Check troubleshooting section above
2. Review logs in terminal
3. Check Redis connection
4. Verify .env configuration

## Useful Commands

```bash
# Check Redis
redis-cli ping

# View all queue tasks
redis-cli ZRANGE hitl:queue 0 -1 WITHSCORES

# Clear all tasks (careful!)
redis-cli DEL hitl:queue

# View task details
redis-cli GET hitl:task:task_001

# Check server health
curl http://localhost:5001/api/health
```

## Environment Variables

```bash
# Redis configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=          # Optional

# Dashboard configuration
HITL_DASHBOARD_PORT=5001  # Default: 5001
```

## Additional Resources

- **Full Documentation**: `README.md`
- **HITL Workflow**: `../MEDIC_HITL_ESCALATION.md`
- **Queue Implementation**: `../agent_system/hitl/queue.py`
- **Schema**: `../agent_system/hitl/schema.json`

---

**Need Help?** Check the full README.md or review the troubleshooting section.
