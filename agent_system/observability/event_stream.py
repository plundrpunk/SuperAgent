"""
WebSocket Event Streaming System for Real-Time Observability

Provides event emission to multiple destinations (WebSocket, console, file)
and metrics aggregation for SuperAgent system monitoring.

Features:
- Daily log rotation (logs/agent-events-YYYY-MM-DD.jsonl)
- Auto-compression of logs older than 7 days
- Auto-deletion of logs older than 30 days
- Structured event fields: timestamp, event_type, agent, task_id, status, cost, duration

Usage:
    from agent_system.observability import emit_event

    # Emit a task queued event
    emit_event('task_queued', {
        'task_id': 't_123',
        'feature': 'checkout',
        'est_cost': 0.25,
        'timestamp': time.time()
    })

    # Emit agent started event
    emit_event('agent_started', {
        'agent': 'scribe',
        'task_id': 't_123',
        'model': 'claude-sonnet-4.5',
        'tools': ['read', 'write', 'edit']
    })
"""
import asyncio
import json
import os
import time
import threading
import gzip
import glob
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field
from pathlib import Path
from enum import Enum

try:
    import websockets
    from websockets.server import WebSocketServerProtocol
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    print("Warning: websockets library not installed. WebSocket functionality disabled.")
    print("Install with: pip install websockets")

try:
    from agent_system.state.redis_client import RedisClient
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    RedisClient = None
    print("Warning: redis library not installed. Metrics storage disabled.")
    print("Install with: pip install redis")


class LogRotationManager:
    """
    Manages log file rotation, compression, and cleanup.

    Features:
    - Daily rotation: logs/agent-events-YYYY-MM-DD.jsonl
    - Compress logs older than 7 days (gzip)
    - Delete logs older than 30 days
    """

    def __init__(
        self,
        log_dir: Path,
        base_name: str = "agent-events",
        compress_after_days: int = 7,
        delete_after_days: int = 30
    ):
        """
        Initialize log rotation manager.

        Args:
            log_dir: Directory for log files
            base_name: Base name for log files
            compress_after_days: Compress logs older than this many days
            delete_after_days: Delete logs older than this many days
        """
        self.log_dir = log_dir
        self.base_name = base_name
        self.compress_after_days = compress_after_days
        self.delete_after_days = delete_after_days
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def get_current_log_path(self) -> Path:
        """Get path for today's log file."""
        today = datetime.now().strftime('%Y-%m-%d')
        return self.log_dir / f"{self.base_name}-{today}.jsonl"

    def get_log_path_for_date(self, date: datetime) -> Path:
        """Get log path for specific date."""
        date_str = date.strftime('%Y-%m-%d')
        return self.log_dir / f"{self.base_name}-{date_str}.jsonl"

    def compress_old_logs(self):
        """
        Compress logs older than compress_after_days.

        Compresses *.jsonl files to *.jsonl.gz
        """
        cutoff_date = datetime.now() - timedelta(days=self.compress_after_days)

        # Find all uncompressed log files
        pattern = str(self.log_dir / f"{self.base_name}-*.jsonl")
        for log_file in glob.glob(pattern):
            log_path = Path(log_file)

            # Skip if already compressed
            if log_path.suffix == '.gz':
                continue

            # Extract date from filename
            try:
                date_str = log_path.stem.split('-', 2)[-1]  # Get YYYY-MM-DD part
                file_date = datetime.strptime(date_str, '%Y-%m-%d')

                # Compress if older than threshold
                if file_date < cutoff_date:
                    self._compress_file(log_path)
            except (ValueError, IndexError):
                # Skip files with invalid date format
                continue

    def _compress_file(self, file_path: Path):
        """Compress a single log file with gzip."""
        compressed_path = Path(str(file_path) + '.gz')

        # Skip if compressed version already exists
        if compressed_path.exists():
            return

        try:
            with open(file_path, 'rb') as f_in:
                with gzip.open(compressed_path, 'wb') as f_out:
                    f_out.writelines(f_in)

            # Delete original after successful compression
            file_path.unlink()
            print(f"Compressed {file_path.name} -> {compressed_path.name}")
        except Exception as e:
            print(f"Failed to compress {file_path}: {e}")

    def delete_old_logs(self):
        """Delete logs older than delete_after_days."""
        cutoff_date = datetime.now() - timedelta(days=self.delete_after_days)

        # Find all log files (compressed and uncompressed)
        patterns = [
            str(self.log_dir / f"{self.base_name}-*.jsonl"),
            str(self.log_dir / f"{self.base_name}-*.jsonl.gz")
        ]

        for pattern in patterns:
            for log_file in glob.glob(pattern):
                log_path = Path(log_file)

                try:
                    # Extract date from filename
                    # Handle both .jsonl and .jsonl.gz
                    name = log_path.name
                    if name.endswith('.jsonl.gz'):
                        date_str = name.replace('.jsonl.gz', '').split('-', 2)[-1]
                    else:
                        date_str = name.replace('.jsonl', '').split('-', 2)[-1]

                    file_date = datetime.strptime(date_str, '%Y-%m-%d')

                    # Delete if older than threshold
                    if file_date < cutoff_date:
                        log_path.unlink()
                        print(f"Deleted old log: {log_path.name}")
                except (ValueError, IndexError):
                    # Skip files with invalid date format
                    continue

    def maintain_logs(self):
        """
        Perform log maintenance: compress old logs and delete very old logs.

        Should be called periodically (e.g., daily).
        """
        self.compress_old_logs()
        self.delete_old_logs()


