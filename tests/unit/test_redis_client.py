"""
Comprehensive unit tests for RedisClient.

Tests all CRUD operations, TTL enforcement, connection health,
queue operations, and error handling with mocked Redis.
"""
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

from agent_system.state.redis_client import RedisClient, RedisConfig


@pytest.fixture
def mock_redis():
    """Mock Redis client with connection pool."""
    with patch('agent_system.state.redis_client.redis.ConnectionPool') as mock_pool, \
         patch('agent_system.state.redis_client.redis.Redis') as mock_redis_class:

        mock_client = MagicMock()
        mock_redis_class.return_value = mock_client

        yield mock_client


@pytest.fixture
def redis_client(mock_redis):
    """RedisClient instance with mocked Redis."""
    config = RedisConfig(
        host='localhost',
        port=6379,
        password=None,
        db=0,
        max_connections=10
    )
    return RedisClient(config)


class TestRedisConfig:
    """Test RedisConfig dataclass initialization."""

    def test_default_config(self):
        """Test default configuration values."""
        config = RedisConfig()
        assert config.host == 'localhost'
        assert config.port == 6379
        assert config.password is None
        assert config.db == 0
        assert config.max_connections == 10
        assert config.socket_timeout == 5
        assert config.socket_connect_timeout == 5
        assert config.retry_on_timeout is True

    def test_custom_config(self):
        """Test custom configuration values."""
        config = RedisConfig(
            host='redis.example.com',
            port=6380,
            password='secret',
            db=2,
            max_connections=20
        )
        assert config.host == 'redis.example.com'
        assert config.port == 6380
        assert config.password == 'secret'
        assert config.db == 2
        assert config.max_connections == 20


class TestRedisClientInitialization:
    """Test RedisClient initialization and setup."""

    def test_init_with_default_config(self, mock_redis):
        """Test initialization with default config."""
        client = RedisClient()
        assert client.config is not None
        assert client.pool is not None
        assert client.client is not None

    def test_init_with_custom_config(self, mock_redis):
        """Test initialization with custom config."""
        config = RedisConfig(host='custom-redis', port=6380)
        client = RedisClient(config)
        assert client.config.host == 'custom-redis'
        assert client.config.port == 6380


class TestHealthCheck:
    """Test Redis connection health checks."""

    def test_health_check_success(self, redis_client, mock_redis):
        """Test successful health check."""
        mock_redis.ping.return_value = True
        assert redis_client.health_check() is True
        mock_redis.ping.assert_called_once()

    def test_health_check_connection_error(self, redis_client, mock_redis):
        """Test health check with connection error."""
        import redis
        mock_redis.ping.side_effect = redis.ConnectionError("Connection failed")
        assert redis_client.health_check() is False


class TestSessionOperations:
    """Test session state CRUD operations."""

    def test_set_session_success(self, redis_client, mock_redis):
        """Test setting session data with default TTL."""
        session_data = {"user_id": "123", "name": "Test User"}
        mock_redis.setex.return_value = True

        result = redis_client.set_session("session_1", session_data)

        assert result is True
        mock_redis.setex.assert_called_once_with(
            "session:session_1",
            3600,  # DEFAULT_TTL
            json.dumps(session_data)
        )

    def test_set_session_custom_ttl(self, redis_client, mock_redis):
        """Test setting session data with custom TTL."""
        session_data = {"user_id": "456"}
        mock_redis.setex.return_value = True

        result = redis_client.set_session("session_2", session_data, ttl=7200)

        assert result is True
        mock_redis.setex.assert_called_once_with(
            "session:session_2",
            7200,
            json.dumps(session_data)
        )

    def test_get_session_exists(self, redis_client, mock_redis):
        """Test retrieving existing session data."""
        session_data = {"user_id": "789", "role": "admin"}
        mock_redis.get.return_value = json.dumps(session_data)

        result = redis_client.get_session("session_3")

        assert result == session_data
        mock_redis.get.assert_called_once_with("session:session_3")

    def test_get_session_not_found(self, redis_client, mock_redis):
        """Test retrieving non-existent session."""
        mock_redis.get.return_value = None

        result = redis_client.get_session("session_missing")

        assert result is None
        mock_redis.get.assert_called_once_with("session:session_missing")

    def test_get_session_expired(self, redis_client, mock_redis):
        """Test retrieving expired session (returns None)."""
        mock_redis.get.return_value = None

        result = redis_client.get_session("session_expired")

        assert result is None

    def test_delete_session_success(self, redis_client, mock_redis):
        """Test deleting existing session."""
        mock_redis.delete.return_value = 1

        result = redis_client.delete_session("session_delete")

        assert result is True
        mock_redis.delete.assert_called_once_with("session:session_delete")

    def test_delete_session_not_found(self, redis_client, mock_redis):
        """Test deleting non-existent session."""
        mock_redis.delete.return_value = 0

        result = redis_client.delete_session("session_missing")

        assert result is False


