# Documentation Summary: HITL (Human-in-the-Loop)

This document summarizes the Human-in-the-Loop (HITL) system, which includes the escalation process and the HITL Dashboard for manual review.

---

## 1. Core Concept

The HITL system is a safety net and a learning mechanism. When the **Medic agent** (the automated bug-fixer) is unable to resolve a failing test, it escalates the task to a human for review. This prevents the system from getting stuck in infinite retry loops and provides an opportunity to capture human expertise.

### Escalation Triggers:
Tasks are automatically escalated to the HITL queue under three conditions:
1.  **Max Retries Exceeded**: The Medic agent fails to fix a test after a set number of attempts (default: 3).
2.  **Regression Detected**: The Medic's proposed fix introduces new failures in the regression test suite. In this case, the fix is automatically rolled back before escalation.
3.  **Low AI Confidence**: The Medic agent self-assesses its generated fix and escalates if its confidence is below a certain threshold (default: 70%).

---

## 2. HITL Queue & Priority

Escalated tasks are added to a priority queue managed in **Redis**.

-   **Priority Scoring**: Tasks are automatically assigned a priority score (0.0 to 1.0) based on several factors, including:
    -   The number of fix attempts (more attempts = higher priority).
    -   The severity of the issue (e.g., a `critical` issue gets a higher base priority).
    -   The time the task has been waiting in the queue.
-   **Storage**: The queue is a sorted set in Redis, ensuring that when a human reviewer looks at the dashboard, the most urgent and important tasks appear first.
-   **TTL**: Tasks in the HITL queue have a 24-hour Time-to-Live (TTL) in Redis.

---

## 3. The HITL Dashboard

A web-based dashboard is provided for human reviewers to manage the HITL queue.

-   **Location**: The dashboard code is in the `/hitl_dashboard` directory.
-   **Technology**: It is a **Flask** backend server that provides a REST API, with a vanilla **JavaScript, HTML, and CSS** frontend.
-   **Access**: It runs on `http://localhost:5001` by default.

### Dashboard Features:
-   **Queue Viewing**: Displays all active tasks, sorted by priority.
-   **Task Details**: Clicking a task opens a modal with comprehensive context, including:
    -   The original error message.
    -   The AI's diagnosis.
    -   A history of automated fix attempts.
    -   Code diffs of the attempted fixes.
    -   Links to logs and screenshots.
-   **Task Resolution**: Provides a form for the human reviewer to annotate the task with their findings.

---

## 4. Human Annotation & Learning

The primary goal of the HITL process is to **capture human expertise** so the agent system can learn.

### Annotation Process:
When resolving a task, the human reviewer provides structured feedback via the dashboard form, including:
-   **Root Cause Category**: A selection from a predefined list (e.g., `selector_flaky`, `timing_race_condition`, `api_contract_changed`).
-   **Fix Strategy**: The strategy used to fix the issue (e.g., `update_selectors`, `add_explicit_waits`).
-   **Severity**: An assessment of the issue's severity (`low`, `medium`, `high`, `critical`).
-   **Human Notes**: A detailed text description of the analysis and solution.
-   **Patch/Diff (Optional)**: The actual code changes applied.

### Learning Loop:
-   This structured annotation is saved permanently to the **Vector DB**. Over time, this creates a rich knowledge base.
-   The **Medic agent** can then query this database (using RAG) when it encounters similar errors in the future, allowing it to learn from past human interventions and improve its automated fixing capabilities.
