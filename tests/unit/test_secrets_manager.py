"""
Unit tests for SecretsManager

Tests API key rotation, fallback, and security features.
"""
import pytest
import os
import time
from unittest.mock import Mock, patch, MagicMock

from agent_system.secrets_manager import SecretsManager, KeyMetadata, RotationState, get_secrets_manager
from agent_system.state.redis_client import RedisClient


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    redis = Mock(spec=RedisClient)
    redis.client = Mock()
    redis.get = Mock(return_value=None)
    redis.set = Mock()
    return redis


@pytest.fixture
def test_env_keys(monkeypatch):
    """Set up test environment with API keys."""
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'sk-ant-test-primary-key')
    monkeypatch.setenv('ANTHROPIC_API_KEY_SECONDARY', 'sk-ant-test-secondary-key')
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-test-openai-primary')
    monkeypatch.setenv('OPENAI_API_KEY_SECONDARY', 'sk-test-openai-secondary')
    monkeypatch.setenv('GEMINI_API_KEY', 'AIzaSy-test-gemini-primary')
    monkeypatch.setenv('KEY_ROTATION_ENABLED', 'true')
    monkeypatch.setenv('KEY_ROTATION_OVERLAP_HOURS', '24')


@pytest.fixture
def secrets_manager(mock_redis, test_env_keys):
    """Create a SecretsManager instance with mock Redis."""
    return SecretsManager(redis_client=mock_redis)


class TestSecretsManagerInitialization:
    """Test SecretsManager initialization."""

    def test_initialization_with_env_keys(self, secrets_manager, mock_redis):
        """Test that manager loads keys from environment."""
        assert 'anthropic' in secrets_manager._keys_cache
        assert 'openai' in secrets_manager._keys_cache
        assert 'gemini' in secrets_manager._keys_cache

        # Check primary keys loaded
        assert secrets_manager._keys_cache['anthropic']['primary'] == 'sk-ant-test-primary-key'
        assert secrets_manager._keys_cache['openai']['primary'] == 'sk-test-openai-primary'

        # Check secondary keys loaded
        assert secrets_manager._keys_cache['anthropic']['secondary'] == 'sk-ant-test-secondary-key'
        assert secrets_manager._keys_cache['openai']['secondary'] == 'sk-test-openai-secondary'

    def test_initialization_with_rotation_disabled(self, mock_redis, monkeypatch):
        """Test initialization with rotation disabled."""
        monkeypatch.setenv('KEY_ROTATION_ENABLED', 'false')
        manager = SecretsManager(redis_client=mock_redis)
        assert manager.enable_rotation is False

    def test_initialization_custom_overlap(self, mock_redis, monkeypatch):
        """Test initialization with custom overlap hours."""
        monkeypatch.setenv('KEY_ROTATION_OVERLAP_HOURS', '48')
        manager = SecretsManager(redis_client=mock_redis)
        assert manager.rotation_overlap_hours == 48


class TestGetAPIKey:
    """Test get_api_key functionality."""

    def test_get_primary_key(self, secrets_manager):
        """Test retrieving primary API key."""
        key = secrets_manager.get_api_key('anthropic')
        assert key == 'sk-ant-test-primary-key'

    def test_get_key_unsupported_service(self, secrets_manager):
        """Test error when service not supported."""
        with pytest.raises(ValueError, match="Unsupported service"):
            secrets_manager.get_api_key('unsupported_service')

    def test_get_key_no_primary_fallback_to_secondary(self, mock_redis, test_env_keys, monkeypatch):
        """Test fallback to secondary when primary not available."""
        # Remove primary key
        monkeypatch.delenv('ANTHROPIC_API_KEY')
        manager = SecretsManager(redis_client=mock_redis)

        # Should fallback to secondary
        key = manager.get_api_key('anthropic')
        assert key == 'sk-ant-test-secondary-key'

    def test_get_key_no_keys_raises_error(self, mock_redis, monkeypatch):
        """Test error when no keys available."""
        # Remove all Anthropic keys
        monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
        monkeypatch.delenv('ANTHROPIC_API_KEY_SECONDARY', raising=False)
        manager = SecretsManager(redis_client=mock_redis)

        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY not found"):
            manager.get_api_key('anthropic')


