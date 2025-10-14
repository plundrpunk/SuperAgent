/**
 * SuperAgent Voice Orchestrator - Example Usage
 *
 * This file demonstrates various ways to use the Voice Orchestrator
 * with OpenAI Realtime API for voice-controlled testing.
 */

import VoiceOrchestrator from './orchestrator';
import * as fs from 'fs';
import * as path from 'path';

// ============================================================================
// Example 1: Basic Voice Session
// ============================================================================

export async function basicVoiceSession() {
  console.log('\n=== Example 1: Basic Voice Session ===\n');

  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    throw new Error('OPENAI_API_KEY not set');
  }

  const orchestrator = new VoiceOrchestrator({
    apiKey,
    voice: 'alloy',
    temperature: 0.8
  });

  // Set up event listeners
  orchestrator.on('connected', () => {
    console.log('✓ Connected to OpenAI Realtime API');
  });

  orchestrator.on('transcription', (text: string) => {
    console.log(`[User]: ${text}`);
  });

  orchestrator.on('kaya_result', (result: any) => {
    console.log(`[Kaya]: ${JSON.stringify(result, null, 2)}`);
  });

  orchestrator.on('text_delta', (delta: string) => {
    process.stdout.write(delta);
  });

  orchestrator.on('audio_complete', (audio: Buffer) => {
    console.log(`\n✓ Audio response ready (${audio.length} bytes)`);
  });

  orchestrator.on('error', (error: Error) => {
    console.error('✗ Error:', error.message);
  });

  // Connect
  await orchestrator.connect();

  // Simulate voice commands (in real usage, these would come from microphone)
  const commands = [
    'Kaya, write a test for user login',
    'Kaya, run tests/login.spec.ts',
    'Kaya, validate the checkout flow'
  ];

  for (const command of commands) {
    console.log(`\n→ Simulating: "${command}"`);
    orchestrator.addMessage('user', command);
    orchestrator.createResponse();

    // Wait for response
    await new Promise(resolve => setTimeout(resolve, 3000));
  }

  // Clean up
  orchestrator.disconnect();
  console.log('\n✓ Disconnected');
}

// ============================================================================
// Example 2: Audio Streaming from File
// ============================================================================

export async function audioStreamingExample() {
  console.log('\n=== Example 2: Audio Streaming ===\n');

  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    throw new Error('OPENAI_API_KEY not set');
  }

  const orchestrator = new VoiceOrchestrator({
    apiKey,
    voice: 'echo'
  });

  orchestrator.on('connected', async () => {
    console.log('✓ Connected, starting audio stream...');

    // Simulate streaming audio chunks (16-bit PCM, 24kHz)
    // In production, this would come from microphone
    const chunkSize = 4800; // 100ms of audio at 24kHz
    const audioBuffer = Buffer.alloc(chunkSize * 10); // 1 second of silence

    for (let i = 0; i < 10; i++) {
      const chunk = audioBuffer.slice(i * chunkSize, (i + 1) * chunkSize);
      orchestrator.streamAudioInput(chunk);
      await new Promise(resolve => setTimeout(resolve, 100));
    }

    // Commit audio when done
    orchestrator.commitAudioInput();
    console.log('✓ Audio streaming complete');
  });

  orchestrator.on('transcription', (text: string) => {
    console.log(`Transcribed: "${text}"`);
  });

  orchestrator.on('audio_complete', (audio: Buffer) => {
    // Save response audio to file
    const outputPath = path.join(__dirname, 'output.pcm');
    fs.writeFileSync(outputPath, audio);
    console.log(`✓ Saved audio response to ${outputPath}`);
  });

  await orchestrator.connect();

  // Wait for processing
  await new Promise(resolve => setTimeout(resolve, 10000));
  orchestrator.disconnect();
}

// ============================================================================
// Example 3: Event Monitoring & Logging
// ============================================================================

export async function eventMonitoringExample() {
  console.log('\n=== Example 3: Event Monitoring ===\n');

  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    throw new Error('OPENAI_API_KEY not set');
  }

  const orchestrator = new VoiceOrchestrator({
    apiKey,
    voice: 'shimmer'
  });

  // Comprehensive event logging
  const events = [
    'connected',
    'disconnected',
    'session_created',
    'session_updated',
    'conversation_item',
    'transcription',
    'kaya_result',
    'audio_delta',
    'audio_complete',
    'text_delta',
    'text_complete',
    'response_complete',
    'error',
    'api_error',
    'parse_error',
    'send_error'
  ];

  events.forEach(eventName => {
    orchestrator.on(eventName, (data: any) => {
      const timestamp = new Date().toISOString();
      console.log(`[${timestamp}] ${eventName}:`,
        typeof data === 'object' ? JSON.stringify(data, null, 2) : data
      );
    });
  });

  await orchestrator.connect();

  // Send test command
  orchestrator.addMessage('user', 'Kaya, what is the status of task t_123?');
  orchestrator.createResponse();

  // Monitor for 5 seconds
  await new Promise(resolve => setTimeout(resolve, 5000));
  orchestrator.disconnect();
}

// ============================================================================
// Example 4: Conversation History & Context
// ============================================================================

