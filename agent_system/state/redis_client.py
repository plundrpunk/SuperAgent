"""
Redis Client for SuperAgent Hot State Management
Manages session state, task queue, and voice transcripts with 1h TTL.
"""
import redis
import json
import os
import time
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict


@dataclass
class RedisConfig:
    """Redis connection configuration."""
    host: str = os.getenv('REDIS_HOST', 'localhost')
    port: int = int(os.getenv('REDIS_PORT', '6379'))
    password: Optional[str] = os.getenv('REDIS_PASSWORD')
    db: int = int(os.getenv('REDIS_DB', '0'))
    max_connections: int = 10
    socket_timeout: int = 5
    socket_connect_timeout: int = 5
    retry_on_timeout: bool = True


class RedisClient:
    """
    Redis client with connection pooling and retry logic.

    Key structure:
    - session:{session_id} -> session data (1h TTL)
    - task_queue -> list of task_ids
    - task:{task_id}:status -> task status
    - voice:{session_id}:transcripts -> voice transcripts
    """

    # Default TTL for hot state (1 hour)
    DEFAULT_TTL = 3600

    def __init__(self, config: Optional[RedisConfig] = None):
        """
        Initialize Redis client with connection pool.

        Args:
            config: Redis configuration (uses defaults if not provided)
        """
        self.config = config or RedisConfig()
        self.pool = redis.ConnectionPool(
            host=self.config.host,
            port=self.config.port,
            password=self.config.password,
            db=self.config.db,
            max_connections=self.config.max_connections,
            socket_timeout=self.config.socket_timeout,
            socket_connect_timeout=self.config.socket_connect_timeout,
            retry_on_timeout=self.config.retry_on_timeout,
            decode_responses=True
        )
        self.client = redis.Redis(connection_pool=self.pool)

    def health_check(self) -> bool:
        """
        Check if Redis connection is healthy.

        Returns:
            True if ping succeeds, False otherwise
        """
        try:
            return self.client.ping()
        except redis.ConnectionError:
            return False

    # Session State Operations

    def set_session(self, session_id: str, data: Dict[str, Any], ttl: int = DEFAULT_TTL) -> bool:
        """
        Store session data with TTL.

        Args:
            session_id: Unique session identifier
            data: Session data dict
            ttl: Time to live in seconds (default 1h)

        Returns:
            True if successful
        """
        key = f"session:{session_id}"
        value = json.dumps(data)
        return self.client.setex(key, ttl, value)

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve session data.

        Args:
            session_id: Unique session identifier

        Returns:
            Session data dict or None if not found
        """
        key = f"session:{session_id}"
        value = self.client.get(key)
        if value:
            return json.loads(value)
        return None

    def delete_session(self, session_id: str) -> bool:
        """
        Delete session data.

        Args:
            session_id: Unique session identifier

        Returns:
            True if deleted
        """
        key = f"session:{session_id}"
        return self.client.delete(key) > 0

    # Task Queue Operations

    def push_task(self, task_id: str) -> bool:
        """
        Add task to queue.

        Args:
            task_id: Unique task identifier

        Returns:
            True if successful
        """
        return self.client.rpush("task_queue", task_id) > 0

    def pop_task(self, timeout: int = 0) -> Optional[str]:
        """
        Remove and return task from queue.

        Args:
            timeout: Block for N seconds if queue empty (0 = no blocking)

        Returns:
            Task ID or None if queue empty
        """
        if timeout > 0:
            result = self.client.blpop("task_queue", timeout)
            return result[1] if result else None
        else:
            return self.client.lpop("task_queue")

    def list_tasks(self) -> List[str]:
        """
        List all tasks in queue without removing.

        Returns:
            List of task IDs
        """
        return self.client.lrange("task_queue", 0, -1)

    def queue_length(self) -> int:
        """
        Get number of tasks in queue.

        Returns:
            Queue length
        """
        return self.client.llen("task_queue")

    # Task Status Operations

    def set_task_status(self, task_id: str, status: str, ttl: int = DEFAULT_TTL) -> bool:
        """
        Set task status.

        Args:
            task_id: Unique task identifier
            status: Status string (pending/doing/done/failed)
            ttl: Time to live in seconds

        Returns:
            True if successful
        """
        key = f"task:{task_id}:status"
        return self.client.setex(key, ttl, status)

    def get_task_status(self, task_id: str) -> Optional[str]:
        """
        Get task status.

        Args:
            task_id: Unique task identifier

        Returns:
            Status string or None if not found
        """
        key = f"task:{task_id}:status"
        return self.client.get(key)

    # Voice Transcripts Operations

    def add_transcript(self, session_id: str, transcript: str, ttl: int = DEFAULT_TTL) -> bool:
        """
        Add voice transcript to session.

        Args:
            session_id: Unique session identifier
            transcript: Transcribed text
            ttl: Time to live in seconds

        Returns:
            True if successful
        """
        key = f"voice:{session_id}:transcripts"
        success = self.client.rpush(key, transcript) > 0
        if success:
            self.client.expire(key, ttl)
        return success

    def get_transcripts(self, session_id: str) -> List[str]:
        """
        Get all voice transcripts for session.

        Args:
            session_id: Unique session identifier

        Returns:
            List of transcript strings
        """
        key = f"voice:{session_id}:transcripts"
        return self.client.lrange(key, 0, -1)

    # Generic Operations

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set arbitrary key-value pair.

        Args:
            key: Redis key
            value: Value to store (will be JSON encoded if not string)
            ttl: Optional time to live in seconds

        Returns:
            True if successful
        """
        if not isinstance(value, str):
            value = json.dumps(value)

        if ttl:
            return self.client.setex(key, ttl, value)
        else:
            return self.client.set(key, value)

    def get(self, key: str) -> Optional[Any]:
        """
        Get value by key.

        Args:
            key: Redis key

        Returns:
            Value (JSON decoded if possible) or None
        """
        value = self.client.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return None

    def delete(self, key: str) -> bool:
        """
        Delete key.

        Args:
            key: Redis key

        Returns:
            True if deleted
        """
        return self.client.delete(key) > 0

    def keys(self, pattern: str = "*") -> List[str]:
        """
        List keys matching pattern.

        Args:
            pattern: Redis key pattern (default: all keys)

        Returns:
            List of matching keys
        """
        return self.client.keys(pattern)

    def close(self):
        """Close Redis connection pool."""
        self.client.close()
        self.pool.disconnect()
