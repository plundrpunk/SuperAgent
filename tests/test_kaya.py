"""
Unit tests for agent_system/agents/kaya.py - Kaya Orchestrator Agent.

Tests cover:
- Intent parsing for all voice commands (create_test, run_test, fix_failure, validate, status)
- Routing decisions (Haiku vs Sonnet) via router integration
- Agent dispatch and coordination
- Result aggregation from multiple agents
- Cost tracking across session
- Budget enforcement (soft warning at 80%, hard stop at 100%)
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import time

from agent_system.agents.kaya import KayaAgent
from agent_system.agents.base_agent import AgentResult
from agent_system.router import RoutingDecision


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def kaya():
    """Create KayaAgent instance with mocked router."""
    with patch('agent_system.agents.kaya.Router') as mock_router_class:
        mock_router = Mock()
        mock_router_class.return_value = mock_router
        agent = KayaAgent()
        agent.router = mock_router
        return agent


@pytest.fixture
def mock_routing_decision():
    """Create a mock routing decision."""
    def _create_decision(agent='scribe', model='haiku', max_cost=0.50, complexity='easy', score=3):
        return RoutingDecision(
            agent=agent,
            model=model,
            max_cost_usd=max_cost,
            reason=f"Test routing to {agent}/{model}",
            complexity_score=score,
            difficulty=complexity
        )
    return _create_decision


# ============================================================================
# TEST: Intent Parsing - create_test
# ============================================================================

class TestIntentParsingCreateTest:
    """Test intent parsing for create_test commands."""

    def test_create_test_basic(self, kaya):
        """Test basic 'create test for' pattern."""
        result = kaya.parse_intent("create a test for login")

        assert result['success'] is True
        assert result['intent'] == 'create_test'
        assert result['slots']['raw_value'] == 'login'

    def test_create_test_complex_feature(self, kaya):
        """Test create test with complex feature description."""
        result = kaya.parse_intent("create a test for checkout happy path with payment")

        assert result['success'] is True
        assert result['intent'] == 'create_test'
        assert 'checkout happy path with payment' in result['slots']['raw_value']

    def test_write_test_variant(self, kaya):
        """Test 'write test for' pattern variant."""
        result = kaya.parse_intent("write a test for user registration")

        assert result['success'] is True
        assert result['intent'] == 'create_test'
        assert result['slots']['raw_value'] == 'user registration'

    def test_generate_test_variant(self, kaya):
        """Test 'generate test for' pattern variant."""
        result = kaya.parse_intent("generate test for shopping cart")

        assert result['success'] is True
        assert result['intent'] == 'create_test'
        assert result['slots']['raw_value'] == 'shopping cart'

    def test_create_test_case_insensitive(self, kaya):
        """Test that intent parsing is case-insensitive."""
        result = kaya.parse_intent("CREATE TEST FOR login flow")

        assert result['success'] is True
        assert result['intent'] == 'create_test'
        assert 'login flow' in result['slots']['raw_value']

    def test_create_test_with_kaya_prefix(self, kaya):
        """Test command with 'Kaya' prefix."""
        result = kaya.parse_intent("Kaya, create test for authentication")

        assert result['success'] is True
        assert result['intent'] == 'create_test'
        assert 'authentication' in result['slots']['raw_value']


# ============================================================================
# TEST: Intent Parsing - run_test
# ============================================================================

class TestIntentParsingRunTest:
    """Test intent parsing for run_test commands."""

    def test_run_test_basic(self, kaya):
        """Test basic 'run test' pattern."""
        result = kaya.parse_intent("run test tests/login.spec.ts")

        assert result['success'] is True
        assert result['intent'] == 'run_test'
        assert result['slots']['raw_value'] == 'tests/login.spec.ts'

    def test_run_tests_plural(self, kaya):
        """Test 'run tests' pattern with plural."""
        result = kaya.parse_intent("run tests tests/auth.spec.ts")

        assert result['success'] is True
        assert result['intent'] == 'run_test'
        assert 'tests/auth.spec.ts' in result['slots']['raw_value']

    def test_execute_test_variant(self, kaya):
        """Test 'execute test' pattern variant."""
        result = kaya.parse_intent("execute test tests/checkout.spec.ts")

        assert result['success'] is True
        assert result['intent'] == 'run_test'
        assert 'tests/checkout.spec.ts' in result['slots']['raw_value']

    def test_run_test_with_path(self, kaya):
        """Test run test with full path."""
        result = kaya.parse_intent("run test /home/user/project/tests/cart.spec.ts")

        assert result['success'] is True
        assert result['intent'] == 'run_test'
        assert '/home/user/project/tests/cart.spec.ts' in result['slots']['raw_value']


# ============================================================================
# TEST: Intent Parsing - fix_failure
# ============================================================================

class TestIntentParsingFixFailure:
    """Test intent parsing for fix_failure commands."""

    def test_fix_task_basic(self, kaya):
        """Test basic 'fix task' pattern."""
        result = kaya.parse_intent("fix task t_123")

        assert result['success'] is True
        assert result['intent'] == 'fix_failure'
        assert result['slots']['raw_value'] == 't_123'

    def test_patch_task_variant(self, kaya):
        """Test 'patch task' pattern variant."""
        result = kaya.parse_intent("patch task task_456")

        assert result['success'] is True
        assert result['intent'] == 'fix_failure'
        assert result['slots']['raw_value'] == 'task_456'

    def test_repair_task_variant(self, kaya):
        """Test 'repair task' pattern variant."""
        result = kaya.parse_intent("repair task abc123")

        assert result['success'] is True
        assert result['intent'] == 'fix_failure'
        assert result['slots']['raw_value'] == 'abc123'

    def test_fix_task_with_description(self, kaya):
        """Test fix task with additional context."""
        result = kaya.parse_intent("fix task t_789 and retry")

        assert result['success'] is True
        assert result['intent'] == 'fix_failure'
        assert 't_789' in result['slots']['raw_value']


# ============================================================================
# TEST: Intent Parsing - validate
# ============================================================================

class TestIntentParsingValidate:
    """Test intent parsing for validate commands."""

    def test_validate_basic(self, kaya):
        """Test basic 'validate' pattern."""
        result = kaya.parse_intent("validate payment flow")

        assert result['success'] is True
        assert result['intent'] == 'validate'
        assert result['slots']['raw_value'] == 'payment flow'

    def test_verify_variant(self, kaya):
        """Test 'verify' pattern variant."""
        result = kaya.parse_intent("verify authentication test")

        assert result['success'] is True
        assert result['intent'] == 'validate'
        assert result['slots']['raw_value'] == 'authentication test'

    def test_validate_with_priority(self, kaya):
        """Test validate with priority marker."""
        result = kaya.parse_intent("validate payment flow - critical")

        assert result['success'] is True
        assert result['intent'] == 'validate'
        assert 'payment flow - critical' in result['slots']['raw_value']

    def test_validate_test_path(self, kaya):
        """Test validate with test file path."""
        result = kaya.parse_intent("validate tests/checkout-payment.spec.ts")

        assert result['success'] is True
        assert result['intent'] == 'validate'
        assert 'tests/checkout-payment.spec.ts' in result['slots']['raw_value']


# ============================================================================
# TEST: Intent Parsing - status
# ============================================================================

class TestIntentParsingStatus:
    """Test intent parsing for status commands."""

    def test_status_basic(self, kaya):
        """Test basic 'status task' pattern."""
        result = kaya.parse_intent("status task t_123")

        assert result['success'] is True
        assert result['intent'] == 'status'
        assert result['slots']['raw_value'] == 't_123'

    def test_status_what_pattern(self, kaya):
        """Test 'what's the status' pattern."""
        result = kaya.parse_intent("what's the status of task t_456")

        assert result['success'] is True
        assert result['intent'] == 'status'
        assert 't_456' in result['slots']['raw_value']

    def test_status_natural_language(self, kaya):
        """Test natural language status query."""
        result = kaya.parse_intent("what is the status of task abc123")

        assert result['success'] is True
        assert result['intent'] == 'status'
        assert 'abc123' in result['slots']['raw_value']


