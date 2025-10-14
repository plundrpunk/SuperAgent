"""
Unit tests for agent_system/hitl/queue.py

Tests cover:
- Adding tasks to HITL queue with priority calculation
- Listing queue items sorted by priority (high to low)
- Marking tasks as resolved with annotations
- Priority scoring algorithm (attempts, feature criticality, time in queue)
- Queue persistence and isolation
- HITL schema validation
- Vector DB annotation storage
"""
import pytest
import json
import time
import sys
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime, timedelta
from typing import Dict, Any

# Mock dependencies before importing HITLQueue
mock_redis = MagicMock()
mock_chromadb = MagicMock()
mock_chromadb_config = MagicMock()
mock_sentence_transformers = MagicMock()

sys.modules['redis'] = mock_redis
sys.modules['chromadb'] = mock_chromadb
sys.modules['chromadb.config'] = mock_chromadb_config
sys.modules['sentence_transformers'] = mock_sentence_transformers

from agent_system.hitl.queue import HITLQueue


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_redis_client():
    """Mock Redis client for testing."""
    mock_client = Mock()

    # Mock zadd for sorted set operations
    mock_client.client.zadd = Mock(return_value=1)

    # Mock zrevrange for getting sorted tasks
    mock_client.client.zrevrange = Mock(return_value=[])

    # Mock zrem for removing from sorted set
    mock_client.client.zrem = Mock(return_value=1)

    # Mock set/get operations
    mock_client.set = Mock(return_value=True)
    mock_client.get = Mock(return_value=None)

    return mock_client


@pytest.fixture
def mock_vector_client():
    """Mock Vector DB client for testing."""
    mock_client = Mock()
    mock_client.store_hitl_annotation = Mock(return_value=True)
    return mock_client


@pytest.fixture
def hitl_queue(mock_redis_client, mock_vector_client):
    """Create HITLQueue with mocked dependencies."""
    return HITLQueue(redis_client=mock_redis_client, vector_client=mock_vector_client)


@pytest.fixture
def sample_task():
    """Sample task matching schema.json."""
    return {
        'task_id': 't_123',
        'feature': 'login form validation',
        'code_path': 'tests/auth/login.spec.ts',
        'logs_path': 'logs/login-20250114.log',
        'screenshots': ['screenshot1.png', 'screenshot2.png'],
        'attempts': 2,
        'last_error': 'Selector not found: [data-testid="login-button"]',
        'priority': None,  # Will be calculated
        'created_at': datetime.utcnow().isoformat()
    }


@pytest.fixture
def sample_auth_task():
    """Sample auth task (high priority feature)."""
    return {
        'task_id': 't_auth_456',
        'feature': 'oauth authentication flow',
        'code_path': 'tests/auth/oauth.spec.ts',
        'logs_path': 'logs/oauth-20250114.log',
        'screenshots': ['oauth1.png'],
        'attempts': 5,
        'last_error': 'OAuth callback timeout',
        'priority': None,
        'created_at': (datetime.utcnow() - timedelta(hours=12)).isoformat()
    }


@pytest.fixture
def sample_payment_task():
    """Sample payment task (critical feature)."""
    return {
        'task_id': 't_pay_789',
        'feature': 'stripe checkout integration',
        'code_path': 'tests/payment/stripe.spec.ts',
        'logs_path': 'logs/payment-20250114.log',
        'screenshots': ['checkout.png'],
        'attempts': 8,
        'last_error': 'Payment intent failed',
        'priority': None,
        'created_at': (datetime.utcnow() - timedelta(hours=20)).isoformat()
    }


@pytest.fixture
def sample_annotation():
    """Sample human annotation."""
    return {
        'root_cause_category': 'selector_flaky',
        'fix_strategy': 'update_selectors',
        'severity': 'medium',
        'human_notes': 'Button selector changed due to UI redesign',
        'patch_diff': '@@ -10,1 +10,1 @@\n-await page.click("[data-testid=\\"login-btn\\"]");\n+await page.click("[data-testid=\\"login-button\\"]");'
    }


# ============================================================================
# TEST: Adding Tasks to Queue
# ============================================================================

