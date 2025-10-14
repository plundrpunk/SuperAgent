"""
Event Streaming Integration Example

Shows how agents should integrate with the event streaming system
for real-time observability.
"""
import asyncio
import time
from agent_system.observability import emit_event, get_emitter


async def example_agent_workflow():
    """
    Example of how an agent workflow should emit events.

    This demonstrates the complete lifecycle of a task through
    the SuperAgent system with proper event emission.
    """

    # Initialize event emitter
    emitter = get_emitter()
    await emitter.start()

    print("Starting example agent workflow...\n")

    # ========================================
    # 1. TASK QUEUED (Kaya receives request)
    # ========================================
    task_id = 't_example_001'
    emit_event('task_queued', {
        'task_id': task_id,
        'feature': 'user_checkout_flow',
        'est_cost': 0.45,
        'timestamp': time.time()
    })

    await asyncio.sleep(1)

    # ========================================
    # 2. AGENT STARTED (Scribe begins work)
    # ========================================
    emit_event('agent_started', {
        'agent': 'scribe',
        'task_id': task_id,
        'model': 'claude-sonnet-4.5',
        'tools': ['read', 'write', 'edit', 'grep']
    })

    # Simulate Scribe writing test
    print("Scribe is writing Playwright test...")
    await asyncio.sleep(2)

    # ========================================
    # 3. AGENT COMPLETED (Scribe finishes)
    # ========================================
    emit_event('agent_completed', {
        'agent': 'scribe',
        'task_id': task_id,
        'status': 'success',
        'duration_ms': 2500,
        'cost_usd': 0.15
    })

    await asyncio.sleep(1)

    # ========================================
    # 4. AGENT STARTED (Critic reviews)
    # ========================================
    emit_event('agent_started', {
        'agent': 'critic',
        'task_id': task_id,
        'model': 'claude-haiku',
        'tools': ['read', 'grep']
    })

    # Simulate Critic review
    print("Critic is reviewing test quality...")
    await asyncio.sleep(1)

    # Critic approves (record decision)
    emitter.record_critic_decision(rejected=False)

    # ========================================
    # 5. AGENT COMPLETED (Critic approves)
    # ========================================
    emit_event('agent_completed', {
        'agent': 'critic',
        'task_id': task_id,
        'status': 'approved',
        'duration_ms': 800,
        'cost_usd': 0.02
    })

    await asyncio.sleep(1)

    # ========================================
    # 6. AGENT STARTED (Runner executes)
    # ========================================
    emit_event('agent_started', {
        'agent': 'runner',
        'task_id': task_id,
        'model': 'claude-haiku',
        'tools': ['bash', 'read', 'grep']
    })

    # Simulate Runner execution
    print("Runner is executing test...")
    await asyncio.sleep(1.5)

    # ========================================
    # 7. AGENT COMPLETED (Runner finishes)
    # ========================================
    emit_event('agent_completed', {
        'agent': 'runner',
        'task_id': task_id,
        'status': 'success',
        'duration_ms': 1500,
        'cost_usd': 0.03
    })

    await asyncio.sleep(1)

    # ========================================
    # 8. AGENT STARTED (Gemini validates)
    # ========================================
    emit_event('agent_started', {
        'agent': 'gemini',
        'task_id': task_id,
        'model': 'gemini-2.5-pro',
        'tools': ['browser_automation']
    })

    # Simulate Gemini validation
    print("Gemini is validating with browser automation...")
    await asyncio.sleep(3)

    # ========================================
    # 9. VALIDATION COMPLETE (Success!)
    # ========================================
    emit_event('validation_complete', {
        'task_id': task_id,
        'result': {
            'browser_launched': True,
            'test_executed': True,
            'test_passed': True,
            'screenshots': ['step1.png', 'step2.png', 'step3.png'],
            'execution_time_ms': 12000,
            'console_errors': [],
            'network_failures': []
        },
        'cost': 0.25,
        'duration_ms': 12000,
        'screenshots': 3
    })

    await asyncio.sleep(1)

    # ========================================
    # 10. BUDGET WARNING (Optional)
    # ========================================
    total_cost = 0.15 + 0.02 + 0.03 + 0.25  # = 0.45
    budget_limit = 0.50

    if total_cost > budget_limit * 0.8:  # 80% threshold
        emit_event('budget_warning', {
            'current_spend': total_cost,
            'limit': budget_limit,
            'remaining': budget_limit - total_cost
        })

    print("\n" + "=" * 60)
    print("WORKFLOW COMPLETE")
    print("=" * 60)

    # Show final metrics
    metrics = emitter.get_metrics()
    print("\nFinal Metrics:")
    for key, value in metrics.items():
        print(f"  {key}: {value:.4f}")

    # Keep server running briefly
    await asyncio.sleep(2)

    # Cleanup
    await emitter.stop()


