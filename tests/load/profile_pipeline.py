"""
Performance Profiling for SuperAgent Pipeline
Identifies bottlenecks in agent communication, Redis, and Vector DB operations.

Usage:
    python tests/load/profile_pipeline.py [--component kaya|scribe|runner|redis|vector]
"""
import cProfile
import pstats
import io
import time
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Any
import statistics

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agent_system.agents.kaya import KayaAgent
from agent_system.agents.scribe import ScribeAgent
from agent_system.agents.runner import RunnerAgent
from agent_system.state.redis_client import RedisClient
from agent_system.state.vector_client import VectorClient
from agent_system.router import Router


class ProfilerResults:
    """Store and analyze profiling results."""

    def __init__(self, component_name: str):
        self.component_name = component_name
        self.profiler = cProfile.Profile()
        self.start_time = None
        self.end_time = None
        self.operation_times = []

    def start(self):
        """Start profiling."""
        self.start_time = time.time()
        self.profiler.enable()

    def stop(self):
        """Stop profiling."""
        self.profiler.disable()
        self.end_time = time.time()

    def add_operation_time(self, duration_ms: float):
        """Record individual operation time."""
        self.operation_times.append(duration_ms)

    def get_top_functions(self, n: int = 20, sort_by: str = 'cumulative') -> List[Dict]:
        """Get top N slowest functions."""
        stream = io.StringIO()
        stats = pstats.Stats(self.profiler, stream=stream)
        stats.strip_dirs()
        stats.sort_stats(sort_by)

        # Extract top functions
        top_functions = []
        for func, (cc, nc, tt, ct, callers) in list(stats.stats.items())[:n]:
            top_functions.append({
                'function': func,
                'calls': nc,
                'tottime': tt,
                'cumtime': ct,
                'percall_tottime': tt / nc if nc > 0 else 0,
                'percall_cumtime': ct / nc if nc > 0 else 0
            })

        return top_functions

    def print_report(self):
        """Print comprehensive profiling report."""
        total_duration = (self.end_time - self.start_time) * 1000 if self.start_time and self.end_time else 0

        print("\n" + "="*100)
        print(f"PERFORMANCE PROFILE: {self.component_name.upper()}")
        print("="*100)

        print(f"\nTotal Duration: {total_duration:.2f}ms")

        if self.operation_times:
            print(f"\nOperation Statistics:")
            print(f"  Count: {len(self.operation_times)}")
            print(f"  Mean: {statistics.mean(self.operation_times):.2f}ms")
            print(f"  Median: {statistics.median(self.operation_times):.2f}ms")
            print(f"  Min: {min(self.operation_times):.2f}ms")
            print(f"  Max: {max(self.operation_times):.2f}ms")
            if len(self.operation_times) > 1:
                print(f"  StdDev: {statistics.stdev(self.operation_times):.2f}ms")

        # Print top functions by cumulative time
        print(f"\nTop Functions (by cumulative time):")
        print(f"{'Function':<50} {'Calls':>10} {'TotTime':>12} {'CumTime':>12} {'Per Call':>12}")
        print("-" * 100)

        top_funcs = self.get_top_functions(n=20, sort_by='cumulative')
        for func in top_funcs:
            func_name = f"{func['function'][0]}:{func['function'][1]}:{func['function'][2]}"
            if len(func_name) > 50:
                func_name = "..." + func_name[-47:]

            print(f"{func_name:<50} {func['calls']:>10} {func['tottime']:>12.3f}s {func['cumtime']:>12.3f}s {func['percall_cumtime']*1000:>11.2f}ms")

        # Print top functions by total time (self time)
        print(f"\nTop Functions (by self time):")
        print(f"{'Function':<50} {'Calls':>10} {'TotTime':>12} {'Per Call':>12}")
        print("-" * 100)

        top_funcs_self = self.get_top_functions(n=20, sort_by='tottime')
        for func in top_funcs_self:
            func_name = f"{func['function'][0]}:{func['function'][1]}:{func['function'][2]}"
            if len(func_name) > 50:
                func_name = "..." + func_name[-47:]

            print(f"{func_name:<50} {func['calls']:>10} {func['tottime']:>12.3f}s {func['percall_tottime']*1000:>11.2f}ms")

        print("\n" + "="*100 + "\n")

    def identify_bottlenecks(self, threshold_ms: float = 100) -> List[Dict]:
        """Identify functions taking > threshold_ms."""
        bottlenecks = []

        for func, (cc, nc, tt, ct, callers) in self.profiler.stats.items():
            if tt * 1000 > threshold_ms:  # Convert to ms
                bottlenecks.append({
                    'function': func,
                    'tottime_ms': tt * 1000,
                    'calls': nc,
                    'per_call_ms': (tt / nc * 1000) if nc > 0 else 0
                })

        # Sort by total time
        bottlenecks.sort(key=lambda x: x['tottime_ms'], reverse=True)
        return bottlenecks