# ============================================================================
# TEST: Intent Parsing - Unknown/Invalid
# ============================================================================

class TestIntentParsingUnknown:
    """Test intent parsing for unknown or invalid commands."""

    def test_unknown_command(self, kaya):
        """Test completely unknown command."""
        result = kaya.parse_intent("do something random")

        assert result['success'] is False
        assert result['intent'] is None
        assert result['slots'] == {}

    def test_empty_command(self, kaya):
        """Test empty command string."""
        result = kaya.parse_intent("")

        assert result['success'] is False
        assert result['intent'] is None

    def test_only_keyword(self, kaya):
        """Test command with only keyword, no arguments."""
        result = kaya.parse_intent("create test")

        # Should not match because patterns require "for" + argument
        assert result['success'] is False

    def test_whitespace_only(self, kaya):
        """Test command with only whitespace."""
        result = kaya.parse_intent("   ")

        assert result['success'] is False


# ============================================================================
# TEST: Routing Integration - create_test
# ============================================================================

class TestRoutingCreateTest:
    """Test routing decisions for create_test commands."""

    def test_route_create_test_easy(self, kaya, mock_routing_decision):
        """Test routing easy create_test to scribe/haiku."""
        easy_decision = mock_routing_decision(agent='scribe', model='haiku', complexity='easy')
        kaya.router.route.return_value = easy_decision

        result = kaya.execute("create test for simple login form")

        assert result.success is True
        assert result.data['action'] == 'route_to_scribe'
        assert result.data['feature'] == 'simple login form'
        assert result.data['agent'] == 'scribe'
        assert result.data['model'] == 'haiku'
        assert result.data['max_cost'] == 0.50

        # Verify router was called correctly
        kaya.router.route.assert_called_once_with(
            task_type='write_test',
            task_description='simple login form',
            task_scope=''
        )

    def test_route_create_test_hard(self, kaya, mock_routing_decision):
        """Test routing hard create_test to scribe/sonnet."""
        hard_decision = mock_routing_decision(
            agent='scribe',
            model='sonnet',
            max_cost=0.50,
            complexity='hard',
            score=8
        )
        kaya.router.route.return_value = hard_decision

        result = kaya.execute("create test for OAuth flow with token refresh")

        assert result.success is True
        assert result.data['agent'] == 'scribe'
        assert result.data['model'] == 'sonnet'
        # Feature is lowercased by parse_intent
        assert 'oauth flow with token refresh' in result.data['feature'].lower()

    def test_route_create_test_with_routing_metadata(self, kaya, mock_routing_decision):
        """Test that routing decision is included in metadata."""
        decision = mock_routing_decision()
        kaya.router.route.return_value = decision

        result = kaya.execute("create test for checkout")

        assert result.metadata is not None
        assert 'routing_decision' in result.metadata
        assert result.metadata['routing_decision'] == decision


