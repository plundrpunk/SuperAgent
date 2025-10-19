# Integration Tests

This directory contains end-to-end integration tests for SuperAgent's multi-agent system.

## Test Files

### test_full_pipeline.py ⭐ NEW
**Comprehensive master test** for the complete SuperAgent pipeline: Scribe → Critic → Runner → Gemini → Medic → Re-validation.

**Features:**
- `PipelineTestHarness` helper class for orchestrating full pipeline tests
- 8 test scenarios (5 active, 3 TODOs) covering entire workflow
- Performance validation (time, cost, retries)
- Artifact generation validation
- References existing integration tests for detailed coverage

**Test Classes:**
- `TestFullPipeline` - 8 comprehensive pipeline scenarios
- `TestPipelinePerformance` - Performance target validation
- `TestPipelineArtifacts` - Artifact generation tests

**Total Tests:** 5 active tests (references 81 existing tests)

**See:** [FULL_PIPELINE_TEST_GUIDE.md](FULL_PIPELINE_TEST_GUIDE.md) for detailed documentation.

### test_closed_loop.py
Complete closed-loop workflow validation with all agents.

**Test Classes:**
- `TestClosedLoopWorkflow` - Full pipeline tests (3 tests)
- `TestClosedLoopCostTracking` - Cost aggregation (1 test)

**Total Tests:** 4 tests

### test_simple_crud_flow.py
Comprehensive end-to-end test for simple CRUD test creation flow.

**Test Classes:**
- `TestSimpleCRUDFlow` - Main integration tests (5 tests)
- `TestFlowPerformance` - Performance validation (1 test)

**Total Tests:** 6 tests, all passing

### test_hitl_escalation_flow.py
End-to-end test for Human-in-the-Loop escalation workflow.

**Test Classes:**
- `TestHITLEscalationFlow` - HITL escalation tests (6 tests)

**Tests:**
1. `test_medic_escalates_after_max_retries` - Medic escalates after 3 failed attempts
2. `test_hitl_priority_calculation` - Priority scoring based on attempts, feature criticality, and age
3. `test_human_resolution_with_annotation` - Human resolves task with annotation storage
4. `test_annotation_retrieval_for_future_fixes` - Medic retrieves HITL patterns for similar failures
5. `test_hitl_queue_listing_and_filtering` - Queue listing and filtering by priority/status
6. `test_hitl_queue_stats` - Queue statistics calculation

**Total Tests:** 6 tests

### test_cost_budget_enforcement.py
End-to-end test for Router's cost budget enforcement system.

**Test Classes:**
- `TestCostBudgetEnforcement` - Main budget enforcement tests (7 tests)
- `TestCostBudgetEnforcementEdgeCases` - Edge cases (4 tests)

**Tests:**
1. `test_normal_operation_under_budget` - Normal operations stay under $0.50
2. `test_soft_warning_at_80_percent` - Soft warning at 80% of $5.00 session budget
3. `test_hard_stop_at_100_percent` - Hard stop at 100% of budget
4. `test_cost_override_for_auth_paths` - Auth/payment paths get $2-3 overrides
5. `test_session_cost_tracking_across_agents` - Accurate cost tracking across agents
6. `test_multiple_expensive_tasks_trigger_warning` - Multiple Sonnet tasks trigger warnings
7. `test_daily_budget_separate_from_session` - Daily vs session budget tracking
8. Edge cases: zero cost, negative cost, exact limit, small costs

**Total Tests:** 11 tests

### test_gemini_validation_flow.py
End-to-end test for Gemini agent's browser-based validation with screenshots.

**Test Classes:**
- `TestGeminiValidationFlow` - Main validation tests (10 tests)
- `TestValidationRubricBatchValidation` - Batch validation (1 test)

**Tests:**
1. `test_successful_validation_with_screenshots` - Successful test validation with screenshots
2. `test_failed_test_validation` - Failed test validation with error capture
3. `test_validation_timeout_handling` - Timeout handling with partial artifacts
4. `test_validation_rubric_schema_compliance` - Schema validation for all required fields
5. `test_console_errors_tracked_as_warnings` - Console errors logged but don't fail validation
6. `test_network_failures_tracked_as_warnings` - Network failures logged but don't fail validation
7. `test_screenshot_collection_from_artifacts` - Screenshot collection from artifacts directory
8. `test_browser_launch_failure` - Browser launch failure handling
9. `test_validation_with_multiple_test_suites` - Multiple test suites validation
10. `test_validation_partial_suite_failure` - Partial suite failure detection
11. `test_artifact_storage_paths` - Artifact directory structure validation
12. `test_batch_validation_multiple_results` - Batch validation of multiple test results

