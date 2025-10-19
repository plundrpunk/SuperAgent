"""
Unit tests for Medic Agent HITL Escalation
Tests the enhanced HITL escalation with attempt tracking and confidence scoring.
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from agent_system.agents.medic import MedicAgent


class TestMedicHITLEscalationEnhanced:
    """Test enhanced HITL escalation with attempt tracking."""

    @patch('agent_system.agents.medic.subprocess.run')
    @patch('agent_system.agents.medic.RedisClient')
    @patch('agent_system.agents.medic.HITLQueue')
    def test_escalation_after_max_retries(
        self,
        mock_hitl_queue,
        mock_redis,
        mock_run,
        tmp_path
    ):
        """Test escalation after MAX_RETRIES attempts."""
        # Setup mocks
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance
        mock_hitl_instance = MagicMock()
        mock_hitl_queue.return_value = mock_hitl_instance

        # Mock Redis to simulate 4th attempt (exceeds MAX_RETRIES=3)
        mock_redis_instance.get.return_value = '3'  # 3 previous attempts
        mock_redis_instance.set.return_value = True
        mock_redis_instance.client.rpush.return_value = True
        mock_redis_instance.client.expire.return_value = True
        mock_redis_instance.client.lrange.return_value = []

        test_file = tmp_path / "test.spec.ts"
        test_file.write_text("test content")

        with patch('agent_system.agents.medic.Anthropic') as mock_anthropic, \
             patch('agent_system.agents.medic.os.getenv') as mock_getenv:

            mock_getenv.return_value = 'fake-api-key'
            mock_client = MagicMock()
            mock_anthropic.return_value = mock_client

            medic = MedicAgent(redis_client=mock_redis_instance, hitl_queue=mock_hitl_instance)

            result = medic.execute(
                test_path=str(test_file),
                error_message="Test failed",
                task_id="test_task_123",
                feature="login"
            )

            # Should escalate immediately due to max retries
            assert result.success is False
            assert result.data['status'] == 'escalated_to_hitl'
            assert result.data['reason'] == 'max_retries_exceeded'
            assert result.data['attempts'] == 4
            assert 'Escalated to HITL' in result.error

            # Verify HITL queue was called
            mock_hitl_instance.add.assert_called_once()
            hitl_task = mock_hitl_instance.add.call_args[0][0]
            assert hitl_task['task_id'] == 'test_task_123'
            assert hitl_task['attempts'] == 4
            assert hitl_task['escalation_reason'] == 'max_retries_exceeded'

    @patch('agent_system.agents.medic.subprocess.run')
    @patch('agent_system.agents.medic.RedisClient')
    @patch('agent_system.agents.medic.HITLQueue')
    def test_escalation_on_low_confidence(
        self,
        mock_hitl_queue,
        mock_redis,
        mock_run,
        tmp_path
    ):
        """Test escalation when AI confidence is low."""
        # Setup mocks
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance
        mock_hitl_instance = MagicMock()
        mock_hitl_queue.return_value = mock_hitl_instance

        # Mock Redis for first attempt
        mock_redis_instance.get.return_value = None
        mock_redis_instance.set.return_value = True
        mock_redis_instance.client.rpush.return_value = True
        mock_redis_instance.client.expire.return_value = True
        mock_redis_instance.client.lrange.return_value = []

        test_file = tmp_path / "test.spec.ts"
        test_file.write_text("test content")

        # Mock baseline regression tests
        baseline_result = MagicMock()
        baseline_result.stdout = "2 passed (5.2s)"
        baseline_result.returncode = 0
        mock_run.return_value = baseline_result

        with patch('agent_system.agents.medic.Anthropic') as mock_anthropic, \
             patch('agent_system.agents.medic.os.getenv') as mock_getenv:

            mock_getenv.return_value = 'fake-api-key'
            mock_client = MagicMock()
            mock_anthropic.return_value = mock_client

            # Mock AI response with low confidence
            mock_response = MagicMock()
            mock_response.content = [
                MagicMock(text="""DIAGNOSIS: Unable to determine root cause - unclear error

CONFIDENCE: 0.3

