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

test.describe('Password Reset', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to base URL from environment
    await page.goto(process.env.BASE_URL || 'http://localhost:3000');
  });

  test('happy path - successfully request password reset', async ({ page }) => {
    // Step 1: Navigate to password reset page
    await page.click(S('forgot-password-link'));
    await page.waitForSelector(S('password-reset-form'));
    await page.screenshot({ path: 'artifacts/reset-page-loaded.png', fullPage: true });

    // Step 2: Fill email input with valid email
    await page.fill(S('email-input'), process.env.TEST_EMAIL || 'test@example.com');
    await page.screenshot({ path: 'artifacts/email-filled.png', fullPage: true });

    // Step 3: Submit password reset request
    await page.click(S('submit-reset-button'));
    await page.waitForSelector(S('success-message'));
    await page.screenshot({ path: 'artifacts/reset-success.png', fullPage: true });

    // Assertions - verify success state
    await expect(page.locator(S('success-message'))).toBeVisible();
    await expect(page.locator(S('success-message'))).toContainText('password reset link has been sent');
    await expect(page.locator(S('email-input'))).toHaveValue(process.env.TEST_EMAIL || 'test@example.com');
  });

  test('error case - invalid email format', async ({ page }) => {
    // Step 1: Navigate to password reset page
    await page.click(S('forgot-password-link'));
    await page.waitForSelector(S('password-reset-form'));
    await page.screenshot({ path: 'artifacts/error-reset-page-loaded.png', fullPage: true });

    // Step 2: Fill email input with invalid email format
    await page.fill(S('email-input'), 'invalid-email');
    await page.screenshot({ path: 'artifacts/error-invalid-email-filled.png', fullPage: true });

    // Step 3: Attempt to submit with invalid email
    await page.click(S('submit-reset-button'));
    await page.waitForSelector(S('error-message'));
    await page.screenshot({ path: 'artifacts/error-validation-shown.png', fullPage: true });

    // Assertions - verify error state
    await expect(page.locator(S('error-message'))).toBeVisible();
    await expect(page.locator(S('error-message'))).toContainText('valid email');
    await expect(page.locator(S('success-message'))).not.toBeVisible();
  });

  test('error case - empty email field', async ({ page }) => {
    // Step 1: Navigate to password reset page
    await page.click(S('forgot-password-link'));
    await page.waitForSelector(S('password-reset-form'));
    await page.screenshot({ path: 'artifacts/error-empty-page-loaded.png', fullPage: true });

    // Step 2: Attempt to submit without filling email
    await page.click(S('submit-reset-button'));
    await page.waitForSelector(S('error-message'));
    await page.screenshot({ path: 'artifacts/error-empty-field.png', fullPage: true });

    // Assertions - verify required field error
    await expect(page.locator(S('error-message'))).toBeVisible();
    await expect(page.locator(S('error-message'))).toContainText('required');
    await expect(page.locator(S('email-input'))).toHaveValue('');
  });

  test('happy path - cancel password reset and return to login', async ({ page }) => {
    // Step 1: Navigate to password reset page
    await page.click(S('forgot-password-link'));
    await page.waitForSelector(S('password-reset-form'));
    await page.screenshot({ path: 'artifacts/cancel-reset-page.png', fullPage: true });

    // Step 2: Click cancel or back to login link
    await page.click(S('back-to-login-link'));
    await page.waitForSelector(S('login-form'));
    await page.screenshot({ path: 'artifacts/cancel-back-to-login.png', fullPage: true });

    // Assertions - verify navigation back to login
    await expect(page.locator(S('login-form'))).toBeVisible();
    await expect(page.locator(S('password-reset-form'))).not.toBeVisible();
  });
});