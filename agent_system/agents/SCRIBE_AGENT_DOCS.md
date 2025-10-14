# Scribe Agent Documentation

## Overview

**Scribe** is the test generation agent in the SuperAgent system. It creates Playwright tests from natural language descriptions using Claude Haiku (for easy tests) or Claude Sonnet 4.5 (for hard tests).

## File Location

- **Production Implementation**: `/agent_system/agents/scribe_full.py`
- **RAG Version** (with vector DB integration): `/agent_system/agents/scribe.py`
- **Configuration**: `/.claude/agents/scribe.yaml`
- **Tests**: `/tests/test_scribe_full.py`

## Key Features

### 1. **AI-Powered Test Generation**
- Uses Anthropic Claude API for intelligent test generation
- Generates complete, production-ready Playwright tests
- Follows VisionFlow patterns and best practices

### 2. **Complexity-Based Model Selection**
- **Easy tests** (complexity score < 5): Claude Haiku
  - Input: $0.80 per 1M tokens
  - Output: $4.00 per 1M tokens
  - Use cases: Simple interactions, basic navigation

- **Hard tests** (complexity score ≥ 5): Claude Sonnet 4.5
  - Input: $3.00 per 1M tokens
  - Output: $15.00 per 1M tokens
  - Use cases: Auth flows, payments, file operations, WebSockets

### 3. **Template-Based Generation**
- Loads from `tests/templates/playwright.template.ts`
- Ensures consistent test structure
- Enforces data-testid selector pattern

### 4. **Self-Validation with Retry**
- Validates generated tests against Critic criteria
- Auto-retries up to 3 times with feedback
- Provides detailed validation results

### 5. **Cost Tracking**
- Tracks token usage per generation
- Calculates costs in real-time
- Reports total cost in AgentResult

## Usage

### Basic Usage

```python
from agent_system.agents.scribe_full import ScribeAgent

scribe = ScribeAgent()

result = scribe.execute(
    task_description="user login flow",
    task_scope="authenticate with email and password",
    complexity="easy"  # Optional, auto-detected if not provided
)

if result.success:
    print(f"Test written to: {result.data['test_path']}")
    print(f"Cost: ${result.cost_usd:.4f}")
    print(f"Model: {result.data['model_used']}")
else:
    print(f"Error: {result.error}")
```

### CLI Usage

```bash
python agent_system/agents/scribe_full.py "user login flow" "authentication" "easy"
```

Output:
```
[Scribe] Task complexity: easy → Using model: claude-haiku-4-20250612
[Scribe] Generating test for: user login flow
[Scribe] Generation attempt 1/3
[Scribe] ✓ Validation passed on attempt 1
[Scribe] Test written to: /path/to/tests/user_login_flow.spec.ts

============================================================
Scribe Result: SUCCESS
============================================================
Cost: $0.0024
Time: 1250ms

Test Path: /path/to/tests/user_login_flow.spec.ts
Model Used: claude-haiku-4-20250612
Complexity: easy
Retries Used: 0

Validation:
  - Assertions: 2
  - Screenshots: 2
  - Uses data-testid: True
  - Syntax valid: True
============================================================
```

## Architecture

### Execution Flow

```
1. Execute(task_description, task_scope, complexity)
   ↓
2. Determine Complexity (if not provided)
   - Use ComplexityEstimator
   - Select Haiku or Sonnet
   ↓
3. Load Template
   - Read playwright.template.ts
   ↓
4. Generate with Retry Loop (max 3 attempts)
   ┌──────────────────────────────────────┐
   │ 4a. Generate Test via Claude API     │
   │ 4b. Validate Test                    │
   │ 4c. If valid → Success               │
   │ 4d. If invalid → Add feedback, retry │
   └──────────────────────────────────────┘
   ↓
5. Write Test File
   - Auto-generate path if not provided
   - Save to tests/ directory
   ↓
6. Return AgentResult
   - success, data, cost_usd, execution_time_ms
```

### Validation Checks

Generated tests must pass ALL checks:

1. **Assertions**: At least 1 `expect()` call
2. **Selectors**: Uses `data-testid` attributes
3. **Screenshots**: At least 1 screenshot capture
4. **Anti-Patterns**: None of the following:
   - `.nth()` (index-based selectors)
   - `.css-*` (generated CSS classes)
   - `waitForTimeout` (use `waitForSelector`)
   - Hard-coded credentials
   - Hard-coded URLs (use `process.env.BASE_URL`)
5. **Syntax**: Balanced braces, parentheses, brackets
6. **Structure**: Has `test.describe()` and `test()` calls

## API Reference

### ScribeAgent Class

#### `__init__()`
Initialize Scribe agent with Anthropic client and complexity estimator.

**Raises:**
- `ValueError`: If `ANTHROPIC_API_KEY` not found in environment

#### `execute(task_description, task_scope="", complexity=None, output_path=None)`
Generate a Playwright test from description.

**Args:**
- `task_description` (str): Description of the feature to test
- `task_scope` (str, optional): Additional context or scope
- `complexity` (str, optional): "easy" or "hard" (auto-detected if not provided)
- `output_path` (str, optional): Custom output path (auto-generated if not provided)

**Returns:**
- `AgentResult` with:
  ```python
  {
    'success': bool,
    'data': {
      'test_content': str,      # Generated TypeScript code
      'test_path': str,          # Absolute path to test file
      'template_used': str,      # Template path
      'model_used': str,         # Model ID used
      'complexity': str,         # Detected or provided complexity
      'validation': {            # Validation results
        'valid': bool,
        'issues': list,
        'checks': dict
      },
      'retries_used': int       # Number of retries needed
    },
    'cost_usd': float,          # Total API cost
    'execution_time_ms': int    # Execution time
  }
  ```

