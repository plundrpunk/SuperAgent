---
description: Ensure the agent has fully read and understands the project's documentation system, structure, and rules (claude.md, SOPs, and doc index).
---
# Goal: SuperAgent Context Priming and Documentation Review

IMPORTANT: You are initiating work on the SuperAgent multi-agent testing system. Your primary goal is to **prime your context** by thoroughly reviewing the repository structure, documentation, and architectural patterns.

## 1. Core Context Files (MUST READ FIRST)

### Primary Instructions
- **`CLAUDE.md`** (root) - Project instructions, agent guidance, conventions, and implementation blueprint
- **`README.md`** (root) - Project overview, quick start, status, and key technical decisions

### Repository Structure (Post-Reorganization)
The repository follows professional Unix/Linux conventions:

```
/SuperAgent/
├── CLAUDE.md                  # AI agent instructions (READ FIRST!)
├── README.md                  # Project overview
├── Makefile                   # Docker & build commands
├── requirements.txt           # Python dependencies
│
├── agent_system/             # Core Python code
│   ├── agents/               # Agent implementations (Kaya, Scribe, Runner, Medic, Critic, Gemini)
│   ├── state/                # State management (Redis, Vector DB)
│   ├── hitl/                 # Human-in-the-Loop system
│   ├── observability/        # Metrics, logging, event streaming
│   └── voice/                # Voice control integration (TypeScript)
│
├── tests/                    # Playwright tests & test suites
│   ├── unit/                 # Unit tests
│   ├── integration/          # Integration tests
│   ├── e2e/                  # End-to-end tests
│   └── templates/            # Test templates
│
├── bin/                      # User executables
│   ├── start_superagent.sh   # Main startup script
│   ├── run_kaya.sh           # Kaya CLI wrapper
│   └── kaya_quick_access.py  # GUI interface
│
├── web/                      # Web interfaces
│   ├── dashboard_server.py   # HTTP dashboard
│   ├── websocket_server.py   # Event streaming
│   └── hitl_dashboard/       # HITL UI
│
├── config/                   # All configuration
│   ├── docker-compose.yml    # Docker orchestration
│   ├── Dockerfile            # Container definition
│   ├── pyproject.toml        # Python project config
│   └── pytest.ini            # Test configuration
│
├── data/                     # Runtime data
│   ├── logs/                 # Application logs
│   ├── vector_db/            # Vector database (cold storage)
│   └── backups/              # Data backups
│
├── build/                    # Build outputs (gitignored)
│   ├── coverage/             # Test coverage reports
│   ├── artifacts/            # Test artifacts
│   └── test-results/         # Test execution results
│
├── docs/                     # All documentation
│   ├── README.md             # Documentation navigation hub
│   ├── getting-started/      # Quick start guides
│   ├── summaries/            # High-level summaries (11 files)
│   ├── archives/             # Historical docs (62 files)
│   ├── ARCHITECTURE.md       # System architecture (55KB)
│   ├── DEPLOYMENT.md         # Deployment guide (36KB)
│   ├── TROUBLESHOOTING.md    # Problem solving (27KB)
│   └── VOICE_COMMANDS_GUIDE.md # Voice integration (27KB)
│
├── tools/                    # Development utilities
│   ├── validation/           # Validation scripts
│   ├── testing/              # Test utilities
│   └── maintenance/          # Maintenance scripts
│
└── examples/                 # Usage examples
    ├── basic/                # Basic examples
    ├── advanced/             # Advanced patterns
    ├── integrations/         # Integration examples
    └── workflows/            # Complete workflows
```

## 2. Documentation System (READ IN ORDER)

### Quick Overview (Start Here)
1. **`docs/summaries/README.md`** - Documentation navigation and index
2. **`docs/summaries/DOC_SUMMARY_Project_Overview.md`** - Core concept, setup, usage
3. **`docs/summaries/DOC_SUMMARY_Architecture.md`** - System architecture overview

### High-Level Summaries (11 files ~4KB each)
Read these for quick understanding:
- **Project_Overview.md** - Core concept, requirements, setup
- **Architecture.md** - System design, agent roles, tech stack
- **Agent_Details.md** - Detailed agent specifications
- **Docker_and_Deployment.md** - Containerization and deployment
- **Voice_Integration.md** - Voice control architecture
- **Data_and_Lifecycle.md** - State management, MCP integration
- **Observability.md** - Monitoring, metrics, cost analytics
- **Testing.md** - Test strategy and validation
- **HITL.md** - Human-in-the-Loop escalation
- **Security.md** - Security architecture and best practices
- **Status_Reports.md** - Implementation progress

