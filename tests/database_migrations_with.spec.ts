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

test.describe('Database Migrations with OAuth', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to base URL from environment
    await page.goto(process.env.BASE_URL || 'http://localhost:3000');
    
    // Step 1: Authenticate with OAuth
    await page.click(S('oauth-login-button'));
    await page.waitForSelector(S('oauth-provider-select'));
    await page.screenshot({ path: 'artifacts/oauth-login.png', fullPage: true });
    
    // Step 2: Select OAuth provider and complete authentication
    await page.click(S('oauth-provider-google'));
    await page.fill(S('oauth-email-input'), process.env.TEST_EMAIL || 'test@example.com');
    await page.fill(S('oauth-password-input'), process.env.TEST_PASSWORD || 'testpassword');
    await page.click(S('oauth-submit-button'));
    await page.waitForSelector(S('dashboard-container'));
    await page.screenshot({ path: 'artifacts/oauth-authenticated.png', fullPage: true });
    
    // Step 3: Navigate to database migrations page
    await page.click(S('admin-menu'));
    await page.click(S('migrations-link'));
    await page.waitForSelector(S('migrations-dashboard'));
    await page.screenshot({ path: 'artifacts/migrations-page.png', fullPage: true });
  });

  test('happy path - execute migration and verify schema changes', async ({ page }) => {
    // Step 1: Check existing records before migration
    await page.click(S('view-existing-records-button'));
    await page.waitForSelector(S('records-table'));
    await page.screenshot({ path: 'artifacts/pre-migration-records.png', fullPage: true });
    
    const preMigrationCount = await page.locator(S('records-count')).textContent();
    await expect(page.locator(S('records-count'))).toBeVisible();
    await expect(page.locator(S('records-count'))).toContainText(/\d+/);
    
    // Step 2: Select migration file to execute
    await page.click(S('select-migration-button'));
    await page.waitForSelector(S('migration-file-list'));
    await page.click(S('migration-file-cloppy-ai-schema'));
    await page.screenshot({ path: 'artifacts/migration-selected.png', fullPage: true });
    
    await expect(page.locator(S('migration-file-name'))).toBeVisible();
    await expect(page.locator(S('migration-file-name'))).toContainText('cloppy_ai_schema');
    
    // Step 3: Execute migration against PostgreSQL
    await page.click(S('execute-migration-button'));
    await page.waitForSelector(S('migration-progress-indicator'));
    await page.screenshot({ path: 'artifacts/migration-executing.png', fullPage: true });
    
    // Step 4: Wait for migration completion
    await page.waitForSelector(S('migration-success-message'), { timeout: 60000 });
    await page.screenshot({ path: 'artifacts/migration-completed.png', fullPage: true });
    
    await expect(page.locator(S('migration-success-message'))).toBeVisible();
    await expect(page.locator(S('migration-success-message'))).toContainText('Migration completed successfully');
    
    // Step 5: Verify schema changes applied correctly
    await page.click(S('view-schema-button'));
    await page.waitForSelector(S('schema-details-panel'));
    await page.screenshot({ path: 'artifacts/schema-changes.png', fullPage: true });
    
    await expect(page.locator(S('schema-table-cloppy-ai'))).toBeVisible();
    await expect(page.locator(S('schema-column-vector-embedding'))).toBeVisible();
    await expect(page.locator(S('schema-column-oauth-token'))).toBeVisible();
    
    // Step 6: Verify no data loss by checking existing records
    await page.click(S('view-existing-records-button'));
    await page.waitForSelector(S('records-table'));
    await page.screenshot({ path: 'artifacts/post-migration-records.png', fullPage: true });
    
    const postMigrationCount = await page.locator(S('records-count')).textContent();
    await expect(page.locator(S('records-count'))).toBeVisible();
    expect(postMigrationCount).toBe(preMigrationCount);
    
    // Step 7: Verify vector search still works after migration
    await page.click(S('test-vector-search-button'));
    await page.fill(S('vector-search-input'), 'test query for vector search');
    await page.click(S('execute-vector-search-button'));
    await page.waitForSelector(S('vector-search-results'));
    await page.screenshot({ path: 'artifacts/vector-search-results.png', fullPage: true });
    
    await expect(page.locator(S('vector-search-results'))).toBeVisible();
    await expect(page.locator(S('vector-search-status'))).toContainText('Search completed');
    await expect(page.locator(S('vector-search-result-item')).first()).toBeVisible();
  });

  test('test rollback functionality after migration', async ({ page }) => {
    // Step 1: Execute a migration first
    await page.click(S('select-migration-button'));
    await page.waitForSelector(S('migration-file-list'));
    await page.click(S('migration-file-cloppy-ai-schema'));
    await page.click(S('execute-migration-button'));
    await page.waitForSelector(S('migration-success-message'), { timeout: 60000 });
    await page.screenshot({ path: 'artifacts/rollback-pre-migration.png', fullPage: true });
    
    await expect(page.locator(S('migration-success-message'))).toBeVisible();
    
    // Step 2: Verify migration was applied
    await page.click(S('view-schema-button'));
    await page.waitForSelector(S('schema-details-panel'));
    await page.screenshot({ path: 'artifacts/rollback-schema-before.png', fullPage: true });
    
    await expect(page.locator(S('schema-table-cloppy-ai'))).toBeVisible();
    
    // Step 3: Initiate rollback
    await page.click(S('migrations-history-button'));
    await page.waitForSelector(S('migration-history-list'));
    await page.click(S('latest-migration-item'));
    await page.click(S('rollback-migration-button'));
    await page.screenshot({ path: 'artifacts/rollback-initiated.png', fullPage: true });
    
    // Step 4: Confirm rollback action
    await page.waitForSelector(S('rollback-confirmation-dialog'));
    await page.click(S('confirm-rollback-button'));
    await page.waitForSelector(S('rollback-progress-indicator'));
    await page.screenshot({ path: 'artifacts/rollback-executing.png', fullPage: true });
    
    // Step 5: Wait for rollback completion
    await page.waitForSelector(S('rollback-success-message'), { timeout: 60000 });
    await page.screenshot({ path: 'artifacts/rollback-completed.png', fullPage: true });
    
    await expect(page.locator(S('rollback-success-message'))).toBeVisible();
    await expect(page.locator(S('rollback-success-message'))).toContainText('Rollback completed successfully');
    
    // Step 6: Verify schema reverted to previous state
    await page.click(S('view-schema-button'));
    await page.waitForSelector(S('schema-details-panel'));
    await page.screenshot({ path: 'artifacts/rollback-schema-after.png', fullPage: true });
    
    await expect(page.locator(S('schema-details-panel'))).toBeVisible();
    await expect(page.locator(S('rollback-verification-status'))).toContainText('Schema reverted');
  });

  test('error case - migration fails with invalid schema', async ({ page }) => {
    // Step 1: Select invalid migration file
    await page.click(S('select-migration-button'));
    await page.waitForSelector(S('migration-file-list'));
    await page.click(S('migration-file-invalid-schema'));
    await page.screenshot({ path: 'artifacts/error-invalid-migration-selected.png', fullPage: true });
    
    await expect(page.locator(S('migration-file-name'))).toBeVisible();
    
    // Step 2: Attempt to execute invalid migration
    await page.click(S('execute-migration-button'));
    await page.waitForSelector(S('migration-progress-indicator'));
    await page.screenshot({ path: 'artifacts/error-migration-executing.png', fullPage: true });
    
    // Step 3: Wait for error message
    await page.waitForSelector(S('migration-error-message'), { timeout: 60000 });
    await page.screenshot({ path: 'artifacts/error-migration-failed.png', fullPage: true });
    
    await expect(page.locator(S('migration-error-message'))).toBeVisible();
    await expect(page.locator(S('migration-error-message'))).toContainText('Migration failed');
    await expect(page.locator(S('migration-error-details'))).toContainText('syntax error');
    
    // Step 4: Verify database state unchanged
    await page.click(S('view-schema-button'));
    await page.waitForSelector(S('schema-details-panel'));
    await page.screenshot({ path: 'artifacts/error-schema-unchanged.png', fullPage: true });
    
    await expect(page.locator(S('schema-status'))).toContainText('No changes applied');
  });

  test('error case - OAuth token expired during migration', async ({ page }) => {
    // Step 1: Simulate OAuth token expiration
    await page.evaluate(() => {
      localStorage.setItem('oauth_token_expired', 'true');
    });
    await page.screenshot({ path: 'artifacts/error-token-expired-setup.png', fullPage: true });
    
    // Step 2: Attempt to execute migration with expired token
    await page.click(S('select-migration-button'));
    await page.waitForSelector(S('migration-file-list'));
    await page.click(S('migration-file-cloppy-ai-schema'));
    await page.click(S('execute-migration-button'));
    await page.screenshot({ path: 'artifacts/error-token-migration-attempt.png', fullPage: true });
    
    // Step 3: Verify authentication error displayed
    await page.waitForSelector(S('auth-error-message'));
    await page.screenshot({ path: 'artifacts/error-auth-failed.png', fullPage: true });
    
    await expect(page.locator(S('auth-error-message'))).toBeVisible();
    await expect(page.locator(S('auth-error-message'))).toContainText('Authentication required');
    await expect(page.locator(S('reauth-button'))).toBeVisible();
  });
});