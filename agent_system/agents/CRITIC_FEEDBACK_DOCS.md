# Critic Agent - Enhanced Rejection Feedback

## Overview

The Critic agent has been enhanced with detailed, actionable rejection feedback to help the Scribe agent quickly identify and fix issues in test code. This feedback system provides structured information about anti-patterns, missing assertions, and performance issues with specific line numbers and fix suggestions.

## Features

### 1. Structured Issue Detection

Each detected issue includes:
- **Type**: Category of issue (anti_pattern, missing_assertions, excessive_steps, excessive_duration)
- **Severity**: Critical or Warning
- **Line Number**: Exact location of the issue (for anti-patterns)
- **Matched Text**: The problematic code that was detected
- **Reason**: Why this is a problem
- **Fix Suggestion**: Actionable code suggestion to resolve the issue

### 2. Priority Ordering

Issues are organized by severity:
1. **Critical Issues** (shown first with X marker):
   - Anti-patterns (nth(), CSS classes, waitForTimeout, hardcoded credentials, localhost)
   - Missing assertions

2. **Warnings** (shown with ! marker):
   - Excessive step count
   - Excessive duration

### 3. Human-Readable Feedback

The feedback is formatted for easy consumption by both agents and humans:

```
REJECTED - Issues Found:

X Anti-patterns (3 issues):
  - Line 15: .nth(2) - Index-based selectors are flaky
    FIX: Replace with data-testid selector: await page.locator('[data-testid="element-name"]').click()
  - Line 23: waitForTimeout - Use waitForSelector instead
    FIX: Replace with waitForSelector: await page.waitForSelector('[data-testid="element"]', { timeout: 5000 })
  - Line 31: .css-abc123 - Avoid generated CSS classes
    FIX: Use data-testid attribute instead of CSS class: <div data-testid="element-name">

X Missing assertions (1 expected, 0 found):
  - Tests must have at least 1 expect() call
  FIX: Add expect() assertions after key actions to verify behavior

! Performance (16 steps, max 10):
  - Test has 16 steps, exceeds maximum of 10
  FIX: Consider splitting test into smaller, focused tests

Summary:
  - Critical issues: 4
  - Warnings: 1
  - Estimated cost: $0.0160
  - Estimated duration: 32.0s
```

## API Response Structure

### AgentResult.data

```python
{
    'status': 'approved' | 'rejected',
    'test_path': str,
    'issues_found': List[Dict],  # Structured issue objects
    'feedback': str,              # Formatted feedback text (None if approved)
    'estimated_cost_usd': float,
    'estimated_duration_ms': int,
    'estimated_steps': int
}
```

### Issue Object Structure

```python
{
    # Common fields
    'type': str,          # anti_pattern | missing_assertions | excessive_steps | excessive_duration
    'severity': str,      # critical | warning
    'reason': str,        # Human-readable explanation
    'fix': str,           # Actionable fix suggestion

    # Anti-pattern specific
    'line': int,          # Line number where issue was found
    'pattern': str,       # Regex pattern that matched
    'matched': str,       # Actual text that matched

    # Performance specific
    'actual': int,        # Actual count/duration
    'max': int,          # Maximum allowed
    'expected': int      # Expected count (for assertions)
}
```

### AgentResult.metadata

```python
{
    'anti_patterns_found': int,  # Count of anti-pattern issues
    'assertion_count': int,       # Total expect() calls found
    'critical_issues': int,       # Count of critical severity issues
    'warnings': int              # Count of warning severity issues
}
```

## Usage Examples

### Example 1: Scribe Integration

```python
from agent_system.agents.critic import CriticAgent

critic = CriticAgent()
result = critic.execute('/path/to/test.spec.ts')

if result.data['status'] == 'rejected':
    # Send feedback to Scribe for revision
    print(result.data['feedback'])

    # Access structured issues for programmatic handling
    for issue in result.data['issues_found']:
        if issue['severity'] == 'critical':
            print(f"MUST FIX: Line {issue.get('line', 'N/A')} - {issue['reason']}")
            print(f"Suggestion: {issue['fix']}")
```

