# SuperAgent Voice Commands Guide

Complete guide to voice-controlled test automation with SuperAgent.

## Table of Contents

1. [Introduction](#introduction)
2. [Prerequisites](#prerequisites)
3. [Getting Started](#getting-started)
4. [Supported Voice Intents](#supported-voice-intents)
5. [Advanced Usage](#advanced-usage)
6. [Troubleshooting](#troubleshooting)
7. [Best Practices](#best-practices)
8. [Examples](#examples)

---

## Introduction

### What is Voice Control in SuperAgent?

SuperAgent's voice control system enables you to manage your entire Playwright testing workflow using natural language voice commands. Instead of typing CLI commands or clicking through UIs, you can simply speak to Kaya (the orchestrator agent) to:

- Create new Playwright tests
- Execute existing tests
- Fix failing tests automatically
- Validate tests with visual browser automation
- Check task status and progress

### How It Works

```
┌─────────────────┐
│  Your Voice     │ "Kaya, write a test for user login"
└────────┬────────┘
         │
         v
┌─────────────────────────────────┐
│  OpenAI Realtime API            │ Speech-to-Text
│  (Voice Transcription)          │
└────────┬────────────────────────┘
         │
         v
┌─────────────────────────────────┐
│  Intent Parser                  │ Extract: create_test, feature="user login"
│  (Pattern Matching)             │
└────────┬────────────────────────┘
         │
         v
┌─────────────────────────────────┐
│  Kaya Orchestrator              │ Route to appropriate agent
│  (Router Agent)                 │
└────────┬────────────────────────┘
         │
         v
┌─────────────────────────────────┐
│  Specialized Agent              │ Execute task
│  (Scribe/Runner/Medic/Gemini)   │
└────────┬────────────────────────┘
         │
         v
┌─────────────────────────────────┐
│  Voice Response                 │ "I'm creating a test for user login..."
│  (Text-to-Speech)               │
└─────────────────────────────────┘
```

The system uses:
- **OpenAI Realtime API** for bidirectional voice streaming
- **Intent Parser** for natural language understanding
- **Kaya Router** for intelligent agent routing
- **Redis** for session state management

---

## Prerequisites

Before using voice commands, ensure you have:

### Required Software
- **Node.js 18+** - For voice orchestrator
- **Python 3.11+** - For agent system
- **Redis** - For state management (optional for voice-only mode)

### API Keys
- **OpenAI API Key** with Realtime API access
  - Get yours at: https://platform.openai.com/api-keys
  - Ensure your account has access to the Realtime API

### Hardware
- **Microphone** with clear audio input
- **Speakers/Headphones** for audio output
- Recommended: Quiet environment for best transcription accuracy

### Network
- Stable internet connection for WebSocket streaming
- Firewall must allow WebSocket connections to OpenAI

---

## Getting Started

### Step 1: Install Dependencies

```bash
cd /Users/rutledge/Documents/DevFolder/SuperAgent/agent_system/voice
npm install
```

### Step 2: Configure API Key

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and add your OpenAI API key
nano .env
```

Add to `.env`:
```env
OPENAI_API_KEY=sk-your-actual-api-key-here
```

### Step 3: Build the Voice Orchestrator

```bash
npm run build
```

### Step 4: Test Your Setup

```bash
# Load environment variables
export $(cat .env | xargs)

# Run the basic example
node dist/examples.js 1
```

If successful, you'll see:
```
Connected to OpenAI Realtime API
Session created: session_abc123
Ready for voice commands!
```

### Step 5: Try Your First Command

Speak clearly into your microphone:
```
"Kaya, write a test for user login"
```

You should hear Kaya respond with something like:
```
"I'm creating a test for user login using the Scribe agent.
This should take about 2 minutes. I'll let you know when it's done."
```

---

## Supported Voice Intents

SuperAgent recognizes five primary voice intents. Each intent has specific slots (parameters) that are extracted from your command.

### 1. Create Test

**Intent**: `create_test`

**Purpose**: Write new Playwright tests for specified features

**Slots**:
- `feature` (required): The feature or functionality to test
- `scope` (optional): Test scope - `happy_path`, `error_cases`, `edge_cases`

**Example Commands**:

```
Basic Commands:
- "Kaya, write a test for user login"
- "Create a test for checkout"
- "Generate a test for password reset"

With Scope Specification:
- "Write a test for shopping cart scope happy_path"
- "Create a test for payment processing scope error_cases"
- "Make a test about user registration scope edge_cases"

Natural Variations:
- "Test the shopping cart feature"
- "I need a test for the checkout flow"
- "Can you create a test about user authentication"
```

**What Happens**:
1. Command routed to **Scribe** agent (or Haiku for simple tests)
2. Scribe analyzes the feature requirements
3. Test written following Playwright best practices
4. Test saved to `tests/` directory
5. You receive voice confirmation with file path

**Response Example**:
```
"I'm creating a test for user login. The Scribe agent will use Claude Sonnet 4.5
since this involves authentication. Estimated time: 2-3 minutes. I'll save it to
tests/user_login.spec.ts."
```

---

### 2. Run Test

**Intent**: `run_test`

**Purpose**: Execute existing Playwright tests

**Slots**:
- `test_path` (required): Path to test file or test suite name

**Example Commands**:

```
With Full Path:
- "Kaya, run tests/cart.spec.ts"
- "Execute tests/authentication/login.spec.ts"
- "Start tests/checkout.spec.ts"

With Partial Name:
- "Run the login test"
- "Execute all authentication tests"
- "Start the checkout test"

Batch Execution:
- "Run all tests"
- "Execute the test suite"
- "Start all authentication tests"
```

**What Happens**:
1. Command routed to **Runner** agent (Claude Haiku)
2. Runner executes `npx playwright test <path>`
3. Output parsed for pass/fail status
4. Results reported with details (assertions, timing, errors)

**Response Examples**:

Success:
```
"Running tests/cart.spec.ts now. [pause] The test passed! All 5 assertions
verified successfully. Execution took 3.2 seconds."
```

Failure:
```
"The test failed. I found an error at line 42: Element with data-testid
'checkout-button' was not found. Would you like me to fix this?"
```

---

### 3. Fix Failure

**Intent**: `fix_failure`

**Purpose**: Automatically diagnose and fix failing tests

**Slots**:
- `task_id` (required): Task ID from HITL queue (format: `t_<id>`)

**Example Commands**:

```
With Task ID:
- "Kaya, fix task t_123"
- "Patch task t_abc456 and retry"
- "Repair task t_789"

With Test Description:
- "Fix the failed checkout test"
- "Repair the login failure"
- "Debug the payment test"
```

**What Happens**:
1. Command routed to **Medic** agent (Claude Sonnet 4.5)
2. Medic reads test code and error output
3. Minimal surgical fix applied
4. Regression tests run (baseline capture before fix)
5. Fix validated (no new failures allowed)
6. Results reported with diff and validation

**Response Example**:
```
"I'm analyzing the failure in task t_123. [pause] I found the issue - the selector
changed. I've updated the data-testid reference and running regression tests.
[pause] Fix successful! The test now passes, and no other tests were affected.
I've created a fix.diff file for your review."
```

**Important**: Medic follows the "Hippocratic Oath" - it will NEVER introduce new test failures. If a fix would break other tests, it will be rejected.

---

### 4. Validate

**Intent**: `validate`

**Purpose**: Validate test correctness using real browser automation with Gemini

**Slots**:
- `test_path` (required): Path to test file or feature name
- `high_priority` (optional): Flag for critical paths (enables higher cost limits)

**Example Commands**:

```
Standard Validation:
- "Kaya, validate tests/checkout.spec.ts"
- "Verify the login test"
- "Validate the authentication flow"

High-Priority Validation:
- "Validate payment flow - critical"
- "Verify checkout - high priority"
- "Validate authentication flow - important"

With Gemini Specification:
- "Validate checkout with Gemini"
- "Use Gemini to verify the payment test"
```

**What Happens**:
1. Test routed to **Critic** agent (pre-validation gatekeeper)
2. Critic checks for anti-patterns (flaky selectors, missing assertions)
3. If approved, routed to **Gemini** agent (Gemini 2.5 Pro)
4. Gemini launches real browser and executes test
5. Screenshots captured at each step
6. Validation rubric checked:
   - Browser launched successfully
   - Test executed without errors
   - Test passed all assertions
   - Screenshots captured
   - Execution time under 45 seconds
7. Visual evidence provided

**Response Example**:
```
"I'm validating tests/checkout.spec.ts. The Critic agent approved it for
validation. [pause] Gemini is now running the test in a real browser. [pause]
Validation successful! The test passed all assertions. I captured 7 screenshots
showing each step. The checkout flow works correctly. Total cost: $0.43."
```

**Cost Notes**:
- Standard validation: ~$0.40-0.60 per test
- High-priority validation: up to $2-3 (for auth/payment flows)
- Critic rejects 15-30% of tests pre-validation to save costs

---

### 5. Status

**Intent**: `status`

**Purpose**: Check status of tasks and agent activity

**Slots**:
- `task_id` (optional): Specific task to check (format: `t_<id>`)

**Example Commands**:

```
Specific Task:
- "Kaya, what's the status of task t_123?"
- "Show me task t_456"
- "What's happening with task t_789?"
- "Get status of task t_abc"

General Status:
- "What are you working on?"
- "Show me all active tasks"
- "What's the current status?"
```

**What Happens**:
1. Kaya queries Redis for task state
2. Returns status, progress, and agent assignment
3. For completed tasks: shows results and artifacts
4. For failed tasks: shows error details

**Response Examples**:

Active Task:
```
"Task t_123 is currently in progress. The Scribe agent is writing a test for
user login. Started 2 minutes ago. Estimated completion: 1 minute."
```

Completed Task:
```
"Task t_456 completed successfully 5 minutes ago. The Runner agent executed
tests/checkout.spec.ts. Result: Passed with 8 assertions verified.
Execution time: 4.3 seconds."
```

Failed Task:
```
"Task t_789 failed 10 minutes ago. The Medic agent attempted to fix a selector
issue but couldn't resolve it without manual intervention. It's now in the
HITL queue awaiting human review."
```

---

## Advanced Usage

### Chaining Commands

You can chain multiple commands in a natural conversation flow:

```
User: "Kaya, write a test for user login"
Kaya: "Creating test... Done! Saved to tests/user_login.spec.ts"

User: "Now run it"
Kaya: "Running tests/user_login.spec.ts... Test passed!"

User: "Great, now validate it - critical"
Kaya: "Validating with high priority... Validation successful!"
```

**Note**: The voice system maintains conversation context, so you can use references like "it", "that test", "the last one", etc.

### Handling Ambiguous Requests

If your command is ambiguous, Kaya will ask for clarification:

```
User: "Fix that test"
Kaya: "I can help fix a failed test. Could you provide the task ID?
       It should look like 't_123'."

User: "Fix t_123"
Kaya: "Got it, fixing task t_123 now..."
```

### Cost Optimization Tips

**Use High Priority Sparingly**:
- Standard validation: $0.40-0.60
- High-priority validation: $2-3
- Only use high priority for auth/payment/critical flows

```
Standard (most features):
"Validate the shopping cart test"

High Priority (critical paths):
"Validate payment processing - critical"
```

**Let Critic Filter First**:
The Critic agent (Haiku, cheap) filters out flaky tests before expensive Gemini validation. Trust this process - it saves 60-70% on validation costs.

**Batch Test Runs**:
Instead of running tests one-by-one, batch them:
```
"Run all authentication tests"  (more efficient)
vs
"Run login test" then "Run signup test" then "Run password reset test"  (wasteful)
```

### Session Management

Voice sessions automatically expire after 1 hour of inactivity. To start a new session:

```bash
# Reconnect
node dist/examples.js 1
```

Session state stored in Redis includes:
- Conversation history (last 10 messages)
- Active tasks
- Task results
- Voice transcripts

To clear session state:
```bash
# Clear Redis session data
python agent_system/voice/redis_cli.py clear-session <session_id>
```

---

## Troubleshooting

### Microphone Not Working

**Symptoms**: No transcription appears, Kaya doesn't respond

**Solutions**:
1. Check microphone permissions:
   ```bash
   # macOS
   System Preferences > Security & Privacy > Microphone
   # Ensure Terminal/Node has access
   ```

2. Test microphone input:
   ```bash
   # List audio devices
   node -e "console.log(require('os').platform())"

   # Test with example
   node dist/examples.js 2  # Audio streaming example
   ```

3. Verify audio format:
   - Required: PCM16, 24kHz, mono
   - Check your microphone settings match

4. Check for background noise:
   - Excessive noise can prevent activation
   - Try in a quieter environment

---

### Intent Not Recognized

**Symptoms**: Kaya responds with "I'm not sure what you want me to do"

**Solutions**:
1. **Speak clearly and slowly**:
   - Bad: "kayawriteatestforlogin"
   - Good: "Kaya, write a test for login"

2. **Use wake word**: Always start with "Kaya" or "Hey Kaya"

3. **Use supported patterns**: See [Supported Voice Intents](#supported-voice-intents)

4. **Break down complex requests**:
   - Bad: "Write and run a test for login then validate it if it passes"
   - Good: "Write a test for login" [wait] "Now run it" [wait] "Validate it"

5. **Check transcription**:
   ```bash
   # View transcription log in Redis
   python agent_system/voice/redis_cli.py get-transcript <session_id>
   ```

---

### Voice Transcripts in Redis

To debug transcription issues, check what the system heard:

```bash
# View recent transcripts
python agent_system/voice/redis_cli.py list-transcripts

# View specific session transcripts
python agent_system/voice/redis_cli.py get-transcript session_abc123
```

Example output:
```json
{
  "timestamp": "2025-10-14T10:23:45Z",
  "raw": "kaya write a test for user login",
  "normalized": "write a test for user login",
  "intent": {
    "type": "create_test",
    "slots": {
      "feature": "user login"
    },
    "confidence": 0.9
  }
}
```

---

### WebSocket Connection Failed

**Symptoms**: "Failed to connect to OpenAI Realtime API"

**Solutions**:
1. **Verify API key**:
   ```bash
   echo $OPENAI_API_KEY
   # Should output: sk-...
   ```

2. **Check API key validity**:
   ```bash
   curl https://api.openai.com/v1/models \
     -H "Authorization: Bearer $OPENAI_API_KEY"
   ```

3. **Verify Realtime API access**:
   - Not all OpenAI accounts have Realtime API access
   - Check your account at: https://platform.openai.com

4. **Check network/firewall**:
   ```bash
   # Test WebSocket connection
   node -e "new WebSocket('wss://api.openai.com/v1/realtime')"
   ```

5. **Check rate limits**:
   - Realtime API has rate limits
   - Wait a few minutes and retry

---

### Kaya Command Timeout

**Symptoms**: "Kaya command timed out after 30 seconds"

**Solutions**:
1. **Check Python environment**:
   ```bash
   which python3
   python3 --version  # Should be 3.11+
   ```

2. **Verify CLI path**:
   ```bash
   python3 /Users/rutledge/Documents/DevFolder/SuperAgent/agent_system/cli.py --help
   ```

3. **Increase timeout** (edit `orchestrator.ts`):
   ```typescript
   const KAYA_TIMEOUT_MS = 60000;  // Increase to 60 seconds
   ```

4. **Check for hung processes**:
   ```bash
   ps aux | grep python
   # Kill any stuck processes
   kill <pid>
   ```

---

### Audio Not Playing

**Symptoms**: Commands work but no voice response

**Solutions**:
1. **Verify audio output handler**:
   - Voice orchestrator emits `audio_complete` events
   - You must implement audio playback in your integration

2. **Check audio buffer**:
   ```typescript
   orchestrator.on('audio_complete', (buffer) => {
     console.log('Audio buffer size:', buffer.length);
     // Should be non-zero
   });
   ```

3. **Test with example**:
   ```bash
   node dist/examples.js 2  # Audio streaming example
   ```

4. **Check speaker/headphone connection**

---

### Debug Mode

Enable verbose logging to diagnose issues:

```bash
# Set debug environment variable
export DEBUG=superagent:voice:*

# Run with debug output
node dist/examples.js 1
```

You'll see detailed logs:
```
superagent:voice:connection Connected to WebSocket
superagent:voice:transcription Received: "kaya write a test for user login"
superagent:voice:intent Parsed intent: create_test
superagent:voice:kaya Executing command: create_test feature="user login"
superagent:voice:kaya Result: success
superagent:voice:response Synthesizing voice response...
```

---

## Best Practices

### Clear Pronunciation Tips

1. **Speak naturally, but clearly**:
   - Don't shout or whisper
   - Maintain consistent volume
   - Pause briefly between phrases

2. **Emphasize key information**:
   - Feature names: "write a test for USER LOGIN"
   - File paths: "run TESTS slash CART dot SPEC dot TS"
   - Task IDs: "fix task T underscore ONE TWO THREE"

3. **Use the wake word**: Always say "Kaya" to activate
   ```
   Good: "Kaya, write a test for login"
   Bad: "write a test for login"
   ```

4. **Avoid filler words**:
   ```
   Bad: "Kaya, um, can you like, maybe write a test for, uh, login"
   Good: "Kaya, write a test for login"
   ```

---

### When to Use CLI vs Voice

**Use Voice For**:
- Initial test creation (exploratory)
- Quick status checks
- Hands-free operation
- Demos and presentations
- Rapid iteration (create → run → fix → validate loop)

**Use CLI For**:
- Batch operations (100+ tests)
- CI/CD pipelines
- Precise control (complex flags)
- Scripting and automation
- When in noisy environment

**Hybrid Approach** (recommended):
```bash
# Use voice for creation
Voice: "Kaya, write a test for checkout"

# Use CLI for batch execution
CLI: npx playwright test tests/ --workers=4

# Use voice for validation
Voice: "Kaya, validate checkout - critical"
```

---

### Cost Implications of Voice Commands

Voice commands have minimal additional cost beyond the underlying agent operations:

**Voice-Specific Costs**:
- OpenAI Realtime API: ~$0.01-0.02 per minute of audio
- Transcription: Included in Realtime API
- Text-to-Speech: Included in Realtime API

**Total Cost Per Command**:
```
Create Test:
- Voice: $0.01
- Scribe agent: $0.15-0.40
- Total: $0.16-0.41

Run Test:
- Voice: $0.01
- Runner agent: $0.02
- Total: $0.03

Fix Failure:
- Voice: $0.01
- Medic agent: $0.20-0.50
- Total: $0.21-0.51

Validate (Standard):
- Voice: $0.01
- Critic: $0.02
- Gemini: $0.40
- Total: $0.43

Validate (High Priority):
- Voice: $0.01
- Critic: $0.02
- Gemini: $1.50-2.50
- Total: $1.53-2.53
```

**Cost Optimization**:
1. Use standard validation for most tests
2. Reserve high-priority for auth/payment flows
3. Let Critic reject flaky tests before Gemini
4. Batch test runs when possible

---

## Examples

### Example 1: Full Test Creation Flow

```
User: "Hey Kaya, write a test for user registration"

Kaya: "I'm creating a test for user registration. I'll use the Scribe agent
       with Claude Sonnet 4.5. This should take about 2-3 minutes."

[2 minutes later]

Kaya: "Test creation complete! I've saved it to tests/user_registration.spec.ts.
       The test covers the happy path with 6 assertions. Would you like me to
       run it?"

User: "Yes, run it"

Kaya: "Running tests/user_registration.spec.ts now."

[5 seconds later]

Kaya: "The test passed! All 6 assertions verified successfully. Execution took
       3.8 seconds."

User: "Great, now validate it"

Kaya: "I'm validating the test now. The Critic agent approved it for validation.
       Gemini is launching a browser to verify correctness."

[30 seconds later]

Kaya: "Validation successful! The test passed in a real browser. I captured
       8 screenshots showing each registration step. The form submission works
       correctly. Total validation cost: $0.44."
```

---

### Example 2: Debugging a Failure

```
User: "Kaya, run tests/checkout.spec.ts"

Kaya: "Running tests/checkout.spec.ts now."

[5 seconds later]

Kaya: "The test failed. I found an error at line 42: Timeout waiting for element
       with data-testid 'checkout-button'. The element was not found after 30
       seconds. This is task t_abc123. Would you like me to fix it?"

User: "Yes, fix task t_abc123"

Kaya: "I'm analyzing the failure now using the Medic agent."

[1 minute later]

Kaya: "I found the issue. The checkout button selector changed from
       'checkout-button' to 'checkout-submit-btn'. I've updated the test and
       I'm running regression tests to ensure no other tests broke."

[10 seconds later]

Kaya: "Fix successful! The test now passes, and all regression tests passed.
       No new failures introduced. I've created a fix.diff file at
       tests/checkout.spec.ts.diff for your review."

User: "Perfect, validate it - critical"

Kaya: "I'm validating the checkout test with high priority since it's marked
       critical. Gemini is running the full checkout flow in a real browser."

[40 seconds later]

Kaya: "Validation successful! The checkout flow works correctly end-to-end.
       I captured 12 screenshots showing each step including payment submission.
       Total validation cost: $2.15."
```

---

### Example 3: Status Checking

```
User: "Kaya, what are you working on?"

Kaya: "I have 3 active tasks:
       - Task t_abc123: Scribe is writing a test for password reset (started
         1 minute ago, 70% complete)
       - Task t_def456: Runner is executing tests/cart.spec.ts (started
         10 seconds ago)
       - Task t_ghi789: Gemini is validating tests/payment.spec.ts (started
         30 seconds ago)"

[2 minutes later]

User: "Kaya, what's the status of task t_abc123?"

Kaya: "Task t_abc123 completed successfully 30 seconds ago. The Scribe agent
       wrote a test for password reset and saved it to
       tests/auth/password_reset.spec.ts. The test includes 4 test cases:
       happy path, invalid email, expired token, and weak password validation.
       Total time: 2 minutes 15 seconds. Cost: $0.38."
```

---

### Example 4: Handling Ambiguous Commands

```
User: "Kaya, fix that test"

Kaya: "I can help fix a failed test. Could you provide the task ID? It should
       look like 't_123'. You can also say 'show me all failed tasks' to see
       the list."

User: "Show me all failed tasks"

Kaya: "I have 2 failed tasks:
       - Task t_xyz789: tests/login.spec.ts failed with selector not found error
         (failed 5 minutes ago)
       - Task t_uvw456: tests/checkout.spec.ts failed with timeout error
         (failed 15 minutes ago)"

User: "Fix task t_xyz789"

Kaya: "Got it, fixing task t_xyz789 now. The Medic agent is analyzing the
       selector error in tests/login.spec.ts..."
```

---

### Example 5: High-Priority Validation

```
User: "Kaya, write a test for payment processing"

Kaya: "I'm creating a test for payment processing. Since this involves payment
       functionality, I'll use the Scribe agent with Claude Sonnet 4.5 and apply
       strict validation. This should take about 3-4 minutes."

[3 minutes later]

Kaya: "Test creation complete! I've saved it to tests/payment/processing.spec.ts.
       The test covers credit card submission, validation, and success confirmation.
       I included mock payment gateway responses. Would you like me to validate
       it with high priority?"

User: "Yes, validate it - critical"

Kaya: "I'm validating the payment test with high priority. The Critic agent
       approved it. Gemini is now running the test with extended timeout and
       detailed screenshot capture for each payment step."

[50 seconds later]

Kaya: "Validation successful! The payment flow works correctly. I captured
       15 screenshots showing:
       - Payment form display
       - Credit card input validation
       - CVV field masking
       - Submit button click
       - Loading state
       - Success confirmation

       All assertions passed. Network requests were properly mocked. Total
       validation cost: $2.28. This exceeds the standard budget but was approved
       for critical payment functionality."
```

---

## Additional Resources

### Documentation
- [Voice Quick Reference](/Users/rutledge/Documents/DevFolder/SuperAgent/docs/VOICE_QUICK_REFERENCE.md) - 1-page cheat sheet
- [Voice Orchestrator README](/Users/rutledge/Documents/DevFolder/SuperAgent/agent_system/voice/README.md) - Technical details
- [Main Documentation](/Users/rutledge/Documents/DevFolder/SuperAgent/README.md) - Full system overview

### Technical References
- [OpenAI Realtime API Docs](https://platform.openai.com/docs/guides/realtime)
- [Intent Parser Source](/Users/rutledge/Documents/DevFolder/SuperAgent/agent_system/voice/intent_parser.py)
- [Kaya Agent Definition](/Users/rutledge/Documents/DevFolder/SuperAgent/.claude/agents/kaya.yaml)

### Support
- **Check transcription logs**: `python agent_system/voice/redis_cli.py list-transcripts`
- **Enable debug mode**: `export DEBUG=superagent:voice:*`
- **View agent logs**: Check `/Users/rutledge/Documents/DevFolder/SuperAgent/logs/`

---

## FAQ

**Q: Can I use voice commands in CI/CD?**
A: Not recommended. Voice commands are designed for interactive development. Use the CLI for CI/CD pipelines.

**Q: How do I cancel a running task?**
A: Say "Kaya, cancel task t_123" or press Ctrl+C in the terminal.

**Q: Can I use voice commands offline?**
A: No. Voice commands require an internet connection for OpenAI Realtime API access.

**Q: How long does voice session history persist?**
A: Session history is stored in Redis for 1 hour. After that, context is cleared.

**Q: Can I customize Kaya's voice?**
A: Yes. Edit `voice/orchestrator.ts` and change the `voice` parameter to 'alloy', 'echo', or 'shimmer'.

**Q: What languages are supported?**
A: Currently English only. The intent parser is trained on English patterns.

**Q: Can I add custom voice intents?**
A: Yes. Edit `voice/intent_parser.py` and add new patterns to the `INTENT_PATTERNS` list.

**Q: How accurate is the transcription?**
A: OpenAI Realtime API has ~95% accuracy in quiet environments. Accuracy decreases with background noise.

**Q: Can multiple users use voice commands simultaneously?**
A: Yes, but each user needs their own session. Sessions are isolated by session_id.

---

**Happy voice testing!** For questions or issues, check the [Troubleshooting](#troubleshooting) section or enable debug mode for detailed logs.
