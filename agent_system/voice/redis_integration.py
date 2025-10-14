"""
Voice-Redis Integration Layer

Provides a clean interface between the Voice Orchestrator (TypeScript)
and Redis storage (Python) for transcript and session management.

This module handles:
- Transcript storage with rich metadata
- Session context retrieval for multi-turn conversations
- Session cleanup and lifecycle management
- Conversation history tracking
"""
import sys
import os
from typing import Dict, List, Optional, Any
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from state.redis_client import RedisClient, RedisConfig


class VoiceRedisIntegration:
    """
    Integration layer for voice transcript storage and retrieval.

    Provides high-level methods for storing and retrieving voice transcripts
    with session context management optimized for multi-turn conversations.
    """

    def __init__(self, redis_config: Optional[RedisConfig] = None):
        """
        Initialize voice-redis integration.

        Args:
            redis_config: Optional Redis configuration (uses defaults if not provided)
        """
        self.redis = RedisClient(redis_config)
        self.default_ttl = 3600  # 1 hour

    def store_user_transcript(
        self,
        session_id: str,
        transcript: str,
        intent_type: Optional[str] = None,
        confidence_score: Optional[float] = None,
        audio_duration_ms: Optional[int] = None
    ) -> bool:
        """
        Store user voice transcript with metadata.

        Args:
            session_id: Unique session identifier
            transcript: Transcribed user speech
            intent_type: Parsed intent (create_test, run_test, etc.)
            confidence_score: Transcription confidence (0-1)
            audio_duration_ms: Audio duration in milliseconds

        Returns:
            True if stored successfully
        """
        metadata = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'speaker': 'user',
        }

        if intent_type:
            metadata['intent_type'] = intent_type
        if confidence_score is not None:
            metadata['confidence_score'] = confidence_score
        if audio_duration_ms is not None:
            metadata['audio_duration_ms'] = audio_duration_ms

        return self.redis.store_transcript(
            session_id=session_id,
            transcript=transcript,
            metadata=metadata,
            ttl=self.default_ttl
        )

    def store_agent_response(
        self,
        session_id: str,
        response: str,
        audio_duration_ms: Optional[int] = None
    ) -> bool:
        """
        Store agent (Kaya) voice response with metadata.

        Args:
            session_id: Unique session identifier
            response: Agent response text
            audio_duration_ms: Audio duration in milliseconds

        Returns:
            True if stored successfully
        """
        metadata = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'speaker': 'agent',
        }

        if audio_duration_ms is not None:
            metadata['audio_duration_ms'] = audio_duration_ms

        return self.redis.store_transcript(
            session_id=session_id,
            transcript=response,
            metadata=metadata,
            ttl=self.default_ttl
        )

    def get_conversation_history(
        self,
        session_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get full conversation history for a session.

        Returns all transcripts with metadata in chronological order.
        Use this for debugging or full session review.

        Args:
            session_id: Unique session identifier

        Returns:
            List of transcript dicts with metadata
        """
        return self.redis.get_session_transcripts(session_id)

    def get_context_for_agent(
        self,
        session_id: str,
        num_messages: int = 5
    ) -> str:
        """
        Get formatted conversation context for agent processing.

        Retrieves recent context and formats it as a readable string
        for passing to Kaya or other agents.

        Args:
            session_id: Unique session identifier
            num_messages: Number of recent messages to include (default 5)

        Returns:
            Formatted context string
        """
        recent = self.redis.get_recent_context(session_id, num_messages)

        if not recent:
            return "No previous context available."

        # Format as conversation history
        lines = []
        for entry in recent:
            speaker = entry.get('speaker', 'unknown').upper()
            text = entry.get('text', '')
            timestamp = entry.get('timestamp', '')

            # Format: [TIMESTAMP] USER: text
            if timestamp:
                lines.append(f"[{timestamp}] {speaker}: {text}")
            else:
                lines.append(f"{speaker}: {text}")

        return "\n".join(lines)

    def get_recent_intents(
        self,
        session_id: str,
        num_intents: int = 3
    ) -> List[str]:
        """
        Get recent user intents from context.

        Useful for understanding conversation flow and detecting
        repeated or related commands.

        Args:
            session_id: Unique session identifier
            num_intents: Number of recent intents to retrieve

        Returns:
            List of intent types (e.g., ['create_test', 'run_test'])
        """
        recent = self.redis.get_recent_context(session_id, num_intents * 2)  # Get more to filter

        intents = []
        for entry in recent:
            if entry.get('speaker') == 'user' and 'intent_type' in entry:
                intents.append(entry['intent_type'])
                if len(intents) >= num_intents:
                    break

        return intents

    def get_session_metadata(
        self,
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get session metadata (start time, last activity).

        Args:
            session_id: Unique session identifier

        Returns:
            Metadata dict or None if session doesn't exist
        """
        metadata_key = f"voice:session:{session_id}:metadata"
        return self.redis.get(metadata_key)

    def get_session_duration_seconds(
        self,
        session_id: str
    ) -> Optional[float]:
        """
        Calculate session duration in seconds.

        Args:
            session_id: Unique session identifier

        Returns:
            Duration in seconds or None if session doesn't exist
        """
        metadata = self.get_session_metadata(session_id)
        if not metadata:
            return None

        start_time_str = metadata.get('start_time')
        last_activity_str = metadata.get('last_activity')

        if not start_time_str or not last_activity_str:
            return None

        try:
            start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
            last_activity = datetime.fromisoformat(last_activity_str.replace('Z', '+00:00'))
            duration = (last_activity - start_time).total_seconds()
            return duration
        except (ValueError, AttributeError):
            return None

    def get_session_message_count(
        self,
        session_id: str
    ) -> int:
        """
        Get total message count for a session.

        Args:
            session_id: Unique session identifier

        Returns:
            Number of messages in session
        """
        transcripts = self.get_conversation_history(session_id)
        return len(transcripts)

    def cleanup_session(
        self,
        session_id: str
    ) -> bool:
        """
        Clean up all session data.

        Deletes transcripts, metadata, and context for a session.
        Use this when a user explicitly ends a session or for
        maintenance/cleanup operations.

        Args:
            session_id: Unique session identifier

        Returns:
            True if session was deleted
        """
        return self.redis.delete_voice_session(session_id)

    def cleanup_old_sessions(
        self,
        max_age_hours: int = 2
    ) -> int:
        """
        Clean up expired sessions older than max_age_hours.

        This is a maintenance operation that should be run periodically
        to prevent memory leaks from abandoned sessions.

        Args:
            max_age_hours: Maximum session age in hours (default 2)

        Returns:
            Number of sessions cleaned up
        """
        # Get all session metadata keys
        pattern = "voice:session:*:metadata"
        metadata_keys = self.redis.keys(pattern)

        cleaned_count = 0
        current_time = datetime.utcnow()

        for metadata_key in metadata_keys:
            # Extract session_id from key
            # Format: voice:session:{session_id}:metadata
            parts = metadata_key.split(':')
            if len(parts) != 4:
                continue
            session_id = parts[2]

            # Get metadata
            metadata = self.redis.get(metadata_key)
            if not metadata:
                continue

            # Check last_activity timestamp
            last_activity_str = metadata.get('last_activity')
            if not last_activity_str:
                continue

            try:
                last_activity = datetime.fromisoformat(last_activity_str.replace('Z', '+00:00'))
                age_hours = (current_time - last_activity).total_seconds() / 3600

                if age_hours > max_age_hours:
                    if self.cleanup_session(session_id):
                        cleaned_count += 1
            except (ValueError, AttributeError):
                # Skip malformed timestamps
                continue

        return cleaned_count

    def health_check(self) -> bool:
        """
        Check if Redis connection is healthy.

        Returns:
            True if connection is healthy
        """
        return self.redis.health_check()

    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about voice storage.

        Returns:
            Dict with storage statistics
        """
        # Count active sessions
        metadata_keys = self.redis.keys("voice:session:*:metadata")
        active_sessions = len(metadata_keys)

        # Count total transcripts across all sessions
        transcript_keys = self.redis.keys("voice:session:*:transcripts")
        total_transcripts = 0
        for key in transcript_keys:
            # Get list length
            length = self.redis.client.llen(key)
            total_transcripts += length

        return {
            'active_sessions': active_sessions,
            'total_transcripts': total_transcripts,
            'redis_healthy': self.health_check()
        }


# Convenience function for quick integration
def get_voice_integration(
    redis_host: Optional[str] = None,
    redis_port: Optional[int] = None,
    redis_password: Optional[str] = None
) -> VoiceRedisIntegration:
    """
    Get a VoiceRedisIntegration instance with custom config.

    Args:
        redis_host: Redis host (default: localhost)
        redis_port: Redis port (default: 6379)
        redis_password: Redis password (default: None)

    Returns:
        VoiceRedisIntegration instance
    """
    config = None
    if redis_host or redis_port or redis_password:
        config = RedisConfig(
            host=redis_host or 'localhost',
            port=redis_port or 6379,
            password=redis_password
        )

    return VoiceRedisIntegration(config)
