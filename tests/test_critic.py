"""
Unit tests for Critic Agent
Tests the pre-validation quality gate for test approval/rejection.
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from agent_system.agents.critic import CriticAgent
from agent_system.agents.base_agent import AgentResult


@pytest.fixture
def critic_agent():
    """Create CriticAgent instance."""
    return CriticAgent()


@pytest.fixture
def clean_test_content():
    """Sample clean test with no issues."""
    return """import { test, expect } from '@playwright/test';

const S = (id: string) => `[data-testid="\${id}"]`;

test.use({
  screenshot: 'on',
  video: 'retain-on-failure',
  trace: 'retain-on-failure'
});

test.describe('Login Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(process.env.BASE_URL!);
  });

  test('happy path - user logs in successfully', async ({ page }) => {
    await page.click(S('login-button'));
    await page.fill(S('email-input'), 'user@example.com');
    await page.fill(S('password-input'), 'secret123');
    await page.click(S('submit-button'));

    await page.waitForSelector(S('dashboard'));
    await page.screenshot({ path: 'login-success.png' });

    expect(await page.textContent(S('welcome-message'))).toContain('Welcome');
    expect(page.url()).toContain('/dashboard');
  });
});
"""


@pytest.fixture
def test_with_nth_selector():
    """Test with .nth() anti-pattern."""
    return """import { test, expect } from '@playwright/test';

test('flaky test with nth', async ({ page }) => {
  await page.goto('http://localhost:3000');
  await page.locator('.item').nth(2).click();
  expect(await page.title()).toBe('Item 3');
});
"""


@pytest.fixture
def test_with_css_class():
    """Test with generated CSS class anti-pattern."""
    return """import { test, expect } from '@playwright/test';

test('test with generated css', async ({ page }) => {
  await page.goto(process.env.BASE_URL!);
  await page.click('.css-1a2b3c4');
  expect(await page.title()).toBe('Dashboard');
});
"""


@pytest.fixture
def test_with_wait_timeout():
    """Test with waitForTimeout anti-pattern."""
    return """import { test, expect } from '@playwright/test';

test('test with timeout', async ({ page }) => {
  await page.goto(process.env.BASE_URL!);
  await page.click('[data-testid="submit"]');
  await page.waitForTimeout(5000);
  expect(await page.isVisible('[data-testid="success"]')).toBe(true);
});
"""


@pytest.fixture
def test_with_no_assertions():
    """Test with no assertions."""
    return """import { test, expect } from '@playwright/test';

test('test without assertions', async ({ page }) => {
  await page.goto(process.env.BASE_URL!);
  await page.click('[data-testid="button"]');
  await page.fill('[data-testid="input"]', 'text');
});
"""


@pytest.fixture
def test_with_hard_coded_credentials():
    """Test with hard-coded credentials."""
    return """import { test, expect } from '@playwright/test';

test('test with credentials', async ({ page }) => {
  const HARD_CODED_CREDENTIAL = 'super-secret-password';
  await page.goto(process.env.BASE_URL!);
  await page.fill('[data-testid="password"]', HARD_CODED_CREDENTIAL);
  expect(await page.isVisible('[data-testid="dashboard"]')).toBe(true);
});
"""


@pytest.fixture
def test_with_localhost():
    """Test with localhost URL."""
    return """import { test, expect } from '@playwright/test';

test('test with localhost', async ({ page }) => {
  await page.goto('http://localhost:3000/login');
  await page.click('[data-testid="submit"]');
  expect(page.url()).toBe('http://127.0.0.1:3000/dashboard');
});
"""


@pytest.fixture
def test_too_many_steps():
    """Test with too many steps (>10)."""
    return """import { test, expect } from '@playwright/test';

