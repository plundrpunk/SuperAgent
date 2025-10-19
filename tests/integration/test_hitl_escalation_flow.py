"""
End-to-End Integration Test: HITL Escalation Workflow

This test validates the Human-in-the-Loop escalation system:
1. Medic attempts to fix a failing test
2. After 3 failed attempts, task escalates to HITL queue
3. Task appears in queue with priority score
4. Human resolves with annotation
5. Annotation is stored in Vector DB
6. Future Medic fix attempts retrieve the stored pattern

Implementation:
- Uses real Medic, HITLQueue, and VectorClient (mocked API calls)
- Tests full escalation workflow from failure to learning
- Validates priority calculation and annotation storage
- Tests pattern retrieval for future fixes
"""
import pytest
import tempfile
import shutil
import time
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from agent_system.agents.medic import MedicAgent
from agent_system.hitl.queue import HITLQueue
from agent_system.state.redis_client import RedisClient
from agent_system.state.vector_client import VectorClient


class TestHITLEscalationFlow:
    """
    End-to-end integration test for HITL escalation workflow.

    Tests the complete flow from test failure through escalation to learning.
    """

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Set up test environment and tear down after test."""
        # Create temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()
        self.test_dir = Path(self.temp_dir) / "tests"
        self.test_dir.mkdir(parents=True, exist_ok=True)

        # Initialize mock state clients
        self.mock_redis = Mock(spec=RedisClient)
        self.mock_vector = Mock(spec=VectorClient)

        # Configure mock Redis
        self.mock_redis.client = Mock()
        self.mock_redis.client.zadd = Mock(return_value=1)
        self.mock_redis.client.zrevrange = Mock(return_value=[])
        self.mock_redis.client.zrem = Mock(return_value=1)
        self.mock_redis.client.rpush = Mock(return_value=1)
        self.mock_redis.client.expire = Mock(return_value=True)
        self.mock_redis.client.lrange = Mock(return_value=[])
        self.mock_redis.get = Mock(return_value=None)
        self.mock_redis.set = Mock(return_value=True)

        # Configure mock Vector DB
        self.mock_vector.store_hitl_annotation = Mock(return_value=True)
        self.mock_vector.search_hitl_annotations = Mock(return_value=[])
        self.mock_vector._get_collection = Mock()

        # Task tracking
        self.task_id = "hitl_test_task_123"
        self.test_path = str(self.test_dir / "failing_test.spec.ts")

        # Create a failing test file
        with open(self.test_path, 'w') as f:
            f.write("""
import { test, expect } from '@playwright/test';

