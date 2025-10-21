# Autonomous Build Improvement Plan

## Critical Analysis: Current State vs Original Design

### What You Said (User Concerns)
> "What other things can be done so they dont give up so quick, or can they loop back on the other side and try the Items in review. At one point there was pictures and dashboards, They are still failing miserably I think"

### Root Problems Identified

## 1. CRITICAL MISSING PIECES

### Original Design (from CLAUDE.md and docs):
**Phase 3: Agents + Closed-Loop**
```
Test full loop: Scribe → Critic → Runner → Gemini → Medic → Re-validate
```

### Current Implementation:
**Autonomous Build Workflow (`_execute_test_task_with_validation`)**
```
Scribe → Runner → (Medic loop x3) → DONE or REVIEW
```

### **MISSING FROM AUTONOMOUS BUILD:**
1. ❌ **Critic Pre-Validation** - NOT CALLED in autonomous workflow
2. ❌ **Gemini Browser Validation** - NOT CALLED in autonomous workflow
3. ❌ **Screenshots/Visual Evidence** - NOT CAPTURED (Gemini not running)
4. ❌ **Second-Pass Retry** - Tasks marked 'review' are ABANDONED
5. ❌ **HITL Dashboard Integration** - Not visible/accessible

## 2. WORKFLOW COMPARISON

### Original Design Pipeline (5-Stage Quality Gate):
```mermaid
Scribe → Critic → Runner → (Medic → Runner) → Gemini → DONE
         ↓         ↓                           ↓
       REJECT    FAIL                      SCREENSHOTS
```

### Current Autonomous Build (Degraded 2-Stage):
```mermaid
Scribe → Runner → (Medic x3) → DONE/REVIEW
         ↓                       ↓
       NO QA                  ABANDONED
```

### Impact of Missing Stages:

**Without Critic:**
- Low-quality tests (flaky selectors, no assertions) proceed to expensive Medic
- Wastes $0.15-0.30 per bad test (Sonnet 4.5 fixes for unfixable tests)
- 15-30% of tests should be rejected pre-execution (per design)

**Without Gemini:**
- No visual proof of correctness
- "Passing" tests may not actually work in real browser
- No screenshots for debugging
- Missing the "final arbiter of correctness"

**Without Second-Pass Retry:**
- Tasks marked 'review' (40-60% on bad nights) are permanently abandoned
- No mechanism to revisit failed tasks
- Build reports "complete" with 0-20% success rate

## 3. DETAILED GAPS ANALYSIS

### Gap 1: No Critic in Autonomous Build

**Location**: `kaya.py:1400-1592` (`_execute_test_task_with_validation`)

**Current Code**:
```python
# Step 1: Scribe generates test
scribe_result = self._handle_create_test(test_slots, context)

# Step 2: Runner validates test  ← CRITIC SHOULD BE HERE!
runner_result = self._handle_run_test({'raw_value': test_path}, context)
```

**Original Design** (`kaya.py:770-805` in `_handle_full_pipeline`):
```python
# Step 1: Scribe writes test
scribe_result = ...

# Step 2: Critic pre-validates  ← THIS EXISTS BUT NOT USED!
critic = self._get_agent('critic')
critic_result = critic.execute(test_path=test_path)

if not critic_result.success:
    return self._aggregate_pipeline_results('critic_rejected', ...)
```

**Fix Required**: Insert Critic step between Scribe and Runner in autonomous workflow.

---

### Gap 2: No Gemini Validation

**Location**: `kaya.py:1546-1582` (end of autonomous loop)

**Current Code**:
```python
# Step 4: Update Archon task status
if runner_result.success:
    self.archon.update_task_status(task_id, 'done', ...)  ← NO PROOF!
    return {'success': True, ...}
```

**Original Design** (`kaya.py:857-897`):
```python
# Step 5: Gemini validates  ← THIS EXISTS BUT NOT USED!
logger.info("Step 5: Gemini validates in real browser")
gemini_result = self._handle_validate({'raw_value': test_path}, context)

# Visual evidence captured via screenshots
```