class TestTaskQueueOperations:
    """Test task queue push/pop/list operations."""

    def test_push_task_success(self, redis_client, mock_redis):
        """Test pushing task to queue."""
        mock_redis.rpush.return_value = 1

        result = redis_client.push_task("task_001")

        assert result is True
        mock_redis.rpush.assert_called_once_with("task_queue", "task_001")

    def test_push_task_failure(self, redis_client, mock_redis):
        """Test push task failure (returns 0)."""
        mock_redis.rpush.return_value = 0

        result = redis_client.push_task("task_002")

        assert result is False

    def test_pop_task_non_blocking_success(self, redis_client, mock_redis):
        """Test non-blocking pop from non-empty queue."""
        mock_redis.lpop.return_value = "task_003"

        result = redis_client.pop_task(timeout=0)

        assert result == "task_003"
        mock_redis.lpop.assert_called_once_with("task_queue")

    def test_pop_task_non_blocking_empty(self, redis_client, mock_redis):
        """Test non-blocking pop from empty queue."""
        mock_redis.lpop.return_value = None

        result = redis_client.pop_task(timeout=0)

        assert result is None

    def test_pop_task_blocking_success(self, redis_client, mock_redis):
        """Test blocking pop with timeout (task available)."""
        mock_redis.blpop.return_value = ("task_queue", "task_004")

        result = redis_client.pop_task(timeout=5)

        assert result == "task_004"
        mock_redis.blpop.assert_called_once_with("task_queue", 5)

    def test_pop_task_blocking_timeout(self, redis_client, mock_redis):
        """Test blocking pop timeout (no task available)."""
        mock_redis.blpop.return_value = None

        result = redis_client.pop_task(timeout=3)

        assert result is None

    def test_list_tasks_multiple(self, redis_client, mock_redis):
        """Test listing multiple tasks in queue."""
        tasks = ["task_005", "task_006", "task_007"]
        mock_redis.lrange.return_value = tasks

        result = redis_client.list_tasks()

        assert result == tasks
        mock_redis.lrange.assert_called_once_with("task_queue", 0, -1)

    def test_list_tasks_empty(self, redis_client, mock_redis):
        """Test listing tasks from empty queue."""
        mock_redis.lrange.return_value = []

        result = redis_client.list_tasks()

        assert result == []

    def test_queue_length_multiple(self, redis_client, mock_redis):
        """Test queue length with multiple tasks."""
        mock_redis.llen.return_value = 5

        result = redis_client.queue_length()

        assert result == 5
        mock_redis.llen.assert_called_once_with("task_queue")

    def test_queue_length_empty(self, redis_client, mock_redis):
        """Test queue length when empty."""
        mock_redis.llen.return_value = 0

        result = redis_client.queue_length()

        assert result == 0


class TestTaskStatusOperations:
    """Test task status get/set operations."""

    def test_set_task_status_default_ttl(self, redis_client, mock_redis):
        """Test setting task status with default TTL."""
        mock_redis.setex.return_value = True

        result = redis_client.set_task_status("task_101", "pending")

        assert result is True
        mock_redis.setex.assert_called_once_with(
            "task:task_101:status",
            3600,
            "pending"
        )

    def test_set_task_status_custom_ttl(self, redis_client, mock_redis):
        """Test setting task status with custom TTL."""
        mock_redis.setex.return_value = True

        result = redis_client.set_task_status("task_102", "doing", ttl=1800)

        assert result is True
        mock_redis.setex.assert_called_once_with(
            "task:task_102:status",
            1800,
            "doing"
        )

    def test_set_task_status_all_statuses(self, redis_client, mock_redis):
        """Test setting all valid task statuses."""
        mock_redis.setex.return_value = True
        statuses = ["pending", "doing", "done", "failed"]

        for status in statuses:
            result = redis_client.set_task_status(f"task_{status}", status)
            assert result is True

    def test_get_task_status_exists(self, redis_client, mock_redis):
        """Test getting existing task status."""
        mock_redis.get.return_value = "done"

        result = redis_client.get_task_status("task_103")

        assert result == "done"
        mock_redis.get.assert_called_once_with("task:task_103:status")

    def test_get_task_status_not_found(self, redis_client, mock_redis):
        """Test getting non-existent task status."""
        mock_redis.get.return_value = None

        result = redis_client.get_task_status("task_missing")

        assert result is None


