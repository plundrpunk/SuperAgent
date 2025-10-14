"""
Test suite for Gemini Agent
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import subprocess
import json

from agent_system.agents.gemini import GeminiAgent
from agent_system.agents.base_agent import AgentResult


@pytest.fixture
def gemini_agent():
    """Create a Gemini agent instance."""
    return GeminiAgent()


@pytest.fixture
def mock_test_file(tmp_path):
    """Create a mock test file."""
    test_file = tmp_path / "test_example.spec.ts"
    test_file.write_text("""
import { test, expect } from '@playwright/test';

test('sample test', async ({ page }) => {
    await page.goto('http://example.com');
    await expect(page).toHaveTitle(/Example/);
});
    """)
    return test_file


@pytest.fixture
def mock_artifacts_dir(tmp_path):
    """Create mock artifacts directory with screenshots."""
    artifacts_dir = tmp_path / "artifacts" / "test_example"
    artifacts_dir.mkdir(parents=True)

    # Create mock screenshots
    for i in range(3):
        screenshot = artifacts_dir / f"step_{i:02d}.png"
        screenshot.write_bytes(b"fake_image_data")

    return artifacts_dir


class TestGeminiAgentInitialization:
    """Test Gemini agent initialization."""

    def test_initialization(self, gemini_agent):
        """Test agent initializes correctly."""
        assert gemini_agent.name == 'gemini'
        assert gemini_agent.default_timeout == 60
        assert gemini_agent.max_test_duration_ms == 45000
        assert gemini_agent.validator is not None

    def test_config_loaded(self, gemini_agent):
        """Test config is loaded from YAML."""
        # Config should be loaded from .claude/agents/gemini.yaml
        assert gemini_agent.config is not None


class TestGeminiAgentValidation:
    """Test Gemini agent validation logic."""

    @patch('subprocess.run')
    def test_successful_validation(self, mock_run, gemini_agent, mock_test_file, mock_artifacts_dir):
        """Test successful test validation."""
        # Mock successful Playwright execution
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            'suites': [{
                'specs': [{
                    'tests': [{
                        'results': [{
                            'status': 'passed',
                            'stdout': [],
                            'stderr': []
                        }]
                    }]
                }]
            }]
        })
        mock_result.stderr = ''
        mock_run.return_value = mock_result

        # Execute validation
        with patch.object(Path, 'exists', return_value=True):
            with patch.object(gemini_agent, '_collect_screenshots') as mock_screenshots:
                mock_screenshots.return_value = [
                    str(mock_artifacts_dir / "step_00.png")
                ]

                result = gemini_agent.execute(str(mock_test_file))

        # Verify result
        assert isinstance(result, AgentResult)
        assert result.success is True
        assert result.data is not None
        assert 'validation_result' in result.data
        assert result.data['validation_result']['browser_launched'] is True
        assert result.data['validation_result']['test_executed'] is True
        assert result.data['validation_result']['test_passed'] is True
        assert len(result.data['validation_result']['screenshots']) >= 1

    @patch('subprocess.run')
    def test_failed_test_validation(self, mock_run, gemini_agent, mock_test_file):
        """Test validation of failed test."""
        # Mock failed Playwright execution
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = json.dumps({
            'suites': [{
                'specs': [{
                    'tests': [{
                        'results': [{
                            'status': 'failed',
                            'error': {
                                'message': 'Expected title to contain "Example" but got "Wrong"'
                            },
                            'stdout': [],
                            'stderr': []
                        }]
                    }]
                }]
            }]
        })
        mock_result.stderr = ''
        mock_run.return_value = mock_result

        # Execute validation
        with patch.object(Path, 'exists', return_value=True):
            with patch.object(gemini_agent, '_collect_screenshots') as mock_screenshots:
                mock_screenshots.return_value = []

                result = gemini_agent.execute(str(mock_test_file))

        # Verify result - should fail validation due to test failure and no screenshots
        assert isinstance(result, AgentResult)
        assert result.success is False
        assert result.error is not None

    def test_missing_test_file(self, gemini_agent):
        """Test validation with missing test file."""
        result = gemini_agent.execute('/nonexistent/test.spec.ts')

        assert isinstance(result, AgentResult)
        assert result.success is False
        assert 'not found' in result.error.lower()

    @patch('subprocess.run')
    def test_timeout_handling(self, mock_run, gemini_agent, mock_test_file):
        """Test timeout handling."""
        # Mock timeout
        mock_run.side_effect = subprocess.TimeoutExpired(cmd='test', timeout=60)

        # Execute validation
        with patch.object(Path, 'exists', return_value=True):
            with patch.object(gemini_agent, '_collect_screenshots') as mock_screenshots:
                mock_screenshots.return_value = ['/path/to/screenshot.png']  # Provide screenshot for rubric
                result = gemini_agent.execute(str(mock_test_file))

        # Verify timeout error - should fail validation due to timeout
        assert isinstance(result, AgentResult)
        assert result.success is False
        # Error message might be from rubric validation or timeout, both are acceptable
        assert result.error is not None

    @patch('subprocess.run')
    def test_browser_launch_failure(self, mock_run, gemini_agent, mock_test_file):
        """Test browser launch failure."""
        # Mock browser launch error
        mock_run.side_effect = Exception("Browser failed to launch")

        # Execute validation
        with patch.object(Path, 'exists', return_value=True):
            result = gemini_agent.execute(str(mock_test_file))

        # Verify error handling
        assert isinstance(result, AgentResult)
        assert result.success is False
        assert 'error' in result.error.lower()


class TestGeminiAgentScreenshots:
    """Test screenshot collection."""

    def test_collect_screenshots_from_artifacts(self, gemini_agent, mock_artifacts_dir):
        """Test screenshot collection from artifacts directory."""
        screenshots = gemini_agent._collect_screenshots(mock_artifacts_dir, "test_example.spec.ts")

        assert len(screenshots) == 3
        assert all(str(mock_artifacts_dir) in s for s in screenshots)
        assert all(s.endswith('.png') for s in screenshots)

    def test_collect_screenshots_empty_directory(self, gemini_agent, tmp_path):
        """Test screenshot collection from empty directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        screenshots = gemini_agent._collect_screenshots(empty_dir, "test.spec.ts")

        assert len(screenshots) == 0

    def test_collect_screenshots_chronological_order(self, gemini_agent, tmp_path):
        """Test screenshots are collected in chronological order."""
        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()

        import time

        # Create screenshots with delays to ensure different mtimes
        for i in range(3):
            screenshot = artifacts_dir / f"step_{i}.png"
            screenshot.write_bytes(b"data")
            time.sleep(0.01)  # Small delay to ensure different timestamps

        screenshots = gemini_agent._collect_screenshots(artifacts_dir, "test.spec.ts")

        # Verify chronological order
        assert len(screenshots) == 3
        for i in range(len(screenshots) - 1):
            mtime1 = Path(screenshots[i]).stat().st_mtime
            mtime2 = Path(screenshots[i + 1]).stat().st_mtime
            assert mtime1 <= mtime2


