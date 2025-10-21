/// <reference types="node" />
import { test, expect } from '@playwright/test';

/**
 * Test configuration - enable screenshots, videos, and traces
 */
test.use({
  screenshot: 'on',
  video: 'retain-on-failure',
  trace: 'retain-on-failure',
});

test.describe('Board Management', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to base URL and handle authentication
    await page.goto(process.env.BASE_URL || 'http://host.docker.internal:5175');
    
    // Check if we need to login
    const emailInput = page.locator('input[type="email"]');
    if (await emailInput.isVisible({ timeout: 3000 }).catch(() => false)) {
      await emailInput.fill(process.env.TEST_EMAIL || '');
      await page.locator('input[type="password"]').fill(process.env.TEST_PASSWORD || '');
      await page.locator('button[type="submit"]').click();
      await page.waitForURL(/\/(boards|dashboard)?/, { timeout: 10000 });
    }
    
    await page.screenshot({ path: 'artifacts/beforeEach-dashboard.png', fullPage: true });
  });

  test('happy path - create board, edit name, delete board, verify persistence', async ({ page }) => {
    // Step 1: Create a new board
    await page.click('.vf-board-glow-button');
    await page.waitForSelector('input#boardName', { state: 'visible' });
    await page.screenshot({ path: 'artifacts/create-board-modal.png', fullPage: true });

    // Step 2: Enter board name and submit
    const boardName = `Test Board ${Date.now()}`;
    await page.fill('input#boardName', boardName);
    await page.screenshot({ path: 'artifacts/board-name-entered.png', fullPage: true });
    
    await page.getByRole('button', { name: /create|submit/i }).click();
    await page.waitForURL(/\/board\/[a-zA-Z0-9-]+/, { timeout: 10000 });
    await page.waitForSelector('.vf-board-canvas', { state: 'visible' });
    await page.screenshot({ path: 'artifacts/board-created.png', fullPage: true });

    // Assertions - Board created successfully
    await expect(page.locator('.vf-board-canvas')).toBeVisible();
    const currentUrl = page.url();
    expect(currentUrl).toMatch(/\/board\/[a-zA-Z0-9-]+/);

    // Step 3: Edit board name
    await page.getByText(/edit|settings/).first().click();
    await page.waitForSelector('input#boardName', { state: 'visible' });
    await page.screenshot({ path: 'artifacts/edit-board-modal.png', fullPage: true });

    const updatedBoardName = `${boardName} - Updated`;
    await page.fill('input#boardName', updatedBoardName);
    await page.screenshot({ path: 'artifacts/board-name-updated.png', fullPage: true });
    
    await page.getByRole('button', { name: /save|update/i }).click();
    await page.waitForSelector('input#boardName', { state: 'hidden', timeout: 5000 });
    await page.screenshot({ path: 'artifacts/board-name-saved.png', fullPage: true });

    // Assertions - Board name updated
    await expect(page.locator('h1, h2, .board-title')).toContainText(updatedBoardName);

    // Step 4: Verify persistence - reload page
    await page.reload();
    await page.waitForSelector('.vf-board-canvas', { state: 'visible' });
    await page.screenshot({ path: 'artifacts/board-after-reload.png', fullPage: true });

    // Assertions - Board persists after reload
    await expect(page.locator('.vf-board-canvas')).toBeVisible();
    await expect(page.locator('h1, h2, .board-title')).toContainText(updatedBoardName);
    expect(page.url()).toBe(currentUrl);

    // Step 5: Navigate back to dashboard
    await page.goto(process.env.BASE_URL || 'http://host.docker.internal:5175');
    await page.waitForSelector('.vf-dashboard-grid', { state: 'visible', timeout: 10000 });
    await page.screenshot({ path: 'artifacts/back-to-dashboard.png', fullPage: true });

    // Assertions - Board appears in dashboard
    await expect(page.locator('.vf-dashboard-card').filter({ hasText: updatedBoardName })).toBeVisible();

    // Step 6: Delete the board
    const boardCard = page.locator('.vf-dashboard-card').filter({ hasText: updatedBoardName });
    await boardCard.getByRole('button', { name: /delete|remove/i }).click();
    await page.getByRole('button', { name: /confirm|delete/i }).click();
    await page.waitForTimeout(2000);
    await page.screenshot({ path: 'artifacts/board-deleted.png', fullPage: true });

    // Assertions - Board deleted successfully
    await expect(page.locator('.vf-dashboard-card').filter({ hasText: updatedBoardName })).not.toBeVisible();

    // Step 7: Verify deletion persists after reload
    await page.reload();
    await page.waitForSelector('.vf-dashboard-grid', { state: 'visible' });
    await page.screenshot({ path: 'artifacts/dashboard-after-delete-reload.png', fullPage: true });

    // Assertions - Board remains deleted after reload
    await expect(page.locator('.vf-dashboard-card').filter({ hasText: updatedBoardName })).not.toBeVisible();
  });

  test('error case - create board with empty name', async ({ page }) => {
    // Step 1: Open create board modal
    await page.click('.vf-board-glow-button');
    await page.waitForSelector('input#boardName', { state: 'visible' });
    await page.screenshot({ path: 'artifacts/error-create-board-modal.png', fullPage: true });

    // Step 2: Try to submit without entering a name
    await page.getByRole('button', { name: /create|submit/i }).click();
    await page.screenshot({ path: 'artifacts/error-empty-name-submit.png', fullPage: true });

    // Assertions - Error message displayed or submit button disabled
    const errorMessage = page.locator('.error, .vf-error, [class*="error"]');
    const submitButton = page.getByRole('button', { name: /create|submit/i });
    
    // Either an error message should be visible or the button should be disabled
    const hasError = await errorMessage.isVisible({ timeout: 2000 }).catch(() => false);
    const isDisabled = await submitButton.isDisabled().catch(() => false);
    
    expect(hasError || isDisabled).toBeTruthy();
    
    // Step 3: Verify we're still on dashboard (not navigated away)
    const currentUrl = page.url();
    expect(currentUrl).not.toMatch(/\/board\/[a-zA-Z0-9-]+/);
    
    // Assertions - Modal should still be visible
    await expect(page.locator('input#boardName')).toBeVisible();
  });

  test('error case - cancel board creation', async ({ page }) => {
    // Step 1: Open create board modal
    await page.click('.vf-board-glow-button');
    await page.waitForSelector('input#boardName', { state: 'visible' });
    await page.screenshot({ path: 'artifacts/error-cancel-modal-open.png', fullPage: true });

    // Step 2: Enter board name but cancel
    await page.fill('input#boardName', 'Board to Cancel');
    await page.screenshot({ path: 'artifacts/error-cancel-name-entered.png', fullPage: true });

    await page.getByRole('button', { name: /cancel|close/i }).click();
    await page.waitForSelector('input#boardName', { state: 'hidden', timeout: 5000 });
    await page.screenshot({ path: 'artifacts/error-cancel-modal-closed.png', fullPage: true });

    // Assertions - Modal closed and no board created
    await expect(page.locator('input#boardName')).not.toBeVisible();
    
    // Verify we're still on dashboard
    const currentUrl = page.url();
    expect(currentUrl).not.toMatch(/\/board\/[a-zA-Z0-9-]+/);
    
    // Verify no new board with that name exists
    await expect(page.locator('.vf-dashboard-card').filter({ hasText: 'Board to Cancel' })).not.toBeVisible();
  });
});