# SuperAgent - Docker Quick Start

Production-ready Docker deployment for SuperAgent.

## Quick Start (30 seconds)

```bash
# 1. Clone and configure
git clone <repository-url>
cd SuperAgent
cp .env.example .env
nano .env  # Add your API keys

# 2. Start with Make
make setup

# 3. Verify
make status
make cli-status
```

## Alternative Start Methods

### Using docker-start.sh

```bash
./docker-start.sh
```

### Using docker-compose directly

```bash
docker compose up -d
docker compose logs -f
```

### Using Makefile

```bash
make up
make logs
```

## Essential Commands

```bash
# Service management
make up              # Start all services
make down            # Stop all services
make restart         # Restart services
make logs            # View logs (follow mode)
make status          # Show service status

# SuperAgent CLI
make cli-status      # System status
make shell           # Interactive shell

# Testing
make test            # Run all tests
make test-unit       # Run unit tests

# Data management
make backup          # Backup volumes
make clean           # Remove stopped containers
```

## Common Tasks

### Run Kaya Orchestrator

```bash
make cli-kaya CMD="create test for user login"
```

### Route a Task

```bash
make cli-route TASK=write_test DESC="Create checkout test"
```

### Execute a Test

```bash
make cli-run TEST=tests/auth.spec.ts
```

### Review with Critic

```bash
make cli-review TEST=tests/auth.spec.ts
```

### Interactive Development

```bash
# Open shell in container
make shell

# Inside container:
cd /app
python agent_system/cli.py status
pytest tests/unit/
exit
```

## Architecture

```
SuperAgent Container
├── Python 3.11
├── Node.js 18
├── Playwright browsers (Chromium)
├── Agent system (Kaya, Scribe, Runner, Medic, Critic, Gemini)
└── Volumes: tests, artifacts, logs, vector_db

Redis Container
├── Redis 7 Alpine
├── Max memory: 256MB
├── Persistence: RDB + AOF
└── Volume: redis_data
```

## Environment Variables

Required in `.env`:

```env
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=...
BASE_URL=http://localhost:3000
```

See `.env.example` for all options.

## Volumes

- `./tests` - Test files (read-write)
- `./artifacts` - Screenshots, videos, traces
- `./logs` - Application logs
- `./test-results` - Playwright test results
- `./playwright-report` - HTML test reports
- `vector_db_data` - Vector database (persistent)
- `redis_data` - Redis data (persistent)

## Ports

- `8000` - Observability dashboard (future)
- `6379` - Redis (internal only)

## Troubleshooting

### Container won't start

```bash
# Check logs
make logs

# Rebuild
make rebuild

# Check environment
docker compose config
```

### Redis connection failed

```bash
# Check Redis health
docker compose ps redis

# Test connection
make redis-cli
> PING
```

### Permission issues

```bash
# Fix permissions on host
chmod -R 755 tests artifacts logs

# Or rebuild without non-root user
# (edit Dockerfile, comment out USER line)
```

## Useful Links

- Full documentation: [DOCKER_DEPLOYMENT.md](DOCKER_DEPLOYMENT.md)
- Project README: [README.md](README.md)
- Architecture guide: [CLAUDE.md](CLAUDE.md)
- Makefile help: `make help`

## Support

```bash
# Get help
make help
make docs

# Check version
make version

# Service health
make status
```

For detailed documentation, see [DOCKER_DEPLOYMENT.md](DOCKER_DEPLOYMENT.md).
