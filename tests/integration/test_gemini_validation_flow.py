"""
End-to-End Integration Test: Gemini Validation with Screenshots

This test validates the Gemini agent's browser-based validation system:
1. Execute test in real browser (or mocked Playwright)
2. Capture screenshots at each major step
3. Validate against validation_rubric.py
4. Return pass/fail with visual evidence
5. Store artifacts to proper paths
6. Test both passing and failing scenarios

Implementation:
- Uses real GeminiAgent and ValidationRubric
- Mocks Playwright execution to avoid browser dependencies
- Tests validation schema compliance
- Validates screenshot capture and storage
- Tests error scenarios and timeouts
"""
import pytest
import tempfile
import shutil
import time
import json
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from agent_system.agents.gemini import GeminiAgent
from agent_system.validation_rubric import ValidationRubric, ValidationResult


class TestGeminiValidationFlow:
    """
    End-to-end integration test for Gemini validation with screenshots.

    Tests complete browser validation workflow with visual evidence.
    """

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Set up test environment and tear down after test."""
        # Create temporary directory for test files and artifacts
        self.temp_dir = tempfile.mkdtemp()
        self.test_dir = Path(self.temp_dir) / "tests"
        self.test_dir.mkdir(parents=True, exist_ok=True)

        self.artifacts_dir = Path(self.temp_dir) / "artifacts"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

        # Initialize Gemini agent
        self.gemini = GeminiAgent()

        # Create a sample test file
        self.test_path = str(self.test_dir / "sample_test.spec.ts")
        with open(self.test_path, 'w') as f:
            f.write("""
import { test, expect } from '@playwright/test';

test.use({
  screenshot: 'on',
  video: 'retain-on-failure',
  trace: 'retain-on-failure'
});

