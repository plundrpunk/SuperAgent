# 🎯 MISSION BRIEF: Fix Cloppy_AI Until All Tests Pass

**Date**: October 14, 2025
**Agent**: Kaya (Multi-Agent Orchestrator)
**Objective**: Test and fix Cloppy_AI application until 100% of P0 tests pass
**Authority Level**: Full autonomy - fix, commit, iterate until complete

---

## 📋 Mission Statement

**Fix all issues in the Cloppy_AI application by iteratively:**
1. Running Playwright E2E tests
2. Identifying failures and root causes
3. Dispatching appropriate agents to fix issues
4. Validating fixes with re-runs
5. Repeating until 100% pass rate achieved

**Success Criteria**: All 207 P0 critical tests passing

---

## 📊 Current Status

### Test Results Summary
- **P0 Tests Generated**: 207 tests across 10 suites
- **Current Pass Rate**: 27% (20/74 tests that ran)
- **Tests Passing**: 20 (mostly billing, error handling)
- **Tests Failing**: 50+ (mostly missing UI features)
- **Critical Blockers Fixed**: 2 (auth setup, createBoard helper)

### What's Working ✅
- Authentication flows
- Board creation and management
- Billing UI (plans, pricing, subscriptions)
- Error handling (timeouts, network errors)
- Basic navigation and routing

### What Needs Fixing ❌
- AudioNode UI (24 tests failing)
- VideoNode UI (25 tests failing)
- ImageNode UI (19 tests failing)
- PDFNode UI (23 tests failing)
- Computer Use automation (20 tests failing)
- Board sharing features (18 tests failing)
- Website node features (21 tests failing)
- Folder organization (15 tests failing)

---

## 🗂️ Knowledge Base

### Key Documentation Locations

**Test Reports**:
- `/Users/rutledge/Documents/DevFolder/Cloppy_Ai/frontend/TEST_SESSION_SUMMARY.md`
- `/Users/rutledge/Documents/DevFolder/Cloppy_Ai/frontend/P0_TEST_RESULTS_REPORT.md`

**Test Files** (All in `/Users/rutledge/Documents/DevFolder/Cloppy_Ai/frontend/e2e/`):
- `audio-node.spec.ts` - 24 tests for audio upload, playback, transcription
- `video-node.spec.ts` - 25 tests for video player, controls, transcription
- `image-node.spec.ts` - 19 tests for image upload, OCR, Vision AI
- `pdf-node.spec.ts` - 23 tests for PDF viewer, extraction, password protection
- `website-node.spec.ts` - 21 tests for web scraping, screenshots
- `computer-use-node.spec.ts` - 20 tests for task automation with safety
- `folder-node.spec.ts` - 15 tests for organization, drag-drop
- `board-sharing.spec.ts` - 18 tests for permissions, collaboration
- `billing.spec.ts` - 22 tests for Stripe integration (mostly passing!)
- `error-scenarios.spec.ts` - 20 tests for resilience (mostly passing!)

**Test Helpers**:
- `/Users/rutledge/Documents/DevFolder/Cloppy_Ai/frontend/e2e/utils/test-helpers.ts`
  - `createBoard()` - Create test board (recently fixed)
  - `addNode()` - Add nodes to board
  - `uploadFile()` - File upload helper
  - Many more utilities

**Application Source** (`/Users/rutledge/Documents/DevFolder/Cloppy_Ai/frontend/src/`):
- `src/pages/BoardsPage.tsx` - Main boards list page
- `src/pages/RegisterPage.tsx` - User registration
- `src/pages/BillingPage.tsx` - Billing and subscriptions
- `src/components/` - All React components
- `src/hooks/` - Custom React hooks
- `src/utils/` - Utility functions

**SuperAgent Guides**:
- `/Users/rutledge/Documents/DevFolder/SuperAgent/DAILY_AGENT_SETUP.md`
- `/Users/rutledge/Documents/DevFolder/SuperAgent/MCP_INTEGRATION_GUIDE.md`
- `/Users/rutledge/Documents/DevFolder/SuperAgent/RECOMMENDED_MCPS.md`
- `/Users/rutledge/Documents/DevFolder/SuperAgent/BRAINSTORM_MODE.md`

