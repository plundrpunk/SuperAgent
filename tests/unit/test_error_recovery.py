"""
Unit Tests for Error Recovery Module

Tests retry policies, circuit breakers, error classification, and fallback strategies.
"""
import pytest
import time
from unittest.mock import Mock, patch
from agent_system.error_recovery import (
    ErrorCategory,
    ErrorClassifier,
    RetryPolicy,
    CircuitBreaker,
    CircuitBreakerState,
    CircuitBreakerOpenError,
    CircuitBreakerConfig,
    retry_with_backoff,
    FallbackStrategy,
    FallbackType,
    get_circuit_breaker,
    get_agent_recovery_decorator,
    GracefulDegradation
)


# Test Error Classification

class TestErrorClassifier:
    """Test error classification logic."""

    def test_classify_by_status_code(self):
        """Test classification by HTTP status code."""
        error = Exception("Some error")

        assert ErrorClassifier.classify_error(error, status_code=429) == ErrorCategory.RATE_LIMIT
        assert ErrorClassifier.classify_error(error, status_code=401) == ErrorCategory.AUTH_ERROR
        assert ErrorClassifier.classify_error(error, status_code=400) == ErrorCategory.INVALID_INPUT
        assert ErrorClassifier.classify_error(error, status_code=500) == ErrorCategory.SERVICE_ERROR
        assert ErrorClassifier.classify_error(error, status_code=504) == ErrorCategory.TIMEOUT

    def test_classify_by_exception_type(self):
        """Test classification by exception type."""
        assert ErrorClassifier.classify_error(TimeoutError("timeout")) == ErrorCategory.TIMEOUT
        assert ErrorClassifier.classify_error(ConnectionError("connection")) == ErrorCategory.NETWORK_ERROR
        assert ErrorClassifier.classify_error(OSError("os error")) == ErrorCategory.TRANSIENT

    def test_classify_by_error_message(self):
        """Test classification by error message patterns."""
        assert ErrorClassifier.classify_error(Exception("rate limit exceeded")) == ErrorCategory.RATE_LIMIT
        assert ErrorClassifier.classify_error(Exception("connection timeout")) == ErrorCategory.TIMEOUT
        assert ErrorClassifier.classify_error(Exception("network error")) == ErrorCategory.NETWORK_ERROR
        assert ErrorClassifier.classify_error(Exception("unauthorized access")) == ErrorCategory.AUTH_ERROR
        assert ErrorClassifier.classify_error(Exception("invalid input")) == ErrorCategory.INVALID_INPUT
        assert ErrorClassifier.classify_error(Exception("not found")) == ErrorCategory.PERMANENT

    def test_classify_subprocess_timeout(self):
        """Test classification of subprocess timeout from context."""
        error = Exception("timeout")
        context = {'is_subprocess_timeout': True}

        assert ErrorClassifier.classify_error(error, context=context) == ErrorCategory.SUBPROCESS_TIMEOUT

    def test_classify_unknown_error(self):
        """Test classification of unknown errors defaults to transient."""
        error = Exception("some unknown error")

        assert ErrorClassifier.classify_error(error) == ErrorCategory.TRANSIENT


# Test Retry Policy

