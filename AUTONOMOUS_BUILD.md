# Autonomous Overnight Build System

## Overview

The SuperAgent system now supports **fully autonomous test generation, validation, and fixing**. You can kick off a build before bed and wake up to a complete, validated test suite for Cloppy AI.

## How It Works

### The Autonomous Loop

```
User Command: "build me <feature description>"
         ↓
    Kaya (Router)
         ↓
   ┌─────────────────────────────────────┐
   │ 1. Create Archon Project            │
   │ 2. Break feature into tasks         │
   └─────────────┬───────────────────────┘
                 ↓
   ┌─────────────────────────────────────┐
   │ For each task:                      │
   │                                     │
   │  ┌──────────────────────────────┐  │
   │  │ Scribe: Generate Test        │  │
   │  │ (Sonnet 4.5, $0.10 per test) │  │
   │  └─────────┬────────────────────┘  │
   │            ↓                        │
   │  ┌──────────────────────────────┐  │
   │  │ Runner: Validate Execution   │  │
   │  │ (Playwright, ~30s)           │  │
   │  └─────────┬────────────────────┘  │
   │            ↓                        │
   │       ┌────────┐                    │
   │       │ Pass?  │                    │
   │       └───┬────┘                    │
   │       Yes │ No                      │
   │           │  └──────────────┐       │
   │           │                 ↓       │
   │           │  ┌───────────────────┐  │
   │           │  │ Medic: Fix Test   │  │
   │           │  │ (Sonnet 4.5)      │  │
   │           │  │ Max 3 attempts    │  │
   │           │  └────────┬──────────┘  │
   │           │           │             │
   │           │           ↓             │
   │           │    Runner: Re-validate │
   │           │           │             │
   │           └───────────┘             │
   │                                     │
   │  ┌──────────────────────────────┐  │
   │  │ Archon: Update Task Status   │  │
   │  │ • done (validation passed)   │  │
   │  │ • review (failed after 3x)   │  │
   │  └──────────────────────────────┘  │
   └─────────────────────────────────────┘
                 ↓
         Report Summary
```

### Key Features

1. **Intelligent Task Breakdown** - Features are automatically split into granular tasks based on complexity:
   - Auth/database features: 4-6 detailed tasks (setup, implement, schema, UI, test, docs)
   - Test generation: 1 focused task
   - Medium features: 2 tasks (implement + test)

2. **Auto-Validation** - Every generated test is immediately executed by Runner to verify it works

3. **Self-Healing** - Failed tests trigger Medic to analyze and fix issues, up to 3 attempts:
   - Selector errors
   - Timing issues
   - Assertion failures
   - Network errors

4. **Progress Tracking** - Archon MCP tracks every task:
   - `todo` → `doing` → `done` (success)
   - `todo` → `doing` → `review` (failed after 3 attempts)

5. **Cost Control** - Optimized model usage:
   - Scribe: Sonnet 4.5 (~$0.10 per test)
   - Medic: Sonnet 4.5 (~$0.15 per fix)
   - Runner: Local Playwright (free)
   - Typical feature: $0.50-2.00

## Quick Start

### Test the Autonomous Loop

Run a quick test with a simple feature (2-5 minutes):

```bash
cd /Users/rutledge/Documents/DevFolder/SuperAgent
./test_autonomous_loop.sh
```

This will:
- Create an Archon project
- Break "board creation test" into tasks
- Execute all tasks autonomously
- Show complete execution trace

### Overnight Build - Complete Test Suite

Run the full Cloppy AI test suite generation (2-4 hours):

```bash
cd /Users/rutledge/Documents/DevFolder/SuperAgent
./build_complete_test_suite.sh
```

This generates **40+ comprehensive tests** covering:
- Board Management (4 tests)
- Node Operations (4 tests)
- Export Functionality (3 tests)
- Search & Filters (3 tests)
- Group Management (4 tests)
- AI Chat Integration (3 tests)
- Media Upload (3 tests)
- Canvas Navigation (3 tests)
- Real-time Collaboration (3 tests)
- RAG Training (3 tests)
- Authentication (4 tests)
- Billing & Pricing (3 tests)

