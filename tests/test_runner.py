"""
Unit tests for Runner Agent
Tests test execution, failure detection, timeout handling, and artifact collection.

Test Coverage:
1. Successful test execution with JSON/TAP/text output
2. Failure detection with error extraction and categorization
3. Timeout handling (60s default)
4. Output parsing for multiple error formats (JSON, TAP, text)
5. Artifact collection (screenshots, videos, traces)
6. Subprocess mocking to avoid actual Playwright execution
7. Error categorization (selector, timeout, assertion, network, javascript)
8. Console error and network failure extraction
"""
import pytest
import subprocess
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from agent_system.agents.runner import RunnerAgent, TestResult, ParsedError
from agent_system.agents.base_agent import AgentResult


@pytest.fixture
def runner_agent():
    """Create RunnerAgent instance."""
    return RunnerAgent()


@pytest.fixture
def mock_subprocess_text_success():
    """Mock successful subprocess result with text output."""
    mock_result = MagicMock()
    mock_result.stdout = """
Running 3 tests using 1 worker

  ✓  tests/example.spec.ts:5:1 › should load homepage (1200ms)
  ✓  tests/example.spec.ts:10:1 › should click button (800ms)
  ✓  tests/example.spec.ts:15:1 › should submit form (2100ms)

  3 passed (4.1s)
"""
    mock_result.stderr = ""
    mock_result.returncode = 0
    return mock_result


@pytest.fixture
def mock_subprocess_json_success():
    """Mock successful subprocess result with JSON output."""
    mock_result = MagicMock()
    json_output = {
        "suites": [{
            "title": "example tests",
            "specs": [{
                "title": "should load homepage",
                "tests": [{
                    "results": [{
                        "status": "passed",
                        "duration": 1200
                    }]
                }]
            }, {
                "title": "should click button",
                "tests": [{
                    "results": [{
                        "status": "passed",
                        "duration": 800
                    }]
                }]
            }]
        }]
    }
    mock_result.stdout = json.dumps(json_output)
    mock_result.stderr = ""
    mock_result.returncode = 0
    return mock_result


@pytest.fixture
def mock_subprocess_tap_output():
    """Mock TAP format output."""
    mock_result = MagicMock()
    mock_result.stdout = """TAP version 13
1..3
ok 1 - tests/example.spec.ts › should load homepage
ok 2 - tests/example.spec.ts › should click button
not ok 3 - tests/example.spec.ts › should fail
# Error: Timeout exceeded
# at page.click (example.spec.ts:15:10)
"""
    mock_result.stderr = ""
    mock_result.returncode = 1
    return mock_result


@pytest.mark.unit
class TestRunnerAgentInitialization:
    """Test Runner agent initialization."""

    def test_initialization(self, runner_agent):
        """Test agent initializes correctly."""
        assert runner_agent.name == 'runner'
        assert runner_agent.default_timeout == 60
        assert runner_agent.reporter_format == 'json'

    def test_initialization_with_config(self):
        """Test agent loads config if available."""
        agent = RunnerAgent()
        assert agent.config is not None
        assert agent.reporter_format == 'json'


