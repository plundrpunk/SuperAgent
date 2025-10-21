import { test, expect } from '@playwright/test';

/**
 * Test configuration - enable screenshots, videos, and traces
 */
test.use({
  screenshot: 'on',
  video: 'retain-on-failure',
  trace: 'retain-on-failure',
});

test.describe('Export Functionality', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to base URL and handle authentication
    await page.goto(process.env.BASE_URL || 'http://localhost:3000');
    
    // Step 1: Login if needed
    const emailInput = page.locator('input[type="email"]');
    if (await emailInput.isVisible({ timeout: 3000 }).catch(() => false)) {
      await emailInput.fill(process.env.TEST_EMAIL || 'test@example.com');
      await page.locator('input[type="password"]').fill(process.env.TEST_PASSWORD || 'password');
      await page.locator('button[type="submit"]').click();
      await page.waitForSelector('.vf-board-glow-button, .vf-dashboard-grid', { timeout: 10000 });
      await page.screenshot({ path: 'artifacts/auth-complete.png', fullPage: true });
    }
    
    // Step 2: Create a new board for testing
    await page.getByText('Create New Board').click();
    await page.waitForSelector('input#boardName', { timeout: 5000 });
    await page.screenshot({ path: 'artifacts/board-modal.png', fullPage: true });
    
    await page.locator('input#boardName').fill('Export Test Board');
    await page.locator('button[type="submit"]').click();
    await page.waitForSelector('.vf-board-canvas', { timeout: 10000 });
    await page.screenshot({ path: 'artifacts/board-created.png', fullPage: true });
  });

  test('happy path - export PDF and verify download', async ({ page }) => {
    // Step 1: Add some content to the board
    await page.waitForSelector('.vf-toolbar-row button', { timeout: 5000 });
    const textButton = page.locator('.vf-toolbar-row button').filter({ hasText: 'TEXT' }).or(
      page.locator('.vf-toolbar-row button').first()
    );
    await textButton.click();
    await page.screenshot({ path: 'artifacts/content-added.png', fullPage: true });
    
    // Step 2: Wait for export button and click PDF export
    const downloadPromise = page.waitForEvent('download');
    await page.getByText('Export').click();
    await page.screenshot({ path: 'artifacts/pdf-export-clicked.png', fullPage: true });
    
    // Step 3: Verify PDF download
    const download = await downloadPromise;
    await page.screenshot({ path: 'artifacts/pdf-download-complete.png', fullPage: true });
    
    // Assertions
    await expect(download.suggestedFilename()).toContain('.pdf');
    const downloadPath = await download.path();
    await expect(downloadPath).toBeTruthy();
  });

  test('happy path - export Markdown and verify download', async ({ page }) => {
    // Step 1: Add some content to the board
    await page.waitForSelector('.vf-toolbar-row button', { timeout: 5000 });
    const textButton = page.locator('.vf-toolbar-row button').filter({ hasText: 'TEXT' }).or(
      page.locator('.vf-toolbar-row button').first()
    );
    await textButton.click();
    await page.screenshot({ path: 'artifacts/markdown-content-added.png', fullPage: true });
    
    // Step 2: Wait for export button and click Markdown export
    const downloadPromise = page.waitForEvent('download');
    await page.getByText('Export').click();
    await page.screenshot({ path: 'artifacts/markdown-export-clicked.png', fullPage: true });
    
    // Step 3: Verify Markdown download
    const download = await downloadPromise;
    await page.screenshot({ path: 'artifacts/markdown-download-complete.png', fullPage: true });
    
    // Assertions
    await expect(download.suggestedFilename()).toMatch(/\.(md|markdown)$/);
    const downloadPath = await download.path();
    await expect(downloadPath).toBeTruthy();
  });

  test('edge case - export with empty board', async ({ page }) => {
    // Step 1: Verify we're on an empty board (no content added)
    await page.waitForSelector('.vf-board-canvas', { timeout: 5000 });
    await page.screenshot({ path: 'artifacts/empty-board.png', fullPage: true });
    
    // Step 2: Attempt to export PDF from empty board
    await page.getByText('Export').click();
    await page.screenshot({ path: 'artifacts/empty-pdf-export-clicked.png', fullPage: true });
    
    // Step 3: Wait for either download or error message
    const errorMessage = page.locator('text=/empty|no content|nothing to export/i');
    const hasError = await errorMessage.isVisible({ timeout: 3000 }).catch(() => false);
    
    if (hasError) {
      await page.screenshot({ path: 'artifacts/empty-board-error.png', fullPage: true });
      await expect(errorMessage).toBeVisible();
      await expect(errorMessage).toContainText(/empty|no content|nothing/i);
    } else {
      // If export proceeds anyway, verify download
      const downloadPromise = page.waitForEvent('download', { timeout: 5000 });
      const download = await downloadPromise;
      await page.screenshot({ path: 'artifacts/empty-board-export-complete.png', fullPage: true });
      await expect(download.suggestedFilename()).toContain('.pdf');
      const downloadPath = await download.path();
      await expect(downloadPath).toBeTruthy();
    }
  });

  test('edge case - export markdown with empty board', async ({ page }) => {
    // Step 1: Verify we're on an empty board
    await page.waitForSelector('.vf-board-canvas', { timeout: 5000 });
    await page.screenshot({ path: 'artifacts/empty-board-markdown.png', fullPage: true });
    
    // Step 2: Attempt to export Markdown from empty board
    await page.getByText('Export').click();
    await page.screenshot({ path: 'artifacts/empty-markdown-export-clicked.png', fullPage: true });
    
    // Step 3: Wait for either download or error message
    const errorMessage = page.locator('text=/empty|no content|nothing to export/i');
    const hasError = await errorMessage.isVisible({ timeout: 3000 }).catch(() => false);
    
    if (hasError) {
      await page.screenshot({ path: 'artifacts/empty-markdown-error.png', fullPage: true });
      await expect(errorMessage).toBeVisible();
      await expect(errorMessage).toContainText(/empty|no content|nothing/i);
    } else {
      // If export proceeds anyway, verify download
      const downloadPromise = page.waitForEvent('download', { timeout: 5000 });
      const download = await downloadPromise;
      await page.screenshot({ path: 'artifacts/empty-markdown-export-complete.png', fullPage: true });
      await expect(download.suggestedFilename()).toMatch(/\.(md|markdown)$/);
      const downloadPath = await download.path();
      await expect(downloadPath).toBeTruthy();
    }
  });
});