# Gemini Agent Quick Start

## 5-Minute Setup

### Step 1: Install Dependencies

```bash
cd /Users/rutledge/Documents/DevFolder/SuperAgent
pip install -r requirements.txt
```

This installs:
- `google-genai==0.3.0` (Gemini API)
- `playwright==1.40.0` (Browser automation)

### Step 2: Get Gemini API Key

1. Visit: https://aistudio.google.com/apikey
2. Click "Create API Key"
3. Copy the key

### Step 3: Set Environment Variable

```bash
export GEMINI_API_KEY="your-api-key-here"
```

Or add to `.env`:
```bash
echo "GEMINI_API_KEY=your-api-key-here" >> .env
```

### Step 4: Enable in Config (Optional)

By default, Gemini API is **disabled** (Playwright-only validation).

To enable AI analysis:

```yaml
# .claude/agents/gemini.yaml
contracts:
  gemini_api:
    enabled: true  # Change from false
```

### Step 5: Test It

```bash
# Run Gemini agent tests
pytest tests/test_gemini_agent.py -v
```

## Usage Examples

### Example 1: Basic Validation (Free - Playwright Only)

```python
from agent_system.agents.gemini import GeminiAgent

gemini = GeminiAgent()
result = gemini.execute(test_path="tests/login.spec.ts")

print(f"Passed: {result.success}")
print(f"Screenshots: {len(result.data['screenshots'])}")
print(f"Cost: ${result.cost_usd}")  # $0.00
```

### Example 2: With AI Analysis (~$0.0075)

```python
gemini = GeminiAgent()
result = gemini.execute(
    test_path="tests/checkout.spec.ts",
    enable_ai_analysis=True  # Costs ~$0.0075
)

# Check AI analysis
if result.data.get('ai_analysis'):
    analysis = result.data['ai_analysis']
    print(f"UI Correctness: {analysis['ui_correctness']}")
    print(f"Confidence: {analysis['confidence_score']}%")
    print(f"Cost: ${result.cost_usd}")
```

### Example 3: Via Kaya Orchestrator

```python
from agent_system.agents.kaya import KayaAgent

kaya = KayaAgent()

# Voice command
result = kaya.execute("validate tests/payment.spec.ts")
```

## Quick Reference

| Command | Description | Cost |
|---------|-------------|------|
| `gemini.execute(test_path)` | Playwright-only validation | $0 |
| `gemini.execute(test_path, enable_ai_analysis=True)` | With Gemini API | ~$0.0075 |
| `kaya.execute("validate path")` | Via orchestrator | $0 |

## Validation Output

```python
AgentResult(
    success=True,
    data={
        'validation_result': {
            'browser_launched': True,
            'test_executed': True,
            'test_passed': True,
            'screenshots': ['step_01.png', 'step_02.png'],
            'execution_time_ms': 38500,
            'console_errors': [],
            'network_failures': []
        },
        'rubric_validation': {
            'passed': True,
            'errors': [],
            'warnings': []
        },
        'ai_analysis': {  # Only if enable_ai_analysis=True
            'ui_correctness': 'pass',
            'confidence_score': 92,
            'findings': '...',
            'cost_usd': 0.0075
        }
    },
    cost_usd=0.0075,
    execution_time_ms=42000
)
```

## When to Use AI Analysis

✅ **Use for**:
- Authentication flows
- Payment/checkout
- Critical user journeys
- Visual regression testing

❌ **Skip for**:
- Unit tests
- API tests
- Smoke tests
- CI/CD (too expensive)

## Troubleshooting

### Issue: `gemini_enabled: false`

**Solution**: Set `GEMINI_API_KEY` environment variable

```bash
export GEMINI_API_KEY="your-key"
```

### Issue: `ImportError: google.genai`

**Solution**: Install package

```bash
pip install google-genai==0.3.0
```

### Issue: Rate limit exceeded

**Wait**: Gemini 2.5 Pro has 10 requests/minute limit

The agent automatically handles rate limiting with `@limit_gemini` decorator.

## Cost Calculator

```python
# Estimate monthly costs
tests_per_day = 50
ai_analysis_enabled = 10  # 10 out of 50 use AI

monthly_cost = (ai_analysis_enabled * 30 * 0.0075)
# = $2.25/month for 10 AI validations per day
```

## Next Steps

1. **Read full docs**: `GEMINI_AGENT_IMPLEMENTATION.md`
2. **Run integration tests**: `pytest tests/integration/test_gemini_validation_flow.py`
3. **Configure router policy**: `.claude/router_policy.yaml`
4. **Set budget limits**: Control costs via RouterPolicy

## Files

- **Config**: `.claude/agents/gemini.yaml`
- **Implementation**: `agent_system/agents/gemini.py`
- **Tests**: `tests/test_gemini_agent.py`
- **Full Docs**: `agent_system/agents/GEMINI_AGENT_IMPLEMENTATION.md`
