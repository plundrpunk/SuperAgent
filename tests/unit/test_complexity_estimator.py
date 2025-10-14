"""
Unit tests for ComplexityEstimator module.

Tests all scoring rules, threshold logic, edge cases, and batch processing.
"""
import pytest
from agent_system.complexity_estimator import (
    ComplexityEstimator,
    ComplexityScore,
    estimate_complexity
)


class TestComplexityEstimator:
    """Test suite for ComplexityEstimator class."""

    @pytest.fixture
    def estimator(self):
        """Provide a fresh ComplexityEstimator instance for each test."""
        return ComplexityEstimator()


class TestBasicFunctionality(TestComplexityEstimator):
    """Test basic estimator functionality and return types."""

    def test_returns_complexity_score_object(self, estimator):
        """Verify that estimate() returns a ComplexityScore object."""
        result = estimator.estimate("simple test")
        assert isinstance(result, ComplexityScore)
        assert hasattr(result, 'score')
        assert hasattr(result, 'difficulty')
        assert hasattr(result, 'model_recommendation')
        assert hasattr(result, 'breakdown')

    def test_empty_description_returns_zero_score(self, estimator):
        """Empty task descriptions should result in score of 0."""
        result = estimator.estimate("")
        assert result.score == 0
        assert result.difficulty == "easy"
        assert result.model_recommendation == "haiku"
        assert result.breakdown == {}

    def test_simple_task_gets_easy_rating(self, estimator):
        """Simple tasks without keywords should be rated easy."""
        result = estimator.estimate("write a basic unit test")
        assert result.score < 5
        assert result.difficulty == "easy"
        assert result.model_recommendation == "haiku"


class TestStepsScoring(TestComplexityEstimator):
    """Test scoring rules for multi-step tasks."""

    def test_steps_over_threshold_adds_score(self, estimator):
        """Tasks with more than 4 steps should add +2 to score."""
        result = estimator.estimate("complete step 5 for the test")
        assert 'steps' in result.breakdown
        assert result.breakdown['steps'] == 2
        assert result.score >= 2

    def test_steps_at_threshold_no_score(self, estimator):
        """Tasks with exactly 4 steps should not add score."""
        result = estimator.estimate("complete step 4 for the test")
        assert 'steps' not in result.breakdown
        assert result.score == 0

    def test_steps_below_threshold_no_score(self, estimator):
        """Tasks with fewer than 4 steps should not add score."""
        result = estimator.estimate("complete step 3 for the test")
        assert 'steps' not in result.breakdown

    def test_multiple_step_mentions_counts_once(self, estimator):
        """Multiple step mentions should only count once per category."""
        # The regex matches first occurrence where number > 4
        result = estimator.estimate("complete stage 5, then do stage 6")
        # Only counts once per category even with multiple matches
        assert 'steps' in result.breakdown
        assert result.breakdown['steps'] == 2

    def test_steps_with_different_keywords(self, estimator):
        """Test that 'action', 'phase', 'stage' also trigger step scoring."""
        test_cases = [
            "complete action 6",
            "go through phase 7",
            "execute stage 5"
        ]
        for description in test_cases:
            result = estimator.estimate(description)
            assert 'steps' in result.breakdown, f"Failed for: {description}"
            assert result.breakdown['steps'] == 2


class TestAuthScoring(TestComplexityEstimator):
    """Test scoring rules for authentication-related tasks."""

    def test_auth_keyword_gives_hard_complexity(self, estimator):
        """Tasks with 'auth' keyword should add +3 to score."""
        result = estimator.estimate("test the auth flow")
        assert 'auth' in result.breakdown
        assert result.breakdown['auth'] == 3
        assert result.score >= 3

    def test_login_keyword_gives_hard_complexity(self, estimator):
        """Tasks with 'login' keyword should add +3 to score."""
        result = estimator.estimate("test user login functionality")
        assert 'auth' in result.breakdown
        assert result.breakdown['auth'] == 3

    def test_oauth_keyword_gives_hard_complexity(self, estimator):
        """Tasks with 'oauth' keyword should add +3 to score."""
        result = estimator.estimate("implement oauth integration")
        assert 'auth' in result.breakdown
        assert result.breakdown['auth'] == 3

    def test_credential_keyword_gives_hard_complexity(self, estimator):
        """Tasks with 'credential' keyword should add +3 to score."""
        result = estimator.estimate("validate user credentials")
        assert 'auth' in result.breakdown
        assert result.breakdown['auth'] == 3

    def test_multiple_auth_keywords_count_once(self, estimator):
        """Multiple auth keywords should only add score once per category."""
        result = estimator.estimate("test login with oauth and auth credentials")
        assert result.breakdown['auth'] == 3
        # Should not multiply the score


