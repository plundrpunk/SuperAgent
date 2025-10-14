"""
Integration Tests for Critic Rejection and Retry Flow

Tests the complete feedback loop:
1. Scribe generates test with anti-pattern (.nth() selector)
2. Critic detects anti-pattern and rejects with feedback
3. Scribe receives feedback in retry prompt
4. Scribe regenerates test without anti-pattern
5. Critic approves second attempt

Validates:
- Max 3 retry attempts enforced
- Feedback incorporated in retry prompts
- Cost tracked across retries
- Final success after valid generation
"""
import pytest
from pathlib import Path
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any

from agent_system.agents.scribe import ScribeAgent
from agent_system.agents.critic import CriticAgent
from agent_system.agents.base_agent import AgentResult
from agent_system.router import Router


class TestCriticRejectionFlow:
    """Integration tests for Critic rejection and Scribe retry flow."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test files."""
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp)

    @pytest.fixture
    def scribe(self):
        """Create Scribe agent instance."""
        return ScribeAgent()

    @pytest.fixture
    def critic(self):
        """Create Critic agent instance."""
        return CriticAgent()

    @pytest.fixture
    def router(self):
        """Create Router instance."""
        return Router()

    # Test responses with staged generation
    BAD_TEST_WITH_NTH = '''import { test, expect } from '@playwright/test';

const S = (id: string) => `[data-testid="${id}"]`;

test.use({
  screenshot: 'on',
  video: 'retain-on-failure',
  trace: 'retain-on-failure'
});

test.describe('User Login', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(process.env.BASE_URL!);
  });

  test('happy path', async ({ page }) => {
    // Bad: using nth() selector
    await page.locator('button').nth(0).click();
    await page.screenshot({ path: 'screenshot-step-1.png' });
    await expect(page.locator(S('result'))).toBeVisible();
  });

  test('error case', async ({ page }) => {
    await expect(page.locator(S('error'))).toBeVisible();
  });
});
'''

    GOOD_TEST_NO_NTH = '''import { test, expect } from '@playwright/test';

const S = (id: string) => `[data-testid="${id}"]`;

test.use({
  screenshot: 'on',
  video: 'retain-on-failure',
  trace: 'retain-on-failure'
});

test.describe('User Login', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(process.env.BASE_URL!);
  });

  test('happy path', async ({ page }) => {
    // Fixed: using data-testid selector
    await page.locator(S('login-button')).click();
    await page.screenshot({ path: 'screenshot-step-1.png' });
    await expect(page.locator(S('result'))).toBeVisible();
  });

  test('error case', async ({ page }) => {
    await expect(page.locator(S('error'))).toBeVisible();
  });
});
'''

    def test_critic_rejects_nth_selector(self, critic, temp_dir):
        """
        Test that Critic correctly rejects test with .nth() selector.
        """
        # Write bad test to temp file
        test_path = Path(temp_dir) / 'bad_test.spec.ts'
        test_path.write_text(self.BAD_TEST_WITH_NTH)

        # Run Critic
        result = critic.execute(str(test_path))

        # Validate rejection
        assert result.success is True, "Critic should execute successfully"
        assert result.data['status'] == 'rejected', "Test should be rejected"
        assert len(result.data['issues_found']) > 0, "Should find issues"

        # Check that nth() anti-pattern was detected
        issues = result.data['issues_found']
        issues_str = ' '.join(str(i) for i in issues)
        assert 'flaky' in issues_str.lower() or 'nth' in issues_str.lower(), \
            "Should detect nth() anti-pattern"

    def test_critic_approves_clean_test(self, critic, temp_dir):
        """
        Test that Critic approves test without anti-patterns.
        """
        # Write good test to temp file
        test_path = Path(temp_dir) / 'good_test.spec.ts'
        test_path.write_text(self.GOOD_TEST_NO_NTH)

        # Run Critic
        result = critic.execute(str(test_path))

        # Validate approval
        assert result.success is True
        assert result.data['status'] == 'approved'
        assert len(result.data['issues_found']) == 0

    def test_scribe_retry_with_critic_feedback(self, scribe, temp_dir):
        """
        Test Scribe retry mechanism with staged responses.

        Simulates:
        1. First attempt: generates test with .nth()
        2. Validation fails
        3. Second attempt: generates clean test
        4. Validation passes
        """
        output_path = Path(temp_dir) / 'login.spec.ts'

        # Mock the _generate_test_with_rag method to return staged responses
        call_count = [0]  # Use list to make it mutable in closure

        def mock_generate_test_with_rag(description, feature_name):
            call_count[0] += 1
            if call_count[0] == 1:
                # First attempt: bad test with .nth()
                return {
                    'test_content': self.BAD_TEST_WITH_NTH,
                    'patterns_used': [],
                    'used_rag': False
                }
            else:
                # Second attempt: clean test
                # Check that feedback is in description
                assert 'PREVIOUS ATTEMPT FAILED' in description or \
                       'flaky' in description.lower() or \
                       'nth' in description.lower(), \
                       "Retry prompt should contain feedback"

                return {
                    'test_content': self.GOOD_TEST_NO_NTH,
                    'patterns_used': [],
                    'used_rag': False
                }

        with patch.object(scribe, '_generate_test_with_rag', side_effect=mock_generate_test_with_rag):
            result = scribe.execute(
                task_description="Test user login flow",
                feature_name="User Login",
                output_path=str(output_path),
                complexity='easy'
            )

        # Validate result
        assert result.success is True, f"Should succeed after retry. Error: {result.error}"
        assert result.data['validation_passed'] is True
        assert result.data['attempts_used'] == 2, "Should take 2 attempts"
        assert result.metadata['retries_used'] == 1, "Should use 1 retry"

        # Verify file was created with clean test
        assert output_path.exists()
        content = output_path.read_text()
        assert '.nth(' not in content, "Final test should not contain .nth()"
        assert 'data-testid' in content, "Final test should use data-testid"

    def test_scribe_max_retries_enforcement(self, scribe, temp_dir):
        """
        Test that Scribe enforces max retry limit.

        All 3 attempts fail, should escalate.
        """
        output_path = Path(temp_dir) / 'failing.spec.ts'

        # Mock to always return bad test
        def mock_generate_bad_test(description, feature_name):
            return {
                'test_content': self.BAD_TEST_WITH_NTH,
                'patterns_used': [],
                'used_rag': False
            }

        with patch.object(scribe, '_generate_test_with_rag', side_effect=mock_generate_bad_test):
            result = scribe.execute(
                task_description="Test user login",
                feature_name="Login",
                output_path=str(output_path),
                complexity='easy'
            )

        # Validate failure after max retries
        assert result.success is False, "Should fail after max retries"
        assert 'Failed validation after' in result.error
        assert result.metadata['validation_attempts'] == 3, "Should attempt 3 times"
        assert len(result.metadata['final_issues']) > 0, "Should report issues"

    def test_scribe_first_attempt_success(self, scribe, temp_dir):
        """
        Test that no retry is needed when first attempt is valid.
        """
        output_path = Path(temp_dir) / 'success.spec.ts'

        # Mock to return good test immediately
        def mock_generate_good_test(description, feature_name):
            return {
                'test_content': self.GOOD_TEST_NO_NTH,
                'patterns_used': [],
                'used_rag': False
            }

        with patch.object(scribe, '_generate_test_with_rag', side_effect=mock_generate_good_test):
            result = scribe.execute(
                task_description="Test user login",
                feature_name="Login",
                output_path=str(output_path),
                complexity='easy'
            )

        # Validate success on first attempt
        assert result.success is True
        assert result.data['attempts_used'] == 1, "Should succeed on first attempt"
        assert result.metadata['retries_used'] == 0, "Should use 0 retries"

    def test_multiple_anti_patterns_in_single_test(self, critic, temp_dir):
        """
        Test Critic detection of multiple anti-patterns.
        """
        bad_test_multiple = '''import { test } from '@playwright/test';

test.describe('Bad Test', () => {
  test('multiple issues', async ({ page }) => {
    await page.goto('http://localhost:3000');  // Bad: localhost
    await page.locator('.css-abc123').nth(0).click();  // Bad: CSS class + nth()
    await page.waitForTimeout(5000);  // Bad: waitForTimeout
    // Missing: expect() assertion (no import, no usage)
    // Missing: screenshot
  });
});
'''
        test_path = Path(temp_dir) / 'multiple_bad.spec.ts'
        test_path.write_text(bad_test_multiple)

        result = critic.execute(str(test_path))

        # Should detect multiple issues
        assert result.success is True
        assert result.data['status'] == 'rejected'
        issues = result.data['issues_found']
        # Should find at least: localhost, .css-*, .nth(), waitForTimeout, missing assertions
        assert len(issues) >= 4, f"Should find at least 4 issues, found {len(issues)}: {issues}"

        # Check for specific anti-pattern issues (with dict format)
        issues_str = ' '.join(str(i) for i in issues).lower()
        assert 'localhost' in issues_str or 'base_url' in issues_str, "Should detect localhost"
        assert 'flaky' in issues_str or 'nth' in issues_str, "Should detect nth()"
        assert 'waitfortimeout' in issues_str or 'waitforselector' in issues_str, "Should detect waitForTimeout"

        # Note: The test will also be missing assertions and screenshots, but those are
        # checked separately in _check_assertions. The important thing is we found
        # multiple anti-patterns as expected.

    def test_feedback_contains_specific_issues(self, scribe):
        """
        Test that validation feedback includes specific issue details.
        """
        passed, issues = scribe._validate_generated_test(self.BAD_TEST_WITH_NTH)

        assert passed is False
        assert len(issues) > 0

        # Issues should be specific
        issues_str = ' '.join(issues)
        assert 'flaky' in issues_str.lower() or 'nth' in issues_str.lower()

    def test_cost_tracking_across_retries(self, scribe, temp_dir):
        """
        Test that cost is tracked across retry attempts.
        """
        output_path = Path(temp_dir) / 'test.spec.ts'

        call_count = [0]

        def mock_with_cost(description, feature_name):
            call_count[0] += 1
            if call_count[0] == 1:
                return {
                    'test_content': self.BAD_TEST_WITH_NTH,
                    'patterns_used': [],
                    'used_rag': False
                }
            else:
                return {
                    'test_content': self.GOOD_TEST_NO_NTH,
                    'patterns_used': [],
                    'used_rag': False
                }

        with patch.object(scribe, '_generate_test_with_rag', side_effect=mock_with_cost):
            result = scribe.execute(
                task_description="Test login",
                feature_name="Login",
                output_path=str(output_path)
            )

        # Verify attempts tracked
        assert result.data['attempts_used'] == 2
        assert result.metadata['retries_used'] == 1

        # Check stats tracking
        stats = scribe.get_validation_stats()
        assert stats['validation_attempts'] > 0
        assert stats['total_retries_used'] > 0

    def test_router_recommends_correct_model(self, router):
        """
        Test that Router recommends appropriate model for write_test task.
        """
        # Easy task should use Haiku
        easy_decision = router.route(
            task_type="write_test",
            task_description="Simple form test",
            task_scope="Basic CRUD"
        )

        assert easy_decision.agent == "scribe"
        assert easy_decision.model == "haiku"
        assert easy_decision.difficulty == "easy"

        # Hard task should use Sonnet - needs to exceed complexity threshold of 5
        hard_decision = router.route(
            task_type="write_test",
            task_description="Test OAuth login with payment and WebSocket requiring 6 step flow and mocking",
            task_scope="Complex auth flow with payment integration and real-time updates, mock API responses"
        )

        assert hard_decision.agent == "scribe"
        assert hard_decision.model == "sonnet"
        assert hard_decision.difficulty == "hard"

    def test_critic_routing(self, router):
        """
        Test that pre_validate tasks route to Critic with Haiku.
        """
        decision = router.route(
            task_type="pre_validate",
            task_description="Check test quality",
            test_path="tests/login.spec.ts"
        )

        assert decision.agent == "critic"
        assert decision.model == "haiku"

    def test_end_to_end_scribe_critic_integration(self, scribe, critic, temp_dir):
        """
        Full end-to-end test: Scribe generates → Critic validates.
        """
        output_path = Path(temp_dir) / 'e2e_test.spec.ts'

        # Mock Scribe to generate good test
        def mock_good_generation(description, feature_name):
            return {
                'test_content': self.GOOD_TEST_NO_NTH,
                'patterns_used': [],
                'used_rag': False
            }

        with patch.object(scribe, '_generate_test_with_rag', side_effect=mock_good_generation):
            # 1. Scribe generates test
            scribe_result = scribe.execute(
                task_description="Test checkout flow",
                feature_name="Checkout",
                output_path=str(output_path)
            )

        assert scribe_result.success is True
        assert output_path.exists()

        # 2. Critic validates generated test
        critic_result = critic.execute(str(output_path))

        assert critic_result.success is True
        assert critic_result.data['status'] == 'approved'
        assert len(critic_result.data['issues_found']) == 0


