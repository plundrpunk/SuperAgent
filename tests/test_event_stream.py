"""
Tests for event streaming system.
"""
import pytest
import asyncio
import time
import json
from pathlib import Path
from agent_system.observability.event_stream import (
    EventEmitter,
    Event,
    EventType,
    MetricsAggregator,
    emit_event,
    get_emitter
)
from agent_system.state.redis_client import RedisClient


class TestEvent:
    """Test Event dataclass."""

    def test_event_creation(self):
        """Test event creation and serialization."""
        event = Event(
            event_type='task_queued',
            timestamp=time.time(),
            payload={'task_id': 't_001', 'feature': 'test'}
        )

        assert event.event_type == 'task_queued'
        assert 'task_id' in event.payload
        assert event.payload['task_id'] == 't_001'

    def test_event_to_dict(self):
        """Test event dictionary conversion."""
        event = Event(
            event_type='task_queued',
            timestamp=1234567890.0,
            payload={'task_id': 't_001'}
        )

        event_dict = event.to_dict()
        assert event_dict['event_type'] == 'task_queued'
        assert event_dict['timestamp'] == 1234567890.0
        assert event_dict['payload']['task_id'] == 't_001'

    def test_event_to_json(self):
        """Test event JSON serialization."""
        event = Event(
            event_type='task_queued',
            timestamp=1234567890.0,
            payload={'task_id': 't_001'}
        )

        event_json = event.to_json()
        parsed = json.loads(event_json)
        assert parsed['event_type'] == 'task_queued'
        assert parsed['payload']['task_id'] == 't_001'


class TestMetricsAggregator:
    """Test metrics aggregation."""

    def test_metrics_initialization(self):
        """Test metrics aggregator initialization."""
        redis_client = RedisClient()
        metrics = MetricsAggregator(redis_client=redis_client)

        assert metrics.window_minutes == 60
        assert len(metrics._feature_costs) == 0
        assert metrics._validation_total == 0

    def test_task_queued_tracking(self):
        """Test task queued event tracking."""
        redis_client = RedisClient()
        metrics = MetricsAggregator(redis_client=redis_client)

        event = Event(
            event_type='task_queued',
            timestamp=time.time(),
            payload={'task_id': 't_001', 'feature': 'test', 'est_cost': 0.25}
        )

        metrics.process_event(event)
        assert 't_001' in metrics._task_start_times

    def test_validation_tracking(self):
        """Test validation event tracking."""
        redis_client = RedisClient()
        metrics = MetricsAggregator(redis_client=redis_client)

        # Queue task first
        queue_event = Event(
            event_type='task_queued',
            timestamp=time.time(),
            payload={'task_id': 't_001'}
        )
        metrics.process_event(queue_event)

        # Wait a bit
        time.sleep(0.1)

        # Complete validation
        validation_event = Event(
            event_type='validation_complete',
            timestamp=time.time(),
            payload={
                'task_id': 't_001',
                'result': {
                    'browser_launched': True,
                    'test_executed': True,
                    'test_passed': True
                },
                'cost': 0.15,
                'duration_ms': 3000
            }
        )
        metrics.process_event(validation_event)

        assert metrics._validation_total == 1
        assert metrics._validation_passed == 1
        assert len(metrics._completion_times) == 1
        assert len(metrics._feature_costs) == 1

    def test_critic_decision_tracking(self):
        """Test critic decision tracking."""
        redis_client = RedisClient()
        metrics = MetricsAggregator(redis_client=redis_client)

        # Record some decisions
        metrics.record_critic_decision(rejected=False)
        metrics.record_critic_decision(rejected=True)
        metrics.record_critic_decision(rejected=True)

        assert metrics._critic_total == 3
        assert metrics._critic_rejected == 2

        # Calculate metrics
        calculated = metrics.calculate_metrics()
        assert calculated['critic_rejection_rate'] == 2/3

    def test_calculate_metrics(self):
        """Test metrics calculation."""
        redis_client = RedisClient()
        metrics = MetricsAggregator(redis_client=redis_client)

        # Add some data
        metrics._feature_costs = [0.25, 0.30, 0.35]
        metrics._retry_counts = [1, 2, 1]
        metrics._validation_total = 10
        metrics._validation_passed = 8

        calculated = metrics.calculate_metrics()

        assert calculated['cost_per_feature'] == 0.30  # Average
        assert calculated['average_retry_count'] == 4/3  # Average
        assert calculated['validation_pass_rate'] == 0.8  # 8/10