class TestAddTask:
    """Test adding tasks to HITL queue."""

    def test_add_task_basic(self, hitl_queue, sample_task, mock_redis_client):
        """Test adding basic task to queue."""
        result = hitl_queue.add(sample_task)

        assert result is True

        # Verify Redis operations
        mock_redis_client.set.assert_called_once()
        args = mock_redis_client.set.call_args[0]
        assert args[0] == 'hitl:task:t_123'
        assert args[1]['task_id'] == 't_123'
        assert 'priority' in args[1]

        # Verify added to sorted set
        mock_redis_client.client.zadd.assert_called_once()

    def test_add_task_calculates_priority(self, hitl_queue, sample_task, mock_redis_client):
        """Test that priority is calculated when not provided."""
        sample_task['priority'] = None

        result = hitl_queue.add(sample_task)

        # Extract the stored task from Redis set call
        stored_task = mock_redis_client.set.call_args[0][1]

        assert stored_task['priority'] is not None
        assert 0.0 <= stored_task['priority'] <= 1.0

    def test_add_task_preserves_existing_priority(self, hitl_queue, sample_task, mock_redis_client):
        """Test that existing priority is preserved."""
        sample_task['priority'] = 0.85

        result = hitl_queue.add(sample_task)

        stored_task = mock_redis_client.set.call_args[0][1]
        assert stored_task['priority'] == 0.85

    def test_add_task_adds_timestamp_if_missing(self, hitl_queue, sample_task, mock_redis_client):
        """Test that created_at timestamp is added if not present."""
        del sample_task['created_at']

        result = hitl_queue.add(sample_task)

        stored_task = mock_redis_client.set.call_args[0][1]
        assert 'created_at' in stored_task
        # Verify it's a valid ISO timestamp
        datetime.fromisoformat(stored_task['created_at'])

    def test_add_task_uses_24h_ttl(self, hitl_queue, sample_task, mock_redis_client):
        """Test that tasks are stored with 24h TTL."""
        hitl_queue.add(sample_task)

        args = mock_redis_client.set.call_args
        assert args[1]['ttl'] == 86400  # 24 hours in seconds

    def test_add_task_raises_error_without_task_id(self, hitl_queue):
        """Test that adding task without task_id raises ValueError."""
        invalid_task = {
            'feature': 'test feature',
            'code_path': 'test.spec.ts'
        }

        with pytest.raises(ValueError, match="task_id is required"):
            hitl_queue.add(invalid_task)

    def test_add_task_with_empty_task_id(self, hitl_queue):
        """Test that empty task_id raises ValueError."""
        invalid_task = {
            'task_id': '',
            'feature': 'test feature',
            'code_path': 'test.spec.ts'
        }

        with pytest.raises(ValueError, match="task_id is required"):
            hitl_queue.add(invalid_task)

    def test_add_task_with_none_task_id(self, hitl_queue):
        """Test that None task_id raises ValueError."""
        invalid_task = {
            'task_id': None,
            'feature': 'test feature',
            'code_path': 'test.spec.ts'
        }

        with pytest.raises(ValueError, match="task_id is required"):
            hitl_queue.add(invalid_task)


# ============================================================================
# TEST: Priority Calculation Algorithm
# ============================================================================

