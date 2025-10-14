"""
Integration test for Voice Orchestrator with Kaya agent.
Tests the connection between TypeScript voice interface and Python agent system.
"""
import subprocess
import json
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent_system.agents.kaya import KayaAgent


def test_kaya_cli_integration():
    """Test that Kaya CLI can be invoked from TypeScript orchestrator."""
    print("\n=== Testing Kaya CLI Integration ===\n")

    # Test commands
    test_commands = [
        "write a test for user login",
        "run tests/cart.spec.ts",
        "fix task t_123",
        "validate checkout flow",
        "status of task t_456"
    ]

    kaya = KayaAgent()

    for command in test_commands:
        print(f"\nTesting: '{command}'")
        print("-" * 50)

        # Execute via Kaya
        result = kaya.execute(command)

        print(f"Success: {result.success}")
        if result.data:
            print(f"Action: {result.data.get('action', 'N/A')}")
            print(f"Agent: {result.data.get('agent', 'N/A')}")
            print(f"Model: {result.data.get('model', 'N/A')}")

        if result.error:
            print(f"Error: {result.error}")

        print(f"Execution time: {result.execution_time_ms}ms")


def test_kaya_cli_subprocess():
    """Test Kaya CLI invocation via subprocess (as orchestrator would)."""
    print("\n=== Testing Kaya CLI via Subprocess ===\n")

    cli_path = Path(__file__).parent.parent / "cli.py"

    test_command = "write a test for user login"

    print(f"CLI Path: {cli_path}")
    print(f"Command: {test_command}\n")

    try:
        result = subprocess.run(
            ['python3', str(cli_path), 'kaya', test_command],
            capture_output=True,
            text=True,
            timeout=10
        )

        print("STDOUT:")
        print(result.stdout)

        if result.stderr:
            print("\nSTDERR:")
            print(result.stderr)

        print(f"\nReturn code: {result.returncode}")

        if result.returncode == 0:
            print("✓ CLI invocation successful")
        else:
            print("✗ CLI invocation failed")

    except subprocess.TimeoutExpired:
        print("✗ CLI command timed out")
    except Exception as e:
        print(f"✗ Error: {str(e)}")


def test_intent_parsing():
    """Test Kaya's intent parsing capabilities."""
    print("\n=== Testing Intent Parsing ===\n")

    kaya = KayaAgent()

    test_cases = [
        {
            'command': 'Kaya, write a test for checkout',
            'expected_intent': 'create_test',
            'expected_slot': 'checkout'
        },
        {
            'command': 'run tests/login.spec.ts',
            'expected_intent': 'run_test',
            'expected_slot': 'tests/login.spec.ts'
        },
        {
            'command': 'fix task t_abc123',
            'expected_intent': 'fix_failure',
            'expected_slot': 't_abc123'
        },
        {
            'command': 'validate payment flow',
            'expected_intent': 'validate',
            'expected_slot': 'payment flow'
        },
        {
            'command': 'what is the status of task t_xyz',
            'expected_intent': 'status',
            'expected_slot': 't_xyz'
        }
    ]

    passed = 0
    failed = 0

    for test in test_cases:
        command = test['command']
        result = kaya.parse_intent(command)

        print(f"\nCommand: '{command}'")
        print(f"Expected: {test['expected_intent']}")
        print(f"Got: {result.get('intent')}")

        if result['success'] and result['intent'] == test['expected_intent']:
            print("✓ PASS")
            passed += 1
        else:
            print("✗ FAIL")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed")
    print(f"{'='*50}")


def test_voice_orchestrator_exists():
    """Test that voice orchestrator files exist."""
    print("\n=== Testing Voice Orchestrator Files ===\n")

    voice_dir = Path(__file__).parent
    required_files = [
        'orchestrator.ts',
        'package.json',
        'tsconfig.json',
        'README.md',
        'QUICK_START.md',
        'examples.ts',
        '.env.example',
        '.gitignore'
    ]

    all_exist = True

    for filename in required_files:
        filepath = voice_dir / filename
        exists = filepath.exists()
        status = "✓" if exists else "✗"
        print(f"{status} {filename}: {'exists' if exists else 'MISSING'}")

        if not exists:
            all_exist = False

    print(f"\n{'='*50}")
    if all_exist:
        print("✓ All required files present")
    else:
        print("✗ Some files missing")
    print(f"{'='*50}")


def main():
    """Run all integration tests."""
    print("\n" + "="*60)
    print("Voice Orchestrator - Integration Tests")
    print("="*60)

    try:
        # Test file existence
        test_voice_orchestrator_exists()

        # Test intent parsing
        test_intent_parsing()

        # Test Kaya CLI integration
        test_kaya_cli_integration()

        # Test subprocess invocation
        test_kaya_cli_subprocess()

        print("\n" + "="*60)
        print("✓ All integration tests completed")
        print("="*60 + "\n")

    except Exception as e:
        print(f"\n✗ Integration tests failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