### Example 2: Filtering by Issue Type

```python
result = critic.execute('/path/to/test.spec.ts')

if result.data['status'] == 'rejected':
    # Get only anti-pattern issues
    anti_patterns = [
        issue for issue in result.data['issues_found']
        if issue['type'] == 'anti_pattern'
    ]

    # Get only performance warnings
    perf_warnings = [
        issue for issue in result.data['issues_found']
        if issue['type'] in ['excessive_steps', 'excessive_duration']
    ]
```

### Example 3: Metadata Analysis

```python
result = critic.execute('/path/to/test.spec.ts')

metadata = result.metadata
if metadata['critical_issues'] > 0:
    print(f"Found {metadata['critical_issues']} critical issues that MUST be fixed")

if metadata['assertion_count'] == 0:
    print("WARNING: Test has no assertions!")
```

## Anti-Pattern Detection

### Detected Patterns

| Pattern | Reason | Fix Suggestion |
|---------|--------|----------------|
| `.nth(\d+)` | Index-based selectors are flaky | Use data-testid selectors |
| `.css-[a-z0-9]+` | Generated CSS classes change frequently | Use data-testid attributes |
| `waitForTimeout` | Non-deterministic waits | Use waitForSelector instead |
| `hard-coded.*credential` | Security risk | Use environment variables |
| `localhost\|127.0.0.1` | Environment-specific | Use process.env.BASE_URL |

### Custom Pattern Example

To add new anti-patterns, modify `ANTI_PATTERNS` in `critic.py`:

```python
ANTI_PATTERNS = [
    {
        'pattern': r'\.nth\(\d+\)',
        'reason': 'Index-based selectors are flaky'
    },
    # Add your custom pattern
    {
        'pattern': r'eval\(',
        'reason': 'eval() is unsafe and should be avoided',
        'flags': re.IGNORECASE
    }
]
```

## Quality Thresholds

### Hard Limits

- **Maximum Steps**: 10 actions per test
- **Maximum Duration**: 60 seconds (60,000ms)
- **Minimum Assertions**: 1 expect() call

### Adjusting Thresholds

Modify class constants in `critic.py`:

```python
class CriticAgent(BaseAgent):
    MAX_STEPS = 10
    MAX_DURATION_MS = 60000
```

## Testing

Run the comprehensive test suite:

```bash
# All feedback tests
python3 -m pytest tests/test_critic_feedback.py -v

# Specific test
python3 -m pytest tests/test_critic_feedback.py::test_critic_rejects_with_detailed_feedback_anti_patterns -v

# See example output
PYTHONPATH=/path/to/SuperAgent python3 tests/example_critic_output.py
```

## Integration with Router (Kaya)

The enhanced feedback is designed to work seamlessly with the Router's retry logic:

```python
# In router.py or orchestration logic
result = critic.execute(test_path)

if result.data['status'] == 'rejected':
    # Pass detailed feedback to Scribe for revision
    scribe_context = {
        'previous_test': test_path,
        'rejection_feedback': result.data['feedback'],
        'structured_issues': result.data['issues_found']
    }

    # Scribe can now fix specific issues with line numbers
    revised_result = scribe.execute(**scribe_context)
```

## Benefits

1. **Faster Iteration**: Scribe knows exactly what to fix and where
2. **Clear Communication**: Human-readable feedback for debugging
3. **Structured Data**: Programmatic access to issues for automation
4. **Priority Ordering**: Critical issues addressed first
5. **Actionable Suggestions**: Specific code examples for fixes
6. **Cost Reduction**: Fewer validation retries due to clearer guidance

## Future Enhancements

Potential improvements for future iterations:

- [ ] Contextual suggestions based on test type (auth, checkout, etc.)
- [ ] Learning from past fixes to improve suggestions
- [ ] Automatic fix application for simple patterns
- [ ] Integration with git diff to show before/after
- [ ] Severity levels based on test criticality (auth vs UI)
- [ ] Custom rule sets per project or domain
