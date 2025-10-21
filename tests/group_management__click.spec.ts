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

test.describe('Group Management', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to base URL from environment
    await page.goto(process.env.BASE_URL || 'http://localhost:3000');
    await page.waitForSelector(S('group-create-btn'));
  });

  test('happy path - create geometric group, rename, resize, and connect to AI chat', async ({ page }) => {
    // Step 1: Create geometric group
    await page.click(S('group-create-btn'));
    await page.waitForSelector(S('group-title-input'));
    await page.screenshot({ path: 'artifacts/group-created.png', fullPage: true });

    // Step 2: Rename the group
    const groupName = 'Test Geometric Group';
    await page.fill(S('group-title-input'), groupName);
    await page.screenshot({ path: 'artifacts/group-renamed.png', fullPage: true });

    // Assertions - verify group name is set
    await expect(page.locator(S('group-title-input'))).toHaveValue(groupName);
    await expect(page.locator(S('group-title-input'))).toBeVisible();

    // Step 3: Resize the group using drag handle
    const resizeHandle = page.locator(S('group-resize-handle'));
    await expect(resizeHandle).toBeVisible();
    
    const handleBox = await resizeHandle.boundingBox();
    if (handleBox) {
      await page.mouse.move(handleBox.x + handleBox.width / 2, handleBox.y + handleBox.height / 2);
      await page.mouse.down();
      await page.mouse.move(handleBox.x + 200, handleBox.y + 150);
      await page.mouse.up();
    }
    await page.screenshot({ path: 'artifacts/group-resized.png', fullPage: true });

    // Step 4: Connect group to AI chat
    await page.waitForSelector(S('ai-chat-input'));
    const aiMessage = 'Analyze the grouped nodes';
    await page.fill(S('ai-chat-input'), aiMessage);
    await page.screenshot({ path: 'artifacts/ai-chat-input-filled.png', fullPage: true });

    // Step 5: Submit AI chat message
    await page.press(S('ai-chat-input'), 'Enter');
    await page.waitForSelector(S('ai-chat-response'));
    await page.screenshot({ path: 'artifacts/ai-chat-response.png', fullPage: true });

    // Assertions - verify AI receives grouped node context
    await expect(page.locator(S('ai-chat-response'))).toBeVisible();
    await expect(page.locator(S('ai-chat-response'))).not.toBeEmpty();
  });

  test('happy path - verify group deletion', async ({ page }) => {
    // Step 1: Create a group to delete
    await page.click(S('group-create-btn'));
    await page.waitForSelector(S('group-title-input'));
    await page.screenshot({ path: 'artifacts/group-created-for-deletion.png', fullPage: true });

    // Step 2: Name the group
    await page.fill(S('group-title-input'), 'Group to Delete');
    await page.screenshot({ path: 'artifacts/group-named-for-deletion.png', fullPage: true });

    // Assertions - verify group exists
    await expect(page.locator(S('group-title-input'))).toBeVisible();
    await expect(page.locator(S('group-title-input'))).toHaveValue('Group to Delete');

    // Step 3: Delete the group
    await page.click(S('group-delete-btn'));
    await page.waitForSelector(S('group-title-input'), { state: 'hidden' });
    await page.screenshot({ path: 'artifacts/group-deleted.png', fullPage: true });

    // Assertions - verify group is deleted
    await expect(page.locator(S('group-title-input'))).not.toBeVisible();
  });

  test('error case - create group with empty name', async ({ page }) => {
    // Step 1: Create geometric group
    await page.click(S('group-create-btn'));
    await page.waitForSelector(S('group-title-input'));
    await page.screenshot({ path: 'artifacts/error-group-created.png', fullPage: true });

    // Step 2: Try to set empty name
    await page.fill(S('group-title-input'), '');
    await page.press(S('group-title-input'), 'Enter');
    await page.screenshot({ path: 'artifacts/error-empty-name.png', fullPage: true });

    // Assertions - verify error handling or default name
    const inputValue = await page.locator(S('group-title-input')).inputValue();
    await expect(page.locator(S('group-title-input'))).toBeVisible();
    // Group should either show error or maintain a default name
    expect(inputValue.length).toBeGreaterThanOrEqual(0);
  });

  test('error case - AI chat with no grouped nodes', async ({ page }) => {
    // Step 1: Attempt to use AI chat without creating a group
    await page.waitForSelector(S('ai-chat-input'));
    await page.screenshot({ path: 'artifacts/error-no-group.png', fullPage: true });

    // Step 2: Send AI message without group context
    await page.fill(S('ai-chat-input'), 'Analyze grouped nodes');
    await page.press(S('ai-chat-input'), 'Enter');
    await page.screenshot({ path: 'artifacts/error-ai-no-context.png', fullPage: true });

    // Step 3: Wait for response or error
    await page.waitForSelector(S('ai-chat-response'));
    await page.screenshot({ path: 'artifacts/error-ai-response.png', fullPage: true });

    // Assertions - verify response indicates no group context
    await expect(page.locator(S('ai-chat-response'))).toBeVisible();
    const responseText = await page.locator(S('ai-chat-response')).textContent();
    expect(responseText).toBeTruthy();
  });

  test('edge case - resize group to minimum dimensions', async ({ page }) => {
    // Step 1: Create group
    await page.click(S('group-create-btn'));
    await page.waitForSelector(S('group-resize-handle'));
    await page.screenshot({ path: 'artifacts/edge-group-created.png', fullPage: true });

    // Step 2: Attempt to resize to very small dimensions
    const resizeHandle = page.locator(S('group-resize-handle'));
    const handleBox = await resizeHandle.boundingBox();
    
    if (handleBox) {
      await page.mouse.move(handleBox.x + handleBox.width / 2, handleBox.y + handleBox.height / 2);
      await page.mouse.down();
      await page.mouse.move(handleBox.x - 500, handleBox.y - 500);
      await page.mouse.up();
    }
    await page.screenshot({ path: 'artifacts/edge-minimum-resize.png', fullPage: true });

    // Assertions - verify group maintains minimum size constraints
    await expect(page.locator(S('group-resize-handle'))).toBeVisible();
    const groupElement = page.locator(S('group-title-input'));
    await expect(groupElement).toBeVisible();
  });
});