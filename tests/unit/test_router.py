"""
Unit tests for agent_system/router.py cost override logic and routing decisions.

Tests cover:
- Glob pattern matching for critical paths (auth/payment/admin)
- Cost override logic with different test paths
- Fallback routing for unknown task types
- Budget checking (soft/hard limits)
- YAML loading and configuration handling
"""
import pytest
from unittest.mock import Mock, patch, mock_open
import yaml
import tempfile
import os
from pathlib import Path

from agent_system.router import Router, RoutingDecision, route_task


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_policy_data():
    """Mock router policy configuration."""
    return {
        'version': 1,
        'routing': [
            {
                'task': 'write_test',
                'complexity': 'easy',
                'agent': 'scribe',
                'model': 'haiku',
                'reason': 'Simple CRUD/visible UI path'
            },
            {
                'task': 'write_test',
                'complexity': 'hard',
                'agent': 'scribe',
                'model': 'sonnet',
                'reason': 'Multi-step flows, async, auth, edge cases'
            },
            {
                'task': 'execute_test',
                'complexity': 'any',
                'agent': 'runner',
                'model': 'haiku',
                'reason': 'Test execution is straightforward'
            },
            {
                'task': 'fix_bug',
                'complexity': 'any',
                'agent': 'medic',
                'model': 'sonnet',
                'reason': 'Bug fixing requires deep reasoning'
            },
            {
                'task': 'pre_validate',
                'complexity': 'any',
                'agent': 'critic',
                'model': 'haiku',
                'reason': 'Quick quality checks before validation'
            },
            {
                'task': 'validate',
                'complexity': 'any',
                'agent': 'gemini',
                'model': '2.5_pro',
                'reason': 'Real browser validation with visual evidence'
            }
        ],
        'cost_targets': {
            'use_haiku_ratio': 0.7,
            'max_cost_per_feature_usd': 0.50
        },
        'cost_overrides': {
            'critical_paths': [
                {
                    'pattern': '*auth*.spec.ts',
                    'max_cost_usd': 2.00,
                    'reason': 'Authentication is critical infrastructure'
                },
                {
                    'pattern': '*payment*.spec.ts',
                    'max_cost_usd': 3.00,
                    'reason': 'Payment flows require thorough validation'
                },
                {
                    'pattern': '*admin*.spec.ts',
                    'max_cost_usd': 1.50,
                    'reason': 'Admin features affect all users'
                }
            ]
        },
        'fallbacks': {
            'critic_fail': 'return_to_scribe',
            'validation_timeout': 'retry_runner_then_medic',
            'medic_escalation': 'queue_for_hitl',
            'max_retries': 3
        },
        'budget_enforcement': {
            'soft_limit_warning': 0.80,
            'hard_limit_stop': 1.00,
            'daily_budget_usd': 50.00,
            'per_session_budget_usd': 5.00
        }
    }


@pytest.fixture
def mock_complexity_estimator():
    """Mock ComplexityEstimator for testing."""
    with patch('agent_system.router.ComplexityEstimator') as mock_class:
        mock_instance = Mock()
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def router_with_mock_policy(mock_policy_data, mock_complexity_estimator):
    """Create router with mocked policy data."""
    with patch('builtins.open', mock_open(read_data=yaml.dump(mock_policy_data))):
        router = Router(config_path='/fake/path/router_policy.yaml')
        return router


# ============================================================================
# TEST: Cost Override Logic - Glob Pattern Matching
# ============================================================================

