"""
Rate Limiter for SuperAgent API Calls

Implements distributed rate limiting using Redis and token bucket algorithm.
Prevents quota exhaustion and handles 429 rate limit errors gracefully.

Features:
- Token bucket algorithm for smooth rate limiting
- Per-service rate limits (Anthropic, OpenAI, Gemini)
- Per-model rate limits (Haiku, Sonnet, Gemini 2.5 Pro)
- Redis-based distributed rate limiting
- Automatic backoff and retry with jitter
- Integration with error_recovery.py
- Graceful degradation when Redis unavailable
"""
import time
import logging
import os
import random
import functools
from typing import Optional, Dict, Any, Callable, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from agent_system.state.redis_client import RedisClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RateLimitService(Enum):
    """API service types."""
    ANTHROPIC = 'anthropic'
    OPENAI = 'openai'
    GEMINI = 'gemini'


class RateLimitModel(Enum):
    """Model-specific rate limit keys."""
    # Anthropic models
    CLAUDE_HAIKU = 'claude-haiku-3.5'
    CLAUDE_SONNET = 'claude-sonnet-4.5'
    CLAUDE_OPUS = 'claude-opus-4.0'

    # OpenAI models
    GPT4_REALTIME = 'gpt-4o-realtime-preview'
    GPT4_TURBO = 'gpt-4-turbo'

    # Gemini models
    GEMINI_PRO = 'gemini-2.5-pro'