class TestRetryPolicy:
    """Test retry policy logic."""

    def test_calculate_delay_exponential(self):
        """Test exponential backoff calculation."""
        policy = RetryPolicy(
            base_delay=1.0,
            backoff_factor=2.0,
            jitter=False  # Disable jitter for deterministic testing
        )

        # Attempt 1: 1.0 * (2^0) = 1.0
        assert policy.calculate_delay(1) == 1.0

        # Attempt 2: 1.0 * (2^1) = 2.0
        assert policy.calculate_delay(2) == 2.0

        # Attempt 3: 1.0 * (2^2) = 4.0
        assert policy.calculate_delay(3) == 4.0

    def test_calculate_delay_max_delay(self):
        """Test delay caps at max_delay."""
        policy = RetryPolicy(
            base_delay=10.0,
            backoff_factor=2.0,
            max_delay=20.0,
            jitter=False
        )

        # Attempt 3: 10.0 * (2^2) = 40.0, but capped at 20.0
        assert policy.calculate_delay(3) == 20.0

    def test_calculate_delay_with_jitter(self):
        """Test jitter adds randomness."""
        policy = RetryPolicy(
            base_delay=10.0,
            backoff_factor=2.0,
            jitter=True
        )

        delays = [policy.calculate_delay(1) for _ in range(10)]

        # All delays should be within +/- 25% of base delay
        for delay in delays:
            assert 7.5 <= delay <= 12.5

        # Delays should not all be identical (jitter adds randomness)
        assert len(set(delays)) > 1

    def test_should_retry_transient_errors(self):
        """Test retry decision for transient errors."""
        policy = RetryPolicy(max_attempts=3)

        # Should retry transient errors up to max attempts
        assert policy.should_retry(1, ErrorCategory.TRANSIENT) is True
        assert policy.should_retry(2, ErrorCategory.TRANSIENT) is True
        assert policy.should_retry(3, ErrorCategory.TRANSIENT) is False  # Max reached

    def test_should_retry_permanent_errors(self):
        """Test retry decision for permanent errors."""
        policy = RetryPolicy(max_attempts=3)

        # Never retry permanent errors
        assert policy.should_retry(1, ErrorCategory.AUTH_ERROR) is False
        assert policy.should_retry(1, ErrorCategory.INVALID_INPUT) is False
        assert policy.should_retry(1, ErrorCategory.PERMANENT) is False

    def test_should_retry_retryable_errors(self):
        """Test retry decision for retryable errors."""
        policy = RetryPolicy(max_attempts=3)

        # Should retry these error types
        assert policy.should_retry(1, ErrorCategory.RATE_LIMIT) is True
        assert policy.should_retry(1, ErrorCategory.TIMEOUT) is True
        assert policy.should_retry(1, ErrorCategory.NETWORK_ERROR) is True
        assert policy.should_retry(1, ErrorCategory.SERVICE_ERROR) is True


# Test Circuit Breaker

