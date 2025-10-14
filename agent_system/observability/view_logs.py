#!/usr/bin/env python3
"""
Log Viewer for SuperAgent Event Logs

A simple CLI tool for viewing and analyzing JSONL event logs.
Supports both compressed (.gz) and uncompressed logs with date filtering.

Usage:
    python view_logs.py                         # View all events
    python view_logs.py --tail 10               # View last 10 events
    python view_logs.py --follow                # Follow logs in real-time
    python view_logs.py --type task_queued      # Filter by event type
    python view_logs.py --stats                 # Show statistics
    python view_logs.py --date 2025-10-14       # View logs for specific date
    python view_logs.py --date-range 2025-10-01 2025-10-14  # Date range
    python view_logs.py --agent scribe          # Filter by agent
    python view_logs.py --task-id t_123         # Filter by task ID
"""
import json
import sys
import time
import gzip
import glob
from pathlib import Path
from collections import Counter
from datetime import datetime, timedelta
import argparse


# ANSI color codes
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    TASK = '\033[94m'      # Blue
    AGENT = '\033[92m'     # Green
    VALIDATION = '\033[95m' # Magenta
    HITL = '\033[93m'      # Yellow
    BUDGET = '\033[91m'    # Red
    INFO = '\033[96m'      # Cyan


def get_color_for_event(event_type):
    """Get color code for event type."""
    if 'task' in event_type:
        return Colors.TASK
    elif 'agent' in event_type:
        return Colors.AGENT
    elif 'validation' in event_type:
        return Colors.VALIDATION
    elif 'hitl' in event_type:
        return Colors.HITL
    elif 'budget' in event_type:
        return Colors.BUDGET
    else:
        return Colors.INFO


def format_event(event, show_timestamp=True):
    """Format event for display."""
    event_type = event.get('event_type', 'unknown')
    timestamp = event.get('timestamp', 0)
    payload = event.get('payload', {})

    color = get_color_for_event(event_type)

    # Format timestamp
    if show_timestamp:
        dt = datetime.fromtimestamp(timestamp)
        time_str = dt.strftime('%H:%M:%S')
        output = f"{color}{Colors.BOLD}[{time_str}] {event_type.upper()}{Colors.RESET}\n"
    else:
        output = f"{color}{Colors.BOLD}{event_type.upper()}{Colors.RESET}\n"

    # Format payload
    for key, value in payload.items():
        if isinstance(value, dict):
            output += f"  {key}:\n"
            for k, v in value.items():
                output += f"    {k}: {v}\n"
        else:
            output += f"  {key}: {value}\n"

    return output


def open_log_file(log_file):
    """
    Open log file (handles both compressed and uncompressed).

    Args:
        log_file: Path to log file

    Returns:
        File handle (text mode)
    """
    if log_file.suffix == '.gz':
        return gzip.open(log_file, 'rt', encoding='utf-8')
    else:
        return open(log_file, 'r', encoding='utf-8')


def read_events_from_file(log_file):
    """Read all events from a single log file."""
    events = []
    if not log_file.exists():
        return events

    try:
        with open_log_file(log_file) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        event = json.loads(line)
                        events.append(event)
                    except json.JSONDecodeError as e:
                        print(f"Warning: Failed to parse line in {log_file.name}: {e}", file=sys.stderr)
    except Exception as e:
        print(f"Error reading {log_file.name}: {e}", file=sys.stderr)

    return events


def find_log_files(log_dir, base_name='agent-events', date=None, start_date=None, end_date=None):
    """
    Find log files matching criteria.

    Args:
        log_dir: Directory containing logs
        base_name: Base name for log files
        date: Specific date (YYYY-MM-DD)
        start_date: Start date for range (YYYY-MM-DD)
        end_date: End date for range (YYYY-MM-DD)

    Returns:
        List of Path objects
    """
    log_dir = Path(log_dir)

    if date:
        # Specific date
        patterns = [
            log_dir / f"{base_name}-{date}.jsonl",
            log_dir / f"{base_name}-{date}.jsonl.gz"
        ]
        return [p for p in patterns if p.exists()]

    elif start_date and end_date:
        # Date range
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')

        files = []
        patterns = [
            str(log_dir / f"{base_name}-*.jsonl"),
            str(log_dir / f"{base_name}-*.jsonl.gz")
        ]

        for pattern in patterns:
            for file_path in glob.glob(pattern):
                file_path = Path(file_path)
                try:
                    # Extract date from filename
                    name = file_path.name
                    if name.endswith('.jsonl.gz'):
                        date_str = name.replace('.jsonl.gz', '').split('-', 2)[-1]
                    else:
                        date_str = name.replace('.jsonl', '').split('-', 2)[-1]

                    file_date = datetime.strptime(date_str, '%Y-%m-%d')

                    if start <= file_date <= end:
                        files.append(file_path)
                except (ValueError, IndexError):
                    continue

        return sorted(files)

    else:
        # All log files
        files = []
        patterns = [
            str(log_dir / f"{base_name}-*.jsonl"),
            str(log_dir / f"{base_name}-*.jsonl.gz")
        ]

        for pattern in patterns:
            files.extend([Path(p) for p in glob.glob(pattern)])

        return sorted(files)


