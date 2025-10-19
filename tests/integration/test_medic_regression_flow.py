"""
Integration Tests for Medic Regression Validation Workflow

Tests the complete fix and regression safety flow:
1. Runner detects test failure (selector not found)
2. Medic captures baseline regression test results (auth.spec.ts, core_nav.spec.ts)
3. Medic diagnoses issue using Claude Sonnet 4.5
4. Medic generates fix with confidence score
5. Medic applies fix to test file
6. Medic runs regression suite after fix
7. Medic compares baseline to post-fix results
8. Validates Hippocratic Oath: max_new_failures = 0
9. Medic stores successful fix in vector DB (future)
10. Verify artifacts generated: fix.diff, regression_report.json

Test Scenarios:
1. Successful fix with no new failures ✅
2. Fix introduces new failure → rollback and escalate to HITL 🔄
3. Low AI confidence → escalate to HITL before applying fix
4. Max retries exceeded → escalate to HITL
5. Regression test baseline failure → abort with error
6. Fix resolves issue + regression passes ✅
"""
import pytest
import json
import tempfile
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
from typing import Dict, Any, List

# Mock external dependencies before importing agents
sys.modules['anthropic'] = MagicMock()
sys.modules['redis'] = MagicMock()

from agent_system.agents.medic import MedicAgent
from agent_system.agents.base_agent import AgentResult
from agent_system.state.redis_client import RedisClient
from agent_system.hitl.queue import HITLQueue


