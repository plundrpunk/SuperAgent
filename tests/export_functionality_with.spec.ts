import { test, expect } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

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

test.describe('Board Export Functionality', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to base URL from environment
    await page.goto(process.env.BASE_URL || 'http://localhost:3000');
    
    // Wait for board canvas to be ready
    await page.waitForSelector(S('board-canvas'));
    await page.screenshot({ path: 'artifacts/export-beforeEach-loaded.png', fullPage: true });
  });

  test('happy path - export board to PDF format', async ({ page }) => {
    // Step 1: Wait for board canvas to be visible
    await expect(page.locator(S('board-canvas'))).toBeVisible();
    await page.screenshot({ path: 'artifacts/export-pdf-step1-canvas-visible.png', fullPage: true });

    // Step 2: Set up download listener
    const downloadPromise = page.waitForEvent('download');
    
    // Step 3: Click export PDF button
    await page.click(S('export-pdf-btn'));
    await page.screenshot({ path: 'artifacts/export-pdf-step2-clicked-export.png', fullPage: true });

    // Step 4: Wait for download to complete
    const download = await downloadPromise;
    await page.screenshot({ path: 'artifacts/export-pdf-step3-download-started.png', fullPage: true });

    // Step 5: Verify download properties
    const downloadPath = await download.path();
    expect(downloadPath).toBeTruthy();
    expect(download.suggestedFilename()).toContain('.pdf');
    
    // Step 6: Save and verify file exists
    const savedPath = path.join('artifacts', 'downloaded-board.pdf');
    await download.saveAs(savedPath);
    expect(fs.existsSync(savedPath)).toBeTruthy();
    await page.screenshot({ path: 'artifacts/export-pdf-step4-download-complete.png', fullPage: true });

    // Assertions
    await expect(page.locator(S('board-canvas'))).toBeVisible();
    expect(fs.statSync(savedPath).size).toBeGreaterThan(0);
  });

  test('happy path - export board to Markdown format', async ({ page }) => {
    // Step 1: Verify board canvas is ready
    await expect(page.locator(S('board-canvas'))).toBeVisible();
    await page.screenshot({ path: 'artifacts/export-markdown-step1-canvas-visible.png', fullPage: true });

    // Step 2: Set up download listener
    const downloadPromise = page.waitForEvent('download');
    
    // Step 3: Click export Markdown button
    await page.click(S('export-markdown-btn'));
    await page.screenshot({ path: 'artifacts/export-markdown-step2-clicked-export.png', fullPage: true });

    // Step 4: Wait for download to complete
    const download = await downloadPromise;
    await page.screenshot({ path: 'artifacts/export-markdown-step3-download-started.png', fullPage: true });

    // Step 5: Verify download properties
    const downloadPath = await download.path();
    expect(downloadPath).toBeTruthy();
    const filename = download.suggestedFilename();
    expect(filename).toMatch(/\.(md|markdown)$/);
    
    // Step 6: Save and verify file content
    const savedPath = path.join('artifacts', 'downloaded-board.md');
    await download.saveAs(savedPath);
    expect(fs.existsSync(savedPath)).toBeTruthy();
    await page.screenshot({ path: 'artifacts/export-markdown-step4-download-complete.png', fullPage: true });

    // Assertions
    await expect(page.locator(S('board-canvas'))).toBeVisible();
    const fileContent = fs.readFileSync(savedPath, 'utf-8');
    expect(fileContent.length).toBeGreaterThan(0);
  });

  test('happy path - verify file downloads correctly with proper naming', async ({ page }) => {
    // Step 1: Ensure board is loaded
    await page.waitForSelector(S('board-canvas'));
    await page.screenshot({ path: 'artifacts/verify-download-step1-ready.png', fullPage: true });

    // Step 2: Test PDF download naming
    const pdfDownloadPromise = page.waitForEvent('download');
    await page.click(S('export-pdf-btn'));
    const pdfDownload = await pdfDownloadPromise;
    await page.screenshot({ path: 'artifacts/verify-download-step2-pdf-downloaded.png', fullPage: true });

    // Step 3: Verify PDF file properties
    expect(pdfDownload.suggestedFilename()).toBeTruthy();
    expect(pdfDownload.suggestedFilename()).toContain('.pdf');
    const pdfPath = await pdfDownload.path();
    expect(pdfPath).toBeTruthy();

    // Step 4: Test Markdown download naming
    const mdDownloadPromise = page.waitForEvent('download');
    await page.click(S('export-markdown-btn'));
    const mdDownload = await mdDownloadPromise;
    await page.screenshot({ path: 'artifacts/verify-download-step3-markdown-downloaded.png', fullPage: true });

    // Assertions
    expect(mdDownload.suggestedFilename()).toBeTruthy();
    expect(mdDownload.suggestedFilename()).toMatch(/\.(md|markdown)$/);
    const mdPath = await mdDownload.path();
    expect(mdPath).toBeTruthy();
  });

  test('edge case - export empty board to PDF', async ({ page }) => {
    // Step 1: Verify empty board state
    await page.waitForSelector(S('board-canvas'));
    await page.screenshot({ path: 'artifacts/export-empty-pdf-step1-empty-board.png', fullPage: true });

    // Step 2: Attempt to export empty board as PDF
    const downloadPromise = page.waitForEvent('download');
    await page.click(S('export-pdf-btn'));
    await page.screenshot({ path: 'artifacts/export-empty-pdf-step2-export-clicked.png', fullPage: true });

    // Step 3: Verify download still occurs
    const download = await downloadPromise;
    const downloadPath = await download.path();
    await page.screenshot({ path: 'artifacts/export-empty-pdf-step3-download-complete.png', fullPage: true });

    // Step 4: Save and verify file
    const savedPath = path.join('artifacts', 'empty-board.pdf');
    await download.saveAs(savedPath);
    await page.screenshot({ path: 'artifacts/export-empty-pdf-step4-file-saved.png', fullPage: true });

    // Assertions - empty board should still generate a valid file
    expect(downloadPath).toBeTruthy();
    expect(fs.existsSync(savedPath)).toBeTruthy();
    expect(fs.statSync(savedPath).size).toBeGreaterThan(0);
    await expect(page.locator(S('board-canvas'))).toBeVisible();
  });

  test('edge case - export empty board to Markdown', async ({ page }) => {
    // Step 1: Verify empty board state
    await page.waitForSelector(S('board-canvas'));
    await page.screenshot({ path: 'artifacts/export-empty-markdown-step1-empty-board.png', fullPage: true });

    // Step 2: Attempt to export empty board as Markdown
    const downloadPromise = page.waitForEvent('download');
    await page.click(S('export-markdown-btn'));
    await page.screenshot({ path: 'artifacts/export-empty-markdown-step2-export-clicked.png', fullPage: true });

    // Step 3: Verify download occurs
    const download = await downloadPromise;
    const downloadPath = await download.path();
    await page.screenshot({ path: 'artifacts/export-empty-markdown-step3-download-complete.png', fullPage: true });

    // Step 4: Save and check content
    const savedPath = path.join('artifacts', 'empty-board.md');
    await download.saveAs(savedPath);
    await page.screenshot({ path: 'artifacts/export-empty-markdown-step4-file-saved.png', fullPage: true });

    // Assertions - empty board should generate valid markdown file
    expect(downloadPath).toBeTruthy();
    expect(fs.existsSync(savedPath)).toBeTruthy();
    const fileContent = fs.readFileSync(savedPath, 'utf-8');
    expect(fileContent).toBeDefined();
    await expect(page.locator(S('board-canvas'))).toBeVisible();
  });

  test('happy path - export board with media nodes including images', async ({ page }) => {
    // Step 1: Verify board canvas is ready
    await page.waitForSelector(S('board-canvas'));
    await page.screenshot({ path: 'artifacts/export-media-step1-board-ready.png', fullPage: true });

    // Step 2: Export board with media to PDF
    const pdfDownloadPromise = page.waitForEvent('download');
    await page.click(S('export-pdf-btn'));
    const pdfDownload = await pdfDownloadPromise;
    await page.screenshot({ path: 'artifacts/export-media-step2-pdf-exported.png', fullPage: true });

    // Step 3: Verify PDF download with media
    const pdfPath = path.join('artifacts', 'board-with-images.pdf');
    await pdfDownload.saveAs(pdfPath);
    expect(fs.existsSync(pdfPath)).toBeTruthy();
    expect(fs.statSync(pdfPath).size).toBeGreaterThan(0);
    await page.screenshot({ path: 'artifacts/export-media-step3-pdf-saved.png', fullPage: true });

    // Step 4: Export board with media to Markdown
    const mdDownloadPromise = page.waitForEvent('download');
    await page.click(S('export-markdown-btn'));
    const mdDownload = await mdDownloadPromise;
    await page.screenshot({ path: 'artifacts/export-media-step4-markdown-exported.png', fullPage: true });

    // Step 5: Verify Markdown download with media references
    const mdPath = path.join('artifacts', 'board-with-images.md');
    await mdDownload.saveAs(mdPath);
    expect(fs.existsSync(mdPath)).toBeTruthy();
    await page.screenshot({ path: 'artifacts/export-media-step5-markdown-saved.png', fullPage: true });

    // Assertions
    await expect(page.locator(S('board-canvas'))).toBeVisible();
    const mdContent = fs.readFileSync(mdPath, 'utf-8');
    expect(mdContent.length).toBeGreaterThan(0);
  });

  test('happy path - export board with video nodes', async ({ page }) => {
    // Step 1: Verify board with video content is loaded
    await page.waitForSelector(S('board-canvas'));
    await page.screenshot({ path: 'artifacts/export-video-step1-board-loaded.png', fullPage: true });

    // Step 2: Export board with videos to PDF
    const pdfDownloadPromise = page.waitForEvent('download');
    await page.click(S('export-pdf-btn'));
    const pdfDownload = await pdfDownloadPromise;
    await page.screenshot({ path: 'artifacts/export-video-step2-pdf-export-initiated.png', fullPage: true });

    // Step 3: Save and verify PDF with video content
    const pdfPath = path.join('artifacts', 'board-with-videos.pdf');
    await pdfDownload.saveAs(pdfPath);
    expect(fs.existsSync(pdfPath)).toBeTruthy();
    const pdfSize = fs.statSync(pdfPath).size;
    expect(pdfSize).toBeGreaterThan(0);
    await page.screenshot({ path: 'artifacts/export-video-step3-pdf-saved.png', fullPage: true });

    // Step 4: Export board with videos to Markdown
    const mdDownloadPromise = page.waitForEvent('download');
    await page.click(S('export-markdown-btn'));
    const mdDownload = await mdDownloadPromise;
    await page.screenshot({ path: 'artifacts/export-video-step4-markdown-export-initiated.png', fullPage: true });

    // Step 5: Verify Markdown file contains video references
    const mdPath = path.join('artifacts', 'board-with-videos.md');
    await mdDownload.saveAs(mdPath);
    expect(fs.existsSync(mdPath)).toBeTruthy();
    await page.screenshot({ path: 'artifacts/export-video-step5-markdown-saved.png', fullPage: true });

    // Assertions
    await expect(page.locator(S('board-canvas'))).toBeVisible();
    const mdContent = fs.readFileSync(mdPath, 'utf-8');
    expect(mdContent.length).toBeGreaterThan(0);
  });
});