**Cost estimate:** $5-10 total
**Time:** 2-4 hours (fully autonomous)

### Custom Feature Build

Build a specific feature:

```bash
docker compose -f config/docker-compose.yml exec -T superagent \
  python agent_system/cli.py kaya "build me <your feature description>"
```

Examples:
```bash
# User authentication
kaya "build me user login with email and password, password reset flow, and OAuth"

# Payment processing
kaya "build me payment checkout: view pricing, add to cart, enter payment details, verify order confirmation"

# Search functionality
kaya "build me search with filters: text search, date range filter, type filter, verify results accuracy"
```

## Understanding the Output

### Task Breakdown
```
📋 Created 4 tasks
  ✓ Task: Set up password reset test foundation
  ✓ Task: Implement core password reset test logic
  ✓ Task: Write tests for password reset test
  ✓ Task: Document password reset test
```

### Execution Progress
```
🚀 Starting autonomous execution of 4 tasks

📝 Task 1/4: Set up password reset test foundation
📝 Scribe: Generating test...
✅ Scribe: Test generated at tests/password_reset_foundation.spec.ts
🏃 Runner: Validating test...
✅ Task 1 completed successfully

📝 Task 2/4: Implement core password reset test logic
📝 Scribe: Generating test...
✅ Scribe: Test generated at tests/password_reset_logic.spec.ts
🏃 Runner: Validating test...
❌ Test failed, attempt 1/3
🏥 Medic: Fixing test (attempt 1)...
✅ Medic: Fix applied, re-validating...
🏃 Runner: Validating test...
✅ Task 2 completed successfully (1 fix)
```

### Final Summary
```
🏗️  Feature Build Complete!

Project: proj_1760912345
Total Tasks: 4
✅ Completed: 4
❌ Failed: 0

Completed Tasks:
  • Set up password reset test foundation
  • Implement core password reset test logic
  • Write tests for password reset test
  • Document password reset test
```

## Monitoring & Troubleshooting

### Check Archon Projects

View all projects and their status:
```bash
docker compose -f config/docker-compose.yml exec -T superagent \
  python -c "from agent_system.archon_client import get_archon_client; print(get_archon_client().find_tasks())"
```

### View Generated Tests

All tests are saved in:
```
/Users/rutledge/Documents/DevFolder/SuperAgent/tests/
```

### Review Failed Tasks

Tasks that failed after 3 fix attempts are marked with status `review` in Archon. Check logs for error details:

```bash
docker compose -f config/docker-compose.yml logs superagent | grep "❌"
```

### Cost Tracking

Each execution logs costs:
```
Cost breakdown:
  • Scribe (4 tests × $0.10): $0.40
  • Medic (2 fixes × $0.15): $0.30
  • Total: $0.70
```

## Configuration

### Adjust Fix Attempts

Edit `agent_system/agents/kaya.py`, line 1405:

```python
max_fix_attempts: int = 3  # Change to 1-5
```

### Change Model Selection

Force all tests to use specific model in `agent_system/agents/scribe_full.py`, line 120:

```python
# Current: Always Sonnet 4.5
model = self.SONNET_MODEL

# Alternative: Use Haiku for simple tests (when available)
model = self.SONNET_MODEL if model_name == "sonnet" else self.HAIKU_MODEL
```

### Customize Task Breakdown

Edit `agent_system/archon_client.py`, method `breakdown_feature_to_tasks()` starting at line 216 to adjust granularity logic.

## Integration with Archon MCP

The system is designed to use real Archon MCP server for:
- Project/task persistence
- RAG search of Cloppy AI docs (10,000+ pages)
- Version history
- Document storage

**Current status:** Using mock implementation (session auth pending)

**To enable real MCP:**
1. Fix Archon MCP session authentication
2. Update `archon_client.py` methods to call MCP tools:
   - `mcp__archon__manage_project`
   - `mcp__archon__manage_task`
   - `mcp__archon__find_tasks`
   - `mcp__archon__rag_search_knowledge_base`

## Success Metrics

