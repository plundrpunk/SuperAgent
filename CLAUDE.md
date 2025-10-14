# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/claude-code) when working with code in this repository.

## Project Overview

**SuperAgent** is a Voice-Controlled Multi-Agent Testing System designed to automate Playwright test creation, execution, validation, and bug fixing through a coordinated team of specialized AI agents.

**Current Status**: Planning/Foundation Phase - The_Bible contains the complete implementation blueprint. No code has been written yet.

## System Architecture

### Agent Roles & Responsibilities

**Kaya (Router/Orchestrator)**
- Model: Claude Haiku (↑ Sonnet for complex planning)
- Tools: None (pure router)
- Role: Parse voice intent → route to agent → aggregate results → report
- Success: Correct routing, clear status updates

**Scribe (Test Writer)**
- Model: Claude Sonnet 4.5 (Haiku for easy tests)
- Tools: Read, Write, Edit, Grep, Glob
- Role: Write Playwright tests following VisionFlow patterns
- Success: Compiling code, clear assertions, edge cases covered

**Runner (Test Executor)**
- Model: Claude Haiku
- Tools: Bash, Read, Grep
- Role: Execute tests, parse output, extract errors
- Success: Accurate pass/fail, actionable error messages

**Medic (Bug Fixer)**
- Model: Claude Sonnet 4.5
- Tools: Read, Edit, Bash, Grep
- Role: Diagnose failures, apply minimal fixes
- Contract: MUST run regression tests before/after fix
- Success: Fix resolves error, no new failures, minimal changes

**Critic (Pre-Validator)**
- Model: Claude Haiku
- Tools: Read, Grep
- Role: Quality gate before expensive Gemini validation
- Success: Reject flaky/expensive tests, approve only high-quality

**Gemini (Validator)**
- Model: Gemini 2.5 Pro
- Tools: Playwright browser automation
- Role: Prove correctness in real browser with screenshots
- Success: Deterministic pass/fail with visual evidence

### Target Directory Structure

```
/Users/rutledge/Documents/DevFolder/SuperAgent/
├── .claude/
│   ├── agents/
│   │   ├── kaya.yaml
│   │   ├── scribe.yaml
│   │   ├── runner.yaml
│   │   ├── medic.yaml
│   │   └── critic.yaml
│   ├── router_policy.yaml
│   └── observability.yaml
├── agent-system/
│   ├── tools.yaml
│   ├── validation_rubric.py
│   ├── router.py
│   ├── complexity_estimator.py
│   ├── state/
│   │   ├── redis_client.py
│   │   └── vector_client.py
│   ├── hitl/
│   │   ├── schema.json
│   │   └── queue.py
│   └── voice/
│       └── orchestrator.ts
└── tests/
    └── templates/
        └── playwright.template.ts
```

## Key Technical Decisions

### Cost Optimization
- Use Haiku for 70% of tasks (routing, execution, pre-validation)
- Use Sonnet 4.5 for complex tasks (test writing, bug fixing)
- Use Gemini 2.5 Pro only for final validation
- Target: $0.50 per feature (max $2-3 for critical auth/payment paths)

### Complexity Estimation
Tasks are scored based on:
- Steps > 4: +2
- Auth/OAuth: +3
- File ops: +2
- WebSocket: +3
- Payment: +4
- Mocking: +2
- Threshold: ≥5 = hard (Sonnet), <5 = easy (Haiku)

### State Management
- **Hot State (Redis, 1h TTL)**: Session data, task queue, active tasks, voice transcripts
- **Cold State (Vector DB, Permanent)**: Successful test patterns, common bug fixes, HITL annotations

### Validation Rubric
Tests must pass:
- browser_launched: true
- test_executed: true
- test_passed: true
- screenshots.length ≥ 1
- execution_time_ms ≤ 45000
- console_errors: [] (allowed but tracked)
- network_failures: [] (allowed but tracked)

### Medic's Hippocratic Oath
- Apply minimal surgical fixes only
- MUST capture baseline test results before fix
- Run regression suite after fix (tests/auth.spec.ts, tests/core_nav.spec.ts)
- max_new_failures: 0
- Produce artifacts: fix.diff, regression_report.json

