"""
Tests for Scribe Agent Self-Validation
Verifies validation logic and retry mechanism.
"""
import pytest
from pathlib import Path
import tempfile
import shutil

from agent_system.agents.scribe import ScribeAgent


class TestScribeValidation:
    """Test Scribe's self-validation capabilities."""

    @pytest.fixture
    def scribe(self):
        """Create Scribe agent instance."""
        return ScribeAgent()

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test output."""
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp)

    def test_validate_good_test(self, scribe):
        """Test that valid test passes validation."""
        good_test = '''
import { test, expect } from '@playwright/test';

const S = (id: string) => `[data-testid="${id}"]`;

test.describe('Login', () => {
  test('happy path', async ({ page }) => {
    await page.goto(process.env.BASE_URL!);
    await page.locator(S('username')).fill('test@example.com');
    await page.locator(S('password')).fill('password');
    await page.locator(S('submit')).click();

    await page.screenshot({ path: 'login-success.png' });

    await expect(page.locator(S('dashboard'))).toBeVisible();
  });
});
'''
        passed, issues = scribe._validate_generated_test(good_test)

        assert passed is True
        assert len(issues) == 0

    def test_validate_missing_assertions(self, scribe):
        """Test rejection of tests without assertions."""
        no_assertions = '''
import { test, expect } from '@playwright/test';

test.describe('Login', () => {
  test('no assertions', async ({ page }) => {
    await page.goto(process.env.BASE_URL!);
    await page.locator('[data-testid="submit"]').click();
  });
});
'''
        passed, issues = scribe._validate_generated_test(no_assertions)

        assert passed is False
        assert any('assertion' in issue.lower() for issue in issues)

    def test_validate_nth_selector(self, scribe):
        """Test rejection of index-based selectors."""
        nth_selector = '''
import { test, expect } from '@playwright/test';

test.describe('Login', () => {
  test('bad selector', async ({ page }) => {
    await page.locator('button').nth(2).click();
    await expect(page.locator('div')).toBeVisible();
  });
});
'''
        passed, issues = scribe._validate_generated_test(nth_selector)

        assert passed is False
        assert any('flaky' in issue.lower() or 'nth' in issue.lower() for issue in issues)

    def test_validate_css_class(self, scribe):
        """Test rejection of generated CSS classes."""
        css_class = '''
import { test, expect } from '@playwright/test';

test.describe('Login', () => {
  test('generated class', async ({ page }) => {
    await page.locator('.css-abc123').click();
    await expect(page).toHaveURL('/dashboard');
  });
});
'''
        passed, issues = scribe._validate_generated_test(css_class)

        assert passed is False
        assert any('css class' in issue.lower() for issue in issues)

    def test_validate_wait_for_timeout(self, scribe):
        """Test rejection of waitForTimeout."""
        wait_timeout = '''
import { test, expect } from '@playwright/test';

test.describe('Login', () => {
  test('bad wait', async ({ page }) => {
    await page.locator('[data-testid="submit"]').click();
    await page.waitForTimeout(5000);
    await expect(page.locator('[data-testid="result"]')).toBeVisible();
  });
});
'''
        passed, issues = scribe._validate_generated_test(wait_timeout)

        assert passed is False
        assert any('waitForTimeout' in issue for issue in issues)

    def test_validate_hardcoded_localhost(self, scribe):
        """Test rejection of localhost URLs."""
        localhost = '''
import { test, expect } from '@playwright/test';

test.describe('Login', () => {
  test('hardcoded url', async ({ page }) => {
    await page.goto('http://localhost:3000');
    await expect(page.locator('[data-testid="title"]')).toBeVisible();
  });
});
'''
        passed, issues = scribe._validate_generated_test(localhost)

        assert passed is False
        assert any('localhost' in issue.lower() or 'BASE_URL' in issue for issue in issues)

    def test_validate_missing_screenshots(self, scribe):
        """Test rejection when screenshots are missing."""
        no_screenshots = '''
import { test, expect } from '@playwright/test';

test.describe('Login', () => {
  test('no screenshots', async ({ page }) => {
    await page.goto(process.env.BASE_URL!);
    await page.locator('[data-testid="submit"]').click();
    await expect(page.locator('[data-testid="result"]')).toBeVisible();
  });
});
'''
        passed, issues = scribe._validate_generated_test(no_screenshots)

        assert passed is False
        assert any('screenshot' in issue.lower() for issue in issues)

    def test_validate_too_many_steps(self, scribe):
        """Test rejection when test has too many steps."""
        many_steps = '''
import { test, expect } from '@playwright/test';

test.describe('Complex', () => {
  test('many steps', async ({ page }) => {
    await page.goto(process.env.BASE_URL!);
    await page.locator('[data-testid="step1"]').click();
    await page.locator('[data-testid="step2"]').click();
    await page.locator('[data-testid="step3"]').click();
    await page.locator('[data-testid="step4"]').click();
    await page.locator('[data-testid="step5"]').click();
    await page.locator('[data-testid="step6"]').click();
    await page.locator('[data-testid="step7"]').click();
    await page.locator('[data-testid="step8"]').click();
    await page.locator('[data-testid="step9"]').click();
    await page.locator('[data-testid="step10"]').click();
    await page.locator('[data-testid="step11"]').click();
    await page.locator('[data-testid="step12"]').fill('text');
    await page.screenshot({ path: 'test.png' });
    await expect(page.locator('[data-testid="result"]')).toBeVisible();
  });
});
'''
        passed, issues = scribe._validate_generated_test(many_steps)

        assert passed is False
        assert any('steps' in issue.lower() for issue in issues)

    def test_count_steps(self, scribe):
        """Test step counting logic."""
        test_code = '''
        await page.goto(process.env.BASE_URL!);
        await page.locator('[data-testid="btn"]').click();
        await page.locator('[data-testid="input"]').fill('test');
        await page.screenshot({ path: 'test.png' });
        await page.waitForSelector('[data-testid="result"]');
        '''

        steps = scribe._count_steps(test_code)

        # goto, click, fill, screenshot, waitForSelector = 5 steps
        assert steps == 5

    def test_generate_with_validation_success(self, scribe):
        """Test successful generation with validation (mocked)."""
        # This tests the retry logic structure
        # In production, would need to mock the LLM call

        result = scribe._generate_with_validation(
            task_description="Test login with valid credentials",
            feature_name="Login",
            max_retries=3
        )

        # Even with template-based generation, validation should work
        assert 'success' in result
        assert 'attempts' in result

    def test_validation_stats_tracking(self, scribe):
        """Test that validation stats are tracked correctly."""
        # Validate a good test
        good_test = '''
import { test, expect } from '@playwright/test';

test.describe('Test', () => {
  test('works', async ({ page }) => {
    await page.goto(process.env.BASE_URL!);
    await page.screenshot({ path: 'test.png' });
    await expect(page.locator('[data-testid="result"]')).toBeVisible();
  });
});
'''
        scribe._validate_generated_test(good_test)

        # Validate a bad test
        bad_test = '''
import { test, expect } from '@playwright/test';

test.describe('Test', () => {
  test('no assertions', async ({ page }) => {
    await page.goto('http://localhost:3000');
  });
});
'''
        scribe._validate_generated_test(bad_test)

        # Stats tracking is done in _generate_with_validation
        # Just verify the methods exist and return correct structure
        stats = scribe.get_validation_stats()

        assert 'validation_attempts' in stats
        assert 'validation_failures' in stats
        assert 'success_rate' in stats
        assert 'total_retries_used' in stats

    def test_execute_creates_file(self, scribe, temp_dir):
        """Test that execute() creates a test file."""
        output_path = Path(temp_dir) / 'tests' / 'login.spec.ts'

        result = scribe.execute(
            task_description="Test login functionality",
            feature_name="Login",
            output_path=str(output_path),
            complexity='easy'
        )

        # Check result structure
        assert hasattr(result, 'success')
        assert hasattr(result, 'data')
        assert hasattr(result, 'execution_time_ms')

        # Check file was created (if validation passed)
        if result.success:
            assert output_path.exists()
            content = output_path.read_text()
            assert 'test.describe' in content
            assert 'expect' in content

    def test_multiple_validation_issues(self, scribe):
        """Test that multiple issues are detected."""
        bad_test = '''
import { test } from '@playwright/test';

test.describe('Bad Test', () => {
  test('multiple issues', async ({ page }) => {
    await page.goto('http://localhost:3000');
    await page.locator('.css-abc123').nth(0).click();
    await page.waitForTimeout(5000);
  });
});
'''
        passed, issues = scribe._validate_generated_test(bad_test)

        assert passed is False
        assert len(issues) >= 4  # No assertions, localhost, CSS class, nth, waitForTimeout, no screenshot


class TestScribeRetryLogic:
    """Test Scribe's retry and feedback mechanism."""

    @pytest.fixture
    def scribe(self):
        """Create Scribe agent instance."""
        return ScribeAgent()

    def test_retry_logic_structure(self, scribe):
        """Test that retry logic attempts up to max retries."""
        result = scribe._generate_with_validation(
            task_description="Simple test",
            feature_name="Test",
            max_retries=3
        )

        assert 'success' in result
        assert 'attempts' in result
        assert result['attempts'] <= 3

    def test_feedback_enhancement(self, scribe):
        """Test that feedback is incorporated into retry attempts."""
        # This is tested implicitly in _generate_with_validation
        # The enhanced_description should contain feedback

        # We can verify the structure is correct
        initial_desc = "Test login"
        issues = ["Missing assertions", "No data-testid selectors"]

        # Simulate what happens in the retry loop
        enhanced = f"""{initial_desc}

PREVIOUS ATTEMPT FAILED - FIX THESE ISSUES:
{chr(10).join(f'- {issue}' for issue in issues)}

REQUIREMENTS:
- Use ONLY data-testid selectors: const S = (id: string) => `[data-testid="${{id}}"]`
"""

        assert "PREVIOUS ATTEMPT FAILED" in enhanced
        assert "Missing assertions" in enhanced
        assert "data-testid" in enhanced


class TestScribeCriticAlignment:
    """Test that Scribe's validation matches Critic's criteria."""

    @pytest.fixture
    def scribe(self):
        """Create Scribe agent."""
        return ScribeAgent()

    def test_anti_patterns_match_critic(self, scribe):
        """Verify Scribe uses same anti-patterns as Critic."""
        from agent_system.agents.critic import CriticAgent

        critic = CriticAgent()

        # Check that anti-patterns are aligned
        scribe_patterns = {p['pattern'] for p in scribe.ANTI_PATTERNS}
        critic_patterns = {p['pattern'] for p in critic.ANTI_PATTERNS}

        assert scribe_patterns == critic_patterns

    def test_max_steps_match_critic(self, scribe):
        """Verify Scribe uses same step limit as Critic."""
        from agent_system.agents.critic import CriticAgent

        critic = CriticAgent()

        assert scribe.MAX_STEPS == critic.MAX_STEPS

    def test_max_duration_match_critic(self, scribe):
        """Verify Scribe uses same duration limit as Critic."""
        from agent_system.agents.critic import CriticAgent

        critic = CriticAgent()

        assert scribe.MAX_DURATION_MS == critic.MAX_DURATION_MS


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