class TestVoiceTranscriptOperations:
    """Test voice transcript operations."""

    def test_add_transcript_success(self, redis_client, mock_redis):
        """Test adding transcript to session."""
        mock_redis.rpush.return_value = 1
        mock_redis.expire.return_value = True

        result = redis_client.add_transcript("session_voice1", "Hello world")

        assert result is True
        mock_redis.rpush.assert_called_once_with(
            "voice:session_voice1:transcripts",
            "Hello world"
        )
        mock_redis.expire.assert_called_once_with(
            "voice:session_voice1:transcripts",
            3600
        )

    def test_add_transcript_custom_ttl(self, redis_client, mock_redis):
        """Test adding transcript with custom TTL."""
        mock_redis.rpush.return_value = 1
        mock_redis.expire.return_value = True

        result = redis_client.add_transcript("session_voice2", "Test message", ttl=7200)

        assert result is True
        mock_redis.expire.assert_called_once_with(
            "voice:session_voice2:transcripts",
            7200
        )

    def test_add_transcript_failure(self, redis_client, mock_redis):
        """Test adding transcript failure."""
        mock_redis.rpush.return_value = 0

        result = redis_client.add_transcript("session_voice3", "Fail message")

        assert result is False
        mock_redis.expire.assert_not_called()

    def test_get_transcripts_multiple(self, redis_client, mock_redis):
        """Test getting multiple transcripts."""
        transcripts = [
            "Kaya, write a test for login",
            "Kaya, run the test",
            "Kaya, fix the failure"
        ]
        mock_redis.lrange.return_value = transcripts

        result = redis_client.get_transcripts("session_voice4")

        assert result == transcripts
        mock_redis.lrange.assert_called_once_with(
            "voice:session_voice4:transcripts",
            0,
            -1
        )

    def test_get_transcripts_empty(self, redis_client, mock_redis):
        """Test getting transcripts from session with none."""
        mock_redis.lrange.return_value = []

        result = redis_client.get_transcripts("session_voice_empty")

        assert result == []


