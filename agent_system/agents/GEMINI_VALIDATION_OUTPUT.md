# Gemini Agent Validation Output Documentation

## Overview

This document provides comprehensive documentation of the Gemini agent's validation output format, including all fields, data types, and expected values.

## Validation Result Structure

The Gemini agent returns an `AgentResult` object with structured validation data that includes both raw test execution results and rubric validation results.

### AgentResult Schema

```python
AgentResult(
    success: bool,
    data: Dict[str, Any],
    error: Optional[str],
    execution_time_ms: int,
    cost_usd: float,
    metadata: Dict[str, Any]
)
```

## Complete Output Format

### Successful Validation Example

```python
AgentResult(
    success=True,
    data={
        'validation_result': {
            'browser_launched': True,
            'test_executed': True,
            'test_passed': True,
            'screenshots': [
                '/absolute/path/to/artifacts/test_name/step_01.png',
                '/absolute/path/to/artifacts/test_name/step_02.png',
                '/absolute/path/to/artifacts/test_name/step_03.png'
            ],
            'console_errors': [],
            'network_failures': [],
            'execution_time_ms': 2340
        },
        'rubric_validation': {
            'passed': True,
            'errors': [],
            'warnings': []
        },
        'test_path': '/absolute/path/to/tests/feature.spec.ts',
        'screenshots': [
            '/absolute/path/to/artifacts/test_name/step_01.png',
            '/absolute/path/to/artifacts/test_name/step_02.png',
            '/absolute/path/to/artifacts/test_name/step_03.png'
        ],
        'artifacts_dir': 'artifacts/feature'
    },
    error=None,
    execution_time_ms=2500,
    cost_usd=0.0
)
```

### Failed Validation Example

```python
AgentResult(
    success=False,
    data={
        'validation_result': {
            'browser_launched': True,
            'test_executed': True,
            'test_passed': False,
            'screenshots': [
                '/absolute/path/to/artifacts/test_name/step_01.png'
            ],
            'console_errors': [
                'Error: Expected element not found'
            ],
            'network_failures': [
                'net::ERR_CONNECTION_REFUSED at https://api.example.com'
            ],
            'execution_time_ms': 15420
        },
        'rubric_validation': {
            'passed': False,
            'errors': [
                'Test failed (test_passed=false)'
            ],
            'warnings': [
                'Console errors detected: 1 errors',
                'Network failures detected: 1 failures'
            ]
        },
        'test_path': '/absolute/path/to/tests/feature.spec.ts',
        'screenshots': [
            '/absolute/path/to/artifacts/test_name/step_01.png'
        ],
        'artifacts_dir': 'artifacts/feature'
    },
    error='Test failed (test_passed=false)',
    execution_time_ms=15600,
    cost_usd=0.0
)
```

## Field Definitions

### Top-Level Fields

#### `success` (boolean)
- **Description**: Overall validation success status
- **Values**:
  - `True`: Test passed validation rubric
  - `False`: Test failed validation rubric
- **Determined by**: Rubric validation result (all criteria must pass)

#### `data` (dict)
- **Description**: Structured validation data
- **Contains**:
  - `validation_result`: Raw test execution data
  - `rubric_validation`: Rubric validation results
  - `test_path`: Absolute path to test file
  - `screenshots`: List of screenshot paths
  - `artifacts_dir`: Directory containing artifacts

#### `error` (string | null)
- **Description**: Error message if validation failed
- **Values**:
  - `None`: Validation passed
  - String: Concatenated rubric errors (joined with `; `)
- **Examples**:
  - `"Test failed (test_passed=false)"`
  - `"No screenshots captured (minimum 1 required)"`
  - `"Schema validation error: [] should be non-empty at screenshots"`

#### `execution_time_ms` (integer)
- **Description**: Total execution time including browser startup
- **Range**: 0 to infinity
- **Includes**:
  - Browser launch time
  - Test execution time
  - Screenshot collection time
  - Validation time

#### `cost_usd` (float)
- **Description**: Cost of validation (currently $0.00 for Playwright-only)
- **Value**: `0.0` (no API costs currently)
- **Future**: Will include Gemini API costs for AI screenshot analysis

### Validation Result Fields

#### `validation_result.browser_launched` (boolean)
- **Description**: Whether Playwright browser successfully launched
- **Required**: Yes (rubric requires `true`)
- **Values**:
  - `True`: Browser launched successfully
  - `False`: Browser failed to launch
- **Failure causes**:
  - Playwright not installed
  - Browser binary missing
  - System resource constraints
  - Permissions issues

#### `validation_result.test_executed` (boolean)
- **Description**: Whether test file was executed
- **Required**: Yes (rubric requires `true`)
- **Values**:
  - `True`: Test executed (regardless of pass/fail)
  - `False`: Test did not execute