class LogLevel(Enum):
    """Log levels for console output."""
    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3


class EventType(Enum):
    """Supported event types."""
    TASK_QUEUED = 'task_queued'
    AGENT_STARTED = 'agent_started'
    AGENT_COMPLETED = 'agent_completed'
    VALIDATION_COMPLETE = 'validation_complete'
    HITL_ESCALATED = 'hitl_escalated'
    BUDGET_WARNING = 'budget_warning'
    BUDGET_EXCEEDED = 'budget_exceeded'


# ANSI color codes for console output
class Colors:
    """ANSI color codes for pretty console output."""
    RESET = '\033[0m'
    BOLD = '\033[1m'

    # Event type colors
    TASK = '\033[94m'      # Blue
    AGENT = '\033[92m'     # Green
    VALIDATION = '\033[95m' # Magenta
    HITL = '\033[93m'      # Yellow
    BUDGET = '\033[91m'    # Red

    # Log level colors
    INFO = '\033[96m'      # Cyan
    WARNING = '\033[93m'   # Yellow
    ERROR = '\033[91m'     # Red
    SUCCESS = '\033[92m'   # Green


@dataclass
class Event:
    """
    Standard event structure for all emitted events.

    Attributes:
        event_type: Type of event (from EventType enum)
        timestamp: Unix timestamp when event occurred
        payload: Event-specific data fields
    """
    event_type: str
    timestamp: float
    payload: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return {
            'event_type': self.event_type,
            'timestamp': self.timestamp,
            'payload': self.payload
        }

    def to_json(self) -> str:
        """Convert event to JSON string."""
        return json.dumps(self.to_dict())


