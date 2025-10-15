"""
Runner Agent - Test Executor
Executes Playwright tests via subprocess and parses results.

Supports multiple Playwright output formats:
- Default text format
- TAP format (--reporter=tap)
- JSON format (--reporter=json)
"""
import subprocess
import time
import re
import json
from typing import Dict, Any, Optional, List, Literal
from pathlib import Path
from dataclasses import dataclass

from agent_system.agents.base_agent import BaseAgent, AgentResult


@dataclass
class TestResult:
    """Individual test result."""
    name: str
    status: Literal["passed", "failed", "skipped", "timedOut"]
    duration_ms: int
    error: Optional[str] = None
    error_location: Optional[str] = None
    stack_trace: Optional[str] = None


@dataclass
class ParsedError:
    """Categorized error information."""
    category: Literal["selector", "timeout", "assertion", "network", "javascript", "unknown"]
    message: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    stack_trace: Optional[str] = None


class RunnerAgent(BaseAgent):
    """
    Runner executes Playwright tests and extracts results.

    Responsibilities:
    - Execute tests via subprocess with timeout
    - Parse stdout/stderr for pass/fail status
    - Extract error messages and stack traces
    - Collect artifacts (screenshots, videos, traces)
    - Return structured execution result
    """

    def __init__(self):
        """Initialize Runner agent."""
        super().__init__('runner')
        self.default_timeout = 60  # seconds
        self.reporter_format = 'json'  # Default to JSON for structured output

    def execute(self, test_path: str, timeout: Optional[int] = None,
                reporter: Optional[str] = None) -> AgentResult:
        """
        Execute Playwright test.

        Args:
            test_path: Path to test file or directory
            timeout: Optional timeout in seconds (default 60s)
            reporter: Optional reporter format ('json', 'tap', 'text', or None for default)

        Returns:
            AgentResult with test execution outcome
        """
        start_time = time.time()
        timeout = timeout or self.default_timeout
        reporter = reporter or self.reporter_format

        try:
            # Determine working directory and test path
            test_path_obj = Path(test_path)

            if test_path_obj.is_dir():
                # If path is a directory, use it as cwd and run all tests
                cwd = str(test_path_obj)
                cmd = ['npx', 'playwright', 'test']
            elif test_path_obj.is_file():
                # If path is a file, use parent as cwd and pass relative path
                cwd = str(test_path_obj.parent)
                cmd = ['npx', 'playwright', 'test', test_path_obj.name]
            else:
                # Fallback: assume it's a relative path, use current dir
                cwd = None
                cmd = ['npx', 'playwright', 'test', test_path]

            # Add max-failures flag to stop after first failure (faster feedback for Medic)
            cmd.extend(['--max-failures', '1'])

            # Add reporter
            if reporter and reporter != 'text':
                cmd.extend(['--reporter', reporter])

            # Run Playwright test with proper working directory
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd
            )

            # Parse output based on format
            if reporter == 'json':
                parsed = self._parse_json_output(result.stdout, result.stderr, result.returncode)
            elif reporter == 'tap':
                parsed = self._parse_tap_output(result.stdout, result.stderr, result.returncode)
            else:
                parsed = self._parse_text_output(result.stdout, result.stderr, result.returncode)

            # Collect artifacts
            artifacts = self._collect_artifacts(test_path)

            execution_time = self._track_execution(start_time)

            return AgentResult(
                success=parsed['success'],
                data={
                    'status': parsed['status'],
                    'test_path': test_path,
                    'test_results': parsed['test_results'],
                    'passed_count': parsed['passed_count'],
                    'failed_count': parsed['failed_count'],
                    'skipped_count': parsed.get('skipped_count', 0),
                    'errors': parsed['errors'],
                    'artifacts': artifacts,
                    'console_errors': parsed.get('console_errors', []),
                    'network_failures': parsed.get('network_failures', []),
                    'stdout': result.stdout[:2000] if len(result.stdout) > 2000 else result.stdout,
                    'stderr': result.stderr[:1000] if result.stderr else None
                },
                error=parsed.get('error'),
                execution_time_ms=execution_time
            )

        except subprocess.TimeoutExpired as e:
            # Tests timed out - run diagnostics to help Medic fix the issue
            diagnostics = self._run_diagnostics(test_path, timeout)

            return AgentResult(
                success=False,
                error=f"Test execution timed out after {timeout}s. {diagnostics['summary']}",
                data={
                    'status': 'timeout',
                    'test_path': test_path,
                    'errors': diagnostics['errors'],  # Provide actionable errors for Medic
                    'diagnostics': diagnostics,
                    'passed_count': 0,
                    'failed_count': 0,
                    'test_results': []
                },
                execution_time_ms=self._track_execution(start_time)
            )
        except Exception as e:
            return AgentResult(
                success=False,
                error=f"Execution error: {str(e)}",
                data={'status': 'error', 'test_path': test_path},
                execution_time_ms=self._track_execution(start_time)
            )

    def _parse_json_output(self, stdout: str, stderr: str, returncode: int) -> Dict[str, Any]:
        """
        Parse Playwright JSON reporter output.

        Args:
            stdout: JSON output from Playwright
            stderr: Standard error
            returncode: Process return code

        Returns:
            Parsed result dict
        """
        # Check if stdout is empty or trivial
        if not stdout or len(stdout.strip()) < 10:
            # No output produced - likely configuration or environment issue
            return {
                'success': False,
                'status': 'error',
                'test_results': [],
                'passed_count': 0,
                'failed_count': 0,
                'skipped_count': 0,
                'errors': [{
                    'category': 'unknown',
                    'message': f'Playwright produced no output. Check: 1) Are servers running? 2) Is playwright.config.ts correct? 3) Run manually: npx playwright test --reporter=list. stderr: {stderr[:200] if stderr else "none"}',
                    'file_path': None,
                    'line_number': None,
                    'stack_trace': None
                }],
                'console_errors': [],
                'network_failures': [],
                'error': 'No test output produced'
            }

        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            # Fallback to text parsing if JSON parsing fails
            return self._parse_text_output(stdout, stderr, returncode)

        test_results = []
        passed_count = 0
        failed_count = 0
        skipped_count = 0
        all_errors = []

        # Parse test suites
        for suite in data.get('suites', []):
            for spec in suite.get('specs', []):
                for test in spec.get('tests', []):
                    test_name = f"{suite.get('title', '')}: {spec.get('title', '')}"

                    for result in test.get('results', []):
                        status = result.get('status', 'unknown')
                        duration_ms = result.get('duration', 0)

                        # Track counts
                        if status == 'passed':
                            passed_count += 1
                        elif status == 'failed':
                            failed_count += 1
                        elif status in ['skipped', 'interrupted']:
                            skipped_count += 1

                        # Extract error information
                        error_msg = None
                        error_location = None
                        stack_trace = None

                        if result.get('error'):
                            error = result['error']
                            error_msg = error.get('message', '')
                            stack_trace = error.get('stack', '')

                            # Extract file and line from stack
                            location_match = re.search(r'at .+? \((.+?):(\d+):\d+\)', stack_trace)
                            if location_match:
                                error_location = f"{location_match.group(1)}:{location_match.group(2)}"

                            # Categorize error
                            categorized_error = self._categorize_error(error_msg, stack_trace)
                            all_errors.append(categorized_error)

                        test_results.append(TestResult(
                            name=test_name,
                            status=status,
                            duration_ms=duration_ms,
                            error=error_msg,
                            error_location=error_location,
                            stack_trace=stack_trace
                        ))

        # Extract top-level load errors (test file syntax errors, import errors, etc.)
        for load_error in data.get('errors', []):
            error_msg = load_error.get('message', '')
            stack_trace = load_error.get('stack', '')
            location = load_error.get('location', {})

            categorized_error = self._categorize_error(error_msg, stack_trace)
            categorized_error.file_path = location.get('file')
            categorized_error.line_number = location.get('line')
            all_errors.append(categorized_error)

        # Determine overall status
        if returncode == 0 and passed_count > 0:
            status = 'pass'
            success = True
            error = None
        elif failed_count > 0:
            status = 'fail'
            success = False
            error = f"{failed_count} test(s) failed"
        elif len(all_errors) > 0:
            status = 'error'
            success = False
            error = f"{len(all_errors)} load error(s)"
        else:
            status = 'error'
            success = False
            error = "Test did not execute successfully"

        return {
            'success': success,
            'status': status,
            'test_results': [self._test_result_to_dict(tr) for tr in test_results],
            'passed_count': passed_count,
            'failed_count': failed_count,
            'skipped_count': skipped_count,
            'errors': [self._error_to_dict(e) for e in all_errors],
            'console_errors': self._extract_console_errors(stdout),
            'network_failures': self._extract_network_failures(stdout),
            'error': error
        }

    def _parse_tap_output(self, stdout: str, stderr: str, returncode: int) -> Dict[str, Any]:
        """
        Parse Playwright TAP (Test Anything Protocol) output.

        Args:
            stdout: TAP output
            stderr: Standard error
            returncode: Process return code

        Returns:
            Parsed result dict
        """
        test_results = []
        passed_count = 0
        failed_count = 0
        skipped_count = 0
        all_errors = []

        # Parse TAP format
        # Format: "ok 1 - test name" or "not ok 1 - test name"
        lines = stdout.split('\n')
        current_test = None
        error_lines = []

        for line in lines:
            # Match test result line
            ok_match = re.match(r'^(not )?ok\s+\d+\s+-\s+(.+)', line)
            if ok_match:
                # Save previous test if exists
                if current_test:
                    test_results.append(current_test)
                    if error_lines:
                        error_msg = '\n'.join(error_lines)
                        categorized_error = self._categorize_error(error_msg, error_msg)
                        all_errors.append(categorized_error)
                        error_lines = []

                # Parse new test
                is_failure = ok_match.group(1) is not None
                test_name = ok_match.group(2).strip()

                # Check for skip directive
                is_skip = '# SKIP' in line or '# skip' in line

                if is_skip:
                    skipped_count += 1
                    status = 'skipped'
                elif is_failure:
                    failed_count += 1
                    status = 'failed'
                else:
                    passed_count += 1
                    status = 'passed'

                current_test = TestResult(
                    name=test_name,
                    status=status,
                    duration_ms=0,  # TAP doesn't include duration
                )

            # Collect error details
            elif current_test and current_test.status == 'failed':
                if line.strip().startswith('#'):
                    error_lines.append(line.strip('# ').strip())

        # Save last test
        if current_test:
            test_results.append(current_test)
            if error_lines:
                error_msg = '\n'.join(error_lines)
                current_test.error = error_msg
                categorized_error = self._categorize_error(error_msg, error_msg)
                all_errors.append(categorized_error)

        # Determine overall status
        if returncode == 0 and passed_count > 0:
            status = 'pass'
            success = True
            error = None
        elif failed_count > 0:
            status = 'fail'
            success = False
            error = f"{failed_count} test(s) failed"
        else:
            status = 'error'
            success = False
            error = "Test did not execute successfully"

        return {
            'success': success,
            'status': status,
            'test_results': [self._test_result_to_dict(tr) for tr in test_results],
            'passed_count': passed_count,
            'failed_count': failed_count,
            'skipped_count': skipped_count,
            'errors': [self._error_to_dict(e) for e in all_errors],
            'console_errors': [],
            'network_failures': [],
            'error': error
        }

    def _parse_text_output(self, stdout: str, stderr: str, returncode: int) -> Dict[str, Any]:
        """
        Parse Playwright default text output.

        Args:
            stdout: Standard output
            stderr: Standard error
            returncode: Process return code

        Returns:
            Parsed result dict
        """
        test_results = []
        all_errors = []

        # Look for pass/fail summary
        # Playwright format: "1 passed (2.1s)" or "1 failed (2.1s)"
        passed_match = re.search(r'(\d+)\s+passed', stdout)
        failed_match = re.search(r'(\d+)\s+failed', stdout)
        skipped_match = re.search(r'(\d+)\s+skipped', stdout)

        passed_count = int(passed_match.group(1)) if passed_match else 0
        failed_count = int(failed_match.group(1)) if failed_match else 0
        skipped_count = int(skipped_match.group(1)) if skipped_match else 0

        # Extract individual test results from output
        # Pattern: "✓ test name" or "✗ test name"
        test_pattern = r'^\s*([✓✗×])\s+(.+?)\s+\((\d+)ms\)'
        for match in re.finditer(test_pattern, stdout, re.MULTILINE):
            symbol = match.group(1)
            test_name = match.group(2).strip()
            duration_ms = int(match.group(3))

            status = 'passed' if symbol == '✓' else 'failed'

            test_results.append(TestResult(
                name=test_name,
                status=status,
                duration_ms=duration_ms
            ))

        # Extract error messages with context
        error_blocks = self._extract_error_blocks(stdout)
        for error_block in error_blocks:
            categorized_error = self._categorize_error(error_block['message'], error_block.get('stack', ''))
            categorized_error.file_path = error_block.get('file_path')
            categorized_error.line_number = error_block.get('line_number')
            all_errors.append(categorized_error)

        # Add stderr if present
        if stderr:
            all_errors.append(ParsedError(
                category='unknown',
                message=stderr[:500]
            ))

        # Determine status
        if returncode == 0 and passed_count > 0:
            status = 'pass'
            success = True
            error = None
        elif failed_count > 0:
            status = 'fail'
            success = False
            error = f"{failed_count} test(s) failed"
        else:
            status = 'error'
            success = False
            error = "Test did not execute successfully"

        return {
            'success': success,
            'status': status,
            'test_results': [self._test_result_to_dict(tr) for tr in test_results],
            'passed_count': passed_count,
            'failed_count': failed_count,
            'skipped_count': skipped_count,
            'errors': [self._error_to_dict(e) for e in all_errors],
            'console_errors': self._extract_console_errors(stdout),
            'network_failures': self._extract_network_failures(stdout),
            'error': error
        }

    def _categorize_error(self, message: str, stack_trace: str) -> ParsedError:
        """
        Categorize error based on message content.

        Args:
            message: Error message
            stack_trace: Stack trace

        Returns:
            ParsedError with category and details
        """
        message_lower = message.lower()

        # Extract file path and line number from stack trace
        file_path = None
        line_number = None
        location_match = re.search(r'at .+? \((.+?):(\d+):\d+\)', stack_trace)
        if location_match:
            file_path = location_match.group(1)
            line_number = int(location_match.group(2))

        # Categorize based on error patterns
        if any(keyword in message_lower for keyword in ['selector', 'locator', 'element not found', 'not visible']):
            category = 'selector'
        elif any(keyword in message_lower for keyword in ['timeout', 'timed out', 'exceeded']):
            category = 'timeout'
        elif any(keyword in message_lower for keyword in ['expect', 'assertion', 'to be', 'to equal', 'to contain']):
            category = 'assertion'
        elif any(keyword in message_lower for keyword in ['network', 'fetch', 'xhr', 'request failed', 'net::']):
            category = 'network'
        elif any(keyword in message_lower for keyword in ['javascript', 'js error', 'referenceerror', 'typeerror', 'syntaxerror']):
            category = 'javascript'
        else:
            category = 'unknown'

        return ParsedError(
            category=category,
            message=message,
            file_path=file_path,
            line_number=line_number,
            stack_trace=stack_trace
        )

    def _extract_error_blocks(self, output: str) -> List[Dict[str, Any]]:
        """
        Extract error blocks with full context from text output.

        Args:
            output: Test output text

        Returns:
            List of error block dicts
        """
        error_blocks = []

        # Split output into sections by test failures
        # Pattern: Look for failure markers and collect lines until next test or end
        lines = output.split('\n')
        i = 0

        while i < len(lines):
            line = lines[i]

            # Look for error indicators
            if 'Error:' in line or 'Failed:' in line or re.match(r'^\s*\d+\)', line):
                # Start collecting error block
                error_lines = [line]
                i += 1

                # Collect subsequent lines that are part of the error
                while i < len(lines):
                    next_line = lines[i]

                    # Stop at next test or empty lines followed by test markers
                    if re.match(r'^\s*[✓✗×]', next_line) or re.match(r'^\s*\d+\s+(passed|failed)', next_line):
                        break

                    if next_line.strip():
                        error_lines.append(next_line)

                    i += 1

                error_text = '\n'.join(error_lines)

                # Extract file path and line number
                file_match = re.search(r'at .+? \((.+?):(\d+):\d+\)', error_text)
                error_block = {
                    'message': error_text,
                    'stack': error_text
                }

                if file_match:
                    error_block['file_path'] = file_match.group(1)
                    error_block['line_number'] = int(file_match.group(2))

                error_blocks.append(error_block)
            else:
                i += 1

        return error_blocks

    def _extract_console_errors(self, output: str) -> List[str]:
        """
        Extract console error messages from output.

        Args:
            output: Test output

        Returns:
            List of console error messages
        """
        console_errors = []

        # Look for console.error() output
        # Pattern: "console.error: <message>"
        error_pattern = r'console\.error[:\s]+(.+?)(?:\n|$)'
        matches = re.finditer(error_pattern, output, re.IGNORECASE)

        for match in matches:
            console_errors.append(match.group(1).strip())

        return console_errors

    def _extract_network_failures(self, output: str) -> List[Dict[str, str]]:
        """
        Extract network failure information from output.

        Args:
            output: Test output

        Returns:
            List of network failure dicts
        """
        network_failures = []

        # Look for network error patterns
        # Pattern: "net::ERR_*" or "Failed to load resource"
        network_pattern = r'(net::\w+|Failed to load resource|ECONNREFUSED|ETIMEDOUT)(?:\s+(.+?))?(?:\n|$)'
        matches = re.finditer(network_pattern, output, re.IGNORECASE)

        for match in matches:
            failure = {
                'type': match.group(1),
                'details': match.group(2).strip() if match.group(2) else None
            }
            network_failures.append(failure)

        return network_failures

    def _test_result_to_dict(self, test_result: TestResult) -> Dict[str, Any]:
        """
        Convert TestResult dataclass to dict.

        Args:
            test_result: TestResult instance

        Returns:
            Dict representation
        """
        return {
            'name': test_result.name,
            'status': test_result.status,
            'duration_ms': test_result.duration_ms,
            'error': test_result.error,
            'error_location': test_result.error_location,
            'stack_trace': test_result.stack_trace
        }

    def _error_to_dict(self, error: ParsedError) -> Dict[str, Any]:
        """
        Convert ParsedError dataclass to dict.

        Args:
            error: ParsedError instance

        Returns:
            Dict representation
        """
        return {
            'category': error.category,
            'message': error.message,
            'file_path': error.file_path,
            'line_number': error.line_number,
            'stack_trace': error.stack_trace
        }

    def _collect_artifacts(self, test_path: str) -> Dict[str, List[str]]:
        """
        Collect test artifacts (screenshots, videos, traces).

        Args:
            test_path: Test file path

        Returns:
            Dict with artifact paths
        """
        artifacts = {
            'screenshots': [],
            'videos': [],
            'traces': []
        }

        # Look in common Playwright output directories
        artifact_dirs = [
            Path('test-results'),
            Path('playwright-report'),
            Path('artifacts')
        ]

        for artifact_dir in artifact_dirs:
            if not artifact_dir.exists():
                continue

            # Find files related to this test
            test_name = Path(test_path).stem

            for file_path in artifact_dir.rglob(f'*{test_name}*'):
                if file_path.is_file():
                    file_str = str(file_path)
                    if file_path.suffix in ['.png', '.jpg', '.jpeg']:
                        artifacts['screenshots'].append(file_str)
                    elif file_path.suffix in ['.webm', '.mp4']:
                        artifacts['videos'].append(file_str)
                    elif file_path.suffix == '.zip' or 'trace' in file_str:
                        artifacts['traces'].append(file_str)

        return artifacts

    def _run_diagnostics(self, test_path: str, timeout: int) -> Dict[str, Any]:
        """
        Run diagnostics when tests timeout to identify root cause.

        Checks:
        - Are required servers running?
        - Is Playwright installed?
        - Are tests configured correctly?

        Args:
            test_path: Path to test that timed out
            timeout: Timeout value that was used

        Returns:
            Dict with diagnostic results and actionable errors
        """
        import socket

        errors = []
        issues = []

        # Check if backend server is running (port 3010)
        backend_running = self._check_port(3010)
        if not backend_running:
            issues.append("Backend server not running on port 3010")
            errors.append({
                'category': 'network',
                'message': 'Backend server (port 3010) is not responding. E2E tests require the backend to be running. Start with: cd backend && pnpm run dev',
                'file_path': None,
                'line_number': None,
                'stack_trace': None
            })

        # Check if frontend server is running (port 5175)
        frontend_running = self._check_port(5175)
        if not frontend_running:
            issues.append("Frontend server not running on port 5175")
            errors.append({
                'category': 'network',
                'message': 'Frontend server (port 5175) is not responding. E2E tests require the frontend to be running. Start with: cd frontend && pnpm run dev',
                'file_path': None,
                'line_number': None,
                'stack_trace': None
            })

        # Check if Playwright is installed
        playwright_installed = self._check_playwright_installed()
        if not playwright_installed:
            issues.append("Playwright not installed")
            errors.append({
                'category': 'unknown',
                'message': 'Playwright does not appear to be installed. Run: npx playwright install',
                'file_path': None,
                'line_number': None,
                'stack_trace': None
            })

        # If no specific issues found, provide general timeout error
        if not errors:
            errors.append({
                'category': 'timeout',
                'message': f'Tests timed out after {timeout}s with no specific diagnostic issues found. This may indicate slow tests, network latency, or test environment issues.',
                'file_path': str(test_path),
                'line_number': None,
                'stack_trace': None
            })
            issues.append(f"Tests exceeded {timeout}s timeout")

        # Build summary
        if issues:
            summary = f"Possible causes: {'; '.join(issues)}"
        else:
            summary = "No specific diagnostic issues detected"

        return {
            'summary': summary,
            'issues': issues,
            'errors': errors,
            'checks': {
                'backend_running': backend_running,
                'frontend_running': frontend_running,
                'playwright_installed': playwright_installed
            }
        }

    def _check_port(self, port: int, host: str = 'localhost') -> bool:
        """
        Check if a port is open/listening.

        Args:
            port: Port number to check
            host: Host to check (default localhost)

        Returns:
            True if port is open, False otherwise
        """
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        try:
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except:
            return False

    def _check_playwright_installed(self) -> bool:
        """
        Check if Playwright is installed.

        Returns:
            True if Playwright is available, False otherwise
        """
        try:
            result = subprocess.run(
                ['npx', 'playwright', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