- **Failure causes**:
  - Syntax errors in test file
  - Missing imports/dependencies
  - Test file not found

#### `validation_result.test_passed` (boolean)
- **Description**: Whether all tests in file passed
- **Required**: Yes (rubric requires `true`)
- **Values**:
  - `True`: All tests passed
  - `False`: One or more tests failed
- **Determined by**: Playwright test status (`passed` or `skipped`)

#### `validation_result.screenshots` (array of strings)
- **Description**: Absolute paths to captured screenshots
- **Required**: Yes (rubric requires `minItems: 1`)
- **Format**: Array of absolute file paths
- **Ordering**: Chronological (sorted by modification time)
- **Locations searched**:
  1. `artifacts/{test_name}/**/*.png`
  2. `test-results/**/*{test_name}*/*.png`
- **Example**:
  ```python
  [
      '/Users/user/project/artifacts/checkout/step_01_cart.png',
      '/Users/user/project/artifacts/checkout/step_02_payment.png',
      '/Users/user/project/artifacts/checkout/step_03_confirm.png'
  ]
  ```

#### `validation_result.console_errors` (array of strings)
- **Description**: Console errors detected during test execution
- **Required**: Yes (empty array allowed)
- **Format**: Array of error message strings
- **Max length**: 200 characters per message (truncated)
- **Detection**: stderr logs containing "error" (case-insensitive)
- **Status**: Tracked but not failing (warnings only)
- **Example**:
  ```python
  [
      'Error: Failed to fetch user data',
      'Warning: Component is deprecated'
  ]
  ```

#### `validation_result.network_failures` (array of strings)
- **Description**: Network failures detected during test execution
- **Required**: Yes (empty array allowed)
- **Format**: Array of failure message strings
- **Max length**: 200 characters per message (truncated)
- **Detection**: Error messages containing:
  - `net::` (Chrome network errors)
  - `ERR_` (Error codes)
  - `timeout` (case-insensitive)
- **Status**: Tracked but not failing (warnings only)
- **Example**:
  ```python
  [
      'net::ERR_CONNECTION_REFUSED at https://api.example.com',
      'Request timeout after 30000ms'
  ]
  ```

#### `validation_result.execution_time_ms` (integer)
- **Description**: Test execution time (excluding browser startup)
- **Required**: Yes (rubric requires `≤ 45000`)
- **Range**: 0 to 45000 (capped at max_test_duration_ms)
- **Unit**: Milliseconds
- **Measured from**: Test start to test completion
- **Capped at**: 45000ms (45 seconds hard limit)

### Rubric Validation Fields

#### `rubric_validation.passed` (boolean)
- **Description**: Whether validation passed all rubric criteria
- **Values**:
  - `True`: All criteria passed
  - `False`: One or more criteria failed
- **Criteria**:
  1. browser_launched = true
  2. test_executed = true
  3. test_passed = true
  4. screenshots.length ≥ 1
  5. execution_time_ms ≤ 45000

#### `rubric_validation.errors` (array of strings)
- **Description**: Validation errors (cause failure)
- **Format**: Array of error message strings
- **Values**: Empty array if all criteria passed
- **Example**:
  ```python
  [
      'Test failed (test_passed=false)',
      'No screenshots captured (minimum 1 required)',
      'Execution time 50000ms exceeds 45000ms limit'
  ]
  ```

#### `rubric_validation.warnings` (array of strings)
- **Description**: Validation warnings (do not cause failure)
- **Format**: Array of warning message strings
- **Values**: Empty array if no warnings
- **Example**:
  ```python
  [
      'Console errors detected: 3 errors',
      'Network failures detected: 1 failures'
  ]
  ```

## Error Scenarios

### 1. Test File Not Found

```python
AgentResult(
    success=False,
    data={},
    error='Test file not found: /path/to/nonexistent.spec.ts',
    execution_time_ms=5,
    cost_usd=0.0
)
```

### 2. Browser Launch Failure

```python
AgentResult(
    success=False,
    data={
        'validation_result': {
            'browser_launched': False,
            'test_executed': False,
            'test_passed': False,
            'screenshots': [],
            'console_errors': ['Browser error: Browser failed to launch'],
            'network_failures': [],
            'execution_time_ms': 100
        },
        'rubric_validation': {
            'passed': False,
            'errors': [
                'Browser failed to launch',
                'Test did not execute',
                'Test failed (test_passed=false)',
                'Schema validation error: [] should be non-empty at screenshots'
            ],
            'warnings': []
        },
        'test_path': '/path/to/test.spec.ts',
        'screenshots': [],
        'artifacts_dir': 'artifacts/test'
    },
    error='Browser failed to launch; Test did not execute; Test failed (test_passed=false); Schema validation error: [] should be non-empty at screenshots',
    execution_time_ms=150,
    cost_usd=0.0
)
```