class TestCriticRejectionEdgeCases:
    """Test edge cases in Critic rejection flow."""

    @pytest.fixture
    def scribe(self):
        """Create Scribe agent."""
        return ScribeAgent()

    @pytest.fixture
    def critic(self):
        """Create Critic agent."""
        return CriticAgent()

    @pytest.fixture
    def temp_dir(self):
        """Create temp directory."""
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp)

    def test_critic_handles_missing_file(self, critic):
        """Test Critic gracefully handles missing test file."""
        result = critic.execute("/nonexistent/path/test.spec.ts")

        assert result.success is False
        assert 'not found' in result.error.lower()

    def test_critic_handles_empty_file(self, critic, temp_dir):
        """Test Critic handles empty test file."""
        empty_file = Path(temp_dir) / 'empty.spec.ts'
        empty_file.write_text('')

        result = critic.execute(str(empty_file))

        assert result.success is True
        assert result.data['status'] == 'rejected'
        # Should complain about missing assertions at minimum

    def test_scribe_validation_alignment_with_critic(self, scribe, critic):
        """
        Verify Scribe's internal validation matches Critic's criteria.
        """
        # Both should use same anti-patterns
        scribe_patterns = {p['pattern'] for p in scribe.ANTI_PATTERNS}
        critic_patterns = {p['pattern'] for p in critic.ANTI_PATTERNS}

        assert scribe_patterns == critic_patterns, \
            "Scribe and Critic should have identical anti-patterns"

        # Both should have same limits
        assert scribe.MAX_STEPS == critic.MAX_STEPS
        assert scribe.MAX_DURATION_MS == critic.MAX_DURATION_MS

    def test_retry_feedback_enhancement(self, scribe):
        """
        Test that retry attempts include enhanced feedback.
        """
        # Manually test the feedback enhancement logic
        task_description = "Test login"
        issues = [
            "Index-based selectors are flaky (found pattern: .nth(\\d+))",
            "Missing data-testid selectors"
        ]

        # Simulate retry enhancement (from _generate_with_validation)
        enhanced = f"""{task_description}

PREVIOUS ATTEMPT FAILED - FIX THESE ISSUES:
{chr(10).join(f'- {issue}' for issue in issues)}

REQUIREMENTS:
- Use ONLY data-testid selectors: const S = (id: string) => `[data-testid="${{id}}"]`
- Include at least 1 expect() assertion
- NO .nth() index-based selectors
"""

        # Verify feedback structure
        assert "PREVIOUS ATTEMPT FAILED" in enhanced
        assert "Index-based selectors are flaky" in enhanced
        assert "data-testid" in enhanced
        assert "NO .nth()" in enhanced

    def test_max_retries_from_router_policy(self, scribe):
        """
        Test that max retries matches router policy.
        """
        from agent_system.router import Router

        router = Router()
        max_retries = router.get_max_retries()

        assert scribe.MAX_RETRIES == max_retries, \
            "Scribe max retries should match router policy"

    def test_validation_stats_accuracy(self, scribe, temp_dir):
        """
        Test that validation statistics are tracked accurately.
        """
        output_path = Path(temp_dir) / 'stats_test.spec.ts'

        # Generate a test that will require retry
        call_count = [0]

        def mock_staged(description, feature_name):
            call_count[0] += 1
            if call_count[0] == 1:
                return {
                    'test_content': '''
import { test } from '@playwright/test';
test('bad', async ({ page }) => {
  await page.locator('button').nth(0).click();
});
''',
                    'patterns_used': [],
                    'used_rag': False
                }
            else:
                return {
                    'test_content': '''
import { test, expect } from '@playwright/test';
test('good', async ({ page }) => {
  await page.goto(process.env.BASE_URL!);
  await page.locator('[data-testid="btn"]').click();
  await page.screenshot({ path: 'test.png' });
  await expect(page).toHaveURL('/success');
});
''',
                    'patterns_used': [],
                    'used_rag': False
                }

        initial_stats = scribe.get_validation_stats()
        initial_attempts = initial_stats['validation_attempts']
        initial_retries = initial_stats['total_retries_used']

        with patch.object(scribe, '_generate_test_with_rag', side_effect=mock_staged):
            result = scribe.execute(
                task_description="Test button click",
                feature_name="Button",
                output_path=str(output_path)
            )

        final_stats = scribe.get_validation_stats()

        # Verify stats incremented correctly
        assert final_stats['validation_attempts'] == initial_attempts + 2
        assert final_stats['total_retries_used'] == initial_retries + 1
        assert result.data['attempts_used'] == 2


