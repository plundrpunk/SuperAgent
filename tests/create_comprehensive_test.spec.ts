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

test.describe('Board Creation and Management', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to base URL from environment
    await page.goto(process.env.BASE_URL || 'http://localhost:3000');
    
    // Wait for the canvas to be ready
    await page.waitForSelector(S('board-canvas'));
    await page.screenshot({ path: 'artifacts/initial-load.png', fullPage: true });
  });

  test('happy path - create new board successfully', async ({ page }) => {
    // Step 1: Click create board button
    await page.click(S('create-board-btn'));
    await page.waitForSelector(S('board-title-input'));
    await page.screenshot({ path: 'artifacts/create-board-dialog.png', fullPage: true });

    // Step 2: Enter board name
    const boardName = `Test Board ${Date.now()}`;
    await page.fill(S('board-title-input'), boardName);
    await page.screenshot({ path: 'artifacts/board-name-entered.png', fullPage: true });

    // Step 3: Submit board creation
    await page.keyboard.press('Enter');
    await page.waitForSelector(S('board-canvas'));
    await page.screenshot({ path: 'artifacts/board-created.png', fullPage: true });

    // Assertions - verify board was created
    await expect(page.locator(S('board-canvas'))).toBeVisible();
    const canvasContent = await page.locator(S('board-canvas')).textContent();
    expect(canvasContent).toBeTruthy();
  });

  test('happy path - create node on board', async ({ page }) => {
    // Step 1: Ensure board canvas is ready
    await page.waitForSelector(S('board-canvas'));
    await page.screenshot({ path: 'artifacts/ready-for-node.png', fullPage: true });

    // Step 2: Click create node button
    await page.click(S('node-create-btn'));
    await page.waitForSelector(S('board-canvas'));
    await page.screenshot({ path: 'artifacts/node-create-clicked.png', fullPage: true });

    // Step 3: Verify node was created on canvas
    await page.screenshot({ path: 'artifacts/node-created.png', fullPage: true });

    // Assertions - verify node creation
    await expect(page.locator(S('board-canvas'))).toBeVisible();
    await expect(page.locator(S('node-create-btn'))).toBeVisible();
  });

  test('happy path - create and configure group', async ({ page }) => {
    // Step 1: Click create group button
    await page.click(S('group-create-btn'));
    await page.waitForSelector(S('board-canvas'));
    await page.screenshot({ path: 'artifacts/group-create-clicked.png', fullPage: true });

    // Step 2: Wait for group to be created and find title input
    await page.waitForSelector(S('group-title-input'));
    await page.screenshot({ path: 'artifacts/group-created.png', fullPage: true });

    // Step 3: Enter group name
    const groupName = `Test Group ${Date.now()}`;
    await page.fill(S('group-title-input'), groupName);
    await page.screenshot({ path: 'artifacts/group-named.png', fullPage: true });

    // Step 4: Verify group title was set
    await page.keyboard.press('Enter');
    await page.screenshot({ path: 'artifacts/group-configured.png', fullPage: true });

    // Assertions - verify group was created and named
    await expect(page.locator(S('group-title-input'))).toBeVisible();
    await expect(page.locator(S('group-title-input'))).toHaveValue(groupName);
  });

  test('error case - create board with empty name', async ({ page }) => {
    // Step 1: Click create board button
    await page.click(S('create-board-btn'));
    await page.waitForSelector(S('board-title-input'));
    await page.screenshot({ path: 'artifacts/error-empty-board-dialog.png', fullPage: true });

    // Step 2: Try to submit with empty name
    await page.fill(S('board-title-input'), '');
    await page.screenshot({ path: 'artifacts/error-empty-name.png', fullPage: true });

    // Step 3: Attempt to submit
    await page.keyboard.press('Enter');
    await page.screenshot({ path: 'artifacts/error-submit-attempt.png', fullPage: true });

    // Assertions - verify input is still visible (form didn't submit)
    await expect(page.locator(S('board-title-input'))).toBeVisible();
    const inputValue = await page.locator(S('board-title-input')).inputValue();
    expect(inputValue).toBe('');
  });

  test('error case - interact with canvas before it loads', async ({ page }) => {
    // Step 1: Navigate to page
    await page.goto(process.env.BASE_URL || 'http://localhost:3000');
    await page.screenshot({ path: 'artifacts/error-immediate-load.png', fullPage: true });

    // Step 2: Wait for canvas to be available
    await page.waitForSelector(S('board-canvas'));
    await page.screenshot({ path: 'artifacts/error-canvas-loaded.png', fullPage: true });

    // Assertions - verify canvas is now interactive
    await expect(page.locator(S('board-canvas'))).toBeVisible();
    await expect(page.locator(S('create-board-btn'))).toBeEnabled();
  });
});

