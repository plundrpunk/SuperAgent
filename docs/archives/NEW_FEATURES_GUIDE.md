# SuperAgent - New Features Guide

## 🎉 Three Major Features Just Added!

### 1. 👀 Visible Browser Windows

**What it does**: Agents now run tests in VISIBLE browser windows so you can watch them work in real-time!

**How it works**:
- Changed `headless: false` in `.claude/agents/gemini.yaml` (line 35)
- Gemini agent now respects this setting and passes `--headed` flag to Playwright
- When tests run, you'll see actual Chrome/Firefox windows open and interact with your app

**Try it**:
```bash
# Run Kaya and watch the browser appear!
python agent_system/cli.py kaya "validate tests/board_creation_for.spec.ts"
```

**Benefits**:
- See exactly what the AI is testing
- Visual debugging - spot issues immediately
- Understand test behavior intuitively
- Great for demos and presentations

**To toggle back to headless**: Set `headless: true` in `.claude/agents/gemini.yaml`

---

### 2. 📸 Live Screenshot Streaming to Dashboard

**What it does**: Screenshots from test execution now appear in real-time on your dashboard!

**How it works**:
- Gemini agent broadcasts `screenshot_captured` events when tests run
- Dashboard listens for these events via WebSocket
- Screenshots display in a grid gallery with metadata

**Try it**:
1. Open the dashboard in your browser:
   ```bash
   open /Users/rutledge/Documents/DevFolder/SuperAgent/dashboard.html
   ```

2. Run a test that generates screenshots:
   ```bash
   python agent_system/cli.py kaya "write a test for Cloppy AI file upload"
   ```

3. Watch the "📸 Live Screenshots" section populate in real-time!

**What you'll see**:
- Screenshot thumbnails in a responsive grid
- Screenshot number (e.g., "1/5", "2/5")
- Test name
- Timestamp
- Up to 12 most recent screenshots

**Dashboard features**:
- **Total Events**: Count of all agent events
- **Active Tasks**: Currently running tasks
- **Total Cost**: Cumulative API costs
- **Success Rate**: % of successful completions
- **Live Events**: Real-time event stream with JSON payloads
- **Live Screenshots**: Visual evidence of test execution

---

### 3. 🔍 Test Coverage Analysis

**What it does**: Kaya can now analyze test coverage and tell you what's covered!

**Voice commands**:
- "Kaya, check test coverage"
- "Kaya, test coverage for src/components/Board.tsx"
- "Kaya, what's the coverage?"
- "Kaya, how much coverage do we have?"

**Try it**:
```bash
# Check overall project coverage
python agent_system/cli.py kaya "check test coverage"

# Check coverage for specific file
python agent_system/cli.py kaya "check coverage for src/auth/Login.tsx"
```

**What you get**:
```json
{
  "overall_coverage": 78.5,
  "grade": "C",
  "summary": {
    "statements": {
      "total": 450,
      "covered": 353,
      "pct": 78.5
    },
    "branches": { "pct": 65.2 },
    "functions": { "pct": 82.1 },
    "lines": { "pct": 78.5 }
  },
  "recommendations": [
    "Good coverage! Aim for 85%+ for critical paths."
  ]
}
```

**For specific files**:
```json
{
  "file": "src/auth/Login.tsx",
  "coverage_percentage": 92.3,
  "total_statements": 52,
  "covered_statements": 48,
  "uncovered_statements": 4,
  "uncovered_lines": [45, 67, 89, 112]
}
```

**Coverage grading**:
- **A**: 90%+ (Excellent)
- **B**: 80-89% (Very Good)
- **C**: 70-79% (Good)
- **D**: 60-69% (Fair)
- **F**: <60% (Needs Improvement)

**How it works**:
1. Parses Istanbul/NYC coverage reports from `coverage/` directory
2. Analyzes `coverage-summary.json` or `coverage-final.json`
3. Calculates statement/branch/function coverage
4. Identifies uncovered lines
5. Provides actionable recommendations

**Setup for coverage** (if not already configured):

Add to `playwright.config.ts`:
```typescript
export default defineConfig({
  use: {
    coverage: true
  }
});
```

Then run tests with coverage:
```bash
npx playwright test --coverage
```

---

## 🎬 Complete Workflow Demo

Here's how all three features work together:

### Step 1: Start the Dashboard
```bash
open /Users/rutledge/Documents/DevFolder/SuperAgent/dashboard.html
```

### Step 2: Start Voice Chat
```bash
cd /Users/rutledge/Documents/DevFolder/SuperAgent/agent_system/voice
REDIS_HOST=localhost node dist/voice_chat.js
```

### Step 3: Give Voice Commands
```
You: "Kaya, write a test for Cloppy AI board creation"
```