**Total Tests:** 11 tests

## Running Tests

### Run all integration tests
```bash
pytest tests/integration/ -v
```

### Run specific test file
```bash
pytest tests/integration/test_simple_crud_flow.py -v
```

### Run specific test with output
```bash
pytest tests/integration/test_simple_crud_flow.py::TestSimpleCRUDFlow::test_full_simple_crud_flow -v -s
```

### Run without coverage (faster)
```bash
pytest tests/integration/ -v --no-cov
```

## Test Coverage

### test_full_simple_crud_flow
Complete 7-step flow validation:
1. Kaya receives request
2. Router selects agent/model
3. Scribe generates test
4. Critic approves test
5. Runner executes test
6. Validates success criteria
7. Generates flow summary

**Success Criteria:**
- Cost < $0.50 ✓
- Execution < 2 minutes ✓
- Test file created ✓
- All artifacts collected ✓

### test_scribe_validation_retry_flow
Tests Scribe's self-validation and retry mechanism.

### test_state_management_flow
Validates Redis/Vector DB state tracking.

### test_cost_tracking_across_agents
Verifies cost accumulation across agents.

### test_error_handling_in_flow
Tests error handling and recovery.

### test_flow_meets_performance_targets
Validates performance targets for each step.

## Expected Results

All integration tests should pass:

```
tests/integration/test_simple_crud_flow.py::TestSimpleCRUDFlow::test_full_simple_crud_flow PASSED
tests/integration/test_simple_crud_flow.py::TestSimpleCRUDFlow::test_scribe_validation_retry_flow PASSED
tests/integration/test_simple_crud_flow.py::TestSimpleCRUDFlow::test_state_management_flow PASSED
tests/integration/test_simple_crud_flow.py::TestSimpleCRUDFlow::test_cost_tracking_across_agents PASSED
tests/integration/test_simple_crud_flow.py::TestSimpleCRUDFlow::test_error_handling_in_flow PASSED
tests/integration/test_simple_crud_flow.py::TestFlowPerformance::test_flow_meets_performance_targets PASSED

tests/integration/test_hitl_escalation_flow.py::TestHITLEscalationFlow::test_medic_escalates_after_max_retries PASSED
tests/integration/test_hitl_escalation_flow.py::TestHITLEscalationFlow::test_hitl_priority_calculation PASSED
tests/integration/test_hitl_escalation_flow.py::TestHITLEscalationFlow::test_human_resolution_with_annotation PASSED
tests/integration/test_hitl_escalation_flow.py::TestHITLEscalationFlow::test_annotation_retrieval_for_future_fixes PASSED
tests/integration/test_hitl_escalation_flow.py::TestHITLEscalationFlow::test_hitl_queue_listing_and_filtering PASSED
tests/integration/test_hitl_escalation_flow.py::TestHITLEscalationFlow::test_hitl_queue_stats PASSED

tests/integration/test_cost_budget_enforcement.py::TestCostBudgetEnforcement::test_normal_operation_under_budget PASSED
tests/integration/test_cost_budget_enforcement.py::TestCostBudgetEnforcement::test_soft_warning_at_80_percent PASSED
tests/integration/test_cost_budget_enforcement.py::TestCostBudgetEnforcement::test_hard_stop_at_100_percent PASSED
tests/integration/test_cost_budget_enforcement.py::TestCostBudgetEnforcement::test_cost_override_for_auth_paths PASSED
tests/integration/test_cost_budget_enforcement.py::TestCostBudgetEnforcement::test_session_cost_tracking_across_agents PASSED
tests/integration/test_cost_budget_enforcement.py::TestCostBudgetEnforcement::test_multiple_expensive_tasks_trigger_warning PASSED
tests/integration/test_cost_budget_enforcement.py::TestCostBudgetEnforcement::test_daily_budget_separate_from_session PASSED
tests/integration/test_cost_budget_enforcement.py::TestCostBudgetEnforcement::test_haiku_ratio_target PASSED
tests/integration/test_cost_budget_enforcement.py::TestCostBudgetEnforcementEdgeCases::test_zero_cost_operations PASSED
tests/integration/test_cost_budget_enforcement.py::TestCostBudgetEnforcementEdgeCases::test_negative_cost_handling PASSED
tests/integration/test_cost_budget_enforcement.py::TestCostBudgetEnforcementEdgeCases::test_exact_budget_limit PASSED
tests/integration/test_cost_budget_enforcement.py::TestCostBudgetEnforcementEdgeCases::test_very_small_costs PASSED

tests/integration/test_gemini_validation_flow.py::TestGeminiValidationFlow::test_successful_validation_with_screenshots PASSED
tests/integration/test_gemini_validation_flow.py::TestGeminiValidationFlow::test_failed_test_validation PASSED
tests/integration/test_gemini_validation_flow.py::TestGeminiValidationFlow::test_validation_timeout_handling PASSED
tests/integration/test_gemini_validation_flow.py::TestGeminiValidationFlow::test_validation_rubric_schema_compliance PASSED
tests/integration/test_gemini_validation_flow.py::TestGeminiValidationFlow::test_console_errors_tracked_as_warnings PASSED
tests/integration/test_gemini_validation_flow.py::TestGeminiValidationFlow::test_network_failures_tracked_as_warnings PASSED
tests/integration/test_gemini_validation_flow.py::TestGeminiValidationFlow::test_screenshot_collection_from_artifacts PASSED
tests/integration/test_gemini_validation_flow.py::TestGeminiValidationFlow::test_browser_launch_failure PASSED
tests/integration/test_gemini_validation_flow.py::TestGeminiValidationFlow::test_validation_with_multiple_test_suites PASSED
tests/integration/test_gemini_validation_flow.py::TestGeminiValidationFlow::test_validation_partial_suite_failure PASSED
tests/integration/test_gemini_validation_flow.py::TestGeminiValidationFlow::test_artifact_storage_paths PASSED
tests/integration/test_gemini_validation_flow.py::TestValidationRubricBatchValidation::test_batch_validation_multiple_results PASSED

============================== 34 passed in ~5s ===============================
```