class TestPriorityCalculation:
    """Test priority scoring algorithm."""

    def test_priority_attempts_factor(self, hitl_queue):
        """Test priority calculation based on attempts."""
        # Low attempts (1)
        task_low = {
            'task_id': 't1',
            'feature': 'test',
            'attempts': 1,
            'created_at': datetime.utcnow().isoformat()
        }
        priority_low = hitl_queue._calculate_priority(task_low)

        # Medium attempts (5)
        task_med = {
            'task_id': 't2',
            'feature': 'test',
            'attempts': 5,
            'created_at': datetime.utcnow().isoformat()
        }
        priority_med = hitl_queue._calculate_priority(task_med)

        # High attempts (10)
        task_high = {
            'task_id': 't3',
            'feature': 'test',
            'attempts': 10,
            'created_at': datetime.utcnow().isoformat()
        }
        priority_high = hitl_queue._calculate_priority(task_high)

        # Verify increasing priority with attempts
        assert priority_low < priority_med < priority_high

        # Verify attempts contribute max 0.4 to score
        assert priority_high <= 0.4 + 0.01  # Allow small float precision

    def test_priority_attempts_caps_at_max(self, hitl_queue):
        """Test that attempts score caps at 0.4 even with very high attempts."""
        task_extreme = {
            'task_id': 't_extreme',
            'feature': 'test',
            'attempts': 100,
            'created_at': datetime.utcnow().isoformat()
        }
        priority = hitl_queue._calculate_priority(task_extreme)

        # Attempts factor should not exceed 0.4
        # Total priority might be higher due to other factors
        assert priority <= 1.0

    def test_priority_auth_feature_boost(self, hitl_queue):
        """Test that auth-related features get +0.3 priority boost."""
        auth_keywords = ['auth', 'login', 'authentication', 'oauth']

        for keyword in auth_keywords:
            task = {
                'task_id': f't_{keyword}',
                'feature': f'{keyword} flow',
                'attempts': 1,
                'created_at': datetime.utcnow().isoformat()
            }
            priority = hitl_queue._calculate_priority(task)

            # Should have base attempts (0.1) + auth boost (0.3) = 0.4
            assert priority >= 0.3  # At least the auth boost

    def test_priority_payment_feature_boost(self, hitl_queue):
        """Test that payment-related features get +0.3 priority boost."""
        payment_keywords = ['payment', 'checkout', 'stripe', 'paypal']

        for keyword in payment_keywords:
            task = {
                'task_id': f't_{keyword}',
                'feature': f'{keyword} integration',
                'attempts': 1,
                'created_at': datetime.utcnow().isoformat()
            }
            priority = hitl_queue._calculate_priority(task)

            # Should have auth boost
            assert priority >= 0.3

    def test_priority_case_insensitive_feature_matching(self, hitl_queue):
        """Test that feature keyword matching is case-insensitive."""
        task_lower = {
            'task_id': 't_lower',
            'feature': 'user authentication',
            'attempts': 1,
            'created_at': datetime.utcnow().isoformat()
        }
        task_upper = {
            'task_id': 't_upper',
            'feature': 'USER AUTHENTICATION',
            'attempts': 1,
            'created_at': datetime.utcnow().isoformat()
        }
        task_mixed = {
            'task_id': 't_mixed',
            'feature': 'User Authentication',
            'attempts': 1,
            'created_at': datetime.utcnow().isoformat()
        }

        priority_lower = hitl_queue._calculate_priority(task_lower)
        priority_upper = hitl_queue._calculate_priority(task_upper)
        priority_mixed = hitl_queue._calculate_priority(task_mixed)

        # All should get same priority boost
        assert priority_lower == priority_upper == priority_mixed

    def test_priority_time_in_queue_factor(self, hitl_queue):
        """Test priority calculation based on time in queue."""
        # Recent task (1 hour old)
        task_recent = {
            'task_id': 't_recent',
            'feature': 'test',
            'attempts': 1,
            'created_at': (datetime.utcnow() - timedelta(hours=1)).isoformat()
        }
        priority_recent = hitl_queue._calculate_priority(task_recent)

        # Old task (12 hours old)
        task_old = {
            'task_id': 't_old',
            'feature': 'test',
            'attempts': 1,
            'created_at': (datetime.utcnow() - timedelta(hours=12)).isoformat()
        }
        priority_old = hitl_queue._calculate_priority(task_old)

        # Very old task (48 hours old)
        task_very_old = {
            'task_id': 't_very_old',
            'feature': 'test',
            'attempts': 1,
            'created_at': (datetime.utcnow() - timedelta(hours=48)).isoformat()
        }
        priority_very_old = hitl_queue._calculate_priority(task_very_old)

        # Older tasks should have higher priority
        assert priority_recent < priority_old < priority_very_old

    def test_priority_time_caps_at_24h(self, hitl_queue):
        """Test that time factor caps at 0.3 after 24 hours."""
        task_30h = {
            'task_id': 't_30h',
            'feature': 'test',
            'attempts': 1,
            'created_at': (datetime.utcnow() - timedelta(hours=30)).isoformat()
        }
        priority_30h = hitl_queue._calculate_priority(task_30h)

        task_100h = {
            'task_id': 't_100h',
            'feature': 'test',
            'attempts': 1,
            'created_at': (datetime.utcnow() - timedelta(hours=100)).isoformat()
        }
        priority_100h = hitl_queue._calculate_priority(task_100h)

        # Both should have same time contribution (capped at 0.3)
        # Total: attempts (0.1) + time (0.3) = 0.4
        assert abs(priority_30h - priority_100h) < 0.01

    def test_priority_missing_created_at_handled(self, hitl_queue):
        """Test that missing created_at doesn't break priority calculation."""
        task_no_time = {
            'task_id': 't_no_time',
            'feature': 'test',
            'attempts': 1
        }

        # Should not raise exception
        priority = hitl_queue._calculate_priority(task_no_time)

        # Should still calculate priority based on attempts
        assert priority >= 0.0
        assert priority <= 1.0

    def test_priority_invalid_created_at_handled(self, hitl_queue):
        """Test that invalid created_at format is handled gracefully."""
        task_bad_time = {
            'task_id': 't_bad_time',
            'feature': 'test',
            'attempts': 1,
            'created_at': 'not-a-valid-timestamp'
        }

        # Should not raise exception
        priority = hitl_queue._calculate_priority(task_bad_time)

        assert priority >= 0.0
        assert priority <= 1.0

    def test_priority_combined_factors(self, hitl_queue):
        """Test priority calculation with all factors combined."""
        task_critical = {
            'task_id': 't_critical',
            'feature': 'payment authentication',  # Both payment and auth keywords
            'attempts': 8,  # High attempts
            'created_at': (datetime.utcnow() - timedelta(hours=20)).isoformat()  # Old
        }

        priority = hitl_queue._calculate_priority(task_critical)

        # Expected: attempts (0.4 max) + critical feature (0.3) + time (~0.25) = ~0.95
        assert priority >= 0.8
        assert priority <= 1.0

    def test_priority_range_validation(self, hitl_queue):
        """Test that priority is always in valid range [0.0, 1.0]."""
        test_cases = [
            {'task_id': 't1', 'feature': 'simple test', 'attempts': 0},
            {'task_id': 't2', 'feature': 'auth payment checkout login', 'attempts': 100},
            {'task_id': 't3', 'feature': 'test', 'attempts': 5, 'created_at': (datetime.utcnow() - timedelta(days=365)).isoformat()},
        ]

        for task in test_cases:
            priority = hitl_queue._calculate_priority(task)
            assert 0.0 <= priority <= 1.0, f"Priority {priority} out of range for task {task['task_id']}"

    def test_priority_default_attempts(self, hitl_queue):
        """Test priority calculation with missing attempts field."""
        task_no_attempts = {
            'task_id': 't_no_attempts',
            'feature': 'test',
            'created_at': datetime.utcnow().isoformat()
        }

        priority = hitl_queue._calculate_priority(task_no_attempts)

        # Should default to attempts=1
        assert priority >= 0.0
        assert priority <= 1.0


