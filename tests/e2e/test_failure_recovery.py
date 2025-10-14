"""
E2E Test: Failure Recovery with Medic

Tests the complete failure recovery workflow:
1. Test fails during execution or validation
2. Medic diagnoses the failure
3. Medic applies surgical fix
4. Regression tests run (before/after comparison)
5. Test re-executed and validated
6. Success with no new failures

This test validates the self-healing capabilities of the system.
"""
import pytest
import tempfile
import shutil
import json
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from agent_system.agents.runner import RunnerAgent
from agent_system.agents.medic import MedicAgent
from agent_system.agents.gemini import GeminiAgent
from agent_system.agents.scribe import ScribeAgent
from agent_system.state.redis_client import RedisClient
from agent_system.state.vector_client import VectorClient
from agent_system.hitl.queue import HITLQueue


class TestFailureRecovery:
    """
    Failure recovery and self-healing workflow tests.

    Tests Medic's ability to diagnose and fix test failures with regression safety.
    """

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_output_dir = Path(self.temp_dir) / "tests"
        self.test_output_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir = Path(self.temp_dir) / "artifacts"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

        # Mock clients
        self.mock_redis = Mock(spec=RedisClient)
        self.mock_vector = Mock(spec=VectorClient)
        self.mock_hitl = Mock(spec=HITLQueue)

        # Configure mocks
        self.mock_redis.get.return_value = None
        self.mock_redis.set.return_value = True
        self.mock_redis.client = Mock()

        self.mock_vector.search_test_patterns.return_value = []
        self.mock_hitl.add.return_value = True

        self.session_id = f"recovery_session_{int(time.time())}"
        self.task_id = f"recovery_task_{int(time.time())}"

        yield

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_runner_failure_medic_fix_success(self):
        """
        Test: Runner fails → Medic fixes → Runner succeeds

        Scenario: Test has a selector bug, Medic fixes it, test passes on retry
        """
        print("\n" + "="*80)
        print("TEST: Runner Failure → Medic Fix → Success")
        print("="*80)

        flow_start = time.time()
        total_cost = 0.0

        # ===== STEP 1: Create test with intentional bug =====
        print("\n=== STEP 1: Create test with selector bug ===")

        test_path = self.test_output_dir / "buggy_login.spec.ts"
        test_path.write_text("""
import { test, expect } from '@playwright/test';

test('login form', async ({ page }) => {
    await page.goto('/login');
    await page.locator('[data-testid="email"]').fill('test@example.com');
    await page.locator('[data-testid="password"]').fill('password123');
    await page.locator('[data-testid="wrong-button"]').click();  // BUG: wrong selector
    await expect(page).toHaveURL(/dashboard/);
});
""")

        print(f"✓ Test created with selector bug: wrong-button")

        # ===== STEP 2: Runner executes and fails =====
        print("\n=== STEP 2: Runner executes test (fails) ===")

        runner = RunnerAgent()

        mock_failure = Mock()
        mock_failure.returncode = 1
        mock_failure.stdout = """
Running 1 test using 1 worker

  ✗  buggy_login.spec.ts:7:1 › login form (1.5s)

    Error: Locator [data-testid="wrong-button"] not found

      at buggy_login.spec.ts:10:50

  1 failed (1.5s)
"""
        mock_failure.stderr = ""

        with patch('subprocess.run', return_value=mock_failure):
            runner_result_1 = runner.execute(str(test_path), timeout=60)

        # Runner should report failure
        assert not runner_result_1.success or runner_result_1.data['status'] == 'fail', \
            "Runner should detect test failure"

        error_message = "Locator [data-testid='wrong-button'] not found"
        total_cost += 0.005

        print(f"✓ Test failed as expected")
        print(f"  Error: {error_message}")
        print(f"  Cost: $0.005")

        # ===== STEP 3: Medic diagnoses and fixes =====
        print("\n=== STEP 3: Medic diagnoses and applies fix ===")

        # Mock Anthropic API response with fix
        mock_anthropic_response = Mock()
        mock_anthropic_response.content = [Mock(text="""
DIAGNOSIS: Selector data-testid="wrong-button" not found. The correct selector should be "login-button" or "submit-button".

CONFIDENCE: 0.85

FIX:
```typescript
import { test, expect } from '@playwright/test';

test('login form', async ({ page }) => {
    await page.goto('/login');
    await page.locator('[data-testid="email"]').fill('test@example.com');
    await page.locator('[data-testid="password"]').fill('password123');
    await page.locator('[data-testid="login-button"]').click();  // FIXED: correct selector
    await expect(page).toHaveURL(/dashboard/);
});
```
""")]
        mock_anthropic_response.usage = Mock(input_tokens=1000, output_tokens=300)

        mock_anthropic_client = Mock()
        mock_anthropic_client.messages.create = Mock(return_value=mock_anthropic_response)

        # Mock regression tests (baseline and after-fix)
        regression_calls = [0]

        def mock_regression(*args, **kwargs):
            result = Mock()
            regression_calls[0] += 1
            if regression_calls[0] == 1:
                # Baseline: 2 tests passing
                result.returncode = 0
                result.stdout = "2 passed (4.0s)"
            else:
                # After fix: 2 tests still passing (no regression)
                result.returncode = 0
                result.stdout = "2 passed (4.2s)"
            result.stderr = ""
            return result

        medic = MedicAgent(redis_client=self.mock_redis, hitl_queue=self.mock_hitl)

        with patch.object(medic, 'client', mock_anthropic_client):
            with patch('subprocess.run', side_effect=mock_regression):
                medic_result = medic.execute(
                    test_path=str(test_path),
                    error_message=error_message,
                    task_id=self.task_id,
                    feature="login_form"
                )

        assert medic_result.success, f"Medic should successfully fix: {medic_result.error}"
        assert medic_result.data['status'] == 'fix_applied'
        assert medic_result.data['comparison']['new_failures'] == 0, \
            "Fix should not introduce regressions"

        medic_cost = 0.015  # Sonnet cost
        total_cost += medic_cost

        print(f"✓ Medic applied fix")
        print(f"  Diagnosis: Selector updated to 'login-button'")
        print(f"  Confidence: 0.85")
        print(f"  Regressions: 0")
        print(f"  Cost: ${medic_cost:.4f}")

        # ===== STEP 4: Re-run test after fix =====
        print("\n=== STEP 4: Re-run test after Medic fix ===")

        mock_success = Mock()
        mock_success.returncode = 0
        mock_success.stdout = """
Running 1 test using 1 worker

  ✓  buggy_login.spec.ts:7:1 › login form (2.1s)

  1 passed (2.1s)
"""
        mock_success.stderr = ""

        with patch('subprocess.run', return_value=mock_success):
            runner_result_2 = runner.execute(str(test_path), timeout=60)

        assert runner_result_2.success, "Test should pass after fix"
        assert runner_result_2.data['status'] == 'pass'

        total_cost += 0.005

        print(f"✓ Test passed after fix")
        print(f"  Tests passed: 1")
        print(f"  Execution time: 2.1s")

        # ===== STEP 5: Verify recovery success =====
        print("\n=== STEP 5: Verify recovery workflow ===")

        flow_duration = time.time() - flow_start

        recovery_summary = {
            'initial_failure': True,
            'medic_fix_applied': medic_result.data['status'] == 'fix_applied',
            'no_regressions': medic_result.data['comparison']['new_failures'] == 0,
            'test_passed_after_fix': runner_result_2.data['status'] == 'pass',
            'total_cost': total_cost,
            'recovery_time_s': flow_duration
        }

        print(f"\n{'='*80}")
        print(f"RECOVERY WORKFLOW COMPLETED")
        print(f"{'='*80}")
        for key, value in recovery_summary.items():
            print(f"{key}: {value}")
        print(f"{'='*80}\n")

        # Assertions
        assert all([
            recovery_summary['medic_fix_applied'],
            recovery_summary['no_regressions'],
            recovery_summary['test_passed_after_fix']
        ])
        assert total_cost < 0.50

    def test_validation_failure_medic_fix_revalidate(self):
        """
        Test: Gemini validation fails → Medic fixes → Revalidation succeeds

        Scenario: Test executes but fails Gemini validation, Medic fixes, revalidation passes
        """
        print("\n" + "="*80)
        print("TEST: Validation Failure → Medic Fix → Revalidation Success")
        print("="*80)

        # Create test
        test_path = self.test_output_dir / "validation_issue.spec.ts"
        scribe = ScribeAgent(vector_client=self.mock_vector)

        scribe_result = scribe.execute(
            task_description="profile page validation",
            feature_name="Profile",
            output_path=str(test_path),
            complexity='easy'
        )

        assert scribe_result.success

        # Runner executes (passes locally)
        print("\n=== Runner executes test (passes) ===")

        runner = RunnerAgent()
        mock_runner_pass = Mock()
        mock_runner_pass.returncode = 0
        mock_runner_pass.stdout = "1 passed (1.8s)"
        mock_runner_pass.stderr = ""

        with patch('subprocess.run', return_value=mock_runner_pass):
            runner_result = runner.execute(str(test_path))

        assert runner_result.success
        print(f"✓ Test passed locally")

        # Gemini validation fails
        print("\n=== Gemini validation fails (assertion too weak) ===")

        gemini = GeminiAgent()
        mock_gemini_fail = Mock()
        mock_gemini_fail.returncode = 1
        mock_gemini_fail.stdout = json.dumps({
            'suites': [{
                'specs': [{
                    'tests': [{
                        'results': [{
                            'status': 'failed',
                            'error': {
                                'message': 'Expected profile name to be visible, but element was hidden'
                            }
                        }]
                    }]
                }]
            }]
        })

        with patch('subprocess.run', return_value=mock_gemini_fail):
            with patch.object(gemini, '_collect_screenshots', return_value=[]):
                gemini_result_1 = gemini.execute(str(test_path))

        assert not gemini_result_1.success
        print(f"✓ Validation failed: Assertion too weak")

        # Medic fixes
        print("\n=== Medic strengthens assertion ===")

        mock_anthropic_response = Mock()
        mock_anthropic_response.content = [Mock(text="""
DIAGNOSIS: Assertion is checking element existence but not visibility. Need to add explicit visibility check.

CONFIDENCE: 0.90

FIX:
```typescript
// Add explicit visibility check
await expect(page.locator('[data-testid="profile-name"]')).toBeVisible();
```
""")]
        mock_anthropic_response.usage = Mock(input_tokens=900, output_tokens=200)

        mock_anthropic_client = Mock()
        mock_anthropic_client.messages.create = Mock(return_value=mock_anthropic_response)

        mock_regression = Mock()
        mock_regression.returncode = 0
        mock_regression.stdout = "2 passed (4.0s)"
        mock_regression.stderr = ""

        medic = MedicAgent(redis_client=self.mock_redis, hitl_queue=self.mock_hitl)

        with patch.object(medic, 'client', mock_anthropic_client):
            with patch('subprocess.run', return_value=mock_regression):
                medic_result = medic.execute(
                    test_path=str(test_path),
                    error_message="Expected profile name to be visible",
                    task_id=self.task_id,
                    feature="profile"
                )

        assert medic_result.success
        print(f"✓ Medic applied fix: Added visibility assertion")

        # Revalidate
        print("\n=== Revalidate after fix ===")

        mock_gemini_success = Mock()
        mock_gemini_success.returncode = 0
        mock_gemini_success.stdout = json.dumps({
            'suites': [{
                'specs': [{
                    'tests': [{
                        'results': [{'status': 'passed', 'duration': 1900}]
                    }]
                }]
            }]
        })

        screenshot_path = self.artifacts_dir / "profile_validated.png"
        screenshot_path.write_text("screenshot")

        with patch('subprocess.run', return_value=mock_gemini_success):
            with patch.object(gemini, '_collect_screenshots', return_value=[str(screenshot_path)]):
                gemini_result_2 = gemini.execute(str(test_path))

        assert gemini_result_2.success
        assert gemini_result_2.data['rubric_validation']['passed']
        print(f"✓ Revalidation passed")

        print(f"\n✓ Validation → Fix → Revalidation workflow completed successfully")

    def test_medic_regression_detection(self):
        """
        Test: Medic detects and prevents regression introduction

        Scenario: Medic's fix would break existing tests, regression detected, escalated
        """
        print("\n" + "="*80)
        print("TEST: Medic Regression Detection")
        print("="*80)

        test_path = self.test_output_dir / "risky_fix.spec.ts"
        test_path.write_text("test content")

        # Mock Anthropic with fix that introduces regression
        mock_anthropic_response = Mock()
        mock_anthropic_response.content = [Mock(text="""
DIAGNOSIS: Need to update selector

CONFIDENCE: 0.85

FIX:
```typescript
// This fix will break other tests
await page.locator('[data-testid="new-selector"]').click();
```
""")]
        mock_anthropic_response.usage = Mock(input_tokens=1000, output_tokens=250)

        mock_anthropic_client = Mock()
        mock_anthropic_client.messages.create = Mock(return_value=mock_anthropic_response)

        # Mock regression: baseline passes, after-fix fails
        regression_counter = [0]

        def mock_regression_with_failure(*args, **kwargs):
            result = Mock()
            regression_counter[0] += 1
            if regression_counter[0] == 1:
                # Baseline: 3 tests passing
                result.returncode = 0
                result.stdout = "3 passed (5.0s)"
            else:
                # After fix: 2 passing, 1 failed (REGRESSION!)
                result.returncode = 1
                result.stdout = "2 passed, 1 failed (5.5s)"
            result.stderr = ""
            return result

        medic = MedicAgent(redis_client=self.mock_redis, hitl_queue=self.mock_hitl)

        print("\n=== Medic attempts fix ===")

        with patch.object(medic, 'client', mock_anthropic_client):
            with patch('subprocess.run', side_effect=mock_regression_with_failure):
                medic_result = medic.execute(
                    test_path=str(test_path),
                    error_message="Selector not found",
                    task_id=self.task_id,
                    feature="risky_feature"
                )

        # Medic should detect regression and escalate
        assert not medic_result.success, "Medic should reject fix that causes regression"
        assert medic_result.data['status'] == 'escalated_to_hitl'
        assert medic_result.data['reason'] == 'regression_detected'
        assert medic_result.data['comparison']['new_failures'] > 0

        print(f"✓ Regression detected")
        print(f"  New failures: {medic_result.data['comparison']['new_failures']}")
        print(f"  Status: {medic_result.data['status']}")
        print(f"  Reason: {medic_result.data['reason']}")

        # Verify HITL escalation
        assert self.mock_hitl.add.called, "Should escalate to HITL"

        hitl_task = self.mock_hitl.add.call_args[0][0]
        assert hitl_task['escalation_reason'] == 'regression_detected'
        assert hitl_task['task_id'] == self.task_id

        print(f"✓ Escalated to HITL")
        print(f"  HITL task ID: {hitl_task['task_id']}")
        print(f"  Reason: {hitl_task['escalation_reason']}")

    def test_multiple_medic_retry_attempts(self):
        """
        Test: Medic makes multiple attempts before succeeding

        Scenario: First fix fails, second fix succeeds
        """
        print("\n" + "="*80)
        print("TEST: Multiple Medic Retry Attempts")
        print("="*80)

        test_path = self.test_output_dir / "multi_attempt.spec.ts"
        test_path.write_text("test content")

        error_message = "Element timeout"

        # Configure Redis to track attempts
        attempt_counter = [0]

        def mock_redis_get(key):
            if 'medic:attempts:' in key:
                return str(attempt_counter[0]) if attempt_counter[0] > 0 else None
            return None

        def mock_redis_set(key, value, ttl=None):
            if 'medic:attempts:' in key:
                attempt_counter[0] = int(value)
            return True

        self.mock_redis.get.side_effect = mock_redis_get
        self.mock_redis.set.side_effect = mock_redis_set

        # First attempt: low confidence → escalate
        print("\n=== Attempt 1: Low confidence ===")

        mock_low_conf = Mock()
        mock_low_conf.content = [Mock(text="""
DIAGNOSIS: Not sure about the issue

CONFIDENCE: 0.3

FIX:
```typescript
// Uncertain fix
```
""")]
        mock_low_conf.usage = Mock(input_tokens=800, output_tokens=150)

        mock_anthropic_client = Mock()
        mock_anthropic_client.messages.create = Mock(return_value=mock_low_conf)

        mock_regression = Mock()
        mock_regression.returncode = 0
        mock_regression.stdout = "2 passed (4.0s)"
        mock_regression.stderr = ""

        medic = MedicAgent(redis_client=self.mock_redis, hitl_queue=self.mock_hitl)

        with patch.object(medic, 'client', mock_anthropic_client):
            with patch('subprocess.run', return_value=mock_regression):
                result_1 = medic.execute(
                    test_path=str(test_path),
                    error_message=error_message,
                    task_id=f"{self.task_id}_1",
                    feature="multi_attempt"
                )

        assert not result_1.success
        assert result_1.data['status'] == 'escalated_to_hitl'
        assert result_1.data['reason'] == 'low_confidence'

        print(f"✓ Attempt 1 escalated due to low confidence (0.3 < 0.7)")

        # Second attempt: high confidence → success
        print("\n=== Attempt 2: High confidence ===")

        attempt_counter[0] = 0  # Reset for new task

        mock_high_conf = Mock()
        mock_high_conf.content = [Mock(text="""
DIAGNOSIS: Selector needs waitForSelector with explicit timeout

CONFIDENCE: 0.90

FIX:
```typescript
await page.waitForSelector('[data-testid="element"]', { timeout: 10000 });
await page.locator('[data-testid="element"]').click();
```
""")]
        mock_high_conf.usage = Mock(input_tokens=850, output_tokens=200)

        mock_anthropic_client.messages.create = Mock(return_value=mock_high_conf)

        with patch.object(medic, 'client', mock_anthropic_client):
            with patch('subprocess.run', return_value=mock_regression):
                result_2 = medic.execute(
                    test_path=str(test_path),
                    error_message=error_message,
                    task_id=f"{self.task_id}_2",
                    feature="multi_attempt"
                )

        assert result_2.success
        assert result_2.data['status'] == 'fix_applied'
        assert result_2.data['comparison']['new_failures'] == 0

        print(f"✓ Attempt 2 succeeded with high confidence (0.90)")
        print(f"  Fix applied: Added waitForSelector")
        print(f"  Regressions: 0")

        print(f"\n✓ Multi-attempt recovery workflow completed")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
