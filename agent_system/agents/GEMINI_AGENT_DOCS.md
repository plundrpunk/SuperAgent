# Gemini Agent Documentation

## Overview

The Gemini Agent is the final validation arbiter in the SuperAgent multi-agent testing system. It validates Playwright tests by executing them in a real browser and capturing screenshots as visual proof of correctness.

## Architecture

### Core Responsibilities

1. **Browser Execution**: Launch Playwright browser and execute tests with 45-second timeout
2. **Screenshot Capture**: Collect screenshots at each test step as visual evidence
3. **Result Parsing**: Parse Playwright JSON output for test results, console errors, and network failures
4. **Validation**: Validate results against strict ValidationRubric schema
5. **Deterministic Pass/Fail**: Return clear pass/fail with detailed error messages

### Model & Tools

- **Model**: Gemini 2.5 Pro (future: for AI-powered screenshot analysis)
- **Tools**: Playwright browser automation via subprocess
- **Cost**: $0.00 (Playwright-only execution, no API calls currently)

## Implementation

### File Structure

```
agent_system/agents/
├── gemini.py                    # Main agent implementation
└── .claude/agents/gemini.yaml   # Configuration file
```

### Key Classes

#### GeminiAgent

```python
class GeminiAgent(BaseAgent):
    """
    Validates tests in real browser with visual proof.
    """

    def execute(self, test_path: str, timeout: Optional[int] = None) -> AgentResult:
        """Execute validation with browser."""

    def execute_async(self, test_path: str, timeout: Optional[int] = None) -> AgentResult:
        """Async version for concurrent validation."""
```

### Configuration (gemini.yaml)

```yaml
name: gemini
model: gemini-2.5-pro
tools: [validate]

contracts:
  browser:
    timeout_ms: 45000
    headless: true
    screenshot: "on"
    video: "retain-on-failure"
    trace: "retain-on-failure"

  validation:
    required_fields:
      - browser_launched
      - test_executed
      - test_passed
      - screenshots
      - console_errors
      - network_failures
      - execution_time_ms
```

## Usage

### Basic Execution

```python
from agent_system.agents import GeminiAgent

# Initialize agent
gemini = GeminiAgent()

# Validate test
result = gemini.execute('tests/checkout.spec.ts')

if result.success:
    print(f"Test passed! Screenshots: {result.data['screenshots']}")
else:
    print(f"Test failed: {result.error}")
```

### Async Execution

```python
import asyncio
from agent_system.agents import GeminiAgent

async def validate_tests():
    gemini = GeminiAgent()

    # Validate multiple tests concurrently
    results = await asyncio.gather(
        gemini.execute_async('tests/test1.spec.ts'),
        gemini.execute_async('tests/test2.spec.ts'),
        gemini.execute_async('tests/test3.spec.ts')
    )

    return results

results = asyncio.run(validate_tests())
```

### Integration with Router

```python
from agent_system.router import Router

router = Router()

# Route validation task
route = router.route_task({
    'type': 'validate',
    'path': 'tests/checkout.spec.ts'
})

# Execute with Gemini
gemini = GeminiAgent()
result = gemini.execute(route['path'])
```

## Validation Result Structure

### AgentResult Schema

```python
AgentResult(
    success: bool,                    # True if validation passed
    data: {
        'validation_result': {
            'browser_launched': bool,
            'test_executed': bool,
            'test_passed': bool,
            'screenshots': List[str],  # Absolute paths
            'console_errors': List[str],
            'network_failures': List[str],
            'execution_time_ms': int
        },
        'rubric_validation': {
            'passed': bool,
            'errors': List[str],
            'warnings': List[str]
        },
        'test_path': str,
        'screenshots': List[str],
        'artifacts_dir': str
    },
    error: Optional[str],             # Error message if failed
    execution_time_ms: int,
    cost_usd: float
)
```

### Validation Rubric

Tests must pass all criteria:

1. **browser_launched**: True
2. **test_executed**: True
3. **test_passed**: True
4. **screenshots**: At least 1 screenshot
5. **execution_time_ms**: <= 45000ms (45 seconds)

Tracked but not failing:
- **console_errors**: Logged as warnings
- **network_failures**: Logged as warnings

## Error Handling

### Common Errors

#### 1. Test File Not Found

```python
AgentResult(
    success=False,
    error="Test file not found: /path/to/test.spec.ts"
)
```

#### 2. Browser Launch Failure

```python
AgentResult(
    success=False,
    error="Validation error: Browser failed to launch"
)
```

#### 3. Test Timeout

```python
AgentResult(
    success=False,
    error="Browser validation timed out after 60s"
)
```

#### 4. No Screenshots

```python
AgentResult(
    success=False,
    error="Schema validation error: [] should be non-empty at screenshots"
)
```

#### 5. Test Execution Failure

```python
AgentResult(
    success=False,
    error="Test failed (test_passed=false)"
)
```

## Screenshot Collection

### Directory Locations

Gemini searches for screenshots in:

1. **Artifacts directory**: `artifacts/{test_name}/*.png`
2. **Test results**: `test-results/**/*{test_name}*/*.png`

### Chronological Ordering

Screenshots are sorted by modification time to ensure chronological order:

```python
screenshots.sort(key=lambda p: Path(p).stat().st_mtime)
```

### Screenshot Pattern

Tests should save screenshots as:

```typescript
await page.screenshot({
    path: 'artifacts/test_name/step_01.png',
    fullPage: true
});
```

## Playwright Integration

### Test Execution Command