# ============================================================================
# TEST: Listing Queue Items
# ============================================================================

class TestListQueue:
    """Test listing queue items sorted by priority."""

    def test_list_empty_queue(self, hitl_queue, mock_redis_client):
        """Test listing empty queue."""
        mock_redis_client.client.zrevrange.return_value = []

        tasks = hitl_queue.list()

        assert tasks == []
        mock_redis_client.client.zrevrange.assert_called_once()

    def test_list_queue_sorted_by_priority(self, hitl_queue, mock_redis_client):
        """Test that tasks are returned sorted by priority (highest first)."""
        # Mock Redis to return task IDs in priority order
        mock_redis_client.client.zrevrange.return_value = [b't_high', b't_med', b't_low']

        # Mock get to return task data
        def mock_get(key):
            if key == 'hitl:task:t_high':
                return {'task_id': 't_high', 'priority': 0.9, 'resolved': False}
            elif key == 'hitl:task:t_med':
                return {'task_id': 't_med', 'priority': 0.5, 'resolved': False}
            elif key == 'hitl:task:t_low':
                return {'task_id': 't_low', 'priority': 0.2, 'resolved': False}
            return None

        mock_redis_client.get.side_effect = mock_get

        tasks = hitl_queue.list()

        assert len(tasks) == 3
        assert tasks[0]['task_id'] == 't_high'
        assert tasks[1]['task_id'] == 't_med'
        assert tasks[2]['task_id'] == 't_low'

    def test_list_queue_excludes_resolved_by_default(self, hitl_queue, mock_redis_client):
        """Test that resolved tasks are excluded by default."""
        mock_redis_client.client.zrevrange.return_value = [b't_active', b't_resolved']

        def mock_get(key):
            if key == 'hitl:task:t_active':
                return {'task_id': 't_active', 'resolved': False}
            elif key == 'hitl:task:t_resolved':
                return {'task_id': 't_resolved', 'resolved': True}
            return None

        mock_redis_client.get.side_effect = mock_get

        tasks = hitl_queue.list()

        assert len(tasks) == 1
        assert tasks[0]['task_id'] == 't_active'

    def test_list_queue_includes_resolved_when_requested(self, hitl_queue, mock_redis_client):
        """Test that resolved tasks are included when requested."""
        mock_redis_client.client.zrevrange.return_value = [b't_active', b't_resolved']

        def mock_get(key):
            if key == 'hitl:task:t_active':
                return {'task_id': 't_active', 'resolved': False}
            elif key == 'hitl:task:t_resolved':
                return {'task_id': 't_resolved', 'resolved': True}
            return None

        mock_redis_client.get.side_effect = mock_get

        tasks = hitl_queue.list(include_resolved=True)

        assert len(tasks) == 2
        assert any(t['task_id'] == 't_active' for t in tasks)
        assert any(t['task_id'] == 't_resolved' for t in tasks)

    def test_list_queue_with_limit(self, hitl_queue, mock_redis_client):
        """Test listing queue with result limit."""
        mock_redis_client.client.zrevrange.return_value = [b't1', b't2']

        def mock_get(key):
            task_id = key.split(':')[-1]
            return {'task_id': task_id, 'resolved': False}

        mock_redis_client.get.side_effect = mock_get

        tasks = hitl_queue.list(limit=2)

        # Verify zrevrange was called with correct limit
        call_args = mock_redis_client.client.zrevrange.call_args[0]
        assert call_args[0] == 'hitl:queue'
        assert call_args[1] == 0
        assert call_args[2] == 1  # limit - 1

    def test_list_queue_with_none_limit(self, hitl_queue, mock_redis_client):
        """Test listing queue with no limit (all results)."""
        mock_redis_client.client.zrevrange.return_value = []

        hitl_queue.list(limit=None)

        # Verify zrevrange was called with -1 for all results
        call_args = mock_redis_client.client.zrevrange.call_args[0]
        assert call_args[2] == -1

    def test_list_queue_skips_missing_tasks(self, hitl_queue, mock_redis_client):
        """Test that list handles missing tasks gracefully."""
        mock_redis_client.client.zrevrange.return_value = [b't_exists', b't_missing', b't_also_exists']

        def mock_get(key):
            if key == 'hitl:task:t_exists':
                return {'task_id': 't_exists', 'resolved': False}
            elif key == 'hitl:task:t_also_exists':
                return {'task_id': 't_also_exists', 'resolved': False}
            return None  # t_missing returns None

        mock_redis_client.get.side_effect = mock_get

        tasks = hitl_queue.list()

        assert len(tasks) == 2
        assert tasks[0]['task_id'] == 't_exists'
        assert tasks[1]['task_id'] == 't_also_exists'


