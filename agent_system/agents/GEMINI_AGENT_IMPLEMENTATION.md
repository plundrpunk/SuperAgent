# Gemini Agent Implementation Guide

## Overview

The Gemini Agent is SuperAgent's **final validator** that provides visual proof of test correctness through a two-phase validation approach:

1. **Phase 1 (Always)**: Browser execution with Playwright
2. **Phase 2 (Optional)**: AI-powered screenshot analysis with Gemini 2.5 Pro

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Gemini Agent                            │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Phase 1: Browser Execution (Playwright)                     │
│  ┌────────────────────────────────────────────┐             │
│  │ 1. Launch browser (headless)                │             │
│  │ 2. Execute test (45s timeout)               │             │
│  │ 3. Capture screenshots                      │             │
│  │ 4. Parse test results                       │             │
│  │ 5. Validate against rubric                  │             │
│  └────────────────────────────────────────────┘             │
│                        │                                      │
│                        ▼                                      │
│  Phase 2: AI Analysis (Gemini 2.5 Pro - Optional)           │
│  ┌────────────────────────────────────────────┐             │
│  │ 1. Send screenshots to Gemini API           │             │
│  │ 2. Analyze UI correctness                   │             │
│  │ 3. Detect visual regressions                │             │
│  │ 4. Generate confidence scores               │             │
│  │ 5. Track API costs                          │             │
│  └────────────────────────────────────────────┘             │
│                        │                                      │
│                        ▼                                      │
│              Return ValidationResult                         │
└─────────────────────────────────────────────────────────────┘
```

## Files

- **Config**: `/Users/rutledge/Documents/DevFolder/SuperAgent/.claude/agents/gemini.yaml`
- **Implementation**: `/Users/rutledge/Documents/DevFolder/SuperAgent/agent_system/agents/gemini.py`
- **Tests**: `/Users/rutledge/Documents/DevFolder/SuperAgent/tests/test_gemini_agent.py`

## Configuration

### gemini.yaml Key Settings

```yaml
model: gemini-2.5-pro
fallback_model: gemini-2.5-flash
tools: [playwright, gemini_api]

contracts:
  browser:
    timeout_ms: 45000
    headless: true
    screenshot: "on"

  gemini_api:
    model: gemini-2.5-pro
    enabled: false  # Enable by setting GEMINI_API_KEY
    temperature: 0.1

cost_estimate:
  estimated_cost_per_validation: 0.0075  # ~$0.0075 with Gemini API
```

## Usage

### Basic Usage (Playwright Only)

```python
from agent_system.agents.gemini import GeminiAgent

gemini = GeminiAgent()

# Execute validation (Playwright only, $0 API cost)
result = gemini.execute(test_path="tests/checkout.spec.ts")

print(f"Success: {result.success}")
print(f"Screenshots: {result.data['screenshots']}")
print(f"Cost: ${result.cost_usd}")
```

### With AI Analysis (Gemini API)

```python
# Enable AI analysis for critical paths
result = gemini.execute(
    test_path="tests/payment.spec.ts",
    enable_ai_analysis=True  # Costs ~$0.0075
)

# Check AI analysis results
if result.data.get('ai_analysis'):
    analysis = result.data['ai_analysis']
    print(f"UI Correctness: {analysis.get('ui_correctness')}")
    print(f"Confidence: {analysis.get('confidence_score')}%")
    print(f"Findings: {analysis.get('findings')}")
```

### Via Kaya Orchestrator

```python
from agent_system.agents.kaya import KayaAgent

kaya = KayaAgent()

# Standard validation (Playwright only)
result = kaya.execute("validate tests/login.spec.ts")

# Critical path validation (with Gemini analysis)
result = kaya.execute("validate tests/checkout.spec.ts - critical")
```

## Validation Rubric

All tests must pass these criteria:

```python
{
  "browser_launched": true,
  "test_executed": true,
  "test_passed": true,
  "screenshots": ["path1.png", "path2.png"],  # Min 1 required
  "execution_time_ms": 38500,  # Max 45000ms
  "console_errors": [],  # Tracked but allowed
  "network_failures": []  # Tracked but allowed
}
```

## Gemini API Integration

### Setup

1. Get API key from [Google AI Studio](https://aistudio.google.com/apikey)

2. Set environment variable:
```bash
export GEMINI_API_KEY="your-api-key-here"
```

3. Enable in config:
```yaml
# .claude/agents/gemini.yaml
contracts:
  gemini_api:
    enabled: true  # Change from false to true
