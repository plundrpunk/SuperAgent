"""
Unit tests for voice transcript storage and retrieval.

Tests the new voice-specific methods in RedisClient:
- store_transcript with metadata
- get_session_transcripts
- get_recent_context
- delete_voice_session

Also tests the VoiceRedisIntegration layer.
"""
import json
import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from typing import Dict, Any

from agent_system.state.redis_client import RedisClient, RedisConfig
from agent_system.voice.redis_integration import VoiceRedisIntegration, get_voice_integration


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
        db=0
    )
    return RedisClient(config)


@pytest.fixture
def voice_integration(mock_redis):
    """VoiceRedisIntegration instance with mocked Redis."""
    config = RedisConfig(
        host='localhost',
        port=6379,
        password=None,
        db=0
    )
    return VoiceRedisIntegration(config)


class TestStoreTranscript:
    """Test store_transcript method with metadata."""

    def test_store_transcript_minimal(self, redis_client, mock_redis):
        """Test storing transcript with minimal metadata."""
        mock_redis.rpush.return_value = 1
        mock_redis.expire.return_value = True
        mock_redis.get.return_value = None  # No existing metadata
        mock_redis.setex.return_value = True

        result = redis_client.store_transcript(
            session_id='session_001',
            transcript='Hello Kaya',
            metadata=None
        )

        assert result is True

        # Verify transcript was stored
        calls = mock_redis.rpush.call_args_list
        assert any('voice:session:session_001:transcripts' in str(call) for call in calls)

        # Verify entry contains required fields
        stored_entry = None
        for call in calls:
            if 'voice:session:session_001:transcripts' in str(call):
                stored_entry = json.loads(call[0][1])
                break

        assert stored_entry is not None
        assert stored_entry['text'] == 'Hello Kaya'
        assert stored_entry['speaker'] == 'user'
        assert 'timestamp' in stored_entry

    def test_store_transcript_with_full_metadata(self, redis_client, mock_redis):
        """Test storing transcript with full metadata."""
        mock_redis.rpush.return_value = 1
        mock_redis.expire.return_value = True
        mock_redis.get.return_value = None
        mock_redis.setex.return_value = True

        metadata = {
            'timestamp': '2025-10-14T10:30:00Z',
            'speaker': 'user',
            'intent_type': 'create_test',
            'confidence_score': 0.95,
            'audio_duration_ms': 2500
        }

        result = redis_client.store_transcript(
            session_id='session_002',
            transcript='Kaya, write a test for login',
            metadata=metadata
        )

        assert result is True

        # Verify metadata was included
        calls = mock_redis.rpush.call_args_list
        stored_entry = None
        for call in calls:
            if 'voice:session:session_002:transcripts' in str(call):
                stored_entry = json.loads(call[0][1])
                break

        assert stored_entry is not None
        assert stored_entry['text'] == 'Kaya, write a test for login'
        assert stored_entry['speaker'] == 'user'
        assert stored_entry['intent_type'] == 'create_test'
        assert stored_entry['confidence_score'] == 0.95
        assert stored_entry['audio_duration_ms'] == 2500

    def test_store_transcript_agent_response(self, redis_client, mock_redis):
        """Test storing agent response with speaker=agent."""
        mock_redis.rpush.return_value = 1
        mock_redis.expire.return_value = True
        mock_redis.get.return_value = None
        mock_redis.setex.return_value = True

        metadata = {
            'speaker': 'agent',
            'timestamp': '2025-10-14T10:30:05Z'
        }

        result = redis_client.store_transcript(
            session_id='session_003',
            transcript='I will create that test for you',
            metadata=metadata
        )

        assert result is True

        # Verify speaker is agent
        calls = mock_redis.rpush.call_args_list
        stored_entry = None
        for call in calls:
            if 'voice:session:session_003:transcripts' in str(call):
                stored_entry = json.loads(call[0][1])
                break

        assert stored_entry is not None
        assert stored_entry['speaker'] == 'agent'

    def test_store_transcript_updates_session_metadata(self, redis_client, mock_redis):
        """Test that storing transcript updates session metadata."""
        mock_redis.rpush.return_value = 1
        mock_redis.expire.return_value = True
        mock_redis.get.return_value = None  # No existing metadata
        mock_redis.setex.return_value = True

        redis_client.store_transcript(
            session_id='session_004',
            transcript='Test message'
        )

        # Verify session metadata was created
        setex_calls = mock_redis.setex.call_args_list
        metadata_call = None
        for call in setex_calls:
            if 'voice:session:session_004:metadata' in str(call):
                metadata_call = call
                break

        assert metadata_call is not None
        metadata = json.loads(metadata_call[0][2])
        assert 'start_time' in metadata
        assert 'last_activity' in metadata

    def test_store_transcript_updates_context_window(self, redis_client, mock_redis):
        """Test that storing transcript updates context window."""
        mock_redis.rpush.return_value = 1
        mock_redis.expire.return_value = True
        mock_redis.get.return_value = None
        mock_redis.setex.return_value = True
        mock_redis.ltrim.return_value = True

        redis_client.store_transcript(
            session_id='session_005',
            transcript='Context message'
        )

        # Verify context window was updated
        rpush_calls = [str(call) for call in mock_redis.rpush.call_args_list]
        assert any('voice:session:session_005:context' in call for call in rpush_calls)

        # Verify ltrim was called to maintain window size
        mock_redis.ltrim.assert_called()
        ltrim_call = mock_redis.ltrim.call_args[0]
        assert ltrim_call[0] == 'voice:session:session_005:context'
        assert ltrim_call[1] == -20
        assert ltrim_call[2] == -1

    def test_store_transcript_with_custom_ttl(self, redis_client, mock_redis):
        """Test storing transcript with custom TTL."""
        mock_redis.rpush.return_value = 1
        mock_redis.expire.return_value = True
        mock_redis.get.return_value = None
        mock_redis.setex.return_value = True

        redis_client.store_transcript(
            session_id='session_006',
            transcript='Custom TTL message',
            ttl=7200
        )

        # Verify TTL was set to 7200
        expire_calls = [call for call in mock_redis.expire.call_args_list]
        assert any(call[0][1] == 7200 for call in expire_calls)


