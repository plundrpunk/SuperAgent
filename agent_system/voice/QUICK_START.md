# Voice Orchestrator - Quick Start Guide

Get started with SuperAgent's voice integration in 5 minutes.

## Prerequisites

- Node.js 18+ installed
- OpenAI API key with Realtime API access
- Python 3.11+ (for Kaya integration)
- SuperAgent system configured

## Step 1: Install Dependencies

```bash
cd agent_system/voice
npm install
```

## Step 2: Configure API Key

```bash
# Copy example env file
cp .env.example .env

# Edit .env and add your OpenAI API key
# OPENAI_API_KEY=sk-your-actual-key-here
```

## Step 3: Build TypeScript

```bash
npm run build
```

## Step 4: Run Example

```bash
# Load environment variables
export $(cat .env | xargs)

# Run basic example
node dist/examples.js 1
```

## Step 5: Try All Examples

```bash
# Example 1: Basic Voice Session
node dist/examples.js 1

# Example 2: Audio Streaming
node dist/examples.js 2

# Example 3: Event Monitoring
node dist/examples.js 3

# Example 4: Conversation History
node dist/examples.js 4

# Example 5: Error Handling & Reconnection
node dist/examples.js 5

# Example 6: All Voice Intents
node dist/examples.js 6
```

## Voice Commands You Can Try

Once connected, you can say:

### Create Test
```
"Kaya, write a test for user login"
"Create a test for the checkout happy path"
"Generate a test for password reset"
```

### Run Test
```
"Kaya, run tests/cart.spec.ts"
"Execute the login test"
"Run all authentication tests"
```

### Fix Failure
```
"Kaya, patch task t_123 and retry"
"Fix the failed checkout test"
"Repair task t_456"
```

### Validate
```
"Kaya, validate payment flow - critical"
"Verify the login test"
"Validate checkout with Gemini"
```

### Status
```
"Kaya, what's the status of task t_123?"
"Show me the status of the checkout test"
"What's happening with task t_789?"
```

## Integration with Your Application

### Basic Integration

```typescript
import VoiceOrchestrator from './orchestrator';

// Create orchestrator
const orchestrator = new VoiceOrchestrator({
  apiKey: process.env.OPENAI_API_KEY!
});

// Connect
await orchestrator.connect();

// Handle transcriptions
orchestrator.on('transcription', (text) => {
  console.log('User said:', text);
});

// Handle responses
orchestrator.on('audio_complete', (audioBuffer) => {
  // Play audio to user
  playAudioToSpeaker(audioBuffer);
});
```

### With Microphone Input

```typescript
import { createReadStream } from 'fs';

// Set up microphone stream (example using node-mic)
const mic = require('mic');

const micInstance = mic({
  rate: '24000',
  channels: '1',
  encoding: 'signed-integer',
  bitwidth: '16'
});

const micInputStream = micInstance.getAudioStream();

micInputStream.on('data', (data) => {
  // Stream to orchestrator
  orchestrator.streamAudioInput(data);
});

// Start recording
micInstance.start();
```

### With Express Server

```typescript
import express from 'express';
import VoiceOrchestrator from './orchestrator';

const app = express();
const orchestrator = new VoiceOrchestrator({
  apiKey: process.env.OPENAI_API_KEY!
});

// Connect on startup
orchestrator.connect();

// WebSocket endpoint for audio streaming
app.ws('/voice', (ws, req) => {
  ws.on('message', (audioChunk) => {
    orchestrator.streamAudioInput(audioChunk);
  });

  orchestrator.on('audio_complete', (audio) => {
    ws.send(audio);
  });
});

app.listen(3000, () => {
  console.log('Voice server running on port 3000');
});
```

## Troubleshooting

### "OPENAI_API_KEY not set"
- Make sure you've created a `.env` file
- Load it: `export $(cat .env | xargs)`
- Or use: `source .env`

### "WebSocket connection failed"
- Verify your API key is valid
- Check you have Realtime API access
- Ensure network allows WebSocket connections

### "Kaya command timeout"
- Check Python environment is activated
- Verify `cli.py` path is correct
- Increase timeout in configuration

### Audio Not Working
- Verify audio format is PCM16, 24kHz, mono
- Check audio chunks are being streamed
- Ensure audio output handler is implemented

## Next Steps

1. **Read the full README** for detailed documentation
2. **Review the orchestrator.ts** source code
3. **Integrate with your audio pipeline**
4. **Set up production deployment**
5. **Add observability and monitoring**

## Production Checklist

- [ ] Set up proper error logging
- [ ] Implement audio recording/playback
- [ ] Add authentication for API endpoints
- [ ] Configure reconnection strategy
- [ ] Set up monitoring and alerts
- [ ] Test with real voice input
- [ ] Load test for concurrent users
- [ ] Document deployment process

## Resources

- [OpenAI Realtime API Docs](https://platform.openai.com/docs/guides/realtime)
- [SuperAgent Main README](../../README.md)
- [Kaya Agent Documentation](../agents/kaya.py)
- [Voice Orchestrator README](./README.md)

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the examples in `examples.ts`
3. Check the main SuperAgent documentation
4. Review OpenAI Realtime API documentation

---

Happy voice testing! 🎤