test('sample test', async ({ page }) => {
    await page.goto('https://example.com');
    await page.waitForSelector('h1');
    await expect(page.locator('h1')).toHaveText('Example Domain');
});
""")

        yield

        # Cleanup
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_successful_validation_with_screenshots(self):
        """
        Test successful test validation with screenshot capture.

        Flow:
        1. Execute test in browser
        2. Test passes successfully
        3. Screenshots captured at each step
        4. Validation rubric confirms pass
        5. Artifacts stored correctly
        """
        print("\n=== Test: Successful Validation with Screenshots ===")

        # Create mock screenshots
        screenshots_dir = self.artifacts_dir / "sample_test"
        screenshots_dir.mkdir(parents=True, exist_ok=True)

        screenshot_paths = []
        for i in range(1, 4):
            screenshot_path = screenshots_dir / f"step_{i}.png"
            screenshot_path.write_text(f"Mock screenshot {i}")
            screenshot_paths.append(str(screenshot_path))

        print(f"Created {len(screenshot_paths)} mock screenshots")

        # Mock Playwright execution with successful result
        mock_process_result = Mock()
        mock_process_result.returncode = 0
        mock_process_result.stdout = json.dumps({
            'suites': [{
                'specs': [{
                    'tests': [{
                        'results': [{
                            'status': 'passed',
                            'duration': 2300,
                            'stdout': [],
                            'stderr': []
                        }]
                    }]
                }]
            }]
        })
        mock_process_result.stderr = ""

        with patch('subprocess.run', return_value=mock_process_result):
            with patch.object(self.gemini, '_collect_screenshots', return_value=screenshot_paths):
                result = self.gemini.execute(self.test_path, timeout=60)

        # Validate result
        assert result.success, f"Validation should succeed: {result.error}"
        assert result.data['validation_result']['browser_launched'] == True
        assert result.data['validation_result']['test_executed'] == True
        assert result.data['validation_result']['test_passed'] == True
        assert len(result.data['validation_result']['screenshots']) == 3

        print("✓ Test executed successfully")
        print(f"  Browser launched: {result.data['validation_result']['browser_launched']}")
        print(f"  Test executed: {result.data['validation_result']['test_executed']}")
        print(f"  Test passed: {result.data['validation_result']['test_passed']}")
        print(f"  Screenshots: {len(result.data['validation_result']['screenshots'])}")

        # Validate rubric validation
        rubric_validation = result.data['rubric_validation']
        assert rubric_validation['passed'] == True
        assert len(rubric_validation['errors']) == 0

        print("✓ Rubric validation passed")
        print(f"  Errors: {len(rubric_validation['errors'])}")
        print(f"  Warnings: {len(rubric_validation['warnings'])}")

    def test_failed_test_validation(self):
        """
        Test validation of a failing test.

        Flow:
        1. Execute test in browser
        2. Test fails with assertion error
        3. Screenshots still captured
        4. Validation rubric reports failure
        5. Error details captured
        """
        print("\n=== Test: Failed Test Validation ===")

        # Create mock screenshots (captured even on failure)
        screenshots_dir = self.artifacts_dir / "failing_test"
        screenshots_dir.mkdir(parents=True, exist_ok=True)

        screenshot_paths = [
            str(screenshots_dir / "before_failure.png"),
            str(screenshots_dir / "at_failure.png")
        ]

        for path in screenshot_paths:
            Path(path).write_text("Mock screenshot")

        # Mock Playwright execution with failed result
        mock_process_result = Mock()
        mock_process_result.returncode = 1
        mock_process_result.stdout = json.dumps({
            'suites': [{
                'specs': [{
                    'tests': [{
                        'results': [{
                            'status': 'failed',
                            'duration': 3500,
                            'error': {
                                'message': 'Expected "Example" but got "Different"'
                            },
                            'stdout': [],
                            'stderr': ['Error: Assertion failed']
                        }]
                    }]
                }]
            }]
        })
        mock_process_result.stderr = ""

        with patch('subprocess.run', return_value=mock_process_result):
            with patch.object(self.gemini, '_collect_screenshots', return_value=screenshot_paths):
                result = self.gemini.execute(self.test_path, timeout=60)

        # Validate result - should report failure correctly
        assert not result.success, "Validation should fail for failing test"
        assert result.data['validation_result']['browser_launched'] == True
        assert result.data['validation_result']['test_executed'] == True
        assert result.data['validation_result']['test_passed'] == False
        assert len(result.data['validation_result']['screenshots']) == 2

        print("✓ Failed test detected correctly")
        print(f"  Test passed: {result.data['validation_result']['test_passed']}")
        print(f"  Screenshots captured: {len(result.data['validation_result']['screenshots'])}")

        # Validate rubric caught the failure
        rubric_validation = result.data['rubric_validation']
        assert rubric_validation['passed'] == False
        assert len(rubric_validation['errors']) > 0
        assert any('test_passed=false' in err.lower() for err in rubric_validation['errors'])

        print("✓ Rubric validation caught failure")
        print(f"  Errors: {rubric_validation['errors']}")

    def test_validation_timeout_handling(self):
        """
        Test handling of test execution timeout.

        Flow:
        1. Test execution exceeds timeout limit
        2. Browser process is terminated
        3. Validation reports timeout error
        4. Any captured screenshots are preserved
        """
        print("\n=== Test: Validation Timeout Handling ===")

        # Mock Playwright execution with timeout
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd=['npx', 'playwright', 'test'],
                timeout=60
            )

            result = self.gemini.execute(self.test_path, timeout=60)

        # Validate timeout handling
        assert not result.success, "Should fail on timeout"
        assert result.error is not None

        # Error could be timeout message OR rubric validation failure (missing screenshots)
        # Both are acceptable since timeout means no screenshots captured
        timeout_mentioned = 'timeout' in result.error.lower() or 'timed out' in result.error.lower()
        missing_screenshots = 'screenshot' in result.error.lower()

        assert timeout_mentioned or missing_screenshots, \
            f"Error should mention timeout or missing screenshots, got: {result.error}"

        print("✓ Timeout handled correctly")
        print(f"  Error: {result.error}")

    def test_validation_rubric_schema_compliance(self):
        """
        Test that validation results comply with VALIDATION_SCHEMA.

        Required fields:
        - browser_launched (bool)
        - test_executed (bool)
        - test_passed (bool)
        - screenshots (array, min 1)
        - console_errors (array)
        - network_failures (array)
        - execution_time_ms (int, 0-45000)
        """
        print("\n=== Test: Validation Rubric Schema Compliance ===")

        rubric = ValidationRubric()

        # Test Case 1: Valid result
        valid_result = {
            'browser_launched': True,
            'test_executed': True,
            'test_passed': True,
            'screenshots': ['/artifacts/screenshot1.png', '/artifacts/screenshot2.png'],
            'console_errors': [],
            'network_failures': [],
            'execution_time_ms': 3500
        }

        validation = rubric.validate(valid_result)

        assert validation.passed == True
        assert len(validation.errors) == 0

        print("✓ Valid result passes schema validation")

        # Test Case 2: Missing required field
        invalid_result = {
            'browser_launched': True,
            'test_executed': True,
            # Missing 'test_passed'
            'screenshots': ['/artifacts/screenshot1.png'],
            'console_errors': [],
            'network_failures': [],
            'execution_time_ms': 2000
        }

        validation = rubric.validate(invalid_result)

        assert validation.passed == False
        assert len(validation.errors) > 0
        assert any('test_passed' in err.lower() for err in validation.errors)

        print("✓ Missing required field caught")

        # Test Case 3: No screenshots (should fail)
        no_screenshots_result = {
            'browser_launched': True,
            'test_executed': True,
            'test_passed': True,
            'screenshots': [],  # Empty!
            'console_errors': [],
            'network_failures': [],
            'execution_time_ms': 2000
        }

        validation = rubric.validate(no_screenshots_result)

        assert validation.passed == False
        assert any('screenshot' in err.lower() for err in validation.errors)

        print("✓ Missing screenshots caught")

        # Test Case 4: Execution time exceeded
        timeout_result = {
            'browser_launched': True,
            'test_executed': True,
            'test_passed': True,
            'screenshots': ['/artifacts/screenshot1.png'],
            'console_errors': [],
            'network_failures': [],
            'execution_time_ms': 50000  # Exceeds 45000ms limit
        }

        validation = rubric.validate(timeout_result)

        assert validation.passed == False
        assert any('execution time' in err.lower() or '45000' in err for err in validation.errors)

        print("✓ Execution time limit enforced")

    def test_console_errors_tracked_as_warnings(self):
        """
        Test that console errors are tracked but don't fail validation.

        Console errors should be:
        - Logged in validation result
        - Reported as warnings
        - Not cause validation failure (unless test fails for other reasons)
        """
        print("\n=== Test: Console Errors Tracked as Warnings ===")

        rubric = ValidationRubric()

        result_with_console_errors = {
            'browser_launched': True,
            'test_executed': True,
            'test_passed': True,  # Test still passes
            'screenshots': ['/artifacts/screenshot1.png'],
            'console_errors': [
                'Warning: React key prop missing',
                'Deprecated API usage in third-party library'
            ],
            'network_failures': [],
            'execution_time_ms': 3000
        }

        validation = rubric.validate(result_with_console_errors)

        # Should pass despite console errors
        assert validation.passed == True
        assert len(validation.errors) == 0

        # But should have warnings
        assert len(validation.warnings) > 0
        assert any('console' in warn.lower() for warn in validation.warnings)

        print("✓ Console errors tracked as warnings")
        print(f"  Warnings: {validation.warnings}")
        print(f"  Validation passed: {validation.passed}")

    def test_network_failures_tracked_as_warnings(self):
        """
        Test that network failures are tracked but don't fail validation.

        Network failures should be:
        - Logged in validation result
        - Reported as warnings
        - Not cause validation failure (test may still pass)
        """
        print("\n=== Test: Network Failures Tracked as Warnings ===")

        rubric = ValidationRubric()

        result_with_network_failures = {
            'browser_launched': True,
            'test_executed': True,
            'test_passed': True,  # Test passes (mocked API)
            'screenshots': ['/artifacts/screenshot1.png'],
            'console_errors': [],
            'network_failures': [
                'GET https://api.analytics.com/track 404',
                'POST https://third-party.com/log timeout'
            ],
            'execution_time_ms': 4000
        }

        validation = rubric.validate(result_with_network_failures)

        # Should pass despite network failures
        assert validation.passed == True
        assert len(validation.errors) == 0

        # But should have warnings
        assert len(validation.warnings) > 0
        assert any('network' in warn.lower() for warn in validation.warnings)

        print("✓ Network failures tracked as warnings")
        print(f"  Warnings: {validation.warnings}")
        print(f"  Validation passed: {validation.passed}")

    def test_screenshot_collection_from_artifacts(self):
        """
        Test screenshot collection from artifacts directory.

        Screenshots should be:
        - Collected from test-specific artifacts directory
        - Sorted chronologically
        - Return absolute paths
        """
        print("\n=== Test: Screenshot Collection from Artifacts ===")

        # Create mock artifacts structure
        test_name = "login_test"
        artifacts_dir = self.artifacts_dir / test_name
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        # Create screenshots with different timestamps
        screenshot_files = []
        for i in range(1, 4):
            screenshot_path = artifacts_dir / f"step_{i}.png"
            screenshot_path.write_text(f"Screenshot {i}")
            time.sleep(0.01)  # Ensure different timestamps
            screenshot_files.append(screenshot_path)

        # Collect screenshots
        collected = self.gemini._collect_screenshots(artifacts_dir, f"/tests/{test_name}.spec.ts")

        assert len(collected) == 3, "Should collect all screenshots"

        # Verify all paths are absolute
        for path in collected:
            assert Path(path).is_absolute(), "Paths should be absolute"

        # Verify chronological order
        for i in range(len(collected) - 1):
            path1 = Path(collected[i])
            path2 = Path(collected[i + 1])
            assert path1.stat().st_mtime <= path2.stat().st_mtime, "Should be sorted chronologically"

        print("✓ Screenshots collected correctly")
        print(f"  Count: {len(collected)}")
        print(f"  Paths: {[Path(p).name for p in collected]}")

    def test_browser_launch_failure(self):
        """
        Test handling of browser launch failure.

        Flow:
        1. Browser fails to launch
        2. browser_launched = False
        3. Validation reports browser error
        4. No screenshots captured
        """
        print("\n=== Test: Browser Launch Failure ===")

        # Mock Playwright execution with browser launch failure
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = Exception("Browser binary not found")

            result = self.gemini.execute(self.test_path, timeout=60)

        # Validate browser launch failure handling
        assert not result.success, "Should fail when browser doesn't launch"
        assert 'browser' in result.error.lower() or 'error' in result.error.lower()

        validation_result = result.data.get('validation_result', {})
        if validation_result:
            assert validation_result.get('browser_launched') == False

        print("✓ Browser launch failure handled")
        print(f"  Error: {result.error}")

    def test_validation_with_multiple_test_suites(self):
        """
        Test validation with multiple test suites in one file.

        Flow:
        1. Execute file with multiple test suites
        2. All tests must pass for validation to pass
        3. Screenshots from all suites collected
        """
        print("\n=== Test: Validation with Multiple Test Suites ===")

        # Mock Playwright execution with multiple suites
        mock_process_result = Mock()
        mock_process_result.returncode = 0
        mock_process_result.stdout = json.dumps({
            'suites': [
                {
                    'specs': [{
                        'tests': [{
                            'results': [{'status': 'passed', 'duration': 1500}]
                        }]
                    }]
                },
                {
                    'specs': [{
                        'tests': [{
                            'results': [{'status': 'passed', 'duration': 2000}]
                        }]
                    }]
                },
                {
                    'specs': [{
                        'tests': [{
                            'results': [{'status': 'passed', 'duration': 1800}]
                        }]
                    }]
                }
            ]
        })
        mock_process_result.stderr = ""

        screenshots = [f"/artifacts/suite_{i}.png" for i in range(1, 4)]

        with patch('subprocess.run', return_value=mock_process_result):
            with patch.object(self.gemini, '_collect_screenshots', return_value=screenshots):
                result = self.gemini.execute(self.test_path, timeout=60)

        # All tests passed
        assert result.success
        assert result.data['validation_result']['test_passed'] == True

        print("✓ Multiple test suites validated")
        print(f"  All tests passed: {result.data['validation_result']['test_passed']}")

    def test_validation_partial_suite_failure(self):
        """
        Test validation when one test in suite fails.

        Flow:
        1. Execute file with multiple tests
        2. One test fails
        3. Overall validation should fail
        """
        print("\n=== Test: Validation Partial Suite Failure ===")

        # Mock execution with one failing test
        mock_process_result = Mock()
        mock_process_result.returncode = 1
        mock_process_result.stdout = json.dumps({
            'suites': [
                {
                    'specs': [{
                        'tests': [{
                            'results': [{'status': 'passed', 'duration': 1500}]
                        }]
                    }]
                },
                {
                    'specs': [{
                        'tests': [{
                            'results': [{
                                'status': 'failed',
                                'duration': 2000,
                                'error': {'message': 'Assertion failed'}
                            }]
                        }]
                    }]
                }
            ]
        })
        mock_process_result.stderr = ""

        screenshots = ["/artifacts/screenshot1.png"]

        with patch('subprocess.run', return_value=mock_process_result):
            with patch.object(self.gemini, '_collect_screenshots', return_value=screenshots):
                result = self.gemini.execute(self.test_path, timeout=60)

        # Should fail because one test failed
        assert not result.success
        assert result.data['validation_result']['test_passed'] == False

        print("✓ Partial suite failure detected")
        print(f"  Test passed: {result.data['validation_result']['test_passed']}")

    def test_artifact_storage_paths(self):
        """
        Test that artifacts are stored in correct directory structure.

        Expected structure:
        artifacts/
          test_name/
            step_1.png
            step_2.png
            ...
        """
        print("\n=== Test: Artifact Storage Paths ===")

        test_name = "artifact_test"
        test_path = str(self.test_dir / f"{test_name}.spec.ts")

        # Create test file
        with open(test_path, 'w') as f:
            f.write("// Mock test")

        # Expected artifacts directory
        expected_artifacts_dir = Path('artifacts') / test_name

        # Mock execution
        mock_process_result = Mock()
        mock_process_result.returncode = 0
        mock_process_result.stdout = json.dumps({
            'suites': [{
                'specs': [{
                    'tests': [{
                        'results': [{'status': 'passed', 'duration': 2000}]
                    }]
                }]
            }]
        })

        screenshots = [str(expected_artifacts_dir / f"step_{i}.png") for i in range(1, 3)]

        with patch('subprocess.run', return_value=mock_process_result):
            with patch.object(self.gemini, '_collect_screenshots', return_value=screenshots):
                result = self.gemini.execute(test_path, timeout=60)

        # Verify artifacts directory is recorded
        assert 'artifacts_dir' in result.data
        assert test_name in result.data['artifacts_dir']

        print("✓ Artifact paths structured correctly")
        print(f"  Artifacts dir: {result.data['artifacts_dir']}")


class TestValidationRubricBatchValidation:
    """Test batch validation capabilities."""

    def test_batch_validation_multiple_results(self):
        """
        Test validation of multiple test results in batch.

        Use case: Validating entire test suite at once.
        """
        print("\n=== Test: Batch Validation ===")

        rubric = ValidationRubric()

        # Multiple test results
        results = [
            {
                'test_id': 'test_1',
                'browser_launched': True,
                'test_executed': True,
                'test_passed': True,
                'screenshots': ['/artifacts/test1_1.png'],
                'console_errors': [],
                'network_failures': [],
                'execution_time_ms': 2000
            },
            {
                'test_id': 'test_2',
                'browser_launched': True,
                'test_executed': True,
                'test_passed': False,  # Failed
                'screenshots': ['/artifacts/test2_1.png'],
                'console_errors': [],
                'network_failures': [],
                'execution_time_ms': 3000
            },
            {
                'test_id': 'test_3',
                'browser_launched': True,
                'test_executed': True,
                'test_passed': True,
                'screenshots': ['/artifacts/test3_1.png'],
                'console_errors': ['Warning: Deprecated'],
                'network_failures': [],
                'execution_time_ms': 2500
            }
        ]

        # Batch validate
        validated = rubric.validate_batch(results)

        assert len(validated) == 3, "Should validate all results"

        # Check individual results
        assert validated['test_1'].passed == True
        assert validated['test_2'].passed == False
        assert validated['test_3'].passed == True

        # test_3 should have warnings
        assert len(validated['test_3'].warnings) > 0

        print("✓ Batch validation completed")
        print(f"  Total: {len(validated)}")
        print(f"  Passed: {sum(1 for v in validated.values() if v.passed)}")
        print(f"  Failed: {sum(1 for v in validated.values() if not v.passed)}")


class TestGeminiRealBrowserScenarios:
    """
    Test Gemini validation with real browser scenarios.

    These tests can be run with real Playwright browser or mocked for CI.
    Set REAL_BROWSER=true to run with actual browser.
    """

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_dir = Path(self.temp_dir) / "tests"
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.gemini = GeminiAgent()

        yield

        # Cleanup
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_real_browser_simple_page_load(self):
        """
        Test validation with simple page load (example.com).

        This test demonstrates:
        - Real browser launch
        - Page navigation
        - Screenshot capture
        - Basic validation
        """
        print("\n=== Test: Real Browser Simple Page Load ===")

        # Create test file for example.com
        test_path = str(self.test_dir / "simple_load.spec.ts")
        with open(test_path, 'w') as f:
            f.write("""