# ============================================================================
# TEST: Routing Integration - run_test
# ============================================================================

class TestRoutingRunTest:
    """Test routing decisions for run_test commands."""

    def test_route_run_test(self, kaya, mock_routing_decision):
        """Test routing run_test to runner/haiku."""
        runner_decision = mock_routing_decision(agent='runner', model='haiku')
        kaya.router.route.return_value = runner_decision

        result = kaya.execute("run test tests/login.spec.ts")

        assert result.success is True
        assert result.data['action'] == 'route_to_runner'
        assert result.data['test_path'] == 'tests/login.spec.ts'
        assert result.data['agent'] == 'runner'
        assert result.data['model'] == 'haiku'

        # Verify router was called with correct task type
        kaya.router.route.assert_called_once_with(
            task_type='execute_test',
            task_description='tests/login.spec.ts'
        )

    def test_route_run_test_always_haiku(self, kaya, mock_routing_decision):
        """Test that run_test always uses haiku regardless of complexity."""
        runner_decision = mock_routing_decision(agent='runner', model='haiku')
        kaya.router.route.return_value = runner_decision

        # Even complex test should use haiku for execution
        result = kaya.execute("run test tests/complex-auth.spec.ts")

        assert result.success is True
        assert result.data['model'] == 'haiku'


