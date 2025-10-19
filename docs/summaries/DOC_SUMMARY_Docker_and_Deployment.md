# Documentation Summary: Docker & Deployment

This document summarizes the Docker containerization, deployment strategies, and operational management of the SuperAgent system.

---

## 1. Docker Architecture

The system is containerized using Docker and orchestrated with Docker Compose. The architecture is designed for both development ease and production readiness.

### Core Components:
1.  **`superagent-app` Container**:
    - A single container that houses the entire multi-agent system (Kaya, Scribe, Runner, etc.).
    - Built from a multi-stage `Dockerfile` using a **Python 3.11-slim** base image, which also includes **Node.js 18** and the **Playwright** framework with its browser binaries.
    - The multi-stage build process optimizes the final image size by separating build-time dependencies from the runtime environment.

2.  **`superagent-redis` Container**:
    - A separate container running **Redis 7** on an Alpine base image.
    - It serves as the "hot state" management layer for session data, task queues, and real-time metrics.
    - Configured for data persistence through both RDB snapshots and AOF (Append-Only File) logging.

### Key `Dockerfile` Features:
- **Multi-stage Build**: Uses separate stages for building Python dependencies, Node.js dependencies, the final production image, and an extended development image. This keeps the production image lean.
- **Health Checks**: The `Dockerfile` includes a `HEALTHCHECK` instruction that verifies both Python application startup and connectivity to the Redis service.
- **Non-Root User**: A non-root user (`superagent`) is defined but commented out by default to ease development. It is recommended to enable this for production.

### Key `docker-compose.yml` Features:
- **Service Orchestration**: Defines the `superagent` and `redis` services and their dependencies (`superagent` waits for `redis` to be healthy).
- **Volume Management**: Uses a mix of host-mounted volumes (for `tests`, `logs`, `artifacts`) to allow easy developer access, and named volumes (`redis_data`, `vector_db_data`) for managed data persistence.
- **Resource Limits**: Sets default CPU and memory limits for containers to prevent resource exhaustion.

---

## 2. Deployment & Operations

The documentation provides multiple ways to manage the deployment, from simple helper scripts to a comprehensive `Makefile`.

### Quick Start (Recommended Method):
- A `Makefile` provides the simplest interface for all common operations.
- **`make setup`**: The primary command for first-time setup. It builds the images and starts the services.
- **`make up` / `make down`**: Standard commands to start and stop the environment.
- **`make cli-kaya CMD="..."`**: The recommended way to interact with the agent system by executing a command through the Kaya orchestrator inside the container.

### Interacting with the Container:
- **Shell Access**: `make shell` provides an interactive bash shell inside the `superagent-app` container.
- **CLI Commands**: Any CLI command can be run via `docker compose exec superagent python agent_system/cli.py <command>` or the corresponding `make` target.

### Production Deployment Strategy:
- The documentation outlines a full production deployment strategy that moves beyond Docker Compose.
- **Architecture**: A load balancer (Nginx) distributing requests across multiple stateless SuperAgent application instances, all connected to a shared, managed Redis instance (e.g., Redis Cloud, AWS ElastiCache).
- **Process Management**: Recommends using `systemd` to manage the application as a persistent service on a Linux host.
- **Security**: Enforces running as a non-root user, using Docker Secrets for API keys (instead of `.env` files), and enabling TLS for Redis connections.

---

## 3. Data, Backups, and CI/CD

### Data Persistence:
- **Hot Data (Redis)**: Session info and active tasks are stored in Redis. The `redis_data` named volume ensures this data persists across container restarts.
- **Cold Data (VectorDB)**: RAG patterns and other long-term knowledge are stored in the `vector_db_data` named volume.
- **Artifacts & Logs**: Test artifacts (screenshots, videos) and application logs are mapped directly to the host filesystem for easy access and analysis.

### Backup & Restore:
- The `Makefile` includes `make backup` and `make restore-*` commands.
- The backup process involves running a temporary container that mounts the named data volumes (`redis_data`, `vector_db_data`) and creates a `tar.gz` archive on the host.

### CI/CD Integration:
- The documentation provides example pipeline configurations for both **GitHub Actions** and **GitLab CI**, demonstrating how to build the Docker image, run tests, and push to a container registry as part of an automated workflow.