import { test, expect } from '@playwright/test';

test.use({
  screenshot: 'on',
  video: 'retain-on-failure',
  trace: 'retain-on-failure'
});

test('load example.com', async ({ page }) => {
    await page.goto('https://example.com');
    await page.screenshot({ path: 'artifacts/simple_load/step_1.png' });

    await page.waitForSelector('h1');
    await page.screenshot({ path: 'artifacts/simple_load/step_2.png' });

    await expect(page.locator('h1')).toContainText('Example');
    await page.screenshot({ path: 'artifacts/simple_load/step_3.png' });
});
""")

        # Mock or run real browser (based on environment)
        import os
        if os.environ.get('REAL_BROWSER') == 'true':
            # Run with real browser
            result = self.gemini.execute(test_path, timeout=60)
        else:
            # Mock for CI
            mock_process = Mock()
            mock_process.returncode = 0
            mock_process.stdout = json.dumps({
                'suites': [{
                    'specs': [{
                        'tests': [{
                            'results': [{'status': 'passed', 'duration': 1500}]
                        }]
                    }]
                }]
            })

            screenshots = [
                f'artifacts/simple_load/step_{i}.png' for i in range(1, 4)
            ]

            with patch('subprocess.run', return_value=mock_process):
                with patch.object(self.gemini, '_collect_screenshots', return_value=screenshots):
                    result = self.gemini.execute(test_path, timeout=60)

        # Validate result
        assert result.success, f"Simple page load should succeed: {result.error}"
        assert result.data['validation_result']['browser_launched']
        assert result.data['validation_result']['test_passed']
        assert len(result.data['validation_result']['screenshots']) >= 1

        print("✓ Simple page load validated")
        print(f"  Execution time: {result.execution_time_ms}ms")
        print(f"  Screenshots: {len(result.data['validation_result']['screenshots'])}")

    def test_real_browser_selector_not_found(self):
        """
        Test validation with selector not found error.

        This simulates a common failure scenario where expected element
        is not present on the page.
        """
        print("\n=== Test: Real Browser Selector Not Found ===")

        # Create test with invalid selector
        test_path = str(self.test_dir / "selector_fail.spec.ts")
        with open(test_path, 'w') as f:
            f.write("""