### 3. Test Timeout

```python
AgentResult(
    success=False,
    data={
        'validation_result': {
            'browser_launched': True,
            'test_executed': True,
            'test_passed': False,
            'screenshots': ['/path/to/partial_screenshot.png'],
            'console_errors': ['Test execution timed out'],
            'network_failures': [],
            'execution_time_ms': 60000
        },
        'rubric_validation': {
            'passed': False,
            'errors': [
                'Test failed (test_passed=false)',
                'Execution time 60000ms exceeds 45000ms limit'
            ],
            'warnings': ['Console errors detected: 1 errors']
        },
        'test_path': '/path/to/test.spec.ts',
        'screenshots': ['/path/to/partial_screenshot.png'],
        'artifacts_dir': 'artifacts/test'
    },
    error='Test failed (test_passed=false); Execution time 60000ms exceeds 45000ms limit',
    execution_time_ms=60200,
    cost_usd=0.0
)
```

### 4. No Screenshots Captured

```python
AgentResult(
    success=False,
    data={
        'validation_result': {
            'browser_launched': True,
            'test_executed': True,
            'test_passed': True,
            'screenshots': [],
            'console_errors': [],
            'network_failures': [],
            'execution_time_ms': 1200
        },
        'rubric_validation': {
            'passed': False,
            'errors': [
                'Schema validation error: [] should be non-empty at screenshots'
            ],
            'warnings': []
        },
        'test_path': '/path/to/test.spec.ts',
        'screenshots': [],
        'artifacts_dir': 'artifacts/test'
    },
    error='Schema validation error: [] should be non-empty at screenshots',
    execution_time_ms=1300,
    cost_usd=0.0
)
```

## Integration Examples

### Using in Closed-Loop Testing

```python
from agent_system.agents import GeminiAgent

# Initialize agent
gemini = GeminiAgent()

# Validate test
result = gemini.execute('tests/checkout.spec.ts')

if result.success:
    # Test passed - continue to next step
    print(f"✓ Test passed in {result.execution_time_ms}ms")
    print(f"  Screenshots: {len(result.data['screenshots'])}")
else:
    # Test failed - route to Medic for fixes
    print(f"✗ Test failed: {result.error}")

    # Check failure details
    validation = result.data['rubric_validation']

    if 'test_passed=false' in result.error:
        # Test logic failed - needs Medic
        route_to_medic(result)
    elif 'No screenshots' in result.error:
        # Missing screenshots - update test to add screenshots
        route_to_scribe(result)
    elif 'Execution time' in result.error:
        # Timeout - optimize test or break into smaller tests
        route_to_critic(result)
```

### Parsing Validation Results

```python
def analyze_validation_result(result: AgentResult) -> Dict[str, Any]:
    """Analyze validation result and extract key metrics."""

    validation = result.data.get('validation_result', {})
    rubric = result.data.get('rubric_validation', {})

    return {
        'passed': result.success,
        'test_status': {
            'browser_launched': validation.get('browser_launched'),
            'test_executed': validation.get('test_executed'),
            'test_passed': validation.get('test_passed')
        },
        'screenshots_count': len(validation.get('screenshots', [])),
        'execution_time_ms': validation.get('execution_time_ms'),
        'has_console_errors': len(validation.get('console_errors', [])) > 0,
        'has_network_failures': len(validation.get('network_failures', [])) > 0,
        'rubric_errors': rubric.get('errors', []),
        'rubric_warnings': rubric.get('warnings', []),
        'cost_usd': result.cost_usd
    }
```

## Best Practices

### 1. Always Check Success Flag First

```python
result = gemini.execute(test_path)

if not result.success:
    # Handle failure - check error field for details
    print(f"Validation failed: {result.error}")
    return
```

### 2. Extract Screenshots for Evidence

```python
if result.success:
    screenshots = result.data['screenshots']

    # Archive screenshots for audit trail
    for screenshot in screenshots:
        archive_screenshot(screenshot)
```

### 3. Monitor Console Errors and Network Failures

```python
validation = result.data['validation_result']

if validation['console_errors']:
    logger.warning(f"Console errors: {validation['console_errors']}")

if validation['network_failures']:
    logger.warning(f"Network failures: {validation['network_failures']}")
```

### 4. Track Execution Time for Performance

```python
execution_time = result.data['validation_result']['execution_time_ms']

if execution_time > 30000:
    logger.warning(f"Slow test: {execution_time}ms (consider optimization)")
```

## References

- [Gemini Agent Documentation](GEMINI_AGENT_DOCS.md)
- [Validation Rubric](../validation_rubric.py)
- [Test Suite](../../tests/test_gemini_agent.py)
- [BaseAgent](base_agent.py)