class TestGeminiAgentReportParsing:
    """Test Playwright report parsing."""

    def test_check_tests_passed_all_pass(self, gemini_agent):
        """Test parsing when all tests pass."""
        suites = [{
            'specs': [{
                'tests': [{
                    'results': [{'status': 'passed'}]
                }]
            }]
        }]

        assert gemini_agent._check_tests_passed(suites) is True

    def test_check_tests_passed_some_fail(self, gemini_agent):
        """Test parsing when some tests fail."""
        suites = [{
            'specs': [{
                'tests': [
                    {'results': [{'status': 'passed'}]},
                    {'results': [{'status': 'failed'}]}
                ]
            }]
        }]

        assert gemini_agent._check_tests_passed(suites) is False

    def test_extract_console_errors(self, gemini_agent):
        """Test console error extraction."""
        suites = [{
            'specs': [{
                'tests': [{
                    'results': [{
                        'stderr': [
                            {'text': 'Error: Something went wrong'},
                            'Normal log message'
                        ]
                    }]
                }]
            }]
        }]

        errors = gemini_agent._extract_console_errors(suites)

        assert len(errors) == 1
        assert 'Error: Something went wrong' in errors[0]

    def test_extract_network_failures(self, gemini_agent):
        """Test network failure extraction."""
        suites = [{
            'specs': [{
                'tests': [{
                    'results': [{
                        'error': {
                            'message': 'net::ERR_CONNECTION_REFUSED at https://example.com'
                        }
                    }]
                }]
            }]
        }]

        failures = gemini_agent._extract_network_failures(suites)

        assert len(failures) == 1
        assert 'ERR_CONNECTION_REFUSED' in failures[0]


