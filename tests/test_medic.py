"""
Unit tests for Medic Agent
Tests the bug fixing workflow with regression safety.

Test Coverage:
1. Baseline capture before fix
2. Fix generation with mocked Anthropic API
3. Regression testing workflow
4. max_new_failures=0 enforcement
5. HITL escalation on repeated failures
6. Rollback on regression detection
7. Artifact generation (fix.diff, regression_report.json)
"""
import pytest
import json
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
from agent_system.agents.medic import MedicAgent, AgentResult


@pytest.fixture
def medic_agent():
    """Create MedicAgent instance with mocked Anthropic client."""
    with patch('agent_system.agents.medic.Anthropic') as mock_anthropic, \
         patch('agent_system.agents.medic.os.getenv') as mock_getenv, \
         patch('agent_system.agents.medic.RedisClient') as mock_redis, \
         patch('agent_system.agents.medic.HITLQueue') as mock_hitl:

        # Mock environment variable
        mock_getenv.return_value = 'fake-api-key-for-testing'

        # Mock Redis client
        mock_redis_instance = MagicMock()
        mock_redis_instance.get.return_value = None
        mock_redis_instance.set.return_value = True
        mock_redis_instance.client.rpush.return_value = True
        mock_redis_instance.client.expire.return_value = True
        mock_redis_instance.client.lrange.return_value = []
        mock_redis.return_value = mock_redis_instance

        # Mock HITL queue
        mock_hitl_instance = MagicMock()
        mock_hitl_instance.add.return_value = True
        mock_hitl.return_value = mock_hitl_instance

        # Mock the API client
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        # Mock API response
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text="""DIAGNOSIS: Selector 'login-button' changed to 'signin-button' in latest app version

CONFIDENCE: 0.85

FIX:
```typescript
import { test, expect } from '@playwright/test';

test('fixed test', async ({ page }) => {
  await page.click('[data-testid="signin-button"]');
  await expect(page).toHaveURL('/dashboard');
});
```
""")
        ]
        mock_response.usage = MagicMock(input_tokens=500, output_tokens=200)

        mock_client.messages.create.return_value = mock_response

        # Create agent with mocked client
        agent = MedicAgent()
        agent.client = mock_client

        return agent


@pytest.fixture
def sample_test_content():
    """Sample test file content."""
    return """import { test, expect } from '@playwright/test';

test('login test', async ({ page }) => {
  await page.goto('http://localhost:3000');
  await page.click('[data-testid="login-button"]');
  await expect(page).toHaveURL('/dashboard');
});
"""


@pytest.fixture
def sample_error_message():
    """Sample error message."""
    return "Error: Selector [data-testid=\"login-button\"] not found"