```

4. Install dependencies:
```bash
pip install google-genai==0.3.0
```

### What Gemini Analyzes

When `enable_ai_analysis=True`, Gemini 2.5 Pro:

1. **UI Correctness**: Verifies all expected elements are visible and properly rendered
2. **Visual Regressions**: Detects layout issues, misalignment, broken components
3. **Test Coverage**: Assesses if screenshots show meaningful test steps
4. **Confidence Score**: 0-100% confidence rating on test correctness

### API Response Format

```json
{
  "ui_correctness": "pass",
  "visual_regressions": [],
  "confidence_score": 92,
  "findings": "All UI elements properly rendered. No visual regressions detected.",
  "screenshot_analysis": [
    "Screenshot 1: Login page - all elements visible",
    "Screenshot 2: Dashboard - layout correct",
    "Screenshot 3: Profile page - data displayed correctly"
  ],
  "cost_usd": 0.00625,
  "screenshots_analyzed": 3,
  "model": "gemini-2.5-pro"
}
```

## Cost Management

### Cost Breakdown

| Component | Cost per Validation | When Used |
|-----------|-------------------|-----------|
| Playwright execution | $0 | Always |
| Gemini API call | ~$0.0075 | When `enable_ai_analysis=True` |

### Cost Calculation

```python
# Gemini 2.5 Pro pricing (per 1M tokens)
INPUT_COST = $1.25   # ≤200k tokens
OUTPUT_COST = $10.00 # ≤200k tokens

# Estimated token usage per validation
input_tokens = 5000   # Screenshots (~1290 each) + prompt
output_tokens = 500   # Analysis response

# Cost calculation
cost = (5000 * 1.25 / 1_000_000) + (500 * 10.00 / 1_000_000)
cost ≈ $0.0075 per validation
```

### Cost Optimization Strategies

1. **Use Playwright-only for most tests** (free)
2. **Enable Gemini only for critical paths**:
   - Authentication flows
   - Payment/checkout pages
   - User onboarding
3. **Limit to 3 screenshots per analysis** (automatic)
4. **Monitor costs via RouterPolicy budget limits**

## Rate Limits

- **Gemini 2.5 Pro**: 10 requests per minute (RPM)
- **Handled automatically** by rate limiter decorator `@limit_gemini`

If rate limit exceeded:
```python
# Agent falls back gracefully
{
  "ai_analysis": {
    "error": "Rate limit exceeded",
    "analysis_skipped": True
  }
}
```

## Integration with SuperAgent Workflow

### Full Pipeline Integration

```
Scribe → Critic → Runner → [Medic] → Gemini Validation
   ↓        ↓        ↓         ↓            ↓
  Test   Quality  Execute   Fix Bug    Visual Proof
 Writer   Gate     Test               + AI Analysis
```

### When Kaya Calls Gemini

```python
# In Kaya._handle_full_pipeline()
# Step 5: Gemini validates
gemini_result = self._handle_validate(
    slots={'raw_value': test_path},
    context=context
)

# AI analysis enabled for critical paths
if 'critical' in feature.lower() or 'payment' in feature.lower():
    gemini_result = gemini.execute(
        test_path=test_path,
        enable_ai_analysis=True  # Extra validation for critical flows
    )
```

## Error Handling

### Graceful Degradation

The agent always returns a valid result, even if Gemini API fails:

```python
# Scenario 1: Gemini API unavailable
result.data['gemini_enabled'] = False
result.data['ai_analysis'] = None
result.cost_usd = 0.0  # No API cost

# Scenario 2: Gemini API call fails
result.data['ai_analysis'] = {
    'error': 'API timeout',
    'analysis_skipped': True
}
result.cost_usd = 0.0  # No charge for failed calls

# Scenario 3: Screenshots missing
result.data['ai_analysis'] = {
    'error': 'No screenshots could be loaded'
}
```

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| `gemini_enabled: false` | No API key set | Set `GEMINI_API_KEY` env var |
| `analysis_skipped: true` | API call failed | Check logs, verify API key |
| `ImportError: google.genai` | Package not installed | `pip install google-genai` |
| Rate limit errors | >10 RPM | Wait 60s, automatic retry |

## Testing

### Run Tests

```bash
# Run all Gemini agent tests
pytest tests/test_gemini_agent.py -v

# Run specific test category
pytest tests/test_gemini_agent.py::TestGeminiAgentValidation -v

# Run with coverage
pytest tests/test_gemini_agent.py --cov=agent_system.agents.gemini
```

### Test Coverage

- ✅ Initialization and config loading
- ✅ Browser execution (Playwright)
- ✅ Screenshot collection
- ✅ Validation rubric integration
- ✅ Error handling (timeouts, missing files, browser failures)
- ✅ Cost tracking
- ✅ Async execution

### Mock Gemini API in Tests

```python
from unittest.mock import Mock, patch

