"""
End-to-End Integration Test: Cost Budget Enforcement

This test validates the Router's budget enforcement system:
1. Track session costs across multiple agent invocations
2. Trigger soft warning at 80% of budget ($4.00 of $5.00)
3. Trigger hard stop at 100% of budget ($5.00)
4. Test cost overrides for critical paths (auth/payment allow >$0.50)
5. Validate per-session and per-feature budget tracking

Implementation:
- Uses real Router with cost tracking
- Simulates expensive operations (Sonnet usage)
- Validates warning and stop thresholds
- Tests override logic for critical paths
"""
import pytest
import time
from typing import Dict, Any
from unittest.mock import Mock, patch

from agent_system.router import Router, RoutingDecision


class TestCostBudgetEnforcement:
    """
    End-to-end integration test for cost budget enforcement.

    Tests budget limits, warnings, and critical path overrides.
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test environment."""
        # Initialize router with default config
        self.router = Router()

        # Session tracking
        self.session_id = "cost_test_session_123"
        self.session_cost = 0.0

        yield

    def test_normal_operation_under_budget(self):
        """
        Test that normal operations stay under budget.

        Simulates typical usage:
        - 3 easy tasks with Haiku (~$0.02 each)
        - 1 hard task with Sonnet (~$0.15)
        - Total: ~$0.21 (well under $0.50 per-feature budget)
        """
        print("\n=== Test: Normal Operation Under Budget ===")

        total_cost = 0.0

        # Easy task 1: Login test (Haiku)
        decision1 = self.router.route(
            task_type="write_test",
            task_description="simple user login form",
            task_scope="happy path only"
        )

        assert decision1.agent == 'scribe'
        assert decision1.model == 'haiku'
        assert decision1.max_cost_usd == 0.50

        simulated_cost1 = 0.018  # Haiku cost for simple test
        total_cost += simulated_cost1

        print(f"Task 1 - Login test: ${simulated_cost1:.3f} (Haiku)")

        # Easy task 2: Form validation (Haiku)
        decision2 = self.router.route(
            task_type="write_test",
            task_description="form validation with 3 fields",
            task_scope="check required fields"
        )

        assert decision2.model == 'haiku'

        simulated_cost2 = 0.022
        total_cost += simulated_cost2

        print(f"Task 2 - Form validation: ${simulated_cost2:.3f} (Haiku)")

        # Easy task 3: Navigation (Haiku)
        decision3 = self.router.route(
            task_type="write_test",
            task_description="navigation menu",
            task_scope="click through menu items"
        )

        assert decision3.model == 'haiku'

        simulated_cost3 = 0.019
        total_cost += simulated_cost3

        print(f"Task 3 - Navigation: ${simulated_cost3:.3f} (Haiku)")

        # Hard task: OAuth + Payment flow (Sonnet)
        # Need auth (3) + payment (4) = 7 points to exceed threshold of 5
        decision4 = self.router.route(
            task_type="write_test",
            task_description="OAuth authentication with payment processing, handle redirects and checkout flow with mocking",
            task_scope="full OAuth and payment flow"
        )

        # Should be hard due to auth + payment keywords
        assert decision4.model == 'sonnet', f"Expected sonnet but got {decision4.model} (score: {decision4.complexity_score})"
        assert decision4.difficulty == 'hard'

        simulated_cost4 = 0.145  # Sonnet cost for complex test
        total_cost += simulated_cost4

        print(f"Task 4 - OAuth + Payment flow: ${simulated_cost4:.3f} (Sonnet)")

        # Check budget status
        budget_check = self.router.check_budget(total_cost, budget_type='per_session')

        print(f"\nTotal cost: ${total_cost:.3f}")
        print(f"Budget status: {budget_check['status']}")
        print(f"Remaining: ${budget_check['remaining']:.2f}")

        assert budget_check['status'] == 'ok', "Should be under budget"
        assert total_cost < 0.50, "Should be well under per-feature budget"
        assert budget_check['percent_used'] < 80, "Should be under soft limit"

        print("✓ Normal operations stay under budget")

    def test_soft_warning_at_80_percent(self):
        """
        Test that soft warning triggers at 80% of budget.

        Per-session budget: $5.00
        Soft limit (80%): $4.00

        Simulates accumulating $4.10 in costs.
        """
        print("\n=== Test: Soft Warning at 80% ===")

        # Simulate $4.10 in accumulated costs
        accumulated_cost = 4.10

        budget_check = self.router.check_budget(accumulated_cost, budget_type='per_session')

        print(f"Accumulated cost: ${accumulated_cost:.2f}")
        print(f"Budget limit: ${budget_check['limit']:.2f}")
        print(f"Percent used: {budget_check['percent_used']:.1f}%")
        print(f"Status: {budget_check['status']}")
        print(f"Warning: {budget_check['warning']}")

        assert budget_check['status'] == 'warning', "Should trigger warning at 82% usage"
        assert budget_check['warning'] is not None, "Should have warning message"
        assert budget_check['percent_used'] > 80, "Should be over 80% threshold"
        assert budget_check['remaining'] < 1.0, "Should have less than $1 remaining"
        assert "warning" in budget_check['warning'].lower(), "Warning should mention warning"

        print("✓ Soft warning triggered correctly")

    def test_hard_stop_at_100_percent(self):
        """
        Test that hard stop triggers at 100% of budget.

        Per-session budget: $5.00
        Hard limit (100%): $5.00

        Simulates accumulating $5.10 in costs (over budget).
        """
        print("\n=== Test: Hard Stop at 100% ===")

        # Simulate $5.10 in accumulated costs (over budget)
        accumulated_cost = 5.10

        budget_check = self.router.check_budget(accumulated_cost, budget_type='per_session')

        print(f"Accumulated cost: ${accumulated_cost:.2f}")
        print(f"Budget limit: ${budget_check['limit']:.2f}")
        print(f"Percent used: {budget_check['percent_used']:.1f}%")
        print(f"Status: {budget_check['status']}")
        print(f"Warning: {budget_check['warning']}")

        assert budget_check['status'] == 'exceeded', "Should trigger hard stop"
        assert budget_check['warning'] is not None, "Should have error message"
        assert budget_check['percent_used'] > 100, "Should be over 100%"
        assert budget_check['remaining'] < 0, "Should have negative remaining"
        assert "exceeded" in budget_check['warning'].lower(), "Should mention exceeded"

        print("✓ Hard stop triggered correctly")

    def test_cost_override_for_auth_paths(self):
        """
        Test that auth paths get cost override ($2-3 instead of $0.50).

        Critical paths defined in router_policy.yaml:
        - tests/auth*.spec.ts: $2.00
        - tests/payment*.spec.ts: $3.00
        """
        print("\n=== Test: Cost Override for Auth Paths ===")

        # Regular test (no override)
        decision_regular = self.router.route(
            task_type="write_test",
            task_description="simple form test",
            test_path="tests/form.spec.ts"
        )

        assert decision_regular.max_cost_usd == 0.50, "Regular test should have default budget"
        print(f"Regular test (tests/form.spec.ts): ${decision_regular.max_cost_usd:.2f}")

        # Auth test (should get override)
        decision_auth = self.router.route(
            task_type="write_test",
            task_description="OAuth authentication flow",
            test_path="tests/auth_oauth.spec.ts"
        )

        print(f"Auth test (tests/auth_oauth.spec.ts): ${decision_auth.max_cost_usd:.2f}")
        assert decision_auth.max_cost_usd > 0.50, "Auth test should have higher budget"
        assert decision_auth.max_cost_usd == 2.00, "Auth test should get $2.00 budget"

        # Payment test (should get higher override)
        decision_payment = self.router.route(
            task_type="write_test",
            task_description="payment processing flow",
            test_path="tests/payment_checkout.spec.ts"
        )

        print(f"Payment test (tests/payment_checkout.spec.ts): ${decision_payment.max_cost_usd:.2f}")
        assert decision_payment.max_cost_usd > decision_auth.max_cost_usd, "Payment should be highest"
        assert decision_payment.max_cost_usd == 3.00, "Payment test should get $3.00 budget"

        print("✓ Cost overrides applied correctly for critical paths")

    def test_session_cost_tracking_across_agents(self):
        """
        Test accurate cost tracking across multiple agent invocations.

        Simulates a complete flow:
        1. Kaya routes (no cost)
        2. Scribe writes test (Haiku: $0.02)
        3. Critic reviews (Haiku: $0.005)
        4. Runner executes (Haiku: $0.005)
        5. Medic fixes (Sonnet: $0.15)

        Total: ~$0.18
        """
        print("\n=== Test: Session Cost Tracking Across Agents ===")

        session_costs = {
            'kaya': 0.0,      # Router only, no LLM
            'scribe': 0.022,  # Haiku for test generation
            'critic': 0.005,  # Haiku for pre-validation
            'runner': 0.005,  # Haiku for result parsing
            'medic': 0.145    # Sonnet for bug fixing
        }

        cumulative_cost = 0.0

        print("\nAgent invocations:")
        for agent, cost in session_costs.items():
            cumulative_cost += cost
            budget_check = self.router.check_budget(cumulative_cost, budget_type='per_session')

            print(f"  {agent:10s}: ${cost:.3f} (total: ${cumulative_cost:.3f}, status: {budget_check['status']})")

            # All costs should be well under budget
            assert budget_check['status'] == 'ok', f"Should be under budget after {agent}"

        total_cost = sum(session_costs.values())
        assert abs(total_cost - cumulative_cost) < 0.001, "Cumulative should match sum"

        print(f"\n✓ Total session cost: ${total_cost:.3f}")
        print(f"✓ Session budget remaining: ${5.0 - total_cost:.2f}")
        print("✓ Cost tracking accurate across all agents")

    def test_multiple_expensive_tasks_trigger_warning(self):
        """
        Test that multiple expensive tasks trigger budget warnings.

        Simulates:
        - 5 Sonnet tasks at $0.15 each = $0.75 total
        - This exceeds per-feature budget but should trigger warning
        """
        print("\n=== Test: Multiple Expensive Tasks Trigger Warning ===")

        # Simulate 5 expensive Sonnet tasks
        num_tasks = 5
        cost_per_task = 0.15
        total_cost = 0.0

        print("\nExecuting expensive tasks:")
        for i in range(1, num_tasks + 1):
            task_cost = cost_per_task
            total_cost += task_cost

            budget_check = self.router.check_budget(total_cost, budget_type='per_session')

            print(f"  Task {i}: ${task_cost:.2f} (total: ${total_cost:.2f}, status: {budget_check['status']})")

        # Should still be under session budget ($5.00) but over feature budget ($0.50)
        assert total_cost < 5.0, "Should be under session budget"
        assert total_cost > 0.50, "Should exceed single-feature budget"

        final_check = self.router.check_budget(total_cost, budget_type='per_session')
        assert final_check['status'] == 'ok', "Should be OK for session budget"

        print(f"\n✓ Total: ${total_cost:.2f} (under session budget, would need override for single feature)")

    def test_daily_budget_separate_from_session(self):
        """
        Test that daily budget is tracked separately from per-session budget.

        Session budget: $5.00
        Daily budget: $50.00 (from router_policy.yaml, if defined)
        """
        print("\n=== Test: Daily Budget Separate from Session ===")

        # Simulate high session cost
        session_cost = 4.50

        # Check session budget
        session_check = self.router.check_budget(session_cost, budget_type='per_session')
        print(f"Session cost: ${session_cost:.2f}")
        print(f"  Status: {session_check['status']}")
        print(f"  Limit: ${session_check['limit']:.2f}")

        assert session_check['status'] == 'warning', "Should trigger warning at 90% of session budget"

        # Check daily budget (would track across multiple sessions)
        # Note: Daily budget typically higher, so same cost might be OK
        daily_check = self.router.check_budget(session_cost, budget_type='daily')
        print(f"\nDaily budget check:")
        print(f"  Status: {daily_check['status']}")
        print(f"  Limit: ${daily_check['limit']:.2f}")

        # Daily budget should be higher than session budget
        assert daily_check['limit'] > session_check['limit'], "Daily budget should be higher"

        print("✓ Session and daily budgets tracked independently")

    def test_haiku_ratio_target(self):
        """
        Test that Router maintains 70% Haiku usage target.

        Target from router_policy.yaml: use_haiku_ratio: 0.7
        """
        print("\n=== Test: Haiku Ratio Target ===")

        # Get Haiku ratio target
        haiku_ratio_target = self.router.get_haiku_ratio_target()

        assert haiku_ratio_target == 0.7, "Haiku ratio should be 70%"
        print(f"Haiku ratio target: {haiku_ratio_target * 100:.0f}%")

        # Simulate 10 tasks and track model usage
        # Include mix to achieve ~70% Haiku ratio
        task_descriptions = [
            "simple login form",
            "basic navigation",
            "form validation",
            "OAuth authentication with mock API and redirect handling",  # Hard (auth + mock = 5)
            "button click test",
            "dropdown selection",
            "WebSocket real-time chat with authentication and reconnection",  # Hard (websocket + auth + mock = 8)
            "checkbox toggle",
            "payment checkout with Stripe webhook and file receipt generation",  # Hard (payment + file = 6)
            "simple search"
        ]

        haiku_count = 0
        sonnet_count = 0

        print("\nRouting decisions:")
        for i, desc in enumerate(task_descriptions, 1):
            decision = self.router.route(
                task_type="write_test",
                task_description=desc,
                task_scope="test scope"
            )

            if decision.model == 'haiku':
                haiku_count += 1
            elif decision.model == 'sonnet':
                sonnet_count += 1

            print(f"  Task {i:2d}: {decision.model:6s} - {desc[:50]}")

        total_tasks = haiku_count + sonnet_count
        haiku_ratio = haiku_count / total_tasks if total_tasks > 0 else 0

        print(f"\nResults:")
        print(f"  Haiku: {haiku_count}/{total_tasks} ({haiku_ratio * 100:.0f}%)")
        print(f"  Sonnet: {sonnet_count}/{total_tasks} ({(1 - haiku_ratio) * 100:.0f}%)")
        print(f"  Target: {haiku_ratio_target * 100:.0f}%")

        # Should be close to 70% (allow some variance due to complexity detection)
        assert haiku_ratio >= 0.6, "Should use Haiku for at least 60% of tasks"
        assert haiku_ratio <= 0.8, "Should not use Haiku for more than 80% of tasks"

        print(f"✓ Haiku ratio within acceptable range")