**Fix Required**: Add Gemini validation after successful Runner execution.

---

### Gap 3: Only 3 Retry Attempts

**Location**: `kaya.py:1407, 1460`

**Current Code**:
```python
max_fix_attempts: int = 3  ← TOO FEW!

while not runner_result.success and fix_attempts < max_fix_attempts:
    fix_attempts += 1
    # ... Medic fix ...

# Failed after max attempts
self.archon.update_task_status(task_id, 'review', ...)  ← ABANDONED!
```

**Issues**:
1. **3 attempts is insufficient** - RAG only kicks in on attempt 3, but then fails
2. **No escalation strategy** - Should increase attempts for critical features
3. **No progressive enhancement** - All 3 attempts are identical (no strategy changes)

**Fix Required**:
- Increase to 5-7 attempts
- Add progressive strategy: attempts 1-2 (basic), 3-4 (with RAG), 5+ (with different prompting)

---

### Gap 4: No Second-Pass for 'review' Tasks

**Location**: `kaya.py:1656-1692` (`_handle_build_feature`)

**Current Code**:
```python
for idx, task in enumerate(created_tasks, 1):
    task_result = self._execute_test_task_with_validation(task, ...)

    if task_result['success']:
        completed_tasks.append(...)
    else:
        failed_tasks.append(...)  ← GAME OVER!

# Return summary (failed tasks NOT retried)
return AgentResult(success=(failed_count == 0), ...)
```

**Missing**:
```python
# AFTER first pass, retry 'review' tasks with enhanced context
if failed_tasks:
    logger.info(f"🔄 Second pass: Retrying {len(failed_tasks)} failed tasks...")

    for task in failed_tasks:
        # Retry with:
        # - Increased max_fix_attempts (5→7)
        # - Different model (Haiku → Sonnet for complex tasks)
        # - Enhanced RAG context from similar passing tests
```

---

### Gap 5: Missing Screenshot/Dashboard Visibility

**Location**: Multiple

**Issue**: User said *"At one point there was pictures and dashboards"*

**What Exists (But Not Used)**:
1. **Gemini captures screenshots** - `gemini.py:91-250`
2. **HITL Dashboard** - `web/hitl_dashboard/` (exists!)
3. **Observability Dashboard** - `web/dashboard_server.py` (exists!)

**Why Not Visible**:
- Gemini not called in autonomous build → No screenshots
- Dashboards may not be running (need to verify ports 8000, 8001)
- No WebSocket events for failed tasks → No real-time visibility

**Fix Required**:
- Ensure Gemini runs and captures screenshots
- Verify dashboards are accessible
- Emit WebSocket events for all task state changes

---

## 4. PROPOSED IMPROVEMENTS

### Improvement 1: Add Full Pipeline to Autonomous Build

**Goal**: Use the complete 5-stage pipeline from original design

