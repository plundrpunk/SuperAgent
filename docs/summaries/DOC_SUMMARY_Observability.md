# Documentation Summary: Observability & Monitoring

This document summarizes SuperAgent's observability, metrics, cost analytics, and alerting systems.

---

## 1. Core Observability Architecture

The observability system is built around a central **`EventEmitter`**, which acts as a global singleton to broadcast events from all agents to multiple destinations simultaneously.

### Event Destinations:
-   **Console**: Color-coded, human-readable log output for real-time development monitoring.
-   **JSONL File**: Structured, line-delimited JSON logs (`logs/agent-events.jsonl`) for persistent storage, analysis, and replay. Logs are automatically rotated daily, compressed after 7 days, and deleted after 30 days.
-   **WebSocket Server**: Streams events in real-time to any connected client, primarily for the visual dashboard. Runs on port `3010`.
-   **Redis**: Metrics are aggregated and persisted in Redis for time-series analysis.

### Key Event Types:
-   `task_queued`: A new task is created.
-   `agent_started` / `agent_completed`: An agent begins or finishes its work. The `completed` event includes status, duration, and cost.
-   `validation_complete`: The Gemini agent finishes a browser validation.
-   `hitl_escalated`: A task is escalated to the Human-in-the-Loop queue.
-   `budget_warning` / `budget_exceeded`: Cost-related alerts.

---

## 2. Metrics Aggregation

The system automatically tracks key performance indicators (KPIs) through the **`MetricsAggregator`**, which is integrated with the event emitter.

### Tracked Metrics:
-   **Agent Utilization**: The percentage of time each agent is active.
-   **Cost Per Feature**: The average end-to-end cost to complete a feature.
-   **Average Retry Count**: The average number of times the Medic agent is invoked to fix a failing test.
-   **Critic Rejection Rate**: The percentage of tests rejected by the Critic for quality issues (target: 15-30%).
-   **Validation Pass Rate**: The percentage of tests that pass final validation by the Gemini agent (target: >95%).
-   **Time to Completion**: The average duration from task creation to final validation.
-   **Model Usage**: A breakdown of costs and usage counts for each AI model (Haiku, Sonnet, Gemini).

### Storage:
-   Metrics are stored in **Redis** using sorted sets, bucketed by the hour and day (e.g., `metrics:daily:2025-10-14`).
-   Data has a 30-day TTL for automatic cleanup.

---

## 3. Cost Analytics & Budgeting

A dedicated **`CostTracker`** system provides granular cost analysis and enforces budget limits defined in `.claude/router_policy.yaml`.

### Key Features:
-   **Tracking**: Costs are tracked per agent, per model, and per feature.
-   **Budget Enforcement**: The system checks the budget before starting an operation.
    -   A `budget_warning` event is emitted when spending reaches **80%** of the defined limit (daily or per-session).
    -   A `budget_exceeded` event is emitted at **100%**, and further operations can be blocked.
-   **Reporting**: A rich set of CLI commands are available under `python agent_system/cli.py cost` to generate reports on daily/weekly spend, breakdowns by agent/model/feature, and historical trends.

---

## 4. Alerting

The **`AlertManager`** monitors the aggregated metrics and triggers alerts when predefined thresholds are breached.

### Key Features:
-   **Configurable Conditions**: Alert rules are defined in `.claude/observability.yaml` (e.g., `critic_rejection_rate > 0.50`).
-   **Notification Channels**: Alerts can be sent to the console (color-coded), a webhook URL, or via email (SMTP).
-   **Rate Limiting**: To prevent alert fatigue, notifications for the same condition are rate-limited (default: once every 10 minutes).

---

## 5. Usage & Integration

-   **Emitting Events**: Agents can easily log their activities using a simple, global function: `emit_event('event_type', { ...payload... })`.
-   **Viewing Logs**: A command-line tool (`view_logs.py`) allows for viewing and filtering the JSONL logs by date, agent, task ID, or status.
-   **Dashboard**: A simple `dashboard.html` file is provided, which connects to the WebSocket server to display a real-time feed of agent events and key metrics.