# Profiling functions for each component

def profile_kaya_orchestrator(tmp_path: Path) -> ProfilerResults:
    """Profile Kaya orchestrator."""
    print("\nProfiling Kaya Orchestrator...")

    results = ProfilerResults("Kaya Orchestrator")
    kaya = KayaAgent()

    # Test commands
    commands = [
        "create test for user login",
        "create test for product search",
        "create test for checkout flow"
    ]

    results.start()

    for cmd in commands:
        op_start = time.time()
        try:
            result = kaya.execute(cmd, context={'dry_run': True})
            duration_ms = (time.time() - op_start) * 1000
            results.add_operation_time(duration_ms)
        except Exception as e:
            print(f"  Error: {e}")

    results.stop()
    return results


def profile_scribe_agent(tmp_path: Path) -> ProfilerResults:
    """Profile Scribe agent."""
    print("\nProfiling Scribe Agent...")

    results = ProfilerResults("Scribe Agent")
    scribe = ScribeAgent()

    # Test tasks
    tasks = [
        ("user can login", "easy"),
        ("user can complete OAuth flow", "hard"),
        ("user can search products", "easy")
    ]

    results.start()

    for i, (task_desc, complexity) in enumerate(tasks):
        op_start = time.time()
        try:
            result = scribe.execute(
                task_description=task_desc,
                feature_name=f"profile_test_{i}",
                output_path=str(tmp_path / f"profile_{i}.spec.ts"),
                complexity=complexity
            )
            duration_ms = (time.time() - op_start) * 1000
            results.add_operation_time(duration_ms)
        except Exception as e:
            print(f"  Error: {e}")

    results.stop()
    return results


def profile_redis_client() -> ProfilerResults:
    """Profile Redis client operations."""
    print("\nProfiling Redis Client...")

    results = ProfilerResults("Redis Client")
    redis = RedisClient()

    num_operations = 1000

    results.start()

    # Profile SET operations
    for i in range(num_operations):
        op_start = time.time()
        redis.set_session(f"profile_session_{i}", {'user_id': i, 'data': 'x' * 100})
        duration_ms = (time.time() - op_start) * 1000
        results.add_operation_time(duration_ms)

    # Profile GET operations
    for i in range(num_operations):
        op_start = time.time()
        redis.get_session(f"profile_session_{i}")
        duration_ms = (time.time() - op_start) * 1000
        results.add_operation_time(duration_ms)

    # Profile DELETE operations
    for i in range(num_operations):
        op_start = time.time()
        redis.delete_session(f"profile_session_{i}")
        duration_ms = (time.time() - op_start) * 1000
        results.add_operation_time(duration_ms)

    results.stop()

    try:
        redis.close()
    except:
        pass

    return results