class TestKeyRotation:
    """Test key rotation functionality."""

    def test_rotate_key_success(self, secrets_manager, mock_redis):
        """Test successful key rotation."""
        new_key = 'sk-ant-new-rotated-key'
        success = secrets_manager.rotate_key('anthropic', new_key)

        assert success is True

        # New key should be added as secondary
        assert secrets_manager._keys_cache['anthropic']['secondary'] == new_key

        # Should create rotation state in Redis
        assert mock_redis.set.called

    def test_rotate_key_no_existing_key(self, mock_redis, monkeypatch):
        """Test rotation when no existing key (sets as primary)."""
        # Start with no keys
        monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
        monkeypatch.delenv('ANTHROPIC_API_KEY_SECONDARY', raising=False)
        manager = SecretsManager(redis_client=mock_redis)

        new_key = 'sk-ant-first-key'
        success = manager.rotate_key('anthropic', new_key)

        assert success is True
        assert manager._keys_cache['anthropic']['primary'] == new_key

    def test_rotate_key_same_key_skips(self, secrets_manager):
        """Test that rotating to same key is skipped."""
        # Try to rotate to current primary
        current_key = secrets_manager._keys_cache['anthropic']['primary']
        success = secrets_manager.rotate_key('anthropic', current_key)

        assert success is False

    def test_rotate_key_rotation_disabled(self, mock_redis, test_env_keys):
        """Test error when rotation is disabled."""
        manager = SecretsManager(redis_client=mock_redis, enable_rotation=False)

        with pytest.raises(ValueError, match="Key rotation is disabled"):
            manager.rotate_key('anthropic', 'sk-ant-new-key')

    def test_rotate_key_unsupported_service(self, secrets_manager):
        """Test error for unsupported service."""
        with pytest.raises(ValueError, match="Unsupported service"):
            secrets_manager.rotate_key('invalid', 'new-key')


class TestRemoveOldKey:
    """Test removing old key after rotation."""

    def test_remove_old_key_success(self, secrets_manager, mock_redis):
        """Test successfully removing old key after overlap period."""
        # Start rotation
        secrets_manager.rotate_key('anthropic', 'sk-ant-new-key')

        # Mock rotation state that has elapsed
        rotation_data = {
            'service': 'anthropic',
            'old_key_id': 'old123',
            'new_key_id': 'new456',
            'started_at': time.time() - (25 * 3600),  # 25 hours ago
            'overlap_hours': 24,
            'completed': False,
            'completed_at': None
        }
        mock_redis.get.return_value = rotation_data

        success = secrets_manager.remove_old_key('anthropic')
        assert success is True

    def test_remove_old_key_overlap_not_complete(self, secrets_manager, mock_redis):
        """Test error when overlap period not complete."""
        # Mock rotation state that hasn't elapsed
        rotation_data = {
            'service': 'anthropic',
            'old_key_id': 'old123',
            'new_key_id': 'new456',
            'started_at': time.time() - (5 * 3600),  # 5 hours ago
            'overlap_hours': 24,
            'completed': False,
            'completed_at': None
        }
        mock_redis.get.return_value = rotation_data

        with pytest.raises(ValueError, match="Rotation overlap period not complete"):
            secrets_manager.remove_old_key('anthropic')

    def test_remove_old_key_no_rotation(self, secrets_manager, mock_redis):
        """Test error when no rotation in progress."""
        mock_redis.get.return_value = None

        with pytest.raises(ValueError, match="No rotation in progress"):
            secrets_manager.remove_old_key('anthropic')


