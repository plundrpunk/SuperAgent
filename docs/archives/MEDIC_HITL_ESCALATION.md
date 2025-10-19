# Medic HITL Escalation Implementation

## Overview

The Medic agent now includes comprehensive Human-in-the-Loop (HITL) escalation functionality that automatically escalates failed test fixes to a queue for human review when automated fixes are unsuccessful or risky.

## Implementation Location

**File**: `/Users/rutledge/Documents/DevFolder/SuperAgent/agent_system/agents/medic.py`

## Key Features

### 1. Automatic Attempt Tracking

The Medic agent now tracks all fix attempts per task using Redis:

- **Storage Key**: `medic:attempts:{task_id}`
- **History Key**: `medic:history:{task_id}`
- **TTL**: 24 hours
- **Tracking Method**: `_increment_fix_attempts(task_id, test_path)`

### 2. Three Escalation Triggers

#### Trigger 1: Max Retries Exceeded
```python
MAX_RETRIES = 3  # After 3 attempts, escalate
```
- Escalates immediately on 4th attempt
- Prevents infinite retry loops
- Severity: `medium` (default)

#### Trigger 2: Regression Detected
```python
if comparison['new_failures'] > 0:
    # Escalate with high severity
```
- Triggers when fix introduces new test failures
- Automatically rolls back changes
- Severity: `high`

#### Trigger 3: Low AI Confidence
```python
CONFIDENCE_THRESHOLD = 0.7  # 0.0-1.0 scale
if confidence < self.CONFIDENCE_THRESHOLD:
    # Escalate before applying risky fix
```
- AI self-assesses fix confidence
- Prevents applying uncertain fixes
- Severity: `medium`

### 3. Confidence Scoring

The AI now returns confidence scores with every fix:

**Prompt Enhancement**:
```
CONFIDENCE: <0.0-1.0 score>
(0.0-0.5 = uncertain, 0.5-0.7 = moderate, 0.7-0.9 = confident, 0.9-1.0 = very confident)
```

**Parsing**:
- Extracted via regex from AI response
- Normalized to 0.0-1.0 range (handles percentages)
- Default confidence: 0.8 if not provided

### 4. Priority Calculation

HITL tasks are prioritized based on multiple factors:

```python
priority = min(base_priority + attempts_factor, 1.0)

# Base priority by severity:
- low: 0.1
- medium: 0.3
- high: 0.5
- critical: 0.7

# Attempts factor:
attempts_factor = min(attempts / 10, 0.3)  # Max 0.3 contribution
```

**Example Priorities**:
- High severity + 5 attempts = 0.8 priority
- Medium severity + 1 attempt = 0.4 priority
- Critical severity + 10 attempts = 1.0 priority (max)

### 5. Comprehensive Context Capture

When escalating, the following data is captured:

```python
hitl_task = {
    'task_id': str,               # Unique identifier
    'feature': str,               # Feature name
    'code_path': str,             # Test file path
    'logs_path': str,             # Execution logs
    'screenshots': List[str],     # Up to 5 screenshots
    'attempts': int,              # Number of fix attempts
    'last_error': str,            # Original error message
    'priority': float,            # 0.0-1.0
    'severity': str,              # low/medium/high/critical
    'escalation_reason': str,     # Why it was escalated
    'attempt_history': List[Dict], # All previous attempts
    'ai_diagnosis': str,          # AI's diagnosis
    'ai_confidence': float,       # AI confidence score
    'artifacts': {
        'diff': str,              # Code changes (truncated)
        'baseline': Dict,         # Pre-fix test results
        'after_fix': Dict,        # Post-fix test results
        'comparison': Dict        # Regression analysis
    },
    'created_at': str             # ISO timestamp
}
```

### 6. Integration with HITL Queue

The escalation integrates with the existing HITL queue system:

```python
from agent_system.hitl.queue import HITLQueue

hitl = HITLQueue(redis_client=self.redis)
hitl.add(hitl_task)
```

The queue automatically:
- Stores task in Redis with 24h TTL
- Adds to sorted set by priority
- Makes available for human review

## Usage

### Basic Usage

```python
from agent_system.agents.medic import MedicAgent

medic = MedicAgent()

result = medic.execute(
    test_path="tests/checkout.spec.ts",
    error_message="Error: Selector not found",
    task_id="task_123",  # Optional, auto-generated if not provided
    feature="checkout"   # Optional, helps with prioritization
)

if result.data.get('status') == 'escalated_to_hitl':
    print(f"Escalated: {result.data['reason']}")
    print(f"Priority: {result.data['priority']}")
    print(f"Attempts: {result.data['attempts']}")
```

### With Custom Redis/HITL Clients

```python
from agent_system.agents.medic import MedicAgent
from agent_system.state.redis_client import RedisClient
from agent_system.hitl.queue import HITLQueue

# Custom configuration
redis = RedisClient()
hitl = HITLQueue(redis_client=redis)

medic = MedicAgent(
    redis_client=redis,
    hitl_queue=hitl
)
```