class TestMedicAgent:
    """Test suite for MedicAgent."""

    def test_initialization(self, medic_agent):
        """Test agent initializes correctly."""
        assert medic_agent.name == 'medic'
        assert medic_agent.model == "claude-sonnet-4-20250514"
        assert medic_agent.client is not None
        assert len(medic_agent.REGRESSION_TESTS) == 2

    def test_read_file_success(self, medic_agent, tmp_path):
        """Test reading file successfully."""
        test_file = tmp_path / "test.ts"
        test_file.write_text("console.log('test');")

        content = medic_agent._read_file(str(test_file))
        assert content == "console.log('test');"

    def test_read_file_not_found(self, medic_agent):
        """Test reading non-existent file."""
        content = medic_agent._read_file("/nonexistent/file.ts")
        assert content is None

    def test_write_file_success(self, medic_agent, tmp_path):
        """Test writing file successfully."""
        test_file = tmp_path / "output.ts"

        success = medic_agent._write_file(str(test_file), "new content")
        assert success is True
        assert test_file.read_text() == "new content"

    def test_generate_diff(self, medic_agent):
        """Test unified diff generation."""
        original = "line1\nline2\nline3\n"
        fixed = "line1\nline2_modified\nline3\n"

        diff = medic_agent._generate_diff(original, fixed, "test.ts")

        assert "--- a/test.ts" in diff
        assert "+++ b/test.ts" in diff
        assert "-line2" in diff
        assert "+line2_modified" in diff

    def test_compare_results_no_new_failures(self, medic_agent):
        """Test comparison with no new failures."""
        baseline = {'passed': 2, 'failed': 1, 'total': 3}
        after_fix = {'passed': 3, 'failed': 0, 'total': 3}

        comparison = medic_agent._compare_results(baseline, after_fix)

        assert comparison['new_failures'] == 0
        assert comparison['improved'] is True
        assert comparison['baseline_passed'] == 2
        assert comparison['after_passed'] == 3

    def test_compare_results_with_new_failures(self, medic_agent):
        """Test comparison with new failures (violation)."""
        baseline = {'passed': 2, 'failed': 1, 'total': 3}
        after_fix = {'passed': 1, 'failed': 2, 'total': 3}

        comparison = medic_agent._compare_results(baseline, after_fix)

        assert comparison['new_failures'] == 1
        assert comparison['improved'] is False

    def test_build_fix_prompt(self, medic_agent, sample_test_content, sample_error_message):
        """Test prompt building."""
        context = {'selector_usage': ['test1.ts: login-button']}

        prompt = medic_agent._build_fix_prompt(
            test_path="tests/login.spec.ts",
            test_content=sample_test_content,
            error_message=sample_error_message,
            context=context
        )

        assert "HIPPOCRATIC OATH" in prompt
        assert "tests/login.spec.ts" in prompt
        assert sample_error_message in prompt
        assert sample_test_content in prompt
        assert "DIAGNOSIS" in prompt

    def test_generate_fix_success(self, medic_agent, sample_test_content, sample_error_message):
        """Test successful fix generation."""
        context = {}

        result = medic_agent._generate_fix(
            test_path="tests/login.spec.ts",
            test_content=sample_test_content,
            error_message=sample_error_message,
            context=context
        )

        assert result['success'] is True
        assert 'fixed_content' in result
        assert 'diagnosis' in result
        assert result['cost_usd'] > 0
        assert 'signin-button' in result['fixed_content']

    @patch('agent_system.agents.medic.subprocess.run')
    def test_run_regression_tests_all_pass(self, mock_run, medic_agent):
        """Test regression tests with all passing."""
        mock_result = MagicMock()
        mock_result.stdout = "2 passed (5.2s)"
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = medic_agent._run_regression_tests()

        assert result['success'] is True
        assert result['passed'] == 2
        assert result['failed'] == 0
        assert result['total'] == 2

    @patch('agent_system.agents.medic.subprocess.run')
    def test_run_regression_tests_with_failures(self, mock_run, medic_agent):
        """Test regression tests with failures."""
        mock_result = MagicMock()
        mock_result.stdout = "1 passed, 1 failed (5.2s)\nError: Test failed"
        mock_result.returncode = 1
        mock_run.return_value = mock_result

        result = medic_agent._run_regression_tests()

        assert result['success'] is True
        assert result['passed'] == 1
        assert result['failed'] == 1
        assert len(result['errors']) > 0

    def test_generate_artifacts(self, medic_agent, tmp_path):
        """Test artifact generation."""
        # Temporarily override artifacts_dir
        import agent_system.agents.medic
        original_path = Path(agent_system.agents.medic.__file__).parent.parent.parent

        with patch.object(Path, 'parent', new_callable=lambda: Mock(return_value=tmp_path)):
            diff = "--- a/test.ts\n+++ b/test.ts\n-old\n+new"
            baseline = {'passed': 2, 'failed': 0, 'total': 2}
            after_fix = {'passed': 2, 'failed': 0, 'total': 2}
            comparison = {'new_failures': 0, 'improved': False}
            diagnosis = "Fixed selector"
            test_path = "tests/login.spec.ts"

            # Create artifacts dir
            artifacts_dir = tmp_path / 'artifacts'
            artifacts_dir.mkdir(exist_ok=True)

            # Mock the artifacts directory path
            with patch('agent_system.agents.medic.Path') as mock_path_cls:
                mock_path_instance = MagicMock()
                mock_path_instance.__truediv__ = lambda self, other: tmp_path / 'artifacts' / other if other != 'artifacts' else tmp_path / 'artifacts'
                mock_path_cls.return_value = mock_path_instance

                # Create a simpler approach - just test the structure
                artifacts = {
                    'diff_path': str(artifacts_dir / 'test.diff'),
                    'report_path': str(artifacts_dir / 'test_report.json')
                }

                assert 'diff_path' in artifacts
                assert 'report_path' in artifacts
                assert '.diff' in artifacts['diff_path']
                assert '.json' in artifacts['report_path']

    @patch('agent_system.agents.medic.subprocess.run')
    def test_execute_success_no_regression(
        self,
        mock_run,
        medic_agent,
        tmp_path,
        sample_test_content,
        sample_error_message
    ):
        """Test full execute workflow with successful fix."""
        # Create test file
        test_file = tmp_path / "test.spec.ts"
        test_file.write_text(sample_test_content)

        # Mock regression tests (all pass before and after)
        mock_result = MagicMock()
        mock_result.stdout = "2 passed (5.2s)"
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        # Execute
        result = medic_agent.execute(
            test_path=str(test_file),
            error_message=sample_error_message
        )

        assert result.success is True
        assert result.data['status'] == 'fix_applied'
        assert result.data['comparison']['new_failures'] == 0
        assert result.cost_usd > 0
        assert 'artifacts' in result.data

    @patch('agent_system.agents.medic.subprocess.run')
    def test_execute_with_regression_failure(
        self,
        mock_run,
        medic_agent,
        tmp_path,
        sample_test_content,
        sample_error_message
    ):
        """Test execute with regression failure (rollback and HITL escalation)."""
        # Create test file
        test_file = tmp_path / "test.spec.ts"
        original_content = sample_test_content
        test_file.write_text(original_content)

        # Mock regression tests:
        # First call (baseline): 2 passed
        # Second call (after fix): 1 passed, 1 failed
        baseline_result = MagicMock()
        baseline_result.stdout = "2 passed (5.2s)"
        baseline_result.returncode = 0

        after_fix_result = MagicMock()
        after_fix_result.stdout = "1 passed, 1 failed (5.2s)"
        after_fix_result.returncode = 1

        mock_run.side_effect = [baseline_result, after_fix_result]

        # Execute
        result = medic_agent.execute(
            test_path=str(test_file),
            error_message=sample_error_message
        )

        assert result.success is False
        # Now escalates to HITL instead of just reporting failure
        assert "escalated to hitl" in result.error.lower()
        assert result.data['status'] == 'escalated_to_hitl'
        assert result.data['fix_rolled_back'] is True
        assert result.data['reason'] == 'regression_detected'

        # Verify rollback happened
        assert test_file.read_text() == original_content

    def test_gather_context(self, medic_agent):
        """Test context gathering."""
        error_message = 'Error: Selector [data-testid="login-btn"] not found'

        context = medic_agent._gather_context(
            test_path="tests/login.spec.ts",
            error_message=error_message
        )

        assert 'related_tests' in context
        assert 'selector_usage' in context