class TestCircuitBreaker:
    """Test circuit breaker logic."""

    def test_initial_state_closed(self):
        """Test circuit breaker starts in CLOSED state."""
        cb = CircuitBreaker('test_cb')
        assert cb.state == CircuitBreakerState.CLOSED

    def test_successful_calls(self):
        """Test successful calls don't change state."""
        cb = CircuitBreaker('test_cb')

        for _ in range(10):
            result = cb.call(lambda: "success")
            assert result == "success"

        assert cb.state == CircuitBreakerState.CLOSED

    def test_open_after_threshold(self):
        """Test circuit opens after failure threshold."""
        config = CircuitBreakerConfig(failure_threshold=3)
        cb = CircuitBreaker('test_cb', config)

        # Fail 3 times -> should open
        for i in range(3):
            try:
                cb.call(lambda: self._raise_error())
            except Exception:
                pass

        assert cb.state == CircuitBreakerState.OPEN

    def test_open_circuit_fails_fast(self):
        """Test open circuit fails fast without calling function."""
        config = CircuitBreakerConfig(failure_threshold=2)
        cb = CircuitBreaker('test_cb', config)

        # Fail twice to open circuit
        for _ in range(2):
            try:
                cb.call(lambda: self._raise_error())
            except Exception:
                pass

        # Now circuit is open - should fail fast
        with pytest.raises(CircuitBreakerOpenError):
            cb.call(lambda: "this should not execute")

    def test_half_open_after_timeout(self):
        """Test circuit transitions to HALF_OPEN after timeout."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            timeout_seconds=0.1  # Short timeout for testing
        )
        cb = CircuitBreaker('test_cb', config)

        # Open the circuit
        for _ in range(2):
            try:
                cb.call(lambda: self._raise_error())
            except Exception:
                pass

        assert cb.state == CircuitBreakerState.OPEN

        # Wait for timeout
        time.sleep(0.15)

        # Next call should transition to HALF_OPEN
        try:
            cb.call(lambda: self._raise_error())
        except Exception:
            pass

        # Should be back to OPEN due to failure
        assert cb.state == CircuitBreakerState.OPEN

    def test_half_open_to_closed_on_success(self):
        """Test circuit closes after successful calls in HALF_OPEN."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            success_threshold=2,
            timeout_seconds=0.1
        )
        cb = CircuitBreaker('test_cb', config)

        # Open the circuit
        for _ in range(2):
            try:
                cb.call(lambda: self._raise_error())
            except Exception:
                pass

        assert cb.state == CircuitBreakerState.OPEN

        # Wait for timeout
        time.sleep(0.15)

        # Transition to HALF_OPEN with first call
        try:
            cb.call(lambda: self._raise_error())
        except Exception:
            pass

        # Wait again
        time.sleep(0.15)

        # Now succeed twice in HALF_OPEN -> should close
        cb.call(lambda: "success")
        cb.call(lambda: "success")

        assert cb.state == CircuitBreakerState.CLOSED

    def test_manual_reset(self):
        """Test manual circuit breaker reset."""
        config = CircuitBreakerConfig(failure_threshold=2)
        cb = CircuitBreaker('test_cb', config)

        # Open the circuit
        for _ in range(2):
            try:
                cb.call(lambda: self._raise_error())
            except Exception:
                pass

        assert cb.state == CircuitBreakerState.OPEN

        # Manual reset
        cb.reset()

        assert cb.state == CircuitBreakerState.CLOSED

    def test_get_stats(self):
        """Test circuit breaker stats."""
        cb = CircuitBreaker('test_cb')

        # Generate some failures
        for _ in range(2):
            try:
                cb.call(lambda: self._raise_error())
            except Exception:
                pass

        stats = cb.get_stats()

        assert stats['name'] == 'test_cb'
        assert stats['state'] == CircuitBreakerState.CLOSED.value
        assert stats['failure_count'] == 2

    @staticmethod
    def _raise_error():
        """Helper to raise an error."""
        raise Exception("Test error")


# Test Retry Decorator

class TestRetryDecorator:
    """Test retry_with_backoff decorator."""

    def test_retry_succeeds_first_attempt(self):
        """Test function succeeds on first attempt."""
        call_count = [0]

        @retry_with_backoff(max_attempts=3, emit_events=False)
        def succeed_immediately():
            call_count[0] += 1
            return "success"

        result = succeed_immediately()

        assert result == "success"
        assert call_count[0] == 1

    def test_retry_succeeds_after_failures(self):
        """Test function succeeds after retries."""
        call_count = [0]

        @retry_with_backoff(max_attempts=3, base_delay=0.01, emit_events=False)
        def succeed_on_third():
            call_count[0] += 1
            if call_count[0] < 3:
                raise ConnectionError("Network error")
            return "success"

        result = succeed_on_third()

        assert result == "success"
        assert call_count[0] == 3

    def test_retry_all_attempts_fail(self):
        """Test function fails after all retries exhausted."""
        call_count = [0]

        @retry_with_backoff(max_attempts=3, base_delay=0.01, emit_events=False)
        def always_fail():
            call_count[0] += 1
            raise ConnectionError("Network error")

        with pytest.raises(ConnectionError):
            always_fail()

        assert call_count[0] == 3

    def test_retry_permanent_error_no_retry(self):
        """Test permanent errors are not retried."""
        call_count = [0]

        @retry_with_backoff(max_attempts=3, emit_events=False)
        def auth_error():
            call_count[0] += 1
            raise Exception("unauthorized access")

        with pytest.raises(Exception, match="unauthorized"):
            auth_error()

        # Should not retry auth errors
        assert call_count[0] == 1

    def test_retry_with_fallback(self):
        """Test fallback is applied after all retries fail."""
        call_count = [0]
        fallback = FallbackStrategy(
            strategy_type=FallbackType.RETURN_DEFAULT.value,
            default_value="fallback_value"
        )

        @retry_with_backoff(
            max_attempts=2,
            base_delay=0.01,
            fallback=fallback,
            emit_events=False
        )
        def always_fail():
            call_count[0] += 1
            raise ConnectionError("Network error")

        result = always_fail()

        assert result == "fallback_value"
        assert call_count[0] == 2

    def test_retry_with_circuit_breaker(self):
        """Test retry works with circuit breaker."""
        cb = get_circuit_breaker('test_retry_cb')
        cb.reset()  # Ensure clean state

        call_count = [0]

        @retry_with_backoff(
            max_attempts=3,
            base_delay=0.01,
            circuit_breaker_name='test_retry_cb',
            emit_events=False
        )
        def fail_then_succeed():
            call_count[0] += 1
            if call_count[0] < 2:
                raise ConnectionError("Network error")
            return "success"

        result = fail_then_succeed()

        assert result == "success"
        assert call_count[0] == 2


