"""
Integration tests for Router.

Tests end-to-end routing with realistic sample tasks, validating:
- Complexity estimation integration
- Agent/model selection based on task type and complexity
- Cost override application for critical paths
- Fallback and budget enforcement logic

Uses real router_policy.yaml (not mocked) to validate actual routing decisions.
"""
import pytest
from pathlib import Path

from agent_system.router import Router, RoutingDecision
from agent_system.complexity_estimator import ComplexityEstimator


class TestRouterIntegration:
    """Integration tests for Router with realistic sample tasks."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up router for each test."""
        self.router = Router()
        self.estimator = ComplexityEstimator()

    def test_easy_crud_task(self):
        """
        Test routing for easy CRUD task.

        Expected: agent=scribe, model=haiku, complexity=easy
        """
        task_description = "Create a simple user profile form test"
        task_scope = "basic form with name, email, bio fields"

        decision = self.router.route(
            task_type="write_test",
            task_description=task_description,
            task_scope=task_scope
        )

        # Validate routing decision
        assert decision.agent == "scribe", "CRUD tasks should route to scribe"
        assert decision.model == "haiku", "Easy tasks should use haiku model"
        assert decision.difficulty == "easy", "CRUD tasks should be marked easy"
        assert decision.complexity_score < 5, "Easy tasks should have complexity score < 5"
        assert decision.max_cost_usd == 0.50, "Default cost limit should be $0.50"
        assert "Simple CRUD" in decision.reason or "visible UI path" in decision.reason

        # Verify complexity estimation
        complexity = self.estimator.estimate(task_description, task_scope)
        assert complexity.difficulty == "easy"
        assert complexity.score < 5

    def test_hard_auth_flow(self):
        """
        Test routing for complex authentication flow.

        Expected: agent=scribe, model=sonnet, complexity=hard
        """
        task_description = "Test OAuth login with 2FA and session management requiring 6 step flow"
        task_scope = "Google OAuth provider, SMS verification, JWT tokens, mock API responses"

        decision = self.router.route(
            task_type="write_test",
            task_description=task_description,
            task_scope=task_scope
        )

        # Validate routing decision
        assert decision.agent == "scribe", "Test writing should route to scribe"
        assert decision.model == "sonnet", "Hard tasks should use sonnet model"
        assert decision.difficulty == "hard", "Auth with OAuth, 2FA, mocking should be hard"
        assert decision.complexity_score >= 5, "Hard tasks should have complexity score >= 5"
        assert decision.max_cost_usd == 0.50, "Default cost without path override"
        assert "Multi-step" in decision.reason or "auth" in decision.reason.lower()

        # Verify complexity estimation breakdown
        complexity = self.estimator.estimate(task_description, task_scope)
        assert complexity.difficulty == "hard"
        assert complexity.score >= 5
        assert "auth" in complexity.breakdown, "Should detect auth pattern"
        assert "mocking" in complexity.breakdown, "Should detect mocking pattern"

    def test_payment_with_cost_override(self):
        """
        Test routing for payment flow with cost override.

        Expected: agent=scribe, model=sonnet, max_cost_usd=3.00
        """
        task_description = "Test Stripe checkout flow with 5 step purchase"
        task_scope = "Add items to cart, apply coupon, proceed to checkout, complete payment, mock Stripe API"
        test_path = "payment/checkout.spec.ts"

        decision = self.router.route(
            task_type="write_test",
            task_description=task_description,
            task_scope=task_scope,
            test_path=test_path
        )

        # Validate routing decision
        assert decision.agent == "scribe", "Test writing should route to scribe"
        assert decision.model == "sonnet", "Payment flows should use sonnet"
        assert decision.difficulty == "hard", "Payment should be marked hard"
        assert decision.complexity_score >= 5, "Payment should have high complexity"
        assert decision.max_cost_usd == 3.00, "Payment path should have $3.00 cost override"

        # Verify complexity estimation detects payment
        complexity = self.estimator.estimate(task_description, task_scope)
        assert complexity.difficulty == "hard"
        assert "payment" in complexity.breakdown, "Should detect payment pattern"
        assert complexity.breakdown["payment"] == 4, "Payment should add +4 to score"
        assert "mocking" in complexity.breakdown, "Should detect mocking pattern"

    def test_websocket_hard_complexity(self):
        """
        Test routing for WebSocket task.

        Expected: complexity=hard (score >=5)
        """
        task_description = "Test realtime WebSocket notifications with auth and 5 step flow"
        task_scope = "Connect to WebSocket, authenticate, send message, receive notification, verify update, mock responses"

        decision = self.router.route(
            task_type="write_test",
            task_description=task_description,
            task_scope=task_scope
        )

        # Validate routing decision
        assert decision.agent == "scribe"
        assert decision.model == "sonnet", "WebSocket with auth and mocking should trigger sonnet model"
        assert decision.difficulty == "hard", "WebSocket with auth and mocking should be marked hard"
        assert decision.complexity_score >= 5, "WebSocket (3) + auth (3) + mocking (2) should exceed threshold"

        # Verify complexity estimation detects websocket
        complexity = self.estimator.estimate(task_description, task_scope)
        assert complexity.difficulty == "hard"
        assert "websocket" in complexity.breakdown, "Should detect websocket pattern"
        assert complexity.breakdown["websocket"] == 3, "WebSocket should add +3 to score"
        assert "auth" in complexity.breakdown, "Should detect auth pattern"
        assert "mocking" in complexity.breakdown, "Should detect mocking pattern"

    def test_execute_test_routing(self):
        """
        Test routing for test execution.

        Expected: agent=runner, model=haiku
        """
        task_description = "Run authentication tests"
        test_path = "tests/auth/login.spec.ts"

        decision = self.router.route(
            task_type="execute_test",
            task_description=task_description,
            test_path=test_path
        )

        # Validate routing decision
        assert decision.agent == "runner", "Test execution should route to runner"
        assert decision.model == "haiku", "Test execution should use haiku"
        assert "execution is straightforward" in decision.reason.lower()

    def test_pre_validate_routing(self):
        """
        Test routing for pre-validation (critic).

        Expected: agent=critic, model=haiku
        """
        task_description = "Pre-validate test quality before Gemini validation"
        test_path = "tests/checkout.spec.ts"

        decision = self.router.route(
            task_type="pre_validate",
            task_description=task_description,
            test_path=test_path
        )

        # Validate routing decision
        assert decision.agent == "critic", "Pre-validation should route to critic"
        assert decision.model == "haiku", "Pre-validation should use haiku"
        assert "quality checks" in decision.reason.lower()

    def test_validate_routing(self):
        """
        Test routing for final validation.

        Expected: agent=gemini, model=2.5_pro
        """
        task_description = "Validate test in real browser with screenshots"
        test_path = "tests/payment/checkout.spec.ts"

        decision = self.router.route(
            task_type="validate",
            task_description=task_description,
            test_path=test_path
        )

        # Validate routing decision
        assert decision.agent == "gemini", "Validation should route to gemini"
        assert decision.model == "2.5_pro", "Validation should use Gemini 2.5 Pro"
        assert "browser validation" in decision.reason.lower() or "visual evidence" in decision.reason.lower()

    def test_fix_bug_routing(self):
        """
        Test routing for bug fixing.

        Expected: agent=medic, model=sonnet
        """
        task_description = "Fix selector issue in login test"
        test_path = "tests/auth/login.spec.ts"

        decision = self.router.route(
            task_type="fix_bug",
            task_description=task_description,
            test_path=test_path
        )

        # Validate routing decision
        assert decision.agent == "medic", "Bug fixing should route to medic"
        assert decision.model == "sonnet", "Bug fixing should use sonnet"
        assert "deep reasoning" in decision.reason.lower() or "bug fixing" in decision.reason.lower()

    def test_auth_path_cost_override(self):
        """Test cost override for auth critical path."""
        task_description = "Test authentication flow"
        test_path = "auth/oauth.spec.ts"

        decision = self.router.route(
            task_type="write_test",
            task_description=task_description,
            test_path=test_path
        )

        # Auth paths should have $2.00 override
        assert decision.max_cost_usd == 2.00, "Auth paths should have $2.00 cost override"

    def test_admin_path_cost_override(self):
        """Test cost override for admin critical path."""
        task_description = "Test admin user management"
        test_path = "admin/users.spec.ts"

        decision = self.router.route(
            task_type="write_test",
            task_description=task_description,
            test_path=test_path
        )

        # Admin paths should have $1.50 override
        assert decision.max_cost_usd == 1.50, "Admin paths should have $1.50 cost override"

    def test_no_cost_override_for_regular_path(self):
        """Test that regular paths use default cost limit."""
        task_description = "Test user profile editing"
        test_path = "tests/profile/edit.spec.ts"

        decision = self.router.route(
            task_type="write_test",
            task_description=task_description,
            test_path=test_path
        )

        # Regular paths should use default $0.50
        assert decision.max_cost_usd == 0.50, "Regular paths should use default cost"

    def test_fallback_actions(self):
        """Test fallback action retrieval."""
        # Test all fallback types
        assert self.router.get_fallback("critic_fail") == "return_to_scribe"
        assert self.router.get_fallback("validation_timeout") == "retry_runner_then_medic"
        assert self.router.get_fallback("medic_escalation") == "queue_for_hitl"

        # Test unknown fallback type
        assert self.router.get_fallback("unknown_failure") == "queue_for_hitl"

    def test_max_retries(self):
        """Test max retries retrieval."""
        max_retries = self.router.get_max_retries()
        assert max_retries == 3, "Max retries should be 3"

    def test_budget_check_ok(self):
        """Test budget check with safe spending."""
        result = self.router.check_budget(current_spend=2.00, budget_type="per_session")

        assert result["status"] == "ok"
        assert result["limit"] == 5.00
        assert result["remaining"] == 3.00
        assert result["percent_used"] == 40.0
        assert result["warning"] is None

    def test_budget_check_warning(self):
        """Test budget check with warning threshold."""
        result = self.router.check_budget(current_spend=4.50, budget_type="per_session")

        assert result["status"] == "warning"
        assert result["limit"] == 5.00
        assert result["remaining"] == 0.50
        assert result["percent_used"] == 90.0
        assert result["warning"] is not None
        assert "Budget warning" in result["warning"]

    def test_budget_check_exceeded(self):
        """Test budget check with exceeded threshold."""
        result = self.router.check_budget(current_spend=5.50, budget_type="per_session")

        assert result["status"] == "exceeded"
        assert result["limit"] == 5.00
        assert result["remaining"] == -0.50
        assert abs(result["percent_used"] - 110.0) < 0.01, "Allow for floating point precision"
        assert result["warning"] is not None
        assert "Budget exceeded" in result["warning"]

    def test_daily_budget_check(self):
        """Test daily budget enforcement."""
        result = self.router.check_budget(current_spend=30.00, budget_type="daily")

        assert result["status"] == "ok"
        assert result["limit"] == 50.00
        assert result["remaining"] == 20.00
        assert result["percent_used"] == 60.0

    def test_haiku_ratio_target(self):
        """Test Haiku usage ratio target."""
        ratio = self.router.get_haiku_ratio_target()
        assert ratio == 0.7, "Haiku ratio target should be 70%"

    def test_complex_multi_step_auth_payment_flow(self):
        """
        Test complex scenario combining multiple complexity factors.

        Expected: Very high complexity score, sonnet model, cost override if payment path
        """
        task_description = "Test complete checkout with OAuth login, Stripe payment, and WebSocket order confirmation"
        task_scope = "Login with Google OAuth, add 3 items to cart, apply coupon, complete payment with Stripe, verify WebSocket notification"
        test_path = "payment/full_checkout.spec.ts"

        decision = self.router.route(
            task_type="write_test",
            task_description=task_description,
            task_scope=task_scope,
            test_path=test_path
        )

        # Should be very complex
        assert decision.difficulty == "hard"
        assert decision.model == "sonnet"
        assert decision.complexity_score >= 10, "Should accumulate high complexity score"
        assert decision.max_cost_usd == 3.00, "Payment path should have cost override"

        # Verify multiple complexity factors detected
        complexity = self.estimator.estimate(task_description, task_scope)
        breakdown = complexity.breakdown
        assert "auth" in breakdown, "Should detect auth"
        assert "payment" in breakdown, "Should detect payment"
        assert "websocket" in breakdown, "Should detect websocket"
        # auth(3) + payment(4) + websocket(3) = 10
        assert complexity.score >= 10, "Combined score should be very high"

    def test_file_upload_complexity(self):
        """Test that file operations are detected and scored."""
        task_description = "Test file upload with image attachment"
        task_scope = "Select file, upload, verify thumbnail"

        decision = self.router.route(
            task_type="write_test",
            task_description=task_description,
            task_scope=task_scope
        )

        # Should detect file operations
        complexity = self.estimator.estimate(task_description, task_scope)
        assert "file_ops" in complexity.breakdown, "Should detect file operations"
        assert complexity.breakdown["file_ops"] == 2

    def test_mocking_complexity(self):
        """Test that mocking requirements are detected."""
        task_description = "Test API error handling with mocked responses"
        task_scope = "Mock failed API calls, verify error messages"

        decision = self.router.route(
            task_type="write_test",
            task_description=task_description,
            task_scope=task_scope
        )

        # Should detect mocking
        complexity = self.estimator.estimate(task_description, task_scope)
        assert "mocking" in complexity.breakdown, "Should detect mocking"
        assert complexity.breakdown["mocking"] == 2

    def test_routing_decision_attributes(self):
        """Test that RoutingDecision contains all expected attributes."""
        decision = self.router.route(
            task_type="write_test",
            task_description="Simple test",
            task_scope="basic"
        )

        # Verify RoutingDecision dataclass structure
        assert hasattr(decision, "agent")
        assert hasattr(decision, "model")
        assert hasattr(decision, "max_cost_usd")
        assert hasattr(decision, "reason")
        assert hasattr(decision, "complexity_score")
        assert hasattr(decision, "difficulty")

        # Verify types
        assert isinstance(decision.agent, str)
        assert isinstance(decision.model, str)
        assert isinstance(decision.max_cost_usd, (int, float))
        assert isinstance(decision.reason, str)
        assert isinstance(decision.complexity_score, int)
        assert isinstance(decision.difficulty, str)

    def test_glob_pattern_matching_variations(self):
        """Test cost override glob pattern matching with various path formats."""
        # Test different auth path patterns (must contain auth somewhere in path)
        auth_paths = [
            "auth/login.spec.ts",
            "src/auth/oauth.spec.ts",
            "features/auth/nested/2fa.spec.ts"
        ]

        for path in auth_paths:
            decision = self.router.route(
                task_type="write_test",
                task_description="Test auth",
                test_path=path
            )
            assert decision.max_cost_usd == 2.00, f"Auth path {path} should have $2.00 override"

        # Test different payment path patterns
        payment_paths = [
            "payment/checkout.spec.ts",
            "src/payment/stripe.spec.ts",
            "features/payment/billing/invoice.spec.ts"
        ]

        for path in payment_paths:
            decision = self.router.route(
                task_type="write_test",
                task_description="Test payment",
                test_path=path
            )
            assert decision.max_cost_usd == 3.00, f"Payment path {path} should have $3.00 override"

    def test_invalid_task_type(self):
        """Test that invalid task type raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            self.router.route(
                task_type="invalid_task_type",
                task_description="Some task"
            )

        assert "No routing rule found" in str(exc_info.value)

    def test_complexity_any_matches_all(self):
        """Test that 'any' complexity matches both easy and hard tasks."""
        # Execute_test has complexity: any, should work for both easy and hard

        # Easy task
        easy_decision = self.router.route(
            task_type="execute_test",
            task_description="Run simple form test"
        )
        assert easy_decision.agent == "runner"

        # Hard task
        hard_decision = self.router.route(
            task_type="execute_test",
            task_description="Run OAuth login with payment test"
        )
        assert hard_decision.agent == "runner"


class TestRouterConvenienceFunction:
    """Test the route_task convenience function."""

    def test_route_task_function(self):
        """Test route_task convenience function returns dict."""
        from agent_system.router import route_task

        result = route_task(
            task_type="write_test",
            task_description="Test user profile form",
            task_scope="simple CRUD"
        )

        # Verify dict structure
        assert isinstance(result, dict)
        assert "agent" in result
        assert "model" in result
        assert "max_cost_usd" in result
        assert "reason" in result
        assert "complexity_score" in result
        assert "difficulty" in result

        # Verify values
        assert result["agent"] == "scribe"
        assert result["model"] == "haiku"
        assert result["difficulty"] == "easy"

    def test_route_task_with_path(self):
        """Test route_task with test path for cost override."""
        from agent_system.router import route_task

        result = route_task(
            task_type="write_test",
            task_description="Test payment flow with auth and mock API",
            test_path="payment/checkout.spec.ts"
        )

        assert result["max_cost_usd"] == 3.00
        assert result["agent"] == "scribe"
        # Should be hard due to payment(4) + auth(3) + mocking(2) = 9 >= 5
        assert result["model"] == "sonnet"


class TestRouterEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up router for each test."""
        self.router = Router()

    def test_empty_description(self):
        """Test routing with empty description (should use defaults)."""
        decision = self.router.route(
            task_type="write_test",
            task_description=""
        )

        # Should default to easy complexity
        assert decision.difficulty == "easy"
        assert decision.model == "haiku"

    def test_no_test_path(self):
        """Test routing without test path (should use base cost)."""
        decision = self.router.route(
            task_type="write_test",
            task_description="Test something",
            test_path=None
        )

        assert decision.max_cost_usd == 0.50

    def test_non_matching_test_path(self):
        """Test that non-critical paths use default cost."""
        decision = self.router.route(
            task_type="write_test",
            task_description="Test feature",
            test_path="tests/random/feature.spec.ts"
        )

        assert decision.max_cost_usd == 0.50

    def test_case_insensitive_complexity_detection(self):
        """Test that complexity detection is case-insensitive."""
        # Uppercase
        decision1 = self.router.route(
            task_type="write_test",
            task_description="Test OAUTH LOGIN with WEBSOCKET"
        )

        # Lowercase
        decision2 = self.router.route(
            task_type="write_test",
            task_description="test oauth login with websocket"
        )

        # Mixed case
        decision3 = self.router.route(
            task_type="write_test",
            task_description="Test OAuth Login with WebSocket"
        )

        # All should be hard complexity
        assert decision1.difficulty == "hard"
        assert decision2.difficulty == "hard"
        assert decision3.difficulty == "hard"

    def test_zero_budget_check(self):
        """Test budget check with zero spending."""
        result = self.router.check_budget(current_spend=0.00, budget_type="per_session")

        assert result["status"] == "ok"
        assert result["remaining"] == 5.00
        assert result["percent_used"] == 0.0

    def test_exact_threshold_budget(self):
        """Test budget check at exact threshold values."""
        # Exactly at 80% (soft limit)
        result = self.router.check_budget(current_spend=4.00, budget_type="per_session")
        assert result["status"] == "warning"

        # Exactly at 100% (hard limit)
        result = self.router.check_budget(current_spend=5.00, budget_type="per_session")
        assert result["status"] == "exceeded"