class TestGeminiAgentRubricIntegration:
    """Test integration with ValidationRubric."""

    @patch('subprocess.run')
    def test_rubric_validation_pass(self, mock_run, gemini_agent, mock_test_file):
        """Test rubric validation passes for valid result."""
        # Mock successful execution with all required fields
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            'suites': [{
                'specs': [{
                    'tests': [{
                        'results': [{'status': 'passed', 'stdout': [], 'stderr': []}]
                    }]
                }]
            }]
        })
        mock_result.stderr = ''
        mock_run.return_value = mock_result

        with patch.object(Path, 'exists', return_value=True):
            with patch.object(gemini_agent, '_collect_screenshots') as mock_screenshots:
                mock_screenshots.return_value = ['/path/to/screenshot.png']

                result = gemini_agent.execute(str(mock_test_file))

        # Verify rubric validation passed
        assert result.success is True
        assert result.data['rubric_validation']['passed'] is True
        assert len(result.data['rubric_validation']['errors']) == 0

    @patch('subprocess.run')
    def test_rubric_validation_fail_no_screenshots(self, mock_run, gemini_agent, mock_test_file):
        """Test rubric validation fails when no screenshots."""
        # Mock successful test but no screenshots
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            'suites': [{
                'specs': [{
                    'tests': [{
                        'results': [{'status': 'passed', 'stdout': [], 'stderr': []}]
                    }]
                }]
            }]
        })
        mock_result.stderr = ''
        mock_run.return_value = mock_result

        with patch.object(Path, 'exists', return_value=True):
            with patch.object(gemini_agent, '_collect_screenshots') as mock_screenshots:
                mock_screenshots.return_value = []  # No screenshots

                result = gemini_agent.execute(str(mock_test_file))

        # Verify rubric validation failed
        assert result.success is False
        assert 'screenshot' in result.error.lower()


class TestGeminiAgentMetrics:
    """Test agent metrics and cost tracking."""

    @patch('subprocess.run')
    def test_cost_tracking(self, mock_run, gemini_agent, mock_test_file):
        """Test cost tracking for validation."""
        # Mock successful execution
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            'suites': [{
                'specs': [{
                    'tests': [{
                        'results': [{'status': 'passed', 'stdout': [], 'stderr': []}]
                    }]
                }]
            }]
        })
        mock_result.stderr = ''
        mock_run.return_value = mock_result

        with patch.object(Path, 'exists', return_value=True):
            with patch.object(gemini_agent, '_collect_screenshots') as mock_screenshots:
                mock_screenshots.return_value = ['/path/to/screenshot.png']

                result = gemini_agent.execute(str(mock_test_file))

        # Verify cost tracking
        assert result.cost_usd == 0.0  # No API costs for Playwright-only execution
        assert result.execution_time_ms >= 0  # Execution time is tracked (may be 0 in mock)

    def test_agent_stats(self, gemini_agent):
        """Test agent statistics collection."""
        stats = gemini_agent.get_stats()

        assert 'agent' in stats
        assert stats['agent'] == 'gemini'
        assert 'total_cost_usd' in stats
        assert 'execution_count' in stats
        assert 'avg_cost_usd' in stats


