```typescript
import { test, expect, Page } from '@playwright/test';

test.describe('Infinite Canvas Node Management', () => {
  let page: Page;

  test.beforeEach(async ({ page: testPage }) => {
    page = testPage;
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.waitForSelector('[data-testid="canvas-container"]');
  });

  test('should create and manage text nodes successfully', async () => {
    // Create text node
    await page.click('[data-testid="create-text-node-button"]');
    await page.waitForSelector('[data-testid="text-node"]');
    
    const textNode = page.locator('[data-testid="text-node"]').first();
    await expect(textNode).toBeVisible();
    await page.screenshot({ path: 'text-node-created.png' });

    // Add content to text node
    await textNode.click();
    await page.fill('[data-testid="text-node-input"]', 'Test text content');
    await page.keyboard.press('Enter');
    
    await expect(page.locator('[data-testid="text-node-content"]')).toHaveText('Test text content');
    await page.screenshot({ path: 'text-node-with-content.png' });
  });

  test('should create and manage media nodes successfully', async () => {
    // Create media node
    await page.click('[data-testid="create-media-node-button"]');
    await page.waitForSelector('[data-testid="media-node"]');
    
    const mediaNode = page.locator('[data-testid="media-node"]').first();
    await expect(mediaNode).toBeVisible();
    
    // Upload media file
    await mediaNode.click();
    const fileInput = page.locator('[data-testid="media-file-input"]');
    await fileInput.setInputFiles('test-assets/sample-image.png');
    
    await page.waitForSelector('[data-testid="media-preview"]');
    await expect(page.locator('[data-testid="media-preview"]')).toBeVisible();
    await page.screenshot({ path: 'media-node-with-content.png' });
  });

  test('should create and manage AI chat nodes successfully', async () => {
    // Create AI chat node
    await page.click('[data-testid="create-ai-chat-node-button"]');
    await page.waitForSelector('[data-testid="ai-chat-node"]');
    
    const aiChatNode = page.locator('[data-testid="ai-chat-node"]').first();
    await expect(aiChatNode).toBeVisible();
    
    // Send message in AI chat
    await aiChatNode.click();
    await page.fill('[data-testid="ai-chat-input"]', 'Hello AI, how are you?');
    await page.click('[data-testid="ai-chat-send-button"]');
    
    await page.waitForSelector('[data-testid="ai-chat-message"]');
    await expect(page.locator('[data-testid="ai-chat-message"]')).toHaveCount(1);
    await page.screenshot({ path: 'ai-chat-node-with-message.png' });
  });

  test('should move nodes around canvas successfully', async () => {
    // Create a text node
    await page.click('[data-testid="create-text-node-button"]');
    const textNode = page.locator('[data-testid="text-node"]').first();
    await expect(textNode).toBeVisible();
    
    // Get initial position
    const initialBox = await textNode.boundingBox();
    expect(initialBox).toBeTruthy();
    
    // Drag node to new position
    await textNode.hover();
    await page.mouse.down();
    await page.mouse.move(initialBox!.x + 200, initialBox!.y + 100);
    await page.mouse.up();
    
    // Verify node moved
    const finalBox = await textNode.boundingBox();
    expect(finalBox!.x).toBeGreaterThan(initialBox!.x + 150);
    expect(finalBox!.y).toBeGreaterThan(initialBox!.y + 50);
    await page.screenshot({ path: 'node-moved.png' });
  });

  test('should resize nodes successfully', async () => {
    // Create a text node
    await page.click('[data-testid="create-text-node-button"]');
    const textNode = page.locator('[data-testid="text-node"]').first();
    await expect(textNode).toBeVisible();
    
    // Select node to show resize handles
    await textNode.click();
    await page.waitForSelector('[data-testid="resize-handle-se"]');
    
    const initialBox = await textNode.boundingBox();
    const resizeHandle = page.locator('[data-testid="resize-handle-se"]');
    
    // Drag resize handle
    await resizeHandle.hover();
    await page.mouse.down();
    await page.mouse.move(initialBox!.x + initialBox!.width + 100, initialBox!.y + initialBox!.height + 50);
    await page.mouse.up();
    
    // Verify node resized
    const finalBox = await textNode.boundingBox();
    expect(finalBox!.width).toBeGreaterThan(initialBox!.width + 50);
    expect(finalBox!.height).toBeGreaterThan(initialBox!.height + 25);
    await page.screenshot({ path: 'node-resized.png' });
  });

  test('should connect nodes with edges successfully', async () => {
    // Create two text nodes
    await page.click('[data-testid="create-text-node-button"]');
    await page.click('[data-testid="create-text-node-button"]');
    
    const nodes = page.locator('[data-testid="text-node"]');
    await expect(nodes).toHaveCount(2);
    
    const firstNode = nodes.nth(0);
    const secondNode = nodes.nth(1);
    
    // Move second node to create distance
    const secondNodeBox = await secondNode.boundingBox();
    await secondNode.hover();
    await page.mouse.down();
    await page.mouse.move(secondNodeBox!.x + 300, secondNodeBox!.y);
    await page.mouse.up();
    
    // Connect nodes
    await firstNode.hover();
    await page.waitForSelector('[data-testid="connection-handle-output"]');
    const outputHandle = firstNode.locator('[data-testid="connection-handle-output"]');
    const inputHandle = secondNode.locator('[data-testid="connection-handle-input"]');
    
    await outputHandle.dragTo(inputHandle);
    
    // Verify edge created
    await page.waitForSelector('[data-testid="edge"]');
    await expect(page.locator('[data-testid="edge"]')).toHaveCount(1);
    await page.screenshot({ path: 'nodes-connected.png' });
  });

  test('should delete nodes successfully', async () => {
    // Create a text node
    await page.click('[data-testid="create-text-node-button"]');
    const textNode = page.locator('[data-testid="text-node"]').first();
    await expect(textNode).toBeVisible();
    
    // Select and delete node
    await textNode.click();
    await page.keyboard.press('Delete');
    
    // Verify node deleted
    await expect(page.locator('[data-testid="text-node"]')).toHaveCount(0);
    await page.screenshot({ path: 'node-deleted.png' });
  });

  test('should perform undo/redo operations successfully', async () => {
    // Create a text node
    await page.click('[data-testid="create-text-node-button"]');
    await expect(page.locator('[data-testid="text-node"]')).toHaveCount(1);
    
    // Undo creation
    await page.keyboard.press('Control+z');
    await expect(page.locator('[data-testid="text-node"]')).toHaveCount(0);
    await page.screenshot({ path: 'after-undo.png' });
    
    // Redo creation
    await page.keyboard.press('Control+y');
    await expect(page.locator('[data-testid="text-node"]')).toHaveCount(1);
    await page.screenshot({ path: 'after-redo.png' });
  });

  test('should save canvas state successfully', async () => {
    // Create multiple nodes
    await page.click('[data-testid="create-text-node-button"]');
    await page.click('[data-testid="create-media-node-button"]');
    await page.click('[data-testid="create-ai-chat-node-button"]');
    
    await expect(page.locator('[data-testid="text-node"]')).toHaveCount(1);
    await expect(page.locator('[data-testid="media-node"]')).toHaveCount(1);
    await expect(page.locator('[data-testid="ai-chat-node"]')).toHaveCount(1);
    
    // Save canvas
    await page.click('[data-testid="save-canvas-button"]');
    await page.waitForSelector('[data-testid="save-success-notification"]');
    
    await expect(page.locator('[data-testid="save-success-notification"]')).toBeVisible();
    await page.screenshot({ path: 'canvas-saved.png' });
  });

  test('should handle error when creating node fails', async () => {
    // Mock network failure
    await page.route('**/api/nodes', route => route.abort());
    
    await page.click('[data-testid="create-text-node-button"]');
    
    // Verify error handling
    await page.waitForSelector('[data-testid="error-notification"]');
    await expect(page.locator('[data-testid="error-notification"]')).toBeVisible();
    await expect(page.locator('[data-testid="error-notification"]')).toContainText('Failed to create node');
    await page.screenshot({ path: 'node-creation-error.png' });
  });

  test('should handle error when saving canvas fails', async () => {
    // Create a node
    await page.click('[data-testid="create-text-node-button"]');
    await expect(page.locator('[data-testid="text-node"]')).toHaveCount(1);
    
    // Mock save failure
    await page.route('**/api/canvas/save', route => route.abort());
    
    await page.click('[data-testid="save-canvas-button"]');
    
    // Verify error handling
    await page.waitForSelector('[data-testid="error-notification"]');
    await expect(page.locator('[data-testid="error-notification"]')).toBeVisible();
    await expect(page.locator('[data-testid="error-notification"]')).toContainText('Failed to save canvas');
    await page.screenshot({ path: 'canvas-save-error.png' });
  });

  test('should handle maximum node limit', async () => {
    // Create nodes up to limit (assuming limit is 50)
    for (let i = 0; i < 51; i++) {
      await page.click('[data-testid="create-text-node-button"]');
    }
    
    // Verify limit notification
    await page.waitForSelector('[data-testid="warning-notification"]');
    await expect(page.locator('[data-testid="warning-notification"]')).toBeVisible();
    await expect(page.locator('[data-testid="warning-notification"]')).toContainText('Maximum node limit reached');
    
    // Verify only 50 nodes created
    await expect(page.locator('[data-testid="text-node"]')).toHaveCount(50);
    await page.screenshot({ path: 'node-limit-reached.png' });
  });
});
```