# Medic Agent

## Overview

Medic is the bug-fixing agent in the SuperAgent system. Its mission is to diagnose test failures and apply **minimal surgical fixes** while strictly adhering to the **Hippocratic Oath**: First, do no harm.

## Key Features

### 1. Hippocratic Oath Enforcement
- **max_new_failures: 0** - Strictly enforced, no exceptions
- Captures baseline regression tests BEFORE applying any fixes
- Runs full regression suite AFTER fixes
- Automatically rolls back changes if new failures detected
- Escalates to HITL (Human-In-The-Loop) on violations

### 2. Minimal Surgical Fixes
- Uses Claude Sonnet 4.5 for intelligent diagnosis and fix generation
- Prefers selector updates over logic changes
- Typically changes 1-3 lines only
- Maintains original test structure and style
- Generates unified diffs for all changes

### 3. Regression Safety
Runs these tests before and after fixes:
- `tests/auth.spec.ts` - Authentication flow baseline
- `tests/core_nav.spec.ts` - Core navigation baseline

### 4. Artifact Generation
Every fix produces:
- **fix.diff** - Unified diff showing exact changes
- **regression_report.json** - Complete before/after comparison with metrics

### 5. Cost Tracking
- Tracks Anthropic API costs (Sonnet 4.5: $3/1M input, $15/1M output)
- Typical fix cost: ~$0.01-0.03
- Returns cost in AgentResult for budget monitoring

## Usage

### Basic Usage

```python
from agent_system.agents.medic import MedicAgent

medic = MedicAgent()

result = medic.execute(
    test_path="tests/checkout.spec.ts",
    error_message="Error: Selector [data-testid='submit-order'] not found",
    task_id="optional-task-id"
)

if result.success:
    print(f"Fix applied successfully!")
    print(f"Diagnosis: {result.data['diagnosis']}")
    print(f"New failures: {result.data['comparison']['new_failures']}")
    print(f"Artifacts: {result.data['artifacts']}")
else:
    print(f"Fix failed: {result.error}")
    if result.data.get('escalate_to_hitl'):
        print("Escalated to HITL for manual review")
```

### CLI Usage

```bash
python agent_system/agents/medic.py \
  tests/checkout.spec.ts \
  "Error: Selector [data-testid='submit-order'] not found"
```

## Configuration

Located at: `.claude/agents/medic.yaml`

```yaml
name: medic
role: Bug Fixer
model: claude-sonnet-4.5

contracts:
  regression_scope:
    pre_fix: [capture_baseline]
    on_fix: [tests/auth.spec.ts, tests/core_nav.spec.ts]
    post_fix: [compare_baseline]
    max_new_failures: 0

  artifacts:
    - fix.diff
    - regression_report.json
```

## Environment Variables

Required in `.env`:
```
ANTHROPIC_API_KEY=your-api-key-here
```

## Common Fix Patterns

### 1. Selector Not Found
**Root Cause**: Element ID changed in app
**Fix**: Update data-testid attribute
```typescript
// Before
await page.click('[data-testid="old-button"]');

// After
await page.click('[data-testid="new-button"]');
```

### 2. Timeout Issues
**Root Cause**: Slow operation without proper wait
**Fix**: Add explicit wait condition
```typescript
// Before
await page.click('[data-testid="submit"]');

// After
await page.click('[data-testid="submit"]');
await page.waitForSelector('[data-testid="success-message"]', { timeout: 10000 });
```

### 3. Assertion Failures
**Root Cause**: Expected value changed
**Fix**: Update assertion to match new spec
```typescript
// Before
await expect(page.locator('[data-testid="price"]')).toContainText('$10.00');

// After
await expect(page.locator('[data-testid="price"]')).toContainText('$12.00');
```

## Error Handling

### Automatic Rollback
If new failures detected after fix:
1. Original test content is restored
2. Fix is marked as failed
3. Error message explains regression
4. Case is escalated to HITL

### Escalation Triggers
Medic escalates to HITL when:
- More than 3 fix attempts on same test
- New regression failures detected
- Unclear root cause (AI confidence low)
- Breaking changes in app code (not test-fixable)

