"""
Performance Tests for Error Recovery Module

Validates that error recovery mechanisms meet performance requirements:
- Circuit breaker overhead < 0.1ms per call
- Retry delay calculation < 0.01ms
- Error classification < 0.05ms
- Thread safety under concurrent load
- Memory usage remains bounded
"""
import pytest
import time
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from agent_system.error_recovery import (
    RetryPolicy,
    CircuitBreaker,
    CircuitBreakerConfig,
    ErrorClassifier,
    ErrorCategory,
    retry_with_backoff,
    get_circuit_breaker,
)


class TestCircuitBreakerPerformance:
    """Performance tests for circuit breaker."""

    def test_circuit_breaker_overhead_minimal(self):
        """
        Test that circuit breaker adds minimal overhead.

        PERFORMANCE REQUIREMENT: < 0.1ms per call
        """
        cb = CircuitBreaker(
            name='perf_test',
            config=CircuitBreakerConfig(failure_threshold=1000)
        )

        iterations = 1000

        # Measure time for successful calls
        start = time.perf_counter()
        for _ in range(iterations):
            cb.call(lambda: "success")
        elapsed = time.perf_counter() - start

        # Calculate per-call overhead
        overhead_per_call_ms = (elapsed / iterations) * 1000

        print(f"\nCircuit breaker overhead: {overhead_per_call_ms:.4f}ms per call")

        # Should be < 0.1ms per call (100 microseconds)
        assert overhead_per_call_ms < 0.1, (
            f"Circuit breaker overhead too high: {overhead_per_call_ms:.4f}ms per call "
            f"(requirement: < 0.1ms)"
        )

    def test_circuit_breaker_state_transition_performance(self):
        """
        Test circuit breaker state transition performance.

        PERFORMANCE CHARACTERISTIC: State transitions should be fast
        """
        cb = CircuitBreaker(
            name='state_test',
            config=CircuitBreakerConfig(
                failure_threshold=3,
                timeout_seconds=0.01
            )
        )

        # Measure time to open circuit (3 failures)
        start = time.perf_counter()
        for _ in range(3):
            try:
                cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
            except Exception:
                pass
        open_time = time.perf_counter() - start

        print(f"\nTime to open circuit (3 failures): {open_time*1000:.4f}ms")

        # Wait for recovery timeout
        time.sleep(0.02)

        # Measure time to close circuit (2 successes in HALF_OPEN)
        start = time.perf_counter()
        try:
            cb.call(lambda: "success")
        except:
            pass
        time.sleep(0.02)  # Wait for another attempt
        cb.call(lambda: "success")
        cb.call(lambda: "success")
        close_time = time.perf_counter() - start

        print(f"Time to close circuit (2 successes): {close_time*1000:.4f}ms")

        # State transitions should be < 10ms (excluding sleep time)
        assert open_time < 0.01, "Opening circuit too slow"

    def test_circuit_breaker_memory_bounded(self):
        """
        Test that circuit breaker memory usage is bounded.

        PERFORMANCE REQUIREMENT: Memory footprint < 10KB
        """
        cb = CircuitBreaker(
            name='memory_test',
            config=CircuitBreakerConfig(failure_threshold=1000)
        )

        # Make many calls to potentially accumulate state
        for i in range(10000):
            try:
                if i % 2 == 0:
                    cb.call(lambda: "success")
                else:
                    cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
            except Exception:
                pass

        # Measure circuit breaker size
        size = sys.getsizeof(cb)
        print(f"\nCircuit breaker memory: {size} bytes")

        # Should be < 10KB
        assert size < 10000, (
            f"Circuit breaker memory too large: {size} bytes "
            f"(requirement: < 10KB)"
        )

    def test_circuit_breaker_concurrent_performance(self):
        """
        Test circuit breaker performance under concurrent load.

        PERFORMANCE CHARACTERISTIC: Thread-safe with minimal contention
        """
        cb = CircuitBreaker(
            name='concurrent_test',
            config=CircuitBreakerConfig(failure_threshold=1000)
        )

        results = []
        errors = []
        num_threads = 50
        calls_per_thread = 100

        def worker():
            for _ in range(calls_per_thread):
                try:
                    result = cb.call(lambda: "success")
                    results.append(result)
                except Exception as e:
                    errors.append(e)

        # Measure concurrent execution time
        start = time.perf_counter()

        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        elapsed = time.perf_counter() - start

        total_calls = num_threads * calls_per_thread
        throughput = total_calls / elapsed

        print(f"\nConcurrent circuit breaker throughput: {throughput:.0f} calls/sec")
        print(f"Total time: {elapsed:.4f}s for {total_calls} calls")
        print(f"Results: {len(results)}, Errors: {len(errors)}")

        # All calls should succeed
        assert len(results) == total_calls
        assert len(errors) == 0

        # Throughput should be reasonable (> 10,000 calls/sec)
        assert throughput > 10000, (
            f"Concurrent throughput too low: {throughput:.0f} calls/sec "
            f"(requirement: > 10,000 calls/sec)"
        )


