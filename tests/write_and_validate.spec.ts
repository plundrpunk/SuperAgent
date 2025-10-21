import { test, expect } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

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
    // Navigate to base URL and handle authentication
    await page.goto(process.env.BASE_URL || 'http://localhost:3000');
    
    // Login if required
    const emailInput = page.locator('input[type="email"]');
    if (await emailInput.isVisible({ timeout: 2000 }).catch(() => false)) {
      await emailInput.fill(process.env.TEST_EMAIL || 'test@example.com');
      await page.locator('input[type="password"]').fill(process.env.TEST_PASSWORD || 'password');
      await page.locator('button[type="submit"]').click();
      await page.waitForSelector('.vf-board-canvas, .vf-board-glow-button', { timeout: 10000 });
    }
    
    // Create or navigate to a board
    const canvas = page.locator('.vf-board-canvas');
    if (!await canvas.isVisible({ timeout: 2000 }).catch(() => false)) {
      await page.getByText('Create New Board').click();
      await page.locator('input#boardName').fill('Test Group Management Board');
      await page.locator('button[type="submit"]').click();
      await page.waitForSelector('.vf-board-canvas', { timeout: 10000 });
    }
    
    await page.screenshot({ path: 'artifacts/group-setup-complete.png', fullPage: true });
  });

  test('happy path - create, rename, resize, add nodes, and delete group', async ({ page }) => {
    // Step 1: Click group create button
    await page.waitForSelector('.vf-group-create-btn', { timeout: 5000 });
    await page.click('.vf-group-create-btn');
    await page.screenshot({ path: 'artifacts/group-created.png', fullPage: true });
    
    // Assert group is created and visible
    await page.waitForSelector('.vf-group-container', { timeout: 5000 });
    await expect(page.locator('.vf-group-container')).toBeVisible();
    
    // Step 2: Rename group using group-title-input
    await page.waitForSelector('.vf-group-title-input', { timeout: 5000 });
    await page.click('.vf-group-title-input');
    await page.fill('.vf-group-title-input', 'My Test Group');
    await page.keyboard.press('Enter');
    await page.screenshot({ path: 'artifacts/group-renamed.png', fullPage: true });
    
    // Assert group title is updated
    await expect(page.locator('.vf-group-title-input')).toHaveValue('My Test Group');
    
    // Step 3: Resize group using group-resize-handle
    await page.waitForSelector('.vf-group-resize-handle', { timeout: 5000 });
    const resizeHandle = page.locator('.vf-group-resize-handle');
    const resizeBox = await resizeHandle.boundingBox();
    
    if (resizeBox) {
      await page.mouse.move(resizeBox.x + resizeBox.width / 2, resizeBox.y + resizeBox.height / 2);
      await page.mouse.down();
      await page.mouse.move(resizeBox.x + 200, resizeBox.y + 150);
      await page.mouse.up();
    }
    await page.screenshot({ path: 'artifacts/group-resized.png', fullPage: true });
    
    // Assert group container is still visible after resize
    await expect(page.locator('.vf-group-container')).toBeVisible();
    
    // Step 4: Create a node and add it to group by drag-drop
    await page.waitForSelector('.vf-toolbar-row button', { timeout: 5000 });
    const textNodeButton = page.locator('.vf-toolbar-row button').filter({ hasText: 'TEXT' }).first();
    await textNodeButton.click();
    await page.waitForSelector('.vf-node-element', { timeout: 5000 });
    await page.screenshot({ path: 'artifacts/node-created.png', fullPage: true });
    
    // Drag node into group
    const node = page.locator('.vf-node-element').first();
    const group = page.locator('.vf-group-container');
    const nodeBox = await node.boundingBox();
    const groupBox = await group.boundingBox();
    
    if (nodeBox && groupBox) {
      await page.mouse.move(nodeBox.x + nodeBox.width / 2, nodeBox.y + nodeBox.height / 2);
      await page.mouse.down();
      await page.mouse.move(groupBox.x + groupBox.width / 2, groupBox.y + groupBox.height / 2);
      await page.mouse.up();
    }
    await page.screenshot({ path: 'artifacts/node-added-to-group.png', fullPage: true });
    
    // Assert node is visible (should be in group now)
    await expect(page.locator('.vf-node-element').first()).toBeVisible();
    
    // Step 5: Delete group
    await page.waitForSelector('.vf-group-delete-btn', { timeout: 5000 });
    await page.click('.vf-group-delete-btn');
    await page.screenshot({ path: 'artifacts/group-delete-initiated.png', fullPage: true });
    
    // Confirm deletion if there's a confirmation dialog
    const confirmButton = page.locator('.vf-confirm-delete-btn');
    if (await confirmButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await confirmButton.click();
    }
    await page.screenshot({ path: 'artifacts/group-deleted.png', fullPage: true });
    
    // Assert group is no longer visible
    await expect(page.locator('.vf-group-container')).not.toBeVisible({ timeout: 5000 });
  });

  test('error case - attempt to rename group with empty title', async ({ page }) => {
    // Step 1: Create a group
    await page.waitForSelector('.vf-group-create-btn', { timeout: 5000 });
    await page.click('.vf-group-create-btn');
    await page.waitForSelector('.vf-group-container', { timeout: 5000 });
    await page.screenshot({ path: 'artifacts/error-group-created.png', fullPage: true });
    
    // Assert group is visible
    await expect(page.locator('.vf-group-container')).toBeVisible();
    
    // Step 2: Try to rename with empty title
    await page.waitForSelector('.vf-group-title-input', { timeout: 5000 });
    await page.click('.vf-group-title-input');
    await page.fill('.vf-group-title-input', '');
    await page.keyboard.press('Enter');
    await page.screenshot({ path: 'artifacts/error-empty-title.png', fullPage: true });
    
    // Assert error message or validation appears
    const errorMessage = page.locator('.vf-error-message');
    const titleInput = page.locator('.vf-group-title-input');
    
    // Check if error message is shown OR input has default value
    const hasError = await errorMessage.isVisible({ timeout: 2000 }).catch(() => false);
    const inputValue = await titleInput.inputValue();
    
    if (hasError) {
      await expect(errorMessage).toBeVisible();
      await expect(errorMessage).toContainText(/required|empty|invalid/i);
    } else {
      // If no error message, verify input has a default or previous value (not empty)
      await expect(titleInput).not.toHaveValue('');
    }
    
    await page.screenshot({ path: 'artifacts/error-validation-complete.png', fullPage: true });
  });

  test('error case - attempt to delete group with confirmation cancel', async ({ page }) => {
    // Step 1: Create a group
    await page.waitForSelector('.vf-group-create-btn', { timeout: 5000 });
    await page.click('.vf-group-create-btn');
    await page.waitForSelector('.vf-group-container', { timeout: 5000 });
    await page.screenshot({ path: 'artifacts/cancel-group-created.png', fullPage: true });
    
    // Assert group is visible
    await expect(page.locator('.vf-group-container')).toBeVisible();
    
    // Step 2: Initiate delete
    await page.waitForSelector('.vf-group-delete-btn', { timeout: 5000 });
    await page.click('.vf-group-delete-btn');
    await page.screenshot({ path: 'artifacts/cancel-delete-initiated.png', fullPage: true });
    
    // Step 3: Cancel deletion if confirmation dialog appears
    const cancelButton = page.locator('.vf-cancel-delete-btn');
    if (await cancelButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await cancelButton.click();
      await page.screenshot({ path: 'artifacts/cancel-delete-cancelled.png', fullPage: true });
      
      // Assert group is still visible after cancellation
      await expect(page.locator('.vf-group-container')).toBeVisible();
    } else {
      // If no confirmation dialog, group should still be visible
      await expect(page.locator('.vf-group-container')).toBeVisible();
    }
    
    // Final assertion - group remains on canvas
    await expect(page.locator('.vf-group-container')).toBeVisible();
    await page.screenshot({ path: 'artifacts/cancel-group-still-exists.png', fullPage: true });
  });
});