# Documentation Summary: Architecture & Agent System

This document summarizes the SuperAgent system's architecture, its core principles, and the roles of its specialized agents.

---

## 1. High-Level Architecture

SuperAgent is a multi-agent system designed to automate the Playwright testing lifecycle. It operates on a principle of **specialization**, where each agent has a single, well-defined responsibility.

The typical workflow is orchestrated by **Kaya**, the router agent, who receives a user command and dispatches it to the appropriate specialist agent.

### Core Principles:
- **Specialization**: Each agent (Scribe, Runner, Medic, etc.) is an expert at its one job.
- **Cost Optimization**: The system defaults to cheaper, faster models (like Claude Haiku) for simple tasks and only uses more powerful models (like Claude Sonnet or Gemini Pro) for complex work like test generation, bug fixing, and final validation.
- **Quality Gates**: A multi-stage validation pipeline (Critic -> Runner -> Gemini) is used to ensure test quality before committing.
- **Human-in-the-Loop (HITL)**: The system has a built-in mechanism to escalate tasks to a human operator if an agent fails repeatedly.

### Technology Stack:
- **Backend**: Python 3.11+, using Anthropic and Google Gemini models.
- **State Management**: Redis for "hot" session data (1-hour TTL) and a Vector DB (ChromaDB) for "cold" long-term memory like successful test patterns and bug fixes.
- **Testing Framework**: Playwright with TypeScript.
- **Infrastructure**: Docker and Docker Compose for containerization.

---

## 2. The Agent Team

The system is composed of six primary agents:

1.  **Kaya (Orchestrator/Router)**:
    - The brain of the operation. Parses user commands, estimates task complexity, selects the appropriate agent and model, and monitors the budget.
    - Primarily uses **Claude Haiku**.

2.  **Scribe (Test Writer)**:
    - Responsible for generating new Playwright test code.
    - Uses Retrieval-Augmented Generation (RAG) by searching the Vector DB for successful test patterns.
    - Primarily uses **Claude Sonnet**.

3.  **Runner (Test Executor)**:
    - A simple agent that executes Playwright tests in a subprocess.
    - It parses the test output to determine pass/fail status and extracts error messages.
    - Uses **Claude Haiku**.

4.  **Critic (Pre-Validator)**:
    - Acts as a fast, cheap quality gate. It performs static analysis on test code to check for anti-patterns (e.g., flaky selectors like `.nth()`, missing assertions, fixed waits) before allowing a test to proceed to more expensive validation stages.
    - Uses **Claude Haiku**.

5.  **Medic (Bug Fixer)**:
    - Attempts to automatically fix failing tests. It uses the error message from the Runner and searches the Vector DB for similar, previously successful fixes.
    - Adheres to a "Hippocratic Oath": it must run regression tests to ensure its fixes do not introduce new bugs.
    - Uses **Claude Sonnet**.

6.  **Gemini (Validator)**:
    - The final arbiter of correctness. It runs a test in a real (headed or headless) browser to prove it works as intended, capturing screenshots as visual evidence.
    - Uses **Gemini 2.5 Pro**.

---

## 3. Agent Interaction Patterns

SuperAgent currently uses an **Iterative Loop** for its primary workflow, which is distinct from the recursive agent spawning seen in other systems like Claude Code.

### Iterative Loop (Current Implementation):
- **Process**: A linear, sequential workflow (e.g., `Kaya -> Runner -> Medic -> Runner`).
- **Depth**: Fixed number of iterations (e.g., a maximum of 5 attempts to fix a test).
- **Control**: Kaya remains the central controller.

### Recursive Spawning (A Potential Future Pattern):
- **Process**: A hierarchical, tree-like structure where agents can dynamically spawn other sub-agents to perform parallel tasks (e.g., research, code generation, and validation all happening at once).
- **Use Case**: Best for complex, research-heavy tasks, but adds significant complexity and cost.
- **Current Status**: Not implemented in SuperAgent. The current iterative loop is considered more efficient and debuggable for the defined task of test-fixing.

---

## 4. Mission Objective

The primary mission defined in the documentation is to **achieve a 100% pass rate for the 207 P0 critical tests** for the "Cloppy_AI" application. The system is given full autonomy to run tests, identify failures, dispatch agents to fix them, and repeat the cycle until the objective is met.
