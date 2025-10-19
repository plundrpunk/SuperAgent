"""
Test suite for Critic agent's enhanced rejection feedback.
"""
import pytest
from pathlib import Path
from agent_system.agents.critic import CriticAgent


@pytest.fixture
def critic():
    """Create Critic agent instance."""
    return CriticAgent()


@pytest.fixture
def temp_test_file(tmp_path):
    """Create temporary test file."""
    test_file = tmp_path / "test_sample.spec.ts"
    return test_file


def test_critic_rejects_with_detailed_feedback_anti_patterns(critic, temp_test_file):
    """Test that Critic provides detailed feedback for anti-patterns."""
    test_code = """
import { test, expect } from '@playwright/test';

test('bad test', async ({ page }) => {
  await page.goto('http://localhost:3000');
  await page.locator('.css-abc123').click();
  const item = page.locator('.item').nth(2);
  await item.click();
  await page.waitForTimeout(5000);
  expect(await page.title()).toBe('Test');
});
"""
    temp_test_file.write_text(test_code)

    result = critic.execute(str(temp_test_file))

    assert result.success
    assert result.data['status'] == 'rejected'
    assert result.data['feedback'] is not None

    feedback = result.data['feedback']
    assert 'REJECTED' in feedback
    assert 'Anti-patterns' in feedback
    assert 'Line 5' in feedback  # localhost
    assert 'Line 6' in feedback  # .css-abc123
    assert 'Line 7' in feedback  # .nth(2)
    assert 'Line 9' in feedback  # waitForTimeout
    assert 'FIX:' in feedback

    # Check structured issues
    issues = result.data['issues_found']
    anti_pattern_issues = [i for i in issues if i['type'] == 'anti_pattern']
    assert len(anti_pattern_issues) == 4


def test_critic_rejects_with_missing_assertions_feedback(critic, temp_test_file):
    """Test that Critic provides detailed feedback for missing assertions."""
    test_code = """
import { test } from '@playwright/test';

test('no assertions', async ({ page }) => {
  await page.goto(process.env.BASE_URL!);
  await page.locator('[data-testid="button"]').click();
});
"""
    temp_test_file.write_text(test_code)

    result = critic.execute(str(temp_test_file))

    assert result.success
    assert result.data['status'] == 'rejected'

    feedback = result.data['feedback']
    assert 'Missing assertions' in feedback
    assert 'expected, 0 found' in feedback
    assert 'expect() call' in feedback

    # Check structured issues
    issues = result.data['issues_found']
    assertion_issues = [i for i in issues if i['type'] == 'missing_assertions']
    assert len(assertion_issues) == 1
    assert assertion_issues[0]['severity'] == 'critical'


def test_critic_rejects_with_performance_warnings(critic, temp_test_file):
    """Test that Critic provides performance warnings."""
    # Create test with many steps
    test_code = """
import { test, expect } from '@playwright/test';

test('many steps', async ({ page }) => {
  await page.goto(process.env.BASE_URL!);
  await page.locator('[data-testid="btn1"]').click();
  await page.locator('[data-testid="btn2"]').click();
  await page.locator('[data-testid="btn3"]').click();
  await page.locator('[data-testid="btn4"]').click();
  await page.locator('[data-testid="btn5"]').click();
  await page.locator('[data-testid="btn6"]').click();
  await page.locator('[data-testid="btn7"]').click();
  await page.locator('[data-testid="btn8"]').click();
  await page.locator('[data-testid="btn9"]').click();
  await page.locator('[data-testid="btn10"]').click();
  await page.locator('[data-testid="btn11"]').click();
  await page.locator('[data-testid="btn12"]').click();
  expect(await page.title()).toBe('Test');
});
"""
    temp_test_file.write_text(test_code)

    result = critic.execute(str(temp_test_file))

    assert result.success
    assert result.data['status'] == 'rejected'

    feedback = result.data['feedback']
    assert 'Performance' in feedback
    assert 'steps' in feedback.lower()
    assert 'max' in feedback.lower()

    # Check structured issues
    issues = result.data['issues_found']
    step_issues = [i for i in issues if i['type'] == 'excessive_steps']
    assert len(step_issues) == 1
    assert step_issues[0]['severity'] == 'warning'


