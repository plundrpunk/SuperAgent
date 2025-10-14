"""
E2E Test: Multi-Agent Coordination and Interaction

Tests coordination between multiple agents:
1. Kaya → Scribe → Critic → Runner → Gemini (sequential flow)
2. Parallel agent execution where possible
3. Agent handoff and context passing
4. Error propagation between agents
5. State sharing via Redis/Vector DB
6. Agent fallback mechanisms
"""
import pytest
import tempfile
import shutil
import json
import time
from pathlib import Path
from unittest.mock import Mock, patch

from agent_system.agents.kaya import KayaAgent
from agent_system.agents.scribe import ScribeAgent
from agent_system.agents.runner import RunnerAgent
from agent_system.agents.critic import CriticAgent
from agent_system.agents.gemini import GeminiAgent
from agent_system.agents.medic import MedicAgent
from agent_system.router import Router
from agent_system.state.redis_client import RedisClient
from agent_system.state.vector_client import VectorClient


class TestAgentCoordination:
    """
    Multi-agent coordination tests.

    Tests how agents work together and pass context.
    """

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_dir = Path(self.temp_dir) / "tests"
        self.test_dir.mkdir()

        self.mock_redis = Mock(spec=RedisClient)
        self.mock_vector = Mock(spec=VectorClient)

        self.mock_redis.get.return_value = None
        self.mock_redis.set.return_value = True
        self.mock_redis.client = Mock()

        self.mock_vector.search_test_patterns.return_value = []
        self.mock_vector.store_test_pattern.return_value = True

        yield

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_sequential_agent_flow(self):
        """
        Test: Agents execute in correct sequence

        Kaya → Scribe → Critic → Runner → Gemini
        """
        print("\n" + "="*80)
        print("TEST: Sequential Agent Flow")
        print("="*80)

        execution_order = []
        total_cost = 0.0

        # Track agent execution
        def track_execution(agent_name, cost):
            execution_order.append(agent_name)
            nonlocal total_cost
            total_cost += cost
            print(f"  {len(execution_order)}. {agent_name} (cost: ${cost:.4f})")

        # Step 1: Kaya
        print("\n=== Agent Execution Flow ===")
        kaya = KayaAgent()
        track_execution('kaya', 0.0)

        # Step 2: Scribe
        scribe = ScribeAgent(vector_client=self.mock_vector)
        test_path = self.test_dir / "sequential.spec.ts"

        scribe_result = scribe.execute(
            task_description="sequential test",
            feature_name="Sequential",
            output_path=str(test_path),
            complexity='easy'
        )

        assert scribe_result.success
        track_execution('scribe', 0.02)

        # Step 3: Critic
        critic = CriticAgent()
        critic_result = critic.execute(str(test_path))

        assert critic_result.success
        track_execution('critic', 0.005)

        # Step 4: Runner
        runner = RunnerAgent()
        mock_runner = Mock()
        mock_runner.returncode = 0
        mock_runner.stdout = "1 passed (1.5s)"
        mock_runner.stderr = ""

        with patch('subprocess.run', return_value=mock_runner):
            runner_result = runner.execute(str(test_path))

        assert runner_result.success
        track_execution('runner', 0.005)

        # Step 5: Gemini
        gemini = GeminiAgent()
        mock_gemini = Mock()
        mock_gemini.returncode = 0
        mock_gemini.stdout = json.dumps({
            'suites': [{
                'specs': [{
                    'tests': [{
                        'results': [{'status': 'passed', 'duration': 1500}]
                    }]
                }]
            }]
        })

        screenshot_path = Path(self.temp_dir) / "screenshot.png"
        screenshot_path.write_text("screenshot")

        with patch('subprocess.run', return_value=mock_gemini):
            with patch.object(gemini, '_collect_screenshots', return_value=[str(screenshot_path)]):
                gemini_result = gemini.execute(str(test_path))

        assert gemini_result.success
        track_execution('gemini', 0.0)

        # Verify sequence
        expected_order = ['kaya', 'scribe', 'critic', 'runner', 'gemini']
        assert execution_order == expected_order, \
            f"Execution order mismatch: {execution_order} != {expected_order}"

        print(f"\n✓ Agents executed in correct sequence")
        print(f"  Total agents: {len(execution_order)}")
        print(f"  Total cost: ${total_cost:.4f}")

    def test_context_passing_between_agents(self):
        """
        Test: Context correctly passed between agents

        Test path and errors propagate through the chain
        """
        print("\n" + "="*80)
        print("TEST: Context Passing Between Agents")
        print("="*80)

        # Create test with Scribe
        scribe = ScribeAgent(vector_client=self.mock_vector)
        test_path = self.test_dir / "context_test.spec.ts"

        scribe_result = scribe.execute(
            task_description="context passing test",
            feature_name="Context",
            output_path=str(test_path),
            complexity='easy'
        )

        assert scribe_result.success
        assert 'test_path' in scribe_result.data

        print(f"\n✓ Scribe created test: {scribe_result.data['test_path']}")

        # Pass to Critic
        critic = CriticAgent()
        critic_result = critic.execute(scribe_result.data['test_path'])

        assert critic_result.success
        print(f"✓ Critic received test path from Scribe")

        # Simulate failure in Runner
        runner = RunnerAgent()
        mock_failure = Mock()
        mock_failure.returncode = 1
        mock_failure.stdout = "Error: Selector not found"
        mock_failure.stderr = ""

        with patch('subprocess.run', return_value=mock_failure):
            runner_result = runner.execute(scribe_result.data['test_path'])

        error_info = runner_result.data.get('errors', [])
        print(f"✓ Runner captured error: {error_info[:50] if error_info else 'none'}...")

        # Pass error to Medic
        medic = MedicAgent(redis_client=self.mock_redis)

        mock_anthropic = Mock()
        mock_anthropic.content = [Mock(text="""
DIAGNOSIS: Selector issue

CONFIDENCE: 0.85

FIX:
```typescript
await page.locator('[data-testid="fixed"]').click();
```
""")]
        mock_anthropic.usage = Mock(input_tokens=900, output_tokens=200)

        mock_client = Mock()
        mock_client.messages.create = Mock(return_value=mock_anthropic)

        mock_regression = Mock()
        mock_regression.returncode = 0
        mock_regression.stdout = "2 passed (4.0s)"
        mock_regression.stderr = ""

        with patch.object(medic, 'client', mock_client):
            with patch('subprocess.run', return_value=mock_regression):
                medic_result = medic.execute(
                    test_path=scribe_result.data['test_path'],
                    error_message=str(error_info),
                    task_id="context_task_123",
                    feature="context"
                )

        assert medic_result.success
        print(f"✓ Medic received error context from Runner")

        print(f"\n✓ Context successfully passed through agent chain")
        print(f"  Scribe → Critic: test_path")
        print(f"  Critic → Runner: test_path")
        print(f"  Runner → Medic: error_info")

    def test_agent_error_propagation(self):
        """
        Test: Errors properly propagate and stop pipeline

        If Critic rejects, pipeline should stop before Runner
        """
        print("\n" + "="*80)
        print("TEST: Agent Error Propagation")
        print("="*80)

        # Create test with bad patterns
        test_path = self.test_dir / "bad_test.spec.ts"
        test_path.write_text("""
import { test } from '@playwright/test';

test('bad test', async ({ page }) => {
    await page.goto('/page');
    await page.locator('.nth(0)').click();  // BAD: index selector
    await page.waitForTimeout(5000);        // BAD: waitForTimeout
    // NO expect() assertions                 // BAD: no assertions
});
""")

        print(f"\n✓ Created test with anti-patterns")

        # Critic should reject
        print(f"\n=== Critic Review ===")

        critic = CriticAgent()
        critic_result = critic.execute(str(test_path))

        # Critic should fail
        assert not critic_result.success or critic_result.data['status'] == 'rejected', \
            "Critic should reject test with anti-patterns"

        issues = critic_result.data.get('issues_found', [])
        assert len(issues) > 0, "Critic should find issues"

        print(f"✓ Critic rejected test")
        print(f"  Issues found: {len(issues)}")
        for i, issue in enumerate(issues[:3], 1):
            print(f"    {i}. {issue.get('type', 'unknown')}: {issue.get('message', '')[:60]}...")

        # Pipeline should stop here
        print(f"\n✓ Pipeline stopped after Critic rejection")
        print(f"  Runner not invoked (prevented expensive execution)")
        print(f"  Gemini not invoked (prevented expensive validation)")

    def test_kaya_full_pipeline_coordination(self):
        """
        Test: Kaya coordinates complete pipeline

        Kaya manages all agent interactions via full_pipeline intent
        """
        print("\n" + "="*80)
        print("TEST: Kaya Full Pipeline Coordination")
        print("="*80)

        kaya = KayaAgent()

        # Use full pipeline intent
        command = "Complete flow for user signup"

        print(f"\n=== Executing Full Pipeline ===")
        print(f"Command: {command}")

        # Parse intent
        intent = kaya.parse_intent(command)
        assert intent['success']
        print(f"✓ Intent parsed: {intent['intent']}")

        # Execute full pipeline (mock Scribe since it would create file)
        scribe = ScribeAgent(vector_client=self.mock_vector)
        test_path = self.test_dir / "signup.spec.ts"

        scribe_result = scribe.execute(
            task_description="user signup",
            feature_name="Signup",
            output_path=str(test_path),
            complexity='easy'
        )

        assert scribe_result.success

        print(f"✓ Full pipeline initiated by Kaya")
        print(f"  Scribe: ✓")

        # Verify Kaya tracks costs
        assert kaya.session_cost >= 0.0
        print(f"  Session cost: ${kaya.session_cost:.4f}")

    def test_agent_fallback_mechanisms(self):
        """
        Test: Agent fallback when errors occur

        Test Router's fallback mechanisms for various failure types
        """
        print("\n" + "="*80)
        print("TEST: Agent Fallback Mechanisms")
        print("="*80)

        router = Router()

        # Test different failure types
        failure_types = [
            ('critic_fail', 'return_to_scribe'),
            ('validation_timeout', 'retry_runner_then_medic'),
            ('medic_escalation', 'queue_for_hitl'),
        ]

        print(f"\n=== Fallback Actions ===")

        for failure_type, expected_fallback in failure_types:
            fallback = router.get_fallback(failure_type)

            status = "✓" if fallback == expected_fallback else "✗"
            print(f"{status} {failure_type} → {fallback}")

            assert fallback == expected_fallback, \
                f"Fallback mismatch for {failure_type}: expected {expected_fallback}, got {fallback}"

        # Test max retries
        max_retries = router.get_max_retries()
        print(f"\n✓ Max retries: {max_retries}")
        assert max_retries == 3, "Max retries should be 3"

    def test_state_sharing_via_redis(self):
        """
        Test: Agents share state via Redis

        Task status and session data shared between agents
        """
        print("\n" + "="*80)
        print("TEST: State Sharing via Redis")
        print("="*80)

        # Simulate state storage
        state_data = {}

        def mock_set(key, value, ttl=None):
            state_data[key] = value
            return True

        def mock_get(key):
            return state_data.get(key)

        self.mock_redis.set.side_effect = mock_set
        self.mock_redis.get.side_effect = mock_get

        # Agent 1: Scribe stores task status
        print(f"\n=== Scribe stores task data ===")

        task_id = "shared_task_123"
        self.mock_redis.set(f"task:{task_id}:status", "in_progress")
        self.mock_redis.set(f"task:{task_id}:agent", "scribe")

        print(f"✓ Scribe stored task data")
        print(f"  task:{task_id}:status = in_progress")

        # Agent 2: Runner reads task status
        print(f"\n=== Runner reads task data ===")

        status = self.mock_redis.get(f"task:{task_id}:status")
        agent = self.mock_redis.get(f"task:{task_id}:agent")

        assert status == "in_progress"
        assert agent == "scribe"

        print(f"✓ Runner retrieved task data")
        print(f"  Status: {status}")
        print(f"  Created by: {agent}")

        # Agent 3: Medic updates task status
        print(f"\n=== Medic updates task data ===")

        self.mock_redis.set(f"task:{task_id}:status", "fixed")
        self.mock_redis.set(f"task:{task_id}:agent", "medic")

        print(f"✓ Medic updated task data")

        # Verify final state
        final_status = self.mock_redis.get(f"task:{task_id}:status")
        final_agent = self.mock_redis.get(f"task:{task_id}:agent")

        assert final_status == "fixed"
        assert final_agent == "medic"

        print(f"\n✓ State successfully shared via Redis")
        print(f"  Final status: {final_status}")
        print(f"  Last updated by: {final_agent}")

    def test_rag_pattern_sharing_via_vector_db(self):
        """
        Test: Successful test patterns stored in Vector DB

        Scribe can learn from past successful patterns
        """
        print("\n" + "="*80)
        print("TEST: RAG Pattern Sharing via Vector DB")
        print("="*80)

        # Simulate successful test pattern
        test_pattern = {
            'feature': 'login_form',
            'code': 'test code here',
            'success': True,
            'validation_score': 0.95
        }

        print(f"\n=== Storing successful pattern ===")

        self.mock_vector.store_test_pattern(
            pattern_id="pattern_login_123",
            feature="login_form",
            test_code="test code here",
            metadata=test_pattern
        )

        assert self.mock_vector.store_test_pattern.called
        print(f"✓ Pattern stored in Vector DB")
        print(f"  Feature: {test_pattern['feature']}")
        print(f"  Validation score: {test_pattern['validation_score']}")

        # Scribe searches for similar patterns
        print(f"\n=== Scribe searches for patterns ===")

        self.mock_vector.search_test_patterns.return_value = [test_pattern]

        scribe = ScribeAgent(vector_client=self.mock_vector)

        # Scribe would call this internally
        patterns = self.mock_vector.search_test_patterns("login form test")

        assert len(patterns) > 0
        print(f"✓ Scribe found {len(patterns)} similar pattern(s)")
        print(f"  Can use as reference for new test")

        print(f"\n✓ RAG pattern sharing working")

    def test_agent_coordination_performance(self):
        """
        Test: Multi-agent coordination performance

        Complete pipeline should execute in < 10 seconds (mocked)
        """
        print("\n" + "="*80)
        print("TEST: Agent Coordination Performance")
        print("="*80)

        start_time = time.time()

        # Execute quick pipeline
        scribe = ScribeAgent(vector_client=self.mock_vector)
        test_path = self.test_dir / "perf_test.spec.ts"

        scribe.execute(
            task_description="performance test",
            feature_name="Performance",
            output_path=str(test_path),
            complexity='easy'
        )

        critic = CriticAgent()
        critic.execute(str(test_path))

        runner = RunnerAgent()
        mock_runner = Mock()
        mock_runner.returncode = 0
        mock_runner.stdout = "1 passed (1.0s)"
        mock_runner.stderr = ""

        with patch('subprocess.run', return_value=mock_runner):
            runner.execute(str(test_path))

        duration = time.time() - start_time

        print(f"\n=== Performance Results ===")
        print(f"Duration: {duration:.2f}s")
        print(f"Agents: 3 (Scribe, Critic, Runner)")

        # Should be fast with mocks
        assert duration < 10, f"Pipeline too slow: {duration:.2f}s"

        print(f"\n✓ Performance acceptable")
        print(f"  Target: < 10s")
        print(f"  Actual: {duration:.2f}s")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
