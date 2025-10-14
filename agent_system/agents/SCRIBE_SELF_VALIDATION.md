# Scribe Agent Self-Validation

## Overview

The Scribe agent now includes built-in self-validation using Critic criteria, reducing unnecessary Gemini validation attempts and improving test quality before submission.

## Key Features

### 1. Pre-Submission Validation
Scribe validates every generated test against all Critic criteria before returning results:

- ❌ **Anti-Patterns Rejected:**
  - `.nth(n)` - Index-based selectors (flaky)
  - `.css-*` - Generated CSS classes (change frequently)
  - `waitForTimeout` - Use `waitForSelector` instead
  - Hard-coded credentials - Use environment variables
  - `localhost`/`127.0.0.1` - Use `process.env.BASE_URL`

- ✅ **Required Patterns:**
  - `data-testid` selectors exclusively
  - At least 1 `expect()` assertion
  - Screenshots at key steps
  - Estimated duration < 60 seconds
  - Step count ≤ 10

### 2. Auto-Retry with Feedback
When validation fails, Scribe automatically retries with detailed feedback:

```python
# Retry Loop
for attempt in range(1, MAX_RETRIES + 1):
    # 1. Generate test
    test_content = generate_test(description)

    # 2. Validate
    passed, issues = validate_generated_test(test_content)

    # 3. If passed, return success
    if passed:
        return success

    # 4. If failed, enhance prompt with feedback
    description = f"{description}\n\nPREVIOUS FAILED: {issues}"
```

**Max Retries:** 3 attempts
**Feedback Provided:** Specific issues found in previous attempt
**Success Rate Target:** 50%+ reduction in Critic rejections

### 3. Validation Metrics
Tracks validation performance:

```python
{
    'agent': 'scribe',
    'validation_attempts': 150,
    'validation_failures': 20,
    'success_rate': 0.867,  # 86.7% pass rate
    'total_retries_used': 25,
    'avg_retries_per_success': 0.19
}
```

## Implementation

### Core Validation Function

```python
def _validate_generated_test(test_content: str) -> Tuple[bool, List[str]]:
    """
    Validate test against Critic criteria.

    Returns:
        (passed: bool, issues: List[str])
    """
    issues = []

    # Check anti-patterns
    for pattern_def in ANTI_PATTERNS:
        if re.search(pattern_def['pattern'], test_content):
            issues.append(pattern_def['reason'])

    # Check required patterns
    if not re.search(r'\bexpect\s*\(', test_content):
        issues.append("Missing expect() assertions")

    if not re.search(r'data-testid', test_content):
        issues.append("Missing data-testid selectors")

    if not re.search(r'\.screenshot\(', test_content):
        issues.append("Missing screenshots")

    # Check complexity
    steps = count_steps(test_content)
    if steps > MAX_STEPS:
        issues.append(f"Too many steps: {steps} > {MAX_STEPS}")

    return (len(issues) == 0, issues)
```

### Generation with Validation

```python
def execute(task_description: str, feature_name: str, output_path: str) -> AgentResult:
    """Generate test with self-validation."""

    # Generate with retry logic
    result = _generate_with_validation(
        task_description=task_description,
        feature_name=feature_name,
        max_retries=3
    )

    if not result['success']:
        return AgentResult(
            success=False,
            error=result['error'],
            metadata={'final_issues': result['issues']}
        )

    # Save validated test
    save_test(output_path, result['test_content'])

    return AgentResult(
        success=True,
        data={'test_path': output_path},
        metadata={'attempts_used': result['attempts']}
    )
```

## Usage

### Basic Usage

```python
from agent_system.agents import ScribeAgent

scribe = ScribeAgent()

result = scribe.execute(
    task_description="Test user login with valid credentials",
    feature_name="Authentication",
    output_path="/tests/auth.spec.ts",
    complexity="easy"
)

if result.success:
    print(f"✓ Test generated: {result.data['test_path']}")
    print(f"  Attempts: {result.metadata['attempts_used']}")
else:
    print(f"✗ Generation failed: {result.error}")
    print(f"  Issues: {result.metadata['final_issues']}")
```

### Check Validation Stats