FIX:
```typescript
// Uncertain fix
test('test', async ({ page }) => {
  await page.click('[data-testid="button"]');
});
```
""")
            ]
            mock_response.usage = MagicMock(input_tokens=500, output_tokens=200)
            mock_client.messages.create.return_value = mock_response

            medic = MedicAgent(redis_client=mock_redis_instance, hitl_queue=mock_hitl_instance)
            medic.client = mock_client

            result = medic.execute(
                test_path=str(test_file),
                error_message="Test failed",
                task_id="test_task_456",
                feature="checkout"
            )

            # Should escalate due to low confidence
            assert result.success is False
            assert result.data['status'] == 'escalated_to_hitl'
            assert result.data['reason'] == 'low_confidence'
            assert result.data['severity'] == 'medium'

            # Verify HITL queue was called
            mock_hitl_instance.add.assert_called_once()
            hitl_task = mock_hitl_instance.add.call_args[0][0]
            assert hitl_task['escalation_reason'] == 'low_confidence'
            assert hitl_task['ai_confidence'] == 0.3

    @patch('agent_system.agents.medic.RedisClient')
    def test_attempt_tracking_increments_correctly(self, mock_redis):
        """Test that attempt tracking increments correctly."""
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        # Mock Redis responses for incrementing
        mock_redis_instance.get.side_effect = [None, '1', '2']
        mock_redis_instance.set.return_value = True
        mock_redis_instance.client.rpush.return_value = True
        mock_redis_instance.client.expire.return_value = True

        with patch('agent_system.agents.medic.Anthropic') as mock_anthropic, \
             patch('agent_system.agents.medic.os.getenv') as mock_getenv:

            mock_getenv.return_value = 'fake-api-key'
            medic = MedicAgent(redis_client=mock_redis_instance)

            # First attempt
            attempts1 = medic._increment_fix_attempts("task_001", "/path/to/test.ts")
            assert attempts1 == 1

            # Second attempt
            attempts2 = medic._increment_fix_attempts("task_001", "/path/to/test.ts")
            assert attempts2 == 2

            # Third attempt
            attempts3 = medic._increment_fix_attempts("task_001", "/path/to/test.ts")
            assert attempts3 == 3

            # Verify Redis set was called each time
            assert mock_redis_instance.set.call_count == 3

    @patch('agent_system.agents.medic.RedisClient')
    def test_attempt_history_tracked(self, mock_redis):
        """Test that attempt history is properly tracked."""
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance
        mock_redis_instance.get.return_value = None
        mock_redis_instance.set.return_value = True
        mock_redis_instance.client.rpush.return_value = True
        mock_redis_instance.client.expire.return_value = True
        mock_redis_instance.client.lrange.return_value = [
            '{"attempt": 1, "timestamp": "2025-01-01T00:00:00", "test_path": "/path/test.ts"}',
            '{"attempt": 2, "timestamp": "2025-01-01T01:00:00", "test_path": "/path/test.ts"}'
        ]

        with patch('agent_system.agents.medic.Anthropic') as mock_anthropic, \
             patch('agent_system.agents.medic.os.getenv') as mock_getenv:

            mock_getenv.return_value = 'fake-api-key'
            medic = MedicAgent(redis_client=mock_redis_instance)

            # Get attempt history
            history = medic._get_attempt_history("task_001")

            assert len(history) == 2
            assert history[0]['attempt'] == 1
            assert history[1]['attempt'] == 2

    @patch('agent_system.agents.medic.RedisClient')
    @patch('agent_system.agents.medic.HITLQueue')
    def test_hitl_priority_calculation(self, mock_hitl_queue, mock_redis):
        """Test HITL priority score calculation."""
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance
        mock_hitl_instance = MagicMock()
        mock_hitl_queue.return_value = mock_hitl_instance

        mock_redis_instance.client.lrange.return_value = []

        with patch('agent_system.agents.medic.Anthropic') as mock_anthropic, \
             patch('agent_system.agents.medic.os.getenv') as mock_getenv:

            mock_getenv.return_value = 'fake-api-key'
            medic = MedicAgent(redis_client=mock_redis_instance, hitl_queue=mock_hitl_instance)

            # Test high severity + many attempts
            result = medic._escalate_to_hitl(
                task_id="task_001",
                test_path="/path/test.ts",
                error_message="error",
                feature="authentication",
                attempts=5,
                reason="max_retries_exceeded",
                artifacts={},
                api_cost=0.05,
                severity="high"
            )

            # Priority should be high (0.5 base + min(5/10, 0.3) = 0.8)
            assert result.data['priority'] == 0.8

            # Test medium severity + few attempts
            result2 = medic._escalate_to_hitl(
                task_id="task_002",
                test_path="/path/test.ts",
                error_message="error",
                feature="ui",
                attempts=1,
                reason="low_confidence",
                artifacts={},
                api_cost=0.02,
                severity="medium"
            )

            # Priority should be moderate (0.3 base + 0.1 = 0.4)
            assert result2.data['priority'] == 0.4

    @patch('agent_system.agents.medic.RedisClient')
    @patch('agent_system.agents.medic.HITLQueue')
    def test_hitl_task_payload_structure(self, mock_hitl_queue, mock_redis):
        """Test HITL task payload has all required fields."""
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance
        mock_hitl_instance = MagicMock()
        mock_hitl_queue.return_value = mock_hitl_instance

        mock_redis_instance.client.lrange.return_value = []

        with patch('agent_system.agents.medic.Anthropic') as mock_anthropic, \
             patch('agent_system.agents.medic.os.getenv') as mock_getenv:

            mock_getenv.return_value = 'fake-api-key'
            medic = MedicAgent(redis_client=mock_redis_instance, hitl_queue=mock_hitl_instance)

            result = medic._escalate_to_hitl(
                task_id="task_123",
                test_path="/path/test.ts",
                error_message="Test failed",
                feature="checkout",
                attempts=3,
                reason="regression_detected",
                artifacts={
                    'diagnosis': 'Selector changed',
                    'confidence': 0.8,
                    'diff': 'test diff',
                    'baseline': {'passed': 2, 'failed': 0},
                    'after_fix': {'passed': 1, 'failed': 1}
                },
                api_cost=0.03,
                severity="high"
            )

            # Verify HITL queue was called
            mock_hitl_instance.add.assert_called_once()
            hitl_task = mock_hitl_instance.add.call_args[0][0]

            # Check all required fields from schema.json
            assert hitl_task['task_id'] == 'task_123'
            assert hitl_task['feature'] == 'checkout'
            assert hitl_task['code_path'] == '/path/test.ts'
            assert hitl_task['attempts'] == 3
            assert hitl_task['last_error'] == 'Test failed'
            assert 'priority' in hitl_task
            assert hitl_task['severity'] == 'high'
            assert hitl_task['escalation_reason'] == 'regression_detected'
            assert hitl_task['ai_diagnosis'] == 'Selector changed'
            assert hitl_task['ai_confidence'] == 0.8
            assert 'created_at' in hitl_task


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