### Checking Attempt Count

```python
# Get current attempt count for a task
attempts = medic._get_fix_attempts("task_123")
print(f"Current attempts: {attempts}")

# Get full attempt history
history = medic._get_attempt_history("task_123")
for attempt in history:
    print(f"Attempt {attempt['attempt']} at {attempt['timestamp']}")
```

## Return Values

### Success Case
```python
AgentResult(
    success=True,
    data={
        'status': 'fix_applied',
        'test_path': str,
        'diagnosis': str,
        'baseline': Dict,
        'after_fix': Dict,
        'comparison': Dict,
        'artifacts': Dict
    },
    cost_usd=float,
    execution_time_ms=int
)
```

### Escalated Case
```python
AgentResult(
    success=False,
    error="Escalated to HITL: {reason} (attempts: {n})",
    data={
        'status': 'escalated_to_hitl',
        'reason': str,  # max_retries_exceeded | regression_detected | low_confidence
        'task_id': str,
        'test_path': str,
        'attempts': int,
        'severity': str,
        'priority': float,
        'hitl_task': Dict,  # Full task payload
        'fix_rolled_back': bool  # Only for regression_detected
    },
    metadata={
        'escalation_reason': str,
        'attempts': int,
        'severity': str
    },
    cost_usd=float,
    execution_time_ms=int
)
```

## Configuration

### Environment Variables

Required in `.env`:
```bash
ANTHROPIC_API_KEY=your-api-key-here
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=  # Optional
```

### Tunable Parameters

Located in `MedicAgent` class:

```python
MAX_RETRIES = 3                    # Number of attempts before escalation
CONFIDENCE_THRESHOLD = 0.7         # Minimum AI confidence (0.0-1.0)
DEFAULT_TIMEOUT = 120              # Test execution timeout (seconds)
```

## Testing

### Unit Tests

**File**: `/Users/rutledge/Documents/DevFolder/SuperAgent/tests/test_medic_hitl_escalation.py`

Run tests:
```bash
pytest tests/test_medic_hitl_escalation.py -v
```

Test coverage:
- ✅ Escalation after max retries
- ✅ Escalation on low confidence
- ✅ Attempt tracking increments correctly
- ✅ Attempt history tracked
- ✅ Priority calculation
- ✅ HITL task payload structure

### Integration Tests

Existing tests updated in `tests/test_medic.py`:
- ✅ Regression detection now escalates to HITL
- ✅ HITL escalation message format
- ✅ Rollback on regression with escalation

## Architecture Decisions

### Why Track Attempts in Redis?

- **Hot state**: Fix attempts are temporary (24h TTL)
- **Fast access**: O(1) lookups for attempt counts
- **Distributed**: Multiple Medic instances can share state
- **Automatic cleanup**: TTL prevents stale data accumulation

### Why Three Escalation Triggers?

1. **Max retries**: Prevents infinite loops, conserves API costs
2. **Regression**: Protects test suite stability (Hippocratic Oath)
3. **Low confidence**: Prevents uncertain fixes from being applied

### Why Confidence Scoring?

- **Self-awareness**: AI knows when it's uncertain
- **Risk mitigation**: Stop risky fixes before they break things
- **Cost optimization**: Don't waste regression tests on uncertain fixes
- **Human expertise**: Route complex issues to humans early

### Why Priority Scoring?

- **Resource allocation**: Humans review high-priority issues first
- **Feature importance**: Auth/payment issues get higher priority
- **Urgency tracking**: More attempts = more urgent
- **Fair queuing**: Prevents low-priority issues from starving

## Performance Impact

### API Cost per Escalation

- **Max retries**: $0.00 (no AI call needed)
- **Low confidence**: ~$0.01-0.03 (1 AI call for diagnosis)
- **Regression**: ~$0.01-0.03 (1 AI call + 2 regression test runs)

### Redis Storage per Task

- **Attempts counter**: ~20 bytes
- **Attempt history**: ~200 bytes per attempt
- **HITL task**: ~5-10 KB (includes truncated diffs)
- **Total per task**: ~10-15 KB
- **TTL**: 24 hours (auto-cleanup)

### Time to Escalate

- **Max retries check**: <10ms (Redis lookup)
- **Confidence check**: 0ms (parsed from AI response)
- **Regression check**: 2-10s (regression test execution)
- **HITL queue add**: <50ms (Redis write)

## Example Scenarios

### Scenario 1: Selector Changed in App

```
Attempt 1: Fix selector → Regression detected → Escalate (high priority)
Result: Escalated immediately, no wasted retries
```

### Scenario 2: Unclear Error Message

```
Attempt 1: AI confidence = 0.4 → Escalate (medium priority)
Result: Escalated before applying uncertain fix
```

### Scenario 3: Intermittent Flaky Test

```
Attempt 1: Fix applied → Test still fails
Attempt 2: Different fix → Test still fails
Attempt 3: Another fix → Test still fails
Attempt 4: Max retries → Escalate (medium-high priority based on attempts)
Result: Human can identify flakiness pattern
```

