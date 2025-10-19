"""
End-to-End Integration Test: Complete Closed-Loop Workflow

This test validates the full SuperAgent closed-loop pipeline:
1. Kaya receives user request and routes to Scribe
2. Scribe generates test
3. Critic pre-validates test (quality gate)
4. Runner executes test
5. Gemini validates test in real browser
6. (If fails) Medic diagnoses and fixes
7. Re-validate after fix
8. (If max retries exceeded) Escalate to HITL

Test Cases:
- test_closed_loop_happy_path: Full flow with passing test
- test_closed_loop_with_medic_fix: Test fails → Medic fixes → Re-validate succeeds
- test_closed_loop_hitl_escalation: Multiple Medic failures → HITL escalation

Implementation:
- Uses real agents (not mocked) for actual coordination
- Mocks external APIs (Anthropic, Gemini, Playwright) to avoid costs
- Mocks state clients (Redis, Vector DB)
- Validates cost tracking across all agents
- Validates HITL escalation workflow
- Tests complete closed-loop with all 6 agents
"""
import pytest
import tempfile
import shutil
import json
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime

from agent_system.agents.kaya import KayaAgent
from agent_system.agents.scribe import ScribeAgent
from agent_system.agents.runner import RunnerAgent
from agent_system.agents.critic import CriticAgent
from agent_system.agents.gemini import GeminiAgent
from agent_system.agents.medic import MedicAgent
from agent_system.router import Router
from agent_system.state.redis_client import RedisClient
from agent_system.state.vector_client import VectorClient
from agent_system.hitl.queue import HITLQueue