class TestMedicRegressionFlow:
    """Integration tests for Medic fix and regression validation workflow."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test files."""
        temp = tempfile.mkdtemp()
        # Create artifacts directory
        artifacts_dir = Path(temp) / 'artifacts'
        artifacts_dir.mkdir(exist_ok=True)
        yield temp
        shutil.rmtree(temp)

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        redis_mock = MagicMock(spec=RedisClient)
        redis_mock.get.return_value = None  # No previous attempts
        redis_mock.set.return_value = True
        redis_mock.client = MagicMock()
        redis_mock.client.rpush.return_value = 1
        redis_mock.client.expire.return_value = True
        redis_mock.client.lrange.return_value = []
        return redis_mock

    @pytest.fixture
    def mock_hitl(self):
        """Mock HITL queue."""
        hitl_mock = MagicMock(spec=HITLQueue)
        hitl_mock.add.return_value = True
        return hitl_mock

    @pytest.fixture
    def medic(self, mock_redis, mock_hitl, temp_dir, monkeypatch):
        """Create Medic agent with mocked dependencies."""
        # Mock environment variables
        monkeypatch.setenv('ANTHROPIC_API_KEY', 'test-key-12345')

        # Patch the artifacts path to use temp_dir
        with patch('agent_system.agents.medic.Path') as mock_path_class:
            # Make Path() work normally but redirect artifact directory
            def path_side_effect(*args, **kwargs):
                if len(args) == 1 and isinstance(args[0], str):
                    p = Path(args[0])
                    # Replace artifacts directory with temp dir
                    if 'artifacts' in str(p):
                        return Path(temp_dir) / 'artifacts'
                    return p
                return Path(*args, **kwargs)

            mock_path_class.side_effect = path_side_effect

            medic = MedicAgent(
                redis_client=mock_redis,
                hitl_queue=mock_hitl
            )

            # Override artifact directory
            medic._artifact_dir = Path(temp_dir) / 'artifacts'

            return medic

    # Mock test content
    FAILING_TEST = '''import { test, expect } from '@playwright/test';

const S = (id: string) => `[data-testid="${id}"]`;

test.use({
  screenshot: 'on',
  video: 'retain-on-failure',
  trace: 'retain-on-failure'
});

test.describe('User Profile', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(process.env.BASE_URL!);
  });

  test('view profile', async ({ page }) => {
    // Bad selector: this data-testid doesn't exist
    await page.click(S('old-profile-button'));
    await page.screenshot({ path: 'profile-step1.png' });
    await expect(page.locator(S('profile-name'))).toBeVisible();
  });
});
'''

    FIXED_TEST = '''import { test, expect } from '@playwright/test';

const S = (id: string) => `[data-testid="${id}"]`;

test.use({
  screenshot: 'on',
  video: 'retain-on-failure',
  trace: 'retain-on-failure'
});

test.describe('User Profile', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(process.env.BASE_URL!);
  });

  test('view profile', async ({ page }) => {
    // Fixed selector: updated to correct data-testid
    await page.click(S('profile-button'));
    await page.screenshot({ path: 'profile-step1.png' });
    await expect(page.locator(S('profile-name'))).toBeVisible();
  });
});
'''

    FIXED_TEST_BREAKS_REGRESSION = '''import { test, expect } from '@playwright/test';

const S = (id: string) => `[data-testid="${id}"]`;

test.use({
  screenshot: 'on',
  video: 'retain-on-failure',
  trace: 'retain-on-failure'
});

test.describe('User Profile', () => {
  test.beforeEach(async ({ page }) => {
    // Bad: This breaks auth tests by changing BASE_URL
    await page.goto('http://localhost:9999');
  });

  test('view profile', async ({ page }) => {
    await page.click(S('profile-button'));
    await page.screenshot({ path: 'profile-step1.png' });
    await expect(page.locator(S('profile-name'))).toBeVisible();
  });
});
'''

    def test_successful_fix_no_regression(self, medic, temp_dir, mock_redis):
        """
        Test Scenario 1: Successful fix with no new failures.

        Flow:
        1. Baseline: 3 passed, 0 failed
        2. Apply fix
        3. After fix: 3 passed, 0 failed
        4. No new failures → Success
        5. Artifacts generated
        """
        # Create failing test file
        test_path = Path(temp_dir) / 'profile.spec.ts'
        test_path.write_text(self.FAILING_TEST)

        error_message = "Error: locator.click: Timeout 30000ms exceeded.\nwaiting for locator('[data-testid=\"old-profile-button\"]')"

        # Mock baseline regression results (all passing)
        baseline_result = {
            'success': True,
            'passed': 3,
            'failed': 0,
            'total': 3,
            'errors': [],
            'stdout': '3 passed',
            'return_code': 0
        }

        # Mock after-fix regression results (still all passing)
        after_fix_result = {
            'success': True,
            'passed': 3,
            'failed': 0,
            'total': 3,
            'errors': [],
            'stdout': '3 passed',
            'return_code': 0
        }

        # Mock AI fix generation
        mock_ai_response = MagicMock()
        mock_ai_response.content = [MagicMock()]
        mock_ai_response.content[0].text = f"""
DIAGNOSIS: Selector 'old-profile-button' not found. Updated to 'profile-button' based on current UI.

CONFIDENCE: 0.85

FIX:
```typescript
{self.FIXED_TEST}
```
"""
        mock_ai_response.usage = MagicMock()
        mock_ai_response.usage.input_tokens = 500
        mock_ai_response.usage.output_tokens = 200

        call_count = [0]

        def mock_run_regression(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return baseline_result
            else:
                return after_fix_result

        with patch.object(medic, '_run_regression_tests', side_effect=mock_run_regression):
            with patch.object(medic.client.messages, 'create', return_value=mock_ai_response):
                result = medic.execute(
                    test_path=str(test_path),
                    error_message=error_message,
                    task_id='test_task_001',
                    feature='User Profile'
                )

        # Validate result
        assert result.success is True, f"Medic should succeed. Error: {result.error}"
        assert result.data['status'] == 'fix_applied'
        assert result.data['comparison']['new_failures'] == 0
        assert result.data['comparison']['improved'] is False  # No improvement in regression (was already passing)

        # Verify fix was applied
        fixed_content = test_path.read_text()
        assert 'profile-button' in fixed_content
        assert 'old-profile-button' not in fixed_content

        # Verify artifacts were generated
        artifacts = result.data['artifacts']
        assert 'diff_path' in artifacts
        assert 'report_path' in artifacts

        # Verify diff file exists
        diff_path = Path(artifacts['diff_path'])
        assert diff_path.exists()
        diff_content = diff_path.read_text()
        assert '--- a/' in diff_content
        assert '+++ b/' in diff_content
        # Check that diff contains the change (- line removed, + line added)
        assert 'old-profile-button' in diff_content
        assert 'profile-button' in diff_content

        # Verify regression report
        report_path = Path(artifacts['report_path'])
        assert report_path.exists()
        report = json.loads(report_path.read_text())
        assert report['test_path'] == str(test_path)
        assert report['baseline']['passed'] == 3
        assert report['after_fix']['passed'] == 3
        assert report['comparison']['new_failures'] == 0
        assert report['fix_applied'] is True
        assert report['hippocratic_oath_honored'] is True

        # Verify cost tracked
        assert result.cost_usd > 0

        # Verify Redis was called to track attempts
        assert mock_redis.set.called

    def test_fix_introduces_regression_rollback(self, medic, temp_dir, mock_redis, mock_hitl):
        """
        Test Scenario 2: Fix introduces new failure → rollback and escalate.

        Flow:
        1. Baseline: 3 passed, 0 failed
        2. Apply fix
        3. After fix: 2 passed, 1 failed (NEW FAILURE)
        4. Hippocratic Oath violated → Rollback fix
        5. Escalate to HITL with full context
        """
        test_path = Path(temp_dir) / 'profile.spec.ts'
        test_path.write_text(self.FAILING_TEST)

        error_message = "Error: Selector not found"

        # Mock baseline (all passing)
        baseline_result = {
            'success': True,
            'passed': 3,
            'failed': 0,
            'total': 3,
            'errors': [],
            'stdout': '3 passed',
            'return_code': 0
        }

        # Mock after-fix (new failure introduced!)
        after_fix_result = {
            'success': True,
            'passed': 2,
            'failed': 1,
            'total': 3,
            'errors': ['Error: locator.click: Auth test failed after profile fix'],
            'stdout': '2 passed, 1 failed',
            'return_code': 1
        }

        # Mock AI fix that breaks regression
        mock_ai_response = MagicMock()
        mock_ai_response.content = [MagicMock()]
        mock_ai_response.content[0].text = f"""
DIAGNOSIS: Selector updated

CONFIDENCE: 0.8

FIX:
```typescript
{self.FIXED_TEST_BREAKS_REGRESSION}
```
"""
        mock_ai_response.usage = MagicMock()
        mock_ai_response.usage.input_tokens = 500
        mock_ai_response.usage.output_tokens = 200

        call_count = [0]

        def mock_run_regression(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return baseline_result
            else:
                return after_fix_result

        with patch.object(medic, '_run_regression_tests', side_effect=mock_run_regression):
            with patch.object(medic.client.messages, 'create', return_value=mock_ai_response):
                result = medic.execute(
                    test_path=str(test_path),
                    error_message=error_message,
                    task_id='test_task_002',
                    feature='User Profile'
                )

        # Validate failure (escalated to HITL)
        assert result.success is False
        assert 'Escalated to HITL' in result.error
        assert result.data['status'] == 'escalated_to_hitl'
        assert result.data['reason'] == 'regression_detected'
        assert result.data['fix_rolled_back'] is True

        # Verify original content was restored (rollback)
        restored_content = test_path.read_text()
        assert 'old-profile-button' in restored_content
        assert 'localhost:9999' not in restored_content

        # Verify HITL was called
        assert mock_hitl.add.called
        hitl_task = mock_hitl.add.call_args[0][0]
        assert hitl_task['escalation_reason'] == 'regression_detected'
        assert hitl_task['severity'] == 'high'
        assert hitl_task['artifacts']['comparison']['new_failures'] == 1

    def test_low_confidence_escalation(self, medic, temp_dir, mock_redis, mock_hitl):
        """
        Test Scenario 3: Low AI confidence → escalate before applying fix.

        Flow:
        1. Baseline captured
        2. AI generates fix with low confidence (0.4)
        3. Confidence < threshold (0.7) → Escalate to HITL
        4. Fix NOT applied
        """
        test_path = Path(temp_dir) / 'complex.spec.ts'
        test_path.write_text(self.FAILING_TEST)

        error_message = "Error: Complex failure with unclear root cause"

        # Mock baseline
        baseline_result = {
            'success': True,
            'passed': 3,
            'failed': 0,
            'total': 3,
            'errors': [],
            'stdout': '3 passed',
            'return_code': 0
        }

        # Mock AI response with LOW confidence
        mock_ai_response = MagicMock()
        mock_ai_response.content = [MagicMock()]
        mock_ai_response.content[0].text = f"""
DIAGNOSIS: Unclear root cause. Could be timing issue or selector mismatch.

CONFIDENCE: 0.4

FIX:
```typescript
{self.FIXED_TEST}
```
"""
        mock_ai_response.usage = MagicMock()
        mock_ai_response.usage.input_tokens = 500
        mock_ai_response.usage.output_tokens = 200

        with patch.object(medic, '_run_regression_tests', return_value=baseline_result):
            with patch.object(medic.client.messages, 'create', return_value=mock_ai_response):
                result = medic.execute(
                    test_path=str(test_path),
                    error_message=error_message,
                    task_id='test_task_003',
                    feature='Complex Feature'
                )

        # Validate escalation
        assert result.success is False
        assert 'Escalated to HITL' in result.error
        assert result.data['reason'] == 'low_confidence'
        assert result.data['status'] == 'escalated_to_hitl'

        # Verify fix was NOT applied
        content = test_path.read_text()
        assert 'old-profile-button' in content  # Original selector still there

        # Verify HITL was called
        assert mock_hitl.add.called
        hitl_task = mock_hitl.add.call_args[0][0]
        assert hitl_task['escalation_reason'] == 'low_confidence'
        assert hitl_task['ai_confidence'] == 0.4

    def test_max_retries_escalation(self, medic, temp_dir, mock_redis, mock_hitl):
        """
        Test Scenario 4: Max retries exceeded → escalate to HITL.

        Flow:
        1. Mock Redis to show 3 previous attempts
        2. Current attempt = 4th attempt
        3. MAX_RETRIES = 3 → Escalate immediately
        4. No fix attempted
        """
        test_path = Path(temp_dir) / 'failing.spec.ts'
        test_path.write_text(self.FAILING_TEST)

        error_message = "Error: Persistent failure"

        # Mock Redis to return 3 previous attempts
        mock_redis.get.return_value = 3  # Already tried 3 times

        with patch.object(medic, '_run_regression_tests') as mock_regression:
            result = medic.execute(
                test_path=str(test_path),
                error_message=error_message,
                task_id='test_task_004',
                feature='Persistent Bug'
            )

        # Validate escalation (should happen BEFORE regression tests)
        assert result.success is False
        assert 'Escalated to HITL' in result.error
        assert result.data['reason'] == 'max_retries_exceeded'
        assert result.data['attempts'] == 4

        # Verify regression tests were NOT run (escalated early)
        assert not mock_regression.called

        # Verify HITL was called
        assert mock_hitl.add.called
        hitl_task = mock_hitl.add.call_args[0][0]
        assert hitl_task['escalation_reason'] == 'max_retries_exceeded'
        assert hitl_task['attempts'] == 4

    def test_baseline_regression_failure(self, medic, temp_dir):
        """
        Test Scenario 5: Baseline regression tests fail → abort with error.

        Flow:
        1. Try to capture baseline
        2. Baseline fails (pre-existing issue)
        3. Abort - cannot proceed without valid baseline
        """
        test_path = Path(temp_dir) / 'test.spec.ts'
        test_path.write_text(self.FAILING_TEST)

        error_message = "Error: Selector not found"

        # Mock baseline failure
        baseline_result = {
            'success': False,
            'error': 'Regression tests timed out after 120s'
        }

        with patch.object(medic, '_run_regression_tests', return_value=baseline_result):
            result = medic.execute(
                test_path=str(test_path),
                error_message=error_message,
                task_id='test_task_005'
            )

        # Validate failure
        assert result.success is False
        assert 'Failed to capture baseline' in result.error
        assert 'baseline' in result.data

    def test_diff_generation_accuracy(self, medic, temp_dir):
        """
        Test that unified diff is generated correctly.
        """
        original = "line 1\nline 2\nold content\nline 4\n"
        fixed = "line 1\nline 2\nnew content\nline 4\n"
        file_path = "test.spec.ts"

        diff = medic._generate_diff(original, fixed, file_path)

        # Validate diff format
        assert '--- a/test.spec.ts' in diff
        assert '+++ b/test.spec.ts' in diff
        assert '-old content' in diff
        assert '+new content' in diff

    def test_comparison_logic(self, medic):
        """
        Test regression comparison logic.
        """
        # Scenario: No change
        baseline = {'passed': 3, 'failed': 0}
        after_fix = {'passed': 3, 'failed': 0}
        comparison = medic._compare_results(baseline, after_fix)
        assert comparison['new_failures'] == 0
        assert comparison['improved'] is False

        # Scenario: Improvement
        baseline = {'passed': 2, 'failed': 1}
        after_fix = {'passed': 3, 'failed': 0}
        comparison = medic._compare_results(baseline, after_fix)
        assert comparison['new_failures'] == 0
        assert comparison['improved'] is True

        # Scenario: Regression
        baseline = {'passed': 3, 'failed': 0}
        after_fix = {'passed': 2, 'failed': 1}
        comparison = medic._compare_results(baseline, after_fix)
        assert comparison['new_failures'] == 1
        assert comparison['improved'] is False

        # Scenario: Mixed (fixed one, broke another)
        baseline = {'passed': 2, 'failed': 1}
        after_fix = {'passed': 2, 'failed': 1}
        comparison = medic._compare_results(baseline, after_fix)
        assert comparison['new_failures'] == 0  # Net zero
        assert comparison['improved'] is False

    def test_artifact_generation(self, medic, temp_dir):
        """
        Test artifact generation (diff, report).
        """
        diff = "--- a/test.spec.ts\n+++ b/test.spec.ts\n@@ -1,1 +1,1 @@\n-old\n+new\n"
        baseline = {'passed': 3, 'failed': 0, 'total': 3}
        after_fix = {'passed': 3, 'failed': 0, 'total': 3}
        comparison = {'new_failures': 0, 'baseline_passed': 3, 'baseline_failed': 0,
                     'after_passed': 3, 'after_failed': 0, 'improved': False}
        diagnosis = "Fixed selector"
        test_path = str(Path(temp_dir) / 'test.spec.ts')

        # Override artifact directory
        medic._artifact_dir = Path(temp_dir) / 'artifacts'
        medic._artifact_dir.mkdir(exist_ok=True)

        # Patch Path in _generate_artifacts to use temp dir
        with patch('agent_system.agents.medic.Path') as mock_path_class:
            def path_side_effect(*args, **kwargs):
                if len(args) >= 1 and str(args[0]) == '__file__':
                    # Return path that resolves to temp dir
                    fake_file = Path(temp_dir) / 'fake_medic.py'
                    return fake_file
                return Path(*args, **kwargs)

            mock_path_class.side_effect = path_side_effect

            artifacts = medic._generate_artifacts(
                diff=diff,
                baseline=baseline,
                after_fix=after_fix,
                comparison=comparison,
                diagnosis=diagnosis,
                test_path=test_path
            )

        # Verify artifacts dict
        assert 'diff_path' in artifacts
        assert 'report_path' in artifacts

        # Verify files exist
        diff_path = Path(artifacts['diff_path'])
        report_path = Path(artifacts['report_path'])

        assert diff_path.exists()
        assert report_path.exists()

        # Verify diff content
        diff_content = diff_path.read_text()
        assert '--- a/test.spec.ts' in diff_content

        # Verify report content
        report = json.loads(report_path.read_text())
        assert report['diagnosis'] == 'Fixed selector'
        assert report['hippocratic_oath_honored'] is True
        assert report['baseline']['passed'] == 3
        assert report['after_fix']['passed'] == 3

    def test_attempt_tracking(self, medic, mock_redis):
        """
        Test that fix attempts are tracked correctly in Redis.
        """
        task_id = 'test_task_123'
        test_path = '/path/to/test.spec.ts'

        # First attempt
        attempts = medic._increment_fix_attempts(task_id, test_path)
        assert attempts == 1
        assert mock_redis.set.called

        # Second attempt
        mock_redis.get.return_value = 1
        attempts = medic._increment_fix_attempts(task_id, test_path)
        assert attempts == 2

    def test_fix_prompt_construction(self, medic):
        """
        Test that fix prompt includes all necessary context.
        """
        test_path = '/path/to/test.spec.ts'
        test_content = 'test code here'
        error_message = 'Selector not found'
        context = {'selector_usage': ['file1.ts', 'file2.ts']}

        prompt = medic._build_fix_prompt(
            test_path=test_path,
            test_content=test_content,
            error_message=error_message,
            context=context
        )

        # Verify prompt structure
        assert 'HIPPOCRATIC OATH' in prompt
        assert 'TEST FILE: /path/to/test.spec.ts' in prompt
        assert 'ERROR MESSAGE:' in prompt
        assert 'Selector not found' in prompt
        assert 'CURRENT TEST CODE:' in prompt
        assert 'test code here' in prompt
        assert 'CONTEXT:' in prompt
        assert 'DIAGNOSIS:' in prompt
        assert 'CONFIDENCE:' in prompt
        assert 'FIX:' in prompt


class TestMedicHippocraticOath:
    """Test enforcement of Medic's Hippocratic Oath."""

    @pytest.fixture
    def medic(self, monkeypatch):
        """Create Medic with mocked dependencies."""
        # Mock environment
        monkeypatch.setenv('ANTHROPIC_API_KEY', 'test-key-12345')

        redis_mock = MagicMock(spec=RedisClient)
        redis_mock.get.return_value = None
        redis_mock.set.return_value = True
        redis_mock.client = MagicMock()
        redis_mock.client.rpush.return_value = 1
        redis_mock.client.expire.return_value = True
        redis_mock.client.lrange.return_value = []

        hitl_mock = MagicMock(spec=HITLQueue)
        hitl_mock.add.return_value = True

        return MedicAgent(redis_client=redis_mock, hitl_queue=hitl_mock)

    def test_zero_new_failures_enforced(self, medic):
        """
        Test that max_new_failures = 0 is strictly enforced.
        """
        baseline = {'passed': 5, 'failed': 0}

        # Any increase in failures should be caught
        for new_failed_count in [1, 2, 5]:
            after_fix = {'passed': 5 - new_failed_count, 'failed': new_failed_count}
            comparison = medic._compare_results(baseline, after_fix)
            assert comparison['new_failures'] == new_failed_count
            assert comparison['new_failures'] > 0  # Should trigger rollback

    def test_improvement_allowed(self, medic):
        """
        Test that improvements (fewer failures) are allowed and detected.
        """
        baseline = {'passed': 3, 'failed': 2}
        after_fix = {'passed': 5, 'failed': 0}

        comparison = medic._compare_results(baseline, after_fix)
        assert comparison['new_failures'] == 0
        assert comparison['improved'] is True

    def test_neutral_change_allowed(self, medic):
        """
        Test that fixes with no regression impact are allowed.
        """
        baseline = {'passed': 3, 'failed': 1}
        after_fix = {'passed': 3, 'failed': 1}

        comparison = medic._compare_results(baseline, after_fix)
        assert comparison['new_failures'] == 0


class TestMedicEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test files."""
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp)

    @pytest.fixture
    def medic(self, monkeypatch):
        """Create Medic with mocked dependencies."""
        # Mock environment
        monkeypatch.setenv('ANTHROPIC_API_KEY', 'test-key-12345')

        redis_mock = MagicMock(spec=RedisClient)
        redis_mock.get.return_value = None
        redis_mock.set.return_value = True
        redis_mock.client = MagicMock()
        redis_mock.client.rpush.return_value = 1
        redis_mock.client.expire.return_value = True
        redis_mock.client.lrange.return_value = []

        hitl_mock = MagicMock(spec=HITLQueue)
        hitl_mock.add.return_value = True

        return MedicAgent(redis_client=redis_mock, hitl_queue=hitl_mock)

    def test_missing_file(self, medic):
        """Test handling of missing test file."""
        result = medic.execute(
            test_path='/nonexistent/test.spec.ts',
            error_message='Error'
        )

        assert result.success is False
        assert 'Could not read test file' in result.error

    def test_ai_response_parse_failure(self, medic, temp_dir):
        """Test handling of unparseable AI response."""
        test_path = Path(temp_dir) / 'test.spec.ts'
        test_path.write_text('test content')

        # Mock baseline
        baseline_result = {
            'success': True,
            'passed': 3,
            'failed': 0,
            'total': 3,
            'errors': [],
            'stdout': '3 passed',
            'return_code': 0
        }

        # Mock AI response with no code block
        mock_ai_response = MagicMock()
        mock_ai_response.content = [MagicMock()]
        mock_ai_response.content[0].text = "This is just text with no code block"
        mock_ai_response.usage = MagicMock()
        mock_ai_response.usage.input_tokens = 100
        mock_ai_response.usage.output_tokens = 50

        with patch.object(medic, '_run_regression_tests', return_value=baseline_result):
            with patch.object(medic.client.messages, 'create', return_value=mock_ai_response):
                result = medic.execute(
                    test_path=str(test_path),
                    error_message='Error'
                )

        assert result.success is False
        assert 'Could not extract fixed code' in result.error

    def test_regression_timeout(self, medic, temp_dir):
        """Test handling of regression test timeout."""
        test_path = Path(temp_dir) / 'test.spec.ts'
        test_path.write_text('test content')

        # Mock timeout
        with patch.object(medic, '_run_regression_tests',
                         side_effect=subprocess.TimeoutExpired('playwright', 120)):
            result = medic.execute(
                test_path=str(test_path),
                error_message='Error'
            )

        # Should handle gracefully
        assert result.success is False


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