class TestGenericOperations:
    """Test generic get/set/delete/keys operations."""

    def test_set_string_value_no_ttl(self, redis_client, mock_redis):
        """Test setting string value without TTL."""
        mock_redis.set.return_value = True

        result = redis_client.set("test_key", "test_value")

        assert result is True
        mock_redis.set.assert_called_once_with("test_key", "test_value")

    def test_set_string_value_with_ttl(self, redis_client, mock_redis):
        """Test setting string value with TTL."""
        mock_redis.setex.return_value = True

        result = redis_client.set("test_key_ttl", "test_value", ttl=1800)

        assert result is True
        mock_redis.setex.assert_called_once_with("test_key_ttl", 1800, "test_value")

    def test_set_dict_value_no_ttl(self, redis_client, mock_redis):
        """Test setting dict value (auto JSON encoding)."""
        mock_redis.set.return_value = True
        data = {"key1": "value1", "key2": 123}

        result = redis_client.set("test_dict", data)

        assert result is True
        mock_redis.set.assert_called_once_with("test_dict", json.dumps(data))

    def test_set_dict_value_with_ttl(self, redis_client, mock_redis):
        """Test setting dict value with TTL."""
        mock_redis.setex.return_value = True
        data = {"nested": {"value": 42}}

        result = redis_client.set("test_dict_ttl", data, ttl=600)

        assert result is True
        mock_redis.setex.assert_called_once_with("test_dict_ttl", 600, json.dumps(data))

    def test_set_list_value(self, redis_client, mock_redis):
        """Test setting list value (auto JSON encoding)."""
        mock_redis.set.return_value = True
        data = [1, 2, 3, "four"]

        result = redis_client.set("test_list", data)

        assert result is True
        mock_redis.set.assert_called_once_with("test_list", json.dumps(data))

    def test_get_string_value(self, redis_client, mock_redis):
        """Test getting plain string value."""
        mock_redis.get.return_value = "plain_string"

        result = redis_client.get("test_key")

        assert result == "plain_string"
        mock_redis.get.assert_called_once_with("test_key")

    def test_get_json_value(self, redis_client, mock_redis):
        """Test getting JSON-encoded value (auto decoding)."""
        data = {"decoded": True, "value": 99}
        mock_redis.get.return_value = json.dumps(data)

        result = redis_client.get("test_json")

        assert result == data

    def test_get_list_value(self, redis_client, mock_redis):
        """Test getting JSON list value."""
        data = ["item1", "item2", "item3"]
        mock_redis.get.return_value = json.dumps(data)

        result = redis_client.get("test_list_get")

        assert result == data

    def test_get_not_found(self, redis_client, mock_redis):
        """Test getting non-existent key."""
        mock_redis.get.return_value = None

        result = redis_client.get("missing_key")

        assert result is None

    def test_delete_success(self, redis_client, mock_redis):
        """Test deleting existing key."""
        mock_redis.delete.return_value = 1

        result = redis_client.delete("delete_me")

        assert result is True
        mock_redis.delete.assert_called_once_with("delete_me")

    def test_delete_not_found(self, redis_client, mock_redis):
        """Test deleting non-existent key."""
        mock_redis.delete.return_value = 0

        result = redis_client.delete("already_gone")

        assert result is False

    def test_keys_all_pattern(self, redis_client, mock_redis):
        """Test listing all keys with default pattern."""
        all_keys = ["session:1", "task:2:status", "voice:3:transcripts"]
        mock_redis.keys.return_value = all_keys

        result = redis_client.keys()

        assert result == all_keys
        mock_redis.keys.assert_called_once_with("*")

    def test_keys_session_pattern(self, redis_client, mock_redis):
        """Test listing keys with session pattern."""
        session_keys = ["session:1", "session:2", "session:3"]
        mock_redis.keys.return_value = session_keys

        result = redis_client.keys("session:*")

        assert result == session_keys
        mock_redis.keys.assert_called_once_with("session:*")

    def test_keys_task_pattern(self, redis_client, mock_redis):
        """Test listing keys with task pattern."""
        task_keys = ["task:101:status", "task:102:status"]
        mock_redis.keys.return_value = task_keys

        result = redis_client.keys("task:*:status")

        assert result == task_keys

    def test_keys_empty_result(self, redis_client, mock_redis):
        """Test listing keys with no matches."""
        mock_redis.keys.return_value = []

        result = redis_client.keys("nonexistent:*")

        assert result == []


class TestConnectionManagement:
    """Test connection lifecycle operations."""

    def test_close_connection(self, redis_client, mock_redis):
        """Test closing Redis connection and pool."""
        mock_pool = redis_client.pool

        redis_client.close()

        mock_redis.close.assert_called_once()
        mock_pool.disconnect.assert_called_once()