class TestFallbackMechanism:
    """Test fallback to secondary key on failure."""

    def test_fallback_to_secondary_success(self, secrets_manager):
        """Test successful fallback to secondary key."""
        success = secrets_manager.fallback_to_secondary('anthropic')
        assert success is True

        # Keys should be swapped
        assert secrets_manager._keys_cache['anthropic']['primary'] == 'sk-ant-test-secondary-key'
        assert secrets_manager._keys_cache['anthropic']['secondary'] == 'sk-ant-test-primary-key'

    def test_fallback_no_secondary_available(self, mock_redis, monkeypatch):
        """Test fallback when no secondary key available."""
        # Set up with only primary key
        monkeypatch.setenv('ANTHROPIC_API_KEY', 'sk-ant-primary-only')
        monkeypatch.delenv('ANTHROPIC_API_KEY_SECONDARY', raising=False)
        manager = SecretsManager(redis_client=mock_redis)

        success = manager.fallback_to_secondary('anthropic')
        assert success is False


class TestSecurityFeatures:
    """Test security features (key sanitization, logging)."""

    def test_get_key_id_anonymization(self, secrets_manager):
        """Test that key IDs are anonymized (last 8 chars of hash)."""
        key = 'sk-ant-test-key-12345'
        key_id = secrets_manager._get_key_id(key)

        # Should be 8 characters
        assert len(key_id) == 8

        # Should be different for different keys
        key2 = 'sk-ant-different-key'
        key_id2 = secrets_manager._get_key_id(key2)
        assert key_id != key_id2

    def test_sanitize_error_removes_anthropic_keys(self, secrets_manager):
        """Test that error messages have Anthropic keys sanitized."""
        error = "Failed with key sk-ant-api03-abc123def456"
        sanitized = secrets_manager._sanitize_error(error)

        assert 'sk-ant-***' in sanitized
        assert 'abc123def456' not in sanitized

    def test_sanitize_error_removes_openai_keys(self, secrets_manager):
        """Test that error messages have OpenAI keys sanitized."""
        error = "Failed with key sk-proj-xyz789abc"
        sanitized = secrets_manager._sanitize_error(error)

        assert 'sk-***' in sanitized
        assert 'xyz789abc' not in sanitized

    def test_sanitize_error_removes_gemini_keys(self, secrets_manager):
        """Test that error messages have Gemini keys sanitized."""
        error = "Failed with key AIzaSyABC123DEF456"
        sanitized = secrets_manager._sanitize_error(error)

        assert 'AIza***' in sanitized
        assert 'ABC123DEF456' not in sanitized


class TestRotationStatus:
    """Test rotation status reporting."""

    def test_get_rotation_status_active(self, secrets_manager, mock_redis):
        """Test getting status of active rotation."""
        rotation_data = {
            'service': 'anthropic',
            'old_key_id': 'old123',
            'new_key_id': 'new456',
            'started_at': time.time() - (10 * 3600),  # 10 hours ago
            'overlap_hours': 24,
            'completed': False,
            'completed_at': None
        }
        mock_redis.get.return_value = rotation_data

        status = secrets_manager.get_rotation_status('anthropic')

        assert status is not None
        assert status['old_key_id'] == 'old123'
        assert status['new_key_id'] == 'new456'
        assert 9 < status['elapsed_hours'] < 11  # Approximately 10 hours
        assert 13 < status['remaining_hours'] < 15  # Approximately 14 hours
        assert status['completed'] is False
        assert status['can_remove_old_key'] is False

    def test_get_rotation_status_none(self, secrets_manager, mock_redis):
        """Test getting status when no rotation in progress."""
        mock_redis.get.return_value = None

        status = secrets_manager.get_rotation_status('anthropic')
        assert status is None


class TestKeyStatistics:
    """Test key usage statistics."""

    def test_get_key_stats(self, secrets_manager, mock_redis):
        """Test retrieving key statistics."""
        # Mock metadata for primary key
        primary_metadata = {
            'service': 'anthropic',
            'key_id': 'abc12345',
            'added_at': time.time() - 3600,
            'is_primary': True,
            'usage_count': 50,
            'failure_count': 2,
            'last_used_at': time.time() - 60,
            'last_failure_at': time.time() - 3000
        }

        # Mock metadata for secondary key
        secondary_metadata = {
            'service': 'anthropic',
            'key_id': 'def67890',
            'added_at': time.time() - 7200,
            'is_primary': False,
            'usage_count': 10,
            'failure_count': 0,
            'last_used_at': time.time() - 3600,
            'last_failure_at': None
        }

        def mock_get_metadata(key):
            if 'abc12345' in key:
                return primary_metadata
            elif 'def67890' in key:
                return secondary_metadata
            return None

        mock_redis.get.side_effect = mock_get_metadata

        stats = secrets_manager.get_key_stats('anthropic')

        assert stats['service'] == 'anthropic'
        assert len(stats['keys']) == 2