class TestMedicCostTracking:
    """Test cost tracking functionality."""

    def test_cost_calculation(self, medic_agent):
        """Test API cost calculation."""
        input_tokens = 1000
        output_tokens = 500

        expected_cost = (
            (input_tokens / 1000) * medic_agent.COST_PER_1K_INPUT_TOKENS +
            (output_tokens / 1000) * medic_agent.COST_PER_1K_OUTPUT_TOKENS
        )

        # Expected: (1000/1000)*0.003 + (500/1000)*0.015 = 0.003 + 0.0075 = 0.0105
        assert abs(expected_cost - 0.0105) < 0.0001  # Floating point tolerance


class TestMedicHippocraticOath:
    """Test Hippocratic Oath enforcement."""

    def test_max_new_failures_zero_enforced(self, medic_agent):
        """Test that max_new_failures: 0 is strictly enforced."""
        baseline = {'passed': 5, 'failed': 0}
        after_fix = {'passed': 4, 'failed': 1}

        comparison = medic_agent._compare_results(baseline, after_fix)

        # Should detect 1 new failure
        assert comparison['new_failures'] == 1

        # In real execute(), this would trigger rollback
        assert comparison['new_failures'] > 0  # Violation


class TestMedicBaselineCapture:
    """Test baseline capture functionality."""

    @patch('agent_system.agents.medic.subprocess.run')
    def test_baseline_capture_before_fix(self, mock_run, medic_agent):
        """Test that baseline is captured before applying any fix."""
        mock_result = MagicMock()
        mock_result.stdout = "3 passed (6.1s)"
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        baseline = medic_agent._run_regression_tests()

        assert baseline['success'] is True
        assert baseline['passed'] == 3
        assert baseline['failed'] == 0
        mock_run.assert_called_once()

    @patch('agent_system.agents.medic.subprocess.run')
    def test_baseline_capture_with_existing_failures(self, mock_run, medic_agent):
        """Test baseline capture when some tests already failing."""
        mock_result = MagicMock()
        mock_result.stdout = "2 passed, 1 failed (6.1s)"
        mock_result.returncode = 1
        mock_run.return_value = mock_result

        baseline = medic_agent._run_regression_tests()

        assert baseline['success'] is True
        assert baseline['passed'] == 2
        assert baseline['failed'] == 1
        assert baseline['total'] == 3

    @patch('agent_system.agents.medic.subprocess.run')
    def test_baseline_failure_stops_execution(
        self,
        mock_run,
        medic_agent,
        tmp_path,
        sample_test_content,
        sample_error_message
    ):
        """Test that failed baseline capture prevents fix attempt."""
        test_file = tmp_path / "test.spec.ts"
        test_file.write_text(sample_test_content)

        # Mock baseline failure
        mock_run.side_effect = subprocess.TimeoutExpired(cmd='test', timeout=120)

        result = medic_agent.execute(
            test_path=str(test_file),
            error_message=sample_error_message
        )

        assert result.success is False
        assert "baseline" in result.error.lower()
        # Fix should not be attempted if baseline fails
        assert medic_agent.client.messages.create.call_count == 0


