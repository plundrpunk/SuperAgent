# SuperAgent Documentation

Complete documentation for deploying, operating, and understanding SuperAgent.

---

## Quick Navigation

### Getting Started
- **[DEPLOYMENT.md](./DEPLOYMENT.md)** - Complete deployment guide
  - Prerequisites (Python, Node.js, Docker, Redis)
  - Environment setup and configuration
  - API key setup (Anthropic, OpenAI, Gemini)
  - Redis and Vector DB configuration
  - Docker deployment with docker-compose
  - Production deployment with Nginx, SSL, systemd
  - Monitoring and observability setup
  - Backup and restore procedures

### Operations
- **[TROUBLESHOOTING.md](./TROUBLESHOOTING.md)** - Common issues and solutions
  - Quick diagnostics and health checks
  - Redis connection issues
  - API key errors and authentication
  - Agent failures and debugging
  - Docker container issues
  - Playwright browser problems
  - Performance optimization
  - Network and database issues

### Architecture
- **[ARCHITECTURE.md](./ARCHITECTURE.md)** - System architecture and design
  - High-level system overview
  - Architecture diagrams and flows
  - Detailed agent specifications
  - Communication patterns
  - State management (Redis + Vector DB)
  - Cost optimization strategy
  - Validation pipeline
  - HITL (Human-in-the-Loop) system
  - Observability and metrics
  - Security architecture

### API Reference
- **[API_QUICK_START.md](./API_QUICK_START.md)** - Get started with the API in 5 minutes
  - Quick setup and testing
  - Common use cases
  - Python client examples
  - Swagger UI and Postman setup
- **[API_HITL_ENDPOINTS.md](./API_HITL_ENDPOINTS.md)** - Complete REST API documentation
  - Full API endpoint reference (5 endpoints)
  - Request/response schemas
  - Python and TypeScript client examples
  - Error handling and troubleshooting
  - Dashboard integration guide
- **[openapi-hitl.yaml](./openapi-hitl.yaml)** - OpenAPI 3.0 specification
  - Machine-readable API specification
  - Use with Swagger UI, Postman, or code generators
  - Complete schema definitions and examples
- **[OPENAPI_USAGE.md](./OPENAPI_USAGE.md)** - OpenAPI tooling guide
  - Swagger UI setup
  - Code generation (10+ languages)
  - Mock servers and testing
  - CI/CD integration

---

## Documentation Structure

```
docs/
├── README.md                  # This file - navigation guide
├── DEPLOYMENT.md              # Deployment guide (1,550 lines)
├── TROUBLESHOOTING.md         # Troubleshooting guide (1,411 lines)
├── ARCHITECTURE.md            # Architecture guide (1,394 lines)
├── API_QUICK_START.md         # HITL API quick start (250 lines)
├── API_HITL_ENDPOINTS.md      # HITL API documentation (1,200 lines)
├── openapi-hitl.yaml          # OpenAPI 3.0 specification (800 lines)
├── OPENAPI_USAGE.md           # OpenAPI tooling guide (450 lines)
├── VOICE_COMMANDS_GUIDE.md    # Voice command guide (1,100 lines)
└── VOICE_QUICK_REFERENCE.md   # Voice quick reference (200 lines)
```

Total: 8,355 lines of comprehensive documentation

---

## Quick Start Paths

