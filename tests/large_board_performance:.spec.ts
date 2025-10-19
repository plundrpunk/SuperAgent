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

test.describe('Large Board Performance', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to base URL from environment
    await page.goto(process.env.BASE_URL || 'http://localhost:3000');
    
    // Wait for board canvas to be ready
    await page.waitForSelector(S('board-canvas'));
    await page.screenshot({ path: 'artifacts/board-initial.png', fullPage: true });
  });

  test('happy path - add 500 nodes and verify performance metrics', async ({ page }) => {
    // Step 1: Get initial memory baseline
    const initialMemory = await page.evaluate(() => {
      return (performance as any).memory?.usedJSHeapSize || 0;
    });
    
    // Step 2: Start rendering timer and add 500 nodes programmatically
    const renderingStartTime = Date.now();
    
    await page.evaluate(() => {
      const canvas = document.querySelector('[data-testid="board-canvas"]');
      if (!canvas) throw new Error('Canvas not found');
      
      for (let i = 0; i < 500; i++) {
        const node = document.createElement('div');
        node.setAttribute('data-testid', `node-${i}`);
        node.setAttribute('data-node-id', `${i}`);
        node.style.position = 'absolute';
        node.style.left = `${(i % 25) * 100}px`;
        node.style.top = `${Math.floor(i / 25) * 100}px`;
        node.style.width = '80px';
        node.style.height = '80px';
        node.style.backgroundColor = '#3b82f6';
        node.textContent = `Node ${i}`;
        canvas.appendChild(node);
      }
    });
    
    // Wait for all nodes to be rendered
    await page.waitForSelector(S('node-499'));
    const renderingEndTime = Date.now();
    const renderingTime = renderingEndTime - renderingStartTime;
    
    await page.screenshot({ path: 'artifacts/nodes-added.png', fullPage: true });
    
    // Step 3: Test panning latency
    const panningStartTime = Date.now();
    await page.mouse.move(500, 500);
    await page.mouse.down();
    await page.mouse.move(300, 300, { steps: 10 });
    await page.mouse.up();
    await page.waitForSelector(S('board-canvas'));
    const panningEndTime = Date.now();
    const panningLatency = panningEndTime - panningStartTime;
    
    await page.screenshot({ path: 'artifacts/after-panning.png', fullPage: true });
    
    // Step 4: Test zooming latency
    const zoomingStartTime = Date.now();
    await page.keyboard.down('Control');
    await page.mouse.wheel(0, 100);
    await page.keyboard.up('Control');
    await page.waitForSelector(S('board-canvas'));
    const zoomingEndTime = Date.now();
    const zoomingLatency = zoomingEndTime - zoomingStartTime;
    
    await page.screenshot({ path: 'artifacts/after-zooming.png', fullPage: true });
    
    // Step 5: Test node selection speed
    const selectionStartTime = Date.now();
    await page.click(S('node-250'));
    await page.waitForSelector(S('node-250'));
    const selectionEndTime = Date.now();
    const selectionSpeed = selectionEndTime - selectionStartTime;
    
    await page.screenshot({ path: 'artifacts/node-selected.png', fullPage: true });
    
    // Step 6: Check final memory usage
    const finalMemory = await page.evaluate(() => {
      return (performance as any).memory?.usedJSHeapSize || 0;
    });
    const memoryIncrease = finalMemory - initialMemory;
    const memoryIncreaseMB = memoryIncrease / (1024 * 1024);
    
    // Assertions - verify all performance metrics
    expect(renderingTime).toBeLessThan(2000);
    expect(panningLatency).toBeLessThan(100);
    expect(zoomingLatency).toBeLessThan(100);
    expect(selectionSpeed).toBeLessThan(50);
    expect(memoryIncreaseMB).toBeLessThan(100);
    
    // Verify nodes are visible
    await expect(page.locator(S('node-0'))).toBeAttached();
    await expect(page.locator(S('node-499'))).toBeAttached();
    
    console.log(`Performance Metrics:
      - Rendering Time: ${renderingTime}ms (target: <2000ms)
      - Panning Latency: ${panningLatency}ms (target: <100ms)
      - Zooming Latency: ${zoomingLatency}ms (target: <100ms)
      - Selection Speed: ${selectionSpeed}ms (target: <50ms)
      - Memory Increase: ${memoryIncreaseMB.toFixed(2)}MB (target: <100MB)
    `);
  });

  test('error case - verify performance degradation with excessive operations', async ({ page }) => {
    // Step 1: Add a moderate number of nodes
    await page.evaluate(() => {
      const canvas = document.querySelector('[data-testid="board-canvas"]');
      if (!canvas) throw new Error('Canvas not found');
      
      for (let i = 0; i < 100; i++) {
        const node = document.createElement('div');
        node.setAttribute('data-testid', `stress-node-${i}`);
        node.style.position = 'absolute';
        node.style.left = `${(i % 10) * 100}px`;
        node.style.top = `${Math.floor(i / 10) * 100}px`;
        node.style.width = '80px';
        node.style.height = '80px';
        node.textContent = `Stress ${i}`;
        canvas.appendChild(node);
      }
    });
    
    await page.waitForSelector(S('stress-node-99'));
    await page.screenshot({ path: 'artifacts/stress-nodes-added.png', fullPage: true });
    
    // Step 2: Perform rapid panning operations
    const rapidPanStart = Date.now();
    for (let i = 0; i < 5; i++) {
      await page.mouse.move(400 + i * 20, 400);
      await page.mouse.down();
      await page.mouse.move(200 - i * 20, 200);
      await page.mouse.up();
    }
    await page.waitForSelector(S('board-canvas'));
    const rapidPanTime = Date.now() - rapidPanStart;
    
    await page.screenshot({ path: 'artifacts/after-rapid-panning.png', fullPage: true });
    
    // Step 3: Perform rapid zoom operations
    const rapidZoomStart = Date.now();
    await page.keyboard.down('Control');
    for (let i = 0; i < 5; i++) {
      await page.mouse.wheel(0, 50);
    }
    await page.keyboard.up('Control');
    await page.waitForSelector(S('board-canvas'));
    const rapidZoomTime = Date.now() - rapidZoomStart;
    
    await page.screenshot({ path: 'artifacts/after-rapid-zooming.png', fullPage: true });
    
    // Assertions - verify system remains responsive under stress
    expect(rapidPanTime).toBeLessThan(1000);
    expect(rapidZoomTime).toBeLessThan(1000);
    await expect(page.locator(S('board-canvas'))).toBeVisible();
    await expect(page.locator(S('stress-node-0'))).toBeAttached();
    
    console.log(`Stress Test Metrics:
      - Rapid Pan Time: ${rapidPanTime}ms (target: <1000ms)
      - Rapid Zoom Time: ${rapidZoomTime}ms (target: <1000ms)
    `);
  });
});