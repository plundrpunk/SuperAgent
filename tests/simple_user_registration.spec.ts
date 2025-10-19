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

test.describe('User Registration', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to registration page
    await page.goto(`${process.env.BASE_URL || 'http://localhost:3000'}/register`);
    await page.waitForSelector(S('registration-form'));
  });

  test('happy path - successful user registration with valid data', async ({ page }) => {
    // Step 1: Fill in username
    await page.fill(S('username-input'), process.env.TEST_USERNAME || 'testuser123');
    await page.screenshot({ path: 'artifacts/registration-step1-username.png', fullPage: true });

    // Step 2: Fill in email
    await page.fill(S('email-input'), process.env.TEST_EMAIL || 'testuser123@example.com');
    await page.screenshot({ path: 'artifacts/registration-step2-email.png', fullPage: true });

    // Step 3: Fill in password
    await page.fill(S('password-input'), process.env.TEST_PASSWORD || 'SecurePass123!');
    await page.screenshot({ path: 'artifacts/registration-step3-password.png', fullPage: true });

    // Step 4: Fill in password confirmation
    await page.fill(S('confirm-password-input'), process.env.TEST_PASSWORD || 'SecurePass123!');
    await page.screenshot({ path: 'artifacts/registration-step4-confirm-password.png', fullPage: true });

    // Step 5: Submit registration form
    await page.click(S('register-submit-button'));
    await page.waitForSelector(S('registration-success-message'));
    await page.screenshot({ path: 'artifacts/registration-step5-success.png', fullPage: true });

    // Assertions - verify successful registration
    await expect(page.locator(S('registration-success-message'))).toBeVisible();
    await expect(page.locator(S('registration-success-message'))).toContainText('Registration successful');
    await expect(page).toHaveURL(/.*dashboard|.*home|.*success/);
  });

  test('error case - registration fails with invalid email format', async ({ page }) => {
    // Step 1: Fill in username
    await page.fill(S('username-input'), 'testuser456');
    await page.screenshot({ path: 'artifacts/error-invalid-email-step1.png', fullPage: true });

    // Step 2: Fill in invalid email
    await page.fill(S('email-input'), 'invalid-email-format');
    await page.screenshot({ path: 'artifacts/error-invalid-email-step2.png', fullPage: true });

    // Step 3: Fill in passwords
    await page.fill(S('password-input'), 'SecurePass123!');
    await page.fill(S('confirm-password-input'), 'SecurePass123!');
    await page.screenshot({ path: 'artifacts/error-invalid-email-step3.png', fullPage: true });

    // Step 4: Attempt to submit
    await page.click(S('register-submit-button'));
    await page.waitForSelector(S('email-error-message'));
    await page.screenshot({ path: 'artifacts/error-invalid-email-step4.png', fullPage: true });

    // Assertions - verify error message is displayed
    await expect(page.locator(S('email-error-message'))).toBeVisible();
    await expect(page.locator(S('email-error-message'))).toContainText(/invalid email|valid email/i);
  });

  test('error case - registration fails with mismatched passwords', async ({ page }) => {
    // Step 1: Fill in username and email
    await page.fill(S('username-input'), 'testuser789');
    await page.fill(S('email-input'), 'testuser789@example.com');
    await page.screenshot({ path: 'artifacts/error-password-mismatch-step1.png', fullPage: true });

    // Step 2: Fill in password
    await page.fill(S('password-input'), 'SecurePass123!');
    await page.screenshot({ path: 'artifacts/error-password-mismatch-step2.png', fullPage: true });

    // Step 3: Fill in different confirmation password
    await page.fill(S('confirm-password-input'), 'DifferentPass456!');
    await page.screenshot({ path: 'artifacts/error-password-mismatch-step3.png', fullPage: true });

    // Step 4: Attempt to submit
    await page.click(S('register-submit-button'));
    await page.waitForSelector(S('password-error-message'));
    await page.screenshot({ path: 'artifacts/error-password-mismatch-step4.png', fullPage: true });

    // Assertions - verify password mismatch error
    await expect(page.locator(S('password-error-message'))).toBeVisible();
    await expect(page.locator(S('password-error-message'))).toContainText(/password.*match|passwords.*same/i);
  });

  test('error case - registration fails with empty required fields', async ({ page }) => {
    // Step 1: Leave all fields empty and attempt to submit
    await page.click(S('register-submit-button'));
    await page.waitForSelector(S('username-error-message'));
    await page.screenshot({ path: 'artifacts/error-empty-fields-step1.png', fullPage: true });

    // Assertions - verify validation errors are displayed
    await expect(page.locator(S('username-error-message'))).toBeVisible();
    await expect(page.locator(S('email-error-message'))).toBeVisible();
    await expect(page.locator(S('password-error-message'))).toBeVisible();
    await expect(page.locator(S('username-error-message'))).toContainText(/required|cannot be empty/i);
  });
});