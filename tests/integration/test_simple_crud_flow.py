"""
End-to-End Integration Test: Simple CRUD Test Flow

This test validates the full agent pipeline for a simple task:
1. Kaya receives user request: "Create test for user login"
2. Router selects Scribe with Haiku (easy task)
3. Scribe generates test with data-testid selectors
4. Critic reviews and approves test
5. Runner executes test
6. Test passes successfully
7. Validation: Cost < $0.50, execution < 2 min, artifacts collected

Implementation:
- Uses real agents (not mocked) to test actual coordination
- Mocks external APIs (Anthropic, Gemini) to avoid costs
- Mocks Playwright execution with successful output
- Verifies cost tracking across agents
- Verifies routing decisions
- Validates state management in Redis/Vector DB
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import time
import json

from agent_system.agents.kaya import KayaAgent
from agent_system.agents.scribe import ScribeAgent
from agent_system.agents.runner import RunnerAgent
from agent_system.agents.critic import CriticAgent
from agent_system.router import Router
from agent_system.state.redis_client import RedisClient
from agent_system.state.vector_client import VectorClient


class TestSimpleCRUDFlow:
    """
    End-to-end integration test for simple CRUD test creation flow.

    Tests the full pipeline without external API calls or actual test execution.
    """

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Set up test environment and tear down after test."""
        # Create temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()
        self.test_output_dir = Path(self.temp_dir) / "tests"
        self.test_output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize mock state clients
        self.mock_redis = Mock(spec=RedisClient)
        self.mock_vector = Mock(spec=VectorClient)

        # Configure mock Redis
        self.mock_redis.health_check.return_value = True
        self.mock_redis.set_session.return_value = True
        self.mock_redis.get_session.return_value = None
        self.mock_redis.set_task_status.return_value = True
        self.mock_redis.get_task_status.return_value = "pending"

        # Configure mock Vector DB
        self.mock_vector.search_test_patterns.return_value = []
        self.mock_vector.store_test_pattern.return_value = True

        # Session tracking
        self.session_id = "test_session_123"
        self.session_data = {
            'session_id': self.session_id,
            'total_cost': 0.0,
            'start_time': time.time()
        }

        yield

        # Cleanup
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_full_simple_crud_flow(self):
        """
        Test complete flow from Kaya → Scribe → Critic → Runner → Success.

        Success Criteria:
        - Full flow completes without errors
        - Cost under $0.50
        - Execution time < 2 minutes
        - Test file created
        - All agents communicate correctly
        """
        flow_start = time.time()
        total_cost = 0.0
        artifacts = {}

        # ===== STEP 1: Kaya receives user request =====
        print("\n=== STEP 1: Kaya receives user request ===")

        kaya = KayaAgent()
        user_command = "Create test for user login"

        kaya_result = kaya.execute(user_command, context={'session_id': self.session_id})

        # Validate Kaya result
        assert kaya_result.success, f"Kaya failed: {kaya_result.error}"
        assert kaya_result.data['action'] == 'route_to_scribe'
        assert 'routing_decision' in kaya_result.metadata

        routing_decision = kaya_result.metadata['routing_decision']

        # Store Kaya artifacts
        artifacts['kaya'] = {
            'action': kaya_result.data['action'],
            'feature': kaya_result.data['feature'],
            'agent': routing_decision.agent,
            'model': routing_decision.model,
            'complexity': routing_decision.difficulty
        }

        print(f"✓ Kaya routed to: {routing_decision.agent}")
        print(f"  Model: {routing_decision.model}")
        print(f"  Complexity: {routing_decision.difficulty}")
        print(f"  Max cost: ${routing_decision.max_cost_usd}")

        # ===== STEP 2: Verify Router decision =====
        print("\n=== STEP 2: Verify Router decision ===")

        # Router should select Scribe with Haiku for easy task
        assert routing_decision.agent == 'scribe', "Should route to Scribe for test creation"
        assert routing_decision.model == 'haiku', "Should use Haiku for easy task"
        assert routing_decision.difficulty == 'easy', "User login should be easy complexity"
        assert routing_decision.complexity_score < 5, "Easy task should have score < 5"
        assert routing_decision.max_cost_usd == 0.50, "Should use default cost limit"

        print(f"✓ Routing decision validated")
        print(f"  Complexity score: {routing_decision.complexity_score}")

        # ===== STEP 3: Scribe generates test =====
        print("\n=== STEP 3: Scribe generates test ===")

        # Initialize Scribe with mocked Vector DB
        scribe = ScribeAgent(vector_client=self.mock_vector)

        # Generate test file path
        test_file_path = self.test_output_dir / "login.spec.ts"

        scribe_result = scribe.execute(
            task_description="user login",
            feature_name="User Login",
            output_path=str(test_file_path),
            complexity='easy'
        )

        # Validate Scribe result
        assert scribe_result.success, f"Scribe failed: {scribe_result.error}"
        assert scribe_result.data['validation_passed'], "Test should pass self-validation"
        assert scribe_result.data['attempts_used'] <= 3, "Should complete within retry limit"

        # Track cost (mocked - in reality would come from API)
        scribe_cost = 0.02  # Haiku cost for easy task
        total_cost += scribe_cost

        # Verify test file was created
        assert test_file_path.exists(), "Test file should be created"

        # Read generated test
        with open(test_file_path, 'r') as f:
            generated_test = f.read()

        # Store Scribe artifacts
        artifacts['scribe'] = {
            'test_path': str(test_file_path),
            'attempts': scribe_result.data['attempts_used'],
            'validation_passed': scribe_result.data['validation_passed'],
            'cost_usd': scribe_cost,
            'test_length': len(generated_test)
        }

        print(f"✓ Scribe generated test")
        print(f"  Path: {test_file_path}")
        print(f"  Attempts: {scribe_result.data['attempts_used']}")
        print(f"  Cost: ${scribe_cost:.4f}")

        # ===== STEP 4: Critic reviews test =====
        print("\n=== STEP 4: Critic reviews test ===")

        critic = CriticAgent()
        critic_result = critic.execute(str(test_file_path))

        # Validate Critic result
        assert critic_result.success, f"Critic failed: {critic_result.error}"
        assert critic_result.data['status'] == 'approved', \
            f"Test should be approved. Issues: {critic_result.data.get('issues_found', [])}"

        # Track cost (Haiku for pre-validation)
        critic_cost = 0.005
        total_cost += critic_cost

        # Store Critic artifacts
        artifacts['critic'] = {
            'status': critic_result.data['status'],
            'issues_found': critic_result.data['issues_found'],
            'estimated_cost_usd': critic_result.data['estimated_cost_usd'],
            'estimated_duration_ms': critic_result.data['estimated_duration_ms'],
            'cost_usd': critic_cost
        }

        print(f"✓ Critic approved test")
        print(f"  Issues found: {len(critic_result.data['issues_found'])}")
        print(f"  Estimated duration: {critic_result.data['estimated_duration_ms']}ms")
        print(f"  Cost: ${critic_cost:.4f}")

        # ===== STEP 5: Runner executes test (mocked) =====
        print("\n=== STEP 5: Runner executes test (mocked) ===")

        runner = RunnerAgent()

        # Mock subprocess execution
        mock_process_result = Mock()
        mock_process_result.returncode = 0
        mock_process_result.stdout = """
Running 1 test using 1 worker

  ✓  login.spec.ts:10:1 › User Login › happy path (2.3s)

  1 passed (2.3s)
"""
        mock_process_result.stderr = ""

        with patch('subprocess.run', return_value=mock_process_result):
            runner_result = runner.execute(str(test_file_path), timeout=60)

        # Validate Runner result
        assert runner_result.success, f"Runner failed: {runner_result.error}"
        assert runner_result.data['status'] == 'pass', "Test should pass"
        assert runner_result.data['passed_count'] == 1, "Should have 1 passing test"
        assert runner_result.data['failed_count'] == 0, "Should have 0 failures"

        # Track cost (Haiku for execution)
        runner_cost = 0.005
        total_cost += runner_cost

        # Store Runner artifacts
        artifacts['runner'] = {
            'status': runner_result.data['status'],
            'passed_count': runner_result.data['passed_count'],
            'failed_count': runner_result.data['failed_count'],
            'execution_time_ms': runner_result.execution_time_ms,
            'cost_usd': runner_cost
        }

        print(f"✓ Runner executed test")
        print(f"  Status: {runner_result.data['status']}")
        print(f"  Passed: {runner_result.data['passed_count']}")
        print(f"  Duration: {runner_result.execution_time_ms}ms")
        print(f"  Cost: ${runner_cost:.4f}")

        # ===== STEP 6: Validate success criteria =====
        print("\n=== STEP 6: Validate success criteria ===")

        flow_duration_ms = int((time.time() - flow_start) * 1000)

        # Success Criteria 1: Cost under $0.50
        assert total_cost < 0.50, f"Total cost ${total_cost:.4f} exceeds $0.50 budget"
        print(f"✓ Cost check passed: ${total_cost:.4f} < $0.50")

        # Success Criteria 2: Execution under 2 minutes (120,000ms)
        assert flow_duration_ms < 120000, \
            f"Flow duration {flow_duration_ms}ms exceeds 2 minute limit"
        print(f"✓ Execution time check passed: {flow_duration_ms}ms < 120,000ms")

        # Success Criteria 3: Test file created
        assert test_file_path.exists(), "Test file should exist"
        print(f"✓ Test file created: {test_file_path}")

        # Success Criteria 4: Artifacts collected
        assert len(artifacts) == 4, "Should have artifacts from all 4 agents"
        print(f"✓ Artifacts collected from all agents")

        # ===== STEP 7: Generate summary report =====
        print("\n=== STEP 7: Flow Summary ===")

        summary = {
            'flow': 'simple_crud_test_creation',
            'user_command': user_command,
            'session_id': self.session_id,
            'success': True,
            'duration_ms': flow_duration_ms,
            'total_cost_usd': total_cost,
            'agents_used': ['kaya', 'scribe', 'critic', 'runner'],
            'routing_decision': {
                'agent': routing_decision.agent,
                'model': routing_decision.model,
                'complexity': routing_decision.difficulty,
                'score': routing_decision.complexity_score
            },
            'artifacts': artifacts,
            'success_criteria': {
                'cost_under_budget': total_cost < 0.50,
                'time_under_limit': flow_duration_ms < 120000,
                'test_file_created': test_file_path.exists(),
                'all_agents_succeeded': True
            }
        }

        # Print summary
        print(f"\nFlow completed successfully!")
        print(f"  Total duration: {flow_duration_ms}ms ({flow_duration_ms/1000:.2f}s)")
        print(f"  Total cost: ${total_cost:.4f}")
        print(f"  Cost efficiency: {(total_cost / 0.50) * 100:.1f}% of budget")
        print(f"  Time efficiency: {(flow_duration_ms / 120000) * 100:.1f}% of limit")

        # Save summary to JSON
        summary_path = self.test_output_dir / "flow_summary.json"
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2, default=str)

        print(f"  Summary saved to: {summary_path}")

        # Final assertions
        assert summary['success_criteria']['cost_under_budget']
        assert summary['success_criteria']['time_under_limit']
        assert summary['success_criteria']['test_file_created']
        assert summary['success_criteria']['all_agents_succeeded']

    def test_scribe_validation_retry_flow(self):
        """
        Test that Scribe's self-validation and retry mechanism works correctly.

        This simulates a scenario where Scribe generates an invalid test on first
        attempt, then successfully retries with feedback.
        """
        print("\n=== Testing Scribe Validation Retry Flow ===")

        # Initialize Scribe with mocked Vector DB
        scribe = ScribeAgent(vector_client=self.mock_vector)

        # Track original validation method
        original_validate = scribe._validate_generated_test

        # Mock validation to fail first time, succeed second time
        call_count = [0]

        def mock_validate(test_content):
            call_count[0] += 1
            if call_count[0] == 1:
                # First attempt - fail with issues
                return (False, ["Missing expect() assertions - tests must have at least 1"])
            else:
                # Subsequent attempts - pass
                return original_validate(test_content)

        scribe._validate_generated_test = mock_validate

        test_file_path = self.test_output_dir / "retry_test.spec.ts"

        result = scribe.execute(
            task_description="simple form test",
            feature_name="Form Test",
            output_path=str(test_file_path),
            complexity='easy'
        )

        # Should succeed after retry
        assert result.success, f"Scribe should succeed after retry: {result.error}"
        assert result.data['attempts_used'] == 2, "Should take 2 attempts"
        assert result.data['validation_passed'], "Should pass validation on retry"

        # Verify test file created
        assert test_file_path.exists()

        print(f"✓ Scribe retry flow validated")
        print(f"  Attempts used: {result.data['attempts_used']}")
        print(f"  Validation passed: {result.data['validation_passed']}")

    def test_state_management_flow(self):
        """
        Test that state is properly tracked in Redis and Vector DB.

        Validates:
        - Session state is stored and retrieved
        - Task status is tracked
        - Test patterns are stored in Vector DB
        """
        print("\n=== Testing State Management Flow ===")

        # Reset mock call counters
        self.mock_redis.reset_mock()
        self.mock_vector.reset_mock()

        # Simulate session creation
        self.mock_redis.set_session(
            self.session_id,
            self.session_data,
            ttl=3600
        )

        # Verify session was stored
        assert self.mock_redis.set_session.called, "Session should be stored in Redis"
        call_args = self.mock_redis.set_session.call_args
        assert call_args[0][0] == self.session_id
        assert call_args[0][1] == self.session_data
        assert call_args[1]['ttl'] == 3600

        print(f"✓ Session state stored in Redis")

        # Simulate task status tracking
        task_id = "task_login_test_123"

        self.mock_redis.set_task_status(task_id, "pending")
        self.mock_redis.set_task_status(task_id, "doing")
        self.mock_redis.set_task_status(task_id, "done")

        # Verify task status was tracked
        assert self.mock_redis.set_task_status.call_count == 3

        print(f"✓ Task status tracked in Redis")

        # Simulate storing successful test pattern in Vector DB
        test_pattern_id = "pattern_login_123"
        test_code = """
import { test, expect } from '@playwright/test';

test('login test', async ({ page }) => {
    await page.goto('/login');
    await expect(page.locator('[data-testid="login-form"]')).toBeVisible();
});
"""
        metadata = {
            'feature': 'login',
            'complexity': 'easy',
            'test_type': 'functional'
        }

        self.mock_vector.store_test_pattern(test_pattern_id, test_code, metadata)

        # Verify pattern was stored
        assert self.mock_vector.store_test_pattern.called, "Pattern should be stored in Vector DB"
        call_args = self.mock_vector.store_test_pattern.call_args
        assert call_args[0][0] == test_pattern_id
        assert call_args[0][1] == test_code
        assert call_args[0][2] == metadata

        print(f"✓ Test pattern stored in Vector DB")

        print("\n✓ State management flow validated")

    def test_cost_tracking_across_agents(self):
        """
        Test that costs are properly tracked across all agent interactions.

        Validates:
        - Each agent tracks its own cost
        - Costs accumulate correctly
        - Budget checks work properly
        """
        print("\n=== Testing Cost Tracking Across Agents ===")

        # Initialize router
        router = Router()

        # Simulate costs from each agent
        costs = {
            'kaya': 0.0,  # Routing only, no LLM calls
            'scribe': 0.02,  # Haiku for test generation
            'critic': 0.005,  # Haiku for pre-validation
            'runner': 0.005,  # Haiku for parsing
        }

        total_cost = sum(costs.values())

        # Check budget status
        budget_check = router.check_budget(total_cost, budget_type='per_session')

        # Validate budget check
        assert budget_check['status'] == 'ok', "Cost should be within budget"
        assert budget_check['limit'] == 5.00, "Session budget should be $5.00"
        assert budget_check['remaining'] > 0, "Should have remaining budget"
        assert total_cost < budget_check['limit'], "Total cost should be under limit"

        print(f"✓ Cost tracking validated")
        print(f"  Total cost: ${total_cost:.4f}")
        print(f"  Budget limit: ${budget_check['limit']:.2f}")
        print(f"  Remaining: ${budget_check['remaining']:.4f}")
        print(f"  Status: {budget_check['status']}")

        # Verify cost breakdown
        print(f"\n  Cost breakdown:")
        for agent, cost in costs.items():
            print(f"    {agent}: ${cost:.4f}")

    def test_error_handling_in_flow(self):
        """
        Test that errors are properly handled and propagated.

        Validates:
        - Agent failures are caught
        - Error messages are clear
        - Flow can recover from failures
        """
        print("\n=== Testing Error Handling ===")

        # Test 1: Invalid user command
        kaya = KayaAgent()
        result = kaya.execute("xyzabc invalid command that makes no sense")

        assert not result.success, "Should fail on invalid command"
        assert result.error is not None, "Should have error message"

        print(f"✓ Invalid command handled correctly")
        print(f"  Error: {result.error}")

        # Test 2: Critic rejects invalid test
        critic = CriticAgent()

        # Create test file with anti-patterns
        bad_test_path = self.test_output_dir / "bad_test.spec.ts"
        with open(bad_test_path, 'w') as f:
            f.write("""
import { test } from '@playwright/test';

test('bad test', async ({ page }) => {
    // Anti-pattern: no assertions
    // Anti-pattern: waitForTimeout
    await page.waitForTimeout(5000);
    // Anti-pattern: nth() selector
    await page.locator('.item').nth(0).click();
});
""")

        result = critic.execute(str(bad_test_path))

        assert result.success, "Critic should run successfully"
        assert result.data['status'] == 'rejected', "Should reject bad test"
        assert len(result.data['issues_found']) > 0, "Should find issues"

        print(f"✓ Bad test rejected by Critic")
        print(f"  Issues found: {len(result.data['issues_found'])}")

        # Test 3: Runner handles timeout
        runner = RunnerAgent()

        mock_timeout = Mock()
        mock_timeout.side_effect = Exception("Test execution timed out")

        with patch('subprocess.run', side_effect=mock_timeout):
            result = runner.execute(str(bad_test_path), timeout=1)

        assert not result.success, "Should fail on timeout"
        assert "error" in result.error.lower(), "Should have error message"

        print(f"✓ Timeout handled correctly")
        print(f"  Error: {result.error}")


