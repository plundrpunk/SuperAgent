# Documentation Summary: Project Overview & Guides

This document summarizes the core purpose, setup, and usage of the SuperAgent system based on the primary getting-started guides.

---

## 1. Core Concept

**SuperAgent** is a Voice-Controlled Multi-Agent Testing System. Its primary purpose is to automate the entire Playwright testing lifecycle—creation, execution, validation, and bug-fixing—using a team of specialized AI agents. The main interface for commands is an orchestrator agent named **Kaya**.

---

## 2. System Status & Requirements

- **Status**: The system is described as fully operational and ready for its mission.
- **Python**: Requires Python 3.10+ (3.11+ recommended).
- **Node.js**: Requires Node.js 16+ for Playwright and voice components.
- **Docker**: Required for the standard, service-based setup.
- **Redis**: Required for state management (task queues, session data). Can be run via Docker or locally (`brew services start redis`).
- **API Keys**: At a minimum, an **Anthropic API key** is required. For full functionality, OpenAI (for voice) and Gemini (for validation) keys are also needed.

---

## 3. Quick Start & Setup

There are two main ways to run the system: **Standalone** (local machine) and **Docker** (recommended).

### Step 1: Configure API Keys
- Create a `.env` file from `.env.example`.
- Add your `ANTHROPIC_API_KEY`. Add `OPENAI_API_KEY` and `GEMINI_API_KEY` for voice and validation features.

### Step 2: Install Dependencies
- Create and activate a Python virtual environment: `python3.11 -m venv venv` and `source venv/bin/activate`.
- Install Python packages: `pip install -r requirements.txt`.
- Install Playwright browsers: `npx playwright install chromium`.

### Step 3: Start Services
- **Recommended (Docker)**: Use `docker compose up -d` to start the SuperAgent application container and its Redis dependency.
- **Local/Standalone**: Ensure Redis is running locally (`redis-server --daemonize yes`).

### Step 4: Verify Installation
- Use the CLI to check the system status: `python agent_system/cli.py status`.

---

## 4. How to Interact with Kaya (The Orchestrator Agent)

Kaya is the main entry point for all commands. You can interact with Kaya in several ways:

1.  **GUI Quick Access (Newest Feature)**:
    - Run `python3 kaya_quick_access.py`.
    - Provides an always-on-top UI to issue text commands (or use `Ctrl+Shift+K`).

2.  **Direct CLI (For Automation)**:
    - The most direct way to issue a command.
    - Example: `python agent_system/cli.py kaya "write a test for user login"`

3.  **Text Chat Interface**:
    - An interactive, real-time chat session.
    - Run: `cd agent_system/voice && REDIS_HOST=localhost node dist/text_chat.js`

4.  **Voice Session**:
    - For actual voice commands (requires microphone).
    - Run: `cd agent_system/voice && node dist/examples.js`

---

## 5. Core Commands

The system understands a variety of commands given to Kaya, from simple tasks to complex missions.

- **Generate a Test**: `kaya "write a test for <feature>"`
- **Run a Test**: `kaya "run tests/<file>.spec.ts"`
- **Review a Test**: `review tests/<file>.spec.ts` (Uses the Critic agent for quality checks).
- **Check System Status**: `status`
- **Check Costs**: `cost daily` or `cost budget`
- **Execute a Full Mission**: `kaya "execute the mission"` (A fully autonomous mode to fix the entire test suite).
- **Fix Failures**: `kaya "fix all test failures"`

---

## 6. Key Technical Concepts for New Users

- **Agent Roles**: The system is composed of specialized agents (Kaya, Scribe, Runner, Medic, Critic, Gemini), each with a specific role. This is detailed in `CLAUDE.md` and `README.md`.
- **Cost Management**: The system is designed to be cost-effective, primarily using Claude Haiku for simple tasks and switching to more powerful models (Sonnet, Opus) for complex ones. Budgets are enforced.
- **State Management**: A "hot state" is kept in Redis for active tasks (1-hour TTL), while a "cold state" for long-term memory (like successful test patterns) is stored in a Vector DB.
- **Troubleshooting**: The primary troubleshooting step for test failures is to ensure the target application's servers (backend and frontend) are running before executing tests. The main `TROUBLESHOOTING.md` file contains detailed guides for various issues.
