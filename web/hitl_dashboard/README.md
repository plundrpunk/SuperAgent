# HITL Dashboard

A web-based Human-in-the-Loop (HITL) dashboard for managing escalated test failures in the SuperAgent system.

## Overview

The HITL Dashboard provides a user-friendly interface for human reviewers to:
- View all escalated tasks sorted by priority
- Examine detailed test failure information
- Review error messages, logs, and screenshots
- Annotate tasks with root cause analysis and fix strategies
- Mark tasks as resolved for agent learning

## Architecture

### Backend (Flask)
- **File**: `server.py`
- **Port**: 5001 (configurable via `HITL_DASHBOARD_PORT`)
- **API Endpoints**:
  - `GET /api/queue` - List all tasks in queue
  - `GET /api/queue/stats` - Get queue statistics
  - `GET /api/queue/<task_id>` - Get specific task details
  - `POST /api/queue/<task_id>/resolve` - Resolve task with annotation
  - `GET /api/health` - Health check endpoint

### Frontend (Vanilla JS)
- **Files**: `static/index.html`, `static/styles.css`, `static/app.js`
- **Features**:
  - Responsive design for desktop use
  - Real-time task list with priority badges
  - Modal-based task detail view
  - Annotation form with validation
  - Auto-refresh capability

## Installation

### 1. Install Dependencies

```bash
cd /Users/rutledge/Documents/DevFolder/SuperAgent
pip install flask flask-cors
```

Or add to `requirements.txt`:
```
flask>=2.3.0
flask-cors>=4.0.0
```

### 2. Configure Environment

Make sure your `.env` file has Redis configuration:
```bash
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=  # Optional

# Optional: Custom dashboard port
HITL_DASHBOARD_PORT=5001
```

### 3. Start Redis

The dashboard requires Redis to be running:
```bash
redis-server
```

## Usage

### Starting the Dashboard

```bash
cd /Users/rutledge/Documents/DevFolder/SuperAgent/hitl_dashboard
python server.py
```

The dashboard will start on `http://localhost:5001`

### Using the Dashboard

1. **View Queue**
   - Open `http://localhost:5001` in your browser
   - Tasks are sorted by priority (highest first)
   - Priority badges: High (red), Medium (yellow), Low (blue)

2. **View Task Details**
   - Click on any task card to see full details
   - View error messages, logs, and attempt history
   - See AI diagnosis and code changes

3. **Resolve Tasks**
   - In the task detail modal, fill out the annotation form:
     - **Root Cause Category**: What caused the failure?
     - **Fix Strategy**: How should it be fixed?
     - **Severity**: How critical is this issue?
     - **Human Notes**: Detailed analysis and findings
     - **Patch/Diff**: Optional code changes applied
   - Click "Resolve Task" to save

4. **View Resolved Tasks**
   - Check "Show Resolved Tasks" to include resolved items
   - Resolved tasks appear grayed out with a "Resolved" badge

## API Usage

### List Tasks
```bash
curl http://localhost:5001/api/queue
```

### Get Task Details
```bash
curl http://localhost:5001/api/queue/<task_id>
```

### Resolve Task
```bash
curl -X POST http://localhost:5001/api/queue/<task_id>/resolve \
  -H "Content-Type: application/json" \
  -d '{
    "root_cause_category": "selector_flaky",
    "fix_strategy": "update_selectors",
    "severity": "medium",
    "human_notes": "Updated data-testid selectors...",
    "patch_diff": "Optional diff content"
  }'
```

### Get Statistics
```bash
curl http://localhost:5001/api/queue/stats
```

## Task Schema

Tasks in the queue follow this structure:

```json
{
  "task_id": "task_123",
  "feature": "checkout flow",
  "code_path": "tests/checkout.spec.ts",
  "logs_path": "logs/test_execution.log",
  "screenshots": ["path/to/screenshot1.png"],
  "attempts": 3,
  "last_error": "Error: Selector not found...",
  "priority": 0.75,
  "severity": "high",
  "escalation_reason": "max_retries_exceeded",
  "created_at": "2025-10-14T12:00:00Z",
  "resolved": false
}
```

## Annotation Categories

### Root Cause Categories
- `selector_flaky` - Selector is unreliable or changed
- `timing_race_condition` - Timing issues or race conditions
- `data_dependency` - Test data issues
- `environment_config` - Environment configuration problems
- `api_contract_changed` - API contract changed
- `browser_compatibility` - Browser-specific issues
- `authentication_issue` - Auth/login problems
- `unknown` - Unknown root cause