@dataclass
class MetricsAggregator:
    """
    Aggregates metrics from events and stores in Redis.

    Tracks:
    - agent_utilization: % of time agents are active
    - cost_per_feature: Average cost per completed feature
    - average_retry_count: Average number of retries per task
    - critic_rejection_rate: % of tests rejected by Critic
    - validation_pass_rate: % of validations that pass
    - time_to_completion: Average time from queue to completion
    """

    redis_client: Optional[Any]  # RedisClient or None
    window_minutes: int = 60

    # Metric counters (in-memory, periodically flushed to Redis)
    _agent_active_time: Dict[str, float] = field(default_factory=dict)
    _agent_start_times: Dict[str, float] = field(default_factory=dict)
    _feature_costs: List[float] = field(default_factory=list)
    _retry_counts: List[int] = field(default_factory=list)
    _critic_total: int = 0
    _critic_rejected: int = 0
    _validation_total: int = 0
    _validation_passed: int = 0
    _completion_times: List[float] = field(default_factory=list)
    _task_start_times: Dict[str, float] = field(default_factory=dict)

    def process_event(self, event: Event):
        """
        Process event and update metrics.

        Args:
            event: Event to process
        """
        event_type = event.event_type
        payload = event.payload

        if event_type == EventType.TASK_QUEUED.value:
            # Track task start time for completion time calculation
            task_id = payload.get('task_id')
            if task_id:
                self._task_start_times[task_id] = event.timestamp

        elif event_type == EventType.AGENT_STARTED.value:
            # Track agent start time for utilization
            agent = payload.get('agent')
            task_id = payload.get('task_id')
            if agent and task_id:
                key = f"{agent}:{task_id}"
                self._agent_start_times[key] = event.timestamp

        elif event_type == EventType.AGENT_COMPLETED.value:
            # Calculate agent utilization and track cost
            agent = payload.get('agent')
            task_id = payload.get('task_id')
            duration_ms = payload.get('duration_ms', 0)
            cost_usd = payload.get('cost_usd', 0)

            if agent and task_id:
                key = f"{agent}:{task_id}"
                if key in self._agent_start_times:
                    # Track active time
                    if agent not in self._agent_active_time:
                        self._agent_active_time[agent] = 0
                    self._agent_active_time[agent] += duration_ms / 1000.0  # Convert to seconds
                    del self._agent_start_times[key]

                # Track cost per feature (if this is a feature completion)
                if cost_usd > 0:
                    self._feature_costs.append(cost_usd)

        elif event_type == EventType.VALIDATION_COMPLETE.value:
            # Track validation pass rate
            self._validation_total += 1
            result = payload.get('result', {})
            if isinstance(result, dict):
                # Check if validation passed (all critical checks pass)
                passed = (
                    result.get('browser_launched', False) and
                    result.get('test_executed', False) and
                    result.get('test_passed', False)
                )
                if passed:
                    self._validation_passed += 1

            # Track time to completion
            task_id = payload.get('task_id')
            if task_id and task_id in self._task_start_times:
                completion_time = event.timestamp - self._task_start_times[task_id]
                self._completion_times.append(completion_time)
                del self._task_start_times[task_id]

            # Track cost
            cost = payload.get('cost', 0)
            if cost > 0:
                self._feature_costs.append(cost)

        elif event_type == EventType.HITL_ESCALATED.value:
            # Track retry count
            attempts = payload.get('attempts', 0)
            if attempts > 0:
                self._retry_counts.append(attempts)

        # Periodically flush to Redis
        self._maybe_flush()

    def _maybe_flush(self):
        """Flush metrics to Redis if it's time (every 60 events or 5 minutes)."""
        # Simple flush every 100 events (can be made time-based)
        total_events = (
            self._critic_total +
            self._validation_total +
            len(self._feature_costs) +
            len(self._retry_counts)
        )

        if total_events > 0 and total_events % 100 == 0:
            self.flush_to_redis()

    def flush_to_redis(self):
        """
        Flush current metrics to Redis with time buckets.

        Stores metrics in Redis with keys like:
        - metrics:hourly:2025-10-14T14:00:00
        - metrics:daily:2025-10-14
        """
        if not self.redis_client:
            # Redis not available, skip flush
            return

        now = datetime.now()

        # Calculate current metrics
        metrics = self.calculate_metrics()

        # Store in hourly bucket
        hourly_key = f"metrics:hourly:{now.strftime('%Y-%m-%dT%H:00:00')}"
        self.redis_client.set(hourly_key, metrics, ttl=7 * 24 * 3600)  # Keep for 7 days

        # Store in daily bucket
        daily_key = f"metrics:daily:{now.strftime('%Y-%m-%d')}"
        self.redis_client.set(daily_key, metrics, ttl=30 * 24 * 3600)  # Keep for 30 days

        # Reset in-memory counters after flush
        # (Keep running totals for the day)

    def calculate_metrics(self) -> Dict[str, float]:
        """
        Calculate current metrics from counters.

        Returns:
            Dictionary of metric name -> value
        """
        metrics = {}

        # Agent utilization (% of time active)
        total_active_time = sum(self._agent_active_time.values())
        window_seconds = self.window_minutes * 60
        if window_seconds > 0:
            metrics['agent_utilization'] = min(total_active_time / window_seconds, 1.0)
        else:
            metrics['agent_utilization'] = 0.0

        # Cost per feature
        if self._feature_costs:
            metrics['cost_per_feature'] = sum(self._feature_costs) / len(self._feature_costs)
        else:
            metrics['cost_per_feature'] = 0.0

        # Average retry count
        if self._retry_counts:
            metrics['average_retry_count'] = sum(self._retry_counts) / len(self._retry_counts)
        else:
            metrics['average_retry_count'] = 0.0

        # Critic rejection rate
        if self._critic_total > 0:
            metrics['critic_rejection_rate'] = self._critic_rejected / self._critic_total
        else:
            metrics['critic_rejection_rate'] = 0.0

        # Validation pass rate
        if self._validation_total > 0:
            metrics['validation_pass_rate'] = self._validation_passed / self._validation_total
        else:
            metrics['validation_pass_rate'] = 0.0

        # Time to completion (average)
        if self._completion_times:
            metrics['time_to_completion'] = sum(self._completion_times) / len(self._completion_times)
        else:
            metrics['time_to_completion'] = 0.0

        return metrics

    def record_critic_decision(self, rejected: bool):
        """
        Record a critic decision for rejection rate tracking.

        Args:
            rejected: True if test was rejected, False if approved
        """
        self._critic_total += 1
        if rejected:
            self._critic_rejected += 1