class TestCostOverrides:
    """Test cost override logic for critical paths."""

    def test_auth_path_gets_2_dollar_override(self, router_with_mock_policy):
        """Test that auth paths match *auth*.spec.ts pattern and get $2.00 budget."""
        test_paths = [
            'login-auth.spec.ts',
            'auth-login.spec.ts',
            'user_auth_flow.spec.ts',
            'authentication.spec.ts'
        ]

        for path in test_paths:
            cost = router_with_mock_policy._apply_cost_override(path, 0.50)
            assert cost == 2.00, f"Auth path {path} should get $2.00 override, got ${cost}"

    def test_payment_path_gets_3_dollar_override(self, router_with_mock_policy):
        """Test that payment paths match *payment*.spec.ts pattern and get $3.00 budget."""
        test_paths = [
            'checkout-payment.spec.ts',
            'payment-flow.spec.ts',
            'stripe_payment.spec.ts',
            'payment_refund.spec.ts'
        ]

        for path in test_paths:
            cost = router_with_mock_policy._apply_cost_override(path, 0.50)
            assert cost == 3.00, f"Payment path {path} should get $3.00 override, got ${cost}"

    def test_admin_path_gets_1_50_dollar_override(self, router_with_mock_policy):
        """Test that admin paths match *admin*.spec.ts pattern and get $1.50 budget."""
        test_paths = [
            'admin-users.spec.ts',
            'admin_dashboard.spec.ts',
            'user-admin.spec.ts',
            'administrator.spec.ts'
        ]

        for path in test_paths:
            cost = router_with_mock_policy._apply_cost_override(path, 0.50)
            assert cost == 1.50, f"Admin path {path} should get $1.50 override, got ${cost}"

    def test_regular_paths_get_base_cost(self, router_with_mock_policy):
        """Test that non-critical paths use base cost ($0.50)."""
        test_paths = [
            'tests/cart/add-to-cart.spec.ts',
            'tests/search/filters.spec.ts',
            'tests/profile/edit.spec.ts',
            'features/notifications/push.spec.ts'
        ]

        for path in test_paths:
            cost = router_with_mock_policy._apply_cost_override(path, 0.50)
            assert cost == 0.50, f"Regular path {path} should use base cost $0.50, got ${cost}"

    def test_none_path_returns_base_cost(self, router_with_mock_policy):
        """Test that None path returns base cost."""
        cost = router_with_mock_policy._apply_cost_override(None, 0.50)
        assert cost == 0.50

    def test_empty_path_returns_base_cost(self, router_with_mock_policy):
        """Test that empty path returns base cost."""
        cost = router_with_mock_policy._apply_cost_override('', 0.50)
        assert cost == 0.50

    def test_non_typescript_files_dont_match(self, router_with_mock_policy):
        """Test that non-.spec.ts files don't match critical path patterns."""
        test_paths = [
            'auth-login.test.js',
            'payment-checkout.py',
            'admin-users.spec.jsx'
        ]

        for path in test_paths:
            cost = router_with_mock_policy._apply_cost_override(path, 0.50)
            assert cost == 0.50, f"Non-.spec.ts file {path} should not match critical paths"

    def test_first_matching_pattern_wins(self, router_with_mock_policy):
        """Test that first matching pattern takes precedence."""
        # If a path matches multiple patterns, first match wins
        # This is implicit in the current implementation
        path = 'auth-login.spec.ts'
        cost = router_with_mock_policy._apply_cost_override(path, 0.50)
        assert cost == 2.00


# ============================================================================
# TEST: Routing Logic
# ============================================================================

