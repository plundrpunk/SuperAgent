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
    - voice:{session_id}:transcripts -> legacy voice transcripts (plain text)
    - voice:session:{session_id}:transcripts -> voice transcripts with metadata (JSON)
    - voice:session:{session_id}:metadata -> session metadata (start_time, last_activity)
    - voice:session:{session_id}:context -> sliding window of recent messages (max 20)
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
        self._connected = None  # Lazy connection check

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

    def store_transcript(
        self,
        session_id: str,
        transcript: str,
        metadata: Optional[Dict[str, Any]] = None,
        ttl: int = DEFAULT_TTL
    ) -> bool:
        """
        Store voice transcript with metadata for session.

        This method stores both the transcript and its metadata, enabling
        rich context retrieval for multi-turn conversations.

        Args:
            session_id: Unique session identifier
            transcript: Transcribed text
            metadata: Optional metadata dict containing:
                - timestamp: ISO format timestamp
                - speaker: 'user' or 'agent'
                - intent_type: parsed intent (create_test, run_test, etc.)
                - confidence_score: float 0-1
                - audio_duration_ms: duration in milliseconds
            ttl: Time to live in seconds (default 1h)

        Returns:
            True if successful, False otherwise
        """
        # Construct transcript entry with metadata
        entry = {
            'text': transcript,
            'timestamp': metadata.get('timestamp', time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())) if metadata else time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'speaker': metadata.get('speaker', 'user') if metadata else 'user',
        }

        # Add optional metadata fields if present
        if metadata:
            if 'intent_type' in metadata:
                entry['intent_type'] = metadata['intent_type']
            if 'confidence_score' in metadata:
                entry['confidence_score'] = metadata['confidence_score']
            if 'audio_duration_ms' in metadata:
                entry['audio_duration_ms'] = metadata['audio_duration_ms']

        # Store transcript entry
        transcripts_key = f"voice:session:{session_id}:transcripts"
        entry_json = json.dumps(entry)
        success = self.client.rpush(transcripts_key, entry_json) > 0

        if success:
            # Set TTL on transcripts list
            self.client.expire(transcripts_key, ttl)

            # Update session metadata
            self._update_session_metadata(session_id, ttl)

            # Update context window (last N messages for quick access)
            self._update_context_window(session_id, entry_json, ttl)

        return success

    def get_session_transcripts(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve all transcripts with metadata for a session.

        Args:
            session_id: Unique session identifier

        Returns:
            List of transcript dicts with metadata, ordered chronologically
        """
        key = f"voice:session:{session_id}:transcripts"
        raw_entries = self.client.lrange(key, 0, -1)

        transcripts = []
        for entry_json in raw_entries:
            try:
                entry = json.loads(entry_json)
                transcripts.append(entry)
            except json.JSONDecodeError:
                # Handle legacy plain text transcripts
                transcripts.append({
                    'text': entry_json,
                    'timestamp': None,
                    'speaker': 'unknown'
                })

        return transcripts

    def get_recent_context(
        self,
        session_id: str,
        num_messages: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get recent conversation context for a session.

        Retrieves the last N transcript entries efficiently from the context window.
        This is optimized for providing context to agents without retrieving
        the full conversation history.

        Args:
            session_id: Unique session identifier
            num_messages: Number of recent messages to retrieve (default 5)

        Returns:
            List of recent transcript dicts, ordered chronologically (oldest to newest)
        """
        context_key = f"voice:session:{session_id}:context"

        # Get last N entries from context window
        # Redis LRANGE with negative indices: -num_messages to -1 gets last N items
        raw_entries = self.client.lrange(context_key, -num_messages, -1)

        context = []
        for entry_json in raw_entries:
            try:
                entry = json.loads(entry_json)
                context.append(entry)
            except json.JSONDecodeError:
                # Handle malformed entries
                continue

        return context

    def delete_voice_session(self, session_id: str) -> bool:
        """
        Delete all voice session data (transcripts, metadata, context).

        Args:
            session_id: Unique session identifier

        Returns:
            True if at least one key was deleted
        """
        keys_to_delete = [
            f"voice:session:{session_id}:transcripts",
            f"voice:session:{session_id}:metadata",
            f"voice:session:{session_id}:context"
        ]

        deleted_count = 0
        for key in keys_to_delete:
            if self.client.delete(key) > 0:
                deleted_count += 1

        return deleted_count > 0

    def _update_session_metadata(self, session_id: str, ttl: int) -> bool:
        """
        Update session metadata (internal helper).

        Tracks session start time and last activity for session management.

        Args:
            session_id: Unique session identifier
            ttl: Time to live in seconds

        Returns:
            True if successful
        """
        metadata_key = f"voice:session:{session_id}:metadata"

        # Check if metadata exists (existing session)
        existing = self.client.get(metadata_key)

        if existing:
            # Update last_activity timestamp
            try:
                metadata = json.loads(existing)
                metadata['last_activity'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            except json.JSONDecodeError:
                # Recreate metadata if corrupted
                metadata = {
                    'start_time': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                    'last_activity': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                }
        else:
            # Create new metadata for new session
            metadata = {
                'start_time': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                'last_activity': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            }

        return self.client.setex(metadata_key, ttl, json.dumps(metadata))

    def _update_context_window(self, session_id: str, entry_json: str, ttl: int) -> bool:
        """
        Update context window with new entry (internal helper).

        Maintains a sliding window of recent messages (max 20) for efficient context retrieval.

        Args:
            session_id: Unique session identifier
            entry_json: JSON-encoded transcript entry
            ttl: Time to live in seconds

        Returns:
            True if successful
        """
        context_key = f"voice:session:{session_id}:context"

        # Add entry to context window
        self.client.rpush(context_key, entry_json)

        # Trim to max 20 entries (keep most recent)
        self.client.ltrim(context_key, -20, -1)

        # Set TTL
        return self.client.expire(context_key, ttl)

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
        try:
            if not isinstance(value, str):
                value = json.dumps(value)

            if ttl:
                return self.client.setex(key, ttl, value)
            else:
                return self.client.set(key, value)
        except (redis.ConnectionError, redis.TimeoutError):
            # Redis not available, fail silently (degraded mode)
            return False

    def get(self, key: str) -> Optional[Any]:
        """
        Get value by key.

        Args:
            key: Redis key

        Returns:
            Value (JSON decoded if possible) or None
        """
        try:
            value = self.client.get(key)
            if value:
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value
            return None
        except (redis.ConnectionError, redis.TimeoutError):
            # Redis not available, return None (degraded mode)
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
