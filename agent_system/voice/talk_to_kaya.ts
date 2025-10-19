/**
 * Simple voice demo - Type commands, HEAR Kaya speak!
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
  console.log('\n🎤 Talk to Kaya - Voice Demo with Echo Voice');
  console.log('=' .repeat(60));

  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    console.error('✗ OPENAI_API_KEY not set');
    process.exit(1);
  }

  const orchestrator = new VoiceOrchestrator({
    apiKey,
    voice: 'echo',
    temperature: 0.8
  });

  console.log('✓ Connecting to OpenAI Realtime API...\n');

  orchestrator.on('connected', () => {
    console.log('✅ CONNECTED!');
    console.log('✓ Audio output will be saved to a WAV file.\n');
    console.log('Sending test command...\n');

    setTimeout(() => {
      console.log('🎙️  Command: "Introduce yourself as Kaya, my AI testing assistant"\n');
      orchestrator.addMessage('user', 'Introduce yourself as Kaya, my AI testing assistant, in 2 sentences');
      orchestrator.createResponse();
    }, 1000);
  });

  orchestrator.on('error', (error: Error) => {
    console.error(`✗ Error: ${error.message}`);
  });

  // Show text as it comes in
  orchestrator.on('text_delta', (delta: string) => {
    process.stdout.write(delta);
  });

  orchestrator.on('text_complete', () => {
    console.log('\n');
  });

  // Save audio to file
  orchestrator.on('audio_complete', (fullAudio: Buffer) => {
    const seconds = (fullAudio.length / (24000 * 2)).toFixed(1);
    const outputPath = path.join(__dirname, 'talk_to_kaya_response.wav');
    const sampleRate = orchestrator.getAudioConfig().sampleRate;
    writeWavFile(outputPath, fullAudio, sampleRate);

    console.log(`\n✓ Audio finished (${seconds} seconds)`);
    console.log(`✓ Audio response saved to: ${outputPath}`);
    console.log('\n🎉 You can now play the WAV file to hear Kaya speak!');

    setTimeout(() => {
      console.log('\nDemo complete!\n');
      orchestrator.disconnect();
      process.exit(0);
    }, 1000);
  });

  await orchestrator.connect();

  // Timeout
  setTimeout(() => {
    console.log('\n⏱️  Timeout');
    orchestrator.disconnect();
    process.exit(0);
  }, 30000);
}

main().catch(console.error);
