"""
Service Lifecycle Management for SuperAgent

Manages graceful startup, health checks, and shutdown for SuperAgent service.
Ensures clean resource cleanup for Docker containers, Redis, Vector DB, and WebSocket servers.

Features:
- Signal handler registration (SIGTERM, SIGINT)
- Graceful shutdown with timeout
- Active task tracking and completion
- Connection registry and cleanup
- Orphaned task detection and recovery
- Health check endpoint
"""
import signal
import sys
import threading
import time
import logging
import os
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """Service lifecycle states."""
    STARTING = "starting"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    SHUTTING_DOWN = "shutting_down"
    STOPPED = "stopped"


@dataclass
class ConnectionInfo:
    """Information about a registered connection."""
    name: str
    connection: Any
    close_method: str = "close"  # Method name to call for cleanup
    registered_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ActiveTask:
    """Information about an active task."""
    task_id: str
    started_at: float
    agent: Optional[str] = None
    feature: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ServiceLifecycle:
    """
    Manages service startup, health checks, and graceful shutdown.

    Responsibilities:
    - Register signal handlers (SIGTERM, SIGINT)
    - Track active tasks and connections
    - Coordinate graceful shutdown
    - Clean up resources in proper order
    - Detect orphaned tasks from previous crashes

    Usage:
        lifecycle = ServiceLifecycle()

        # Register connections
        lifecycle.register_connection("redis", redis_client)
        lifecycle.register_connection("vector_db", vector_client)

        # Register signal handlers
        lifecycle.setup_signal_handlers()

        # Start service
        lifecycle.mark_started()

        # Track tasks
        lifecycle.add_active_task("t_123", agent="scribe", feature="login")
        # ... do work ...
        lifecycle.remove_active_task("t_123")

        # Graceful shutdown (called automatically on signals)
        lifecycle.shutdown(timeout=30)
    """

    def __init__(self):
        """Initialize lifecycle manager."""
        self.shutdown_event = threading.Event()
        self.active_tasks: Dict[str, ActiveTask] = {}
        self.connections: Dict[str, ConnectionInfo] = {}
        self.status = ServiceStatus.STARTING
        self.started_at: Optional[float] = None
        self.shutdown_callbacks: List[Callable] = []
        self._lock = threading.Lock()

        # Shutdown state
        self._shutdown_in_progress = False
        self._original_handlers: Dict[signal.Signals, Any] = {}

        logger.info("ServiceLifecycle initialized")

    def setup_signal_handlers(self):
        """
        Register signal handlers for graceful shutdown.

        Handles:
        - SIGTERM: Docker stop, systemd stop
        - SIGINT: Ctrl+C
        """
        # Store original handlers for restoration
        for sig in [signal.SIGTERM, signal.SIGINT]:
            self._original_handlers[sig] = signal.getsignal(sig)
            signal.signal(sig, self._signal_handler)

        logger.info("Signal handlers registered (SIGTERM, SIGINT)")

    def _signal_handler(self, signum: int, frame):
        """
        Handle shutdown signals.

        Args:
            signum: Signal number
            frame: Current stack frame
        """
        sig_name = signal.Signals(signum).name
        logger.info(f"Received signal {sig_name} ({signum}), initiating graceful shutdown")

        # Trigger shutdown
        self.shutdown()

    def mark_started(self):
        """Mark service as started and healthy."""
        self.started_at = time.time()
        self.status = ServiceStatus.HEALTHY
        logger.info("Service marked as started and healthy")

    def register_connection(
        self,
        name: str,
        connection: Any,
        close_method: str = "close",
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Register a connection for cleanup on shutdown.

        Args:
            name: Connection name (e.g., "redis", "vector_db")
            connection: Connection object
            close_method: Method name to call for cleanup (default: "close")
            metadata: Optional metadata about connection

        Example:
            lifecycle.register_connection("redis", redis_client)
            lifecycle.register_connection("vector_db", vector_client)
            lifecycle.register_connection("websocket", ws_server, close_method="stop")
        """
        with self._lock:
            self.connections[name] = ConnectionInfo(
                name=name,
                connection=connection,
                close_method=close_method,
                metadata=metadata or {}
            )
        logger.info(f"Registered connection: {name}")

    def unregister_connection(self, name: str) -> bool:
        """
        Unregister a connection.

        Args:
            name: Connection name

        Returns:
            True if connection was found and removed
        """
        with self._lock:
            if name in self.connections:
                del self.connections[name]
                logger.info(f"Unregistered connection: {name}")
                return True
            return False

    def add_active_task(
        self,
        task_id: str,
        agent: Optional[str] = None,
        feature: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Track an active task.

        Args:
            task_id: Unique task identifier
            agent: Agent handling the task
            feature: Feature being tested
            metadata: Additional task metadata
        """
        with self._lock:
            self.active_tasks[task_id] = ActiveTask(
                task_id=task_id,
                started_at=time.time(),
                agent=agent,
                feature=feature,
                metadata=metadata or {}
            )
        logger.debug(f"Added active task: {task_id} (agent={agent}, feature={feature})")

    def remove_active_task(self, task_id: str) -> bool:
        """
        Mark task as completed.

        Args:
            task_id: Task identifier

        Returns:
            True if task was found and removed
        """
        with self._lock:
            if task_id in self.active_tasks:
                task = self.active_tasks[task_id]
                duration = time.time() - task.started_at
                del self.active_tasks[task_id]
                logger.debug(f"Removed active task: {task_id} (duration={duration:.2f}s)")
                return True
            return False

    def is_shutting_down(self) -> bool:
        """
        Check if shutdown is in progress.

        Returns:
            True if shutdown event is set
        """
        return self.shutdown_event.is_set()

    def can_accept_tasks(self) -> bool:
        """
        Check if service can accept new tasks.

        Returns:
            True if service is healthy and not shutting down
        """
        return self.status == ServiceStatus.HEALTHY and not self.is_shutting_down()

    def add_shutdown_callback(self, callback: Callable):
        """
        Add a callback to be called during shutdown.

        Callbacks are called in FIFO order before connection cleanup.

        Args:
            callback: Callable to invoke during shutdown
        """
        self.shutdown_callbacks.append(callback)
        logger.debug(f"Added shutdown callback: {callback.__name__}")

    def shutdown(self, timeout: int = 30):
        """
        Graceful shutdown sequence.

        Steps:
        1. Set shutdown event (stop accepting new tasks)
        2. Wait for active tasks to complete (up to timeout)
        3. Call shutdown callbacks
        4. Close all registered connections
        5. Mark service as stopped

        Args:
            timeout: Maximum seconds to wait for active tasks (default: 30)
        """
        # Prevent multiple shutdown attempts
        if self._shutdown_in_progress:
            logger.warning("Shutdown already in progress")
            return

        self._shutdown_in_progress = True
        self.status = ServiceStatus.SHUTTING_DOWN
        logger.info(f"Starting graceful shutdown (timeout={timeout}s)")

        # Step 1: Signal shutdown (stop accepting new tasks)
        self.shutdown_event.set()
        logger.info("Shutdown event set - no new tasks will be accepted")

        # Step 2: Wait for active tasks to complete
        self._wait_for_tasks(timeout)

        # Step 3: Call shutdown callbacks
        self._call_shutdown_callbacks()

        # Step 4: Close all connections
        self._close_connections()

        # Step 5: Flush logs
        self._flush_logs()

        # Step 6: Mark as stopped
        self.status = ServiceStatus.STOPPED
        logger.info("Service shutdown complete")

    def _wait_for_tasks(self, timeout: int):
        """
        Wait for active tasks to complete.

        Args:
            timeout: Maximum seconds to wait
        """
        start_time = time.time()
        active_count = len(self.active_tasks)

        if active_count == 0:
            logger.info("No active tasks to wait for")
            return

        logger.info(f"Waiting for {active_count} active task(s) to complete...")

        while len(self.active_tasks) > 0 and (time.time() - start_time) < timeout:
            remaining = timeout - (time.time() - start_time)
            logger.info(f"Active tasks: {len(self.active_tasks)}, timeout in {remaining:.1f}s")

            # List active tasks
            with self._lock:
                for task_id, task in list(self.active_tasks.items()):
                    duration = time.time() - task.started_at
                    logger.info(f"  - {task_id}: {task.agent} ({duration:.1f}s)")

            time.sleep(1)

        # Check if tasks completed
        if len(self.active_tasks) == 0:
            logger.info("All active tasks completed successfully")
        else:
            logger.warning(f"Timeout reached - forcing shutdown with {len(self.active_tasks)} active task(s)")
            # Log tasks that didn't complete
            with self._lock:
                for task_id, task in self.active_tasks.items():
                    duration = time.time() - task.started_at
                    logger.warning(f"  Incomplete task: {task_id} ({task.agent}, {duration:.1f}s)")

    def _call_shutdown_callbacks(self):
        """Call all registered shutdown callbacks."""
        if not self.shutdown_callbacks:
            return

        logger.info(f"Calling {len(self.shutdown_callbacks)} shutdown callback(s)")

        for callback in self.shutdown_callbacks:
            try:
                logger.debug(f"Calling shutdown callback: {callback.__name__}")
                callback()
            except Exception as e:
                logger.error(f"Shutdown callback {callback.__name__} failed: {e}", exc_info=True)

    def _close_connections(self):
        """Close all registered connections in reverse registration order."""
        if not self.connections:
            logger.info("No connections to close")
            return

        logger.info(f"Closing {len(self.connections)} connection(s)")

        # Close in reverse order (LIFO)
        connection_list = list(self.connections.values())
        connection_list.reverse()

        for conn_info in connection_list:
            try:
                logger.info(f"Closing connection: {conn_info.name}")

                # Get close method
                close_method = getattr(conn_info.connection, conn_info.close_method, None)

                if close_method and callable(close_method):
                    close_method()
                    logger.info(f"Successfully closed {conn_info.name}")
                else:
                    logger.warning(f"Connection {conn_info.name} has no {conn_info.close_method} method")

            except Exception as e:
                logger.error(f"Failed to close {conn_info.name}: {e}", exc_info=True)

        # Clear connections dict
        with self._lock:
            self.connections.clear()

    def _flush_logs(self):
        """Flush all log handlers."""
        logger.info("Flushing logs...")
        try:
            logging.shutdown()
        except Exception as e:
            # Log to stderr since logging may be unavailable
            print(f"Failed to flush logs: {e}", file=sys.stderr)

    def get_health_status(self) -> Dict[str, Any]:
        """
        Get current health status.

        Returns:
            Dict with service health information
        """
        uptime = time.time() - self.started_at if self.started_at else 0

        with self._lock:
            active_task_count = len(self.active_tasks)
            connection_count = len(self.connections)

            # Build connection status
            connection_status = {}
            for name, conn_info in self.connections.items():
                # Try to check connection health
                health_ok = True
                try:
                    # Try calling health_check method if available
                    if hasattr(conn_info.connection, 'health_check'):
                        health_ok = conn_info.connection.health_check()
                    elif hasattr(conn_info.connection, 'ping'):
                        health_ok = conn_info.connection.ping()
                except Exception:
                    health_ok = False

                connection_status[name] = {
                    'healthy': health_ok,
                    'registered_at': conn_info.registered_at
                }

        return {
            'status': self.status.value,
            'uptime_seconds': uptime,
            'active_tasks': active_task_count,
            'connections': {
                'count': connection_count,
                'status': connection_status
            },
            'shutdown_in_progress': self._shutdown_in_progress,
            'can_accept_tasks': self.can_accept_tasks(),
            'timestamp': time.time()
        }

    def check_orphaned_tasks(self, redis_client) -> List[Dict[str, Any]]:
        """
        Check for orphaned tasks from previous crashes.

        Orphaned tasks are tasks in Redis that were started but never completed
        due to service crash or unclean shutdown.

        Args:
            redis_client: Redis client to query

        Returns:
            List of orphaned task info dicts
        """
        orphaned = []

        try:
            # Look for task status keys that are stuck in "doing" state
            pattern = "task:*:status"
            task_keys = redis_client.keys(pattern)

            for key in task_keys:
                status = redis_client.get(key)
                if status == "doing":
                    # Extract task_id from key (task:<task_id>:status)
                    task_id = key.split(':')[1]

                    # Try to get additional task info
                    task_data_key = f"task:{task_id}:data"
                    task_data = redis_client.get(task_data_key)

                    orphaned.append({
                        'task_id': task_id,
                        'status': status,
                        'data': task_data,
                        'redis_key': key
                    })

            if orphaned:
                logger.warning(f"Found {len(orphaned)} orphaned task(s) from previous session")
                for task in orphaned:
                    logger.warning(f"  - Orphaned: {task['task_id']} (status={task['status']})")

        except Exception as e:
            logger.error(f"Failed to check for orphaned tasks: {e}", exc_info=True)

        return orphaned

    def recover_orphaned_tasks(self, redis_client, orphaned_tasks: List[Dict[str, Any]]):
        """
        Recover orphaned tasks by resetting their status.

        Args:
            redis_client: Redis client
            orphaned_tasks: List of orphaned task info dicts
        """
        if not orphaned_tasks:
            logger.info("No orphaned tasks to recover")
            return

        logger.info(f"Recovering {len(orphaned_tasks)} orphaned task(s)")

        for task in orphaned_tasks:
            task_id = task['task_id']
            try:
                # Reset task status to "failed" (can be retried)
                redis_client.set_task_status(task_id, "failed")
                logger.info(f"Reset orphaned task {task_id} to 'failed' status")
            except Exception as e:
                logger.error(f"Failed to recover task {task_id}: {e}", exc_info=True)

    def clear_orphaned_tasks(self, redis_client, orphaned_tasks: List[Dict[str, Any]]):
        """
        Clear orphaned tasks from Redis.

        Args:
            redis_client: Redis client
            orphaned_tasks: List of orphaned task info dicts
        """
        if not orphaned_tasks:
            logger.info("No orphaned tasks to clear")
            return

        logger.info(f"Clearing {len(orphaned_tasks)} orphaned task(s)")

        for task in orphaned_tasks:
            task_id = task['task_id']
            try:
                # Delete task status key
                redis_client.delete(task['redis_key'])
                # Delete task data key if exists
                redis_client.delete(f"task:{task_id}:data")
                logger.info(f"Cleared orphaned task {task_id}")
            except Exception as e:
                logger.error(f"Failed to clear task {task_id}: {e}", exc_info=True)


# Global lifecycle instance
_global_lifecycle: Optional[ServiceLifecycle] = None
_lifecycle_lock = threading.Lock()


def get_lifecycle() -> ServiceLifecycle:
    """
    Get or create the global lifecycle instance.

    Returns:
        Global ServiceLifecycle instance
    """
    global _global_lifecycle

    if _global_lifecycle is None:
        with _lifecycle_lock:
            if _global_lifecycle is None:
                _global_lifecycle = ServiceLifecycle()

    return _global_lifecycle


def setup_lifecycle() -> ServiceLifecycle:
    """
    Set up lifecycle management with signal handlers.

    Returns:
        Configured ServiceLifecycle instance
    """
    lifecycle = get_lifecycle()
    lifecycle.setup_signal_handlers()
    return lifecycle


# Example usage
if __name__ == '__main__':
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Create lifecycle
    lifecycle = ServiceLifecycle()

    # Register signal handlers
    lifecycle.setup_signal_handlers()

    # Mark service as started
    lifecycle.mark_started()

    print("\nService started. Press Ctrl+C to trigger graceful shutdown.\n")

    # Simulate some work
    try:
        # Add a task
        lifecycle.add_active_task("t_001", agent="scribe", feature="login")
        print("Started task t_001")

        time.sleep(2)

        # Complete task
        lifecycle.remove_active_task("t_001")
        print("Completed task t_001")

        # Add another task
        lifecycle.add_active_task("t_002", agent="runner", feature="checkout")
        print("Started task t_002")

        # Keep running
        while not lifecycle.is_shutting_down():
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nKeyboard interrupt received")

    # Graceful shutdown (also triggered by signal handler)
    if not lifecycle._shutdown_in_progress:
        lifecycle.shutdown(timeout=30)