---

## 🤖 Agent Team & Coordination

### Your Agent Team

**Scribe** (Test Writer / Code Generator)
- **Model**: Claude Sonnet 4.5
- **Tools**: Read, Write, Edit, Grep, Glob
- **Use For**: Writing missing UI components, adding data-testids, generating code
- **Example**: "Scribe, create the AudioNode component with upload and playback controls"

**Runner** (Test Executor)
- **Model**: Claude Haiku
- **Tools**: Bash, Read, Grep
- **Use For**: Running Playwright tests, parsing output, extracting errors
- **Example**: "Runner, execute all audio-node tests and report failures"

**Medic** (Bug Fixer)
- **Model**: Claude Sonnet 4.5
- **Tools**: Read, Edit, Bash, Grep
- **Contract**: MUST run regression tests before/after fix
- **Use For**: Fixing specific test failures, debugging errors
- **Example**: "Medic, fix the timeout error in audio node upload test"

**Critic** (Pre-Validator)
- **Model**: Claude Haiku
- **Tools**: Read, Grep
- **Use For**: Quality gate before expensive validation, reject flaky tests
- **Example**: "Critic, review the new AudioNode component before we test it"

**Gemini** (Validator)
- **Model**: Gemini 2.5 Pro
- **Tools**: Playwright browser automation
- **Use For**: Prove correctness in real browser with screenshots
- **Example**: "Gemini, validate the billing page works end-to-end"

### Coordination Strategy

**Iterative Fix Loop**:
```
1. Runner: Run P0 tests → Identify top 5 failures
2. Medic: Fix each failure → Run regression tests
3. Critic: Review fixes → Approve or request changes
4. Runner: Re-run tests → Measure improvement
5. Repeat until 100% pass rate
```

**Parallel Work Strategy**:
```
If failures span multiple features:
- Dispatch Medic for bug fixes (e.g., existing features broken)
- Dispatch Scribe for missing features (e.g., AudioNode doesn't exist)
- Coordinate both in parallel for maximum velocity
```

---

## 🔧 Archon MCP Integration

### What is Archon MCP?

Archon is your **persistent memory system** that tracks ALL work across sessions.

**Location**: `/Users/rutledge/Documents/DevFolder/SuperAgent/agent_system/mcp_integration.py`

### How to Use MCP

**Creating Projects**:
```python
from agent_system.mcp_integration import get_mcp_client

mcp = get_mcp_client()
project = mcp.create_project(
    name="Cloppy_AI Testing & Fixes",
    description="Comprehensive testing and bug fixing mission"
)
```

**Tracking Tasks**:
```python
# When dispatching to Scribe
task = mcp.create_task(
    project_id=project['id'],
    title="Build AudioNode component with upload functionality",
    agent="scribe",
    task_type="feature_implementation"
)

# After Scribe completes
mcp.update_task(
    task_id=task['id'],
    status="completed",
    result={"tests_passing": 5, "tests_failing": 0}
)
```

**Retrieving History**:
```python
# See all tasks for this project
tasks = mcp.get_tasks(project_id=project['id'])

# Get project statistics
stats = mcp.get_project_stats(project['id'])
# Returns: {'total_tasks': 50, 'completed': 30, 'success_rate': 0.6}
```

### Why MCP Matters for This Mission

1. **Resume After Interruptions**: If process crashes, you know exactly where you left off
2. **Track Progress**: See which features are done vs. in-progress
3. **Learn from Patterns**: Identify which test fixes work best
4. **Performance Metrics**: Track agent success rates over time
5. **Knowledge Building**: Create institutional memory of how to fix specific issues

**Use MCP for every dispatch**:
- Create task when dispatching agent
- Update task with results when agent completes
- Query tasks to avoid duplicate work
- Build knowledge base of successful fixes