### Path 1: Local Development (10 minutes)
1. Read [DEPLOYMENT.md - Environment Setup](./DEPLOYMENT.md#environment-setup)
2. Follow quick start steps
3. Configure API keys
4. Start developing

### Path 2: Docker Deployment (20 minutes)
1. Read [DEPLOYMENT.md - Docker Deployment](./DEPLOYMENT.md#docker-deployment)
2. Use Makefile commands
3. Verify with health checks
4. Start using CLI

### Path 3: Production Deployment (2 hours)
1. Read [DEPLOYMENT.md - Production Deployment](./DEPLOYMENT.md#production-deployment)
2. Set up server infrastructure
3. Configure Nginx + SSL
4. Deploy with systemd
5. Set up monitoring
6. Configure automated backups

---

## Key Concepts

### Agents
SuperAgent uses six specialized AI agents:

- **Kaya** (Router/Orchestrator) - Routes commands, coordinates agents
- **Scribe** (Test Writer) - Generates Playwright tests
- **Runner** (Test Executor) - Executes tests via subprocess
- **Critic** (Pre-Validator) - Quality gate before validation
- **Medic** (Bug Fixer) - Applies surgical fixes to failing tests
- **Gemini** (Validator) - Real browser validation with screenshots

[Learn more →](./ARCHITECTURE.md#agent-details)

### Cost Optimization
- 70% Haiku (routing, execution, pre-validation)
- 30% Sonnet 4.5 (test writing, bug fixing)
- Gemini 2.5 Pro only for final validation
- Target: $0.50 per feature ($2-3 for critical paths)

[Learn more →](./ARCHITECTURE.md#cost-optimization-strategy)

### State Management
- **Hot State (Redis, 1h TTL)**: Session data, task queue, transcripts
- **Cold State (Vector DB, Permanent)**: Test patterns, bug fixes, HITL annotations

[Learn more →](./ARCHITECTURE.md#state-management)

### Validation Pipeline
Three-stage validation ensures quality:
1. **Static Analysis** (Critic) - Fast anti-pattern detection
2. **Test Execution** (Runner) - Verify test compiles and runs
3. **Browser Validation** (Gemini) - Prove correctness with screenshots

[Learn more →](./ARCHITECTURE.md#validation-pipeline)

---

## Common Tasks

### Deploy SuperAgent

**Local**:
```bash
# See: DEPLOYMENT.md - Environment Setup
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
npx playwright install chromium
cp .env.example .env
# Edit .env with API keys
python agent_system/cli.py status
```

**Docker**:
```bash
# See: DEPLOYMENT.md - Docker Deployment
cp .env.example .env
# Edit .env with API keys
docker compose up -d
docker compose logs -f
docker compose exec superagent python agent_system/cli.py status
```

**Production**:
```bash
# See: DEPLOYMENT.md - Production Deployment
# Follow complete production setup guide
```

### Troubleshoot Issues

**Quick diagnostics**:
```bash
# See: TROUBLESHOOTING.md - Quick Diagnostics
./health_check.sh
tail -100 logs/agent-events.jsonl | jq
redis-cli ping
docker compose ps
```

**Common issues**:
- [Redis connection failed](./TROUBLESHOOTING.md#redis-connection-issues)
- [API key errors](./TROUBLESHOOTING.md#api-key-errors)
- [Agent failures](./TROUBLESHOOTING.md#agent-failures)
- [Docker issues](./TROUBLESHOOTING.md#docker-issues)
- [Performance problems](./TROUBLESHOOTING.md#performance-problems)

### Understanding Architecture

**System overview**:
- [High-level architecture](./ARCHITECTURE.md#system-overview)
- [Architecture diagrams](./ARCHITECTURE.md#architecture-diagrams)
- [Agent communication flow](./ARCHITECTURE.md#communication-flow)

**Deep dives**:
- [Agent specifications](./ARCHITECTURE.md#agent-details)
- [State management](./ARCHITECTURE.md#state-management)
- [Cost optimization](./ARCHITECTURE.md#cost-optimization-strategy)
- [HITL system](./ARCHITECTURE.md#hitl-system)

**API Reference**:
- [HITL Dashboard API](./API_HITL_ENDPOINTS.md) - Complete REST API docs
- [OpenAPI Specification](./openapi-hitl.yaml) - Machine-readable spec
- [Voice Commands](./VOICE_COMMANDS_GUIDE.md) - Voice command reference

---

## Additional Resources

### Project Documentation
- [README.md](../README.md) - Project overview and quick start
- [CLAUDE.md](../CLAUDE.md) - Agent guidance and conventions
- [DOCKER.md](../DOCKER.md) - Docker quick start guide
- [DOCKER_DEPLOYMENT.md](../DOCKER_DEPLOYMENT.md) - Full Docker deployment guide

### Implementation Summaries
- [Observability Implementation](../OBSERVABILITY_IMPLEMENTATION_SUMMARY.md)
- [Scribe Implementation](../SCRIBE_IMPLEMENTATION_SUMMARY.md)
- [HITL Dashboard Implementation](../HITL_DASHBOARD_IMPLEMENTATION.md)
- [RAG Integration](../RAG_INTEGRATION_SUMMARY.md)

### Quick Start Guides
- [Observability Quick Start](../agent_system/observability/QUICKSTART.md)
- [Scribe Quick Start](../SCRIBE_QUICK_START.md)
- [Voice Integration Quick Start](../agent_system/voice/QUICK_START.md)
- [HITL Dashboard Quick Start](../hitl_dashboard/QUICK_START.md)

### Reference
- [Docker Quick Reference](../DOCKER_QUICK_REFERENCE.md)
- [Observability Quick Reference](../agent_system/observability/QUICK_REFERENCE.md)
- [Makefile Help](../Makefile) - `make help`

---

## Support

### Getting Help

1. **Check documentation**: Use navigation above to find relevant guide
2. **Run diagnostics**: See [TROUBLESHOOTING.md - Quick Diagnostics](./TROUBLESHOOTING.md#quick-diagnostics)
3. **Check logs**: `tail -f logs/agent-events.jsonl | jq`
4. **Review common issues**: See [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)

### Reporting Issues

When reporting issues, include:
- Output from health check script
- Error messages (full stack trace)
- Steps to reproduce
- Expected vs actual behavior
- SuperAgent version
- Environment (OS, Docker version, etc.)

---

## Document Updates

| Document | Version | Last Updated | Lines |
|----------|---------|--------------|-------|
| DEPLOYMENT.md | 1.0.0 | January 2025 | 1,550 |
| TROUBLESHOOTING.md | 1.0.0 | January 2025 | 1,411 |
| ARCHITECTURE.md | 1.0.0 | January 2025 | 1,394 |
| API_QUICK_START.md | 1.0.0 | October 2025 | 250 |
| API_HITL_ENDPOINTS.md | 1.0.0 | October 2025 | 1,200 |
| openapi-hitl.yaml | 1.0.0 | October 2025 | 800 |
| OPENAPI_USAGE.md | 1.0.0 | October 2025 | 450 |
| VOICE_COMMANDS_GUIDE.md | 1.0.0 | October 2025 | 1,100 |
| VOICE_QUICK_REFERENCE.md | 1.0.0 | October 2025 | 200 |

---

**Total Documentation**: 8,355 lines (240 KB)
**Maintainer**: SuperAgent Team
**License**: MIT
