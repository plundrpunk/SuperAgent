# SuperAgent Quick Start Guide

Get SuperAgent running in **5 minutes**! 🚀

## 1. Add Your API Keys (Required)

Edit `.env` and add your Anthropic API key (required):

```bash
# Open in your editor
nano .env
# or
code .env
```

**Minimum required:**
```bash
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

**Optional (for advanced features):**
```bash
OPENAI_API_KEY=sk-proj-your-key-here      # For voice commands
GEMINI_API_KEY=AIzaSy-your-key-here       # For AI-powered validation
```

**Get API keys:**
- Anthropic: https://console.anthropic.com/settings/keys
- OpenAI: https://platform.openai.com/api-keys
- Gemini: https://aistudio.google.com/apikey

## 2. Install Dependencies (1-2 minutes)

```bash
# Activate virtual environment
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Install Playwright browsers (one-time setup)
npx playwright install chromium
```

## 3. Start Services (30 seconds)

SuperAgent needs Redis for state management:

```bash
# Start all services with Docker
docker compose up -d

# Verify services are running
docker compose ps
```

You should see:
- ✅ `superagent-redis` - Running on port 6379
- ✅ `superagent-chromadb` - Running on port 8000 (optional)

## 4. Verify Installation

```bash
# Check system status
python agent_system/cli.py status

# Check health
python agent_system/cli.py health
```

You should see all components marked as ✓ ready!

## 5. Your First Commands

### Test the Router (No API calls, instant)

```bash
python agent_system/cli.py route write_test "Create login test with happy path"
```

**Expected output:**
```
✓ Routing Decision:
  Agent: scribe
  Model: claude-haiku-3.5-20241022
  Max Cost: $0.50
  Difficulty: easy
  Complexity Score: 3
  Reason: Simple test, using cost-optimized Haiku
```

### Generate a Test (Uses API, costs ~$0.01)

```bash
# Ask Kaya to create a simple test
python agent_system/cli.py kaya "write a test for user login"
```

Kaya will:
1. Route to Scribe agent
2. Generate Playwright test code
3. Save to `tests/login.spec.ts`
4. Report cost and execution time

### Run a Test

```bash
# Execute an existing test
python agent_system/cli.py run tests/login.spec.ts
```

### Check Costs

```bash
# View today's spending
python agent_system/cli.py cost daily

# View by agent
python agent_system/cli.py cost by-agent

# Check budget status
python agent_system/cli.py cost budget
```

### View Metrics

```bash
# Overall metrics summary
python agent_system/cli.py metrics summary

# Agent utilization
python agent_system/cli.py metrics agent-utilization

# Cost trends (last 7 days)
python agent_system/cli.py metrics trend --days 7
```

## 6. Full Pipeline Example (5 minutes, ~$0.50)

Run the complete closed-loop workflow:

```bash
# 1. Create test
python agent_system/cli.py kaya "write a test for shopping cart checkout"

# 2. Review with Critic (validates quality)
python agent_system/cli.py review tests/checkout.spec.ts

# 3. Run the test
python agent_system/cli.py run tests/checkout.spec.ts

# 4. If it fails, fix with Medic
python agent_system/cli.py kaya "fix the failing checkout test"
```

## 7. Advanced: Integration Tests

Run the full test suite to verify everything works:

```bash
# Run unit tests (fast, no API calls)
pytest tests/unit/ -v

# Run integration tests (slower, uses real agents)
pytest tests/integration/test_simple_crud_flow.py -v

# Run the complete pipeline test
pytest tests/integration/test_full_pipeline.py -v
```

## 8. Observability Dashboard

The WebSocket event stream is running on port 3010:

```bash
# Check if it's running
curl http://localhost:3010/health

# View real-time events (in browser)
# Connect to: ws://localhost:3010/agent-events
```

## Common Commands Cheat Sheet

```bash
# System
python agent_system/cli.py status          # System status
python agent_system/cli.py health          # Service health

# Routing
python agent_system/cli.py route <type> <description>

# Agents
python agent_system/cli.py kaya "<command>"           # Orchestrator
python agent_system/cli.py run <test_path>            # Execute test
python agent_system/cli.py review <test_path>         # Critic review

# Cost & Budget
python agent_system/cli.py cost daily                 # Daily report
python agent_system/cli.py cost budget                # Budget status
python agent_system/cli.py cost trend --days 7        # 7-day trend

# Metrics
python agent_system/cli.py metrics summary            # All metrics
python agent_system/cli.py metrics agent-utilization  # Agent usage
python agent_system/cli.py metrics cost-per-feature   # Feature costs

# Secrets (API Key Management)
python agent_system/cli.py secrets status             # Key status
python agent_system/cli.py secrets stats              # Usage stats
python agent_system/cli.py secrets rotate --service anthropic --new-key sk-ant-...

# HITL Queue
python agent_system/cli.py hitl list                  # List failed tasks
python agent_system/cli.py hitl stats                 # Queue statistics
```

## Troubleshooting

### "Redis connection failed"
```bash
# Start Redis with Docker
docker compose up -d redis

# Or start standalone
redis-server
```

### "API key not found"
```bash
# Verify .env file has keys
grep ANTHROPIC_API_KEY .env

# Make sure venv is activated
source venv/bin/activate
```

### "Module not found"
```bash
# Reinstall dependencies
pip install -r requirements.txt
```

### "Playwright not installed"
```bash
# Install Playwright browsers
npx playwright install chromium
```

### Check logs
```bash
# View agent logs
tail -f logs/agent-events.jsonl

# View Docker logs
docker compose logs -f
```

## Next Steps

1. **Read the full guide**: `docs/VOICE_COMMANDS_GUIDE.md` for voice control
2. **Explore metrics**: `METRICS_GUIDE.md` for KPI tracking
3. **API documentation**: `docs/API_HITL_ENDPOINTS.md` for HITL integration
4. **Performance tuning**: `PERFORMANCE_REPORT.md` for optimization tips
5. **Security**: `SECURITY.md` for production deployment

## Cost Targets (from CLAUDE.md)

- **Simple feature**: ~$0.50 (Target: ≤ $0.50) ✓
- **Complex feature**: ~$2-3 (Target: ≤ $3) ✓
- **Monthly budget**: Set in `.env` with `DAILY_BUDGET_USD=10`

## Support

- **Documentation**: `/docs` directory
- **Tests**: `/tests` for examples
- **Sprint summary**: `SPRINT_SUMMARY_2025-10-14.md` for what's implemented
- **Issues**: Check GitHub issues or create new one

---

**Ready to build? LFG! 🚀**

Start with: `python agent_system/cli.py kaya "write a test for user login"`