---

## 🎯 Mission Execution Plan

### Phase 1: Quick Wins (Estimated: 2-4 hours)

**Objective**: Get from 27% to 40% pass rate

**Actions**:
1. **Add Data TestIDs** (Scribe)
   - Add `data-testid` attributes to all interactive elements
   - Targets: Buttons, inputs, modals, navigation elements
   - Expected impact: ~10-15 tests start passing

2. **Fix Partially Implemented Features** (Medic)
   - Board sharing modal (exists but incomplete)
   - Stripe checkout flow (UI exists, needs integration)
   - Expected impact: ~5-10 tests start passing

3. **Validate Passing Tests** (Gemini)
   - Run all 20 passing tests in real browser
   - Capture screenshots proving correctness
   - Build confidence in test infrastructure

**Dispatch Example**:
```
Scribe: "Add data-testid='add-audio-node' to the audio node creation button in src/components/NodeToolbar.tsx"
Runner: "Run audio-node.spec.ts and report first 5 failures"
Medic: "Fix the Stripe checkout integration in src/pages/BillingPage.tsx"
```

### Phase 2: Core Features (Estimated: 8-12 hours)

**Objective**: Implement missing node UIs

**Priority Order**:
1. **AudioNode** (24 tests) - Start here
2. **ImageNode** (19 tests) - High value
3. **FolderNode** (15 tests) - Simpler implementation
4. **VideoNode** (25 tests) - Complex, do later
5. **PDFNode** (23 tests) - Complex, do later

**For Each Node**:
```
Step 1: Scribe builds component with basic structure
Step 2: Runner tests → identifies missing features
Step 3: Scribe adds missing features
Step 4: Medic fixes any errors
Step 5: Critic reviews quality
Step 6: Gemini validates in browser
Step 7: MCP marks task complete
```

**AudioNode Implementation Plan**:
```
1. Create src/components/nodes/AudioNode.tsx
   - File upload (drag-drop + picker)
   - Audio player with controls
   - Play/pause, seek, volume
   - Display duration and current time

2. Add transcription feature
   - "Generate Transcription" button
   - Display transcription with timestamps
   - Click timestamp to seek

3. Add waveform visualization
   - Canvas-based waveform
   - Update position during playback

4. Error handling
   - Reject invalid file types
   - Show upload progress
   - Handle corrupt files
   - Network failure retry

Expected: All 24 audio-node tests pass
```

### Phase 3: Advanced Features (Estimated: 12-16 hours)

**Objective**: Build complex features

**Features**:
1. **Computer Use Automation** (20 tests)
   - Task execution UI
   - Safety warning system
   - Credit cost display
   - Execution step visualization

2. **Board Sharing** (18 tests)
   - Permission management UI
   - User invite modal
   - Collaboration indicators
   - Share link generation

3. **Website Node** (21 tests)
   - Web scraping UI
   - Screenshot capture
   - Metadata extraction

4. **Video & PDF Nodes** (48 tests combined)
   - Video player with chapters
   - PDF viewer with text extraction
   - Advanced features (OCR, transcription)

### Phase 4: Polish & Validation (Estimated: 4-6 hours)

**Objective**: 100% pass rate

**Actions**:
1. Fix all remaining edge cases
2. Validate ALL tests with Gemini
3. Run full regression suite
4. Performance optimization
5. Visual regression testing

---

## 🚨 Critical Rules & Constraints

### Testing Protocols

**Before ANY Fix**:
1. Run tests to get baseline results
2. Create MCP task for tracking
3. Make fix
4. Run regression tests
5. Update MCP task with results

**Regression Tests** (MUST pass after every fix):
- `e2e/auth.spec.ts` - Authentication flows
- `e2e/board-workflow.spec.ts` - Core board functionality
- `e2e/billing.spec.ts` - Billing (already passing, keep it that way!)

**If Regression Fails**:
- Revert changes immediately
- Analyze why change broke existing functionality
- Redesign fix to avoid regression
- Never ship a fix that breaks something else

