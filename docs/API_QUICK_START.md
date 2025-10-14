# HITL API Quick Start Guide

Get up and running with the SuperAgent HITL Dashboard API in 5 minutes.

## Prerequisites

- Python 3.11+
- Redis running on localhost:6379
- SuperAgent HITL Dashboard running

## 1. Start the API Server

```bash
cd /Users/rutledge/Documents/DevFolder/SuperAgent/hitl_dashboard
python server.py
```

The API will be available at: `http://localhost:5001/api`

## 2. Test the API

### Health Check

```bash
curl http://localhost:5001/api/health
```

**Expected Response**:
```json
{
  "success": true,
  "redis": true,
  "message": "HITL Dashboard API is running"
}
```

### List Tasks

```bash
curl http://localhost:5001/api/queue
```

**Expected Response**:
```json
{
  "success": true,
  "tasks": [],
  "count": 0
}
```

### Get Statistics

```bash
curl http://localhost:5001/api/queue/stats
```

**Expected Response**:
```json
{
  "success": true,
  "stats": {
    "total_count": 0,
    "active_count": 0,
    "resolved_count": 0,
    "avg_priority": 0.0,
    "high_priority_count": 0
  }
}
```

## 3. Add a Test Task

```python
# test_hitl_api.py
from agent_system.hitl.queue import HITLQueue

queue = HITLQueue()

# Add a test task
task = {
    "task_id": "test_task_001",
    "feature": "login flow",
    "code_path": "/path/to/test.spec.ts",
    "logs_path": "/path/to/logs.txt",
    "screenshots": ["/path/to/screenshot.png"],
    "attempts": 2,
    "last_error": "Selector not found: [data-testid='login-button']",
    "severity": "high",
    "escalation_reason": "max_retries_exceeded"
}

queue.add(task)
print("Task added to queue!")
```

Run it:
```bash
python test_hitl_api.py
```

## 4. Fetch the Task via API

```bash
# List all tasks
curl http://localhost:5001/api/queue | jq

# Get specific task
curl http://localhost:5001/api/queue/test_task_001 | jq
```

## 5. Resolve the Task

```bash
curl -X POST http://localhost:5001/api/queue/test_task_001/resolve \
  -H "Content-Type: application/json" \
  -d '{
    "root_cause_category": "selector_flaky",
    "fix_strategy": "update_selectors",
    "severity": "medium",
    "human_notes": "Updated selector to use data-testid instead of CSS class"
  }'
```

**Expected Response**:
```json
{
  "success": true,
  "message": "Task test_task_001 resolved successfully"
}
```

## 6. View Interactive Documentation

### Option A: Swagger UI (Docker)

```bash
cd /Users/rutledge/Documents/DevFolder/SuperAgent

docker run -p 8080:8080 \
  -e SWAGGER_JSON=/docs/openapi-hitl.yaml \
  -v $(pwd)/docs:/docs \
  swaggerapi/swagger-ui
```

Open: http://localhost:8080

### Option B: Swagger UI (npx)

```bash
cd /Users/rutledge/Documents/DevFolder/SuperAgent/docs

npx @apidevtools/swagger-ui-cli openapi-hitl.yaml
```

Open: http://localhost:8000

## 7. Use Python Client

```python
# hitl_client_example.py
import requests

class HITLClient:
    def __init__(self, base_url="http://localhost:5001/api"):
        self.base_url = base_url

    def health_check(self):
        response = requests.get(f"{self.base_url}/health")
        return response.json()

    def list_tasks(self, limit=None):
        params = {}
        if limit:
            params['limit'] = limit
        response = requests.get(f"{self.base_url}/queue", params=params)
        return response.json()['tasks']

    def get_task(self, task_id):
        response = requests.get(f"{self.base_url}/queue/{task_id}")
        return response.json()['task']

    def resolve_task(self, task_id, annotation):
        response = requests.post(
            f"{self.base_url}/queue/{task_id}/resolve",
            json=annotation
        )
        return response.json()

    def get_stats(self):
        response = requests.get(f"{self.base_url}/queue/stats")
        return response.json()['stats']

# Usage
client = HITLClient()

# Check health
health = client.health_check()
print(f"API Status: {health['message']}")

# List tasks
tasks = client.list_tasks(limit=5)
print(f"Found {len(tasks)} tasks")

# Get stats
stats = client.get_stats()
print(f"Active tasks: {stats['active_count']}")
print(f"High priority: {stats['high_priority_count']}")
```