class TestGetSessionTranscripts:
    """Test get_session_transcripts method."""

    def test_get_session_transcripts_multiple(self, redis_client, mock_redis):
        """Test retrieving multiple transcripts with metadata."""
        mock_transcripts = [
            json.dumps({
                'text': 'Hello Kaya',
                'timestamp': '2025-10-14T10:00:00Z',
                'speaker': 'user',
                'intent_type': 'status'
            }),
            json.dumps({
                'text': 'Hello! How can I help you?',
                'timestamp': '2025-10-14T10:00:01Z',
                'speaker': 'agent'
            }),
            json.dumps({
                'text': 'Write a test for login',
                'timestamp': '2025-10-14T10:00:05Z',
                'speaker': 'user',
                'intent_type': 'create_test',
                'confidence_score': 0.92
            })
        ]

        mock_redis.lrange.return_value = mock_transcripts

        result = redis_client.get_session_transcripts('session_007')

        assert len(result) == 3
        assert result[0]['text'] == 'Hello Kaya'
        assert result[0]['speaker'] == 'user'
        assert result[0]['intent_type'] == 'status'
        assert result[1]['speaker'] == 'agent'
        assert result[2]['intent_type'] == 'create_test'
        assert result[2]['confidence_score'] == 0.92

        mock_redis.lrange.assert_called_once_with(
            'voice:session:session_007:transcripts',
            0,
            -1
        )

    def test_get_session_transcripts_empty(self, redis_client, mock_redis):
        """Test retrieving transcripts from empty session."""
        mock_redis.lrange.return_value = []

        result = redis_client.get_session_transcripts('session_empty')

        assert result == []

    def test_get_session_transcripts_handles_legacy_format(self, redis_client, mock_redis):
        """Test handling of legacy plain text transcripts."""
        mock_transcripts = [
            'Plain text transcript 1',
            json.dumps({
                'text': 'New format transcript',
                'timestamp': '2025-10-14T10:00:00Z',
                'speaker': 'user'
            }),
            'Plain text transcript 2'
        ]

        mock_redis.lrange.return_value = mock_transcripts

        result = redis_client.get_session_transcripts('session_mixed')

        assert len(result) == 3
        assert result[0]['text'] == 'Plain text transcript 1'
        assert result[0]['speaker'] == 'unknown'
        assert result[1]['text'] == 'New format transcript'
        assert result[1]['speaker'] == 'user'
        assert result[2]['text'] == 'Plain text transcript 2'