# ============================================================================
# TEST: Getting Specific Task
# ============================================================================

class TestGetTask:
    """Test getting specific task details."""

    def test_get_existing_task(self, hitl_queue, mock_redis_client):
        """Test getting existing task by ID."""
        task_data = {
            'task_id': 't_123',
            'feature': 'test feature',
            'priority': 0.5
        }
        mock_redis_client.get.return_value = task_data

        result = hitl_queue.get('t_123')

        assert result == task_data
        mock_redis_client.get.assert_called_once_with('hitl:task:t_123')

    def test_get_nonexistent_task(self, hitl_queue, mock_redis_client):
        """Test getting non-existent task returns None."""
        mock_redis_client.get.return_value = None

        result = hitl_queue.get('t_nonexistent')

        assert result is None


# ============================================================================
# TEST: Resolving Tasks
# ============================================================================

class TestResolveTask:
    """Test marking tasks as resolved with annotations."""

    def test_resolve_task_updates_status(self, hitl_queue, mock_redis_client, mock_vector_client, sample_annotation):
        """Test that resolve updates task status."""
        existing_task = {
            'task_id': 't_123',
            'feature': 'login',
            'priority': 0.5,
            'resolved': False
        }
        mock_redis_client.get.return_value = existing_task

        result = hitl_queue.resolve('t_123', sample_annotation)

        assert result is True

        # Verify task was updated with resolved status
        mock_redis_client.set.assert_called_once()
        updated_task = mock_redis_client.set.call_args[0][1]
        assert updated_task['resolved'] is True
        assert 'resolved_at' in updated_task

    def test_resolve_task_merges_annotation(self, hitl_queue, mock_redis_client, mock_vector_client, sample_annotation):
        """Test that resolve merges annotation into task."""
        existing_task = {
            'task_id': 't_123',
            'feature': 'login',
            'priority': 0.5
        }
        mock_redis_client.get.return_value = existing_task

        hitl_queue.resolve('t_123', sample_annotation)

        updated_task = mock_redis_client.set.call_args[0][1]
        assert updated_task['root_cause_category'] == 'selector_flaky'
        assert updated_task['fix_strategy'] == 'update_selectors'
        assert updated_task['severity'] == 'medium'
        assert updated_task['human_notes'] == sample_annotation['human_notes']

    def test_resolve_task_removes_from_queue(self, hitl_queue, mock_redis_client, mock_vector_client, sample_annotation):
        """Test that resolve removes task from active queue."""
        existing_task = {
            'task_id': 't_123',
            'feature': 'login',
            'priority': 0.5
        }
        mock_redis_client.get.return_value = existing_task

        hitl_queue.resolve('t_123', sample_annotation)

        # Verify task was removed from sorted set
        mock_redis_client.client.zrem.assert_called_once_with('hitl:queue', 't_123')

    def test_resolve_task_stores_annotation_in_vector_db(self, hitl_queue, mock_redis_client, mock_vector_client, sample_annotation):
        """Test that resolve stores annotation in vector DB."""
        existing_task = {
            'task_id': 't_123',
            'feature': 'login authentication',
            'priority': 0.5
        }
        mock_redis_client.get.return_value = existing_task

        hitl_queue.resolve('t_123', sample_annotation)

        # Verify vector DB was called
        mock_vector_client.store_hitl_annotation.assert_called_once()
        call_args = mock_vector_client.store_hitl_annotation.call_args

        # Verify annotation_id format
        assert call_args[1]['annotation_id'].startswith('hitl_t_123_')

        # Verify task description
        assert call_args[1]['task_description'] == 'login authentication'

        # Verify annotation data
        assert call_args[1]['annotation'] == sample_annotation

    def test_resolve_nonexistent_task(self, hitl_queue, mock_redis_client, mock_vector_client, sample_annotation):
        """Test that resolving non-existent task returns False."""
        mock_redis_client.get.return_value = None

        result = hitl_queue.resolve('t_nonexistent', sample_annotation)

        assert result is False
        mock_vector_client.store_hitl_annotation.assert_not_called()

    def test_resolve_task_with_empty_feature(self, hitl_queue, mock_redis_client, mock_vector_client, sample_annotation):
        """Test resolve with task that has empty feature field."""
        existing_task = {
            'task_id': 't_123',
            'feature': '',
            'priority': 0.5
        }
        mock_redis_client.get.return_value = existing_task

        result = hitl_queue.resolve('t_123', sample_annotation)

        assert result is True
        # Should use empty string as task description
        call_args = mock_vector_client.store_hitl_annotation.call_args
        assert call_args[1]['task_description'] == ''

    def test_resolve_task_preserves_original_fields(self, hitl_queue, mock_redis_client, mock_vector_client, sample_annotation):
        """Test that resolve preserves original task fields."""
        existing_task = {
            'task_id': 't_123',
            'feature': 'login',
            'code_path': 'tests/auth/login.spec.ts',
            'attempts': 3,
            'priority': 0.5
        }
        mock_redis_client.get.return_value = existing_task

        hitl_queue.resolve('t_123', sample_annotation)

        updated_task = mock_redis_client.set.call_args[0][1]
        assert updated_task['task_id'] == 't_123'
        assert updated_task['feature'] == 'login'
        assert updated_task['code_path'] == 'tests/auth/login.spec.ts'
        assert updated_task['attempts'] == 3


