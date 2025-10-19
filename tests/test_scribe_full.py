"""
Comprehensive unit tests for Scribe Agent (scribe_full.py)

Test Coverage:
1. Model selection (easy→Haiku, hard→Sonnet based on complexity)
2. Template loading from tests/templates/playwright.template.ts
3. Test generation with mocked Anthropic API
4. Self-validation against Critic criteria
5. Retry logic (max 3 attempts with feedback)
6. Cost tracking (input/output tokens, total cost)
7. Test with various task complexities

Reference implementations:
- tests/test_gemini_agent.py (18 tests, 92% coverage)
- tests/test_medic.py (17 tests passing)
"""
import pytest
import re
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open
from agent_system.agents.scribe_full import ScribeAgent
from agent_system.agents.base_agent import AgentResult
from agent_system.complexity_estimator import ComplexityScore


@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client for API calls."""
    with patch('agent_system.agents.scribe_full.Anthropic') as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_env():
    """Mock environment variables."""
    with patch('agent_system.agents.scribe_full.os.getenv') as mock_getenv:
        mock_getenv.return_value = 'fake-api-key-for-testing'
        yield mock_getenv


@pytest.fixture
def scribe_agent(mock_anthropic_client, mock_env):
    """Create ScribeAgent instance with mocked dependencies."""
    agent = ScribeAgent()
    agent.client = mock_anthropic_client
    return agent


@pytest.fixture
def sample_template():
    """Sample Playwright template content."""
    return r"""import { test, expect } from '@playwright/test';