### Comprehensive Documentation (Read as needed)
- **`docs/ARCHITECTURE.md`** (55KB) - Complete system architecture, diagrams, patterns
- **`docs/DEPLOYMENT.md`** (36KB) - Full deployment guide, Docker, production
- **`docs/TROUBLESHOOTING.md`** (27KB) - Common issues, debugging, solutions
- **`docs/VOICE_COMMANDS_GUIDE.md`** (27KB) - Voice control reference

### Getting Started Guides
- **`docs/getting-started/START_HERE.md`** - Quick launch guide
- **`docs/getting-started/QUICK_START.md`** - 5-minute setup
- **`docs/getting-started/YOUR_FIRST_5_MINUTES.md`** - Tutorial
- **`docs/getting-started/LAUNCH_GUIDE.md`** - Complete operational guide

## 3. Critical Architectural Patterns

### Agent System
**6 Specialized Agents** (each with specific role):
- **Kaya** (Router/Orchestrator) - Claude Haiku, routes and coordinates
- **Scribe** (Test Writer) - Claude Sonnet 4.5, generates Playwright tests
- **Runner** (Test Executor) - Claude Haiku, runs tests and parses output
- **Medic** (Bug Fixer) - Claude Sonnet 4.5, applies surgical fixes
- **Critic** (Pre-Validator) - Claude Haiku, quality gate before validation
- **Gemini** (Validator) - Gemini 2.5 Pro, browser validation with screenshots

### Cost Optimization Strategy
- **70% Haiku** - Routing, execution, pre-validation (~$0.01 per task)
- **30% Sonnet/Gemini** - Complex tasks, validation (~$0.10-0.50 per task)
- **Target**: $0.50 per feature, $2-3 for critical auth/payment paths
- **Budget Enforcement**: Per-session ($2), daily ($10), monthly ($200) limits

### State Management
- **Hot State (Redis, 1h TTL)** - Session data, task queue, voice transcripts
- **Cold State (Vector DB, Permanent)** - Test patterns, bug fixes, HITL annotations

### Validation Pipeline (3-Stage Quality Gate)
1. **Static Analysis** (Critic) - Fast anti-pattern detection
2. **Test Execution** (Runner) - Verify test compiles and runs
3. **Browser Validation** (Gemini) - Prove correctness with screenshots

## 4. Key Conventions and Standards

### Code Style
- **Python**: PEP 8, type hints, dataclasses for structured data
- **TypeScript**: Strict mode, async/await patterns
- **Tests**: Playwright with data-testid selectors (NO CSS classes, NO nth())

### Test Requirements (from Critic)
- ✅ data-testid selectors only
- ✅ Minimum 1 expect() assertion
- ✅ Screenshots after major steps
- ❌ NO .nth() selectors
- ❌ NO generated CSS classes (`.css-[a-z0-9]+`)
- ❌ NO waitForTimeout (use waitForSelector)
- ❌ Execution time ≤ 60 seconds

### Medic's Hippocratic Oath
- Apply **minimal surgical fixes** only
- MUST capture baseline test results before fix
- Run regression suite after fix (tests/auth.spec.ts, tests/core_nav.spec.ts)
- **max_new_failures: 0** (cannot introduce new failures)
- Produce artifacts: fix.diff, regression_report.json

### File Naming Conventions
- Tests: `feature_name.spec.ts` (e.g., `user_login.spec.ts`)
- Agents: `agent_name.py` (e.g., `kaya.py`, `scribe.py`)
- Configs: `service_name.yaml` (e.g., `router_policy.yaml`)

## 5. Configuration Files

### Agent Configurations (.claude/agents/)
- `kaya.yaml` - Router/Orchestrator config
- `scribe.yaml` - Test Writer config
- `runner.yaml` - Test Executor config
- `medic.yaml` - Bug Fixer config
- `critic.yaml` - Pre-Validator config
- `gemini.yaml` - Browser Validator config

### System Configurations (.claude/)
- `router_policy.yaml` - Routing rules and cost policies
- `observability.yaml` - Event streaming and metrics config

