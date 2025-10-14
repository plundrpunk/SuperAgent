# SuperAgent - System Architecture

Complete technical architecture documentation for the SuperAgent multi-agent testing system.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Diagrams](#architecture-diagrams)
3. [Agent Details](#agent-details)
4. [Communication Flow](#communication-flow)
5. [State Management](#state-management)
6. [Cost Optimization Strategy](#cost-optimization-strategy)
7. [Validation Pipeline](#validation-pipeline)
8. [HITL System](#hitl-system)
9. [Observability](#observability)
10. [Security Architecture](#security-architecture)

---

## System Overview

SuperAgent is a voice-controlled multi-agent testing system that automates Playwright test creation, execution, validation, and bug fixing through a coordinated team of specialized AI agents.

### Core Principles

1. **Specialization**: Each agent has a single, well-defined responsibility
2. **Cost Optimization**: 70% Haiku, 30% Sonnet/Gemini for optimal cost/quality
3. **Quality Gates**: Multi-stage validation before expensive operations
4. **Human-in-the-Loop**: Automatic escalation when agents fail
5. **Observability**: Real-time event streaming and metrics

### Technology Stack

**Backend**:
- Python 3.11+ (agent system, routing, state management)
- Anthropic Claude (Haiku, Sonnet 4.5)
- Google Gemini 2.5 Pro (validation)
- Redis (hot state, 1h TTL)
- ChromaDB (cold storage, RAG)

**Frontend/Testing**:
- TypeScript (Playwright tests)
- Node.js 18+ (test execution)
- Playwright (browser automation)

**Infrastructure**:
- Docker + Docker Compose (containerization)
- Nginx (reverse proxy, load balancing)
- WebSocket (real-time events)

---

## Architecture Diagrams

### High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Interface                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Voice Input  │  │  CLI Tool    │  │   Web UI     │          │
│  │ (Realtime)   │  │              │  │  (Future)    │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
└─────────┼──────────────────┼──────────────────┼─────────────────┘
          │                  │                  │
          └──────────────────┼──────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                    Kaya (Router/Orchestrator)                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Intent Parser → Complexity Estimator → Model Selector   │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
┌───────▼────────┐  ┌────────▼────────┐  ┌───────▼────────┐
│     Scribe     │  │     Runner      │  │     Critic     │
│  (Test Writer) │  │   (Executor)    │  │  (Pre-Valid)   │
│  Sonnet/Haiku  │  │     Haiku       │  │     Haiku      │
└───────┬────────┘  └────────┬────────┘  └───────┬────────┘
        │                    │                    │
        └────────────────────┼────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
┌───────▼────────┐  ┌────────▼────────┐  ┌───────▼────────┐
│     Gemini     │  │     Medic       │  │  HITL Queue    │
│  (Validator)   │  │  (Bug Fixer)    │  │  (Escalation)  │
│  Gemini 2.5    │  │     Sonnet      │  │                │
└────────────────┘  └─────────────────┘  └────────────────┘
        │                    │                    │
        └────────────────────┼────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                        State Layer                               │
│  ┌─────────────────────┐         ┌──────────────────────┐      │
│  │   Redis (Hot)       │         │  Vector DB (Cold)    │      │
│  │ - Session data      │         │ - Test patterns      │      │
│  │ - Task queue        │         │ - Bug fixes          │      │
│  │ - Voice transcripts │         │ - HITL annotations   │      │
│  │ - Metrics (1h TTL)  │         │ - Embeddings (RAG)   │      │
│  └─────────────────────┘         └──────────────────────┘      │
└─────────────────────────────────────────────────────────────────┘
        │
┌───────▼─────────────────────────────────────────────────────────┐
│                    Observability Layer                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │  WebSocket  │  │  JSONL Logs │  │   Metrics   │            │
│  │   Events    │  │   (File)    │  │  (Redis)    │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

### Agent Communication Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                     1. Task Initiation                            │
│                                                                   │
│  User: "Kaya, create a test for user login with OAuth"          │
│         │                                                         │
│         ▼                                                         │
│    ┌─────────┐  Parse intent                                     │
│    │  Kaya   │  Estimate complexity: 8 (OAuth +3, steps +2)      │
│    └────┬────┘  Select model: Sonnet (≥5)                        │
│         │       Budget check: $0.50 available                    │
│         │       Emit: task_queued                                │
└─────────┼───────────────────────────────────────────────────────┘
          │
┌─────────▼───────────────────────────────────────────────────────┐
│                     2. Test Generation                            │
│                                                                   │
│    ┌─────────┐                                                   │
│    │ Scribe  │  Search RAG for OAuth patterns                    │
│    │ (Sonnet)│  Generate test with data-testid selectors         │
│    └────┬────┘  Write to tests/login_oauth.spec.ts              │
│         │       Emit: agent_completed ($0.12)                    │
└─────────┼───────────────────────────────────────────────────────┘
          │
┌─────────▼───────────────────────────────────────────────────────┐
│                     3. Pre-Validation (Gate)                      │
│                                                                   │
│    ┌─────────┐                                                   │
│    │ Critic  │  Check for anti-patterns:                         │
│    │ (Haiku) │  ✓ No .nth() selectors                           │
│    └────┬────┘  ✓ No CSS class selectors                        │
│         │       ✓ Has expect() assertions                        │
│         │       ✓ Uses data-testid                               │
│         │       Decision: APPROVED                               │
│         │       Emit: agent_completed ($0.01)                    │
└─────────┼───────────────────────────────────────────────────────┘
          │
┌─────────▼───────────────────────────────────────────────────────┐
│                     4. Test Execution                             │
│                                                                   │
│    ┌─────────┐                                                   │
│    │ Runner  │  Execute: npx playwright test                     │
│    │ (Haiku) │  Parse output                                     │
│    └────┬────┘  Result: PASSED (2.5s)                           │
│         │       Emit: agent_completed ($0.01)                    │
└─────────┼───────────────────────────────────────────────────────┘
          │
┌─────────▼───────────────────────────────────────────────────────┐
│                     5. Browser Validation                         │
│                                                                   │
│    ┌─────────┐                                                   │
│    │ Gemini  │  Launch browser (headless)                        │
│    │  2.5    │  Execute test with screenshots                    │
│    └────┬────┘  Validate rubric:                                │
│         │       ✓ browser_launched: true                         │
│         │       ✓ test_executed: true                            │
│         │       ✓ test_passed: true                              │
│         │       ✓ screenshots: 3                                 │
│         │       ✓ execution_time_ms: 2500 (<45000)              │
│         │       Decision: PASSED                                 │
│         │       Emit: validation_complete ($0.08)                │
└─────────┼───────────────────────────────────────────────────────┘
          │
┌─────────▼───────────────────────────────────────────────────────┐
│                     6. Completion                                 │
│                                                                   │
│    ┌─────────┐                                                   │
│    │  Kaya   │  Aggregate results                                │
│    └────┬────┘  Total cost: $0.22 (<$0.50 limit)                │
│         │       Store pattern in Vector DB                       │
│         │       Response: "✓ Test created and validated"         │
└─────────┴───────────────────────────────────────────────────────┘
```

### Failure Handling Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                     Test Execution Failed                         │
│                                                                   │
│  Runner: Test failed with "Selector timeout"                     │
│         │                                                         │
│         ▼                                                         │
│    ┌─────────┐  Attempt 1                                        │
│    │  Medic  │  Search RAG for similar errors                    │
│    │ (Sonnet)│  Apply fix: Add waitForSelector()                 │
│    └────┬────┘  Run regression tests                             │
│         │       Result: FAILED (selector still not found)        │
│         │       Emit: agent_completed ($0.15)                    │
└─────────┼───────────────────────────────────────────────────────┘
          │
┌─────────▼───────────────────────────────────────────────────────┐
│                     Retry Logic                                   │
│                                                                   │
│    ┌─────────┐  Attempt 2                                        │
│    │  Medic  │  Different strategy: Check element visibility     │
│    │ (Sonnet)│  Apply fix: Wait for network idle                 │
│    └────┬────┘  Run regression tests                             │
│         │       Result: FAILED (same error)                      │
│         │       Emit: agent_completed ($0.15)                    │
└─────────┼───────────────────────────────────────────────────────┘
          │
┌─────────▼───────────────────────────────────────────────────────┐
│                     HITL Escalation                               │
│                                                                   │
│    Max retries (2) exceeded                                       │
│         │                                                         │
│         ▼                                                         │
│    ┌──────────────┐                                              │
│    │ HITL Queue   │  Priority score: 0.75 (HIGH)                │
│    │              │  - attempts: 2                                │
│    └──────┬───────┘  - feature: login                            │
│           │          - error: "Selector timeout"                 │
│           │          - cost_spent: $0.30                         │
│           │          Emit: hitl_escalated                        │
└───────────┼──────────────────────────────────────────────────────┘
            │
┌───────────▼──────────────────────────────────────────────────────┐
│                     Human Resolution                              │
│                                                                   │
│    Human reviews task in dashboard                                │
│         │                                                         │
│         ▼                                                         │
│    Root cause: data-testid changed in app                        │
│    Fix: Update selector in test                                  │
│    Annotation: Store fix pattern in Vector DB                    │
│         │                                                         │
│         ▼                                                         │
│    Test re-validated → PASSED                                    │
│    Pattern learned for future similar issues                     │
└──────────────────────────────────────────────────────────────────┘
```

---

## Agent Details

### Kaya (Router/Orchestrator)

**Role**: Parse voice intent, route to appropriate agent, aggregate results.

**Model**: Claude Haiku (upgrades to Sonnet for complex planning)

**Tools**: None (pure router)

**Inputs**:
- Voice transcript or text command
- User intent (create_test, run_test, fix_failure, validate, status)

**Outputs**:
- Routing decision (agent, model, budget)
- Aggregated results from agents
- Status updates to user

**Algorithm**:
```python
def route_task(command: str) -> RoutingDecision:
    # 1. Parse intent
    intent = parse_intent(command)  # create_test, run_test, etc.

    # 2. Estimate complexity
    complexity = estimate_complexity(command)
    # OAuth +3, WebSocket +3, Payment +4, Steps >4 +2, etc.

    # 3. Select model
    if complexity >= 5:
        model = "sonnet"  # Complex task
    else:
        model = "haiku"   # Simple task

    # 4. Check budget
    feature = extract_feature(command)
    cost_limit = get_cost_limit(feature)  # $0.50 or $3.00 for critical

    # 5. Route to agent
    agent = select_agent(intent)  # Scribe, Runner, Critic, etc.

    return RoutingDecision(agent, model, cost_limit)
```

**Success Criteria**:
- Correct routing (100% accuracy on test cases)
- Accurate complexity estimation (±1 point)
- Cost enforcement (no budget overruns)

### Scribe (Test Writer)

**Role**: Generate Playwright tests following VisionFlow patterns.

**Model**: Claude Sonnet 4.5 (downgrades to Haiku for simple tests)

**Tools**: Read, Write, Edit, Grep, Glob

**Inputs**:
- Feature description
- RAG patterns (similar successful tests)
- Test template

**Outputs**:
- Playwright test file (.spec.ts)
- Test metadata (cost, complexity, coverage)

**Algorithm**:
```python
def write_test(feature: str) -> TestFile:
    # 1. Search RAG for patterns
    patterns = vector_db.search_similar_tests(feature, limit=3)

    # 2. Load template
    template = read_file("tests/templates/playwright.template.ts")

    # 3. Generate test using Claude
    prompt = f"""
    Feature: {feature}
    Similar patterns: {patterns}
    Template: {template}

    Generate Playwright test with:
    - data-testid selectors only
    - expect() assertions (min 1)
    - Screenshots after major steps
    - Error case coverage
    """
    test_code = claude.generate(prompt)

    # 4. Write test file
    filename = f"tests/{slugify(feature)}.spec.ts"
    write_file(filename, test_code)

    # 5. Store pattern
    vector_db.store_test_pattern(
        test_id=filename,
        feature=feature,
        code=test_code,
        metadata={"model": "sonnet", "cost": 0.12}
    )

    return TestFile(filename, test_code, cost=0.12)
```

**Success Criteria**:
- Compiling TypeScript code
- Clear assertions (min 1 expect)
- Edge cases covered
- data-testid selectors only

### Runner (Test Executor)

**Role**: Execute Playwright tests, parse output, extract errors.

**Model**: Claude Haiku

**Tools**: Bash, Read, Grep

**Inputs**:
- Test file path
- Execution environment config

**Outputs**:
- Test result (pass/fail)
- Execution time
- Error messages (if failed)
- Artifacts (screenshots, videos, traces)

**Algorithm**:
```python
def execute_test(test_path: str) -> TestResult:
    # 1. Execute test
    result = subprocess.run(
        ["npx", "playwright", "test", test_path],
        capture_output=True,
        timeout=60
    )

    # 2. Parse output
    passed = result.returncode == 0
    output = result.stdout.decode()
    errors = extract_errors(output) if not passed else []

    # 3. Extract metrics
    execution_time = extract_execution_time(output)
    artifacts = find_artifacts(test_path)

    # 4. Return result
    return TestResult(
        passed=passed,
        execution_time_ms=execution_time,
        errors=errors,
        artifacts=artifacts
    )
```

**Success Criteria**:
- Accurate pass/fail detection
- Actionable error messages
- Artifact capture (screenshots, videos)

### Critic (Pre-Validator)

**Role**: Quality gate before expensive Gemini validation.

**Model**: Claude Haiku

**Tools**: Read, Grep

**Inputs**:
- Test file path
- Anti-pattern rules

**Outputs**:
- Decision (approve/reject)
- Rejection reason (if rejected)
- Cost estimate for validation

**Algorithm**:
```python
def review_test(test_path: str) -> ReviewDecision:
    # 1. Read test file
    test_code = read_file(test_path)

    # 2. Check anti-patterns
    issues = []

    if re.search(r'\.nth\(\d+\)', test_code):
        issues.append("Index-based selector: .nth()")

    if re.search(r'\.css-[a-z0-9]+', test_code):
        issues.append("Generated CSS class selector")

    if 'waitForTimeout' in test_code:
        issues.append("Fixed timeout: waitForTimeout")

    if 'expect(' not in test_code:
        issues.append("Missing assertions")

    # 3. Estimate execution time
    steps = count_actions(test_code)
    estimated_time_ms = steps * 500

    if estimated_time_ms > 60000:
        issues.append(f"Estimated execution too long: {estimated_time_ms}ms")

    # 4. Decision
    if issues:
        return ReviewDecision(
            approved=False,
            rejection_reason=", ".join(issues)
        )
    else:
        return ReviewDecision(
            approved=True,
            est_validation_cost=0.08
        )
```

**Success Criteria**:
- Reject flaky tests (15-30% rejection rate)
- Approve only high-quality tests
- Fast execution (<1 second)

### Medic (Bug Fixer)

**Role**: Diagnose test failures and apply minimal surgical fixes.

**Model**: Claude Sonnet 4.5

**Tools**: Read, Edit, Bash, Grep

**Inputs**:
- Test file path
- Error message from Runner
- RAG fix patterns

**Outputs**:
- Fixed test file
- Fix diff
- Regression test results

**Algorithm**:
```python
def fix_test(test_path: str, error: str) -> FixResult:
    # 1. Search RAG for similar errors
    fix_patterns = vector_db.search_similar_fixes(error, limit=3)

    # 2. Run regression tests (baseline)
    baseline = run_regression_tests()

    # 3. Generate fix using Claude
    test_code = read_file(test_path)
    prompt = f"""
    Test file: {test_path}
    Error: {error}
    Similar fixes: {fix_patterns}

    Apply minimal fix. Hippocratic Oath:
    - Minimal changes only
    - No new test failures
    - Keep existing functionality
    """
    fixed_code = claude.generate_fix(prompt)

    # 4. Apply fix
    write_file(test_path, fixed_code)
    diff = generate_diff(test_code, fixed_code)

    # 5. Run regression tests
    regression_result = run_regression_tests()
    new_failures = regression_result.failures - baseline.failures

    # 6. Check Hippocratic Oath
    if new_failures > 0:
        # Rollback fix
        write_file(test_path, test_code)
        return FixResult(success=False, reason="New failures introduced")

    # 7. Store fix pattern
    vector_db.store_bug_fix(
        error_signature=error,
        fix_strategy="extracted_from_code",
        code_diff=diff,
        success_rate=1.0
    )

    return FixResult(
        success=True,
        diff=diff,
        regression_passed=True
    )
```

**Success Criteria**:
- Fix resolves error
- No new test failures (max_new_failures: 0)
- Minimal code changes
- Regression tests pass

### Gemini (Validator)

**Role**: Prove test correctness in real browser with screenshots.

**Model**: Gemini 2.5 Pro

**Tools**: Playwright browser automation

**Inputs**:
- Test file path
- Validation rubric

**Outputs**:
- Validation result (pass/fail)
- Screenshots (visual evidence)
- Execution metrics
- Rubric compliance

**Algorithm**:
```python
async def validate_test(test_path: str) -> ValidationResult:
    # 1. Launch browser
    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context(
        viewport={'width': 1280, 'height': 720}
    )
    page = await context.new_page()

    # 2. Execute test with instrumentation
    screenshots = []
    errors = []

    try:
        # Run test
        result = await run_playwright_test(test_path, page)

        # Capture screenshots
        screenshots.append(await page.screenshot())

        # Check rubric
        rubric = {
            'browser_launched': True,
            'test_executed': result.executed,
            'test_passed': result.passed,
            'screenshots': len(screenshots),
            'execution_time_ms': result.execution_time,
            'console_errors': errors,
            'network_failures': []
        }

    except Exception as e:
        rubric = {
            'browser_launched': False,
            'test_executed': False,
            'test_passed': False,
            'error': str(e)
        }

    finally:
        await browser.close()

    # 3. Validate rubric
    passed = (
        rubric['browser_launched'] and
        rubric['test_executed'] and
        rubric['test_passed'] and
        rubric['screenshots'] >= 1 and
        rubric['execution_time_ms'] <= 45000
    )

    return ValidationResult(
        passed=passed,
        rubric=rubric,
        screenshots=screenshots,
        cost=0.08
    )
```

**Success Criteria**:
- Deterministic pass/fail
- Visual evidence (screenshots)
- Rubric compliance
- Execution time <45s

---

## Communication Flow

### Inter-Agent Communication

Agents communicate through:

1. **Direct function calls** (synchronous):
```python
result = scribe.write_test(feature="login")
```

2. **Task queue** (asynchronous):
```python
redis.lpush("task_queue", json.dumps({
    "task_id": "t_123",
    "agent": "scribe",
    "feature": "login"
}))
```

3. **Event streaming** (observability):
```python
emit_event('agent_completed', {
    'agent': 'scribe',
    'task_id': 't_123',
    'status': 'success',
    'cost_usd': 0.12
})
```

### Message Format

**AgentResult** (standard return type):
```python
@dataclass
class AgentResult:
    success: bool
    data: Dict[str, Any]
    cost_usd: float
    execution_time_ms: int
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
```

**Task** (queue format):
```python
{
    "task_id": "t_123",
    "feature": "user_login",
    "agent": "scribe",
    "model": "sonnet",
    "priority": 0.8,
    "cost_limit": 0.50,
    "metadata": {
        "user_id": "user_456",
        "timestamp": 1729012418.123
    }
}
```

---

## State Management

### Hot State (Redis, 1h TTL)

**Purpose**: Temporary data for active tasks

**Schema**:
```
session:{session_id}          # User session data
task:{task_id}                # Task metadata and status
voice:transcript:{id}         # Voice transcripts
metrics:hourly:{timestamp}    # Hourly aggregated metrics
metrics:daily:{date}          # Daily aggregated metrics
```

**Example**:
```python
# Store task
redis.set("task:t_123", {
    "status": "in_progress",
    "agent": "scribe",
    "started_at": 1729012418.123,
    "cost_so_far": 0.12
}, ttl=3600)

# Get task
task = redis.get("task:t_123")
```

### Cold State (Vector DB, Permanent)

**Purpose**: Long-term storage for RAG patterns

**Collections**:
```
test_patterns       # Successful test code
bug_fixes           # Error → fix mappings
hitl_annotations    # Human feedback
```

**Example**:
```python
# Store test pattern
vector_db.store_test_pattern(
    test_id="test_login_001",
    feature="login",
    pattern_type="success",
    code="...",
    metadata={
        "model": "sonnet",
        "cost": 0.12,
        "complexity": 3,
        "selectors": ["email", "password", "submit"]
    }
)

# Search patterns
results = vector_db.search_similar_tests(
    query="login with OAuth",
    limit=3
)
```

### State Lifecycle

```
1. Task Created
   ├─ Store in Redis (hot)
   ├─ Add to task queue
   └─ Emit task_queued event

2. Task In Progress
   ├─ Update status in Redis
   ├─ Track cost in Redis
   └─ Emit agent_started/completed events

3. Task Completed (Success)
   ├─ Store pattern in Vector DB (cold)
   ├─ Remove from Redis (TTL expiry)
   └─ Emit completion metrics

4. Task Failed (HITL)
   ├─ Store in HITL queue (Redis)
   ├─ Keep task data until resolved
   └─ Emit hitl_escalated event

5. Human Resolution
   ├─ Store annotation in Vector DB
   ├─ Remove from HITL queue
   └─ Emit resolution event
```

---

## Cost Optimization Strategy

### Model Selection Matrix

| Task | Complexity | Model | Cost (est) | When to Use |
|------|-----------|-------|-----------|-------------|
| Routing | N/A | Haiku | $0.01 | Always |
| Simple test | <5 | Haiku | $0.05 | Login, navigation |
| Complex test | ≥5 | Sonnet | $0.12 | OAuth, payments, WebSocket |
| Test execution | N/A | Haiku | $0.01 | Always |
| Pre-validation | N/A | Haiku | $0.01 | Always |
| Final validation | N/A | Gemini | $0.08 | After Critic approval |
| Bug fix | N/A | Sonnet | $0.15 | After Runner failure |

### Complexity Scoring

```python
def estimate_complexity(description: str) -> int:
    score = 0

    # Count steps
    steps = count_steps(description)
    if steps > 4:
        score += 2

    # Check keywords
    if re.search(r'auth|oauth|jwt|token', description, re.I):
        score += 3

    if re.search(r'file|upload|download', description, re.I):
        score += 2

    if re.search(r'websocket|ws|realtime', description, re.I):
        score += 3

    if re.search(r'payment|stripe|checkout', description, re.I):
        score += 4

    if re.search(r'mock|stub|spy', description, re.I):
        score += 2

    return score

# Examples:
# "Create login test" → 0 → Haiku
# "Create OAuth login with 2FA" → 3+2=5 → Sonnet
# "Test payment flow with Stripe" → 4 → Sonnet (critical override)
```

### Budget Enforcement

```python
def check_budget(feature: str, estimated_cost: float) -> bool:
    # Get limits
    if is_critical_path(feature):  # auth, payment
        limit = 3.00
    else:
        limit = 0.50

    # Track spending
    spent = redis.get(f"cost:daily:{today}")
    daily_limit = 50.00

    # Check limits
    if estimated_cost > limit:
        emit_event('budget_warning', {
            'feature': feature,
            'estimated_cost': estimated_cost,
            'limit': limit
        })
        return False

    if spent + estimated_cost > daily_limit:
        emit_event('budget_exceeded', {
            'daily_spent': spent,
            'daily_limit': daily_limit
        })
        return False

    return True
```

### Cost Tracking

**Per-task tracking**:
```python
{
    "task_id": "t_123",
    "costs": {
        "scribe": 0.12,   # Test generation
        "critic": 0.01,   # Pre-validation
        "runner": 0.01,   # Execution
        "gemini": 0.08,   # Validation
        "total": 0.22
    },
    "budget": 0.50,
    "remaining": 0.28
}
```

**Daily aggregation**:
```python
metrics:daily:2025-01-14 = {
    "total_cost": 12.45,
    "tasks_completed": 34,
    "avg_cost_per_task": 0.37,
    "model_breakdown": {
        "haiku": 6.80,
        "sonnet": 4.25,
        "gemini": 1.40
    }
}
```

---

## Validation Pipeline

### Three-Stage Validation

```
┌─────────────────────────────────────────────────────────────┐
│                    Stage 1: Static Analysis                  │
│                       (Critic - Haiku)                       │
│                         Cost: $0.01                          │
│                                                              │
│  ✓ No .nth() selectors                                      │
│  ✓ No CSS class selectors                                   │
│  ✓ Has expect() assertions                                  │
│  ✓ Uses data-testid                                         │
│  ✓ No waitForTimeout                                        │
│                                                              │
│  Rejection rate: 15-30%                                      │
│  Purpose: Fast quality gate before expensive operations      │
└──────────────────┬──────────────────────────────────────────┘
                   │ APPROVED
┌──────────────────▼──────────────────────────────────────────┐
│                    Stage 2: Test Execution                   │
│                       (Runner - Haiku)                       │
│                         Cost: $0.01                          │
│                                                              │
│  Execute: npx playwright test {file}                        │
│  Timeout: 60 seconds                                         │
│  Capture: stdout, stderr, exit code                         │
│  Artifacts: screenshots, videos, traces                      │
│                                                              │
│  Pass rate: 60-70% (first attempt)                          │
│  Purpose: Verify test compiles and runs                     │
└──────────────────┬──────────────────────────────────────────┘
                   │ PASSED
┌──────────────────▼──────────────────────────────────────────┐
│                    Stage 3: Browser Validation               │
│                       (Gemini 2.5 Pro)                       │
│                         Cost: $0.08                          │
│                                                              │
│  Launch browser (Chromium)                                   │
│  Execute test with instrumentation                           │
│  Capture screenshots at each step                            │
│  Validate rubric:                                            │
│    ✓ browser_launched: true                                 │
│    ✓ test_executed: true                                    │
│    ✓ test_passed: true                                      │
│    ✓ screenshots.length ≥ 1                                 │
│    ✓ execution_time_ms ≤ 45000                              │
│    ✓ console_errors: [] (tracked)                           │
│    ✓ network_failures: [] (tracked)                         │
│                                                              │
│  Purpose: Prove correctness with visual evidence             │
└─────────────────────────────────────────────────────────────┘
```

### Validation Rubric

**Schema** (JSON):
```json
{
  "browser_launched": true,
  "test_executed": true,
  "test_passed": true,
  "screenshots": 3,
  "execution_time_ms": 2500,
  "console_errors": [],
  "network_failures": [],
  "coverage": {
    "assertions": 2,
    "interactions": 5,
    "navigation": 1
  }
}
```

**Pass Criteria**:
- All boolean fields must be `true`
- `screenshots` must be ≥ 1
- `execution_time_ms` must be ≤ 45000
- `console_errors` and `network_failures` tracked but not blocking

---

## HITL System

### Human-in-the-Loop Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    Failure Triggers HITL                      │
│                                                               │
│  Medic attempts: 2                                            │
│  Both attempts failed                                         │
│  Cost spent: $0.30                                            │
│  Error: "Selector timeout: [data-testid='submit']"          │
└───────────────────┬──────────────────────────────────────────┘
                    │
┌───────────────────▼──────────────────────────────────────────┐
│                    Priority Scoring                           │
│                                                               │
│  priority = (                                                 │
│    0.3 * (attempts / max_attempts) +                         │
│    0.2 * (cost_spent / cost_limit) +                         │
│    0.3 * is_critical_feature +                               │
│    0.2 * time_in_queue                                       │
│  )                                                            │
│                                                               │
│  Result: 0.75 (HIGH priority)                                │
└───────────────────┬──────────────────────────────────────────┘
                    │
┌───────────────────▼──────────────────────────────────────────┐
│                    HITL Queue                                 │
│                                                               │
│  Task added to queue with metadata:                          │
│  - task_id: t_123                                            │
│  - feature: login                                            │
│  - priority: 0.75                                            │
│  - attempts: 2                                               │
│  - last_error: "Selector timeout"                           │
│  - test_path: tests/login.spec.ts                           │
│  - artifacts: [screenshots, logs]                            │
│  - timestamp: 2025-01-14T12:00:00Z                          │
│                                                               │
│  Emit: hitl_escalated event                                  │
└───────────────────┬──────────────────────────────────────────┘
                    │
┌───────────────────▼──────────────────────────────────────────┐
│                    Human Dashboard                            │
│                                                               │
│  Web UI displays:                                             │
│  - Task details                                               │
│  - Error history                                              │
│  - Test code (with diffs)                                     │
│  - Screenshots/artifacts                                      │
│  - Suggested fixes from RAG                                   │
│                                                               │
│  Human actions:                                               │
│  1. Review error                                              │
│  2. Identify root cause                                       │
│  3. Apply fix                                                 │
│  4. Add annotation                                            │
└───────────────────┬──────────────────────────────────────────┘
                    │
┌───────────────────▼──────────────────────────────────────────┐
│                    Resolution                                 │
│                                                               │
│  Human annotation:                                            │
│  {                                                            │
│    "root_cause_category": "selector_changed",                │
│    "fix_strategy": "update_selector",                        │
│    "patch_diff": "- [data-testid='submit']                  │
│                   + [data-testid='submit-button']",          │
│    "human_notes": "App changed selector naming convention",  │
│    "confidence": 0.95                                        │
│  }                                                            │
│                                                               │
│  Store in Vector DB for future learning                      │
│  Remove from HITL queue                                       │
│  Re-validate test → PASSED                                    │
└──────────────────────────────────────────────────────────────┘
```

### Priority Algorithm

```python
def calculate_priority(task: Dict) -> float:
    # Weights
    W_ATTEMPTS = 0.3
    W_COST = 0.2
    W_CRITICAL = 0.3
    W_TIME = 0.2

    # Normalize values (0-1)
    attempts_score = task['attempts'] / MAX_RETRY_ATTEMPTS
    cost_score = task['cost_spent'] / task['cost_limit']
    critical_score = 1.0 if is_critical_feature(task['feature']) else 0.0
    time_score = min(1.0, task['time_in_queue'] / 3600)  # 1 hour = max

    # Calculate priority
    priority = (
        W_ATTEMPTS * attempts_score +
        W_COST * cost_score +
        W_CRITICAL * critical_score +
        W_TIME * time_score
    )

    return priority

# Examples:
# Login (critical), 2 attempts, $0.30 spent, 10 min in queue
# → 0.3*0.67 + 0.2*0.60 + 0.3*1.0 + 0.2*0.17 = 0.75 (HIGH)

# Settings (non-critical), 1 attempt, $0.10 spent, 2 min in queue
# → 0.3*0.33 + 0.2*0.20 + 0.3*0.0 + 0.2*0.03 = 0.15 (LOW)
```

---

## Observability

### Event Streaming Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    Event Sources                              │
│                                                               │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │
│  │  Kaya   │  │ Scribe  │  │ Runner  │  │  Medic  │        │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘        │
│       │            │            │            │               │
│       └────────────┼────────────┼────────────┘               │
│                    │            │                            │
└────────────────────┼────────────┼────────────────────────────┘
                     │            │
┌────────────────────▼────────────▼────────────────────────────┐
│                    EventEmitter                               │
│                  (Global Singleton)                           │
│                                                               │
│  emit_event(event_type, payload)                             │
│         │                                                     │
│         ├─────────┬─────────┬─────────┐                     │
│         │         │         │         │                     │
│         ▼         ▼         ▼         ▼                     │
│    Console   JSONL File  WebSocket  Redis                   │
└────────┬──────────┬─────────┬─────────┬─────────────────────┘
         │          │         │         │
         ▼          ▼         ▼         ▼
    Terminal   agent-events  Dashboard  Metrics
    Output    .jsonl        (Port 3010) (Aggregated)
```

### Event Types

1. **task_queued** - Task enters queue
2. **agent_started** - Agent begins work
3. **agent_completed** - Agent finishes work
4. **validation_complete** - Gemini validation results
5. **hitl_escalated** - Human-in-the-loop escalation
6. **budget_warning** - 80% budget threshold
7. **budget_exceeded** - Budget limit exceeded

### Metrics Aggregation

**In-memory counters**:
```python
{
    "tasks_queued": 100,
    "tasks_completed": 85,
    "tasks_failed": 15,
    "agent_time_ms": {
        "scribe": 245000,
        "runner": 85000,
        "critic": 8500,
        "gemini": 68000,
        "medic": 127500
    },
    "total_cost": 12.45,
    "critic_rejections": 25,
    "validation_passes": 60
}
```

**Calculated KPIs**:
```python
{
    "agent_utilization": 0.87,           # 87% of time agents active
    "cost_per_feature": 0.37,            # $0.37 average
    "average_retry_count": 0.18,         # 0.18 retries per task
    "critic_rejection_rate": 0.25,       # 25% rejected
    "validation_pass_rate": 0.71,        # 71% passed
    "time_to_completion": 165.5          # 2m 45s average
}
```

---

## Security Architecture

### Authentication & Authorization

**API Key Security**:
- Store in environment variables (never in code)
- Rotate keys quarterly
- Use different keys per environment (dev, staging, prod)

**Access Control**:
- Agents have restricted tool access (defined in .claude/agents/*.yaml)
- Sandbox mode restricts file system access
- Network isolation between containers

### Data Security

**In Transit**:
- TLS 1.2+ for all external API calls
- WebSocket connections over WSS (production)
- Redis TLS for managed Redis

**At Rest**:
- Vector database encrypted at rest (filesystem encryption)
- Redis RDB/AOF files encrypted (production)
- Sensitive data (API keys) in secrets management

### Network Security

**Firewall Rules**:
```bash
# Allow
- 22/tcp (SSH)
- 80/tcp (HTTP → HTTPS redirect)
- 443/tcp (HTTPS)

# Deny
- 6379/tcp (Redis - internal only)
- 3010/tcp (WebSocket - internal only)
- 8000/tcp (Observability - internal only)
```

**Container Isolation**:
- Separate Docker networks for services
- Redis accessible only from SuperAgent container
- No privileged containers

### Audit Logging

**All events logged**:
```json
{
  "timestamp": "2025-01-14T12:00:00.123Z",
  "event_type": "agent_started",
  "agent": "scribe",
  "task_id": "t_123",
  "user_id": "user_456",
  "ip_address": "192.168.1.100",
  "payload": {...}
}
```

**Retention**:
- JSONL logs: 90 days
- Redis metrics: 30 days (daily), 7 days (hourly)
- Vector DB: Permanent (with backups)

---

## Performance Characteristics

### Latency

| Operation | Latency | Notes |
|-----------|---------|-------|
| Intent parsing | 50-100ms | Kaya routing |
| Test generation | 2-5s | Scribe with RAG |
| Pre-validation | 200-500ms | Critic static analysis |
| Test execution | 2-10s | Runner subprocess |
| Browser validation | 3-8s | Gemini with screenshots |
| Bug fix | 3-6s | Medic with RAG |
| Total (success) | 10-30s | End-to-end |
| Total (with retry) | 20-60s | Including Medic |

### Throughput

**Single instance**:
- Test generation: 12-20 per hour
- Test execution: 60-120 per hour
- Validation: 30-50 per hour

**Scaled (3 instances)**:
- Test generation: 36-60 per hour
- Test execution: 180-360 per hour
- Validation: 90-150 per hour

### Resource Usage

**Per task**:
- CPU: 0.5-1.0 cores
- Memory: 500 MB - 1 GB
- Disk: 10-50 MB (artifacts)
- Network: 1-5 MB

**System-wide** (single instance):
- CPU: 1-2 cores (idle), 2-4 cores (active)
- Memory: 2-4 GB
- Disk: 10 GB (including Docker images)
- Network: 100 MB/hour (API calls)

---

## Scalability

### Horizontal Scaling

```
┌────────────────────────────────────────────────────────────┐
│                      Load Balancer                          │
│                         (Nginx)                             │
└────────────────┬───────────────────────┬───────────────────┘
                 │                       │
     ┌───────────┼───────────────────────┼──────────┐
     │           │                       │          │
┌────▼────┐ ┌───▼─────┐ ┌────▼────┐ ┌──▼──────┐
│ Agent 1 │ │ Agent 2 │ │ Agent 3 │ │ Agent N │
└────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘
     │           │            │           │
     └───────────┼────────────┼───────────┘
                 │            │
         ┌───────▼────────────▼────────┐
         │   Shared State (Redis)      │
         │   Vector DB (ChromaDB)      │
         └─────────────────────────────┘
```

**Scale agents independently**:
```bash
docker compose up -d --scale superagent=3
```

### Vertical Scaling

**Memory optimization**:
- Increase for more concurrent tests
- Decrease with artifact cleanup

**CPU optimization**:
- Increase for faster test execution
- Parallel Playwright workers

---

## Disaster Recovery

### Backup Strategy

**Automated daily backups**:
- Redis (RDB + AOF)
- Vector DB (full directory)
- Test files
- Artifacts
- Logs

**Retention**:
- Daily: 30 days
- Weekly: 3 months
- Monthly: 1 year

### Recovery Procedures

**Redis failure**:
1. Stop SuperAgent
2. Restore Redis from backup
3. Restart Redis
4. Restart SuperAgent
5. Verify metrics

**Vector DB corruption**:
1. Stop SuperAgent
2. Move corrupted DB to backup
3. Restore from backup
4. Reinitialize if necessary
5. Restart SuperAgent

**Complete system failure**:
1. Provision new server
2. Install Docker
3. Clone repository
4. Restore volumes from backup
5. Start services
6. Verify health checks

---

## Related Documentation

- [Deployment Guide](./DEPLOYMENT.md) - Complete deployment instructions
- [Troubleshooting Guide](./TROUBLESHOOTING.md) - Common issues and solutions
- [Docker Guide](../DOCKER.md) - Docker quick start
- [README](../README.md) - Project overview

---

**Version**: 1.0.0
**Last Updated**: January 2025
**Maintainer**: SuperAgent Team