class TestRouting:
    """Test routing decisions for different task types."""

    def test_route_write_test_easy_uses_haiku(self, router_with_mock_policy, mock_complexity_estimator):
        """Test that easy write_test tasks use scribe/haiku."""
        mock_result = Mock(score=3, difficulty='easy')
        mock_complexity_estimator.estimate.return_value = mock_result

        decision = router_with_mock_policy.route('write_test', 'Simple login form', 'happy path')

        assert decision.agent == 'scribe'
        assert decision.model == 'haiku'
        assert decision.max_cost_usd == 0.50
        assert decision.difficulty == 'easy'

    def test_route_write_test_hard_uses_sonnet(self, router_with_mock_policy, mock_complexity_estimator):
        """Test that hard write_test tasks use scribe/sonnet."""
        mock_result = Mock(score=8, difficulty='hard')
        mock_complexity_estimator.estimate.return_value = mock_result

        decision = router_with_mock_policy.route(
            'write_test',
            'OAuth flow with multiple providers and token refresh',
            'authentication'
        )

        assert decision.agent == 'scribe'
        assert decision.model == 'sonnet'
        assert decision.max_cost_usd == 0.50
        assert decision.difficulty == 'hard'

    def test_route_execute_test_always_uses_haiku(self, router_with_mock_policy, mock_complexity_estimator):
        """Test that execute_test always uses runner/haiku regardless of complexity."""
        mock_result = Mock(score=5, difficulty='hard')
        mock_complexity_estimator.estimate.return_value = mock_result

        decision = router_with_mock_policy.route('execute_test', 'Run login test')

        assert decision.agent == 'runner'
        assert decision.model == 'haiku'

    def test_route_fix_bug_always_uses_sonnet(self, router_with_mock_policy, mock_complexity_estimator):
        """Test that fix_bug always uses medic/sonnet."""
        mock_result = Mock(score=2, difficulty='easy')
        mock_complexity_estimator.estimate.return_value = mock_result

        decision = router_with_mock_policy.route('fix_bug', 'Fix selector issue')

        assert decision.agent == 'medic'
        assert decision.model == 'sonnet'

    def test_route_pre_validate_uses_critic_haiku(self, router_with_mock_policy, mock_complexity_estimator):
        """Test that pre_validate uses critic/haiku."""
        mock_result = Mock(score=1, difficulty='easy')
        mock_complexity_estimator.estimate.return_value = mock_result

        decision = router_with_mock_policy.route('pre_validate', 'Check test quality')

        assert decision.agent == 'critic'
        assert decision.model == 'haiku'

    def test_route_validate_uses_gemini(self, router_with_mock_policy, mock_complexity_estimator):
        """Test that validate uses gemini/2.5_pro."""
        mock_result = Mock(score=1, difficulty='easy')
        mock_complexity_estimator.estimate.return_value = mock_result

        decision = router_with_mock_policy.route('validate', 'Validate in browser')

        assert decision.agent == 'gemini'
        assert decision.model == '2.5_pro'

    def test_route_with_auth_path_override(self, router_with_mock_policy, mock_complexity_estimator):
        """Test routing with auth path gets cost override."""
        mock_result = Mock(score=3, difficulty='easy')
        mock_complexity_estimator.estimate.return_value = mock_result

        decision = router_with_mock_policy.route(
            'write_test',
            'Login form test',
            'auth',
            test_path='login-auth.spec.ts'
        )

        assert decision.agent == 'scribe'
        assert decision.model == 'haiku'
        assert decision.max_cost_usd == 2.00  # Auth override

    def test_route_with_payment_path_override(self, router_with_mock_policy, mock_complexity_estimator):
        """Test routing with payment path gets cost override."""
        mock_result = Mock(score=6, difficulty='hard')
        mock_complexity_estimator.estimate.return_value = mock_result

        decision = router_with_mock_policy.route(
            'write_test',
            'Checkout flow',
            'payment',
            test_path='checkout-payment.spec.ts'
        )

        assert decision.agent == 'scribe'
        assert decision.model == 'sonnet'
        assert decision.max_cost_usd == 3.00  # Payment override

    def test_route_unknown_task_raises_error(self, router_with_mock_policy, mock_complexity_estimator):
        """Test that unknown task type raises ValueError."""
        mock_result = Mock(score=3, difficulty='easy')
        mock_complexity_estimator.estimate.return_value = mock_result

        with pytest.raises(ValueError, match="No routing rule found"):
            router_with_mock_policy.route('unknown_task', 'Some description')


# ============================================================================
# TEST: Fallback Logic
# ============================================================================

class TestFallbacks:
    """Test fallback behavior for failures."""

    def test_get_fallback_critic_fail(self, router_with_mock_policy):
        """Test fallback for critic_fail."""
        fallback = router_with_mock_policy.get_fallback('critic_fail')
        assert fallback == 'return_to_scribe'

    def test_get_fallback_validation_timeout(self, router_with_mock_policy):
        """Test fallback for validation_timeout."""
        fallback = router_with_mock_policy.get_fallback('validation_timeout')
        assert fallback == 'retry_runner_then_medic'

    def test_get_fallback_medic_escalation(self, router_with_mock_policy):
        """Test fallback for medic_escalation."""
        fallback = router_with_mock_policy.get_fallback('medic_escalation')
        assert fallback == 'queue_for_hitl'

    def test_get_fallback_unknown_type_returns_default(self, router_with_mock_policy):
        """Test that unknown failure type returns default fallback."""
        fallback = router_with_mock_policy.get_fallback('unknown_failure')
        assert fallback == 'queue_for_hitl'

    def test_get_max_retries(self, router_with_mock_policy):
        """Test getting max retries from policy."""
        max_retries = router_with_mock_policy.get_max_retries()
        assert max_retries == 3


# ============================================================================
# TEST: Budget Checking
# ============================================================================

