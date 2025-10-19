import { test, expect } from '@playwright/test';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

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

test.describe('Cloppy AI Docker Deployment', () => {
  const FRONTEND_URL = process.env.BASE_URL || 'http://localhost:3000';
  const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';
  const DB_PORT = process.env.DB_PORT || '5432';

  test.beforeEach(async ({ page }) => {
    // Navigate to frontend URL
    await page.goto(FRONTEND_URL);
    await page.waitForLoadState('networkidle');
  });

  test('happy path - verify all services are running and connected', async ({ page }) => {
    // Step 1: Verify frontend is accessible
    await page.waitForSelector(S('app-container'));
    await page.screenshot({ path: 'artifacts/frontend-loaded.png', fullPage: true });

    // Step 2: Check backend connectivity through health check
    await page.click(S('health-check-button'));
    await page.waitForSelector(S('backend-status'));
    await page.screenshot({ path: 'artifacts/backend-connected.png', fullPage: true });

    // Step 3: Verify database connection status
    await page.click(S('db-status-button'));
    await page.waitForSelector(S('database-status'));
    await page.screenshot({ path: 'artifacts/database-connected.png', fullPage: true });

    // Step 4: Test data persistence by creating a record
    await page.fill(S('data-input'), 'Test persistence data');
    await page.click(S('save-data-button'));
    await page.waitForSelector(S('save-success-message'));
    await page.screenshot({ path: 'artifacts/data-saved.png', fullPage: true });

    // Assertions - verify all services are operational
    await expect(page.locator(S('backend-status'))).toBeVisible();
    await expect(page.locator(S('backend-status'))).toContainText('Connected');
    await expect(page.locator(S('database-status'))).toBeVisible();
    await expect(page.locator(S('database-status'))).toContainText('Active');
    await expect(page.locator(S('save-success-message'))).toBeVisible();
    await expect(page.locator(S('save-success-message'))).toContainText('Data saved successfully');
  });

  test('happy path - test volume persistence across container restarts', async ({ page }) => {
    // Step 1: Create test data before restart
    await page.waitForSelector(S('data-input'));
    const testData = `Persistence Test ${Date.now()}`;
    await page.fill(S('data-input'), testData);
    await page.click(S('save-data-button'));
    await page.waitForSelector(S('save-success-message'));
    await page.screenshot({ path: 'artifacts/before-restart-data-saved.png', fullPage: true });

    // Step 2: Get the saved data ID for verification
    await page.waitForSelector(S('saved-data-id'));
    const dataId = await page.locator(S('saved-data-id')).textContent();
    await page.screenshot({ path: 'artifacts/saved-data-id.png', fullPage: true });

    // Step 3: Simulate container restart (restart backend and database containers)
    await page.click(S('restart-containers-button'));
    await page.waitForSelector(S('restart-initiated-message'));
    await page.screenshot({ path: 'artifacts/restart-initiated.png', fullPage: true });

    // Step 4: Wait for services to come back online
    await page.waitForSelector(S('services-online-indicator'), { timeout: 60000 });
    await page.screenshot({ path: 'artifacts/services-back-online.png', fullPage: true });

    // Step 5: Verify data persisted after restart
    await page.click(S('load-data-button'));
    await page.fill(S('data-id-input'), dataId || '');
    await page.click(S('fetch-data-button'));
    await page.waitForSelector(S('loaded-data-display'));
    await page.screenshot({ path: 'artifacts/data-after-restart.png', fullPage: true });

    // Assertions - verify data persistence
    await expect(page.locator(S('loaded-data-display'))).toBeVisible();
    await expect(page.locator(S('loaded-data-display'))).toContainText(testData);
    await expect(page.locator(S('services-online-indicator'))).toContainText('All services online');
  });

  test('happy path - verify network connectivity between containers', async ({ page }) => {
    // Step 1: Test frontend to backend communication
    await page.click(S('test-network-button'));
    await page.waitForSelector(S('network-test-results'));
    await page.screenshot({ path: 'artifacts/network-test-started.png', fullPage: true });

    // Step 2: Verify frontend can reach backend on port 8000
    await page.waitForSelector(S('frontend-backend-status'));
    await page.screenshot({ path: 'artifacts/frontend-backend-connection.png', fullPage: true });

    // Step 3: Verify backend can reach database on port 5432
    await page.waitForSelector(S('backend-database-status'));
    await page.screenshot({ path: 'artifacts/backend-database-connection.png', fullPage: true });

    // Step 4: Test end-to-end data flow
    await page.fill(S('network-test-input'), 'Network test data');
    await page.click(S('send-network-test-button'));
    await page.waitForSelector(S('network-test-response'));
    await page.screenshot({ path: 'artifacts/network-test-complete.png', fullPage: true });

    // Assertions - verify network connectivity
    await expect(page.locator(S('frontend-backend-status'))).toBeVisible();
    await expect(page.locator(S('frontend-backend-status'))).toContainText('Connected');
    await expect(page.locator(S('backend-database-status'))).toBeVisible();
    await expect(page.locator(S('backend-database-status'))).toContainText('Connected');
    await expect(page.locator(S('network-test-response'))).toContainText('Success');
  });

  test('happy path - test real-time features with WebSocket connection', async ({ page }) => {
    // Step 1: Establish WebSocket connection
    await page.click(S('connect-realtime-button'));
    await page.waitForSelector(S('websocket-status'));
    await page.screenshot({ path: 'artifacts/websocket-connecting.png', fullPage: true });

    // Step 2: Verify WebSocket connection is established
    await page.waitForSelector(S('websocket-connected-indicator'));
    await page.screenshot({ path: 'artifacts/websocket-connected.png', fullPage: true });

    // Step 3: Send real-time message
    const realtimeMessage = `Real-time test ${Date.now()}`;
    await page.fill(S('realtime-message-input'), realtimeMessage);
    await page.click(S('send-realtime-message-button'));
    await page.screenshot({ path: 'artifacts/realtime-message-sent.png', fullPage: true });

    // Step 4: Verify real-time message received
    await page.waitForSelector(S('realtime-message-received'));
    await page.screenshot({ path: 'artifacts/realtime-message-received.png', fullPage: true });

    // Step 5: Test real-time updates
    await page.click(S('trigger-realtime-update-button'));
    await page.waitForSelector(S('realtime-update-notification'));
    await page.screenshot({ path: 'artifacts/realtime-update-received.png', fullPage: true });

    // Assertions - verify real-time functionality
    await expect(page.locator(S('websocket-connected-indicator'))).toBeVisible();
    await expect(page.locator(S('websocket-connected-indicator'))).toContainText('Connected');
    await expect(page.locator(S('realtime-message-received'))).toContainText(realtimeMessage);
    await expect(page.locator(S('realtime-update-notification'))).toBeVisible();
    await expect(page.locator(S('realtime-update-notification'))).toContainText('Update received');
  });

  test('error case - handle backend service unavailability', async ({ page }) => {
    // Step 1: Stop backend service to simulate failure
    await page.click(S('stop-backend-button'));
    await page.waitForSelector(S('backend-stopped-message'));
    await page.screenshot({ path: 'artifacts/error-backend-stopped.png', fullPage: true });

    // Step 2: Attempt to interact with backend
    await page.fill(S('data-input'), 'Test data during failure');
    await page.click(S('save-data-button'));
    await page.waitForSelector(S('error-message'));
    await page.screenshot({ path: 'artifacts/error-backend-unavailable.png', fullPage: true });

    // Step 3: Verify error handling and user feedback
    await page.waitForSelector(S('connection-error-indicator'));
    await page.screenshot({ path: 'artifacts/error-connection-indicator.png', fullPage: true });

    // Assertions - verify error handling
    await expect(page.locator(S('error-message'))).toBeVisible();
    await expect(page.locator(S('error-message'))).toContainText('Backend service unavailable');
    await expect(page.locator(S('connection-error-indicator'))).toBeVisible();
    await expect(page.locator(S('connection-error-indicator'))).toContainText('Disconnected');
  });

  test('error case - handle database connection failure', async ({ page }) => {
    // Step 1: Simulate database connection failure
    await page.click(S('simulate-db-failure-button'));
    await page.waitForSelector(S('db-failure-simulated-message'));
    await page.screenshot({ path: 'artifacts/error-db-failure-simulated.png', fullPage: true });

    // Step 2: Attempt database operation
    await page.fill(S('data-input'), 'Test during DB failure');
    await page.click(S('save-data-button'));
    await page.waitForSelector(S('database-error-message'));
    await page.screenshot({ path: 'artifacts/error-database-operation-failed.png', fullPage: true });

    // Step 3: Check database status indicator
    await page.click(S('db-status-button'));
    await page.waitForSelector(S('database-status'));
    await page.screenshot({ path: 'artifacts/error-database-disconnected.png', fullPage: true });

    // Assertions - verify database error handling
    await expect(page.locator(S('database-error-message'))).toBeVisible();
    await expect(page.locator(S('database-error-message'))).toContainText('Database connection failed');
    await expect(page.locator(S('database-status'))).toContainText('Disconnected');
  });

  test('error case - handle real-time connection interruption', async ({ page }) => {
    // Step 1: Establish WebSocket connection
    await page.click(S('connect-realtime-button'));
    await page.waitForSelector(S('websocket-connected-indicator'));
    await page.screenshot({ path: 'artifacts/error-realtime-connected.png', fullPage: true });

    // Step 2: Simulate connection interruption
    await page.click(S('disconnect-realtime-button'));
    await page.waitForSelector(S('websocket-disconnected-indicator'));
    await page.screenshot({ path: 'artifacts/error-realtime-disconnected.png', fullPage: true });

    // Step 3: Attempt to send message while disconnected
    await page.fill(S('realtime-message-input'), 'Message during disconnection');
    await page.click(S('send-realtime-message-button'));
    await page.waitForSelector(S('realtime-error-message'));
    await page.screenshot({ path: 'artifacts/error-realtime-send-failed.png', fullPage: true });

    // Assertions - verify real-time error handling
    await expect(page.locator(S('websocket-disconnected-indicator'))).toBeVisible();
    await expect(page.locator(S('websocket-disconnected-indicator'))).toContainText('Disconnected');
    await expect(page.locator(S('realtime-error-message'))).toBeVisible();
    await expect(page.locator(S('realtime-error-message'))).toContainText('WebSocket connection not established');
  });
});