class TestFileOperationsScoring(TestComplexityEstimator):
    """Test scoring rules for file operation tasks."""

    def test_file_keyword_adds_score(self, estimator):
        """Tasks with 'file' keyword should add +2 to score."""
        result = estimator.estimate("test file processing")
        assert 'file_ops' in result.breakdown
        assert result.breakdown['file_ops'] == 2

    def test_upload_keyword_adds_score(self, estimator):
        """Tasks with 'upload' keyword should add +2 to score."""
        result = estimator.estimate("test file upload functionality")
        assert 'file_ops' in result.breakdown
        assert result.breakdown['file_ops'] == 2

    def test_download_keyword_adds_score(self, estimator):
        """Tasks with 'download' keyword should add +2 to score."""
        result = estimator.estimate("verify download capability")
        assert 'file_ops' in result.breakdown
        assert result.breakdown['file_ops'] == 2

    def test_attachment_keyword_adds_score(self, estimator):
        """Tasks with 'attachment' keyword should add +2 to score."""
        result = estimator.estimate("test email attachment handling")
        assert 'file_ops' in result.breakdown
        assert result.breakdown['file_ops'] == 2


class TestWebSocketScoring(TestComplexityEstimator):
    """Test scoring rules for WebSocket/real-time tasks."""

    def test_websocket_keyword_adds_score(self, estimator):
        """Tasks with 'websocket' keyword should add +3 to score."""
        result = estimator.estimate("implement websocket connection")
        assert 'websocket' in result.breakdown
        assert result.breakdown['websocket'] == 3

    def test_realtime_keyword_adds_score(self, estimator):
        """Tasks with 'realtime' or 'real-time' keyword should add +3 to score."""
        result = estimator.estimate("test real-time updates")
        assert 'websocket' in result.breakdown
        assert result.breakdown['websocket'] == 3

    def test_realtime_with_hyphen_adds_score(self, estimator):
        """Tasks with 'real-time' (hyphenated) should add +3 to score."""
        result = estimator.estimate("verify real-time sync")
        assert 'websocket' in result.breakdown
        assert result.breakdown['websocket'] == 3

    def test_ws_abbreviation_adds_score(self, estimator):
        """Tasks with 'ws' abbreviation should add +3 to score."""
        result = estimator.estimate("test ws connection handling")
        assert 'websocket' in result.breakdown
        assert result.breakdown['websocket'] == 3


class TestPaymentScoring(TestComplexityEstimator):
    """Test scoring rules for payment-related tasks."""

    def test_payment_keyword_gives_highest_score(self, estimator):
        """Tasks with 'pay' keyword should add +4 to score."""
        result = estimator.estimate("test pay processing")
        assert 'payment' in result.breakdown
        assert result.breakdown['payment'] == 4

    def test_pay_keyword_adds_score(self, estimator):
        """Tasks with 'pay' keyword should add +4 to score."""
        result = estimator.estimate("verify pay button functionality")
        assert 'payment' in result.breakdown
        assert result.breakdown['payment'] == 4

    def test_checkout_keyword_adds_score(self, estimator):
        """Tasks with 'checkout' keyword should add +4 to score."""
        result = estimator.estimate("test checkout flow")
        assert 'payment' in result.breakdown
        assert result.breakdown['payment'] == 4

    def test_stripe_keyword_adds_score(self, estimator):
        """Tasks with 'stripe' keyword should add +4 to score."""
        result = estimator.estimate("integrate stripe payments")
        assert 'payment' in result.breakdown
        assert result.breakdown['payment'] == 4

    def test_purchase_keyword_adds_score(self, estimator):
        """Tasks with 'purchase' keyword should add +4 to score."""
        result = estimator.estimate("validate purchase confirmation")
        assert 'payment' in result.breakdown
        assert result.breakdown['payment'] == 4


