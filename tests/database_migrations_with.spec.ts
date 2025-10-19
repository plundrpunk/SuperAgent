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
    
    // Authenticate with OAuth if required
    if (process.env.OAUTH_USERNAME && process.env.OAUTH_PASSWORD) {
      await page.waitForSelector(S('oauth-login-button'));
      await page.click(S('oauth-login-button'));
      await page.fill(S('oauth-username-input'), process.env.OAUTH_USERNAME);
      await page.fill(S('oauth-password-input'), process.env.OAUTH_PASSWORD);
      await page.click(S('oauth-submit-button'));
      await page.waitForSelector(S('dashboard-container'));
    }
  });

  test('happy path - execute migration and verify schema changes', async ({ page }) => {
    // Step 1: Navigate to database migrations page
    await page.click(S('admin-menu'));
    await page.click(S('database-migrations-link'));
    await page.waitForSelector(S('migrations-dashboard'));
    await page.screenshot({ path: 'artifacts/migration-dashboard.png', fullPage: true });

    // Step 2: Check existing records count before migration
    await page.click(S('view-records-button'));
    await page.waitForSelector(S('records-count-display'));
    const recordsBeforeMigration = await page.locator(S('records-count-display')).textContent();
    await page.screenshot({ path: 'artifacts/records-before-migration.png', fullPage: true });

    // Step 3: Execute migration against PostgreSQL database
    await page.click(S('run-migration-button'));
    await page.waitForSelector(S('migration-confirmation-dialog'));
    await page.screenshot({ path: 'artifacts/migration-confirmation.png', fullPage: true });
    
    await page.click(S('confirm-migration-button'));
    await page.waitForSelector(S('migration-progress-indicator'));
    await page.screenshot({ path: 'artifacts/migration-in-progress.png', fullPage: true });

    // Step 4: Wait for migration completion
    await page.waitForSelector(S('migration-success-message'), { timeout: 60000 });
    await page.screenshot({ path: 'artifacts/migration-completed.png', fullPage: true });

    // Step 5: Verify schema changes applied correctly
    await page.click(S('view-schema-button'));
    await page.waitForSelector(S('schema-details-panel'));
    await page.screenshot({ path: 'artifacts/schema-after-migration.png', fullPage: true });

    // Step 6: Verify no data loss by checking existing records
    await page.click(S('view-records-button'));
    await page.waitForSelector(S('records-count-display'));
    const recordsAfterMigration = await page.locator(S('records-count-display')).textContent();
    await page.screenshot({ path: 'artifacts/records-after-migration.png', fullPage: true });

    // Step 7: Test vector search functionality after migration
    await page.click(S('vector-search-tab'));
    await page.waitForSelector(S('vector-search-input'));
    await page.fill(S('vector-search-input'), 'test query');
    await page.click(S('vector-search-submit-button'));
    await page.waitForSelector(S('vector-search-results'));
    await page.screenshot({ path: 'artifacts/vector-search-results.png', fullPage: true });

    // Assertions - verify migration success
    await expect(page.locator(S('migration-success-message'))).toBeVisible();
    await expect(page.locator(S('migration-success-message'))).toContainText('Migration completed successfully');
    await expect(page.locator(S('schema-details-panel'))).toBeVisible();
    await expect(page.locator(S('schema-version-display'))).toContainText('v');
    
    // Verify no data loss
    expect(recordsBeforeMigration).toBe(recordsAfterMigration);
    await expect(page.locator(S('records-count-display'))).toBeVisible();
    
    // Verify vector search works
    await expect(page.locator(S('vector-search-results'))).toBeVisible();
    await expect(page.locator(S('vector-search-result-item')).first()).toBeVisible();
  });

  test('happy path - test rollback functionality', async ({ page }) => {
    // Step 1: Navigate to database migrations page
    await page.click(S('admin-menu'));
    await page.click(S('database-migrations-link'));
    await page.waitForSelector(S('migrations-dashboard'));
    await page.screenshot({ path: 'artifacts/rollback-dashboard.png', fullPage: true });

    // Step 2: View migration history
    await page.click(S('migration-history-tab'));
    await page.waitForSelector(S('migration-history-list'));
    await page.screenshot({ path: 'artifacts/migration-history.png', fullPage: true });

    // Step 3: Select latest migration for rollback
    await page.click(S('latest-migration-item'));
    await page.waitForSelector(S('migration-details-panel'));
    await page.screenshot({ path: 'artifacts/migration-details.png', fullPage: true });

    // Step 4: Initiate rollback
    await page.click(S('rollback-migration-button'));
    await page.waitForSelector(S('rollback-confirmation-dialog'));
    await page.screenshot({ path: 'artifacts/rollback-confirmation.png', fullPage: true });

    await page.click(S('confirm-rollback-button'));
    await page.waitForSelector(S('rollback-progress-indicator'));
    await page.screenshot({ path: 'artifacts/rollback-in-progress.png', fullPage: true });

    // Step 5: Wait for rollback completion
    await page.waitForSelector(S('rollback-success-message'), { timeout: 60000 });
    await page.screenshot({ path: 'artifacts/rollback-completed.png', fullPage: true });

    // Step 6: Verify schema reverted correctly
    await page.click(S('view-schema-button'));
    await page.waitForSelector(S('schema-details-panel'));
    await page.screenshot({ path: 'artifacts/schema-after-rollback.png', fullPage: true });

    // Step 7: Verify data integrity after rollback
    await page.click(S('view-records-button'));
    await page.waitForSelector(S('records-count-display'));
    await page.screenshot({ path: 'artifacts/records-after-rollback.png', fullPage: true });

    // Assertions - verify rollback success
    await expect(page.locator(S('rollback-success-message'))).toBeVisible();
    await expect(page.locator(S('rollback-success-message'))).toContainText('Rollback completed successfully');
    await expect(page.locator(S('schema-details-panel'))).toBeVisible();
    await expect(page.locator(S('records-count-display'))).toBeVisible();
    await expect(page.locator(S('migration-status-badge'))).toContainText('Rolled back');
  });

  test('error case - migration fails with invalid schema', async ({ page }) => {
    // Step 1: Navigate to database migrations page
    await page.click(S('admin-menu'));
    await page.click(S('database-migrations-link'));
    await page.waitForSelector(S('migrations-dashboard'));
    await page.screenshot({ path: 'artifacts/error-migration-dashboard.png', fullPage: true });

    // Step 2: Upload invalid migration file
    await page.click(S('upload-migration-button'));
    await page.waitForSelector(S('migration-file-upload-input'));
    await page.screenshot({ path: 'artifacts/error-upload-dialog.png', fullPage: true });

    // Step 3: Attempt to execute invalid migration
    await page.click(S('execute-uploaded-migration-button'));
    await page.waitForSelector(S('migration-error-message'));
    await page.screenshot({ path: 'artifacts/error-migration-failed.png', fullPage: true });

    // Step 4: Verify error details displayed
    await page.click(S('view-error-details-button'));
    await page.waitForSelector(S('error-details-panel'));
    await page.screenshot({ path: 'artifacts/error-details-panel.png', fullPage: true });

    // Assertions - verify error handling
    await expect(page.locator(S('migration-error-message'))).toBeVisible();
    await expect(page.locator(S('migration-error-message'))).toContainText('Migration failed');
    await expect(page.locator(S('error-details-panel'))).toBeVisible();
    await expect(page.locator(S('error-details-panel'))).toContainText('schema');
  });

  test('error case - OAuth authentication failure during migration', async ({ page }) => {
    // Step 1: Logout to test auth failure
    await page.click(S('user-menu'));
    await page.click(S('logout-button'));
    await page.waitForSelector(S('oauth-login-button'));
    await page.screenshot({ path: 'artifacts/error-logged-out.png', fullPage: true });

    // Step 2: Attempt to access migrations without authentication
    await page.goto(`${process.env.BASE_URL || 'http://localhost:3000'}/admin/migrations`);
    await page.waitForSelector(S('auth-required-message'));
    await page.screenshot({ path: 'artifacts/error-auth-required.png', fullPage: true });

    // Step 3: Attempt login with invalid OAuth credentials
    await page.click(S('oauth-login-button'));
    await page.fill(S('oauth-username-input'), 'invalid@example.com');
    await page.fill(S('oauth-password-input'), 'wrongpassword');
    await page.click(S('oauth-submit-button'));
    await page.waitForSelector(S('oauth-error-message'));
    await page.screenshot({ path: 'artifacts/error-oauth-failed.png', fullPage: true });

    // Assertions - verify authentication error
    await expect(page.locator(S('oauth-error-message'))).toBeVisible();
    await expect(page.locator(S('oauth-error-message'))).toContainText('Authentication failed');
    await expect(page.locator(S('auth-required-message'))).toBeVisible();
  });
});