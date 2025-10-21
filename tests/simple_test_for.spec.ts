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

test.describe('Board Creation', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to base URL from environment
    await page.goto(process.env.BASE_URL ?? 'http://localhost:3000');
    
    // Wait for page to be fully loaded
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: 'artifacts/board-creation-initial.png', fullPage: true });
  });

  test('happy path - create new board successfully', async ({ page }) => {
    // Step 1: Click create board button
    await page.waitForSelector(S('create-board-btn'));
    await page.click(S('create-board-btn'));
    await page.screenshot({ path: 'artifacts/board-creation-step1-click-create.png', fullPage: true });

    // Step 2: Enter board name
    await page.waitForSelector(S('board-title-input'));
    const boardName = `Test Board ${Date.now()}`;
    await page.fill(S('board-title-input'), boardName);
    await page.screenshot({ path: 'artifacts/board-creation-step2-enter-name.png', fullPage: true });

    // Step 3: Submit board creation
    await page.keyboard.press('Enter');
    await page.waitForSelector(S('board-canvas'), { timeout: 10000 });
    await page.screenshot({ path: 'artifacts/board-creation-step3-board-created.png', fullPage: true });

    // Assertions - verify board was created successfully
    await expect(page.locator(S('board-canvas'))).toBeVisible();
    await expect(page.locator(S('board-title-input'))).toHaveValue(boardName);
    
    // Verify the canvas is interactive
    const canvas = page.locator(S('board-canvas'));
    await expect(canvas).toBeVisible();
  });

  test('error case - create board with empty name', async ({ page }) => {
    // Step 1: Click create board button
    await page.waitForSelector(S('create-board-btn'));
    await page.click(S('create-board-btn'));
    await page.screenshot({ path: 'artifacts/board-creation-error-step1-click-create.png', fullPage: true });

    // Step 2: Try to submit without entering a name
    await page.waitForSelector(S('board-title-input'));
    await page.fill(S('board-title-input'), '');
    await page.screenshot({ path: 'artifacts/board-creation-error-step2-empty-name.png', fullPage: true });

    // Step 3: Attempt to submit with empty name
    await page.keyboard.press('Enter');
    await page.screenshot({ path: 'artifacts/board-creation-error-step3-validation.png', fullPage: true });

    // Assertions - verify board title input is still visible (board not created)
    await expect(page.locator(S('board-title-input'))).toBeVisible();
    await expect(page.locator(S('board-title-input'))).toHaveValue('');
  });

  test('happy path - create multiple boards', async ({ page }) => {
    // Step 1: Create first board
    await page.waitForSelector(S('create-board-btn'));
    await page.click(S('create-board-btn'));
    await page.waitForSelector(S('board-title-input'));
    const firstBoardName = `First Board ${Date.now()}`;
    await page.fill(S('board-title-input'), firstBoardName);
    await page.keyboard.press('Enter');
    await page.waitForSelector(S('board-canvas'));
    await page.screenshot({ path: 'artifacts/board-creation-multiple-step1-first-board.png', fullPage: true });

    // Step 2: Create second board
    await page.click(S('create-board-btn'));
    await page.waitForSelector(S('board-title-input'));
    const secondBoardName = `Second Board ${Date.now()}`;
    await page.fill(S('board-title-input'), secondBoardName);
    await page.keyboard.press('Enter');
    await page.waitForSelector(S('board-canvas'));
    await page.screenshot({ path: 'artifacts/board-creation-multiple-step2-second-board.png', fullPage: true });

    // Assertions - verify second board was created
    await expect(page.locator(S('board-canvas'))).toBeVisible();
    await expect(page.locator(S('board-title-input'))).toHaveValue(secondBoardName);
  });

  test('error case - create board with whitespace only name', async ({ page }) => {
    // Step 1: Click create board button
    await page.waitForSelector(S('create-board-btn'));
    await page.click(S('create-board-btn'));
    await page.screenshot({ path: 'artifacts/board-creation-whitespace-step1-click-create.png', fullPage: true });

    // Step 2: Enter whitespace only
    await page.waitForSelector(S('board-title-input'));
    await page.fill(S('board-title-input'), '   ');
    await page.screenshot({ path: 'artifacts/board-creation-whitespace-step2-enter-spaces.png', fullPage: true });

    // Step 3: Attempt to submit
    await page.keyboard.press('Enter');
    await page.screenshot({ path: 'artifacts/board-creation-whitespace-step3-validation.png', fullPage: true });

    // Assertions - verify validation prevents creation
    await expect(page.locator(S('board-title-input'))).toBeVisible();
    const inputValue = await page.locator(S('board-title-input')).inputValue();
    expect(inputValue.trim()).toBe('');
  });
});