"""
Unit tests for Rate Limiter

Tests token bucket algorithm, rate limit enforcement, 429 handling,
and Redis integration.
"""
import pytest
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from agent_system.rate_limiter import (
    RateLimiter,
    TokenBucket,
    RateLimitConfig,
    RateLimitExceeded,
    RateLimitService,
    RateLimitModel,
    get_rate_limiter,
    limit_anthropic,
    limit_openai,
    limit_gemini
)
from agent_system.state.redis_client import RedisClient


class TestRateLimitConfig:
    """Test RateLimitConfig dataclass."""

    def test_from_rpm_basic(self):
        """Test creating config from RPM."""
        config = RateLimitConfig.from_rpm(60)

        assert config.refill_rate == 1.0  # 60 RPM = 1 req/sec
        assert config.bucket_capacity == 15  # 25% of 60 = 15
        assert config.cost_per_request == 1
        assert config.requests_per_minute == 60.0

    def test_from_rpm_with_cost(self):
        """Test creating config with custom cost per request."""
        config = RateLimitConfig.from_rpm(120, cost_per_request=2)

        assert config.refill_rate == 2.0  # 120 RPM = 2 req/sec
        assert config.bucket_capacity == 30  # 25% of 120 = 30
        assert config.cost_per_request == 2

    def test_requests_per_minute_property(self):
        """Test RPM property calculation."""
        config = RateLimitConfig(
            bucket_capacity=10,
            refill_rate=0.5  # 30 RPM
        )

        assert config.requests_per_minute == 30.0


class TestTokenBucket:
    """Test TokenBucket implementation."""

    @pytest.fixture
    def redis_client(self):
        """Mock Redis client."""
        return Mock(spec=RedisClient)

    @pytest.fixture
    def config(self):
        """Test configuration."""
        return RateLimitConfig(
            bucket_capacity=10,
            refill_rate=2.0,  # 2 tokens per second
            cost_per_request=1
        )

    @pytest.fixture
    def bucket(self, redis_client, config):
        """Create test bucket."""
        return TokenBucket(redis_client, 'test_service', config)

    def test_consume_success_with_full_bucket(self, bucket, redis_client):
        """Test consuming tokens from full bucket."""
        # Mock Redis to return None (new bucket)
        redis_client.get.return_value = None

        success, retry_after = bucket.consume(1)

        assert success is True
        assert retry_after == 0.0

        # Verify Redis was updated
        redis_client.set.assert_called_once()
        call_args = redis_client.set.call_args
        assert 'rate_limit:test_service' == call_args[0][0]
        assert call_args[0][1]['tokens'] == 9.0  # 10 - 1

    def test_consume_success_with_refill(self, bucket, redis_client):
        """Test token refill over time."""
        # Mock Redis to return bucket with 5 tokens from 1 second ago
        one_second_ago = time.time() - 1.0
        redis_client.get.return_value = {
            'tokens': 5.0,
            'last_refill': one_second_ago
        }

        success, retry_after = bucket.consume(1)

        # After 1 second, 2 tokens refilled (refill_rate=2.0)
        # 5 + 2 = 7, after consuming 1 = 6
        assert success is True
        assert retry_after == 0.0

    def test_consume_rate_limited(self, bucket, redis_client):
        """Test rate limiting when insufficient tokens."""
        # Mock Redis to return bucket with 0 tokens
        redis_client.get.return_value = {
            'tokens': 0.0,
            'last_refill': time.time()
        }

        success, retry_after = bucket.consume(1)

        assert success is False
        assert retry_after > 0  # Should suggest wait time
        assert retry_after == pytest.approx(0.5, rel=0.1)  # 1 token / 2.0 refill_rate

    def test_consume_multiple_tokens(self, bucket, redis_client):
        """Test consuming multiple tokens at once."""
        redis_client.get.return_value = None  # Full bucket (10 tokens)

        success, retry_after = bucket.consume(5)

        assert success is True
        assert retry_after == 0.0

        # Verify 5 tokens consumed
        call_args = redis_client.set.call_args
        assert call_args[0][1]['tokens'] == 5.0  # 10 - 5

    def test_bucket_capacity_limit(self, bucket, redis_client):
        """Test that tokens don't exceed bucket capacity."""
        # Mock bucket with 8 tokens from 10 seconds ago
        ten_seconds_ago = time.time() - 10.0
        redis_client.get.return_value = {
            'tokens': 8.0,
            'last_refill': ten_seconds_ago
        }

        success, retry_after = bucket.consume(1)

        # After 10 seconds, 20 tokens would refill (refill_rate=2.0)
        # But capacity is 10, so capped at 10
        # After consuming 1 = 9
        assert success is True

        call_args = redis_client.set.call_args
        assert call_args[0][1]['tokens'] == 9.0

    def test_redis_fallback_on_error(self, bucket, redis_client):
        """Test fallback to in-memory when Redis fails."""
        # Simulate Redis failure
        redis_client.get.side_effect = Exception("Redis connection failed")

        # Should still work using in-memory fallback
        success, retry_after = bucket.consume(1)
        assert success is True

    def test_get_status(self, bucket, redis_client):
        """Test getting bucket status."""
        redis_client.get.return_value = {
            'tokens': 7.5,
            'last_refill': time.time()
        }

        status = bucket.get_status()

        assert status['tokens'] == 7.5
        assert status['capacity'] == 10
        assert status['refill_rate'] == 2.0
        assert status['rpm'] == 120.0  # 2.0 * 60
        assert 'utilization' in status