class TestEdgeCases:
    """Test edge cases and error scenarios."""

    def test_set_session_empty_data(self, redis_client, mock_redis):
        """Test setting session with empty dict."""
        mock_redis.setex.return_value = True

        result = redis_client.set_session("session_empty", {})

        assert result is True
        mock_redis.setex.assert_called_once_with(
            "session:session_empty",
            3600,
            "{}"
        )

    def test_set_session_complex_nested_data(self, redis_client, mock_redis):
        """Test setting session with deeply nested data."""
        mock_redis.setex.return_value = True
        complex_data = {
            "user": {
                "id": 123,
                "profile": {
                    "name": "Test",
                    "settings": {
                        "theme": "dark",
                        "notifications": [1, 2, 3]
                    }
                }
            }
        }

        result = redis_client.set_session("session_complex", complex_data)

        assert result is True
        call_args = mock_redis.setex.call_args[0]
        assert call_args[0] == "session:session_complex"
        assert json.loads(call_args[2]) == complex_data

    def test_get_session_malformed_json(self, redis_client, mock_redis):
        """Test getting session with invalid JSON (should raise exception)."""
        mock_redis.get.return_value = "{invalid json"

        with pytest.raises(json.JSONDecodeError):
            redis_client.get_session("session_malformed")

    def test_push_multiple_tasks_sequential(self, redis_client, mock_redis):
        """Test pushing multiple tasks sequentially."""
        mock_redis.rpush.return_value = 1
        task_ids = ["task_a", "task_b", "task_c", "task_d"]

        for task_id in task_ids:
            result = redis_client.push_task(task_id)
            assert result is True

        assert mock_redis.rpush.call_count == 4

    def test_add_transcript_unicode(self, redis_client, mock_redis):
        """Test adding transcript with unicode characters."""
        mock_redis.rpush.return_value = 1
        mock_redis.expire.return_value = True

        unicode_text = "Kaya, test unicode: こんにちは 🚀 ñ ü"
        result = redis_client.add_transcript("session_unicode", unicode_text)

        assert result is True
        mock_redis.rpush.assert_called_once_with(
            "voice:session_unicode:transcripts",
            unicode_text
        )

    def test_set_zero_ttl(self, redis_client, mock_redis):
        """Test setting value with TTL of 0 (edge case - treated as no TTL)."""
        # When ttl is 0, the condition "if ttl:" evaluates to False, so set() is used
        mock_redis.set.return_value = True

        result = redis_client.set("test_zero_ttl", "value", ttl=0)

        # TTL of 0 is falsy, so regular set() is called without expiration
        assert result is True
        mock_redis.set.assert_called_once_with("test_zero_ttl", "value")

    def test_get_with_json_decode_error_fallback(self, redis_client, mock_redis):
        """Test get() fallback when JSON decode fails."""
        mock_redis.get.return_value = "not-json-just-plain-text"

        result = redis_client.get("plain_text_key")

        # Should return plain string when JSON decode fails
        assert result == "not-json-just-plain-text"

    def test_concurrent_session_operations(self, redis_client, mock_redis):
        """Test multiple session operations in sequence."""
        # Set session
        mock_redis.setex.return_value = True
        redis_client.set_session("session_concurrent", {"step": 1})

        # Get session
        mock_redis.get.return_value = json.dumps({"step": 1})
        result = redis_client.get_session("session_concurrent")
        assert result == {"step": 1}

        # Update session
        redis_client.set_session("session_concurrent", {"step": 2})

        # Delete session
        mock_redis.delete.return_value = 1
        deleted = redis_client.delete_session("session_concurrent")
        assert deleted is True


class TestTTLEnforcement:
    """Test TTL enforcement across all operations."""

    def test_default_ttl_constant(self):
        """Test DEFAULT_TTL constant value."""
        assert RedisClient.DEFAULT_TTL == 3600

    def test_session_uses_default_ttl(self, redis_client, mock_redis):
        """Test that session operations use DEFAULT_TTL by default."""
        mock_redis.setex.return_value = True

        redis_client.set_session("session_ttl", {"data": "test"})

        call_args = mock_redis.setex.call_args[0]
        assert call_args[1] == 3600  # DEFAULT_TTL

    def test_task_status_uses_default_ttl(self, redis_client, mock_redis):
        """Test that task status operations use DEFAULT_TTL by default."""
        mock_redis.setex.return_value = True

        redis_client.set_task_status("task_ttl", "pending")

        call_args = mock_redis.setex.call_args[0]
        assert call_args[1] == 3600  # DEFAULT_TTL

    def test_transcript_uses_default_ttl(self, redis_client, mock_redis):
        """Test that transcript operations use DEFAULT_TTL by default."""
        mock_redis.rpush.return_value = 1
        mock_redis.expire.return_value = True

        redis_client.add_transcript("session_ttl", "test message")

        call_args = mock_redis.expire.call_args[0]
        assert call_args[1] == 3600  # DEFAULT_TTL


class TestErrorHandling:
    """Test error handling for connection and operation failures."""

    def test_connection_error_on_health_check(self, redis_client, mock_redis):
        """Test connection error during health check."""
        import redis
        mock_redis.ping.side_effect = redis.ConnectionError("Cannot connect")

        result = redis_client.health_check()

        assert result is False

    def test_timeout_error_on_operation(self, redis_client, mock_redis):
        """Test timeout error during Redis operation."""
        import redis
        mock_redis.get.side_effect = redis.TimeoutError("Operation timed out")

        with pytest.raises(redis.TimeoutError):
            redis_client.get("timeout_key")

    def test_redis_error_on_set(self, redis_client, mock_redis):
        """Test Redis error during set operation."""
        import redis
        mock_redis.set.side_effect = redis.RedisError("Redis error")

        with pytest.raises(redis.RedisError):
            redis_client.set("error_key", "value")

    def test_json_decode_error_handling(self, redis_client, mock_redis):
        """Test JSON decode error is caught and handled."""
        mock_redis.get.return_value = "{invalid:json"

        # Should return the string as-is when JSON decode fails
        result = redis_client.get("bad_json_key")

        assert result == "{invalid:json"


# Mark all tests in this module as unit tests
pytestmark = pytest.mark.unit
