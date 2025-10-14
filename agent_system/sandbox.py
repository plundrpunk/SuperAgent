"""
Test Execution Sandbox with Resource Limits and Security Controls
Provides isolated execution environment for Playwright tests.
"""
import os
import sys
import subprocess
import time
from typing import Dict, Any, List, Optional, Set
from pathlib import Path
from dataclasses import dataclass
import logging

# Resource limits only available on Unix systems
if sys.platform != 'win32':
    import resource


logger = logging.getLogger(__name__)


@dataclass
class SandboxConfig:
    """Configuration for sandbox execution."""
    max_cpu_seconds: int = 300  # 5 minutes CPU time
    max_memory_mb: int = 2048  # 2GB memory
    max_execution_time_seconds: int = 60  # 60 seconds wall clock time
    max_file_size_mb: int = 100  # 100MB max file size
    max_processes: int = 100  # Max subprocess count
    network_isolation: bool = False  # Future: enable network namespaces
    allowed_dirs: List[str] = None  # Permitted file access directories
    allowed_commands: Set[str] = None  # Permitted commands to execute

    def __post_init__(self):
        """Initialize default values."""
        if self.allowed_dirs is None:
            self.allowed_dirs = ['./tests', './artifacts', './test-results', './playwright-report']
        if self.allowed_commands is None:
            self.allowed_commands = {'npx', 'playwright', 'node'}


class SecurityError(Exception):
    """Raised when security validation fails."""
    pass