```python
scribe = ScribeAgent()

# Generate multiple tests...

stats = scribe.get_validation_stats()
print(f"Success rate: {stats['success_rate']:.1%}")
print(f"Avg retries: {stats['avg_retries_per_success']:.2f}")
```

## Benefits

### 1. Cost Reduction
- **Before:** Scribe → Critic → Gemini (rejection) → Retry
- **After:** Scribe validates internally → Only valid tests to Critic/Gemini
- **Savings:** 50%+ reduction in expensive Gemini calls

### 2. Faster Feedback
- **Before:** Wait for Critic review, then regenerate
- **After:** Immediate validation and retry within same session
- **Speed:** 2-3x faster iteration on failed generations

### 3. Higher Quality
- Tests validated against production criteria from the start
- Feedback loop ensures learning from mistakes
- Consistent quality standards across all generated tests

### 4. Transparency
- Detailed tracking of validation attempts
- Clear feedback on what issues were found
- Metrics on retry effectiveness

## Testing

Comprehensive test suite in `/tests/test_scribe_validation.py`:

```bash
# Run validation tests
pytest tests/test_scribe_validation.py -v

# Test categories:
# - TestScribeValidation: Individual validation checks
# - TestScribeRetryLogic: Retry mechanism
# - TestScribeCriticAlignment: Alignment with Critic agent
```

### Test Coverage

- ✅ Valid test passes validation
- ✅ Missing assertions detected
- ✅ Index-based selectors rejected
- ✅ Generated CSS classes rejected
- ✅ waitForTimeout rejected
- ✅ Hardcoded localhost rejected
- ✅ Missing screenshots detected
- ✅ Too many steps rejected
- ✅ Multiple issues detected simultaneously
- ✅ Retry logic attempts up to max retries
- ✅ Feedback incorporated into retries
- ✅ Anti-patterns aligned with Critic
- ✅ Limits aligned with Critic

## Configuration

Validation thresholds in `scribe.py`:

```python
MAX_RETRIES = 3           # Max retry attempts
MAX_STEPS = 10            # Max test steps
MAX_DURATION_MS = 60000   # Max estimated duration (60s)
```

Anti-patterns synced with `.claude/agents/critic.yaml`:

```yaml
rejection_criteria:
  selectors:
    - pattern: ".nth(\\d+)"
    - pattern: "\\.css-[a-z0-9]+"
  anti_patterns:
    - pattern: "waitForTimeout"
    - pattern: "hard-coded.*credential"
    - pattern: "localhost|127.0.0.1"
```

## Metrics

Expected validation performance:

| Metric | Target | Current |
|--------|--------|---------|
| First-attempt pass rate | 60-70% | 📊 Track in production |
| Retry success rate | 80-90% | 📊 Track in production |
| Max retries hit | <5% | 📊 Track in production |
| Critic rejection reduction | 50%+ | 📊 Measure vs baseline |

## Future Enhancements

1. **Learning from Failures:**
   - Store failed patterns in Vector DB
   - Use historical failures to improve prompts

2. **Dynamic Retry Limits:**
   - Adjust max retries based on complexity
   - Easy tests: 2 retries
   - Hard tests: 5 retries

3. **Severity-Based Validation:**
   - Critical issues: Hard fail (nth, no assertions)
   - Warnings: Soft fail (missing screenshots)
   - Allow override for warnings

4. **Cost-Aware Validation:**
   - Estimate validation cost vs retry cost
   - Skip validation for very simple tests

## Integration with Pipeline

```
Voice Input
    ↓
Kaya (Router)
    ↓
Scribe → [Self-Validate] → [Retry if needed] → Valid Test
    ↓
Critic (Optional verification)
    ↓
Runner
    ↓
Gemini (Final validation)
```

**Critic's New Role:**
- Verification spot-checks
- Catch edge cases Scribe missed
- Provide additional quality assurance

**Reduced Load:**
- Critic sees pre-validated tests
- Lower rejection rate (target: <10%)
- Focus on complex edge cases

## Conclusion

Self-validation in Scribe provides:
- **Faster iteration** through immediate feedback
- **Lower costs** by avoiding unnecessary validations
- **Higher quality** tests from the start
- **Transparent metrics** for continuous improvement

The retry mechanism with detailed feedback creates a learning loop that improves generation quality over time, while maintaining strict alignment with Critic criteria ensures consistency across the pipeline.