test('test with many steps', async ({ page }) => {
  await page.goto(process.env.BASE_URL!);
  await page.click('[data-testid="step1"]');
  await page.fill('[data-testid="input1"]', 'value1');
  await page.click('[data-testid="step2"]');
  await page.fill('[data-testid="input2"]', 'value2');
  await page.click('[data-testid="step3"]');
  await page.waitForSelector('[data-testid="result1"]');
  await page.screenshot({ path: 'step3.png' });
  await page.click('[data-testid="step4"]');
  await page.fill('[data-testid="input3"]', 'value3');
  await page.click('[data-testid="step5"]');
  await page.waitForSelector('[data-testid="result2"]');
  await page.screenshot({ path: 'step5.png' });
  expect(await page.isVisible('[data-testid="final"]')).toBe(true);
});
"""


class TestCriticInitialization:
    """Test Critic agent initialization."""

    def test_initialization(self, critic_agent):
        """Test agent initializes correctly."""
        assert critic_agent.name == 'critic'
        assert len(critic_agent.ANTI_PATTERNS) == 5
        assert critic_agent.MAX_STEPS == 10
        assert critic_agent.MAX_DURATION_MS == 60000

    def test_anti_patterns_loaded(self, critic_agent):
        """Test anti-patterns are properly defined."""
        patterns = [ap['pattern'] for ap in critic_agent.ANTI_PATTERNS]

        assert r'\.nth\(\d+\)' in patterns
        assert r'\.css-[a-z0-9]+' in patterns
        assert r'waitForTimeout' in patterns
        assert r'hard[_-]?coded.*credential' in patterns
        assert r'localhost|127\.0\.0\.1' in patterns


class TestCriticApproval:
    """Test approval of clean tests."""

    def test_approve_clean_test(self, critic_agent, tmp_path, clean_test_content):
        """Test that clean tests are approved."""
        test_file = tmp_path / "clean_test.spec.ts"
        test_file.write_text(clean_test_content)

        result = critic_agent.execute(str(test_file))

        assert result.success is True
        assert result.data['status'] == 'approved'
        assert len(result.data['issues_found']) == 0
        assert result.data['estimated_cost_usd'] > 0
        assert result.data['estimated_duration_ms'] > 0
        assert result.data['estimated_steps'] > 0
        assert result.metadata['assertion_count'] >= 1
        assert result.execution_time_ms >= 0  # Can be 0 for very fast operations

    def test_approval_includes_cost_estimate(self, critic_agent, tmp_path, clean_test_content):
        """Test that approved tests include cost estimates."""
        test_file = tmp_path / "clean_test.spec.ts"
        test_file.write_text(clean_test_content)

        result = critic_agent.execute(str(test_file))

        assert result.data['estimated_cost_usd'] > 0
        assert result.data['estimated_duration_ms'] > 0
        assert result.data['estimated_steps'] > 0

    def test_approval_counts_assertions(self, critic_agent, tmp_path, clean_test_content):
        """Test that assertion count is tracked."""
        test_file = tmp_path / "clean_test.spec.ts"
        test_file.write_text(clean_test_content)

        result = critic_agent.execute(str(test_file))

        # clean_test_content has 2 expect() calls
        assert result.metadata['assertion_count'] == 2


class TestCriticRejectionAntiPatterns:
    """Test rejection for various anti-patterns."""

    def test_reject_nth_selector(self, critic_agent, tmp_path, test_with_nth_selector):
        """Test rejection of .nth() index selectors."""
        test_file = tmp_path / "flaky_test.spec.ts"
        test_file.write_text(test_with_nth_selector)

        result = critic_agent.execute(str(test_file))

        assert result.success is True
        assert result.data['status'] == 'rejected'
        assert len(result.data['issues_found']) > 0
        assert any('Index-based selectors' in issue.get('reason', '') for issue in result.data['issues_found'])
        assert result.metadata['anti_patterns_found'] >= 1

    def test_reject_css_generated_class(self, critic_agent, tmp_path, test_with_css_class):
        """Test rejection of generated CSS classes."""
        test_file = tmp_path / "css_test.spec.ts"
        test_file.write_text(test_with_css_class)

        result = critic_agent.execute(str(test_file))

        assert result.success is True
        assert result.data['status'] == 'rejected'
        assert any('Generated CSS classes' in issue.get('reason', '') for issue in result.data['issues_found'])
        assert result.metadata['anti_patterns_found'] >= 1

    def test_reject_wait_for_timeout(self, critic_agent, tmp_path, test_with_wait_timeout):
        """Test rejection of waitForTimeout usage."""
        test_file = tmp_path / "timeout_test.spec.ts"
        test_file.write_text(test_with_wait_timeout)

        result = critic_agent.execute(str(test_file))

        assert result.success is True
        assert result.data['status'] == 'rejected'
        assert any('waitForSelector' in issue.get('reason', '') for issue in result.data['issues_found'])
        assert result.metadata['anti_patterns_found'] >= 1

    def test_reject_missing_assertions(self, critic_agent, tmp_path, test_with_no_assertions):
        """Test rejection of tests without assertions."""
        test_file = tmp_path / "no_assert_test.spec.ts"
        test_file.write_text(test_with_no_assertions)

        result = critic_agent.execute(str(test_file))

        assert result.success is True
        assert result.data['status'] == 'rejected'
        # Check for missing_assertions issue type
        assert any(issue.get('type') == 'missing_assertions' for issue in result.data['issues_found'])
        assert result.metadata['assertion_count'] == 0

    def test_reject_hard_coded_credentials(self, critic_agent, tmp_path, test_with_hard_coded_credentials):
        """Test rejection of hard-coded credentials."""
        test_file = tmp_path / "credentials_test.spec.ts"
        test_file.write_text(test_with_hard_coded_credentials)

        result = critic_agent.execute(str(test_file))

        assert result.success is True
        assert result.data['status'] == 'rejected'
        assert any('environment variables' in issue.get('reason', '').lower() for issue in result.data['issues_found'])
        assert result.metadata['anti_patterns_found'] >= 1

    def test_reject_localhost_url(self, critic_agent, tmp_path, test_with_localhost):
        """Test rejection of localhost/127.0.0.1 URLs."""
        test_file = tmp_path / "localhost_test.spec.ts"
        test_file.write_text(test_with_localhost)

        result = critic_agent.execute(str(test_file))

        assert result.success is True
        assert result.data['status'] == 'rejected'
        assert any('BASE_URL' in issue.get('reason', '') for issue in result.data['issues_found'])
        # Should detect both localhost and 127.0.0.1
        assert result.metadata['anti_patterns_found'] >= 1

    def test_reject_multiple_anti_patterns(self, critic_agent, tmp_path):
        """Test rejection when multiple anti-patterns are present."""
        test_content = """import { test, expect } from '@playwright/test';