class TestRetryPolicyPerformance:
    """Performance tests for retry policy."""

    def test_delay_calculation_fast(self):
        """
        Test that delay calculation is fast.

        PERFORMANCE REQUIREMENT: < 0.01ms per calculation
        """
        policy = RetryPolicy(
            max_attempts=10,
            base_delay=1.0,
            backoff_factor=2.0,
            jitter=True
        )

        iterations = 10000

        # Measure time for delay calculations
        start = time.perf_counter()
        for attempt in range(1, 101):
            for _ in range(100):
                policy.calculate_delay(attempt % 10 + 1)
        elapsed = time.perf_counter() - start

        # Calculate per-calculation time
        time_per_calc_ms = (elapsed / iterations) * 1000

        print(f"\nDelay calculation time: {time_per_calc_ms:.6f}ms per calculation")

        # Should be < 0.01ms (10 microseconds)
        assert time_per_calc_ms < 0.01, (
            f"Delay calculation too slow: {time_per_calc_ms:.6f}ms "
            f"(requirement: < 0.01ms)"
        )

    def test_should_retry_decision_fast(self):
        """
        Test that retry decision is fast.

        PERFORMANCE CHARACTERISTIC: Minimal decision overhead
        """
        policy = RetryPolicy(max_attempts=5)

        error_categories = [
            ErrorCategory.TRANSIENT,
            ErrorCategory.RATE_LIMIT,
            ErrorCategory.TIMEOUT,
            ErrorCategory.AUTH_ERROR,
            ErrorCategory.PERMANENT,
        ]

        iterations = 10000

        # Measure time for retry decisions
        start = time.perf_counter()
        for _ in range(iterations):
            for category in error_categories:
                policy.should_retry(1, category)
        elapsed = time.perf_counter() - start

        time_per_decision_us = (elapsed / (iterations * len(error_categories))) * 1_000_000

        print(f"\nRetry decision time: {time_per_decision_us:.4f}µs per decision")

        # Should be < 5 microseconds
        assert time_per_decision_us < 5, (
            f"Retry decision too slow: {time_per_decision_us:.4f}µs"
        )


class TestErrorClassifierPerformance:
    """Performance tests for error classifier."""

    def test_error_classification_fast(self):
        """
        Test that error classification is fast.

        PERFORMANCE REQUIREMENT: < 0.05ms per classification
        """
        test_errors = [
            (Exception("rate limit exceeded"), None),
            (TimeoutError("operation timed out"), None),
            (ConnectionError("connection refused"), None),
            (Exception("authentication failed"), None),
            (Exception("service unavailable"), 503),
            (Exception("too many requests"), 429),
            (Exception("unauthorized"), 401),
        ]

        iterations = 1000

        # Measure classification time
        start = time.perf_counter()
        for _ in range(iterations):
            for error, status_code in test_errors:
                ErrorClassifier.classify_error(error, status_code)
        elapsed = time.perf_counter() - start

        total_classifications = iterations * len(test_errors)
        time_per_classification_ms = (elapsed / total_classifications) * 1000

        print(f"\nError classification time: {time_per_classification_ms:.6f}ms per classification")

        # Should be < 0.05ms (50 microseconds)
        assert time_per_classification_ms < 0.05, (
            f"Error classification too slow: {time_per_classification_ms:.6f}ms "
            f"(requirement: < 0.05ms)"
        )

    def test_classification_with_context(self):
        """Test classification performance with context parsing."""
        iterations = 1000

        start = time.perf_counter()
        for _ in range(iterations):
            ErrorClassifier.classify_error(
                TimeoutError("timeout"),
                status_code=504,
                context={'is_subprocess_timeout': True}
            )
        elapsed = time.perf_counter() - start

        time_per_classification_us = (elapsed / iterations) * 1_000_000

        print(f"\nClassification with context: {time_per_classification_us:.4f}µs")

        # Should still be fast
        assert time_per_classification_us < 100


