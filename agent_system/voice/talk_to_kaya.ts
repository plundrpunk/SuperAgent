/**
 * Simple voice demo - Type commands, HEAR Kaya speak!
 */

import * as dotenv from 'dotenv';
dotenv.config();

import VoiceOrchestrator from './orchestrator';
import Speaker from 'speaker';

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

  let currentSpeaker: Speaker | null = null;

  console.log('✓ Connecting to OpenAI Realtime API...\n');

  orchestrator.on('connected', () => {
    console.log('✅ CONNECTED!');
    console.log('🔊 Audio output enabled - you will HEAR Kaya speak!\n');
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

  // Play audio!
  orchestrator.on('audio_delta', (audioDelta: Buffer) => {
    if (!currentSpeaker) {
      currentSpeaker = new Speaker({
        channels: 1,
        bitDepth: 16,
        sampleRate: 24000
      });
      console.log('🔊 PLAYING AUDIO NOW - Listen to your speakers!\n');
    }
    currentSpeaker.write(audioDelta);
  });

  orchestrator.on('audio_complete', (fullAudio: Buffer) => {
    const seconds = (fullAudio.length / (24000 * 2)).toFixed(1);
    console.log(`\n✓ Audio finished (${seconds} seconds)`);
    console.log('\n🎉 You should have heard Kaya\'s voice!');

    if (currentSpeaker) {
      // Give speaker time to flush buffer before closing (fixes truncation)
      setTimeout(() => {
        if (currentSpeaker) {
          currentSpeaker.end();
          currentSpeaker = null;
        }
      }, 500);
    }

    setTimeout(() => {
      console.log('\nDemo complete!\n');
      orchestrator.disconnect();
      process.exit(0);
    }, 2500);  // Increased to account for speaker flush delay
  });

  await orchestrator.connect();

  // Timeout
  setTimeout(() => {
    console.log('\n⏱️  Timeout');
    if (currentSpeaker) currentSpeaker.end();
    orchestrator.disconnect();
    process.exit(0);
  }, 30000);
}

main().catch(console.error);
