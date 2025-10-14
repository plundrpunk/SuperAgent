# SuperAgent Voice Orchestrator

OpenAI Realtime API integration for voice-controlled multi-agent testing system.

## Overview

The Voice Orchestrator enables natural language voice control of SuperAgent's multi-agent testing system. Users can speak commands like "Kaya, write a test for user login" and receive spoken responses about the test creation, execution, and validation process.

## Features

- **WebSocket Connection**: Maintains persistent connection to OpenAI Realtime API
- **Audio Streaming**: Bidirectional audio streaming for voice input/output
- **Voice Transcription**: Automatic speech-to-text conversion
- **Intent Parsing**: Extracts structured commands from natural language
- **Kaya Integration**: Routes commands to Kaya orchestrator agent
- **Voice Synthesis**: Converts agent responses back to speech
- **Reconnection Logic**: Automatic reconnection with exponential backoff
- **Event System**: Rich event emitters for integration and monitoring

## Installation

```bash
cd agent_system/voice
npm install
```

## Configuration

Create a `.env` file in the `voice` directory:

```env
OPENAI_API_KEY=your_api_key_here
```

## TypeScript Compilation

```bash
# Build once
npm run build

# Watch mode for development
npm run dev
```

## Usage

### Basic Example

```typescript
import VoiceOrchestrator from './orchestrator';

const orchestrator = new VoiceOrchestrator({
  apiKey: process.env.OPENAI_API_KEY!,
  voice: 'alloy',
  temperature: 0.8
});

// Set up event listeners
orchestrator.on('connected', () => {
  console.log('Ready for voice commands!');
});

orchestrator.on('transcription', (text) => {
  console.log('User said:', text);
});

orchestrator.on('kaya_result', (result) => {
  console.log('Kaya processed:', result);
});

orchestrator.on('audio_complete', (audioBuffer) => {
  // Play audio to user
  playAudio(audioBuffer);
});

// Connect
await orchestrator.connect();
```

### Streaming Audio Input

```typescript
// From microphone or audio source
const audioStream = getMicrophoneStream();

audioStream.on('data', (chunk) => {
  orchestrator.streamAudioInput(chunk);
});

// When user stops speaking
orchestrator.commitAudioInput();
```

### Text-Based Commands

```typescript
// Send text command instead of voice
orchestrator.addMessage('user', 'Kaya, write a test for checkout');
orchestrator.createResponse();
```

## Supported Voice Intents

### 1. Create Test
**Intent**: `create_test`
**Example Commands**:
- "Kaya, write a test for user login"
- "Create a test for the checkout happy path"
- "Generate a test for password reset"

**Response**: Routes to Scribe agent for test creation

---

### 2. Run Test
**Intent**: `run_test`
**Example Commands**:
- "Kaya, run tests/cart.spec.ts"
- "Execute the login test"
- "Run all authentication tests"

**Response**: Routes to Runner agent for test execution

---

### 3. Fix Failure
**Intent**: `fix_failure`
**Example Commands**:
- "Kaya, patch task t_123 and retry"
- "Fix the failed checkout test"
- "Repair task t_456"

**Response**: Routes to Medic agent for bug fixing

---

### 4. Validate
**Intent**: `validate`
**Example Commands**:
- "Kaya, validate payment flow - critical"
- "Verify the login test"
- "Validate checkout with Gemini"

**Response**: Routes to Gemini agent for browser validation

---

### 5. Status
**Intent**: `status`
**Example Commands**:
- "Kaya, what's the status of task t_123?"
- "Show me the status of the checkout test"
- "What's happening with task t_789?"

**Response**: Returns current task status

## Events

The orchestrator emits the following events:

### Connection Events
- `connected` - Successfully connected to Realtime API
- `disconnected` - Disconnected from Realtime API
- `session_created` - Session initialized
- `session_updated` - Session configuration updated
- `error` - WebSocket error
- `max_reconnect_failed` - Maximum reconnection attempts reached

### Audio Events
- `audio_delta` - Incremental audio chunk received
- `audio_complete` - Full audio response ready
- `transcription` - Voice transcription completed

### Processing Events
- `kaya_result` - Kaya agent result received
- `conversation_item` - New conversation item created
- `response_complete` - Assistant response completed

### Error Events
- `api_error` - OpenAI API error
- `parse_error` - Message parsing error
- `send_error` - Error sending event

## Architecture