def test_critic_approves_clean_test(critic, temp_test_file):
    """Test that Critic approves well-written tests."""
    test_code = """
import { test, expect } from '@playwright/test';

test('good test', async ({ page }) => {
  await page.goto(process.env.BASE_URL!);
  await page.locator('[data-testid="login-btn"]').click();
  await page.locator('[data-testid="username"]').fill('testuser');
  await page.locator('[data-testid="password"]').fill('testpass');
  await page.locator('[data-testid="submit"]').click();

  await page.waitForSelector('[data-testid="dashboard"]');
  expect(await page.locator('[data-testid="welcome"]').textContent()).toContain('Welcome');
});
"""
    temp_test_file.write_text(test_code)

    result = critic.execute(str(temp_test_file))

    assert result.success
    assert result.data['status'] == 'approved'
    assert result.data['feedback'] is None
    assert len(result.data['issues_found']) == 0


def test_critic_feedback_has_priority_ordering(critic, temp_test_file):
    """Test that feedback prioritizes critical issues over warnings."""
    test_code = """
import { test } from '@playwright/test';

test('mixed issues', async ({ page }) => {
  await page.goto('http://localhost:3000');
  await page.locator('.item').nth(0).click();
  await page.locator('[data-testid="btn1"]').click();
  await page.locator('[data-testid="btn2"]').click();
  await page.locator('[data-testid="btn3"]').click();
  await page.locator('[data-testid="btn4"]').click();
  await page.locator('[data-testid="btn5"]').click();
  await page.locator('[data-testid="btn6"]').click();
  await page.locator('[data-testid="btn7"]').click();
  await page.locator('[data-testid="btn8"]').click();
  await page.locator('[data-testid="btn9"]').click();
  await page.locator('[data-testid="btn10"]').click();
  await page.locator('[data-testid="btn11"]').click();
});
"""
    temp_test_file.write_text(test_code)

    result = critic.execute(str(temp_test_file))

    feedback = result.data['feedback']

    # Critical issues should appear before warnings
    anti_pattern_pos = feedback.find('Anti-patterns')
    assertion_pos = feedback.find('Missing assertions')
    performance_pos = feedback.find('Performance')

    assert anti_pattern_pos < performance_pos
    assert assertion_pos < performance_pos


def test_critic_metadata_counts(critic, temp_test_file):
    """Test that metadata includes correct counts."""
    test_code = """
import { test } from '@playwright/test';

test('test', async ({ page }) => {
  await page.goto('http://localhost:3000');
  await page.locator('.css-abc').click();
  await page.locator('[data-testid="btn1"]').click();
  await page.locator('[data-testid="btn2"]').click();
  await page.locator('[data-testid="btn3"]').click();
  await page.locator('[data-testid="btn4"]').click();
  await page.locator('[data-testid="btn5"]').click();
  await page.locator('[data-testid="btn6"]').click();
  await page.locator('[data-testid="btn7"]').click();
  await page.locator('[data-testid="btn8"]').click();
  await page.locator('[data-testid="btn9"]').click();
  await page.locator('[data-testid="btn10"]').click();
  await page.locator('[data-testid="btn11"]').click();
});
"""
    temp_test_file.write_text(test_code)

    result = critic.execute(str(temp_test_file))

    metadata = result.metadata
    assert metadata['critical_issues'] == 3  # localhost, .css-, no assertions
    assert metadata['warnings'] == 1  # excessive steps only (duration is 26s < 60s max)
    assert metadata['assertion_count'] == 0
    assert metadata['anti_patterns_found'] == 2


def test_critic_fix_suggestions(critic, temp_test_file):
    """Test that fix suggestions are actionable."""
    test_code = """
import { test, expect } from '@playwright/test';

test('test', async ({ page }) => {
  await page.goto('http://localhost:3000');
  await page.locator('.item').nth(0).click();
  expect(true).toBe(true);
});
"""
    temp_test_file.write_text(test_code)

    result = critic.execute(str(temp_test_file))

    issues = result.data['issues_found']

    # Check that each anti-pattern has a fix suggestion
    for issue in issues:
        if issue['type'] == 'anti_pattern':
            assert 'fix' in issue
            assert len(issue['fix']) > 0
            # Fix should be actionable
            assert any(keyword in issue['fix'].lower() for keyword in ['replace', 'use', 'data-testid', 'environment'])