# ============================================================================
# TEST: Queue Statistics
# ============================================================================

class TestQueueStats:
    """Test queue statistics."""

    def test_get_stats_empty_queue(self, hitl_queue, mock_redis_client):
        """Test stats for empty queue."""
        mock_redis_client.client.zrevrange.return_value = []

        stats = hitl_queue.get_stats()

        assert stats['total_count'] == 0
        assert stats['active_count'] == 0
        assert stats['resolved_count'] == 0
        assert stats['avg_priority'] == 0.0
        assert stats['high_priority_count'] == 0

    def test_get_stats_with_active_tasks(self, hitl_queue, mock_redis_client):
        """Test stats with active tasks."""
        mock_redis_client.client.zrevrange.return_value = [b't1', b't2', b't3']

        def mock_get(key):
            if key == 'hitl:task:t1':
                return {'task_id': 't1', 'priority': 0.8, 'resolved': False}
            elif key == 'hitl:task:t2':
                return {'task_id': 't2', 'priority': 0.5, 'resolved': False}
            elif key == 'hitl:task:t3':
                return {'task_id': 't3', 'priority': 0.3, 'resolved': False}
            return None

        mock_redis_client.get.side_effect = mock_get

        stats = hitl_queue.get_stats()

        assert stats['total_count'] == 3
        assert stats['active_count'] == 3
        assert stats['resolved_count'] == 0
        assert stats['avg_priority'] == pytest.approx((0.8 + 0.5 + 0.3) / 3)
        assert stats['high_priority_count'] == 1  # Only t1 is > 0.7

    def test_get_stats_with_resolved_tasks(self, hitl_queue, mock_redis_client):
        """Test stats with mix of active and resolved tasks."""
        mock_redis_client.client.zrevrange.return_value = [b't1', b't2', b't3']

        def mock_get(key):
            if key == 'hitl:task:t1':
                return {'task_id': 't1', 'priority': 0.8, 'resolved': False}
            elif key == 'hitl:task:t2':
                return {'task_id': 't2', 'priority': 0.5, 'resolved': True}
            elif key == 'hitl:task:t3':
                return {'task_id': 't3', 'priority': 0.9, 'resolved': True}
            return None

        mock_redis_client.get.side_effect = mock_get

        stats = hitl_queue.get_stats()

        assert stats['total_count'] == 3
        assert stats['active_count'] == 1
        assert stats['resolved_count'] == 2
        assert stats['avg_priority'] == 0.8  # Only active task
        assert stats['high_priority_count'] == 1

    def test_get_stats_high_priority_threshold(self, hitl_queue, mock_redis_client):
        """Test high priority count uses 0.7 threshold."""
        mock_redis_client.client.zrevrange.return_value = [b't1', b't2', b't3', b't4']

        def mock_get(key):
            priorities = {
                'hitl:task:t1': 0.9,
                'hitl:task:t2': 0.71,
                'hitl:task:t3': 0.7,
                'hitl:task:t4': 0.69
            }
            task_id = key.split(':')[-1]
            return {'task_id': task_id, 'priority': priorities.get(key, 0.5), 'resolved': False}

        mock_redis_client.get.side_effect = mock_get

        stats = hitl_queue.get_stats()

        # Only t1 (0.9) and t2 (0.71) are > 0.7
        assert stats['high_priority_count'] == 2


