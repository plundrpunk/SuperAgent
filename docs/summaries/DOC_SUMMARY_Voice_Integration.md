# Documentation Summary: Voice Integration

This document summarizes the architecture, features, and usage of SuperAgent's voice control system.

---

## 1. Core Concept

SuperAgent's voice control enables users to manage the entire testing workflow through natural language commands. The system is built around the **OpenAI Realtime API**, which provides bidirectional audio streaming for both voice transcription (speech-to-text) and response synthesis (text-to-speech).

The central component is the **Voice Orchestrator** (`agent_system/voice/orchestrator.ts`), a TypeScript-based module that manages the WebSocket connection to OpenAI, handles audio buffering, and orchestrates the command-and-response loop.

### How It Works:
1.  The user speaks a command (e.g., `"Kaya, write a test for user login"`).
2.  The Voice Orchestrator streams the user's voice to the OpenAI Realtime API.
3.  OpenAI transcribes the speech to text.
4.  An **Intent Parser** within the orchestrator analyzes the transcribed text to identify the user's intent (e.g., `create_test`) and extracts key parameters, or "slots" (e.g., `feature: "user login"`).
5.  This structured intent is sent to the **Kaya** agent (the Python-based router).
6.  Kaya processes the command and returns a structured result.
7.  The Voice Orchestrator generates a user-friendly, natural language summary of Kaya's result.
8.  This text summary is sent back to the OpenAI Realtime API for **Text-to-Speech (TTS)** synthesis.
9.  The synthesized audio is streamed back and played to the user.

---

## 2. Key Features

-   **Intent Parsing**: The system uses regex patterns to recognize five core intents: `create_test`, `run_test`, `fix_failure`, `validate`, and `status`. It extracts necessary parameters (like file paths or feature descriptions) from the user's speech.

-   **Ambiguous Command Clarification**: If a command is unclear (e.g., `"Kaya, test something"`), the system will not proceed but will instead ask a clarifying question (e.g., `"Would you like me to create a test, run a test, or validate a test?"`).

-   **Real-Time Status Updates**: For long-running operations (over 10 seconds), Kaya provides periodic voice updates to the user (e.g., `"Still creating your test. About 90 seconds remaining."`). This prevents the user from feeling like the system has stalled.

-   **User Interruption**: Long-running operations can be canceled by saying `"Cancel that"` or `"Stop"`.

-   **Redis Transcript Storage**: All voice transcripts are automatically stored in Redis with a 1-hour TTL, providing a short-term memory of the conversation.

-   **Text-Based Fallback**: For development and debugging, a text-based chat interface is provided (`text_chat.js`) that bypasses the need for a microphone and audio output but uses the same underlying orchestration logic.

---

## 3. Getting Started

### Requirements:
-   **Node.js 18+**.
-   An **OpenAI API Key** with access to the Realtime API.
-   A microphone and speakers.

### Setup:
1.  Navigate to `agent_system/voice`.
2.  Run `npm install` to install Node.js dependencies.
3.  Create a `.env` file in the `voice` directory and add your `OPENAI_API_KEY`.
4.  Compile the TypeScript code with `npm run build`.
5.  Run an example script, such as `node dist/examples.js 1` or the interactive `node dist/text_chat.js`.

---

## 4. Voice Commands

All commands should be prefaced with the wake word **"Kaya"**.

-   **Create a test**: `"Kaya, write a test for [feature name]"`
-   **Run a test**: `"Kaya, run [path/to/test.spec.ts]"`
-   **Fix a failure**: `"Kaya, fix task [task_id]"`
-   **Validate a test**: `"Kaya, validate [test_path]"`
    -   Add `"- critical"` for high-priority validation.
-   **Check status**: `"Kaya, what's the status of [task_id]?"` or `"What are you working on?"`

---

## 5. Technical Details

-   **Audio Format**: The system uses **PCM16 @ 24kHz mono** for both input and output audio streams.
-   **TTS Voice**: The default text-to-speech voice is **"alloy"** from OpenAI, but this is configurable.
-   **State Management**: While voice transcripts are stored in Redis, the core agent and task state relies on the main Redis instance used by the Python backend. The documentation emphasizes the need to ensure Redis is running and accessible to both the Node.js voice system and the Python agent system.