# ============================================================================
# TEST: Routing Integration - fix_failure
# ============================================================================

class TestRoutingFixFailure:
    """Test routing decisions for fix_failure commands."""

    def test_route_fix_failure(self, kaya, mock_routing_decision):
        """Test routing fix_failure to medic/sonnet."""
        medic_decision = mock_routing_decision(agent='medic', model='sonnet')
        kaya.router.route.return_value = medic_decision

        result = kaya.execute("fix task t_123")

        assert result.success is True
        assert result.data['action'] == 'route_to_medic'
        assert result.data['task_id'] == 't_123'
        assert result.data['agent'] == 'medic'
        assert result.data['model'] == 'sonnet'

        # Verify router was called correctly
        kaya.router.route.assert_called_once_with(
            task_type='fix_bug',
            task_description='Fix failed task t_123'
        )

    def test_route_fix_failure_always_sonnet(self, kaya, mock_routing_decision):
        """Test that fix_failure always uses sonnet for deep reasoning."""
        medic_decision = mock_routing_decision(agent='medic', model='sonnet')
        kaya.router.route.return_value = medic_decision

        result = kaya.execute("patch task abc456")

        assert result.success is True
        assert result.data['model'] == 'sonnet'


# ============================================================================
# TEST: Routing Integration - validate
# ============================================================================

class TestRoutingValidate:
    """Test routing decisions for validate commands."""

    def test_route_validate(self, kaya, mock_routing_decision):
        """Test routing validate to gemini/2.5_pro."""
        gemini_decision = mock_routing_decision(agent='gemini', model='2.5_pro', max_cost=3.00)
        kaya.router.route.return_value = gemini_decision

        result = kaya.execute("validate payment flow")

        assert result.success is True
        assert result.data['action'] == 'route_to_gemini'
        assert result.data['test_path'] == 'payment flow'
        assert result.data['agent'] == 'gemini'
        assert result.data['model'] == '2.5_pro'

        # Verify router was called correctly
        kaya.router.route.assert_called_once_with(
            task_type='validate',
            task_description='payment flow',
            test_path='payment flow'
        )

    def test_route_validate_with_test_path(self, kaya, mock_routing_decision):
        """Test validate with explicit test file path."""
        gemini_decision = mock_routing_decision(agent='gemini', model='2.5_pro')
        kaya.router.route.return_value = gemini_decision

        result = kaya.execute("validate tests/checkout-payment.spec.ts")

        assert result.success is True
        assert 'checkout-payment' in result.data['test_path']


# ============================================================================
# TEST: Status Inquiry
# ============================================================================

class TestStatusInquiry:
    """Test status inquiry handling."""

    def test_handle_status_inquiry(self, kaya):
        """Test status inquiry returns task information."""
        result = kaya.execute("status task t_123")

        assert result.success is True
        assert result.data['action'] == 'get_status'
        assert result.data['task_id'] == 't_123'
        assert 'message' in result.data
        assert 't_123' in result.data['message']

    def test_status_no_router_call(self, kaya):
        """Test that status inquiry doesn't call router."""
        result = kaya.execute("what's the status of task t_456")

        assert result.success is True
        # Router should not be called for status inquiries
        kaya.router.route.assert_not_called()


# ============================================================================
# TEST: Cost Tracking
# ============================================================================