@patch.object(GeminiAgent, '_analyze_screenshots_with_gemini')
def test_with_ai_analysis(mock_analyze, gemini_agent):
    mock_analyze.return_value = {
        'ui_correctness': 'pass',
        'confidence_score': 95,
        'cost_usd': 0.0075
    }

    result = gemini_agent.execute(
        test_path="test.spec.ts",
        enable_ai_analysis=True
    )

    assert result.data['ai_analysis']['confidence_score'] == 95
```

## Observability

### Logging

```python
# Agent logs key events
logger.info("Phase 1: Executing test in browser: tests/login.spec.ts")
logger.info("Phase 2: Analyzing screenshots with Gemini API")
logger.warning("Gemini API analysis failed: Rate limit exceeded")
logger.error("Gemini API analysis failed: Invalid API key")
```

### Metrics Tracked

- **execution_time_ms**: Total validation time
- **cost_usd**: API costs (Gemini calls only)
- **screenshots_analyzed**: Number of screenshots sent to API
- **confidence_score**: AI confidence in test correctness
- **browser_launched**: Browser startup success
- **test_passed**: Test execution result

## Production Deployment

### Environment Variables

```bash
# Required for Gemini API integration
export GEMINI_API_KEY="your-key-here"

# Optional
export BASE_URL="https://staging.example.com"  # Test target
export GEMINI_API_ENABLED="true"  # Override config
```

### Docker Configuration

```dockerfile
# Dockerfile
ENV GEMINI_API_KEY=""
ENV GEMINI_API_ENABLED="false"

# Install Playwright browsers
RUN npx playwright install --with-deps chromium
```

### Health Check

```bash
# Verify Gemini agent is operational
curl -X POST http://localhost:8000/api/validate \
  -H "Content-Type: application/json" \
  -d '{"test_path": "tests/health_check.spec.ts"}'
```

## Best Practices

### When to Use AI Analysis

✅ **Use Gemini API for**:
- Critical user journeys (auth, checkout, payments)
- Visual regression testing
- UI correctness verification
- High-value features

❌ **Skip Gemini API for**:
- Unit-level component tests
- API/backend tests (no UI)
- Smoke tests
- Frequent CI/CD runs

### Screenshot Best Practices

1. **Take screenshots at key steps**:
```typescript
await page.screenshot({ path: 'step_01_login.png' });
await page.click(S('submit-button'));
await page.screenshot({ path: 'step_02_dashboard.png' });
```

2. **Use descriptive filenames**:
```typescript
const S = (id: string) => `[data-testid="${id}"]`;
await page.screenshot({ path: `${testName}_step_${stepNumber}.png` });
```

3. **Limit to 3-5 key screenshots** (cost optimization)

### Cost Control

```python
# Set budget limits in router_policy.yaml
budget_limits:
  per_feature: 0.50  # Max $0.50 per feature
  validation_override:
    critical_paths: 2.00  # Allow $2 for critical features
```

## Troubleshooting

### Debug Mode

```python
import logging
logging.basicConfig(level=logging.DEBUG)

gemini = GeminiAgent()
result = gemini.execute(test_path="test.spec.ts", enable_ai_analysis=True)

# Check detailed logs
print(result.metadata)
```

### Verify API Key

```bash
# Test Gemini API directly
python -c "
from google import genai
client = genai.Client(api_key='your-key')
response = client.models.list()
print('API key valid:', response)
"
```

### Check Screenshots

```bash
# Verify screenshots are being captured
ls -lh artifacts/test_name/*.png
ls -lh test-results/**/*.png
```

## Future Enhancements

- [ ] Gemini 2.5 Computer Use model integration for direct browser control
- [ ] Visual regression baseline comparison
- [ ] Multi-browser validation (Chrome, Firefox, Safari)
- [ ] Parallel test execution with async validation
- [ ] Integration with vector DB for historical analysis
- [ ] Confidence score threshold enforcement

## References

- **Gemini API Docs**: https://ai.google.dev/gemini-api/docs
- **Gemini Pricing**: https://ai.google.dev/gemini-api/docs/pricing
- **Computer Use**: https://ai.google.dev/gemini-api/docs/computer-use
- **Playwright Docs**: https://playwright.dev/docs/api/class-playwright

## Support

For issues or questions:
1. Check logs: `tail -f logs/gemini_agent.log`
2. Review test failures: `pytest tests/test_gemini_agent.py -v`
3. Verify configuration: `cat .claude/agents/gemini.yaml`
4. Check API quota: https://aistudio.google.com/apikey
