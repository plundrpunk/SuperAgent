"""
Comprehensive Load Testing for SuperAgent - Concurrent Feature Generation
Tests the system's ability to handle multiple parallel test generation requests.

Target Metrics:
- 10 parallel simple features: <5 minutes total, <$5 total cost, <2s p95 latency
- 5 parallel complex features: <15 minutes total, <$15 total cost, <5s p95 latency
- Zero Redis connection errors under load
- Zero race conditions in cost tracking
- Accurate cost tracking under concurrent load
"""
import pytest
import time
import statistics
import concurrent.futures
import threading
from typing import List, Dict, Any, Tuple
from pathlib import Path
import sys
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agent_system.agents.kaya import KayaAgent
from agent_system.agents.scribe import ScribeAgent
from agent_system.state.redis_client import RedisClient
from agent_system.state.vector_client import VectorClient
from agent_system.router import Router
from agent_system.cost_analytics import CostTracker


# Performance tracking utilities
class PerformanceMetrics:
    """Thread-safe performance metrics tracker."""

    def __init__(self):
        self.response_times: List[float] = []
        self.errors: List[Dict[str, Any]] = []
        self.costs: List[float] = []
        self.start_time = None
        self.end_time = None
        self._lock = threading.Lock()

    def record_response(self, duration_ms: float, cost_usd: float = 0.0, error: str = None):
        """Thread-safe response recording."""
        with self._lock:
            self.response_times.append(duration_ms)
            self.costs.append(cost_usd)
            if error:
                self.errors.append({
                    'error': error,
                    'timestamp': time.time(),
                    'duration_ms': duration_ms
                })

    def calculate_percentiles(self) -> Dict[str, float]:
        """Calculate p50, p95, p99 response times."""
        with self._lock:
            if not self.response_times:
                return {'p50': 0, 'p95': 0, 'p99': 0, 'min': 0, 'max': 0, 'mean': 0, 'stdev': 0}

            sorted_times = sorted(self.response_times)
            return {
                'p50': statistics.median(sorted_times),
                'p95': sorted_times[int(len(sorted_times) * 0.95)] if len(sorted_times) > 1 else sorted_times[0],
                'p99': sorted_times[int(len(sorted_times) * 0.99)] if len(sorted_times) > 1 else sorted_times[0],
                'min': min(sorted_times),
                'max': max(sorted_times),
                'mean': statistics.mean(sorted_times),
                'stdev': statistics.stdev(sorted_times) if len(sorted_times) > 1 else 0
            }

    def get_summary(self) -> Dict[str, Any]:
        """Get complete performance summary."""
        with self._lock:
            percentiles = self.calculate_percentiles()
            total_duration = (self.end_time - self.start_time) * 1000 if self.start_time and self.end_time else 0
            total_cost = sum(self.costs)

            return {
                'total_requests': len(self.response_times),
                'successful_requests': len(self.response_times) - len(self.errors),
                'failed_requests': len(self.errors),
                'error_rate': len(self.errors) / len(self.response_times) if self.response_times else 0,
                'response_times': percentiles,
                'total_duration_ms': total_duration,
                'total_cost_usd': total_cost,
                'avg_cost_per_request': total_cost / len(self.response_times) if self.response_times else 0,
                'throughput_rps': len(self.response_times) / (total_duration / 1000) if total_duration > 0 else 0,
                'errors': self.errors
            }


# Test fixtures
@pytest.fixture
def test_output_dir(tmp_path):
    """Create temporary directory for test outputs."""
    output_dir = tmp_path / "test_outputs"
    output_dir.mkdir()
    return output_dir


@pytest.fixture
def redis_client():
    """Create Redis client for testing."""
    client = RedisClient()
    yield client
    # Cleanup
    try:
        client.close()
    except:
        pass


@pytest.fixture
def vector_client():
    """Create Vector DB client for testing."""
    client = VectorClient()
    yield client
    # Cleanup
    try:
        client.close()
    except:
        pass


@pytest.fixture
def cost_tracker():
    """Create cost tracker for testing."""
    return CostTracker()


