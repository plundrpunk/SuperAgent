# SuperAgent - Voice-Controlled Multi-Agent Testing System

**Status**: Sprint Day 1 Complete - Foundation Ready

## Overview

SuperAgent is a Voice-Controlled Multi-Agent Testing System that automates Playwright test creation, execution, validation, and bug fixing through a coordinated team of specialized AI agents.

## Architecture

### 🤖 Agents Implemented

- **Kaya (Router/Orchestrator)** ✅ - Routes commands and coordinates agents
- **Runner (Test Executor)** ✅ - Executes Playwright tests via subprocess
- **Critic (Pre-Validator)** ✅ - Quality gate before expensive validation
- **Gemini (Validator)** ✅ - Real browser validation with screenshots
- **Scribe (Test Writer)** 🚧 - Generates Playwright tests (stub created)
- **Medic (Bug Fixer)** 🚧 - Applies surgical fixes (stub created)

### 🏗️ Core Infrastructure

- ✅ Project structure and configuration
- ✅ Router with cost enforcement and complexity estimation
- ✅ Redis client for hot state (session, task queue, transcripts)
- ✅ Vector DB client for cold storage (RAG patterns, bug fixes, HITL)
- ✅ HITL queue system with priority scoring
- ✅ Validation rubric with JSON schema
- ✅ Playwright test templates and baseline tests

### 📁 Project Structure

```
SuperAgent/
├── agent_system/
│   ├── agents/
│   │   ├── base_agent.py      # Base class for all agents
│   │   ├── kaya.py             # Orchestrator ✅
│   │   ├── runner.py           # Test executor ✅
│   │   ├── critic.py           # Pre-validator ✅
│   │   └── ...                 # Scribe, Medic, Gemini (stubs)
│   ├── state/
│   │   ├── redis_client.py     # Hot state management ✅
│   │   └── vector_client.py    # Cold storage + RAG ✅
│   ├── hitl/
│   │   ├── schema.json         # HITL queue schema ✅
│   │   └── queue.py            # Queue management ✅
│   ├── router.py               # Routing logic ✅
│   ├── complexity_estimator.py # Task complexity scoring ✅
│   ├── validation_rubric.py    # Validation schema ✅
│   └── cli.py                  # CLI entry point ✅
├── tests/
│   ├── templates/
│   │   └── playwright.template.ts  # Test template ✅
│   ├── auth.spec.ts            # Baseline regression test ✅
│   └── core_nav.spec.ts        # Baseline regression test ✅
├── .claude/
│   ├── agents/                 # Agent YAML configs
│   ├── router_policy.yaml      # Routing and cost policies
│   └── observability.yaml      # Event streaming config
├── requirements.txt            # Python dependencies ✅
├── pyproject.toml              # Package config ✅
└── pytest.ini                  # Test config ✅
```

## Requirements

- **Python 3.10+** (3.11+ recommended)
- Node.js 16+ (for Playwright)
- Redis (optional, for state management)
- Git

## Quick Start

### 1. Set Up Python Environment

```bash
# Ensure you have Python 3.11+ installed
python3.11 --version  # Should show 3.11.x or higher

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Upgrade pip and install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Install Playwright browsers
npx playwright install
```

### 2. Configure Environment

Create `.env` file:

```env
# Redis (optional - uses localhost by default)
REDIS_HOST=localhost
REDIS_PORT=6379

# Vector DB
VECTOR_DB_PATH=./vector_db

# API Keys (for future agents)
ANTHROPIC_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
GEMINI_API_KEY=your_key_here

# Test target
BASE_URL=http://localhost:3000
```

### 3. Try the CLI

```bash
# Activate virtual environment first
source venv/bin/activate

# Route a task
python agent_system/cli.py route write_test "Create login test with OAuth"

# Review a test with Critic
python agent_system/cli.py review tests/auth.spec.ts

# Check system status
python agent_system/cli.py status

# Run Kaya orchestrator
python agent_system/cli.py kaya create test for user registration
```

## Implementation Status

### ✅ Completed (Sprint Day 1)