class TestRetryDecoratorPerformance:
    """Performance tests for retry decorator."""

    def test_decorator_overhead_on_success(self):
        """
        Test retry decorator overhead when function succeeds immediately.

        PERFORMANCE CHARACTERISTIC: Minimal overhead on success path
        """
        call_count = [0]

        @retry_with_backoff(max_attempts=3, emit_events=False)
        def fast_success():
            call_count[0] += 1
            return "success"

        iterations = 1000

        # Measure overhead
        start = time.perf_counter()
        for _ in range(iterations):
            fast_success()
        elapsed = time.perf_counter() - start

        overhead_per_call_us = (elapsed / iterations) * 1_000_000

        print(f"\nRetry decorator overhead (success): {overhead_per_call_us:.4f}µs per call")

        # Should be < 100 microseconds
        assert overhead_per_call_us < 100, (
            f"Decorator overhead too high: {overhead_per_call_us:.4f}µs"
        )

    def test_backoff_timing_accuracy(self):
        """
        Test that exponential backoff timing is accurate.

        PERFORMANCE CHARACTERISTIC: Actual delays match calculated delays
        """
        call_times = []

        @retry_with_backoff(
            max_attempts=3,
            base_delay=0.05,  # 50ms
            backoff_factor=2.0,
            emit_events=False
        )
        def failing_func():
            call_times.append(time.perf_counter())
            if len(call_times) < 3:
                raise ConnectionError("Network error")
            return "success"

        failing_func()

        # Calculate actual delays
        actual_delays = [
            call_times[i+1] - call_times[i] for i in range(len(call_times) - 1)
        ]

        print(f"\nBackoff delays: {[f'{d*1000:.1f}ms' for d in actual_delays]}")

        # Expected delays: 50ms, 100ms (with some tolerance for jitter and execution time)
        # Allow ±30% variance due to jitter and system scheduling
        assert 35 <= actual_delays[0] * 1000 <= 75, "First delay timing off"
        assert 70 <= actual_delays[1] * 1000 <= 150, "Second delay timing off"


class TestScalabilityCharacteristics:
    """Test scalability under load."""

    def test_multiple_circuit_breakers_performance(self):
        """
        Test performance with multiple circuit breakers.

        PERFORMANCE CHARACTERISTIC: Scales linearly with number of breakers
        """
        num_breakers = 100
        calls_per_breaker = 100

        # Create multiple circuit breakers
        breakers = [
            get_circuit_breaker(f'breaker_{i}', CircuitBreakerConfig())
            for i in range(num_breakers)
        ]

        # Measure time to make calls across all breakers
        start = time.perf_counter()
        for cb in breakers:
            for _ in range(calls_per_breaker):
                cb.call(lambda: "success")
        elapsed = time.perf_counter() - start

        total_calls = num_breakers * calls_per_breaker
        throughput = total_calls / elapsed

        print(f"\nMultiple breakers throughput: {throughput:.0f} calls/sec")
        print(f"Time for {total_calls} calls across {num_breakers} breakers: {elapsed:.4f}s")

        # Should maintain good throughput
        assert throughput > 10000

    def test_retry_at_scale(self):
        """
        Test retry performance with many concurrent retries.

        PERFORMANCE CHARACTERISTIC: Handles concurrent retries efficiently
        """
        num_workers = 20
        calls_per_worker = 50

        results = []

        def worker():
            @retry_with_backoff(max_attempts=2, base_delay=0.001, emit_events=False)
            def flaky_call():
                import random
                if random.random() < 0.3:  # 30% failure rate
                    raise ConnectionError("Flaky error")
                return "success"

            for _ in range(calls_per_worker):
                try:
                    result = flaky_call()
                    results.append(result)
                except:
                    pass

        start = time.perf_counter()

        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(worker) for _ in range(num_workers)]
            for future in as_completed(futures):
                future.result()

        elapsed = time.perf_counter() - start

        total_calls = num_workers * calls_per_worker
        throughput = len(results) / elapsed

        print(f"\nConcurrent retry throughput: {throughput:.0f} successful calls/sec")
        print(f"Success rate: {len(results)}/{total_calls} ({len(results)/total_calls*100:.1f}%)")
        print(f"Total time: {elapsed:.4f}s")

        # Should handle concurrent load efficiently
        assert throughput > 500