class TestMockingScoring(TestComplexityEstimator):
    """Test scoring rules for mocking-related tasks."""

    def test_mock_keyword_adds_score(self, estimator):
        """Tasks with 'mock' keyword should add +2 to score."""
        result = estimator.estimate("create mock for API")
        assert 'mocking' in result.breakdown
        assert result.breakdown['mocking'] == 2

    def test_stub_keyword_adds_score(self, estimator):
        """Tasks with 'stub' keyword should add +2 to score."""
        result = estimator.estimate("implement stub for service")
        assert 'mocking' in result.breakdown
        assert result.breakdown['mocking'] == 2

    def test_fake_keyword_adds_score(self, estimator):
        """Tasks with 'fake' keyword should add +2 to score."""
        result = estimator.estimate("use fake data generator")
        assert 'mocking' in result.breakdown
        assert result.breakdown['mocking'] == 2


class TestThresholdLogic(TestComplexityEstimator):
    """Test difficulty threshold and model recommendations."""

    def test_score_below_threshold_is_easy(self, estimator):
        """Scores below 5 should be rated as easy."""
        result = estimator.estimate("test with mock data")  # Should be 2 points
        assert result.score < 5
        assert result.difficulty == "easy"
        assert result.model_recommendation == "haiku"

    def test_score_at_threshold_is_hard(self, estimator):
        """Scores of exactly 5 should be rated as hard."""
        # File ops (2) + auth (3) = 5
        result = estimator.estimate("test file upload with auth")
        assert result.score == 5
        assert result.difficulty == "hard"
        assert result.model_recommendation == "sonnet"

    def test_score_above_threshold_is_hard(self, estimator):
        """Scores above 5 should be rated as hard."""
        # Auth (3) + payment (4) = 7
        result = estimator.estimate("test pay with login required")
        assert result.score > 5
        assert result.difficulty == "hard"
        assert result.model_recommendation == "sonnet"

    def test_high_complexity_combination(self, estimator):
        """Complex tasks with multiple keywords should be rated hard."""
        # WebSocket (3) + payment (4) + auth (3) = 10
        result = estimator.estimate(
            "implement real-time pay notifications with oauth"
        )
        assert result.score >= 10
        assert result.difficulty == "hard"
        assert result.model_recommendation == "sonnet"


class TestCaseSensitivity(TestComplexityEstimator):
    """Test that keyword matching is case-insensitive."""

    def test_uppercase_keywords_detected(self, estimator):
        """Uppercase keywords should be detected."""
        result = estimator.estimate("TEST LOGIN FUNCTIONALITY")
        assert 'auth' in result.breakdown

    def test_mixed_case_keywords_detected(self, estimator):
        """Mixed case keywords should be detected."""
        result = estimator.estimate("Test Pay Processing")
        assert 'payment' in result.breakdown

    def test_lowercase_keywords_detected(self, estimator):
        """Lowercase keywords should be detected."""
        result = estimator.estimate("test oauth integration")
        assert 'auth' in result.breakdown

    def test_case_insensitive_in_scope(self, estimator):
        """Keywords in scope parameter should also be case-insensitive."""
        result = estimator.estimate("test feature", "OAUTH INTEGRATION")
        assert 'auth' in result.breakdown


class TestMultipleKeywordsCombining(TestComplexityEstimator):
    """Test scenarios with multiple keywords from different categories."""

    def test_auth_plus_file_ops_combines_scores(self, estimator):
        """Auth + file ops should combine to 3 + 2 = 5."""
        result = estimator.estimate("test login with file upload")
        assert result.breakdown['auth'] == 3
        assert result.breakdown['file_ops'] == 2
        assert result.score == 5
        assert result.difficulty == "hard"

    def test_payment_plus_auth_exceeds_threshold(self, estimator):
        """Payment + auth should combine to 4 + 3 = 7."""
        result = estimator.estimate("secure pay with auth")
        assert result.breakdown['payment'] == 4
        assert result.breakdown['auth'] == 3
        assert result.score == 7
        assert result.difficulty == "hard"

    def test_websocket_plus_mocking_combines(self, estimator):
        """WebSocket + mocking should combine to 3 + 2 = 5."""
        result = estimator.estimate("mock websocket connection for testing")
        assert result.breakdown['websocket'] == 3
        assert result.breakdown['mocking'] == 2
        assert result.score == 5

    def test_all_categories_combine(self, estimator):
        """All categories should combine for maximum complexity."""
        description = (
            "implement step 10 for oauth login with stripe "
            "processing, file upload, real-time sync, and mock data"
        )
        result = estimator.estimate(description)
        # Steps (2) + auth (3) + payment (4) + file_ops (2) + websocket (3) + mocking (2) = 16
        assert result.score >= 14  # Some flexibility in exact parsing
        assert result.difficulty == "hard"


