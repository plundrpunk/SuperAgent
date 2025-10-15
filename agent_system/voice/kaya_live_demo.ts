/**
 * Live Kaya Demo - Actually generates and runs tests
 */

import * as dotenv from 'dotenv';
dotenv.config();

import { spawn } from 'child_process';

async function runKayaCommand(command: string): Promise<any> {
  return new Promise((resolve, reject) => {
    console.log(`\n🤖 Executing: ${command}`);

    const childProcess = spawn('/Users/rutledge/Documents/DevFolder/SuperAgent/venv/bin/python', [
      '/Users/rutledge/Documents/DevFolder/SuperAgent/agent_system/cli.py',
      'kaya',
      command
    ], {
      cwd: '/Users/rutledge/Documents/DevFolder/SuperAgent',
      env: { ...process.env, PYTHONPATH: '/Users/rutledge/Documents/DevFolder/SuperAgent' }
    });

    let output = '';
    let error = '';

    childProcess.stdout?.on('data', (data: Buffer) => {
      output += data.toString();
      console.log(data.toString());
    });

    childProcess.stderr?.on('data', (data: Buffer) => {
      error += data.toString();
      console.error(data.toString());
    });

    childProcess.on('close', (code: number | null) => {
      if (code === 0) {
        resolve({ success: true, output });
      } else {
        reject(new Error(error || 'Command failed'));
      }
    });

    // Timeout after 2 minutes
    setTimeout(() => {
      childProcess.kill();
      reject(new Error('Command timeout'));
    }, 120000);
  });
}

async function liveDemo() {
  console.log('\n🎤 Kaya Live Demo - Real Test Generation for Cloppy_Ai\n');
  console.log('=' .repeat(60));

  const commands = [
    {
      voice: "Kaya, write a test for Cloppy AI's board creation",
      actual: "write a test for Cloppy AI board creation"
    },
    {
      voice: "Kaya, write a test for Cloppy AI's file upload",
      actual: "write a test for Cloppy AI file upload"
    }
  ];

  for (const cmd of commands) {
    console.log(`\n${'─'.repeat(60)}`);
    console.log(`🗣️  Voice Command: "${cmd.voice}"`);
    console.log(`${'─'.repeat(60)}`);

    try {
      const result = await runKayaCommand(cmd.actual);
      console.log('\n✅ Success!');
      console.log(result.output);
    } catch (error: any) {
      console.error('\n❌ Failed:', error.message);
    }

    // Wait between commands
    await new Promise(resolve => setTimeout(resolve, 2000));
  }

  console.log(`\n${'='.repeat(60)}`);
  console.log('✅ Live demo complete!');
  console.log(`${'='.repeat(60)}\n`);

  console.log('📁 Check for generated tests:');
  console.log('   ls -la tests/');
  console.log('\n💰 Check costs:');
  console.log('   python agent_system/cli.py cost daily');
}

liveDemo().catch(console.error);
