│ Ready to code?                                                                                                       │
│                                                                                                                      │
│ Here is Claude's plan:                                                                                               │
│ ╭──────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮ │
│ │ Phase 0 → Phase 4: Voice-Controlled Multi-Agent Testing System                                                   │ │
│ │                                                                                                                  │ │
│ │ The Complete Implementation Blueprint                                                                            │ │
│ │                                                                                                                  │ │
│ │ ---                                                                                                              │ │
│ │ PHASE 0: Strategic Foundation (Complete - Ready to Execute) ✅                                                    │ │
│ │                                                                                                                  │ │
│ │ Agent Charter (Final Roles)                                                                                      │ │
│ │                                                                                                                  │ │
│ │ Kaya (Router/Orchestrator)                                                                                       │ │
│ │ - Model: Claude Haiku (↑ Sonnet for complex planning)                                                            │ │
│ │ - Tools: None (pure router)                                                                                      │ │
│ │ - Role: Parse voice intent → route to agent → aggregate results → report                                         │ │
│ │ - Success: Correct routing, clear status updates                                                                 │ │
│ │                                                                                                                  │ │
│ │ Scribe (Test Writer)                                                                                             │ │
│ │ - Model: Claude Sonnet 4.5 (Haiku for easy tests)                                                                │ │
│ │ - Tools: Read, Write, Edit, Grep, Glob                                                                           │ │
│ │ - Role: Write Playwright tests following VisionFlow patterns                                                     │ │
│ │ - Success: Compiling code, clear assertions, edge cases covered                                                  │ │
│ │                                                                                                                  │ │
│ │ Runner (Test Executor)                                                                                           │ │
│ │ - Model: Claude Haiku                                                                                            │ │
│ │ - Tools: Bash, Read, Grep                                                                                        │ │
│ │ - Role: Execute tests, parse output, extract errors                                                              │ │
│ │ - Success: Accurate pass/fail, actionable error messages                                                         │ │
│ │                                                                                                                  │ │
│ │ Medic (Bug Fixer)                                                                                                │ │
│ │ - Model: Claude Sonnet 4.5                                                                                       │ │
│ │ - Tools: Read, Edit, Bash, Grep                                                                                  │ │
│ │ - Role: Diagnose failures, apply minimal fixes                                                                   │ │
│ │ - Contract: MUST run regression tests before/after fix                                                           │ │
│ │ - Success: Fix resolves error, no new failures, minimal changes                                                  │ │
│ │                                                                                                                  │ │
│ │ Critic (Pre-Validator)                                                                                           │ │
│ │ - Model: Claude Haiku                                                                                            │ │
│ │ - Tools: Read, Grep                                                                                              │ │
│ │ - Role: Quality gate before expensive Gemini validation                                                          │ │
│ │ - Success: Reject flaky/expensive tests, approve only high-quality                                               │ │
│ │                                                                                                                  │ │
│ │ Gemini (Validator)                                                                                               │ │
│ │ - Model: Gemini 2.5 Pro                                                                                          │ │
│ │ - Tools: Playwright browser automation                                                                           │ │
│ │ - Role: Prove correctness in real browser with screenshots                                                       │ │
│ │ - Success: Deterministic pass/fail with visual evidence                                                          │ │
│ │                                                                                                                  │ │
│ │ ---                                                                                                              │ │
│ │ PHASE 1: Repository Scaffolding (Week 1 - Days 1-2)                                                              │ │
│ │                                                                                                                  │ │
│ │ Directory Structure                                                                                              │ │
│ │                                                                                                                  │ │
│ │ /Users/rutledge/Documents/DevFolder/Cloppy_Ai/                                                                   │ │
│ │ ├── .claude/                                                                                                     │ │
│ │ │   ├── agents/                                                                                                  │ │
│ │ │   │   ├── kaya.yaml                                                                                            │ │
│ │ │   │   ├── scribe.yaml                                                                                          │ │
│ │ │   │   ├── runner.yaml                                                                                          │ │
│ │ │   │   ├── medic.yaml                                                                                           │ │
│ │ │   │   └── critic.yaml                                                                                          │ │
│ │ │   ├── router_policy.yaml                                                                                       │ │
│ │ │   └── observability.yaml                                                                                       │ │
│ │ ├── agent-system/                                                                                                │ │
│ │ │   ├── tools.yaml                                                                                               │ │
│ │ │   ├── validation_rubric.py                                                                                     │ │
│ │ │   ├── router.py                                                                                                │ │
│ │ │   ├── complexity_estimator.py                                                                                  │ │
│ │ │   ├── state/                                                                                                   │ │
│ │ │   │   ├── redis_client.py                                                                                      │ │
│ │ │   │   └── vector_client.py                                                                                     │ │
│ │ │   ├── hitl/                                                                                                    │ │
│ │ │   │   ├── schema.json                                                                                          │ │
│ │ │   │   └── queue.py                                                                                             │ │
│ │ │   └── voice/                                                                                                   │ │
│ │ │       └── orchestrator.ts                                                                                      │ │
│ │ └── tests/                                                                                                       │ │
│ │     └── templates/                                                                                               │ │
│ │         └── playwright.template.ts                                                                               │ │
│ │                                                                                                                  │ │
│ │ Configuration Files (Copy/Paste Ready)                                                                           │ │
│ │                                                                                                                  │ │
│ │ router_policy.yaml                                                                                               │ │
│ │ version: 1                                                                                                       │ │
│ │ routing:                                                                                                         │ │
│ │   - task: write_test                                                                                             │ │
│ │     complexity: easy                                                                                             │ │
│ │     agent: scribe                                                                                                │ │
│ │     model: haiku                                                                                                 │ │
│ │     reason: "Simple CRUD/visible UI path"                                                                        │ │
│ │   - task: write_test                                                                                             │ │
│ │     complexity: hard                                                                                             │ │
│ │     agent: scribe                                                                                                │ │
│ │     model: sonnet                                                                                                │ │
│ │     reason: "Multi-step flows, async, auth, edge cases"                                                          │ │
│ │   - task: execute_test                                                                                           │ │
│ │     complexity: any                                                                                              │ │
│ │     agent: runner                                                                                                │ │
│ │     model: haiku                                                                                                 │ │
│ │   - task: fix_bug                                                                                                │ │
│ │     complexity: any                                                                                              │ │
│ │     agent: medic                                                                                                 │ │
│ │     model: sonnet                                                                                                │ │
│ │   - task: pre_validate                                                                                           │ │
│ │     complexity: any                                                                                              │ │
│ │     agent: critic                                                                                                │ │
│ │     model: haiku                                                                                                 │ │
│ │   - task: validate                                                                                               │ │
│ │     complexity: any                                                                                              │ │
│ │     agent: gemini                                                                                                │ │
│ │     model: 2.5_pro                                                                                               │ │
│ │                                                                                                                  │ │
│ │ cost_targets:                                                                                                    │ │
│ │   use_haiku_ratio: 0.7                                                                                           │ │
│ │   max_cost_per_feature_usd: 0.50                                                                                 │ │
│ │                                                                                                                  │ │
│ │ cost_overrides:                                                                                                  │ │
│ │   critical_paths:                                                                                                │ │
│ │     - pattern: "**/auth/**/*.spec.ts"                                                                            │ │
│ │       max_cost_usd: 2.00                                                                                         │ │
│ │     - pattern: "**/payment/**/*.spec.ts"                                                                         │ │
│ │       max_cost_usd: 3.00                                                                                         │ │
│ │                                                                                                                  │ │
│ │ fallbacks:                                                                                                       │ │
│ │   critic_fail: "return_to_scribe"                                                                                │ │
│ │   validation_timeout: "retry_runner_then_medic"                                                                  │ │
│ │                                                                                                                  │ │
│ │ tools.yaml                                                                                                       │ │
│ │ version: 1                                                                                                       │ │
│ │ permissions:                                                                                                     │ │
│ │   scribe: [read, write, edit, grep, glob]                                                                        │ │
│ │   runner: [bash, read, grep]                                                                                     │ │
│ │   medic:  [read, edit, bash, grep]                                                                               │ │
│ │   critic: [read, grep]                                                                                           │ │
│ │   gemini: [validate]                                                                                             │ │
│ │                                                                                                                  │ │
│ │ tools:                                                                                                           │ │
│ │   read:                                                                                                          │ │
│ │     description: Read files or directories                                                                       │ │
│ │     params: {path: string}                                                                                       │ │
│ │     returns: {content: string}                                                                                   │ │
│ │     security: {allowed_agents: [scribe, runner, medic, critic]}                                                  │ │
│ │     timeout_s: 2                                                                                                 │ │
│ │                                                                                                                  │ │
│ │   write:                                                                                                         │ │
│ │     description: Create a file                                                                                   │ │
│ │     params: {path: string, content: string}                                                                      │ │
│ │     returns: {ok: boolean}                                                                                       │ │
│ │     security: {allowed_agents: [scribe]}                                                                         │ │
│ │     timeout_s: 2                                                                                                 │ │
│ │                                                                                                                  │ │
│ │   edit:                                                                                                          │ │
│ │     description: Apply patch to file                                                                             │ │
│ │     params: {path: string, patch: string}                                                                        │ │
│ │     returns: {ok: boolean}                                                                                       │ │
│ │     security: {allowed_agents: [scribe, medic]}                                                                  │ │
│ │     timeout_s: 5                                                                                                 │ │
│ │                                                                                                                  │ │
│ │   bash:                                                                                                          │ │
│ │     description: Execute in sandbox                                                                              │ │
│ │     params: {cmd: string}                                                                                        │ │
│ │     returns: {stdout: string, stderr: string, code: integer}                                                     │ │
│ │     security: {allowed_agents: [runner, medic]}                                                                  │ │
│ │     timeout_s: 60                                                                                                │ │
│ │                                                                                                                  │ │
│ │   validate:                                                                                                      │ │
│ │     description: Real browser via Gemini                                                                         │ │
│ │     params: {test_path: string, timeout_ms: integer}                                                             │ │
│ │     returns: {result_json: object}                                                                               │ │
│ │     security: {allowed_agents: [gemini]}                                                                         │ │
│ │     timeout_s: 45                                                                                                │ │
│ │                                                                                                                  │ │
│ │ medic.yaml (with Hippocratic Oath)                                                                               │ │
│ │ name: medic                                                                                                      │ │
│ │ model: claude-sonnet-4.5                                                                                         │ │
│ │ tools: [read, edit, bash, grep]                                                                                  │ │
│ │ contracts:                                                                                                       │ │
│ │   coding_style: "minimal surgical fixes only"                                                                    │ │
│ │   regression_scope:                                                                                              │ │
│ │     pre_fix: ["capture_baseline"]                                                                                │ │
│ │     on_fix: ["tests/auth.spec.ts", "tests/core_nav.spec.ts"]                                                     │ │
│ │     post_fix: ["compare_baseline"]                                                                               │ │
│ │     max_new_failures: 0                                                                                          │ │
│ │   artifacts: ["fix.diff", "regression_report.json"]                                                              │ │
│ │                                                                                                                  │ │
│ │ critic.yaml (with rejection criteria)                                                                            │ │
│ │ name: critic                                                                                                     │ │
│ │ model: claude-haiku                                                                                              │ │
│ │ tools: [read, grep]                                                                                              │ │
│ │ contracts:                                                                                                       │ │
│ │   rejection_criteria:                                                                                            │ │
│ │     selectors:                                                                                                   │ │
│ │       - pattern: ".nth(\\d+)"                                                                                    │ │
│ │         reason: "Index-based selectors are flaky"                                                                │ │
│ │       - pattern: "\\.css-[a-z0-9]+"                                                                              │ │
│ │         reason: "Generated CSS classes change"                                                                   │ │
│ │     missing_assertions:                                                                                          │ │
│ │       min_expect_calls: 1                                                                                        │ │
│ │     cost_estimate:                                                                                               │ │
│ │       max_steps: 10                                                                                              │ │
│ │       max_duration_ms: 60000                                                                                     │ │
│ │     anti_patterns:                                                                                               │ │
│ │       - "waitForTimeout"                                                                                         │ │
│ │         reason: "Use waitForSelector instead"                                                                    │ │
│ │                                                                                                                  │ │
│ │ observability.yaml                                                                                               │ │
│ │ version: 1                                                                                                       │ │
│ │ events:                                                                                                          │ │
│ │   - on: "task_queued"                                                                                            │ │
│ │     emit: ["task_id", "feature", "est_cost", "timestamp"]                                                        │ │
│ │   - on: "agent_started"                                                                                          │ │
│ │     emit: ["agent", "task_id", "model", "tools"]                                                                 │ │
│ │   - on: "validation_complete"                                                                                    │ │
│ │     emit: ["task_id", "result", "cost", "duration_ms"]                                                           │ │
│ │   - on: "hitl_escalated"                                                                                         │ │
│ │     emit: ["task_id", "attempts", "last_error"]                                                                  │ │
│ │                                                                                                                  │ │
│ │ destinations:                                                                                                    │ │
│ │   - type: "websocket"                                                                                            │ │
│ │     url: "ws://localhost:3010/agent-events"                                                                      │ │
│ │   - type: "console"                                                                                              │ │
│ │     level: "info"                                                                                                │ │
│ │                                                                                                                  │ │
│ │ ---                                                                                                              │ │
│ │ PHASE 2: Core Router & Validation (Week 1 - Days 3-5)                                                            │ │
│ │                                                                                                                  │ │
│ │ complexity_estimator.py                                                                                          │ │
│ │                                                                                                                  │ │
│ │ """Estimates task complexity using rule-based heuristics."""                                                     │ │
│ │                                                                                                                  │ │
│ │ def estimate_complexity(task: dict) -> str:                                                                      │ │
│ │     """                                                                                                          │ │
│ │     Returns: 'easy' | 'hard'                                                                                     │ │
│ │                                                                                                                  │ │
│ │     Scoring:                                                                                                     │ │
│ │     - Steps > 4: +2                                                                                              │ │
│ │     - Auth/OAuth: +3                                                                                             │ │
│ │     - File ops: +2                                                                                               │ │
│ │     - WebSocket: +3                                                                                              │ │
│ │     - Payment: +4                                                                                                │ │
│ │     - Mocking: +2                                                                                                │ │
│ │                                                                                                                  │ │
│ │     Threshold: ≥5 = hard (Sonnet), <5 = easy (Haiku)                                                             │ │
│ │     """                                                                                                          │ │
│ │     score = 0                                                                                                    │ │
│ │     desc = task.get('description', '').lower()                                                                   │ │
│ │                                                                                                                  │ │
│ │     # Step count                                                                                                 │ │
│ │     if task.get('estimated_steps', 0) > 4:                                                                       │ │
│ │         score += 2                                                                                               │ │
│ │                                                                                                                  │ │
│ │     # Auth required                                                                                              │ │
│ │     if any(kw in desc for kw in ['login', 'auth', 'oauth', '2fa']):                                              │ │
│ │         score += 3                                                                                               │ │
│ │                                                                                                                  │ │
│ │     # File operations                                                                                            │ │
│ │     if any(kw in desc for kw in ['upload', 'download', 'file']):                                                 │ │
│ │         score += 2                                                                                               │ │
│ │                                                                                                                  │ │
│ │     # WebSocket/realtime                                                                                         │ │
│ │     if any(kw in desc for kw in ['websocket', 'realtime', 'sync']):                                              │ │
│ │         score += 3                                                                                               │ │
│ │                                                                                                                  │ │
│ │     # Payment/financial                                                                                          │ │
│ │     if any(kw in desc for kw in ['payment', 'stripe', 'checkout', 'billing']):                                   │ │
│ │         score += 4                                                                                               │ │
│ │                                                                                                                  │ │
│ │     # Network mocking                                                                                            │ │
│ │     if 'mock' in desc:                                                                                           │ │
│ │         score += 2                                                                                               │ │
│ │                                                                                                                  │ │
│ │     return 'hard' if score >= 5 else 'easy'                                                                      │ │
│ │                                                                                                                  │ │
│ │ validation_rubric.py                                                                                             │ │
│ │                                                                                                                  │ │
│ │ """Gemini validation with strict JSON schema."""                                                                 │ │
│ │ from jsonschema import validate, ValidationError                                                                 │ │
│ │                                                                                                                  │ │
│ │ SCHEMA = {                                                                                                       │ │
│ │     "$schema": "https://json-schema.org/draft/2020-12/schema",                                                   │ │
│ │     "type": "object",                                                                                            │ │
│ │     "required": [                                                                                                │ │
│ │         "browser_launched", "test_executed", "test_passed",                                                      │ │
│ │         "screenshots", "console_errors", "network_failures",                                                     │ │
│ │         "execution_time_ms"                                                                                      │ │
│ │     ],                                                                                                           │ │
│ │     "properties": {                                                                                              │ │
│ │         "browser_launched": {"type": "boolean"},                                                                 │ │
│ │         "test_executed": {"type": "boolean"},                                                                    │ │
│ │         "test_passed": {"type": "boolean"},                                                                      │ │
│ │         "screenshots": {                                                                                         │ │
│ │             "type": "array",                                                                                     │ │
│ │             "items": {"type": "string"},                                                                         │ │
│ │             "minItems": 1                                                                                        │ │
│ │         },                                                                                                       │ │
│ │         "console_errors": {                                                                                      │ │
│ │             "type": "array",                                                                                     │ │
│ │             "items": {"type": "string"}                                                                          │ │
│ │         },                                                                                                       │ │
│ │         "network_failures": {                                                                                    │ │
│ │             "type": "array",                                                                                     │ │
│ │             "items": {"type": "string"}                                                                          │ │
│ │         },                                                                                                       │ │
│ │         "execution_time_ms": {                                                                                   │ │
│ │             "type": "integer",                                                                                   │ │
│ │             "minimum": 1,                                                                                        │ │
│ │             "maximum": 45000  # Match tool timeout                                                               │ │
│ │         }                                                                                                        │ │
│ │     },                                                                                                           │ │
│ │     "additionalProperties": False                                                                                │ │
│ │ }                                                                                                                │ │
│ │                                                                                                                  │ │
│ │ def is_pass(result: dict) -> tuple[bool, list[str]]:                                                             │ │
│ │     """                                                                                                          │ │
│ │     Deterministic pass/fail.                                                                                     │ │
│ │     Returns: (passed: bool, errors: list[str])                                                                   │ │
│ │     """                                                                                                          │ │
│ │     errors = []                                                                                                  │ │
│ │                                                                                                                  │ │
│ │     # Schema validation                                                                                          │ │
│ │     try:                                                                                                         │ │
│ │         validate(result, SCHEMA)                                                                                 │ │
│ │     except ValidationError as e:                                                                                 │ │
│ │         return False, [f"schema_invalid: {e.message}"]                                                           │ │
│ │                                                                                                                  │ │
│ │     # Business logic checks                                                                                      │ │
│ │     if not result["browser_launched"]:                                                                           │ │
│ │         errors.append("browser_not_launched")                                                                    │ │
│ │                                                                                                                  │ │
│ │     if not result["test_executed"]:                                                                              │ │
│ │         errors.append("test_not_executed")                                                                       │ │
│ │                                                                                                                  │ │
│ │     if not result["test_passed"]:                                                                                │ │
│ │         errors.append("assertions_failed")                                                                       │ │
│ │                                                                                                                  │ │
│ │     if len(result["screenshots"]) == 0:                                                                          │ │
│ │         errors.append("no_visual_evidence")                                                                      │ │
│ │                                                                                                                  │ │
│ │     if result["execution_time_ms"] > 45000:                                                                      │ │
│ │         errors.append("timeout_exceeded")                                                                        │ │
│ │                                                                                                                  │ │
│ │     return (len(errors) == 0), errors                                                                            │ │
│ │                                                                                                                  │ │
│ │ router.py                                                                                                        │ │
│ │                                                                                                                  │ │
│ │ """Main routing logic with cost enforcement."""                                                                  │ │
│ │ import yaml                                                                                                      │ │
│ │ from complexity_estimator import estimate_complexity                                                             │ │
│ │                                                                                                                  │ │
│ │ def load_policy():                                                                                               │ │
│ │     with open('.claude/router_policy.yaml') as f:                                                                │ │
│ │         return yaml.safe_load(f)                                                                                 │ │
│ │                                                                                                                  │ │
│ │ def route_task(task: dict) -> dict:                                                                              │ │
│ │     """                                                                                                          │ │
│ │     Routes task to appropriate agent/model.                                                                      │ │
│ │     Enforces cost caps and complexity heuristics.                                                                │ │
│ │     """                                                                                                          │ │
│ │     policy = load_policy()                                                                                       │ │
│ │                                                                                                                  │ │
│ │     # Estimate complexity                                                                                        │ │
│ │     complexity = estimate_complexity(task)                                                                       │ │
│ │                                                                                                                  │ │
│ │     # Find matching route                                                                                        │ │
│ │     for rule in policy['routing']:                                                                               │ │
│ │         if rule['task'] == task['type']:                                                                         │ │
│ │             if rule['complexity'] in ['any', complexity]:                                                        │ │
│ │                 route = {                                                                                        │ │
│ │                     'agent': rule['agent'],                                                                      │ │
│ │                     'model': rule['model'],                                                                      │ │
│ │                     'reason': rule['reason']                                                                     │ │
│ │                 }                                                                                                │ │
│ │                                                                                                                  │ │
│ │                 # Apply cost overrides if applicable                                                             │ │
│ │                 max_cost = policy['cost_targets']['max_cost_per_feature_usd']                                    │ │
│ │                 for override in policy.get('cost_overrides', {}).get('critical_paths', []):                      │ │
│ │                     if matches_pattern(task['path'], override['pattern']):                                       │ │
│ │                         max_cost = override['max_cost_usd']                                                      │ │
│ │                         break                                                                                    │ │
│ │                                                                                                                  │ │
│ │                 route['max_cost'] = max_cost                                                                     │ │
│ │                 return route                                                                                     │ │
│ │                                                                                                                  │ │
│ │     # Fallback                                                                                                   │ │
│ │     return {'agent': 'kaya', 'model': 'haiku', 'max_cost': 0.50}                                                 │ │
│ │                                                                                                                  │ │
│ │ def matches_pattern(path: str, pattern: str) -> bool:                                                            │ │
│ │     """Simple glob matching."""                                                                                  │ │
│ │     import fnmatch                                                                                               │ │
│ │     return fnmatch.fnmatch(path, pattern)                                                                        │ │
│ │                                                                                                                  │ │
│ │ ---                                                                                                              │ │
│ │ PHASE 3: State Management (Week 2 - Days 1-3)                                                                    │ │
│ │                                                                                                                  │ │
│ │ Redis Keys (Hot State - 1h TTL)                                                                                  │ │
│ │                                                                                                                  │ │
│ │ state:session:{session_id}                                                                                       │ │
│ │   → {conversation_history: [], active_task_id, budget_remaining}                                                 │ │
│ │                                                                                                                  │ │
│ │ state:queue:tasks                                                                                                │ │
│ │   → [task_id_1, task_id_2, ...]                                                                                  │ │
│ │                                                                                                                  │ │
│ │ state:task:{task_id}                                                                                             │ │
│ │   → {status, agent, started_at, attempts, artifacts_path}                                                        │ │
│ │                                                                                                                  │ │
│ │ state:voice:last                                                                                                 │ │
│ │   → {transcript, intent, slots, timestamp}                                                                       │ │
│ │                                                                                                                  │ │
│ │ Vector Collections (Cold State - Permanent)                                                                      │ │
│ │                                                                                                                  │ │
│ │ vec:patterns:test_success                                                                                        │ │
│ │   → {title, steps, selectors, tags, embedding}                                                                   │ │
│ │                                                                                                                  │ │
│ │ vec:fixes:common_bugs                                                                                            │ │
│ │   → {symptom, root_cause, minimal_fix, diff, embedding}                                                          │ │
│ │                                                                                                                  │ │
│ │ vec:annotations:hitl                                                                                             │ │
│ │   → {root_cause_category, fix_strategy, severity,                                                                │ │
│ │      human_notes, patch_diff, time_to_resolve_min, embedding}                                                    │ │
│ │                                                                                                                  │ │
│ │ Structured HITL Schema                                                                                           │ │
│ │                                                                                                                  │ │
│ │ {                                                                                                                │ │
│ │   "task_id": "t_123",                                                                                            │ │
│ │   "feature": "cart_add_remove",                                                                                  │ │
│ │   "code_path": "tests/cart.spec.ts",                                                                             │ │
│ │   "logs_path": "artifacts/cart/run1.log",                                                                        │ │
│ │   "screenshots": ["artifacts/cart/01.png"],                                                                      │ │
│ │   "attempts": 3,                                                                                                 │ │
│ │   "last_error": "expect(locator).toBeVisible() timeout",                                                         │ │
│ │   "applied_fixes": ["patch_2025-10-14.diff"],                                                                    │ │
│ │   "priority": 0.82,                                                                                              │ │
│ │   "root_cause_category": "selector_flakiness",                                                                   │ │
│ │   "fix_strategy": "update_selector",                                                                             │ │
│ │   "severity": "high",                                                                                            │ │
│ │   "human_notes": "Button ID changed in PR #456",                                                                 │ │
│ │   "patch_diff": "...",                                                                                           │ │
│ │   "time_to_resolve_minutes": 15                                                                                  │ │
│ │ }                                                                                                                │ │
│ │                                                                                                                  │ │
│ │ ---                                                                                                              │ │
│ │ PHASE 4: Voice Orchestration (Week 2-3 - Days 4-7)                                                               │ │
│ │                                                                                                                  │ │
│ │ Voice Intents                                                                                                    │ │
│ │                                                                                                                  │ │
│ │ intents:                                                                                                         │ │
│ │   - create_test:                                                                                                 │ │
│ │       slots: [feature, scope]                                                                                    │ │
│ │       example: "Kaya, write a test for checkout happy path"                                                      │ │
│ │                                                                                                                  │ │
│ │   - run_test:                                                                                                    │ │
│ │       slots: [path]                                                                                              │ │
│ │       example: "Kaya, run tests/cart.spec.ts"                                                                    │ │
│ │                                                                                                                  │ │
│ │   - fix_failure:                                                                                                 │ │
│ │       slots: [task_id]                                                                                           │ │
│ │       example: "Kaya, patch task t_123 and retry"                                                                │ │
│ │                                                                                                                  │ │
│ │   - validate:                                                                                                    │ │
│ │       slots: [path, high_priority]                                                                               │ │
│ │       example: "Kaya, validate payment flow - critical"                                                          │ │
│ │                                                                                                                  │ │
│ │   - status:                                                                                                      │ │
│ │       slots: [task_id]                                                                                           │ │
│ │       example: "Kaya, what's the status of t_123?"                                                               │ │
│ │                                                                                                                  │ │
│ │ Playwright Template (Enhanced)                                                                                   │ │
│ │                                                                                                                  │ │
│ │ // tests/templates/playwright.template.ts                                                                        │ │
│ │ import { test, expect } from '@playwright/test';                                                                 │ │
│ │                                                                                                                  │ │
│ │ const S = (id: string) => `[data-testid="${id}"]`;                                                               │ │
│ │                                                                                                                  │ │
│ │ test.use({                                                                                                       │ │
│ │   screenshot: 'on',                                                                                              │ │
│ │   video: 'retain-on-failure',                                                                                    │ │
│ │   trace: 'retain-on-failure'                                                                                     │ │
│ │ });                                                                                                              │ │
│ │                                                                                                                  │ │
│ │ test.describe('FEATURE_NAME', () => {                                                                            │ │
│ │   test.beforeEach(async ({ page }) => {                                                                          │ │
│ │     await page.goto(process.env.BASE_URL!);                                                                      │ │
│ │   });                                                                                                            │ │
│ │                                                                                                                  │ │
│ │   test('happy path', async ({ page }) => {                                                                       │ │
│ │     // Step 1: Login                                                                                             │ │
│ │     await page.getByTestId('login.email').fill(process.env.USER_EMAIL!);                                         │ │
│ │     await page.getByTestId('login.submit').click();                                                              │ │
│ │     await expect(page.locator(S('dashboard.welcome'))).toBeVisible();                                            │ │
│ │                                                                                                                  │ │
│ │     // Artifact checkpoint for Gemini                                                                            │ │
│ │     await page.screenshot({ path: 'artifacts/step_01.png' });                                                    │ │
│ │                                                                                                                  │ │
│ │     // Step 2: Main action                                                                                       │ │
│ │     await page.getByTestId('action.button').click();                                                             │ │
│ │     await expect(page.locator(S('result.success'))).toBeVisible();                                               │ │
│ │                                                                                                                  │ │
│ │     await page.screenshot({ path: 'artifacts/step_02.png' });                                                    │ │
│ │   });                                                                                                            │ │
│ │                                                                                                                  │ │
│ │   test('error case', async ({ page }) => {                                                                       │ │
│ │     await page.getByTestId('action.invalid').click();                                                            │ │
│ │     await expect(page.locator(S('error.message'))).toBeVisible();                                                │ │
│ │   });                                                                                                            │ │
│ │ });                                                                                                              │ │
│ │                                                                                                                  │ │
│ │ ---                                                                                                              │ │
│ │ Implementation Timeline (4 Weeks)                                                                                │ │
│ │                                                                                                                  │ │
│ │ Week 1: Foundation                                                                                               │ │
│ │                                                                                                                  │ │
│ │ Days 1-2: Scaffold repo, create all YAML configs                                                                 │ │
│ │ Days 3-4: Implement router.py + validation_rubric.py                                                             │ │
│ │ Day 5: Set up Redis + Vector DB, test state flow                                                                 │ │
│ │                                                                                                                  │ │
│ │ Deliverable: Router assigns tasks correctly, validation schema works                                             │ │
│ │                                                                                                                  │ │
│ │ ---                                                                                                              │ │
│ │ Week 2: Agents + Closed-Loop                                                                                     │ │
│ │                                                                                                                  │ │
│ │ Days 1-2: Wire Scribe + Runner (no Gemini yet)                                                                   │ │
│ │ Days 3-4: Add Medic with regression checks                                                                       │ │
│ │ Day 5: Integrate Critic gatekeeper                                                                               │ │
│ │ Days 6-7: Add Gemini validation, test full loop                                                                  │ │
│ │                                                                                                                  │ │
│ │ Deliverable: Scribe → Critic → Runner → Gemini → Medic → Re-validate loop works                                  │ │
│ │                                                                                                                  │ │
│ │ ---                                                                                                              │ │
│ │ Week 3: Voice + HITL                                                                                             │ │
│ │                                                                                                                  │ │
│ │ Days 1-3: OpenAI Realtime integration                                                                            │ │
│ │ Days 4-5: Build HITL dashboard (simple web UI)                                                                   │ │
│ │ Days 6-7: Voice → Full loop end-to-end testing                                                                   │ │
│ │                                                                                                                  │ │
│ │ Deliverable: Voice command → validated feature in <10 minutes                                                    │ │
│ │                                                                                                                  │ │
│ │ ---                                                                                                              │ │
│ │ Week 4: Production Hardening                                                                                     │ │
│ │                                                                                                                  │ │
│ │ Days 1-2: Add observability dashboard (WebSocket events)                                                         │ │
│ │ Days 3-4: Cost analytics + budget alerting                                                                       │ │
│ │ Days 5: Security audit (sandbox, permissions)                                                                    │ │
│ │ Days 6-7: Load testing, optimize for production                                                                  │ │
│ │                                                                                                                  │ │
│ │ Deliverable: Production-ready system with monitoring                                                             │ │
│ │                                                                                                                  │ │
│ │ ---                                                                                                              │ │
│ │ Success Metrics (KPIs)                                                                                           │ │
│ │                                                                                                                  │ │
│ │ Week 1:                                                                                                          │ │
│ │ - ✅ Router makes correct agent/model decisions                                                                   │ │
│ │ - ✅ Validation rubric returns deterministic pass/fail                                                            │ │
│ │                                                                                                                  │ │
│ │ Week 2:                                                                                                          │ │
│ │ - ✅ Closed-loop completes without manual intervention                                                            │ │
│ │ - ✅ Average retries per failure ≤ 1.5                                                                            │ │
│ │ - ✅ Cost per feature ≤ $0.50                                                                                     │ │
│ │                                                                                                                  │ │
│ │ Week 3:                                                                                                          │ │
│ │ - ✅ Voice command → validated feature in <10 minutes                                                             │ │
│ │ - ✅ HITL queue handles failures gracefully                                                                       │ │
│ │                                                                                                                  │ │
│ │ Week 4:                                                                                                          │ │
│ │ - ✅ 95%+ pass rate (flake-adjusted)                                                                              │ │
│ │ - ✅ Critic rejects 15-30% of tests pre-validation                                                                │ │
│ │ - ✅ Observability dashboard shows all agent activity                                                             │ │
│ │                                                                                                                  │ │
│ │ ---                                                                                                              │ │
│ │ Pre-Flight Checklist (Tomorrow Morning)                                                                          │ │
│ │                                                                                                                  │ │
│ │ Before starting implementation, validate:                                                                        │ │
│ │                                                                                                                  │ │
│ │ ✅ All YAML configs reviewed and approved                                                                         │ │
│ │ ✅ Agent roles are clear and non-overlapping                                                                      │ │
│ │ ✅ Validation rubric is machine-readable                                                                          │ │
│ │ ✅ HITL workflow handles all failure cases                                                                        │ │
│ │ ✅ Router logic optimizes cost/performance                                                                        │ │
│ │ ✅ State management strategy is scalable                                                                          │ │
│ │ ✅ Tool permissions follow least-privilege                                                                        │ │
│ │                                                                                                                  │ │
│ │ ---                                                                                                              │ │
│ │ Day 1 Action Items (Tomorrow)                                                                                    │ │
│ │                                                                                                                  │ │
│ │ 1. Create directory structure                                                                                    │ │
│ │ 2. Copy/paste all YAML configs                                                                                   │ │
│ │ 3. Implement complexity_estimator.py                                                                             │ │
│ │ 4. Implement validation_rubric.py                                                                                │ │
│ │ 5. Write router.py basic logic                                                                                   │ │
│ │ 6. Test router with sample tasks (dry run, no API calls)                                                         │ │
│ │ 7. Validate configs with yaml linter                                                                             │ │
│ │                                                                                                                  │ │
│ │ Expected time: 4-6 hours                                                                                         │ │
│ │ Blocker risk: Low (pure setup, no external dependencies)                                                         │ │
│ │                                                                                                                  │ │
│ │ ---                                                                                                              │ │
│ │ This is the complete, production-ready plan. Wake up, execute Day 1, and you'll have the foundation in place by  │ │
│ │ end of day tomorrow.                                                                                             │ │
│ │                                                                                                                  │ │
│ │ Sleep well - we build tomorrow! 🚀