class TestAllServicesStatus:
    """Test getting status for all services."""

    def test_get_all_services_status(self, secrets_manager):
        """Test getting status for all services."""
        status = secrets_manager.get_all_services_status()

        assert 'anthropic' in status
        assert 'openai' in status
        assert 'gemini' in status

        # Check anthropic status
        anthropic_status = status['anthropic']
        assert anthropic_status['has_primary'] is True
        assert anthropic_status['has_secondary'] is True
        assert anthropic_status['rotation_in_progress'] is False


class TestPromoteSecondary:
    """Test promoting secondary key to primary."""

    def test_promote_secondary_to_primary(self, secrets_manager):
        """Test promoting secondary key to primary."""
        original_secondary = secrets_manager._keys_cache['anthropic']['secondary']

        success = secrets_manager.promote_secondary_to_primary('anthropic')
        assert success is True

        # Secondary should now be primary
        assert secrets_manager._keys_cache['anthropic']['primary'] == original_secondary

    def test_promote_no_secondary(self, mock_redis, monkeypatch):
        """Test promoting when no secondary exists."""
        monkeypatch.setenv('ANTHROPIC_API_KEY', 'sk-ant-primary-only')
        monkeypatch.delenv('ANTHROPIC_API_KEY_SECONDARY', raising=False)
        manager = SecretsManager(redis_client=mock_redis)

        success = manager.promote_secondary_to_primary('anthropic')
        assert success is False


class TestGlobalInstance:
    """Test global secrets manager instance."""

    def test_get_secrets_manager_singleton(self, mock_redis, test_env_keys):
        """Test that get_secrets_manager returns singleton."""
        # Reset global instance
        import agent_system.secrets_manager
        agent_system.secrets_manager._global_secrets_manager = None

        manager1 = get_secrets_manager(redis_client=mock_redis)
        manager2 = get_secrets_manager()

        # Should be same instance
        assert manager1 is manager2


class TestIntegrationWithCostAnalytics:
    """Test integration with cost analytics (usage tracking)."""

    def test_key_metadata_updated_on_use(self, secrets_manager, mock_redis):
        """Test that key metadata is updated when key is used."""
        # Get API key (should update usage)
        key = secrets_manager.get_api_key('anthropic')

        # Check that update_key_metadata was called
        assert mock_redis.set.called

    def test_key_metadata_updated_on_failure(self, secrets_manager, mock_redis):
        """Test that key metadata is updated when key fails."""
        # Manually mark key as failed
        key = secrets_manager._keys_cache['anthropic']['primary']
        secrets_manager._update_key_metadata(
            service='anthropic',
            key=key,
            is_primary=True,
            failed=True
        )

        # Check that update was called
        assert mock_redis.set.called


class TestBackwardCompatibility:
    """Test backward compatibility with single key setup."""

    def test_works_with_single_key(self, mock_redis, monkeypatch):
        """Test that system works with only primary keys (no rotation)."""
        # Set up with only primary keys
        monkeypatch.setenv('ANTHROPIC_API_KEY', 'sk-ant-primary-only')
        monkeypatch.delenv('ANTHROPIC_API_KEY_SECONDARY', raising=False)
        monkeypatch.setenv('OPENAI_API_KEY', 'sk-openai-primary-only')
        monkeypatch.delenv('OPENAI_API_KEY_SECONDARY', raising=False)

        manager = SecretsManager(redis_client=mock_redis)

        # Should still work
        key = manager.get_api_key('anthropic')
        assert key == 'sk-ant-primary-only'

        # Should not have secondary
        assert 'secondary' not in manager._keys_cache.get('anthropic', {})


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
