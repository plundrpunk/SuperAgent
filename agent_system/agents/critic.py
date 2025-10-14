"""
Critic Agent - Pre-Validator
Quality gate before expensive Gemini validation.
"""
import re
import time
from typing import Dict, Any, List, Tuple
from pathlib import Path

from agent_system.agents.base_agent import BaseAgent, AgentResult


class CriticAgent(BaseAgent):
    """
    Critic reviews tests before validation to prevent flaky/expensive tests.

    Responsibilities:
    - Check for anti-patterns (nth(), CSS classes, waitForTimeout)
    - Validate minimum assertions (at least 1 expect call)
    - Estimate execution cost and duration
    - Provide detailed rejection feedback
    - Approve only high-quality deterministic tests
    """

    # Anti-patterns from critic.yaml
    ANTI_PATTERNS = [
        {
            'pattern': r'\.nth\(\d+\)',
            'reason': 'Index-based selectors are flaky'
        },
        {
            'pattern': r'\.css-[a-z0-9]+',
            'reason': 'Generated CSS classes change frequently'
        },
        {
            'pattern': r'waitForTimeout',
            'reason': 'Use waitForSelector instead'
        },
        {
            'pattern': r'hard[_-]?coded.*credential',
            'reason': 'Use environment variables',
            'flags': re.IGNORECASE
        },
        {
            'pattern': r'localhost|127\.0\.0\.1',
            'reason': 'Use process.env.BASE_URL'
        }
    ]

    MAX_STEPS = 10
    MAX_DURATION_MS = 60000

    def __init__(self):
        """Initialize Critic agent."""
        super().__init__('critic')

    def execute(self, test_path: str) -> AgentResult:
        """
        Review test for quality issues.

        Args:
            test_path: Path to test file

        Returns:
            AgentResult with approved/rejected and feedback
        """
        start_time = time.time()

        try:
            # Read test file
            with open(test_path, 'r') as f:
                test_code = f.read()

            # Run all checks
            issues = []

            # 1. Check for anti-patterns
            pattern_issues = self._check_anti_patterns(test_code)
            issues.extend(pattern_issues)

            # 2. Check for minimum assertions
            assertion_issues = self._check_assertions(test_code)
            issues.extend(assertion_issues)

            # 3. Estimate cost and duration
            cost_estimate = self._estimate_cost(test_code)
            duration_estimate = self._estimate_duration(test_code)

            if cost_estimate['steps'] > self.MAX_STEPS:
                issues.append({
                    'type': 'excessive_steps',
                    'severity': 'warning',
                    'actual': cost_estimate['steps'],
                    'max': self.MAX_STEPS,
                    'reason': f'Test has {cost_estimate["steps"]} steps, exceeds maximum of {self.MAX_STEPS}',
                    'fix': 'Consider splitting test into smaller, focused tests'
                })

            if duration_estimate > self.MAX_DURATION_MS:
                issues.append({
                    'type': 'excessive_duration',
                    'severity': 'warning',
                    'actual': duration_estimate,
                    'max': self.MAX_DURATION_MS,
                    'reason': f'Estimated duration {duration_estimate}ms exceeds {self.MAX_DURATION_MS}ms',
                    'fix': 'Reduce wait times or split test into smaller units'
                })

            # Determine approval
            approved = len(issues) == 0

            # Generate formatted feedback
            feedback = self._format_feedback(issues, cost_estimate, duration_estimate) if not approved else None

            execution_time = self._track_execution(start_time)

            return AgentResult(
                success=True,
                data={
                    'status': 'approved' if approved else 'rejected',
                    'test_path': test_path,
                    'issues_found': issues,
                    'feedback': feedback,
                    'estimated_cost_usd': cost_estimate['cost_usd'],
                    'estimated_duration_ms': duration_estimate,
                    'estimated_steps': cost_estimate['steps']
                },
                metadata={
                    'anti_patterns_found': len(pattern_issues),
                    'assertion_count': self._count_assertions(test_code),
                    'critical_issues': len([i for i in issues if i.get('severity') == 'critical']),
                    'warnings': len([i for i in issues if i.get('severity') == 'warning'])
                },
                execution_time_ms=execution_time
            )

        except FileNotFoundError:
            return AgentResult(
                success=False,
                error=f"Test file not found: {test_path}",
                execution_time_ms=self._track_execution(start_time)
            )
        except Exception as e:
            return AgentResult(
                success=False,
                error=f"Critic error: {str(e)}",
                execution_time_ms=self._track_execution(start_time)
            )

    def _check_anti_patterns(self, code: str) -> List[Dict[str, Any]]:
        """
        Check for anti-patterns in test code with line numbers.

        Args:
            code: Test code content

        Returns:
            List of issue dictionaries with line numbers and details
        """
        issues = []
        lines = code.split('\n')

        for pattern_def in self.ANTI_PATTERNS:
            pattern = pattern_def['pattern']
            reason = pattern_def['reason']
            flags = pattern_def.get('flags', 0)

            # Find all matches with line numbers
            for line_num, line in enumerate(lines, start=1):
                matches = re.finditer(pattern, line, flags)
                for match in matches:
                    issues.append({
                        'type': 'anti_pattern',
                        'line': line_num,
                        'pattern': pattern,
                        'matched': match.group(),
                        'reason': reason,
                        'severity': 'critical',
                        'fix': self._suggest_fix(pattern, reason)
                    })

        return issues

    def _check_assertions(self, code: str) -> List[Dict[str, Any]]:
        """
        Check for minimum assertions.

        Args:
            code: Test code content

        Returns:
            List of issues (empty if assertions found)
        """
        assertion_count = self._count_assertions(code)

        if assertion_count < 1:
            return [{
                'type': 'missing_assertions',
                'severity': 'critical',
                'expected': 1,
                'actual': 0,
                'reason': 'Tests must have at least 1 expect() call',
                'fix': 'Add expect() assertions after key actions to verify behavior'
            }]

        return []

    def _count_assertions(self, code: str) -> int:
        """
        Count expect() calls in code.

        Args:
            code: Test code

        Returns:
            Number of assertions
        """
        # Count expect(...) patterns
        return len(re.findall(r'\bexpect\s*\(', code))

    def _estimate_cost(self, code: str) -> Dict[str, Any]:
        """
        Estimate execution cost.

        Args:
            code: Test code

        Returns:
            Dict with steps and cost_usd estimate
        """
        # Count test actions
        action_patterns = [
            r'\.click\(',
            r'\.fill\(',
            r'\.type\(',
            r'\.press\(',
            r'\.goto\(',
            r'waitFor',
            r'\.screenshot\('
        ]

        step_count = sum(len(re.findall(pattern, code)) for pattern in action_patterns)

        # Rough cost estimate: $0.01 per 10 steps
        cost_usd = (step_count / 10) * 0.01

        return {
            'steps': step_count,
            'cost_usd': cost_usd
        }

    def _estimate_duration(self, code: str) -> int:
        """
        Estimate execution duration in milliseconds.

        Args:
            code: Test code

        Returns:
            Estimated duration in ms
        """
        # Rough estimate: 2 seconds per action
        cost_estimate = self._estimate_cost(code)
        steps = cost_estimate['steps']

        return steps * 2000  # 2s per step

    def _suggest_fix(self, pattern: str, reason: str) -> str:
        """
        Suggest a fix for detected anti-pattern.

        Args:
            pattern: Regex pattern that was matched
            reason: Reason for rejection

        Returns:
            Actionable fix suggestion
        """
        fix_suggestions = {
            r'\.nth\(\d+\)': 'Replace with data-testid selector: await page.locator(\'[data-testid="element-name"]\').click()',
            r'\.css-[a-z0-9]+': 'Use data-testid attribute instead of CSS class: <div data-testid="element-name">',
            r'waitForTimeout': 'Replace with waitForSelector: await page.waitForSelector(\'[data-testid="element"]\', { timeout: 5000 })',
            r'hard[_-]?coded.*credential': 'Use environment variable: process.env.TEST_USERNAME',
            r'localhost|127\.0\.0\.1': 'Use environment variable: await page.goto(process.env.BASE_URL!)'
        }

        for pattern_key, suggestion in fix_suggestions.items():
            if pattern == pattern_key:
                return suggestion

        return reason

    def _format_feedback(self, issues: List[Dict[str, Any]], cost_estimate: Dict[str, Any], duration_estimate: int) -> str:
        """
        Format structured feedback for Scribe agent consumption.

        Args:
            issues: List of detected issues
            cost_estimate: Cost estimation details
            duration_estimate: Duration estimation in ms

        Returns:
            Formatted feedback string with actionable suggestions
        """
        # Sort issues by severity (critical first)
        critical_issues = [i for i in issues if i.get('severity') == 'critical']
        warnings = [i for i in issues if i.get('severity') == 'warning']

        feedback_lines = ['REJECTED - Issues Found:', '']

        # Critical issues first
        if critical_issues:
            # Group by type
            anti_pattern_issues = [i for i in critical_issues if i['type'] == 'anti_pattern']
            assertion_issues = [i for i in critical_issues if i['type'] == 'missing_assertions']

            if anti_pattern_issues:
                feedback_lines.append(f'X Anti-patterns ({len(anti_pattern_issues)} issues):')
                for issue in anti_pattern_issues:
                    feedback_lines.append(f'  - Line {issue["line"]}: {issue["matched"]} - {issue["reason"]}')
                    feedback_lines.append(f'    FIX: {issue["fix"]}')
                feedback_lines.append('')

            if assertion_issues:
                for issue in assertion_issues:
                    feedback_lines.append(f'X Missing assertions ({issue["expected"]} expected, {issue["actual"]} found):')
                    feedback_lines.append(f'  - {issue["reason"]}')
                    feedback_lines.append(f'  FIX: {issue["fix"]}')
                    feedback_lines.append('')

        # Warnings
        if warnings:
            for issue in warnings:
                if issue['type'] == 'excessive_steps':
                    feedback_lines.append(f'! Performance ({issue["actual"]} steps, max {issue["max"]}):')
                    feedback_lines.append(f'  - {issue["reason"]}')
                    feedback_lines.append(f'  FIX: {issue["fix"]}')
                    feedback_lines.append('')
                elif issue['type'] == 'excessive_duration':
                    duration_sec = issue['actual'] / 1000
                    max_sec = issue['max'] / 1000
                    feedback_lines.append(f'! Performance ({duration_sec:.1f}s estimated, max {max_sec:.1f}s):')
                    feedback_lines.append(f'  - {issue["reason"]}')
                    feedback_lines.append(f'  FIX: {issue["fix"]}')
                    feedback_lines.append('')

        # Summary
        feedback_lines.append('Summary:')
        feedback_lines.append(f'  - Critical issues: {len(critical_issues)}')
        feedback_lines.append(f'  - Warnings: {len(warnings)}')
        feedback_lines.append(f'  - Estimated cost: ${cost_estimate["cost_usd"]:.4f}')
        feedback_lines.append(f'  - Estimated duration: {duration_estimate / 1000:.1f}s')

        return '\n'.join(feedback_lines)