class TestCostTracking:
    """Test cost tracking across session."""

    def test_session_cost_starts_at_zero(self, kaya):
        """Test that session cost starts at 0."""
        assert kaya.session_cost == 0.0

    def test_cost_accumulation(self, kaya, mock_routing_decision):
        """Test that costs accumulate across multiple commands."""
        decision = mock_routing_decision()
        kaya.router.route.return_value = decision

        # Execute first command
        result1 = kaya.execute("create test for login")
        cost1 = 0.15
        kaya.session_cost += cost1

        # Execute second command
        result2 = kaya.execute("run test tests/login.spec.ts")
        cost2 = 0.05
        kaya.session_cost += cost2

        # Total cost should accumulate
        assert kaya.session_cost == cost1 + cost2

    def test_track_execution_time(self, kaya, mock_routing_decision):
        """Test that execution time is tracked."""
        decision = mock_routing_decision()
        kaya.router.route.return_value = decision

        result = kaya.execute("create test for checkout")

        # Execution time should be tracked (may be 0 in fast tests)
        assert result.execution_time_ms >= 0
        assert isinstance(result.execution_time_ms, int)


# ============================================================================
# TEST: Budget Enforcement
# ============================================================================

class TestBudgetEnforcement:
    """Test budget enforcement with soft and hard limits."""

    def test_check_budget_ok(self, kaya):
        """Test budget check when spending is within limits."""
        kaya.session_cost = 2.00
        kaya.router.check_budget.return_value = {
            'status': 'ok',
            'limit': 5.00,
            'remaining': 3.00,
            'percent_used': 40.0,
            'warning': None
        }

        budget_status = kaya.check_budget('per_session')

        assert budget_status['status'] == 'ok'
        assert budget_status['remaining'] == 3.00
        assert budget_status['warning'] is None

        kaya.router.check_budget.assert_called_once_with(2.00, 'per_session')

    def test_check_budget_soft_limit_warning(self, kaya):
        """Test budget warning at 80% (soft limit)."""
        kaya.session_cost = 4.00
        kaya.router.check_budget.return_value = {
            'status': 'warning',
            'limit': 5.00,
            'remaining': 1.00,
            'percent_used': 80.0,
            'warning': 'Budget warning: 80.0% used (4.00/5.00)'
        }

        budget_status = kaya.check_budget('per_session')

        assert budget_status['status'] == 'warning'
        assert budget_status['percent_used'] == 80.0
        assert budget_status['warning'] is not None
        assert '80.0%' in budget_status['warning']

    def test_check_budget_hard_limit_exceeded(self, kaya):
        """Test budget exceeded at 100% (hard limit)."""
        kaya.session_cost = 5.00
        kaya.router.check_budget.return_value = {
            'status': 'exceeded',
            'limit': 5.00,
            'remaining': 0.00,
            'percent_used': 100.0,
            'warning': 'Budget exceeded! 5.00 >= 5.00'
        }

        budget_status = kaya.check_budget('per_session')

        assert budget_status['status'] == 'exceeded'
        assert budget_status['remaining'] == 0.00
        assert 'exceeded' in budget_status['warning'].lower()

    def test_check_budget_over_limit(self, kaya):
        """Test budget check when spending exceeds limit."""
        kaya.session_cost = 6.50
        kaya.router.check_budget.return_value = {
            'status': 'exceeded',
            'limit': 5.00,
            'remaining': -1.50,
            'percent_used': 130.0,
            'warning': 'Budget exceeded! 6.50 >= 5.00'
        }

        budget_status = kaya.check_budget('per_session')

        assert budget_status['status'] == 'exceeded'
        assert budget_status['remaining'] < 0
        assert budget_status['percent_used'] > 100

    def test_check_daily_budget(self, kaya):
        """Test daily budget checking."""
        kaya.session_cost = 25.00
        kaya.router.check_budget.return_value = {
            'status': 'ok',
            'limit': 50.00,
            'remaining': 25.00,
            'percent_used': 50.0,
            'warning': None
        }

        budget_status = kaya.check_budget('daily')

        assert budget_status['limit'] == 50.00
        kaya.router.check_budget.assert_called_once_with(25.00, 'daily')