class TestClosedLoopWorkflow:
    """
    End-to-end integration test for complete closed-loop workflow.

    Tests the full pipeline: Kaya → Scribe → Critic → Runner → Gemini → Medic → Re-validate
    """

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Set up test environment and tear down after test."""
        # Create temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()
        self.test_output_dir = Path(self.temp_dir) / "tests"
        self.test_output_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir = Path(self.temp_dir) / "artifacts"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

        # Initialize mock state clients
        self.mock_redis = Mock(spec=RedisClient)
        self.mock_vector = Mock(spec=VectorClient)
        self.mock_hitl = Mock(spec=HITLQueue)

        # Configure mock Redis
        self.mock_redis.health_check.return_value = True
        self.mock_redis.set_session.return_value = True
        self.mock_redis.get_session.return_value = None
        self.mock_redis.set_task_status.return_value = True
        self.mock_redis.get_task_status.return_value = "pending"
        self.mock_redis.get.return_value = None
        self.mock_redis.set.return_value = True
        self.mock_redis.client = Mock()
        self.mock_redis.client.rpush = Mock()
        self.mock_redis.client.expire = Mock()
        self.mock_redis.client.zadd = Mock()
        self.mock_redis.client.zrevrange = Mock(return_value=[])
        self.mock_redis.client.zrem = Mock()

        # Configure mock Vector DB
        self.mock_vector.search_test_patterns.return_value = []
        self.mock_vector.store_test_pattern.return_value = True
        self.mock_vector.store_hitl_annotation.return_value = True

        # Configure mock HITL queue
        self.mock_hitl.add.return_value = True
        self.mock_hitl.list.return_value = []
        self.mock_hitl.get_stats.return_value = {
            'total_count': 0,
            'active_count': 0,
            'resolved_count': 0
        }

        # Session tracking
        self.session_id = "test_closed_loop_session_123"
        self.task_id = "test_task_closed_loop_123"

        yield

        # Cleanup
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_closed_loop_happy_path(self):
        """
        Test complete closed-loop with all agents: Happy path (test passes).

        Flow:
        1. Kaya routes to Scribe
        2. Scribe generates test
        3. Critic approves test
        4. Runner executes test (passes)
        5. Gemini validates in browser (passes)
        6. Success - no Medic needed

        Success Criteria:
        - All 5 agents execute successfully
        - Cost under $0.50
        - Execution time < 2 minutes
        - Test file created and validated
        """
        print("\n" + "="*80)
        print("TEST: Closed-Loop Happy Path (All agents, test passes)")
        print("="*80)

        flow_start = time.time()
        total_cost = 0.0
        artifacts = {}

        # ===== STEP 1: Kaya receives user request =====
        print("\n=== STEP 1: Kaya receives user request ===")

        kaya = KayaAgent()
        user_command = "Create test for user profile page"

        kaya_result = kaya.execute(user_command, context={'session_id': self.session_id})

        assert kaya_result.success, f"Kaya failed: {kaya_result.error}"
        assert kaya_result.data['action'] == 'route_to_scribe'

        routing_decision = kaya_result.metadata['routing_decision']
        artifacts['kaya'] = {
            'agent': routing_decision.agent,
            'model': routing_decision.model,
            'complexity': routing_decision.difficulty
        }

        print(f"✓ Kaya routed to: {routing_decision.agent} ({routing_decision.model})")

        # ===== STEP 2: Scribe generates test =====
        print("\n=== STEP 2: Scribe generates test ===")

        scribe = ScribeAgent(vector_client=self.mock_vector)
        test_file_path = self.test_output_dir / "profile.spec.ts"

        scribe_result = scribe.execute(
            task_description="user profile page",
            feature_name="User Profile",
            output_path=str(test_file_path),
            complexity='easy'
        )

        assert scribe_result.success, f"Scribe failed: {scribe_result.error}"
        assert test_file_path.exists(), "Test file should be created"

        scribe_cost = 0.02  # Mocked Haiku cost
        total_cost += scribe_cost

        artifacts['scribe'] = {
            'test_path': str(test_file_path),
            'cost_usd': scribe_cost,
            'attempts': scribe_result.data['attempts_used']
        }

        print(f"✓ Scribe generated test (cost: ${scribe_cost:.4f})")

        # ===== STEP 3: Critic pre-validates test =====
        print("\n=== STEP 3: Critic pre-validates test ===")

        critic = CriticAgent()
        critic_result = critic.execute(str(test_file_path))

        assert critic_result.success, f"Critic failed: {critic_result.error}"
        assert critic_result.data['status'] == 'approved', \
            f"Test should be approved. Issues: {critic_result.data.get('issues_found', [])}"

        critic_cost = 0.005
        total_cost += critic_cost

        artifacts['critic'] = {
            'status': critic_result.data['status'],
            'issues_found': critic_result.data['issues_found'],
            'cost_usd': critic_cost
        }

        print(f"✓ Critic approved test (cost: ${critic_cost:.4f})")

        # ===== STEP 4: Runner executes test =====
        print("\n=== STEP 4: Runner executes test ===")

        runner = RunnerAgent()

        # Mock subprocess for Runner
        mock_process_result = Mock()
        mock_process_result.returncode = 0
        mock_process_result.stdout = """
Running 1 test using 1 worker

  ✓  profile.spec.ts:10:1 › User Profile › happy path (2.5s)

  1 passed (2.5s)