test('multiple issues', async ({ page }) => {
  await page.goto('http://localhost:3000');
  await page.locator('.item').nth(0).click();
  await page.waitForTimeout(2000);
  await page.click('.css-abc123');
});
"""
        test_file = tmp_path / "multi_issue_test.spec.ts"
        test_file.write_text(test_content)

        result = critic_agent.execute(str(test_file))

        assert result.success is True
        assert result.data['status'] == 'rejected'
        # Should detect: localhost, nth(), waitForTimeout, css class, missing assertions
        assert len(result.data['issues_found']) >= 4
        assert result.metadata['anti_patterns_found'] >= 3


class TestCriticComplexityEstimation:
    """Test complexity and cost estimation."""

    def test_estimate_cost_accuracy(self, critic_agent, clean_test_content):
        """Test cost estimation counts actions correctly."""
        cost_estimate = critic_agent._estimate_cost(clean_test_content)

        # clean_test_content has: 1 goto, 3 clicks, 2 fills, 1 waitForSelector, 1 screenshot
        # Total: 7 actions (waitForSelector matches waitFor pattern)
        assert cost_estimate['steps'] == 7
        assert cost_estimate['cost_usd'] == (7 / 10) * 0.01

    def test_estimate_duration_accuracy(self, critic_agent, clean_test_content):
        """Test duration estimation is 2s per step."""
        duration = critic_agent._estimate_duration(clean_test_content)

        # 7 steps * 2000ms = 14000ms
        assert duration == 14000

    def test_reject_too_many_steps(self, critic_agent, tmp_path, test_too_many_steps):
        """Test rejection when steps exceed MAX_STEPS."""
        test_file = tmp_path / "long_test.spec.ts"
        test_file.write_text(test_too_many_steps)

        result = critic_agent.execute(str(test_file))

        assert result.success is True
        assert result.data['status'] == 'rejected'
        assert result.data['estimated_steps'] > critic_agent.MAX_STEPS
        assert any('steps' in issue.get('reason', '').lower() for issue in result.data['issues_found'])

    def test_reject_excessive_duration(self, critic_agent, tmp_path):
        """Test rejection when estimated duration exceeds limit."""
        # Create test with >30 steps to exceed 60000ms limit (30 * 2000 = 60000)
        actions = []
        for i in range(32):
            actions.append(f"  await page.click('[data-testid=\"button{i}\"]');")

        test_content = f"""import {{ test, expect }} from '@playwright/test';