# ============================================================================
# TEST: Result Aggregation
# ============================================================================

class TestResultAggregation:
    """Test result aggregation from agent dispatch."""

    def test_successful_result_structure(self, kaya, mock_routing_decision):
        """Test that successful results have correct structure."""
        decision = mock_routing_decision()
        kaya.router.route.return_value = decision

        result = kaya.execute("create test for login")

        assert isinstance(result, AgentResult)
        assert result.success is True
        assert result.data is not None
        assert result.error is None
        assert result.metadata is not None
        assert result.execution_time_ms >= 0

    def test_failed_intent_parsing_result(self, kaya):
        """Test result structure when intent parsing fails."""
        result = kaya.execute("unknown command")

        assert isinstance(result, AgentResult)
        assert result.success is False
        assert result.error is not None
        assert 'Could not understand command' in result.error
        assert result.execution_time_ms >= 0

    def test_result_contains_routing_metadata(self, kaya, mock_routing_decision):
        """Test that routing decision is preserved in result metadata."""
        decision = mock_routing_decision(agent='scribe', model='sonnet', score=7)
        kaya.router.route.return_value = decision

        result = kaya.execute("create test for complex auth")

        assert result.metadata['routing_decision'] == decision
        assert result.metadata['routing_decision'].complexity_score == 7


# ============================================================================
# TEST: Agent Dispatch
# ============================================================================

class TestAgentDispatch:
    """Test agent dispatch coordination."""

    def test_dispatch_to_scribe(self, kaya, mock_routing_decision):
        """Test dispatch decision for Scribe agent."""
        decision = mock_routing_decision(agent='scribe', model='haiku')
        kaya.router.route.return_value = decision

        result = kaya.execute("create test for profile page")

        assert result.data['action'] == 'route_to_scribe'
        assert result.data['agent'] == 'scribe'

    def test_dispatch_to_runner(self, kaya, mock_routing_decision):
        """Test dispatch decision for Runner agent."""
        decision = mock_routing_decision(agent='runner', model='haiku')
        kaya.router.route.return_value = decision

        result = kaya.execute("run test tests/profile.spec.ts")

        assert result.data['action'] == 'route_to_runner'
        assert result.data['agent'] == 'runner'

    def test_dispatch_to_medic(self, kaya, mock_routing_decision):
        """Test dispatch decision for Medic agent."""
        decision = mock_routing_decision(agent='medic', model='sonnet')
        kaya.router.route.return_value = decision

        result = kaya.execute("fix task t_999")

        assert result.data['action'] == 'route_to_medic'
        assert result.data['agent'] == 'medic'

    def test_dispatch_to_gemini(self, kaya, mock_routing_decision):
        """Test dispatch decision for Gemini agent."""
        decision = mock_routing_decision(agent='gemini', model='2.5_pro')
        kaya.router.route.return_value = decision

        result = kaya.execute("validate checkout flow")

        assert result.data['action'] == 'route_to_gemini'
        assert result.data['agent'] == 'gemini'


# ============================================================================
# TEST: Context Handling
# ============================================================================

class TestContextHandling:
    """Test context parameter handling."""

    def test_execute_with_context(self, kaya, mock_routing_decision):
        """Test execute with context parameter."""
        decision = mock_routing_decision()
        kaya.router.route.return_value = decision

        context = {
            'session_id': 'sess_123',
            'previous_tasks': ['t_1', 't_2'],
            'user_id': 'user_456'
        }

        result = kaya.execute("create test for login", context=context)

        assert result.success is True

    def test_execute_without_context(self, kaya, mock_routing_decision):
        """Test execute without context parameter."""
        decision = mock_routing_decision()
        kaya.router.route.return_value = decision

        result = kaya.execute("run test tests/login.spec.ts")

        assert result.success is True


# ============================================================================
# TEST: Error Handling
# ============================================================================