# Load Test 1: 10 Parallel Simple Features
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.requires_api
class TestParallelSimpleFeatures:
    """Test 10 parallel simple feature generation requests."""

    def test_10_parallel_simple_features(self, test_output_dir):
        """
        Simulate 10 users generating simple tests concurrently.

        Target Metrics:
        - Total time: <5 minutes (300s)
        - Total cost: <$5
        - P95 latency: <2s per feature
        - Zero errors
        """
        num_features = 10
        metrics = PerformanceMetrics()

        # Simple feature templates
        simple_features = [
            "user can click login button",
            "user can fill out contact form",
            "user can view product details",
            "user can add item to cart",
            "user can navigate to homepage",
            "user can open menu dropdown",
            "user can close modal dialog",
            "user can toggle dark mode",
            "user can search for products",
            "user can filter results"
        ]

        def generate_simple_test(i: int) -> Tuple[bool, float, float, str]:
            """Generate a simple test and measure time/cost."""
            start = time.time()
            try:
                # Create Scribe agent (each thread gets its own instance)
                scribe = ScribeAgent()

                feature = simple_features[i % len(simple_features)]
                result = scribe.execute(
                    task_description=feature,
                    feature_name=f"simple_feature_{i}",
                    output_path=str(test_output_dir / f"simple_{i}.spec.ts"),
                    complexity='easy'
                )

                duration_ms = (time.time() - start) * 1000
                cost = result.cost_usd if hasattr(result, 'cost_usd') else 0.0

                return result.success, duration_ms, cost, result.error or ""
            except Exception as e:
                duration_ms = (time.time() - start) * 1000
                return False, duration_ms, 0.0, str(e)

        # Execute concurrent requests
        print(f"\nStarting {num_features} parallel simple feature generations...")
        metrics.start_time = time.time()

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_features) as executor:
            futures = [executor.submit(generate_simple_test, i) for i in range(num_features)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        metrics.end_time = time.time()

        # Record metrics
        for success, duration_ms, cost, error in results:
            metrics.record_response(duration_ms, cost, error if not success else None)

        # Analyze results
        summary = metrics.get_summary()
        percentiles = summary['response_times']

        # Print detailed report
        self._print_load_test_report(
            "10 PARALLEL SIMPLE FEATURES",
            summary,
            target_duration_ms=300000,  # 5 minutes
            target_cost_usd=5.0,
            target_p95_ms=2000  # 2 seconds
        )

        # Assertions
        assert summary['error_rate'] == 0, f"Should have no errors, got {summary['failed_requests']} failures: {summary['errors']}"
        assert summary['total_duration_ms'] < 300000, f"Total time {summary['total_duration_ms']/1000:.2f}s exceeds 5min target"
        assert summary['total_cost_usd'] < 5.0, f"Total cost ${summary['total_cost_usd']:.2f} exceeds $5 target"
        assert percentiles['p95'] < 2000, f"P95 latency {percentiles['p95']:.2f}ms exceeds 2s target"

    def _print_load_test_report(self, title: str, summary: Dict, target_duration_ms: float, target_cost_usd: float, target_p95_ms: float):
        """Print formatted load test report."""
        percentiles = summary['response_times']

        print("\n" + "="*100)
        print(f"{title:^100}")
        print("="*100)

        print(f"\n{'REQUESTS':<30}")
        print(f"  Total Requests:              {summary['total_requests']}")
        print(f"  Successful:                  {summary['successful_requests']} ({summary['successful_requests']/summary['total_requests']*100:.1f}%)")
        print(f"  Failed:                      {summary['failed_requests']} ({summary['error_rate']*100:.1f}%)")

        print(f"\n{'RESPONSE TIMES (ms)':<30}")
        print(f"  P50 (Median):                {percentiles['p50']:.2f}ms")
        print(f"  P95:                         {percentiles['p95']:.2f}ms {'✓' if percentiles['p95'] < target_p95_ms else '✗ EXCEEDS TARGET'}")
        print(f"  P99:                         {percentiles['p99']:.2f}ms")
        print(f"  Min:                         {percentiles['min']:.2f}ms")
        print(f"  Max:                         {percentiles['max']:.2f}ms")
        print(f"  Mean:                        {percentiles['mean']:.2f}ms")
        print(f"  StdDev:                      {percentiles['stdev']:.2f}ms")

        print(f"\n{'DURATION & THROUGHPUT':<30}")
        print(f"  Total Duration:              {summary['total_duration_ms']/1000:.2f}s {'✓' if summary['total_duration_ms'] < target_duration_ms else '✗ EXCEEDS TARGET'}")
        print(f"  Target Duration:             {target_duration_ms/1000:.2f}s")
        print(f"  Throughput:                  {summary['throughput_rps']:.2f} requests/sec")

        print(f"\n{'COST ANALYSIS':<30}")
        print(f"  Total Cost:                  ${summary['total_cost_usd']:.4f} {'✓' if summary['total_cost_usd'] < target_cost_usd else '✗ EXCEEDS TARGET'}")
        print(f"  Target Cost:                 ${target_cost_usd:.2f}")
        print(f"  Avg Cost/Request:            ${summary['avg_cost_per_request']:.4f}")

        if summary['errors']:
            print(f"\n{'ERRORS':<30}")
            for i, error in enumerate(summary['errors'][:5], 1):  # Show first 5 errors
                print(f"  {i}. {error['error'][:80]}")

        print("="*100 + "\n")


# Load Test 2: 5 Parallel Complex Features
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.requires_api
class TestParallelComplexFeatures:
    """Test 5 parallel complex feature generation requests."""

    def test_5_parallel_complex_features(self, test_output_dir):
        """
        Simulate 5 complex features (auth, payment flows) concurrently.

        Target Metrics:
        - Total time: <15 minutes (900s)
        - Total cost: <$15
        - P95 latency: <5s per feature
        - Zero errors
        """
        num_features = 5
        metrics = PerformanceMetrics()

        # Complex feature templates
        complex_features = [
            "user can complete OAuth login with Google, including redirect handling and token exchange",
            "user can process payment with credit card including validation, 3DS verification, and receipt",
            "user can register account with email verification, password strength checks, and profile setup",
            "user can upload multiple files with progress tracking, validation, and preview generation",
            "user can participate in real-time chat with WebSocket connection, message history, and notifications"
        ]

        def generate_complex_test(i: int) -> Tuple[bool, float, float, str]:
            """Generate a complex test and measure time/cost."""
            start = time.time()
            try:
                # Create Scribe agent
                scribe = ScribeAgent()

                feature = complex_features[i]
                result = scribe.execute(
                    task_description=feature,
                    feature_name=f"complex_feature_{i}",
                    output_path=str(test_output_dir / f"complex_{i}.spec.ts"),
                    complexity='hard'
                )

                duration_ms = (time.time() - start) * 1000
                cost = result.cost_usd if hasattr(result, 'cost_usd') else 0.0

                return result.success, duration_ms, cost, result.error or ""
            except Exception as e:
                duration_ms = (time.time() - start) * 1000
                return False, duration_ms, 0.0, str(e)

        # Execute concurrent requests
        print(f"\nStarting {num_features} parallel complex feature generations...")
        metrics.start_time = time.time()

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_features) as executor:
            futures = [executor.submit(generate_complex_test, i) for i in range(num_features)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        metrics.end_time = time.time()

        # Record metrics
        for success, duration_ms, cost, error in results:
            metrics.record_response(duration_ms, cost, error if not success else None)

        # Analyze results
        summary = metrics.get_summary()
        percentiles = summary['response_times']

        # Print detailed report
        self._print_load_test_report(
            "5 PARALLEL COMPLEX FEATURES",
            summary,
            target_duration_ms=900000,  # 15 minutes
            target_cost_usd=15.0,
            target_p95_ms=5000  # 5 seconds
        )

        # Assertions
        assert summary['error_rate'] == 0, f"Should have no errors, got {summary['failed_requests']} failures"
        assert summary['total_duration_ms'] < 900000, f"Total time {summary['total_duration_ms']/1000:.2f}s exceeds 15min target"
        assert summary['total_cost_usd'] < 15.0, f"Total cost ${summary['total_cost_usd']:.2f} exceeds $15 target"
        assert percentiles['p95'] < 5000, f"P95 latency {percentiles['p95']:.2f}ms exceeds 5s target"

    def _print_load_test_report(self, title: str, summary: Dict, target_duration_ms: float, target_cost_usd: float, target_p95_ms: float):
        """Print formatted load test report (same as simple features)."""
        percentiles = summary['response_times']

        print("\n" + "="*100)
        print(f"{title:^100}")
        print("="*100)

        print(f"\n{'REQUESTS':<30}")
        print(f"  Total Requests:              {summary['total_requests']}")
        print(f"  Successful:                  {summary['successful_requests']} ({summary['successful_requests']/summary['total_requests']*100:.1f}%)")
        print(f"  Failed:                      {summary['failed_requests']} ({summary['error_rate']*100:.1f}%)")

        print(f"\n{'RESPONSE TIMES (ms)':<30}")
        print(f"  P50 (Median):                {percentiles['p50']:.2f}ms")
        print(f"  P95:                         {percentiles['p95']:.2f}ms {'✓' if percentiles['p95'] < target_p95_ms else '✗ EXCEEDS TARGET'}")
        print(f"  P99:                         {percentiles['p99']:.2f}ms")
        print(f"  Min:                         {percentiles['min']:.2f}ms")
        print(f"  Max:                         {percentiles['max']:.2f}ms")
        print(f"  Mean:                        {percentiles['mean']:.2f}ms")
        print(f"  StdDev:                      {percentiles['stdev']:.2f}ms")

        print(f"\n{'DURATION & THROUGHPUT':<30}")
        print(f"  Total Duration:              {summary['total_duration_ms']/1000:.2f}s {'✓' if summary['total_duration_ms'] < target_duration_ms else '✗ EXCEEDS TARGET'}")
        print(f"  Target Duration:             {target_duration_ms/1000:.2f}s")
        print(f"  Throughput:                  {summary['throughput_rps']:.2f} requests/sec")

        print(f"\n{'COST ANALYSIS':<30}")
        print(f"  Total Cost:                  ${summary['total_cost_usd']:.4f} {'✓' if summary['total_cost_usd'] < target_cost_usd else '✗ EXCEEDS TARGET'}")
        print(f"  Target Cost:                 ${target_cost_usd:.2f}")
        print(f"  Avg Cost/Request:            ${summary['avg_cost_per_request']:.4f}")

        if summary['errors']:
            print(f"\n{'ERRORS':<30}")
            for i, error in enumerate(summary['errors'][:5], 1):
                print(f"  {i}. {error['error'][:80]}")

        print("="*100 + "\n")


# Load Test 3: Redis Connection Pool Under Load
@pytest.mark.integration
@pytest.mark.requires_redis
class TestRedisConnectionPoolUnderLoad:
    """Verify Redis connection pooling works under load."""

    def test_redis_connection_pool_under_load(self, redis_client):
        """
        Test Redis connection pool with 100 concurrent operations.
        Verifies no connection errors occur and performance remains good.
        """
        num_operations = 100
        metrics = PerformanceMetrics()

        def redis_operation(i: int) -> Tuple[bool, float, str]:
            """Perform typical Redis operations."""
            start = time.time()
            try:
                session_id = f"load_test_session_{i}"
                task_id = f"load_test_task_{i}"

                # Write operations
                redis_client.set_session(session_id, {
                    'user_id': i,
                    'feature': f'feature_{i}',
                    'created_at': time.time()
                })
                redis_client.push_task(task_id)
                redis_client.set_task_status(task_id, 'pending')

                # Read operations
                session = redis_client.get_session(session_id)
                status = redis_client.get_task_status(task_id)
                queue_len = redis_client.queue_length()

                # Cleanup
                redis_client.delete_session(session_id)
                redis_client.delete(f"task:{task_id}:status")

                duration_ms = (time.time() - start) * 1000

                # Verify
                if not session or status != 'pending':
                    return False, duration_ms, "Data verification failed"

                return True, duration_ms, ""
            except Exception as e:
                duration_ms = (time.time() - start) * 1000
                return False, duration_ms, str(e)

        # Execute concurrent operations
        print(f"\nStarting {num_operations} concurrent Redis operations...")
        metrics.start_time = time.time()

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(redis_operation, i) for i in range(num_operations)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        metrics.end_time = time.time()

        # Record metrics
        for success, duration_ms, error in results:
            metrics.record_response(duration_ms, 0.0, error if not success else None)

        # Analyze results
        summary = metrics.get_summary()
        percentiles = summary['response_times']

        print("\n" + "="*80)
        print("REDIS CONNECTION POOL LOAD TEST")
        print("="*80)
        print(f"Total Operations:    {summary['total_requests']}")
        print(f"Successful:          {summary['successful_requests']}")
        print(f"Failed:              {summary['failed_requests']}")
        print(f"Error Rate:          {summary['error_rate']:.2%}")
        print(f"\nResponse Times:")
        print(f"  P50: {percentiles['p50']:.2f}ms")
        print(f"  P95: {percentiles['p95']:.2f}ms")
        print(f"  P99: {percentiles['p99']:.2f}ms")
        print(f"\nThroughput:          {summary['throughput_rps']:.2f} ops/sec")
        print(f"Connection Pool:     max_connections={redis_client.config.max_connections}")
        print("="*80 + "\n")

        # Assertions
        assert summary['error_rate'] == 0, f"Should have zero connection errors, got {summary['failed_requests']}"
        assert percentiles['p95'] < 100, f"P95 latency {percentiles['p95']:.2f}ms too high for Redis"


# Load Test 4: Vector DB Concurrent Writes
@pytest.mark.integration
@pytest.mark.requires_vectordb
class TestVectorDBConcurrentWrites:
    """Test ChromaDB handles concurrent test pattern storage."""

    def test_vector_db_concurrent_writes(self, vector_client):
        """
        Test Vector DB with 50 concurrent embedding generation and storage operations.
        Verifies no race conditions and embeddings are cached properly.
        """
        num_patterns = 50
        metrics = PerformanceMetrics()

        def store_test_pattern(i: int) -> Tuple[bool, float, str]:
            """Store a test pattern and measure time."""
            start = time.time()
            try:
                test_id = f"load_test_pattern_{i}"
                test_code = f"""
import {{ test, expect }} from '@playwright/test';

test.describe('Feature {i}', () => {{
  test('should work correctly', async ({{ page }}) => {{
    await page.goto('/feature-{i}');
    await expect(page).toHaveTitle(/Feature {i}/);
  }});
}});
"""
                metadata = {
                    'feature': f'feature_{i}',
                    'complexity': 'easy' if i % 2 == 0 else 'hard',
                    'timestamp': time.time()
                }

                success = vector_client.store_test_pattern(test_id, test_code, metadata)
                duration_ms = (time.time() - start) * 1000

                return success, duration_ms, "" if success else "Storage failed"
            except Exception as e:
                duration_ms = (time.time() - start) * 1000
                return False, duration_ms, str(e)

        # Execute concurrent writes
        print(f"\nStarting {num_patterns} concurrent Vector DB writes...")
        metrics.start_time = time.time()

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(store_test_pattern, i) for i in range(num_patterns)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        metrics.end_time = time.time()

        # Record metrics
        for success, duration_ms, error in results:
            metrics.record_response(duration_ms, 0.0, error if not success else None)

        # Analyze results
        summary = metrics.get_summary()
        percentiles = summary['response_times']

        print("\n" + "="*80)
        print("VECTOR DB CONCURRENT WRITES TEST")
        print("="*80)
        print(f"Total Writes:        {summary['total_requests']}")
        print(f"Successful:          {summary['successful_requests']}")
        print(f"Failed:              {summary['failed_requests']}")
        print(f"Error Rate:          {summary['error_rate']:.2%}")
        print(f"\nResponse Times:")
        print(f"  P50: {percentiles['p50']:.2f}ms")
        print(f"  P95: {percentiles['p95']:.2f}ms")
        print(f"  P99: {percentiles['p99']:.2f}ms")
        print(f"\nThroughput:          {summary['throughput_rps']:.2f} writes/sec")
        print(f"Embedding Cache:     LRU cache (maxsize=1000)")
        print("="*80 + "\n")

        # Assertions
        assert summary['error_rate'] == 0, f"Should have no write errors, got {summary['failed_requests']}"
        assert percentiles['p95'] < 1000, f"P95 latency {percentiles['p95']:.2f}ms too high"


# Load Test 5: Cost Tracking Accuracy Under Load
@pytest.mark.integration
@pytest.mark.requires_redis
class TestCostTrackingAccuracyUnderLoad:
    """Ensure cost tracking doesn't lose data under concurrent load."""

    def test_cost_tracking_accurate_under_load(self, cost_tracker):
        """
        Test cost tracker with 100 concurrent cost logging operations.
        Verifies no race conditions and all costs are accurately recorded.
        """
        num_operations = 100
        expected_total_cost = 0.0
        cost_increments = []
        lock = threading.Lock()

        def log_cost(i: int) -> Tuple[bool, str]:
            """Log a cost entry."""
            try:
                # Vary costs to test accuracy
                cost = 0.001 * (i + 1)  # $0.001, $0.002, $0.003, etc.

                with lock:
                    cost_increments.append(cost)

                cost_tracker.log_cost(
                    agent='scribe' if i % 2 == 0 else 'runner',
                    model='claude-haiku' if i % 3 == 0 else 'claude-sonnet',
                    task_type='write_test',
                    feature=f'feature_{i}',
                    cost_usd=cost,
                    input_tokens=100 * i,
                    output_tokens=50 * i,
                    metadata={'test_id': i}
                )

                return True, ""
            except Exception as e:
                return False, str(e)

        # Execute concurrent cost logging
        print(f"\nStarting {num_operations} concurrent cost logging operations...")
        start_time = time.time()

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(log_cost, i) for i in range(num_operations)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        duration_ms = (time.time() - start_time) * 1000

        # Calculate expected total
        expected_total_cost = sum(cost_increments)

        # Get actual total from cost tracker
        daily_report = cost_tracker.get_daily_report()
        actual_total_cost = daily_report['total_cost_usd']

        # Count successes
        successes = sum(1 for success, _ in results if success)
        failures = len(results) - successes

        print("\n" + "="*80)
        print("COST TRACKING ACCURACY UNDER LOAD")
        print("="*80)
        print(f"Total Operations:    {num_operations}")
        print(f"Successful:          {successes}")
        print(f"Failed:              {failures}")
        print(f"Duration:            {duration_ms:.2f}ms")
        print(f"\nCost Accuracy:")
        print(f"  Expected Total:    ${expected_total_cost:.6f}")
        print(f"  Actual Total:      ${actual_total_cost:.6f}")
        print(f"  Difference:        ${abs(expected_total_cost - actual_total_cost):.6f}")
        print(f"  Accuracy:          {(1 - abs(expected_total_cost - actual_total_cost) / expected_total_cost) * 100:.2f}%")
        print("="*80 + "\n")

        # Assertions
        assert failures == 0, f"Should have no failures, got {failures}"
        assert abs(expected_total_cost - actual_total_cost) < 0.0001, \
            f"Cost tracking inaccurate: expected ${expected_total_cost:.6f}, got ${actual_total_cost:.6f}"


# Stress Test: Rate Limiter Fairness
@pytest.mark.integration
class TestRateLimiterDistributesFairly:
    """Verify rate limiting doesn't starve requests."""

    def test_rate_limiter_distributes_fairly(self):
        """
        Test that under high load, all requests eventually complete
        and no requests are indefinitely starved.

        This is a conceptual test - actual rate limiting would need
        to be implemented in the Router or a middleware layer.
        """
        # This test would verify rate limiting behavior once implemented
        # For now, it serves as a placeholder and documentation

        print("\n" + "="*80)
        print("RATE LIMITER FAIRNESS TEST")
        print("="*80)
        print("Note: Rate limiting not yet implemented in SuperAgent")
        print("This test will be implemented when rate limiting is added")
        print("="*80 + "\n")

        # Placeholder assertion
        assert True, "Rate limiting not yet implemented"


if __name__ == '__main__':
    """Run load tests directly."""
    pytest.main([__file__, '-v', '-s', '--tb=short'])