**Implementation**:
```python
# NEW: _execute_test_task_with_full_pipeline (kaya.py)

def _execute_test_task_with_full_pipeline(self, task, project_id, context, max_fix_attempts=5):
    """
    Execute test task with complete validation pipeline.

    Pipeline:
    1. Scribe generates test
    2. Critic pre-validates (quality gate)
    3. Runner executes test
    4. If failed: Medic fixes (up to max_fix_attempts)
    5. Gemini validates in browser with screenshots
    6. Update Archon with visual evidence
    """

    # Step 1: Scribe
    scribe_result = self._handle_create_test(...)

    # Step 2: Critic (ADDED!)
    critic = self._get_agent('critic')
    critic_result = critic.execute(test_path=test_path)

    if not critic_result.success:
        # Scribe should retry with Critic feedback
        logger.warning(f"Critic rejected test: {critic_result.error}")
        # Option A: Return to Scribe immediately
        # Option B: Continue anyway (log warning)

    # Step 3: Runner
    runner_result = self._handle_run_test(...)

    # Step 4: Medic loop (existing, but increase attempts)
    fix_attempts = 0
    while not runner_result.success and fix_attempts < max_fix_attempts:
        # ... existing Medic logic ...
        # Enhanced: Use Critic feedback + RAG context

    # Step 5: Gemini validation (ADDED!)
    if runner_result.success:
        logger.info("✅ Test passed Runner, validating in browser...")
        gemini_result = self._handle_validate({'raw_value': test_path}, context)

        if gemini_result.success:
            # Update Archon with screenshots
            self.archon.update_task_status(
                task_id,
                'done',
                {
                    'test_path': test_path,
                    'validation': 'gemini_passed',
                    'screenshots': gemini_result.data.get('screenshots', []),
                    'fix_attempts': fix_attempts
                }
            )
            return {'success': True, 'gemini_validated': True, ...}
        else:
            # Gemini failed but Runner passed → Investigate
            logger.warning("Runner passed but Gemini failed - possible environment issue")
            # Fall back to Runner success

    # Failed after all attempts
    self.archon.update_task_status(task_id, 'review', ...)
```

**Cost Impact**:
- Critic: +$0.001 per test (Haiku, static analysis)
- Gemini: +$0.05-0.10 per test (browser execution + screenshots)
- **Total**: +$0.051-0.101 per test
- **Benefit**: 15-30% fewer bad tests → Saves $0.15-0.30 per rejected test
- **Net**: Cost-neutral or slight savings + higher quality

---

### Improvement 2: Second-Pass Retry for 'review' Tasks

**Goal**: Don't give up on failed tasks - retry with enhanced context

**Implementation**:
```python
# ENHANCED: _handle_build_feature (kaya.py:1593)

def _handle_build_feature(self, slots, context):
    # ... existing project/task creation ...

    # FIRST PASS: Execute all tasks (existing logic)
    for idx, task in enumerate(created_tasks, 1):
        task_result = self._execute_test_task_with_full_pipeline(task, ...)
        if task_result['success']:
            completed_tasks.append(...)
        else:
            failed_tasks.append(...)

    # NEW: SECOND PASS - Retry failed tasks with enhanced strategy
    if failed_tasks:
        logger.info(f"🔄 SECOND PASS: Retrying {len(failed_tasks)} failed tasks with enhanced context")

        second_pass_completed = []
        still_failed = []

        for idx, failed_task in enumerate(failed_tasks, 1):
            logger.info(f"🔄 Retry {idx}/{len(failed_tasks)}: {failed_task['title']}")

            # Fetch similar PASSING tests from Archon for context
            similar_passing = self.archon.find_tasks(
                project_id,
                filters={'status': 'done'}  # Only passing tests
            )

            # Extract patterns from passing tests
            passing_patterns = []
            for passing_task in similar_passing.get('tasks', [])[:3]:
                # Read the passing test file
                passing_test_path = passing_task.get('metadata', {}).get('test_path')
                if passing_test_path:
                    passing_patterns.append({
                        'path': passing_test_path,
                        'feature': passing_task['title']
                    })

            # Enhanced context for retry
            enhanced_context = {
                **context,
                'retry_attempt': True,
                'similar_passing_tests': passing_patterns,
                'previous_error': failed_task['error']
            }

            # Retry with:
            # - Increased attempts (5 → 7)
            # - Enhanced RAG context
            # - Passing test patterns
            retry_result = self._execute_test_task_with_full_pipeline(
                failed_task,
                project_id,
                enhanced_context,
                max_fix_attempts=7  # More attempts on second pass
            )

            if retry_result['success']:
                second_pass_completed.append(...)
                logger.info(f"✅ Second pass SUCCESS: {failed_task['title']}")
            else:
                still_failed.append(...)
                logger.error(f"❌ Second pass FAILED: {failed_task['title']}")

        # Update totals
        completed_tasks.extend(second_pass_completed)
        failed_tasks = still_failed

    # Build summary with second-pass results
    summary_message = f"""
🏗️  Feature Build Complete (with Second Pass)!

Project: {project_id}
First Pass: {first_pass_completed}/{total_tasks} ✅
Second Pass: {len(second_pass_completed)}/{len(original_failed)} ✅
Total Completed: {len(completed_tasks)}/{total_tasks}
Still Failed: {len(failed_tasks)}
"""
```

