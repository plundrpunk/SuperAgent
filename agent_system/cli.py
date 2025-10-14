#!/usr/bin/env python3
"""
SuperAgent CLI
Command-line interface for the SuperAgent system.
"""
import sys
import argparse
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent_system.agents.kaya import KayaAgent
from agent_system.agents.runner import RunnerAgent
from agent_system.agents.critic import CriticAgent
from agent_system.router import Router
from agent_system.hitl.queue import HITLQueue


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description='SuperAgent - Voice-Controlled Multi-Agent Testing System')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Kaya orchestrator
    kaya_parser = subparsers.add_parser('kaya', help='Run Kaya orchestrator')
    kaya_parser.add_argument('command_text', nargs='+', help='Command to execute')

    # Runner
    runner_parser = subparsers.add_parser('run', help='Run a test')
    runner_parser.add_argument('test_path', help='Path to test file')

    # Critic
    critic_parser = subparsers.add_parser('review', help='Review a test with Critic')
    critic_parser.add_argument('test_path', help='Path to test file')

    # Router
    router_parser = subparsers.add_parser('route', help='Route a task')
    router_parser.add_argument('task_type', help='Task type (write_test, execute_test, etc.)')
    router_parser.add_argument('description', help='Task description')

    # HITL Queue
    hitl_parser = subparsers.add_parser('hitl', help='HITL queue operations')
    hitl_parser.add_argument('action', choices=['list', 'stats'], help='Queue action')

    # Status
    subparsers.add_parser('status', help='Show system status')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        if args.command == 'kaya':
            kaya = KayaAgent()
            command = ' '.join(args.command_text)
            result = kaya.execute(command)
            print(f"\n✓ Success: {result.success}")
            if result.data:
                print(f"Data: {result.data}")
            if result.error:
                print(f"✗ Error: {result.error}")
            print(f"Execution time: {result.execution_time_ms}ms")

        elif args.command == 'run':
            runner = RunnerAgent()
            result = runner.execute(args.test_path)
            print(f"\n✓ Test Status: {result.data.get('status')}")
            print(f"Passed: {result.data.get('passed_count')}")
            print(f"Failed: {result.data.get('failed_count')}")
            if result.data.get('errors'):
                print("\nErrors:")
                for error in result.data['errors']:
                    print(f"  - {error.get('message')}")
            print(f"\nExecution time: {result.execution_time_ms}ms")

        elif args.command == 'review':
            critic = CriticAgent()
            result = critic.execute(args.test_path)
            status = result.data.get('status')
            print(f"\n✓ Review Status: {status}")
            if status == 'rejected':
                print(f"\n✗ Issues found: {len(result.data.get('issues_found', []))}")
                for issue in result.data.get('issues_found', []):
                    print(f"  - {issue}")
            print(f"\nEstimated cost: ${result.data.get('estimated_cost_usd', 0):.4f}")
            print(f"Estimated duration: {result.data.get('estimated_duration_ms')}ms")
            print(f"Execution time: {result.execution_time_ms}ms")

        elif args.command == 'route':
            router = Router()
            decision = router.route(args.task_type, args.description)
            print(f"\n✓ Routing Decision:")
            print(f"  Agent: {decision.agent}")
            print(f"  Model: {decision.model}")
            print(f"  Max Cost: ${decision.max_cost_usd}")
            print(f"  Difficulty: {decision.difficulty}")
            print(f"  Complexity Score: {decision.complexity_score}")
            print(f"  Reason: {decision.reason}")

        elif args.command == 'hitl':
            queue = HITLQueue()
            if args.action == 'list':
                tasks = queue.list(limit=10)
                print(f"\n✓ HITL Queue ({len(tasks)} items):")
                for task in tasks:
                    print(f"  [{task['priority']:.2f}] {task['task_id']}: {task['feature']}")
                    print(f"     Attempts: {task['attempts']}, Error: {task['last_error'][:50]}...")
            elif args.action == 'stats':
                stats = queue.get_stats()
                print(f"\n✓ HITL Queue Statistics:")
                print(f"  Total: {stats['total_count']}")
                print(f"  Active: {stats['active_count']}")
                print(f"  Resolved: {stats['resolved_count']}")
                print(f"  Avg Priority: {stats['avg_priority']:.2f}")
                print(f"  High Priority: {stats['high_priority_count']}")

        elif args.command == 'status':
            print("\n✓ SuperAgent System Status")
            print("\nImplemented Components:")
            print("  ✓ Project structure and configuration")
            print("  ✓ Core router with cost enforcement")
            print("  ✓ Complexity estimator")
            print("  ✓ Validation rubric")
            print("  ✓ Redis client (hot state)")
            print("  ✓ Vector DB client (cold storage)")
            print("  ✓ Kaya orchestrator")
            print("  ✓ Runner agent (test executor)")
            print("  ✓ Critic agent (pre-validator)")
            print("  ✓ HITL queue system")
            print("\nReady for Development:")
            print("  - Scribe agent (test writer)")
            print("  - Medic agent (bug fixer)")
            print("  - Gemini agent (validator)")
            print("  - Voice integration")
            print("  - Observability dashboard")
            print("\nNext Steps:")
            print("  1. Install dependencies: pip install -r requirements.txt")
            print("  2. Set up Redis and Vector DB")
            print("  3. Configure API keys (.env file)")
            print("  4. Run integration tests")

    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