# Test Fallback Strategies

class TestFallbackStrategies:
    """Test fallback strategy implementations."""

    def test_return_default_fallback(self):
        """Test RETURN_DEFAULT fallback strategy."""
        fallback = FallbackStrategy(
            strategy_type=FallbackType.RETURN_DEFAULT.value,
            default_value={'status': 'default'}
        )

        @retry_with_backoff(
            max_attempts=1,
            fallback=fallback,
            emit_events=False
        )
        def fail():
            raise Exception("error")

        result = fail()

        assert result == {'status': 'default'}

    def test_skip_validation_fallback(self):
        """Test SKIP_VALIDATION fallback strategy."""
        fallback = FallbackStrategy(
            strategy_type=FallbackType.SKIP_VALIDATION.value
        )

        @retry_with_backoff(
            max_attempts=1,
            fallback=fallback,
            emit_events=False
        )
        def fail():
            raise Exception("validation error")

        result = fail()

        assert result['success'] is True
        assert result['validated'] is False
        assert result['fallback_applied'] is True

    def test_mark_unvalidated_fallback(self):
        """Test MARK_UNVALIDATED fallback strategy."""
        fallback = FallbackStrategy(
            strategy_type=FallbackType.MARK_UNVALIDATED.value
        )

        @retry_with_backoff(
            max_attempts=1,
            fallback=fallback,
            emit_events=False
        )
        def fail():
            raise Exception("validation unavailable")

        result = fail()

        assert result['validated'] is False
        assert result['fallback_applied'] is True
        assert 'validation unavailable' in result['fallback_reason']


# Test Agent-Specific Recovery

class TestAgentRecovery:
    """Test agent-specific recovery configurations."""

    def test_get_agent_recovery_decorator(self):
        """Test getting recovery decorator for agents."""
        # Should return decorator without error
        scribe_decorator = get_agent_recovery_decorator('scribe')
        runner_decorator = get_agent_recovery_decorator('runner')
        medic_decorator = get_agent_recovery_decorator('medic')
        critic_decorator = get_agent_recovery_decorator('critic')
        gemini_decorator = get_agent_recovery_decorator('gemini')

        assert callable(scribe_decorator)
        assert callable(runner_decorator)
        assert callable(medic_decorator)
        assert callable(critic_decorator)
        assert callable(gemini_decorator)

    def test_scribe_recovery_config(self):
        """Test Scribe agent recovery behavior."""
        call_count = [0]

        @get_agent_recovery_decorator('scribe')
        def scribe_execute():
            call_count[0] += 1
            if call_count[0] < 2:
                raise ConnectionError("API error")
            return "success"

        # Should retry and succeed
        result = scribe_execute()
        assert result == "success"
        assert call_count[0] == 2

    def test_critic_fail_fast(self):
        """Test Critic fails fast (max_attempts=1)."""
        call_count = [0]

        @get_agent_recovery_decorator('critic')
        def critic_execute():
            call_count[0] += 1
            raise Exception("error")

        with pytest.raises(Exception):
            critic_execute()

        # Critic should not retry (max_attempts=1)
        assert call_count[0] == 1