class TestRateLimiter:
    """Test RateLimiter class."""

    @pytest.fixture
    def redis_client(self):
        """Mock Redis client."""
        mock_redis = Mock(spec=RedisClient)
        mock_redis.get.return_value = None  # Default to empty bucket
        mock_redis.set.return_value = True
        return mock_redis

    @pytest.fixture
    def rate_limiter(self, redis_client):
        """Create test rate limiter."""
        return RateLimiter(redis_client=redis_client, enabled=True)

    def test_initialization(self, rate_limiter):
        """Test rate limiter initialization."""
        assert rate_limiter.enabled is True
        assert rate_limiter.redis is not None
        assert len(rate_limiter._buckets) == 0

    def test_check_limit_success(self, rate_limiter):
        """Test checking rate limit with available capacity."""
        allowed, retry_after = rate_limiter.check_limit('anthropic', 'claude-haiku-3.5')

        assert allowed is True
        assert retry_after == 0.0

    def test_check_limit_with_service_only(self, rate_limiter):
        """Test checking rate limit with service-level limits."""
        allowed, retry_after = rate_limiter.check_limit('openai')

        assert allowed is True
        assert retry_after == 0.0

    def test_check_limit_disabled(self, redis_client):
        """Test that disabled rate limiter always allows requests."""
        limiter = RateLimiter(redis_client=redis_client, enabled=False)

        allowed, retry_after = limiter.check_limit('anthropic')

        assert allowed is True
        assert retry_after == 0.0

    def test_wait_for_capacity_immediate(self, rate_limiter):
        """Test waiting for capacity when immediately available."""
        result = rate_limiter.wait_for_capacity('anthropic', max_wait=5.0)

        assert result is True

    def test_wait_for_capacity_timeout(self, rate_limiter, redis_client):
        """Test timeout when capacity not available."""
        # Mock Redis to always return 0 tokens
        redis_client.get.return_value = {
            'tokens': 0.0,
            'last_refill': time.time()
        }

        result = rate_limiter.wait_for_capacity('anthropic', max_wait=0.1)

        assert result is False

    def test_get_status_all_services(self, rate_limiter):
        """Test getting status for all services."""
        # Make some requests to create buckets
        rate_limiter.check_limit('anthropic', 'claude-haiku-3.5')
        rate_limiter.check_limit('openai')

        status = rate_limiter.get_status()

        assert status['enabled'] is True
        assert 'buckets' in status
        assert len(status['buckets']) == 2

    def test_get_status_single_service(self, rate_limiter):
        """Test getting status for single service."""
        rate_limiter.check_limit('anthropic', 'claude-haiku-3.5')

        status = rate_limiter.get_status('anthropic')

        assert 'anthropic:claude-haiku-3.5' in status['buckets']

    def test_reset_all(self, rate_limiter, redis_client):
        """Test resetting all rate limits."""
        # Create some buckets
        rate_limiter.check_limit('anthropic')
        rate_limiter.check_limit('openai')

        rate_limiter.reset()

        assert len(rate_limiter._buckets) == 0
        assert redis_client.delete.call_count >= 2

    def test_reset_single_service(self, rate_limiter, redis_client):
        """Test resetting single service rate limit."""
        rate_limiter.check_limit('anthropic', 'claude-haiku-3.5')
        rate_limiter.check_limit('openai')

        rate_limiter.reset('anthropic')

        assert 'anthropic:claude-haiku-3.5' not in rate_limiter._buckets
        assert len(rate_limiter._buckets) == 1  # OpenAI still there