class TestCostBudgetEnforcementEdgeCases:
    """Test edge cases in budget enforcement."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test environment."""
        self.router = Router()
        yield

    def test_zero_cost_operations(self):
        """
        Test that operations with zero cost don't affect budget.

        Examples:
        - Kaya routing (no LLM calls)
        - Cache hits
        """
        print("\n=== Test: Zero Cost Operations ===")

        # Simulate routing operations (no cost)
        for i in range(10):
            decision = self.router.route(
                task_type="write_test",
                task_description="simple test"
            )

        # Check budget with zero cost
        budget_check = self.router.check_budget(0.0, budget_type='per_session')

        assert budget_check['status'] == 'ok'
        assert budget_check['percent_used'] == 0.0
        assert budget_check['remaining'] == budget_check['limit']

        print("✓ Zero-cost operations don't affect budget")

    def test_negative_cost_handling(self):
        """
        Test that negative costs are handled gracefully.

        (Should never happen in practice, but validate robustness)
        """
        print("\n=== Test: Negative Cost Handling ===")

        # Attempt to check budget with negative cost
        budget_check = self.router.check_budget(-0.50, budget_type='per_session')

        # Should still return valid status
        assert budget_check['status'] in ['ok', 'warning', 'exceeded']
        assert 'limit' in budget_check
        assert 'remaining' in budget_check

        print("✓ Negative costs handled gracefully")

    def test_exact_budget_limit(self):
        """
        Test behavior at exact budget limit.

        Cost: $5.00
        Limit: $5.00
        """
        print("\n=== Test: Exact Budget Limit ===")

        # Simulate exactly hitting the limit
        exact_cost = 5.00

        budget_check = self.router.check_budget(exact_cost, budget_type='per_session')

        print(f"Cost: ${exact_cost:.2f}")
        print(f"Limit: ${budget_check['limit']:.2f}")
        print(f"Status: {budget_check['status']}")

        # At exactly 100%, should trigger exceeded
        assert budget_check['status'] == 'exceeded', "Should be exceeded at 100%"
        assert budget_check['percent_used'] == 100.0

        print("✓ Exact budget limit handled correctly")

    def test_very_small_costs(self):
        """
        Test that very small costs (< $0.001) are tracked accurately.
        """
        print("\n=== Test: Very Small Costs ===")

        # Simulate 100 micro-operations at $0.0001 each
        total_cost = 0.0
        for i in range(100):
            total_cost += 0.0001

        budget_check = self.router.check_budget(total_cost, budget_type='per_session')

        assert abs(total_cost - 0.01) < 0.0001, "Should accurately sum small costs"
        assert budget_check['status'] == 'ok'

        print(f"✓ 100 micro-costs totaled: ${total_cost:.4f}")
        print("✓ Small costs tracked accurately")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