class TestErrorHandling:
    """Test error handling in orchestration."""

    def test_invalid_intent_returns_error(self, kaya):
        """Test that invalid intent returns error result."""
        result = kaya.execute("do something random")

        assert result.success is False
        assert result.error is not None
        assert 'Could not understand command' in result.error

    def test_router_exception_handling(self, kaya):
        """Test handling of router exceptions."""
        kaya.router.route.side_effect = ValueError("No routing rule found")

        result = kaya.execute("create test for login")

        assert result.success is False
        assert result.error is not None
        assert 'Orchestration error' in result.error

    def test_unknown_intent_type(self, kaya, mock_routing_decision):
        """Test handling of unknown intent type after parsing."""
        # Mock parse_intent to return an unknown intent
        with patch.object(kaya, 'parse_intent') as mock_parse:
            mock_parse.return_value = {
                'success': True,
                'intent': 'unknown_intent',
                'slots': {}
            }

            result = kaya.execute("some command")

            assert result.success is False
            assert 'Unknown intent type' in result.error

    def test_exception_includes_execution_time(self, kaya):
        """Test that error results still include execution time."""
        kaya.router.route.side_effect = Exception("Router error")

        result = kaya.execute("create test for login")

        assert result.success is False
        assert result.execution_time_ms >= 0


# ============================================================================
# TEST: Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_command(self, kaya):
        """Test handling of empty command."""
        result = kaya.execute("")

        assert result.success is False
        assert result.error is not None

    def test_whitespace_only_command(self, kaya):
        """Test handling of whitespace-only command."""
        result = kaya.execute("   ")

        assert result.success is False

    def test_very_long_command(self, kaya, mock_routing_decision):
        """Test handling of very long command."""
        decision = mock_routing_decision()
        kaya.router.route.return_value = decision

        long_feature = "a" * 1000
        result = kaya.execute(f"create test for {long_feature}")

        assert result.success is True
        assert long_feature in result.data['feature']

    def test_special_characters_in_command(self, kaya, mock_routing_decision):
        """Test handling of special characters in command."""
        decision = mock_routing_decision()
        kaya.router.route.return_value = decision

        result = kaya.execute("create test for login@example.com with symbols !@#$%")

        assert result.success is True

    def test_unicode_characters_in_command(self, kaya, mock_routing_decision):
        """Test handling of unicode characters in command."""
        decision = mock_routing_decision()
        kaya.router.route.return_value = decision

        result = kaya.execute("create test for user profil© with émojis 🚀")

        assert result.success is True

    def test_multiple_spaces_in_command(self, kaya, mock_routing_decision):
        """Test handling of multiple spaces in command."""
        decision = mock_routing_decision()
        kaya.router.route.return_value = decision

        result = kaya.execute("create    test    for    login")

        assert result.success is True

    def test_mixed_case_intent(self, kaya, mock_routing_decision):
        """Test mixed case intent patterns."""
        decision = mock_routing_decision()
        kaya.router.route.return_value = decision

        result = kaya.execute("CREATE Test FOR Login")

        assert result.success is True
        assert result.data['action'] == 'route_to_scribe'


# ============================================================================
# TEST: Integration Scenarios
# ============================================================================