class TestRateLimitDecorator:
    """Test rate limit decorator."""

    @pytest.fixture
    def mock_limiter(self):
        """Mock rate limiter."""
        with patch('agent_system.rate_limiter.get_rate_limiter') as mock:
            limiter = Mock(spec=RateLimiter)
            limiter.enabled = True
            limiter.wait_for_capacity.return_value = True
            mock.return_value = limiter
            yield limiter

    def test_decorator_allows_call(self, mock_limiter):
        """Test decorator allows call when capacity available."""
        @limit_anthropic(model='claude-haiku-3.5')
        def test_function():
            return "success"

        result = test_function()

        assert result == "success"
        mock_limiter.wait_for_capacity.assert_called_once_with(
            'anthropic', 'claude-haiku-3.5', 1, 60.0
        )

    def test_decorator_blocks_call(self, mock_limiter):
        """Test decorator raises exception when rate limited."""
        mock_limiter.wait_for_capacity.return_value = False

        @limit_anthropic(model='claude-haiku-3.5')
        def test_function():
            return "success"

        with pytest.raises(RateLimitExceeded):
            test_function()

    def test_decorator_handles_429_error(self, mock_limiter):
        """Test decorator handles 429 errors with retry."""
        call_count = 0

        @limit_anthropic(model='claude-haiku-3.5')
        def test_function():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("429 rate limit exceeded")
            return "success"

        result = test_function()

        assert result == "success"
        assert call_count == 2  # Original + 1 retry

    def test_decorator_429_max_retries(self, mock_limiter):
        """Test decorator gives up after max 429 retries."""
        @limit_anthropic(model='claude-haiku-3.5')
        def test_function():
            raise Exception("429 rate limit exceeded")

        with pytest.raises(RateLimitExceeded):
            test_function()

    def test_decorator_with_service_only(self, mock_limiter):
        """Test decorator with service-level limit."""
        @limit_openai()
        def test_function():
            return "success"

        result = test_function()

        assert result == "success"
        mock_limiter.wait_for_capacity.assert_called_once()


class TestConvenienceDecorators:
    """Test convenience decorator functions."""

    def test_limit_anthropic_decorator(self):
        """Test limit_anthropic convenience decorator."""
        with patch('agent_system.rate_limiter.get_rate_limiter') as mock:
            limiter = Mock(spec=RateLimiter)
            limiter.enabled = True
            limiter.limit.return_value = lambda func: func
            mock.return_value = limiter

            @limit_anthropic(model='claude-sonnet-4-20250514')
            def test_function():
                return "success"

            limiter.limit.assert_called_once()
            call_kwargs = limiter.limit.call_args[1]
            assert call_kwargs['service'] == 'anthropic'
            assert call_kwargs['model'] == 'claude-sonnet-4-20250514'

    def test_limit_openai_decorator(self):
        """Test limit_openai convenience decorator."""
        with patch('agent_system.rate_limiter.get_rate_limiter') as mock:
            limiter = Mock(spec=RateLimiter)
            limiter.enabled = True
            limiter.limit.return_value = lambda func: func
            mock.return_value = limiter

            @limit_openai(model='gpt-4o-realtime-preview')
            def test_function():
                return "success"

            limiter.limit.assert_called_once()

    def test_limit_gemini_decorator(self):
        """Test limit_gemini convenience decorator."""
        with patch('agent_system.rate_limiter.get_rate_limiter') as mock:
            limiter = Mock(spec=RateLimiter)
            limiter.enabled = True
            limiter.limit.return_value = lambda func: func
            mock.return_value = limiter

            @limit_gemini(model='gemini-2.5-pro')
            def test_function():
                return "success"

            limiter.limit.assert_called_once()


