"""
E2E Test: HITL (Human-in-the-Loop) Escalation Flow

Tests various HITL escalation scenarios:
1. Low confidence diagnosis → Escalate to HITL
2. Max retries exceeded → Escalate to HITL
3. Regression detected → Escalate to HITL
4. Critical path failure → High priority HITL
5. HITL queue management and prioritization
"""
import pytest
import tempfile
import shutil
import time
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime

from agent_system.agents.medic import MedicAgent
from agent_system.hitl.queue import HITLQueue
from agent_system.state.redis_client import RedisClient
from agent_system.state.vector_client import VectorClient


class TestHITLEscalation:
    """
    HITL escalation workflow tests.

    Tests various failure scenarios that require human intervention.
    """

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_dir = Path(self.temp_dir) / "tests"
        self.test_dir.mkdir()

        # Real HITL queue for testing
        self.mock_redis = Mock(spec=RedisClient)
        self.mock_vector = Mock(spec=VectorClient)

        # Configure Redis for HITL queue
        self.hitl_queue_data = {}
        self.hitl_scores = {}

        def mock_redis_set(key, value, ttl=None):
            self.hitl_queue_data[key] = value
            return True

        def mock_redis_get(key):
            return self.hitl_queue_data.get(key)

        def mock_zadd(queue_key, mapping):
            self.hitl_scores.update(mapping)
            return len(mapping)

        def mock_zrevrange(queue_key, start, stop):
            sorted_items = sorted(self.hitl_scores.items(), key=lambda x: x[1], reverse=True)
            if stop == -1:
                return [item[0] for item in sorted_items]
            return [item[0] for item in sorted_items[start:stop+1]]

        def mock_zrem(queue_key, *members):
            for member in members:
                self.hitl_scores.pop(member, None)
            return len(members)

        self.mock_redis.set.side_effect = mock_redis_set
        self.mock_redis.get.side_effect = mock_redis_get
        self.mock_redis.client = Mock()
        self.mock_redis.client.zadd = Mock(side_effect=mock_zadd)
        self.mock_redis.client.zrevrange = Mock(side_effect=mock_zrevrange)
        self.mock_redis.client.zrem = Mock(side_effect=mock_zrem)

        self.mock_vector.store_hitl_annotation.return_value = True

        self.hitl_queue = HITLQueue(
            redis_client=self.mock_redis,
            vector_client=self.mock_vector
        )

        yield

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_low_confidence_escalation(self):
        """
        Test: Low confidence diagnosis escalates to HITL

        Medic confidence < 0.7 → Immediate HITL escalation
        """
        print("\n" + "="*80)
        print("TEST: Low Confidence → HITL Escalation")
        print("="*80)

        test_path = self.test_dir / "ambiguous_issue.spec.ts"
        test_path.write_text("test content")

        # Mock Anthropic with low confidence response
        mock_anthropic_response = Mock()
        mock_anthropic_response.content = [Mock(text="""
DIAGNOSIS: Multiple possible causes - timeout could be network, selector, or page load issue

CONFIDENCE: 0.35

FIX:
```typescript
// Not confident about this fix
await page.waitForTimeout(5000);
```
""")]
        mock_anthropic_response.usage = Mock(input_tokens=900, output_tokens=200)

        mock_anthropic_client = Mock()
        mock_anthropic_client.messages.create = Mock(return_value=mock_anthropic_response)

        mock_regression = Mock()
        mock_regression.returncode = 0
        mock_regression.stdout = "2 passed (4.0s)"
        mock_regression.stderr = ""

        medic = MedicAgent(redis_client=self.mock_redis, hitl_queue=self.hitl_queue)

        print("\n=== Medic attempts diagnosis ===")

        with patch.object(medic, 'client', mock_anthropic_client):
            with patch('subprocess.run', return_value=mock_regression):
                result = medic.execute(
                    test_path=str(test_path),
                    error_message="Timeout waiting for element",
                    task_id="task_low_conf_123",
                    feature="ambiguous_feature"
                )

        # Should escalate due to low confidence
        assert not result.success
        assert result.data['status'] == 'escalated_to_hitl'
        assert result.data['reason'] == 'low_confidence'
        assert result.data['diagnosis_confidence'] == 0.35

        print(f"✓ Escalated to HITL")
        print(f"  Confidence: {result.data['diagnosis_confidence']}")
        print(f"  Threshold: 0.70")
        print(f"  Reason: {result.data['reason']}")

        # Verify HITL queue
        hitl_tasks = self.hitl_queue.list()
        assert len(hitl_tasks) == 1

        hitl_task = hitl_tasks[0]
        assert hitl_task['task_id'] == "task_low_conf_123"
        assert hitl_task['escalation_reason'] == 'low_confidence'
        assert hitl_task['feature'] == 'ambiguous_feature'

        print(f"\n✓ HITL queue contains escalated task")
        print(f"  Task ID: {hitl_task['task_id']}")
        print(f"  Priority: {hitl_task['priority']:.2f}")

    def test_max_retries_escalation(self):
        """
        Test: Max retries exceeded → HITL escalation

        Medic attempts 3+ fixes, all fail → Escalate
        """
        print("\n" + "="*80)
        print("TEST: Max Retries Exceeded → HITL Escalation")
        print("="*80)

        test_path = self.test_dir / "persistent_failure.spec.ts"
        test_path.write_text("test content")

        # Configure Redis to track attempts
        attempt_counter = [0]

        def mock_redis_get_attempts(key):
            if 'medic:attempts:' in key:
                return str(attempt_counter[0]) if attempt_counter[0] > 0 else None
            return self.hitl_queue_data.get(key)

        def mock_redis_set_attempts(key, value, ttl=None):
            if 'medic:attempts:' in key:
                attempt_counter[0] = int(value)
            else:
                self.hitl_queue_data[key] = value
            return True

        self.mock_redis.get.side_effect = mock_redis_get_attempts
        self.mock_redis.set.side_effect = mock_redis_set_attempts

        # Mock Anthropic with fix that introduces regression
        mock_anthropic_response = Mock()
        mock_anthropic_response.content = [Mock(text="""
DIAGNOSIS: Selector issue

CONFIDENCE: 0.85

FIX:
```typescript
// This fix causes regression
await page.locator('[data-testid="new-element"]').click();
```
""")]
        mock_anthropic_response.usage = Mock(input_tokens=1000, output_tokens=250)

        mock_anthropic_client = Mock()
        mock_anthropic_client.messages.create = Mock(return_value=mock_anthropic_response)

        # Mock regression that always fails
        regression_counter = [0]

        def mock_regression_always_fails(*args, **kwargs):
            result = Mock()
            regression_counter[0] += 1
            if regression_counter[0] % 2 == 1:
                # Baseline: passing
                result.returncode = 0
                result.stdout = "2 passed (4.0s)"
            else:
                # After fix: regression
                result.returncode = 1
                result.stdout = "1 passed, 1 failed (4.5s)"
            result.stderr = ""
            return result

        medic = MedicAgent(redis_client=self.mock_redis, hitl_queue=self.hitl_queue)

        print("\n=== Attempting multiple Medic fixes ===")

        task_id = "task_max_retries_123"

        # Attempt 1, 2, 3 - all cause regressions
        for attempt in range(1, 4):
            print(f"\n--- Attempt {attempt} ---")

            regression_counter[0] = 0

            with patch.object(medic, 'client', mock_anthropic_client):
                with patch('subprocess.run', side_effect=mock_regression_always_fails):
                    result = medic.execute(
                        test_path=str(test_path),
                        error_message="Persistent failure",
                        task_id=task_id,
                        feature="persistent"
                    )

            assert not result.success
            print(f"✓ Attempt {attempt} failed: {result.data['reason']}")

        # Attempt 4 - should escalate due to MAX_RETRIES
        print(f"\n--- Attempt 4 (exceeds MAX_RETRIES=3) ---")

        regression_counter[0] = 0

        with patch.object(medic, 'client', mock_anthropic_client):
            with patch('subprocess.run', side_effect=mock_regression_always_fails):
                result = medic.execute(
                    test_path=str(test_path),
                    error_message="Persistent failure",
                    task_id=task_id,
                    feature="persistent"
                )

        assert not result.success
        assert result.data['status'] == 'escalated_to_hitl'
        assert result.data['reason'] == 'max_retries_exceeded'

        print(f"✓ Escalated to HITL after exceeding MAX_RETRIES")
        print(f"  Attempts: {attempt_counter[0]}")
        print(f"  Reason: {result.data['reason']}")

        # Verify HITL escalation
        hitl_tasks = self.hitl_queue.list()
        assert len(hitl_tasks) > 0

        escalated_task = next((t for t in hitl_tasks if t['task_id'] == task_id), None)
        assert escalated_task is not None
        assert escalated_task['escalation_reason'] == 'max_retries_exceeded'
        assert escalated_task['attempts'] == 4

        print(f"\n✓ HITL queue updated")
        print(f"  Total attempts: {escalated_task['attempts']}")

    def test_critical_path_high_priority(self):
        """
        Test: Critical path failure gets high priority in HITL queue

        Authentication/Payment failures → Priority > 0.7
        """
        print("\n" + "="*80)
        print("TEST: Critical Path → High Priority HITL")
        print("="*80)

        # Add multiple tasks with different features
        tasks = [
            {
                'task_id': 'task_regular_1',
                'feature': 'profile_page',
                'last_error': 'Regular error',
                'attempts': 2,
                'code_path': str(self.test_dir / 'profile.spec.ts'),
                'escalation_reason': 'low_confidence',
                'severity': 'medium'
            },
            {
                'task_id': 'task_auth_1',
                'feature': 'authentication',
                'last_error': 'Auth failure',
                'attempts': 1,
                'code_path': str(self.test_dir / 'auth.spec.ts'),
                'escalation_reason': 'max_retries_exceeded',
                'severity': 'high'
            },
            {
                'task_id': 'task_payment_1',
                'feature': 'payment_checkout',
                'last_error': 'Payment failure',
                'attempts': 3,
                'code_path': str(self.test_dir / 'payment.spec.ts'),
                'escalation_reason': 'regression_detected',
                'severity': 'critical'
            },
            {
                'task_id': 'task_regular_2',
                'feature': 'navigation',
                'last_error': 'Nav error',
                'attempts': 1,
                'code_path': str(self.test_dir / 'nav.spec.ts'),
                'escalation_reason': 'low_confidence',
                'severity': 'low'
            }
        ]

        print("\n=== Adding tasks to HITL queue ===")

        for task in tasks:
            self.hitl_queue.add(task)
            print(f"✓ Added {task['feature']} (severity: {task['severity']})")

        # Get queue sorted by priority
        print("\n=== HITL Queue (sorted by priority) ===")

        queue_tasks = self.hitl_queue.list(limit=10)

        for i, task in enumerate(queue_tasks):
            print(f"{i+1}. {task['feature']}")
            print(f"   Priority: {task['priority']:.2f}")
            print(f"   Severity: {task['severity']}")
            print(f"   Reason: {task['escalation_reason']}")

        # Verify prioritization
        # Critical paths (auth, payment) should be higher priority
        priorities = {task['task_id']: task['priority'] for task in queue_tasks}

        assert priorities['task_payment_1'] > 0.5, "Payment should have high priority"
        assert priorities['task_auth_1'] > 0.3, "Auth should have elevated priority"
        assert priorities['task_payment_1'] > priorities['task_regular_1'], \
            "Critical paths should outrank regular features"

        print(f"\n✓ Critical paths have higher priority")
        print(f"  Payment priority: {priorities['task_payment_1']:.2f}")
        print(f"  Auth priority: {priorities['task_auth_1']:.2f}")
        print(f"  Regular priority: {priorities['task_regular_1']:.2f}")

        # Verify payment is at top of queue
        assert queue_tasks[0]['feature'] == 'payment_checkout', \
            "Payment should be first in queue"

        print(f"\n✓ Queue correctly prioritized")

    def test_hitl_resolution_workflow(self):
        """
        Test: Complete HITL resolution workflow

        1. Task escalated to HITL
        2. Human resolves with annotation
        3. Annotation stored in vector DB
        4. Task marked as resolved
        """
        print("\n" + "="*80)
        print("TEST: HITL Resolution Workflow")
        print("="*80)

        # Add task to HITL
        print("\n=== Adding task to HITL ===")

        task = {
            'task_id': 'task_resolve_123',
            'feature': 'complex_form',
            'last_error': 'Complex selector issue',
            'attempts': 2,
            'code_path': str(self.test_dir / 'form.spec.ts'),
            'escalation_reason': 'low_confidence',
            'severity': 'medium'
        }

        self.hitl_queue.add(task)
        print(f"✓ Task added to HITL queue: {task['task_id']}")

        # Verify task in queue
        queue_tasks = self.hitl_queue.list()
        assert len(queue_tasks) == 1
        assert queue_tasks[0]['task_id'] == 'task_resolve_123'
        assert not queue_tasks[0].get('resolved', False)

        print(f"✓ Task active in queue (not resolved)")

        # Human provides resolution
        print("\n=== Human resolves task ===")

        annotation = {
            'root_cause_category': 'selector_specificity',
            'fix_strategy': 'use_more_specific_selector',
            'patch_diff': """
- await page.locator('.button').click();
+ await page.locator('[data-testid="submit-button"]').click();
""",
            'human_notes': 'The selector was too generic. Need to use data-testid for stability.',
            'resolution_time_minutes': 15,
            'resolved_by': 'human_reviewer_1'
        }

        success = self.hitl_queue.resolve('task_resolve_123', annotation)
        assert success, "Resolution should succeed"

        print(f"✓ Human provided resolution")
        print(f"  Root cause: {annotation['root_cause_category']}")
        print(f"  Strategy: {annotation['fix_strategy']}")
        print(f"  Time: {annotation['resolution_time_minutes']} minutes")

        # Verify task marked as resolved
        resolved_task = self.hitl_queue.get('task_resolve_123')
        assert resolved_task is not None
        assert resolved_task['resolved'] == True
        assert 'resolved_at' in resolved_task
        assert resolved_task['root_cause_category'] == 'selector_specificity'

        print(f"✓ Task marked as resolved")
        print(f"  Resolved at: {resolved_task['resolved_at']}")

        # Verify task removed from active queue
        active_tasks = self.hitl_queue.list(include_resolved=False)
        assert len(active_tasks) == 0, "No active tasks should remain"

        print(f"✓ Task removed from active queue")

        # Verify annotation stored in vector DB
        assert self.mock_vector.store_hitl_annotation.called
        print(f"✓ Annotation stored in vector DB for learning")

        print(f"\n✓ Complete HITL resolution workflow successful")

    def test_hitl_queue_stats(self):
        """
        Test: HITL queue statistics and reporting
        """
        print("\n" + "="*80)
        print("TEST: HITL Queue Statistics")
        print("="*80)

        # Add mix of tasks
        for i in range(5):
            self.hitl_queue.add({
                'task_id': f'task_{i}',
                'feature': f'feature_{i}',
                'last_error': f'Error {i}',
                'attempts': i + 1,
                'code_path': str(self.test_dir / f'test_{i}.spec.ts'),
                'escalation_reason': 'low_confidence',
                'severity': 'medium',
                'priority': 0.5 + (i * 0.1)
            })

        # Resolve some tasks
        self.hitl_queue.resolve('task_1', {'resolution': 'fixed'})
        self.hitl_queue.resolve('task_3', {'resolution': 'fixed'})

        # Get stats
        print("\n=== Queue Statistics ===")

        stats = self.hitl_queue.get_stats()

        print(f"Total tasks: {stats['total_count']}")
        print(f"Active tasks: {stats['active_count']}")
        print(f"Resolved tasks: {stats['resolved_count']}")
        print(f"High priority count: {stats['high_priority_count']}")
        print(f"Average priority: {stats['avg_priority']:.2f}")

        # Verify stats
        assert stats['total_count'] == 5
        assert stats['active_count'] == 3
        assert stats['resolved_count'] == 2
        assert stats['high_priority_count'] >= 0

        print(f"\n✓ Queue statistics accurate")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