### Code Quality Standards

**Required for All Code**:
- `data-testid` attributes on ALL interactive elements
- TypeScript strict mode compliance
- Error boundaries for all new components
- Loading states and error states
- Proper cleanup in useEffect hooks
- Accessible (ARIA labels, keyboard navigation)

**Playwright Test Standards**:
- Use `data-testid` selectors primarily
- Fallback to text-based selectors with regex
- Take screenshots after major steps
- Use `waitForSelector` not `waitForTimeout`
- Min 1 `expect` assertion per test
- Max 60 second execution time per test

**File Organization**:
```
src/
├── components/
│   ├── nodes/
│   │   ├── AudioNode.tsx       ← Create these
│   │   ├── VideoNode.tsx
│   │   ├── ImageNode.tsx
│   │   └── PDFNode.tsx
│   └── shared/
│       └── FileUpload.tsx      ← Reusable components
├── hooks/
│   └── useMediaUpload.ts       ← Custom hooks
└── utils/
    └── mediaHelpers.ts         ← Utilities
```

### When to Escalate (Human-in-the-Loop)

**Escalate if**:
1. Same fix attempted 3+ times without success
2. Architectural decision needed (e.g., "Should we use library X or Y?")
3. Cost exceeds $5 for single feature
4. Security concern identified
5. Tests passing locally but failing in CI

**Escalation Format**:
```
🚨 ESCALATION NEEDED

Issue: Unable to fix audio transcription after 3 attempts
Attempts:
  1. Used Web Speech API - browser support issues
  2. Used AssemblyAI - API key missing
  3. Mocked transcription - tests still failing

Recommendation: Need to decide on transcription provider and get API key
Estimated Impact: 5 tests blocked

Request: Human decision on transcription strategy
```

---

## 💰 Cost Management

### Budget Allocation
- **Total Budget**: $20 for full mission
- **Per Feature**: ~$0.50 average, $2-3 max for complex features
- **Model Selection**:
  - Haiku for routing, test execution, pre-validation
  - Sonnet 4.5 for code generation, bug fixing
  - Gemini 2.5 Pro only for final validation

### Cost Tracking
```python
# Track costs in MCP
task_result = {
    "model_used": "claude-sonnet-4-5-20250929",
    "tokens_input": 12500,
    "tokens_output": 3200,
    "estimated_cost": 0.45,
    "tests_fixed": 5
}
mcp.update_task(task_id, result=task_result)
```

### Optimization Strategies
1. Batch similar fixes together
2. Use Haiku for simple fixes
3. Cache successful patterns for reuse
4. Validate in batches (not one-by-one with Gemini)
5. Use MCP to avoid duplicate work

---

## 📊 Progress Reporting

### Status Updates (Every 2 Hours)
```
📊 Kaya Progress Report

Time: 2 hours into mission
Pass Rate: 27% → 35% (+8%)
Tests Fixed: 8 tests
Tests Remaining: 42 tests

Recent Completions:
✅ Added data-testids to all buttons (+3 tests)
✅ Fixed Stripe checkout flow (+5 tests)

In Progress:
🔄 Building AudioNode component (Scribe)
🔄 Testing folder organization (Runner)

Next Up:
⏳ Implement ImageNode
⏳ Fix board sharing modal

Blockers: None
ETA to 100%: ~10-12 hours
```

### Final Report
When mission complete, generate:
- Full test results (all passing)
- List of all features implemented
- Cost breakdown by agent/feature
- Lessons learned for future missions
- Recommendations for maintenance

---

## 🎓 Learning & Knowledge Building

### Patterns to Remember (Store in MCP)

**When X Fails → Do Y**:
```
TimeoutError waiting for element
→ Check if element has data-testid
→ Check if feature is implemented in UI
→ If missing, dispatch Scribe to build it

Tests pass locally but fail in CI
→ Check for race conditions
→ Add proper wait conditions
→ Increase timeout for slow operations

TypeError: Cannot read property 'X' of undefined
→ Add null checks and loading states
→ Implement error boundaries
→ Add fallback UI for error states
```