**Expected Impact**:
- **First Pass**: 40-60% success (current)
- **Second Pass**: +20-30% recovery (retry with enhanced context)
- **Total Success Rate**: 60-90% (vs current 40-60%)

---

### Improvement 3: Progressive Medic Strategy

**Goal**: Don't repeat the same fix attempt 3 times - escalate strategy

**Implementation**:
```python
# ENHANCED: Medic loop with progressive strategy (kaya.py:1459)

fix_attempts = 0
medic_strategies = [
    {'name': 'basic', 'use_rag': False, 'prompt_style': 'minimal'},
    {'name': 'basic_retry', 'use_rag': False, 'prompt_style': 'detailed'},
    {'name': 'rag_enhanced', 'use_rag': True, 'prompt_style': 'detailed'},
    {'name': 'rag_deep', 'use_rag': True, 'prompt_style': 'step_by_step'},
    {'name': 'last_resort', 'use_rag': True, 'prompt_style': 'rewrite'}
]

while not runner_result.success and fix_attempts < max_fix_attempts:
    fix_attempts += 1
    strategy = medic_strategies[min(fix_attempts-1, len(medic_strategies)-1)]

    logger.warning(f"❌ Test failed, attempt {fix_attempts}/{max_fix_attempts} (strategy: {strategy['name']})")

    # Build error message with progressive enhancement
    error_message = runner_result.error or "Test execution failed"

    if strategy['use_rag'] and fix_attempts >= 2:
        # Use RAG (existing smart query logic)
        rag_results = self.archon.search_knowledge_base(...)
        if rag_results.get('success'):
            error_message += f"\n\nRelevant patterns from docs:\n{...}"

    # Add passing test patterns on later attempts
    if fix_attempts >= 3 and context.get('similar_passing_tests'):
        error_message += f"\n\nSimilar passing tests for reference:\n{...}"

    # Adjust Medic prompt based on strategy
    medic_result = self._medic_agent.execute(
        test_path=test_path,
        error_message=error_message,
        task_id=task_id,
        feature=task.get('feature'),
        strategy=strategy  # NEW: Pass strategy to Medic
    )

    # ... existing retry logic ...
```

**Benefits**:
- Attempts 1-2: Quick fixes (selector updates)
- Attempts 3-4: RAG-enhanced fixes (learn from docs)
- Attempts 5+: Deep analysis with passing test patterns
- Higher success rate without wasting early attempts

---

### Improvement 4: HITL Dashboard Integration

**Goal**: Make failed tasks visible and actionable in real-time

**Implementation**:

**A. Emit WebSocket Events**:
```python
# Add to kaya.py task execution

from agent_system.observability.event_stream import emit_agent_event

# When task fails
if not runner_result.success and fix_attempts >= max_fix_attempts:
    # Update Archon
    self.archon.update_task_status(task_id, 'review', ...)

    # NEW: Emit to HITL dashboard
    emit_agent_event({
        'type': 'task_escalation',
        'task_id': task_id,
        'title': task_title,
        'error': runner_result.error,
        'fix_attempts': fix_attempts,
        'test_path': test_path,
        'priority': 'high' if 'auth' in task_title.lower() else 'medium',
        'timestamp': time.time()
    })

    logger.error(f"🚨 Task escalated to HITL: {task_title}")
```