class EventEmitter:
    """
    Central event emitter that broadcasts to multiple destinations.

    Destinations:
    - WebSocket: Real-time streaming to connected clients
    - Console: Pretty-printed colored output
    - File: JSONL log file with daily rotation

    Usage:
        emitter = EventEmitter()
        await emitter.start()

        emitter.emit('task_queued', {
            'task_id': 't_123',
            'feature': 'checkout',
            'est_cost': 0.25,
            'timestamp': time.time()
        })
    """

    def __init__(
        self,
        websocket_enabled: bool = True,
        websocket_port: int = 3010,
        console_enabled: bool = True,
        console_level: LogLevel = LogLevel.INFO,
        file_enabled: bool = True,
        file_path: str = 'logs/agent-events.jsonl',
        redis_client: Optional[RedisClient] = None,
        enable_log_rotation: bool = True,
        compress_after_days: int = 7,
        delete_after_days: int = 30
    ):
        """
        Initialize event emitter.

        Args:
            websocket_enabled: Enable WebSocket server
            websocket_port: Port for WebSocket server
            console_enabled: Enable console logging
            console_level: Minimum log level for console
            file_enabled: Enable file logging
            file_path: Path to JSONL log file (or directory for rotation)
            redis_client: Redis client for metrics storage
            enable_log_rotation: Enable daily log rotation
            compress_after_days: Compress logs older than this many days
            delete_after_days: Delete logs older than this many days
        """
        self.websocket_enabled = websocket_enabled and WEBSOCKETS_AVAILABLE
        self.websocket_port = websocket_port
        self.console_enabled = console_enabled
        self.console_level = console_level
        self.file_enabled = file_enabled
        self.enable_log_rotation = enable_log_rotation

        # WebSocket state
        self.clients: Set[WebSocketServerProtocol] = set()
        self.server = None
        self.server_task = None

        # File state and log rotation
        if self.file_enabled:
            if enable_log_rotation:
                # Use log rotation with date-stamped files
                log_path = Path(file_path)
                self.log_dir = log_path.parent if log_path.suffix else log_path
                self.log_dir.mkdir(parents=True, exist_ok=True)

                # Initialize log rotation manager
                base_name = log_path.stem if log_path.suffix else 'agent-events'
                self.rotation_manager = LogRotationManager(
                    log_dir=self.log_dir,
                    base_name=base_name,
                    compress_after_days=compress_after_days,
                    delete_after_days=delete_after_days
                )

                # Run initial maintenance
                self.rotation_manager.maintain_logs()

                # Track last maintenance time
                self._last_maintenance = datetime.now()
            else:
                # Traditional single file logging
                self.file_path = Path(file_path)
                self.file_path.parent.mkdir(parents=True, exist_ok=True)
                self.rotation_manager = None

        # Metrics
        if REDIS_AVAILABLE:
            self.redis_client = redis_client or RedisClient()
        else:
            self.redis_client = None
        self.metrics = MetricsAggregator(redis_client=self.redis_client)

        # Event loop
        self.loop = None
        self._running = False

    async def start(self):
        """Start the event emitter (WebSocket server and Redis subscriber if enabled)."""
        self._running = True
        self.loop = asyncio.get_event_loop()

        if self.websocket_enabled:
            try:
                self.server = await websockets.serve(
                    self._handle_client,
                    'localhost',
                    self.websocket_port
                )
                print(f"{Colors.SUCCESS}WebSocket server started on ws://localhost:{self.websocket_port}/agent-events{Colors.RESET}")
            except Exception as e:
                print(f"{Colors.ERROR}Failed to start WebSocket server: {e}{Colors.RESET}")
                self.websocket_enabled = False

        # Start Redis subscriber to relay events from other processes
        if REDIS_AVAILABLE and self.redis_client:
            asyncio.create_task(self._redis_subscriber())
            print(f"{Colors.SUCCESS}Redis event subscriber started{Colors.RESET}")

    async def stop(self):
        """Stop the event emitter and close all connections gracefully."""
        print(f"{Colors.INFO}Shutting down event stream...{Colors.RESET}")
        self._running = False

        # Send shutdown notification to all clients
        if self.clients:
            shutdown_event = Event(
                event_type='service_shutdown',
                timestamp=time.time(),
                payload={'message': 'Server shutting down'}
            )
            await self._emit_websocket(shutdown_event)

        # Close WebSocket server
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            print(f"{Colors.INFO}WebSocket server closed{Colors.RESET}")

        # Close all client connections
        if self.clients:
            await asyncio.gather(
                *[client.close() for client in self.clients],
                return_exceptions=True
            )
            print(f"{Colors.INFO}All WebSocket clients disconnected{Colors.RESET}")

        # Flush metrics to Redis
        self.metrics.flush_to_redis()
        print(f"{Colors.INFO}Metrics flushed to Redis{Colors.RESET}")

        # Close Redis connection if available
        if self.redis_client:
            try:
                self.redis_client.close()
                print(f"{Colors.INFO}Redis connection closed{Colors.RESET}")
            except Exception as e:
                print(f"{Colors.ERROR}Failed to close Redis: {e}{Colors.RESET}")

        print(f"{Colors.SUCCESS}Event stream shutdown complete{Colors.RESET}")

    def close(self):
        """
        Synchronous close method for lifecycle management.

        This method is called by the lifecycle manager during shutdown.
        It creates a new event loop if needed and runs the async stop method.
        """
        try:
            # If we have a running loop, use it
            if self.loop and self.loop.is_running():
                # Schedule stop() as a task
                future = asyncio.run_coroutine_threadsafe(self.stop(), self.loop)
                future.result(timeout=10)  # Wait up to 10 seconds
            else:
                # Create new loop for synchronous context
                asyncio.run(self.stop())
        except Exception as e:
            print(f"{Colors.ERROR}Error during event stream close: {e}{Colors.RESET}")

    async def _handle_client(self, websocket: WebSocketServerProtocol):
        """
        Handle WebSocket client connection.

        Args:
            websocket: WebSocket connection
        """
        self.clients.add(websocket)
        try:
            # Send welcome message
            await websocket.send(json.dumps({
                'event_type': 'connection_established',
                'timestamp': time.time(),
                'message': 'Connected to SuperAgent event stream'
            }))

            # Keep connection alive
            async for message in websocket:
                # Echo back any messages (for ping/pong)
                await websocket.send(message)

        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.clients.remove(websocket)

    def emit(self, event_type: str, payload: Dict[str, Any]):
        """
        Emit event to all configured destinations.

        Args:
            event_type: Type of event (e.g., 'task_queued')
            payload: Event data
        """
        # Create event
        event = Event(
            event_type=event_type,
            timestamp=time.time(),
            payload=payload
        )

        # Emit to destinations
        if self.console_enabled:
            self._emit_console(event)

        if self.file_enabled:
            self._emit_file(event)

        if self.websocket_enabled and self.clients:
            asyncio.run_coroutine_threadsafe(
                self._emit_websocket(event),
                self.loop
            ) if self.loop else None

        # Update metrics
        self.metrics.process_event(event)

    def _emit_console(self, event: Event):
        """
        Emit event to console with pretty formatting.

        Args:
            event: Event to emit
        """
        event_type = event.event_type
        payload = event.payload
        timestamp = datetime.fromtimestamp(event.timestamp).strftime('%H:%M:%S')

        # Determine color based on event type
        if 'task' in event_type:
            color = Colors.TASK
        elif 'agent' in event_type:
            color = Colors.AGENT
        elif 'validation' in event_type:
            color = Colors.VALIDATION
        elif 'hitl' in event_type:
            color = Colors.HITL
        elif 'budget' in event_type:
            color = Colors.BUDGET
        else:
            color = Colors.INFO

        # Format event
        print(f"{color}{Colors.BOLD}[{timestamp}] {event_type.upper()}{Colors.RESET}")

        # Print payload fields
        for key, value in payload.items():
            print(f"  {key}: {value}")

        print()  # Blank line for readability

    def _emit_file(self, event: Event):
        """
        Emit event to JSONL file.

        With log rotation enabled, writes to date-stamped files and performs
        periodic maintenance (compression and cleanup).

        Args:
            event: Event to emit
        """
        try:
            if self.enable_log_rotation and self.rotation_manager:
                # Get current log file (date-stamped)
                current_log = self.rotation_manager.get_current_log_path()

                # Write event
                with open(current_log, 'a') as f:
                    f.write(event.to_json() + '\n')

                # Perform maintenance daily
                if (datetime.now() - self._last_maintenance).days >= 1:
                    self.rotation_manager.maintain_logs()
                    self._last_maintenance = datetime.now()
            else:
                # Traditional single file logging
                with open(self.file_path, 'a') as f:
                    f.write(event.to_json() + '\n')
        except Exception as e:
            print(f"{Colors.ERROR}Failed to write to log file: {e}{Colors.RESET}")

    async def _emit_websocket(self, event: Event):
        """
        Emit event to all connected WebSocket clients.

        Args:
            event: Event to emit
        """
        if not self.clients:
            return

        message = event.to_json()

        # Broadcast to all clients
        disconnected = set()
        for client in self.clients:
            try:
                await client.send(message)
            except websockets.exceptions.ConnectionClosed:
                disconnected.add(client)

        # Remove disconnected clients
        self.clients -= disconnected

    async def _redis_subscriber(self):
        """
        Subscribe to Redis 'agent-events' channel and relay to WebSocket clients.

        This allows events from other processes (like Kaya CLI) to reach the dashboard.
        """
        try:
            pubsub = self.redis_client.client.pubsub()
            pubsub.subscribe('agent-events')

            print(f"{Colors.INFO}Subscribed to Redis channel: agent-events{Colors.RESET}")

            while self._running:
                try:
                    message = pubsub.get_message(timeout=1.0)

                    if message and message['type'] == 'message':
                        # Parse event JSON
                        event_json = message['data'].decode('utf-8') if isinstance(message['data'], bytes) else message['data']
                        event_dict = json.loads(event_json)

                        # Create Event object
                        event = Event(
                            event_type=event_dict['event_type'],
                            timestamp=event_dict['timestamp'],
                            payload=event_dict['payload']
                        )

                        # Emit to all destinations (console, file, WebSocket)
                        if self.console_enabled:
                            self._emit_console(event)

                        if self.file_enabled:
                            self._emit_file(event)

                        if self.websocket_enabled and self.clients:
                            await self._emit_websocket(event)

                        # Update metrics
                        self.metrics.process_event(event)

                    await asyncio.sleep(0.01)  # Small delay to prevent busy loop

                except Exception as e:
                    print(f"{Colors.WARNING}Redis subscriber error: {e}{Colors.RESET}")
                    await asyncio.sleep(1.0)

        except Exception as e:
            print(f"{Colors.ERROR}Fatal Redis subscriber error: {e}{Colors.RESET}")
        finally:
            try:
                pubsub.unsubscribe('agent-events')
                pubsub.close()
            except:
                pass

    def get_metrics(self) -> Dict[str, float]:
        """
        Get current metrics.

        Returns:
            Dictionary of metric name -> value
        """
        return self.metrics.calculate_metrics()

    def record_critic_decision(self, rejected: bool):
        """
        Record a critic decision for tracking.

        Args:
            rejected: True if test was rejected
        """
        self.metrics.record_critic_decision(rejected)