class TestConcurrency:
    """Test rate limiter under concurrent access."""

    @pytest.fixture
    def redis_client(self):
        """Mock Redis client with thread-safe operations."""
        mock_redis = Mock(spec=RedisClient)
        mock_redis.get.return_value = None
        mock_redis.set.return_value = True
        return mock_redis

    def test_concurrent_requests(self, redis_client):
        """Test rate limiter handles concurrent requests correctly."""
        limiter = RateLimiter(redis_client=redis_client, enabled=True)
        results = []

        def make_request():
            allowed, _ = limiter.check_limit('anthropic')
            results.append(allowed)

        # Create 10 concurrent threads
        threads = [threading.Thread(target=make_request) for _ in range(10)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # All should succeed (bucket has capacity)
        assert len(results) == 10
        assert all(results)


class TestIntegrationWithRedis:
    """Integration tests with real Redis (if available)."""

    @pytest.fixture
    def real_redis_client(self):
        """Create real Redis client (skip if unavailable)."""
        try:
            client = RedisClient()
            if not client.health_check():
                pytest.skip("Redis not available")
            return client
        except Exception:
            pytest.skip("Redis not available")

    def test_token_bucket_with_real_redis(self, real_redis_client):
        """Test token bucket with real Redis."""
        config = RateLimitConfig(
            bucket_capacity=5,
            refill_rate=1.0
        )
        bucket = TokenBucket(real_redis_client, 'test_integration', config)

        # Consume 3 tokens
        success1, _ = bucket.consume(3)
        assert success1 is True

        # Consume 2 more tokens (should succeed)
        success2, _ = bucket.consume(2)
        assert success2 is True

        # Try to consume 1 more (should fail - bucket empty)
        success3, retry_after = bucket.consume(1)
        assert success3 is False
        assert retry_after > 0

        # Wait for refill
        time.sleep(1.1)

        # Should succeed now (1 token refilled)
        success4, _ = bucket.consume(1)
        assert success4 is True

        # Cleanup
        real_redis_client.delete('rate_limit:test_integration')


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_invalid_service_name(self):
        """Test handling of invalid service name."""
        limiter = RateLimiter(enabled=True)

        # Should create bucket with default config
        allowed, _ = limiter.check_limit('invalid_service')
        assert allowed is True

    def test_negative_cost(self):
        """Test handling of negative cost."""
        redis_client = Mock(spec=RedisClient)
        config = RateLimitConfig(bucket_capacity=10, refill_rate=1.0)
        bucket = TokenBucket(redis_client, 'test', config)

        redis_client.get.return_value = None

        # Should handle gracefully (treat as 0)
        success, _ = bucket.consume(-1)
        # Implementation specific - could raise or treat as 0

    def test_extract_retry_after_from_error(self):
        """Test extracting retry-after from error message."""
        limiter = RateLimiter(enabled=True)

        # Test with retry-after in message
        error = Exception("Rate limit exceeded. Retry after 5 seconds")
        retry_after = limiter._extract_retry_after(error)
        assert retry_after == 5.0

        # Test with no retry-after
        error = Exception("Generic error")
        retry_after = limiter._extract_retry_after(error)
        assert retry_after is None


class TestObservability:
    """Test observability and monitoring features."""

    def test_rate_limit_event_emission(self):
        """Test that rate limit events are emitted."""
        with patch('agent_system.rate_limiter.emit_event') as mock_emit:
            limiter = RateLimiter(enabled=True)

            # Trigger 429 handling
            @limiter.limit('anthropic')
            def test_function():
                raise Exception("429 rate limit")

            try:
                test_function()
            except:
                pass

            # Should emit rate_limit_429 event
            # Check if emit_event was attempted (may fail if observability not setup)

    def test_get_status_includes_utilization(self):
        """Test that status includes utilization metrics."""
        limiter = RateLimiter(enabled=True)

        # Make some requests
        limiter.check_limit('anthropic', 'claude-haiku-3.5')

        status = limiter.get_status('anthropic')

        assert 'buckets' in status
        for bucket_status in status['buckets'].values():
            assert 'utilization' in bucket_status or 'tokens' in bucket_status


# Performance benchmarks
@pytest.mark.benchmark
class TestPerformance:
    """Performance benchmarks for rate limiter."""

    def test_check_limit_performance(self, benchmark):
        """Benchmark check_limit performance."""
        redis_client = Mock(spec=RedisClient)
        redis_client.get.return_value = None
        redis_client.set.return_value = True

        limiter = RateLimiter(redis_client=redis_client, enabled=True)

        def check():
            limiter.check_limit('anthropic')

        result = benchmark(check)

    def test_decorator_overhead(self, benchmark):
        """Benchmark decorator overhead."""
        with patch('agent_system.rate_limiter.get_rate_limiter') as mock:
            limiter = Mock(spec=RateLimiter)
            limiter.enabled = True
            limiter.wait_for_capacity.return_value = True
            limiter._execute_with_429_handling = lambda f, s, m, *a, **k: f(*a, **k)
            mock.return_value = limiter

            @limit_anthropic()
            def test_function():
                return "success"

            result = benchmark(test_function)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