# ============================================================================
# TEST: Schema Validation
# ============================================================================

class TestSchemaValidation:
    """Test that tasks conform to schema.json."""

    def test_task_has_required_fields(self, hitl_queue, mock_redis_client, sample_task):
        """Test that added tasks have all required schema fields."""
        hitl_queue.add(sample_task)

        stored_task = mock_redis_client.set.call_args[0][1]

        # Required fields from schema.json
        required_fields = [
            'task_id', 'feature', 'code_path', 'logs_path',
            'screenshots', 'attempts', 'last_error', 'priority', 'created_at'
        ]

        for field in required_fields:
            assert field in stored_task, f"Required field '{field}' missing"

    def test_priority_in_valid_range(self, hitl_queue, mock_redis_client, sample_task):
        """Test that priority is in range [0, 1] as per schema."""
        hitl_queue.add(sample_task)

        stored_task = mock_redis_client.set.call_args[0][1]
        priority = stored_task['priority']

        assert 0.0 <= priority <= 1.0

    def test_attempts_is_positive_integer(self, hitl_queue, mock_redis_client, sample_task):
        """Test that attempts is a positive integer."""
        hitl_queue.add(sample_task)

        stored_task = mock_redis_client.set.call_args[0][1]
        attempts = stored_task['attempts']

        assert isinstance(attempts, int)
        assert attempts >= 1

    def test_screenshots_is_array(self, hitl_queue, mock_redis_client, sample_task):
        """Test that screenshots is an array."""
        hitl_queue.add(sample_task)

        stored_task = mock_redis_client.set.call_args[0][1]
        screenshots = stored_task['screenshots']

        assert isinstance(screenshots, list)

    def test_annotation_fields_valid_enums(self, hitl_queue, mock_redis_client, mock_vector_client):
        """Test that annotation fields use valid enum values from schema."""
        existing_task = {
            'task_id': 't_123',
            'feature': 'test',
            'priority': 0.5
        }
        mock_redis_client.get.return_value = existing_task

        # Valid enum values from schema.json
        annotation = {
            'root_cause_category': 'timing_race_condition',
            'fix_strategy': 'add_explicit_waits',
            'severity': 'high'
        }

        result = hitl_queue.resolve('t_123', annotation)

        assert result is True
        updated_task = mock_redis_client.set.call_args[0][1]
        assert updated_task['root_cause_category'] == 'timing_race_condition'
        assert updated_task['fix_strategy'] == 'add_explicit_waits'
        assert updated_task['severity'] == 'high'


# ============================================================================
# TEST: Queue Isolation
# ============================================================================

class TestQueueIsolation:
    """Test that queue operations don't affect other tasks."""

    def test_resolve_doesnt_affect_other_tasks(self, hitl_queue, mock_redis_client, mock_vector_client, sample_annotation):
        """Test that resolving one task doesn't affect others."""
        existing_task = {
            'task_id': 't_123',
            'feature': 'test',
            'priority': 0.5
        }
        mock_redis_client.get.return_value = existing_task

        hitl_queue.resolve('t_123', sample_annotation)

        # Only t_123 should be removed from queue
        mock_redis_client.client.zrem.assert_called_once_with('hitl:queue', 't_123')

    def test_add_task_generates_unique_keys(self, hitl_queue, mock_redis_client):
        """Test that each task gets unique Redis key."""
        task1 = {
            'task_id': 't_1',
            'feature': 'test1',
            'code_path': 'test1.spec.ts',
            'logs_path': 'logs1.log',
            'screenshots': [],
            'attempts': 1,
            'last_error': 'error1',
            'priority': 0.5,
            'created_at': datetime.utcnow().isoformat()
        }
        task2 = {
            'task_id': 't_2',
            'feature': 'test2',
            'code_path': 'test2.spec.ts',
            'logs_path': 'logs2.log',
            'screenshots': [],
            'attempts': 1,
            'last_error': 'error2',
            'priority': 0.5,
            'created_at': datetime.utcnow().isoformat()
        }

        hitl_queue.add(task1)
        hitl_queue.add(task2)

        # Verify different keys were used
        calls = mock_redis_client.set.call_args_list
        key1 = calls[0][0][0]
        key2 = calls[1][0][0]

        assert key1 == 'hitl:task:t_1'
        assert key2 == 'hitl:task:t_2'
        assert key1 != key2


