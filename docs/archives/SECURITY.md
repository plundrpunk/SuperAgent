# Security Policy

## Overview

SuperAgent is a voice-controlled multi-agent testing system that handles sensitive data including API keys, test code, and system commands. This document outlines our security practices, known security controls, and vulnerability reporting procedures.

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Security Architecture

### Threat Model

SuperAgent operates in environments where:
- AI agents execute code via subprocess calls
- User input flows through voice commands and CLI arguments
- API keys for multiple services (Anthropic, OpenAI, Gemini) are required
- File system access is necessary for test generation and execution
- Network access is required for external API calls and test execution

**Key Threats:**
1. **Command Injection**: Malicious input in voice commands or test paths
2. **API Key Exposure**: Keys logged, stored in code, or exposed in errors
3. **Path Traversal**: Unauthorized file access outside permitted directories
4. **Arbitrary Code Execution**: Unsafe subprocess calls or eval usage
5. **Resource Exhaustion**: Unbounded test execution or memory usage
6. **Privilege Escalation**: Container escape or unauthorized system access

### Security Controls

#### 1. API Key Management

**Current Implementation:**
- ✅ All API keys loaded exclusively from environment variables via SecretsManager
- ✅ No hardcoded credentials in codebase
- ✅ API keys never logged or printed to stdout/stderr
- ✅ Error messages sanitized to prevent key leakage
- ✅ `.env.example` provides template without real keys
- ✅ `.gitignore` prevents `.env` file commits
- ✅ **NEW:** Zero-downtime key rotation with overlap period
- ✅ **NEW:** Automatic fallback to secondary key on primary failure
- ✅ **NEW:** Per-key usage and failure tracking in Redis
- ✅ **NEW:** CLI commands for managing key lifecycle

**Verification:**
```bash
# Check for hardcoded keys
grep -rE "(sk-ant-|sk-proj-|AIzaSy)" agent_system/ --exclude-dir=venv
# Should return no results

# Verify .env is gitignored
git check-ignore .env
# Should output: .env

# Check secrets manager status
python agent_system/cli.py secrets status
```

**Best Practices:**
- Rotate API keys every 90 days (now automated with SecretsManager)
- Use separate keys for development/staging/production
- Monitor API usage for anomalies via `secrets stats` command
- Revoke keys immediately upon suspected compromise
- Use 24-hour overlap period during rotation (configurable)

**Key Rotation Workflow:**

1. **Start Rotation** (adds new key as secondary):
```bash
python agent_system/cli.py secrets rotate \
  --service anthropic \
  --new-key sk-ant-new-key-here
```

2. **Monitor Rotation** (check overlap period):
```bash
python agent_system/cli.py secrets status --service anthropic
```

3. **Complete Rotation** (remove old key after overlap):
```bash
# After 24 hours (or configured overlap period)
python agent_system/cli.py secrets remove-old --service anthropic
```

**Environment Variables:**
```bash
# Primary keys (active)
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-proj-...
GEMINI_API_KEY=AIzaSy...

# Secondary keys (for rotation, optional)
ANTHROPIC_API_KEY_SECONDARY=sk-ant-new-...
OPENAI_API_KEY_SECONDARY=sk-proj-new-...
GEMINI_API_KEY_SECONDARY=AIzaSy-new-...

# Rotation settings
KEY_ROTATION_ENABLED=true
KEY_ROTATION_OVERLAP_HOURS=24
```

**Security Features:**
- **Sanitized Logging**: All error messages automatically strip API keys
- **Key Anonymization**: Keys identified by last 8 chars of SHA-256 hash
- **Redis Encryption**: Rotation state stored encrypted in Redis
- **Automatic Fallback**: System switches to secondary key on primary failure
- **Usage Tracking**: Per-key usage and failure metrics for auditing
- **Observability Events**: Rotation lifecycle events emitted for monitoring

**Example: Automatic Fallback**
```python
from agent_system.secrets_manager import get_secrets_manager

secrets = get_secrets_manager()

# Get API key (automatically uses primary, falls back to secondary if needed)
api_key = secrets.get_api_key('anthropic')

# If primary fails, manually trigger fallback
secrets.fallback_to_secondary('anthropic')
```

#### 2. Input Sanitization