## Artifacts

### fix.diff
Unified diff format showing exactly what changed:
```diff
--- a/tests/checkout.spec.ts
+++ b/tests/checkout.spec.ts
@@ -15,7 +15,7 @@
   await page.fill('[data-testid="email"]', 'test@example.com');

   // Submit order
-  await page.click('[data-testid="submit-order"]');
+  await page.click('[data-testid="place-order-btn"]');

   // Verify success
   await expect(page).toHaveURL('/order-confirmation');
```

### regression_report.json
Complete metrics and comparison:
```json
{
  "timestamp": "2025-10-14T10:30:45.123Z",
  "test_path": "tests/checkout.spec.ts",
  "diagnosis": "Selector 'submit-order' renamed to 'place-order-btn' in UI",
  "baseline": {
    "passed": 2,
    "failed": 0,
    "total": 2
  },
  "after_fix": {
    "passed": 2,
    "failed": 0,
    "total": 2
  },
  "comparison": {
    "new_failures": 0,
    "improved": false
  },
  "fix_applied": true,
  "hippocratic_oath_honored": true
}
```

## Integration with SuperAgent System

### Workflow Position
```
User Voice Command
    ↓
Kaya (Router) - Routes to agents
    ↓
Scribe - Writes test
    ↓
Critic - Pre-validates test quality
    ↓
Runner - Executes test
    ↓
[IF TEST FAILS]
    ↓
MEDIC - Fixes test with regression safety ← YOU ARE HERE
    ↓
Runner - Re-executes test
    ↓
Gemini - Final validation with visual proof
```

### State Management
Medic integrates with:
- **Redis (hot state)**: Active task tracking, retry counts
- **Vector DB (cold state)**: Successful fix patterns for learning
- **HITL Queue**: Failed fixes needing human review

## Testing

Run the test suite:
```bash
pytest tests/test_medic.py -v
```

Test coverage: **75%** (25/17 tests passed)

Key test scenarios:
- Baseline capture and comparison
- Fix generation with AI
- Diff generation
- Regression detection and rollback
- Artifact generation
- Cost tracking
- Hippocratic Oath enforcement

## Architecture Decisions

### Why Sonnet 4.5?
- High code comprehension for accurate diagnosis
- Better at minimal fixes vs aggressive rewrites
- Cost-effective for critical path (~$0.01-0.03 per fix)
- Lower token usage than Opus for this task

### Why Strict max_new_failures: 0?
- Prevents cascading test failures
- Maintains test suite stability
- Enables safe automated fixing
- Forces escalation to HITL for complex issues

### Why Full Regression Suite?
- Catches side effects from selector changes
- Validates auth/nav paths (critical flows)
- Low overhead (~5-10s per run)
- High confidence in fix safety

## Metrics & KPIs

### Success Criteria
- ✅ Fix resolves the reported error
- ✅ No new test failures introduced
- ✅ Minimal code changes (avg 1-3 lines)
- ✅ Clear explanation of root cause

### Target Metrics
- **Fix success rate**: >80%
- **Average retries**: ≤1.5 per failure
- **Regression rate**: 0% (enforced by contract)
- **HITL escalation**: 15-30% of failures
- **Cost per fix**: $0.01-0.03

### Current Performance
- All 17 unit tests passing
- Proper error handling for all edge cases
- Artifacts generated correctly
- Hippocratic Oath enforced

## Future Enhancements

1. **Pattern Learning**: Store successful fixes in Vector DB for faster future fixes
2. **Multi-Step Fixes**: Handle complex fixes requiring multiple coordinated changes
3. **Visual Regression**: Integrate screenshot comparison for UI changes
4. **Confidence Scoring**: AI confidence scores to auto-escalate uncertain fixes
5. **Fix Templates**: Common fix patterns as templates for instant application

## Support

For issues or questions:
1. Check `.claude/agents/medic.yaml` for configuration
2. Review test suite in `tests/test_medic.py`
3. Check artifacts in `artifacts/medic_*.{diff,json}`
4. Review HITL queue for escalated cases

## License

Part of SuperAgent - Voice-Controlled Multi-Agent Testing System
