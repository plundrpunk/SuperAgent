# SuperAgent - Docker Deployment Guide

Complete guide for deploying SuperAgent using Docker and Docker Compose.

## Prerequisites

- **Docker**: 20.10+ ([Install Docker](https://docs.docker.com/get-docker/))
- **Docker Compose**: 2.0+ (included with Docker Desktop)
- **API Keys**: Anthropic, OpenAI, Gemini (optional)

Verify installation:
```bash
docker --version
docker-compose --version
```

## Quick Start

### 1. Clone and Configure

```bash
# Navigate to project directory
cd /Users/rutledge/Documents/DevFolder/SuperAgent

# Create environment file
cp .env.example .env

# Edit .env with your API keys
nano .env  # or use your preferred editor
```

**Required environment variables:**
```env
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here
OPENAI_API_KEY=sk-your-key-here
GEMINI_API_KEY=your-gemini-key-here
BASE_URL=http://localhost:3000
```

### 2. Build and Start Services

```bash
# Build Docker image
docker-compose build

# Start all services (SuperAgent + Redis)
docker-compose up -d

# View logs
docker-compose logs -f
```

### 3. Verify Deployment

```bash
# Check service health
docker-compose ps

# Test CLI
docker-compose exec superagent python agent_system/cli.py status

# Run a command
docker-compose exec superagent python agent_system/cli.py route write_test "Create login test"
```

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  SuperAgent                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │   Kaya   │  │  Scribe  │  │  Runner  │      │
│  │ (Router) │  │ (Writer) │  │(Executor)│      │
│  └──────────┘  └──────────┘  └──────────┘      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │  Critic  │  │  Medic   │  │  Gemini  │      │
│  │  (Gate)  │  │  (Fixer) │  │(Validate)│      │
│  └──────────┘  └──────────┘  └──────────┘      │
│                                                  │
│  Volumes:                                        │
│  - tests/         (test files)                   │
│  - artifacts/     (screenshots, videos)          │
│  - logs/          (application logs)             │
│  - vector_db/     (RAG storage)                  │
└─────────────────────────────────────────────────┘
                      ↓
           ┌──────────────────┐
           │      Redis        │
           │  (State Storage)  │
           └──────────────────┘
```

## Docker Services

### SuperAgent (Main Application)

**Container**: `superagent-app`
**Image**: Built from `Dockerfile`
**Base**: Python 3.11 slim + Node.js 18 + Playwright browsers

**Resources**:
- CPU: 1-2 cores
- Memory: 2-4 GB
- Storage: ~2 GB (base image) + volumes

**Volumes**:
- `./tests` → `/app/tests` (test files)
- `./artifacts` → `/app/tests/artifacts` (test artifacts)
- `./logs` → `/app/logs` (application logs)
- `vector_db_data` → `/app/vector_db` (vector database)

**Ports**:
- `8000` → Observability dashboard (future)

### Redis (State Management)

**Container**: `superagent-redis`
**Image**: `redis:7-alpine`

**Configuration**:
- Max memory: 256 MB
- Eviction policy: `allkeys-lru`
- Persistence: RDB + AOF
- TTL: 1 hour (hot state)

**Volume**:
- `redis_data` → `/data` (persistent storage)

## Usage Examples

### CLI Commands

```bash
# Show system status
docker-compose exec superagent python agent_system/cli.py status

# Route a task
docker-compose exec superagent python agent_system/cli.py route write_test "Create checkout test"

# Run Kaya orchestrator
docker-compose exec superagent python agent_system/cli.py kaya "create test for user registration"

# Execute a test
docker-compose exec superagent python agent_system/cli.py run tests/auth.spec.ts

# Review test with Critic
docker-compose exec superagent python agent_system/cli.py review tests/auth.spec.ts

# Check HITL queue
docker-compose exec superagent python agent_system/cli.py hitl list
docker-compose exec superagent python agent_system/cli.py hitl stats
```

### Interactive Shell

```bash
# Open bash shell in container
docker-compose exec superagent /bin/bash

# Inside container:
cd /app
python agent_system/cli.py status
pytest tests/unit/
exit
```

### Python REPL

```bash
# Open Python interpreter with SuperAgent loaded
docker-compose exec superagent python

# Inside Python:
>>> from agent_system.agents.kaya import KayaAgent
>>> kaya = KayaAgent()
>>> result = kaya.execute("create test for login")
>>> print(result)
>>> exit()
```

## Volume Management

### Local Development

Mount local code for live editing:

```yaml
# In docker-compose.yml, uncomment:
volumes:
  - ./agent_system:/app/agent_system:ro  # Read-only
```

Restart after changes:
```bash
docker-compose restart superagent
```

### Data Persistence

**Persistent volumes** (survives `docker-compose down`):
- `redis_data`: Redis state
- `vector_db_data`: RAG patterns, bug fixes, HITL annotations

**Host-mounted directories**:
- `./tests`: Test files (read-write)
- `./artifacts`: Screenshots, videos, traces
- `./logs`: Application logs

**Backup volumes**:
```bash
# Backup vector database
docker run --rm \
  -v superagent-vector-db:/data \
  -v $(pwd)/backups:/backup \
  alpine tar czf /backup/vector_db_$(date +%Y%m%d).tar.gz /data

# Backup Redis data
docker run --rm \
  -v superagent-redis-data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar czf /backup/redis_$(date +%Y%m%d).tar.gz /data
```

**Restore volumes**:
```bash
# Restore vector database
docker run --rm \
  -v superagent-vector-db:/data \
  -v $(pwd)/backups:/backup \
  alpine tar xzf /backup/vector_db_20250114.tar.gz -C /

# Restore Redis data
docker run --rm \
  -v superagent-redis-data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar xzf /backup/redis_20250114.tar.gz -C /
```

### Clean Up

```bash
# Stop services
docker-compose down

# Stop and remove volumes (WARNING: deletes all data)
docker-compose down -v

# Remove dangling images
docker image prune -f

# Full cleanup (images, containers, networks, volumes)
docker system prune -a --volumes
```

## Logs and Debugging

### View Logs

```bash
# All services
docker-compose logs -f

# SuperAgent only
docker-compose logs -f superagent

# Redis only
docker-compose logs -f redis

# Last 100 lines
docker-compose logs --tail=100 superagent

# Since timestamp
docker-compose logs --since 2025-01-14T12:00:00 superagent
```

### Debug Container

```bash
# Check container status
docker-compose ps

# Inspect container details
docker inspect superagent-app

# View resource usage
docker-compose stats

# Check health
docker inspect --format='{{.State.Health.Status}}' superagent-app
```

### Common Issues

**Issue**: Container exits immediately
```bash
# Check logs
docker-compose logs superagent

# Verify environment variables
docker-compose config

# Test build
docker-compose build --no-cache
```

**Issue**: Redis connection failed
```bash
# Verify Redis is running
docker-compose ps redis

# Test Redis connection
docker-compose exec redis redis-cli ping

# Check network
docker network inspect superagent-network
```

**Issue**: Playwright browsers not found
```bash
# Rebuild with --no-cache
docker-compose build --no-cache

# Verify browsers installed
docker-compose exec superagent npx playwright --version
docker-compose exec superagent npx playwright list
```

**Issue**: Permission denied on volumes
```bash
# Fix permissions on host
chmod -R 755 tests artifacts logs

# Or run container as root (not recommended for production)
# In docker-compose.yml, comment out 'user: superagent'
```

## Production Deployment

### Security Hardening

1. **Run as non-root user**:
   ```dockerfile
   # In Dockerfile, uncomment:
   RUN useradd -m -u 1000 superagent && \
       chown -R superagent:superagent /app
   USER superagent
   ```

2. **Use secrets management**:
   ```bash
   # Docker Secrets (Swarm mode)
   docker secret create anthropic_key anthropic_key.txt
   docker secret create openai_key openai_key.txt
   ```

3. **Enable TLS for Redis**:
   ```yaml
   # docker-compose.yml
   redis:
     command: >
       redis-server
       --tls-port 6380
       --tls-cert-file /tls/redis.crt
       --tls-key-file /tls/redis.key
   ```

4. **Network isolation**:
   ```yaml
   # Only expose necessary ports
   ports:
     - "127.0.0.1:8000:8000"  # Bind to localhost only
   ```

### External Redis

For production, use managed Redis (AWS ElastiCache, Redis Cloud):

```yaml
# docker-compose.yml
services:
  superagent:
    environment:
      - REDIS_HOST=your-redis.cloud.redislabs.com
      - REDIS_PORT=12345
      - REDIS_PASSWORD=your-secure-password
      - REDIS_TLS=true

  # Remove local redis service
  # redis: ...
```

### Monitoring

**Health checks**:
```bash
# Automated health monitoring
watch -n 10 docker-compose ps
```

**Resource monitoring**:
```bash
# Export metrics to Prometheus
docker-compose exec superagent python agent_system/cli.py metrics export
```

**Log aggregation**:
```yaml
# docker-compose.yml
services:
  superagent:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### Scaling

**Horizontal scaling** (multiple SuperAgent instances):
```bash
docker-compose up -d --scale superagent=3
```

**Load balancing** (using Nginx):
```yaml
# docker-compose.yml
services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - superagent
```

## Performance Optimization

### Image Size

Current image size: ~2 GB (Python + Node.js + Playwright browsers)

**Reduce image size**:
1. Install only Chromium browser (not Firefox/WebKit):
   ```dockerfile
   RUN npx playwright install chromium  # ~300 MB smaller
   ```

2. Use multi-stage builds (already implemented in Dockerfile)

3. Remove dev dependencies:
   ```dockerfile
   RUN pip install --no-cache-dir --no-dev -r requirements.txt
   ```

### Build Cache

```bash
# Use BuildKit for faster builds
DOCKER_BUILDKIT=1 docker-compose build

# Leverage layer caching
docker-compose build --pull --parallel
```

### Resource Limits

Adjust in `docker-compose.yml`:
```yaml
services:
  superagent:
    deploy:
      resources:
        limits:
          memory: 4G      # Increase for more concurrent tests
          cpus: '2.0'     # Increase for faster test execution
```

## CI/CD Integration

### GitHub Actions

```yaml
# .github/workflows/deploy.yml
name: Deploy SuperAgent

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Build Docker image
        run: docker-compose build

      - name: Run tests
        run: docker-compose run --rm superagent pytest tests/unit/

      - name: Push to registry
        run: |
          docker tag superagent:latest registry.example.com/superagent:latest
          docker push registry.example.com/superagent:latest
```

### GitLab CI

```yaml
# .gitlab-ci.yml
stages:
  - build
  - test
  - deploy

build:
  stage: build
  script:
    - docker-compose build

test:
  stage: test
  script:
    - docker-compose run --rm superagent pytest tests/

deploy:
  stage: deploy
  script:
    - docker-compose up -d
  only:
    - main
```

## Troubleshooting

### Health Check Failures

```bash
# Check health status
docker inspect --format='{{json .State.Health}}' superagent-app | jq

# View health check logs
docker inspect superagent-app | jq '.[0].State.Health.Log'

# Manually test health check
docker-compose exec superagent python -c "from agent_system.cli import main; print('OK')"
```

### Network Connectivity

```bash
# Test Redis connection
docker-compose exec superagent redis-cli -h redis ping

# Test DNS resolution
docker-compose exec superagent nslookup redis

# Inspect network
docker network inspect superagent-network
```

### Performance Issues

```bash
# Check resource usage
docker stats superagent-app

# Analyze Playwright test execution
docker-compose exec superagent npx playwright test --debug

# Enable verbose logging
docker-compose exec superagent python agent_system/cli.py --log-level DEBUG status
```

## Additional Resources

- [Dockerfile Reference](https://docs.docker.com/engine/reference/builder/)
- [Docker Compose Reference](https://docs.docker.com/compose/compose-file/)
- [Playwright Docker](https://playwright.dev/docs/docker)
- [SuperAgent README](README.md)
- [SuperAgent Architecture](CLAUDE.md)

## Support

For issues and questions:
1. Check logs: `docker-compose logs -f`
2. Review [Common Issues](#common-issues)
3. Open an issue on GitHub

---

**Version**: 1.0.0
**Last Updated**: January 2025
**Maintainer**: SuperAgent Team
