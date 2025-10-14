#!/usr/bin/env python3
"""
SuperAgent CLI
Command-line interface for the SuperAgent system.
"""
import sys
import argparse
from pathlib import Path
import re

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent_system.agents.kaya import KayaAgent
from agent_system.agents.runner import RunnerAgent
from agent_system.agents.critic import CriticAgent
from agent_system.router import Router
from agent_system.hitl.queue import HITLQueue
from agent_system.cost_analytics import CostTracker
from agent_system.lifecycle import setup_lifecycle, get_lifecycle
from agent_system.state.redis_client import RedisClient
from agent_system.state.vector_client import VectorClient
from agent_system.secrets_manager import get_secrets_manager
from agent_system.observability import emit_event


def sanitize_test_path(path: str) -> str:
    """
    Sanitize test path to prevent path traversal attacks.

    Args:
        path: Test file path from user input

    Returns:
        Sanitized path string

    Raises:
        ValueError: If path is invalid or contains malicious patterns
    """
    # Remove any shell metacharacters
    dangerous_chars = [';', '&', '|', '`', '$', '\n', '\r']
    for char in dangerous_chars:
        if char in path:
            raise ValueError(f"Invalid character in path: {char}")

    # Reject path traversal attempts
    if '..' in path or path.startswith('/'):
        raise ValueError(f"Path traversal detected: {path}")

    # Ensure path is within allowed directories
    resolved = Path(path).resolve()
    project_root = Path(__file__).parent.parent
    allowed_dirs = [
        project_root / 'tests',
        project_root / 'artifacts',
        project_root / 'test-results',
    ]

    for allowed_dir in allowed_dirs:
        try:
            resolved.relative_to(allowed_dir.resolve())
            return path  # Path is valid
        except ValueError:
            continue

    raise ValueError(f"Path outside allowed directories: {path}")


def sanitize_command_text(text: str) -> str:
    """
    Sanitize user command text.

    Args:
        text: Raw command text from user

    Returns:
        Sanitized command text

    Raises:
        ValueError: If text contains invalid characters
    """
    # Remove shell metacharacters
    dangerous_chars = [';', '&', '|', '`', '$']
    for char in dangerous_chars:
        if char in text:
            raise ValueError(f"Invalid character in command: {char}")

    # Limit length
    if len(text) > 1000:
        raise ValueError("Command text too long (max 1000 characters)")

    return text.strip()


