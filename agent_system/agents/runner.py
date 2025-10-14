"""
Runner Agent - Test Executor
Executes Playwright tests via subprocess and parses results.
"""
import subprocess
import time
import re
from typing import Dict, Any, Optional, List
from pathlib import Path

from agent_system.agents.base_agent import BaseAgent, AgentResult


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

    def execute(self, test_path: str, timeout: Optional[int] = None) -> AgentResult:
        """
        Execute Playwright test.

        Args:
            test_path: Path to test file
            timeout: Optional timeout in seconds (default 60s)

        Returns:
            AgentResult with test execution outcome
        """
        start_time = time.time()
        timeout = timeout or self.default_timeout

        try:
            # Run Playwright test
            result = subprocess.run(
                ['npx', 'playwright', 'test', test_path],
                capture_output=True,
                text=True,
                timeout=timeout
            )

            # Parse output
            parsed = self._parse_output(result.stdout, result.stderr, result.returncode)

            # Collect artifacts
            artifacts = self._collect_artifacts(test_path)

            execution_time = self._track_execution(start_time)

            return AgentResult(
                success=parsed['success'],
                data={
                    'status': parsed['status'],
                    'test_path': test_path,
                    'passed_count': parsed['passed_count'],
                    'failed_count': parsed['failed_count'],
                    'errors': parsed['errors'],
                    'artifacts': artifacts,
                    'stdout': result.stdout[:1000],  # Truncate for brevity
                    'stderr': result.stderr[:1000] if result.stderr else None
                },
                error=parsed.get('error'),
                execution_time_ms=execution_time
            )

        except subprocess.TimeoutExpired:
            return AgentResult(
                success=False,
                error=f"Test execution timed out after {timeout}s",
                data={'status': 'timeout', 'test_path': test_path},
                execution_time_ms=self._track_execution(start_time)
            )
        except Exception as e:
            return AgentResult(
                success=False,
                error=f"Execution error: {str(e)}",
                data={'status': 'error', 'test_path': test_path},
                execution_time_ms=self._track_execution(start_time)
            )

    def _parse_output(self, stdout: str, stderr: str, returncode: int) -> Dict[str, Any]:
        """
        Parse Playwright output.

        Args:
            stdout: Standard output
            stderr: Standard error
            returncode: Process return code

        Returns:
            Parsed result dict
        """
        # Look for pass/fail summary
        # Playwright format: "1 passed (2.1s)" or "1 failed (2.1s)"
        passed_match = re.search(r'(\d+)\s+passed', stdout)
        failed_match = re.search(r'(\d+)\s+failed', stdout)

        passed_count = int(passed_match.group(1)) if passed_match else 0
        failed_count = int(failed_match.group(1)) if failed_match else 0

        # Extract error messages
        errors = self._extract_errors(stdout, stderr)

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
            'passed_count': passed_count,
            'failed_count': failed_count,
            'errors': errors,
            'error': error
        }

    def _extract_errors(self, stdout: str, stderr: str) -> List[Dict[str, str]]:
        """
        Extract error messages and stack traces.

        Args:
            stdout: Standard output
            stderr: Standard error

        Returns:
            List of error dicts with message and location
        """
        errors = []

        # Look for error patterns in stdout
        # Pattern: "Error: <message>" followed by "at <location>"
        error_pattern = r'Error:\s*(.+?)(?:\n\s+at\s+(.+?))?(?:\n|$)'
        matches = re.finditer(error_pattern, stdout, re.MULTILINE)

        for match in matches:
            message = match.group(1).strip()
            location = match.group(2).strip() if match.group(2) else None

            errors.append({
                'message': message,
                'location': location
            })

        # Add stderr if present
        if stderr:
            errors.append({
                'message': stderr[:500],  # Truncate
                'location': 'stderr'
            })

        return errors

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
