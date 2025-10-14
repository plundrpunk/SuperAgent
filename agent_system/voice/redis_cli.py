#!/usr/bin/env python3
"""
Redis CLI wrapper for Voice Orchestrator
Simple command-line interface to Redis operations for transcript storage
"""
import sys
import json
import os

# Add parent directory to path to import redis_client
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from state.redis_client import RedisClient


def add_transcript(session_id: str, transcript_json: str):
    """Add transcript to Redis with 1h TTL (legacy method)"""
    try:
        client = RedisClient()
        transcript_data = json.loads(transcript_json)
        transcript_text = transcript_data.get('text', '')

        success = client.add_transcript(session_id, transcript_text)
        print(json.dumps({'success': success}))
        return 0 if success else 1
    except Exception as e:
        print(json.dumps({'success': False, 'error': str(e)}), file=sys.stderr)
        return 1


def store_transcript(session_id: str, transcript: str, metadata_json: str = '{}'):
    """Store transcript with metadata"""
    try:
        client = RedisClient()
        metadata = json.loads(metadata_json) if metadata_json else {}

        success = client.store_transcript(
            session_id=session_id,
            transcript=transcript,
            metadata=metadata
        )
        print(json.dumps({'success': success}))
        return 0 if success else 1
    except Exception as e:
        print(json.dumps({'success': False, 'error': str(e)}), file=sys.stderr)
        return 1


def get_transcripts(session_id: str):
    """Retrieve all transcripts for session (legacy method)"""
    try:
        client = RedisClient()
        transcripts = client.get_transcripts(session_id)
        print(json.dumps(transcripts))
        return 0
    except Exception as e:
        print(json.dumps({'error': str(e)}), file=sys.stderr)
        return 1


def get_session_transcripts(session_id: str):
    """Retrieve all transcripts with metadata for session"""
    try:
        client = RedisClient()
        transcripts = client.get_session_transcripts(session_id)
        print(json.dumps(transcripts))
        return 0
    except Exception as e:
        print(json.dumps({'error': str(e)}), file=sys.stderr)
        return 1


def get_recent_context(session_id: str, num_messages: str = '5'):
    """Get recent conversation context"""
    try:
        client = RedisClient()
        num = int(num_messages)
        context = client.get_recent_context(session_id, num)
        print(json.dumps(context))
        return 0
    except Exception as e:
        print(json.dumps({'error': str(e)}), file=sys.stderr)
        return 1


def delete_voice_session(session_id: str):
    """Delete all voice session data"""
    try:
        client = RedisClient()
        success = client.delete_voice_session(session_id)
        print(json.dumps({'success': success}))
        return 0 if success else 1
    except Exception as e:
        print(json.dumps({'success': False, 'error': str(e)}), file=sys.stderr)
        return 1


def main():
    if len(sys.argv) < 2:
        print('Usage: redis_cli.py <command> [args...]', file=sys.stderr)
        print('Commands:', file=sys.stderr)
        print('  add_transcript <session_id> <transcript_json>             (legacy)', file=sys.stderr)
        print('  store_transcript <session_id> <transcript> [metadata_json]', file=sys.stderr)
        print('  get_transcripts <session_id>                              (legacy)', file=sys.stderr)
        print('  get_session_transcripts <session_id>', file=sys.stderr)
        print('  get_recent_context <session_id> [num_messages=5]', file=sys.stderr)
        print('  delete_voice_session <session_id>', file=sys.stderr)
        return 1

    command = sys.argv[1]

    if command == 'add_transcript':
        if len(sys.argv) != 4:
            print('Usage: add_transcript <session_id> <transcript_json>', file=sys.stderr)
            return 1
        return add_transcript(sys.argv[2], sys.argv[3])

    elif command == 'store_transcript':
        if len(sys.argv) < 4:
            print('Usage: store_transcript <session_id> <transcript> [metadata_json]', file=sys.stderr)
            return 1
        metadata = sys.argv[4] if len(sys.argv) > 4 else '{}'
        return store_transcript(sys.argv[2], sys.argv[3], metadata)

    elif command == 'get_transcripts':
        if len(sys.argv) != 3:
            print('Usage: get_transcripts <session_id>', file=sys.stderr)
            return 1
        return get_transcripts(sys.argv[2])

    elif command == 'get_session_transcripts':
        if len(sys.argv) != 3:
            print('Usage: get_session_transcripts <session_id>', file=sys.stderr)
            return 1
        return get_session_transcripts(sys.argv[2])

    elif command == 'get_recent_context':
        if len(sys.argv) < 3:
            print('Usage: get_recent_context <session_id> [num_messages=5]', file=sys.stderr)
            return 1
        num_messages = sys.argv[3] if len(sys.argv) > 3 else '5'
        return get_recent_context(sys.argv[2], num_messages)

    elif command == 'delete_voice_session':
        if len(sys.argv) != 3:
            print('Usage: delete_voice_session <session_id>', file=sys.stderr)
            return 1
        return delete_voice_session(sys.argv[2])

    else:
        print(f'Unknown command: {command}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