@pytest.mark.unit
class TestRunnerTextOutputParsing:
    """Test text output format parsing."""

    @patch('agent_system.agents.runner.subprocess.run')
    @patch('agent_system.agents.runner.RunnerAgent._collect_artifacts')
    def test_execute_text_success(self, mock_artifacts, mock_run, runner_agent, mock_subprocess_text_success):
        """Test successful execution with text output."""
        mock_run.return_value = mock_subprocess_text_success
        mock_artifacts.return_value = {'screenshots': [], 'videos': [], 'traces': []}

        result = runner_agent.execute(test_path='tests/example.spec.ts', reporter='text')

        assert result.success is True
        assert result.data['status'] == 'pass'
        assert result.data['passed_count'] == 3
        assert result.data['failed_count'] == 0
        assert 'test_results' in result.data
        assert 'console_errors' in result.data
        assert 'network_failures' in result.data

    def test_parse_text_output_with_failures(self, runner_agent):
        """Test parsing text output with failures."""
        stdout = """
  ✓  test 1 (100ms)
  ✗  test 2 (200ms)

  1 passed, 1 failed (300ms)

Error: Selector not found
    at test.spec.ts:10:5
"""
        parsed = runner_agent._parse_text_output(stdout, "", 1)

        assert parsed['status'] == 'fail'
        assert parsed['passed_count'] == 1
        assert parsed['failed_count'] == 1
        assert len(parsed['errors']) > 0

    def test_extract_console_errors(self, runner_agent):
        """Test console error extraction."""
        output = """
console.error: Failed to load resource
console.error: Network request failed
"""
        console_errors = runner_agent._extract_console_errors(output)

        assert len(console_errors) == 2
        assert "Failed to load resource" in console_errors[0]

    def test_extract_network_failures(self, runner_agent):
        """Test network failure extraction."""
        output = """
net::ERR_CONNECTION_REFUSED
Failed to load resource: the server responded with a status of 404
"""
        network_failures = runner_agent._extract_network_failures(output)

        assert len(network_failures) >= 1
        assert any('ERR_CONNECTION_REFUSED' in f['type'] for f in network_failures)


@pytest.mark.unit
class TestRunnerJSONOutputParsing:
    """Test JSON output format parsing."""

    @patch('agent_system.agents.runner.subprocess.run')
    @patch('agent_system.agents.runner.RunnerAgent._collect_artifacts')
    def test_execute_json_success(self, mock_artifacts, mock_run, runner_agent, mock_subprocess_json_success):
        """Test successful execution with JSON output."""
        mock_run.return_value = mock_subprocess_json_success
        mock_artifacts.return_value = {'screenshots': [], 'videos': [], 'traces': []}

        result = runner_agent.execute(test_path='tests/example.spec.ts', reporter='json')

        assert result.success is True
        assert result.data['passed_count'] == 2
        assert result.data['failed_count'] == 0
        assert len(result.data['test_results']) == 2

    def test_parse_json_with_errors(self, runner_agent):
        """Test JSON parsing with error information."""
        json_output = {
            "suites": [{
                "title": "suite",
                "specs": [{
                    "title": "test",
                    "tests": [{
                        "results": [{
                            "status": "failed",
                            "duration": 1000,
                            "error": {
                                "message": "Timeout exceeded",
                                "stack": "at page.click (test.spec.ts:10:5)"
                            }
                        }]
                    }]
                }]
            }]
        }

        parsed = runner_agent._parse_json_output(json.dumps(json_output), "", 1)

        assert parsed['status'] == 'fail'
        assert parsed['failed_count'] == 1
        assert len(parsed['errors']) == 1
        assert parsed['errors'][0]['category'] == 'timeout'

    def test_json_fallback_to_text(self, runner_agent):
        """Test fallback to text parsing when JSON is invalid."""
        invalid_json = "3 passed (2.0s)"

        parsed = runner_agent._parse_json_output(invalid_json, "", 0)

        assert parsed['passed_count'] == 3
        assert parsed['status'] == 'pass'


@pytest.mark.unit
class TestRunnerTAPOutputParsing:
    """Test TAP output format parsing."""

    @patch('agent_system.agents.runner.subprocess.run')
    @patch('agent_system.agents.runner.RunnerAgent._collect_artifacts')
    def test_execute_tap_format(self, mock_artifacts, mock_run, runner_agent, mock_subprocess_tap_output):
        """Test execution with TAP format."""
        mock_run.return_value = mock_subprocess_tap_output
        mock_artifacts.return_value = {'screenshots': [], 'videos': [], 'traces': []}

        result = runner_agent.execute(test_path='tests/example.spec.ts', reporter='tap')

        assert result.success is False
        assert result.data['passed_count'] == 2
        assert result.data['failed_count'] == 1

    def test_parse_tap_with_skip(self, runner_agent):
        """Test TAP parsing with skipped tests."""
        tap_output = """ok 1 - test 1
ok 2 - test 2 # SKIP
not ok 3 - test 3
"""
        parsed = runner_agent._parse_tap_output(tap_output, "", 1)

        assert parsed['passed_count'] == 1
        assert parsed['skipped_count'] == 1
        assert parsed['failed_count'] == 1