@dataclass
class RateLimitConfig:
    """
    Rate limit configuration for a service or model.

    Uses token bucket algorithm:
    - bucket_capacity: Maximum number of tokens (requests)
    - refill_rate: Tokens added per second
    - cost_per_request: Number of tokens consumed per request
    """
    bucket_capacity: int  # Max tokens in bucket
    refill_rate: float  # Tokens per second
    cost_per_request: int = 1  # Tokens consumed per request

    @property
    def requests_per_minute(self) -> float:
        """Calculate effective RPM from refill rate."""
        return self.refill_rate * 60

    @classmethod
    def from_rpm(cls, rpm: int, cost_per_request: int = 1) -> 'RateLimitConfig':
        """
        Create config from requests per minute.

        Args:
            rpm: Requests per minute
            cost_per_request: Tokens consumed per request

        Returns:
            RateLimitConfig instance
        """
        refill_rate = rpm / 60.0  # Convert to requests per second
        bucket_capacity = max(rpm // 4, 10)  # Allow bursts of ~25% of RPM

        return cls(
            bucket_capacity=bucket_capacity,
            refill_rate=refill_rate,
            cost_per_request=cost_per_request
        )


# Default rate limit configurations per service
# Based on typical API tier limits (conservative defaults)
DEFAULT_SERVICE_LIMITS = {
    RateLimitService.ANTHROPIC: RateLimitConfig.from_rpm(
        rpm=int(os.getenv('RATE_LIMIT_ANTHROPIC_RPM', '50'))
    ),
    RateLimitService.OPENAI: RateLimitConfig.from_rpm(
        rpm=int(os.getenv('RATE_LIMIT_OPENAI_RPM', '60'))
    ),
    RateLimitService.GEMINI: RateLimitConfig.from_rpm(
        rpm=int(os.getenv('RATE_LIMIT_GEMINI_RPM', '150'))
    ),
}

# Model-specific rate limits (override service limits if specified)
DEFAULT_MODEL_LIMITS = {
    RateLimitModel.CLAUDE_HAIKU: RateLimitConfig.from_rpm(50),
    RateLimitModel.CLAUDE_SONNET: RateLimitConfig.from_rpm(50),
    RateLimitModel.CLAUDE_OPUS: RateLimitConfig.from_rpm(50),
    RateLimitModel.GPT4_REALTIME: RateLimitConfig.from_rpm(60),
    RateLimitModel.GPT4_TURBO: RateLimitConfig.from_rpm(60),
    RateLimitModel.GEMINI_PRO: RateLimitConfig.from_rpm(150),
}


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""
    def __init__(self, message: str, retry_after_seconds: float):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class TokenBucket:
    """
    Token bucket algorithm implementation for rate limiting.

    The token bucket algorithm allows for burst traffic while maintaining
    an average rate limit. Tokens are added to the bucket at a fixed rate,
    and each request consumes tokens. If insufficient tokens are available,
    the request is rate limited.

    Redis storage format:
    - Key: rate_limit:{service}:{model}
    - Value: JSON with {tokens: float, last_refill: timestamp}
    """

    def __init__(
        self,
        redis_client: RedisClient,
        key: str,
        config: RateLimitConfig,
        ttl: int = 3600
    ):
        """
        Initialize token bucket.

        Args:
            redis_client: Redis client instance
            key: Redis key for this bucket
            config: Rate limit configuration
            ttl: Time to live for Redis key (seconds)
        """
        self.redis = redis_client
        self.key = f"rate_limit:{key}"
        self.config = config
        self.ttl = ttl

        # In-memory fallback (when Redis unavailable)
        self._fallback_tokens = float(config.bucket_capacity)
        self._fallback_last_refill = time.time()

    def _refill_tokens(self, current_tokens: float, last_refill: float) -> Tuple[float, float]:
        """
        Calculate refilled token count.

        Args:
            current_tokens: Current token count
            last_refill: Last refill timestamp

        Returns:
            Tuple of (new_tokens, current_time)
        """
        now = time.time()
        elapsed = now - last_refill

        # Add tokens based on elapsed time and refill rate
        new_tokens = min(
            self.config.bucket_capacity,
            current_tokens + (elapsed * self.config.refill_rate)
        )

        return new_tokens, now

    def consume(self, tokens: int = 1) -> Tuple[bool, float]:
        """
        Attempt to consume tokens from bucket.

        Args:
            tokens: Number of tokens to consume

        Returns:
            Tuple of (success: bool, retry_after_seconds: float)
            - success: True if tokens consumed, False if rate limited
            - retry_after_seconds: Time to wait before retrying (if rate limited)
        """
        try:
            # Get current bucket state from Redis
            bucket_data = self.redis.get(self.key)

            if bucket_data is None:
                # Initialize new bucket
                current_tokens = float(self.config.bucket_capacity)
                last_refill = time.time()
            else:
                current_tokens = float(bucket_data.get('tokens', self.config.bucket_capacity))
                last_refill = float(bucket_data.get('last_refill', time.time()))

            # Refill tokens based on elapsed time
            current_tokens, now = self._refill_tokens(current_tokens, last_refill)

            # Check if enough tokens available
            if current_tokens >= tokens:
                # Consume tokens
                new_tokens = current_tokens - tokens

                # Update Redis
                self.redis.set(
                    self.key,
                    {'tokens': new_tokens, 'last_refill': now},
                    ttl=self.ttl
                )

                logger.debug(
                    f"Rate limit OK: {self.key} consumed {tokens} tokens "
                    f"({new_tokens:.2f}/{self.config.bucket_capacity} remaining)"
                )

                return True, 0.0
            else:
                # Rate limited - calculate retry time
                tokens_needed = tokens - current_tokens
                retry_after = tokens_needed / self.config.refill_rate

                logger.warning(
                    f"Rate limit exceeded: {self.key} needs {tokens_needed:.2f} more tokens. "
                    f"Retry after {retry_after:.2f}s"
                )

                return False, retry_after

        except Exception as e:
            logger.warning(f"Redis error in token bucket, using in-memory fallback: {e}")

            # Fallback to in-memory bucket
            self._fallback_tokens, now = self._refill_tokens(
                self._fallback_tokens,
                self._fallback_last_refill
            )

            if self._fallback_tokens >= tokens:
                self._fallback_tokens -= tokens
                self._fallback_last_refill = now
                return True, 0.0
            else:
                tokens_needed = tokens - self._fallback_tokens
                retry_after = tokens_needed / self.config.refill_rate
                return False, retry_after

    def get_status(self) -> Dict[str, Any]:
        """
        Get current bucket status.

        Returns:
            Dict with tokens, capacity, and refill rate
        """
        try:
            bucket_data = self.redis.get(self.key)

            if bucket_data is None:
                return {
                    'tokens': self.config.bucket_capacity,
                    'capacity': self.config.bucket_capacity,
                    'refill_rate': self.config.refill_rate,
                    'rpm': self.config.requests_per_minute
                }

            current_tokens = float(bucket_data.get('tokens', self.config.bucket_capacity))
            last_refill = float(bucket_data.get('last_refill', time.time()))

            # Refill to get current count
            current_tokens, _ = self._refill_tokens(current_tokens, last_refill)

            return {
                'tokens': current_tokens,
                'capacity': self.config.bucket_capacity,
                'refill_rate': self.config.refill_rate,
                'rpm': self.config.requests_per_minute,
                'utilization': 1.0 - (current_tokens / self.config.bucket_capacity)
            }
        except Exception as e:
            logger.warning(f"Failed to get bucket status: {e}")
            return {
                'tokens': self._fallback_tokens,
                'capacity': self.config.bucket_capacity,
                'refill_rate': self.config.refill_rate,
                'rpm': self.config.requests_per_minute,
                'fallback': True
            }


class RateLimiter:
    """
    Distributed rate limiter with Redis backend.

    Manages rate limits for multiple services and models, using token bucket
    algorithm for smooth rate limiting with burst support.

    Example usage:
        rate_limiter = RateLimiter()

        # Wrap API call
        @rate_limiter.limit(service='anthropic', model='claude-sonnet-4.5')
        def call_claude_api():
            # API call here
            pass
    """

    def __init__(
        self,
        redis_client: Optional[RedisClient] = None,
        enabled: bool = True
    ):
        """
        Initialize rate limiter.

        Args:
            redis_client: Optional Redis client (creates new if not provided)
            enabled: Enable/disable rate limiting (default: True)
        """
        self.redis = redis_client or RedisClient()
        self.enabled = enabled and os.getenv('RATE_LIMIT_ENABLED', 'true').lower() == 'true'

        # Cache of token buckets
        self._buckets: Dict[str, TokenBucket] = {}

        logger.info(f"RateLimiter initialized: enabled={self.enabled}")

    def _get_bucket(
        self,
        service: str,
        model: Optional[str] = None
    ) -> TokenBucket:
        """
        Get or create token bucket for service/model.

        Args:
            service: Service name (anthropic, openai, gemini)
            model: Optional model name for model-specific limits

        Returns:
            TokenBucket instance
        """
        # Create unique key
        key = f"{service}:{model}" if model else service

        # Check cache
        if key in self._buckets:
            return self._buckets[key]

        # Determine config
        config = None

        # Try model-specific limit first
        if model:
            try:
                model_enum = RateLimitModel(model)
                config = DEFAULT_MODEL_LIMITS.get(model_enum)
            except ValueError:
                pass

        # Fall back to service limit
        if config is None:
            try:
                service_enum = RateLimitService(service)
                config = DEFAULT_SERVICE_LIMITS.get(service_enum)
            except ValueError:
                # Unknown service - use conservative default
                config = RateLimitConfig.from_rpm(30)
                logger.warning(f"Unknown service '{service}', using default rate limit")

        # Create bucket
        bucket = TokenBucket(self.redis, key, config)
        self._buckets[key] = bucket

        return bucket

    def check_limit(
        self,
        service: str,
        model: Optional[str] = None,
        cost: int = 1
    ) -> Tuple[bool, float]:
        """
        Check if request is within rate limit.

        Args:
            service: Service name (anthropic, openai, gemini)
            model: Optional model name
            cost: Number of tokens to consume (default: 1)

        Returns:
            Tuple of (allowed: bool, retry_after: float)
        """
        if not self.enabled:
            return True, 0.0

        bucket = self._get_bucket(service, model)
        return bucket.consume(cost)

    def wait_for_capacity(
        self,
        service: str,
        model: Optional[str] = None,
        cost: int = 1,
        max_wait: float = 60.0
    ) -> bool:
        """
        Wait for rate limit capacity to become available.

        Args:
            service: Service name
            model: Optional model name
            cost: Number of tokens needed
            max_wait: Maximum time to wait in seconds

        Returns:
            True if capacity acquired, False if max_wait exceeded
        """
        if not self.enabled:
            return True

        start_time = time.time()

        while True:
            allowed, retry_after = self.check_limit(service, model, cost)

            if allowed:
                return True

            elapsed = time.time() - start_time
            if elapsed + retry_after > max_wait:
                logger.error(
                    f"Rate limit wait timeout: would exceed max_wait={max_wait}s"
                )
                return False

            # Wait with jitter to avoid thundering herd
            jitter = random.uniform(0, 0.1 * retry_after)
            wait_time = retry_after + jitter

            logger.info(
                f"Rate limited: waiting {wait_time:.2f}s for {service}:{model}"
            )
            time.sleep(wait_time)

    def limit(
        self,
        service: str,
        model: Optional[str] = None,
        cost: int = 1,
        max_wait: float = 60.0,
        handle_429: bool = True
    ):
        """
        Decorator to rate limit API calls.

        Args:
            service: Service name (anthropic, openai, gemini)
            model: Optional model name
            cost: Number of tokens per request
            max_wait: Maximum time to wait for capacity
            handle_429: Automatically handle 429 errors with backoff

        Example:
            @rate_limiter.limit(service='anthropic', model='claude-sonnet-4.5')
            def call_claude_api():
                # API call here
                pass
        """
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                # Skip if disabled
                if not self.enabled:
                    return func(*args, **kwargs)

                # Wait for capacity
                if not self.wait_for_capacity(service, model, cost, max_wait):
                    raise RateLimitExceeded(
                        f"Rate limit exceeded for {service}:{model}. "
                        f"Could not acquire capacity within {max_wait}s",
                        retry_after_seconds=max_wait
                    )

                # Execute function with 429 handling
                if handle_429:
                    return self._execute_with_429_handling(
                        func, service, model, *args, **kwargs
                    )
                else:
                    return func(*args, **kwargs)

            return wrapper
        return decorator

    def _execute_with_429_handling(
        self,
        func: Callable,
        service: str,
        model: Optional[str],
        *args,
        **kwargs
    ) -> Any:
        """
        Execute function with automatic 429 error handling.

        Args:
            func: Function to execute
            service: Service name
            model: Model name
            *args, **kwargs: Function arguments

        Returns:
            Function result

        Raises:
            Original exception if not 429 or retry failed
        """
        max_retries = 3
        base_delay = 2.0

        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)

            except Exception as e:
                # Check if 429 rate limit error
                error_str = str(e).lower()
                is_429 = (
                    '429' in error_str or
                    'rate limit' in error_str or
                    'too many requests' in error_str
                )

                if not is_429 or attempt == max_retries - 1:
                    # Not a 429 or final attempt - re-raise
                    raise

                # Extract retry-after from error if available
                retry_after = self._extract_retry_after(e)

                if retry_after is None:
                    # Use exponential backoff
                    retry_after = base_delay * (2 ** attempt)

                # Add jitter
                jitter = random.uniform(0, 0.25 * retry_after)
                wait_time = retry_after + jitter

                logger.warning(
                    f"429 rate limit from {service}:{model} on attempt {attempt + 1}. "
                    f"Retrying in {wait_time:.2f}s"
                )

                # Emit observability event
                self._emit_rate_limit_event(service, model, attempt, wait_time)

                time.sleep(wait_time)

        # Should not reach here
        raise RateLimitExceeded(
            f"Failed after {max_retries} attempts due to 429 errors",
            retry_after_seconds=0
        )

    def _extract_retry_after(self, error: Exception) -> Optional[float]:
        """
        Extract retry-after value from error.

        Args:
            error: Exception from API call

        Returns:
            Retry-after seconds or None if not found
        """
        # Try to extract from error message
        error_str = str(error)

        # Look for "retry after X seconds" pattern
        import re
        match = re.search(r'retry.*?(\d+(?:\.\d+)?)\s*(?:second|sec|s)', error_str, re.IGNORECASE)
        if match:
            return float(match.group(1))

        # Check if error has retry_after attribute (some SDKs)
        if hasattr(error, 'retry_after'):
            return float(error.retry_after)

        return None

    def _emit_rate_limit_event(
        self,
        service: str,
        model: Optional[str],
        attempt: int,
        wait_time: float
    ):
        """Emit rate limit event to observability system."""
        try:
            from agent_system.observability.event_stream import emit_event
            emit_event('rate_limit_429', {
                'service': service,
                'model': model,
                'attempt': attempt,
                'wait_time': wait_time,
                'timestamp': time.time()
            })
        except Exception as e:
            logger.warning(f"Failed to emit rate limit event: {e}")

    def get_status(self, service: Optional[str] = None) -> Dict[str, Any]:
        """
        Get rate limit status for service(s).

        Args:
            service: Optional service name (None = all services)

        Returns:
            Dict with status for each bucket
        """
        if service:
            # Single service
            buckets_to_check = {
                k: v for k, v in self._buckets.items()
                if k.startswith(service)
            }
        else:
            # All services
            buckets_to_check = self._buckets

        status = {}
        for key, bucket in buckets_to_check.items():
            status[key] = bucket.get_status()

        return {
            'enabled': self.enabled,
            'buckets': status
        }

    def reset(self, service: Optional[str] = None):
        """
        Reset rate limits (useful for testing).

        Args:
            service: Optional service name (None = reset all)
        """
        if service:
            # Reset specific service
            keys_to_reset = [k for k in self._buckets.keys() if k.startswith(service)]
            for key in keys_to_reset:
                del self._buckets[key]
                self.redis.delete(f"rate_limit:{key}")
        else:
            # Reset all
            for key in self._buckets.keys():
                self.redis.delete(f"rate_limit:{key}")
            self._buckets.clear()

        logger.info(f"Rate limits reset: service={service or 'all'}")


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """
    Get global rate limiter instance (singleton).

    Returns:
        RateLimiter instance
    """
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