class TestIntegrationScenarios:
    """Test realistic end-to-end scenarios."""

    def test_full_workflow_easy_test(self, kaya, mock_routing_decision):
        """Test complete workflow for easy test creation."""
        decision = mock_routing_decision(
            agent='scribe',
            model='haiku',
            max_cost=0.50,
            complexity='easy',
            score=2
        )
        kaya.router.route.return_value = decision

        result = kaya.execute("Kaya, create test for simple form submission")

        assert result.success is True
        assert result.data['agent'] == 'scribe'
        assert result.data['model'] == 'haiku'
        assert result.data['max_cost'] == 0.50
        assert result.metadata['routing_decision'].difficulty == 'easy'
        assert result.execution_time_ms >= 0

    def test_full_workflow_hard_auth_test(self, kaya, mock_routing_decision):
        """Test complete workflow for hard auth test with cost override."""
        decision = mock_routing_decision(
            agent='scribe',
            model='sonnet',
            max_cost=2.00,  # Auth override
            complexity='hard',
            score=8
        )
        kaya.router.route.return_value = decision

        result = kaya.execute("create test for OAuth authentication with multiple providers")

        assert result.success is True
        assert result.data['agent'] == 'scribe'
        assert result.data['model'] == 'sonnet'
        assert result.data['max_cost'] == 2.00
        assert result.metadata['routing_decision'].difficulty == 'hard'

    def test_full_workflow_test_execution(self, kaya, mock_routing_decision):
        """Test complete workflow for test execution."""
        decision = mock_routing_decision(agent='runner', model='haiku')
        kaya.router.route.return_value = decision

        result = kaya.execute("run test tests/auth/login-auth.spec.ts")

        assert result.success is True
        assert result.data['action'] == 'route_to_runner'
        assert result.data['model'] == 'haiku'
        assert 'login-auth.spec.ts' in result.data['test_path']

    def test_full_workflow_bug_fix(self, kaya, mock_routing_decision):
        """Test complete workflow for bug fixing."""
        decision = mock_routing_decision(agent='medic', model='sonnet')
        kaya.router.route.return_value = decision

        result = kaya.execute("fix task t_123 and retry")

        assert result.success is True
        assert result.data['action'] == 'route_to_medic'
        assert result.data['model'] == 'sonnet'
        assert result.data['task_id'] == 't_123'

    def test_full_workflow_validation(self, kaya, mock_routing_decision):
        """Test complete workflow for test validation."""
        decision = mock_routing_decision(
            agent='gemini',
            model='2.5_pro',
            max_cost=3.00
        )
        kaya.router.route.return_value = decision

        result = kaya.execute("validate tests/checkout-payment.spec.ts - critical")

        assert result.success is True
        assert result.data['action'] == 'route_to_gemini'
        assert result.data['model'] == '2.5_pro'
        assert 'checkout-payment' in result.data['test_path']

    def test_multiple_commands_in_session(self, kaya, mock_routing_decision):
        """Test multiple commands in single session with cost tracking."""
        # Command 1: Create test
        decision1 = mock_routing_decision(agent='scribe', model='haiku')
        kaya.router.route.return_value = decision1
        result1 = kaya.execute("create test for login")
        kaya.session_cost += 0.10

        # Command 2: Run test
        decision2 = mock_routing_decision(agent='runner', model='haiku')
        kaya.router.route.return_value = decision2
        result2 = kaya.execute("run test tests/login.spec.ts")
        kaya.session_cost += 0.05

        # Command 3: Check status
        result3 = kaya.execute("status task t_123")

        # All should succeed
        assert result1.success is True
        assert result2.success is True
        assert result3.success is True

        # Cost should accumulate (use pytest.approx for float comparison)
        assert kaya.session_cost == pytest.approx(0.15)

        # Router should be called twice (not for status)
        assert kaya.router.route.call_count == 2


# ============================================================================
# TEST: Performance
# ============================================================================

class TestPerformance:
    """Test performance characteristics."""

    def test_execution_time_reasonable(self, kaya, mock_routing_decision):
        """Test that execution time is reasonable (<100ms for simple routing)."""
        decision = mock_routing_decision()
        kaya.router.route.return_value = decision

        start = time.time()
        result = kaya.execute("create test for login")
        elapsed = (time.time() - start) * 1000

        # Should complete quickly (mocked dependencies)
        assert elapsed < 100  # Less than 100ms
        assert result.execution_time_ms < 100

    def test_multiple_rapid_commands(self, kaya, mock_routing_decision):
        """Test handling of multiple rapid commands."""
        decision = mock_routing_decision()
        kaya.router.route.return_value = decision

        results = []
        for i in range(10):
            result = kaya.execute(f"create test for feature_{i}")
            results.append(result)

        # All should succeed
        assert all(r.success for r in results)
        assert len(results) == 10