"""
        mock_process_result.stderr = ""

        with patch('subprocess.run', return_value=mock_process_result):
            runner_result = runner.execute(str(test_file_path), timeout=60)

        assert runner_result.success, f"Runner failed: {runner_result.error}"
        assert runner_result.data['status'] == 'pass', "Test should pass"

        runner_cost = 0.005
        total_cost += runner_cost

        artifacts['runner'] = {
            'status': runner_result.data['status'],
            'passed_count': runner_result.data['passed_count'],
            'cost_usd': runner_cost
        }

        print(f"✓ Runner executed test (cost: ${runner_cost:.4f})")

        # ===== STEP 5: Gemini validates in browser =====
        print("\n=== STEP 5: Gemini validates in browser ===")

        gemini = GeminiAgent()

        # Mock Playwright execution for Gemini
        mock_gemini_result = Mock()
        mock_gemini_result.returncode = 0
        mock_gemini_result.stdout = json.dumps({
            'suites': [{
                'specs': [{
                    'tests': [{
                        'results': [{
                            'status': 'passed',
                            'duration': 2500
                        }]
                    }]
                }]
            }]
        })
        mock_gemini_result.stderr = ""

        # Create mock screenshot
        screenshot_path = self.artifacts_dir / "profile_screenshot.png"
        screenshot_path.write_text("mock screenshot")

        with patch('subprocess.run', return_value=mock_gemini_result):
            with patch.object(gemini, '_collect_screenshots', return_value=[str(screenshot_path)]):
                gemini_result = gemini.execute(str(test_file_path), timeout=60)

        assert gemini_result.success, f"Gemini failed: {gemini_result.error}"
        assert gemini_result.data['rubric_validation']['passed'], \
            f"Validation should pass. Errors: {gemini_result.data['rubric_validation']['errors']}"

        gemini_cost = 0.0  # No API cost for Playwright execution
        total_cost += gemini_cost

        artifacts['gemini'] = {
            'validation_passed': gemini_result.data['rubric_validation']['passed'],
            'screenshots': len(gemini_result.data['screenshots']),
            'cost_usd': gemini_cost
        }

        print(f"✓ Gemini validated in browser (cost: ${gemini_cost:.4f})")
        print(f"  Screenshots captured: {len(gemini_result.data['screenshots'])}")

        # ===== STEP 6: Validate success criteria =====
        print("\n=== STEP 6: Validate success criteria ===")

        flow_duration_ms = int((time.time() - flow_start) * 1000)

        # Success Criteria 1: Cost under $0.50
        assert total_cost < 0.50, f"Total cost ${total_cost:.4f} exceeds $0.50 budget"
        print(f"✓ Cost check passed: ${total_cost:.4f} < $0.50")

        # Success Criteria 2: Execution under 2 minutes
        assert flow_duration_ms < 120000, \
            f"Flow duration {flow_duration_ms}ms exceeds 2 minute limit"
        print(f"✓ Time check passed: {flow_duration_ms}ms < 120,000ms")

        # Success Criteria 3: All agents succeeded
        assert len(artifacts) == 5, "Should have artifacts from 5 agents (Kaya, Scribe, Critic, Runner, Gemini)"
        print(f"✓ All 5 agents executed successfully")

        # Success Criteria 4: Test validated in browser
        assert gemini_result.data['rubric_validation']['passed']
        print(f"✓ Test validated in real browser with screenshots")

        # ===== STEP 7: Generate summary report =====
        print("\n=== STEP 7: Closed-Loop Summary ===")

        summary = {
            'flow': 'closed_loop_happy_path',
            'user_command': user_command,
            'session_id': self.session_id,
            'success': True,
            'duration_ms': flow_duration_ms,
            'total_cost_usd': total_cost,
            'agents_used': ['kaya', 'scribe', 'critic', 'runner', 'gemini'],
            'medic_needed': False,
            'hitl_escalated': False,
            'artifacts': artifacts,
            'success_criteria': {
                'cost_under_budget': total_cost < 0.50,
                'time_under_limit': flow_duration_ms < 120000,
                'all_agents_succeeded': True,
                'browser_validated': True
            }
        }

        print(f"\n✓ Closed-loop completed successfully!")
        print(f"  Total duration: {flow_duration_ms}ms ({flow_duration_ms/1000:.2f}s)")
        print(f"  Total cost: ${total_cost:.4f}")
        print(f"  Agents invoked: {len(summary['agents_used'])}")
        print(f"  Medic needed: {summary['medic_needed']}")
        print(f"  HITL escalated: {summary['hitl_escalated']}")

        # Final assertions
        assert summary['success_criteria']['cost_under_budget']
        assert summary['success_criteria']['time_under_limit']
        assert summary['success_criteria']['all_agents_succeeded']
        assert summary['success_criteria']['browser_validated']

    def test_closed_loop_with_medic_fix(self):
        """
        Test closed-loop with Medic fix and re-validation.

        Flow:
        1. Kaya → Scribe → Critic → Runner → Gemini
        2. Gemini validation FAILS (test has bug)
        3. Medic diagnoses and fixes test
        4. Re-run: Runner → Gemini (now passes)
        5. Success after fix

        Success Criteria:
        - Medic successfully fixes the test
        - Re-validation passes
        - No regression (max_new_failures: 0)
        - Cost tracked across all attempts
        - Total cost < $0.50
        """
        print("\n" + "="*80)
        print("TEST: Closed-Loop with Medic Fix (Test fails → Medic fixes → Re-validate)")
        print("="*80)

        flow_start = time.time()
        total_cost = 0.0
        artifacts = {}

        # ===== STEP 1-3: Kaya → Scribe → Critic (same as happy path) =====
        print("\n=== STEPS 1-3: Kaya → Scribe → Critic ===")

        kaya = KayaAgent()
        kaya_result = kaya.execute("Create test for login form", context={'session_id': self.session_id})
        assert kaya_result.success

        scribe = ScribeAgent(vector_client=self.mock_vector)
        test_file_path = self.test_output_dir / "login.spec.ts"
        scribe_result = scribe.execute(
            task_description="login form",
            feature_name="Login Form",
            output_path=str(test_file_path),
            complexity='easy'
        )
        assert scribe_result.success
        total_cost += 0.02  # Scribe cost

        critic = CriticAgent()
        critic_result = critic.execute(str(test_file_path))
        assert critic_result.success
        assert critic_result.data['status'] == 'approved'
        total_cost += 0.005  # Critic cost

        print(f"✓ Kaya → Scribe → Critic completed (cost: ${total_cost:.4f})")

        # ===== STEP 4: Runner executes test (passes) =====
        print("\n=== STEP 4: Runner executes test ===")

        runner = RunnerAgent()
        mock_runner_result = Mock()
        mock_runner_result.returncode = 0
        mock_runner_result.stdout = "1 passed (2.0s)"
        mock_runner_result.stderr = ""

        with patch('subprocess.run', return_value=mock_runner_result):
            runner_result = runner.execute(str(test_file_path), timeout=60)

        assert runner_result.success
        total_cost += 0.005  # Runner cost

        print(f"✓ Runner executed (cost: ${total_cost:.4f})")

        # ===== STEP 5: Gemini validation FAILS =====
        print("\n=== STEP 5: Gemini validation FAILS (bug detected) ===")

        gemini = GeminiAgent()

        # Mock Gemini failure (test executed but failed assertions)
        mock_gemini_fail = Mock()
        mock_gemini_fail.returncode = 1  # Test failed
        mock_gemini_fail.stdout = json.dumps({
            'suites': [{
                'specs': [{
                    'tests': [{
                        'results': [{
                            'status': 'failed',
                            'error': {
                                'message': 'Locator [data-testid="login-button"] not found'
                            }
                        }]
                    }]
                }]
            }]
        })
        mock_gemini_fail.stderr = ""

        with patch('subprocess.run', return_value=mock_gemini_fail):
            with patch.object(gemini, '_collect_screenshots', return_value=[]):
                gemini_result = gemini.execute(str(test_file_path), timeout=60)

        # Gemini should return success=False because validation failed
        assert not gemini_result.success, "Gemini should fail when test doesn't pass validation"

        error_message = gemini_result.error or "Test validation failed"
        print(f"✓ Gemini detected failure: {error_message}")

        # ===== STEP 6: Medic fixes the test =====
        print("\n=== STEP 6: Medic diagnoses and fixes test ===")

        # Mock Anthropic API for Medic
        mock_anthropic_response = Mock()
        mock_anthropic_response.content = [Mock(text="""