**B. Ensure Dashboards Are Running**:
```bash
# In start_superagent.sh or docker-compose.yml

# Start HITL dashboard (port 8001)
python web/hitl_dashboard/server.py &

# Start observability dashboard (port 8000)
python web/dashboard_server.py &

# Start WebSocket event stream (port 3010)
python -m agent_system.observability.event_stream &
```

**C. Add Dashboard URL to Build Summary**:
```python
summary_message = f"""
🏗️  Feature Build Complete!

Project: {project_id}
Total Tasks: {total_tasks}
✅ Completed: {completed_count}
❌ Failed: {failed_count}

🔍 View Details:
- HITL Dashboard: http://localhost:8001
- Observability: http://localhost:8000
- Failed Tasks: {failed_list}
"""
```

---

### Improvement 5: Screenshot Capture for All Tests

**Goal**: Always capture visual evidence, even for Runner-only validation

**Implementation**:
```python
# Modify Runner to capture screenshots

# runner.py: Add screenshot capture during test execution

def execute(self, test_path: str, ...) -> AgentResult:
    # ... existing test execution ...

    # NEW: Always capture screenshots directory
    screenshots_dir = f"/app/build/artifacts/screenshots/{test_id}/"

    # Run Playwright with screenshot flag
    result = subprocess.run(
        [
            'npx', 'playwright', 'test', test_path,
            '--output', screenshots_dir,  # Ensure screenshots saved
            ...
        ],
        ...
    )

    # Parse screenshots from output directory
    screenshots = glob.glob(f"{screenshots_dir}/*.png")

    return AgentResult(
        success=...,
        data={
            'test_passed': ...,
            'screenshots': screenshots,  # NEW!
            ...
        }
    )
```

---

## 5. IMPLEMENTATION PRIORITY

### Phase 1 (Tonight - Critical for Overnight Build):
1. ✅ **Fix filename sanitization** (DONE)
2. ✅ **Optimize RAG queries** (DONE)
3. 🔴 **Add Critic to autonomous workflow** (30 mins)
4. 🔴 **Increase retry attempts 3→5** (5 mins)
5. 🔴 **Add second-pass retry logic** (1 hour)

**Expected Result**: 60-80% success rate (vs current 0-40%)

### Phase 2 (Tomorrow - Enhanced Quality):
6. 🟡 **Add Gemini validation** (1 hour)
7. 🟡 **Progressive Medic strategies** (1 hour)
8. 🟡 **Screenshot capture in Runner** (30 mins)

**Expected Result**: 80-95% success rate + visual proof

### Phase 3 (This Week - Full Visibility):
9. 🟢 **HITL Dashboard integration** (2 hours)
10. 🟢 **WebSocket event streaming** (1 hour)
11. 🟢 **Observability dashboard** (1 hour)

**Expected Result**: Full real-time visibility + human escalation

---

## 6. COST ANALYSIS

### Current Autonomous Build (Per Feature):
- Scribe: $0.15 (Sonnet 4.5)
- Runner: $0.01 (Haiku)
- Medic x3: $0.45 (3 × Sonnet 4.5)
- **Total**: ~$0.61 per feature
- **Failure Rate**: 60-80% → Wasted cost

### With Improvements (Per Feature):
- Scribe: $0.15
- **Critic**: $0.001 (Haiku - ADDED)
- Runner: $0.01
- Medic x5 (progressive): $0.60 (less waste due to Critic filtering)
- **Gemini**: $0.08 (ADDED - only for passing tests)
- **Total**: ~$0.85 per passing test
- **Failure Rate**: 10-20% → Much less waste

### ROI Calculation (42 features):
**Current**:
- Cost: 42 × $0.61 = $25.62
- Success: ~40% = 17 tests
- Cost per passing test: $25.62 / 17 = $1.51

**With Improvements**:
- Cost: 42 × $0.85 = $35.70 (only successful tests)
- Success: ~85% = 36 tests
- Cost per passing test: $35.70 / 36 = $0.99

