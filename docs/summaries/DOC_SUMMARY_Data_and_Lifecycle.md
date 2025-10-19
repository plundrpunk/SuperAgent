# Documentation Summary: Data, MCP & Lifecycle

This document summarizes SuperAgent's approach to data persistence, task management through the Model Context Protocol (MCP), and service lifecycle management.

---

## 1. Data & State Management Strategy

SuperAgent uses a two-tiered approach to manage state, separating ephemeral "hot" data from permanent "cold" data.

-   **Hot State (Redis)**:
    -   **Purpose**: Manages temporary data for active tasks and user sessions.
    -   **Data Types**: Session information, active task queues, and voice transcripts.
    -   **TTL (Time-to-Live)**: Data is ephemeral, with a default TTL of **1 hour**.
    -   **Problem Solved**: Before MCP, all data was in Redis, meaning tasks and history were lost after an hour.

-   **Cold State (Archon MCP & Vector DB)**:
    -   **Purpose**: Provides long-term, persistent storage for projects, tasks, and learned knowledge.
    -   **Technology**: The primary implementation is **Archon MCP**, which acts as the system of record. A Vector DB (ChromaDB) is also used for storing embeddings for RAG.
    -   **Data Types**: All projects, all tasks and their results, agent performance metrics, successful test patterns, and bug-fix solutions.
    -   **Benefit**: Enables cross-session history, project organization, and powerful search capabilities. It allows the agent system to learn and improve over time.

### Data Privacy:
-   The system is designed to **NOT** store sensitive information like secrets, credentials, full file contents, or personal information in the MCP.

---

## 2. MCP (Model Context Protocol) Integration

**MCP** is a protocol that extends an AI's capabilities with tools and data sources. SuperAgent is deeply integrated with **Archon MCP** for task and project management.

### Key MCP Features:
-   **Project Management**: Users can create, switch, and archive projects (e.g., `"Kaya, create a project called 'Cloppy AI Testing'"`).
-   **Task Tracking**: Agent actions are automatically tracked as tasks within a project. The system tracks status (`pending`, `in_progress`, `completed`), results, and associated metadata.
-   **Agent Coordination**: Tasks can be assigned to specific agents, and the MCP tracks agent performance (success rate, speed) and prevents duplicate work.
-   **History & Search**: Provides a full, searchable audit trail of all agent actions.

### Recommended MCPs:
Beyond the integrated Archon MCP, the documentation highly recommends adding other MCPs to enhance Kaya's autonomy:
-   **Filesystem MCP**: To allow Kaya to read/write files and browse directories.
-   **GitHub MCP**: To enable Kaya to commit code and create pull requests.
-   **Brave Search MCP**: To let Kaya search the web for solutions to unknown errors.
-   **Memory MCP**: To give Kaya long-term memory of user preferences and conversations.

---

## 3. Service Lifecycle Management

SuperAgent has a robust lifecycle management system to ensure graceful startup, shutdown, and production reliability.

### Key Features:
-   **Graceful Shutdown**: The system listens for `SIGTERM` and `SIGINT` signals (e.g., from `docker compose down`). When a signal is received:
    1.  It **stops accepting new tasks**.
    2.  It **waits for all active tasks to complete**, up to a configurable timeout (default: 45 seconds in Docker).
    3.  It cleanly **closes all registered connections** (Redis, Vector DB, etc.).
    4.  It flushes logs and exits cleanly.
-   **Active Task Tracking**: Long-running operations are registered with the lifecycle manager. This ensures the system doesn't shut down in the middle of a critical task.
-   **Health Checks**: A `health` command is available via the CLI (`python agent_system/cli.py health`) to report the service status (`HEALTHY`, `DEGRADED`, `SHUTTING_DOWN`), uptime, and the health of its connections.
-   **Orphaned Task Recovery**: On startup, the system can detect tasks from a previous crash that were left in an incomplete state. It can then either mark them as `failed` (for a potential retry) or clear them.

### Docker Integration:
-   The `docker-compose.yml` file is configured with `stop_signal: SIGTERM` and `stop_grace_period: 45s` to fully support the graceful shutdown procedure.