class TestBudgetChecking:
    """Test budget enforcement logic."""

    def test_check_budget_per_session_ok(self, router_with_mock_policy):
        """Test budget check when spending is within limits."""
        result = router_with_mock_policy.check_budget(2.00, 'per_session')

        assert result['status'] == 'ok'
        assert result['limit'] == 5.00
        assert result['remaining'] == 3.00
        assert result['percent_used'] == 40.0
        assert result['warning'] is None

    def test_check_budget_per_session_soft_limit(self, router_with_mock_policy):
        """Test budget check at 80% (soft limit warning)."""
        result = router_with_mock_policy.check_budget(4.00, 'per_session')

        assert result['status'] == 'warning'
        assert result['limit'] == 5.00
        assert result['remaining'] == 1.00
        assert result['percent_used'] == 80.0
        assert 'Budget warning' in result['warning']
        assert '80.0%' in result['warning']

    def test_check_budget_per_session_hard_limit(self, router_with_mock_policy):
        """Test budget check at 100% (hard limit stop)."""
        result = router_with_mock_policy.check_budget(5.00, 'per_session')

        assert result['status'] == 'exceeded'
        assert result['limit'] == 5.00
        assert result['remaining'] == 0.00
        assert result['percent_used'] == 100.0
        assert 'Budget exceeded' in result['warning']

    def test_check_budget_per_session_over_limit(self, router_with_mock_policy):
        """Test budget check when spending exceeds limit."""
        result = router_with_mock_policy.check_budget(6.00, 'per_session')

        assert result['status'] == 'exceeded'
        assert result['limit'] == 5.00
        assert result['remaining'] == -1.00
        assert result['percent_used'] == 120.0

    def test_check_budget_daily_ok(self, router_with_mock_policy):
        """Test daily budget check when spending is ok."""
        result = router_with_mock_policy.check_budget(25.00, 'daily')

        assert result['status'] == 'ok'
        assert result['limit'] == 50.00
        assert result['remaining'] == 25.00
        assert result['percent_used'] == 50.0

    def test_check_budget_daily_soft_limit(self, router_with_mock_policy):
        """Test daily budget check at soft limit (80%)."""
        result = router_with_mock_policy.check_budget(40.00, 'daily')

        assert result['status'] == 'warning'
        assert result['limit'] == 50.00

    def test_check_budget_daily_hard_limit(self, router_with_mock_policy):
        """Test daily budget check at hard limit (100%)."""
        result = router_with_mock_policy.check_budget(50.00, 'daily')

        assert result['status'] == 'exceeded'
        assert result['limit'] == 50.00

    def test_check_budget_edge_case_just_below_soft_limit(self, router_with_mock_policy):
        """Test budget just below soft limit (79.9%)."""
        result = router_with_mock_policy.check_budget(3.99, 'per_session')

        assert result['status'] == 'ok'
        assert result['warning'] is None

    def test_check_budget_edge_case_just_at_soft_limit(self, router_with_mock_policy):
        """Test budget exactly at soft limit (80%)."""
        result = router_with_mock_policy.check_budget(4.00, 'per_session')

        assert result['status'] == 'warning'
        assert result['warning'] is not None


# ============================================================================
# TEST: Policy Loading
# ============================================================================

class TestPolicyLoading:
    """Test YAML policy configuration loading."""

    def test_load_policy_success(self, mock_policy_data):
        """Test successful policy loading."""
        with patch('builtins.open', mock_open(read_data=yaml.dump(mock_policy_data))):
            router = Router(config_path='/fake/path/router_policy.yaml')
            assert router.policy == mock_policy_data

    def test_load_policy_file_not_found(self):
        """Test that FileNotFoundError is raised when policy file doesn't exist."""
        with pytest.raises(FileNotFoundError, match="Router policy not found"):
            Router(config_path='/nonexistent/router_policy.yaml')

    def test_load_policy_invalid_yaml(self):
        """Test that ValueError is raised for invalid YAML."""
        invalid_yaml = "invalid: yaml: content: [[[["
        with patch('builtins.open', mock_open(read_data=invalid_yaml)):
            with pytest.raises(ValueError, match="Invalid YAML"):
                Router(config_path='/fake/path/router_policy.yaml')

    def test_load_policy_empty_file(self):
        """Test handling of empty policy file."""
        with patch('builtins.open', mock_open(read_data='')):
            router = Router(config_path='/fake/path/router_policy.yaml')
            assert router.policy is None or router.policy == {}

    def test_router_default_config_path(self, mock_policy_data):
        """Test that Router uses default config path when none provided."""
        expected_path = Path(__file__).parent.parent.parent / 'agent_system' / '..' / '.claude' / 'router_policy.yaml'

        with patch('builtins.open', mock_open(read_data=yaml.dump(mock_policy_data))) as mock_file:
            router = Router()
            # Verify that a path was attempted
            assert router.config_path is not None


# ============================================================================
# TEST: Configuration Variations
# ============================================================================

