"""
Unit tests for ServiceLifecycle management

Tests graceful shutdown, signal handling, connection cleanup, and task tracking.
"""
import pytest
import signal
import time
import threading
from unittest.mock import Mock, MagicMock, patch

from agent_system.lifecycle import (
    ServiceLifecycle,
    ServiceStatus,
    ConnectionInfo,
    ActiveTask,
    get_lifecycle,
    setup_lifecycle
)


class TestServiceLifecycle:
    """Test suite for ServiceLifecycle class."""

    def test_initialization(self):
        """Test lifecycle initialization."""
        lifecycle = ServiceLifecycle()

        assert lifecycle.status == ServiceStatus.STARTING
        assert not lifecycle.is_shutting_down()
        assert lifecycle.can_accept_tasks() == False  # Not started yet
        assert len(lifecycle.active_tasks) == 0
        assert len(lifecycle.connections) == 0

    def test_mark_started(self):
        """Test marking service as started."""
        lifecycle = ServiceLifecycle()
        lifecycle.mark_started()

        assert lifecycle.status == ServiceStatus.HEALTHY
        assert lifecycle.started_at is not None
        assert lifecycle.can_accept_tasks() == True

    def test_register_connection(self):
        """Test registering connections."""
        lifecycle = ServiceLifecycle()
        mock_connection = Mock()

        # Register connection
        lifecycle.register_connection("test_conn", mock_connection)

        assert "test_conn" in lifecycle.connections
        assert lifecycle.connections["test_conn"].connection == mock_connection
        assert lifecycle.connections["test_conn"].close_method == "close"

    def test_register_connection_custom_close_method(self):
        """Test registering connection with custom close method."""
        lifecycle = ServiceLifecycle()
        mock_connection = Mock()

        lifecycle.register_connection(
            "custom_conn",
            mock_connection,
            close_method="shutdown",
            metadata={"type": "websocket"}
        )

        conn_info = lifecycle.connections["custom_conn"]
        assert conn_info.close_method == "shutdown"
        assert conn_info.metadata["type"] == "websocket"

    def test_unregister_connection(self):
        """Test unregistering connections."""
        lifecycle = ServiceLifecycle()
        mock_connection = Mock()

        lifecycle.register_connection("test_conn", mock_connection)
        assert "test_conn" in lifecycle.connections

        # Unregister
        result = lifecycle.unregister_connection("test_conn")
        assert result == True
        assert "test_conn" not in lifecycle.connections

        # Try to unregister again
        result = lifecycle.unregister_connection("test_conn")
        assert result == False

    def test_add_active_task(self):
        """Test adding active tasks."""
        lifecycle = ServiceLifecycle()

        lifecycle.add_active_task(
            "task_001",
            agent="scribe",
            feature="login",
            metadata={"priority": "high"}
        )

        assert "task_001" in lifecycle.active_tasks
        task = lifecycle.active_tasks["task_001"]
        assert task.task_id == "task_001"
        assert task.agent == "scribe"
        assert task.feature == "login"
        assert task.metadata["priority"] == "high"

    def test_remove_active_task(self):
        """Test removing active tasks."""
        lifecycle = ServiceLifecycle()

        lifecycle.add_active_task("task_001", agent="runner")
        assert "task_001" in lifecycle.active_tasks

        # Remove task
        result = lifecycle.remove_active_task("task_001")
        assert result == True
        assert "task_001" not in lifecycle.active_tasks

        # Try to remove again
        result = lifecycle.remove_active_task("task_001")
        assert result == False

    def test_shutdown_event(self):
        """Test shutdown event setting."""
        lifecycle = ServiceLifecycle()
        lifecycle.mark_started()

        assert lifecycle.can_accept_tasks() == True
        assert lifecycle.is_shutting_down() == False

        # Trigger shutdown
        lifecycle.shutdown_event.set()

        assert lifecycle.can_accept_tasks() == False
        assert lifecycle.is_shutting_down() == True

    def test_shutdown_with_no_tasks(self):
        """Test shutdown with no active tasks."""
        lifecycle = ServiceLifecycle()
        lifecycle.mark_started()

        # Shutdown should complete immediately
        lifecycle.shutdown(timeout=5)

        assert lifecycle.status == ServiceStatus.STOPPED
        assert lifecycle.is_shutting_down() == True

    def test_shutdown_with_active_tasks(self):
        """Test shutdown waits for active tasks."""
        lifecycle = ServiceLifecycle()
        lifecycle.mark_started()

        # Add a task
        lifecycle.add_active_task("task_001", agent="scribe")

        # Start shutdown in background
        def delayed_task_completion():
            time.sleep(0.5)
            lifecycle.remove_active_task("task_001")

        thread = threading.Thread(target=delayed_task_completion)
        thread.start()

        # Shutdown should wait for task
        start_time = time.time()
        lifecycle.shutdown(timeout=2)
        duration = time.time() - start_time

        assert duration >= 0.5  # Waited for task
        assert duration < 2  # Didn't hit timeout
        assert lifecycle.status == ServiceStatus.STOPPED

        thread.join()

    def test_shutdown_timeout(self):
        """Test shutdown timeout with stuck tasks."""
        lifecycle = ServiceLifecycle()
        lifecycle.mark_started()

        # Add a task that won't complete
        lifecycle.add_active_task("stuck_task", agent="scribe")

        # Shutdown should timeout
        start_time = time.time()
        lifecycle.shutdown(timeout=1)
        duration = time.time() - start_time

        assert duration >= 1  # Hit timeout
        assert lifecycle.status == ServiceStatus.STOPPED
        # Task should still be tracked (forced shutdown)
        # But status should be STOPPED

    def test_connection_cleanup(self):
        """Test that connections are closed during shutdown."""
        lifecycle = ServiceLifecycle()

        # Create mock connections
        mock_redis = Mock()
        mock_redis.close = Mock()

        mock_vector = Mock()
        mock_vector.close = Mock()

        # Register connections
        lifecycle.register_connection("redis", mock_redis)
        lifecycle.register_connection("vector_db", mock_vector)

        # Shutdown
        lifecycle.shutdown(timeout=1)

        # Verify close methods were called
        mock_redis.close.assert_called_once()
        mock_vector.close.assert_called_once()

        # Connections should be cleared
        assert len(lifecycle.connections) == 0

    def test_connection_cleanup_custom_method(self):
        """Test connection cleanup with custom close method."""
        lifecycle = ServiceLifecycle()

        # Create mock with custom close method
        mock_ws = Mock()
        mock_ws.stop = Mock()

        lifecycle.register_connection("websocket", mock_ws, close_method="stop")

        # Shutdown
        lifecycle.shutdown(timeout=1)

        # Verify custom method was called
        mock_ws.stop.assert_called_once()

    def test_shutdown_callbacks(self):
        """Test shutdown callbacks are executed."""
        lifecycle = ServiceLifecycle()

        callback_called = {"count": 0}

        def shutdown_callback():
            callback_called["count"] += 1

        # Add callback
        lifecycle.add_shutdown_callback(shutdown_callback)

        # Shutdown
        lifecycle.shutdown(timeout=1)

        # Verify callback was called
        assert callback_called["count"] == 1

    def test_multiple_shutdown_attempts(self):
        """Test that multiple shutdown attempts are handled gracefully."""
        lifecycle = ServiceLifecycle()

        # First shutdown
        lifecycle.shutdown(timeout=1)
        assert lifecycle.status == ServiceStatus.STOPPED

        # Second shutdown should be ignored
        lifecycle.shutdown(timeout=1)
        assert lifecycle.status == ServiceStatus.STOPPED

    def test_signal_handler_setup(self):
        """Test signal handler registration."""
        lifecycle = ServiceLifecycle()

        # Setup signal handlers
        lifecycle.setup_signal_handlers()

        # Verify handlers were registered
        assert signal.SIGTERM in lifecycle._original_handlers
        assert signal.SIGINT in lifecycle._original_handlers

    def test_health_status(self):
        """Test health status reporting."""
        lifecycle = ServiceLifecycle()
        lifecycle.mark_started()

        # Add some state
        lifecycle.add_active_task("task_001", agent="scribe")
        mock_conn = Mock()
        mock_conn.health_check = Mock(return_value=True)
        lifecycle.register_connection("redis", mock_conn)

        # Get health status
        health = lifecycle.get_health_status()

        assert health['status'] == ServiceStatus.HEALTHY.value
        assert health['active_tasks'] == 1
        assert health['connections']['count'] == 1
        assert health['can_accept_tasks'] == True
        assert health['shutdown_in_progress'] == False
        assert 'uptime_seconds' in health
        assert 'timestamp' in health

    def test_orphaned_tasks_detection(self):
        """Test detection of orphaned tasks."""
        lifecycle = ServiceLifecycle()

        # Mock Redis client with orphaned tasks
        mock_redis = Mock()
        mock_redis.keys = Mock(return_value=[
            "task:t_001:status",
            "task:t_002:status"
        ])
        mock_redis.get = Mock(side_effect=lambda key: "doing" if "status" in key else None)

        # Check for orphaned tasks
        orphaned = lifecycle.check_orphaned_tasks(mock_redis)

        assert len(orphaned) == 2
        assert orphaned[0]['task_id'] == 't_001'
        assert orphaned[0]['status'] == 'doing'
        assert orphaned[1]['task_id'] == 't_002'

    def test_orphaned_tasks_recovery(self):
        """Test recovery of orphaned tasks."""
        lifecycle = ServiceLifecycle()

        # Mock Redis client
        mock_redis = Mock()
        mock_redis.set_task_status = Mock()

        orphaned_tasks = [
            {'task_id': 't_001', 'status': 'doing', 'redis_key': 'task:t_001:status'},
            {'task_id': 't_002', 'status': 'doing', 'redis_key': 'task:t_002:status'}
        ]

        # Recover tasks
        lifecycle.recover_orphaned_tasks(mock_redis, orphaned_tasks)

        # Verify tasks were reset to "failed"
        assert mock_redis.set_task_status.call_count == 2
        mock_redis.set_task_status.assert_any_call('t_001', 'failed')
        mock_redis.set_task_status.assert_any_call('t_002', 'failed')

    def test_orphaned_tasks_clear(self):
        """Test clearing of orphaned tasks."""
        lifecycle = ServiceLifecycle()

        # Mock Redis client
        mock_redis = Mock()
        mock_redis.delete = Mock()

        orphaned_tasks = [
            {'task_id': 't_001', 'status': 'doing', 'redis_key': 'task:t_001:status'},
        ]

        # Clear tasks
        lifecycle.clear_orphaned_tasks(mock_redis, orphaned_tasks)

        # Verify keys were deleted
        assert mock_redis.delete.call_count == 2  # Status key + data key
        mock_redis.delete.assert_any_call('task:t_001:status')
        mock_redis.delete.assert_any_call('task:t_001:data')