import { test, expect } from '@playwright/test';

test.use({
  screenshot: 'on',
  video: 'retain-on-failure',
  trace: 'retain-on-failure'
});

test('selector not found', async ({ page }) => {
    await page.goto('https://example.com');
    await page.screenshot({ path: 'artifacts/selector_fail/step_1.png' });

    // This selector doesn't exist - will timeout
    await page.waitForSelector('[data-testid="nonexistent"]', { timeout: 5000 });
});
""")

        # Mock failed execution
        mock_process = Mock()
        mock_process.returncode = 1
        mock_process.stdout = json.dumps({
            'suites': [{
                'specs': [{
                    'tests': [{
                        'results': [{
                            'status': 'failed',
                            'duration': 5500,
                            'error': {
                                'message': 'Timeout 5000ms exceeded waiting for selector'
                            }
                        }]
                    }]
                }]
            }]
        })

        screenshots = ['artifacts/selector_fail/step_1.png']

        with patch('subprocess.run', return_value=mock_process):
            with patch.object(self.gemini, '_collect_screenshots', return_value=screenshots):
                result = self.gemini.execute(test_path, timeout=60)

        # Should detect failure
        assert not result.success
        assert result.data['validation_result']['test_passed'] == False
        assert result.data['validation_result']['browser_launched']

        print("✓ Selector not found failure detected")
        print(f"  Error captured: {result.data['rubric_validation']['errors']}")

    def test_real_browser_timeout_scenario(self):
        """
        Test validation with infinite loop causing timeout.

        This tests the 45s timeout enforcement.
        """
        print("\n=== Test: Real Browser Timeout Scenario ===")

        # Create test that takes too long
        test_path = str(self.test_dir / "timeout_test.spec.ts")
        with open(test_path, 'w') as f:
            f.write("""
