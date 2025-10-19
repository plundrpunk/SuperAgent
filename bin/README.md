# SuperAgent Executables

This directory contains the main user-facing executables for SuperAgent.

## Quick Start

### Start SuperAgent System
```bash
./bin/start_superagent.sh
```

Starts all SuperAgent services:
- Dashboard server (http://localhost:8080)
- WebSocket event stream (ws://localhost:3010)
- Real-time observability

### Run Kaya Commands
```bash
./bin/run_kaya.sh "write a test for user login"
./bin/run_kaya.sh "status"
./bin/run_kaya.sh "fix all test failures"
```

Simple CLI wrapper for Kaya with automatic environment setup.

### GUI Quick Access
```bash
python bin/kaya_quick_access.py
```

Always-on-top GUI interface with keyboard shortcut (Ctrl+Shift+K).

## Executables

### [start_superagent.sh](./start_superagent.sh)
Main system startup script.

**Usage:**
```bash
./bin/start_superagent.sh
```

**What it does:**
- Cleans up existing processes
- Starts dashboard server on port 8080
- Starts WebSocket server on port 3010
- Shows usage instructions
- Handles graceful shutdown (Ctrl+C)

**Requirements:**
- Python virtual environment at `venv/`
- Redis running (local or Docker)
- API keys configured in `.env`

---

### [run_kaya.sh](./run_kaya.sh)
Standalone Kaya runner.

**Usage:**
```bash
./bin/run_kaya.sh "<command>"
./bin/run_kaya.sh status
./bin/run_kaya.sh "write a test for checkout"
```

**What it does:**
- Validates environment (.env, venv)
- Activates virtual environment
- Runs Kaya with provided command
- Shows helpful error messages

**Examples:**
```bash
# Check status
./bin/run_kaya.sh status

# Generate test
./bin/run_kaya.sh "write a test for user registration"

# Fix failures
./bin/run_kaya.sh "fix all test failures"

# Execute mission
./bin/run_kaya.sh "execute the mission"
```

---

### [kaya_quick_access.py](./kaya_quick_access.py)
GUI interface for Kaya commands.

**Usage:**
```bash
python bin/kaya_quick_access.py
```

**Features:**
- Always-on-top window in top-right corner
- Keyboard shortcut: Ctrl+Shift+K
- Text command input
- Real-time status updates
- Toggle always-on-top

**Example Commands:**
- "execute the mission"
- "fix all test failures"
- "use opus for everything"
- "status"

---

### [kaya](./kaya) (Standalone Executable)
Direct Kaya executable (if available).

**Usage:**
```bash
./bin/kaya "command"
```

---

## Alternative: Use Makefile

For Docker-based deployments, use the Makefile instead:

```bash
# Start services
make up

# Run Kaya
make cli-kaya CMD="write a test for login"

# Check status
make cli-status

# View logs
make logs
```

See `Makefile` for all available commands.

---

## Directory Structure

```
bin/
├── README.md (this file)
├── start_superagent.sh    # Main startup script
├── run_kaya.sh            # Kaya CLI wrapper
├── kaya_quick_access.py   # GUI interface
└── kaya (optional)        # Direct executable
```

---

## Environment Setup

All scripts expect:
- **Root directory**: `/path/to/SuperAgent`
- **Virtual environment**: `venv/` in root
- **Configuration**: `.env` in root
- **Redis**: Running on localhost:6379

---

## Troubleshooting

### "Virtual environment not found"
```bash
cd /path/to/SuperAgent
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### "Redis connection failed"
```bash
# Start Redis
redis-server

# Or use Docker
docker compose -f config/docker-compose.yml up -d redis
```

### ".env file not found"
```bash
cp .env.example .env
# Edit .env and add your API keys
```

### Port already in use
```bash
# Kill existing processes
lsof -ti:8080 | xargs kill -9
lsof -ti:3010 | xargs kill -9
```

---

## Related Documentation

- [docs/getting-started/quick-start.md](../docs/getting-started/quick-start.md) - Complete setup guide
- [docs/getting-started/your-first-5-minutes.md](../docs/getting-started/your-first-5-minutes.md) - Quick tutorial
- [README.md](../README.md) - Project overview
- [Makefile](../Makefile) - Docker commands

---

**Last Updated**: October 19, 2025