# Test Graceful Degradation

class TestGracefulDegradation:
    """Test graceful degradation utilities."""

    def test_redis_fallback_to_memory_get(self):
        """Test Redis fallback to in-memory cache for get."""
        # Mock failing Redis client
        mock_redis = Mock()
        mock_redis.get.side_effect = Exception("Redis connection failed")

        # Should use in-memory fallback
        result = GracefulDegradation.redis_with_fallback(
            mock_redis, 'get', 'test_key'
        )

        assert result is None  # Key not in memory cache

    def test_redis_fallback_to_memory_set(self):
        """Test Redis fallback to in-memory cache for set."""
        # Clear in-memory cache first
        GracefulDegradation._in_memory_cache.clear()

        # Mock failing Redis client
        mock_redis = Mock()
        mock_redis.set.side_effect = Exception("Redis connection failed")
        mock_redis.get.side_effect = Exception("Redis connection failed")

        # Should use in-memory fallback for set
        result = GracefulDegradation.redis_with_fallback(
            mock_redis, 'set', 'test_key', {'data': 'value'}
        )

        assert result is True

        # Verify value stored in memory (get should also fail over)
        result = GracefulDegradation.redis_with_fallback(
            mock_redis, 'get', 'test_key'
        )
        assert result == {'data': 'value'}

        # Cleanup
        GracefulDegradation._in_memory_cache.clear()

    def test_vector_db_fallback(self):
        """Test Vector DB fallback returns empty list."""
        # Mock failing vector client
        mock_vector = Mock()
        mock_vector.search_test_patterns.side_effect = Exception("Vector DB unavailable")

        # Should return empty list (graceful degradation)
        result = GracefulDegradation.vector_db_with_fallback(
            mock_vector, 'test query'
        )

        assert result == []

    def test_gemini_fallback(self):
        """Test Gemini validation fallback marks as unvalidated."""
        # Mock failing Gemini validator
        mock_gemini = Mock()
        mock_gemini.execute.side_effect = Exception("Gemini API unavailable")

        # Should return unvalidated result
        result = GracefulDegradation.gemini_with_fallback(
            mock_gemini, 'test.spec.ts'
        )

        assert result['success'] is True
        assert result['validated'] is False
        assert result['fallback_applied'] is True


# Test Integration

class TestErrorRecoveryIntegration:
    """Integration tests for error recovery system."""

    def test_full_recovery_flow(self):
        """Test complete recovery flow with retry, circuit breaker, and fallback."""
        cb = get_circuit_breaker('integration_test_cb')
        cb.reset()

        call_count = [0]
        fallback = FallbackStrategy(
            strategy_type=FallbackType.RETURN_DEFAULT.value,
            default_value="fallback_result"
        )

        @retry_with_backoff(
            max_attempts=3,
            base_delay=0.01,
            circuit_breaker_name='integration_test_cb',
            fallback=fallback,
            emit_events=False
        )
        def integration_test():
            call_count[0] += 1
            raise Exception("persistent error")

        # Should exhaust retries and apply fallback
        result = integration_test()

        assert result == "fallback_result"
        assert call_count[0] == 3

    def test_circuit_breaker_registry(self):
        """Test circuit breaker registry."""
        cb1 = get_circuit_breaker('test_service_1')
        cb2 = get_circuit_breaker('test_service_1')
        cb3 = get_circuit_breaker('test_service_2')

        # Same name should return same instance
        assert cb1 is cb2

        # Different name should return different instance
        assert cb1 is not cb3


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
