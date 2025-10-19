/**
 * Voice chat interface - Type to Kaya, and her response will be saved to a WAV file.
 */

import * as dotenv from 'dotenv';
dotenv.config();

import VoiceOrchestrator from './orchestrator';
import * as readline from 'readline';
import * as fs from 'fs';
import * as path from 'path';

// WAV file writing helper
function writeWavFile(filePath: string, pcmData: Buffer, sampleRate: number) {
  const header = Buffer.alloc(44);
  const numChannels = 1;
  const bitsPerSample = 16;
  const byteRate = sampleRate * numChannels * (bitsPerSample / 8);
  const blockAlign = numChannels * (bitsPerSample / 8);

  header.write('RIFF', 0);
  header.writeUInt32LE(36 + pcmData.length, 4);
  header.write('WAVE', 8);
  header.write('fmt ', 12);
  header.writeUInt32LE(16, 16);
  header.writeUInt16LE(1, 20);
  header.writeUInt16LE(numChannels, 22);
  header.writeUInt32LE(sampleRate, 24);
  header.writeUInt32LE(byteRate, 28);
  header.writeUInt16LE(blockAlign, 32);
  header.writeUInt16LE(bitsPerSample, 34);
  header.write('data', 36);
  header.writeUInt32LE(pcmData.length, 40);

  const wavBuffer = Buffer.concat([header, pcmData]);
  fs.writeFileSync(filePath, wavBuffer);
}

async function main() {
  console.log('\n🎤 SuperAgent - Talk to Kaya (VOICE-TO-FILE MODE)');
  console.log('=' .repeat(60));

  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    console.error('✗ OPENAI_API_KEY not set in .env file');
    process.exit(1);
  }

  console.log('✓ OpenAI API key found');
  console.log('✓ Connecting to OpenAI Realtime API...');
  console.log('✓ Audio output will be saved to a WAV file.\n');

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
    console.log('🔊 AUDIO-TO-FILE ENABLED - Kaya\'s responses will be saved as WAV files!');
    console.log('=' .repeat(60));
    console.log('\nExamples:');
    console.log('  • "write a test for Cloppy AI authentication"');
    console.log('  • "run tests/auth.spec.ts"');
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

  // Show transcription
  orchestrator.on('transcription', (text: string) => {
    console.log(`\n📝 You said: "${text}"`);
  });

  // Show Kaya's results
  orchestrator.on('kaya_result', (result: any) => {
    console.log('\n🤖 Kaya executed:');
    console.log(`  Agent: ${result.agent || 'unknown'}`);
    console.log(`  Action: ${result.data?.action || 'unknown'}`);
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

  // Save audio to a .wav file
  orchestrator.on('audio_complete', (fullAudio: Buffer) => {
    const outputPath = path.join(__dirname, `kaya_response_${Date.now()}.wav`);
    const sampleRate = orchestrator.getAudioConfig().sampleRate;
    writeWavFile(outputPath, fullAudio, sampleRate);
    console.log(`\n✓ Audio response saved to: ${outputPath}`);
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
