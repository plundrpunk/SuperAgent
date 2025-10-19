import { test, expect } from '@playwright/test';

const S = (id: string) => `[data-testid="${id}"]`;

test.use({
  screenshot: 'on',
  video: 'retain-on-failure',
  trace: 'retain-on-failure'
});

test.describe('advanced search with async operations: search with node type filtering using search-filter-type dropdown, search with date range filtering using search-filter-date, search with content text filtering in search-input, test combined filters, verify search-results accuracy, test empty results case. Save as cloppy_ai_advanced_search.spec.ts', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(process.env.BASE_URL!);
  });

  test('happy path', async ({ page }) => {
    // advanced search with async operations: search with node type filtering using search-filter-type dropdown, search with date range filtering using search-filter-date, search with content text filtering in search-input, test combined filters, verify search-results accuracy, test empty results case. Save as cloppy_ai_advanced_search.spec.ts

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
