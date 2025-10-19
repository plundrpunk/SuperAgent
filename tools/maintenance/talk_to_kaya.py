#!/usr/bin/env python3
"""
Voice client to speak with Kaya - SuperAgent's voice orchestrator.
"""

import sys
import os
import subprocess
import time

sys.path.insert(0, '/Users/rutledge/Documents/DevFolder/SuperAgent')

from dotenv import load_dotenv
load_dotenv()

def main():
    print("🎤 SuperAgent Voice Control - Talk to Kaya")
    print("=" * 60)
    print()
    print("Starting services...")
    print()

    # Check if observability is running
    print("✓ Observability dashboard: http://localhost:3010")
    print("  (WebSocket event stream running in background)")
    print()

    # Start voice orchestrator
    print("Starting voice orchestrator...")
    print()

    voice_dir = '/Users/rutledge/Documents/DevFolder/SuperAgent/agent_system/voice'

    # Check if built
    if not os.path.exists(f'{voice_dir}/dist/orchestrator.js'):
        print("Building voice orchestrator...")
        subprocess.run(['npm', 'run', 'build'], cwd=voice_dir, check=True)

    print()
    print("=" * 60)
    print("🎙️  VOICE COMMANDS YOU CAN SAY:")
    print("=" * 60)
    print()
    print("1. CREATE TEST")
    print("   'Kaya, write a test for user login'")
    print("   'Create a test for the checkout flow'")
    print()
    print("2. RUN TEST")
    print("   'Kaya, run the login test'")
    print("   'Execute tests/auth.spec.ts'")
    print()
    print("3. VALIDATE")
    print("   'Kaya, validate the payment flow'")
    print("   'Verify the checkout test with Gemini'")
    print()
    print("4. FIX FAILURE")
    print("   'Kaya, fix the failed test'")
    print("   'Repair the checkout errors'")
    print()
    print("5. STATUS")
    print("   'Kaya, what's the status?'")
    print("   'Show me task progress'")
    print()
    print("=" * 60)
    print()
    print("Starting voice session...")
    print("(Press Ctrl+C to stop)")
    print()

    # Run the voice examples (interactive mode)
    try:
        subprocess.run([
            'node',
            'dist/examples.js'
        ], cwd=voice_dir)
    except KeyboardInterrupt:
        print("\n\n✓ Voice session ended")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("\nTry running manually:")
        print(f"  cd {voice_dir}")
        print("  node dist/examples.js")

if __name__ == '__main__':
    main()