class TestGetRecentContext:
    """Test get_recent_context method."""

    def test_get_recent_context_default_limit(self, redis_client, mock_redis):
        """Test getting recent context with default limit (5)."""
        mock_context = [
            json.dumps({'text': 'Message 1', 'speaker': 'user', 'timestamp': '2025-10-14T10:00:00Z'}),
            json.dumps({'text': 'Message 2', 'speaker': 'agent', 'timestamp': '2025-10-14T10:00:01Z'}),
            json.dumps({'text': 'Message 3', 'speaker': 'user', 'timestamp': '2025-10-14T10:00:02Z'}),
            json.dumps({'text': 'Message 4', 'speaker': 'agent', 'timestamp': '2025-10-14T10:00:03Z'}),
            json.dumps({'text': 'Message 5', 'speaker': 'user', 'timestamp': '2025-10-14T10:00:04Z'})
        ]

        mock_redis.lrange.return_value = mock_context

        result = redis_client.get_recent_context('session_008')

        assert len(result) == 5
        assert result[0]['text'] == 'Message 1'
        assert result[4]['text'] == 'Message 5'

        # Verify Redis was queried with correct indices
        mock_redis.lrange.assert_called_once_with(
            'voice:session:session_008:context',
            -5,
            -1
        )

    def test_get_recent_context_custom_limit(self, redis_client, mock_redis):
        """Test getting recent context with custom limit."""
        mock_context = [
            json.dumps({'text': 'Message 1', 'speaker': 'user'}),
            json.dumps({'text': 'Message 2', 'speaker': 'agent'}),
            json.dumps({'text': 'Message 3', 'speaker': 'user'})
        ]

        mock_redis.lrange.return_value = mock_context

        result = redis_client.get_recent_context('session_009', num_messages=3)

        assert len(result) == 3

        mock_redis.lrange.assert_called_once_with(
            'voice:session:session_009:context',
            -3,
            -1
        )

    def test_get_recent_context_empty(self, redis_client, mock_redis):
        """Test getting context from session with no context."""
        mock_redis.lrange.return_value = []

        result = redis_client.get_recent_context('session_no_context')

        assert result == []

    def test_get_recent_context_handles_malformed_entries(self, redis_client, mock_redis):
        """Test that malformed JSON entries are skipped."""
        mock_context = [
            json.dumps({'text': 'Valid message 1', 'speaker': 'user'}),
            '{invalid json',
            json.dumps({'text': 'Valid message 2', 'speaker': 'agent'}),
            'not json at all',
            json.dumps({'text': 'Valid message 3', 'speaker': 'user'})
        ]

        mock_redis.lrange.return_value = mock_context

        result = redis_client.get_recent_context('session_malformed')

        # Should only return valid entries
        assert len(result) == 3
        assert result[0]['text'] == 'Valid message 1'
        assert result[1]['text'] == 'Valid message 2'
        assert result[2]['text'] == 'Valid message 3'


class TestDeleteVoiceSession:
    """Test delete_voice_session method."""

    def test_delete_voice_session_all_keys(self, redis_client, mock_redis):
        """Test deleting all voice session keys."""
        # Mock that all 3 keys exist and are deleted
        mock_redis.delete.return_value = 1

        result = redis_client.delete_voice_session('session_010')

        assert result is True

        # Verify all 3 keys were attempted to be deleted
        delete_calls = [call[0][0] for call in mock_redis.delete.call_args_list]
        assert 'voice:session:session_010:transcripts' in delete_calls
        assert 'voice:session:session_010:metadata' in delete_calls
        assert 'voice:session:session_010:context' in delete_calls

    def test_delete_voice_session_partial(self, redis_client, mock_redis):
        """Test deleting session with only some keys existing."""
        # Mock that only some keys exist
        def delete_side_effect(key):
            if 'transcripts' in key:
                return 1
            return 0

        mock_redis.delete.side_effect = delete_side_effect

        result = redis_client.delete_voice_session('session_partial')

        # Should return True if at least one key was deleted
        assert result is True

    def test_delete_voice_session_not_found(self, redis_client, mock_redis):
        """Test deleting non-existent session."""
        mock_redis.delete.return_value = 0

        result = redis_client.delete_voice_session('session_nonexistent')

        assert result is False