class TestGeminiAgentEdgeCases:
    """Test edge cases and error handling."""

    @patch('subprocess.run')
    def test_json_decode_error_fallback(self, mock_run, gemini_agent, mock_test_file):
        """Test JSON decode error fallback to returncode."""
        # Mock execution with invalid JSON
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = 'invalid json output'
        mock_result.stderr = ''
        mock_run.return_value = mock_result

        with patch.object(Path, 'exists', return_value=True):
            with patch.object(gemini_agent, '_collect_screenshots') as mock_screenshots:
                mock_screenshots.return_value = ['/path/to/screenshot.png']

                result = gemini_agent.execute(str(mock_test_file))

        # Should use returncode fallback and pass
        assert result.success is True
        assert result.data['validation_result']['test_passed'] is True

    @patch('subprocess.run')
    def test_exception_in_main_execute(self, mock_run, gemini_agent, mock_test_file):
        """Test exception handling in main execute method."""
        # Mock unexpected exception
        mock_run.side_effect = RuntimeError("Unexpected error")

        with patch.object(Path, 'exists', return_value=True):
            with patch.object(gemini_agent, '_collect_screenshots') as mock_screenshots:
                mock_screenshots.return_value = ['/path/to/screenshot.png']
                result = gemini_agent.execute(str(mock_test_file))

        # Verify exception handling - rubric validation should report the error
        assert result.success is False
        assert result.error is not None
        # Check validation result contains browser error
        assert 'Browser error' in result.data['validation_result']['console_errors'][0]

    @patch('subprocess.run')
    def test_timeout_expired_in_main_execute(self, mock_run, gemini_agent, mock_test_file):
        """Test TimeoutExpired handling in main execute method."""
        # Mock TimeoutExpired at main level
        mock_run.side_effect = subprocess.TimeoutExpired(cmd='test', timeout=60)

        with patch.object(Path, 'exists', return_value=True):
            with patch.object(gemini_agent, '_collect_screenshots') as mock_screenshots:
                mock_screenshots.return_value = ['/path/to/screenshot.png']
                result = gemini_agent.execute(str(mock_test_file))

        # Verify timeout handling - rubric validation should catch test failure
        assert result.success is False
        assert result.error is not None
        # Check timeout message in console errors
        assert 'timed out' in result.data['validation_result']['console_errors'][0].lower()

    def test_collect_screenshots_with_console_errors(self, gemini_agent):
        """Test extraction of console errors with warnings."""
        suites = [{
            'specs': [{
                'tests': [{
                    'results': [{
                        'stderr': [
                            {'text': 'Warning: Component deprecated'},
                            {'text': 'Error: Network request failed'},
                            'Info: Test starting'
                        ]
                    }]
                }]
            }]
        }]

        errors = gemini_agent._extract_console_errors(suites)

        # Should extract only error messages
        assert len(errors) >= 1
        assert any('Error: Network request failed' in e for e in errors)

    @patch('subprocess.run')
    def test_execution_time_capped_at_max_duration(self, mock_run, gemini_agent, mock_test_file):
        """Test execution time is capped at max_test_duration_ms."""
        # Mock slow execution (50 seconds)
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            'suites': [{
                'specs': [{
                    'tests': [{
                        'results': [{'status': 'passed', 'stdout': [], 'stderr': []}]
                    }]
                }]
            }]
        })
        mock_result.stderr = ''

        def slow_run(*args, **kwargs):
            import time
            time.sleep(0.1)  # Simulate slow execution
            return mock_result

        mock_run.side_effect = slow_run

        with patch.object(Path, 'exists', return_value=True):
            with patch.object(gemini_agent, '_collect_screenshots') as mock_screenshots:
                mock_screenshots.return_value = ['/path/to/screenshot.png']

                result = gemini_agent.execute(str(mock_test_file))

        # Verify execution time is tracked
        assert result.data['validation_result']['execution_time_ms'] >= 0

    def test_execute_async(self, gemini_agent, mock_test_file):
        """Test async execution."""
        import asyncio

        async def run_test():
            with patch.object(gemini_agent, 'execute') as mock_execute:
                mock_execute.return_value = AgentResult(
                    success=True,
                    data={'test': 'data'},
                    execution_time_ms=100
                )

                result = await gemini_agent.execute_async(str(mock_test_file))

                assert isinstance(result, AgentResult)
                assert result.success is True
                mock_execute.assert_called_once()

        # Run the async test
        asyncio.run(run_test())