@pytest.mark.unit
class TestErrorCategorization:
    """Test error categorization functionality."""

    def test_categorize_selector_error(self, runner_agent):
        """Test selector error categorization."""
        error = runner_agent._categorize_error(
            "locator not found",
            "at page.click (test.spec.ts:10:5)"
        )

        assert error.category == 'selector'
        assert error.file_path == 'test.spec.ts'
        assert error.line_number == 10

    def test_categorize_timeout_error(self, runner_agent):
        """Test timeout error categorization."""
        error = runner_agent._categorize_error(
            "Timeout 30000ms exceeded",
            ""
        )

        assert error.category == 'timeout'

    def test_categorize_assertion_error(self, runner_agent):
        """Test assertion error categorization."""
        error = runner_agent._categorize_error(
            "expect(received).toBe(expected)",
            ""
        )

        assert error.category == 'assertion'

    def test_categorize_network_error(self, runner_agent):
        """Test network error categorization."""
        error = runner_agent._categorize_error(
            "net::ERR_CONNECTION_REFUSED",
            ""
        )

        assert error.category == 'network'

    def test_categorize_javascript_error(self, runner_agent):
        """Test JavaScript error categorization."""
        error = runner_agent._categorize_error(
            "ReferenceError: undefined is not defined",
            ""
        )

        assert error.category == 'javascript'

    def test_categorize_unknown_error(self, runner_agent):
        """Test unknown error categorization."""
        error = runner_agent._categorize_error(
            "Something went wrong",
            ""
        )

        assert error.category == 'unknown'


@pytest.mark.unit
class TestTimeoutHandling:
    """Test timeout handling."""

    @patch('agent_system.agents.runner.subprocess.run')
    @patch('agent_system.agents.runner.time.time')
    def test_execute_timeout(self, mock_time, mock_run, runner_agent):
        """Test execution timeout handling."""
        mock_time.side_effect = [1000.0, 1060.0]
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd=['npx', 'playwright', 'test', 'tests/slow.spec.ts'],
            timeout=60
        )

        result = runner_agent.execute(test_path='tests/slow.spec.ts', timeout=60)

        assert result.success is False
        assert result.error == "Test execution timed out after 60s"
        assert result.data['status'] == 'timeout'
        assert result.execution_time_ms >= 0

    @patch('agent_system.agents.runner.subprocess.run')
    def test_custom_timeout(self, mock_run, runner_agent, mock_subprocess_text_success):
        """Test custom timeout parameter."""
        mock_run.return_value = mock_subprocess_text_success

        runner_agent.execute(test_path='tests/example.spec.ts', timeout=45, reporter='text')

        # Verify timeout was passed to subprocess
        assert mock_run.call_args[1]['timeout'] == 45


@pytest.mark.unit
class TestExceptionHandling:
    """Test exception handling."""

    @patch('agent_system.agents.runner.subprocess.run')
    def test_subprocess_error(self, mock_run, runner_agent):
        """Test handling of subprocess errors."""
        mock_run.side_effect = OSError("Command not found: npx")

        result = runner_agent.execute(test_path='tests/example.spec.ts')

        assert result.success is False
        assert "Execution error:" in result.error
        assert "Command not found: npx" in result.error
        assert result.data['status'] == 'error'

    @patch('agent_system.agents.runner.subprocess.run')
    def test_permission_error(self, mock_run, runner_agent):
        """Test handling of permission errors."""
        mock_run.side_effect = PermissionError("Permission denied")

        result = runner_agent.execute(test_path='tests/example.spec.ts')

        assert result.success is False
        assert "Permission denied" in result.error


