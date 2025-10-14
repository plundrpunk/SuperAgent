"""
Example script to demonstrate Critic agent's enhanced feedback.
Run this to see sample rejection feedback output.
"""
from pathlib import Path
from agent_system.agents.critic import CriticAgent


def create_bad_test():
    """Create a test file with multiple issues."""
    return """
import { test, expect } from '@playwright/test';

test('checkout flow', async ({ page }) => {
  // Bad: hardcoded localhost
  await page.goto('http://localhost:3000/shop');

  // Bad: CSS class selector
  await page.locator('.product-card').first().click();

  // Bad: nth() selector
  const item = page.locator('.cart-item').nth(2);
  await item.click();

  // Bad: waitForTimeout
  await page.waitForTimeout(5000);

  // Too many steps follow...
  await page.locator('[data-testid="checkout-btn"]').click();
  await page.locator('[data-testid="email"]').fill('test@example.com');
  await page.locator('[data-testid="name"]').fill('Test User');
  await page.locator('[data-testid="address"]').fill('123 Main St');
  await page.locator('[data-testid="city"]').fill('Anytown');
  await page.locator('[data-testid="state"]').fill('CA');
  await page.locator('[data-testid="zip"]').fill('12345');
  await page.locator('[data-testid="card"]').fill('4111111111111111');
  await page.locator('[data-testid="exp"]').fill('12/25');
  await page.locator('[data-testid="cvv"]').fill('123');
  await page.locator('[data-testid="submit"]').click();

  // Good: proper assertion
  expect(await page.locator('[data-testid="confirmation"]').textContent()).toContain('Order Confirmed');
});
"""


def main():
    """Run example and print feedback."""
    # Create temp test file
    test_path = Path('/tmp/bad_test.spec.ts')
    test_path.write_text(create_bad_test())

    # Run Critic
    critic = CriticAgent()
    result = critic.execute(str(test_path))

    print("=" * 70)
    print("CRITIC AGENT - ENHANCED REJECTION FEEDBACK EXAMPLE")
    print("=" * 70)
    print()

    if result.success:
        print(f"Status: {result.data['status'].upper()}")
        print()

        if result.data['feedback']:
            print(result.data['feedback'])
            print()

        print("-" * 70)
        print("STRUCTURED ISSUES DATA:")
        print("-" * 70)
        for i, issue in enumerate(result.data['issues_found'], 1):
            print(f"\nIssue #{i}:")
            print(f"  Type: {issue['type']}")
            print(f"  Severity: {issue['severity']}")
            if 'line' in issue:
                print(f"  Line: {issue['line']}")
                print(f"  Matched: {issue['matched']}")
            if 'actual' in issue:
                print(f"  Actual: {issue['actual']}")
            if 'max' in issue:
                print(f"  Max: {issue['max']}")
            print(f"  Reason: {issue['reason']}")
            print(f"  Fix: {issue['fix']}")

        print()
        print("-" * 70)
        print("METADATA:")
        print("-" * 70)
        print(f"  Critical Issues: {result.metadata['critical_issues']}")
        print(f"  Warnings: {result.metadata['warnings']}")
        print(f"  Assertion Count: {result.metadata['assertion_count']}")
        print(f"  Anti-patterns Found: {result.metadata['anti_patterns_found']}")
        print(f"  Estimated Cost: ${result.data['estimated_cost_usd']:.4f}")
        print(f"  Estimated Duration: {result.data['estimated_duration_ms'] / 1000:.1f}s")
        print(f"  Execution Time: {result.execution_time_ms}ms")
    else:
        print(f"ERROR: {result.error}")

    print()
    print("=" * 70)


if __name__ == '__main__':
    main()
