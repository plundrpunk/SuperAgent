"""
Gemini Agent - Test Validator
Validates Playwright tests in real browser with screenshots as proof of correctness.

Two-phase validation:
1. Browser execution with Playwright (always)
2. AI-powered screenshot analysis with Gemini 2.5 Pro (optional, for critical paths)
"""
import asyncio
import time
import subprocess
import json
import os
import base64
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

from agent_system.agents.base_agent import BaseAgent, AgentResult
from agent_system.validation_rubric import ValidationRubric
from agent_system.rate_limiter import limit_gemini

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GeminiAgent(BaseAgent):
    """
    Gemini validates tests in real browser with visual proof.

    Responsibilities:
    - Launch Playwright browser via subprocess
    - Execute test file with 45s timeout
    - Capture screenshots as visual evidence
    - Parse test results and validate against rubric
    - Optionally analyze screenshots with Gemini 2.5 Pro API
    - Return deterministic pass/fail with artifacts

    Model: Gemini 2.5 Pro for AI-powered screenshot analysis
    Tools: Playwright browser automation + Google Gemini API
    """

    def __init__(self):
        """Initialize Gemini agent."""
        super().__init__('gemini')
        self.validator = ValidationRubric()
        self.default_timeout = 60  # seconds (includes browser startup time)
        self.max_test_duration_ms = 45000  # 45 seconds for test execution

        # Gemini API configuration
        self.gemini_enabled = self._check_gemini_api_available()
        self.gemini_client = None

        if self.gemini_enabled:
            try:
                from google import genai
                from google.genai import types

                api_key = self.secrets_manager.get_secret('GEMINI_API_KEY')
                if api_key:
                    self.gemini_client = genai.Client(api_key=api_key)
                    self.genai_types = types
                    logger.info("Gemini API integration enabled")
                else:
                    self.gemini_enabled = False
                    logger.info("Gemini API key not found - using Playwright validation only")
            except ImportError:
                self.gemini_enabled = False
                logger.warning("google-genai package not installed - using Playwright validation only")
            except Exception as e:
                self.gemini_enabled = False
                logger.warning(f"Failed to initialize Gemini API: {e} - using Playwright validation only")

    def _check_gemini_api_available(self) -> bool:
        """
        Check if Gemini API is available and enabled.

        Returns:
            True if Gemini API should be used
        """
        # Check config
        gemini_config = self.config.get('contracts', {}).get('gemini_api', {})
        if not gemini_config.get('enabled', False):
            return False

        # Check for API key
        api_key = self.secrets_manager.get_secret('GEMINI_API_KEY')
        return api_key is not None

    def execute(self, test_path: str, timeout: Optional[int] = None, enable_ai_analysis: bool = False) -> AgentResult:
        """
        Validate test in real browser with screenshots.

        Args:
            test_path: Path to Playwright test file
            timeout: Optional timeout in seconds (default 60s)
            enable_ai_analysis: Enable Gemini API screenshot analysis (default False)

        Returns:
            AgentResult with validation result and screenshots
        """
        start_time = time.time()
        timeout = timeout or self.default_timeout
        api_cost = 0.0

        try:
            # Validate test file exists
            if not Path(test_path).exists():
                return AgentResult(
                    success=False,
                    error=f"Test file not found: {test_path}",
                    execution_time_ms=self._track_execution(start_time)
                )

            # Prepare artifacts directory
            test_name = Path(test_path).stem
            artifacts_dir = Path('artifacts') / test_name
            artifacts_dir.mkdir(parents=True, exist_ok=True)

            # Phase 1: Execute test with Playwright
            logger.info(f"Phase 1: Executing test in browser: {test_path}")
            validation_result = self._execute_test_in_browser(test_path, timeout, artifacts_dir)

            # Phase 2: Optional AI analysis with Gemini API
            ai_analysis = None
            if enable_ai_analysis and self.gemini_enabled and validation_result.get('screenshots'):
                logger.info("Phase 2: Analyzing screenshots with Gemini API")
                try:
                    ai_analysis = self._analyze_screenshots_with_gemini(
                        validation_result.get('screenshots', []),
                        test_path
                    )
                    api_cost = ai_analysis.get('cost_usd', 0.0)
                except Exception as e:
                    logger.warning(f"Gemini API analysis failed: {e}")
                    ai_analysis = {'error': str(e), 'analysis_skipped': True}

            # Validate against rubric
            rubric_result = self.validator.validate(validation_result)

            execution_time = self._track_execution(start_time, api_cost)

            # Determine success based on rubric validation
            success = rubric_result.passed
            error = None if success else '; '.join(rubric_result.errors)

            return AgentResult(
                success=success,
                data={
                    'validation_result': validation_result,
                    'rubric_validation': {
                        'passed': rubric_result.passed,
                        'errors': rubric_result.errors,
                        'warnings': rubric_result.warnings
                    },
                    'ai_analysis': ai_analysis,
                    'test_path': test_path,
                    'screenshots': validation_result.get('screenshots', []),
                    'artifacts_dir': str(artifacts_dir),
                    'gemini_enabled': self.gemini_enabled
                },
                error=error,
                execution_time_ms=execution_time,
                cost_usd=api_cost
            )

        except subprocess.TimeoutExpired:
            return AgentResult(
                success=False,
                error=f"Browser validation timed out after {timeout}s",
                data={'status': 'timeout', 'test_path': test_path},
                execution_time_ms=self._track_execution(start_time)
            )
        except Exception as e:
            return AgentResult(
                success=False,
                error=f"Validation error: {str(e)}",
                data={'status': 'error', 'test_path': test_path},
                execution_time_ms=self._track_execution(start_time)
            )

    def _execute_test_in_browser(
        self,
        test_path: str,
        timeout: int,
        artifacts_dir: Path
    ) -> Dict[str, Any]:
        """
        Execute test in Playwright browser and collect results.

        Args:
            test_path: Path to test file
            timeout: Timeout in seconds
            artifacts_dir: Directory for artifacts

        Returns:
            Validation result dict matching VALIDATION_SCHEMA
        """
        browser_launched = False
        test_executed = False
        test_passed = False
        screenshots = []
        console_errors = []
        network_failures = []
        execution_start = time.time()

        try:
            # Get browser config from YAML
            browser_config = self.config.get('contracts', {}).get('browser', {})
            headless = browser_config.get('headless', True)

            # Run Playwright test with JSON reporter
            env = {
                **subprocess.os.environ.copy(),
                'PWTEST_SKIP_TEST_OUTPUT': '1'
            }

            # Build Playwright command
            playwright_args = [
                'npx', 'playwright', 'test',
                test_path,
                '--reporter=json',
                '--timeout', str(self.max_test_duration_ms)
            ]

            # Add headed mode if configured
            if not headless:
                playwright_args.append('--headed')

            result = subprocess.run(
                playwright_args,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env
            )

            browser_launched = True
            test_executed = True

            # Parse Playwright JSON output
            try:
                # Playwright outputs JSON to stdout when using --reporter=json
                report_data = json.loads(result.stdout) if result.stdout else {}

                # Check test results
                suites = report_data.get('suites', [])
                test_passed = self._check_tests_passed(suites)

                # Extract console errors and network failures from report
                console_errors = self._extract_console_errors(suites)
                network_failures = self._extract_network_failures(suites)

            except json.JSONDecodeError:
                # Fallback: parse text output
                test_passed = result.returncode == 0

            # Collect screenshots from artifacts directory
            screenshots = self._collect_screenshots(artifacts_dir, test_path)

            # Broadcast screenshot events for dashboard streaming
            for i, screenshot_path in enumerate(screenshots):
                self.event_emitter.emit('screenshot_captured', {
                    'test_path': test_path,
                    'screenshot_path': screenshot_path,
                    'screenshot_number': i + 1,
                    'total_screenshots': len(screenshots),
                    'timestamp': time.time()
                })

            # Calculate execution time
            execution_time_ms = int((time.time() - execution_start) * 1000)

            return {
                'browser_launched': browser_launched,
                'test_executed': test_executed,
                'test_passed': test_passed,
                'screenshots': screenshots,
                'console_errors': console_errors,
                'network_failures': network_failures,
                'execution_time_ms': min(execution_time_ms, self.max_test_duration_ms)
            }

        except subprocess.TimeoutExpired:
            # Test exceeded timeout
            execution_time_ms = int((time.time() - execution_start) * 1000)
            screenshots = self._collect_screenshots(artifacts_dir, test_path)

            return {
                'browser_launched': browser_launched,
                'test_executed': test_executed,
                'test_passed': False,
                'screenshots': screenshots,
                'console_errors': ['Test execution timed out'],
                'network_failures': [],
                'execution_time_ms': execution_time_ms
            }

        except Exception as e:
            # Browser launch or execution failed
            execution_time_ms = int((time.time() - execution_start) * 1000)

            return {
                'browser_launched': browser_launched,
                'test_executed': test_executed,
                'test_passed': False,
                'screenshots': [],
                'console_errors': [f'Browser error: {str(e)}'],
                'network_failures': [],
                'execution_time_ms': execution_time_ms
            }

    def _check_tests_passed(self, suites: List[Dict]) -> bool:
        """
        Check if all tests passed in Playwright JSON report.

        Args:
            suites: Test suites from Playwright JSON report

        Returns:
            True if all tests passed
        """
        for suite in suites:
            for spec in suite.get('specs', []):
                for test in spec.get('tests', []):
                    for result in test.get('results', []):
                        status = result.get('status', 'failed')
                        if status not in ['passed', 'skipped']:
                            return False
        return True

    def _extract_console_errors(self, suites: List[Dict]) -> List[str]:
        """
        Extract console errors from test results.

        Args:
            suites: Test suites from Playwright JSON report

        Returns:
            List of console error messages
        """
        errors = []

        for suite in suites:
            for spec in suite.get('specs', []):
                for test in spec.get('tests', []):
                    for result in test.get('results', []):
                        # Look for console errors in stdout/stderr
                        stdout = result.get('stdout', [])
                        stderr = result.get('stderr', [])

                        for log in stderr:
                            if isinstance(log, dict):
                                text = log.get('text', '')
                            else:
                                text = str(log)

                            if text and 'error' in text.lower():
                                errors.append(text[:200])  # Truncate long errors

        return errors

    def _extract_network_failures(self, suites: List[Dict]) -> List[str]:
        """
        Extract network failures from test results.

        Args:
            suites: Test suites from Playwright JSON report

        Returns:
            List of network failure messages
        """
        failures = []

        for suite in suites:
            for spec in suite.get('specs', []):
                for test in spec.get('tests', []):
                    for result in test.get('results', []):
                        error = result.get('error', {})
                        if error:
                            message = error.get('message', '')
                            if 'net::' in message or 'ERR_' in message or 'timeout' in message.lower():
                                failures.append(message[:200])

        return failures

    def _collect_screenshots(self, artifacts_dir: Path, test_path: str) -> List[str]:
        """
        Collect screenshot paths from artifacts directory.

        Args:
            artifacts_dir: Directory containing artifacts
            test_path: Test file path

        Returns:
            List of absolute screenshot paths
        """
        screenshots = []

        # Look in artifacts directory
        if artifacts_dir.exists():
            for screenshot_file in artifacts_dir.glob('**/*.png'):
                screenshots.append(str(screenshot_file.absolute()))

        # Also check Playwright's default test-results directory
        test_results_dir = Path('test-results')
        if test_results_dir.exists():
            test_name = Path(test_path).stem
            for screenshot_file in test_results_dir.glob(f'**/*{test_name}*/*.png'):
                screenshots.append(str(screenshot_file.absolute()))

        # Sort by modification time (chronological order)
        screenshots.sort(key=lambda p: Path(p).stat().st_mtime)

        return screenshots

    @limit_gemini(model='gemini-2.5-pro')
    def _analyze_screenshots_with_gemini(
        self,
        screenshot_paths: List[str],
        test_path: str
    ) -> Dict[str, Any]:
        """
        Analyze screenshots using Gemini 2.5 Pro API (rate limited).

        Args:
            screenshot_paths: List of screenshot file paths
            test_path: Path to test file for context

        Returns:
            Analysis result dict with confidence scores and findings
        """
        if not self.gemini_client:
            return {'error': 'Gemini API client not initialized'}

        try:
            # Read test file for context
            test_content = Path(test_path).read_text()[:2000]  # First 2000 chars

            # Prepare screenshots for API
            screenshot_parts = []
            for screenshot_path in screenshot_paths[:3]:  # Limit to first 3 screenshots
                try:
                    with open(screenshot_path, 'rb') as f:
                        image_data = f.read()
                        screenshot_parts.append(
                            self.genai_types.Part.from_bytes(
                                data=image_data,
                                mime_type='image/png'
                            )
                        )
                except Exception as e:
                    logger.warning(f"Failed to read screenshot {screenshot_path}: {e}")

            if not screenshot_parts:
                return {'error': 'No screenshots could be loaded'}

            # Build analysis prompt
            prompt = f"""Analyze these Playwright test screenshots for UI correctness and visual regressions.

Test File Context:
```typescript
{test_content}
```

Please analyze:
1. UI Correctness: Are all expected UI elements visible and properly rendered?
2. Visual Regressions: Any obvious visual bugs (misalignment, broken layouts, missing elements)?
3. Test Coverage: Do the screenshots show meaningful test steps?
4. Confidence: Rate your confidence in the test's correctness (0-100%)

Provide a JSON response with:
{{
  "ui_correctness": "pass|fail",
  "visual_regressions": ["issue1", "issue2"],
  "confidence_score": 85,
  "findings": "Brief summary of findings",
  "screenshot_analysis": ["analysis of each screenshot"]
}}"""

            # Create content for API
            contents = [
                self.genai_types.Content(
                    role="user",
                    parts=[self.genai_types.Part(text=prompt)] + screenshot_parts
                )
            ]

            # Configure API call
            config = self.genai_types.GenerateContentConfig(
                temperature=0.1,  # Low temperature for deterministic output
                max_output_tokens=2048
            )

            # Call Gemini API
            response = self.gemini_client.models.generate_content(
                model='gemini-2.5-pro',
                contents=contents,
                config=config
            )

            # Extract response text
            response_text = response.text if hasattr(response, 'text') else str(response)

            # Parse JSON response
            try:
                # Try to extract JSON from response
                import re
                json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_text)
                if json_match:
                    analysis_data = json.loads(json_match.group())
                else:
                    analysis_data = {
                        'findings': response_text,
                        'confidence_score': 70,
                        'ui_correctness': 'unknown'
                    }
            except json.JSONDecodeError:
                analysis_data = {
                    'findings': response_text,
                    'confidence_score': 70,
                    'ui_correctness': 'unknown'
                }

            # Calculate cost
            # Gemini 2.5 Pro: $1.25/1M input tokens, $10/1M output tokens
            # Estimated: ~5000 input tokens (screenshots + prompt), ~500 output tokens
            estimated_input_tokens = 5000
            estimated_output_tokens = 500
            cost_usd = (estimated_input_tokens * 1.25 / 1_000_000) + \
                       (estimated_output_tokens * 10.00 / 1_000_000)

            return {
                **analysis_data,
                'cost_usd': cost_usd,
                'screenshots_analyzed': len(screenshot_parts),
                'model': 'gemini-2.5-pro'
            }

        except Exception as e:
            logger.error(f"Gemini API analysis failed: {e}")
            return {
                'error': str(e),
                'cost_usd': 0.0
            }

    async def execute_async(self, test_path: str, timeout: Optional[int] = None, enable_ai_analysis: bool = False) -> AgentResult:
        """
        Async version of execute for concurrent validation.

        Args:
            test_path: Path to test file
            timeout: Optional timeout in seconds
            enable_ai_analysis: Enable Gemini API screenshot analysis

        Returns:
            AgentResult with validation result
        """
        # Run synchronous execute in thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.execute, test_path, timeout, enable_ai_analysis)