## Prompt Engineering

The generation prompt includes:

1. **Role Definition**: "You are Scribe, an expert Playwright test writer"
2. **Task Context**: Description and scope
3. **Template Reference**: Full template content
4. **Requirements** (9 sections):
   - Selector patterns
   - Test structure
   - Screenshot requirements
   - Assertion requirements
   - Wait patterns
   - Configuration
   - Anti-patterns to avoid
   - Feature naming
   - Comments
5. **Output Format**: TypeScript code block

### Retry Feedback

On validation failure, the prompt is enhanced with:

```
PREVIOUS ATTEMPT FAILED - FIX THESE ISSUES:
- Issue 1
- Issue 2

CRITICAL REQUIREMENTS:
- Use ONLY data-testid selectors with S() helper
- Include expect() assertions (minimum 2)
- NO .nth() selectors
- NO .css-* classes
- NO waitForTimeout (use waitForSelector)
- Use process.env.BASE_URL for navigation
- Add screenshots after major steps
```

## Configuration

### Environment Variables

Required:
```bash
ANTHROPIC_API_KEY=sk-ant-...
```

### Agent Config (`.claude/agents/scribe.yaml`)

```yaml
name: scribe
role: Test Writer
model: claude-haiku  # For easy tests
complex_model: claude-sonnet-4.5  # For hard tests
tools:
  - read
  - write
  - edit
  - grep
  - glob

success_criteria:
  - Code compiles without errors
  - Uses data-testid selectors exclusively
  - Clear, descriptive assertions with expect()
  - Edge cases covered (happy path + error cases)
  - Screenshots after major steps
  - No flaky patterns (nth(), CSS classes, waitForTimeout)
```

## Testing

### Run Unit Tests

```bash
pytest tests/test_scribe_full.py -v
```

### Test Coverage

- ✅ Initialization
- ✅ Template loading
- ✅ Output path generation
- ✅ Test validation (valid tests)
- ✅ Test validation (anti-patterns)
- ✅ Test validation (missing assertions)
- ✅ TypeScript syntax checking
- ✅ AI generation (mocked)
- ✅ End-to-end execution
- ✅ Complexity-based model selection

## Performance Benchmarks

### Cost per Test

| Complexity | Model | Avg Tokens | Avg Cost | Time |
|-----------|-------|-----------|----------|------|
| Easy | Haiku | 800 (in) + 500 (out) | $0.002-0.003 | 1-2s |
| Hard | Sonnet | 1200 (in) + 800 (out) | $0.015-0.020 | 2-4s |

### Retry Statistics

Based on initial testing:
- **First attempt success**: ~85%
- **Success after 1 retry**: ~95%
- **Success after 2 retries**: ~98%
- **Failure after 3 retries**: ~2%

## Error Handling

### Common Errors

1. **Missing API Key**
   ```
   ValueError: ANTHROPIC_API_KEY not found in environment
   ```
   **Solution**: Add to `.env` file

2. **Template Not Found**
   ```
   Error: Could not load template from tests/templates/playwright.template.ts
   ```
   **Solution**: Ensure template file exists

3. **Validation Failure**
   ```
   Generated test failed validation after 3 attempts
   ```
   **Solution**: Review task description, may be too complex or ambiguous

4. **API Rate Limit**
   ```
   AI generation failed: rate_limit_error
   ```
   **Solution**: Implement exponential backoff or reduce request rate

## Integration with Other Agents

### Kaya (Router)
```python
# Kaya routes to Scribe
routing_decision = router.route(
    task_type='write_test',
    task_description='user login',
    task_scope='authentication'
)

# Execute Scribe
scribe = ScribeAgent()
result = scribe.execute(
    task_description=routing_decision.task_description,
    task_scope=routing_decision.task_scope,
    complexity=routing_decision.complexity
)
```

### Critic (Pre-Validation)
```python
# After Scribe generates test
critic = CriticAgent()
critic_result = critic.execute(test_path=scribe_result.data['test_path'])

if critic_result.data['status'] == 'rejected':
    # Send back to Scribe with feedback
    ...
```

### Runner (Execution)
```python
# After Scribe writes test
runner = RunnerAgent()
runner_result = runner.execute(test_path=scribe_result.data['test_path'])

if not runner_result.success:
    # Send to Medic for fixing
    ...
```

## Roadmap

### Phase 1 (Current)
- ✅ Basic AI generation with Claude API
- ✅ Template-based generation
- ✅ Validation with retry
- ✅ Cost tracking

### Phase 2 (Planned)
- [ ] RAG integration (use vector DB for similar test patterns)
- [ ] Learning from successful tests
- [ ] Improved prompt engineering based on feedback
- [ ] Support for multiple template types

### Phase 3 (Future)
- [ ] Multi-model support (GPT-4, Gemini)
- [ ] Custom selector strategies
- [ ] Visual regression test generation
- [ ] API test generation (REST, GraphQL)

## Contributing

When modifying Scribe:

1. **Test First**: Add tests before changing logic
2. **Cost Awareness**: Monitor token usage and costs
3. **Validation**: Ensure all validation checks pass
4. **Documentation**: Update this file with changes

## Support

For issues or questions:
- File GitHub issue
- Check logs in `[Scribe]` prefix
- Review validation failures in result.data