# Convenience decorators for each service
def limit_anthropic(model: Optional[str] = None, cost: int = 1):
    """Rate limit Anthropic API calls."""
    return get_rate_limiter().limit(
        service='anthropic',
        model=model,
        cost=cost
    )


def limit_openai(model: Optional[str] = None, cost: int = 1):
    """Rate limit OpenAI API calls."""
    return get_rate_limiter().limit(
        service='openai',
        model=model,
        cost=cost
    )


def limit_gemini(model: Optional[str] = None, cost: int = 1):
    """Rate limit Gemini API calls."""
    return get_rate_limiter().limit(
        service='gemini',
        model=model,
        cost=cost
    )


# Example usage and testing
if __name__ == '__main__':
    import sys

    # Test rate limiter
    limiter = RateLimiter()

    print("Rate Limiter Test")
    print("=" * 50)

    # Test 1: Basic rate limiting
    print("\nTest 1: Basic rate limiting")

    @limiter.limit(service='anthropic', model='claude-haiku-3.5')
    def test_api_call(i: int):
        print(f"  API call {i} succeeded")
        return f"result_{i}"

    for i in range(5):
        try:
            result = test_api_call(i)
        except RateLimitExceeded as e:
            print(f"  API call {i} rate limited: {e}")

    # Test 2: Status check
    print("\nTest 2: Rate limit status")
    status = limiter.get_status('anthropic')
    print(f"  Status: {status}")

    # Test 3: Manual check
    print("\nTest 3: Manual rate limit check")
    allowed, retry_after = limiter.check_limit('gemini', 'gemini-2.5-pro')
    print(f"  Allowed: {allowed}, Retry after: {retry_after}s")

    print("\nRate limiter tests completed successfully")