## Implementation Notes

### Mocking Strategy
- External APIs (Anthropic, Gemini) are mocked to avoid costs
- Playwright execution is mocked for speed and reliability
- Redis and Vector DB clients are mocked for simplicity
- Real agent implementations are used to test coordination

### Temporary Files
Tests create temporary directories for test output files. These are automatically cleaned up after each test run.

### Flow Summary
Each test run generates a JSON summary with:
- Total cost and duration
- Agent routing decisions
- Artifacts from each agent
- Success criteria validation

## Troubleshooting

### Import Errors
Make sure you're using the virtual environment:
```bash
source venv/bin/activate
```

### Coverage Failures
If running with coverage, use `--no-cov` flag:
```bash
pytest tests/integration/ -v --no-cov
```

### Verbose Output
Add `-s` flag to see print statements:
```bash
pytest tests/integration/ -v -s
```

## Test Summary

Total integration tests: **86+ tests** across **9 test files**

### Coverage by Workflow
- **Full Pipeline (Master)**: 5 tests + references to 81 existing tests
- **Closed-Loop Workflow**: 4 tests
- **Simple CRUD Flow**: 6 tests
- **Critic Rejection Flow**: 11+ tests
- **Medic Regression Flow**: 12+ tests
- **HITL Escalation**: 6 tests
- **Cost Budget Enforcement**: 11 tests (including edge cases)
- **Gemini Validation**: 11 tests (including batch validation)
- **Router Integration**: 10+ tests

### Key Validations
1. Full agent pipeline coordination (Kaya → Scribe → Critic → Runner → Medic)
2. HITL escalation workflow with priority calculation and annotation storage
3. Cost budget enforcement with warnings, hard stops, and critical path overrides
4. Browser-based test validation with screenshot capture and rubric compliance
5. State management across Redis and Vector DB
6. Error handling and recovery mechanisms
7. Performance targets and optimization

## Next Steps

Future integration tests to add:
1. ✅ **Full Pipeline Master Test** - COMPLETED (test_full_pipeline.py)
2. 🚧 **State Persistence** - Requires Docker Redis container
3. 🚧 **Concurrent Features** - Requires async pipeline implementation
4. 🚧 **Voice Integration** - OpenAI Realtime API (requires API key)
5. 🚧 **Observability Dashboard** - WebSocket event streaming
6. 🚧 **Load Testing** - 10+ concurrent sessions with locust/k6

## See Also

- **[FULL_PIPELINE_TEST_GUIDE.md](FULL_PIPELINE_TEST_GUIDE.md)** - Comprehensive guide to pipeline testing ⭐
- [Integration Test Summary](../../INTEGRATION_TEST_SUMMARY.md) - Detailed results and analysis
- [Router Integration Tests](test_router_integration.py) - Router-specific tests
- [Unit Tests](../unit/) - Component-level tests
- [CLAUDE.md](../../CLAUDE.md) - Project overview and guidelines
