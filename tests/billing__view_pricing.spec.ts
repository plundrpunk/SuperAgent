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

test.describe('Billing and Pricing', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to base URL from environment
    await page.goto(process.env.BASE_URL ?? 'http://localhost:3000');
    
    // Assume user needs to be logged in to access billing
    // If login is required, add login steps here
    await page.waitForSelector(S('board-canvas'), { timeout: 10000 });
  });

  test('happy path - view pricing plans and upgrade to paid plan', async ({ page }) => {
    // Step 1: Navigate to billing/pricing page
    await page.click(S('billing-menu-btn'));
    await page.waitForSelector(S('pricing-plans-container'));
    await page.screenshot({ path: 'artifacts/billing-pricing-plans.png', fullPage: true });

    // Step 2: Verify pricing plans are displayed
    await expect(page.locator(S('pricing-plan-free'))).toBeVisible();
    await expect(page.locator(S('pricing-plan-pro'))).toBeVisible();
    await expect(page.locator(S('pricing-plan-enterprise'))).toBeVisible();
    await page.screenshot({ path: 'artifacts/billing-all-plans-visible.png', fullPage: true });

    // Step 3: Click upgrade button for Pro plan
    await page.click(S('upgrade-btn-pro'));
    await page.waitForSelector(S('payment-form'));
    await page.screenshot({ path: 'artifacts/billing-payment-form.png', fullPage: true });

    // Step 4: Fill payment details
    await page.fill(S('payment-card-number'), '4242424242424242');
    await page.fill(S('payment-card-expiry'), '12/25');
    await page.fill(S('payment-card-cvc'), '123');
    await page.fill(S('payment-cardholder-name'), 'Test User');
    await page.screenshot({ path: 'artifacts/billing-payment-details-filled.png', fullPage: true });

    // Step 5: Submit payment
    await page.click(S('payment-submit-btn'));
    await page.waitForSelector(S('payment-success-message'));
    await page.screenshot({ path: 'artifacts/billing-payment-success.png', fullPage: true });

    // Step 6: Verify upgrade success
    await expect(page.locator(S('payment-success-message'))).toBeVisible();
    await expect(page.locator(S('payment-success-message'))).toContainText('successfully upgraded');
    await expect(page.locator(S('current-plan-badge'))).toContainText('Pro');
    await page.screenshot({ path: 'artifacts/billing-upgraded-plan-confirmed.png', fullPage: true });
  });

  test('happy path - view usage metrics', async ({ page }) => {
    // Step 1: Navigate to billing page
    await page.click(S('billing-menu-btn'));
    await page.waitForSelector(S('billing-container'));
    await page.screenshot({ path: 'artifacts/usage-billing-page.png', fullPage: true });

    // Step 2: Navigate to usage tab
    await page.click(S('billing-usage-tab'));
    await page.waitForSelector(S('usage-metrics-container'));
    await page.screenshot({ path: 'artifacts/usage-metrics-displayed.png', fullPage: true });

    // Step 3: Verify usage metrics are displayed
    await expect(page.locator(S('usage-metric-boards'))).toBeVisible();
    await expect(page.locator(S('usage-metric-nodes'))).toBeVisible();
    await expect(page.locator(S('usage-metric-ai-requests'))).toBeVisible();
    await expect(page.locator(S('usage-metric-storage'))).toBeVisible();
    await page.screenshot({ path: 'artifacts/usage-all-metrics-visible.png', fullPage: true });

    // Step 4: Verify usage chart is displayed
    await expect(page.locator(S('usage-chart'))).toBeVisible();
    await page.screenshot({ path: 'artifacts/usage-chart-visible.png', fullPage: true });

    // Step 5: Filter usage by date range
    await page.click(S('usage-date-filter'));
    await page.click(S('usage-date-filter-last-30-days'));
    await page.waitForSelector(S('usage-chart'));
    await page.screenshot({ path: 'artifacts/usage-filtered-by-date.png', fullPage: true });

    // Assertions
    await expect(page.locator(S('usage-metrics-container'))).toBeVisible();
    await expect(page.locator(S('usage-chart'))).toBeVisible();
  });

  test('error case - payment failure handling with invalid card', async ({ page }) => {
    // Step 1: Navigate to billing and select upgrade
    await page.click(S('billing-menu-btn'));
    await page.waitForSelector(S('pricing-plans-container'));
    await page.screenshot({ path: 'artifacts/error-pricing-plans.png', fullPage: true });

    // Step 2: Click upgrade for Pro plan
    await page.click(S('upgrade-btn-pro'));
    await page.waitForSelector(S('payment-form'));
    await page.screenshot({ path: 'artifacts/error-payment-form.png', fullPage: true });

    // Step 3: Fill payment details with invalid card
    await page.fill(S('payment-card-number'), '4000000000000002');
    await page.fill(S('payment-card-expiry'), '12/25');
    await page.fill(S('payment-card-cvc'), '123');
    await page.fill(S('payment-cardholder-name'), 'Test User');
    await page.screenshot({ path: 'artifacts/error-invalid-card-filled.png', fullPage: true });

    // Step 4: Submit payment and expect failure
    await page.click(S('payment-submit-btn'));
    await page.waitForSelector(S('payment-error-message'));
    await page.screenshot({ path: 'artifacts/error-payment-failed.png', fullPage: true });

    // Step 5: Verify error message is displayed
    await expect(page.locator(S('payment-error-message'))).toBeVisible();
    await expect(page.locator(S('payment-error-message'))).toContainText('declined');
    await page.screenshot({ path: 'artifacts/error-payment-error-visible.png', fullPage: true });

    // Step 6: Verify user remains on current plan
    await page.click(S('payment-cancel-btn'));
    await page.waitForSelector(S('current-plan-badge'));
    await expect(page.locator(S('current-plan-badge'))).toContainText('Free');
    await page.screenshot({ path: 'artifacts/error-plan-unchanged.png', fullPage: true });
  });

  test('error case - payment failure with expired card', async ({ page }) => {
    // Step 1: Navigate to upgrade flow
    await page.click(S('billing-menu-btn'));
    await page.waitForSelector(S('pricing-plans-container'));
    await page.click(S('upgrade-btn-pro'));
    await page.waitForSelector(S('payment-form'));
    await page.screenshot({ path: 'artifacts/error-expired-card-form.png', fullPage: true });

    // Step 2: Fill payment details with expired card
    await page.fill(S('payment-card-number'), '4000000000000069');
    await page.fill(S('payment-card-expiry'), '01/20');
    await page.fill(S('payment-card-cvc'), '123');
    await page.fill(S('payment-cardholder-name'), 'Test User');
    await page.screenshot({ path: 'artifacts/error-expired-card-details.png', fullPage: true });

    // Step 3: Submit and verify error
    await page.click(S('payment-submit-btn'));
    await page.waitForSelector(S('payment-error-message'));
    await page.screenshot({ path: 'artifacts/error-expired-card-error.png', fullPage: true });

    // Assertions
    await expect(page.locator(S('payment-error-message'))).toBeVisible();
    await expect(page.locator(S('payment-error-message'))).toContainText('expired');
  });

  test('error case - insufficient funds payment failure', async ({ page }) => {
    // Step 1: Navigate to payment form
    await page.click(S('billing-menu-btn'));
    await page.waitForSelector(S('pricing-plans-container'));
    await page.click(S('upgrade-btn-enterprise'));
    await page.waitForSelector(S('payment-form'));
    await page.screenshot({ path: 'artifacts/error-insufficient-funds-form.png', fullPage: true });

    // Step 2: Use card that will be declined for insufficient funds
    await page.fill(S('payment-card-number'), '4000000000009995');
    await page.fill(S('payment-card-expiry'), '12/25');
    await page.fill(S('payment-card-cvc'), '123');
    await page.fill(S('payment-cardholder-name'), 'Test User');
    await page.screenshot({ path: 'artifacts/error-insufficient-funds-details.png', fullPage: true });

    // Step 3: Submit payment
    await page.click(S('payment-submit-btn'));
    await page.waitForSelector(S('payment-error-message'));
    await page.screenshot({ path: 'artifacts/error-insufficient-funds-error.png', fullPage: true });

    // Assertions
    await expect(page.locator(S('payment-error-message'))).toBeVisible();
    await expect(page.locator(S('payment-error-message'))).toContainText('insufficient funds');
    await page.screenshot({ path: 'artifacts/error-insufficient-funds-final.png', fullPage: true });
  });

  test('happy path - downgrade plan', async ({ page }) => {
    // Step 1: Navigate to billing
    await page.click(S('billing-menu-btn'));
    await page.waitForSelector(S('billing-container'));
    await page.screenshot({ path: 'artifacts/downgrade-billing-page.png', fullPage: true });

    // Step 2: Click manage subscription
    await page.click(S('manage-subscription-btn'));
    await page.waitForSelector(S('subscription-management-modal'));
    await page.screenshot({ path: 'artifacts/downgrade-subscription-modal.png', fullPage: true });

    // Step 3: Click downgrade button
    await page.click(S('downgrade-plan-btn'));
    await page.waitForSelector(S('downgrade-confirmation-modal'));
    await page.screenshot({ path: 'artifacts/downgrade-confirmation.png', fullPage: true });

    // Step 4: Confirm downgrade
    await page.click(S('confirm-downgrade-btn'));
    await page.waitForSelector(S('downgrade-success-message'));
    await page.screenshot({ path: 'artifacts/downgrade-success.png', fullPage: true });

    // Assertions
    await expect(page.locator(S('downgrade-success-message'))).toBeVisible();
    await expect(page.locator(S('downgrade-success-message'))).toContainText('downgraded');
  });
});