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

test.describe('Advanced Search with Async Operations', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to base URL from environment
    await page.goto(process.env.BASE_URL || 'http://localhost:3000');
    
    // Wait for search interface to load
    await page.waitForSelector(S('search-input'));
    await page.screenshot({ path: 'artifacts/initial-page-load.png', fullPage: true });
  });

  test('happy path - search with node type filtering', async ({ page }) => {
    // Step 1: Open node type filter dropdown
    await page.click(S('search-filter-type'));
    await page.waitForSelector(S('search-filter-type-options'));
    await page.screenshot({ path: 'artifacts/node-type-dropdown-opened.png', fullPage: true });

    // Step 2: Select a specific node type
    await page.click(S('search-filter-type-option-document'));
    await page.screenshot({ path: 'artifacts/node-type-selected.png', fullPage: true });

    // Step 3: Wait for async search results
    await page.waitForSelector(S('search-results'));
    await page.screenshot({ path: 'artifacts/node-type-results.png', fullPage: true });

    // Assertions
    await expect(page.locator(S('search-results'))).toBeVisible();
    await expect(page.locator(S('search-filter-type'))).toContainText('document');
  });

  test('happy path - search with date range filtering', async ({ page }) => {
    // Step 1: Open date range filter
    await page.click(S('search-filter-date'));
    await page.waitForSelector(S('search-filter-date-start'));
    await page.screenshot({ path: 'artifacts/date-filter-opened.png', fullPage: true });

    // Step 2: Set start date
    await page.fill(S('search-filter-date-start'), '2024-01-01');
    await page.screenshot({ path: 'artifacts/date-start-filled.png', fullPage: true });

    // Step 3: Set end date
    await page.fill(S('search-filter-date-end'), '2024-12-31');
    await page.screenshot({ path: 'artifacts/date-end-filled.png', fullPage: true });

    // Step 4: Apply date filter
    await page.click(S('search-filter-date-apply'));
    await page.waitForSelector(S('search-results'));
    await page.screenshot({ path: 'artifacts/date-range-results.png', fullPage: true });

    // Assertions
    await expect(page.locator(S('search-results'))).toBeVisible();
    await expect(page.locator(S('search-filter-date-start'))).toHaveValue('2024-01-01');
    await expect(page.locator(S('search-filter-date-end'))).toHaveValue('2024-12-31');
  });

  test('happy path - search with content text filtering', async ({ page }) => {
    // Step 1: Enter search text
    await page.fill(S('search-input'), 'test query');
    await page.screenshot({ path: 'artifacts/search-text-entered.png', fullPage: true });

    // Step 2: Trigger search (press Enter or click search button)
    await page.press(S('search-input'), 'Enter');
    await page.screenshot({ path: 'artifacts/search-triggered.png', fullPage: true });

    // Step 3: Wait for async search results
    await page.waitForSelector(S('search-results'));
    await page.screenshot({ path: 'artifacts/text-search-results.png', fullPage: true });

    // Assertions
    await expect(page.locator(S('search-results'))).toBeVisible();
    await expect(page.locator(S('search-input'))).toHaveValue('test query');
    await expect(page.locator(S('search-results'))).not.toBeEmpty();
  });

  test('happy path - combined filters search', async ({ page }) => {
    // Step 1: Enter search text
    await page.fill(S('search-input'), 'project report');
    await page.screenshot({ path: 'artifacts/combined-text-entered.png', fullPage: true });

    // Step 2: Select node type filter
    await page.click(S('search-filter-type'));
    await page.waitForSelector(S('search-filter-type-options'));
    await page.click(S('search-filter-type-option-file'));
    await page.screenshot({ path: 'artifacts/combined-type-selected.png', fullPage: true });

    // Step 3: Set date range
    await page.click(S('search-filter-date'));
    await page.waitForSelector(S('search-filter-date-start'));
    await page.fill(S('search-filter-date-start'), '2024-06-01');
    await page.fill(S('search-filter-date-end'), '2024-06-30');
    await page.click(S('search-filter-date-apply'));
    await page.screenshot({ path: 'artifacts/combined-date-applied.png', fullPage: true });

    // Step 4: Execute combined search
    await page.press(S('search-input'), 'Enter');
    await page.waitForSelector(S('search-results'));
    await page.screenshot({ path: 'artifacts/combined-search-results.png', fullPage: true });

    // Assertions
    await expect(page.locator(S('search-results'))).toBeVisible();
    await expect(page.locator(S('search-input'))).toHaveValue('project report');
    await expect(page.locator(S('search-filter-type'))).toContainText('file');
    await expect(page.locator(S('search-results-count'))).toBeVisible();
  });

  test('happy path - verify search results accuracy', async ({ page }) => {
    // Step 1: Perform search with specific criteria
    await page.fill(S('search-input'), 'unique document title');
    await page.screenshot({ path: 'artifacts/accuracy-search-entered.png', fullPage: true });

    // Step 2: Execute search
    await page.press(S('search-input'), 'Enter');
    await page.waitForSelector(S('search-results'));
    await page.screenshot({ path: 'artifacts/accuracy-results-loaded.png', fullPage: true });

    // Step 3: Verify result items contain search text
    await page.waitForSelector(S('search-result-item'));
    await page.screenshot({ path: 'artifacts/accuracy-results-verified.png', fullPage: true });

    // Assertions
    await expect(page.locator(S('search-result-item')).first()).toBeVisible();
    await expect(page.locator(S('search-result-item')).first()).toContainText('unique document title');
    await expect(page.locator(S('search-results-count'))).toBeVisible();
    await expect(page.locator(S('search-results-count'))).toContainText(/\d+/);
  });

  test('error case - empty results with no matches', async ({ page }) => {
    // Step 1: Enter search query that will return no results
    await page.fill(S('search-input'), 'xyznonexistentquery12345');
    await page.screenshot({ path: 'artifacts/empty-search-entered.png', fullPage: true });

    // Step 2: Execute search
    await page.press(S('search-input'), 'Enter');
    await page.waitForSelector(S('search-results'));
    await page.screenshot({ path: 'artifacts/empty-search-executed.png', fullPage: true });

    // Step 3: Wait for empty state message
    await page.waitForSelector(S('search-results-empty'));
    await page.screenshot({ path: 'artifacts/empty-results-displayed.png', fullPage: true });

    // Assertions
    await expect(page.locator(S('search-results-empty'))).toBeVisible();
    await expect(page.locator(S('search-results-empty'))).toContainText(/no results|not found|no matches/i);
    await expect(page.locator(S('search-result-item'))).not.toBeVisible();
  });

  test('error case - invalid date range', async ({ page }) => {
    // Step 1: Open date filter
    await page.click(S('search-filter-date'));
    await page.waitForSelector(S('search-filter-date-start'));
    await page.screenshot({ path: 'artifacts/invalid-date-opened.png', fullPage: true });

    // Step 2: Set end date before start date
    await page.fill(S('search-filter-date-start'), '2024-12-31');
    await page.fill(S('search-filter-date-end'), '2024-01-01');
    await page.screenshot({ path: 'artifacts/invalid-date-entered.png', fullPage: true });

    // Step 3: Attempt to apply invalid date range
    await page.click(S('search-filter-date-apply'));
    await page.waitForSelector(S('search-filter-date-error'));
    await page.screenshot({ path: 'artifacts/invalid-date-error.png', fullPage: true });

    // Assertions
    await expect(page.locator(S('search-filter-date-error'))).toBeVisible();
    await expect(page.locator(S('search-filter-date-error'))).toContainText(/invalid|error|start date.*end date/i);
  });

  test('error case - empty search with no filters', async ({ page }) => {
    // Step 1: Attempt to search without entering any criteria
    await page.press(S('search-input'), 'Enter');
    await page.screenshot({ path: 'artifacts/empty-criteria-search.png', fullPage: true });

    // Step 2: Wait for validation message or default results
    await page.waitForSelector(S('search-validation-message'));
    await page.screenshot({ path: 'artifacts/empty-criteria-validation.png', fullPage: true });

    // Assertions
    await expect(page.locator(S('search-validation-message'))).toBeVisible();
    await expect(page.locator(S('search-validation-message'))).toContainText(/enter search|required|please provide/i);
  });
});