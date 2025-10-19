import { test, expect } from '@playwright/test';

/**
 * Selector helper - ALWAYS use data-testid attributes
 * Example: await page.click(S('login-button'))
 */
const S = (id: string) => `[data-testid="${id}"]`;

/**
 * Test configuration - enable screenshots, videos, and traces
 */
test.use({
  screenshot: 'on',
  video: 'retain-on-failure',
  trace: 'retain-on-failure',
});

test.describe('FEATURE_NAME', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to base URL from environment
    await page.goto(process.env.BASE_URL || 'http://localhost:3000');
  });

  test('happy path - DESCRIBE_ACTION', async ({ page }) => {
    // Step 1: Action description
    await page.click(S('element-id'));
    await page.screenshot({ path: 'artifacts/step1.png', fullPage: true });

    // Step 2: Fill form or interact
    await page.fill(S('input-id'), 'test value');
    await page.screenshot({ path: 'artifacts/step2.png', fullPage: true });

    // Step 3: Submit or proceed
    await page.click(S('submit-button'));
    await page.waitForSelector(S('success-message'));
    await page.screenshot({ path: 'artifacts/step3.png', fullPage: true });

    // Assertions - ALWAYS include expect statements
    await expect(page.locator(S('success-message'))).toBeVisible();
    await expect(page.locator(S('success-message'))).toContainText('Success');
  });

  test('error case - DESCRIBE_ERROR_SCENARIO', async ({ page }) => {
    // Test error handling or edge cases
    await page.click(S('action-button'));
    await page.screenshot({ path: 'artifacts/error-step1.png', fullPage: true });

    // Trigger error condition
    await page.fill(S('input-id'), 'invalid value');
    await page.click(S('submit-button'));
    await page.screenshot({ path: 'artifacts/error-step2.png', fullPage: true });

    // Assert error state
    await expect(page.locator(S('error-message'))).toBeVisible();
    await expect(page.locator(S('error-message'))).toContainText('Error');
  });
});