### Docker Configurations (config/)
- `docker-compose.yml` - Service orchestration (ports 8000, 8001, 8002)
- `Dockerfile` - Container build instructions
- `.dockerignore` - Build exclusions

## 6. Common Operations

### Starting SuperAgent
```bash
# Option 1: Makefile (recommended)
make up
make status

# Option 2: Wrapper script
./docker-compose up -d
./docker-compose ps

# Option 3: Direct executables
./bin/start_superagent.sh
./bin/run_kaya.sh "status"
```

### Running Kaya Commands
```bash
# Via Makefile
make cli-kaya CMD="write a test for user login"

# Via wrapper
./docker-compose exec superagent python agent_system/cli.py kaya "write a test"

# Via bin script
./bin/run_kaya.sh "write a test for checkout"
```

### Testing
```bash
make test              # All tests
make test-unit         # Unit tests only
make test-integration  # Integration tests only
pytest tests/unit/ -v  # Direct pytest
```

## 7. HITL (Human-in-the-Loop) System

When agents fail 3+ times, tasks escalate to HITL queue:
- **Priority Scoring**: Based on attempts, feature criticality, error type
- **Dashboard**: http://localhost:8001 (when running)
- **Resolution**: Humans annotate with root cause, fix strategy, notes
- **Learning**: Annotations stored in Vector DB for future reference

## 8. Voice Control Integration

**OpenAI Realtime API** integration for voice commands:
- **Wake Word**: "Kaya"
- **Intents**: create_test, run_test, fix_failure, validate, status
- **Text Fallback**: `node dist/text_chat.js` for development
- **Voice Session**: `node dist/examples.js` for microphone input

## 9. Observability

Three dashboards available:
- **Port 8000**: Observability dashboard (WebSocket events)
- **Port 8001**: HITL dashboard (human escalations)
- **Port 8002**: Metrics and monitoring endpoint

Real-time event streaming via WebSocket (ws://localhost:3010/agent-events)

## 10. Important Constraints

### Security
- ✅ .env file is gitignored (NEVER commit API keys)
- ✅ Secrets manager handles API key rotation
- ✅ Sandbox execution for untrusted code
- ✅ Rate limiting per agent/model

### Tool Permissions
Each agent has strictly defined tool access (see `tools.yaml` in CLAUDE.md)

### Cost Enforcement
Router enforces per-feature cost caps with overrides for critical paths:
- Default: $0.50 per feature
- Auth/Payment: Up to $3.00 (critical paths)
- Budget alerts at 80% usage

## 11. Troubleshooting Quick Reference

Common issues:
- **Redis connection failed**: Start Redis (`redis-server` or `make up`)
- **Docker build failed**: Check `config/Dockerfile` paths
- **Port conflicts**: Ports 8000-8002, 3010 must be free
- **API key errors**: Verify `.env` file has keys set
- **Module not found**: Activate venv (`source venv/bin/activate`)

See `docs/TROUBLESHOOTING.md` for comprehensive debugging guide.

## 12. Recent Major Changes

**Repository Reorganization (Oct 19, 2025)**:
- ✅ 63% cleaner root directory (51→19 items)
- ✅ Professional structure (bin/, config/, data/, build/, web/, tools/)
- ✅ Consolidated documentation in docs/
- ✅ Updated Makefile and docker-compose.yml paths
- ✅ Enhanced .gitignore for better security

**Key Migrations**:
- Scripts → bin/ (executables) and tools/ (utilities)
- Configs → config/ (all configuration)
- Runtime data → data/ (logs, vector_db, backups)
- Build outputs → build/ (coverage, artifacts, test-results)
- Web assets → web/ (dashboards, servers)
- Docs → docs/ (with subdirectories)

---

## Usage Notes

### Arguments Support
Pass specific files or topics: `/prime_repo_docs agent_architecture`

### Context Engineering
This command ensures you have the **full necessary context** as the "parent agent." Sub-agents operate in isolated contexts and communicate primarily through files, so thorough context priming is critical.

### When to Use
- Starting new tasks or features
- After repository reorganization
- When unclear about architecture
- Before making significant changes
- When debugging complex issues

### Memory Integration
Review all information previously saved to memory using pound symbol (`#`) notation.

$arguments