def read_events(log_file_or_dir, date=None, start_date=None, end_date=None):
    """
    Read events from log file(s).

    Args:
        log_file_or_dir: Path to log file or directory
        date: Specific date filter (YYYY-MM-DD)
        start_date: Start date for range
        end_date: End date for range

    Returns:
        List of events
    """
    path = Path(log_file_or_dir)

    if path.is_dir():
        # Read from multiple files
        log_files = find_log_files(path, date=date, start_date=start_date, end_date=end_date)
        events = []
        for log_file in log_files:
            events.extend(read_events_from_file(log_file))
        return events
    else:
        # Single file
        return read_events_from_file(path)


def filter_events(events, agent=None, task_id=None, status=None):
    """
    Filter events by criteria.

    Args:
        events: List of events
        agent: Filter by agent name
        task_id: Filter by task ID
        status: Filter by status

    Returns:
        Filtered list of events
    """
    filtered = events

    if agent:
        filtered = [e for e in filtered if e.get('payload', {}).get('agent') == agent]

    if task_id:
        filtered = [e for e in filtered if e.get('payload', {}).get('task_id') == task_id]

    if status:
        filtered = [e for e in filtered if e.get('payload', {}).get('status') == status]

    return filtered


def view_all(log_file, tail=None, date=None, start_date=None, end_date=None, agent=None, task_id=None, status=None):
    """View all events with optional filters."""
    events = read_events(log_file, date=date, start_date=start_date, end_date=end_date)

    if not events:
        print("No events found.")
        return

    # Apply filters
    events = filter_events(events, agent=agent, task_id=task_id, status=status)

    if not events:
        print("No events matching filters.")
        return

    if tail:
        events = events[-tail:]

    for event in events:
        print(format_event(event))


def follow_logs(log_file):
    """Follow logs in real-time (like tail -f)."""
    print(f"Following {log_file} (Ctrl+C to stop)...\n")

    # Read existing events first
    if log_file.exists():
        with open(log_file, 'r') as f:
            f.seek(0, 2)  # Seek to end
            try:
                while True:
                    line = f.readline()
                    if line:
                        try:
                            event = json.loads(line.strip())
                            print(format_event(event))
                        except json.JSONDecodeError:
                            pass
                    else:
                        time.sleep(0.1)
            except KeyboardInterrupt:
                print("\nStopped following logs.")
    else:
        print(f"Log file {log_file} does not exist yet. Waiting for events...")
        while not log_file.exists():
            time.sleep(1)
        follow_logs(log_file)


def filter_by_type(log_file, event_type):
    """Filter events by type."""
    events = read_events(log_file)

    if not events:
        print("No events found.")
        return

    filtered = [e for e in events if e.get('event_type') == event_type]

    if not filtered:
        print(f"No events of type '{event_type}' found.")
        return

    print(f"Found {len(filtered)} events of type '{event_type}':\n")

    for event in filtered:
        print(format_event(event))


def show_stats(log_file):
    """Show statistics about events."""
    events = read_events(log_file)

    if not events:
        print("No events found.")
        return

    # Count by type
    event_types = Counter(e.get('event_type', 'unknown') for e in events)

    # Calculate metrics
    total_events = len(events)
    task_ids = set()
    total_cost = 0.0
    validation_total = 0
    validation_passed = 0
    critic_total = 0
    critic_rejected = 0
    completion_times = []

    for event in events:
        event_type = event.get('event_type')
        payload = event.get('payload', {})

        # Track task IDs
        if 'task_id' in payload:
            task_ids.add(payload['task_id'])

        # Track costs
        if event_type == 'agent_completed':
            if 'cost_usd' in payload:
                total_cost += payload['cost_usd']
            if payload.get('status') == 'rejected':
                critic_rejected += 1
                critic_total += 1
            elif payload.get('status') == 'approved':
                critic_total += 1

        # Track validations
        if event_type == 'validation_complete':
            validation_total += 1
            if 'cost' in payload:
                total_cost += payload['cost']
            result = payload.get('result', {})
            if isinstance(result, dict) and result.get('test_passed'):
                validation_passed += 1
            if 'duration_ms' in payload:
                completion_times.append(payload['duration_ms'] / 1000)

    # Print statistics
    print(f"{Colors.BOLD}Event Log Statistics{Colors.RESET}")
    print("=" * 60)
    print(f"Total events: {total_events}")
    print(f"Unique tasks: {len(task_ids)}")
    print(f"Total cost: ${total_cost:.2f}")

    if validation_total > 0:
        pass_rate = (validation_passed / validation_total) * 100
        print(f"Validation pass rate: {pass_rate:.1f}% ({validation_passed}/{validation_total})")

    if critic_total > 0:
        rejection_rate = (critic_rejected / critic_total) * 100
        print(f"Critic rejection rate: {rejection_rate:.1f}% ({critic_rejected}/{critic_total})")

    if completion_times:
        avg_time = sum(completion_times) / len(completion_times)
        print(f"Average completion time: {avg_time:.1f}s")

    print(f"\n{Colors.BOLD}Events by Type:{Colors.RESET}")
    for event_type, count in event_types.most_common():
        color = get_color_for_event(event_type)
        print(f"  {color}{event_type}{Colors.RESET}: {count}")

    # Time range
    if events:
        first_timestamp = events[0].get('timestamp', 0)
        last_timestamp = events[-1].get('timestamp', 0)
        first_time = datetime.fromtimestamp(first_timestamp).strftime('%Y-%m-%d %H:%M:%S')
        last_time = datetime.fromtimestamp(last_timestamp).strftime('%Y-%m-%d %H:%M:%S')
        print(f"\n{Colors.BOLD}Time Range:{Colors.RESET}")
        print(f"  First event: {first_time}")
        print(f"  Last event: {last_time}")