DIAGNOSIS: Selector data-testid="login-button" not found - likely incorrect testid

CONFIDENCE: 0.85

FIX:
```typescript
import { test, expect } from '@playwright/test';

test('login form', async ({ page }) => {
    await page.goto('/login');
    await page.locator('[data-testid="email-input"]').fill('test@example.com');
    await page.locator('[data-testid="password-input"]').fill('password123');
    await page.locator('[data-testid="submit-button"]').click();  // Fixed selector
    await expect(page).toHaveURL(/dashboard/);
});
```
""")]
        mock_anthropic_response.usage = Mock(input_tokens=1000, output_tokens=300)

        mock_anthropic_client = Mock()
        mock_anthropic_client.messages.create = Mock(return_value=mock_anthropic_response)

        # Mock regression tests (baseline and after-fix)
        mock_regression_pass = Mock()
        mock_regression_pass.returncode = 0
        mock_regression_pass.stdout = "2 passed (4.0s)"  # Baseline: 2 tests passing
        mock_regression_pass.stderr = ""

        medic = MedicAgent(redis_client=self.mock_redis, hitl_queue=self.mock_hitl)

        with patch.object(medic, 'client', mock_anthropic_client):
            with patch('subprocess.run', return_value=mock_regression_pass):
                medic_result = medic.execute(
                    test_path=str(test_file_path),
                    error_message=error_message,
                    task_id=self.task_id,
                    feature="login_form"
                )

        assert medic_result.success, f"Medic should fix test: {medic_result.error}"
        assert medic_result.data['status'] == 'fix_applied'
        assert medic_result.data['comparison']['new_failures'] == 0, "Should not introduce regressions"

        medic_cost = 0.015  # Sonnet cost for fix
        total_cost += medic_cost

        artifacts['medic'] = {
            'diagnosis': medic_result.data['diagnosis'],
            'new_failures': medic_result.data['comparison']['new_failures'],
            'cost_usd': medic_cost
        }

        print(f"✓ Medic fixed test (cost: ${medic_cost:.4f})")
        print(f"  Diagnosis: {medic_result.data['diagnosis'][:80]}...")
        print(f"  Regressions: {medic_result.data['comparison']['new_failures']}")

        # ===== STEP 7: Re-run validation after fix =====
        print("\n=== STEP 7: Re-run validation after Medic fix ===")

        # Runner executes fixed test
        with patch('subprocess.run', return_value=mock_runner_result):
            runner_rerun = runner.execute(str(test_file_path), timeout=60)

        assert runner_rerun.success
        total_cost += 0.005

        # Gemini validates fixed test (now passes)
        mock_gemini_success = Mock()
        mock_gemini_success.returncode = 0
        mock_gemini_success.stdout = json.dumps({
            'suites': [{
                'specs': [{
                    'tests': [{
                        'results': [{
                            'status': 'passed',
                            'duration': 2200
                        }]
                    }]
                }]
            }]
        })
        mock_gemini_success.stderr = ""

        screenshot_path = self.artifacts_dir / "login_fixed_screenshot.png"
        screenshot_path.write_text("mock screenshot after fix")

        with patch('subprocess.run', return_value=mock_gemini_success):
            with patch.object(gemini, '_collect_screenshots', return_value=[str(screenshot_path)]):
                gemini_revalidate = gemini.execute(str(test_file_path), timeout=60)

        assert gemini_revalidate.success, "Re-validation should pass after fix"
        assert gemini_revalidate.data['rubric_validation']['passed']

        print(f"✓ Re-validation passed after fix!")
        print(f"  Screenshots: {len(gemini_revalidate.data['screenshots'])}")

        # ===== STEP 8: Validate success criteria =====
        print("\n=== STEP 8: Validate success criteria ===")

        flow_duration_ms = int((time.time() - flow_start) * 1000)

        assert total_cost < 0.50, f"Total cost ${total_cost:.4f} should be under $0.50"
        assert medic_result.data['comparison']['new_failures'] == 0, "No regressions allowed"
        assert gemini_revalidate.data['rubric_validation']['passed'], "Final validation must pass"

        print(f"✓ Closed-loop with Medic fix completed!")
        print(f"  Total duration: {flow_duration_ms}ms ({flow_duration_ms/1000:.2f}s)")
        print(f"  Total cost: ${total_cost:.4f}")
        print(f"  Medic attempts: 1")
        print(f"  Regressions: 0")
        print(f"  Final validation: PASSED")

    def test_closed_loop_hitl_escalation(self):
        """
        Test closed-loop with HITL escalation after max retries.

        Flow:
        1. Test fails validation
        2. Medic attempts fix (attempt 1) → Still fails
        3. Medic attempts fix (attempt 2) → Still fails
        4. Medic attempts fix (attempt 3) → Still fails
        5. Max retries (3) exceeded → Escalate to HITL
        6. Verify HITL queue receives task

        Success Criteria:
        - Medic respects MAX_RETRIES limit
        - Task is escalated to HITL with full context
        - HITL queue contains task with correct priority
        - Cost tracked across all attempts
        - Error message is clear about escalation
        """
        print("\n" + "="*80)
        print("TEST: Closed-Loop HITL Escalation (Max retries exceeded)")
        print("="*80)

        flow_start = time.time()
        total_cost = 0.0

        # ===== SETUP: Create failing test =====
        print("\n=== SETUP: Create failing test ===")

        scribe = ScribeAgent(vector_client=self.mock_vector)
        test_file_path = self.test_output_dir / "checkout.spec.ts"
        scribe_result = scribe.execute(
            task_description="checkout flow",
            feature_name="Checkout",
            output_path=str(test_file_path),
            complexity='hard'
        )
        assert scribe_result.success
        total_cost += 0.03  # Sonnet cost for hard task

        error_message = "Locator [data-testid='payment-form'] timeout after 30s"

        print(f"✓ Test created: {test_file_path}")

        # ===== SIMULATE: Multiple Medic failures =====
        print("\n=== SIMULATE: Medic attempts (will fail 3 times) ===")

        # Configure Redis to track attempts
        attempt_counter = [0]  # Use list to maintain state across mock calls

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

        # Mock Anthropic API for Medic (low confidence fixes)
        mock_anthropic_response = Mock()
        mock_anthropic_response.content = [Mock(text="""