const S = (id: string) => \`[data-testid="\${id}"]\`;

test.use({
  screenshot: 'on',
  video: 'retain-on-failure',
  trace: 'retain-on-failure',
});

test.describe('FEATURE_NAME', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(process.env.BASE_URL || 'http://localhost:3000');
  });

  test('happy path', async ({ page }) => {
    await page.click(S('button'));
    await page.screenshot({ path: 'artifacts/step1.png', fullPage: true });
    await expect(page.locator(S('result'))).toBeVisible();
  });
});
"""


@pytest.fixture
def valid_generated_test():
    """Valid generated test content that passes validation."""
    return r"""import { test, expect } from '@playwright/test';

const S = (id: string) => \`[data-testid="\${id}"]\`;

test.use({
  screenshot: 'on',
  video: 'retain-on-failure',
  trace: 'retain-on-failure',
});

test.describe('Login Feature', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(process.env.BASE_URL || 'http://localhost:3000');
  });

  test('happy path - user login', async ({ page }) => {
    // Step 1: Navigate to login
    await page.click(S('login-button'));
    await page.screenshot({ path: 'artifacts/step1.png', fullPage: true });

    // Step 2: Fill credentials
    await page.fill(S('username-input'), 'testuser');
    await page.fill(S('password-input'), 'password123');
    await page.screenshot({ path: 'artifacts/step2.png', fullPage: true });

    // Step 3: Submit
    await page.click(S('submit-button'));
    await page.waitForSelector(S('dashboard'));
    await page.screenshot({ path: 'artifacts/step3.png', fullPage: true });

    // Assertions
    await expect(page.locator(S('dashboard'))).toBeVisible();
    await expect(page.locator(S('welcome-message'))).toContainText('Welcome');
  });

  test('error case - invalid credentials', async ({ page }) => {
    await page.click(S('login-button'));
    await page.fill(S('username-input'), 'invalid');
    await page.fill(S('password-input'), 'wrong');
    await page.click(S('submit-button'));
    await page.screenshot({ path: 'artifacts/error.png', fullPage: true });

    await expect(page.locator(S('error-message'))).toBeVisible();
    await expect(page.locator(S('error-message'))).toContainText('Invalid');
  });
});
"""


@pytest.fixture
def invalid_generated_test_no_assertions():
    """Invalid test - missing assertions."""
    return r"""import { test, expect } from '@playwright/test';

test('login test', async ({ page }) => {
  await page.goto('http://localhost:3000');
  await page.click('[data-testid="login-button"]');
  await page.screenshot({ path: 'artifacts/step1.png', fullPage: true });
});
"""


@pytest.fixture
def invalid_generated_test_anti_patterns():
    """Invalid test - contains anti-patterns."""
    return r"""import { test, expect } from '@playwright/test';

const S = (id: string) => \`[data-testid="\${id}"]\`;

test('login test', async ({ page }) => {
  await page.goto('http://localhost:3000');
  await page.locator('.css-abc123').nth(2).click();
  await page.waitForTimeout(5000);
  await page.screenshot({ path: 'artifacts/step1.png', fullPage: true });
  await expect(page.locator(S('result'))).toBeVisible();
});
"""


class TestScribeAgentInitialization:
    """Test Scribe agent initialization."""

    def test_initialization(self, scribe_agent):
        """Test agent initializes correctly."""
        assert scribe_agent.name == 'scribe'
        assert scribe_agent.client is not None
        assert scribe_agent.complexity_estimator is not None
        assert scribe_agent.HAIKU_MODEL == "claude-haiku-4-20250612"
        assert scribe_agent.SONNET_MODEL == "claude-sonnet-4-20250514"

    def test_initialization_without_api_key(self, mock_anthropic_client):
        """Test initialization fails without API key."""
        with patch('agent_system.agents.scribe_full.os.getenv') as mock_getenv:
            mock_getenv.return_value = None
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY not found"):
                ScribeAgent()

    def test_cost_constants(self, scribe_agent):
        """Test cost constants are defined correctly."""
        assert scribe_agent.HAIKU_INPUT_COST == 0.0008
        assert scribe_agent.HAIKU_OUTPUT_COST == 0.004
        assert scribe_agent.SONNET_INPUT_COST == 0.003
        assert scribe_agent.SONNET_OUTPUT_COST == 0.015

    def test_anti_patterns_defined(self, scribe_agent):
        """Test anti-patterns are defined."""
        assert len(scribe_agent.ANTI_PATTERNS) > 0
        assert any('nth' in str(p['pattern']) for p in scribe_agent.ANTI_PATTERNS)
        assert any('css-' in str(p['pattern']) for p in scribe_agent.ANTI_PATTERNS)
        assert any('waitForTimeout' in str(p['pattern']) for p in scribe_agent.ANTI_PATTERNS)


class TestScribeModelSelection:
    """Test model selection based on complexity."""

    def test_easy_task_selects_haiku(self, scribe_agent, sample_template, valid_generated_test):
        """Test easy task uses Haiku model."""
        # Mock template loading
        with patch.object(scribe_agent, '_load_template', return_value=sample_template):
            # Mock API response
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text=f"```typescript\n{valid_generated_test}\n```")]
            mock_response.usage = MagicMock(input_tokens=500, output_tokens=1000)
            scribe_agent.client.messages.create.return_value = mock_response

            # Mock complexity estimator to return easy
            with patch.object(scribe_agent.complexity_estimator, 'estimate') as mock_estimate:
                mock_estimate.return_value = ComplexityScore(
                    score=2,
                    difficulty="easy",
                    model_recommendation="haiku",
                    breakdown={'steps': 2}
                )

                result = scribe_agent.execute(
                    task_description="Simple button click test",
                    task_scope="Basic navigation"
                )

                # Verify Haiku was selected
                call_args = scribe_agent.client.messages.create.call_args
                assert call_args[1]['model'] == scribe_agent.HAIKU_MODEL

    def test_hard_task_selects_sonnet(self, scribe_agent, sample_template, valid_generated_test):
        """Test hard task uses Sonnet model."""
        with patch.object(scribe_agent, '_load_template', return_value=sample_template):
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text=f"```typescript\n{valid_generated_test}\n```")]
            mock_response.usage = MagicMock(input_tokens=500, output_tokens=1000)
            scribe_agent.client.messages.create.return_value = mock_response

            # Mock complexity estimator to return hard
            with patch.object(scribe_agent.complexity_estimator, 'estimate') as mock_estimate:
                mock_estimate.return_value = ComplexityScore(
                    score=7,
                    difficulty="hard",
                    model_recommendation="sonnet",
                    breakdown={'auth': 3, 'payment': 4}
                )

                result = scribe_agent.execute(
                    task_description="OAuth authentication with payment flow",
                    task_scope="Multi-step checkout process"
                )

                # Verify Sonnet was selected
                call_args = scribe_agent.client.messages.create.call_args
                assert call_args[1]['model'] == scribe_agent.SONNET_MODEL

    def test_manual_complexity_override(self, scribe_agent, sample_template, valid_generated_test):
        """Test manual complexity override."""
        with patch.object(scribe_agent, '_load_template', return_value=sample_template):
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text=f"```typescript\n{valid_generated_test}\n```")]
            mock_response.usage = MagicMock(input_tokens=500, output_tokens=1000)
            scribe_agent.client.messages.create.return_value = mock_response

            # Override to "hard" manually
            result = scribe_agent.execute(
                task_description="Simple task",
                complexity="hard"
            )

            # Verify Sonnet was used despite simple description
            call_args = scribe_agent.client.messages.create.call_args
            assert call_args[1]['model'] == scribe_agent.SONNET_MODEL


class TestScribeTemplateLoading:
    """Test template loading functionality."""

    def test_load_template_success(self, scribe_agent, sample_template):
        """Test successful template loading."""
        template_path = scribe_agent.project_root / scribe_agent.TEMPLATE_PATH

        with patch('builtins.open', mock_open(read_data=sample_template)):
            content = scribe_agent._load_template()
            assert content == sample_template
            assert 'data-testid' in content
            assert 'test.describe' in content

    def test_load_template_file_not_found(self, scribe_agent):
        """Test template loading fails gracefully."""
        with patch('builtins.open', side_effect=FileNotFoundError):
            content = scribe_agent._load_template()
            assert content is None

    def test_execute_fails_without_template(self, scribe_agent):
        """Test execute fails if template cannot be loaded."""
        with patch.object(scribe_agent, '_load_template', return_value=None):
            result = scribe_agent.execute(
                task_description="Test task",
                task_scope="Test scope"
            )

            assert result.success is False
            assert "template" in result.error.lower()


class TestScribeTestGeneration:
    """Test AI test generation."""

    def test_generate_test_success(self, scribe_agent, sample_template, valid_generated_test):
        """Test successful test generation."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=f"```typescript\n{valid_generated_test}\n```")]
        mock_response.usage = MagicMock(input_tokens=500, output_tokens=1000)
        scribe_agent.client.messages.create.return_value = mock_response

        result = scribe_agent._generate_test(
            task_description="User login",
            task_scope="Authentication",
            template=sample_template,
            model=scribe_agent.HAIKU_MODEL
        )

        assert result['success'] is True
        assert 'test_content' in result
        assert 'cost_usd' in result
        assert result['test_content'] == valid_generated_test

    def test_generate_test_extracts_code_from_markdown(self, scribe_agent, sample_template):
        """Test code extraction from markdown code blocks."""
        code = "import { test } from '@playwright/test';"
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=f"Here's the test:\n```typescript\n{code}\n```\nEnjoy!")]
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)
        scribe_agent.client.messages.create.return_value = mock_response

        result = scribe_agent._generate_test(
            task_description="Test",
            task_scope="",
            template="template",
            model=scribe_agent.HAIKU_MODEL
        )

        assert result['success'] is True
        assert result['test_content'] == code

    def test_generate_test_no_code_block(self, scribe_agent, sample_template):
        """Test generation fails if no code block found."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Just some text without code blocks")]
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)
        scribe_agent.client.messages.create.return_value = mock_response

        result = scribe_agent._generate_test(
            task_description="Test",
            task_scope="",
            template=sample_template,
            model=scribe_agent.HAIKU_MODEL
        )

        assert result['success'] is False
        assert "extract TypeScript code" in result['error']

    def test_generate_test_api_error(self, scribe_agent, sample_template):
        """Test generation handles API errors."""
        scribe_agent.client.messages.create.side_effect = Exception("API error")

        result = scribe_agent._generate_test(
            task_description="Test",
            task_scope="",
            template=sample_template,
            model=scribe_agent.HAIKU_MODEL
        )

        assert result['success'] is False
        assert "AI generation failed" in result['error']


class TestScribeValidation:
    """Test self-validation against Critic criteria."""

    def test_validate_test_success(self, scribe_agent, valid_generated_test):
        """Test validation passes for valid test."""
        result = scribe_agent._validate_test(valid_generated_test)

        assert result['valid'] is True
        assert len(result['issues']) == 0
        assert result['checks']['has_assertions'] is True
        assert result['checks']['uses_testid'] is True
        assert result['checks']['has_screenshots'] is True
        assert result['checks']['syntax_valid'] is True
        assert result['checks']['has_structure'] is True
        assert result['checks']['assertion_count'] >= 2

    def test_validate_test_no_assertions(self, scribe_agent, invalid_generated_test_no_assertions):
        """Test validation fails without assertions."""
        result = scribe_agent._validate_test(invalid_generated_test_no_assertions)

        assert result['valid'] is False
        assert any('assertion' in issue.lower() for issue in result['issues'])
        assert result['checks']['has_assertions'] is False

    def test_validate_test_anti_patterns(self, scribe_agent, invalid_generated_test_anti_patterns):
        """Test validation detects anti-patterns."""
        result = scribe_agent._validate_test(invalid_generated_test_anti_patterns)

        assert result['valid'] is False
        assert len(result['checks']['anti_patterns']) > 0
        assert any('.nth()' in issue or 'Index-based' in issue for issue in result['issues'])
        assert any('waitForTimeout' in issue or 'waitForSelector' in issue for issue in result['issues'])

    def test_validate_test_no_testid_selectors(self, scribe_agent):
        """Test validation fails without data-testid selectors."""
        test_without_testid = """import { test, expect } from '@playwright/test';
test('test', async ({ page }) => {
  await page.click('.my-button');
  await page.screenshot({ path: 'artifacts/step1.png', fullPage: true });
  await expect(page.locator('.result')).toBeVisible();
});
"""
        result = scribe_agent._validate_test(test_without_testid)

        assert result['valid'] is False
        assert any('data-testid' in issue.lower() for issue in result['issues'])

    def test_validate_test_no_screenshots(self, scribe_agent):
        """Test validation fails without screenshots."""
        test_without_screenshots = """import { test, expect } from '@playwright/test';
const S = (id: string) => \`[data-testid="\${id}"]\`;
test.describe('Test', () => {
  test('test', async ({ page }) => {
    await page.click(S('button'));
    await expect(page.locator(S('result'))).toBeVisible();
  });
});
"""
        result = scribe_agent._validate_test(test_without_screenshots)

        assert result['valid'] is False
        assert any('screenshot' in issue.lower() for issue in result['issues'])

    def test_validate_test_no_test_structure(self, scribe_agent):
        """Test validation fails without proper test structure."""
        test_without_structure = """import { test, expect } from '@playwright/test';
const S = (id: string) => \`[data-testid="\${id}"]\`;
console.log('not a test');
"""
        result = scribe_agent._validate_test(test_without_structure)

        assert result['valid'] is False
        assert any('test.describe' in issue or 'test()' in issue for issue in result['issues'])


class TestScribeRetryLogic:
    """Test retry logic with validation feedback."""

    def test_retry_succeeds_on_first_attempt(self, scribe_agent, sample_template, valid_generated_test):
        """Test successful generation on first attempt."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=f"```typescript\n{valid_generated_test}\n```")]
        mock_response.usage = MagicMock(input_tokens=500, output_tokens=1000)
        scribe_agent.client.messages.create.return_value = mock_response

        result = scribe_agent._generate_with_retry(
            task_description="User login",
            task_scope="Authentication",
            template=sample_template,
            model=scribe_agent.HAIKU_MODEL,
            max_retries=3
        )

        assert result['success'] is True
        assert result['retries_used'] == 0
        assert scribe_agent.client.messages.create.call_count == 1

    def test_retry_succeeds_on_second_attempt(self, scribe_agent, sample_template,
                                               invalid_generated_test_no_assertions,
                                               valid_generated_test):
        """Test successful generation on second attempt after feedback."""
        # First call returns invalid test, second returns valid
        mock_response_1 = MagicMock()
        mock_response_1.content = [MagicMock(text=f"```typescript\n{invalid_generated_test_no_assertions}\n```")]
        mock_response_1.usage = MagicMock(input_tokens=500, output_tokens=1000)

        mock_response_2 = MagicMock()
        mock_response_2.content = [MagicMock(text=f"```typescript\n{valid_generated_test}\n```")]
        mock_response_2.usage = MagicMock(input_tokens=600, output_tokens=1200)

        scribe_agent.client.messages.create.side_effect = [mock_response_1, mock_response_2]

        result = scribe_agent._generate_with_retry(
            task_description="User login",
            task_scope="Authentication",
            template=sample_template,
            model=scribe_agent.HAIKU_MODEL,
            max_retries=3
        )

        assert result['success'] is True
        assert result['retries_used'] == 1
        assert scribe_agent.client.messages.create.call_count == 2

        # Verify feedback was added to prompt on second attempt
        second_call_prompt = scribe_agent.client.messages.create.call_args_list[1][1]['messages'][0]['content']
        assert 'PREVIOUS ATTEMPT FAILED' in second_call_prompt
        assert 'FIX THESE ISSUES' in second_call_prompt

    def test_retry_fails_after_max_attempts(self, scribe_agent, sample_template,
                                            invalid_generated_test_no_assertions):
        """Test retry fails after max attempts."""
        # All attempts return invalid test
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=f"```typescript\n{invalid_generated_test_no_assertions}\n```")]
        mock_response.usage = MagicMock(input_tokens=500, output_tokens=1000)
        scribe_agent.client.messages.create.return_value = mock_response

        result = scribe_agent._generate_with_retry(
            task_description="User login",
            task_scope="Authentication",
            template=sample_template,
            model=scribe_agent.HAIKU_MODEL,
            max_retries=3
        )

        assert result['success'] is False
        assert "failed validation after 3 attempts" in result['error']
        assert scribe_agent.client.messages.create.call_count == 3
        assert 'validation' in result['data']

    def test_retry_accumulates_cost(self, scribe_agent, sample_template, valid_generated_test):
        """Test cost accumulates across retry attempts."""
        # Two attempts before success
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=f"```typescript\n{valid_generated_test}\n```")]
        mock_response.usage = MagicMock(input_tokens=500, output_tokens=1000)
        scribe_agent.client.messages.create.return_value = mock_response

        # Force one retry by mocking validation to fail once
        with patch.object(scribe_agent, '_validate_test') as mock_validate:
            mock_validate.side_effect = [
                {'valid': False, 'issues': ['Missing assertions'], 'checks': {}},
                {'valid': True, 'issues': [], 'checks': {
                    'has_assertions': True, 'uses_testid': True, 'has_screenshots': True,
                    'syntax_valid': True, 'has_structure': True, 'assertion_count': 2,
                    'screenshot_count': 2, 'anti_patterns': []
                }}
            ]

            result = scribe_agent._generate_with_retry(
                task_description="Test",
                task_scope="",
                template=sample_template,
                model=scribe_agent.HAIKU_MODEL,
                max_retries=3
            )

            # Cost should be doubled (2 API calls)
            expected_cost = 2 * ((500 / 1000) * scribe_agent.HAIKU_INPUT_COST +
                               (1000 / 1000) * scribe_agent.HAIKU_OUTPUT_COST)
            assert abs(result['cost_usd'] - expected_cost) < 0.0001


class TestScribeCostTracking:
    """Test cost tracking and calculation."""

    def test_cost_calculation_haiku(self, scribe_agent):
        """Test cost calculation for Haiku model."""
        input_tokens = 1000
        output_tokens = 2000

        expected_cost = (
            (input_tokens / 1000) * scribe_agent.HAIKU_INPUT_COST +
            (output_tokens / 1000) * scribe_agent.HAIKU_OUTPUT_COST
        )

        # Expected: (1000/1000)*0.0008 + (2000/1000)*0.004 = 0.0008 + 0.008 = 0.0088
        assert abs(expected_cost - 0.0088) < 0.0001

    def test_cost_calculation_sonnet(self, scribe_agent):
        """Test cost calculation for Sonnet model."""
        input_tokens = 1000
        output_tokens = 2000

        expected_cost = (
            (input_tokens / 1000) * scribe_agent.SONNET_INPUT_COST +
            (output_tokens / 1000) * scribe_agent.SONNET_OUTPUT_COST
        )

        # Expected: (1000/1000)*0.003 + (2000/1000)*0.015 = 0.003 + 0.030 = 0.033
        assert abs(expected_cost - 0.033) < 0.0001

    def test_end_to_end_cost_tracking(self, scribe_agent, sample_template, valid_generated_test):
        """Test end-to-end cost tracking in execute()."""
        with patch.object(scribe_agent, '_load_template', return_value=sample_template):
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text=f"```typescript\n{valid_generated_test}\n```")]
            mock_response.usage = MagicMock(input_tokens=500, output_tokens=1000)
            scribe_agent.client.messages.create.return_value = mock_response

            result = scribe_agent.execute(
                task_description="User login",
                complexity="easy"
            )

            assert result.success is True
            assert result.cost_usd > 0
            expected_cost = (500 / 1000) * scribe_agent.HAIKU_INPUT_COST + (1000 / 1000) * scribe_agent.HAIKU_OUTPUT_COST
            assert abs(result.cost_usd - expected_cost) < 0.0001


class TestScribeSyntaxValidation:
    """Test TypeScript syntax validation."""

    def test_check_typescript_syntax_valid(self, scribe_agent):
        """Test syntax check passes for valid code."""
        valid_code = """import { test, expect } from '@playwright/test';

test('test', async ({ page }) => {
  await page.goto('http://example.com');
  await expect(page).toHaveTitle(/Example/);
});
"""
        result = scribe_agent._check_typescript_syntax(valid_code)
        assert result['valid'] is True
        assert len(result['errors']) == 0

    def test_check_typescript_syntax_unbalanced_braces(self, scribe_agent):
        """Test syntax check detects unbalanced braces."""
        invalid_code = """test('test', async ({ page }) => {
  await page.goto('url');
  // Missing closing brace
"""
        result = scribe_agent._check_typescript_syntax(invalid_code)
        assert result['valid'] is False
        assert any('brace' in error.lower() for error in result['errors'])

    def test_check_typescript_syntax_unbalanced_parentheses(self, scribe_agent):
        """Test syntax check detects unbalanced parentheses."""
        invalid_code = """test('test', async ({ page } => {
  await page.click('button');
});
"""
        result = scribe_agent._check_typescript_syntax(invalid_code)
        assert result['valid'] is False
        assert any('parenthes' in error.lower() for error in result['errors'])

    def test_check_typescript_syntax_missing_import(self, scribe_agent):
        """Test syntax check detects missing import."""
        invalid_code = """test('test', async ({ page }) => {
  await page.goto('url');
});
"""
        result = scribe_agent._check_typescript_syntax(invalid_code)
        assert result['valid'] is False
        assert any('import' in error.lower() for error in result['errors'])


class TestScribeOutputPath:
    """Test output path generation."""

    def test_generate_output_path_basic(self, scribe_agent):
        """Test basic output path generation."""
        path = scribe_agent._generate_output_path("User login test")
        assert path == "tests/user_login.spec.ts"

    def test_generate_output_path_removes_common_words(self, scribe_agent):
        """Test common words are removed from path."""
        path = scribe_agent._generate_output_path("Test for the login feature")
        assert "for" not in path
        assert "the" not in path

    def test_generate_output_path_handles_special_chars(self, scribe_agent):
        """Test special characters are handled."""
        path = scribe_agent._generate_output_path("User's login & authentication!")
        assert "&" not in path
        assert "!" not in path

    def test_generate_output_path_length_limit(self, scribe_agent):
        """Test path length is limited."""
        long_description = "A very long task description that goes on and on with many words " * 5
        path = scribe_agent._generate_output_path(long_description)
        filename = path.replace("tests/", "").replace(".spec.ts", "")
        assert len(filename) <= 50


class TestScribeIntegration:
    """Integration tests for full execute workflow."""

    def test_execute_success_full_workflow(self, scribe_agent, sample_template, valid_generated_test, tmp_path):
        """Test successful end-to-end execution."""
        with patch.object(scribe_agent, '_load_template', return_value=sample_template):
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text=f"```typescript\n{valid_generated_test}\n```")]
            mock_response.usage = MagicMock(input_tokens=500, output_tokens=1000)
            scribe_agent.client.messages.create.return_value = mock_response

            # Override project_root to use tmp_path
            scribe_agent.project_root = tmp_path

            output_path = "tests/login_test.spec.ts"
            result = scribe_agent.execute(
                task_description="User login flow",
                task_scope="Authentication feature",
                complexity="easy",
                output_path=output_path
            )

            assert result.success is True
            assert result.data['test_path'] == str(tmp_path / output_path)
            assert result.data['model_used'] == scribe_agent.HAIKU_MODEL
            assert result.data['complexity'] == "easy"
            assert result.data['validation']['valid'] is True
            assert result.cost_usd > 0
            assert result.execution_time_ms >= 0

            # Verify file was written
            test_file = tmp_path / output_path
            assert test_file.exists()
            assert valid_generated_test in test_file.read_text()

    def test_execute_with_auto_generated_path(self, scribe_agent, sample_template, valid_generated_test, tmp_path):
        """Test execute with auto-generated output path."""
        with patch.object(scribe_agent, '_load_template', return_value=sample_template):
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text=f"```typescript\n{valid_generated_test}\n```")]
            mock_response.usage = MagicMock(input_tokens=500, output_tokens=1000)
            scribe_agent.client.messages.create.return_value = mock_response

            scribe_agent.project_root = tmp_path

            result = scribe_agent.execute(
                task_description="Shopping cart checkout",
                complexity="easy"
            )

            assert result.success is True
            assert "shopping_cart_checkout" in result.data['test_path']
            assert result.data['test_path'].endswith(".spec.ts")

    def test_execute_metadata_populated(self, scribe_agent, sample_template, valid_generated_test):
        """Test metadata is populated correctly."""
        with patch.object(scribe_agent, '_load_template', return_value=sample_template):
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text=f"```typescript\n{valid_generated_test}\n```")]
            mock_response.usage = MagicMock(input_tokens=500, output_tokens=1000)
            scribe_agent.client.messages.create.return_value = mock_response

            result = scribe_agent.execute(
                task_description="User profile update",
                task_scope="Settings page"
            )

            assert result.success is True
            assert result.metadata['feature_description'] == "User profile update"
            assert result.metadata['scope'] == "Settings page"
            assert result.metadata['line_count'] > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
