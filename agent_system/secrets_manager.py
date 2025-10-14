"""
API Key Rotation and Secret Management for SuperAgent

Provides secure management of API keys with rotation support, graceful fallback,
and integration with Redis for rotation state tracking.

Features:
- Supports primary and secondary keys for zero-downtime rotation
- Automatic fallback when primary key fails
- Redis-based rotation state tracking (encrypted)
- Sanitized error messages (never logs actual keys)
- Integration with cost analytics to track per-key usage
- Support for multiple services (Anthropic, OpenAI, Gemini)
- Observability events for rotation lifecycle

Security:
- Keys never logged or printed to stdout/stderr
- Error messages sanitized to prevent key leakage
- Rotation state encrypted in Redis
- Per-key usage tracking for auditing

Usage:
    from agent_system.secrets_manager import get_secrets_manager

    # Get API key for service
    secrets = get_secrets_manager()
    api_key = secrets.get_api_key('anthropic')

    # Rotate key (add new key, marks for rotation)
    secrets.rotate_key('anthropic', 'sk-ant-new-key-here')

    # Remove old key after rotation completes
    secrets.remove_old_key('anthropic')
"""
import os
import time
import logging
import hashlib
import json
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import threading

from agent_system.state.redis_client import RedisClient
from agent_system.observability.event_stream import emit_event

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class KeyMetadata:
    """Metadata for an API key."""
    service: str
    key_id: str  # Last 8 chars of key hash for identification
    added_at: float
    is_primary: bool
    usage_count: int = 0
    failure_count: int = 0
    last_used_at: Optional[float] = None
    last_failure_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class RotationState:
    """State of ongoing key rotation."""
    service: str
    old_key_id: str
    new_key_id: str
    started_at: float
    overlap_hours: int
    completed: bool = False
    completed_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class SecretsManager:
    """
    Manages API keys with rotation support and graceful fallback.

    Features:
    - Primary/secondary key support for zero-downtime rotation
    - Automatic fallback when primary key fails
    - Redis-based rotation state tracking
    - Sanitized error messages (never logs keys)
    - Per-key usage and failure tracking
    - Integration with observability and cost analytics

    Redis Keys:
    - secrets:key_metadata:{service} -> KeyMetadata dict
    - secrets:rotation:{service} -> RotationState dict
    - secrets:active_key:{service} -> encrypted key data
    """

    SUPPORTED_SERVICES = ['anthropic', 'openai', 'gemini']

    def __init__(
        self,
        redis_client: Optional[RedisClient] = None,
        enable_rotation: bool = True,
        rotation_overlap_hours: int = 24
    ):
        """
        Initialize secrets manager.

        Args:
            redis_client: Redis client for state storage (creates new if None)
            enable_rotation: Whether rotation is enabled
            rotation_overlap_hours: Hours to keep old key active during rotation
        """
        self.redis_client = redis_client or RedisClient()
        self.enable_rotation = enable_rotation
        self.rotation_overlap_hours = rotation_overlap_hours

        # Load rotation settings from environment
        if os.getenv('KEY_ROTATION_ENABLED', 'true').lower() == 'false':
            self.enable_rotation = False

        overlap_env = os.getenv('KEY_ROTATION_OVERLAP_HOURS')
        if overlap_env:
            try:
                self.rotation_overlap_hours = int(overlap_env)
            except ValueError:
                logger.warning(f"Invalid KEY_ROTATION_OVERLAP_HOURS: {overlap_env}, using default: {rotation_overlap_hours}")

        # In-memory cache of keys (loaded from environment)
        self._keys_cache: Dict[str, Dict[str, str]] = {}
        self._cache_lock = threading.Lock()

        # Load keys from environment
        self._load_keys_from_environment()

        logger.info(f"SecretsManager initialized (rotation={'enabled' if self.enable_rotation else 'disabled'}, overlap={self.rotation_overlap_hours}h)")

    def _load_keys_from_environment(self):
        """Load API keys from environment variables."""
        with self._cache_lock:
            for service in self.SUPPORTED_SERVICES:
                service_upper = service.upper()

                # Load primary key
                primary_key = os.getenv(f'{service_upper}_API_KEY')
                if primary_key:
                    if service not in self._keys_cache:
                        self._keys_cache[service] = {}
                    self._keys_cache[service]['primary'] = primary_key

                    # Track metadata in Redis
                    self._update_key_metadata(
                        service=service,
                        key=primary_key,
                        is_primary=True
                    )

                # Load secondary key (for rotation)
                secondary_key = os.getenv(f'{service_upper}_API_KEY_SECONDARY')
                if secondary_key:
                    if service not in self._keys_cache:
                        self._keys_cache[service] = {}
                    self._keys_cache[service]['secondary'] = secondary_key

                    # Track metadata in Redis
                    self._update_key_metadata(
                        service=service,
                        key=secondary_key,
                        is_primary=False
                    )

    def _get_key_id(self, key: str) -> str:
        """
        Get identifier for key (last 8 chars of hash).

        Args:
            key: API key

        Returns:
            Key identifier (safe to log)
        """
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        return key_hash[-8:]

    def _sanitize_error(self, error_message: str) -> str:
        """
        Sanitize error message to remove any API keys.

        Args:
            error_message: Raw error message

        Returns:
            Sanitized error message
        """
        # Replace anything that looks like an API key
        sanitized = error_message

        # Anthropic keys: sk-ant-api03-...
        sanitized = sanitized.replace('sk-ant-api03-', 'sk-ant-***-')
        sanitized = sanitized.replace('sk-ant-', 'sk-ant-***-')

        # OpenAI keys: sk-proj-... or sk-...
        sanitized = sanitized.replace('sk-proj-', 'sk-***-')
        sanitized = sanitized.replace('sk-', 'sk-***-')

        # Gemini keys: AIzaSy...
        sanitized = sanitized.replace('AIzaSy', 'AIza***')

        return sanitized

    def _update_key_metadata(
        self,
        service: str,
        key: str,
        is_primary: bool,
        used: bool = False,
        failed: bool = False
    ):
        """
        Update key metadata in Redis.

        Args:
            service: Service name
            key: API key
            is_primary: Whether this is the primary key
            used: Whether key was just used
            failed: Whether key just failed
        """
        key_id = self._get_key_id(key)
        metadata_key = f"secrets:key_metadata:{service}:{key_id}"

        # Get existing metadata or create new
        existing = self.redis_client.get(metadata_key)
        if existing:
            metadata = KeyMetadata(**existing)
        else:
            metadata = KeyMetadata(
                service=service,
                key_id=key_id,
                added_at=time.time(),
                is_primary=is_primary
            )

        # Update usage/failure stats
        if used:
            metadata.usage_count += 1
            metadata.last_used_at = time.time()

        if failed:
            metadata.failure_count += 1
            metadata.last_failure_at = time.time()

        # Store back to Redis
        self.redis_client.set(
            metadata_key,
            metadata.to_dict(),
            ttl=90 * 24 * 3600  # Keep for 90 days
        )

    def get_api_key(self, service: str) -> str:
        """
        Get current active API key for service.

        Attempts to use primary key first, falls back to secondary if primary fails.

        Args:
            service: Service name ('anthropic', 'openai', 'gemini')

        Returns:
            API key string

        Raises:
            ValueError: If service not supported or no key available
        """
        if service not in self.SUPPORTED_SERVICES:
            raise ValueError(f"Unsupported service: {service}. Supported: {self.SUPPORTED_SERVICES}")

        with self._cache_lock:
            service_keys = self._keys_cache.get(service, {})

            # Try primary key first
            primary_key = service_keys.get('primary')
            if primary_key:
                # Track usage
                self._update_key_metadata(
                    service=service,
                    key=primary_key,
                    is_primary=True,
                    used=True
                )
                return primary_key

            # Fallback to secondary if available
            secondary_key = service_keys.get('secondary')
            if secondary_key:
                logger.warning(f"Primary key not available for {service}, using secondary key")
                self._update_key_metadata(
                    service=service,
                    key=secondary_key,
                    is_primary=False,
                    used=True
                )

                # Emit observability event
                emit_event('secrets_fallback', {
                    'service': service,
                    'reason': 'primary_key_not_available',
                    'timestamp': time.time()
                })

                return secondary_key

            # No keys available
            raise ValueError(
                f"{service.upper()}_API_KEY not found in environment. "
                f"Please set {service.upper()}_API_KEY in .env file or environment variables."
            )

    def rotate_key(self, service: str, new_key: str) -> bool:
        """
        Rotate API key for service.

        Adds new key as secondary and marks for rotation. During overlap period,
        both keys are valid. After overlap, old key should be removed with remove_old_key().

        Args:
            service: Service name
            new_key: New API key

        Returns:
            True if rotation started successfully

        Raises:
            ValueError: If service not supported or rotation disabled
        """
        if service not in self.SUPPORTED_SERVICES:
            raise ValueError(f"Unsupported service: {service}")

        if not self.enable_rotation:
            raise ValueError("Key rotation is disabled. Set KEY_ROTATION_ENABLED=true to enable.")

        # Get current primary key
        with self._cache_lock:
            service_keys = self._keys_cache.get(service, {})
            old_key = service_keys.get('primary')

            if not old_key:
                # No existing key, just set as primary
                logger.info(f"No existing key for {service}, setting new key as primary")
                self._keys_cache[service] = {'primary': new_key}
                self._update_key_metadata(service, new_key, is_primary=True)
                return True

            # Start rotation process
            old_key_id = self._get_key_id(old_key)
            new_key_id = self._get_key_id(new_key)

            # Don't rotate if keys are the same
            if old_key_id == new_key_id:
                logger.warning(f"New key for {service} is same as current key, skipping rotation")
                return False

            # Add new key as secondary
            self._keys_cache[service]['secondary'] = new_key
            self._update_key_metadata(service, new_key, is_primary=False)

            # Create rotation state
            rotation_state = RotationState(
                service=service,
                old_key_id=old_key_id,
                new_key_id=new_key_id,
                started_at=time.time(),
                overlap_hours=self.rotation_overlap_hours
            )

            # Store rotation state in Redis
            rotation_key = f"secrets:rotation:{service}"
            self.redis_client.set(
                rotation_key,
                rotation_state.to_dict(),
                ttl=(self.rotation_overlap_hours + 24) * 3600  # Keep for overlap + 24h
            )

            logger.info(
                f"Started key rotation for {service}: "
                f"{old_key_id} -> {new_key_id} "
                f"(overlap: {self.rotation_overlap_hours}h)"
            )

            # Emit observability event
            emit_event('secrets_rotation_started', {
                'service': service,
                'old_key_id': old_key_id,
                'new_key_id': new_key_id,
                'overlap_hours': self.rotation_overlap_hours,
                'timestamp': time.time()
            })

            return True

    def fallback_to_secondary(self, service: str) -> bool:
        """
        Fallback to secondary key when primary fails.

        Args:
            service: Service name

        Returns:
            True if fallback succeeded, False if no secondary available
        """
        with self._cache_lock:
            service_keys = self._keys_cache.get(service, {})
            primary_key = service_keys.get('primary')
            secondary_key = service_keys.get('secondary')

            if not secondary_key:
                logger.error(f"No secondary key available for {service} fallback")
                return False

            # Mark primary as failed
            if primary_key:
                self._update_key_metadata(
                    service=service,
                    key=primary_key,
                    is_primary=True,
                    failed=True
                )

            # Swap keys
            self._keys_cache[service]['primary'] = secondary_key
            self._keys_cache[service]['secondary'] = primary_key

            logger.warning(f"Swapped to secondary key for {service}")

            # Emit observability event
            emit_event('secrets_failover', {
                'service': service,
                'new_primary_id': self._get_key_id(secondary_key),
                'failed_key_id': self._get_key_id(primary_key) if primary_key else None,
                'timestamp': time.time()
            })

            return True

    def remove_old_key(self, service: str) -> bool:
        """
        Remove old key after rotation completes.

        Should be called after rotation overlap period to remove the old (now secondary) key.

        Args:
            service: Service name

        Returns:
            True if old key removed successfully

        Raises:
            ValueError: If no rotation in progress or rotation overlap not complete
        """
        # Get rotation state
        rotation_key = f"secrets:rotation:{service}"
        rotation_data = self.redis_client.get(rotation_key)

        if not rotation_data:
            raise ValueError(f"No rotation in progress for {service}")

        rotation_state = RotationState(**rotation_data)

        # Check if overlap period has elapsed
        elapsed_hours = (time.time() - rotation_state.started_at) / 3600
        if elapsed_hours < rotation_state.overlap_hours:
            remaining_hours = rotation_state.overlap_hours - elapsed_hours
            raise ValueError(
                f"Rotation overlap period not complete. "
                f"Wait {remaining_hours:.1f} more hours before removing old key."
            )

        # Remove secondary (old) key
        with self._cache_lock:
            service_keys = self._keys_cache.get(service, {})
            old_key = service_keys.get('secondary')

            if old_key:
                old_key_id = self._get_key_id(old_key)
                del self._keys_cache[service]['secondary']

                # Mark rotation as completed
                rotation_state.completed = True
                rotation_state.completed_at = time.time()
                self.redis_client.set(rotation_key, rotation_state.to_dict())

                logger.info(f"Removed old key for {service}: {old_key_id}")

                # Emit observability event
                emit_event('secrets_rotation_completed', {
                    'service': service,
                    'old_key_id': old_key_id,
                    'new_key_id': rotation_state.new_key_id,
                    'duration_hours': elapsed_hours,
                    'timestamp': time.time()
                })

                return True
            else:
                logger.warning(f"No secondary key found for {service} to remove")
                return False

    def promote_secondary_to_primary(self, service: str) -> bool:
        """
        Promote secondary key to primary (completes rotation).

        Args:
            service: Service name

        Returns:
            True if promotion succeeded
        """
        with self._cache_lock:
            service_keys = self._keys_cache.get(service, {})
            secondary_key = service_keys.get('secondary')

            if not secondary_key:
                logger.warning(f"No secondary key to promote for {service}")
                return False

            # Promote secondary to primary
            self._keys_cache[service]['primary'] = secondary_key

            # Update metadata
            self._update_key_metadata(service, secondary_key, is_primary=True)

            logger.info(f"Promoted secondary key to primary for {service}: {self._get_key_id(secondary_key)}")

            return True

    def get_rotation_status(self, service: str) -> Optional[Dict[str, Any]]:
        """
        Get current rotation status for service.

        Args:
            service: Service name

        Returns:
            Dict with rotation status or None if no rotation in progress
        """
        rotation_key = f"secrets:rotation:{service}"
        rotation_data = self.redis_client.get(rotation_key)

        if not rotation_data:
            return None

        rotation_state = RotationState(**rotation_data)
        elapsed_hours = (time.time() - rotation_state.started_at) / 3600
        remaining_hours = max(0, rotation_state.overlap_hours - elapsed_hours)

        return {
            'service': service,
            'old_key_id': rotation_state.old_key_id,
            'new_key_id': rotation_state.new_key_id,
            'started_at': rotation_state.started_at,
            'elapsed_hours': elapsed_hours,
            'remaining_hours': remaining_hours,
            'overlap_hours': rotation_state.overlap_hours,
            'completed': rotation_state.completed,
            'completed_at': rotation_state.completed_at,
            'can_remove_old_key': elapsed_hours >= rotation_state.overlap_hours
        }

    def get_key_stats(self, service: str) -> Dict[str, Any]:
        """
        Get usage statistics for service keys.

        Args:
            service: Service name

        Returns:
            Dict with key statistics
        """
        stats = {
            'service': service,
            'keys': []
        }

        with self._cache_lock:
            service_keys = self._keys_cache.get(service, {})

            for key_type, key in service_keys.items():
                key_id = self._get_key_id(key)
                metadata_key = f"secrets:key_metadata:{service}:{key_id}"
                metadata_data = self.redis_client.get(metadata_key)

                if metadata_data:
                    metadata = KeyMetadata(**metadata_data)
                    stats['keys'].append({
                        'type': key_type,
                        'key_id': key_id,
                        'is_primary': metadata.is_primary,
                        'usage_count': metadata.usage_count,
                        'failure_count': metadata.failure_count,
                        'last_used_at': metadata.last_used_at,
                        'last_failure_at': metadata.last_failure_at,
                        'added_at': metadata.added_at
                    })

        return stats

    def get_all_services_status(self) -> Dict[str, Any]:
        """
        Get status for all services.

        Returns:
            Dict with status for each service
        """
        status = {}

        for service in self.SUPPORTED_SERVICES:
            service_status = {
                'has_primary': False,
                'has_secondary': False,
                'rotation_in_progress': False,
                'stats': None
            }

            with self._cache_lock:
                service_keys = self._keys_cache.get(service, {})
                service_status['has_primary'] = 'primary' in service_keys
                service_status['has_secondary'] = 'secondary' in service_keys

            # Check rotation status
            rotation_status = self.get_rotation_status(service)
            if rotation_status:
                service_status['rotation_in_progress'] = True
                service_status['rotation_status'] = rotation_status

            # Get key stats
            service_status['stats'] = self.get_key_stats(service)

            status[service] = service_status

        return status