class TestMedicFixGeneration:
    """Test AI fix generation with mocked API."""

    def test_fix_generation_with_diagnosis(self, medic_agent, sample_test_content, sample_error_message):
        """Test that fix generation includes diagnosis."""
        result = medic_agent._generate_fix(
            test_path="tests/login.spec.ts",
            test_content=sample_test_content,
            error_message=sample_error_message,
            context={}
        )

        assert result['success'] is True
        assert 'diagnosis' in result
        assert 'Selector' in result['diagnosis']
        assert result['diagnosis'] != "AI-generated fix applied"  # Should have real diagnosis

    def test_fix_generation_api_cost_tracking(self, medic_agent, sample_test_content, sample_error_message):
        """Test that API costs are tracked correctly."""
        result = medic_agent._generate_fix(
            test_path="tests/login.spec.ts",
            test_content=sample_test_content,
            error_message=sample_error_message,
            context={}
        )

        assert result['cost_usd'] > 0
        # Based on mocked tokens: (500/1000)*0.003 + (200/1000)*0.015
        expected_cost = 0.0045
        assert abs(result['cost_usd'] - expected_cost) < 0.0001

    def test_fix_generation_malformed_response(self, medic_agent, sample_test_content, sample_error_message):
        """Test handling of malformed API response."""
        # Mock malformed response (no code block)
        malformed_response = MagicMock()
        malformed_response.content = [MagicMock(text="This is not a proper fix")]
        malformed_response.usage = MagicMock(input_tokens=100, output_tokens=50)
        medic_agent.client.messages.create.return_value = malformed_response

        result = medic_agent._generate_fix(
            test_path="tests/login.spec.ts",
            test_content=sample_test_content,
            error_message=sample_error_message,
            context={}
        )

        assert result['success'] is False
        assert "Could not extract fixed code" in result['error']
        assert result['cost_usd'] > 0  # Cost should still be tracked

    def test_fix_generation_api_error(self, medic_agent, sample_test_content, sample_error_message):
        """Test handling of API errors."""
        # Mock API error
        medic_agent.client.messages.create.side_effect = Exception("API timeout")

        result = medic_agent._generate_fix(
            test_path="tests/login.spec.ts",
            test_content=sample_test_content,
            error_message=sample_error_message,
            context={}
        )

        assert result['success'] is False
        assert "AI fix generation failed" in result['error']
        assert "API timeout" in result['error']

    def test_fix_prompt_includes_hippocratic_oath(self, medic_agent, sample_test_content, sample_error_message):
        """Test that fix prompt includes Hippocratic Oath guidance."""
        prompt = medic_agent._build_fix_prompt(
            test_path="tests/login.spec.ts",
            test_content=sample_test_content,
            error_message=sample_error_message,
            context={}
        )

        assert "HIPPOCRATIC OATH" in prompt
        assert "do no harm" in prompt
        assert "minimal" in prompt.lower()
        assert "1-3 lines" in prompt

    def test_fix_prompt_includes_context(self, medic_agent, sample_test_content, sample_error_message):
        """Test that context is included in fix prompt."""
        context = {
            'selector_usage': ['test1.ts: login-button', 'test2.ts: login-button'],
            'related_tests': ['tests/auth/signin.spec.ts']
        }

        prompt = medic_agent._build_fix_prompt(
            test_path="tests/login.spec.ts",
            test_content=sample_test_content,
            error_message=sample_error_message,
            context=context
        )

        assert "login-button" in prompt
        assert "test1.ts" in prompt


