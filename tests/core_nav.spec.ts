import { test, expect } from '@playwright/test';

const S = (id: string) => `[data-testid="${id}"]`;

test.use({
  screenshot: 'on',
  video: 'retain-on-failure',
  trace: 'retain-on-failure',
});

test.describe('Core Navigation Regression Baseline', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(process.env.BASE_URL || 'http://localhost:3000');
  });

  test('navigate to home page', async ({ page }) => {
    // Verify home page loads
    await page.waitForSelector(S('home-hero'), { timeout: 5000 });
    await page.screenshot({ path: 'artifacts/nav-home.png', fullPage: true });

    // Verify key elements
    await expect(page.locator(S('home-hero'))).toBeVisible();
    await expect(page.locator(S('nav-menu'))).toBeVisible();
  });

  test('navigate to about page', async ({ page }) => {
    // Click about link
    await page.click(S('about-link'));
    await page.waitForSelector(S('about-content'), { timeout: 5000 });
    await page.screenshot({ path: 'artifacts/nav-about.png', fullPage: true });

    // Verify about page content
    await expect(page.locator(S('about-content'))).toBeVisible();
    await expect(page).toHaveURL(/.*\/about/);
  });

  test('navigate to dashboard (authenticated)', async ({ page }) => {
    // This test assumes authentication context
    await page.click(S('dashboard-link'));
    await page.waitForSelector(S('dashboard-container'), { timeout: 5000 });
    await page.screenshot({ path: 'artifacts/nav-dashboard.png', fullPage: true });

    // Verify dashboard loaded
    await expect(page.locator(S('dashboard-container'))).toBeVisible();
    await expect(page).toHaveURL(/.*\/dashboard/);
  });

  test('navigate using browser back button', async ({ page }) => {
    // Navigate to about
    await page.click(S('about-link'));
    await page.waitForSelector(S('about-content'));

    // Go back
    await page.goBack();
    await page.waitForSelector(S('home-hero'), { timeout: 5000 });
    await page.screenshot({ path: 'artifacts/nav-back-button.png', fullPage: true });

    // Verify back on home
    await expect(page.locator(S('home-hero'))).toBeVisible();
  });

  test('responsive navigation menu', async ({ page }) => {
    // Test mobile menu if viewport is small
    await page.setViewportSize({ width: 375, height: 667 });
    await page.click(S('mobile-menu-button'));
    await page.waitForSelector(S('mobile-menu'), { timeout: 3000 });
    await page.screenshot({ path: 'artifacts/nav-mobile-menu.png', fullPage: true });

    // Verify mobile menu visible
    await expect(page.locator(S('mobile-menu'))).toBeVisible();

    // Click a navigation item
    await page.click(S('mobile-about-link'));
    await page.waitForSelector(S('about-content'), { timeout: 5000 });

    // Verify navigation worked
    await expect(page.locator(S('about-content'))).toBeVisible();
  });
});