test('test with excessive duration', async ({{ page }}) => {{
  await page.goto(process.env.BASE_URL!);
{chr(10).join(actions)}
  expect(page.url()).toContain('/dashboard');
}});
"""
        test_file = tmp_path / "long_duration_test.spec.ts"
        test_file.write_text(test_content)

        result = critic_agent.execute(str(test_file))

        assert result.success is True
        assert result.data['status'] == 'rejected'
        # Should have both excessive_steps and excessive_duration
        assert any(issue.get('type') == 'excessive_duration' for issue in result.data['issues_found'])

    def test_cost_estimate_zero_for_empty_test(self, critic_agent):
        """Test cost estimate for test with no actions."""
        empty_test = """import { test, expect } from '@playwright/test';

test('empty test', async ({ page }) => {
  // No actions
});
"""
        cost_estimate = critic_agent._estimate_cost(empty_test)

        assert cost_estimate['steps'] == 0
        assert cost_estimate['cost_usd'] == 0.0


class TestCriticAssertionCounting:
    """Test assertion counting functionality."""

    def test_count_assertions_single(self, critic_agent):
        """Test counting single assertion."""
        code = "expect(page.url()).toBe('/dashboard');"
        count = critic_agent._count_assertions(code)
        assert count == 1

    def test_count_assertions_multiple(self, critic_agent):
        """Test counting multiple assertions."""
        code = """
        expect(page.url()).toBe('/dashboard');
        expect(await page.title()).toBe('Dashboard');
        expect(await page.isVisible('[data-testid="menu"]')).toBe(true);
        """
        count = critic_agent._count_assertions(code)
        assert count == 3

    def test_count_assertions_none(self, critic_agent):
        """Test counting when no assertions present."""
        code = """
        await page.goto('/login');
        await page.click('[data-testid="submit"]');
        """
        count = critic_agent._count_assertions(code)
        assert count == 0

    def test_count_assertions_multiline(self, critic_agent):
        """Test counting assertions with multiline formatting."""
        code = """
        expect(
            await page.textContent('[data-testid="title"]')
        ).toBe('Welcome');
        """
        count = critic_agent._count_assertions(code)
        assert count == 1


class TestCriticFeedbackGeneration:
    """Test detailed feedback generation."""

    def test_feedback_includes_all_issues(self, critic_agent, tmp_path):
        """Test that feedback includes all detected issues."""
        test_content = """import { test, expect } from '@playwright/test';