@pytest.mark.unit
class TestArtifactCollection:
    """Test artifact collection."""

    def test_collect_artifacts_structure(self, runner_agent):
        """Test artifact collection returns correct structure."""
        artifacts = runner_agent._collect_artifacts('tests/example.spec.ts')

        assert 'screenshots' in artifacts
        assert 'videos' in artifacts
        assert 'traces' in artifacts
        assert isinstance(artifacts['screenshots'], list)
        assert isinstance(artifacts['videos'], list)
        assert isinstance(artifacts['traces'], list)

    def test_collect_artifacts_no_directories(self, runner_agent, tmp_path):
        """Test artifact collection when no directories exist."""
        # Mock Path to return non-existent directories
        with patch('agent_system.agents.runner.Path') as mock_path:
            mock_dir = MagicMock()
            mock_dir.exists.return_value = False
            mock_path.return_value = mock_dir

            artifacts = runner_agent._collect_artifacts('tests/example.spec.ts')

        assert artifacts['screenshots'] == []
        assert artifacts['videos'] == []
        assert artifacts['traces'] == []


@pytest.mark.unit
class TestDataIntegrity:
    """Test data integrity and truncation."""

    @patch('agent_system.agents.runner.subprocess.run')
    @patch('agent_system.agents.runner.RunnerAgent._collect_artifacts')
    def test_stdout_truncation(self, mock_artifacts, mock_run, runner_agent):
        """Test stdout is truncated to 2000 chars."""
        mock_result = MagicMock()
        mock_result.stdout = "x" * 3000  # 3000 chars
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        mock_artifacts.return_value = {'screenshots': [], 'videos': [], 'traces': []}

        result = runner_agent.execute(test_path='tests/example.spec.ts', reporter='text')

        assert len(result.data['stdout']) == 2000

    @patch('agent_system.agents.runner.subprocess.run')
    @patch('agent_system.agents.runner.RunnerAgent._collect_artifacts')
    def test_stderr_truncation(self, mock_artifacts, mock_run, runner_agent):
        """Test stderr is truncated to 1000 chars."""
        mock_result = MagicMock()
        mock_result.stdout = "1 passed (1.0s)"
        mock_result.stderr = "y" * 2000  # 2000 chars
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        mock_artifacts.return_value = {'screenshots': [], 'videos': [], 'traces': []}

        result = runner_agent.execute(test_path='tests/example.spec.ts', reporter='text')

        assert result.data['stderr'] is not None
        assert len(result.data['stderr']) == 1000


@pytest.mark.unit
class TestExecutionMetrics:
    """Test execution timing and metrics."""

    @patch('agent_system.agents.runner.subprocess.run')
    @patch('agent_system.agents.runner.RunnerAgent._collect_artifacts')
    @patch('agent_system.agents.runner.time.time')
    def test_execution_time_tracking(self, mock_time, mock_artifacts, mock_run, runner_agent):
        """Test execution time is tracked correctly."""
        mock_time.side_effect = [1000.0, 1002.5]  # 2.5 seconds

        mock_result = MagicMock()
        mock_result.stdout = "1 passed (2.5s)"
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        mock_artifacts.return_value = {'screenshots': [], 'videos': [], 'traces': []}

        result = runner_agent.execute(test_path='tests/example.spec.ts', reporter='text')

        assert result.execution_time_ms == 2500


