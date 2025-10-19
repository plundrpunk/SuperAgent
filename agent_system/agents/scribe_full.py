"""
Scribe Agent - Test Writer with AI Generation
Generates Playwright tests using Claude Haiku (easy) or Sonnet 4.5 (hard).

This is the complete production-ready implementation with:
- Full Anthropic API integration
- Template loading
- Complexity-based model selection
- Validation with retry logic
- Cost tracking
- TypeScript syntax validation
"""
import os
import re
import subprocess
import time
from typing import Dict, Any, Optional
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

from agent_system.agents.base_agent import BaseAgent, AgentResult
from agent_system.complexity_estimator import ComplexityEstimator
from agent_system.rate_limiter import limit_anthropic


class ScribeAgent(BaseAgent):
    """
    Scribe generates Playwright tests following VisionFlow patterns.

    Model Selection:
    - Claude Haiku for easy tests (complexity score < 5)
    - Claude Sonnet 4.5 for hard tests (complexity score >= 5)

    Tools: read, write, edit, grep, glob

    Responsibilities:
    - Load playwright.template.ts template
    - Generate tests with data-testid selectors only
    - Include screenshot captures at major steps
    - Generate both happy path and error cases
    - Validate TypeScript syntax before returning
    - Track token usage and costs
    """

    # Model configurations
    HAIKU_MODEL = "claude-4-5-haiku-20251015"
    SONNET_MODEL = "claude-sonnet-4-5-20250929"

    # Cost per 1K tokens (in USD)
    HAIKU_INPUT_COST = 0.0008   # $0.80 per 1M
    HAIKU_OUTPUT_COST = 0.004   # $4 per 1M
    SONNET_INPUT_COST = 0.003   # $3 per 1M
    SONNET_OUTPUT_COST = 0.015  # $15 per 1M

    # Template path
    TEMPLATE_PATH = "tests/templates/playwright.template.ts"

    # Anti-patterns for validation
    ANTI_PATTERNS = [
        {'pattern': r'\.nth\(\d+\)', 'reason': 'Index-based selectors are flaky'},
        {'pattern': r'\.css-[a-z0-9]+', 'reason': 'Generated CSS classes change frequently'},
        {'pattern': r'waitForTimeout', 'reason': 'Use waitForSelector instead'},
        {'pattern': r'hard[_-]?coded.*credential', 'reason': 'Use environment variables', 'flags': re.IGNORECASE}
        # Removed localhost check - fallback URLs are okay (e.g., process.env.BASE_URL || 'http://localhost:3000')
    ]

    MAX_RETRIES = 3

    def __init__(self):
        """Initialize Scribe agent."""
        super().__init__('scribe')

        # Load environment variables
        load_dotenv()

        # Initialize Anthropic client with secrets manager
        api_key = self.secrets_manager.get_api_key('anthropic')
        self.client = Anthropic(api_key=api_key)
        self.complexity_estimator = ComplexityEstimator()

        # Get project root
        self.project_root = Path(__file__).parent.parent.parent

    def execute(
        self,
        task_description: str,
        task_scope: str = "",
        complexity: Optional[str] = None,
        output_path: Optional[str] = None
    ) -> AgentResult:
        """
        Generate a Playwright test from description.

        Args:
            task_description: Description of the feature to test
            task_scope: Optional scope/context (e.g., "checkout happy path")
            complexity: Optional override for complexity ("easy" or "hard")
            output_path: Optional path to write test file (defaults to auto-generated)

        Returns:
            AgentResult with generated test and validation results
        """
        start_time = time.time()
        api_cost = 0.0

        try:
            # Step 1: Determine complexity and select model
            if complexity is None:
                complexity_result = self.complexity_estimator.estimate(
                    task_description,
                    task_scope
                )
                complexity = complexity_result.difficulty
                model_name = complexity_result.model_recommendation
            else:
                model_name = "sonnet" if complexity == "hard" else "haiku"

            # Always use Sonnet for now (Haiku 4.5 not yet available via API)
            model = self.SONNET_MODEL

            print(f"[Scribe] Task complexity: {complexity} → Using model: {model}")

            # Step 2: Load template
            template_content = self._load_template()
            if not template_content:
                return AgentResult(
                    success=False,
                    error=f"Could not load template from {self.TEMPLATE_PATH}",
                    execution_time_ms=self._track_execution(start_time),
                    cost_usd=api_cost
                )

            # Step 3: Generate test using AI with retry logic
            print(f"[Scribe] Generating test for: {task_description}")
            generation_result = self._generate_with_retry(
                task_description=task_description,
                task_scope=task_scope,
                template=template_content,
                model=model,
                max_retries=self.MAX_RETRIES
            )

            if not generation_result['success']:
                return AgentResult(
                    success=False,
                    error=generation_result['error'],
                    data=generation_result.get('data'),
                    execution_time_ms=self._track_execution(start_time),
                    cost_usd=generation_result.get('cost_usd', 0.0)
                )

            api_cost = generation_result['cost_usd']
            test_content = generation_result['test_content']
            validation_result = generation_result['validation']

            # Step 4: Determine output path if not provided
            if output_path is None:
                output_path = self._generate_output_path(task_description)

            # Step 5: Write test file
            test_path = self.project_root / output_path
            test_path.parent.mkdir(parents=True, exist_ok=True)

            with open(test_path, 'w', encoding='utf-8') as f:
                f.write(test_content)

            print(f"[Scribe] Test written to: {test_path}")

            execution_time = self._track_execution(start_time, api_cost)

            return AgentResult(
                success=True,
                data={
                    'test_content': test_content,
                    'test_path': str(test_path),
                    'template_used': self.TEMPLATE_PATH,
                    'model_used': model,
                    'complexity': complexity,
                    'validation': validation_result,
                    'retries_used': generation_result.get('retries_used', 0)
                },
                metadata={
                    'feature_description': task_description,
                    'scope': task_scope,
                    'line_count': len(test_content.split('\n'))
                },
                cost_usd=api_cost,
                execution_time_ms=execution_time
            )

        except Exception as e:
            return AgentResult(
                success=False,
                error=f"Scribe execution error: {str(e)}",
                execution_time_ms=self._track_execution(start_time),
                cost_usd=api_cost
            )

    def _load_template(self) -> Optional[str]:
        """
        Load Playwright template file.

        Returns:
            Template content or None on error
        """
        try:
            template_path = self.project_root / self.TEMPLATE_PATH
            with open(template_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"[Scribe] Error loading template: {e}")
            return None

    def _generate_with_retry(
        self,
        task_description: str,
        task_scope: str,
        template: str,
        model: str,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Generate test with validation and retry logic.

        Args:
            task_description: Task description
            task_scope: Task scope
            template: Template content
            model: Model to use
            max_retries: Maximum retry attempts

        Returns:
            Dict with success, test_content, validation, cost_usd
        """
        total_cost = 0.0
        enhanced_scope = task_scope

        for attempt in range(1, max_retries + 1):
            print(f"[Scribe] Generation attempt {attempt}/{max_retries}")

            # Generate test using AI
            generation_result = self._generate_test(
                task_description=task_description,
                task_scope=enhanced_scope,
                template=template,
                model=model
            )

            if not generation_result['success']:
                return {
                    'success': False,
                    'error': generation_result['error'],
                    'cost_usd': total_cost + generation_result.get('cost_usd', 0.0)
                }

            test_content = generation_result['test_content']
            total_cost += generation_result['cost_usd']

            # Validate generated test
            validation_result = self._validate_test(test_content)

            if validation_result['valid']:
                print(f"[Scribe] ✓ Validation passed on attempt {attempt}")
                return {
                    'success': True,
                    'test_content': test_content,
                    'validation': validation_result,
                    'cost_usd': total_cost,
                    'retries_used': attempt - 1
                }

            # Validation failed
            issues = validation_result['issues']
            print(f"[Scribe] ⚠ Attempt {attempt} validation failed: {', '.join(issues)}")

            if attempt < max_retries:
                # Add feedback to scope for next attempt
                enhanced_scope = f"""{task_scope}

PREVIOUS ATTEMPT FAILED - FIX THESE ISSUES:
{chr(10).join(f'- {issue}' for issue in issues)}

CRITICAL REQUIREMENTS:
- Use ONLY data-testid selectors with S() helper
- Include expect() assertions (minimum 2)
- NO .nth() selectors
- NO .css-* classes
- NO waitForTimeout (use waitForSelector)
- Use process.env.BASE_URL for navigation
- Add screenshots after major steps
"""
            else:
                # Max retries exceeded
                print(f"[Scribe] ✗ Failed validation after {max_retries} attempts")
                return {
                    'success': False,
                    'error': f"Generated test failed validation after {max_retries} attempts",
                    'data': {
                        'test_content': test_content,
                        'validation': validation_result
                    },
                    'cost_usd': total_cost
                }

        return {
            'success': False,
            'error': 'Unexpected error in retry loop',
            'cost_usd': total_cost
        }

    def _generate_test(
        self,
        task_description: str,
        task_scope: str,
        template: str,
        model: str
    ) -> Dict[str, Any]:
        """
        Generate test code using Claude API (rate limited).

        Args:
            task_description: Feature description
            task_scope: Task scope (may include feedback)
            template: Template content
            model: Model to use

        Returns:
            Dict with success, test_content, cost_usd
        """
        try:
            # Build prompt
            prompt = self._build_generation_prompt(
                task_description=task_description,
                task_scope=task_scope,
                template=template
            )

            # Call Anthropic API (rate limited)
            response = self.client.messages.create(
                model=model,
                max_tokens=4096,
                temperature=0.7,
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

            if model == self.HAIKU_MODEL:
                cost_usd = (
                    (input_tokens / 1000) * self.HAIKU_INPUT_COST +
                    (output_tokens / 1000) * self.HAIKU_OUTPUT_COST
                )
            else:  # SONNET_MODEL
                cost_usd = (
                    (input_tokens / 1000) * self.SONNET_INPUT_COST +
                    (output_tokens / 1000) * self.SONNET_OUTPUT_COST
                )

            # Extract test code from response
            response_text = response.content[0].text

            # Look for code block (between ```typescript and ```)
            code_match = re.search(
                r'```(?:typescript|ts)?\n(.*?)```',
                response_text,
                re.DOTALL
            )

            if not code_match:
                return {
                    'success': False,
                    'error': "Could not extract TypeScript code from AI response",
                    'cost_usd': cost_usd
                }

            test_content = code_match.group(1).strip()

            return {
                'success': True,
                'test_content': test_content,
                'cost_usd': cost_usd,
                'tokens': {
                    'input': input_tokens,
                    'output': output_tokens
                }
            }

        except Exception as e:
            return {
                'success': False,
                'error': f"AI generation failed: {str(e)}",
                'cost_usd': 0.0
            }

    def _build_generation_prompt(
        self,
        task_description: str,
        task_scope: str,
        template: str
    ) -> str:
        """
        Build prompt for test generation.

        Args:
            task_description: Feature description
            task_scope: Task scope (may include feedback)
            template: Template content

        Returns:
            Prompt string
        """
        prompt = f"""You are Scribe, an expert Playwright test writer. Generate a complete, production-ready test following these requirements:

TASK DESCRIPTION:
{task_description}

SCOPE/CONTEXT:
{task_scope if task_scope else "Standard feature testing"}

TEMPLATE (use as reference):
```typescript
{template}
```

REQUIREMENTS:
1. **Selectors**: ONLY use data-testid attributes via the S() helper
   - Example: await page.click(S('login-button'))
   - NEVER use: .nth(), CSS classes (.css-*), XPath, or text selectors

2. **Test Structure**:
   - Use test.describe() to group related tests
   - Include test.beforeEach() for setup
   - Generate at least 2 tests: happy path + error case

3. **Screenshots**:
   - Take screenshot after EACH major step
   - Use descriptive paths: 'artifacts/step-description.png'
   - Always use fullPage: true

4. **Assertions**:
   - MUST include expect() assertions (minimum 2 per test)
   - Test both visibility and content
   - Use toBeVisible(), toContainText(), toHaveValue(), etc.

5. **Waits**:
   - Use waitForSelector() instead of waitForTimeout()
   - Wait for elements before interacting
   - Add waits before screenshots for stability

6. **Configuration**:
   - Keep test.use() config from template
   - Use process.env.BASE_URL for navigation
   - Enable screenshots, videos, traces

7. **Anti-Patterns to AVOID**:
   - Index-based selectors: .nth()
   - Generated CSS classes: .css-*
   - Hard-coded URLs (use process.env.BASE_URL)
   - Hard-coded credentials (use process.env)
   - waitForTimeout (use waitForSelector)
   - Missing assertions

8. **Feature Name**:
   - Replace FEATURE_NAME with descriptive name from task
   - Use clear, descriptive test names

9. **Comments**:
   - Add step comments to explain what each section does
   - Keep comments concise and helpful

OUTPUT:
Return ONLY the complete TypeScript test file in a code block.
Do not include explanations outside the code block.

```typescript
// Your complete test here
```
"""
        return prompt

    def _validate_test(self, test_content: str) -> Dict[str, Any]:
        """
        Validate generated test for quality and correctness.

        Args:
            test_content: Generated test content

        Returns:
            Dict with valid (bool), issues (list), and detailed checks
        """
        issues = []
        checks = {}

        # Check 1: Has assertions
        assertion_count = len(re.findall(r'\bexpect\s*\(', test_content))
        checks['has_assertions'] = assertion_count > 0
        checks['assertion_count'] = assertion_count
        if assertion_count == 0:
            issues.append("No expect() assertions found")

        # Check 2: Uses data-testid selectors
        has_testid = bool(re.search(r'data-testid|S\(["\']', test_content))
        checks['uses_testid'] = has_testid
        if not has_testid:
            issues.append("No data-testid selectors found")

        # Check 3: No anti-patterns
        anti_patterns_found = []

        for pattern_def in self.ANTI_PATTERNS:
            pattern = pattern_def['pattern']
            reason = pattern_def['reason']
            flags = pattern_def.get('flags', 0)

            if re.search(pattern, test_content, flags):
                anti_patterns_found.append(reason)
                issues.append(f"Anti-pattern: {reason}")

        checks['anti_patterns'] = anti_patterns_found

        # Check 4: Has screenshots
        screenshot_count = len(re.findall(r'\.screenshot\(', test_content))
        checks['has_screenshots'] = screenshot_count > 0
        checks['screenshot_count'] = screenshot_count
        if screenshot_count == 0:
            issues.append("No screenshots found")

        # Check 5: TypeScript syntax (basic check)
        syntax_checks = self._check_typescript_syntax(test_content)
        checks['syntax_valid'] = syntax_checks['valid']
        if not syntax_checks['valid']:
            issues.extend(syntax_checks['errors'])

        # Check 6: Has test structure
        has_describe = bool(re.search(r'test\.describe\(', test_content))
        has_test = bool(re.search(r'test\(["\']', test_content))
        checks['has_structure'] = has_describe and has_test
        if not has_describe:
            issues.append("Missing test.describe() structure")
        if not has_test:
            issues.append("Missing test() definitions")

        # Determine overall validity
        valid = len(issues) == 0

        return {
            'valid': valid,
            'issues': issues,
            'checks': checks
        }

    def _check_typescript_syntax(self, code: str) -> Dict[str, Any]:
        """
        Check TypeScript syntax using basic checks.

        Args:
            code: TypeScript code to check

        Returns:
            Dict with valid (bool) and errors (list)
        """
        errors = []

        # Check for balanced braces
        open_braces = code.count('{')
        close_braces = code.count('}')
        if open_braces != close_braces:
            errors.append(f"Unbalanced braces: {open_braces} open, {close_braces} close")

        # Check for balanced parentheses
        open_parens = code.count('(')
        close_parens = code.count(')')
        if open_parens != close_parens:
            errors.append(f"Unbalanced parentheses: {open_parens} open, {close_parens} close")

        # Check for balanced brackets
        open_brackets = code.count('[')
        close_brackets = code.count(']')
        if open_brackets != close_brackets:
            errors.append(f"Unbalanced brackets: {open_brackets} open, {close_brackets} close")

        # Check for basic TypeScript/JavaScript structure
        if not re.search(r'import\s+.*from\s+["\']', code):
            errors.append("Missing import statement")

        # Check for async/await consistency
        async_functions = re.findall(r'async\s+\([^)]*\)\s*=>', code)
        if async_functions:
            has_await = bool(re.search(r'\bawait\s+', code))
            if not has_await:
                errors.append("Async function without await statements")

        return {
            'valid': len(errors) == 0,
            'errors': errors
        }

    def _generate_output_path(self, task_description: str) -> str:
        """
        Generate output path from task description.

        Args:
            task_description: Task description

        Returns:
            Relative path for test file
        """
        # Extract feature name from description
        # Convert to snake_case for file name
        feature_name = task_description.lower()

        # Remove common words
        feature_name = re.sub(r'\b(test|for|the|a|an)\b', '', feature_name)

        # Replace spaces and special chars with underscores
        feature_name = re.sub(r'[^a-z0-9]+', '_', feature_name)

        # Remove leading/trailing underscores
        feature_name = feature_name.strip('_')

        # Limit length
        feature_name = feature_name[:50]

        return f"tests/{feature_name}.spec.ts"


# CLI for testing
if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python scribe_full.py <task_description> [task_scope] [complexity]")
        print("Example: python scribe_full.py 'user login flow' 'authentication' 'hard'")
        sys.exit(1)

    task_description = sys.argv[1]
    task_scope = sys.argv[2] if len(sys.argv) > 2 else ""
    complexity = sys.argv[3] if len(sys.argv) > 3 else None

    scribe = ScribeAgent()
    result = scribe.execute(
        task_description=task_description,
        task_scope=task_scope,
        complexity=complexity
    )

    print(f"\n{'='*60}")
    print(f"Scribe Result: {'SUCCESS' if result.success else 'FAILURE'}")
    print(f"{'='*60}")
    print(f"Cost: ${result.cost_usd:.4f}")
    print(f"Time: {result.execution_time_ms}ms")

    if result.success:
        print(f"\nTest Path: {result.data['test_path']}")
        print(f"Model Used: {result.data['model_used']}")
        print(f"Complexity: {result.data['complexity']}")
        print(f"Retries Used: {result.data['retries_used']}")
        print(f"\nValidation:")
        validation = result.data['validation']
        print(f"  - Assertions: {validation['checks']['assertion_count']}")
        print(f"  - Screenshots: {validation['checks']['screenshot_count']}")
        print(f"  - Uses data-testid: {validation['checks']['uses_testid']}")
        print(f"  - Syntax valid: {validation['checks']['syntax_valid']}")
        if validation['checks']['anti_patterns']:
            print(f"  - Anti-patterns: {', '.join(validation['checks']['anti_patterns'])}")
    else:
        print(f"\nError: {result.error}")
        if result.data and 'validation' in result.data:
            print(f"Validation issues: {result.data['validation']['issues']}")

    print(f"{'='*60}\n")