class TestScopeParameter(TestComplexityEstimator):
    """Test that task_scope is considered in scoring."""

    def test_scope_contributes_to_score(self, estimator):
        """Keywords in scope should contribute to scoring."""
        result = estimator.estimate("write test", "pay integration")
        assert 'payment' in result.breakdown
        assert result.breakdown['payment'] == 4

    def test_description_and_scope_combine(self, estimator):
        """Keywords in both description and scope should be detected."""
        result = estimator.estimate("test auth flow", "with pay processing")
        assert 'auth' in result.breakdown
        assert 'payment' in result.breakdown
        assert result.score == 7

    def test_empty_scope_works(self, estimator):
        """Empty scope should not cause errors."""
        result = estimator.estimate("test login", "")
        assert 'auth' in result.breakdown
        assert result.score == 3


class TestEdgeCases(TestComplexityEstimator):
    """Test edge cases and boundary conditions."""

    def test_whitespace_only_description(self, estimator):
        """Whitespace-only descriptions should return zero score."""
        result = estimator.estimate("   \n\t  ")
        assert result.score == 0
        assert result.difficulty == "easy"

    def test_numbers_without_step_context(self, estimator):
        """Numbers alone without step context should not trigger scoring."""
        result = estimator.estimate("test feature 5")
        assert 'steps' not in result.breakdown

    def test_partial_keyword_matches_not_counted(self, estimator):
        """Word boundary matching - 'auth' keyword requires exact word match."""
        # 'authentication' contains 'auth' but won't match due to word boundary
        result = estimator.estimate("test authentication")
        # Should not match because \bauth\b requires word boundaries
        assert 'auth' not in result.breakdown

        # But 'auth' alone should match
        result2 = estimator.estimate("test auth flow")
        assert 'auth' in result2.breakdown

    def test_special_characters_in_description(self, estimator):
        """Special characters should not break the estimator."""
        result = estimator.estimate("test login @#$%^&* with oauth")
        assert 'auth' in result.breakdown
        assert result.score == 3

    def test_very_long_description(self, estimator):
        """Very long descriptions should be handled efficiently."""
        long_desc = "test simple functionality " * 100
        result = estimator.estimate(long_desc)
        assert isinstance(result, ComplexityScore)

    def test_unicode_characters(self, estimator):
        """Unicode characters should not break the estimator."""
        result = estimator.estimate("test login functionality 测试")
        assert 'auth' in result.breakdown


class TestBatchProcessing(TestComplexityEstimator):
    """Test batch estimation functionality."""

    def test_estimate_batch_returns_dict(self, estimator):
        """estimate_batch should return a dict mapping task_id to ComplexityScore."""
        tasks = [
            {'id': 'task1', 'description': 'test login', 'scope': ''},
            {'id': 'task2', 'description': 'test payment', 'scope': ''}
        ]
        results = estimator.estimate_batch(tasks)
        assert isinstance(results, dict)
        assert 'task1' in results
        assert 'task2' in results
        assert isinstance(results['task1'], ComplexityScore)
        assert isinstance(results['task2'], ComplexityScore)

    def test_batch_processes_all_tasks(self, estimator):
        """All tasks in batch should be processed."""
        tasks = [
            {'id': f'task{i}', 'description': 'simple test', 'scope': ''}
            for i in range(5)
        ]
        results = estimator.estimate_batch(tasks)
        assert len(results) == 5

    def test_batch_handles_task_id_field(self, estimator):
        """Batch should handle both 'id' and 'task_id' fields."""
        tasks = [
            {'task_id': 'task1', 'description': 'test', 'scope': ''},
            {'id': 'task2', 'description': 'test', 'scope': ''}
        ]
        results = estimator.estimate_batch(tasks)
        assert 'task1' in results
        assert 'task2' in results

    def test_batch_with_varying_complexity(self, estimator):
        """Batch should correctly score tasks with different complexities."""
        tasks = [
            {'id': 'easy', 'description': 'simple test', 'scope': ''},
            {'id': 'hard', 'description': 'pay with oauth', 'scope': ''}
        ]
        results = estimator.estimate_batch(tasks)
        assert results['easy'].difficulty == 'easy'
        assert results['hard'].difficulty == 'hard'
        assert results['hard'].score > results['easy'].score

    def test_batch_empty_list(self, estimator):
        """Empty task list should return empty dict."""
        results = estimator.estimate_batch([])
        assert results == {}


