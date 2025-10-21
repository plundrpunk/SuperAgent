"""
Medic Agent - Bug Fixer
Diagnoses and fixes test failures with strict regression safety.

HIPPOCRATIC OATH:
- First, do no harm (max_new_failures: 0)
- Apply minimal surgical fixes only
- Always run regression tests before/after
- Escalate to HITL if uncertain
"""
import json
import os
import subprocess
import time
import difflib
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from datetime import datetime

from anthropic import Anthropic
from dotenv import load_dotenv

from agent_system.agents.base_agent import BaseAgent, AgentResult
from agent_system.state.redis_client import RedisClient
from agent_system.hitl.queue import HITLQueue
from agent_system.rate_limiter import limit_anthropic


class MedicAgent(BaseAgent):
    """
    Medic diagnoses and fixes test failures.

    Model: Claude Sonnet 4.5
    Tools: read, edit, bash, grep

    Responsibilities:
    - Capture baseline test results before fixing
    - Diagnose root cause of test failure
    - Apply minimal surgical fixes using AI assistance
    - Run regression suite after fix
    - Enforce max_new_failures: 0 (strict)
    - Generate artifacts: fix.diff, regression_report.json
    - Escalate to HITL on repeated failures or unclear issues
    """

    # Regression test suite (from medic.yaml)
    REGRESSION_TESTS = [
        "tests/auth.spec.ts",
        "tests/core_nav.spec.ts"
    ]

    # Cost constants (Sonnet 4.5)
    COST_PER_1K_INPUT_TOKENS = 0.003  # $3 per 1M input tokens
    COST_PER_1K_OUTPUT_TOKENS = 0.015  # $15 per 1M output tokens

    MAX_RETRIES = 3
    DEFAULT_TIMEOUT = 120  # seconds for test execution
    CONFIDENCE_THRESHOLD = 0.7  # Minimum AI confidence to proceed (0-1)

    def __init__(
        self,
        redis_client: Optional[RedisClient] = None,
        hitl_queue: Optional[HITLQueue] = None,
        disable_hitl_escalation: bool = False  # For autonomous overnight builds
    ):
        """
        Initialize Medic agent.

        Args:
            redis_client: Optional Redis client for fix attempt tracking
            hitl_queue: Optional HITL queue for escalations
        """
        super().__init__('medic')

        # Load environment variables
        load_dotenv()

        # Initialize Anthropic client with secrets manager
        api_key = self.secrets_manager.get_api_key('anthropic')
        self.client = Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-20250514"  # Sonnet 4.5

        # Initialize state management
        self.redis = redis_client or RedisClient()
        self.hitl = hitl_queue or HITLQueue(redis_client=self.redis)
        self.disable_hitl_escalation = disable_hitl_escalation

    def execute(
        self,
        test_path: str,
        error_message: str,
        task_id: Optional[str] = None,
        feature: Optional[str] = None
    ) -> AgentResult:
        """
        Fix a failing test with regression safety and HITL escalation.

        Args:
            test_path: Path to the failing test file
            error_message: Error message from test execution
            task_id: Optional task ID for tracking
            feature: Optional feature name for better context

        Returns:
            AgentResult with fix status and artifacts
        """
        start_time = time.time()
        api_cost = 0.0

        # Generate task_id if not provided
        if not task_id:
            task_id = f"medic_{int(time.time())}_{Path(test_path).stem}"

        try:
            # Step 0: Track fix attempts and check for escalation
            print(f"[Medic] Tracking fix attempts for task {task_id}...")
            attempts = self._increment_fix_attempts(task_id, test_path)
            print(f"[Medic] Attempt #{attempts} for {test_path}")

            # Check if we've exceeded max retries
            if attempts > self.MAX_RETRIES:
                if self.disable_hitl_escalation:
                    # For autonomous builds: just fail gracefully without escalation
                    print(f"[Medic] Max retries ({self.MAX_RETRIES}) exceeded. Marking for review (HITL disabled).")
                    return AgentResult(
                        success=False,
                        error=f"Max fix attempts ({self.MAX_RETRIES}) exceeded. Test needs manual review.",
                        data={
                            'action': 'max_retries_exceeded',
                            'test_path': test_path,
                            'attempts': attempts,
                            'error_message': error_message,
                            'hitl_disabled': True
                        }
                    )
                else:
                    # Normal operation: escalate to HITL
                    print(f"[Medic] Max retries ({self.MAX_RETRIES}) exceeded. Escalating to HITL.")
                    escalation_result = self._escalate_to_hitl(
                        task_id=task_id,
                        test_path=test_path,
                        error_message=error_message,
                        feature=feature,
                        attempts=attempts,
                        reason="max_retries_exceeded",
                        artifacts={},
                        api_cost=api_cost
                    )
                    return escalation_result
            # Step 1: Capture baseline (pre-fix regression test results)
            print(f"[Medic] Capturing baseline regression tests...")
            baseline = self._run_regression_tests()

            if not baseline['success']:
                return AgentResult(
                    success=False,
                    error="Failed to capture baseline regression tests",
                    data={'baseline': baseline},
                    execution_time_ms=self._track_execution(start_time),
                    cost_usd=api_cost
                )

            # Step 2: Read failed test and analyze
            print(f"[Medic] Reading failed test: {test_path}")
            test_content = self._read_file(test_path)

            if not test_content:
                return AgentResult(
                    success=False,
                    error=f"Could not read test file: {test_path}",
                    execution_time_ms=self._track_execution(start_time),
                    cost_usd=api_cost
                )

            # Step 3: Search for related patterns (use grep for context)
            print(f"[Medic] Searching for related patterns...")
            context = self._gather_context(test_path, error_message)

            # Step 4: Generate fix using Claude Sonnet 4.5
            print(f"[Medic] Generating minimal surgical fix with AI...")
            fix_result = self._generate_fix(
                test_path=test_path,
                test_content=test_content,
                error_message=error_message,
                context=context
            )

            if not fix_result['success']:
                return AgentResult(
                    success=False,
                    error=fix_result['error'],
                    execution_time_ms=self._track_execution(start_time),
                    cost_usd=fix_result.get('cost_usd', 0.0)
                )

            api_cost += fix_result['cost_usd']
            proposed_fix = fix_result['fixed_content']
            diagnosis = fix_result['diagnosis']
            confidence = fix_result.get('confidence', 0.0)

            # Check if AI confidence is too low
            if confidence < self.CONFIDENCE_THRESHOLD:
                if self.disable_hitl_escalation:
                    # For autonomous builds: just log and continue with fix anyway
                    print(f"[Medic] Low AI confidence ({confidence:.2f}) but HITL disabled - applying fix anyway")
                else:
                    # Normal operation: escalate to HITL
                    print(f"[Medic] Low AI confidence ({confidence:.2f}). Escalating to HITL.")
                    escalation_result = self._escalate_to_hitl(
                        task_id=task_id,
                        test_path=test_path,
                        error_message=error_message,
                        feature=feature,
                        attempts=attempts,
                        reason="low_confidence",
                        artifacts={
                            'diagnosis': diagnosis,
                            'confidence': confidence,
                            'proposed_fix': proposed_fix[:500]  # Truncate for storage
                        },
                        api_cost=api_cost
                    )
                    return escalation_result

            # Step 5: Apply fix and generate diff
            print(f"[Medic] Applying fix to {test_path}...")
            original_content = test_content
            diff = self._generate_diff(original_content, proposed_fix, test_path)

            self._write_file(test_path, proposed_fix)

            # Step 6: Run regression tests (post-fix)
            print(f"[Medic] Running regression tests after fix...")
            after_fix = self._run_regression_tests()

            # Step 7: Compare results and enforce max_new_failures: 0
            print(f"[Medic] Comparing baseline vs after-fix results...")
            comparison = self._compare_results(baseline, after_fix)

            # Step 8: Generate artifacts
            artifacts = self._generate_artifacts(
                diff=diff,
                baseline=baseline,
                after_fix=after_fix,
                comparison=comparison,
                diagnosis=diagnosis,
                test_path=test_path
            )

            # Step 9: Enforce Hippocratic Oath
            if comparison['new_failures'] > 0:
                # VIOLATION: New failures introduced
                print(f"[Medic] REGRESSION DETECTED: {comparison['new_failures']} new failures")

                # Rollback fix
                self._write_file(test_path, original_content)

                # Escalate to HITL with full context
                escalation_result = self._escalate_to_hitl(
                    task_id=task_id,
                    test_path=test_path,
                    error_message=error_message,
                    feature=feature,
                    attempts=attempts,
                    reason="regression_detected",
                    artifacts={
                        'diagnosis': diagnosis,
                        'confidence': confidence,
                        'diff': diff,
                        'baseline': baseline,
                        'after_fix': after_fix,
                        'comparison': comparison,
                        'new_failures': comparison['new_failures']
                    },
                    api_cost=api_cost,
                    severity="high"  # Regressions are high severity
                )

                # Add rollback info
                escalation_result.data['fix_rolled_back'] = True

                return escalation_result

            # Success: Fix applied without breaking regression tests
            print(f"[Medic] Fix successful! No new failures detected.")

            return AgentResult(
                success=True,
                data={
                    'status': 'fix_applied',
                    'test_path': test_path,
                    'diagnosis': diagnosis,
                    'baseline': baseline,
                    'after_fix': after_fix,
                    'comparison': comparison,
                    'artifacts': artifacts
                },
                metadata={
                    'new_failures': comparison['new_failures'],
                    'fix_lines_changed': diff.count('\n')
                },
                execution_time_ms=self._track_execution(start_time),
                cost_usd=api_cost
            )

        except Exception as e:
            return AgentResult(
                success=False,
                error=f"Medic execution error: {str(e)}",
                execution_time_ms=self._track_execution(start_time),
                cost_usd=api_cost
            )

    def _run_regression_tests(self) -> Dict[str, Any]:
        """
        Run regression test suite.

        Returns:
            Dict with test results
        """
        try:
            # Run Playwright tests for regression suite
            result = subprocess.run(
                ['npx', 'playwright', 'test'] + self.REGRESSION_TESTS,
                capture_output=True,
                text=True,
                timeout=self.DEFAULT_TIMEOUT,
                cwd=Path(__file__).parent.parent.parent  # SuperAgent root
            )

            # Parse results
            import re
            passed_match = re.search(r'(\d+)\s+passed', result.stdout)
            failed_match = re.search(r'(\d+)\s+failed', result.stdout)

            passed = int(passed_match.group(1)) if passed_match else 0
            failed = int(failed_match.group(1)) if failed_match else 0

            # Extract error details if any failures
            errors = []
            if failed > 0:
                # Try to extract error messages
                error_pattern = r'Error:\s*(.+?)(?:\n|$)'
                error_matches = re.finditer(error_pattern, result.stdout, re.MULTILINE)
                errors = [match.group(1).strip() for match in error_matches]

            return {
                'success': True,
                'passed': passed,
                'failed': failed,
                'total': passed + failed,
                'errors': errors,
                'stdout': result.stdout[:2000],  # Truncate for storage
                'return_code': result.returncode
            }

        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': f"Regression tests timed out after {self.DEFAULT_TIMEOUT}s"
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Failed to run regression tests: {str(e)}"
            }

    def _read_file(self, file_path: str) -> Optional[str]:
        """
        Read file contents.

        Args:
            file_path: Path to file

        Returns:
            File contents or None on error
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"[Medic] Error reading file {file_path}: {e}")
            return None

    def _write_file(self, file_path: str, content: str) -> bool:
        """
        Write file contents.

        Args:
            file_path: Path to file
            content: Content to write

        Returns:
            True if successful
        """
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except Exception as e:
            print(f"[Medic] Error writing file {file_path}: {e}")
            return False

    def _sanitize_selector(self, selector: str) -> str:
        """
        Sanitize selector to prevent command injection.

        Args:
            selector: Raw selector string

        Returns:
            Sanitized selector string

        Raises:
            ValueError: If selector contains invalid characters
        """
        # Only allow alphanumeric, dash, underscore, and colon
        import re
        if not re.match(r'^[a-zA-Z0-9_:-]+$', selector):
            raise ValueError(f"Invalid selector format: {selector}")
        return selector

    def _gather_context(self, test_path: str, error_message: str) -> Dict[str, Any]:
        """
        Gather additional context using grep.

        Args:
            test_path: Test file path
            error_message: Error message to search for

        Returns:
            Dict with context information
        """
        context = {
            'related_tests': [],
            'selector_usage': []
        }

        try:
            # Extract selector from error if present
            import re
            selector_match = re.search(r'data-testid[="]([^"\']+)', error_message)

            if selector_match:
                raw_selector = selector_match.group(1)

                # SECURITY: Sanitize selector to prevent command injection
                try:
                    selector = self._sanitize_selector(raw_selector)
                except ValueError as e:
                    print(f"[Medic] Skipping context gathering - invalid selector: {e}")
                    return context

                # Search for selector usage in other tests
                result = subprocess.run(
                    ['grep', '-r', f'data-testid="{selector}"', 'tests/'],
                    capture_output=True,
                    text=True,
                    cwd=Path(__file__).parent.parent.parent
                )

                if result.returncode == 0:
                    context['selector_usage'] = result.stdout.split('\n')[:5]  # Limit to 5

        except Exception as e:
            print(f"[Medic] Error gathering context: {e}")

        return context

    @limit_anthropic(model='claude-sonnet-4-20250514')
    def _generate_fix(
        self,
        test_path: str,
        test_content: str,
        error_message: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate fix using Claude Sonnet 4.5.

        Args:
            test_path: Test file path
            test_content: Current test content
            error_message: Error message
            context: Additional context

        Returns:
            Dict with fixed_content, diagnosis, success, cost_usd
        """
        try:
            # Construct prompt following Medic's philosophy
            prompt = self._build_fix_prompt(
                test_path=test_path,
                test_content=test_content,
                error_message=error_message,
                context=context
            )

            # Call Anthropic API (rate limited)
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            # Calculate cost
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            cost_usd = (
                (input_tokens / 1000) * self.COST_PER_1K_INPUT_TOKENS +
                (output_tokens / 1000) * self.COST_PER_1K_OUTPUT_TOKENS
            )

            # Parse response
            response_text = response.content[0].text

            # Extract fixed code (between ```typescript and ```)
            import re
            code_match = re.search(
                r'```(?:typescript|ts)?\n(.*?)```',
                response_text,
                re.DOTALL
            )

            if not code_match:
                return {
                    'success': False,
                    'error': "Could not extract fixed code from AI response",
                    'cost_usd': cost_usd
                }

            fixed_content = code_match.group(1).strip()

            # Extract diagnosis (look for "DIAGNOSIS:" or similar)
            diagnosis_match = re.search(
                r'(?:DIAGNOSIS|ROOT CAUSE):\s*(.+?)(?:\n\n|FIX:|CONFIDENCE:)',
                response_text,
                re.IGNORECASE | re.DOTALL
            )

            diagnosis = (
                diagnosis_match.group(1).strip()
                if diagnosis_match
                else "AI-generated fix applied"
            )

            # Extract confidence score (0.0-1.0)
            confidence_match = re.search(
                r'CONFIDENCE:\s*(\d+(?:\.\d+)?)',
                response_text,
                re.IGNORECASE
            )

            confidence = 0.8  # Default confidence
            if confidence_match:
                try:
                    confidence = float(confidence_match.group(1))
                    # Normalize if given as percentage
                    if confidence > 1.0:
                        confidence = confidence / 100
                except ValueError:
                    pass

            return {
                'success': True,
                'fixed_content': fixed_content,
                'diagnosis': diagnosis,
                'confidence': confidence,
                'cost_usd': cost_usd,
                'response_text': response_text[:1000]  # Truncate for logging
            }

        except Exception as e:
            return {
                'success': False,
                'error': f"AI fix generation failed: {str(e)}",
                'cost_usd': 0.0
            }

    def _build_fix_prompt(
        self,
        test_path: str,
        test_content: str,
        error_message: str,
        context: Dict[str, Any]
    ) -> str:
        """
        Build prompt for AI fix generation.

        Args:
            test_path: Test file path
            test_content: Current test content
            error_message: Error message
            context: Additional context

        Returns:
            Prompt string
        """
        # Load VisionFlow context if available
        visionflow_context = ""
        try:
            from pathlib import Path
            project_root = Path(__file__).parent.parent.parent
            context_path = project_root / "visionflow_context.md"
            if context_path.exists():
                visionflow_context = context_path.read_text()
        except Exception as e:
            print(f"[Medic] Warning: Could not load visionflow_context.md: {e}")

        prompt = f"""You are Medic, a test repair specialist. Your mission: apply MINIMAL surgical fixes to failing Playwright tests.

HIPPOCRATIC OATH:
- First, do no harm (preserve working tests)
- Apply minimal changes only (1-3 lines if possible)
- Prefer selector updates over logic changes
- Maintain test structure and style

TEST FILE: {test_path}
ERROR MESSAGE:
{error_message}

CURRENT TEST CODE:
```typescript
{test_content}
```

{"APPLICATION CONTEXT (VisionFlow/Cloppy AI - USE THESE SELECTORS):" if visionflow_context else ""}
{visionflow_context}

CONTEXT:
{json.dumps(context, indent=2)}

COMMON FIX PATTERNS:
1. Selector not found → Update data-testid or add waitForSelector
2. Timeout → Increase timeout or add intermediate waits
3. Assertion failure → Verify expected vs actual values

INSTRUCTIONS:
1. Diagnose the root cause
2. Apply the SMALLEST possible fix
3. Rate your confidence in the fix (0.0-1.0)
4. Return the COMPLETE fixed file (not just the changed section)
5. Use this format:

DIAGNOSIS: <one-line root cause>

CONFIDENCE: <0.0-1.0 score>
(0.0-0.5 = uncertain, 0.5-0.7 = moderate, 0.7-0.9 = confident, 0.9-1.0 = very confident)

FIX:
```typescript
<complete fixed test file>
```

IMPORTANT:
- Only change what's necessary to fix the error
- Keep all existing test structure
- Preserve formatting and style
- Don't add new tests or remove existing ones
- Be honest about confidence - if root cause is unclear, rate it low
"""
        return prompt

    def _generate_diff(
        self,
        original: str,
        fixed: str,
        file_path: str
    ) -> str:
        """
        Generate unified diff.

        Args:
            original: Original content
            fixed: Fixed content
            file_path: File path for diff header

        Returns:
            Unified diff string
        """
        diff = difflib.unified_diff(
            original.splitlines(keepends=True),
            fixed.splitlines(keepends=True),
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            lineterm=''
        )

        return ''.join(diff)

    def _compare_results(
        self,
        baseline: Dict[str, Any],
        after_fix: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Compare baseline vs after-fix results.

        Args:
            baseline: Baseline test results
            after_fix: After-fix test results

        Returns:
            Comparison dict with new_failures count
        """
        # Calculate new failures
        baseline_failed = baseline.get('failed', 0)
        after_failed = after_fix.get('failed', 0)

        new_failures = max(0, after_failed - baseline_failed)

        return {
            'new_failures': new_failures,
            'baseline_passed': baseline.get('passed', 0),
            'baseline_failed': baseline_failed,
            'after_passed': after_fix.get('passed', 0),
            'after_failed': after_failed,
            'improved': after_failed < baseline_failed
        }

    def _generate_artifacts(
        self,
        diff: str,
        baseline: Dict[str, Any],
        after_fix: Dict[str, Any],
        comparison: Dict[str, Any],
        diagnosis: str,
        test_path: str
    ) -> Dict[str, str]:
        """
        Generate required artifacts.

        Args:
            diff: Unified diff
            baseline: Baseline results
            after_fix: After-fix results
            comparison: Comparison results
            diagnosis: Fix diagnosis
            test_path: Test file path

        Returns:
            Dict with artifact paths
        """
        artifacts_dir = Path(__file__).parent.parent.parent / 'artifacts'
        artifacts_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Write fix.diff
        diff_path = artifacts_dir / f"medic_fix_{timestamp}.diff"
        with open(diff_path, 'w') as f:
            f.write(diff)

        # Write regression_report.json
        report = {
            'timestamp': datetime.now().isoformat(),
            'test_path': test_path,
            'diagnosis': diagnosis,
            'baseline': {
                'passed': baseline.get('passed', 0),
                'failed': baseline.get('failed', 0),
                'total': baseline.get('total', 0)
            },
            'after_fix': {
                'passed': after_fix.get('passed', 0),
                'failed': after_fix.get('failed', 0),
                'total': after_fix.get('total', 0)
            },
            'comparison': comparison,
            'fix_applied': comparison['new_failures'] == 0,
            'hippocratic_oath_honored': comparison['new_failures'] == 0
        }

        report_path = artifacts_dir / f"medic_regression_report_{timestamp}.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)

        return {
            'diff_path': str(diff_path),
            'report_path': str(report_path)
        }

    def _increment_fix_attempts(self, task_id: str, test_path: str) -> int:
        """
        Track and increment fix attempts for a task.

        Args:
            task_id: Unique task identifier
            test_path: Path to test file

        Returns:
            Current attempt count (1-indexed)
        """
        key = f"medic:attempts:{task_id}"

        # Get current attempts
        current = self.redis.get(key)
        if current is None:
            attempts = 1
        else:
            attempts = int(current) + 1

        # Store updated count with 24h TTL
        self.redis.set(key, attempts, ttl=86400)

        # Also store attempt history
        history_key = f"medic:history:{task_id}"
        attempt_record = {
            'attempt': attempts,
            'timestamp': datetime.now().isoformat(),
            'test_path': test_path
        }
        self.redis.client.rpush(history_key, json.dumps(attempt_record))
        self.redis.client.expire(history_key, 86400)

        return attempts

    def _get_fix_attempts(self, task_id: str) -> int:
        """
        Get current fix attempt count for a task.

        Args:
            task_id: Unique task identifier

        Returns:
            Current attempt count (0 if not found)
        """
        key = f"medic:attempts:{task_id}"
        current = self.redis.get(key)
        return int(current) if current else 0

    def _get_attempt_history(self, task_id: str) -> List[Dict[str, Any]]:
        """
        Get full attempt history for a task.

        Args:
            task_id: Unique task identifier

        Returns:
            List of attempt records
        """
        history_key = f"medic:history:{task_id}"
        records = self.redis.client.lrange(history_key, 0, -1)
        return [json.loads(r) for r in records]

    def _escalate_to_hitl(
        self,
        task_id: str,
        test_path: str,
        error_message: str,
        feature: Optional[str],
        attempts: int,
        reason: str,
        artifacts: Dict[str, Any],
        api_cost: float,
        severity: str = "medium"
    ) -> AgentResult:
        """
        Escalate task to HITL queue with full context.

        Args:
            task_id: Unique task identifier
            test_path: Path to test file
            error_message: Original error message
            feature: Feature name
            attempts: Number of fix attempts made
            reason: Escalation reason (max_retries_exceeded, regression_detected, low_confidence)
            artifacts: Artifact paths and data
            api_cost: API cost incurred
            severity: Issue severity (low/medium/high/critical)

        Returns:
            AgentResult with escalated status
        """
        print(f"[Medic] Escalating to HITL: {reason}")

        # Gather all artifacts and context
        attempt_history = self._get_attempt_history(task_id)

        # Get screenshots if available
        screenshots = []
        artifacts_dir = Path(__file__).parent.parent.parent / 'artifacts'
        if artifacts_dir.exists():
            # Look for recent screenshots related to this test
            test_name = Path(test_path).stem
            screenshot_pattern = f"*{test_name}*.png"
            for screenshot in artifacts_dir.glob(screenshot_pattern):
                screenshots.append(str(screenshot))

        # Get logs path
        logs_dir = Path(__file__).parent.parent.parent / 'logs'
        logs_path = str(logs_dir / f"{task_id}.log") if logs_dir.exists() else ""

        # Calculate priority based on attempts and severity
        severity_scores = {
            'low': 0.1,
            'medium': 0.3,
            'high': 0.5,
            'critical': 0.7
        }
        base_priority = severity_scores.get(severity, 0.3)
        attempts_factor = min(attempts / 10, 0.3)  # Max 0.3 from attempts
        priority = min(base_priority + attempts_factor, 1.0)

        # Build HITL task payload
        hitl_task = {
            'task_id': task_id,
            'feature': feature or Path(test_path).stem,
            'code_path': test_path,
            'logs_path': logs_path,
            'screenshots': screenshots[:5],  # Limit to 5 most recent
            'attempts': attempts,
            'last_error': error_message,
            'priority': priority,
            'severity': severity,
            'escalation_reason': reason,
            'attempt_history': attempt_history,
            'ai_diagnosis': artifacts.get('diagnosis', 'Unknown'),
            'ai_confidence': artifacts.get('confidence', 0.0),
            'artifacts': {
                'diff': artifacts.get('diff', '')[:2000],  # Truncate
                'baseline': artifacts.get('baseline', {}),
                'after_fix': artifacts.get('after_fix', {}),
                'comparison': artifacts.get('comparison', {}),
            },
            'created_at': datetime.now().isoformat()
        }

        # Add to HITL queue
        try:
            self.hitl.add(hitl_task)
            print(f"[Medic] Successfully added to HITL queue with priority {priority:.2f}")
        except Exception as e:
            print(f"[Medic] Warning: Failed to add to HITL queue: {e}")

        # Return AgentResult with escalated status
        return AgentResult(
            success=False,
            error=f"Escalated to HITL: {reason} (attempts: {attempts})",
            data={
                'status': 'escalated_to_hitl',
                'reason': reason,
                'task_id': task_id,
                'test_path': test_path,
                'attempts': attempts,
                'severity': severity,
                'priority': priority,
                'hitl_task': hitl_task
            },
            metadata={
                'escalation_reason': reason,
                'attempts': attempts,
                'severity': severity
            },
            execution_time_ms=int((time.time() - time.time()) * 1000),  # Will be updated by caller
            cost_usd=api_cost
        )


# CLI for testing
if __name__ == '__main__':
    import sys

    if len(sys.argv) < 3:
        print("Usage: python medic.py <test_path> <error_message>")
        sys.exit(1)

    test_path = sys.argv[1]
    error_message = sys.argv[2]

    medic = MedicAgent()
    result = medic.execute(
        test_path=test_path,
        error_message=error_message
    )

    print(f"\n{'='*60}")
    print(f"Medic Result: {'SUCCESS' if result.success else 'FAILURE'}")
    print(f"{'='*60}")
    print(f"Cost: ${result.cost_usd:.4f}")
    print(f"Time: {result.execution_time_ms}ms")

    if result.success:
        print(f"\nDiagnosis: {result.data.get('diagnosis')}")
        print(f"New Failures: {result.data['comparison']['new_failures']}")
        print(f"\nArtifacts:")
        for key, path in result.data['artifacts'].items():
            print(f"  - {key}: {path}")
    else:
        print(f"\nError: {result.error}")

    print(f"{'='*60}\n")
