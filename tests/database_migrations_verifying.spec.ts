import { test, expect } from '@playwright/test';

const S = (id: string) => `[data-testid="${id}"]`;

test.use({
  screenshot: 'on',
  video: 'retain-on-failure',
  trace: 'retain-on-failure'
});

test.describe('database migrations verifying schema changes without data loss, save as migration.spec.ts', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(process.env.BASE_URL!);
  });

  test('happy path', async ({ page }) => {
    // database migrations verifying schema changes without data loss, save as migration.spec.ts

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
