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
  screenshot: 'only-on-failure',
  video: 'retain-on-failure',
  trace: 'retain-on-failure',
});

test.describe('Board Management', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to base URL from environment
    await page.goto(process.env.BASE_URL || 'http://localhost:3000');
    await page.waitForSelector(S('board-canvas'));
  });

  test('happy path - create, edit, and delete board', async ({ page }) => {
    // Step 1: Create new board
    await page.click(S('create-board-btn'));
    await page.waitForSelector(S('board-title-input'));
    await page.screenshot({ path: 'artifacts/board-create-dialog.png', fullPage: true });

    // Step 2: Enter board name and save
    const boardName = `Test Board ${Date.now()}`;
    await page.fill(S('board-title-input'), boardName);
    await page.screenshot({ path: 'artifacts/board-name-entered.png', fullPage: true });
    
    await page.click(S('board-save-btn'));
    await page.waitForSelector(S('board-canvas'));
    await page.screenshot({ path: 'artifacts/board-created.png', fullPage: true });

    // Assertions - Verify board was created
    await expect(page.locator(S('board-title-display'))).toBeVisible();
    await expect(page.locator(S('board-title-display'))).toContainText(boardName);

    // Step 3: Edit board name
    await page.click(S('board-edit-btn'));
    await page.waitForSelector(S('board-title-input'));
    await page.screenshot({ path: 'artifacts/board-edit-dialog.png', fullPage: true });

    const updatedBoardName = `Updated Board ${Date.now()}`;
    await page.fill(S('board-title-input'), updatedBoardName);
    await page.screenshot({ path: 'artifacts/board-name-updated.png', fullPage: true });
    
    await page.click(S('board-save-btn'));
    await page.waitForSelector(S('board-canvas'));
    await page.screenshot({ path: 'artifacts/board-edited.png', fullPage: true });

    // Assertions - Verify board was updated
    await expect(page.locator(S('board-title-display'))).toBeVisible();
    await expect(page.locator(S('board-title-display'))).toContainText(updatedBoardName);

    // Step 4: Delete board
    await page.click(S('board-delete-btn'));
    await page.waitForSelector(S('board-delete-confirm-dialog'));
    await page.screenshot({ path: 'artifacts/board-delete-confirm.png', fullPage: true });

    await page.click(S('board-delete-confirm-btn'));
    await page.waitForSelector(S('board-deleted-message'));
    await page.screenshot({ path: 'artifacts/board-deleted.png', fullPage: true });

    // Assertions - Verify board was deleted
    await expect(page.locator(S('board-deleted-message'))).toBeVisible();
    await expect(page.locator(S('board-deleted-message'))).toContainText('deleted');
  });

  test('error case - create board with empty name', async ({ page }) => {
    // Step 1: Open create board dialog
    await page.click(S('create-board-btn'));
    await page.waitForSelector(S('board-title-input'));
    await page.screenshot({ path: 'artifacts/error-create-dialog.png', fullPage: true });

    // Step 2: Try to save without entering a name
    await page.click(S('board-save-btn'));
    await page.waitForSelector(S('board-error-message'));
    await page.screenshot({ path: 'artifacts/error-empty-name.png', fullPage: true });

    // Assertions - Verify error message is shown
    await expect(page.locator(S('board-error-message'))).toBeVisible();
    await expect(page.locator(S('board-error-message'))).toContainText('required');
  });

  test('error case - cancel board deletion', async ({ page }) => {
    // Step 1: Create a board first
    await page.click(S('create-board-btn'));
    await page.waitForSelector(S('board-title-input'));
    
    const boardName = `Cancel Delete Test ${Date.now()}`;
    await page.fill(S('board-title-input'), boardName);
    await page.click(S('board-save-btn'));
    await page.waitForSelector(S('board-canvas'));
    await page.screenshot({ path: 'artifacts/cancel-board-created.png', fullPage: true });

    // Step 2: Open delete confirmation dialog
    await page.click(S('board-delete-btn'));
    await page.waitForSelector(S('board-delete-confirm-dialog'));
    await page.screenshot({ path: 'artifacts/cancel-delete-dialog.png', fullPage: true });

    // Step 3: Cancel deletion
    await page.click(S('board-delete-cancel-btn'));
    await page.waitForSelector(S('board-canvas'));
    await page.screenshot({ path: 'artifacts/cancel-deletion-cancelled.png', fullPage: true });

    // Assertions - Verify board still exists
    await expect(page.locator(S('board-title-display'))).toBeVisible();
    await expect(page.locator(S('board-title-display'))).toContainText(boardName);
  });

  test('happy path - create multiple boards and verify list', async ({ page }) => {
    // Step 1: Create first board
    await page.click(S('create-board-btn'));
    await page.waitForSelector(S('board-title-input'));
    
    const firstBoardName = `First Board ${Date.now()}`;
    await page.fill(S('board-title-input'), firstBoardName);
    await page.click(S('board-save-btn'));
    await page.waitForSelector(S('board-canvas'));
    await page.screenshot({ path: 'artifacts/multi-first-board.png', fullPage: true });

    // Step 2: Create second board
    await page.click(S('create-board-btn'));
    await page.waitForSelector(S('board-title-input'));
    
    const secondBoardName = `Second Board ${Date.now()}`;
    await page.fill(S('board-title-input'), secondBoardName);
    await page.click(S('board-save-btn'));
    await page.waitForSelector(S('board-canvas'));
    await page.screenshot({ path: 'artifacts/multi-second-board.png', fullPage: true });

    // Step 3: Open board list
    await page.click(S('board-list-btn'));
    await page.waitForSelector(S('board-list-container'));
    await page.screenshot({ path: 'artifacts/multi-board-list.png', fullPage: true });

    // Assertions - Verify both boards appear in list
    await expect(page.locator(S('board-list-container'))).toBeVisible();
    const boardListText = await page.locator(S('board-list-container')).textContent();
    expect(boardListText).toContain(firstBoardName);
    expect(boardListText).toContain(secondBoardName);
  });
});