class TestGlobalLifecycle:
    """Test suite for global lifecycle functions."""

    def test_get_lifecycle(self):
        """Test getting global lifecycle instance."""
        lifecycle1 = get_lifecycle()
        lifecycle2 = get_lifecycle()

        # Should return same instance
        assert lifecycle1 is lifecycle2

    def test_setup_lifecycle(self):
        """Test setting up lifecycle with signal handlers."""
        lifecycle = setup_lifecycle()

        assert lifecycle is not None
        assert signal.SIGTERM in lifecycle._original_handlers
        assert signal.SIGINT in lifecycle._original_handlers


class TestConnectionInfo:
    """Test ConnectionInfo dataclass."""

    def test_connection_info_creation(self):
        """Test creating ConnectionInfo."""
        mock_conn = Mock()
        info = ConnectionInfo(
            name="test",
            connection=mock_conn,
            close_method="shutdown",
            metadata={"type": "redis"}
        )

        assert info.name == "test"
        assert info.connection == mock_conn
        assert info.close_method == "shutdown"
        assert info.metadata["type"] == "redis"
        assert info.registered_at > 0


class TestActiveTask:
    """Test ActiveTask dataclass."""

    def test_active_task_creation(self):
        """Test creating ActiveTask."""
        task = ActiveTask(
            task_id="t_001",
            started_at=time.time(),
            agent="scribe",
            feature="login",
            metadata={"priority": "high"}
        )

        assert task.task_id == "t_001"
        assert task.agent == "scribe"
        assert task.feature == "login"
        assert task.metadata["priority"] == "high"
        assert task.started_at > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