# Global emitter instance
_global_emitter: Optional[EventEmitter] = None
_emitter_lock = threading.Lock()


def get_emitter() -> EventEmitter:
    """
    Get or create the global event emitter instance.

    Returns:
        Global EventEmitter instance
    """
    global _global_emitter

    if _global_emitter is None:
        with _emitter_lock:
            if _global_emitter is None:
                _global_emitter = EventEmitter()

    return _global_emitter


def emit_event(event_type: str, payload: Dict[str, Any]):
    """
    Convenience function to emit event using global emitter OR Redis pub/sub.

    This function tries TWO approaches:
    1. If global emitter exists and has event loop -> emit directly
    2. Otherwise -> publish to Redis for event stream server to pick up

    Args:
        event_type: Type of event
        payload: Event data

    Example:
        emit_event('task_queued', {
            'task_id': 't_123',
            'feature': 'checkout',
            'est_cost': 0.25,
            'timestamp': time.time()
        })
    """
    emitter = get_emitter()

    # Check if emitter has running event loop
    if emitter.loop and emitter.loop.is_running():
        # Emitter is started, emit normally
        emitter.emit(event_type, payload)
    else:
        # Emitter not started - use Redis pub/sub as bridge
        try:
            if REDIS_AVAILABLE:
                from agent_system.state.redis_client import RedisClient
                redis_client = RedisClient()

                event = Event(
                    event_type=event_type,
                    timestamp=time.time(),
                    payload=payload
                )

                # Publish to Redis channel
                redis_client.client.publish('agent-events', event.to_json())
            else:
                # No Redis, just log to console
                emitter.emit(event_type, payload)
        except Exception as e:
            # Fallback to console-only emission
            print(f"{Colors.WARNING}Warning: Could not publish to Redis: {e}{Colors.RESET}")
            emitter.emit(event_type, payload)