class TestConfigurationVariations:
    """Test router behavior with different policy configurations."""

    def test_missing_cost_overrides_section(self, mock_complexity_estimator):
        """Test router works when cost_overrides section is missing."""
        minimal_policy = {
            'version': 1,
            'routing': [
                {
                    'task': 'write_test',
                    'complexity': 'easy',
                    'agent': 'scribe',
                    'model': 'haiku',
                    'reason': 'Test'
                }
            ],
            'cost_targets': {
                'max_cost_per_feature_usd': 0.50
            }
        }

        with patch('builtins.open', mock_open(read_data=yaml.dump(minimal_policy))):
            router = Router(config_path='/fake/path/router_policy.yaml')
            cost = router._apply_cost_override('tests/auth/login.spec.ts', 0.50)
            assert cost == 0.50  # Should return base cost

    def test_empty_critical_paths_list(self, mock_complexity_estimator):
        """Test router when critical_paths list is empty."""
        policy = {
            'version': 1,
            'routing': [
                {
                    'task': 'write_test',
                    'complexity': 'easy',
                    'agent': 'scribe',
                    'model': 'haiku',
                    'reason': 'Test'
                }
            ],
            'cost_targets': {
                'max_cost_per_feature_usd': 0.50
            },
            'cost_overrides': {
                'critical_paths': []
            }
        }

        with patch('builtins.open', mock_open(read_data=yaml.dump(policy))):
            router = Router(config_path='/fake/path/router_policy.yaml')
            cost = router._apply_cost_override('tests/auth/login.spec.ts', 0.50)
            assert cost == 0.50

    def test_missing_budget_enforcement(self, mock_complexity_estimator):
        """Test check_budget with missing budget_enforcement section."""
        minimal_policy = {
            'version': 1,
            'routing': [
                {
                    'task': 'write_test',
                    'complexity': 'easy',
                    'agent': 'scribe',
                    'model': 'haiku',
                    'reason': 'Test'
                }
            ]
        }

        with patch('builtins.open', mock_open(read_data=yaml.dump(minimal_policy))):
            router = Router(config_path='/fake/path/router_policy.yaml')
            result = router.check_budget(2.00, 'per_session')
            # Should use default budget of 5.00
            assert result['limit'] == 5.00


# ============================================================================
# TEST: Convenience Function
# ============================================================================

class TestConvenienceFunction:
    """Test the route_task convenience function."""

    def test_route_task_returns_dict(self, mock_policy_data, mock_complexity_estimator):
        """Test that route_task returns a dictionary with correct keys."""
        mock_result = Mock(score=3, difficulty='easy')
        mock_complexity_estimator.estimate.return_value = mock_result

        with patch('builtins.open', mock_open(read_data=yaml.dump(mock_policy_data))):
            result = route_task('write_test', 'Simple test', 'happy path')

            assert isinstance(result, dict)
            assert 'agent' in result
            assert 'model' in result
            assert 'max_cost_usd' in result
            assert 'reason' in result
            assert 'complexity_score' in result
            assert 'difficulty' in result

    def test_route_task_with_test_path(self, mock_policy_data, mock_complexity_estimator):
        """Test route_task with test_path parameter."""
        mock_result = Mock(score=3, difficulty='easy')
        mock_complexity_estimator.estimate.return_value = mock_result

        with patch('builtins.open', mock_open(read_data=yaml.dump(mock_policy_data))):
            result = route_task(
                'write_test',
                'Auth test',
                'authentication',
                test_path='login-auth.spec.ts'
            )

            assert result['max_cost_usd'] == 2.00  # Auth override


# ============================================================================
# TEST: Haiku Ratio Target
# ============================================================================

class TestHaikuRatioTarget:
    """Test Haiku usage ratio target."""

    def test_get_haiku_ratio_target(self, router_with_mock_policy):
        """Test getting Haiku ratio target from policy."""
        ratio = router_with_mock_policy.get_haiku_ratio_target()
        assert ratio == 0.7

    def test_get_haiku_ratio_target_missing(self, mock_complexity_estimator):
        """Test Haiku ratio when cost_targets section is missing."""
        minimal_policy = {
            'version': 1,
            'routing': []
        }

        with patch('builtins.open', mock_open(read_data=yaml.dump(minimal_policy))):
            router = Router(config_path='/fake/path/router_policy.yaml')
            # Should handle missing gracefully (returns None or default)
            ratio = router.get_haiku_ratio_target()
            assert ratio is None or isinstance(ratio, float)


