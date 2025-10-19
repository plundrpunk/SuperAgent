import { test, expect } from '@playwright/test';

const S = (id: string) => `[data-testid="${id}"]`;

test.use({
  screenshot: 'on',
  video: 'retain-on-failure',
  trace: 'retain-on-failure'
});

test.describe('user login', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(process.env.BASE_URL!);
  });

  test('happy path', async ({ page }) => {
    // user login

    // Take screenshots at key steps
    await page.screenshot({ path: 'screenshot-step-1.png' });

    // Add assertions
    await expect(page.locator(S('result'))).toBeVisible();
  });

  test('error case', async ({ page }) => {
    // Test error handling
    await expect(page.locator(S('error'))).toBeVisible();
  });
});
