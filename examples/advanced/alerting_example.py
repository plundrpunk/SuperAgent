#!/usr/bin/env python3
"""
Example: Alert System Integration with Event Stream

Demonstrates how to use AlertManager with MetricsAggregator
to monitor system health and send notifications.
"""
import asyncio
import time
from agent_system.observability import EventEmitter, AlertManager


async def main():
    """Demonstrate alert system with simulated events."""

    # Create event emitter (with metrics aggregation)
    emitter = EventEmitter(
        websocket_enabled=False,  # Disable for this example
        console_enabled=True,
        file_enabled=False
    )

    # Create alert manager
    alert_manager = AlertManager(
        console_enabled=True,
        webhook_enabled=False,
        email_enabled=False
    )

    print("=" * 70)
    print("SuperAgent Alert System Demo")
    print("=" * 70)
    print(f"\nLoaded {len(alert_manager.conditions)} alert conditions:\n")

    for condition in alert_manager.conditions:
        print(f"  - {condition.metric} {condition.operator} {condition.threshold}")
        print(f"    Action: {condition.action}")
        print(f"    Message: {condition.message}\n")

    print("\n" + "=" * 70)
    print("Simulating Events with Good Metrics")
    print("=" * 70 + "\n")

    # Simulate some events with GOOD metrics
    # Task 1: Simple test (low cost, passes)
    emitter.emit('task_queued', {
        'task_id': 't_001',
        'feature': 'login_test',
        'est_cost': 0.20,
        'timestamp': time.time()
    })

    emitter.emit('agent_started', {
        'agent': 'scribe',
        'task_id': 't_001',
        'model': 'claude-haiku',
        'tools': ['read', 'write']
    })

    await asyncio.sleep(0.5)

    emitter.emit('agent_completed', {
        'agent': 'scribe',
        'task_id': 't_001',
        'status': 'success',
        'duration_ms': 2000,
        'cost_usd': 0.05
    })

    # Record critic decision (approved)
    emitter.record_critic_decision(rejected=False)

    await asyncio.sleep(0.5)

    emitter.emit('validation_complete', {
        'task_id': 't_001',
        'result': {
            'browser_launched': True,
            'test_executed': True,
            'test_passed': True,
            'screenshots': ['screenshot1.png']
        },
        'cost': 0.15,
        'duration_ms': 3000,
        'screenshots': 1
    })

    # Check alerts (should be none)
    metrics = emitter.get_metrics()
    print("\nCurrent Metrics (Good):")
    for key, value in metrics.items():
        print(f"  {key}: {value:.4f}")

    triggered = alert_manager.check_alerts(metrics)
    print(f"\n✓ {len(triggered)} alerts triggered (expected: 0)\n")

    print("\n" + "=" * 70)
    print("Simulating Events with BAD Metrics (Triggers Alerts)")
    print("=" * 70 + "\n")

    # Simulate events that will trigger alerts

    # Critic rejections (to raise rejection rate)
    for i in range(6):
        emitter.record_critic_decision(rejected=True)

    for i in range(4):
        emitter.record_critic_decision(rejected=False)

    # Failed validations (to lower pass rate)
    for i in range(3):
        emitter.emit('validation_complete', {
            'task_id': f't_00{i+2}',
            'result': {
                'browser_launched': True,
                'test_executed': True,
                'test_passed': False,  # Failed
                'screenshots': []
            },
            'cost': 0.10,
            'duration_ms': 2000,
            'screenshots': 0
        })

    # High-cost features
    for i in range(3):
        emitter.emit('agent_completed', {
            'agent': 'scribe',
            'task_id': f't_00{i+5}',
            'status': 'success',
            'duration_ms': 5000,
            'cost_usd': 1.50  # High cost!
        })

    # High retry counts (HITL escalations)
    for i in range(3):
        emitter.emit('hitl_escalated', {
            'task_id': f't_00{i+8}',
            'attempts': 3,  # High retry count!
            'last_error': 'Selector timeout',
            'priority': 0.8
        })

    await asyncio.sleep(1)

    # Check alerts (should trigger multiple)
    metrics = emitter.get_metrics()
    print("\nCurrent Metrics (Bad):")
    for key, value in metrics.items():
        print(f"  {key}: {value:.4f}")

    print("\n" + "=" * 70)
    print("Checking Alert Conditions...")
    print("=" * 70 + "\n")

    triggered = alert_manager.check_alerts(metrics)
    print(f"\n⚠ {len(triggered)} alerts triggered!\n")

    # Show alert statistics
    print("\n" + "=" * 70)
    print("Alert Statistics")
    print("=" * 70 + "\n")

    stats = alert_manager.get_stats()
    print(f"Total alerts: {stats['total_alerts']}")
    print(f"\nAlerts by metric:")
    for metric, count in stats['alerts_by_metric'].items():
        print(f"  {metric}: {count}")
    print(f"\nAlerts by action:")
    for action, count in stats['alerts_by_action'].items():
        print(f"  {action}: {count}")

    if stats['most_recent']:
        print(f"\nMost recent alert:")
        recent = stats['most_recent']
        print(f"  Metric: {recent['metric']}")
        print(f"  Value: {recent['current_value']:.4f}")
        print(f"  Message: {recent['message']}")

    print("\n" + "=" * 70)
    print("Testing Rate Limiting")
    print("=" * 70 + "\n")

    # Try to trigger same alerts again (should be rate limited)
    print("Checking alerts again immediately (should be rate limited)...")
    triggered_again = alert_manager.check_alerts(metrics)
    print(f"✓ {len(triggered_again)} alerts triggered (expected: 0 due to rate limiting)\n")

    # Reset rate limits and try again
    print("Resetting rate limits and checking again...")
    alert_manager.reset_rate_limits()
    triggered_after_reset = alert_manager.check_alerts(metrics)
    print(f"⚠ {len(triggered_after_reset)} alerts triggered (rate limits reset)\n")

    print("\n" + "=" * 70)
    print("Demo Complete!")
    print("=" * 70)


if __name__ == '__main__':
    asyncio.run(main())