**What happens**:
1. **Scribe** writes the test file
2. **Dashboard** shows `task_queued` event
3. **Critic** validates test quality
4. **Runner** executes the test
5. **Visible browser** opens - you see Chrome testing your app!
6. **Screenshots appear** in dashboard as test runs
7. **Gemini** validates with visual proof
8. **Dashboard** shows final results + costs

### Step 4: Check Coverage
```
You: "Kaya, check test coverage"
```

Kaya responds:
```
"Overall test coverage is 78.5%, Grade C.
You have 353 out of 450 statements covered.
Good coverage! Aim for 85% or higher for critical paths."
```

---

## 📊 Dashboard URL

Your dashboard is accessible at:
```
file:///Users/rutledge/Documents/DevFolder/SuperAgent/dashboard.html
```

**Features**:
- ✅ Real-time event streaming
- ✅ Live cost tracking
- ✅ Success rate metrics
- ✅ Screenshot gallery (NEW!)
- ✅ Active task monitoring
- ✅ WebSocket reconnection on disconnect

**WebSocket endpoint**: `ws://localhost:3010/agent-events`

---

## 🎤 Voice Commands Reference

### Test Creation
- "Kaya, write a test for user authentication"
- "Kaya, create a test for file upload"
- "Kaya, generate a test for checkout flow"

### Test Execution
- "Kaya, run tests/auth.spec.ts"
- "Kaya, execute all tests"

### Validation
- "Kaya, validate tests/board_creation.spec.ts"
- "Kaya, verify the login flow"

### Coverage Analysis (NEW!)
- "Kaya, check test coverage"
- "Kaya, what's the coverage for src/Board.tsx?"
- "Kaya, how much coverage do we have?"

### Status
- "Kaya, what's the status?"
- "Kaya, show me session stats"

### Full Pipeline
- "Kaya, full pipeline for shopping cart"
- "Kaya, end-to-end test for payment processing"

---

## 🛠️ Configuration Files

### Visible Browsers
**File**: `.claude/agents/gemini.yaml`
```yaml
contracts:
  browser:
    headless: false  # Change to true for headless mode
    screenshot: "on"
    video: "retain-on-failure"
```

### Screenshot Streaming
**File**: `agent_system/agents/gemini.py`
- Lines 262-270: Screenshot event broadcasting
- Broadcasts to WebSocket server automatically

**File**: `dashboard.html`
- Lines 55-59: Screenshot gallery UI
- Lines 73-77: Screenshot event handling
- Lines 108-133: Screenshot rendering logic

### Coverage Analysis
**File**: `agent_system/coverage_analyzer.py`
- Full coverage parsing and analysis
- Supports Istanbul/NYC reports
- Project-wide and file-specific analysis

**File**: `agent_system/agents/kaya.py`
- Lines 58-64: Coverage intent patterns
- Lines 548-626: Coverage handler implementation

---

## 🎯 Tips & Best Practices

### For Visual Debugging
1. **Use visible browsers** for debugging failing tests
2. **Switch to headless** for batch operations
3. **Watch the browser** to understand what selectors to use

### For Screenshot Gallery
1. Screenshots auto-expire after 12 newest
2. Refresh dashboard if images don't load (browser security)
3. Check `artifacts/` directory for full screenshot history

### For Coverage Analysis
1. Run tests with `--coverage` flag first
2. Check `coverage/` directory exists
3. Use file-specific analysis to find gaps
4. Aim for 85%+ coverage on critical paths

---

## 🚀 Next Steps

1. **Test the features**: Try all three commands above
2. **Open dashboard**: Watch events and screenshots stream in
3. **Check coverage**: See where your tests need improvement
4. **Go full voice**: Use voice commands for everything!

---

## 🐛 Troubleshooting

### Browser doesn't appear
- Check `headless: false` in `.claude/agents/gemini.yaml`
- Ensure Playwright browsers are installed: `npx playwright install`

### Screenshots not showing in dashboard
- Verify WebSocket connection (green indicator in dashboard)
- Check browser console for errors
- Ensure test is actually running (check events section)

### Coverage analysis fails
- Run tests with coverage first: `npx playwright test --coverage`
- Check `coverage/` directory exists
- Verify `coverage-summary.json` or `coverage-final.json` present

### Dashboard not connecting
- Ensure WebSocket server is running: `python3 -m agent_system.observability.event_stream`
- Check port 3010 is not in use: `lsof -i :3010`

---

## 📝 Summary

You now have:
1. ✅ **Visible browsers** - See tests run in real-time
2. ✅ **Live screenshots** - Visual proof in dashboard
3. ✅ **Coverage analysis** - Know what's tested

All three features work seamlessly together to give you complete visibility into your AI-powered testing system!

Enjoy! 🎉