class TestEventEmitter:
    """Test event emitter."""

    def test_emitter_initialization(self):
        """Test emitter initialization."""
        emitter = EventEmitter(
            websocket_enabled=False,
            console_enabled=True,
            file_enabled=False
        )

        assert emitter.websocket_enabled is False
        assert emitter.console_enabled is True
        assert emitter.file_enabled is False

    def test_emit_to_console(self, capsys):
        """Test console emission."""
        emitter = EventEmitter(
            websocket_enabled=False,
            console_enabled=True,
            file_enabled=False
        )

        emitter.emit('task_queued', {
            'task_id': 't_001',
            'feature': 'test',
            'est_cost': 0.25
        })

        captured = capsys.readouterr()
        assert 'TASK_QUEUED' in captured.out
        assert 't_001' in captured.out

    def test_emit_to_file(self, tmp_path):
        """Test file emission."""
        log_file = tmp_path / 'events.jsonl'

        emitter = EventEmitter(
            websocket_enabled=False,
            console_enabled=False,
            file_enabled=True,
            file_path=str(log_file)
        )

        emitter.emit('task_queued', {
            'task_id': 't_001',
            'feature': 'test'
        })

        # Read file
        assert log_file.exists()
        with open(log_file, 'r') as f:
            line = f.readline()
            event = json.loads(line)
            assert event['event_type'] == 'task_queued'
            assert event['payload']['task_id'] == 't_001'

    def test_get_metrics(self):
        """Test metrics retrieval."""
        emitter = EventEmitter(
            websocket_enabled=False,
            console_enabled=False,
            file_enabled=False
        )

        # Emit some events
        emitter.emit('task_queued', {'task_id': 't_001'})
        emitter.emit('validation_complete', {
            'task_id': 't_001',
            'result': {
                'browser_launched': True,
                'test_executed': True,
                'test_passed': True
            },
            'cost': 0.15
        })

        metrics = emitter.get_metrics()
        assert 'validation_pass_rate' in metrics
        assert 'cost_per_feature' in metrics


class TestGlobalEmitter:
    """Test global emitter functions."""

    def test_get_global_emitter(self):
        """Test global emitter retrieval."""
        emitter1 = get_emitter()
        emitter2 = get_emitter()

        # Should be same instance
        assert emitter1 is emitter2

    def test_emit_event_function(self, capsys):
        """Test convenience emit_event function."""
        # This uses the global emitter
        emit_event('task_queued', {
            'task_id': 't_999',
            'feature': 'global_test'
        })

        captured = capsys.readouterr()
        assert 't_999' in captured.out


@pytest.mark.asyncio
async def test_websocket_server():
    """Test WebSocket server (integration test)."""
    try:
        import websockets

        emitter = EventEmitter(
            websocket_enabled=True,
            websocket_port=3011,  # Use different port for testing
            console_enabled=False,
            file_enabled=False
        )

        # Start server
        await emitter.start()
        await asyncio.sleep(0.5)  # Let server start

        # Connect client
        try:
            async with websockets.connect('ws://localhost:3011') as websocket:
                # Receive welcome message
                message = await websocket.recv()
                data = json.loads(message)
                assert data['event_type'] == 'connection_established'

                # Emit event
                emitter.emit('task_queued', {'task_id': 't_ws_001'})

                # Receive event
                message = await websocket.recv()
                data = json.loads(message)
                assert data['event_type'] == 'task_queued'
                assert data['payload']['task_id'] == 't_ws_001'

        finally:
            await emitter.stop()

    except ImportError:
        pytest.skip("websockets library not installed")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