### Fix Strategies
- `update_selectors` - Update element selectors
- `add_explicit_waits` - Add wait conditions
- `mock_external_api` - Mock external dependencies
- `fix_test_data` - Fix test data
- `update_assertions` - Update test assertions
- `refactor_test_logic` - Refactor test structure
- `report_bug` - Report as application bug
- `other` - Other fix strategy

### Severity Levels
- `low` - Minor issue, low impact
- `medium` - Moderate issue, medium impact
- `high` - Major issue, high impact
- `critical` - Critical issue, blocks key features

## Integration with SuperAgent

### How Tasks Get Added

Tasks are automatically added to the HITL queue by the Medic agent when:
1. Max retries exceeded (3 attempts)
2. Regression detected (fix introduces new failures)
3. Low AI confidence (<0.7 confidence score)

See `MEDIC_HITL_ESCALATION.md` for details.

### Learning from Annotations

When you resolve a task, the annotation is stored in the vector database for agent learning:
- Future similar failures may reference your analysis
- Fix strategies are learned and suggested
- Common patterns are identified

## Screenshots

The dashboard provides:
- **Queue View**: List of all tasks with priority badges
- **Task Detail Modal**: Full task information with annotation form
- **Statistics Bar**: Real-time queue metrics
- **Responsive Design**: Works on desktop browsers

## Development

### Running in Development Mode

```bash
# The Flask server runs with debug=True by default
python server.py
```

Changes to static files (HTML/CSS/JS) are reflected immediately.
Changes to Python code will auto-reload.

### Adding New Fields

To add new annotation fields:

1. Update `schema.json` with new field
2. Add form field to `renderAnnotationForm()` in `app.js`
3. Add display field to `renderResolvedAnnotation()` in `app.js`
4. No backend changes needed (flexible schema)

## Production Deployment

### Using Docker

The dashboard can be deployed with the SuperAgent Docker stack:

```bash
docker-compose up hitl-dashboard
```

### Standalone Deployment

For production, use a production WSGI server:

```bash
pip install gunicorn

gunicorn -w 4 -b 0.0.0.0:5001 server:app
```

## Troubleshooting

### Redis Connection Error

**Error**: `Connection refused` or `Redis client not connected`

**Solution**:
1. Check if Redis is running: `redis-cli ping`
2. Verify Redis host/port in `.env`
3. Check firewall rules

### Tasks Not Appearing

**Possible causes**:
1. No tasks in queue: Check with `redis-cli ZRANGE hitl:queue 0 -1`
2. Tasks expired: Redis TTL is 24 hours
3. Wrong Redis database: Check REDIS_DB in config

### Unable to Resolve Tasks

**Error**: `Task not found or already resolved`

**Solution**:
1. Refresh the page to get latest data
2. Check if task was already resolved
3. Verify task_id is correct

## File Structure

```
hitl_dashboard/
├── README.md              # This file
├── server.py              # Flask backend server
├── requirements.txt       # Python dependencies (create this)
└── static/
    ├── index.html         # Dashboard UI
    ├── styles.css         # Styling
    └── app.js             # Frontend logic
```

## Key Features

- Real-time queue monitoring
- Priority-based task sorting
- Detailed task inspection
- Screenshot viewing (when available)
- Attempt history tracking
- Structured annotation system
- Vector DB integration for learning
- Responsive design
- Clean, modern UI

## Future Enhancements

Potential improvements:
- [ ] WebSocket support for real-time updates
- [ ] Bulk task operations
- [ ] Advanced filtering and search
- [ ] Export annotations to CSV
- [ ] Analytics dashboard
- [ ] User authentication
- [ ] Task assignment to specific reviewers
- [ ] Inline screenshot viewing
- [ ] Code diff viewer
- [ ] Pattern detection alerts

## References

- **HITL Queue**: `/Users/rutledge/Documents/DevFolder/SuperAgent/agent_system/hitl/queue.py`
- **Schema**: `/Users/rutledge/Documents/DevFolder/SuperAgent/agent_system/hitl/schema.json`
- **Medic Agent**: `/Users/rutledge/Documents/DevFolder/SuperAgent/agent_system/agents/medic.py`
- **Documentation**: `/Users/rutledge/Documents/DevFolder/SuperAgent/MEDIC_HITL_ESCALATION.md`

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review `MEDIC_HITL_ESCALATION.md` for workflow details
3. Verify Redis connection and configuration
4. Check browser console for JavaScript errors

## License

Part of the SuperAgent project.
