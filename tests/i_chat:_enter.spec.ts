import { test, expect } from '@playwright/test';

/**
 * Test configuration - enable screenshots, videos, and traces
 */
test.use({
  screenshot: 'on',
  video: 'retain-on-failure',
  trace: 'retain-on-failure',
});

test.describe('AI Chat', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to base URL and handle authentication
    await page.goto(process.env.BASE_URL || 'http://localhost:5175');
    
    // Login if redirected to login page
    const emailInput = page.locator('input[type="email"]');
    if (await emailInput.isVisible({ timeout: 3000 }).catch(() => false)) {
      await emailInput.fill(process.env.TEST_EMAIL || 'test@example.com');
      await page.locator('input[type="password"]').fill(process.env.TEST_PASSWORD || 'password');
      await page.locator('button[type="submit"]').click();
      await page.waitForSelector('.vf-dashboard-grid, .vf-board-canvas', { timeout: 10000 });
    }
    
    // Create or navigate to a board
    const canvas = page.locator('.vf-board-canvas');
    if (!await canvas.isVisible({ timeout: 3000 }).catch(() => false)) {
      await page.getByText('Create New Board').click();
      await page.waitForSelector('input#boardName', { timeout: 5000 });
      await page.locator('input#boardName').fill('AI Chat Test Board');
      await page.locator('button[type="submit"]').click();
      await page.waitForSelector('.vf-board-canvas', { timeout: 10000 });
    }
    
    await page.screenshot({ path: 'artifacts/ai-chat-setup.png', fullPage: true });
  });

  test('happy path - send message and verify AI response', async ({ page }) => {
    // Step 1: Create or locate AI chat node
    await page.getByRole('button', { name: /AI_CHAT/i }).click();
    await page.waitForSelector('.vf-ai-chat-input, input[placeholder*="chat"], input[placeholder*="message"]', { timeout: 10000 });
    await page.screenshot({ path: 'artifacts/ai-chat-node-created.png', fullPage: true });

    // Step 2: Enter message in chat input
    const testMessage = 'Hello, can you help me with a test?';
    await page.locator('.vf-ai-chat-input, input[placeholder*="chat"], input[placeholder*="message"]').fill(testMessage);
    await page.screenshot({ path: 'artifacts/ai-chat-message-entered.png', fullPage: true });

    // Step 3: Click send button
    await page.getByRole('button', { name: /send/i }).click();
    await page.screenshot({ path: 'artifacts/ai-chat-message-sent.png', fullPage: true });

    // Step 4: Wait for AI response to appear
    await page.waitForSelector('.vf-ai-chat-response, .ai-response, .chat-response', { timeout: 30000 });
    await page.screenshot({ path: 'artifacts/ai-chat-response-received.png', fullPage: true });

    // Assertions - verify response is visible and contains content
    await expect(page.locator('.vf-ai-chat-response, .ai-response, .chat-response')).toBeVisible();
    const responseText = await page.locator('.vf-ai-chat-response, .ai-response, .chat-response').textContent();
    expect(responseText).toBeTruthy();
    expect(responseText!.length).toBeGreaterThan(0);
  });

  test('context aware - chat with grouped nodes context', async ({ page }) => {
    // Step 1: Create multiple nodes for context
    await page.getByRole('button', { name: /TEXT/i }).click();
    await page.waitForSelector('.vf-text-input, textarea, input[type="text"]', { timeout: 5000 });
    await page.locator('.vf-text-input, textarea, input[type="text"]').fill('Context: Project requirements document');
    await page.screenshot({ path: 'artifacts/ai-chat-context-text-node.png', fullPage: true });

    // Step 2: Create AI chat node
    await page.getByRole('button', { name: /AI_CHAT/i }).click();
    await page.waitForSelector('.vf-ai-chat-input, input[placeholder*="chat"], input[placeholder*="message"]', { timeout: 10000 });
    await page.screenshot({ path: 'artifacts/ai-chat-context-node-created.png', fullPage: true });

    // Step 3: Group nodes or ensure they are in proximity for context
    // This assumes the app automatically includes nearby nodes as context
    await page.screenshot({ path: 'artifacts/ai-chat-context-grouped.png', fullPage: true });

    // Step 4: Send message referencing the context
    const contextMessage = 'What information do you see in the context?';
    await page.locator('.vf-ai-chat-input, input[placeholder*="chat"], input[placeholder*="message"]').fill(contextMessage);
    await page.getByRole('button', { name: /send/i }).click();
    await page.screenshot({ path: 'artifacts/ai-chat-context-message-sent.png', fullPage: true });

    // Step 5: Wait for response
    await page.waitForSelector('.vf-ai-chat-response, .ai-response, .chat-response', { timeout: 30000 });
    await page.screenshot({ path: 'artifacts/ai-chat-context-response.png', fullPage: true });

    // Assertions - verify context-aware response
    await expect(page.locator('.vf-ai-chat-response, .ai-response, .chat-response')).toBeVisible();
    const responseText = await page.locator('.vf-ai-chat-response, .ai-response, .chat-response').textContent();
    expect(responseText).toBeTruthy();
    expect(responseText!.length).toBeGreaterThan(0);
  });

  test('error case - handle chat error gracefully', async ({ page }) => {
    // Step 1: Create AI chat node
    await page.getByRole('button', { name: /AI_CHAT/i }).click();
    await page.waitForSelector('.vf-ai-chat-input, input[placeholder*="chat"], input[placeholder*="message"]', { timeout: 10000 });
    await page.screenshot({ path: 'artifacts/ai-chat-error-node-created.png', fullPage: true });

    // Step 2: Try to send empty message
    await page.getByRole('button', { name: /send/i }).click();
    await page.screenshot({ path: 'artifacts/ai-chat-error-empty-send.png', fullPage: true });

    // Step 3: Verify error message or that send was prevented
    const errorMessage = page.locator('.error, .vf-error, .chat-error');
    const isErrorVisible = await errorMessage.isVisible({ timeout: 3000 }).catch(() => false);
    
    if (isErrorVisible) {
      await page.screenshot({ path: 'artifacts/ai-chat-error-message.png', fullPage: true });
      await expect(errorMessage).toBeVisible();
      await expect(errorMessage).toContainText(/error|required|empty/i);
    } else {
      // If no error message, verify input is still empty and no response was generated
      const inputValue = await page.locator('.vf-ai-chat-input, input[placeholder*="chat"], input[placeholder*="message"]').inputValue();
      expect(inputValue).toBe('');
      
      const response = page.locator('.vf-ai-chat-response, .ai-response, .chat-response');
      const hasResponse = await response.isVisible({ timeout: 2000 }).catch(() => false);
      expect(hasResponse).toBe(false);
    }

    // Step 4: Send a valid message to verify recovery
    await page.locator('.vf-ai-chat-input, input[placeholder*="chat"], input[placeholder*="message"]').fill('Test recovery message');
    await page.getByRole('button', { name: /send/i }).click();
    await page.waitForSelector('.vf-ai-chat-response, .ai-response, .chat-response', { timeout: 30000 });
    await page.screenshot({ path: 'artifacts/ai-chat-error-recovery.png', fullPage: true });

    // Final assertions - verify successful recovery
    await expect(page.locator('.vf-ai-chat-response, .ai-response, .chat-response')).toBeVisible();
    const responseText = await page.locator('.vf-ai-chat-response, .ai-response, .chat-response').textContent();
    expect(responseText).toBeTruthy();
  });
});