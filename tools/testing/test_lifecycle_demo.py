#!/usr/bin/env python3
"""
Standalone demonstration of lifecycle management

This script demonstrates the lifecycle system without requiring external dependencies.
"""
import time
import threading
import signal
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from agent_system.lifecycle import ServiceLifecycle, ServiceStatus


class MockConnection:
    """Mock connection for demonstration."""

    def __init__(self, name):
        self.name = name
        self.is_closed = False

    def close(self):
        """Close the connection."""
        print(f"  Closing {self.name} connection...")
        time.sleep(0.2)  # Simulate close delay
        self.is_closed = True
        print(f"  ✓ {self.name} connection closed")

    def health_check(self):
        """Check if connection is healthy."""
        return not self.is_closed


def simulate_long_running_task(lifecycle, task_id, duration):
    """
    Simulate a long-running task that respects shutdown signals.

    Args:
        lifecycle: ServiceLifecycle instance
        task_id: Task identifier
        duration: How long the task should run (seconds)
    """
    print(f"\n  Task {task_id} started (duration: {duration}s)")

    # Track the task
    lifecycle.add_active_task(task_id, agent="demo_agent", feature="test_feature")

    start_time = time.time()

    try:
        # Simulate work in chunks, checking for shutdown
        while (time.time() - start_time) < duration:
            # Check if shutting down
            if lifecycle.is_shutting_down():
                print(f"  Task {task_id} detected shutdown, cleaning up...")
                break

            # Do a chunk of work
            time.sleep(0.5)

        elapsed = time.time() - start_time
        print(f"  Task {task_id} completed (took {elapsed:.1f}s)")

    finally:
        # Always remove task from tracking
        lifecycle.remove_active_task(task_id)


def main():
    """Run lifecycle demonstration."""
    print("\n" + "="*60)
    print("SuperAgent Lifecycle Management Demo")
    print("="*60)

    # Create lifecycle instance
    print("\n1. Initializing lifecycle manager...")
    lifecycle = ServiceLifecycle()
    print(f"   Status: {lifecycle.status.value}")

    # Register signal handlers
    print("\n2. Registering signal handlers (SIGTERM, SIGINT)...")
    lifecycle.setup_signal_handlers()
    print("   ✓ Signal handlers registered")
    print("   (Press Ctrl+C to trigger graceful shutdown)")

    # Register mock connections
    print("\n3. Registering connections...")
    redis_mock = MockConnection("Redis")
    vector_mock = MockConnection("VectorDB")
    websocket_mock = MockConnection("WebSocket")

    lifecycle.register_connection("redis", redis_mock)
    lifecycle.register_connection("vector_db", vector_mock)
    lifecycle.register_connection("websocket", websocket_mock)
    print(f"   ✓ Registered {len(lifecycle.connections)} connections")

    # Add shutdown callback
    def on_shutdown():
        print("\n  Shutdown callback: Flushing logs...")

    lifecycle.add_shutdown_callback(on_shutdown)

    # Mark as started
    print("\n4. Starting service...")
    lifecycle.mark_started()
    print(f"   Status: {lifecycle.status.value}")
    print(f"   Can accept tasks: {lifecycle.can_accept_tasks()}")

    # Show health status
    print("\n5. Health Check...")
    health = lifecycle.get_health_status()
    print(f"   Status: {health['status']}")
    print(f"   Uptime: {health['uptime_seconds']:.2f}s")
    print(f"   Active Tasks: {health['active_tasks']}")
    print(f"   Connections: {health['connections']['count']}")
    for name, status in health['connections']['status'].items():
        icon = "✓" if status['healthy'] else "✗"
        print(f"     {icon} {name}")

    # Start some background tasks
    print("\n6. Starting background tasks...")

    # Task 1: Quick task
    task1_thread = threading.Thread(
        target=simulate_long_running_task,
        args=(lifecycle, "task_001", 3)
    )
    task1_thread.start()

    # Task 2: Medium task
    task2_thread = threading.Thread(
        target=simulate_long_running_task,
        args=(lifecycle, "task_002", 5)
    )
    task2_thread.start()

    # Wait a bit
    time.sleep(1)

    # Show active tasks
    print(f"\n   Active tasks: {len(lifecycle.active_tasks)}")
    for task_id, task in lifecycle.active_tasks.items():
        duration = time.time() - task.started_at
        print(f"     - {task_id}: {task.agent} ({duration:.1f}s)")

    print("\n7. Service running...")
    print("   (Waiting for tasks to complete or Ctrl+C to shutdown)")

    try:
        # Keep running until shutdown
        while not lifecycle.is_shutting_down():
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n\n✗ Keyboard interrupt received")

    # Wait for task threads
    print("\n8. Waiting for task threads to finish...")
    task1_thread.join(timeout=10)
    task2_thread.join(timeout=10)

    # Trigger shutdown (if not already triggered by signal)
    if not lifecycle.is_shutting_down():
        print("\n9. Initiating graceful shutdown...")
        lifecycle.shutdown(timeout=10)

    # Show final status
    print("\n" + "="*60)
    print("Shutdown Complete")
    print("="*60)
    print(f"Final Status: {lifecycle.status.value}")
    print(f"Connections closed: {len(lifecycle.connections) == 0}")

    # Verify all connections are closed
    if redis_mock.is_closed and vector_mock.is_closed and websocket_mock.is_closed:
        print("\n✓ All resources cleaned up successfully!")
    else:
        print("\n✗ Warning: Some resources may not have been cleaned up")

    print("\nDemo complete.\n")


if __name__ == '__main__':
    main()