async def example_failure_workflow():
    """
    Example workflow showing failure handling and HITL escalation.
    """

    emitter = get_emitter()
    await emitter.start()

    print("\nStarting failure handling example...\n")

    task_id = 't_example_002'

    # Task queued
    emit_event('task_queued', {
        'task_id': task_id,
        'feature': 'payment_processing',
        'est_cost': 0.50,
        'timestamp': time.time()
    })

    await asyncio.sleep(1)

    # Scribe writes test
    emit_event('agent_started', {
        'agent': 'scribe',
        'task_id': task_id,
        'model': 'claude-sonnet-4.5',
        'tools': ['read', 'write', 'edit']
    })

    await asyncio.sleep(2)

    emit_event('agent_completed', {
        'agent': 'scribe',
        'task_id': task_id,
        'status': 'success',
        'duration_ms': 2000,
        'cost_usd': 0.12
    })

    # Runner executes - FAILS
    emit_event('agent_started', {
        'agent': 'runner',
        'task_id': task_id,
        'model': 'claude-haiku',
        'tools': ['bash', 'read']
    })

    await asyncio.sleep(1)

    emit_event('agent_completed', {
        'agent': 'scribe',
        'task_id': task_id,
        'status': 'failed',
        'duration_ms': 1000,
        'cost_usd': 0.02
    })

    # Medic attempts fix - Attempt 1
    print("Medic attempting first fix...")
    emit_event('agent_started', {
        'agent': 'medic',
        'task_id': task_id,
        'model': 'claude-sonnet-4.5',
        'tools': ['read', 'edit', 'bash']
    })

    await asyncio.sleep(2)

    emit_event('agent_completed', {
        'agent': 'medic',
        'task_id': task_id,
        'status': 'failed',
        'duration_ms': 2000,
        'cost_usd': 0.15
    })

    # Medic attempts fix - Attempt 2
    print("Medic attempting second fix...")
    await asyncio.sleep(2)

    emit_event('agent_completed', {
        'agent': 'medic',
        'task_id': task_id,
        'status': 'failed',
        'duration_ms': 2200,
        'cost_usd': 0.16
    })

    # HITL Escalation after 2 failed attempts
    print("\nEscalating to human-in-the-loop...")
    emit_event('hitl_escalated', {
        'task_id': task_id,
        'attempts': 2,
        'last_error': 'Selector not found: [data-testid="payment-submit"]',
        'priority': 'high'
    })

    # Budget exceeded
    total_cost = 0.12 + 0.02 + 0.15 + 0.16  # = 0.45
    budget_limit = 0.50

    if total_cost > budget_limit:
        emit_event('budget_exceeded', {
            'current_spend': total_cost,
            'limit': budget_limit,
            'tasks_blocked': 1
        })

    print("\n" + "=" * 60)
    print("FAILURE WORKFLOW COMPLETE - ESCALATED TO HITL")
    print("=" * 60)

    await asyncio.sleep(2)
    await emitter.stop()


async def example_websocket_client():
    """
    Example WebSocket client that listens to events.

    Run this in a separate terminal to see events in real-time.
    """
    try:
        import websockets

        print("Connecting to event stream...")
        async with websockets.connect('ws://localhost:3010') as websocket:
            print("Connected! Listening for events...\n")

            async for message in websocket:
                event = json.loads(message)
                print(f"[{event['event_type']}]")
                print(f"  Payload: {event['payload']}")
                print()

    except ImportError:
        print("websockets library not installed")
        print("Install with: pip install websockets")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == '--client':
        # Run as WebSocket client
        asyncio.run(example_websocket_client())
    elif len(sys.argv) > 1 and sys.argv[1] == '--failure':
        # Run failure workflow
        asyncio.run(example_failure_workflow())
    else:
        # Run success workflow
        asyncio.run(example_agent_workflow())