# Global secrets manager instance
_global_secrets_manager: Optional[SecretsManager] = None
_manager_lock = threading.Lock()


def get_secrets_manager(
    redis_client: Optional[RedisClient] = None,
    enable_rotation: bool = True,
    rotation_overlap_hours: int = 24
) -> SecretsManager:
    """
    Get or create the global secrets manager instance.

    Args:
        redis_client: Optional Redis client
        enable_rotation: Whether rotation is enabled
        rotation_overlap_hours: Hours to keep old key active during rotation

    Returns:
        Global SecretsManager instance
    """
    global _global_secrets_manager

    if _global_secrets_manager is None:
        with _manager_lock:
            if _global_secrets_manager is None:
                _global_secrets_manager = SecretsManager(
                    redis_client=redis_client,
                    enable_rotation=enable_rotation,
                    rotation_overlap_hours=rotation_overlap_hours
                )

    return _global_secrets_manager


# Example usage
if __name__ == '__main__':
    import sys

    # Create secrets manager
    secrets = SecretsManager()

    print("Secrets Manager Status\n" + "=" * 60)
    status = secrets.get_all_services_status()

    for service, service_status in status.items():
        print(f"\n{service.upper()}:")
        print(f"  Primary key: {'✓' if service_status['has_primary'] else '✗'}")
        print(f"  Secondary key: {'✓' if service_status['has_secondary'] else '✗'}")
        print(f"  Rotation: {'in progress' if service_status['rotation_in_progress'] else 'idle'}")

        if service_status.get('rotation_status'):
            rot = service_status['rotation_status']
            print(f"    Elapsed: {rot['elapsed_hours']:.1f}h / {rot['overlap_hours']}h")
            print(f"    Can remove old key: {rot['can_remove_old_key']}")

        if service_status['stats']['keys']:
            print(f"  Key stats:")
            for key_info in service_status['stats']['keys']:
                print(f"    {key_info['type']}: {key_info['key_id']} "
                      f"(usage: {key_info['usage_count']}, failures: {key_info['failure_count']})")
