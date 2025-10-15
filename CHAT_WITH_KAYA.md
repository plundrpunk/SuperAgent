# 💬 Chat with Kaya - Text Interface

## 🚀 Start Chatting NOW (Local Setup - No Docker Needed!)

### Option 1: Interactive Text Chat

```bash
cd /Users/rutledge/Documents/DevFolder/SuperAgent/agent_system/voice
REDIS_HOST=localhost node dist/text_chat.js
```

### Option 2: Live Demo (Actually Generates Tests!)

```bash
cd /Users/rutledge/Documents/DevFolder/SuperAgent/agent_system/voice
REDIS_HOST=localhost node dist/kaya_live_demo.js
```

**Note**: We're using `REDIS_HOST=localhost` to bypass Docker and use your local system directly.

## ✅ What This Does

The live demo will:
1. Connect to OpenAI Realtime API
2. Execute Kaya commands to generate tests
3. Show real test generation for Cloppy_Ai:
   - Board creation test
   - File upload test
4. Save tests to `/Users/rutledge/Documents/DevFolder/SuperAgent/tests/`
5. Show costs and execution time

## 💬 Interactive Chat Interface

When you run `text_chat.js`, you'll see:

```
🤖 SuperAgent - Talk to Kaya (Text Mode)
============================================================
✓ OpenAI API key found
✓ Connecting to OpenAI Realtime API...

✅ Connected!

============================================================
You can now talk to Kaya!
============================================================

Examples:
  • "write a test for Cloppy AI authentication"
  • "run tests/auth.spec.ts"
  • "what's the status?"
  • "validate the login flow - critical"

Type "exit" to quit

You: _
```

## 🎯 What to Type

### Generate Tests
```
You: write a test for Cloppy AI's authentication
```

Response:
```
📝 Transcribed: "write a test for Cloppy AI's authentication"

🤖 Kaya Response:
{
  "success": true,
  "agent": "scribe",
  "model": "claude-sonnet-4-20250514",
  "test_path": "tests/cloppy_ai_auth.spec.ts",
  "cost_usd": 0.045,
  "duration_ms": 8234
}

I've generated a test for Cloppy AI authentication using the Scribe agent.
The test is saved at tests/cloppy_ai_auth.spec.ts and cost $0.045.

────────────────────────────────────────────────────────────
You: _
```

### Run Tests
```
You: run the auth test
```

### Check Status
```
You: what's happening?
```

### Validate with Browser
```
You: validate the login flow - critical
```

## 🎤 Why No Audio?

The voice orchestrator receives audio as **raw PCM data** from OpenAI, but:
- Playing audio requires a media library (not included)
- Text responses work perfectly and show everything!
- You can see all transcriptions and results in text
- Faster than audio
- No microphone needed

## 💡 This Is Better!

Text mode is actually **better for development**:
- See exact responses
- Copy/paste commands
- Review conversation history
- Faster than audio

## 🔧 Troubleshooting

If you get "Cannot connect to Redis":
- Make sure you're using `REDIS_HOST=localhost` before the node command
- Or start Redis via Docker (if it's built): `docker compose up redis -d`

## 🚀 Try It Now!

```bash
cd /Users/rutledge/Documents/DevFolder/SuperAgent/agent_system/voice
REDIS_HOST=localhost node dist/text_chat.js
```

Then type: **"write a test for Cloppy AI authentication"**

Watch Kaya respond in real-time! 🎉