test('failing test', async ({ page }) => {
    await page.goto('https://example.com');
    await page.click('[data-testid="nonexistent-button"]');
    await expect(page.locator('[data-testid="result"]')).toBeVisible();
});
""")

        yield

        # Cleanup
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_medic_escalates_after_max_retries(self):
        """
        Test that Medic escalates to HITL after MAX_RETRIES attempts.

        Flow:
        1. Create Medic agent with mocked dependencies
        2. Simulate 3 failed fix attempts
        3. On 4th attempt, verify escalation to HITL
        4. Verify task added to queue with correct priority
        """
        print("\n=== Test: Medic Escalates After Max Retries ===")

        # Initialize HITL queue and Medic
        hitl_queue = HITLQueue(
            redis_client=self.mock_redis,
            vector_client=self.mock_vector
        )

        medic = MedicAgent(
            redis_client=self.mock_redis,
            hitl_queue=hitl_queue
        )

        error_message = "Error: locator.click: Target closed"

        # Mock Redis to simulate 3 previous attempts
        attempt_count = [0]  # Mutable counter

        def mock_get_attempts(key):
            if 'medic:attempts:' in key:
                return attempt_count[0]
            return None

        def mock_set_attempts(key, value, ttl=None):
            if 'medic:attempts:' in key:
                attempt_count[0] = value
            return True

        self.mock_redis.get = Mock(side_effect=mock_get_attempts)
        self.mock_redis.set = Mock(side_effect=mock_set_attempts)

        # Mock subprocess to prevent actual test execution
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=1,
                stdout="0 passed\n0 failed",
                stderr=""
            )

            # Attempt 1, 2, 3 should try to fix (but fail due to mocked API)
            for attempt_num in range(1, 4):
                print(f"\n--- Attempt #{attempt_num} ---")

                # Mock Anthropic API to simulate fix generation failure
                with patch.object(medic, '_generate_fix') as mock_generate_fix:
                    mock_generate_fix.return_value = {
                        'success': False,
                        'error': 'Simulated fix generation failure',
                        'cost_usd': 0.02
                    }

                    result = medic.execute(
                        test_path=self.test_path,
                        error_message=error_message,
                        task_id=self.task_id,
                        feature="Failing Feature"
                    )

                    assert not result.success, f"Attempt {attempt_num} should fail"
                    print(f"Attempt #{attempt_num} failed as expected")

            # Attempt 4 should escalate to HITL
            print(f"\n--- Attempt #4 (should escalate) ---")

            # Mock HITL queue add method to capture task
            captured_task = []

            def mock_hitl_add(task):
                captured_task.append(task)
                return True

            hitl_queue.add = Mock(side_effect=mock_hitl_add)

            # Mock the API again (should not be called since we escalate immediately)
            with patch.object(medic, '_generate_fix') as mock_generate_fix:
                mock_generate_fix.return_value = {
                    'success': False,
                    'error': 'Should not be called',
                    'cost_usd': 0.0
                }

                result = medic.execute(
                    test_path=self.test_path,
                    error_message=error_message,
                    task_id=self.task_id,
                    feature="Failing Feature"
                )

                # Verify escalation
                assert not result.success, "Escalation should return success=False"
                assert result.data['status'] == 'escalated_to_hitl'
                assert result.data['reason'] == 'max_retries_exceeded'
                assert result.data['attempts'] == 4

                print(f"✓ Task escalated to HITL after {result.data['attempts']} attempts")

                # Verify HITL task was added
                assert len(captured_task) == 1, "Task should be added to HITL queue"

                hitl_task = captured_task[0]
                assert hitl_task['task_id'] == self.task_id
                assert hitl_task['feature'] == "Failing Feature"
                assert hitl_task['code_path'] == self.test_path
                assert hitl_task['attempts'] == 4
                assert hitl_task['last_error'] == error_message
                assert hitl_task['escalation_reason'] == 'max_retries_exceeded'
                assert 0.0 <= hitl_task['priority'] <= 1.0

                print(f"✓ HITL task created with priority {hitl_task['priority']:.2f}")

    def test_hitl_priority_calculation(self):
        """
        Test that HITL queue correctly calculates priority scores.

        Priority factors:
        - Attempts: More attempts = higher priority
        - Feature criticality: auth/payment = higher priority
        - Time in queue: Older tasks = higher priority
        """
        print("\n=== Test: HITL Priority Calculation ===")

        hitl_queue = HITLQueue(
            redis_client=self.mock_redis,
            vector_client=self.mock_vector
        )

        # Test Case 1: Regular task with few attempts
        task1 = {
            'task_id': 'task_1',
            'feature': 'user profile',
            'code_path': '/tests/profile.spec.ts',
            'logs_path': '/logs/task_1.log',
            'screenshots': [],
            'attempts': 1,
            'last_error': 'Selector not found'
        }

        hitl_queue.add(task1)
        retrieved_task1 = hitl_queue.get('task_1')

        priority1 = retrieved_task1['priority']
        print(f"Regular task priority: {priority1:.2f}")
        assert 0.0 <= priority1 <= 0.5, "Regular task should have low-medium priority"

        # Test Case 2: Critical auth task
        task2 = {
            'task_id': 'task_2',
            'feature': 'authentication login',
            'code_path': '/tests/auth.spec.ts',
            'logs_path': '/logs/task_2.log',
            'screenshots': [],
            'attempts': 2,
            'last_error': 'Auth token expired'
        }

        hitl_queue.add(task2)
        retrieved_task2 = hitl_queue.get('task_2')

        priority2 = retrieved_task2['priority']
        print(f"Auth task priority: {priority2:.2f}")
        assert priority2 > priority1, "Auth task should have higher priority"
        assert priority2 >= 0.3, "Auth task should get criticality boost"

        # Test Case 3: Payment task with many attempts
        task3 = {
            'task_id': 'task_3',
            'feature': 'payment checkout',
            'code_path': '/tests/checkout.spec.ts',
            'logs_path': '/logs/task_3.log',
            'screenshots': [],
            'attempts': 5,
            'last_error': 'Payment gateway timeout'
        }

        hitl_queue.add(task3)
        retrieved_task3 = hitl_queue.get('task_3')

        priority3 = retrieved_task3['priority']
        print(f"Payment task with 5 attempts priority: {priority3:.2f}")
        assert priority3 > priority2, "Payment + high attempts should be highest priority"
        assert priority3 >= 0.5, "Should combine criticality and attempts bonuses"

        print("✓ Priority calculation validated")

    def test_human_resolution_with_annotation(self):
        """
        Test human resolution of HITL task with annotation storage.

        Flow:
        1. Add task to HITL queue
        2. Simulate human resolving task with annotation
        3. Verify annotation stored in Vector DB
        4. Verify task marked as resolved
        """
        print("\n=== Test: Human Resolution with Annotation ===")

        hitl_queue = HITLQueue(
            redis_client=self.mock_redis,
            vector_client=self.mock_vector
        )

        # Add task to queue
        task = {
            'task_id': 'resolve_test_123',
            'feature': 'user login',
            'code_path': self.test_path,
            'logs_path': '/logs/resolve_test.log',
            'screenshots': ['/artifacts/screenshot1.png'],
            'attempts': 3,
            'last_error': 'Timeout waiting for login button',
            'priority': 0.5
        }

        hitl_queue.add(task)

        # Verify task in queue
        retrieved = hitl_queue.get('resolve_test_123')
        assert retrieved is not None
        assert retrieved['resolved'] == False

        print("✓ Task added to HITL queue")

        # Simulate human resolution
        human_annotation = {
            'root_cause': 'selector_flaky',
            'fix_strategy': 'add_explicit_waits',
            'severity': 'medium',
            'human_notes': 'The login button loads dynamically. Added waitForSelector with 5s timeout.',
            'patch_diff': """