**Successful Fix Templates**:
Store in MCP for reuse:
```
Audio/Video node upload pattern:
  1. <input type="file" accept="audio/*" />
  2. FileReader to read file
  3. Upload to server (or mock)
  4. Display player when ready
  5. Add data-testid at each step

Result: 100% success rate for media upload tests
```

---

## 🚀 Mission Start Checklist

Before beginning, verify:

- [ ] Dashboard servers running:
  - Dashboard: http://localhost:8080
  - WebSocket: ws://localhost:3010

- [ ] Redis running:
  ```bash
  redis-cli ping  # Should return PONG
  ```

- [ ] Cloppy_AI dev server accessible:
  ```bash
  cd /Users/rutledge/Documents/DevFolder/Cloppy_Ai/frontend
  # Verify server is running or start it
  ```

- [ ] Test infrastructure working:
  ```bash
  npx playwright test e2e/auth.setup.ts  # Should pass
  ```

- [ ] MCP integration active:
  ```python
  from agent_system.mcp_integration import get_mcp_client
  mcp = get_mcp_client()
  print(mcp.enabled)  # Should be True
  ```

- [ ] All agent configs loaded:
  ```bash
  ls -la .claude/agents/
  # Should see: kaya.yaml, scribe.yaml, runner.yaml, medic.yaml, critic.yaml
  ```

---

## 🎯 Success Metrics

### Definition of Done
- ✅ 100% of P0 tests passing (207/207)
- ✅ No regressions in existing tests
- ✅ All features validated with Gemini (screenshots)
- ✅ Cost under budget ($20 total)
- ✅ All work tracked in MCP
- ✅ Final report generated

### Celebration Criteria
When you achieve 100% pass rate:
1. Generate comprehensive completion report
2. Create PR summary with all changes
3. Export metrics to share with stakeholders
4. Document lessons learned in MCP
5. 🎉 Notify user: "Mission accomplished! All 207 tests passing!"

---

## 📞 Communication Protocols

### Real-Time Updates
- Log all events to Redis (`agent-events` channel)
- Events appear in dashboard at http://localhost:8080
- WebSocket pushes updates automatically

### Event Types to Emit
```python
- agent.dispatch (when routing to another agent)
- task.start (when beginning work on feature)
- task.progress (every 15 minutes during long tasks)
- task.complete (when feature done)
- test.run (when executing tests)
- test.results (pass/fail counts)
- error.encountered (when hitting blocker)
- milestone.reached (pass rate thresholds: 40%, 60%, 80%, 100%)
```

---

## 🎪 The Big Picture

### Why This Mission Matters

Your human partner wants to **quit the boiler business**. The ONLY thing standing between them and freedom is this app working perfectly.

Every test you fix = one step closer to that goal.

Your job is to be **relentless**:
- Fix tests
- Build features
- Iterate until perfect
- Don't stop until 100%

### Your Superpowers

1. **Multi-Agent Coordination**: You command 5 specialized agents
2. **Persistent Memory**: MCP remembers everything
3. **Web Search**: Brave Search for finding solutions
4. **Real-Time Visibility**: Dashboard shows your every move
5. **Autonomy**: Full authority to fix without asking permission

### Your Mission, Should You Choose to Accept It

**Test the fucking app and fix the issues until there are no more.**

Go forth and make it happen, Kaya. 🚀

---

**Mission Start Time**: Awaiting your command
**Expected Completion**: 24-36 hours of agent time
**User Impact**: Life-changing (literally can quit boiler business)

**Remember**: Every test passing = progress. Every feature built = freedom.

Don't stop until it's done. 💪

---

**Last Updated**: October 14, 2025
**Mission Commander**: Kaya
**Support Team**: Scribe, Runner, Medic, Critic, Gemini
**Mission Status**: READY TO LAUNCH 🚀
