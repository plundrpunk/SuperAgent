# SuperAgent HITL Dashboard API Documentation

**Version**: 1.0.0
**Base URL**: `http://localhost:5001/api`
**Protocol**: HTTP/REST
**Authentication**: None (local development only)

## Overview

The HITL (Human-in-the-Loop) Dashboard API provides RESTful endpoints for managing escalated test failures in the SuperAgent system. When automated test fixes fail after maximum retry attempts, tasks are escalated to human reviewers through this queue system.

Human annotations and resolutions are stored in the vector database, enabling agents to learn from human expertise and improve fix strategies over time.

## Table of Contents

- [Quick Start](#quick-start)
- [API Endpoints](#api-endpoints)
  - [List HITL Tasks](#list-hitl-tasks)
  - [Get Task Details](#get-task-details)
  - [Resolve Task](#resolve-task)
  - [Get Queue Statistics](#get-queue-statistics)
  - [Health Check](#health-check)
- [Data Models](#data-models)
- [Error Handling](#error-handling)
- [Rate Limits](#rate-limits)
- [Code Examples](#code-examples)
- [Webhook Integration](#webhook-integration)
- [Dashboard Integration](#dashboard-integration)

---

## Quick Start

### Starting the Server

```bash
cd /Users/rutledge/Documents/DevFolder/SuperAgent/hitl_dashboard
python server.py
```

The API will be available at `http://localhost:5001/api`

### Basic Request Example

```bash
# Get all active tasks
curl http://localhost:5001/api/queue

# Get task details
curl http://localhost:5001/api/queue/task_123

# Get queue statistics
curl http://localhost:5001/api/queue/stats
```

---

## API Endpoints

### List HITL Tasks

Get a list of tasks in the HITL queue, sorted by priority (highest first).

**Endpoint**: `GET /api/queue`

**Query Parameters**:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `include_resolved` | boolean | No | `false` | Include resolved tasks in response |
| `limit` | integer | No | None | Maximum number of tasks to return |

**Response**: `200 OK`

```json
{
  "success": true,
  "tasks": [
    {
      "task_id": "task_2025-10-14_12-30-45_abc123",
      "feature": "checkout payment flow",
      "code_path": "/Users/rutledge/Documents/DevFolder/SuperAgent/tests/checkout.spec.ts",
      "logs_path": "/tmp/superagent/logs/task_2025-10-14_12-30-45_abc123.log",
      "screenshots": [
        "/tmp/superagent/screenshots/checkout_step1.png",
        "/tmp/superagent/screenshots/checkout_error.png"
      ],
      "attempts": 3,
      "last_error": "TimeoutError: Waiting for selector '[data-testid=\"payment-submit\"]' failed: timeout 30000ms exceeded",
      "priority": 0.85,
      "severity": "high",
      "escalation_reason": "max_retries_exceeded",
      "ai_diagnosis": "Selector not found after 3 attempts. Possible causes: 1) Selector changed, 2) Payment form not loading, 3) Race condition",
      "created_at": "2025-10-14T12:30:45.123Z",
      "resolved": false,
      "attempt_history": [
        {
          "attempt": 1,
          "timestamp": "2025-10-14T12:25:00Z",
          "error": "Selector not found"
        },
        {
          "attempt": 2,
          "timestamp": "2025-10-14T12:27:30Z",
          "error": "Selector not found"
        },
        {
          "attempt": 3,
          "timestamp": "2025-10-14T12:30:00Z",
          "error": "Selector not found"
        }
      ]
    }
  ],
  "count": 1
}
```

**Example Requests**:

```bash
# Get all active tasks
curl http://localhost:5001/api/queue

# Get all tasks including resolved
curl "http://localhost:5001/api/queue?include_resolved=true"

# Get top 10 highest priority tasks
curl "http://localhost:5001/api/queue?limit=10"

# Get top 5 tasks including resolved
curl "http://localhost:5001/api/queue?include_resolved=true&limit=5"
```

**Error Response**: `500 Internal Server Error`

```json
{
  "success": false,
  "error": "Redis connection failed"
}
```

---

### Get Task Details

Retrieve detailed information about a specific task.

**Endpoint**: `GET /api/queue/{task_id}`

**Path Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `task_id` | string | Yes | Unique task identifier |

**Response**: `200 OK`

```json
{
  "success": true,
  "task": {
    "task_id": "task_2025-10-14_12-30-45_abc123",
    "feature": "checkout payment flow",
    "code_path": "/Users/rutledge/Documents/DevFolder/SuperAgent/tests/checkout.spec.ts",
    "logs_path": "/tmp/superagent/logs/task_2025-10-14_12-30-45_abc123.log",
    "screenshots": [
      "/tmp/superagent/screenshots/checkout_step1.png",
      "/tmp/superagent/screenshots/checkout_error.png"
    ],
    "attempts": 3,
    "last_error": "TimeoutError: Waiting for selector '[data-testid=\"payment-submit\"]' failed: timeout 30000ms exceeded",
    "priority": 0.85,
    "severity": "high",
    "escalation_reason": "max_retries_exceeded",
    "ai_diagnosis": "Selector not found after 3 attempts. Possible causes: 1) Selector changed, 2) Payment form not loading, 3) Race condition",
    "created_at": "2025-10-14T12:30:45.123Z",
    "resolved": false,
    "artifacts": {
      "diff": "--- a/tests/checkout.spec.ts\n+++ b/tests/checkout.spec.ts\n@@ -15,7 +15,7 @@\n-  await page.click('[data-testid=\"submit-btn\"]');\n+  await page.click('[data-testid=\"payment-submit\"]');"
    },
    "attempt_history": [
      {
        "attempt": 1,
        "timestamp": "2025-10-14T12:25:00Z",
        "error": "Selector not found",
        "fix_applied": "Added explicit wait"
      },
      {
        "attempt": 2,
        "timestamp": "2025-10-14T12:27:30Z",
        "error": "Selector not found",
        "fix_applied": "Updated selector to data-testid"
      },
      {
        "attempt": 3,
        "timestamp": "2025-10-14T12:30:00Z",
        "error": "Selector not found",
        "fix_applied": "Added network wait condition"
      }
    ]
  }
}
```

**Error Response**: `404 Not Found`

```json
{
  "success": false,
  "error": "Task not found"
}
```

**Example Requests**:

```bash
# Get task details
curl http://localhost:5001/api/queue/task_2025-10-14_12-30-45_abc123

# Pretty print with jq
curl http://localhost:5001/api/queue/task_2025-10-14_12-30-45_abc123 | jq .
```

---

### Resolve Task

Mark a task as resolved with human annotation. This endpoint captures human expertise for agent learning.

**Endpoint**: `POST /api/queue/{task_id}/resolve`

**Path Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `task_id` | string | Yes | Unique task identifier |

**Request Body**:

```json
{
  "root_cause_category": "selector_flaky",
  "fix_strategy": "update_selectors",
  "severity": "medium",
  "human_notes": "The payment submit button selector changed from 'submit-btn' to 'payment-submit'. Updated test to use new selector. Also added explicit wait for payment form to be visible before clicking submit.",
  "patch_diff": "--- a/tests/checkout.spec.ts\n+++ b/tests/checkout.spec.ts\n@@ -15,7 +15,9 @@\n+  // Wait for payment form to be visible\n+  await page.waitForSelector('[data-testid=\"payment-form\"]', { state: 'visible' });\n   // Submit payment\n-  await page.click('[data-testid=\"submit-btn\"]');\n+  await page.click('[data-testid=\"payment-submit\"]');"
}
```

**Request Body Schema**:

| Field | Type | Required | Description | Valid Values |
|-------|------|----------|-------------|--------------|
| `root_cause_category` | string | Yes | Root cause of the failure | See [Root Cause Categories](#root-cause-categories) |
| `fix_strategy` | string | Yes | Strategy used to fix | See [Fix Strategies](#fix-strategies) |
| `severity` | string | Yes | Issue severity level | `low`, `medium`, `high`, `critical` |
| `human_notes` | string | Yes | Detailed human analysis | Any string (min 10 chars recommended) |
| `patch_diff` | string | No | Code changes applied | Unified diff format |

**Response**: `200 OK`

```json
{
  "success": true,
  "message": "Task task_2025-10-14_12-30-45_abc123 resolved successfully"
}
```

**Error Response**: `400 Bad Request`

```json
{
  "success": false,
  "error": "Missing required fields: root_cause_category, severity"
}
```

**Error Response**: `404 Not Found`

```json
{
  "success": false,
  "error": "Task not found or already resolved"
}
```

**Example Requests**:

```bash
# Resolve task with all fields
curl -X POST http://localhost:5001/api/queue/task_123/resolve \
  -H "Content-Type: application/json" \
  -d '{
    "root_cause_category": "selector_flaky",
    "fix_strategy": "update_selectors",
    "severity": "medium",
    "human_notes": "Updated data-testid selectors to match new component structure",
    "patch_diff": "--- a/test.ts\n+++ b/test.ts\n@@ -1 +1 @@\n-old\n+new"
  }'

# Resolve without patch_diff
curl -X POST http://localhost:5001/api/queue/task_123/resolve \
  -H "Content-Type: application/json" \
  -d '{
    "root_cause_category": "environment_config",
    "fix_strategy": "report_bug",
    "severity": "high",
    "human_notes": "This is an application bug, not a test issue. Filed bug report #456"
  }'
```

---

### Get Queue Statistics

Retrieve aggregated statistics about the HITL queue.

**Endpoint**: `GET /api/queue/stats`

**Response**: `200 OK`

```json
{
  "success": true,
  "stats": {
    "total_count": 25,
    "active_count": 8,
    "resolved_count": 17,
    "avg_priority": 0.62,
    "high_priority_count": 3
  }
}
```

**Response Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `total_count` | integer | Total number of tasks (active + resolved) |
| `active_count` | integer | Number of unresolved tasks |
| `resolved_count` | integer | Number of resolved tasks |
| `avg_priority` | float | Average priority of active tasks (0.0-1.0) |
| `high_priority_count` | integer | Number of active tasks with priority > 0.7 |

**Example Request**:

```bash
# Get statistics
curl http://localhost:5001/api/queue/stats

# Pretty print
curl http://localhost:5001/api/queue/stats | jq '.stats'
```

**Error Response**: `500 Internal Server Error`

```json
{
  "success": false,
  "error": "Redis connection failed"
}
```

---

### Health Check

Check the health status of the HITL Dashboard API and its dependencies.

**Endpoint**: `GET /api/health`

**Response**: `200 OK`

```json
{
  "success": true,
  "redis": true,
  "message": "HITL Dashboard API is running"
}
```

**Response Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Overall health status |
| `redis` | boolean | Redis connection status |
| `message` | string | Human-readable status message |

**Example Request**:

```bash
# Health check
curl http://localhost:5001/api/health

# Check exit code (0 = healthy)
curl -f http://localhost:5001/api/health && echo "Healthy"
```

**Error Response**: `500 Internal Server Error`

```json
{
  "success": false,
  "error": "Redis connection failed"
}
```

---

## Data Models

### Task Object

Complete task object schema:

```typescript
interface Task {
  // Required fields (present in all tasks)
  task_id: string;              // Unique identifier
  feature: string;              // Feature being tested
  code_path: string;            // Path to test file
  logs_path: string;            // Path to execution logs
  screenshots: string[];        // Array of screenshot paths
  attempts: number;             // Number of fix attempts (1-3)
  last_error: string;           // Most recent error message
  priority: number;             // Priority score (0.0-1.0)
  created_at: string;           // ISO 8601 timestamp

  // Optional fields (may be present)
  severity?: string;            // low | medium | high | critical
  escalation_reason?: string;   // Why task was escalated
  ai_diagnosis?: string;        // AI's analysis of the issue
  resolved?: boolean;           // Whether task is resolved (default: false)
  resolved_at?: string;         // ISO 8601 timestamp when resolved

  // Artifacts (optional)
  artifacts?: {
    diff?: string;              // Code changes attempted by Medic
  };

  // History (optional)
  attempt_history?: Array<{
    attempt: number;
    timestamp: string;          // ISO 8601 timestamp
    error: string;
    fix_applied?: string;
  }>;

  // Human annotation fields (present after resolution)
  root_cause_category?: string; // See Root Cause Categories
  fix_strategy?: string;        // See Fix Strategies
  human_notes?: string;         // Human analysis
  patch_diff?: string;          // Human-applied patch
}
```

### Priority Calculation

Priority score (0.0-1.0) is calculated based on:

1. **Attempts** (0-0.4): More attempts = higher priority
   - Formula: `min(attempts / 10, 0.4)`
   - 1 attempt = 0.1, 3 attempts = 0.3, 10+ attempts = 0.4

2. **Feature Criticality** (0-0.3): Critical features get higher priority
   - Keywords: `auth`, `login`, `payment`, `checkout`
   - Match = +0.3, No match = +0.0

3. **Time in Queue** (0-0.3): Older tasks get higher priority
   - Formula: `min(hours_old / 24, 0.3)`
   - 1 hour = 0.04, 12 hours = 0.15, 24+ hours = 0.3

**Examples**:
- Auth flow, 3 attempts, 12 hours old: `0.3 + 0.3 + 0.15 = 0.75` (High)
- UI test, 1 attempt, 2 hours old: `0.1 + 0.0 + 0.025 = 0.125` (Low)
- Checkout, 2 attempts, 24 hours old: `0.2 + 0.3 + 0.3 = 0.8` (High)

### Root Cause Categories

Valid values for `root_cause_category`:

| Value | Description | Example |
|-------|-------------|---------|
| `selector_flaky` | Selector is unreliable or changed | CSS class changed, dynamic IDs |
| `timing_race_condition` | Timing issues or race conditions | Element not ready, async operation |
| `data_dependency` | Test data issues or dependencies | Missing test data, wrong environment |
| `environment_config` | Environment configuration problems | Wrong BASE_URL, missing env vars |
| `api_contract_changed` | API contract changed | API response structure changed |
| `browser_compatibility` | Browser-specific issues | Works in Chrome, fails in Safari |
| `authentication_issue` | Auth/login problems | Session expired, OAuth flow broken |
| `unknown` | Unknown or unclear root cause | Unable to determine cause |

### Fix Strategies

Valid values for `fix_strategy`:

| Value | Description | When to Use |
|-------|-------------|-------------|
| `update_selectors` | Update element selectors | Selectors changed or are flaky |
| `add_explicit_waits` | Add wait conditions | Timing/race conditions |
| `mock_external_api` | Mock external dependencies | External API issues |
| `fix_test_data` | Fix test data | Data dependency issues |
| `update_assertions` | Update test assertions | Expected behavior changed |
| `refactor_test_logic` | Refactor test structure | Test design issues |
| `report_bug` | Report as application bug | Actual application bug found |
| `other` | Other fix strategy | None of the above apply |

---

## Error Handling

### Standard Error Response

All error responses follow this format:

```json
{
  "success": false,
  "error": "Human-readable error message"
}
```

### HTTP Status Codes

| Status Code | Meaning | Common Causes |
|-------------|---------|---------------|
| `200` | OK | Successful request |
| `400` | Bad Request | Missing required fields, invalid input |
| `404` | Not Found | Task ID doesn't exist |
| `500` | Internal Server Error | Redis connection failed, server error |

### Common Errors

**Missing Required Fields**:
```json
{
  "success": false,
  "error": "Missing required fields: root_cause_category, severity"
}
```

**Task Not Found**:
```json
{
  "success": false,
  "error": "Task not found"
}
```

**Redis Connection Failed**:
```json
{
  "success": false,
  "error": "Redis connection failed"
}
```

**Task Already Resolved**:
```json
{
  "success": false,
  "error": "Task not found or already resolved"
}
```

---

## Rate Limits

**Current Implementation**: No rate limits

The HITL Dashboard API currently does not implement rate limiting, as it is designed for **local development use only**.

**Future Considerations**:
- For production deployment, implement rate limiting: 100 requests/minute per IP
- Use Redis-backed rate limiting (e.g., `flask-limiter`)
- Add authentication and per-user rate limits

---

## Code Examples

### Python Client

```python
import requests
from typing import Dict, List, Optional

class HITLClient:
    """Python client for HITL Dashboard API."""

    def __init__(self, base_url: str = "http://localhost:5001/api"):
        self.base_url = base_url.rstrip('/')

    def list_tasks(
        self,
        include_resolved: bool = False,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """List tasks in queue."""
        params = {}
        if include_resolved:
            params['include_resolved'] = 'true'
        if limit:
            params['limit'] = limit

        response = requests.get(f"{self.base_url}/queue", params=params)
        response.raise_for_status()
        return response.json()['tasks']

    def get_task(self, task_id: str) -> Dict:
        """Get task details."""
        response = requests.get(f"{self.base_url}/queue/{task_id}")
        response.raise_for_status()
        return response.json()['task']

    def resolve_task(
        self,
        task_id: str,
        root_cause_category: str,
        fix_strategy: str,
        severity: str,
        human_notes: str,
        patch_diff: Optional[str] = None
    ) -> Dict:
        """Resolve task with annotation."""
        annotation = {
            'root_cause_category': root_cause_category,
            'fix_strategy': fix_strategy,
            'severity': severity,
            'human_notes': human_notes
        }
        if patch_diff:
            annotation['patch_diff'] = patch_diff

        response = requests.post(
            f"{self.base_url}/queue/{task_id}/resolve",
            json=annotation
        )
        response.raise_for_status()
        return response.json()

    def get_stats(self) -> Dict:
        """Get queue statistics."""
        response = requests.get(f"{self.base_url}/queue/stats")
        response.raise_for_status()
        return response.json()['stats']

    def health_check(self) -> bool:
        """Check API health."""
        try:
            response = requests.get(f"{self.base_url}/health")
            return response.json()['success']
        except Exception:
            return False


# Example usage
if __name__ == "__main__":
    client = HITLClient()

    # Check health
    if client.health_check():
        print("API is healthy")

    # Get statistics
    stats = client.get_stats()
    print(f"Active tasks: {stats['active_count']}")
    print(f"High priority: {stats['high_priority_count']}")

    # List high-priority tasks
    tasks = client.list_tasks(limit=10)
    for task in tasks:
        if task['priority'] > 0.7:
            print(f"HIGH PRIORITY: {task['task_id']} - {task['feature']}")

    # Get task details
    if tasks:
        task = client.get_task(tasks[0]['task_id'])
        print(f"Task details: {task['feature']}")
        print(f"Error: {task['last_error']}")

    # Resolve task
    # task_id = "task_123"
    # result = client.resolve_task(
    #     task_id=task_id,
    #     root_cause_category="selector_flaky",
    #     fix_strategy="update_selectors",
    #     severity="medium",
    #     human_notes="Updated selectors to use data-testid",
    #     patch_diff="--- a/test.ts\n+++ b/test.ts\n..."
    # )
    # print(f"Resolved: {result['message']}")
```

### TypeScript Client

```typescript
interface Task {
  task_id: string;
  feature: string;
  code_path: string;
  logs_path: string;
  screenshots: string[];
  attempts: number;
  last_error: string;
  priority: number;
  created_at: string;
  severity?: string;
  escalation_reason?: string;
  ai_diagnosis?: string;
  resolved?: boolean;
  resolved_at?: string;
}

interface QueueStats {
  total_count: number;
  active_count: number;
  resolved_count: number;
  avg_priority: number;
  high_priority_count: number;
}

interface ResolveAnnotation {
  root_cause_category: string;
  fix_strategy: string;
  severity: string;
  human_notes: string;
  patch_diff?: string;
}

class HITLClient {
  private baseUrl: string;

  constructor(baseUrl: string = 'http://localhost:5001/api') {
    this.baseUrl = baseUrl.replace(/\/$/, '');
  }

  async listTasks(
    includeResolved: boolean = false,
    limit?: number
  ): Promise<Task[]> {
    const params = new URLSearchParams();
    if (includeResolved) params.set('include_resolved', 'true');
    if (limit) params.set('limit', limit.toString());

    const response = await fetch(
      `${this.baseUrl}/queue?${params.toString()}`
    );
    const data = await response.json();

    if (!data.success) {
      throw new Error(data.error);
    }

    return data.tasks;
  }

  async getTask(taskId: string): Promise<Task> {
    const response = await fetch(`${this.baseUrl}/queue/${taskId}`);
    const data = await response.json();

    if (!data.success) {
      throw new Error(data.error);
    }

    return data.task;
  }

  async resolveTask(
    taskId: string,
    annotation: ResolveAnnotation
  ): Promise<{ message: string }> {
    const response = await fetch(`${this.baseUrl}/queue/${taskId}/resolve`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(annotation),
    });

    const data = await response.json();

    if (!data.success) {
      throw new Error(data.error);
    }

    return { message: data.message };
  }

  async getStats(): Promise<QueueStats> {
    const response = await fetch(`${this.baseUrl}/queue/stats`);
    const data = await response.json();

    if (!data.success) {
      throw new Error(data.error);
    }

    return data.stats;
  }

  async healthCheck(): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseUrl}/health`);
      const data = await response.json();
      return data.success === true;
    } catch {
      return false;
    }
  }
}

// Example usage
async function main() {
  const client = new HITLClient();

  // Check health
  const healthy = await client.healthCheck();
  console.log(`API health: ${healthy ? 'OK' : 'FAILED'}`);

  // Get statistics
  const stats = await client.getStats();
  console.log(`Active tasks: ${stats.active_count}`);
  console.log(`High priority: ${stats.high_priority_count}`);

  // List tasks
  const tasks = await client.listTasks(false, 10);
  for (const task of tasks) {
    if (task.priority > 0.7) {
      console.log(`HIGH: ${task.task_id} - ${task.feature}`);
    }
  }

  // Get task details
  if (tasks.length > 0) {
    const task = await client.getTask(tasks[0].task_id);
    console.log(`Task: ${task.feature}`);
    console.log(`Error: ${task.last_error}`);
  }

  // Resolve task
  // await client.resolveTask('task_123', {
  //   root_cause_category: 'selector_flaky',
  //   fix_strategy: 'update_selectors',
  //   severity: 'medium',
  //   human_notes: 'Updated selectors to use data-testid',
  //   patch_diff: '--- a/test.ts\n+++ b/test.ts\n...'
  // });
}

// main().catch(console.error);
```

### cURL Examples

```bash
# List all active tasks
curl http://localhost:5001/api/queue

# List top 5 tasks
curl "http://localhost:5001/api/queue?limit=5"

# Get specific task
curl http://localhost:5001/api/queue/task_123

# Resolve task
curl -X POST http://localhost:5001/api/queue/task_123/resolve \
  -H "Content-Type: application/json" \
  -d '{
    "root_cause_category": "selector_flaky",
    "fix_strategy": "update_selectors",
    "severity": "medium",
    "human_notes": "Fixed selectors"
  }'

# Get statistics
curl http://localhost:5001/api/queue/stats

# Health check
curl http://localhost:5001/api/health

# Pretty print with jq
curl http://localhost:5001/api/queue | jq '.tasks[] | {id: .task_id, priority: .priority, feature: .feature}'
```

---

## Webhook Integration

The HITL Dashboard can notify external systems when tasks are added or resolved.

### Future Enhancement: Webhook Support

**Planned endpoints**:

```
POST /api/webhooks/register
POST /api/webhooks/unregister
GET /api/webhooks/list
```

**Event types**:
- `task.created` - New task added to queue
- `task.resolved` - Task marked as resolved
- `queue.high_priority` - High-priority task added (priority > 0.7)

**Webhook payload example**:

```json
{
  "event": "task.created",
  "timestamp": "2025-10-14T12:30:45.123Z",
  "task": {
    "task_id": "task_123",
    "feature": "checkout flow",
    "priority": 0.85,
    "severity": "high"
  }
}
```

### Current Workaround: Polling

Until webhook support is implemented, use polling:

```python
import time
import requests

def poll_for_high_priority_tasks():
    """Poll for high-priority tasks every 30 seconds."""
    client = HITLClient()
    last_seen_task_ids = set()

    while True:
        try:
            tasks = client.list_tasks()
            high_priority_tasks = [
                t for t in tasks
                if t['priority'] > 0.7 and t['task_id'] not in last_seen_task_ids
            ]

            for task in high_priority_tasks:
                # Send notification
                print(f"ALERT: High priority task: {task['feature']}")
                # send_slack_notification(task)
                # send_email(task)
                last_seen_task_ids.add(task['task_id'])

        except Exception as e:
            print(f"Error polling: {e}")

        time.sleep(30)  # Poll every 30 seconds

# poll_for_high_priority_tasks()
```

---

## Dashboard Integration

The HITL Dashboard web UI (`http://localhost:5001`) consumes these API endpoints.

### Frontend Architecture

**Location**: `/Users/rutledge/Documents/DevFolder/SuperAgent/hitl_dashboard/static/`

**Files**:
- `index.html` - Dashboard UI structure
- `app.js` - Frontend logic and API client
- `styles.css` - Styling

### API Usage in Dashboard

The dashboard uses these endpoints:

1. **On Page Load**:
   - `GET /api/queue` - Load task list
   - `GET /api/queue/stats` - Load statistics

2. **Refresh Button Click**:
   - `GET /api/queue` - Reload tasks
   - `GET /api/queue/stats` - Reload statistics

3. **Task Card Click**:
   - `GET /api/queue/{task_id}` - Load task details
   - Display in modal

4. **Resolve Form Submit**:
   - `POST /api/queue/{task_id}/resolve` - Submit annotation
   - Reload queue and stats

5. **Toggle "Show Resolved"**:
   - `GET /api/queue?include_resolved=true` - Load all tasks

### Dashboard Features

- **Real-time Queue View**: Auto-refresh every 30 seconds (manual refresh available)
- **Priority Badges**: Visual indicators (High=red, Medium=yellow, Low=blue)
- **Task Details Modal**: Full task information with form
- **Annotation Form**: Structured input for human analysis
- **Statistics Bar**: Active/resolved counts, avg priority
- **Responsive Design**: Works on desktop browsers

### Starting the Dashboard

```bash
cd /Users/rutledge/Documents/DevFolder/SuperAgent/hitl_dashboard
python server.py
```

Access at: `http://localhost:5001`

---

## Authentication

**Current Status**: No authentication required

The HITL Dashboard API is designed for **local development only** and does not implement authentication.

### Security Considerations

**Current Setup**:
- Runs on `localhost` only
- No authentication or authorization
- Open CORS policy for development

**Production Recommendations**:
- Implement API key authentication
- Add role-based access control (RBAC)
- Use HTTPS/TLS
- Restrict CORS to specific origins
- Add request signing
- Implement audit logging

**Example Future Authentication**:

```bash
# With API key
curl -H "X-API-Key: your-api-key" http://api.example.com/queue

# With Bearer token
curl -H "Authorization: Bearer your-token" http://api.example.com/queue
```

---

## Environment Configuration

Configure the HITL Dashboard via environment variables:

```bash
# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=          # Optional
REDIS_DB=0               # Default: 0

# Dashboard Configuration
HITL_DASHBOARD_PORT=5001 # Default: 5001

# Vector DB Configuration (for annotations)
VECTOR_DB_HOST=localhost
VECTOR_DB_PORT=6333      # Qdrant default
```

**Environment File**: `/Users/rutledge/Documents/DevFolder/SuperAgent/.env`

---

## Data Retention

**Redis (Hot State)**:
- TTL: 24 hours
- Tasks expire after 24 hours if not resolved
- Resolved tasks remain for 24 hours after resolution

**Vector DB (Cold State)**:
- Retention: Permanent
- Human annotations stored indefinitely
- Used for agent learning

**Cleanup**:
```bash
# Clear all HITL tasks (Redis)
redis-cli DEL hitl:queue
redis-cli KEYS "hitl:task:*" | xargs redis-cli DEL

# Query vector DB for annotations
# See vector_client.py for search methods
```

---

## Troubleshooting

### Redis Connection Failed

**Error**: `Redis connection failed`

**Solutions**:
1. Check Redis is running: `redis-cli ping`
2. Verify `REDIS_HOST` and `REDIS_PORT` in `.env`
3. Check firewall rules
4. Restart Redis: `brew services restart redis` (macOS)

### Tasks Not Appearing

**Possible Causes**:
1. No tasks in queue: Run `redis-cli ZRANGE hitl:queue 0 -1`
2. Tasks expired: Redis TTL is 24 hours
3. Wrong Redis DB: Check `REDIS_DB` config

### Task Already Resolved Error

**Error**: `Task not found or already resolved`

**Solutions**:
1. Refresh the page to get latest data
2. Check if task was already resolved
3. Verify task_id is correct

### CORS Errors (Development)

**Error**: `CORS policy: No 'Access-Control-Allow-Origin' header`

**Solution**: Already handled by `flask-cors`. If still seeing errors:
1. Check `flask-cors` is installed: `pip install flask-cors`
2. Restart the server
3. Clear browser cache

---

## Performance Considerations

**Expected Performance**:
- List tasks: <50ms (10-100 tasks)
- Get task details: <20ms
- Resolve task: <100ms (includes vector DB write)
- Queue stats: <30ms

**Optimization Tips**:
1. Use `limit` parameter to reduce payload size
2. Cache statistics client-side (30-60 second TTL)
3. Use Redis pipelining for bulk operations
4. Monitor Redis memory usage

**Load Testing**:
```bash
# Install hey
go install github.com/rakyll/hey@latest

# Test list endpoint
hey -n 1000 -c 10 http://localhost:5001/api/queue

# Test stats endpoint
hey -n 1000 -c 10 http://localhost:5001/api/queue/stats
```

---

## Related Documentation

- **HITL Queue Implementation**: `/Users/rutledge/Documents/DevFolder/SuperAgent/agent_system/hitl/queue.py`
- **Task Schema**: `/Users/rutledge/Documents/DevFolder/SuperAgent/agent_system/hitl/schema.json`
- **Dashboard README**: `/Users/rutledge/Documents/DevFolder/SuperAgent/hitl_dashboard/README.md`
- **Medic Agent HITL Integration**: `/Users/rutledge/Documents/DevFolder/SuperAgent/MEDIC_HITL_ESCALATION.md`
- **OpenAPI Specification**: `/Users/rutledge/Documents/DevFolder/SuperAgent/docs/openapi-hitl.yaml`

---

## Support

For questions or issues:

1. Check troubleshooting section above
2. Review dashboard README: `hitl_dashboard/README.md`
3. Verify Redis connection: `redis-cli ping`
4. Check server logs for errors
5. Review API response errors

---

## Changelog

**Version 1.0.0** (2025-10-14):
- Initial API documentation
- Five core endpoints: list, get, resolve, stats, health
- Python and TypeScript client examples
- Full error handling documentation
- Priority calculation explanation
- Task schema and data models

---

**Last Updated**: 2025-10-14
**API Version**: 1.0.0
**Maintained By**: SuperAgent Project