**Command Injection Prevention:**
- ✅ CLI uses `argparse` for structured argument parsing
- ✅ Subprocess calls use list format (not shell strings): `['npx', 'playwright', 'test', path]`
- ✅ No use of `shell=True` in subprocess calls
- ⚠️ **VULNERABILITY IDENTIFIED**: `runner.py` line 79-81 constructs command as list but could benefit from path validation
- ⚠️ **VULNERABILITY IDENTIFIED**: `medic.py` line 412-416 uses grep with unsanitized selectors

**Path Traversal Prevention:**
```python
# RECOMMENDED: Add to all file operations
def validate_path(path: str, allowed_dirs: List[str]) -> bool:
    """Validate path is within allowed directories."""
    resolved = Path(path).resolve()
    return any(resolved.is_relative_to(Path(d).resolve()) for d in allowed_dirs)
```

**Current Status:**
- ❌ No explicit path validation in `runner.py`, `medic.py`, `scribe.py`
- ❌ Test paths accepted from user input without sanitization
- ✅ Docker volumes limit write access to specific directories

#### 3. Subprocess Security

**Blocked Commands** (from `tools.yaml`):
```yaml
blocked_commands: [rm -rf, sudo, curl, wget]
```

**Issues Identified:**
1. **Incomplete Blocklist**: Only blocks specific dangerous commands, not comprehensive
2. **No Sandboxing**: Subprocess runs with full container permissions
3. **No Resource Limits**: No CPU/memory/time limits enforced programmatically

**Recommended Enhancements:**
```python
# Implement subprocess wrapper with security controls
def secure_subprocess_run(cmd: List[str], timeout: int = 60,
                         allowed_commands: Set[str] = {'npx', 'playwright'}) -> subprocess.CompletedProcess:
    """Execute subprocess with security controls."""
    if not cmd or cmd[0] not in allowed_commands:
        raise SecurityError(f"Command not allowed: {cmd[0]}")

    # Run with resource limits (Linux only)
    import resource
    def limit_resources():
        # Limit CPU time to 5 minutes
        resource.setrlimit(resource.RLIMIT_CPU, (300, 300))
        # Limit memory to 2GB
        resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))

    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        preexec_fn=limit_resources if os.name != 'nt' else None
    )
```

#### 4. File System Permissions

**Docker Volume Strategy:**
```yaml
# Read-write access (agent-controlled)
- ./tests:/app/tests
- ./artifacts:/app/tests/artifacts
- ./logs:/app/logs

# Read-only access (recommended for production)
- ./agent_system:/app/agent_system:ro
```

**Recommendations:**
1. ✅ Use Docker volumes to restrict file access
2. ❌ **MISSING**: Path validation middleware for file operations
3. ❌ **MISSING**: File type restrictions (only allow `.ts`, `.js`, `.json`, `.yaml`)
4. ✅ Artifacts stored in separate directory

#### 5. Network Security

**Container Network Isolation:**
- ✅ Redis exposed only to internal Docker network
- ✅ Application ports configurable via environment variables
- ⚠️ **CONCERN**: No TLS/SSL enforcement for Redis connections
- ⚠️ **CONCERN**: External API calls not validated/restricted

**Recommendations:**
```yaml
# docker-compose.yml enhancements
redis:
  command: >
    redis-server
    --requirepass ${REDIS_PASSWORD}
    --tls-port 6380
    --tls-cert-file /certs/redis.crt
    --tls-key-file /certs/redis.key
```

#### 6. Docker Security

**Current Configuration:**
```dockerfile
# Security concerns:
- Running as root user (lines 120-122 commented out)
- No seccomp profile
- No AppArmor profile
- Full capabilities granted
```

**CRITICAL RECOMMENDATIONS:**
```dockerfile
# Enable non-root user
RUN useradd -m -u 1000 superagent && \
    chown -R superagent:superagent /app
USER superagent

# Apply security options
services:
  superagent:
    security_opt:
      - no-new-privileges:true
      - seccomp:default
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE  # Only if needed
    read_only: true  # Make root filesystem read-only
    tmpfs:
      - /tmp:noexec,nosuid,size=100m
```

### 7. Test Execution Sandboxing

**CRITICAL MISSING FEATURE**: Isolated test execution environment

