import { test, expect } from '@playwright/test';
import * as fs from 'fs';

/**
 * Selector helper - ALWAYS use data-testid attributes
 * Example: await page.click(S('login-button'))
 */
const S = (id: string) => `[data-testid="${id}"]`;

test.describe('Board Creation', () => {
  test.beforeEach(async ({ page }) => {
    // Ensure artifacts directory exists
    if (!fs.existsSync('artifacts')) {
      fs.mkdirSync('artifacts', { recursive: true });
    }
    
    // Navigate to base URL from environment
    await page.goto(process.env.BASE_URL || 'http://localhost:3000');
    await page.waitForLoadState('networkidle');
  });

  test('happy path - create board with valid name', async ({ page }) => {
    // Step 1: Click create board button
    await page.waitForSelector(S('create-board-btn'));
    await page.click(S('create-board-btn'));
    await page.screenshot({ path: 'artifacts/board-creation-step1.png', fullPage: true });

    // Step 2: Enter board name
    await page.waitForSelector(S('board-title-input'));
    const boardName = `Test Board ${Date.now()}`;
    await page.fill(S('board-title-input'), boardName);
    await page.screenshot({ path: 'artifacts/board-creation-step2.png', fullPage: true });

    // Step 3: Submit board creation
    await page.keyboard.press('Enter');
    await page.waitForSelector(S('board-canvas'));
    await page.screenshot({ path: 'artifacts/board-creation-step3.png', fullPage: true });

    // Assertions - verify board was created and canvas is visible
    await expect(page.locator(S('board-canvas'))).toBeVisible();
    await expect(page.locator(S('board-title-input'))).toHaveValue(boardName);
  });

  test('happy path - create board with long name', async ({ page }) => {
    // Step 1: Click create board button
    await page.waitForSelector(S('create-board-btn'));
    await page.click(S('create-board-btn'));
    await page.screenshot({ path: 'artifacts/board-long-name-step1.png', fullPage: true });

    // Step 2: Enter long board name
    await page.waitForSelector(S('board-title-input'));
    const longBoardName = 'This is a very long board name to test the maximum character limit and UI handling';
    await page.fill(S('board-title-input'), longBoardName);
    await page.screenshot({ path: 'artifacts/board-long-name-step2.png', fullPage: true });

    // Step 3: Submit board creation
    await page.keyboard.press('Enter');
    await page.waitForSelector(S('board-canvas'));
    await page.screenshot({ path: 'artifacts/board-long-name-step3.png', fullPage: true });

    // Assertions - verify board was created with long name
    await expect(page.locator(S('board-canvas'))).toBeVisible();
    await expect(page.locator(S('board-title-input'))).toBeVisible();
  });

  test('error case - create board with empty name', async ({ page }) => {
    // Step 1: Click create board button
    await page.waitForSelector(S('create-board-btn'));
    await page.click(S('create-board-btn'));
    await page.screenshot({ path: 'artifacts/board-empty-name-step1.png', fullPage: true });

    // Step 2: Leave board name empty and try to submit
    await page.waitForSelector(S('board-title-input'));
    await page.fill(S('board-title-input'), '');
    await page.screenshot({ path: 'artifacts/board-empty-name-step2.png', fullPage: true });

    // Step 3: Attempt to submit with empty name
    await page.keyboard.press('Enter');
    await page.screenshot({ path: 'artifacts/board-empty-name-step3.png', fullPage: true });

    // Assertions - verify empty name is handled (input should still be visible, canvas might not appear)
    await expect(page.locator(S('board-title-input'))).toBeVisible();
    await expect(page.locator(S('board-title-input'))).toHaveValue('');
  });

  test('error case - cancel board creation', async ({ page }) => {
    // Step 1: Click create board button
    await page.waitForSelector(S('create-board-btn'));
    await page.click(S('create-board-btn'));
    await page.screenshot({ path: 'artifacts/board-cancel-step1.png', fullPage: true });

    // Step 2: Enter board name
    await page.waitForSelector(S('board-title-input'));
    await page.fill(S('board-title-input'), 'Cancelled Board');
    await page.screenshot({ path: 'artifacts/board-cancel-step2.png', fullPage: true });

    // Step 3: Press Escape to cancel
    await page.keyboard.press('Escape');
    await page.screenshot({ path: 'artifacts/board-cancel-step3.png', fullPage: true });

    // Assertions - verify create button is still visible (board creation was cancelled)
    await expect(page.locator(S('create-board-btn'))).toBeVisible();
  });
});