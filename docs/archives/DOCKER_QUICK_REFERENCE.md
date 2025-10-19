# SuperAgent - Docker Quick Reference Card

One-page reference for Docker commands. Print or bookmark this page.

## Setup (First Time)

```bash
cp .env.example .env && nano .env     # Add API keys
make setup                             # Build and start (5-10 min)
make status                            # Verify deployment
```

## Daily Commands

| Command | Description |
|---------|-------------|
| `make up` | Start services |
| `make down` | Stop services |
| `make restart` | Restart services |
| `make logs` | View all logs (follow) |
| `make status` | Service health check |
| `make shell` | Open bash shell |

## SuperAgent CLI

| Command | Description |
|---------|-------------|
| `make cli-status` | System status |
| `make cli-kaya CMD="..."` | Run Kaya orchestrator |
| `make cli-route TASK=... DESC="..."` | Route a task |
| `make cli-run TEST=...` | Execute test |
| `make cli-review TEST=...` | Review with Critic |
| `make cli-hitl` | Show HITL queue |

### Examples

```bash
# Kaya orchestrator
make cli-kaya CMD="create test for user login"

# Route task
make cli-route TASK=write_test DESC="Create checkout test"

# Run test
make cli-run TEST=tests/auth.spec.ts

# Review test
make cli-review TEST=tests/auth.spec.ts
```

## Testing

| Command | Description |
|---------|-------------|
| `make test` | Run all tests |
| `make test-unit` | Run unit tests |
| `make test-integration` | Run integration tests |
| `make test-cov` | Run with coverage |
| `make test-playwright` | Run Playwright tests |

## Logs & Debugging

| Command | Description |
|---------|-------------|
| `make logs` | All logs (follow) |
| `make logs-app` | SuperAgent only |
| `make logs-redis` | Redis only |
| `make logs-tail` | Last 100 lines |
| `make stats` | Resource usage |

### Interactive Debugging

```bash
make shell          # Bash shell
make python         # Python REPL
make redis-cli      # Redis CLI
```

## Data Management

| Command | Description |
|---------|-------------|
| `make backup` | Backup all volumes |
| `make restore-vector FILE=...` | Restore vector DB |
| `make restore-redis FILE=...` | Restore Redis |
| `make clean-artifacts` | Clean test artifacts |

### Backup & Restore

```bash
# Backup (creates timestamped files in ./backups)
make backup

# Restore
make restore-vector FILE=backups/vector_db_20250114_120000.tar.gz
make restore-redis FILE=backups/redis_20250114_120000.tar.gz
```

## Cleanup

| Command | Description |
|---------|-------------|
| `make clean` | Remove stopped containers |
| `make clean-artifacts` | Clean test artifacts |
| `make clean-all` | Remove EVERYTHING (⚠ DANGER) |

## Maintenance

| Command | Description |
|---------|-------------|
| `make rebuild` | Rebuild without cache |
| `make update` | Pull + rebuild + restart |
| `make pull` | Pull latest base images |

## Troubleshooting

### Service Won't Start

```bash
make logs           # Check error messages
make rebuild        # Rebuild from scratch
docker compose ps   # Check service status
```

### Redis Connection Failed

```bash
docker compose ps redis      # Check Redis health
make redis-cli               # Test connection
docker compose restart redis # Restart Redis
```

### Permission Issues

```bash
chmod -R 755 tests artifacts logs   # Fix permissions
make rebuild                        # Rebuild container
```

### Playwright Browsers Missing

```bash
make rebuild                        # Rebuild with --no-cache
make shell                          # Open shell
npx playwright install chromium     # Reinstall browsers
```

## Direct Docker Commands

If make is not available:

```bash
# Start
docker compose up -d

# Stop
docker compose down

# Logs
docker compose logs -f

# Shell
docker compose exec superagent /bin/bash

# CLI
docker compose exec superagent python agent_system/cli.py status
```

## Volumes