## 8. Import into Postman

1. Open Postman
2. Click **Import** button
3. Select **File** tab
4. Choose `/Users/rutledge/Documents/DevFolder/SuperAgent/docs/openapi-hitl.yaml`
5. Click **Import**

All endpoints will be automatically imported!

## 9. Generate Client Library

### Python Client

```bash
# Install generator
npm install -g @openapitools/openapi-generator-cli

# Generate client
cd /Users/rutledge/Documents/DevFolder/SuperAgent

openapi-generator-cli generate \
  -i docs/openapi-hitl.yaml \
  -g python \
  -o clients/python-hitl \
  --additional-properties=packageName=hitl_client

# Install client
cd clients/python-hitl
pip install .

# Use it
python -c "from hitl_client.api.queue_api import QueueApi; print('Client ready!')"
```

### TypeScript Client

```bash
openapi-generator-cli generate \
  -i docs/openapi-hitl.yaml \
  -g typescript-fetch \
  -o clients/typescript-hitl \
  --additional-properties=npmName=@superagent/hitl-client

cd clients/typescript-hitl
npm install
npm run build
```

## 10. Access the Dashboard UI

Open your browser: http://localhost:5001

The dashboard provides a visual interface for:
- Viewing all tasks in the queue
- Inspecting task details
- Resolving tasks with annotations
- Viewing queue statistics

## Common Tasks

### Filter Active Tasks Only

```bash
curl http://localhost:5001/api/queue?include_resolved=false
```

### Get High-Priority Tasks

```bash
curl http://localhost:5001/api/queue | jq '.tasks[] | select(.priority > 0.7)'
```

### Check for Tasks Needing Attention

```python
client = HITLClient()
tasks = client.list_tasks()

high_priority = [t for t in tasks if t['priority'] > 0.7]
print(f"High priority tasks: {len(high_priority)}")

for task in high_priority:
    print(f"  - {task['task_id']}: {task['feature']} (priority: {task['priority']:.2f})")
```

### Bulk Resolve (Future Enhancement)

```python
# This will be available in future versions
# client.bulk_resolve([task_id_1, task_id_2], annotation)
```

## Troubleshooting

### API Returns 500 Error

**Error**: `{"success": false, "error": "Redis connection failed"}`

**Solution**:
1. Check Redis is running: `redis-cli ping`
2. Verify Redis config in `.env`
3. Restart Redis: `brew services restart redis` (macOS)

### No Tasks in Queue

**Check Redis**:
```bash
redis-cli ZRANGE hitl:queue 0 -1
redis-cli KEYS "hitl:task:*"
```

**Add Test Task**:
```python
from agent_system.hitl.queue import HITLQueue
queue = HITLQueue()
queue.add({
    "task_id": "test_001",
    "feature": "test feature",
    "code_path": "/test.ts",
    "logs_path": "/test.log",
    "screenshots": [],
    "attempts": 1,
    "last_error": "Test error"
})
```

### CORS Errors

If accessing from a different origin:
1. Check `flask-cors` is installed: `pip install flask-cors`
2. Restart the server
3. Clear browser cache

## Next Steps

- **Read Full API Docs**: [API_HITL_ENDPOINTS.md](./API_HITL_ENDPOINTS.md)
- **View OpenAPI Spec**: [openapi-hitl.yaml](./openapi-hitl.yaml)
- **Learn OpenAPI Tools**: [OPENAPI_USAGE.md](./OPENAPI_USAGE.md)
- **Understand Architecture**: [ARCHITECTURE.md](./ARCHITECTURE.md)

## Quick Reference

**Base URL**: `http://localhost:5001/api`

**Endpoints**:
- `GET /queue` - List tasks
- `GET /queue/stats` - Get statistics
- `GET /queue/{task_id}` - Get task details
- `POST /queue/{task_id}/resolve` - Resolve task
- `GET /health` - Health check

**Dashboard UI**: `http://localhost:5001`

**Documentation**:
- API Docs: `docs/API_HITL_ENDPOINTS.md`
- OpenAPI Spec: `docs/openapi-hitl.yaml`
- This Guide: `docs/API_QUICK_START.md`

---

**Need Help?** See [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) or check the full [API Documentation](./API_HITL_ENDPOINTS.md).