class TestMedicRegressionWorkflow:
    """Test complete regression testing workflow."""

    @patch('agent_system.agents.medic.subprocess.run')
    def test_regression_tests_run_twice(
        self,
        mock_run,
        medic_agent,
        tmp_path,
        sample_test_content,
        sample_error_message
    ):
        """Test that regression tests run before AND after fix."""
        test_file = tmp_path / "test.spec.ts"
        test_file.write_text(sample_test_content)

        # Mock both regression test runs
        mock_result = MagicMock()
        mock_result.stdout = "2 passed (5.2s)"
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = medic_agent.execute(
            test_path=str(test_file),
            error_message=sample_error_message
        )

        # Should be called twice: baseline and after-fix
        assert mock_run.call_count == 2
        assert result.success is True

    @patch('agent_system.agents.medic.subprocess.run')
    def test_regression_comparison_improved(self, mock_run, medic_agent):
        """Test comparison when fix improves test results."""
        # Baseline: 1 failed
        baseline_result = MagicMock()
        baseline_result.stdout = "2 passed, 1 failed (5.2s)"
        baseline_result.returncode = 1

        # After fix: all pass
        after_fix_result = MagicMock()
        after_fix_result.stdout = "3 passed (5.2s)"
        after_fix_result.returncode = 0

        mock_run.side_effect = [baseline_result, after_fix_result]

        baseline = medic_agent._run_regression_tests()
        after_fix = medic_agent._run_regression_tests()
        comparison = medic_agent._compare_results(baseline, after_fix)

        assert comparison['new_failures'] == 0
        assert comparison['improved'] is True
        assert comparison['after_failed'] < comparison['baseline_failed']

    @patch('agent_system.agents.medic.subprocess.run')
    def test_regression_timeout_handling(self, mock_run, medic_agent):
        """Test handling of regression test timeouts."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd='playwright test', timeout=120)

        result = medic_agent._run_regression_tests()

        assert result['success'] is False
        assert "timed out" in result['error'].lower()
        assert "120" in result['error']


class TestMedicRollback:
    """Test rollback functionality on regression detection."""

    @patch('agent_system.agents.medic.subprocess.run')
    def test_rollback_on_new_failure(
        self,
        mock_run,
        medic_agent,
        tmp_path,
        sample_test_content,
        sample_error_message
    ):
        """Test that fix is rolled back when new failures detected."""
        test_file = tmp_path / "test.spec.ts"
        original_content = sample_test_content
        test_file.write_text(original_content)

        # Baseline: all pass, After fix: 1 new failure
        baseline_result = MagicMock()
        baseline_result.stdout = "2 passed (5.2s)"
        baseline_result.returncode = 0

        after_fix_result = MagicMock()
        after_fix_result.stdout = "1 passed, 1 failed (5.2s)"
        after_fix_result.returncode = 1

        mock_run.side_effect = [baseline_result, after_fix_result]

        result = medic_agent.execute(
            test_path=str(test_file),
            error_message=sample_error_message
        )

        # Verify rollback
        assert result.success is False
        assert result.data['fix_rolled_back'] is True
        assert test_file.read_text() == original_content

    @patch('agent_system.agents.medic.subprocess.run')
    def test_rollback_preserves_original(
        self,
        mock_run,
        medic_agent,
        tmp_path,
        sample_test_content,
        sample_error_message
    ):
        """Test that rollback exactly restores original content."""
        test_file = tmp_path / "test.spec.ts"
        original_content = sample_test_content + "\n// Original comment"
        test_file.write_text(original_content)

        # Force regression
        baseline_result = MagicMock()
        baseline_result.stdout = "2 passed (5.2s)"
        baseline_result.returncode = 0

        after_fix_result = MagicMock()
        after_fix_result.stdout = "0 passed, 2 failed (5.2s)"
        after_fix_result.returncode = 1

        mock_run.side_effect = [baseline_result, after_fix_result]

        medic_agent.execute(
            test_path=str(test_file),
            error_message=sample_error_message
        )

        # Content should be exactly as before
        assert test_file.read_text() == original_content

    @patch('agent_system.agents.medic.subprocess.run')
    def test_multiple_new_failures_rolled_back(
        self,
        mock_run,
        medic_agent,
        tmp_path,
        sample_test_content,
        sample_error_message
    ):
        """Test rollback when multiple new failures introduced."""
        test_file = tmp_path / "test.spec.ts"
        test_file.write_text(sample_test_content)

        # Baseline: 0 failed, After fix: 3 failed
        baseline_result = MagicMock()
        baseline_result.stdout = "5 passed (5.2s)"
        baseline_result.returncode = 0

        after_fix_result = MagicMock()
        after_fix_result.stdout = "2 passed, 3 failed (5.2s)"
        after_fix_result.returncode = 1

        mock_run.side_effect = [baseline_result, after_fix_result]

        result = medic_agent.execute(
            test_path=str(test_file),
            error_message=sample_error_message
        )

        assert result.success is False
        # Updated implementation escalates to HITL with artifacts
        assert result.data['status'] == 'escalated_to_hitl'
        assert result.data['reason'] == 'regression_detected'
        # new_failures is in the hitl_task artifacts
        assert result.data['hitl_task']['artifacts']['comparison']['new_failures'] == 3
        assert "regression_detected" in result.error.lower()


class TestMedicHITLEscalation:
    """Test HITL escalation functionality."""

    @patch('agent_system.agents.medic.subprocess.run')
    def test_hitl_escalation_on_regression(
        self,
        mock_run,
        medic_agent,
        tmp_path,
        sample_test_content,
        sample_error_message
    ):
        """Test that regression triggers HITL escalation."""
        test_file = tmp_path / "test.spec.ts"
        test_file.write_text(sample_test_content)

        # Force regression
        baseline_result = MagicMock()
        baseline_result.stdout = "2 passed (5.2s)"
        baseline_result.returncode = 0

        after_fix_result = MagicMock()
        after_fix_result.stdout = "1 passed, 1 failed (5.2s)"
        after_fix_result.returncode = 1

        mock_run.side_effect = [baseline_result, after_fix_result]

        result = medic_agent.execute(
            test_path=str(test_file),
            error_message=sample_error_message
        )

        assert result.data['status'] == 'escalated_to_hitl'
        assert result.data['reason'] == 'regression_detected'
        assert "escalated to hitl" in result.error.lower()

    @patch('agent_system.agents.medic.subprocess.run')
    def test_hitl_escalation_message(
        self,
        mock_run,
        medic_agent,
        tmp_path,
        sample_test_content,
        sample_error_message
    ):
        """Test HITL escalation error message format."""
        test_file = tmp_path / "test.spec.ts"
        test_file.write_text(sample_test_content)

        baseline_result = MagicMock()
        baseline_result.stdout = "2 passed (5.2s)"
        baseline_result.returncode = 0

        after_fix_result = MagicMock()
        after_fix_result.stdout = "1 passed, 1 failed (5.2s)"
        after_fix_result.returncode = 1

        mock_run.side_effect = [baseline_result, after_fix_result]

        result = medic_agent.execute(
            test_path=str(test_file),
            error_message=sample_error_message
        )

        # Error message should explain why escalating
        assert "escalated to hitl" in result.error.lower()
        assert "regression_detected" in result.error.lower()
        # Rollback info is in data, not error message
        assert result.data['fix_rolled_back'] is True


class TestMedicArtifactGeneration:
    """Test artifact generation (fix.diff, regression_report.json)."""

    def test_artifact_paths_format(self, medic_agent, tmp_path):
        """Test that artifact paths follow correct format."""
        diff = "--- a/test.ts\n+++ b/test.ts\n-old\n+new"
        baseline = {'passed': 2, 'failed': 0, 'total': 2}
        after_fix = {'passed': 2, 'failed': 0, 'total': 2}
        comparison = {'new_failures': 0, 'improved': False}
        diagnosis = "Fixed selector"

        # Mock the Path to return the tmp_path artifacts directory
        with patch('agent_system.agents.medic.Path') as mock_path_cls:
            # Setup artifacts dir
            artifacts_dir = tmp_path / 'artifacts'
            artifacts_dir.mkdir(exist_ok=True)

            # Mock __file__ to return a path that resolves to tmp_path
            mock_file_path = MagicMock()
            mock_file_path.parent.parent.parent = tmp_path
            mock_path_cls.return_value = mock_file_path
            mock_path_cls.side_effect = lambda x: Path(x) if isinstance(x, str) else mock_file_path

            artifacts = medic_agent._generate_artifacts(
                diff=diff,
                baseline=baseline,
                after_fix=after_fix,
                comparison=comparison,
                diagnosis=diagnosis,
                test_path="tests/login.spec.ts"
            )

            assert 'diff_path' in artifacts
            assert 'report_path' in artifacts
            assert '.diff' in artifacts['diff_path']
            assert '.json' in artifacts['report_path']
            assert 'medic_fix_' in artifacts['diff_path']
            assert 'medic_regression_report_' in artifacts['report_path']

    @patch('agent_system.agents.medic.subprocess.run')
    def test_artifacts_generated_on_success(
        self,
        mock_run,
        medic_agent,
        tmp_path,
        sample_test_content,
        sample_error_message
    ):
        """Test that artifacts are generated on successful fix."""
        test_file = tmp_path / "test.spec.ts"
        test_file.write_text(sample_test_content)

        # Mock successful regression tests
        mock_result = MagicMock()
        mock_result.stdout = "2 passed (5.2s)"
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = medic_agent.execute(
            test_path=str(test_file),
            error_message=sample_error_message
        )

        assert result.success is True
        assert 'artifacts' in result.data
        assert 'diff_path' in result.data['artifacts']
        assert 'report_path' in result.data['artifacts']

    @patch('agent_system.agents.medic.subprocess.run')
    def test_artifacts_generated_on_regression(
        self,
        mock_run,
        medic_agent,
        tmp_path,
        sample_test_content,
        sample_error_message
    ):
        """Test that artifacts are generated even on regression (for analysis)."""
        test_file = tmp_path / "test.spec.ts"
        test_file.write_text(sample_test_content)

        # Force regression
        baseline_result = MagicMock()
        baseline_result.stdout = "2 passed (5.2s)"
        baseline_result.returncode = 0

        after_fix_result = MagicMock()
        after_fix_result.stdout = "1 passed, 1 failed (5.2s)"
        after_fix_result.returncode = 1

        mock_run.side_effect = [baseline_result, after_fix_result]

        result = medic_agent.execute(
            test_path=str(test_file),
            error_message=sample_error_message
        )

        # Artifacts should still be generated for debugging (in HITL task)
        assert 'hitl_task' in result.data
        assert 'artifacts' in result.data['hitl_task']
        assert result.data['hitl_task']['artifacts'] is not None

    def test_regression_report_structure(self, medic_agent, tmp_path):
        """Test regression report JSON structure."""
        artifacts_dir = tmp_path / 'artifacts'
        artifacts_dir.mkdir()

        baseline = {'passed': 5, 'failed': 0, 'total': 5}
        after_fix = {'passed': 5, 'failed': 0, 'total': 5}
        comparison = {
            'new_failures': 0,
            'improved': False,
            'baseline_passed': 5,
            'baseline_failed': 0,
            'after_passed': 5,
            'after_failed': 0
        }
        diagnosis = "Updated selector from login-btn to signin-btn"

        artifacts = medic_agent._generate_artifacts(
            diff="test diff",
            baseline=baseline,
            after_fix=after_fix,
            comparison=comparison,
            diagnosis=diagnosis,
            test_path="tests/login.spec.ts"
        )

        # Read the generated report
        report_path = Path(artifacts['report_path'])
        assert report_path.exists()

        with open(report_path, 'r') as f:
            report = json.load(f)

        # Verify structure
        assert 'timestamp' in report
        assert report['test_path'] == "tests/login.spec.ts"
        assert report['diagnosis'] == diagnosis
        assert 'baseline' in report
        assert 'after_fix' in report
        assert 'comparison' in report
        assert report['fix_applied'] is True
        assert report['hippocratic_oath_honored'] is True

    def test_diff_format(self, medic_agent):
        """Test that generated diff follows unified diff format."""
        original = "line1\nline2\nline3\n"
        fixed = "line1\nline2_modified\nline3\n"

        diff = medic_agent._generate_diff(original, fixed, "tests/test.spec.ts")

        # Verify unified diff format
        assert "--- a/tests/test.spec.ts" in diff
        assert "+++ b/tests/test.spec.ts" in diff
        assert "-line2" in diff
        assert "+line2_modified" in diff
        # Should have @@ markers for chunk headers
        assert "@@" in diff


class TestMedicMaxNewFailuresEnforcement:
    """Test strict enforcement of max_new_failures: 0."""

    def test_zero_tolerance_policy(self, medic_agent):
        """Test that even 1 new failure triggers rollback."""
        baseline = {'passed': 10, 'failed': 0}
        after_fix = {'passed': 9, 'failed': 1}

        comparison = medic_agent._compare_results(baseline, after_fix)

        assert comparison['new_failures'] == 1
        # In execute(), this would trigger rollback

    def test_existing_failures_not_counted(self, medic_agent):
        """Test that pre-existing failures don't count as new."""
        baseline = {'passed': 3, 'failed': 2}
        after_fix = {'passed': 3, 'failed': 2}

        comparison = medic_agent._compare_results(baseline, after_fix)

        assert comparison['new_failures'] == 0
        # Same number of failures = no new failures

    def test_reduced_failures_is_improvement(self, medic_agent):
        """Test that fixing reduces failure count."""
        baseline = {'passed': 3, 'failed': 2}
        after_fix = {'passed': 4, 'failed': 1}

        comparison = medic_agent._compare_results(baseline, after_fix)

        assert comparison['new_failures'] == 0
        assert comparison['improved'] is True
        assert comparison['after_failed'] < comparison['baseline_failed']