class TestSandbox:
    """
    Sandbox for isolated test execution with resource limits and security controls.

    Features:
    - Path validation (prevent directory traversal)
    - Resource limits (CPU, memory, processes, file size)
    - Command whitelist (only allow specific commands)
    - Environment sanitization (remove sensitive env vars)
    - Timeout enforcement
    - Detailed execution metrics

    Usage:
        sandbox = TestSandbox()
        result = sandbox.execute_test('tests/auth.spec.ts')

        if result['success']:
            print(f"Test passed: {result['stdout']}")
        else:
            print(f"Test failed: {result['error']}")
    """

    def __init__(self, config: Optional[SandboxConfig] = None):
        """
        Initialize sandbox with security configuration.

        Args:
            config: Optional SandboxConfig (uses defaults if not provided)
        """
        self.config = config or SandboxConfig()
        self.project_root = Path(__file__).parent.parent
        logger.info(f"Sandbox initialized with config: {self.config}")

    def validate_path(self, path: str) -> bool:
        """
        Validate that path is within allowed directories.

        Args:
            path: File path to validate

        Returns:
            True if path is safe, False otherwise

        Security: Prevents directory traversal attacks
        """
        try:
            # Resolve to absolute path (handles .. and symlinks)
            resolved = Path(path).resolve()

            # Check if path is within any allowed directory
            for allowed_dir in self.config.allowed_dirs:
                allowed_path = (self.project_root / allowed_dir).resolve()
                try:
                    resolved.relative_to(allowed_path)
                    logger.debug(f"Path validated: {path} -> {resolved}")
                    return True
                except ValueError:
                    continue

            logger.warning(f"Path validation failed: {path} not in allowed dirs: {self.config.allowed_dirs}")
            return False

        except Exception as e:
            logger.error(f"Path validation error: {e}")
            return False

    def sanitize_command(self, cmd: List[str]) -> List[str]:
        """
        Validate and sanitize command arguments.

        Args:
            cmd: Command as list [executable, arg1, arg2, ...]

        Returns:
            Sanitized command list

        Raises:
            SecurityError: If command is not allowed

        Security: Prevents command injection
        """
        if not cmd or not isinstance(cmd, list):
            raise SecurityError("Command must be a non-empty list")

        executable = cmd[0]

        # Check if command is in whitelist
        if executable not in self.config.allowed_commands:
            raise SecurityError(
                f"Command not allowed: {executable}. "
                f"Allowed commands: {self.config.allowed_commands}"
            )

        # Validate all arguments are strings
        if not all(isinstance(arg, str) for arg in cmd):
            raise SecurityError("All command arguments must be strings")

        # Check for shell injection patterns
        dangerous_patterns = [';', '&&', '||', '|', '`', '$', '>', '<', '\n', '\r']
        for arg in cmd:
            if any(pattern in arg for pattern in dangerous_patterns):
                logger.warning(f"Potentially dangerous pattern in argument: {arg}")

        return cmd

    def execute_test(
        self,
        test_path: str,
        reporter: str = 'json',
        timeout: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute Playwright test in sandboxed environment with resource limits.

        Args:
            test_path: Path to test file
            reporter: Playwright reporter format ('json', 'tap', 'text')
            timeout: Optional timeout override (seconds)
            **kwargs: Additional arguments

        Returns:
            Dict with:
                - success: bool (True if test passed)
                - stdout: str (standard output)
                - stderr: str (standard error)
                - returncode: int (process exit code)
                - execution_time_ms: int (wall clock time)
                - error: str (error message if failed)
                - timeout: bool (True if timed out)
                - resource_usage: dict (CPU, memory stats if available)

        Raises:
            SecurityError: If path validation or command validation fails
        """
        start_time = time.time()

        # Security: Validate path
        if not self.validate_path(test_path):
            raise SecurityError(
                f"Path outside allowed directories: {test_path}. "
                f"Allowed: {self.config.allowed_dirs}"
            )

        # Build command
        cmd = ['npx', 'playwright', 'test', test_path]
        if reporter:
            cmd.extend(['--reporter', reporter])

        # Security: Sanitize command
        try:
            cmd = self.sanitize_command(cmd)
        except SecurityError as e:
            return {
                'success': False,
                'error': str(e),
                'execution_time_ms': int((time.time() - start_time) * 1000),
                'security_violation': True
            }

        # Use config timeout or override
        execution_timeout = timeout or self.config.max_execution_time_seconds

        logger.info(f"Executing test in sandbox: {test_path} (timeout: {execution_timeout}s)")

        try:
            # Execute with resource limits
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=execution_timeout,
                preexec_fn=self._set_resource_limits if sys.platform != 'win32' else None,
                cwd=self.project_root,
                env=self._get_sandboxed_env()
            )

            execution_time_ms = int((time.time() - start_time) * 1000)

            return {
                'success': result.returncode == 0,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'returncode': result.returncode,
                'execution_time_ms': execution_time_ms,
                'test_path': test_path,
                'command': ' '.join(cmd),
                'timeout': False
            }

        except subprocess.TimeoutExpired as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            logger.warning(f"Test execution timeout: {test_path} after {execution_timeout}s")

            return {
                'success': False,
                'error': f'Test execution timeout after {execution_timeout}s',
                'stdout': e.stdout.decode() if e.stdout else '',
                'stderr': e.stderr.decode() if e.stderr else '',
                'execution_time_ms': execution_time_ms,
                'test_path': test_path,
                'timeout': True,
                'timeout_seconds': execution_timeout
            }

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Sandbox execution error: {e}")

            return {
                'success': False,
                'error': f'Sandbox execution error: {str(e)}',
                'execution_time_ms': execution_time_ms,
                'test_path': test_path,
                'exception_type': type(e).__name__
            }

    def _set_resource_limits(self):
        """
        Set resource limits for subprocess (Unix only).
        Called via preexec_fn in subprocess.run.

        Security: Prevents resource exhaustion attacks
        """
        if sys.platform == 'win32':
            return  # Resource limits not supported on Windows

        try:
            # CPU time limit (seconds of CPU time)
            resource.setrlimit(
                resource.RLIMIT_CPU,
                (self.config.max_cpu_seconds, self.config.max_cpu_seconds)
            )

            # Memory limit (address space)
            max_memory_bytes = self.config.max_memory_mb * 1024 * 1024
            resource.setrlimit(
                resource.RLIMIT_AS,
                (max_memory_bytes, max_memory_bytes)
            )

            # Process limit
            resource.setrlimit(
                resource.RLIMIT_NPROC,
                (self.config.max_processes, self.config.max_processes)
            )

            # File size limit
            max_file_bytes = self.config.max_file_size_mb * 1024 * 1024
            resource.setrlimit(
                resource.RLIMIT_FSIZE,
                (max_file_bytes, max_file_bytes)
            )

            logger.debug(
                f"Resource limits set: CPU={self.config.max_cpu_seconds}s, "
                f"Memory={self.config.max_memory_mb}MB, "
                f"Processes={self.config.max_processes}, "
                f"FileSize={self.config.max_file_size_mb}MB"
            )

        except Exception as e:
            logger.error(f"Failed to set resource limits: {e}")
            # Don't raise - continue execution without limits rather than failing

    def _get_sandboxed_env(self) -> Dict[str, str]:
        """
        Get sanitized environment variables for subprocess.

        Security:
        - Removes API keys and sensitive data
        - Keeps only necessary variables for test execution
        - Prevents credential leakage to test processes

        Returns:
            Sanitized environment dict
        """
        # Start with minimal safe environment
        safe_env = {
            'PATH': os.getenv('PATH', ''),
            'HOME': os.getenv('HOME', ''),
            'USER': os.getenv('USER', 'superagent'),
            'LANG': os.getenv('LANG', 'en_US.UTF-8'),
        }

        # Add Playwright-specific variables
        playwright_vars = [
            'BASE_URL',
            'PLAYWRIGHT_BROWSERS_PATH',
            'PLAYWRIGHT_TIMEOUT',
            'PLAYWRIGHT_HEADLESS',
            'PLAYWRIGHT_SCREENSHOT',
            'PLAYWRIGHT_VIDEO',
            'PLAYWRIGHT_TRACE',
        ]

        for var in playwright_vars:
            value = os.getenv(var)
            if value:
                safe_env[var] = value

        # Add Node.js variables if needed
        node_vars = ['NODE_PATH', 'NODE_OPTIONS']
        for var in node_vars:
            value = os.getenv(var)
            if value:
                safe_env[var] = value

        # IMPORTANT: Do NOT include API keys
        # Tests should not have access to:
        # - ANTHROPIC_API_KEY
        # - OPENAI_API_KEY
        # - GEMINI_API_KEY
        # - REDIS_PASSWORD
        # - Any *_SECRET or *_TOKEN variables

        logger.debug(f"Sandboxed environment created with {len(safe_env)} variables")

        return safe_env

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get sandbox configuration and capabilities.

        Returns:
            Dict with sandbox metrics and limits
        """
        return {
            'config': {
                'max_cpu_seconds': self.config.max_cpu_seconds,
                'max_memory_mb': self.config.max_memory_mb,
                'max_execution_time_seconds': self.config.max_execution_time_seconds,
                'max_file_size_mb': self.config.max_file_size_mb,
                'max_processes': self.config.max_processes,
                'network_isolation': self.config.network_isolation,
                'allowed_dirs': self.config.allowed_dirs,
                'allowed_commands': list(self.config.allowed_commands),
            },
            'capabilities': {
                'resource_limits_supported': sys.platform != 'win32',
                'platform': sys.platform,
                'project_root': str(self.project_root),
            }
        }


# CLI for testing
if __name__ == '__main__':
    import sys
    import json

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Usage: python sandbox.py <test_path>")
        print("\nExample:")
        print("  python sandbox.py tests/auth.spec.ts")
        sys.exit(1)

    test_path = sys.argv[1]

    # Create sandbox with default config
    sandbox = TestSandbox()

    # Display sandbox configuration
    print("\nSandbox Configuration:")
    print(json.dumps(sandbox.get_metrics(), indent=2))

    # Execute test
    print(f"\nExecuting test: {test_path}")
    print("=" * 60)

    result = sandbox.execute_test(test_path)

    # Display results
    print("\nTest Results:")
    print(json.dumps({
        'success': result['success'],
        'execution_time_ms': result['execution_time_ms'],
        'returncode': result.get('returncode'),
        'timeout': result.get('timeout', False),
        'error': result.get('error'),
    }, indent=2))

    if result.get('stdout'):
        print("\nStdout:")
        print(result['stdout'][:1000])  # Truncate for readability

    if result.get('stderr'):
        print("\nStderr:")
        print(result['stderr'][:1000])

    sys.exit(0 if result['success'] else 1)