# Example usage
if __name__ == '__main__':
    import asyncio

    async def main():
        """Example usage of event streaming system."""
        # Create emitter
        emitter = EventEmitter(
            websocket_enabled=True,
            websocket_port=3010,
            console_enabled=True,
            file_enabled=True
        )

        # Start emitter
        await emitter.start()

        print(f"\n{Colors.SUCCESS}Event streaming system started!{Colors.RESET}\n")
        print(f"WebSocket server: ws://localhost:3010/agent-events")

        # Get log file path (handle rotation vs single file)
        if emitter.enable_log_rotation:
            log_path = emitter.rotation_manager.get_current_log_path()
        else:
            log_path = emitter.file_path
        print(f"Log file: {log_path}")
        print(f"\nEmitting example events...\n")

        # Emit some example events

        # 1. Task queued
        emitter.emit('task_queued', {
            'task_id': 't_001',
            'feature': 'user_authentication',
            'est_cost': 0.35,
            'timestamp': time.time()
        })

        await asyncio.sleep(1)

        # 2. Agent started
        emitter.emit('agent_started', {
            'agent': 'scribe',
            'task_id': 't_001',
            'model': 'claude-sonnet-4.5',
            'tools': ['read', 'write', 'edit', 'grep']
        })

        await asyncio.sleep(2)

        # 3. Agent completed
        emitter.emit('agent_completed', {
            'agent': 'scribe',
            'task_id': 't_001',
            'status': 'success',
            'duration_ms': 2500,
            'cost_usd': 0.12
        })

        await asyncio.sleep(1)

        # 4. Validation complete
        emitter.emit('validation_complete', {
            'task_id': 't_001',
            'result': {
                'browser_launched': True,
                'test_executed': True,
                'test_passed': True,
                'screenshots': ['screenshot1.png', 'screenshot2.png']
            },
            'cost': 0.08,
            'duration_ms': 5000,
            'screenshots': 2
        })

        await asyncio.sleep(1)

        # 5. Budget warning
        emitter.emit('budget_warning', {
            'current_spend': 0.85,
            'limit': 1.00,
            'remaining': 0.15
        })

        await asyncio.sleep(1)

        # Print metrics
        print(f"\n{Colors.BOLD}Current Metrics:{Colors.RESET}")
        metrics = emitter.get_metrics()
        for key, value in metrics.items():
            print(f"  {key}: {value:.4f}")

        print(f"\n{Colors.INFO}Event stream running. Press Ctrl+C to stop.{Colors.RESET}")

        # Keep running
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print(f"\n{Colors.WARNING}Shutting down...{Colors.RESET}")
            await emitter.stop()

    # Run example
    asyncio.run(main())