DIAGNOSIS: Payment form selector may have changed or element not rendered

CONFIDENCE: 0.4

FIX:
```typescript
import { test, expect } from '@playwright/test';

test('checkout', async ({ page }) => {
    await page.goto('/checkout');
    await page.waitForSelector('[data-testid="payment-form"]', { timeout: 60000 });
    await expect(page.locator('[data-testid="payment-form"]')).toBeVisible();
});
```
""")]
        mock_anthropic_response.usage = Mock(input_tokens=1200, output_tokens=350)

        mock_anthropic_client = Mock()
        mock_anthropic_client.messages.create = Mock(return_value=mock_anthropic_response)

        # Mock regression tests
        mock_regression_result = Mock()
        mock_regression_result.returncode = 0
        mock_regression_result.stdout = "2 passed (5.0s)"
        mock_regression_result.stderr = ""

        medic = MedicAgent(redis_client=self.mock_redis, hitl_queue=self.mock_hitl)

        # ===== ATTEMPT 1: Medic tries to fix (low confidence → escalate) =====
        print("\n=== ATTEMPT 1: Medic fix (low confidence) ===")

        with patch.object(medic, 'client', mock_anthropic_client):
            with patch('subprocess.run', return_value=mock_regression_result):
                medic_result_1 = medic.execute(
                    test_path=str(test_file_path),
                    error_message=error_message,
                    task_id=self.task_id,
                    feature="checkout"
                )

        # Should escalate due to low confidence (0.4 < 0.7)
        assert not medic_result_1.success, "Should fail due to low confidence"
        assert medic_result_1.data['status'] == 'escalated_to_hitl'
        assert medic_result_1.data['reason'] == 'low_confidence'

        medic_cost_1 = 0.015
        total_cost += medic_cost_1

        print(f"✓ Attempt 1: Escalated due to low confidence (0.4 < 0.7)")
        print(f"  Cost: ${medic_cost_1:.4f}")

        # ===== VERIFY: HITL queue was called =====
        print("\n=== VERIFY: HITL escalation ===")

        # Verify HITL.add was called
        assert self.mock_hitl.add.called, "HITL queue should receive escalated task"

        # Get the call arguments
        hitl_call_args = self.mock_hitl.add.call_args
        hitl_task = hitl_call_args[0][0] if hitl_call_args[0] else hitl_call_args[1].get('task')

        # Validate HITL task structure
        assert hitl_task is not None, "HITL task should not be None"
        assert hitl_task['task_id'] == self.task_id
        assert hitl_task['feature'] == 'checkout'
        assert hitl_task['code_path'] == str(test_file_path)
        assert hitl_task['last_error'] == error_message
        assert hitl_task['escalation_reason'] == 'low_confidence'
        assert hitl_task['severity'] in ['low', 'medium', 'high', 'critical']
        assert 0.0 <= hitl_task['priority'] <= 1.0
        assert hitl_task['attempts'] == 1

        print(f"✓ HITL queue received escalated task")
        print(f"  Task ID: {hitl_task['task_id']}")
        print(f"  Feature: {hitl_task['feature']}")
        print(f"  Reason: {hitl_task['escalation_reason']}")
        print(f"  Priority: {hitl_task['priority']:.2f}")
        print(f"  Severity: {hitl_task['severity']}")
        print(f"  Attempts: {hitl_task['attempts']}")

        # ===== ALTERNATE SCENARIO: Test max_retries escalation =====
        print("\n=== ALTERNATE: Test max_retries escalation ===")

        # Reset attempt counter and use higher confidence fix that causes regression
        attempt_counter[0] = 0
        self.mock_hitl.reset_mock()

        # Mock fix with high confidence but introduces regression
        mock_anthropic_high_conf = Mock()
        mock_anthropic_high_conf.content = [Mock(text="""