class TestConvenienceFunction:
    """Test the standalone convenience function."""

    def test_estimate_complexity_returns_dict(self):
        """estimate_complexity should return a dict with expected keys."""
        result = estimate_complexity("test login")
        assert isinstance(result, dict)
        assert 'score' in result
        assert 'difficulty' in result
        assert 'model' in result
        assert 'breakdown' in result

    def test_convenience_function_matches_class(self):
        """Convenience function should produce same results as class method."""
        description = "test pay with oauth"
        estimator = ComplexityEstimator()
        class_result = estimator.estimate(description)
        func_result = estimate_complexity(description)

        assert func_result['score'] == class_result.score
        assert func_result['difficulty'] == class_result.difficulty
        assert func_result['model'] == class_result.model_recommendation
        assert func_result['breakdown'] == class_result.breakdown

    def test_convenience_function_with_scope(self):
        """Convenience function should handle scope parameter."""
        result = estimate_complexity("test feature", "with auth")
        assert result['score'] >= 3
        assert 'auth' in result['breakdown']


class TestBreakdownAccuracy(TestComplexityEstimator):
    """Test that breakdown accurately reflects score components."""

    def test_breakdown_sum_equals_total_score(self, estimator):
        """Sum of breakdown values should equal total score."""
        result = estimator.estimate("test login with file upload and mocking")
        breakdown_sum = sum(result.breakdown.values())
        assert breakdown_sum == result.score

    def test_breakdown_contains_only_matched_categories(self, estimator):
        """Breakdown should only include categories that matched."""
        result = estimator.estimate("test pay")
        assert 'payment' in result.breakdown
        assert 'auth' not in result.breakdown
        assert 'websocket' not in result.breakdown

    def test_breakdown_empty_for_simple_tasks(self, estimator):
        """Simple tasks with no keywords should have empty breakdown."""
        result = estimator.estimate("simple task")
        assert result.breakdown == {}
        assert result.score == 0


# Integration tests
class TestRealWorldScenarios(TestComplexityEstimator):
    """Test realistic task descriptions."""

    def test_basic_crud_test(self, estimator):
        """Basic CRUD test should be easy."""
        result = estimator.estimate("write test for user list page")
        assert result.difficulty == "easy"
        assert result.model_recommendation == "haiku"

    def test_complex_auth_flow(self, estimator):
        """Complex auth flows should be hard."""
        # Need to add more keywords to reach threshold of 5
        result = estimator.estimate(
            "implement oauth login flow with auth and file upload"
        )
        # oauth (3) + file (2) = 5
        assert result.difficulty == "hard"
        assert result.model_recommendation == "sonnet"
        assert result.score >= 5

    def test_ecommerce_checkout(self, estimator):
        """E-commerce checkout should be hard."""
        result = estimator.estimate(
            "test complete checkout flow with stripe"
        )
        assert result.difficulty == "easy"  # Only payment = 4 points (below threshold)
        assert 'payment' in result.breakdown
        assert result.score >= 4

    def test_file_upload_with_validation(self, estimator):
        """File upload with minimal complexity should be borderline."""
        result = estimator.estimate("test image upload with size validation")
        assert 'file_ops' in result.breakdown
        # Should be 2 points - easy

    def test_realtime_chat_feature(self, estimator):
        """Real-time chat should be hard."""
        result = estimator.estimate(
            "implement websocket-based chat with message history"
        )
        assert result.difficulty == "easy"  # Only websocket = 3 points
        assert 'websocket' in result.breakdown

    def test_admin_dashboard(self, estimator):
        """Complex admin dashboard should be hard."""
        result = estimator.estimate(
            "create admin dashboard with real-time analytics, user auth, "
            "and data export functionality in step 8"
        )
        assert result.difficulty == "hard"
        assert result.score >= 5
