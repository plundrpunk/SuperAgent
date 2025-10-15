/**
 * Voice chat interface - Type to Kaya, HEAR her respond!
 * Plays audio output through speakers
 */

import * as dotenv from 'dotenv';
dotenv.config();

import VoiceOrchestrator from './orchestrator';
import * as readline from 'readline';
import Speaker from 'speaker';

async function main() {
  console.log('\n🎤 SuperAgent - Talk to Kaya (VOICE MODE)');
  console.log('=' .repeat(60));

  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    console.error('✗ OPENAI_API_KEY not set in .env file');
    process.exit(1);
  }

  console.log('✓ OpenAI API key found');
  console.log('✓ Connecting to OpenAI Realtime API...');
  console.log('✓ Audio output: ENABLED (you will hear Kaya speak!)');
  console.log();

  const orchestrator = new VoiceOrchestrator({
    apiKey,
    voice: 'echo',  // Options: alloy, echo, shimmer
    temperature: 0.8
  });

  // Set up readline for text input
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
  });

  // Track connection status
  let connected = false;
  let currentSpeaker: Speaker | null = null;

  function showPrompt() {
    if (connected) {
      rl.prompt();
    }
  }

  orchestrator.on('connected', () => {
    connected = true;
    console.log('✅ Connected!\n');
    console.log('=' .repeat(60));
    console.log('🔊 AUDIO ENABLED - You will HEAR Kaya respond!');
    console.log('=' .repeat(60));
    console.log('\nExamples:');
    console.log('  • "write a test for Cloppy AI authentication"');
    console.log('  • "run tests/auth.spec.ts"');
    console.log('  • "what\'s the status?"');
    console.log('  • "validate the login flow - critical"');
    console.log('\nType "exit" to quit\n');
    showPrompt();
  });

  orchestrator.on('disconnected', () => {
    if (connected) {
      console.log('\n✗ Disconnected from OpenAI');
    }
    if (currentSpeaker) {
      currentSpeaker.end();
      currentSpeaker = null;
    }
  });

  orchestrator.on('error', (error: Error) => {
    console.error(`\n✗ Error: ${error.message}`);
    showPrompt();
  });

  // Show transcription
  orchestrator.on('transcription', (text: string) => {
    console.log(`\n📝 You said: "${text}"`);
  });

  // Show Kaya's results
  orchestrator.on('kaya_result', (result: any) => {
    console.log('\n🤖 Kaya executed:');
    console.log(`  Agent: ${result.agent || 'unknown'}`);
    console.log(`  Action: ${result.data?.action || 'unknown'}`);
    if (result.data?.test_path) {
      console.log(`  Test: ${result.data.test_path}`);
    }
  });

  // Show text responses as they stream
  let textBuffer = '';
  orchestrator.on('text_delta', (delta: string) => {
    process.stdout.write(delta);
    textBuffer += delta;
  });

  orchestrator.on('text_complete', () => {
    if (textBuffer) {
      console.log('\n');
    }
    textBuffer = '';
  });

  // Play audio through speakers!
  orchestrator.on('audio_delta', (audioDelta: Buffer) => {
    if (!currentSpeaker) {
      // Create speaker with OpenAI's audio format
      // 24kHz, 16-bit, 1 channel (mono), little-endian
      currentSpeaker = new Speaker({
        channels: 1,
        bitDepth: 16,
        sampleRate: 24000
      });

      console.log('🔊 Playing audio...');
    }

    // Write audio chunk to speaker
    currentSpeaker.write(audioDelta);
  });

  orchestrator.on('audio_complete', (fullAudio: Buffer) => {
    console.log(`✓ Audio complete (${fullAudio.length} bytes)`);

    if (currentSpeaker) {
      // Give speaker time to flush buffer before closing (fixes truncation)
      setTimeout(() => {
        if (currentSpeaker) {
          currentSpeaker.end();
          currentSpeaker = null;
        }
      }, 500);
    }
  });

  orchestrator.on('response_complete', () => {
    console.log('\n' + '─'.repeat(60));
    showPrompt();
  });

  // Connect to OpenAI
  await orchestrator.connect();

  rl.setPrompt('You: ');

  rl.on('line', async (input: string) => {
    const command = input.trim();

    if (command.toLowerCase() === 'exit') {
      console.log('\n👋 Goodbye!');
      if (currentSpeaker) {
        currentSpeaker.end();
      }
      orchestrator.disconnect();
      rl.close();
      process.exit(0);
    }

    if (!command) {
      showPrompt();
      return;
    }

    // Send to Kaya
    console.log('🎙️  Sending to Kaya...');
    orchestrator.addMessage('user', command);
    orchestrator.createResponse();
  });

  rl.on('close', () => {
    if (currentSpeaker) {
      currentSpeaker.end();
    }
    orchestrator.disconnect();
    process.exit(0);
  });

  // Handle Ctrl+C
  process.on('SIGINT', () => {
    console.log('\n\n👋 Goodbye!');
    if (currentSpeaker) {
      currentSpeaker.end();
    }
    orchestrator.disconnect();
    process.exit(0);
  });
}

main().catch(console.error);