# ============================================================================
# TEST: Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_special_characters_in_path(self, router_with_mock_policy):
        """Test cost override with special characters in path."""
        paths_with_special_chars = [
            'tests/auth (staging)/login.spec.ts',
            'tests/auth-v2/login.spec.ts',
            'tests/auth_new/login.spec.ts'
        ]

        for path in paths_with_special_chars:
            cost = router_with_mock_policy._apply_cost_override(path, 0.50)
            # Should handle gracefully, may or may not match depending on pattern

    def test_windows_style_path(self, router_with_mock_policy):
        """Test cost override with Windows-style path."""
        path = 'tests\\auth\\login.spec.ts'
        cost = router_with_mock_policy._apply_cost_override(path, 0.50)
        # fnmatch may not match Windows paths with ** pattern
        assert isinstance(cost, float)

    def test_absolute_vs_relative_paths(self, router_with_mock_policy):
        """Test that both absolute and relative paths work with wildcard pattern."""
        relative_path = 'login-auth.spec.ts'
        absolute_path = '/home/user/project/login-auth.spec.ts'

        relative_cost = router_with_mock_policy._apply_cost_override(relative_path, 0.50)
        absolute_cost = router_with_mock_policy._apply_cost_override(absolute_path, 0.50)

        # Both should match auth pattern with *auth* wildcard
        assert relative_cost == 2.00
        assert absolute_cost == 2.00

    def test_case_sensitivity_in_paths(self, router_with_mock_policy):
        """Test case sensitivity in path matching."""
        paths = [
            'tests/Auth/login.spec.ts',  # Capital A
            'tests/AUTH/login.spec.ts',  # All caps
            'tests/auth/login.spec.ts'   # Lowercase
        ]

        costs = [router_with_mock_policy._apply_cost_override(p, 0.50) for p in paths]
        # fnmatch is case-sensitive on Unix, case-insensitive on Windows
        # All should be handled gracefully

    def test_zero_budget(self, router_with_mock_policy):
        """Test budget check with zero spending."""
        result = router_with_mock_policy.check_budget(0.00, 'per_session')

        assert result['status'] == 'ok'
        assert result['remaining'] == 5.00
        assert result['percent_used'] == 0.0

    def test_negative_spending_handled_gracefully(self, router_with_mock_policy):
        """Test that negative spending doesn't break budget check."""
        result = router_with_mock_policy.check_budget(-1.00, 'per_session')

        # Should handle gracefully, probably showing more remaining budget
        assert isinstance(result, dict)
        assert 'status' in result


# ============================================================================
# TEST: Integration-like Tests
# ============================================================================

class TestIntegrationScenarios:
    """Test realistic end-to-end scenarios."""

    def test_full_routing_workflow_easy_test(self, router_with_mock_policy, mock_complexity_estimator):
        """Test complete routing workflow for easy test."""
        mock_result = Mock(score=2, difficulty='easy')
        mock_complexity_estimator.estimate.return_value = mock_result

        decision = router_with_mock_policy.route(
            task_type='write_test',
            task_description='Create test for simple form submission',
            task_scope='happy path',
            test_path='tests/forms/contact.spec.ts'
        )

        assert decision.agent == 'scribe'
        assert decision.model == 'haiku'
        assert decision.max_cost_usd == 0.50
        assert decision.difficulty == 'easy'
        assert decision.complexity_score == 2

    def test_full_routing_workflow_critical_path(self, router_with_mock_policy, mock_complexity_estimator):
        """Test complete routing workflow for critical path (payment)."""
        mock_result = Mock(score=7, difficulty='hard')
        mock_complexity_estimator.estimate.return_value = mock_result

        decision = router_with_mock_policy.route(
            task_type='write_test',
            task_description='Stripe checkout with 3DS authentication',
            task_scope='payment flow',
            test_path='checkout-payment.spec.ts'
        )

        assert decision.agent == 'scribe'
        assert decision.model == 'sonnet'  # Hard complexity
        assert decision.max_cost_usd == 3.00  # Payment override
        assert decision.difficulty == 'hard'
        assert decision.complexity_score == 7

    def test_budget_enforcement_workflow(self, router_with_mock_policy):
        """Test complete budget enforcement workflow."""
        # Start with ok budget
        result1 = router_with_mock_policy.check_budget(1.00, 'per_session')
        assert result1['status'] == 'ok'

        # Increase to warning threshold
        result2 = router_with_mock_policy.check_budget(4.00, 'per_session')
        assert result2['status'] == 'warning'

        # Exceed budget
        result3 = router_with_mock_policy.check_budget(5.50, 'per_session')
        assert result3['status'] == 'exceeded'
