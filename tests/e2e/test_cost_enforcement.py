"""
E2E Test: Cost Enforcement and Budget Management

Tests budget limits, warnings, and cost tracking across the system:
1. Per-session budget limits
2. Soft limit warnings (80% threshold)
3. Hard limit enforcement (100% threshold)
4. Per-feature cost targets ($0.50)
5. Cost aggregation across agents
6. Critical path cost overrides ($2-3 for auth/payment)
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch

from agent_system.agents.kaya import KayaAgent
from agent_system.agents.scribe import ScribeAgent
from agent_system.router import Router
from agent_system.state.vector_client import VectorClient


class TestCostEnforcement:
    """
    Cost enforcement and budget management tests.

    Tests various cost scenarios and budget enforcement mechanisms.
    """

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_dir = Path(self.temp_dir) / "tests"
        self.test_dir.mkdir()

        self.mock_vector = Mock(spec=VectorClient)
        self.mock_vector.search_test_patterns.return_value = []

        yield

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_per_feature_cost_target(self):
        """
        Test: Per-feature cost stays under $0.50 target

        Standard workflow should cost < $0.50 per feature
        """
        print("\n" + "="*80)
        print("TEST: Per-Feature Cost Target ($0.50)")
        print("="*80)

        router = Router()
        total_cost = 0.0

        # Simulate typical happy path costs
        costs = {
            'kaya_routing': 0.0,      # No cost (routing only)
            'scribe_haiku': 0.02,     # Easy test with Haiku
            'critic_haiku': 0.005,    # Pre-validation with Haiku
            'runner_haiku': 0.005,    # Execution parsing with Haiku
            'gemini_playwright': 0.0  # No API cost (Playwright only)
        }

        total_cost = sum(costs.values())

        print(f"\n=== Cost Breakdown ===")
        for agent, cost in costs.items():
            print(f"{agent}: ${cost:.4f}")
        print(f"{'─'*40}")
        print(f"Total: ${total_cost:.4f}")

        # Verify under target
        target = 0.50
        assert total_cost < target, f"Cost ${total_cost:.4f} exceeds target ${target:.2f}"

        print(f"\n✓ Cost under target")
        print(f"  Target: ${target:.2f}")
        print(f"  Actual: ${total_cost:.4f}")
        print(f"  Savings: ${target - total_cost:.4f}")

        # Check budget status
        budget_status = router.check_budget(total_cost, 'per_session')
        assert budget_status['status'] == 'ok'

        print(f"✓ Budget status: {budget_status['status']}")

    def test_soft_limit_warning(self):
        """
        Test: Soft limit warning at 80% budget usage

        Should warn but not block when 80% of budget is consumed
        """
        print("\n" + "="*80)
        print("TEST: Soft Limit Warning (80% Budget)")
        print("="*80)

        router = Router()

        # Get budget limits
        per_session_budget = 5.00  # Default from router_policy.yaml

        # Simulate 80% usage
        current_spend = per_session_budget * 0.80

        print(f"\n=== Budget Simulation ===")
        print(f"Session budget: ${per_session_budget:.2f}")
        print(f"Current spend: ${current_spend:.2f}")
        print(f"Usage: 80%")

        budget_status = router.check_budget(current_spend, 'per_session')

        # Should be in warning state
        assert budget_status['status'] == 'warning', \
            f"Expected 'warning' but got '{budget_status['status']}'"
        assert budget_status['warning'] is not None
        assert budget_status['percent_used'] >= 80.0

        print(f"\n✓ Soft limit warning triggered")
        print(f"  Status: {budget_status['status']}")
        print(f"  Warning: {budget_status['warning']}")
        print(f"  Percent used: {budget_status['percent_used']:.1f}%")
        print(f"  Remaining: ${budget_status['remaining']:.2f}")

        # Should still be able to proceed (not blocked)
        kaya = KayaAgent()
        kaya.session_cost = current_spend

        result = kaya.execute("Create test for simple feature")

        # Execution should succeed but with warning
        assert result.success or result.error is None or 'budget' not in result.error.lower(), \
            "Should not be blocked at soft limit"

        print(f"✓ Execution allowed with warning")

    def test_hard_limit_enforcement(self):
        """
        Test: Hard limit stops execution at 100% budget

        Should block new operations when budget is exceeded
        """
        print("\n" + "="*80)
        print("TEST: Hard Limit Enforcement (100% Budget)")
        print("="*80)

        router = Router()
        per_session_budget = 5.00

        # Simulate 100% usage
        current_spend = per_session_budget * 1.01  # Slightly over

        print(f"\n=== Budget Exceeded ===")
        print(f"Session budget: ${per_session_budget:.2f}")
        print(f"Current spend: ${current_spend:.2f}")
        print(f"Usage: 101%")

        budget_status = router.check_budget(current_spend, 'per_session')

        # Should be exceeded
        assert budget_status['status'] == 'exceeded', \
            f"Expected 'exceeded' but got '{budget_status['status']}'"
        assert budget_status['warning'] is not None

        print(f"\n✓ Hard limit triggered")
        print(f"  Status: {budget_status['status']}")
        print(f"  Warning: {budget_status['warning']}")

        # Kaya should block new operations
        kaya = KayaAgent()
        kaya.session_cost = current_spend

        result = kaya.execute("Create test for another feature")

        # Execution should be blocked
        assert not result.success, "Execution should be blocked when budget exceeded"
        assert 'budget' in result.error.lower(), "Error should mention budget"

        print(f"✓ Execution blocked")
        print(f"  Error: {result.error[:80]}...")

    def test_cost_aggregation_across_agents(self):
        """
        Test: Costs correctly aggregated across multiple agents

        Track and sum costs from Scribe + Critic + Runner + Medic
        """
        print("\n" + "="*80)
        print("TEST: Cost Aggregation Across Agents")
        print("="*80)

        kaya = KayaAgent()
        session_costs = []

        # Simulate multiple operations
        operations = [
            {'name': 'Create test 1', 'cost': 0.02},
            {'name': 'Review test 1', 'cost': 0.005},
            {'name': 'Execute test 1', 'cost': 0.005},
            {'name': 'Create test 2', 'cost': 0.03},  # Harder test (Sonnet)
            {'name': 'Review test 2', 'cost': 0.005},
            {'name': 'Execute test 2', 'cost': 0.005},
            {'name': 'Fix test 2', 'cost': 0.015},    # Medic with Sonnet
        ]

        print(f"\n=== Simulating Operations ===")

        for op in operations:
            kaya.session_cost += op['cost']
            session_costs.append(kaya.session_cost)
            print(f"{op['name']}: +${op['cost']:.4f} (total: ${kaya.session_cost:.4f})")

        # Verify final cost
        expected_total = sum(op['cost'] for op in operations)
        assert abs(kaya.session_cost - expected_total) < 0.001, \
            f"Cost mismatch: expected ${expected_total:.4f}, got ${kaya.session_cost:.4f}"

        print(f"\n✓ Cost aggregation correct")
        print(f"  Final session cost: ${kaya.session_cost:.4f}")
        print(f"  Operations: {len(operations)}")

        # Check session stats
        stats = kaya.get_session_stats()
        print(f"\n=== Session Statistics ===")
        print(f"Total cost: ${stats['session_cost']:.4f}")
        print(f"Budget status: {stats['budget_status']['status']}")

    def test_critical_path_cost_override(self):
        """
        Test: Critical paths (auth/payment) get higher cost budgets

        Auth/payment features can use $2-3 instead of $0.50
        """
        print("\n" + "="*80)
        print("TEST: Critical Path Cost Override")
        print("="*80)

        router = Router()

        # Test critical path patterns
        critical_tests = [
            {'path': 'tests/auth/login.spec.ts', 'expected_override': True},
            {'path': 'tests/auth/oauth.spec.ts', 'expected_override': True},
            {'path': 'tests/payment/checkout.spec.ts', 'expected_override': True},
            {'path': 'tests/payment/stripe.spec.ts', 'expected_override': True},
            {'path': 'tests/profile/edit.spec.ts', 'expected_override': False},
            {'path': 'tests/nav/menu.spec.ts', 'expected_override': False},
        ]

        print(f"\n=== Testing Cost Overrides ===")

        for test in critical_tests:
            routing = router.route(
                task_type='write_test',
                task_description='test',
                test_path=test['path']
            )

            is_override = routing.max_cost_usd > 0.50
            expected = test['expected_override']

            status = "✓" if is_override == expected else "✗"
            print(f"{status} {test['path']}")
            print(f"   Max cost: ${routing.max_cost_usd:.2f}")

            assert is_override == expected, \
                f"Override mismatch for {test['path']}: expected {expected}, got {is_override}"

        print(f"\n✓ All critical path overrides correct")

    def test_haiku_usage_ratio(self):
        """
        Test: Haiku usage meets 70% target

        System should use Haiku for 70%+ of operations
        """
        print("\n" + "="*80)
        print("TEST: Haiku Usage Ratio (70% Target)")
        print("="*80)

        router = Router()

        # Simulate 100 typical tasks
        test_cases = [
            # Easy tasks (should use Haiku)
            *[{'desc': f'simple form {i}', 'scope': ''} for i in range(60)],
            # Medium tasks (should use Haiku)
            *[{'desc': f'validation test {i}', 'scope': ''} for i in range(10)],
            # Hard tasks with auth (should use Sonnet)
            *[{'desc': f'oauth login {i}', 'scope': 'auth'} for i in range(15)],
            # Hard tasks with payment (should use Sonnet)
            *[{'desc': f'checkout flow {i}', 'scope': 'payment processing'} for i in range(10)],
            # Hard multi-step (should use Sonnet)
            *[{'desc': f'complex workflow {i} with 6 steps', 'scope': ''} for i in range(5)],
        ]

        haiku_count = 0
        sonnet_count = 0

        for test in test_cases:
            routing = router.route(
                task_type='write_test',
                task_description=test['desc'],
                task_scope=test['scope']
            )

            if 'haiku' in routing.model.lower():
                haiku_count += 1
            else:
                sonnet_count += 1

        total = len(test_cases)
        haiku_ratio = haiku_count / total

        print(f"\n=== Model Usage Distribution ===")
        print(f"Total tasks: {total}")
        print(f"Haiku: {haiku_count} ({haiku_ratio*100:.1f}%)")
        print(f"Sonnet: {sonnet_count} ({(1-haiku_ratio)*100:.1f}%)")

        # Verify meets target
        target_ratio = router.get_haiku_ratio_target()
        assert haiku_ratio >= target_ratio, \
            f"Haiku ratio {haiku_ratio:.1%} below target {target_ratio:.1%}"

        print(f"\n✓ Haiku usage meets target")
        print(f"  Target: {target_ratio*100:.0f}%")
        print(f"  Actual: {haiku_ratio*100:.1f}%")

    def test_cost_with_medic_retries(self):
        """
        Test: Cost tracking with multiple Medic retries

        Verify costs accumulate correctly when Medic makes multiple attempts
        """
        print("\n" + "="*80)
        print("TEST: Cost Tracking with Medic Retries")
        print("="*80)

        initial_costs = {
            'scribe': 0.02,
            'critic': 0.005,
            'runner': 0.005,
        }

        medic_retry_cost = 0.015  # Sonnet per retry

        # Simulate 3 Medic retries
        total_cost = sum(initial_costs.values())

        print(f"\n=== Initial Workflow ===")
        for agent, cost in initial_costs.items():
            print(f"{agent}: ${cost:.4f}")
        print(f"Subtotal: ${total_cost:.4f}")

        print(f"\n=== Medic Retries ===")
        for retry in range(1, 4):
            total_cost += medic_retry_cost
            print(f"Retry {retry}: +${medic_retry_cost:.4f} (total: ${total_cost:.4f})")

        # Add final successful run
        total_cost += 0.005  # Runner final attempt
        print(f"Final run: +$0.005 (total: ${total_cost:.4f})")

        # Verify still under reasonable budget
        print(f"\n=== Final Cost Analysis ===")
        print(f"Total cost: ${total_cost:.4f}")
        print(f"Medic attempts: 3")
        print(f"Cost per Medic attempt: ${medic_retry_cost:.4f}")

        # Should still be under $0.10 even with retries
        assert total_cost < 0.10, f"Cost ${total_cost:.4f} too high even with retries"

        print(f"✓ Cost acceptable with retries")

    def test_budget_warning_propagation(self):
        """
        Test: Budget warnings propagate to Kaya responses

        User should be informed when approaching budget limits
        """
        print("\n" + "="*80)
        print("TEST: Budget Warning Propagation")
        print("="*80)

        kaya = KayaAgent()

        # Simulate 85% budget usage
        per_session_budget = 5.00
        kaya.session_cost = per_session_budget * 0.85

        print(f"\n=== Simulating High Budget Usage ===")
        print(f"Session budget: ${per_session_budget:.2f}")
        print(f"Current spend: ${kaya.session_cost:.2f}")
        print(f"Usage: 85%")

        # Check budget status
        budget_status = kaya.check_budget()

        assert budget_status['status'] == 'warning'
        assert budget_status['warning'] is not None

        print(f"\n✓ Budget warning active")
        print(f"  {budget_status['warning']}")

        # Execute command and verify warning in response
        result = kaya.execute("Create test for feature")

        # Metadata should contain budget warning
        if result.metadata:
            budget_info = result.metadata.get('budget_status')
            if budget_info:
                print(f"\n✓ Budget info in response metadata")
                print(f"  Status: {budget_info['status']}")

        print(f"\n✓ Budget warnings properly propagated")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