def main():
    """Main CLI entry point."""
    # Set up lifecycle management with signal handlers
    lifecycle = setup_lifecycle()

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

    # Cost Analytics
    cost_parser = subparsers.add_parser('cost', help='Cost analytics and reports')
    cost_parser.add_argument('action', choices=['daily', 'weekly', 'budget', 'by-agent', 'by-model', 'by-feature', 'trend'], help='Cost report type')
    cost_parser.add_argument('--date', help='Date for report (YYYY-MM-DD, default: today)', default=None)
    cost_parser.add_argument('--week', help='Week for report (YYYY-WXX, default: current week)', default=None)
    cost_parser.add_argument('--days', type=int, help='Number of days for trend report (default: 7)', default=7)

    # Status
    subparsers.add_parser('status', help='Show system status')

    # Metrics
    metrics_parser = subparsers.add_parser('metrics', help='Performance metrics and analytics')
    metrics_parser.add_argument('metric_type', choices=['summary', 'agent-utilization', 'cost-per-feature', 'rejection-rate', 'validation-rate', 'retry-count', 'model-usage', 'trend'], help='Metric type')
    metrics_parser.add_argument('--window', type=int, help='Time window in hours (default: 1)', default=1)
    metrics_parser.add_argument('--days', type=int, help='Number of days for trend (default: 7)', default=7)

    # Health
    subparsers.add_parser('health', help='Show service health status')

    # Secrets/Key Management
    secrets_parser = subparsers.add_parser('secrets', help='API key management and rotation')
    secrets_parser.add_argument('action', choices=['status', 'rotate', 'promote', 'remove-old', 'stats'], help='Secrets action')
    secrets_parser.add_argument('--service', choices=['anthropic', 'openai', 'gemini'], help='Service name')
    secrets_parser.add_argument('--new-key', help='New API key for rotation')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Check if service can accept tasks
    if args.command not in ['status', 'health'] and not lifecycle.can_accept_tasks():
        print(f"\n✗ Service is shutting down - cannot accept new tasks")
        sys.exit(1)

    try:
        # Register connections for cleanup
        redis_client = None
        vector_client = None
        if args.command == 'kaya':
            kaya = KayaAgent()
            command = ' '.join(args.command_text)
            # SECURITY: Sanitize command text
            command = sanitize_command_text(command)
            result = kaya.execute(command)
            print(f"\n✓ Success: {result.success}")
            if result.data:
                print(f"Data: {result.data}")
            if result.error:
                print(f"✗ Error: {result.error}")
            print(f"Execution time: {result.execution_time_ms}ms")

        elif args.command == 'run':
            runner = RunnerAgent()
            # SECURITY: Sanitize test path
            test_path = sanitize_test_path(args.test_path)
            result = runner.execute(test_path)
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
            # SECURITY: Sanitize test path
            test_path = sanitize_test_path(args.test_path)
            result = critic.execute(test_path)
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

        elif args.command == 'cost':
            tracker = CostTracker()

            if args.action == 'daily':
                report = tracker.get_daily_report(args.date)
                print(f"\n✓ Daily Cost Report: {report['date']}")
                print(f"  Total Cost: ${report['total_cost_usd']:.4f}")
                print(f"  Budget: ${report['budget_usd']:.2f}")
                print(f"  Remaining: ${report['remaining_usd']:.2f}")
                print(f"  Usage: {report['percent_used']:.1f}%")
                print(f"  Entries: {report['entry_count']}")

                if report['by_agent']:
                    print("\n  By Agent:")
                    for agent, cost in sorted(report['by_agent'].items(), key=lambda x: x[1], reverse=True):
                        print(f"    {agent:20s} ${cost:.4f}")

                if report['by_model']:
                    print("\n  By Model:")
                    for model, cost in sorted(report['by_model'].items(), key=lambda x: x[1], reverse=True):
                        print(f"    {model:20s} ${cost:.4f}")

                if report['by_feature']:
                    print("\n  By Feature:")
                    for feature, cost in sorted(report['by_feature'].items(), key=lambda x: x[1], reverse=True):
                        print(f"    {feature:30s} ${cost:.4f}")

            elif args.action == 'weekly':
                report = tracker.get_weekly_report(args.week)
                print(f"\n✓ Weekly Cost Report: {report['week']}")
                print(f"  Total Cost: ${report['total_cost_usd']:.4f}")
                print(f"  Entries: {report['entry_count']}")

                if report['by_agent']:
                    print("\n  By Agent:")
                    for agent, cost in sorted(report['by_agent'].items(), key=lambda x: x[1], reverse=True):
                        print(f"    {agent:20s} ${cost:.4f}")

                if report['by_model']:
                    print("\n  By Model:")
                    for model, cost in sorted(report['by_model'].items(), key=lambda x: x[1], reverse=True):
                        print(f"    {model:20s} ${cost:.4f}")

            elif args.action == 'budget':
                status = tracker.get_budget_status()

                print("\n✓ Budget Status")
                print("\nDaily Budget:")
                daily = status['daily']
                print(f"  Current Spend: ${daily['current_spend_usd']:.4f}")
                print(f"  Budget Limit: ${daily['budget_usd']:.2f}")
                print(f"  Remaining: ${daily['remaining_usd']:.2f}")
                print(f"  Usage: {daily['percent_used']:.1f}%")
                print(f"  Status: {daily['status'].upper()}")

                print("\nSession Budget:")
                session = status['session']
                print(f"  Session ID: {session['session_id']}")
                print(f"  Current Spend: ${session['current_spend_usd']:.4f}")
                print(f"  Budget Limit: ${session['budget_usd']:.2f}")
                print(f"  Remaining: ${session['remaining_usd']:.2f}")
                print(f"  Usage: {session['percent_used']:.1f}%")
                print(f"  Status: {session['status'].upper()}")

            elif args.action == 'by-agent':
                by_agent = tracker.get_cost_by_agent(args.date)
                date = args.date or tracker._get_date_key()
                print(f"\n✓ Cost by Agent: {date}")
                if by_agent:
                    for agent, cost in sorted(by_agent.items(), key=lambda x: x[1], reverse=True):
                        print(f"  {agent:20s} ${cost:.4f}")
                else:
                    print("  No cost data available")

            elif args.action == 'by-model':
                by_model = tracker.get_cost_by_model(args.date)
                date = args.date or tracker._get_date_key()
                print(f"\n✓ Cost by Model: {date}")
                if by_model:
                    for model, cost in sorted(by_model.items(), key=lambda x: x[1], reverse=True):
                        print(f"  {model:20s} ${cost:.4f}")
                else:
                    print("  No cost data available")

            elif args.action == 'by-feature':
                by_feature = tracker.get_cost_by_feature(args.date)
                date = args.date or tracker._get_date_key()
                print(f"\n✓ Cost by Feature: {date}")
                if by_feature:
                    for feature, cost in sorted(by_feature.items(), key=lambda x: x[1], reverse=True):
                        print(f"  {feature:30s} ${cost:.4f}")
                else:
                    print("  No cost data available")

            elif args.action == 'trend':
                trend = tracker.get_historical_trend(days=args.days)
                print(f"\n✓ Cost Trend (Last {args.days} Days)")
                print(f"  {'Date':<12} {'Total Cost':<12} {'Budget %':<12} {'Entries'}")
                print(f"  {'-'*12} {'-'*12} {'-'*12} {'-'*10}")

                for day_report in trend:
                    print(f"  {day_report['date']:<12} "
                          f"${day_report['total_cost_usd']:<11.4f} "
                          f"{day_report['percent_used']:<11.1f}% "
                          f"{day_report['entry_count']}")

                # Calculate summary
                total_cost = sum(d['total_cost_usd'] for d in trend)
                total_entries = sum(d['entry_count'] for d in trend)
                avg_daily = total_cost / len(trend) if trend else 0

                print(f"\n  Summary:")
                print(f"    Total Cost: ${total_cost:.4f}")
                print(f"    Total Entries: {total_entries}")
                print(f"    Avg Daily Cost: ${avg_daily:.4f}")

        elif args.command == 'metrics':
            from agent_system.metrics_aggregator import get_metrics_aggregator

            aggregator = get_metrics_aggregator()

            if args.metric_type == 'summary':
                summary = aggregator.get_metrics_summary(window_hours=args.window)
                print(f"\n✓ Metrics Summary (Last {args.window} Hour{'s' if args.window > 1 else ''})")

                print("\nAgent Utilization:")
                for agent, stats in summary['agent_utilization'].items():
                    print(f"  {agent:20s} {stats['utilization_percent']:>6.2f}% "
                          f"(active: {stats['active_time_ms']/1000:.1f}s, cost: ${stats['total_cost']:.4f})")

                print("\nCost Per Feature:")
                for feature, stats in summary['cost_per_feature'].items():
                    print(f"  {feature:30s} ${stats['average_cost']:.4f} (count: {stats['count']})")

                print(f"\nRetry & Rejection Metrics:")
                print(f"  Average Retry Count:       {summary['average_retry_count']:.2f}")
                print(f"  Critic Rejection Rate:     {summary['critic_rejection_rate']*100:.1f}%")
                print(f"  Validation Pass Rate:      {summary['validation_pass_rate']*100:.1f}%")

                print("\nModel Usage:")
                for model, stats in summary['model_usage'].items():
                    if stats['count'] > 0:
                        print(f"  {model:20s} count: {stats['count']}, cost: ${stats['total_cost']:.4f}")

            elif args.metric_type == 'agent-utilization':
                summary = aggregator.get_metrics_summary(window_hours=args.window)
                print(f"\n✓ Agent Utilization (Last {args.window} Hour{'s' if args.window > 1 else ''})")
                for agent, stats in summary['agent_utilization'].items():
                    print(f"  {agent:20s}")
                    print(f"    Utilization:    {stats['utilization_percent']:>6.2f}%")
                    print(f"    Active Time:    {stats['active_time_ms']/1000:.1f}s")
                    print(f"    Total Cost:     ${stats['total_cost']:.4f}")

            elif args.metric_type == 'cost-per-feature':
                summary = aggregator.get_metrics_summary(window_hours=args.window)
                print(f"\n✓ Cost Per Feature (Last {args.window} Hour{'s' if args.window > 1 else ''})")
                for feature, stats in summary['cost_per_feature'].items():
                    print(f"  {feature:30s}")
                    print(f"    Average Cost:   ${stats['average_cost']:.4f}")
                    print(f"    Total Cost:     ${stats['total_cost']:.4f}")
                    print(f"    Count:          {stats['count']}")

            elif args.metric_type == 'rejection-rate':
                summary = aggregator.get_metrics_summary(window_hours=args.window)
                print(f"\n✓ Critic Rejection Rate (Last {args.window} Hour{'s' if args.window > 1 else ''})")
                print(f"  Rejection Rate: {summary['critic_rejection_rate']*100:.1f}%")

            elif args.metric_type == 'validation-rate':
                summary = aggregator.get_metrics_summary(window_hours=args.window)
                print(f"\n✓ Validation Pass Rate (Last {args.window} Hour{'s' if args.window > 1 else ''})")
                print(f"  Pass Rate: {summary['validation_pass_rate']*100:.1f}%")

            elif args.metric_type == 'retry-count':
                summary = aggregator.get_metrics_summary(window_hours=args.window)
                print(f"\n✓ Average Retry Count (Last {args.window} Hour{'s' if args.window > 1 else ''})")
                print(f"  Average Retries: {summary['average_retry_count']:.2f}")

            elif args.metric_type == 'model-usage':
                summary = aggregator.get_metrics_summary(window_hours=args.window)
                print(f"\n✓ Model Usage (Last {args.window} Hour{'s' if args.window > 1 else ''})")
                for model, stats in summary['model_usage'].items():
                    if stats['count'] > 0:
                        print(f"  {model:20s}")
                        print(f"    Count:          {stats['count']}")
                        print(f"    Total Duration: {stats['total_duration_ms']/1000:.1f}s")
                        print(f"    Total Cost:     ${stats['total_cost']:.4f}")

            elif args.metric_type == 'trend':
                metric_name = 'cost_per_feature'  # Default trend metric
                trend = aggregator.get_historical_trend(metric_name, days=args.days)
                print(f"\n✓ Historical Trend - {metric_name.replace('_', ' ').title()} (Last {args.days} Days)")
                print(f"  {'Date':<12} {'Value':<12} {'Count'}")
                print(f"  {'-'*12} {'-'*12} {'-'*10}")

                for data_point in trend:
                    value = data_point.get('value', 0)
                    count = data_point.get('count', 0)
                    if metric_name == 'cost_per_feature':
                        print(f"  {data_point['date']:<12} ${value:<11.4f} {count}")
                    else:
                        print(f"  {data_point['date']:<12} {value:<12.4f} {count}")

        elif args.command == 'health':
            # Initialize clients for health check
            try:
                redis_client = RedisClient()
                lifecycle.register_connection("redis", redis_client)
            except Exception as e:
                print(f"Warning: Could not connect to Redis: {e}")

            try:
                vector_client = VectorClient()
                lifecycle.register_connection("vector_db", vector_client, close_method="client.close")
            except Exception as e:
                print(f"Warning: Could not connect to Vector DB: {e}")

            # Mark as started
            lifecycle.mark_started()

            # Get health status
            health = lifecycle.get_health_status()

            print(f"\n✓ Service Health Status")
            print(f"\nStatus: {health['status'].upper()}")
            print(f"Uptime: {health['uptime_seconds']:.2f}s")
            print(f"Active Tasks: {health['active_tasks']}")
            print(f"Can Accept Tasks: {'Yes' if health['can_accept_tasks'] else 'No'}")

            print(f"\nConnections ({health['connections']['count']}):")
            for name, status in health['connections']['status'].items():
                status_icon = "✓" if status['healthy'] else "✗"
                print(f"  {status_icon} {name}: {'healthy' if status['healthy'] else 'unhealthy'}")

            # Check for orphaned tasks
            if redis_client:
                orphaned = lifecycle.check_orphaned_tasks(redis_client)
                if orphaned:
                    print(f"\n⚠ Orphaned Tasks: {len(orphaned)}")
                    for task in orphaned[:5]:  # Show first 5
                        print(f"  - {task['task_id']}")

                    # Ask if should recover
                    print("\nRun 'lifecycle.recover_orphaned_tasks()' to reset these tasks")

        elif args.command == 'secrets':
            secrets_manager = get_secrets_manager()

            if args.action == 'status':
                # Show status for all services or specific service
                if args.service:
                    rotation_status = secrets_manager.get_rotation_status(args.service)
                    stats = secrets_manager.get_key_stats(args.service)

                    print(f"\n✓ Secrets Status: {args.service.upper()}")
                    print(f"\nKey Information:")
                    for key_info in stats['keys']:
                        print(f"  {key_info['type'].upper()}:")
                        print(f"    Key ID: {key_info['key_id']}")
                        print(f"    Is Primary: {key_info['is_primary']}")
                        print(f"    Usage Count: {key_info['usage_count']}")
                        print(f"    Failure Count: {key_info['failure_count']}")
                        if key_info['last_used_at']:
                            from datetime import datetime
                            last_used = datetime.fromtimestamp(key_info['last_used_at'])
                            print(f"    Last Used: {last_used.strftime('%Y-%m-%d %H:%M:%S')}")

                    if rotation_status:
                        print(f"\n  Rotation Status:")
                        print(f"    Old Key ID: {rotation_status['old_key_id']}")
                        print(f"    New Key ID: {rotation_status['new_key_id']}")
                        print(f"    Elapsed: {rotation_status['elapsed_hours']:.1f}h / {rotation_status['overlap_hours']}h")
                        print(f"    Remaining: {rotation_status['remaining_hours']:.1f}h")
                        print(f"    Can Remove Old: {rotation_status['can_remove_old_key']}")
                        print(f"    Completed: {rotation_status['completed']}")
                    else:
                        print(f"\n  No rotation in progress")
                else:
                    # Show all services
                    all_status = secrets_manager.get_all_services_status()
                    print("\n✓ Secrets Status (All Services)")

                    for service, status in all_status.items():
                        print(f"\n{service.upper()}:")
                        print(f"  Primary Key: {'✓' if status['has_primary'] else '✗'}")
                        print(f"  Secondary Key: {'✓' if status['has_secondary'] else '✗'}")
                        print(f"  Rotation: {'in progress' if status['rotation_in_progress'] else 'idle'}")

                        if status['rotation_in_progress']:
                            rot = status['rotation_status']
                            print(f"    Elapsed: {rot['elapsed_hours']:.1f}h / {rot['overlap_hours']}h")
                            print(f"    Can remove old: {rot['can_remove_old_key']}")

            elif args.action == 'rotate':
                # Rotate API key for service
                if not args.service:
                    print("\n✗ Error: --service required for rotation")
                    sys.exit(1)
                if not args.new_key:
                    print("\n✗ Error: --new-key required for rotation")
                    sys.exit(1)

                try:
                    success = secrets_manager.rotate_key(args.service, args.new_key)
                    if success:
                        print(f"\n✓ Key rotation started for {args.service}")
                        rotation_status = secrets_manager.get_rotation_status(args.service)
                        if rotation_status:
                            print(f"  Old Key ID: {rotation_status['old_key_id']}")
                            print(f"  New Key ID: {rotation_status['new_key_id']}")
                            print(f"  Overlap Period: {rotation_status['overlap_hours']} hours")
                            print(f"\n  During the overlap period, both keys are active.")
                            print(f"  After {rotation_status['overlap_hours']} hours, run:")
                            print(f"    python agent_system/cli.py secrets remove-old --service {args.service}")
                    else:
                        print(f"\n✗ Key rotation failed for {args.service}")
                except Exception as e:
                    print(f"\n✗ Error: {str(e)}")
                    sys.exit(1)

            elif args.action == 'promote':
                # Promote secondary key to primary
                if not args.service:
                    print("\n✗ Error: --service required for promotion")
                    sys.exit(1)

                try:
                    success = secrets_manager.promote_secondary_to_primary(args.service)
                    if success:
                        print(f"\n✓ Secondary key promoted to primary for {args.service}")
                    else:
                        print(f"\n✗ No secondary key to promote for {args.service}")
                except Exception as e:
                    print(f"\n✗ Error: {str(e)}")
                    sys.exit(1)

            elif args.action == 'remove-old':
                # Remove old key after rotation completes
                if not args.service:
                    print("\n✗ Error: --service required")
                    sys.exit(1)

                try:
                    success = secrets_manager.remove_old_key(args.service)
                    if success:
                        print(f"\n✓ Old key removed for {args.service}")
                        print(f"  Rotation completed successfully")
                    else:
                        print(f"\n✗ Failed to remove old key for {args.service}")
                except Exception as e:
                    print(f"\n✗ Error: {str(e)}")
                    sys.exit(1)

            elif args.action == 'stats':
                # Show key statistics
                if args.service:
                    stats = secrets_manager.get_key_stats(args.service)
                    print(f"\n✓ Key Statistics: {args.service.upper()}")
                    for key_info in stats['keys']:
                        print(f"\n  {key_info['type'].upper()} Key ({key_info['key_id']}):")
                        print(f"    Usage Count: {key_info['usage_count']}")
                        print(f"    Failure Count: {key_info['failure_count']}")
                        if key_info['last_used_at']:
                            from datetime import datetime
                            last_used = datetime.fromtimestamp(key_info['last_used_at'])
                            print(f"    Last Used: {last_used.strftime('%Y-%m-%d %H:%M:%S')}")
                        if key_info['last_failure_at']:
                            from datetime import datetime
                            last_failure = datetime.fromtimestamp(key_info['last_failure_at'])
                            print(f"    Last Failure: {last_failure.strftime('%Y-%m-%d %H:%M:%S')}")
                else:
                    # Show stats for all services
                    all_status = secrets_manager.get_all_services_status()
                    print("\n✓ Key Statistics (All Services)")
                    for service, status in all_status.items():
                        print(f"\n{service.upper()}:")
                        stats = status['stats']
                        for key_info in stats['keys']:
                            print(f"  {key_info['type']}: {key_info['key_id']} "
                                  f"(usage: {key_info['usage_count']}, failures: {key_info['failure_count']})")

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
            print("  ✓ Cost analytics and budget alerting")
            print("  ✓ Lifecycle management and graceful shutdown")
            print("  ✓ Secrets manager with key rotation")
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
    finally:
        # Clean shutdown on exit (if not already shutting down)
        if not lifecycle.is_shutting_down():
            lifecycle.shutdown(timeout=5)


if __name__ == '__main__':
    main()
