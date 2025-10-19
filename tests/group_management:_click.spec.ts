import { test, expect } from '@playwright/test';

const S = (id: string) => `[data-testid="${id}"]`;

test.use({
  screenshot: 'on',
  video: 'retain-on-failure',
  trace: 'retain-on-failure'
});

test.describe('group management: click group-create-btn to create geometric group, enter name in group-title-input to rename, drag group-resize-handle to resize, verify group deletion, test connecting group to AI chat using ai-chat-input and verify AI receives grouped node context. Save as cloppy_ai_group_management.spec.ts', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(process.env.BASE_URL!);
  });

  test('happy path', async ({ page }) => {
    // group management: click group-create-btn to create geometric group, enter name in group-title-input to rename, drag group-resize-handle to resize, verify group deletion, test connecting group to AI chat using ai-chat-input and verify AI receives grouped node context. Save as cloppy_ai_group_management.spec.ts

    // Take screenshots at key steps
    await page.screenshot({ path: 'screenshot-step-1.png' });

    // Add assertions
    await expect(page.locator(S('result'))).toBeVisible();
  });

  test('error case', async ({ page }) => {
    // Test error handling
    await expect(page.locator(S('error'))).toBeVisible();
  });
});