class TestMemoryEfficiency:
    """Test memory efficiency of error recovery components."""

    def test_retry_policy_memory_footprint(self):
        """Test RetryPolicy memory footprint is small."""
        policy = RetryPolicy(
            max_attempts=10,
            base_delay=1.0,
            max_delay=60.0,
            backoff_factor=2.0
        )

        size = sys.getsizeof(policy)
        print(f"\nRetryPolicy memory: {size} bytes")

        # Should be tiny (< 1KB)
        assert size < 1000

    def test_circuit_breaker_growth_bounded(self):
        """
        Test that circuit breaker memory doesn't grow unbounded.

        PERFORMANCE REQUIREMENT: O(1) memory usage
        """
        cb = CircuitBreaker(
            name='growth_test',
            config=CircuitBreakerConfig(failure_threshold=100)
        )

        # Measure initial size
        initial_size = sys.getsizeof(cb)

        # Make many calls
        for i in range(100000):
            try:
                if i % 2 == 0:
                    cb.call(lambda: "success")
                else:
                    cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
            except Exception:
                pass

        # Measure final size
        final_size = sys.getsizeof(cb)

        growth = final_size - initial_size
        growth_pct = (growth / initial_size) * 100

        print(f"\nCircuit breaker memory growth:")
        print(f"  Initial: {initial_size} bytes")
        print(f"  Final: {final_size} bytes")
        print(f"  Growth: {growth} bytes ({growth_pct:.1f}%)")

        # Growth should be minimal (< 20%)
        assert growth_pct < 20, (
            f"Circuit breaker memory grew too much: {growth_pct:.1f}% "
            f"(requirement: < 20%)"
        )


class TestWorstCaseScenarios:
    """Test worst-case performance scenarios."""

    def test_circuit_breaker_rapid_failures(self):
        """Test circuit breaker under rapid failure conditions."""
        cb = CircuitBreaker(
            name='rapid_fail_test',
            config=CircuitBreakerConfig(failure_threshold=10)
        )

        iterations = 1000

        start = time.perf_counter()
        for _ in range(iterations):
            try:
                cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
            except Exception:
                pass
        elapsed = time.perf_counter() - start

        time_per_call_ms = (elapsed / iterations) * 1000

        print(f"\nCircuit breaker under rapid failures: {time_per_call_ms:.4f}ms per call")

        # Even under failures, should remain fast
        assert time_per_call_ms < 0.5

    def test_retry_max_backoff_scenario(self):
        """Test retry behavior at maximum backoff delay."""
        policy = RetryPolicy(
            max_attempts=10,
            base_delay=1.0,
            max_delay=5.0,
            backoff_factor=2.0,
            jitter=False
        )

        # At high attempt numbers, should cap at max_delay
        for attempt in range(1, 20):
            delay = policy.calculate_delay(attempt)
            assert delay <= 5.0, f"Delay exceeded max at attempt {attempt}: {delay}s"

        print(f"\nMax delay correctly capped at {policy.max_delay}s")


def run_performance_summary():
    """Run all performance tests and print summary."""
    print("\n" + "="*80)
    print("ERROR RECOVERY PERFORMANCE TEST SUMMARY")
    print("="*80)

    # Run pytest with performance tests
    pytest.main([
        __file__,
        '-v',
        '--tb=short',
        '-k', 'Performance or Efficiency or Scalability or WorstCase'
    ])


if __name__ == '__main__':
    run_performance_summary()