# ============================================================================
# TEST: Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_add_task_with_minimal_fields(self, hitl_queue, mock_redis_client):
        """Test adding task with only required fields."""
        minimal_task = {
            'task_id': 't_minimal',
            'feature': 'test',
            'code_path': 'test.spec.ts',
            'logs_path': 'test.log',
            'screenshots': [],
            'attempts': 1,
            'last_error': 'error'
        }

        result = hitl_queue.add(minimal_task)

        assert result is True

    def test_priority_with_zero_attempts(self, hitl_queue):
        """Test priority calculation with zero attempts."""
        task = {
            'task_id': 't_zero',
            'feature': 'test',
            'attempts': 0,
            'created_at': datetime.utcnow().isoformat()
        }

        priority = hitl_queue._calculate_priority(task)

        # Should handle gracefully
        assert 0.0 <= priority <= 1.0

    def test_priority_with_negative_attempts(self, hitl_queue):
        """Test priority calculation with negative attempts (edge case)."""
        task = {
            'task_id': 't_neg',
            'feature': 'test',
            'attempts': -1,
            'created_at': datetime.utcnow().isoformat()
        }

        priority = hitl_queue._calculate_priority(task)

        # Should handle gracefully, likely treating as 0 or 1
        assert 0.0 <= priority <= 1.0

    def test_list_with_zero_limit(self, hitl_queue, mock_redis_client):
        """Test listing queue with limit=0."""
        mock_redis_client.client.zrevrange.return_value = []

        tasks = hitl_queue.list(limit=0)

        # Should handle gracefully (likely return empty list)
        assert isinstance(tasks, list)

    def test_resolve_with_empty_annotation(self, hitl_queue, mock_redis_client, mock_vector_client):
        """Test resolve with empty annotation dict."""
        existing_task = {
            'task_id': 't_123',
            'feature': 'test',
            'priority': 0.5
        }
        mock_redis_client.get.return_value = existing_task

        result = hitl_queue.resolve('t_123', {})

        assert result is True

    def test_priority_with_future_timestamp(self, hitl_queue):
        """Test priority calculation with future timestamp (clock skew)."""
        future_time = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        task = {
            'task_id': 't_future',
            'feature': 'test',
            'attempts': 1,
            'created_at': future_time
        }

        priority = hitl_queue._calculate_priority(task)

        # Should handle gracefully (time factor should be 0 or minimal)
        assert 0.0 <= priority <= 1.0


# ============================================================================
# TEST: Integration Scenarios
# ============================================================================

@pytest.mark.unit
class TestIntegrationScenarios:
    """Test realistic workflow scenarios."""

    def test_typical_hitl_workflow(self, hitl_queue, mock_redis_client, mock_vector_client, sample_task, sample_annotation):
        """Test typical HITL workflow: add -> list -> resolve."""
        # Step 1: Add task to queue
        mock_redis_client.client.zadd.reset_mock()
        result = hitl_queue.add(sample_task)
        assert result is True

        # Step 2: List tasks
        mock_redis_client.client.zrevrange.return_value = [b't_123']
        mock_redis_client.get.return_value = sample_task
        tasks = hitl_queue.list()
        assert len(tasks) == 1

        # Step 3: Get specific task
        mock_redis_client.get.return_value = sample_task
        task = hitl_queue.get('t_123')
        assert task['task_id'] == 't_123'

        # Step 4: Resolve task
        result = hitl_queue.resolve('t_123', sample_annotation)
        assert result is True

        # Step 5: Verify removal from active queue
        mock_redis_client.client.zrem.assert_called_with('hitl:queue', 't_123')

    def test_multiple_tasks_priority_ordering(self, hitl_queue, mock_redis_client):
        """Test adding multiple tasks results in correct priority ordering."""
        tasks = [
            {
                'task_id': 't_low',
                'feature': 'simple test',
                'code_path': 'test.spec.ts',
                'logs_path': 'test.log',
                'screenshots': [],
                'attempts': 1,
                'last_error': 'error',
                'created_at': datetime.utcnow().isoformat()
            },
            {
                'task_id': 't_high',
                'feature': 'payment checkout',
                'code_path': 'payment.spec.ts',
                'logs_path': 'payment.log',
                'screenshots': [],
                'attempts': 10,
                'last_error': 'error',
                'created_at': (datetime.utcnow() - timedelta(hours=20)).isoformat()
            },
            {
                'task_id': 't_med',
                'feature': 'auth login',
                'code_path': 'auth.spec.ts',
                'logs_path': 'auth.log',
                'screenshots': [],
                'attempts': 3,
                'last_error': 'error',
                'created_at': (datetime.utcnow() - timedelta(hours=5)).isoformat()
            }
        ]

        # Add all tasks
        for task in tasks:
            hitl_queue.add(task)

        # Verify zadd was called with different priorities
        zadd_calls = mock_redis_client.client.zadd.call_args_list
        assert len(zadd_calls) == 3

        # Extract priorities from zadd calls
        priorities = []
        for call in zadd_calls:
            priority_dict = call[0][1]
            priority = list(priority_dict.values())[0]
            priorities.append(priority)

        # High priority task should have highest score
        assert priorities[1] > priorities[2] > priorities[0]
