/**
 * Auto-demo - Hear Kaya speak automatically!
 * This will send a command immediately so you can hear the voice
 */

import * as dotenv from 'dotenv';
dotenv.config();

import VoiceOrchestrator from './orchestrator';
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
  console.log('\n🎤 SuperAgent - Hearing Kaya Speak Demo');
  console.log('=' .repeat(60));
  console.log('This will automatically send a command to Kaya');
  console.log('and save her voice response to a WAV file!\n');

  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    console.error('✗ OPENAI_API_KEY not set');
    process.exit(1);
  }

  const orchestrator = new VoiceOrchestrator({
    apiKey,
    voice: 'echo',  // Clear and professional voice
    temperature: 0.8
  });

  let fullTranscript = '';

  orchestrator.on('connected', () => {
    console.log('✅ Connected to OpenAI!\n');
    console.log('🎙️  Sending command: "Tell me about SuperAgent"\n');

    // Send a simple command automatically
    setTimeout(() => {
      orchestrator.addMessage('user', 'Tell me about SuperAgent in one sentence');
      orchestrator.createResponse();
    }, 500);
  });

  orchestrator.on('error', (error: Error) => {
    console.error(`✗ Error: ${error.message}`);
    process.exit(1);
  });

  // Show text response
  let textBuffer = '';
  orchestrator.on('text_delta', (delta: string) => {
    process.stdout.write(delta);
    textBuffer += delta;
    fullTranscript += delta;
  });

  orchestrator.on('text_complete', () => {
    if (textBuffer) {
      console.log('\n');
    }
    textBuffer = '';
  });

  // Save audio to a .wav file
  orchestrator.on('audio_complete', (fullAudio: Buffer) => {
    const durationSeconds = (fullAudio.length / (24000 * 2)).toFixed(1);
    const outputPath = path.join(__dirname, 'kaya_speak_demo.wav');
    const sampleRate = orchestrator.getAudioConfig().sampleRate;
    writeWavFile(outputPath, fullAudio, sampleRate);

    console.log(`\n✓ Audio complete (${fullAudio.length} bytes, ${durationSeconds}s)`);
    console.log(`✓ Audio response saved to: ${outputPath}`);
    console.log('\n🎉 You can now play the WAV file to hear Kaya speak!');

    if (fullTranscript) {
      console.log('\n📝 Kaya said:');
      console.log(`   "${fullTranscript}"`);
    }

    // Exit after a short delay
    setTimeout(() => {
      console.log('\n👋 Demo complete! Disconnecting...\n');
      orchestrator.disconnect();
      process.exit(0);
    }, 1000);
  });

  orchestrator.on('response_complete', () => {
    console.log('\n' + '─'.repeat(60));
  });

  // Connect
  await orchestrator.connect();

  // Timeout after 30 seconds
  setTimeout(() => {
    console.log('\n⏱️  Timeout - exiting');
    orchestrator.disconnect();
    process.exit(0);
  }, 30000);
}

main().catch((error) => {
  console.error('Fatal error:', error);
  process.exit(1);
});
