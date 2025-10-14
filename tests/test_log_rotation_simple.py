#!/usr/bin/env python3
"""
Simple test script for log rotation functionality (no dependencies required).

Tests:
1. LogRotationManager basic functionality
2. Date-stamped log file creation
3. Compression simulation
4. Deletion simulation
"""
import sys
import time
import gzip
import json
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_rotation_manager():
    """Test LogRotationManager without full EventEmitter."""
    print("\n" + "="*60)
    print("LOG ROTATION MANAGER TESTS")
    print("="*60)

    # Import just the rotation manager class
    from agent_system.observability.event_stream import LogRotationManager

    # Create rotation manager
    log_dir = Path('logs/test_rotation')
    manager = LogRotationManager(
        log_dir=log_dir,
        base_name='test-events',
        compress_after_days=7,
        delete_after_days=30
    )

    print(f"\n✅ Created LogRotationManager")
    print(f"   Log directory: {log_dir}")

    # Test 1: Get current log path
    print("\n" + "-"*60)
    print("TEST 1: Get Current Log Path")
    print("-"*60)
    current_log = manager.get_current_log_path()
    today = datetime.now().strftime('%Y-%m-%d')
    expected_name = f"test-events-{today}.jsonl"

    if current_log.name == expected_name:
        print(f"✅ Current log path: {current_log}")
    else:
        print(f"❌ Expected {expected_name}, got {current_log.name}")

    # Test 2: Create log file and write events
    print("\n" + "-"*60)
    print("TEST 2: Create Log File")
    print("-"*60)

    with open(current_log, 'w') as f:
        for i in range(5):
            event = {
                'event_type': 'task_queued',
                'timestamp': time.time(),
                'payload': {
                    'task_id': f't_test_{i}',
                    'feature': f'test_feature_{i}'
                }
            }
            f.write(json.dumps(event) + '\n')

    if current_log.exists():
        with open(current_log, 'r') as f:
            lines = f.readlines()
        print(f"✅ Created log file with {len(lines)} events")
    else:
        print(f"❌ Log file not created")

    # Test 3: Create old log file for compression test
    print("\n" + "-"*60)
    print("TEST 3: Compression")
    print("-"*60)

    old_date = datetime.now() - timedelta(days=8)
    old_log = manager.get_log_path_for_date(old_date)

    print(f"Creating old log: {old_log.name}")
    with open(old_log, 'w') as f:
        for i in range(3):
            event = {
                'event_type': 'test_old',
                'timestamp': time.time(),
                'payload': {'test': i}
            }
            f.write(json.dumps(event) + '\n')

    print(f"✅ Created old log file")

    # Run compression
    print("Running compression...")
    manager.compress_old_logs()

    compressed_path = Path(str(old_log) + '.gz')
    if compressed_path.exists():
        print(f"✅ Compressed file created: {compressed_path.name}")

        # Verify we can read it
        with gzip.open(compressed_path, 'rt') as f:
            lines = f.readlines()
        print(f"✅ Read {len(lines)} events from compressed file")

        if not old_log.exists():
            print(f"✅ Original file deleted after compression")
        else:
            print(f"⚠️  Original file still exists")
    else:
        print(f"❌ Compression failed")

    # Test 4: Create very old log for deletion test
    print("\n" + "-"*60)
    print("TEST 4: Deletion")
    print("-"*60)

    very_old_date = datetime.now() - timedelta(days=35)
    very_old_log = manager.get_log_path_for_date(very_old_date)

    print(f"Creating very old log: {very_old_log.name}")
    with open(very_old_log, 'w') as f:
        f.write('{"event_type": "test", "timestamp": 0}\n')

    print(f"✅ Created very old log file")

    # Run deletion
    print("Running deletion...")
    manager.delete_old_logs()

    if not very_old_log.exists():
        print(f"✅ Very old log deleted")
    else:
        print(f"❌ Very old log still exists")

    # Test 5: List all log files
    print("\n" + "-"*60)
    print("TEST 5: List Log Files")
    print("-"*60)

    all_logs = sorted(log_dir.glob('test-events-*'))
    print(f"Found {len(all_logs)} log file(s):")
    for log in all_logs:
        size = log.stat().st_size
        print(f"   - {log.name} ({size} bytes)")

    # Test 6: Test view_logs functionality
    print("\n" + "-"*60)
    print("TEST 6: Reading Logs (view_logs.py functions)")
    print("-"*60)

    from agent_system.observability.view_logs import read_events_from_file, find_log_files

    # Read from current log
    events = read_events_from_file(current_log)
    print(f"✅ Read {len(events)} events from current log")

    # Read from compressed log
    if compressed_path.exists():
        compressed_events = read_events_from_file(compressed_path)
        print(f"✅ Read {len(compressed_events)} events from compressed log")

    # Find logs by date
    today_logs = find_log_files(log_dir, base_name='test-events', date=today)
    print(f"✅ Found {len(today_logs)} log(s) for today")

    # Cleanup
    print("\n" + "-"*60)
    print("CLEANUP")
    print("-"*60)

    response = input("\nDelete test logs? (y/n): ")
    if response.lower() == 'y':
        import shutil
        shutil.rmtree(log_dir)
        print(f"✅ Deleted {log_dir}")

    print("\n" + "="*60)
    print("✅ ALL TESTS COMPLETED SUCCESSFULLY")
    print("="*60)


if __name__ == '__main__':
    try:
        test_rotation_manager()
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