def profile_vector_client() -> ProfilerResults:
    """Profile Vector DB client operations."""
    print("\nProfiling Vector DB Client...")

    results = ProfilerResults("Vector DB Client")
    vector = VectorClient()

    num_operations = 100

    results.start()

    # Profile embedding generation and storage
    for i in range(num_operations):
        op_start = time.time()

        test_code = f"""
import {{ test, expect }} from '@playwright/test';

test.describe('Feature {i}', () => {{
  test('should work', async ({{ page }}) => {{
    await page.goto('/feature-{i}');
    await expect(page).toHaveTitle(/Feature {i}/);
  }});
}});
"""
        vector.store_test_pattern(
            f"profile_pattern_{i}",
            test_code,
            {'feature': f'feature_{i}', 'complexity': 'easy'}
        )

        duration_ms = (time.time() - op_start) * 1000
        results.add_operation_time(duration_ms)

    # Profile search operations
    for i in range(num_operations // 10):  # Fewer search operations
        op_start = time.time()

        vector.search_test_patterns(f"Feature {i}", n_results=5)

        duration_ms = (time.time() - op_start) * 1000
        results.add_operation_time(duration_ms)

    results.stop()

    try:
        vector.close()
    except:
        pass

    return results


def profile_router() -> ProfilerResults:
    """Profile Router routing decisions."""
    print("\nProfiling Router...")

    results = ProfilerResults("Router")
    router = Router()

    num_operations = 10000

    tasks = [
        ('write_test', 'Simple login form'),
        ('write_test', 'Complex OAuth with 2FA and token refresh'),
        ('execute_test', 'Run auth tests'),
        ('fix_bug', 'Fix selector timeout'),
        ('pre_validate', 'Check test quality')
    ]

    results.start()

    for i in range(num_operations):
        op_start = time.time()

        task_type, desc = tasks[i % len(tasks)]
        router.route(task_type=task_type, task_description=desc)

        duration_ms = (time.time() - op_start) * 1000
        results.add_operation_time(duration_ms)

    results.stop()
    return results


def main():
    """Main profiling entry point."""
    parser = argparse.ArgumentParser(description='Profile SuperAgent components')
    parser.add_argument(
        '--component',
        choices=['all', 'kaya', 'scribe', 'router', 'redis', 'vector'],
        default='all',
        help='Component to profile'
    )
    parser.add_argument(
        '--bottleneck-threshold',
        type=float,
        default=100.0,
        help='Threshold in ms for identifying bottlenecks (default: 100ms)'
    )

    args = parser.parse_args()

    # Create temporary directory for test outputs
    import tempfile
    tmp_dir = Path(tempfile.mkdtemp(prefix='superagent_profile_'))

    print("="*100)
    print("SUPERAGENT PERFORMANCE PROFILING")
    print("="*100)

    all_results = []
    all_bottlenecks = []

    # Profile selected components
    if args.component in ['all', 'router']:
        results = profile_router()
        results.print_report()
        bottlenecks = results.identify_bottlenecks(args.bottleneck_threshold)
        all_results.append(results)
        all_bottlenecks.extend([(results.component_name, b) for b in bottlenecks])

    if args.component in ['all', 'redis']:
        try:
            results = profile_redis_client()
            results.print_report()
            bottlenecks = results.identify_bottlenecks(args.bottleneck_threshold)
            all_results.append(results)
            all_bottlenecks.extend([(results.component_name, b) for b in bottlenecks])
        except Exception as e:
            print(f"\nSkipping Redis profiling: {e}")

    if args.component in ['all', 'vector']:
        try:
            results = profile_vector_client()
            results.print_report()
            bottlenecks = results.identify_bottlenecks(args.bottleneck_threshold)
            all_results.append(results)
            all_bottlenecks.extend([(results.component_name, b) for b in bottlenecks])
        except Exception as e:
            print(f"\nSkipping Vector DB profiling: {e}")

    if args.component in ['all', 'kaya']:
        try:
            results = profile_kaya_orchestrator(tmp_dir)
            results.print_report()
            bottlenecks = results.identify_bottlenecks(args.bottleneck_threshold)
            all_results.append(results)
            all_bottlenecks.extend([(results.component_name, b) for b in bottlenecks])
        except Exception as e:
            print(f"\nSkipping Kaya profiling: {e}")

    if args.component in ['all', 'scribe']:
        try:
            results = profile_scribe_agent(tmp_dir)
            results.print_report()
            bottlenecks = results.identify_bottlenecks(args.bottleneck_threshold)
            all_results.append(results)
            all_bottlenecks.extend([(results.component_name, b) for b in bottlenecks])
        except Exception as e:
            print(f"\nSkipping Scribe profiling: {e}")

    # Print summary of all bottlenecks
    if all_bottlenecks:
        print("\n" + "="*100)
        print("SUMMARY: IDENTIFIED BOTTLENECKS (>{:.0f}ms)".format(args.bottleneck_threshold))
        print("="*100)

        for component_name, bottleneck in sorted(all_bottlenecks, key=lambda x: x[1]['tottime_ms'], reverse=True)[:20]:
            func = bottleneck['function']
            func_name = f"{func[0]}:{func[1]}:{func[2]}"
            if len(func_name) > 60:
                func_name = "..." + func_name[-57:]

            print(f"{component_name:20s} {func_name:<60s} {bottleneck['tottime_ms']:>10.2f}ms ({bottleneck['calls']:>6} calls)")

        print("="*100 + "\n")

    # Cleanup
    import shutil
    try:
        shutil.rmtree(tmp_dir)
    except:
        pass

    print("\nProfiling complete!")


if __name__ == '__main__':
    main()