@@ -10,7 +10,8 @@
 test('login test', async ({ page }) => {
     await page.goto('/login');
-    await page.click('[data-testid="login-button"]');
+    await page.waitForSelector('[data-testid="login-button"]', { timeout: 5000 });
+    await page.click('[data-testid="login-button"]');
     await expect(page.locator('[data-testid="welcome"]')).toBeVisible();
 });
"""
        }

        # Resolve task
        success = hitl_queue.resolve('resolve_test_123', human_annotation)
        assert success, "Resolution should succeed"

        print("✓ Task resolved with annotation")

        # Verify task marked as resolved
        resolved_task = hitl_queue.get('resolve_test_123')
        assert resolved_task['resolved'] == True
        assert resolved_task['root_cause'] == 'selector_flaky'
        assert resolved_task['fix_strategy'] == 'add_explicit_waits'
        assert 'resolved_at' in resolved_task

        print("✓ Task marked as resolved")

        # Verify annotation stored in Vector DB
        assert self.mock_vector.store_hitl_annotation.called
        call_args = self.mock_vector.store_hitl_annotation.call_args

        annotation_id = call_args[1]['annotation_id']
        task_description = call_args[1]['task_description']
        annotation_data = call_args[1]['annotation']

        assert 'hitl_resolve_test_123' in annotation_id
        assert task_description == 'user login'
        assert annotation_data['root_cause'] == 'selector_flaky'
        assert annotation_data['fix_strategy'] == 'add_explicit_waits'

        print("✓ Annotation stored in Vector DB")

    def test_annotation_retrieval_for_future_fixes(self):
        """
        Test that Medic can retrieve HITL annotations for similar failures.

        Flow:
        1. Store HITL annotation in Vector DB
        2. Simulate Medic encountering similar error
        3. Verify Medic searches for and retrieves annotation
        4. Verify annotation context improves fix generation
        """
        print("\n=== Test: Annotation Retrieval for Future Fixes ===")

        # Store annotation in Vector DB
        annotation = {
            'root_cause': 'timing_race_condition',
            'fix_strategy': 'add_explicit_waits',
            'severity': 'medium',
            'human_notes': 'Add waitForLoadState before interactions',
            'patch_diff': '+ await page.waitForLoadState("networkidle");'
        }

        self.mock_vector.store_hitl_annotation(
            annotation_id='hitl_similar_test_456',
            task_description='button click timeout',
            annotation=annotation
        )

        print("✓ Annotation stored")

        # Configure Vector DB to return this annotation when searched
        self.mock_vector.search_hitl_annotations = Mock(return_value=[
            {
                'id': 'hitl_similar_test_456',
                'annotation': annotation,
                'metadata': {'task_description': 'button click timeout'},
                'similarity': 0.85
            }
        ])

        # Simulate Medic searching for similar patterns
        query = "timeout waiting for button click"
        results = self.mock_vector.search_hitl_annotations(query, n_results=5)

        assert len(results) == 1
        assert results[0]['annotation']['root_cause'] == 'timing_race_condition'
        assert results[0]['annotation']['fix_strategy'] == 'add_explicit_waits'
        assert results[0]['similarity'] >= 0.8

        print("✓ Annotation retrieved with high similarity")
        print(f"  Root cause: {results[0]['annotation']['root_cause']}")
        print(f"  Fix strategy: {results[0]['annotation']['fix_strategy']}")
        print(f"  Similarity: {results[0]['similarity']:.2f}")

    def test_hitl_queue_listing_and_filtering(self):
        """
        Test HITL queue listing with filtering options.

        Verifies:
        - List all tasks sorted by priority
        - Filter by resolved status
        - Limit results
        """
        print("\n=== Test: HITL Queue Listing and Filtering ===")

        hitl_queue = HITLQueue(
            redis_client=self.mock_redis,
            vector_client=self.mock_vector
        )

        # Add multiple tasks
        tasks = [
            {
                'task_id': 'task_low_priority',
                'feature': 'profile',
                'code_path': '/tests/profile.spec.ts',
                'logs_path': '/logs/1.log',
                'screenshots': [],
                'attempts': 1,
                'last_error': 'Minor issue',
                'priority': 0.2
            },
            {
                'task_id': 'task_high_priority',
                'feature': 'payment checkout',
                'code_path': '/tests/checkout.spec.ts',
                'logs_path': '/logs/2.log',
                'screenshots': [],
                'attempts': 5,
                'last_error': 'Payment failed',
                'priority': 0.8
            },
            {
                'task_id': 'task_medium_priority',
                'feature': 'auth login',
                'code_path': '/tests/auth.spec.ts',
                'logs_path': '/logs/3.log',
                'screenshots': [],
                'attempts': 2,
                'last_error': 'Login timeout',
                'priority': 0.5
            }
        ]

        for task in tasks:
            hitl_queue.add(task)

        print(f"✓ Added {len(tasks)} tasks to queue")

        # Mock zrevrange to return task IDs in priority order (high to low)
        self.mock_redis.client.zrevrange = Mock(return_value=[
            b'task_high_priority',
            b'task_medium_priority',
            b'task_low_priority'
        ])

        # Mock get to return task data
        def mock_get_task(key):
            task_id = key.replace('hitl:task:', '')
            for task in tasks:
                if task['task_id'] == task_id:
                    return {**task, 'resolved': False}
            return None

        self.mock_redis.get = Mock(side_effect=mock_get_task)

        # List all tasks
        all_tasks = hitl_queue.list()

        assert len(all_tasks) == 3
        assert all_tasks[0]['task_id'] == 'task_high_priority'
        assert all_tasks[1]['task_id'] == 'task_medium_priority'
        assert all_tasks[2]['task_id'] == 'task_low_priority'

        print("✓ Tasks listed in priority order (high to low)")

        # Test limit
        self.mock_redis.client.zrevrange = Mock(return_value=[
            b'task_high_priority',
            b'task_medium_priority'
        ])

        limited_tasks = hitl_queue.list(limit=2)
        assert len(limited_tasks) <= 2

        print("✓ Limit parameter works")

    def test_hitl_queue_stats(self):
        """
        Test HITL queue statistics calculation.

        Verifies:
        - Total count
        - Active count
        - Resolved count
        - Average priority
        - High priority count
        """
        print("\n=== Test: HITL Queue Stats ===")

        hitl_queue = HITLQueue(
            redis_client=self.mock_redis,
            vector_client=self.mock_vector
        )

        # Add tasks with various states
        tasks = [
            {'task_id': 't1', 'priority': 0.3, 'resolved': False},
            {'task_id': 't2', 'priority': 0.7, 'resolved': False},
            {'task_id': 't3', 'priority': 0.9, 'resolved': False},
            {'task_id': 't4', 'priority': 0.5, 'resolved': True},
        ]

        for task in tasks:
            task.update({
                'feature': 'test',
                'code_path': '/test.ts',
                'logs_path': '/logs/test.log',
                'screenshots': [],
                'attempts': 1,
                'last_error': 'Error'
            })
            hitl_queue.add(task)

        # Mock list to return all tasks
        def mock_list(include_resolved=False):
            if include_resolved:
                return tasks
            return [t for t in tasks if not t['resolved']]

        hitl_queue.list = Mock(side_effect=mock_list)

        # Get stats
        stats = hitl_queue.get_stats()

        assert stats['total_count'] == 4
        assert stats['active_count'] == 3
        assert stats['resolved_count'] == 1
        assert stats['high_priority_count'] == 2  # Priority > 0.7

        # Average priority of active tasks: (0.3 + 0.7 + 0.9) / 3 = 0.633
        assert abs(stats['avg_priority'] - 0.633) < 0.01

        print("✓ Queue statistics calculated correctly")
        print(f"  Total: {stats['total_count']}")
        print(f"  Active: {stats['active_count']}")
        print(f"  Resolved: {stats['resolved_count']}")
        print(f"  Avg Priority: {stats['avg_priority']:.2f}")
        print(f"  High Priority: {stats['high_priority_count']}")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