| Volume | Path | Purpose |
|--------|------|---------|
| `./tests` | `/app/tests` | Test files |
| `./artifacts` | `/app/tests/artifacts` | Screenshots, videos |
| `./logs` | `/app/logs` | Application logs |
| `vector_db_data` | `/app/vector_db` | RAG storage |
| `redis_data` | `/data` | Redis data |

## Ports

| Port | Service | Purpose |
|------|---------|---------|
| `8000` | SuperAgent | Observability (future) |
| `6379` | Redis | Internal only |

## Environment Variables

Edit `.env` for configuration:

```env
# Required
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=...

# Optional
BASE_URL=http://localhost:3000
REDIS_HOST=redis
LOG_LEVEL=INFO
```

## Resource Usage

| Component | CPU | Memory | Disk |
|-----------|-----|--------|------|
| SuperAgent | 1-2 cores | 2-4 GB | ~2 GB |
| Redis | 0.25-0.5 cores | 128-256 MB | ~100 MB |
| **Total** | **1.25-2.5 cores** | **2.1-4.3 GB** | **~2.1 GB** |

## Health Checks

```bash
# Service status
make status

# Health details
docker inspect --format='{{.State.Health.Status}}' superagent-app

# Network connectivity
docker network inspect superagent-network

# Volume info
docker volume ls | grep superagent
```

## Help & Documentation

| Command | Description |
|---------|-------------|
| `make help` | Show all make targets |
| `make docs` | Quick reference |
| `make version` | Version info |
| `./validate-docker.sh` | Validate setup |

### Documentation Files

- **DOCKER.md** - Quick start guide
- **DOCKER_DEPLOYMENT.md** - Full deployment guide
- **README.md** - Project overview
- **CLAUDE.md** - Architecture details

## Common Workflows

### Development

```bash
make up              # Start services
make logs-app        # Watch logs
make shell           # Open shell for debugging
make test            # Run tests
make down            # Stop when done
```

### Testing a Feature

```bash
make up
make cli-kaya CMD="create test for feature X"
make cli-run TEST=tests/feature-x.spec.ts
make cli-review TEST=tests/feature-x.spec.ts
make logs-app        # Check results
```

### Daily Standup Check

```bash
make status          # Service health
make cli-status      # SuperAgent status
make cli-hitl        # Check HITL queue
make stats           # Resource usage
```

### End of Day Cleanup

```bash
make backup          # Backup data
make down            # Stop services
```

## Emergency Commands

### Reset Everything

```bash
make down            # Stop services
make clean-all       # Remove all data (⚠ DANGER)
make setup           # Fresh start
```

### Force Rebuild

```bash
docker compose down -v              # Remove volumes
docker system prune -a --volumes    # Clean everything
docker compose build --no-cache     # Rebuild
docker compose up -d                # Start
```

### Recover from Crash

```bash
docker compose down                 # Stop everything
docker compose up -d redis          # Start Redis first
docker compose up -d superagent     # Start SuperAgent
make logs                           # Check logs
```

## Tips & Tricks

1. **Alias frequently used commands**:
   ```bash
   alias sa='docker compose exec superagent python agent_system/cli.py'
   sa status
   sa route write_test "Create test"
   ```

2. **Watch logs in real-time**:
   ```bash
   make logs | grep ERROR
   ```

3. **Quick test cycle**:
   ```bash
   make test-unit && make test-integration
   ```

4. **Development mode** (code changes reflect immediately):
   ```bash
   # Uncomment code volume in docker-compose.yml
   docker compose up -d
   ```

5. **Production checklist**:
   - [ ] Uncomment `USER superagent` in Dockerfile
   - [ ] Use external Redis
   - [ ] Set up TLS
   - [ ] Configure log aggregation
   - [ ] Enable monitoring
   - [ ] Set resource limits

## Support

**Need help?**

1. Check logs: `make logs`
2. Validate setup: `./validate-docker.sh`
3. Read docs: `DOCKER_DEPLOYMENT.md`
4. Check status: `make status`

**Report issues**: Include output from `make status` and `make logs`

---

**Version**: 1.0.0 | **Last Updated**: January 2025
