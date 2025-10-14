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
                issues.append(f"Too many steps: {cost_estimate['steps']} > {self.MAX_STEPS}")

            if duration_estimate > self.MAX_DURATION_MS:
                issues.append(f"Estimated duration {duration_estimate}ms exceeds {self.MAX_DURATION_MS}ms")

            # Determine approval
            approved = len(issues) == 0

            execution_time = self._track_execution(start_time)

            return AgentResult(
                success=True,
                data={
                    'status': 'approved' if approved else 'rejected',
                    'test_path': test_path,
                    'issues_found': issues,
                    'estimated_cost_usd': cost_estimate['cost_usd'],
                    'estimated_duration_ms': duration_estimate,
                    'estimated_steps': cost_estimate['steps']
                },
                metadata={
                    'anti_patterns_found': len(pattern_issues),
                    'assertion_count': self._count_assertions(test_code)
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

    def _check_anti_patterns(self, code: str) -> List[str]:
        """
        Check for anti-patterns in test code.

        Args:
            code: Test code content

        Returns:
            List of issue descriptions
        """
        issues = []

        for pattern_def in self.ANTI_PATTERNS:
            pattern = pattern_def['pattern']
            reason = pattern_def['reason']
            flags = pattern_def.get('flags', 0)

            if re.search(pattern, code, flags):
                issues.append(f"Anti-pattern detected: {reason} (pattern: {pattern})")

        return issues

    def _check_assertions(self, code: str) -> List[str]:
        """
        Check for minimum assertions.

        Args:
            code: Test code content

        Returns:
            List of issues (empty if assertions found)
        """
        assertion_count = self._count_assertions(code)

        if assertion_count < 1:
            return ["No assertions found - tests must have at least 1 expect() call"]

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