```
┌─────────────────┐
│  User Voice     │
└────────┬────────┘
         │
         v
┌─────────────────────────────────┐
│  VoiceOrchestrator              │
│  ┌───────────────────────────┐  │
│  │ WebSocket (Realtime API)  │  │
│  └───────────────────────────┘  │
│  ┌───────────────────────────┐  │
│  │ Audio Streaming           │  │
│  └───────────────────────────┘  │
│  ┌───────────────────────────┐  │
│  │ Transcription Handler     │  │
│  └───────────────────────────┘  │
└──────────┬──────────────────────┘
           │
           v
┌─────────────────────────────────┐
│  Kaya Agent (Python)            │
│  - Parse Intent                 │
│  - Route to Agent               │
│  - Return Result                │
└──────────┬──────────────────────┘
           │
           v
┌─────────────────────────────────┐
│  Agent Execution                │
│  - Scribe (write test)          │
│  - Runner (execute test)        │
│  - Medic (fix bugs)             │
│  - Gemini (validate)            │
│  - Critic (pre-validate)        │
└──────────┬──────────────────────┘
           │
           v
┌─────────────────────────────────┐
│  Response Synthesis (Voice)     │
└─────────────────────────────────┘
```

## Configuration Options

### RealtimeConfig
```typescript
{
  apiKey: string;              // OpenAI API key (required)
  model?: string;              // Model name (default: gpt-4o-realtime-preview)
  voice?: 'alloy' | 'echo' | 'shimmer';  // Voice selection (default: alloy)
  temperature?: number;        // Response randomness 0-1 (default: 0.8)
  max_response_tokens?: number; // Max tokens per response (default: 4096)
}
```

### AudioConfig
```typescript
{
  sampleRate: 24000;          // Audio sample rate (Hz)
  channels: 1;                // Mono audio
  encoding: 'pcm16';          // PCM 16-bit encoding
}
```

## Integration with Kaya

The orchestrator integrates with Kaya via the Python CLI:

```typescript
// Internal method
private async executeKayaCommand(command: string): Promise<KayaResult> {
  const process = spawn('python3', [
    '/path/to/agent_system/cli.py',
    'kaya',
    command
  ]);

  // Parse output and return structured result
}
```

## Example Voice Session

```
User: "Kaya, write a test for user login"
→ Transcribed: "write a test for user login"
→ Intent: create_test, feature: "user login"
→ Kaya routes to Scribe agent
→ Response: "I'm creating a test for user login. This will use the Scribe agent and should take about 2 minutes."

User: "Kaya, run the login test"
→ Transcribed: "run the login test"
→ Intent: run_test, path: "login test"
→ Kaya routes to Runner agent
→ Response: "Running the login test now. I'll let you know the results."

[Test execution completes]
→ Response: "The login test passed with 5 assertions verified. Execution took 3.2 seconds."
```

## Error Handling

The orchestrator includes comprehensive error handling:

- **Connection Errors**: Automatic reconnection with exponential backoff
- **Timeout Protection**: 30-second timeout for Kaya commands
- **Graceful Degradation**: Continues operating even if some features fail
- **Error Events**: All errors emitted for logging and monitoring

## Best Practices

1. **Always check connection status** before streaming audio
2. **Handle all error events** for robust operation
3. **Commit audio input** when user stops speaking
4. **Clear conversation history** periodically to manage context size
5. **Monitor event emissions** for debugging and observability
6. **Use environment variables** for API keys (never hardcode)

## Testing

```bash
# Run tests
npm test

# Run with coverage
npm test -- --coverage
```

## Development

```bash
# Watch mode for development
npm run dev

# Lint code
npm run lint

# Clean build artifacts
npm run clean
```

## Production Deployment

1. Build TypeScript: `npm run build`
2. Set environment variables
3. Run compiled code: `node dist/orchestrator.js`
4. Monitor events for observability
5. Implement audio playback for output

## Troubleshooting

### WebSocket Connection Fails
- Verify `OPENAI_API_KEY` is set correctly
- Check network connectivity
- Ensure firewall allows WebSocket connections

### No Audio Output
- Verify audio output handler is implemented
- Check audio buffer is not empty
- Ensure audio format matches system requirements

### Transcription Not Working
- Check audio input format (PCM16, 24kHz)
- Verify microphone permissions
- Ensure audio chunks are properly formatted

### Kaya Commands Timeout
- Increase timeout limit (default: 30s)
- Check Python environment is configured
- Verify Kaya CLI path is correct

## License

MIT

## Support

For issues and questions, please refer to the main SuperAgent documentation.
