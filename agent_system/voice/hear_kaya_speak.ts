/**
 * Auto-demo - Hear Kaya speak automatically!
 * This will send a command immediately so you can hear the voice
 */

import * as dotenv from 'dotenv';
dotenv.config();

import VoiceOrchestrator from './orchestrator';
import Speaker from 'speaker';

async function main() {
  console.log('\n🎤 SuperAgent - Hearing Kaya Speak Demo');
  console.log('=' .repeat(60));
  console.log('This will automatically send a command to Kaya');
  console.log('and you will HEAR her voice response!\n');

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

  let currentSpeaker: Speaker | null = null;
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

  // Play audio through speakers!
  orchestrator.on('audio_delta', (audioDelta: Buffer) => {
    if (!currentSpeaker) {
      currentSpeaker = new Speaker({
        channels: 1,
        bitDepth: 16,
        sampleRate: 24000
      });

      console.log('🔊 Playing audio... (listen to your speakers!)');
    }

    currentSpeaker.write(audioDelta);
  });

  orchestrator.on('audio_complete', (fullAudio: Buffer) => {
    const durationSeconds = (fullAudio.length / (24000 * 2)).toFixed(1);
    console.log(`\n✓ Audio complete (${fullAudio.length} bytes, ${durationSeconds}s)`);
    console.log('\n🎉 You should have heard Kaya speak!');

    if (fullTranscript) {
      console.log('\n📝 Kaya said:');
      console.log(`   "${fullTranscript}"`);
    }

    if (currentSpeaker) {
      // Give speaker time to flush buffer before closing (fixes truncation)
      setTimeout(() => {
        if (currentSpeaker) {
          currentSpeaker.end();
          currentSpeaker = null;
        }
      }, 500);
    }

    // Exit after 2.5 seconds (increased to account for speaker flush delay)
    setTimeout(() => {
      console.log('\n👋 Demo complete! Disconnecting...\n');
      orchestrator.disconnect();
      process.exit(0);
    }, 2500);
  });

  orchestrator.on('response_complete', () => {
    console.log('\n─'.repeat(60));
  });

  // Connect
  await orchestrator.connect();

  // Timeout after 30 seconds
  setTimeout(() => {
    console.log('\n⏱️  Timeout - exiting');
    if (currentSpeaker) {
      currentSpeaker.end();
    }
    orchestrator.disconnect();
    process.exit(0);
  }, 30000);
}

main().catch((error) => {
  console.error('Fatal error:', error);
  process.exit(1);
});
