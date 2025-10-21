import { test, expect } from '@playwright/test';

/**
 * Test configuration - enable screenshots, videos, and traces
 */
test.use({
  screenshot: 'on',
  video: 'retain-on-failure',
  trace: 'retain-on-failure',
});

test.describe('Media Upload', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to base URL and handle authentication
    await page.goto(process.env.BASE_URL || 'http://localhost:5175');
    
    // Login if needed
    const emailInput = page.locator('input[type="email"]');
    if (await emailInput.isVisible({ timeout: 3000 }).catch(() => false)) {
      await emailInput.fill(process.env.TEST_EMAIL || 'test@example.com');
      await page.locator('input[type="password"]').fill(process.env.TEST_PASSWORD || 'password123');
      await page.locator('button[type="submit"]').click();
      await page.waitForSelector('.vf-board-canvas, .vf-board-glow-button', { timeout: 10000 });
      await page.screenshot({ path: 'artifacts/login-complete.png', fullPage: true });
    }

    // Create a new board for testing
    const createButton = page.locator('.vf-board-glow-button').first();
    if (await createButton.isVisible({ timeout: 3000 }).catch(() => false)) {
      await createButton.click();
      await page.waitForSelector('input#boardName', { timeout: 5000 });
      await page.locator('input#boardName').fill('Media Upload Test Board');
      await page.screenshot({ path: 'artifacts/board-modal.png', fullPage: true });
      
      const submitButton = page.locator('button[type="submit"]').or(page.getByRole('button', { name: /create|submit/i }));
      await submitButton.click();
      await page.waitForSelector('.vf-board-canvas', { timeout: 10000 });
      await page.screenshot({ path: 'artifacts/board-created.png', fullPage: true });
    }
  });

  test('happy path - upload image file to node', async ({ page }) => {
    // Step 1: Click IMAGE node button in toolbar
    const imageButton = page.locator('.vf-toolbar-row button').filter({ hasText: /image/i }).or(
      page.getByRole('button', { name: /image/i })
    );
    await imageButton.click();
    await page.screenshot({ path: 'artifacts/image-node-clicked.png', fullPage: true });

    // Step 2: Wait for file input or upload area to appear
    const fileInput = page.locator('input[type="file"]').first();
    await fileInput.waitFor({ state: 'attached', timeout: 5000 });
    await page.screenshot({ path: 'artifacts/image-upload-ready.png', fullPage: true });

    // Step 3: Upload image file
    await fileInput.setInputFiles({
      name: 'test-image.png',
      mimeType: 'image/png',
      buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==', 'base64')
    });
    await page.screenshot({ path: 'artifacts/image-uploaded.png', fullPage: true });

    // Step 4: Wait for media preview to render
    const mediaPreview = page.locator('img[src*="blob:"]').or(
      page.locator('.vf-media-preview, .media-preview, img[alt*="preview"]')
    );
    await mediaPreview.waitFor({ state: 'visible', timeout: 10000 });
    await page.screenshot({ path: 'artifacts/image-preview-rendered.png', fullPage: true });

    // Assertions
    await expect(mediaPreview).toBeVisible();
    const previewCount = await page.locator('img').count();
    expect(previewCount).toBeGreaterThan(0);
  });

  test('happy path - upload video file to node', async ({ page }) => {
    // Step 1: Click VIDEO node button in toolbar
    const videoButton = page.locator('.vf-toolbar-row button').filter({ hasText: /video/i }).or(
      page.getByRole('button', { name: /video/i })
    );
    await videoButton.click();
    await page.screenshot({ path: 'artifacts/video-node-clicked.png', fullPage: true });

    // Step 2: Wait for file input or upload area to appear
    const fileInput = page.locator('input[type="file"]').first();
    await fileInput.waitFor({ state: 'attached', timeout: 5000 });
    await page.screenshot({ path: 'artifacts/video-upload-ready.png', fullPage: true });

    // Step 3: Upload video file (minimal valid MP4)
    await fileInput.setInputFiles({
      name: 'test-video.mp4',
      mimeType: 'video/mp4',
      buffer: Buffer.from('AAAAIGZ0eXBpc29tAAACAGlzb21pc28yYXZjMW1wNDEAAAAIZnJlZQAAAAhtZGF0AAAA', 'base64')
    });
    await page.screenshot({ path: 'artifacts/video-uploaded.png', fullPage: true });

    // Step 4: Wait for video preview to render
    const videoPreview = page.locator('video[src*="blob:"]').or(
      page.locator('.vf-media-preview video, .media-preview video, video')
    );
    await videoPreview.waitFor({ state: 'visible', timeout: 10000 });
    await page.screenshot({ path: 'artifacts/video-preview-rendered.png', fullPage: true });

    // Assertions
    await expect(videoPreview).toBeVisible();
    const videoElement = page.locator('video').first();
    await expect(videoElement).toBeAttached();
  });

  test('error case - invalid file format handling', async ({ page }) => {
    // Step 1: Click IMAGE node button
    const imageButton = page.locator('.vf-toolbar-row button').filter({ hasText: /image/i }).or(
      page.getByRole('button', { name: /image/i })
    );
    await imageButton.click();
    await page.screenshot({ path: 'artifacts/error-image-node-clicked.png', fullPage: true });

    // Step 2: Wait for file input
    const fileInput = page.locator('input[type="file"]').first();
    await fileInput.waitFor({ state: 'attached', timeout: 5000 });
    await page.screenshot({ path: 'artifacts/error-upload-ready.png', fullPage: true });

    // Step 3: Upload invalid file format (text file to image node)
    await fileInput.setInputFiles({
      name: 'invalid-file.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('This is not an image file')
    });
    await page.screenshot({ path: 'artifacts/error-invalid-file-uploaded.png', fullPage: true });

    // Step 4: Wait for error message to appear
    const errorMessage = page.locator('.error, .error-message, [role="alert"]').filter({ hasText: /invalid|format|type|not supported/i });
    await errorMessage.waitFor({ state: 'visible', timeout: 10000 });
    await page.screenshot({ path: 'artifacts/error-message-displayed.png', fullPage: true });

    // Assertions
    await expect(errorMessage).toBeVisible();
    await expect(errorMessage).toContainText(/invalid|format|type|not supported/i);
  });

  test('error case - video node with invalid format', async ({ page }) => {
    // Step 1: Click VIDEO node button
    const videoButton = page.locator('.vf-toolbar-row button').filter({ hasText: /video/i }).or(
      page.getByRole('button', { name: /video/i })
    );
    await videoButton.click();
    await page.screenshot({ path: 'artifacts/error-video-node-clicked.png', fullPage: true });

    // Step 2: Wait for file input
    const fileInput = page.locator('input[type="file"]').first();
    await fileInput.waitFor({ state: 'attached', timeout: 5000 });

    // Step 3: Upload invalid file format (image to video node)
    await fileInput.setInputFiles({
      name: 'invalid-video.png',
      mimeType: 'image/png',
      buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==', 'base64')
    });
    await page.screenshot({ path: 'artifacts/error-invalid-video-uploaded.png', fullPage: true });

    // Step 4: Wait for error message
    const errorMessage = page.locator('.error, .error-message, [role="alert"]').filter({ hasText: /invalid|format|video|not supported/i });
    await errorMessage.waitFor({ state: 'visible', timeout: 10000 });
    await page.screenshot({ path: 'artifacts/error-video-message-displayed.png', fullPage: true });

    // Assertions
    await expect(errorMessage).toBeVisible();
    const errorText = await errorMessage.textContent();
    expect(errorText?.toLowerCase()).toMatch(/invalid|format|video|not supported/);
  });
});