export async function conversationHistoryExample() {
  console.log('\n=== Example 4: Conversation History ===\n');

  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    throw new Error('OPENAI_API_KEY not set');
  }

  const orchestrator = new VoiceOrchestrator({
    apiKey
  });

  await orchestrator.connect();

  // Multi-turn conversation
  const conversation = [
    'Kaya, write a test for user registration',
    'Add validation for email format',
    'Now run that test',
    'What was the result?'
  ];

  for (const message of conversation) {
    console.log(`\n[User]: ${message}`);
    orchestrator.addMessage('user', message);
    orchestrator.createResponse();

    await new Promise(resolve => setTimeout(resolve, 3000));

    // Display conversation history
    const history = orchestrator.getConversationHistory();
    console.log(`\nConversation History (${history.length} messages):`);
    history.slice(-4).forEach((msg, i) => {
      console.log(`  ${i + 1}. [${msg.role}]: ${msg.content.substring(0, 50)}...`);
    });
  }

  // Clear history
  orchestrator.clearConversationHistory();
  console.log('\n✓ Conversation history cleared');

  orchestrator.disconnect();
}

// ============================================================================
// Example 5: Error Handling & Reconnection
// ============================================================================

export async function errorHandlingExample() {
  console.log('\n=== Example 5: Error Handling & Reconnection ===\n');

  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    throw new Error('OPENAI_API_KEY not set');
  }

  const orchestrator = new VoiceOrchestrator({
    apiKey
  });

  let connectionAttempts = 0;

  orchestrator.on('connected', () => {
    connectionAttempts++;
    console.log(`✓ Connected (attempt ${connectionAttempts})`);
  });

  orchestrator.on('disconnected', () => {
    console.log('✗ Disconnected - will attempt reconnection');
  });

  orchestrator.on('error', (error: Error) => {
    console.error(`✗ Error: ${error.message}`);
  });

  orchestrator.on('api_error', (error: any) => {
    console.error(`✗ API Error: ${JSON.stringify(error)}`);
  });

  orchestrator.on('max_reconnect_failed', () => {
    console.error('✗ Maximum reconnection attempts reached');
  });

  // Initial connection
  await orchestrator.connect();

  // Simulate network disruption after 2 seconds
  setTimeout(() => {
    console.log('\n⚠ Simulating network disruption...');
    orchestrator.disconnect();
  }, 2000);

  // Wait to see reconnection attempts
  await new Promise(resolve => setTimeout(resolve, 15000));

  if (orchestrator.isActive()) {
    console.log('\n✓ Successfully reconnected');
    orchestrator.disconnect();
  } else {
    console.log('\n✗ Failed to reconnect');
  }
}

// ============================================================================
// Example 6: All Voice Intents
// ============================================================================

export async function allVoiceIntentsExample() {
  console.log('\n=== Example 6: All Voice Intents ===\n');

  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    throw new Error('OPENAI_API_KEY not set');
  }

  const orchestrator = new VoiceOrchestrator({
    apiKey,
    voice: 'alloy'
  });

  orchestrator.on('connected', () => {
    console.log('✓ Connected - demonstrating all voice intents\n');
  });

  orchestrator.on('kaya_result', (result: any) => {
    console.log(`  → Action: ${result.data?.action || 'unknown'}`);
    console.log(`  → Success: ${result.success}`);
    if (result.data) {
      console.log(`  → Data:`, result.data);
    }
  });

  await orchestrator.connect();

  const intents = [
    {
      type: 'create_test',
      command: 'Kaya, write a test for user login with OAuth',
      description: 'Creates a new test file using Scribe agent'
    },
    {
      type: 'run_test',
      command: 'Kaya, run tests/auth/login.spec.ts',
      description: 'Executes test file using Runner agent'
    },
    {
      type: 'fix_failure',
      command: 'Kaya, fix task t_abc123',
      description: 'Repairs failed test using Medic agent'
    },
    {
      type: 'validate',
      command: 'Kaya, validate payment checkout flow - critical',
      description: 'Validates test in real browser using Gemini agent'
    },
    {
      type: 'status',
      command: 'Kaya, what is the status of task t_xyz789?',
      description: 'Retrieves current task status'
    }
  ];

  for (const intent of intents) {
    console.log(`\n─────────────────────────────────────────`);
    console.log(`Intent: ${intent.type}`);
    console.log(`Description: ${intent.description}`);
    console.log(`Command: "${intent.command}"\n`);

    orchestrator.addMessage('user', intent.command);
    orchestrator.createResponse();

    await new Promise(resolve => setTimeout(resolve, 4000));
  }

  console.log(`\n─────────────────────────────────────────\n`);
  orchestrator.disconnect();
}

// ============================================================================
// Main Runner
// ============================================================================

async function main() {
  const examples: Record<string, { name: string; fn: () => Promise<void> }> = {
    '1': { name: 'Basic Voice Session', fn: basicVoiceSession },
    '2': { name: 'Audio Streaming', fn: audioStreamingExample },
    '3': { name: 'Event Monitoring', fn: eventMonitoringExample },
    '4': { name: 'Conversation History', fn: conversationHistoryExample },
    '5': { name: 'Error Handling', fn: errorHandlingExample },
    '6': { name: 'All Voice Intents', fn: allVoiceIntentsExample }
  };

  const exampleNum = process.argv[2] || '1';

  if (!examples[exampleNum]) {
    console.log('\nSuperAgent Voice Orchestrator - Examples\n');
    console.log('Usage: node examples.js [example_number]\n');
    console.log('Available examples:');
    Object.entries(examples).forEach(([num, example]) => {
      console.log(`  ${num}: ${example.name}`);
    });
    console.log();
    process.exit(0);
  }

  try {
    await examples[exampleNum].fn();
    console.log('\n✓ Example completed\n');
  } catch (error: any) {
    console.error('\n✗ Example failed:', error.message);
    process.exit(1);
  }
}

// Run if executed directly
if (require.main === module) {
  main().catch(console.error);
}