### Scenario 4: Breaking Change in API

```
Attempt 1: Fix API call → Regression: 3 new failures → Escalate (high priority)
Result: Human realizes API contract changed, needs broader fix
```

## Monitoring & Observability

### Key Metrics to Track

1. **Escalation Rate**: `escalated_tasks / total_tasks`
   - Target: 15-30% (per README_MEDIC.md)

2. **Escalation Reason Distribution**:
   - `max_retries_exceeded`: ~40%
   - `regression_detected`: ~30%
   - `low_confidence`: ~30%

3. **Average Attempts Before Escalation**:
   - Target: ≤1.5 retries per failure

4. **HITL Queue Depth**:
   - Alert if queue > 20 items

5. **Priority Distribution**:
   - High (>0.7): ~20%
   - Medium (0.3-0.7): ~60%
   - Low (<0.3): ~20%

### Logging

All escalations are logged with context:
```
[Medic] Escalating to HITL: {reason}
[Medic] Successfully added to HITL queue with priority {priority}
```

### Dashboards

Recommended metrics for observability dashboard:
- Real-time escalation events
- Queue depth over time
- Average time in queue
- Resolution rate by reason
- Cost per escalation

## Human Workflow

### HITL Dashboard (Future)

When implemented, humans will:
1. View queue sorted by priority
2. See full context (errors, diffs, attempts)
3. Annotate root cause
4. Provide fix strategy
5. Optionally apply patch directly
6. Mark as resolved

Annotations are stored in vector DB for agent learning.

## Future Enhancements

### 1. Pattern Learning
Store successful escalation resolutions in vector DB:
```python
# After human resolves issue
vector.store_hitl_annotation(
    annotation_id=f"hitl_{task_id}_{timestamp}",
    task_description=feature,
    annotation={
        'root_cause': str,
        'fix_strategy': str,
        'patch_diff': str
    }
)
```

### 2. Escalation Prediction
Use historical data to predict escalations:
```python
if pattern_matches_previous_escalation(error_message):
    # Escalate immediately, skip retries
    escalate_to_hitl(reason="similar_to_previous_escalation")
```

### 3. Dynamic Threshold Adjustment
Adjust confidence threshold based on historical accuracy:
```python
if ai_accuracy_last_week > 0.90:
    CONFIDENCE_THRESHOLD = 0.65  # More aggressive
else:
    CONFIDENCE_THRESHOLD = 0.75  # More conservative
```

### 4. Multi-Agent Consultation
Before escalating, consult other agents:
```python
# Ask Gemini to validate the fix
gemini_validation = gemini.validate_fix(fix, test_path)
if gemini_validation.success:
    # Apply fix with confidence
else:
    # Escalate with Gemini's feedback
```

## Troubleshooting

### Issue: Tasks not escalating

**Check**:
1. Redis connection: `redis.health_check()`
2. Attempt counter: `redis.get(f"medic:attempts:{task_id}")`
3. HITL queue: `hitl.list()`

### Issue: Escalating too frequently

**Solutions**:
1. Lower `CONFIDENCE_THRESHOLD` (e.g., 0.6)
2. Increase `MAX_RETRIES` (e.g., 5)
3. Check if AI prompts are properly formed

### Issue: Not escalating enough

**Solutions**:
1. Raise `CONFIDENCE_THRESHOLD` (e.g., 0.8)
2. Decrease `MAX_RETRIES` (e.g., 2)
3. Review AI confidence scores in logs

### Issue: Priority scores seem wrong

**Check**:
1. Severity mapping: `severity_scores` dict
2. Attempts factor calculation
3. Feature name matching (auth/payment keywords)

## References

- **Implementation**: `/Users/rutledge/Documents/DevFolder/SuperAgent/agent_system/agents/medic.py`
- **Tests**: `/Users/rutledge/Documents/DevFolder/SuperAgent/tests/test_medic_hitl_escalation.py`
- **HITL Queue**: `/Users/rutledge/Documents/DevFolder/SuperAgent/agent_system/hitl/queue.py`
- **Redis Client**: `/Users/rutledge/Documents/DevFolder/SuperAgent/agent_system/state/redis_client.py`
- **Schema**: `/Users/rutledge/Documents/DevFolder/SuperAgent/agent_system/hitl/schema.json`
- **Documentation**: `/Users/rutledge/Documents/DevFolder/SuperAgent/agent_system/agents/README_MEDIC.md`

## Summary

The Medic HITL escalation system provides:

✅ **Automatic escalation** on 3 triggers (max retries, regression, low confidence)
✅ **Attempt tracking** with full history in Redis
✅ **Confidence scoring** from AI self-assessment
✅ **Priority calculation** based on severity and attempts
✅ **Comprehensive context** capture for human review
✅ **Safe rollback** on regression detection
✅ **Cost-effective** operation with early escalation
✅ **Fully tested** with comprehensive unit tests

This ensures that Medic follows its **Hippocratic Oath** ("First, do no harm") while providing a safety valve for complex issues that require human expertise.