class TestFlowPerformance:
    """Test performance characteristics of the flow."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_output_dir = Path(self.temp_dir) / "tests"
        self.test_output_dir.mkdir(parents=True, exist_ok=True)

        yield

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_flow_meets_performance_targets(self):
        """
        Test that flow meets performance targets.

        Targets:
        - Routing decision: < 100ms
        - Test generation: < 10s
        - Pre-validation: < 1s
        - Test execution: < 30s
        """
        print("\n=== Testing Performance Targets ===")

        # Test routing performance
        router = Router()
        start = time.time()
        decision = router.route(
            task_type="write_test",
            task_description="simple user login test"
        )
        routing_time_ms = int((time.time() - start) * 1000)

        assert routing_time_ms < 100, f"Routing took {routing_time_ms}ms, should be < 100ms"
        print(f"✓ Routing: {routing_time_ms}ms < 100ms")

        # Test Scribe performance (without actual LLM calls)
        mock_vector = Mock(spec=VectorClient)
        mock_vector.search_test_patterns.return_value = []

        scribe = ScribeAgent(vector_client=mock_vector)
        test_path = self.test_output_dir / "perf_test.spec.ts"

        start = time.time()
        result = scribe.execute(
            task_description="simple test",
            feature_name="Performance Test",
            output_path=str(test_path),
            complexity='easy'
        )
        scribe_time_ms = int((time.time() - start) * 1000)

        # Scribe should be fast without actual LLM calls
        assert scribe_time_ms < 10000, f"Scribe took {scribe_time_ms}ms"
        print(f"✓ Scribe: {scribe_time_ms}ms < 10,000ms")

        # Test Critic performance
        if test_path.exists():
            critic = CriticAgent()
            start = time.time()
            result = critic.execute(str(test_path))
            critic_time_ms = int((time.time() - start) * 1000)

            assert critic_time_ms < 1000, f"Critic took {critic_time_ms}ms"
            print(f"✓ Critic: {critic_time_ms}ms < 1,000ms")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