### What "Success" Looks Like

After overnight build:
- ✅ 40+ tests generated
- ✅ 95%+ passing rate (with auto-fixes)
- ✅ All tests use proper data-testid selectors
- ✅ All tests have screenshots
- ✅ All tests follow VisionFlow patterns
- ✅ Failed tests marked for human review
- ✅ Cost under $10 total

### Example Overnight Result

```
🌙 OVERNIGHT BUILD COMPLETE

Generated: 42 tests
Passed: 39 (92.8%)
Fixed: 18 (Medic auto-fixed)
Failed: 3 (marked for review)
Time: 3h 24m
Cost: $7.80

Failed tests:
  • tests/real_time_collaboration_conflict.spec.ts (WebSocket timeout)
  • tests/rag_training_large_document.spec.ts (Memory error)
  • tests/payment_3d_secure.spec.ts (Stripe sandbox issue)

Action Required:
  Review 3 failed tests manually
  All other tests ready for production
```

## Next Steps

1. **Run Quick Test** - Validate autonomous loop with `./test_autonomous_loop.sh`
2. **Start Overnight Build** - Kick off full suite with `./build_complete_test_suite.sh`
3. **Review Results** - Check tests/ directory in the morning
4. **Fix Stragglers** - Manually address tasks marked `review`
5. **Deploy to CI** - Add passing tests to CI pipeline

## Voice Integration (Coming Soon)

Once voice is re-enabled:

```
You: "Kaya, build me the complete Cloppy AI test suite overnight"
Kaya: "Starting autonomous build of 12 features with 40+ tests.
       This will take approximately 3 hours. I'll notify you when complete.
       Estimated cost: $6-8. Proceed?"
You: "Yes, do it"
Kaya: "Build started. Go to sleep - I'll handle everything."

[3 hours later]

Kaya: "Build complete! Generated 42 tests, 39 passing, 3 need review.
       Total cost: $7.80. Ready for your review."
```

## Architecture

### Files Modified

- `agent_system/agents/kaya.py` - Added `_execute_test_task_with_validation()` and enhanced `_handle_build_feature()`
- `agent_system/archon_client.py` - Added `breakdown_feature_to_tasks()` with intelligent task splitting

### New Files

- `build_complete_test_suite.sh` - Full overnight build script
- `test_autonomous_loop.sh` - Quick validation test
- `AUTONOMOUS_BUILD.md` - This documentation

### Agent Flow

1. **Kaya** (Router) - Parses intent, creates project, orchestrates execution
2. **Scribe** (Test Writer) - Generates tests with Sonnet 4.5
3. **Runner** (Validator) - Executes tests via Playwright
4. **Medic** (Fixer) - Diagnoses and fixes failures with Sonnet 4.5
5. **Archon** (State) - Tracks all projects, tasks, and progress

## FAQ

**Q: Can I pause and resume a build?**
A: Not yet - builds run to completion. To pause, Ctrl+C and restart with same feature description.

**Q: What if my environment isn't ready (DB, Redis, etc)?**
A: Tests will fail validation. Ensure Docker services are running:
```bash
docker compose -f config/docker-compose.yml ps
```

**Q: How do I prioritize certain features?**
A: Run them individually instead of using the full suite script:
```bash
kaya "build me authentication tests" # High priority first
kaya "build me export tests"          # Then other features
```

**Q: Can I customize test templates?**
A: Yes, edit `agent_system/agents/scribe_full.py` system prompt (lines 80-150) to adjust test patterns.

**Q: What about flaky tests?**
A: Critic validation (not yet enabled) will reject flaky patterns. Medic also identifies and fixes common flake sources (timing, selectors).

## Support

Issues? Check:
1. Docker services running: `docker compose -f config/docker-compose.yml ps`
2. Redis connectivity: `redis-cli ping`
3. Anthropic API key: Check `.env` file
4. Logs: `docker compose -f config/docker-compose.yml logs -f superagent`

For Archon MCP issues:
```bash
cd "/Users/rutledge/Documents/DevFolder/New Archon/archon"
docker compose logs -f archon-mcp
```