**Recommended Implementation:**
```python
# agent_system/sandbox.py
import resource
import subprocess
from typing import Dict, Any
from pathlib import Path

class TestSandbox:
    """Sandbox for isolated test execution with resource limits."""

    def __init__(self, config: Dict[str, Any]):
        self.max_cpu_seconds = config.get('max_cpu_seconds', 300)
        self.max_memory_mb = config.get('max_memory_mb', 2048)
        self.max_execution_time = config.get('max_execution_time_ms', 60000) // 1000
        self.network_isolation = config.get('network_isolation', False)
        self.allowed_dirs = config.get('allowed_dirs', ['./tests', './artifacts'])

    def validate_path(self, path: str) -> bool:
        """Validate path is within allowed directories."""
        resolved = Path(path).resolve()
        return any(
            str(resolved).startswith(str(Path(d).resolve()))
            for d in self.allowed_dirs
        )

    def execute_test(self, test_path: str, **kwargs) -> Dict[str, Any]:
        """Execute test in sandboxed environment."""
        if not self.validate_path(test_path):
            raise SecurityError(f"Path outside allowed directories: {test_path}")

        # Set resource limits (Linux only)
        def limit_resources():
            # CPU time limit
            resource.setrlimit(resource.RLIMIT_CPU, (self.max_cpu_seconds, self.max_cpu_seconds))
            # Memory limit
            max_memory_bytes = self.max_memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (max_memory_bytes, max_memory_bytes))
            # Process limit
            resource.setrlimit(resource.RLIMIT_NPROC, (100, 100))
            # File size limit (100MB)
            resource.setrlimit(resource.RLIMIT_FSIZE, (100 * 1024 * 1024, 100 * 1024 * 1024))

        cmd = ['npx', 'playwright', 'test', test_path]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.max_execution_time,
                preexec_fn=limit_resources if os.name != 'nt' else None,
                cwd=Path(__file__).parent.parent,
                env=self._get_sandboxed_env()
            )

            return {
                'success': result.returncode == 0,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'returncode': result.returncode
            }

        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': f'Test execution timeout after {self.max_execution_time}s',
                'timeout': True
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Sandbox execution error: {str(e)}'
            }

    def _get_sandboxed_env(self) -> Dict[str, str]:
        """Get environment with sensitive data removed."""
        import os
        env = os.environ.copy()

        # Keep only necessary env vars
        safe_env = {
            'PATH': env.get('PATH', ''),
            'BASE_URL': env.get('BASE_URL', 'http://localhost:3000'),
            'PLAYWRIGHT_BROWSERS_PATH': env.get('PLAYWRIGHT_BROWSERS_PATH', ''),
            'NODE_PATH': env.get('NODE_PATH', ''),
        }

        return safe_env
```

**Usage:**
```python
from agent_system.sandbox import TestSandbox

sandbox = TestSandbox({
    'max_cpu_seconds': 300,
    'max_memory_mb': 2048,
    'max_execution_time_ms': 60000,
    'network_isolation': False,
    'allowed_dirs': ['./tests', './artifacts']
})

result = sandbox.execute_test('tests/auth.spec.ts')
```

## Known Vulnerabilities

### HIGH SEVERITY

**1. Path Traversal in File Operations** (CVE-PENDING)
- **Location**: `runner.py`, `medic.py`, `scribe.py`
- **Impact**: Arbitrary file read/write outside permitted directories
- **Status**: Identified, patch in progress
- **Mitigation**: Use Docker volume restrictions until patched
- **Fix ETA**: v0.2.0

**2. Command Injection via Grep** (CVE-PENDING)
- **Location**: `medic.py:412-416`
- **Impact**: Arbitrary command execution via crafted selector names
- **Status**: Identified, patch in progress
- **Mitigation**: Sanitize all user inputs before shell commands
- **Fix ETA**: v0.2.0

### MEDIUM SEVERITY

**3. Missing Resource Limits**
- **Location**: All subprocess calls
- **Impact**: Resource exhaustion, DoS
- **Status**: Design phase for sandboxing solution
- **Mitigation**: Monitor container resource usage
- **Fix ETA**: v0.3.0

**4. Running as Root User**
- **Location**: `Dockerfile:120-122`
- **Impact**: Container escape, privilege escalation
- **Status**: Non-root user implementation commented out
- **Mitigation**: Uncomment USER directive in Dockerfile
- **Fix ETA**: v0.2.0

### LOW SEVERITY

**5. No Redis Authentication**
- **Location**: `docker-compose.yml`, `.env.example`
- **Impact**: Unauthorized access to hot state if network compromised
- **Status**: Optional authentication supported but not enforced
- **Mitigation**: Enable `REDIS_PASSWORD` in production
- **Fix ETA**: Documentation update v0.1.1

## Security Best Practices

### Deployment Checklist

Before deploying to production:

- [ ] Create `.env` file with real API keys (never commit)
- [ ] Enable Redis authentication (`REDIS_PASSWORD`)
- [ ] Run container as non-root user (uncomment in Dockerfile)
- [ ] Apply Docker security options (seccomp, AppArmor, cap_drop)
- [ ] Configure resource limits in `docker-compose.yml`
- [ ] Enable TLS for Redis connections
- [ ] Set up log aggregation and monitoring
- [ ] Configure network firewall rules
- [ ] Enable observability dashboard with authentication
- [ ] Rotate API keys from example values
- [ ] Run security audit: `docker scan superagent:latest`
- [ ] Review and restrict file system permissions
- [ ] Enable audit logging for all agent actions
- [ ] Set up automated backup for vector DB
- [ ] Configure budget alerts for API usage

### Development Best Practices

1. **Never commit API keys**
   - Use `.env` file (gitignored)
   - Validate with: `git secrets --scan`

2. **Validate all user inputs**
   - Use `argparse` for CLI arguments
   - Sanitize paths before file operations
   - Escape shell arguments

3. **Use subprocess safely**
   - Always use list format: `['cmd', 'arg1', 'arg2']`
   - Never use `shell=True`
   - Set explicit timeouts
   - Apply resource limits

4. **Minimize permissions**
   - Read-only volumes where possible
   - Drop unnecessary Linux capabilities
   - Run as non-root user

5. **Monitor and log**
   - Log all agent actions
   - Track API usage and costs
   - Alert on anomalies

## Reporting a Vulnerability

### Reporting Process

**DO NOT** create public GitHub issues for security vulnerabilities.

**Instead, please email**: security@superagent-project.example.com

Include:
1. **Description**: Clear explanation of the vulnerability
2. **Impact**: Potential damage or exploit scenarios
3. **Proof of Concept**: Steps to reproduce (if applicable)
4. **Environment**: Version, OS, deployment method
5. **Suggested Fix**: If you have a patch or recommendation

### Response Timeline

- **Acknowledgment**: Within 48 hours
- **Initial Assessment**: Within 7 days
- **Status Update**: Every 14 days
- **Fix Release**: Based on severity
  - Critical: 7-14 days
  - High: 30 days
  - Medium: 60 days
  - Low: 90 days

### Responsible Disclosure

We follow coordinated vulnerability disclosure:
1. Report received and acknowledged
2. Vulnerability confirmed and severity assessed
3. Fix developed and tested
4. Fix released to users
5. Public disclosure 30 days after fix release

### Bug Bounty Program

Status: **PLANNED** for v1.0.0

Scope will include:
- Command injection vulnerabilities
- Authentication bypass
- API key extraction
- Container escape
- Privilege escalation
- Path traversal
- Arbitrary code execution

## Security Contacts

- **Primary**: security@superagent-project.example.com
- **PGP Key**: [To be added]
- **Security Lead**: [To be assigned]

## Security Changelog

### v0.1.0 (Current)
- Initial security audit completed
- Identified HIGH severity path traversal issues
- Identified MEDIUM severity resource limit gaps
- Documented security architecture and threat model
- Created security policy and vulnerability reporting process

### Planned for v0.2.0
- Fix path traversal vulnerabilities
- Fix command injection in grep calls
- Enable non-root user by default
- Implement input sanitization middleware
- Add path validation to all file operations

### Planned for v0.3.0
- Implement full test execution sandboxing
- Add resource limits (CPU, memory, disk)
- Enable network isolation for tests
- Add seccomp and AppArmor profiles
- Implement audit logging

## References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Docker Security Best Practices](https://docs.docker.com/engine/security/)
- [CWE-78: OS Command Injection](https://cwe.mitre.org/data/definitions/78.html)
- [CWE-22: Path Traversal](https://cwe.mitre.org/data/definitions/22.html)
- [CWE-798: Use of Hard-coded Credentials](https://cwe.mitre.org/data/definitions/798.html)

## Appendix: Security Audit Tools

```bash
# Run security scan on Docker image
docker scan superagent:latest

# Check for secrets in code
pip install detect-secrets
detect-secrets scan --baseline .secrets.baseline

# Static analysis
pip install bandit
bandit -r agent_system/ -ll

# Dependency vulnerabilities
pip install safety
safety check --json

# Lint Dockerfile
docker run --rm -i hadolint/hadolint < Dockerfile
```

---

**Last Updated**: 2025-10-14
**Next Review**: 2026-01-14 (Quarterly)