@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases and unusual scenarios."""

    @patch('agent_system.agents.runner.subprocess.run')
    @patch('agent_system.agents.runner.RunnerAgent._collect_artifacts')
    def test_empty_stdout(self, mock_artifacts, mock_run, runner_agent):
        """Test handling of empty stdout."""
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        mock_artifacts.return_value = {'screenshots': [], 'videos': [], 'traces': []}

        result = runner_agent.execute(test_path='tests/example.spec.ts', reporter='text')

        assert result.success is False
        assert result.data['status'] == 'error'

    @patch('agent_system.agents.runner.subprocess.run')
    @patch('agent_system.agents.runner.RunnerAgent._collect_artifacts')
    def test_malformed_output(self, mock_artifacts, mock_run, runner_agent):
        """Test handling of malformed output."""
        mock_result = MagicMock()
        mock_result.stdout = "Completely unexpected output!!!"
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        mock_artifacts.return_value = {'screenshots': [], 'videos': [], 'traces': []}

        result = runner_agent.execute(test_path='tests/example.spec.ts', reporter='text')

        # Should handle gracefully
        assert result.data['passed_count'] == 0
        assert result.data['failed_count'] == 0


@pytest.mark.unit
class TestIntegrationScenarios:
    """Test realistic integration scenarios."""

    @patch('agent_system.agents.runner.subprocess.run')
    @patch('agent_system.agents.runner.RunnerAgent._collect_artifacts')
    def test_full_successful_run(self, mock_artifacts, mock_run, runner_agent):
        """Test complete successful run."""
        mock_result = MagicMock()
        mock_result.stdout = """
  ✓  test 1 (100ms)
  ✓  test 2 (200ms)
  ✓  test 3 (300ms)

  3 passed (600ms)
"""
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        mock_artifacts.return_value = {
            'screenshots': ['screen1.png', 'screen2.png'],
            'videos': ['video.webm'],
            'traces': ['trace.zip']
        }

        result = runner_agent.execute(test_path='tests/example.spec.ts', reporter='text')

        assert result.success is True
        assert result.data['passed_count'] == 3
        assert len(result.data['artifacts']['screenshots']) == 2
        assert len(result.data['artifacts']['videos']) == 1

    @patch('agent_system.agents.runner.subprocess.run')
    @patch('agent_system.agents.runner.RunnerAgent._collect_artifacts')
    def test_partial_failure(self, mock_artifacts, mock_run, runner_agent):
        """Test partial failure scenario."""
        mock_result = MagicMock()
        mock_result.stdout = """
  ✓  test 1 (100ms)
  ✗  test 2 (200ms)

  1 passed, 1 failed (300ms)

Error: Assertion failed
    at test.spec.ts:45:10
"""
        mock_result.stderr = ""
        mock_result.returncode = 1
        mock_run.return_value = mock_result

        mock_artifacts.return_value = {
            'screenshots': ['failure-screen.png'],
            'videos': ['failure-video.webm'],
            'traces': []
        }

        result = runner_agent.execute(test_path='tests/example.spec.ts', reporter='text')

        assert result.success is False
        assert result.data['passed_count'] == 1
        assert result.data['failed_count'] == 1
        assert len(result.data['errors']) > 0


@pytest.mark.unit
class TestReporterFormats:
    """Test different reporter format handling."""

    @patch('agent_system.agents.runner.subprocess.run')
    @patch('agent_system.agents.runner.RunnerAgent._collect_artifacts')
    def test_json_reporter_command(self, mock_artifacts, mock_run, runner_agent, mock_subprocess_json_success):
        """Test JSON reporter adds --reporter flag."""
        mock_run.return_value = mock_subprocess_json_success
        mock_artifacts.return_value = {'screenshots': [], 'videos': [], 'traces': []}

        runner_agent.execute(test_path='tests/example.spec.ts', reporter='json')

        call_args = mock_run.call_args[0][0]
        assert '--reporter' in call_args
        assert 'json' in call_args

    @patch('agent_system.agents.runner.subprocess.run')
    @patch('agent_system.agents.runner.RunnerAgent._collect_artifacts')
    def test_text_reporter_no_flag(self, mock_artifacts, mock_run, runner_agent, mock_subprocess_text_success):
        """Test text reporter doesn't add --reporter flag."""
        mock_run.return_value = mock_subprocess_text_success
        mock_artifacts.return_value = {'screenshots': [], 'videos': [], 'traces': []}

        runner_agent.execute(test_path='tests/example.spec.ts', reporter='text')

        call_args = mock_run.call_args[0][0]
        assert '--reporter' not in call_args


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
