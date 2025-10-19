# Documentation Summary: Testing

This document summarizes the testing strategy, test suites, and performance metrics for the SuperAgent system.

---

## 1. Testing Philosophy & Strategy

The project employs a multi-layered testing strategy that combines unit tests, comprehensive integration tests, and load tests to ensure the reliability, correctness, and performance of the multi-agent system.

-   **Unit Tests**: Focused on individual components and functions in isolation.
-   **Integration Tests**: Validate the coordination and data flow between multiple agents in realistic workflows.
-   **End-to-End (E2E) Tests**: Test the full application pipeline, from user command to final output.
-   **Load Tests**: Measure the system's performance and stability under concurrent load.

All tests are heavily reliant on **mocking** for external dependencies (AI models, Playwright execution, databases) to ensure tests are fast, deterministic, and cost-free.

---

## 2. Key Test Suites

The testing structure is centered around a series of detailed integration and E2E test files.

### `test_full_pipeline.py` (Master Test)
-   This is the main orchestration test that validates the complete, end-to-end "happy path" workflow: **Scribe -> Critic -> Runner -> Gemini**.
-   It uses a `PipelineTestHarness` class to manage setup, execution, and assertions.
-   It also serves as a master guide, referencing and integrating the scenarios covered in other, more specific test files.

### `test_closed_loop.py`
-   Focuses on the failure recovery and self-healing capabilities.
-   **Key Scenario**: A test fails validation, the **Medic** agent is invoked to fix it, and the test is then successfully re-validated.
-   It also tests the **HITL (Human-in-the-Loop) escalation** triggers, such as when the Medic agent fails to fix a bug after multiple retries or when its fix introduces a regression.

### `test_gemini_validation_flow.py`
-   Dedicated to the **Gemini** agent's validation process.
-   It verifies that the agent correctly launches a browser, captures screenshots, and evaluates the results against the strict **Validation Rubric** (e.g., must have >= 1 screenshot, execution time < 45s).
-   It also confirms that console and network errors are correctly identified as warnings, not hard failures.

### `test_scribe_full.py` & `test_scribe_validation.py`
-   These files contain a large number of unit and integration tests (38+) specifically for the **Scribe** agent.
-   They validate Scribe's self-validation and auto-retry logic, ensuring it catches its own mistakes (like using flaky selectors or forgetting assertions) before passing the test to the Critic.

### `test_cost_budget_enforcement.py`
-   Focuses on the system's financial guardrails.
-   It tests that the **Router** correctly enforces the per-feature and per-session budgets, issues warnings at 80% usage, and performs a hard stop at 100%.
-   It also validates the critical path override, where features like "authentication" or "payment" are granted a higher budget.

### `test_load_concurrent_features.py`
-   This is the primary load testing suite.
-   It runs tests for multiple simple and complex features in parallel (e.g., 10 concurrent requests) to measure latency and throughput under load.
-   It also includes stress tests for the Redis connection pool and concurrent write operations to the Vector DB.

---

## 3. Performance & Optimization

The `PERFORMANCE_REPORT.md` and `LOAD_TESTING_QUICK_START.md` documents detail the system's performance and the optimizations that have been implemented.

### Key Performance Metrics:
-   **Router/Complexity Estimator**: Extremely fast, capable of over 44,000 requests per second (rps).
-   **Scribe Agent**: Excellent performance, with a P95 latency of ~257ms for 10 concurrent requests.
-   **Primary Bottleneck**: The main performance bottleneck identified was the **vector embedding generation** for the RAG system, which is a CPU-bound task.

### Implemented Optimizations:
-   **Redis Connection Pooling**: The connection pool was increased to handle higher concurrency.
-   **Batch Embedding**: The system now batches requests for vector embeddings, significantly speeding up the process for concurrent tasks.
-   **Router Caching**: Routing decisions are now cached (LRU cache) to avoid re-calculating complexity for repeated requests.
-   **Buffered Cost Logging**: Cost tracking writes are buffered and flushed periodically, turning a synchronous I/O operation into a non-blocking one.
-   **Agent Pooling**: Pre-initialized agent instances are kept in a pool to eliminate the 80-350ms startup time for each agent.

**Overall Impact**: The combined optimizations resulted in a **4.3x speedup** for concurrent operations.