1. **Foundation** (Waves 1-2)
   - Project structure
   - Configuration files (pyproject.toml, pytest.ini, requirements.txt)
   - Test templates and baseline tests

2. **Core Modules** (Wave 3)
   - `complexity_estimator.py` - Rule-based scoring
   - `validation_rubric.py` - JSON schema validation
   - `redis_client.py` - Hot state with 1h TTL
   - `vector_client.py` - RAG with embeddings

3. **Router** (Wave 5)
   - `router.py` - Routing logic with cost enforcement
   - Cost overrides for critical paths (auth/payment)
   - Budget tracking and enforcement

4. **Agents** (Wave 6 - Partial)
   - Kaya orchestrator - Intent parsing and routing
   - Runner agent - Test execution via subprocess
   - Critic agent - Pre-validation with anti-pattern detection
   - Gemini agent - Browser validation with screenshots (18 tests, 92% coverage)

5. **HITL System**
   - Queue schema and management
   - Priority scoring algorithm
   - Human annotation storage in vector DB

### 🚧 In Progress

- **Scribe Agent**: Test generation with Anthropic API
- **Medic Agent**: Bug fixing with regression testing

### 📋 Remaining Work

1. **Complete Core Agents** (2-4 hours)
   - ✅ Implement Gemini browser validation
   - Implement Scribe test generation with RAG
   - Implement Medic regression testing workflow

2. **Integration** (2-3 hours)
   - Wire closed-loop: Scribe → Critic → Runner → Gemini → Medic
   - End-to-end integration tests
   - Cost tracking validation

3. **Voice Integration** (3-4 hours)
   - OpenAI Realtime API connection
   - Intent parsing from voice
   - Response synthesis

4. **Observability** (2-3 hours)
   - WebSocket event streaming
   - Real-time dashboard
   - Metrics aggregation and alerting

5. **Production** (2-3 hours)
   - Docker containerization
   - Security audit
   - Deployment documentation

## Key Technical Decisions

### Cost Optimization

- **70% Haiku Usage**: Routing, execution, pre-validation
- **Sonnet for Complexity**: Test writing, bug fixing
- **Gemini Only for Final Validation**: Real browser proof
- **Target**: $0.50 per feature ($2-3 for auth/payment)

### Complexity Estimation

Scoring rules:
- Steps > 4: +2
- Auth/OAuth: +3
- File ops: +2
- WebSocket: +3
- Payment: +4
- Mocking: +2
- **Threshold**: ≥5 = hard (Sonnet), <5 = easy (Haiku)

### State Management

- **Hot State (Redis, 1h TTL)**: Session data, task queue, voice transcripts
- **Cold State (Vector DB, Permanent)**: Test patterns, bug fixes, HITL annotations

## Testing

```bash
# Run unit tests (when implemented)
pytest tests/unit/

# Run integration tests (when implemented)
pytest tests/integration/

# Run with coverage
pytest --cov=agent_system --cov-report=html
```

## Architecture Highlights

### Agent Communication

```python
# 1. User → Kaya (orchestrator)
result = kaya.execute("create test for user login")

# 2. Kaya → Router → Select Agent
routing = router.route("write_test", "user login")

# 3. Agent executes and returns AgentResult
agent_result = AgentResult(
    success=True,
    data={"status": "completed"},
    cost_usd=0.02,
    execution_time_ms=1500
)
```

### HITL Escalation

```python
# Medic fails 3 times → Escalate to HITL
hitl_queue.add({
    "task_id": "t_123",
    "feature": "login",
    "attempts": 3,
    "last_error": "Selector timeout",
    "priority": 0.75
})

# Human resolves with annotation
hitl_queue.resolve("t_123", {
    "root_cause_category": "selector_flaky",
    "fix_strategy": "update_selectors",
    "patch_diff": "...",
    "human_notes": "Selectors were too brittle"
})
```

## Next Session Priorities

1. ✅ Complete Scribe agent implementation
2. ✅ Complete Medic agent with regression testing
3. ✅ Complete Gemini validation agent
4. ✅ End-to-end integration test
5. ✅ Deploy to staging environment

## Contributing

See `CLAUDE.md` for detailed implementation guidance and conventions.

## License

MIT