class TestSessionMetadataHelpers:
    """Test internal session metadata helper methods."""

    def test_update_session_metadata_new_session(self, redis_client, mock_redis):
        """Test creating metadata for new session."""
        mock_redis.get.return_value = None  # No existing metadata
        mock_redis.setex.return_value = True

        result = redis_client._update_session_metadata('session_new', 3600)

        assert result is True

        # Verify metadata was created with start_time and last_activity
        call_args = mock_redis.setex.call_args[0]
        assert call_args[0] == 'voice:session:session_new:metadata'
        assert call_args[1] == 3600

        metadata = json.loads(call_args[2])
        assert 'start_time' in metadata
        assert 'last_activity' in metadata

    def test_update_session_metadata_existing_session(self, redis_client, mock_redis):
        """Test updating metadata for existing session."""
        existing_metadata = json.dumps({
            'start_time': '2025-10-14T10:00:00Z',
            'last_activity': '2025-10-14T10:00:00Z'
        })
        mock_redis.get.return_value = existing_metadata
        mock_redis.setex.return_value = True

        result = redis_client._update_session_metadata('session_existing', 3600)

        assert result is True

        # Verify last_activity was updated
        call_args = mock_redis.setex.call_args[0]
        metadata = json.loads(call_args[2])
        assert metadata['start_time'] == '2025-10-14T10:00:00Z'
        assert metadata['last_activity'] != '2025-10-14T10:00:00Z'  # Should be updated

    def test_update_context_window_trimming(self, redis_client, mock_redis):
        """Test that context window is trimmed to max 20 entries."""
        mock_redis.rpush.return_value = 1
        mock_redis.ltrim.return_value = True
        mock_redis.expire.return_value = True

        entry_json = json.dumps({'text': 'Test', 'speaker': 'user'})
        result = redis_client._update_context_window('session_trim', entry_json, 3600)

        assert result is True

        # Verify ltrim maintains max 20 entries
        mock_redis.ltrim.assert_called_once_with(
            'voice:session:session_trim:context',
            -20,
            -1
        )


class TestVoiceRedisIntegration:
    """Test VoiceRedisIntegration high-level interface."""

    def test_store_user_transcript(self, voice_integration, mock_redis):
        """Test storing user transcript via integration layer."""
        mock_redis.rpush.return_value = 1
        mock_redis.expire.return_value = True
        mock_redis.get.return_value = None
        mock_redis.setex.return_value = True
        mock_redis.ltrim.return_value = True

        result = voice_integration.store_user_transcript(
            session_id='int_session_001',
            transcript='Kaya, run tests',
            intent_type='run_test',
            confidence_score=0.88,
            audio_duration_ms=1800
        )

        assert result is True

    def test_store_agent_response(self, voice_integration, mock_redis):
        """Test storing agent response via integration layer."""
        mock_redis.rpush.return_value = 1
        mock_redis.expire.return_value = True
        mock_redis.get.return_value = None
        mock_redis.setex.return_value = True
        mock_redis.ltrim.return_value = True

        result = voice_integration.store_agent_response(
            session_id='int_session_002',
            response='Running tests now',
            audio_duration_ms=1200
        )

        assert result is True

    def test_get_conversation_history(self, voice_integration, mock_redis):
        """Test getting full conversation history."""
        mock_transcripts = [
            json.dumps({
                'text': 'User message',
                'speaker': 'user',
                'timestamp': '2025-10-14T10:00:00Z'
            }),
            json.dumps({
                'text': 'Agent response',
                'speaker': 'agent',
                'timestamp': '2025-10-14T10:00:01Z'
            })
        ]
        mock_redis.lrange.return_value = mock_transcripts

        result = voice_integration.get_conversation_history('int_session_003')

        assert len(result) == 2
        assert result[0]['speaker'] == 'user'
        assert result[1]['speaker'] == 'agent'

    def test_get_context_for_agent(self, voice_integration, mock_redis):
        """Test getting formatted context for agent."""
        mock_context = [
            json.dumps({
                'text': 'Write a test',
                'speaker': 'user',
                'timestamp': '2025-10-14T10:00:00Z'
            }),
            json.dumps({
                'text': 'Creating test',
                'speaker': 'agent',
                'timestamp': '2025-10-14T10:00:01Z'
            })
        ]
        mock_redis.lrange.return_value = mock_context

        result = voice_integration.get_context_for_agent('int_session_004', num_messages=2)

        assert isinstance(result, str)
        assert 'USER:' in result
        assert 'AGENT:' in result
        assert 'Write a test' in result

    def test_get_recent_intents(self, voice_integration, mock_redis):
        """Test extracting recent user intents."""
        mock_context = [
            json.dumps({
                'text': 'Write a test',
                'speaker': 'user',
                'intent_type': 'create_test',
                'timestamp': '2025-10-14T10:00:00Z'
            }),
            json.dumps({
                'text': 'Creating test',
                'speaker': 'agent',
                'timestamp': '2025-10-14T10:00:01Z'
            }),
            json.dumps({
                'text': 'Run the test',
                'speaker': 'user',
                'intent_type': 'run_test',
                'timestamp': '2025-10-14T10:00:02Z'
            })
        ]
        mock_redis.lrange.return_value = mock_context

        result = voice_integration.get_recent_intents('int_session_005', num_intents=2)

        assert len(result) == 2
        assert 'create_test' in result
        assert 'run_test' in result

    def test_cleanup_session(self, voice_integration, mock_redis):
        """Test session cleanup via integration layer."""
        mock_redis.delete.return_value = 1

        result = voice_integration.cleanup_session('int_session_006')

        assert result is True

    def test_get_stats(self, voice_integration, mock_redis):
        """Test getting storage statistics."""
        mock_redis.keys.side_effect = [
            ['voice:session:s1:metadata', 'voice:session:s2:metadata'],  # 2 sessions
            ['voice:session:s1:transcripts', 'voice:session:s2:transcripts']  # 2 transcript keys
        ]
        mock_redis.llen.side_effect = [5, 8]  # 5 + 8 = 13 total transcripts
        mock_redis.ping.return_value = True

        result = voice_integration.get_stats()

        assert result['active_sessions'] == 2
        assert result['total_transcripts'] == 13
        assert result['redis_healthy'] is True


