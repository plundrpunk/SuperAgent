# Your First 5 Minutes with SuperAgent

## What You're About To Do

You'll run SuperAgent's router to see how it automatically selects the right agent and model for a task - **without making any API calls** (completely free!).

## Prerequisites ✅

- ✅ Docker installed and running
- ✅ Python 3.9+ with venv
- ✅ API key in `.env` file

## Step 1: Start Services (Already Done!)

```bash
cd /Users/rutledge/Documents/DevFolder/SuperAgent
docker compose up -d
```

Wait for services to be "healthy" (check with `docker compose ps`)

## Step 2: Activate Virtual Environment

```bash
source venv/bin/activate
```

You should see `(venv)` in your terminal prompt.

## Step 3: Test the Router (FREE - No API calls!)

The router decides which agent and model to use based on task complexity. Try these:

### Simple Task → Uses Haiku (Cheap)

```bash
python agent_system/cli.py route write_test "test user login"
```

**Expected output:**
```
✓ Routing Decision:
  Agent: scribe
  Model: claude-haiku-3.5-20241022  ← Cheap model!
  Max Cost: $0.50
  Difficulty: easy
  Complexity Score: 2
```

### Complex Task → Uses Sonnet (Powerful)

```bash
python agent_system/cli.py route write_test "test OAuth SSO login with multi-factor authentication and session persistence"
```

**Expected output:**
```
✓ Routing Decision:
  Agent: scribe
  Model: claude-sonnet-4-20250514  ← Powerful model!
  Max Cost: $0.50
  Difficulty: hard
  Complexity Score: 8
  Reason: Complex auth flow requires Sonnet
```

## Step 4: Check System Status

```bash
python agent_system/cli.py status
```

You should see ✓ checkmarks for all implemented components!

## Step 5: Your First REAL Command (Costs ~$0.01)

Now let's actually generate a test file:

```bash
python agent_system/cli.py kaya "write a test for user login"
```

**What happens:**
1. Kaya receives your command
2. Routes to Scribe agent
3. Scribe uses Claude API to generate test code
4. Saves to `tests/login.spec.ts`
5. Reports cost and execution time

**Example output:**
```
✓ Success: true
Data: {
  'test_path': 'tests/login.spec.ts',
  'test_generated': true,
  'complexity_score': 2
}
Execution time: 3500ms
```

## Step 6: View the Generated Test

```bash
cat tests/login.spec.ts
```

You'll see a complete Playwright test with:
- Proper imports
- Data-testid selectors
- Clear assertions
- Comments explaining the flow

## Step 7: Check the Cost

```bash
python agent_system/cli.py cost daily
```

You should see ~$0.01-0.02 for that one test generation!

## What to Try Next

### Run the Test

```bash
python agent_system/cli.py run tests/login.spec.ts
```

### Review with Critic (Quality Check)

```bash
python agent_system/cli.py review tests/login.spec.ts
```

Critic checks for:
- Flaky selectors (nth(), css classes)
- Missing assertions
- Timeout usage
- Complexity estimation

### View Metrics

```bash
python agent_system/cli.py metrics summary
```

### Explore Integration Tests

```bash
# Fast unit tests (no API calls)
pytest tests/unit/test_router.py -v

# Integration test (full pipeline)
pytest tests/integration/test_simple_crud_flow.py -v
```

## Common Commands Reference

```bash
# System
python agent_system/cli.py status
python agent_system/cli.py health

# Generate tests
python agent_system/cli.py kaya "write a test for <feature>"

# Execute tests
python agent_system/cli.py run tests/<file>.spec.ts

# Review quality
python agent_system/cli.py review tests/<file>.spec.ts

# Check costs
python agent_system/cli.py cost daily
python agent_system/cli.py cost budget

# View metrics
python agent_system/cli.py metrics summary
python agent_system/cli.py metrics agent-utilization
```

## Troubleshooting

### "Redis connection failed"
```bash
docker compose ps  # Check if redis is running
docker compose logs redis  # Check for errors
```

### "Anthropic API key not found"
```bash
cat .env | grep ANTHROPIC  # Should show your key
source venv/bin/activate   # Make sure venv is active
```

### Generated test file not found
```bash
ls -la tests/  # Check the tests directory
# May need to create it:
mkdir -p tests
```

## Cost Expectations

- **Router decision**: $0 (no API calls)
- **Simple test generation**: ~$0.01-0.02 (Haiku)
- **Complex test generation**: ~$0.05-0.10 (Sonnet)
- **Full pipeline** (Scribe → Critic → Runner → Gemini → Medic): ~$0.50

## You're Ready! 🚀

The system is now running. Try the router commands above, then generate your first test!

For more advanced features, see:
- `QUICK_START.md` - Complete guide
- `docs/VOICE_COMMANDS_GUIDE.md` - Voice control
- `METRICS_GUIDE.md` - Performance tracking
- `docs/API_HITL_ENDPOINTS.md` - API integration

**Next**: `python agent_system/cli.py kaya "write a test for user signup"`
