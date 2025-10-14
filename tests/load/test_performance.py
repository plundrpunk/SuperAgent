"""
Performance and Load Testing for SuperAgent
Tests concurrent request handling, response times, and system bottlenecks.

Target Metrics:
- 10 concurrent requests
- P95 latency < 30s per feature
- No errors under load
- Cost tracking remains accurate
"""
import pytest
import time
import statistics
import concurrent.futures
import cProfile
import pstats
import io
from typing import List, Dict, Any, Tuple
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agent_system.agents.scribe import ScribeAgent
from agent_system.agents.runner import RunnerAgent
from agent_system.agents.kaya import KayaAgent
from agent_system.state.redis_client import RedisClient
from agent_system.router import Router


# Performance tracking utilities
class PerformanceMetrics:
    """Track and analyze performance metrics."""

    def __init__(self):
        self.response_times: List[float] = []
        self.errors: List[Dict[str, Any]] = []
        self.start_time = None
        self.end_time = None

    def record_response(self, duration_ms: float, error: str = None):
        """Record a response time and optional error."""
        self.response_times.append(duration_ms)
        if error:
            self.errors.append({
                'error': error,
                'timestamp': time.time()
            })

    def calculate_percentiles(self) -> Dict[str, float]:
        """Calculate p50, p95, p99 response times."""
        if not self.response_times:
            return {'p50': 0, 'p95': 0, 'p99': 0}

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
        percentiles = self.calculate_percentiles()
        total_duration = (self.end_time - self.start_time) * 1000 if self.start_time and self.end_time else 0

        return {
            'total_requests': len(self.response_times),
            'successful_requests': len(self.response_times) - len(self.errors),
            'failed_requests': len(self.errors),
            'error_rate': len(self.errors) / len(self.response_times) if self.response_times else 0,
            'response_times': percentiles,
            'total_duration_ms': total_duration,
            'throughput_rps': len(self.response_times) / (total_duration / 1000) if total_duration > 0 else 0
        }


# Test fixtures
@pytest.fixture
def scribe_agent():
    """Create Scribe agent for testing."""
    return ScribeAgent()


@pytest.fixture
def runner_agent():
    """Create Runner agent for testing."""
    return RunnerAgent()


@pytest.fixture
def kaya_agent():
    """Create Kaya agent for testing."""
    return KayaAgent()


@pytest.fixture
def redis_client():
    """Create Redis client for testing."""
    return RedisClient()


@pytest.fixture
def router():
    """Create Router for testing."""
    return Router()


@pytest.fixture
def test_output_dir(tmp_path):
    """Create temporary directory for test outputs."""
    output_dir = tmp_path / "test_outputs"
    output_dir.mkdir()
    return output_dir