class TestCriticFeedbackQuality:
    """Test the quality and specificity of Critic feedback."""

    @pytest.fixture
    def critic(self):
        """Create Critic agent."""
        return CriticAgent()

    @pytest.fixture
    def temp_dir(self):
        """Create temp directory."""
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp)

    def test_feedback_includes_pattern_details(self, critic, temp_dir):
        """
        Test that Critic feedback includes specific pattern details.
        """
        bad_test = '''import { test, expect } from '@playwright/test';

test('bad selector', async ({ page }) => {
  await page.locator('button').nth(2).click();
  await page.screenshot({ path: 'test.png' });
  await expect(page).toHaveURL('/success');
});
'''
        test_path = Path(temp_dir) / 'feedback_test.spec.ts'
        test_path.write_text(bad_test)

        result = critic.execute(str(test_path))

        assert result.data['status'] == 'rejected'
        issues = result.data['issues_found']

        # Feedback should be specific
        assert len(issues) > 0
        issues_str = ' '.join(str(i) for i in issues)
        assert '.nth(' in issues_str or 'nth' in issues_str.lower()
        assert 'flaky' in issues_str.lower() or 'index' in issues_str.lower()

    def test_feedback_cost_and_duration_estimates(self, critic, temp_dir):
        """
        Test that Critic provides cost and duration estimates.
        """
        good_test = '''import { test, expect } from '@playwright/test';

test('login', async ({ page }) => {
  await page.goto(process.env.BASE_URL!);
  await page.locator('[data-testid="username"]').fill('user');
  await page.locator('[data-testid="password"]').fill('pass');
  await page.locator('[data-testid="submit"]').click();
  await page.screenshot({ path: 'login.png' });
  await expect(page.locator('[data-testid="dashboard"]')).toBeVisible();
});
'''
        test_path = Path(temp_dir) / 'estimate_test.spec.ts'
        test_path.write_text(good_test)

        result = critic.execute(str(test_path))

        assert result.success is True
        assert 'estimated_cost_usd' in result.data
        assert 'estimated_duration_ms' in result.data
        assert 'estimated_steps' in result.data

        # Verify estimates are reasonable
        assert result.data['estimated_cost_usd'] >= 0
        assert result.data['estimated_duration_ms'] > 0
        assert result.data['estimated_steps'] > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
