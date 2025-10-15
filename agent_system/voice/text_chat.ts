/**
 * Text-based chat interface for talking to Kaya
 * No audio - just text input/output
 */

import * as dotenv from 'dotenv';
dotenv.config();

import VoiceOrchestrator from './orchestrator';
import * as readline from 'readline';

async function main() {
  console.log('\n🤖 SuperAgent - Talk to Kaya (Text Mode)');
  console.log('=' .repeat(60));

  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    console.error('✗ OPENAI_API_KEY not set in .env file');
    process.exit(1);
  }

  console.log('✓ OpenAI API key found');
  console.log('✓ Connecting to OpenAI Realtime API...\n');

  const orchestrator = new VoiceOrchestrator({
    apiKey,
    voice: 'alloy',
    temperature: 0.8
  });

  // Set up readline for text input FIRST
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
  });

  // Track connection status
  let connected = false;

  function showPrompt() {
    if (connected) {
      rl.prompt();
    }
  }

  orchestrator.on('connected', () => {
    connected = true;
    console.log('✅ Connected!\n');
    console.log('=' .repeat(60));
    console.log('You can now talk to Kaya!');
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
  });

  orchestrator.on('error', (error: Error) => {
    console.error(`\n✗ Error: ${error.message}`);
    showPrompt();
  });

  // Show transcription (what OpenAI heard)
  orchestrator.on('transcription', (text: string) => {
    console.log(`\n📝 Transcribed: "${text}"`);
  });

  // Show Kaya's results
  orchestrator.on('kaya_result', (result: any) => {
    console.log('\n🤖 Kaya Response:');
    console.log(JSON.stringify(result, null, 2));
  });

  // Show text responses as they stream in
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

  orchestrator.on('response_complete', () => {
    console.log('\n' + '─'.repeat(60));
    showPrompt();
  });

  // Connect
  await orchestrator.connect();

  rl.setPrompt('You: ');

  rl.on('line', async (input: string) => {
    const command = input.trim();

    if (command.toLowerCase() === 'exit') {
      console.log('\n👋 Goodbye!');
      orchestrator.disconnect();
      rl.close();
      process.exit(0);
    }

    if (!command) {
      showPrompt();
      return;
    }

    // Send to Kaya
    orchestrator.addMessage('user', command);
    orchestrator.createResponse();
  });

  rl.on('close', () => {
    orchestrator.disconnect();
    process.exit(0);
  });

  // Handle Ctrl+C
  process.on('SIGINT', () => {
    console.log('\n\n👋 Goodbye!');
    orchestrator.disconnect();
    process.exit(0);
  });
}

main().catch(console.error);