class TestGetVoiceIntegrationFactory:
    """Test get_voice_integration factory function."""

    def test_get_voice_integration_default(self, mock_redis):
        """Test factory with default config."""
        integration = get_voice_integration()

        assert isinstance(integration, VoiceRedisIntegration)

    def test_get_voice_integration_custom_config(self, mock_redis):
        """Test factory with custom config."""
        integration = get_voice_integration(
            redis_host='custom-redis',
            redis_port=6380,
            redis_password='secret'
        )

        assert isinstance(integration, VoiceRedisIntegration)
        assert integration.redis.config.host == 'custom-redis'
        assert integration.redis.config.port == 6380
        assert integration.redis.config.password == 'secret'


class TestConcurrentSessions:
    """Test handling of multiple concurrent voice sessions."""

    def test_multiple_sessions_isolated(self, redis_client, mock_redis):
        """Test that multiple sessions are isolated from each other."""
        mock_redis.rpush.return_value = 1
        mock_redis.expire.return_value = True
        mock_redis.get.return_value = None
        mock_redis.setex.return_value = True
        mock_redis.ltrim.return_value = True

        # Store transcripts for multiple sessions
        redis_client.store_transcript('session_A', 'Message A1')
        redis_client.store_transcript('session_B', 'Message B1')
        redis_client.store_transcript('session_A', 'Message A2')

        # Verify correct keys were used
        rpush_calls = [call[0][0] for call in mock_redis.rpush.call_args_list]

        # Should have calls for both session_A and session_B transcripts
        session_a_calls = [c for c in rpush_calls if 'session_A:transcripts' in c]
        session_b_calls = [c for c in rpush_calls if 'session_B:transcripts' in c]

        assert len(session_a_calls) >= 2  # At least 2 messages for session A
        assert len(session_b_calls) >= 1  # At least 1 message for session B


class TestTTLEnforcement:
    """Test TTL enforcement for voice storage."""

    def test_all_keys_have_ttl(self, redis_client, mock_redis):
        """Test that all voice keys have TTL set."""
        mock_redis.rpush.return_value = 1
        mock_redis.expire.return_value = True
        mock_redis.get.return_value = None
        mock_redis.setex.return_value = True
        mock_redis.ltrim.return_value = True

        redis_client.store_transcript('session_ttl', 'Test message', ttl=7200)

        # Verify expire was called for transcripts and context
        expire_calls = [call[0] for call in mock_redis.expire.call_args_list]
        assert any('transcripts' in call[0] for call in expire_calls)
        assert any('context' in call[0] for call in expire_calls)

        # Verify setex was called for metadata (which includes TTL)
        setex_calls = [call[0] for call in mock_redis.setex.call_args_list]
        assert any('metadata' in call[0] for call in setex_calls)


# Mark all tests in this module as unit tests
pytestmark = pytest.mark.unit
