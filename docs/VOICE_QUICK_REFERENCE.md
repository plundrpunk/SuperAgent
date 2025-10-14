# SuperAgent Voice Commands - Quick Reference

One-page cheat sheet for voice-controlled testing.

---

## Setup (5 minutes)

```bash
cd agent_system/voice
npm install
cp .env.example .env
# Add OPENAI_API_KEY to .env
npm run build
export $(cat .env | xargs)
node dist/examples.js 1
```

---

## Voice Command Patterns

### Create Test
**Pattern**: `Kaya, write a test for <feature>`

```
"Kaya, write a test for user login"
"Create a test for checkout happy path"
"Generate a test for password reset"
```

**Agent**: Scribe | **Cost**: $0.16-0.41 | **Time**: 2-3 min

---

### Run Test
**Pattern**: `Kaya, run <test_path>`

```
"Kaya, run tests/cart.spec.ts"
"Execute the login test"
"Run all authentication tests"
```

**Agent**: Runner | **Cost**: $0.03 | **Time**: 5-10 sec

---

### Fix Failure
**Pattern**: `Kaya, fix task <task_id>`

```
"Kaya, fix task t_123"
"Patch task t_abc456 and retry"
"Fix the failed checkout test"
```

**Agent**: Medic | **Cost**: $0.21-0.51 | **Time**: 1-2 min

---

### Validate
**Pattern**: `Kaya, validate <test_path> [- critical]`

```
"Kaya, validate tests/checkout.spec.ts"
"Validate payment flow - critical"
"Verify the login test"
```

**Agent**: Critic → Gemini | **Cost**: $0.43 (standard), $1.50-2.50 (critical) | **Time**: 30-50 sec

---

### Status
**Pattern**: `Kaya, what's the status of <task_id>`

```
"Kaya, what's the status of task t_123?"
"Show me all active tasks"
"What are you working on?"
```

**Agent**: Kaya | **Cost**: $0.01 | **Time**: Instant

---

## Quick Troubleshooting

| Issue | Solution |
|-------|----------|
| No transcription | Check mic permissions, verify audio format (PCM16, 24kHz) |
| "Intent not recognized" | Speak clearly, use wake word "Kaya", check supported patterns |
| WebSocket failed | Verify `OPENAI_API_KEY`, check Realtime API access |
| Command timeout | Check Python path, increase timeout in `orchestrator.ts` |
| No audio output | Implement audio playback handler, check speaker connection |

**Debug Mode**: `export DEBUG=superagent:voice:*`

**Check Transcripts**: `python agent_system/voice/redis_cli.py list-transcripts`

---

## Cost Optimization

| Command Type | Standard Cost | High-Priority Cost |
|--------------|---------------|-------------------|
| Create Test | $0.16-0.41 | N/A |
| Run Test | $0.03 | N/A |
| Fix Failure | $0.21-0.51 | N/A |
| Validate | $0.43 | $1.53-2.53 |

**Tips**:
- Use standard validation for most tests
- Reserve high-priority for auth/payment flows
- Let Critic filter flaky tests (saves 60-70%)
- Batch test runs when possible

---

## Full Workflow Example

```
User: "Kaya, write a test for user login"
Kaya: "Creating test... [2 min] Done! Saved to tests/user_login.spec.ts"

User: "Now run it"
Kaya: "Running... [5 sec] Test passed! 5 assertions verified."

User: "Validate it"
Kaya: "Validating... [35 sec] Success! Captured 7 screenshots. Cost: $0.44"
```

**Total Time**: 3 minutes | **Total Cost**: $0.60

---

## Best Practices

**DO**:
- Always use wake word "Kaya"
- Speak clearly and naturally
- Wait for response before next command
- Use high-priority only for critical paths
- Check status before re-running commands

**DON'T**:
- Shout or whisper
- Use filler words ("um", "like", "uh")
- Chain complex multi-step commands
- Use voice for batch operations (100+ tests)
- Use in noisy environments

---

## Intent Slot Reference

| Intent | Required Slots | Optional Slots |
|--------|---------------|----------------|
| create_test | feature | scope (happy_path, error_cases, edge_cases) |
| run_test | test_path | - |
| fix_failure | task_id | - |
| validate | test_path | high_priority (critical, important) |
| status | - | task_id |

---

## Common Phrases

### Starting
- "Hey Kaya" or "Kaya"
- Always use wake word

### Confirming
- "Yes" / "Sure" / "Go ahead"
- "Run it" / "Fix it" / "Validate it"

### Status Checking
- "What's happening?"
- "Show me the status"
- "What are you working on?"

### Canceling
- "Cancel that"
- "Stop" / "Never mind"
- Or press Ctrl+C

---

## Resources

**Full Guide**: `/docs/VOICE_COMMANDS_GUIDE.md`

**Technical Docs**: `/agent_system/voice/README.md`

**OpenAI API**: https://platform.openai.com/docs/guides/realtime

**Debug Logs**: `export DEBUG=superagent:voice:*`

---

## API Configuration

Edit `agent_system/voice/orchestrator.ts`:

```typescript
{
  apiKey: process.env.OPENAI_API_KEY,
  model: 'gpt-4o-realtime-preview',
  voice: 'alloy',  // Options: alloy, echo, shimmer
  temperature: 0.8,
  max_response_tokens: 4096
}
```

---

## Session Management

**Session Duration**: 1 hour (auto-expire)

**Clear Session**:
```bash
python agent_system/voice/redis_cli.py clear-session <session_id>
```

**View Session History**:
```bash
python agent_system/voice/redis_cli.py get-transcript <session_id>
```

---

**For detailed information, see the full Voice Commands Guide at `/docs/VOICE_COMMANDS_GUIDE.md`**