test('bad test', async ({ page }) => {
  await page.goto('http://localhost:3000');
  await page.locator('.item').nth(0).click();
  await page.waitForTimeout(2000);
});
"""
        test_file = tmp_path / "bad_test.spec.ts"
        test_file.write_text(test_content)

        result = critic_agent.execute(str(test_file))

        issues = result.data['issues_found']

        # Should have issues for: localhost, nth(), waitForTimeout, missing assertions
        assert len(issues) >= 4
        # Check for issues by examining their content
        issue_reasons = ' '.join([issue.get('reason', '') + ' ' + issue.get('matched', '') for issue in issues]).lower()
        assert 'localhost' in issue_reasons or '127.0.0.1' in issue_reasons
        assert 'nth' in issue_reasons or 'index' in issue_reasons
        assert 'timeout' in issue_reasons or 'waitselector' in issue_reasons
        assert 'assertion' in issue_reasons or 'expect' in issue_reasons

    def test_feedback_includes_pattern_details(self, critic_agent, tmp_path, test_with_nth_selector):
        """Test that feedback includes pattern details."""
        test_file = tmp_path / "test.spec.ts"
        test_file.write_text(test_with_nth_selector)

        result = critic_agent.execute(str(test_file))

        issues = result.data['issues_found']

        # Should include the pattern that was detected
        assert any('pattern' in issue for issue in issues)

    def test_approved_feedback_is_empty(self, critic_agent, tmp_path, clean_test_content):
        """Test that approved tests have no issues."""
        test_file = tmp_path / "clean_test.spec.ts"
        test_file.write_text(clean_test_content)

        result = critic_agent.execute(str(test_file))

        assert result.data['issues_found'] == []


class TestCriticErrorHandling:
    """Test error handling."""

    def test_file_not_found(self, critic_agent):
        """Test handling of non-existent file."""
        result = critic_agent.execute('/nonexistent/test.spec.ts')

        assert result.success is False
        assert 'not found' in result.error.lower()
        assert result.execution_time_ms >= 0  # Can be 0 for very fast operations

    def test_invalid_file_path(self, critic_agent):
        """Test handling of invalid file path."""
        result = critic_agent.execute('')

        assert result.success is False
        assert result.error is not None

    def test_execution_time_tracking(self, critic_agent, tmp_path, clean_test_content):
        """Test that execution time is tracked."""
        test_file = tmp_path / "test.spec.ts"
        test_file.write_text(clean_test_content)

        result = critic_agent.execute(str(test_file))

        assert result.execution_time_ms >= 0  # Can be 0 for very fast operations
        assert isinstance(result.execution_time_ms, int)


class TestCriticIntegrationWithConfig:
    """Test integration with critic.yaml config."""

    def test_config_loaded(self, critic_agent):
        """Test that config is loaded from YAML."""
        # Config should be loaded from .claude/agents/critic.yaml
        assert critic_agent.config is not None

    def test_config_contracts_match_code(self, critic_agent):
        """Test that code anti-patterns match config contracts."""
        if critic_agent.config:
            # If config is loaded, verify patterns match
            config_contracts = critic_agent.config.get('contracts', {})

            # Should have rejection criteria defined
            if 'rejection_criteria' in config_contracts:
                assert 'selectors' in config_contracts['rejection_criteria'] or \
                       'anti_patterns' in config_contracts['rejection_criteria'] or \
                       'missing_assertions' in config_contracts['rejection_criteria']


class TestCriticStatistics:
    """Test agent statistics tracking."""

    def test_execution_count_increments(self, critic_agent, tmp_path, clean_test_content):
        """Test that execution count is tracked."""
        test_file = tmp_path / "test.spec.ts"
        test_file.write_text(clean_test_content)

        initial_count = critic_agent.execution_count

        critic_agent.execute(str(test_file))

        assert critic_agent.execution_count == initial_count + 1

    def test_get_stats(self, critic_agent, tmp_path, clean_test_content):
        """Test getting agent statistics."""
        test_file = tmp_path / "test.spec.ts"
        test_file.write_text(clean_test_content)

        critic_agent.execute(str(test_file))

        stats = critic_agent.get_stats()

        assert stats['agent'] == 'critic'
        assert stats['execution_count'] > 0
        assert 'total_cost_usd' in stats
        assert 'avg_cost_usd' in stats


class TestCriticEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_exactly_max_steps(self, critic_agent, tmp_path):
        """Test with exactly MAX_STEPS actions."""
        # Create test with exactly 10 steps
        actions = []
        for i in range(10):
            actions.append(f"  await page.click('[data-testid=\"button{i}\"]');")

        test_content = f"""import {{ test, expect }} from '@playwright/test';