def search_logs(log_file, query):
    """Search logs for a query string."""
    events = read_events(log_file)

    if not events:
        print("No events found.")
        return

    matched = []
    for event in events:
        event_str = json.dumps(event).lower()
        if query.lower() in event_str:
            matched.append(event)

    if not matched:
        print(f"No events matching '{query}' found.")
        return

    print(f"Found {len(matched)} events matching '{query}':\n")

    for event in matched:
        print(format_event(event))


def main():
    parser = argparse.ArgumentParser(
        description='View and analyze SuperAgent event logs (supports compressed .gz files)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                      # View all events
  %(prog)s --tail 10                            # View last 10 events
  %(prog)s --follow                             # Follow logs in real-time
  %(prog)s --type task_queued                   # Filter by event type
  %(prog)s --stats                              # Show statistics
  %(prog)s --search "t_123"                     # Search for task ID
  %(prog)s --date 2025-10-14                    # View logs for specific date
  %(prog)s --date-range 2025-10-01 2025-10-14   # View logs in date range
  %(prog)s --agent scribe                       # Filter by agent
  %(prog)s --task-id t_123                      # Filter by task ID
  %(prog)s --status success                     # Filter by status
  %(prog)s --file custom.jsonl                  # Use custom log file
  %(prog)s --dir logs                           # Use logs directory
        """
    )

    parser.add_argument(
        '--file',
        help='Path to log file (single file mode)'
    )

    parser.add_argument(
        '--dir',
        default='logs',
        help='Path to logs directory (default: logs)'
    )

    parser.add_argument(
        '--tail',
        type=int,
        metavar='N',
        help='Show last N events'
    )

    parser.add_argument(
        '--follow', '-f',
        action='store_true',
        help='Follow logs in real-time (like tail -f)'
    )

    parser.add_argument(
        '--type',
        metavar='EVENT_TYPE',
        help='Filter by event type'
    )

    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show statistics'
    )

    parser.add_argument(
        '--search',
        metavar='QUERY',
        help='Search for query string in events'
    )

    parser.add_argument(
        '--date',
        metavar='YYYY-MM-DD',
        help='View logs for specific date'
    )

    parser.add_argument(
        '--date-range',
        nargs=2,
        metavar=('START', 'END'),
        help='View logs in date range (YYYY-MM-DD YYYY-MM-DD)'
    )

    parser.add_argument(
        '--agent',
        metavar='AGENT_NAME',
        help='Filter by agent name (e.g., scribe, runner, critic)'
    )

    parser.add_argument(
        '--task-id',
        metavar='TASK_ID',
        help='Filter by task ID'
    )

    parser.add_argument(
        '--status',
        metavar='STATUS',
        help='Filter by status (e.g., success, failed, pending)'
    )

    args = parser.parse_args()

    # Determine log path
    if args.file:
        log_path = Path(args.file)
    else:
        log_path = Path(args.dir)

    # Parse date range
    start_date = None
    end_date = None
    if args.date_range:
        start_date, end_date = args.date_range

    # Execute command
    if args.stats:
        show_stats(log_path)
    elif args.follow:
        # Follow only works with current log file
        if log_path.is_dir():
            current_log = log_path / f"agent-events-{datetime.now().strftime('%Y-%m-%d')}.jsonl"
            follow_logs(current_log)
        else:
            follow_logs(log_path)
    elif args.type:
        filter_by_type(log_path, args.type)
    elif args.search:
        search_logs(log_path, args.search)
    else:
        view_all(
            log_path,
            tail=args.tail,
            date=args.date,
            start_date=start_date,
            end_date=end_date,
            agent=args.agent,
            task_id=args.task_id,
            status=args.status
        )


if __name__ == '__main__':
    main()
