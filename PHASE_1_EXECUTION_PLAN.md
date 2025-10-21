# Phase 1 Execution Plan - 30 Minutes

## User Decisions
1. **Critic behavior**: LOG AND CONTINUE (warn but don't block)
2. **Budget**: $2.00 max for tonight's build
3. **Gemini**: Run on all passing tests
4. **Timeline**: 30 minutes to implement critical fixes

## Parallel Task Breakdown

### Task 1: Add Critic to Autonomous Workflow (10 mins)
**File**: `agent_system/agents/kaya.py`
**Location**: Lines 1434-1456 (in `_execute_test_task_with_validation`)
**Changes**:
```python
# AFTER Scribe generates test (line 1449)
test_path = scribe_result.data.get('test_path')
logger.info(f"✅ Scribe: Test generated at {test_path}")

# NEW: Step 1.5 - Critic pre-validates (LOG AND CONTINUE)
logger.info("🔍 Critic: Pre-validating test quality...")
try:
    critic = self._get_agent('critic')
    critic_result = critic.execute(test_path=test_path)

    if not critic_result.success:
        logger.warning(f"⚠️  Critic found issues: {critic_result.error}")
        logger.warning("Continuing anyway - Medic will fix if needed")
    else:
        logger.info("✅ Critic: Test quality approved")
except Exception as e:
    logger.warning(f"Critic failed: {e}, continuing anyway")

# EXISTING: Step 2: Runner validates test
logger.info("🏃 Runner: Validating test...")
```

**Expected Time**: 10 minutes
**Impact**: 15-30% of bad tests logged early, better debugging info

---

### Task 2: Increase Retry Attempts 3→5 (2 mins)
**File**: `agent_system/agents/kaya.py`
**Location**: Line 1407
**Changes**:
```python
# BEFORE
max_fix_attempts: int = 3

# AFTER
max_fix_attempts: int = 5  # Increased for better recovery
```

**Location**: Line 1670 (in `_handle_build_feature`)
**Changes**:
```python
# When calling the task execution
task_result = self._execute_test_task_with_validation(
    task,
    project_id,
    context,
    max_fix_attempts=5  # Explicitly pass 5 attempts
)
```

**Expected Time**: 2 minutes
**Impact**: +20-30% recovery rate (more chances to fix)

---

### Task 3: Add Second-Pass Retry Logic (15 mins)
**File**: `agent_system/agents/kaya.py`
**Location**: Lines 1693-1719 (after first pass completes in `_handle_build_feature`)
**Changes**:
```python
# AFTER first pass (line 1691)
# ... existing first pass logic ...

# NEW: SECOND PASS - Retry failed tasks
second_pass_completed = []
if failed_tasks and len(failed_tasks) <= 10:  # Don't retry if too many failures
    logger.info(f"🔄 SECOND PASS: Retrying {len(failed_tasks)} failed tasks with enhanced context")

    for idx, failed_task_info in enumerate(failed_tasks, 1):
        logger.info(f"🔄 Retry {idx}/{len(failed_tasks)}: {failed_task_info['title']}")

        # Fetch the full task details
        task_to_retry = None
        for task in created_tasks:
            if task['task_id'] == failed_task_info['task_id']:
                task_to_retry = task
                break

        if not task_to_retry:
            continue

        # Enhanced context for second pass
        enhanced_context = {
            **(context or {}),
            'retry_attempt': True,
            'previous_error': failed_task_info['error'],
            'first_pass_failed': True
        }

        # Retry with MORE attempts (5 → 7)
        logger.info(f"🔄 Retrying with 7 attempts and enhanced RAG context...")
        retry_result = self._execute_test_task_with_validation(
            task_to_retry,
            project_id,
            enhanced_context,
            max_fix_attempts=7  # Extra attempts on second pass
        )

        if retry_result['success']:
            second_pass_completed.append({
                'task_id': task_to_retry['task_id'],
                'title': task_to_retry['title'],
                'result': retry_result
            })
            logger.info(f"✅ Second pass SUCCESS: {task_to_retry['title']}")

            # Remove from failed_tasks
            failed_tasks = [t for t in failed_tasks if t['task_id'] != task_to_retry['task_id']]
        else:
            logger.error(f"❌ Second pass FAILED: {task_to_retry['title']}")

    # Update totals
    completed_tasks.extend(second_pass_completed)
    completed_count = len(completed_tasks)
    failed_count = len(failed_tasks)

# Update summary_message to include second pass stats
summary_message = f"""
🏗️  Feature Build Complete!

Project: {project_id}
Total Tasks: {total_tasks}
✅ First Pass: {completed_count - len(second_pass_completed)}/{total_tasks}
🔄 Second Pass: {len(second_pass_completed)} recovered
✅ Total Completed: {completed_count}/{total_tasks}
❌ Still Failed: {failed_count}

Completed Tasks:
{completed_list}
{failed_list}

💡 Second pass recovered {len(second_pass_completed)} tasks that initially failed!
"""
```

**Expected Time**: 15 minutes
**Impact**: +20-30% recovery (retry failed tasks with more attempts)

---

### Task 4: Budget Enforcement for $2 Cap (3 mins)
**File**: `agent_system/agents/kaya.py`
**Location**: Start of `_handle_build_feature` (after line 1618)
**Changes**:
```python
# After feature description check (line 1616)
try:
    logger.info(f"🏗️  Building feature: {feature}")

    # NEW: Initialize cost tracking with $2 budget
    total_cost = 0.0
    budget_cap = 2.00  # User's max budget for tonight

    logger.info(f"💰 Budget cap: ${budget_cap:.2f}")

    # ... existing project creation ...

    # MODIFY: Track costs during task execution
    # In the task execution loop (line 1662), add:
    for idx, task in enumerate(created_tasks, 1):
        # Check budget before executing
        if total_cost >= budget_cap:
            logger.warning(f"💰 Budget cap reached (${total_cost:.2f}), stopping execution")
            # Mark remaining tasks as 'todo'
            for remaining_task in created_tasks[idx:]:
                self.archon.update_task_status(remaining_task['task_id'], 'todo')
            break

        logger.info(f"📝 Task {idx}/{len(created_tasks)}: {task['title']} (budget: ${total_cost:.2f}/${budget_cap:.2f})")

        # ... existing task execution ...

        # Track cost from task result
        if 'cost_usd' in task_result:
            total_cost += task_result.get('cost_usd', 0)
```

**Expected Time**: 3 minutes
**Impact**: Ensures build stops at $2 cap

---

## Execution Timeline

```
00:00 - START
│
├─ 00:00-00:10 │ Task 1: Add Critic (log and continue)
│              │ Agent: Code modification in kaya.py lines 1434-1456
│
├─ 00:10-00:12 │ Task 2: Increase retry attempts 3→5
│              │ Agent: Quick find-replace in kaya.py
│
├─ 00:12-00:27 │ Task 3: Add second-pass retry logic
│              │ Agent: Code addition in kaya.py lines 1693+
│
├─ 00:27-00:30 │ Task 4: Budget enforcement
│              │ Agent: Cost tracking in kaya.py
│
└─ 00:30 - COMMIT & TEST
```

## File Changes Summary

**Single File**: `agent_system/agents/kaya.py`

**4 Modifications**:
1. Lines 1434-1456: Insert Critic step (10 lines added)
2. Line 1407: Change `max_fix_attempts: int = 3` → `5`
3. Lines 1693-1750: Add second-pass retry logic (60 lines added)
4. Lines 1618-1670: Add budget tracking (20 lines added)

**Total Lines Changed**: ~90 lines in one file

## Testing Before Overnight Build

```bash
# Quick test with 1 feature
docker exec superagent-app python agent_system/cli.py kaya \
  "write a test for logout button"

# Verify in logs:
# - "🔍 Critic: Pre-validating..."
# - "max_fix_attempts: 5"
# - Cost tracking messages

# Mini-build with 3 features
docker exec superagent-app python agent_system/cli.py kaya \
  "build 3 features: login, logout, profile"

# Verify:
# - First pass completes
# - "🔄 SECOND PASS" message appears
# - Some tasks recovered in second pass
# - Budget messages show cost tracking
```

## Expected Results Tonight

### First Pass (Standard):
- **Target**: 40-50% success rate
- **Budget Used**: ~$0.80-$1.20

### Second Pass (Recovery):
- **Target**: +15-25% recovery
- **Budget Used**: +$0.40-$0.80

### Total:
- **Success Rate**: 55-75% (vs previous 0-40%)
- **Total Cost**: $1.20-$2.00 (within budget)
- **Tests Generated**: 23-32 passing (out of 42 features)

## Success Criteria

✅ Critic runs and logs warnings (not blocking)
✅ Tasks get 5 attempts instead of 3
✅ Second pass recovers 15-25% of failures
✅ Build stops at $2.00 budget cap
✅ More than 20 passing tests (vs previous ~10)

## Rollback Plan

```bash
# If issues occur
git stash
docker compose -f config/docker-compose.yml restart superagent

# Or revert to known good commit
git checkout e6a05c1  # Filename fix commit
```

## Next (After Tonight's Success)

Tomorrow we'll add:
- Gemini browser validation
- Progressive Medic strategies
- Screenshot capture
- HITL dashboard integration

**Target**: 80-95% success rate with visual proof

---

**Ready to execute in 30 minutes!** 🚀