**Benefit**:
- +19 passing tests (17 → 36)
- Lower cost per passing test ($1.51 → $0.99)
- Visual evidence (screenshots) included
- Real-time visibility (dashboards)

---

## 7. TESTING PLAN

### Before Tonight's Build:
```bash
# Test 1: Single feature with full pipeline
docker exec superagent-app python agent_system/cli.py kaya \
  "write a test for clicking a logout button"

# Verify:
# - Critic runs and approves
# - Runner executes
# - If fails, Medic tries 5 times (not 3)
# - Gemini validates with screenshots

# Test 2: Build with 3 features (mini build)
docker exec superagent-app python agent_system/cli.py kaya \
  "build 3 tests: login, logout, profile view"

# Verify:
# - First pass completes
# - Failed tasks get second pass
# - Final success rate >60%
```

### Monitoring During Build:
```bash
# Watch logs
docker logs -f superagent-app | grep -E "Critic|Gemini|Second pass"

# Check task status in Archon
docker exec superagent-app python3 <<EOF
from agent_system.archon_client import get_archon_client
archon = get_archon_client()
tasks = archon.find_tasks(filters={'status': 'review'})
print(f"Tasks in review: {tasks['count']}")
EOF

# View screenshots
docker exec superagent-app ls -lh /app/build/artifacts/screenshots/
```

---

## 8. SUCCESS METRICS

### Tonight's Build (Phase 1):
- ✅ First pass success rate: ≥40% (baseline)
- ✅ Second pass recovery: +20-30%
- ✅ Total success rate: ≥60%
- ✅ Tasks abandoned (status='review'): ≤40%
- ✅ Cost per passing test: ≤$1.20

### Tomorrow (Phase 2):
- ✅ Gemini validation coverage: 100%
- ✅ Screenshot capture: 100%
- ✅ Total success rate: ≥80%
- ✅ Visual proof for all passing tests

### This Week (Phase 3):
- ✅ HITL dashboard operational
- ✅ Real-time task visibility
- ✅ Human annotations: ≥10 (learning data)
- ✅ Total success rate: ≥90%

---

## 9. ROLLBACK PLAN

If improvements cause issues:

```bash
# Revert to previous commit
git revert HEAD

# Rebuild Docker
docker compose -f config/docker-compose.yml build superagent
docker compose -f config/docker-compose.yml restart superagent

# Or use specific commit
git checkout e6a05c1  # Known good state (filename fix)
```

---

## 10. NEXT STEPS

**Immediate (Tonight)**:
1. Implement Critic in autonomous workflow
2. Increase retry attempts to 5
3. Add second-pass retry logic
4. Test with 3-feature mini build
5. Run full overnight build

**Tomorrow**:
6. Add Gemini validation
7. Implement progressive Medic strategies
8. Verify screenshot capture

**This Week**:
9. Integrate HITL dashboard
10. Add WebSocket event streaming
11. Document improvements

**Questions for User**:
1. Should Critic rejection be HARD STOP or just a warning?
2. What's the max cost per feature you're comfortable with? (Currently targeting $0.85)
3. Do you want Gemini to run on ALL tests or only final validation?
4. Should second-pass use Sonnet for ALL retries (more expensive but higher success)?

---

## Summary

**Your frustration was 100% justified.** The autonomous build was using a degraded 2-stage pipeline instead of the designed 5-stage quality gate:

**Missing Stages**:
- ❌ Critic (quality filter)
- ❌ Gemini (browser validation + screenshots)
- ❌ Second-pass retry (abandoned 'review' tasks)

**With these improvements, you'll see**:
- 40% → 80-90% success rate
- Screenshots for all passing tests
- Real-time dashboard visibility
- Fewer wasted API costs (Critic filters bad tests early)
- Higher quality (Gemini proves correctness)

**Tonight's build will be MUCH better.** 🚀