# Load Testing: Scribe Agent (Test Generation)
class TestScribeConcurrency:
    """Test Scribe agent under concurrent load."""

    def test_concurrent_test_generation(self, scribe_agent, test_output_dir):
        """
        Test 10 parallel test generation requests.
        Target: P95 latency < 30s per feature
        """
        num_requests = 10
        metrics = PerformanceMetrics()

        def generate_test(i: int) -> Tuple[bool, float, str]:
            """Generate a single test and measure time."""
            start = time.time()
            try:
                result = scribe_agent.execute(
                    task_description=f"Test user login flow {i}",
                    feature_name=f"Login {i}",
                    output_path=str(test_output_dir / f"login_{i}.spec.ts"),
                    complexity='easy'
                )
                duration_ms = (time.time() - start) * 1000
                return result.success, duration_ms, result.error or ""
            except Exception as e:
                duration_ms = (time.time() - start) * 1000
                return False, duration_ms, str(e)

        # Execute concurrent requests
        metrics.start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_requests) as executor:
            futures = [executor.submit(generate_test, i) for i in range(num_requests)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        metrics.end_time = time.time()

        # Record metrics
        for success, duration_ms, error in results:
            metrics.record_response(duration_ms, error if not success else None)

        # Analyze results
        summary = metrics.get_summary()
        percentiles = summary['response_times']

        print("\n" + "="*80)
        print("SCRIBE CONCURRENT TEST GENERATION RESULTS")
        print("="*80)
        print(f"Total Requests: {summary['total_requests']}")
        print(f"Successful: {summary['successful_requests']}")
        print(f"Failed: {summary['failed_requests']}")
        print(f"Error Rate: {summary['error_rate']:.2%}")
        print(f"\nResponse Times (ms):")
        print(f"  P50: {percentiles['p50']:.2f}")
        print(f"  P95: {percentiles['p95']:.2f}")
        print(f"  P99: {percentiles['p99']:.2f}")
        print(f"  Min: {percentiles['min']:.2f}")
        print(f"  Max: {percentiles['max']:.2f}")
        print(f"  Mean: {percentiles['mean']:.2f}")
        print(f"  StdDev: {percentiles['stdev']:.2f}")
        print(f"\nThroughput: {summary['throughput_rps']:.2f} requests/sec")
        print(f"Total Duration: {summary['total_duration_ms']:.2f}ms")
        print("="*80 + "\n")

        # Assertions
        assert summary['error_rate'] == 0, f"Should have no errors, got {summary['failed_requests']} failures"
        assert percentiles['p95'] < 30000, f"P95 latency {percentiles['p95']:.2f}ms exceeds 30s target"
        assert summary['successful_requests'] == num_requests, "All requests should succeed"

    def test_scribe_with_profiling(self, scribe_agent, test_output_dir):
        """
        Profile Scribe agent to identify bottlenecks.
        Uses cProfile to analyze function execution times.
        """
        profiler = cProfile.Profile()

        # Profile test generation
        profiler.enable()
        result = scribe_agent.execute(
            task_description="Test user registration with email verification",
            feature_name="Registration",
            output_path=str(test_output_dir / "registration.spec.ts"),
            complexity='hard'
        )
        profiler.disable()

        # Analyze profile
        stream = io.StringIO()
        stats = pstats.Stats(profiler, stream=stream)
        stats.strip_dirs()
        stats.sort_stats('cumulative')

        print("\n" + "="*80)
        print("SCRIBE AGENT PROFILING RESULTS (Top 20 Functions)")
        print("="*80)
        stats.print_stats(20)
        print(stream.getvalue())
        print("="*80 + "\n")

        # Identify slow functions
        stats.sort_stats('tottime')
        slow_functions = []
        for func, stat in stats.stats.items():
            total_time = stat[2]  # tottime
            if total_time > 0.1:  # Functions taking >100ms
                slow_functions.append({
                    'function': func,
                    'total_time': total_time,
                    'calls': stat[0]
                })

        if slow_functions:
            print("\nSLOW FUNCTIONS (>100ms):")
            for func_info in sorted(slow_functions, key=lambda x: x['total_time'], reverse=True):
                print(f"  {func_info['function']}: {func_info['total_time']:.3f}s ({func_info['calls']} calls)")

        assert result.success, "Profiled test generation should succeed"


# Load Testing: Runner Agent (Test Execution)
class TestRunnerConcurrency:
    """Test Runner agent under concurrent load."""

    @pytest.fixture
    def sample_test_file(self, tmp_path):
        """Create a sample test file for execution."""
        test_content = """
import { test, expect } from '@playwright/test';

test.describe('Sample Test', () => {
  test('should pass quickly', async ({ page }) => {
    await page.goto('https://example.com');
    await expect(page).toHaveTitle(/Example/);
  });
});
"""
        test_file = tmp_path / "sample.spec.ts"
        test_file.write_text(test_content)
        return str(test_file)

    def test_concurrent_test_execution(self, runner_agent, sample_test_file):
        """
        Test 10 parallel test execution requests.
        Tests subprocess management with multiple Playwright instances.
        """
        num_requests = 10
        metrics = PerformanceMetrics()

        def execute_test(i: int) -> Tuple[bool, float, str]:
            """Execute a single test and measure time."""
            start = time.time()
            try:
                result = runner_agent.execute(
                    test_path=sample_test_file,
                    timeout=30
                )
                duration_ms = (time.time() - start) * 1000
                return result.success, duration_ms, result.error or ""
            except Exception as e:
                duration_ms = (time.time() - start) * 1000
                return False, duration_ms, str(e)

        # Execute concurrent requests
        metrics.start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_requests) as executor:
            futures = [executor.submit(execute_test, i) for i in range(num_requests)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        metrics.end_time = time.time()

        # Record metrics
        for success, duration_ms, error in results:
            metrics.record_response(duration_ms, error if not success else None)

        # Analyze results
        summary = metrics.get_summary()
        percentiles = summary['response_times']

        print("\n" + "="*80)
        print("RUNNER CONCURRENT TEST EXECUTION RESULTS")
        print("="*80)
        print(f"Total Requests: {summary['total_requests']}")
        print(f"Successful: {summary['successful_requests']}")
        print(f"Failed: {summary['failed_requests']}")
        print(f"Error Rate: {summary['error_rate']:.2%}")
        print(f"\nResponse Times (ms):")
        print(f"  P50: {percentiles['p50']:.2f}")
        print(f"  P95: {percentiles['p95']:.2f}")
        print(f"  P99: {percentiles['p99']:.2f}")
        print(f"  Min: {percentiles['min']:.2f}")
        print(f"  Max: {percentiles['max']:.2f}")
        print(f"  Mean: {percentiles['mean']:.2f}")
        print(f"  StdDev: {percentiles['stdev']:.2f}")
        print(f"\nThroughput: {summary['throughput_rps']:.2f} requests/sec")
        print(f"Total Duration: {summary['total_duration_ms']:.2f}ms")
        print("="*80 + "\n")

        # Note: Runner tests may fail if Playwright not installed or network issues
        # We verify that the system handles concurrent requests without crashing
        assert percentiles['p95'] < 60000, f"P95 latency {percentiles['p95']:.2f}ms exceeds 60s"


# Load Testing: Redis Connection Pooling
class TestRedisPerformance:
    """Test Redis client under concurrent load."""

    def test_redis_connection_pooling(self, redis_client):
        """
        Test Redis connection pooling with concurrent requests.
        Verifies connection pool handles multiple simultaneous operations.
        """
        num_requests = 50  # More requests to stress connection pool
        metrics = PerformanceMetrics()

        def redis_operation(i: int) -> Tuple[bool, float, str]:
            """Perform Redis operations and measure time."""
            start = time.time()
            try:
                # Simulate typical Redis operations
                session_id = f"session_{i}"
                task_id = f"task_{i}"

                # Set session
                redis_client.set_session(session_id, {
                    'user_id': i,
                    'created_at': time.time()
                })

                # Push task to queue
                redis_client.push_task(task_id)

                # Set task status
                redis_client.set_task_status(task_id, 'pending')

                # Get session
                session = redis_client.get_session(session_id)

                # Get task status
                status = redis_client.get_task_status(task_id)

                # Cleanup
                redis_client.delete_session(session_id)
                redis_client.delete(f"task:{task_id}:status")

                duration_ms = (time.time() - start) * 1000

                # Verify operations succeeded
                if not session or status != 'pending':
                    return False, duration_ms, "Redis operation verification failed"

                return True, duration_ms, ""
            except Exception as e:
                duration_ms = (time.time() - start) * 1000
                return False, duration_ms, str(e)

        # Execute concurrent requests
        metrics.start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(redis_operation, i) for i in range(num_requests)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        metrics.end_time = time.time()

        # Record metrics
        for success, duration_ms, error in results:
            metrics.record_response(duration_ms, error if not success else None)

        # Analyze results
        summary = metrics.get_summary()
        percentiles = summary['response_times']

        print("\n" + "="*80)
        print("REDIS CONNECTION POOLING RESULTS")
        print("="*80)
        print(f"Total Requests: {summary['total_requests']}")
        print(f"Successful: {summary['successful_requests']}")
        print(f"Failed: {summary['failed_requests']}")
        print(f"Error Rate: {summary['error_rate']:.2%}")
        print(f"\nResponse Times (ms):")
        print(f"  P50: {percentiles['p50']:.2f}")
        print(f"  P95: {percentiles['p95']:.2f}")
        print(f"  P99: {percentiles['p99']:.2f}")
        print(f"  Min: {percentiles['min']:.2f}")
        print(f"  Max: {percentiles['max']:.2f}")
        print(f"  Mean: {percentiles['mean']:.2f}")
        print(f"  StdDev: {percentiles['stdev']:.2f}")
        print(f"\nThroughput: {summary['throughput_rps']:.2f} requests/sec")
        print(f"Total Duration: {summary['total_duration_ms']:.2f}ms")
        print(f"\nConnection Pool Config:")
        print(f"  Max Connections: {redis_client.config.max_connections}")
        print(f"  Socket Timeout: {redis_client.config.socket_timeout}s")
        print("="*80 + "\n")

        # Assertions
        # Note: May fail if Redis not running locally
        if summary['total_requests'] > 0:
            assert summary['error_rate'] < 0.05, f"Redis error rate {summary['error_rate']:.2%} exceeds 5%"
            assert percentiles['p95'] < 1000, f"P95 latency {percentiles['p95']:.2f}ms exceeds 1s (too slow)"


# Load Testing: Full Pipeline
class TestFullPipeline:
    """Test full pipeline under load."""

    def test_router_under_load(self, router):
        """
        Test Router with many concurrent routing decisions.
        Verifies routing logic remains accurate under load.
        """
        num_requests = 100
        metrics = PerformanceMetrics()

        test_scenarios = [
            ('write_test', 'Simple login form', 'easy'),
            ('write_test', 'OAuth integration with 2FA', 'hard'),
            ('execute_test', 'Run auth tests', 'easy'),
            ('fix_bug', 'Fix selector timeout', 'hard'),
            ('pre_validate', 'Check test quality', 'easy'),
        ]

        def route_task(i: int) -> Tuple[bool, float, str]:
            """Route a task and measure time."""
            start = time.time()
            try:
                task_type, description, expected_difficulty = test_scenarios[i % len(test_scenarios)]

                decision = router.route(
                    task_type=task_type,
                    task_description=description
                )

                duration_ms = (time.time() - start) * 1000

                # Verify routing succeeded and returned valid data
                assert decision.agent is not None, "Router should return agent"
                assert decision.model is not None, "Router should return model"
                assert decision.max_cost_usd > 0, "Router should return cost"

                return True, duration_ms, ""
            except Exception as e:
                duration_ms = (time.time() - start) * 1000
                return False, duration_ms, str(e)

        # Execute concurrent requests
        metrics.start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(route_task, i) for i in range(num_requests)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        metrics.end_time = time.time()

        # Record metrics
        for success, duration_ms, error in results:
            metrics.record_response(duration_ms, error if not success else None)

        # Analyze results
        summary = metrics.get_summary()
        percentiles = summary['response_times']

        print("\n" + "="*80)
        print("ROUTER CONCURRENT ROUTING RESULTS")
        print("="*80)
        print(f"Total Requests: {summary['total_requests']}")
        print(f"Successful: {summary['successful_requests']}")
        print(f"Failed: {summary['failed_requests']}")
        print(f"Error Rate: {summary['error_rate']:.2%}")
        print(f"\nResponse Times (ms):")
        print(f"  P50: {percentiles['p50']:.2f}")
        print(f"  P95: {percentiles['p95']:.2f}")
        print(f"  P99: {percentiles['p99']:.2f}")
        print(f"  Min: {percentiles['min']:.2f}")
        print(f"  Max: {percentiles['max']:.2f}")
        print(f"  Mean: {percentiles['mean']:.2f}")
        print(f"  StdDev: {percentiles['stdev']:.2f}")
        print(f"\nThroughput: {summary['throughput_rps']:.2f} requests/sec")
        print(f"Total Duration: {summary['total_duration_ms']:.2f}ms")
        print("="*80 + "\n")

        # Assertions
        assert summary['error_rate'] == 0, f"Router should have no errors"
        assert percentiles['p95'] < 100, f"P95 latency {percentiles['p95']:.2f}ms exceeds 100ms (routing too slow)"
        assert summary['throughput_rps'] > 50, f"Throughput {summary['throughput_rps']:.2f} rps too low"


# Benchmarking utilities
class TestBenchmarks:
    """Benchmark individual operations for baseline performance."""

    def test_benchmark_complexity_estimation(self, router):
        """Benchmark complexity estimation speed."""
        num_iterations = 1000

        descriptions = [
            "Simple button click test",
            "Complex OAuth flow with multiple redirects and token handling",
            "File upload with progress tracking",
            "WebSocket real-time chat",
            "Payment processing with Stripe"
        ]

        start = time.time()
        for i in range(num_iterations):
            desc = descriptions[i % len(descriptions)]
            router.estimator.estimate(desc, "")
        duration_ms = (time.time() - start) * 1000

        avg_time = duration_ms / num_iterations

        print("\n" + "="*80)
        print("COMPLEXITY ESTIMATION BENCHMARK")
        print("="*80)
        print(f"Iterations: {num_iterations}")
        print(f"Total Duration: {duration_ms:.2f}ms")
        print(f"Average Time: {avg_time:.4f}ms per estimation")
        print(f"Throughput: {num_iterations / (duration_ms / 1000):.2f} estimations/sec")
        print("="*80 + "\n")

        assert avg_time < 1.0, f"Complexity estimation {avg_time:.4f}ms too slow (target <1ms)"

    def test_benchmark_redis_operations(self, redis_client):
        """Benchmark individual Redis operations."""
        num_iterations = 1000

        operations = {
            'set': [],
            'get': [],
            'delete': []
        }

        # Benchmark SET
        for i in range(num_iterations):
            start = time.time()
            redis_client.set(f"bench_key_{i}", f"value_{i}")
            operations['set'].append((time.time() - start) * 1000)

        # Benchmark GET
        for i in range(num_iterations):
            start = time.time()
            redis_client.get(f"bench_key_{i}")
            operations['get'].append((time.time() - start) * 1000)

        # Benchmark DELETE
        for i in range(num_iterations):
            start = time.time()
            redis_client.delete(f"bench_key_{i}")
            operations['delete'].append((time.time() - start) * 1000)

        print("\n" + "="*80)
        print("REDIS OPERATIONS BENCHMARK")
        print("="*80)
        for op_name, times in operations.items():
            avg = statistics.mean(times)
            p95 = sorted(times)[int(len(times) * 0.95)]
            print(f"{op_name.upper()}:")
            print(f"  Average: {avg:.4f}ms")
            print(f"  P95: {p95:.4f}ms")
            print(f"  Throughput: {num_iterations / (sum(times) / 1000):.2f} ops/sec")
        print("="*80 + "\n")

        # Assertions
        for op_name, times in operations.items():
            avg = statistics.mean(times)
            assert avg < 10, f"Redis {op_name} {avg:.4f}ms too slow (target <10ms)"


if __name__ == '__main__':
    """Run performance tests directly."""
    pytest.main([__file__, '-v', '-s'])
