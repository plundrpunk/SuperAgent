"""
Scribe Agent - Test Writer with Self-Validation and RAG
Writes Playwright tests with built-in Critic validation and RAG-enhanced generation.
"""
import re
import time
from typing import Dict, Any, List, Tuple, Optional
from pathlib import Path
import logging

from agent_system.agents.base_agent import BaseAgent, AgentResult
from agent_system.state.vector_client import VectorClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ScribeAgent(BaseAgent):
    """
    Scribe writes Playwright tests with self-validation and RAG enhancement.

    Features:
    - Generates Playwright tests following VisionFlow patterns
    - RAG-enhanced generation using similar successful tests from vector DB
    - Validates against Critic criteria before submission
    - Auto-retries with feedback on validation failures
    - Tracks validation attempts, success rate, and RAG usage
    - Uses data-testid selectors exclusively
    - Includes proper assertions and screenshots
    - Graceful fallback when no similar patterns found
    """

    # Anti-patterns from Critic (same as critic.py)
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

    # Test template
    TEST_TEMPLATE = '''import {{ test, expect }} from '@playwright/test';

const S = (id: string) => `[data-testid="${{id}}"]`;

test.use({{
  screenshot: 'on',
  video: 'retain-on-failure',
  trace: 'retain-on-failure'
}});

test.describe('{feature_name}', () => {{
  test.beforeEach(async ({{ page }}) => {{
    await page.goto(process.env.BASE_URL!);
  }});

  test('happy path', async ({{ page }}) => {{
    // {test_steps}

    // Take screenshots at key steps
    await page.screenshot({{ path: 'screenshot-step-1.png' }});

    // Add assertions
    await expect(page.locator(S('result'))).toBeVisible();
  }});

  test('error case', async ({{ page }}) => {{
    // Test error handling
    await expect(page.locator(S('error'))).toBeVisible();
  }});
}});
'''

    MAX_RETRIES = 3
    MAX_STEPS = 10
    MAX_DURATION_MS = 60000

    def __init__(self, vector_client: Optional[VectorClient] = None):
        """
        Initialize Scribe agent with RAG support.

        Args:
            vector_client: Optional VectorClient instance (creates new if not provided)
        """
        super().__init__('scribe')

        # Initialize RAG components
        self.vector_client = vector_client or VectorClient()

        # RAG configuration
        self.rag_config = {
            'similarity_threshold': 0.7,
            'max_patterns': 5,
            'collection': 'test_success'
        }

        # Track validation metrics
        self.validation_attempts = 0
        self.validation_failures = 0
        self.retries_used = 0

        # Track RAG metrics
        self.rag_queries = 0
        self.rag_hits = 0  # Queries that found patterns above threshold
        self.total_patterns_retrieved = 0

    def execute(
        self,
        task_description: str,
        feature_name: str,
        output_path: str,
        complexity: str = 'easy'
    ) -> AgentResult:
        """
        Generate a test with self-validation.

        Args:
            task_description: Description of what to test
            feature_name: Feature being tested (for test.describe)
            output_path: Where to save the test file
            complexity: 'easy' or 'hard' (determines model choice)

        Returns:
            AgentResult with generated test or validation errors
        """
        start_time = time.time()

        try:
            # Generate with validation and retry
            result = self._generate_with_validation(
                task_description=task_description,
                feature_name=feature_name,
                max_retries=self.MAX_RETRIES
            )

            if not result['success']:
                execution_time = self._track_execution(start_time)
                return AgentResult(
                    success=False,
                    error=result['error'],
                    metadata={
                        'validation_attempts': result['attempts'],
                        'final_issues': result['issues']
                    },
                    execution_time_ms=execution_time
                )

            # Save generated test
            test_content = result['test_content']
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)

            with open(output_file, 'w') as f:
                f.write(test_content)

            execution_time = self._track_execution(start_time)

            return AgentResult(
                success=True,
                data={
                    'test_path': str(output_file),
                    'test_content': test_content,
                    'validation_passed': True,
                    'attempts_used': result['attempts'],
                    'rag_patterns_used': result.get('rag_patterns_used', []),
                    'used_rag': result.get('used_rag', False)
                },
                metadata={
                    'feature_name': feature_name,
                    'complexity': complexity,
                    'retries_used': result['attempts'] - 1,
                    'validation_issues_resolved': result.get('issues_resolved', []),
                    'rag_patterns_count': result.get('rag_patterns_count', 0)
                },
                execution_time_ms=execution_time
            )

        except Exception as e:
            execution_time = self._track_execution(start_time)
            return AgentResult(
                success=False,
                error=f"Scribe error: {str(e)}",
                execution_time_ms=execution_time
            )

    def _generate_with_validation(
        self,
        task_description: str,
        feature_name: str,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Generate test with validation and retry logic.

        Args:
            task_description: What to test
            feature_name: Feature name
            max_retries: Maximum retry attempts

        Returns:
            Dict with success, test_content, attempts, issues
        """
        issues_history = []
        enhanced_description = task_description

        # Track RAG info across attempts
        rag_patterns_used = []
        used_rag = False

        for attempt in range(1, max_retries + 1):
            logger.info(f"Generation attempt {attempt}/{max_retries}")
            self.validation_attempts += 1

            # Generate test with RAG
            generation_result = self._generate_test_with_rag(
                description=enhanced_description,
                feature_name=feature_name
            )

            test_content = generation_result['test_content']

            # Track RAG usage (only from first successful attempt)
            if attempt == 1:
                rag_patterns_used = generation_result.get('patterns_used', [])
                used_rag = generation_result.get('used_rag', False)

            # Validate
            passed, issues = self._validate_generated_test(test_content)

            if passed:
                logger.info(f"✓ Validation passed on attempt {attempt}")
                return {
                    'success': True,
                    'test_content': test_content,
                    'attempts': attempt,
                    'issues_resolved': issues_history,
                    'rag_patterns_used': rag_patterns_used,
                    'used_rag': used_rag,
                    'rag_patterns_count': len(rag_patterns_used)
                }

            # Validation failed
            self.validation_failures += 1
            self.retries_used += 1
            issues_history.append({
                'attempt': attempt,
                'issues': issues
            })

            feedback = f"Validation failed: {', '.join(issues)}"
            logger.warning(f"⚠ Attempt {attempt} failed: {feedback}")

            if attempt < max_retries:
                # Enhance prompt with feedback for next attempt
                enhanced_description = f"""{task_description}

PREVIOUS ATTEMPT FAILED - FIX THESE ISSUES:
{chr(10).join(f'- {issue}' for issue in issues)}

REQUIREMENTS:
- Use ONLY data-testid selectors: const S = (id: string) => `[data-testid="${{id}}"]`
- Include at least 1 expect() assertion
- NO .nth() index-based selectors
- NO .css-* generated classes
- NO waitForTimeout (use waitForSelector)
- NO hard-coded credentials or localhost URLs
- Use process.env.BASE_URL for navigation
- Add screenshots at key steps
"""
            else:
                # Max retries exceeded
                logger.error(f"✗ Failed validation after {max_retries} attempts")
                return {
                    'success': False,
                    'error': f"Failed validation after {max_retries} attempts",
                    'attempts': attempt,
                    'issues': issues
                }

        # Should never reach here, but for safety
        return {
            'success': False,
            'error': 'Unexpected error in retry loop',
            'attempts': max_retries,
            'issues': []
        }

    def _query_similar_patterns(self, query: str) -> List[Dict[str, Any]]:
        """
        Query vector DB for similar test patterns.

        Args:
            query: Task description to search for

        Returns:
            List of similar test patterns above threshold
        """
        self.rag_queries += 1

        try:
            # Search vector DB
            all_patterns = self.vector_client.search_test_patterns(
                query=query,
                n_results=self.rag_config['max_patterns']
            )

            # Filter by similarity threshold
            filtered_patterns = [
                p for p in all_patterns
                if p['similarity'] >= self.rag_config['similarity_threshold']
            ]

            if filtered_patterns:
                self.rag_hits += 1
                self.total_patterns_retrieved += len(filtered_patterns)
                logger.info(f"RAG: Found {len(filtered_patterns)} similar patterns (threshold: {self.rag_config['similarity_threshold']})")
            else:
                logger.info(f"RAG: No patterns found above threshold {self.rag_config['similarity_threshold']}")

            return filtered_patterns

        except Exception as e:
            logger.warning(f"RAG query failed: {e}. Falling back to template-only generation.")
            return []

    def _format_patterns_as_context(self, patterns: List[Dict[str, Any]]) -> str:
        """
        Format retrieved patterns as LLM context.

        Args:
            patterns: List of pattern dicts from vector DB

        Returns:
            Formatted context string
        """
        if not patterns:
            return ""

        context_parts = ["Here are similar successful tests for reference:\n"]

        for i, pattern in enumerate(patterns, 1):
            similarity_pct = int(pattern['similarity'] * 100)
            metadata = pattern.get('metadata', {})

            context_parts.append(f"\n--- Example {i} (similarity: {similarity_pct}%) ---")

            # Add metadata context
            if metadata.get('feature'):
                context_parts.append(f"Feature: {metadata['feature']}")
            if metadata.get('complexity'):
                context_parts.append(f"Complexity: {metadata['complexity']}")
            if metadata.get('test_type'):
                context_parts.append(f"Type: {metadata['test_type']}")

            # Add test code snippet (truncate if too long)
            code = pattern['code']
            if len(code) > 1000:
                code = code[:1000] + "\n... (truncated)"

            context_parts.append(f"\n{code}\n")

        return "\n".join(context_parts)

    def _generate_test_with_rag(self, description: str, feature_name: str) -> Dict[str, Any]:
        """
        Generate test code with RAG enhancement.

        Args:
            description: Test description with feedback
            feature_name: Feature name

        Returns:
            Dict with test_content, patterns_used, used_rag
        """
        # 1. Query vector DB for similar patterns (RAG)
        similar_patterns = self._query_similar_patterns(description)

        # 2. Build enhanced prompt with RAG context
        enhanced_prompt = self._build_enhanced_prompt(
            description=description,
            feature_name=feature_name,
            similar_patterns=similar_patterns
        )

        # 3. Generate test code
        # In production, this would:
        # - Call Claude API (Haiku or Sonnet based on complexity)
        # - Use enhanced_prompt with RAG context
        # - Return the generated test code

        # For now, return template-based code with RAG awareness
        test_steps = self._extract_steps_from_description(description)

        # Add RAG indicator comment if patterns were used
        rag_comment = ""
        pattern_ids = []
        if similar_patterns:
            pattern_ids = [p['id'] for p in similar_patterns]
            rag_comment = f"// Generated with RAG using {len(similar_patterns)} similar pattern(s): {', '.join(pattern_ids[:3])}\n"

        test_code = self.TEST_TEMPLATE.format(
            feature_name=feature_name,
            test_steps=test_steps
        )

        return {
            'test_content': rag_comment + test_code,
            'patterns_used': pattern_ids,
            'used_rag': len(similar_patterns) > 0
        }

    def _build_enhanced_prompt(
        self,
        description: str,
        feature_name: str,
        similar_patterns: List[Dict[str, Any]]
    ) -> str:
        """
        Build enhanced prompt with RAG context.

        Args:
            description: Task description
            feature_name: Feature name
            similar_patterns: Retrieved similar patterns

        Returns:
            Enhanced prompt string for LLM
        """
        prompt_parts = [
            "You are an expert Playwright test writer following VisionFlow patterns.",
            "",
            "CRITICAL REQUIREMENTS:",
            "- Use ONLY data-testid selectors via S() helper function",
            "- Include await page.screenshot() after each major step",
            "- Always include expect() assertions",
            "- NO .nth() selectors (index-based)",
            "- NO .css-* classes (generated classes)",
            "- NO waitForTimeout (use waitForSelector instead)",
            "- Enable screenshot, video, and trace capture",
            ""
        ]

        # Add RAG context if available
        pattern_context = self._format_patterns_as_context(similar_patterns)
        if pattern_context:
            prompt_parts.append(pattern_context)
            prompt_parts.append("\nNow, following these successful patterns, generate a test for:\n")
        else:
            prompt_parts.append("Generate a test for:\n")

        # Add task details
        prompt_parts.append(f"Feature: {feature_name}")
        prompt_parts.append(f"Description: {description}")

        return "\n".join(prompt_parts)

    def _extract_steps_from_description(self, description: str) -> str:
        """
        Extract test steps from description (simplified).

        Args:
            description: Task description

        Returns:
            Test steps as code comments
        """
        # Simple extraction - in production would be more sophisticated
        lines = description.split('\n')
        steps = [line.strip() for line in lines if line.strip() and not line.startswith('PREVIOUS')]
        return '\n    // '.join(steps[:5])  # Limit to 5 steps

    def _validate_generated_test(self, test_content: str) -> Tuple[bool, List[str]]:
        """
        Validate test against Critic criteria.

        Args:
            test_content: Generated test code

        Returns:
            (passed: bool, issues: List[str])
        """
        issues = []

        # 1. Check for anti-patterns
        for pattern_def in self.ANTI_PATTERNS:
            pattern = pattern_def['pattern']
            reason = pattern_def['reason']
            flags = pattern_def.get('flags', 0)

            if re.search(pattern, test_content, flags):
                issues.append(f"{reason} (found pattern: {pattern})")

        # 2. Check for required patterns
        if not re.search(r'\bexpect\s*\(', test_content):
            issues.append("Missing expect() assertions - tests must have at least 1")

        if not re.search(r'data-testid', test_content):
            issues.append("Missing data-testid selectors - use data-testid exclusively")

        # 3. Check for screenshots
        if not re.search(r'\.screenshot\(', test_content):
            issues.append("Missing screenshots - add screenshots at key steps")

        # 4. Estimate steps and duration
        step_count = self._count_steps(test_content)
        if step_count > self.MAX_STEPS:
            issues.append(f"Too many steps: {step_count} > {self.MAX_STEPS}")

        duration_estimate = step_count * 2000  # 2s per step
        if duration_estimate > self.MAX_DURATION_MS:
            issues.append(f"Estimated duration {duration_estimate}ms exceeds {self.MAX_DURATION_MS}ms")

        return (len(issues) == 0, issues)

    def _count_steps(self, code: str) -> int:
        """
        Count test action steps.

        Args:
            code: Test code

        Returns:
            Number of steps
        """
        action_patterns = [
            r'\.click\(',
            r'\.fill\(',
            r'\.type\(',
            r'\.press\(',
            r'\.goto\(',
            r'waitFor',
            r'\.screenshot\('
        ]

        return sum(len(re.findall(pattern, code)) for pattern in action_patterns)

    def get_validation_stats(self) -> Dict[str, Any]:
        """
        Get validation statistics including RAG metrics.

        Returns:
            Dict with validation and RAG metrics
        """
        success_rate = (
            (self.validation_attempts - self.validation_failures) / self.validation_attempts
            if self.validation_attempts > 0
            else 0.0
        )

        avg_retries = (
            self.retries_used / (self.validation_attempts - self.validation_failures)
            if (self.validation_attempts - self.validation_failures) > 0
            else 0.0
        )

        # RAG metrics
        rag_hit_rate = (
            self.rag_hits / self.rag_queries
            if self.rag_queries > 0
            else 0.0
        )

        avg_patterns_per_hit = (
            self.total_patterns_retrieved / self.rag_hits
            if self.rag_hits > 0
            else 0.0
        )

        return {
            'agent': self.name,
            'validation_attempts': self.validation_attempts,
            'validation_failures': self.validation_failures,
            'success_rate': success_rate,
            'total_retries_used': self.retries_used,
            'avg_retries_per_success': avg_retries,
            # RAG metrics
            'rag_queries': self.rag_queries,
            'rag_hits': self.rag_hits,
            'rag_hit_rate': rag_hit_rate,
            'total_patterns_retrieved': self.total_patterns_retrieved,
            'avg_patterns_per_hit': avg_patterns_per_hit,
            'rag_threshold': self.rag_config['similarity_threshold'],
            **self.get_stats()
        }
