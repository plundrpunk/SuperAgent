#!/usr/bin/env python3
"""
Test script for log rotation, compression, and cleanup functionality.

Tests:
1. Daily log rotation (date-stamped files)
2. Compression of logs older than 7 days
3. Deletion of logs older than 30 days
4. Reading compressed logs
5. Date filtering
"""
import sys
import time
import gzip
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent_system.observability.event_stream import EventEmitter, LogRotationManager


def test_log_rotation():
    """Test basic log rotation with date-stamped files."""
    print("\n" + "="*60)
    print("TEST 1: Daily Log Rotation")
    print("="*60)

    # Create emitter with log rotation
    emitter = EventEmitter(
        websocket_enabled=False,
        console_enabled=False,
        file_enabled=True,
        file_path='logs/test-events.jsonl',
        enable_log_rotation=True
    )

    # Emit some test events
    print("Emitting test events...")
    for i in range(5):
        emitter.emit('task_queued', {
            'task_id': f't_test_{i}',
            'feature': f'test_feature_{i}',
            'est_cost': 0.25,
            'timestamp': time.time()
        })

    # Check that log file was created with today's date
    today = datetime.now().strftime('%Y-%m-%d')
    expected_log = Path(f'logs/test-events-{today}.jsonl')

    if expected_log.exists():
        print(f"✅ Log file created: {expected_log}")
        with open(expected_log, 'r') as f:
            lines = f.readlines()
            print(f"✅ {len(lines)} events written to log")
    else:
        print(f"❌ Expected log file not found: {expected_log}")

    print()


def test_compression():
    """Test compression of old logs."""
    print("="*60)
    print("TEST 2: Log Compression")
    print("="*60)

    # Create rotation manager
    log_dir = Path('logs')
    manager = LogRotationManager(
        log_dir=log_dir,
        base_name='test-events',
        compress_after_days=0,  # Compress immediately for testing
        delete_after_days=30
    )

    # Create a test log file dated 8 days ago
    old_date = datetime.now() - timedelta(days=8)
    old_log_path = manager.get_log_path_for_date(old_date)

    print(f"Creating old log file: {old_log_path}")
    with open(old_log_path, 'w') as f:
        for i in range(3):
            f.write(f'{{"event_type": "test", "timestamp": {time.time()}, "payload": {{"test": {i}}}}}\n')

    print(f"✅ Created test log with 3 events")

    # Run compression
    print("Running compression...")
    manager.compress_old_logs()

    # Check if compressed file exists
    compressed_path = Path(str(old_log_path) + '.gz')
    if compressed_path.exists():
        print(f"✅ Compressed file created: {compressed_path.name}")

        # Verify we can read compressed file
        with gzip.open(compressed_path, 'rt') as f:
            lines = f.readlines()
            print(f"✅ Read {len(lines)} events from compressed file")

        # Check original was deleted
        if not old_log_path.exists():
            print(f"✅ Original uncompressed file deleted")
        else:
            print(f"❌ Original file still exists: {old_log_path}")
    else:
        print(f"❌ Compressed file not found: {compressed_path}")

    print()


def test_deletion():
    """Test deletion of very old logs."""
    print("="*60)
    print("TEST 3: Old Log Deletion")
    print("="*60)

    # Create rotation manager
    log_dir = Path('logs')
    manager = LogRotationManager(
        log_dir=log_dir,
        base_name='test-events',
        compress_after_days=7,
        delete_after_days=0  # Delete immediately for testing
    )

    # Create a very old log file (35 days old)
    very_old_date = datetime.now() - timedelta(days=35)
    very_old_log_path = manager.get_log_path_for_date(very_old_date)

    print(f"Creating very old log file: {very_old_log_path}")
    with open(very_old_log_path, 'w') as f:
        f.write('{"event_type": "test", "timestamp": 0, "payload": {}}\n')

    print(f"✅ Created very old log file")

    # Run deletion
    print("Running deletion...")
    manager.delete_old_logs()

    # Check if file was deleted
    if not very_old_log_path.exists():
        print(f"✅ Very old log file deleted")
    else:
        print(f"❌ Very old log file still exists: {very_old_log_path}")

    print()


def test_view_logs_compressed():
    """Test that view_logs.py can read compressed logs."""
    print("="*60)
    print("TEST 4: Reading Compressed Logs")
    print("="*60)

    from agent_system.observability.view_logs import read_events_from_file

    # Find a compressed log file
    log_dir = Path('logs')
    compressed_logs = list(log_dir.glob('test-events-*.jsonl.gz'))

    if compressed_logs:
        compressed_log = compressed_logs[0]
        print(f"Reading compressed log: {compressed_log.name}")

        events = read_events_from_file(compressed_log)
        print(f"✅ Read {len(events)} events from compressed log")

        if events:
            print(f"✅ Sample event: {events[0].get('event_type')}")
    else:
        print("⚠️  No compressed logs found (this is OK if compression test didn't run)")

    print()


def test_date_filtering():
    """Test date filtering in view_logs.py."""
    print("="*60)
    print("TEST 5: Date Filtering")
    print("="*60)

    from agent_system.observability.view_logs import find_log_files

    log_dir = Path('logs')
    today = datetime.now().strftime('%Y-%m-%d')

    # Find logs for today
    print(f"Finding logs for date: {today}")
    today_logs = find_log_files(log_dir, base_name='test-events', date=today)

    if today_logs:
        print(f"✅ Found {len(today_logs)} log file(s) for today:")
        for log in today_logs:
            print(f"   - {log.name}")
    else:
        print(f"⚠️  No logs found for today (expected if no events emitted)")

    # Find all test logs
    print("\nFinding all test logs...")
    all_logs = find_log_files(log_dir, base_name='test-events')
    print(f"✅ Found {len(all_logs)} total test log file(s):")
    for log in all_logs:
        print(f"   - {log.name}")

    print()


def cleanup_test_logs():
    """Clean up test logs."""
    print("="*60)
    print("CLEANUP: Removing Test Logs")
    print("="*60)

    log_dir = Path('logs')
    test_logs = list(log_dir.glob('test-events-*'))

    for log in test_logs:
        log.unlink()
        print(f"Deleted: {log.name}")

    print(f"✅ Cleaned up {len(test_logs)} test log file(s)")
    print()


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("LOG ROTATION TEST SUITE")
    print("="*60)

    try:
        test_log_rotation()
        test_compression()
        test_deletion()
        test_view_logs_compressed()
        test_date_filtering()

        print("="*60)
        print("✅ ALL TESTS COMPLETED")
        print("="*60)

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Cleanup
        print()
        response = input("Clean up test logs? (y/n): ")
        if response.lower() == 'y':
            cleanup_test_logs()

    print("\nDone!")


if __name__ == '__main__':
    main()