test('exactly 10 steps', async ({{ page }}) => {{
  await page.goto(process.env.BASE_URL!);
{chr(10).join(actions)}
  expect(page.url()).toContain('/dashboard');
}});
"""
        test_file = tmp_path / "exact_steps.spec.ts"
        test_file.write_text(test_content)

        result = critic_agent.execute(str(test_file))

        # Should be rejected (over MAX_STEPS)
        assert result.data['estimated_steps'] == 11  # 10 clicks + 1 goto
        assert result.data['status'] == 'rejected'  # Over MAX_STEPS
        assert any(issue.get('type') == 'excessive_steps' for issue in result.data['issues_found'])

    def test_empty_test_file(self, critic_agent, tmp_path):
        """Test with empty test file."""
        test_file = tmp_path / "empty.spec.ts"
        test_file.write_text("")

        result = critic_agent.execute(str(test_file))

        assert result.success is True
        assert result.data['status'] == 'rejected'
        assert any(issue.get('type') == 'missing_assertions' for issue in result.data['issues_found'])

    def test_test_with_only_comments(self, critic_agent, tmp_path):
        """Test with file containing only comments."""
        test_content = """
// This is a comment
/* This is a multiline
   comment */
"""
        test_file = tmp_path / "comments_only.spec.ts"
        test_file.write_text(test_content)

        result = critic_agent.execute(str(test_file))

        assert result.success is True
        assert result.data['status'] == 'rejected'
        assert result.data['estimated_steps'] == 0
        assert result.data['estimated_cost_usd'] == 0.0

    def test_case_insensitive_credential_pattern(self, critic_agent):
        """Test that credential pattern is case-insensitive."""
        test_content = """import { test, expect } from '@playwright/test';

test('test', async ({ page }) => {
  const HARD_CODED_CREDENTIAL = 'password';
  const hard_coded_credential = 'password';
  const HardCodedCredential = 'password';
  expect(true).toBe(true);
});
"""
        issues = critic_agent._check_anti_patterns(test_content)

        # Should detect all variations (case-insensitive with IGNORECASE flag)
        assert len(issues) >= 1
        # Check that at least one issue is about credentials
        has_credential_issue = False
        for issue in issues:
            if 'credential' in issue.get('reason', '').lower() or \
               'credential' in issue.get('matched', '').lower():
                has_credential_issue = True
                break
        assert has_credential_issue


class TestCriticResultStructure:
    """Test result data structure."""

    def test_result_has_required_fields(self, critic_agent, tmp_path, clean_test_content):
        """Test that result has all required fields."""
        test_file = tmp_path / "test.spec.ts"
        test_file.write_text(clean_test_content)

        result = critic_agent.execute(str(test_file))

        # AgentResult fields
        assert hasattr(result, 'success')
        assert hasattr(result, 'data')
        assert hasattr(result, 'error')
        assert hasattr(result, 'metadata')
        assert hasattr(result, 'execution_time_ms')

        # Data fields
        assert 'status' in result.data
        assert 'test_path' in result.data
        assert 'issues_found' in result.data
        assert 'estimated_cost_usd' in result.data
        assert 'estimated_duration_ms' in result.data
        assert 'estimated_steps' in result.data

        # Metadata fields
        assert 'anti_patterns_found' in result.metadata
        assert 'assertion_count' in result.metadata

    def test_status_values(self, critic_agent, tmp_path, clean_test_content, test_with_nth_selector):
        """Test that status is either 'approved' or 'rejected'."""
        # Approved test
        test_file1 = tmp_path / "approved.spec.ts"
        test_file1.write_text(clean_test_content)
        result1 = critic_agent.execute(str(test_file1))
        assert result1.data['status'] in ['approved', 'rejected']
        assert result1.data['status'] == 'approved'

        # Rejected test
        test_file2 = tmp_path / "rejected.spec.ts"
        test_file2.write_text(test_with_nth_selector)
        result2 = critic_agent.execute(str(test_file2))
        assert result2.data['status'] in ['approved', 'rejected']
        assert result2.data['status'] == 'rejected'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
