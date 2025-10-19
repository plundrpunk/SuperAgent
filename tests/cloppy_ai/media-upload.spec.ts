```typescript
import { test, expect, Page } from '@playwright/test';
import path from 'path';

test.describe('Media Upload and Processing Pipeline', () => {
  let page: Page;

  test.beforeEach(async ({ page: testPage }) => {
    page = testPage;
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    // Login or setup if required
    await page.getByTestId('board-canvas').waitFor();
    await page.screenshot({ path: 'screenshots/initial-board.png' });
  });

  test('should upload and process video file successfully', async () => {
    const videoPath = path.join(__dirname, 'fixtures/test-video.mp4');
    
    // Upload video file
    await page.getByTestId('upload-button').click();
    await page.getByTestId('file-input').setInputFiles(videoPath);
    await page.screenshot({ path: 'screenshots/video-upload-started.png' });
    
    // Verify upload progress
    await expect(page.getByTestId('upload-progress')).toBeVisible();
    await expect(page.getByTestId('upload-status')).toContainText('Uploading');
    
    // Wait for processing to complete
    await expect(page.getByTestId('upload-status')).toContainText('Processing', { timeout: 30000 });
    await expect(page.getByTestId('upload-status')).toContainText('Completed', { timeout: 120000 });
    
    // Verify video appears on canvas
    await expect(page.getByTestId('media-item-video')).toBeVisible();
    await page.screenshot({ path: 'screenshots/video-on-canvas.png' });
    
    // Check transcription results
    await page.getByTestId('media-item-video').click();
    await expect(page.getByTestId('transcription-panel')).toBeVisible();
    await expect(page.getByTestId('transcription-text')).not.toBeEmpty();
    await page.screenshot({ path: 'screenshots/video-transcription.png' });
  });

  test('should upload and process audio file successfully', async () => {
    const audioPath = path.join(__dirname, 'fixtures/test-audio.mp3');
    
    // Upload audio file
    await page.getByTestId('upload-button').click();
    await page.getByTestId('file-input').setInputFiles(audioPath);
    
    // Verify upload and processing
    await expect(page.getByTestId('upload-progress')).toBeVisible();
    await expect(page.getByTestId('upload-status')).toContainText('Completed', { timeout: 60000 });
    
    // Verify audio appears on canvas
    await expect(page.getByTestId('media-item-audio')).toBeVisible();
    await page.screenshot({ path: 'screenshots/audio-on-canvas.png' });
    
    // Check transcription results
    await page.getByTestId('media-item-audio').click();
    await expect(page.getByTestId('transcription-panel')).toBeVisible();
    await expect(page.getByTestId('transcription-text')).not.toBeEmpty();
    await page.screenshot({ path: 'screenshots/audio-transcription.png' });
  });

  test('should upload and process PDF document successfully', async () => {
    const pdfPath = path.join(__dirname, 'fixtures/test-document.pdf');
    
    // Upload PDF file
    await page.getByTestId('upload-button').click();
    await page.getByTestId('file-input').setInputFiles(pdfPath);
    
    // Verify upload and processing
    await expect(page.getByTestId('upload-status')).toContainText('Completed', { timeout: 60000 });
    
    // Verify PDF appears on canvas
    await expect(page.getByTestId('media-item-document')).toBeVisible();
    await page.screenshot({ path: 'screenshots/pdf-on-canvas.png' });
    
    // Check OCR results
    await page.getByTestId('media-item-document').click();
    await expect(page.getByTestId('ocr-panel')).toBeVisible();
    await expect(page.getByTestId('ocr-text')).not.toBeEmpty();
    await page.screenshot({ path: 'screenshots/pdf-ocr.png' });
  });

  test('should upload and process image successfully', async () => {
    const imagePath = path.join(__dirname, 'fixtures/test-image.jpg');
    
    // Upload image file
    await page.getByTestId('upload-button').click();
    await page.getByTestId('file-input').setInputFiles(imagePath);
    
    // Verify upload and processing
    await expect(page.getByTestId('upload-status')).toContainText('Completed', { timeout: 30000 });
    
    // Verify image appears on canvas
    await expect(page.getByTestId('media-item-image')).toBeVisible();
    await page.screenshot({ path: 'screenshots/image-on-canvas.png' });
    
    // Check OCR results
    await page.getByTestId('media-item-image').click();
    await expect(page.getByTestId('ocr-panel')).toBeVisible();
    await expect(page.getByTestId('ocr-text')).toBeVisible();
    await page.screenshot({ path: 'screenshots/image-ocr.png' });
  });

  test('should handle multiple file uploads simultaneously', async () => {
    const files = [
      path.join(__dirname, 'fixtures/test-image.jpg'),
      path.join(__dirname, 'fixtures/test-audio.mp3'),
      path.join(__dirname, 'fixtures/test-document.pdf')
    ];
    
    // Upload multiple files
    await page.getByTestId('upload-button').click();
    await page.getByTestId('file-input').setInputFiles(files);
    
    // Verify all uploads show progress
    await expect(page.getByTestId('upload-queue')).toBeVisible();
    await expect(page.getByTestId('upload-item')).toHaveCount(3);
    
    // Wait for all to complete
    await expect(page.locator('[data-testid="upload-item"][data-status="completed"]')).toHaveCount(3, { timeout: 120000 });
    
    // Verify all media items appear on canvas
    await expect(page.getByTestId('media-item-image')).toBeVisible();
    await expect(page.getByTestId('media-item-audio')).toBeVisible();
    await expect(page.getByTestId('media-item-document')).toBeVisible();
    
    await page.screenshot({ path: 'screenshots/multiple-files-canvas.png' });
  });

  test('should show error for unsupported file type', async () => {
    const unsupportedPath = path.join(__dirname, 'fixtures/test-file.txt');
    
    // Attempt to upload unsupported file
    await page.getByTestId('upload-button').click();
    await page.getByTestId('file-input').setInputFiles(unsupportedPath);
    
    // Verify error message
    await expect(page.getByTestId('upload-error')).toBeVisible();
    await expect(page.getByTestId('upload-error')).toContainText('Unsupported file type');
    await page.screenshot({ path: 'screenshots/unsupported-file-error.png' });
    
    // Verify file is not added to canvas
    await expect(page.getByTestId('media-item')).toHaveCount(0);
  });

  test('should handle file upload failure gracefully', async () => {
    const largePath = path.join(__dirname, 'fixtures/large-video.mp4');
    
    // Mock network failure
    await page.route('**/api/upload', route => {
      route.abort('failed');
    });
    
    // Attempt upload
    await page.getByTestId('upload-button').click();
    await page.getByTestId('file-input').setInputFiles(largePath);
    
    // Verify error handling
    await expect(page.getByTestId('upload-status')).toContainText('Failed', { timeout: 30000 });
    await expect(page.getByTestId('upload-error')).toBeVisible();
    await expect(page.getByTestId('retry-upload-button')).toBeVisible();
    
    await page.screenshot({ path: 'screenshots/upload-failure.png' });
  });

  test('should show processing status for each file type', async () => {
    const videoPath = path.join(__dirname, 'fixtures/test-video.mp4');
    
    // Upload video and monitor status changes
    await page.getByTestId('upload-button').click();
    await page.getByTestId('file-input').setInputFiles(videoPath);
    
    // Check status progression
    await expect(page.getByTestId('processing-status')).toContainText('Uploading');
    await page.screenshot({ path: 'screenshots/status-uploading.png' });
    
    await expect(page.getByTestId('processing-status')).toContainText('Processing Video', { timeout: 30000 });
    await page.screenshot({ path: 'screenshots/status-processing.png' });
    
    await expect(page.getByTestId('processing-status')).toContainText('Generating Transcription', { timeout: 60000 });
    await page.screenshot({ path: 'screenshots/status-transcription.png' });
    
    await expect(page.getByTestId('processing-status')).toContainText('Completed', { timeout: 120000 });
    await page.screenshot({ path: 'screenshots/status-completed.png' });
  });

  test('should verify processing progress indicators', async () => {
    const files = [
      path.join(__dirname, 'fixtures/test-video.mp4'),
      path.join(__dirname, 'fixtures/test-document.pdf')
    ];
    
    await page.getByTestId('upload-button').click();
    await page.getByTestId('file-input').setInputFiles(files);
    
    // Verify progress bars appear
    await expect(page.getByTestId('upload-progress-bar')).toHaveCount(2);
    
    // Check progress percentages
    const progressBars = page.getByTestId('upload-progress-bar');
    await expect(progressBars.first()).toHaveAttribute('aria-valuenow', /\d+/);
    
    // Verify completion indicators
    await expect(page.getByTestId('processing-complete-icon')).toHaveCount(2, { timeout: 120000 });
    
    await page.screenshot({ path: 'screenshots/progress-indicators.png' });
  });

  test('should cancel file upload in progress', async () => {
    const largePath = path.join(__dirname, 'fixtures/large-video.mp4');
    
    // Start upload
    await page.getByTestId('upload-button').click();
    await page.getByTestId('file-input').setInputFiles(largePath);
    
    // Cancel during upload
    await expect(page.getByTestId('cancel-upload-button')).toBeVisible();
    await page.getByTestId('cancel-upload-button').click();
    
    // Verify cancellation
    await expect(page.getByTestId('upload-status')).toContainText('Cancelled');
    await expect(page.getByTestId('media-item')).toHaveCount(0);
    
    await page.screenshot({ path: 'screenshots/upload-cancelled.png' });
  });
});
```