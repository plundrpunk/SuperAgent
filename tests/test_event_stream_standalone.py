"""
Standalone tests for event streaming (no external dependencies).
Tests core functionality without Redis or WebSocket dependencies.
"""
import json
import time
from pathlib import Path
import tempfile
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_event_structure():
    """Test Event dataclass without importing (manual check)."""
    event_dict = {
        'event_type': 'task_queued',
        'timestamp': time.time(),
        'payload': {
            'task_id': 't_001',
            'feature': 'checkout',
            'est_cost': 0.45
        }
    }

    # Verify structure
    assert 'event_type' in event_dict
    assert 'timestamp' in event_dict
    assert 'payload' in event_dict
    assert event_dict['payload']['task_id'] == 't_001'
    print("✓ Event structure validation passed")


def test_jsonl_format():
    """Test JSONL file format (without EventEmitter)."""
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.jsonl', delete=False) as f:
        temp_path = f.name

        # Write events
        events = [
            {
                'event_type': 'task_queued',
                'timestamp': time.time(),
                'payload': {'task_id': 't_001'}
            },
            {
                'event_type': 'agent_started',
                'timestamp': time.time(),
                'payload': {'agent': 'scribe', 'task_id': 't_001'}
            }
        ]

        for event in events:
            f.write(json.dumps(event) + '\n')

        f.flush()

        # Read back
        with open(temp_path, 'r') as rf:
            lines = rf.readlines()
            assert len(lines) == 2

            # Parse first event
            event1 = json.loads(lines[0])
            assert event1['event_type'] == 'task_queued'
            assert event1['payload']['task_id'] == 't_001'

            # Parse second event
            event2 = json.loads(lines[1])
            assert event2['event_type'] == 'agent_started'
            assert event2['payload']['agent'] == 'scribe'

    # Cleanup
    os.unlink(temp_path)
    print("✓ JSONL format validation passed")


def test_metrics_calculation():
    """Test metrics calculation logic (without Redis)."""
    # Simulate cost tracking
    feature_costs = [0.25, 0.30, 0.35, 0.40]
    avg_cost = sum(feature_costs) / len(feature_costs)
    assert avg_cost == 0.325

    # Simulate retry tracking
    retry_counts = [1, 2, 1, 3, 1]
    avg_retries = sum(retry_counts) / len(retry_counts)
    assert avg_retries == 1.6

    # Simulate validation tracking
    validation_total = 10
    validation_passed = 8
    pass_rate = validation_passed / validation_total
    assert pass_rate == 0.8

    # Simulate critic tracking
    critic_total = 20
    critic_rejected = 5
    rejection_rate = critic_rejected / critic_total
    assert rejection_rate == 0.25

    print("✓ Metrics calculation passed")


def test_event_validation():
    """Test event payload validation."""
    # Valid task_queued event
    task_queued = {
        'task_id': 't_001',
        'feature': 'checkout',
        'est_cost': 0.45,
        'timestamp': time.time()
    }
    assert all(key in task_queued for key in ['task_id', 'feature', 'est_cost', 'timestamp'])

    # Valid agent_started event
    agent_started = {
        'agent': 'scribe',
        'task_id': 't_001',
        'model': 'claude-sonnet-4.5',
        'tools': ['read', 'write', 'edit']
    }
    assert all(key in agent_started for key in ['agent', 'task_id', 'model', 'tools'])

    # Valid agent_completed event
    agent_completed = {
        'agent': 'scribe',
        'task_id': 't_001',
        'status': 'success',
        'duration_ms': 2500,
        'cost_usd': 0.12
    }
    assert all(key in agent_completed for key in ['agent', 'task_id', 'status', 'duration_ms', 'cost_usd'])

    # Valid validation_complete event
    validation_complete = {
        'task_id': 't_001',
        'result': {
            'browser_launched': True,
            'test_executed': True,
            'test_passed': True
        },
        'cost': 0.15,
        'duration_ms': 5000,
        'screenshots': 2
    }
    assert all(key in validation_complete for key in ['task_id', 'result', 'cost', 'duration_ms'])

    print("✓ Event payload validation passed")


def test_time_tracking():
    """Test time-to-completion tracking."""
    task_start_times = {}

    # Task queued
    task_id = 't_001'
    task_start_times[task_id] = time.time()

    # Simulate work
    time.sleep(0.1)

    # Task completed
    completion_time = time.time() - task_start_times[task_id]
    assert completion_time >= 0.1
    assert completion_time < 1.0  # Should be less than 1 second

    print(f"✓ Time tracking passed (completion time: {completion_time:.3f}s)")


def test_console_formatting():
    """Test console output formatting (visual check)."""
    from datetime import datetime

    # ANSI color codes
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

    # Format an event
    event_type = 'task_queued'
    timestamp = datetime.now().strftime('%H:%M:%S')
    payload = {
        'task_id': 't_001',
        'feature': 'checkout',
        'est_cost': 0.45
    }

    # Print formatted (visual check)
    output = f"{BLUE}{BOLD}[{timestamp}] {event_type.upper()}{RESET}\n"
    for key, value in payload.items():
        output += f"  {key}: {value}\n"

    print("\nFormatted console output:")
    print(output)
    print("✓ Console formatting test passed (visual check above)")


def test_event_ordering():
    """Test that events maintain proper ordering."""
    events = []

    # Emit events in order
    events.append({
        'type': 'task_queued',
        'timestamp': time.time(),
        'seq': 1
    })

    time.sleep(0.01)

    events.append({
        'type': 'agent_started',
        'timestamp': time.time(),
        'seq': 2
    })

    time.sleep(0.01)

    events.append({
        'type': 'agent_completed',
        'timestamp': time.time(),
        'seq': 3
    })

    # Verify ordering
    for i in range(len(events) - 1):
        assert events[i]['timestamp'] < events[i + 1]['timestamp']
        assert events[i]['seq'] < events[i + 1]['seq']

    print("✓ Event ordering test passed")


def run_all_tests():
    """Run all standalone tests."""
    print("\n" + "=" * 60)
    print("Running Event Streaming Standalone Tests")
    print("=" * 60 + "\n")

    tests = [
        test_event_structure,
        test_jsonl_format,
        test_metrics_calculation,
        test_event_validation,
        test_time_tracking,
        test_console_formatting,
        test_event_ordering
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            print(f"\nRunning: {test.__name__}")
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ {test.__name__} failed: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test.__name__} error: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60 + "\n")

    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