```bash
npx playwright test <test_path> \
  --reporter=json \
  --timeout 45000
```

### JSON Report Parsing

Gemini parses Playwright's JSON output:

```python
{
    'suites': [{
        'specs': [{
            'tests': [{
                'results': [{
                    'status': 'passed',  # or 'failed', 'skipped'
                    'stdout': [...],
                    'stderr': [...],
                    'error': {...}
                }]
            }]
        }]
    }]
}
```

### Console Error Detection

Errors are extracted from stderr:

```python
if 'error' in log.lower():
    console_errors.append(log[:200])  # Truncate long errors
```

### Network Failure Detection

Network failures are detected by patterns:

```python
if 'net::' in message or 'ERR_' in message or 'timeout' in message.lower():
    network_failures.append(message[:200])
```

## Testing

### Test Coverage

18 comprehensive tests covering:

- Agent initialization
- Successful validation
- Failed test handling
- Missing test file
- Timeout handling
- Browser launch failure
- Screenshot collection
- Report parsing (pass/fail/errors/network)
- Rubric integration
- Cost tracking
- Agent statistics

### Running Tests

```bash
# Run all Gemini tests
pytest tests/test_gemini_agent.py -v

# Run with coverage
pytest tests/test_gemini_agent.py -v --cov=agent_system/agents/gemini

# Run specific test class
pytest tests/test_gemini_agent.py::TestGeminiAgentValidation -v
```

### Test Results

```
18 passed, 1 warning in 0.14s
Coverage: 92% (agent_system/agents/gemini.py)
```

## Performance

### Execution Times

- **Fast tests**: 1-5 seconds
- **Medium tests**: 5-15 seconds
- **Complex tests**: 15-45 seconds
- **Timeout**: 45 seconds (hard limit)

### Cost Analysis

- **Playwright execution**: $0.00 (infrastructure only)
- **Gemini API**: $0.00 (not used currently)
- **Target cost per test**: <$0.01

## Future Enhancements

### 1. AI Screenshot Analysis

Use Gemini 2.5 Pro to analyze screenshots for visual regressions:

```python
# Future implementation
def analyze_screenshots_with_ai(screenshots: List[str]) -> Dict:
    """Use Gemini Vision to detect UI issues."""
    pass
```

### 2. Visual Diff Detection

Compare screenshots against baseline:

```python
def compare_to_baseline(screenshot: str, baseline: str) -> float:
    """Return similarity score."""
    pass
```

### 3. Performance Profiling

Track performance metrics:

```python
{
    'page_load_time_ms': 1200,
    'interaction_time_ms': 300,
    'total_time_ms': 1500
}
```

### 4. Parallel Execution

Run multiple tests concurrently:

```python
async def validate_batch(test_paths: List[str]) -> List[AgentResult]:
    """Validate multiple tests in parallel."""
    pass
```

## Integration Points

### With Critic Agent

Critic pre-validates tests before Gemini:

```
Scribe → Critic → Gemini → Result
         ↓ reject
      Return to Scribe
```

### With Medic Agent

Medic fixes failures detected by Gemini:

```
Gemini → Fail → Medic → Fix → Re-validate with Gemini
```

### With Router

Router assigns validation tasks to Gemini:

```python
route = {
    'agent': 'gemini',
    'model': '2.5_pro',
    'max_cost': 0.50
}
```

## Best Practices

### 1. Test Quality

- Always include assertions (`expect()` calls)
- Use data-testid selectors
- Take screenshots at key steps
- Keep tests under 45 seconds

### 2. Screenshot Strategy

```typescript
// Good: Take screenshots at checkpoints
await page.screenshot({ path: 'artifacts/step_01_login.png' });
await page.screenshot({ path: 'artifacts/step_02_action.png' });

// Bad: Too many screenshots
for (let i = 0; i < 100; i++) {
    await page.screenshot({ path: `step_${i}.png` });
}
```

### 3. Error Handling

Always handle errors gracefully:

```python
try:
    result = gemini.execute(test_path)
except Exception as e:
    logger.error(f"Validation failed: {e}")
    # Escalate to HITL
```

### 4. Cost Management

Monitor validation costs:

```python
stats = gemini.get_stats()
if stats['total_cost_usd'] > budget:
    alert_team()
```

## Troubleshooting

### Problem: Browser Fails to Launch

**Solution**: Ensure Playwright is installed:

```bash
npx playwright install chromium
```

### Problem: No Screenshots Captured

**Solution**: Check artifacts directory exists and test writes screenshots:

```bash
mkdir -p artifacts
```

### Problem: Validation Timeout

**Solution**: Reduce test complexity or increase timeout:

```python
result = gemini.execute(test_path, timeout=90)
```

### Problem: JSON Parse Error

**Solution**: Check Playwright version and JSON reporter:

```bash
npx playwright --version
npx playwright test --reporter=json
```

## References

- [Validation Output Format](GEMINI_VALIDATION_OUTPUT.md) - **Comprehensive output documentation**
- [Playwright Documentation](https://playwright.dev)
- [ValidationRubric Source](../validation_rubric.py)
- [BaseAgent Source](base_agent.py)
- [Gemini Config](../../.claude/agents/gemini.yaml)
- [Test Suite](../../tests/test_gemini_agent.py)

## Support

For issues or questions:
1. Check [Validation Output Format](GEMINI_VALIDATION_OUTPUT.md) for result structure
2. Check test suite for examples
3. Review ValidationRubric schema
4. Verify Playwright installation
5. Check agent logs in `logs/gemini.log`