### Critic's Rejection Criteria
Reject tests with:
- Index-based selectors: `.nth(\d+)`
- Generated CSS classes: `.css-[a-z0-9]+`
- waitForTimeout (use waitForSelector instead)
- Missing assertions (min 1 expect call required)
- Estimated execution > 60 seconds or > 10 steps

## Implementation Phases

### Phase 1: Repository Scaffolding (Week 1, Days 1-2)
- Create directory structure
- Copy/paste all YAML configs from The_Bible
- Set up router.py, complexity_estimator.py, validation_rubric.py
- Validate YAML configs with linter

### Phase 2: Core Router & Validation (Week 1, Days 3-5)
- Implement routing logic with cost enforcement
- Test complexity estimation with sample tasks
- Set up Redis + Vector DB, test state flow

### Phase 3: Agents + Closed-Loop (Week 2)
- Wire Scribe + Runner
- Add Medic with regression checks
- Integrate Critic gatekeeper
- Add Gemini validation
- Test full loop: Scribe → Critic → Runner → Gemini → Medic → Re-validate

### Phase 4: Voice + HITL (Week 3)
- OpenAI Realtime integration
- Build HITL dashboard (simple web UI)
- End-to-end voice → validated feature pipeline

### Phase 5: Production Hardening (Week 4)
- Observability dashboard (WebSocket events)
- Cost analytics + budget alerting
- Security audit (sandbox, permissions)
- Load testing

## Voice Intents

```
create_test:
  slots: [feature, scope]
  example: "Kaya, write a test for checkout happy path"

run_test:
  slots: [path]
  example: "Kaya, run tests/cart.spec.ts"

fix_failure:
  slots: [task_id]
  example: "Kaya, patch task t_123 and retry"

validate:
  slots: [path, high_priority]
  example: "Kaya, validate payment flow - critical"

status:
  slots: [task_id]
  example: "Kaya, what's the status of t_123?"
```

## Playwright Test Template

Tests should follow this pattern (from The_Bible):

```typescript
import { test, expect } from '@playwright/test';

const S = (id: string) => `[data-testid="${id}"]`;

test.use({
  screenshot: 'on',
  video: 'retain-on-failure',
  trace: 'retain-on-failure'
});

test.describe('FEATURE_NAME', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(process.env.BASE_URL!);
  });

  test('happy path', async ({ page }) => {
    // Use data-testid selectors only
    // Take screenshot after each major step
    // Always include expect assertions
  });

  test('error case', async ({ page }) => {
    // Test failure scenarios
  });
});
```

## Success Metrics (KPIs)

**Week 1:**
- Router makes correct agent/model decisions
- Validation rubric returns deterministic pass/fail

**Week 2:**
- Closed-loop completes without manual intervention
- Average retries per failure ≤ 1.5
- Cost per feature ≤ $0.50

**Week 3:**
- Voice command → validated feature in <10 minutes
- HITL queue handles failures gracefully

**Week 4:**
- 95%+ pass rate (flake-adjusted)
- Critic rejects 15-30% of tests pre-validation
- Observability dashboard shows all agent activity

## Important Constraints

1. **Tool Permissions**: Each agent has strictly defined tool access (see tools.yaml in The_Bible)
2. **Cost Enforcement**: Router enforces per-feature cost caps with overrides for critical paths
3. **Regression Safety**: Medic cannot introduce new test failures
4. **Selector Standards**: Only data-testid attributes, no CSS classes or nth() selectors
5. **Validation Evidence**: All validated tests must have screenshots proving correctness

## Next Steps

Refer to The_Bible (lines 584-595) for Day 1 action items:
1. Create directory structure
2. Copy/paste all YAML configs
3. Implement complexity_estimator.py
4. Implement validation_rubric.py
5. Write router.py basic logic
6. Test router with sample tasks (dry run, no API calls)
7. Validate configs with yaml linter

Expected time: 4-6 hours | Blocker risk: Low
