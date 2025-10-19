# Kaya Troubleshooting Guide

## Issue: "no_failures_found" but tests exist

### Symptoms
```
INFO:agent_system.agents.kaya:Testing directory: /Users/rutledge/Documents/DevFolder/Cloppy_Ai
...
{'iteration': 1, 'status': 'no_failures_found', 'cost': 0.0}
```

### Root Cause
Playwright E2E tests need the application servers running:
- **Backend**: Port 3010 (NestJS)
- **Frontend**: Port 5175 (Vite)

If servers aren't running, tests timeout and Runner thinks there are no failures.

---

## Solution 1: Start Servers First

### Start Backend
```bash
cd /Users/rutledge/Documents/DevFolder/Cloppy_Ai/backend
pnpm run dev
```

### Start Frontend (in another terminal)
```bash
cd /Users/rutledge/Documents/DevFolder/Cloppy_Ai/frontend
pnpm run dev
```

### Then Run Kaya
```bash
cd /Users/rutledge/Documents/DevFolder/SuperAgent
./kaya "fix all test failures in /Users/rutledge/Documents/DevFolder/Cloppy_Ai"
```

---

## Solution 2: Use Dedicated Test Environment

Check if Cloppy_AI has a test environment setup:

```bash
cd /Users/rutledge/Documents/DevFolder/Cloppy_Ai
cat package.json | grep test
```

Look for test scripts that might start servers automatically.

---

## Solution 3: Run Tests Manually First

To verify tests actually fail:

```bash
cd /Users/rutledge/Documents/DevFolder/Cloppy_Ai
npx playwright test --reporter=list 2>&1 | head -50
```

This shows you what's actually happening with the tests.

---

## Understanding Runner Behavior

Runner executes tests with:
- **Timeout**: 120 seconds
- **Working Directory**: Changes to test directory
- **Command**: `npx playwright test`
- **Reporter**: JSON format for parsing

If tests don't complete within 120s, Runner treats it as "no output" = "no failures".

---

## Quick Diagnosis Commands

### Check if servers are running:
```bash
lsof -i :3010  # Backend
lsof -i :5175  # Frontend
```

### Check test configuration:
```bash
cd /Users/rutledge/Documents/DevFolder/Cloppy_Ai
cat playwright.config.ts | grep baseURL
```

### Run one test manually:
```bash
cd /Users/rutledge/Documents/DevFolder/Cloppy_Ai
npx playwright test canvas-nodes.spec.ts --headed
```

---

## Current Status

✅ **Fixed**:
- Directory path parsing
- Case-sensitive file paths
- Intent regex patterns

❓ **To Investigate**:
- Do tests need servers running?
- What's the correct test environment setup?
- Are there test configuration issues?

---

## Recommended Workflow

1. **Start servers** (backend + frontend)
2. **Verify tests run** manually first
3. **Then use Kaya** to automate fixes

Example:
```bash
# Terminal 1: Backend
cd /Users/rutledge/Documents/DevFolder/Cloppy_Ai/backend && pnpm run dev

# Terminal 2: Frontend
cd /Users/rutledge/Documents/DevFolder/Cloppy_Ai/frontend && pnpm run dev

# Terminal 3: Kaya
cd /Users/rutledge/Documents/DevFolder/SuperAgent
./kaya "fix all test failures in /Users/rutledge/Documents/DevFolder/Cloppy_Ai"
```

---

## Alternative: Unit Tests Only

If you want to fix unit tests (not E2E), specify the directory:

```bash
./kaya "fix all test failures in /Users/rutledge/Documents/DevFolder/Cloppy_Ai/src"
```

This would run unit tests that don't need servers.

---

## Next Steps

1. Check what's in the Cloppy_AI logs
2. Verify server status
3. Run tests manually to see actual failures
4. Then let Kaya fix them!