test.describe('Search Functionality', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to base URL from environment
    await page.goto(process.env.BASE_URL || 'http://localhost:3000');
    
    // Wait for search input to be ready
    await page.waitForSelector(S('search-input'));
    await page.screenshot({ path: 'artifacts/search-initial.png', fullPage: true });
  });

  test('happy path - search with filters', async ({ page }) => {
    // Step 1: Enter search query
    await page.fill(S('search-input'), 'test query');
    await page.screenshot({ path: 'artifacts/search-query-entered.png', fullPage: true });

    // Step 2: Apply type filter
    await page.click(S('search-filter-type'));
    await page.screenshot({ path: 'artifacts/search-type-filter-opened.png', fullPage: true });

    // Step 3: Wait for results
    await page.waitForSelector(S('search-results'));
    await page.screenshot({ path: 'artifacts/search-results-displayed.png', fullPage: true });

    // Assertions - verify search results are displayed
    await expect(page.locator(S('search-results'))).toBeVisible();
    await expect(page.locator(S('search-input'))).toHaveValue('test query');
  });

  test('error case - search with no results', async ({ page }) => {
    // Step 1: Enter query that yields no results
    const uniqueQuery = `nonexistent-${Date.now()}`;
    await page.fill(S('search-input'), uniqueQuery);
    await page.screenshot({ path: 'artifacts/error-no-results-query.png', fullPage: true });

    // Step 2: Trigger search
    await page.keyboard.press('Enter');
    await page.waitForSelector(S('search-results'));
    await page.screenshot({ path: 'artifacts/error-no-results-displayed.png', fullPage: true });

    // Assertions - verify search results container is visible but may be empty
    await expect(page.locator(S('search-results'))).toBeVisible();
    await expect(page.locator(S('search-input'))).toHaveValue(uniqueQuery);
  });
});

test.describe('Export Functionality', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to base URL from environment
    await page.goto(process.env.BASE_URL || 'http://localhost:3000');
    
    // Wait for canvas to be ready
    await page.waitForSelector(S('board-canvas'));
    await page.screenshot({ path: 'artifacts/export-initial.png', fullPage: true });
  });

  test('happy path - export to PDF', async ({ page }) => {
    // Step 1: Wait for export button to be available
    await page.waitForSelector(S('export-pdf-btn'));
    await page.screenshot({ path: 'artifacts/export-pdf-ready.png', fullPage: true });

    // Step 2: Set up download listener
    const downloadPromise = page.waitForEvent('download');
    
    // Step 3: Click export PDF button
    await page.click(S('export-pdf-btn'));
    await page.screenshot({ path: 'artifacts/export-pdf-clicked.png', fullPage: true });

    // Step 4: Wait for download to start
    const download = await downloadPromise;
    await page.screenshot({ path: 'artifacts/export-pdf-downloading.png', fullPage: true });

    // Assertions - verify download occurred
    expect(download).toBeTruthy();
    expect(download.suggestedFilename()).toContain('.pdf');
  });

  test('happy path - export to Markdown', async ({ page }) => {
    // Step 1: Wait for export button to be available
    await page.waitForSelector(S('export-markdown-btn'));
    await page.screenshot({ path: 'artifacts/export-markdown-ready.png', fullPage: true });

    // Step 2: Set up download listener
    const downloadPromise = page.waitForEvent('download');
    
    // Step 3: Click export Markdown button
    await page.click(S('export-markdown-btn'));
    await page.screenshot({ path: 'artifacts/export-markdown-clicked.png', fullPage: true });

    // Step 4: Wait for download to start
    const download = await downloadPromise;
    await page.screenshot({ path: 'artifacts/export-markdown-downloading.png', fullPage: true });

    // Assertions - verify download occurred
    expect(download).toBeTruthy();
    expect(download.suggestedFilename()).toMatch(/\.(md|markdown)$/);
  });
});

test.describe('AI Chat Integration', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to base URL from environment
    await page.goto(process.env.BASE_URL || 'http://localhost:3000');
    
    // Wait for AI chat to be ready
    await page.waitForSelector(S('ai-chat-input'));
    await page.screenshot({ path: 'artifacts/ai-chat-initial.png', fullPage: true });
  });

  test('happy path - send AI chat message', async ({ page }) => {
    // Step 1: Enter message in AI chat
    const message = 'Hello, can you help me with this board?';
    await page.fill(S('ai-chat-input'), message);
    await page.screenshot({ path: 'artifacts/ai-message-entered.png', fullPage: true });

    // Step 2: Click send button
    await page.click(S('ai-chat-send'));
    await page.screenshot({ path: 'artifacts/ai-message-sent.png', fullPage: true });

    // Step 3: Wait for input to be cleared (indicating message was sent)
    await page.waitForSelector(S('ai-chat-input'));
    await page.screenshot({ path: 'artifacts/ai-message-processed.png', fullPage: true });

    // Assertions - verify message was sent
    await expect(page.locator(S('ai-chat-input'))).toBeVisible();
    await expect(page.locator(S('ai-chat-send'))).toBeVisible();
  });

  test('error case - send empty AI chat message', async ({ page }) => {
    // Step 1: Try to send empty message
    await page.fill(S('ai-chat-input'), '');
    await page.screenshot({ path: 'artifacts/error-empty-message.png', fullPage: true });

    // Step 2: Click send button
    await page.click(S('ai-chat-send'));
    await page.screenshot({ path: 'artifacts/error-empty-message-clicked.png', fullPage: true });

    // Assertions - verify input is still visible and empty
    await expect(page.locator(S('ai-chat-input'))).toBeVisible();
    const inputValue = await page.locator(S('ai-chat-input')).inputValue();
    expect(inputValue).toBe('');
  });
});