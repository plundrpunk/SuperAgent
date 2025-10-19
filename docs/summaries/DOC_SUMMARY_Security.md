# Documentation Summary: Security

This document summarizes SuperAgent's security architecture, identified vulnerabilities, and implemented fixes.

---

## 1. Security Posture & Threat Model

-   **Overall Posture**: Assessed as **Moderate Risk**. The system has good API key management but had critical vulnerabilities related to command injection and path traversal that have now been addressed.
-   **Threat Model**: The primary threats involve malicious user input (via voice or CLI) leading to arbitrary code execution, API key exposure, or unauthorized file system access.

---

## 2. Vulnerabilities and Fixes

A security audit identified several vulnerabilities, with the most critical ones being fixed immediately.

### High-Severity Vulnerabilities (FIXED):
1.  **Path Traversal (CWE-22)**:
    -   **Vulnerability**: Agents like `Runner` and `Scribe` accepted file paths from user input without validation, allowing an attacker to read or write files anywhere on the system (e.g., `../../../etc/passwd`).
    -   **Fix**: A `sanitize_test_path` function was implemented in the main CLI to strictly validate all incoming paths, ensuring they are relative and confined to permitted project directories (`/tests`, `/artifacts`, etc.).

2.  **Command Injection (CWE-78)**:
    -   **Vulnerability**: The `Medic` agent used a `grep` command in a subprocess with an unsanitized selector, allowing an attacker to inject arbitrary shell commands (e.g., `"; rm -rf /; echo "`).
    -   **Fix**: A `_sanitize_selector` method was added to the `Medic` agent to validate that the selector string only contains safe, expected characters before being used in the shell command.

### Medium-Severity Vulnerabilities (Mitigated / Planned):
-   **Insufficient Input Validation**: The main CLI now sanitizes all free-form text commands to strip shell metacharacters.
-   **Running as Root in Docker**: The `Dockerfile` was configured to run as a non-root user (`superagent`), but this was commented out by default for development ease. The recommendation is to **uncomment this for all production deployments**.

---

## 3. Key Security Controls

### API Key Management:
-   **Secure Loading**: All API keys (Anthropic, OpenAI, Gemini) are loaded exclusively from a git-ignored `.env` file or environment variables. There are no hardcoded keys in the codebase.
-   **Zero-Downtime Rotation**: The system supports a key rotation mechanism with an overlap period. A new key can be added as a secondary, and the system will automatically fall back to it if the primary key fails, allowing for seamless key updates.
-   **Sanitized Logging**: Error messages and logs are sanitized to prevent accidental exposure of API keys.

### Test Execution Sandbox:
-   A `TestSandbox` class was implemented to provide a secure environment for executing Playwright tests.
-   **Controls**: The sandbox enforces several critical security measures:
    -   **Path Validation**: Ensures tests only access files within their designated directories.
    -   **Command Whitelist**: Only allows execution of expected commands like `npx` and `playwright`.
    -   **Resource Limits**: Sets limits on CPU time, memory usage, and the number of processes to prevent resource exhaustion attacks.
    -   **Environment Sanitization**: Removes sensitive environment variables (like API keys) from the test execution context.

### Docker Security:
-   **Hardening**: The documentation strongly recommends applying security options to the Docker configuration for production, such as dropping all Linux capabilities (`cap_drop: ALL`), making the root filesystem read-only, and enabling `seccomp` and `AppArmor` profiles.
-   **Network Isolation**: The `docker-compose.yml` file sets up a bridge network, isolating the `superagent` and `redis` containers from the host network by default.

---

## 4. Vulnerability Reporting

A security policy (`SECURITY.md`) is in place that defines a process for responsible disclosure. Security vulnerabilities should **NOT** be reported as public GitHub issues but should instead be emailed to `security@superagent-project.example.com`.