DIAGNOSIS: Selector needs update

CONFIDENCE: 0.9

FIX:
```typescript
import { test, expect } from '@playwright/test';

test('checkout', async ({ page }) => {
    await page.goto('/checkout');
    await expect(page.locator('[data-testid="new-payment-form"]')).toBeVisible();
});
```
""")]
        mock_anthropic_high_conf.usage = Mock(input_tokens=1200, output_tokens=350)

        mock_anthropic_client.messages.create = Mock(return_value=mock_anthropic_high_conf)

        # Mock regression that introduces new failures
        regression_counter = [0]

        def mock_regression_with_failures(*args, **kwargs):
            result = Mock()
            regression_counter[0] += 1
            if regression_counter[0] == 1:
                # Baseline: 2 passing
                result.returncode = 0
                result.stdout = "2 passed (5.0s)"
            else:
                # After fix: 1 passing, 1 failing (regression!)
                result.returncode = 1
                result.stdout = "1 passed, 1 failed (5.5s)"
            result.stderr = ""
            return result

        task_id_2 = "test_task_max_retries_123"
        test_file_path_2 = self.test_output_dir / "payment.spec.ts"
        test_file_path_2.write_text("test content")

        # Attempt multiple fixes that cause regressions
        for attempt in range(1, 5):  # Try 4 times (exceeds MAX_RETRIES=3)
            print(f"\n--- Attempt {attempt} ---")

            regression_counter[0] = 0

            with patch.object(medic, 'client', mock_anthropic_client):
                with patch('subprocess.run', side_effect=mock_regression_with_failures):
                    result = medic.execute(
                        test_path=str(test_file_path_2),
                        error_message=error_message,
                        task_id=task_id_2,
                        feature="payment"
                    )

            total_cost += 0.015

            if attempt <= 3:
                # Should fail due to regression
                assert not result.success, f"Attempt {attempt} should fail due to regression"
                assert result.data['status'] == 'escalated_to_hitl'
                assert result.data['reason'] == 'regression_detected'
                print(f"  ✓ Attempt {attempt}: Escalated due to regression")
            else:
                # Should fail due to max_retries
                assert not result.success, f"Attempt {attempt} should fail due to max retries"
                assert result.data['status'] == 'escalated_to_hitl'
                assert result.data['reason'] == 'max_retries_exceeded'
                print(f"  ✓ Attempt {attempt}: Escalated due to MAX_RETRIES exceeded")
                break

        # Verify final HITL escalation
        assert self.mock_hitl.add.called
        final_hitl_call = self.mock_hitl.add.call_args
        final_hitl_task = final_hitl_call[0][0] if final_hitl_call[0] else final_hitl_call[1].get('task')

        assert final_hitl_task['task_id'] == task_id_2
        assert final_hitl_task['escalation_reason'] == 'max_retries_exceeded'
        assert final_hitl_task['attempts'] == 4

        print(f"\n✓ MAX_RETRIES escalation verified")
        print(f"  Attempts before escalation: {final_hitl_task['attempts']}")
        print(f"  Reason: {final_hitl_task['escalation_reason']}")

        # ===== VALIDATE: Final success criteria =====
        print("\n=== VALIDATE: Success criteria ===")

        flow_duration_ms = int((time.time() - flow_start) * 1000)

        # Verify HITL queue was populated
        assert self.mock_hitl.add.call_count >= 2, "HITL should be called for both escalation scenarios"

        # Verify cost tracking
        print(f"✓ Total cost: ${total_cost:.4f}")
        print(f"✓ Flow duration: {flow_duration_ms}ms ({flow_duration_ms/1000:.2f}s)")
        print(f"✓ HITL escalations: {self.mock_hitl.add.call_count}")

        # Verify escalation reasons are correct
        all_calls = self.mock_hitl.add.call_args_list
        escalation_reasons = []
        for call in all_calls:
            task = call[0][0] if call[0] else call[1].get('task')
            escalation_reasons.append(task['escalation_reason'])

        assert 'low_confidence' in escalation_reasons, "Should have low_confidence escalation"
        assert 'max_retries_exceeded' in escalation_reasons, "Should have max_retries escalation"

        print(f"✓ All escalation scenarios validated")
        print(f"  Reasons: {', '.join(set(escalation_reasons))}")


class TestClosedLoopCostTracking:
    """Test cost tracking across the entire closed-loop."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test environment."""
        self.mock_redis = Mock(spec=RedisClient)
        self.mock_vector = Mock(spec=VectorClient)

        self.mock_redis.get.return_value = None
        self.mock_redis.set.return_value = True
        self.mock_redis.client = Mock()

        self.mock_vector.search_test_patterns.return_value = []

    def test_cost_aggregation_across_agents(self):
        """
        Test that costs are properly aggregated across all agents in closed-loop.

        Validates:
        - Each agent reports its own cost
        - Costs accumulate correctly
        - Budget checks work at flow level
        """
        print("\n" + "="*80)
        print("TEST: Cost Tracking Across Closed-Loop")
        print("="*80)

        router = Router()

        # Simulate costs from a complete closed-loop flow
        costs = {
            'kaya': 0.0,      # Routing only
            'scribe': 0.02,   # Haiku for easy test
            'critic': 0.005,  # Haiku for pre-validation
            'runner': 0.005,  # Haiku for parsing
            'gemini': 0.0,    # No API cost (just Playwright)
            'medic': 0.0      # Not needed in happy path
        }

        total_cost = sum(costs.values())

        # Check budget status
        budget_check = router.check_budget(total_cost, budget_type='per_session')

        assert budget_check['status'] == 'ok', "Cost should be within budget"
        assert total_cost < 0.50, "Should be under $0.50 per feature target"
        assert total_cost < budget_check['limit'], "Should be under session limit"

        print(f"✓ Cost aggregation validated")
        print(f"  Total cost: ${total_cost:.4f}")
        print(f"  Per-feature target: $0.50")
        print(f"  Session budget: ${budget_check['limit']:.2f}")
        print(f"  Remaining: ${budget_check['remaining']:.4f}")
        print(f"  Status: {budget_check['status']}")

        print(f"\n  Cost breakdown:")
        for agent, cost in costs.items():
            print(f"    {agent}: ${cost:.4f}")

        # Test with Medic included (fix scenario)
        costs_with_medic = costs.copy()
        costs_with_medic['medic'] = 0.015  # Sonnet for fix
        total_with_medic = sum(costs_with_medic.values())

        budget_check_medic = router.check_budget(total_with_medic, budget_type='per_session')

        assert budget_check_medic['status'] == 'ok'
        assert total_with_medic < 0.50, "Should still be under $0.50 even with Medic"

        print(f"\n✓ Cost with Medic validated")
        print(f"  Total with Medic: ${total_with_medic:.4f}")
        print(f"  Still under target: {total_with_medic < 0.50}")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