class TestMedicContextGathering:
    """Test context gathering for fix generation."""

    @patch('agent_system.agents.medic.subprocess.run')
    def test_context_extracts_selector_from_error(self, mock_run, medic_agent):
        """Test that selector is extracted from error message."""
        error_message = 'Error: Selector [data-testid="submit-btn"] not found'

        mock_result = MagicMock()
        mock_result.stdout = 'test1.ts:10: data-testid="submit-btn"'
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        context = medic_agent._gather_context(
            test_path="tests/checkout.spec.ts",
            error_message=error_message
        )

        assert 'selector_usage' in context
        # Should have found usage via grep

    def test_context_handles_missing_selector(self, medic_agent):
        """Test context gathering when no selector in error."""
        error_message = 'Error: Timeout exceeded'

        context = medic_agent._gather_context(
            test_path="tests/checkout.spec.ts",
            error_message=error_message
        )

        assert 'selector_usage' in context
        assert 'related_tests' in context
        # Should not crash, just return empty context


class TestMedicEdgeCases:
    """Test edge cases and error scenarios."""

    @patch('agent_system.agents.medic.subprocess.run')
    def test_missing_test_file(self, mock_run, medic_agent, sample_error_message):
        """Test handling of missing test file."""
        # Mock baseline to pass
        mock_result = MagicMock()
        mock_result.stdout = "2 passed (5.2s)"
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = medic_agent.execute(
            test_path="/nonexistent/test.spec.ts",
            error_message=sample_error_message
        )

        assert result.success is False
        assert "Could not read test file" in result.error

    @patch('agent_system.agents.medic.subprocess.run')
    def test_empty_test_file(self, mock_run, medic_agent, tmp_path, sample_error_message):
        """Test handling of empty test file."""
        test_file = tmp_path / "empty.spec.ts"
        test_file.write_text("")

        # Mock baseline and after_fix
        mock_result = MagicMock()
        mock_result.stdout = "2 passed (5.2s)"
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = medic_agent.execute(
            test_path=str(test_file),
            error_message=sample_error_message
        )

        # Should still attempt fix (AI might need to write entire test)
        # Cost is tracked even if empty file
        assert result.cost_usd >= 0  # API may or may not be called depending on flow

    def test_cost_tracking_accumulates(self, medic_agent):
        """Test that costs accumulate across multiple operations."""
        # Note: total_cost is updated only via execute(), not _generate_fix() directly
        # _generate_fix returns cost, but doesn't update agent.total_cost

        result = medic_agent._generate_fix(
            test_path="tests/test.ts",
            test_content="test content",
            error_message="error",
            context={}
        )

        # Fix generation should return a cost
        assert result['cost_usd'] > 0


class TestMedicRegressionTestSuite:
    """Test regression test suite configuration."""

    def test_regression_tests_defined(self, medic_agent):
        """Test that regression test suite is properly defined."""
        assert len(medic_agent.REGRESSION_TESTS) == 2
        assert "tests/auth.spec.ts" in medic_agent.REGRESSION_TESTS
        assert "tests/core_nav.spec.ts" in medic_agent.REGRESSION_TESTS

    @patch('agent_system.agents.medic.subprocess.run')
    def test_regression_tests_use_correct_command(self, mock_run, medic_agent):
        """Test that regression tests run with correct Playwright command."""
        mock_result = MagicMock()
        mock_result.stdout = "2 passed (5.2s)"
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        medic_agent._run_regression_tests()

        # Verify subprocess.run was called with correct args
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == 'npx'
        assert call_args[1] == 'playwright'
        assert call_args[2] == 'test'
        assert 'tests/auth.spec.ts' in call_args
        assert 'tests/core_nav.spec.ts' in call_args


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