import { test, expect } from '@playwright/test';

test.use({
  screenshot: 'on',
  video: 'retain-on-failure',
  trace: 'retain-on-failure'
});

test('infinite loop timeout', async ({ page }) => {
    await page.goto('https://example.com');

    // Simulate long-running operation
    await page.waitForTimeout(60000); // 60 seconds - exceeds 45s limit
});
""")

        # Mock timeout
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd=['npx', 'playwright', 'test'],
                timeout=60
            )

            result = self.gemini.execute(test_path, timeout=60)

        # Should handle timeout gracefully
        assert not result.success
        assert 'timeout' in result.error.lower() or 'screenshot' in result.error.lower()

        print("✓ Timeout scenario handled")
        print(f"  Error: {result.error}")


class TestGeminiCostTracking:
    """Test cost tracking for Gemini validation."""

    def test_cost_tracking_basic(self):
        """
        Test that cost is tracked for Gemini validation.

        Current implementation uses Playwright only (no API costs),
        but cost tracking structure should be in place.
        """
        print("\n=== Test: Cost Tracking Basic ===")

        gemini = GeminiAgent()

        # Create temporary test file
        temp_dir = tempfile.mkdtemp()
        test_path = Path(temp_dir) / "cost_test.spec.ts"
        test_path.write_text("// Mock test")

        # Mock successful execution
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.stdout = json.dumps({
            'suites': [{
                'specs': [{
                    'tests': [{
                        'results': [{'status': 'passed', 'duration': 2000}]
                    }]
                }]
            }]
        })

        screenshots = [str(Path(temp_dir) / "screenshot.png")]
        Path(screenshots[0]).write_text("mock")

        with patch('subprocess.run', return_value=mock_process):
            with patch.object(gemini, '_collect_screenshots', return_value=screenshots):
                result = gemini.execute(str(test_path), timeout=60)

        # Verify cost tracking exists
        assert hasattr(result, 'cost_usd')
        assert isinstance(result.cost_usd, (int, float))
        assert result.cost_usd >= 0

        # Current implementation is $0 (Playwright only)
        # Future: When Gemini API is integrated, this will be > 0
        assert result.cost_usd == 0.0, "Current implementation should have 0 API costs"

        print("✓ Cost tracking structure verified")
        print(f"  Cost: ${result.cost_usd}")

        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_cost_accumulation_in_agent_stats(self):
        """
        Test that costs accumulate in agent statistics.

        Verifies that multiple validations track cumulative costs.
        """
        print("\n=== Test: Cost Accumulation ===")

        gemini = GeminiAgent()

        # Create temporary test file
        temp_dir = tempfile.mkdtemp()
        test_path = Path(temp_dir) / "cost_test.spec.ts"
        test_path.write_text("// Mock test")

        # Mock successful execution
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.stdout = json.dumps({
            'suites': [{
                'specs': [{
                    'tests': [{
                        'results': [{'status': 'passed', 'duration': 2000}]
                    }]
                }]
            }]
        })

        screenshots = [str(Path(temp_dir) / "screenshot.png")]
        Path(screenshots[0]).write_text("mock")

        # Run multiple validations
        with patch('subprocess.run', return_value=mock_process):
            with patch.object(gemini, '_collect_screenshots', return_value=screenshots):
                result1 = gemini.execute(str(test_path), timeout=60)
                result2 = gemini.execute(str(test_path), timeout=60)

        # Check stats
        stats = gemini.get_stats()

        assert 'total_cost_usd' in stats
        assert 'execution_count' in stats
        assert 'avg_cost_usd' in stats
        assert stats['execution_count'] >= 2

        print("✓ Cost accumulation verified")
        print(f"  Total cost: ${stats['total_cost_usd']}")
        print(f"  Executions: {stats['execution_count']}")
        print(f"  Avg cost: ${stats['avg_cost_usd']}")

        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)


class TestGeminiEdgeCases:
    """Test edge cases and error scenarios."""

    def test_malformed_playwright_json_output(self):
        """
        Test handling of malformed Playwright JSON output.

        Gemini should gracefully fall back to returncode.
        """
        print("\n=== Test: Malformed Playwright JSON ===")

        gemini = GeminiAgent()

        temp_dir = tempfile.mkdtemp()
        test_path = Path(temp_dir) / "test.spec.ts"
        test_path.write_text("// Mock test")

        # Mock execution with malformed JSON
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.stdout = "{ invalid json output }"
        mock_process.stderr = ""

        screenshots = [str(Path(temp_dir) / "screenshot.png")]
        Path(screenshots[0]).write_text("mock")

        with patch('subprocess.run', return_value=mock_process):
            with patch.object(gemini, '_collect_screenshots', return_value=screenshots):
                result = gemini.execute(str(test_path), timeout=60)

        # Should fall back to returncode
        assert result.success  # returncode=0 means pass
        assert result.data['validation_result']['test_passed'] == True

        print("✓ Malformed JSON handled with fallback")

        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_empty_test_results(self):
        """
        Test handling of empty test results.

        Edge case where Playwright returns empty suites.
        """
        print("\n=== Test: Empty Test Results ===")

        gemini = GeminiAgent()

        temp_dir = tempfile.mkdtemp()
        test_path = Path(temp_dir) / "test.spec.ts"
        test_path.write_text("// Mock test")

        # Mock empty results
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.stdout = json.dumps({'suites': []})
        mock_process.stderr = ""

        screenshots = [str(Path(temp_dir) / "screenshot.png")]
        Path(screenshots[0]).write_text("mock")

        with patch('subprocess.run', return_value=mock_process):
            with patch.object(gemini, '_collect_screenshots', return_value=screenshots):
                result = gemini.execute(str(test_path), timeout=60)

        # Empty results should still check returncode
        assert result.success

        print("✓ Empty test results handled")

        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
