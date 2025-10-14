import { test, expect } from '@playwright/test';

const S = (id: string) => `[data-testid="${id}"]`;

test.use({
  screenshot: 'on',
  video: 'retain-on-failure',
  trace: 'retain-on-failure',
});

test.describe('Authentication Regression Baseline', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(process.env.BASE_URL || 'http://localhost:3000');
  });

  test('login flow - happy path', async ({ page }) => {
    // Navigate to login page
    await page.click(S('login-link'));
    await page.waitForSelector(S('email-input'));
    await page.screenshot({ path: 'artifacts/auth-step1-login-page.png', fullPage: true });

    // Fill credentials
    await page.fill(S('email-input'), 'test@example.com');
    await page.fill(S('password-input'), 'password123');
    await page.screenshot({ path: 'artifacts/auth-step2-filled-form.png', fullPage: true });

    // Submit login
    await page.click(S('login-submit'));
    await page.waitForSelector(S('user-menu'), { timeout: 10000 });
    await page.screenshot({ path: 'artifacts/auth-step3-logged-in.png', fullPage: true });

    // Verify logged in state
    await expect(page.locator(S('user-menu'))).toBeVisible();
    await expect(page.locator(S('logout-button'))).toBeVisible();
  });

  test('logout flow', async ({ page }) => {
    // Assume already logged in (or handle login first)
    await page.goto(`${process.env.BASE_URL || 'http://localhost:3000'}/dashboard`);

    // Open user menu
    await page.click(S('user-menu'));
    await page.waitForSelector(S('logout-button'));
    await page.screenshot({ path: 'artifacts/auth-logout-step1-menu.png', fullPage: true });

    // Click logout
    await page.click(S('logout-button'));
    await page.waitForSelector(S('login-link'), { timeout: 10000 });
    await page.screenshot({ path: 'artifacts/auth-logout-step2-logged-out.png', fullPage: true });

    // Verify logged out state
    await expect(page.locator(S('login-link'))).toBeVisible();
    await expect(page.locator(S('user-menu'))).not.toBeVisible();
  });

  test('login with invalid credentials', async ({ page }) => {
    await page.click(S('login-link'));
    await page.waitForSelector(S('email-input'));

    // Fill with invalid credentials
    await page.fill(S('email-input'), 'invalid@example.com');
    await page.fill(S('password-input'), 'wrongpassword');
    await page.click(S('login-submit'));

    // Wait for error message
    await page.waitForSelector(S('error-message'), { timeout: 5000 });
    await page.screenshot({ path: 'artifacts/auth-error-invalid-creds.png', fullPage: true });

    // Verify error displayed
    await expect(page.locator(S('error-message'))).toBeVisible();
    await expect(page.locator(S('error-message'))).toContainText(/invalid|incorrect|failed/i);
  });
});
