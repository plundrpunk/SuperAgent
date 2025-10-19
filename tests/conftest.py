"""
pytest configuration and shared fixtures for SuperAgent tests.
"""
import pytest
from unittest.mock import Mock, MagicMock
import json
import tempfile
import os


@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    redis_mock = Mock()
    redis_mock.get = Mock(return_value=None)
    redis_mock.set = Mock(return_value=True)
    redis_mock.delete = Mock(return_value=True)
    redis_mock.keys = Mock(return_value=[])
    redis_mock.expire = Mock(return_value=True)
    redis_mock.ping = Mock(return_value=True)
    return redis_mock


@pytest.fixture
def mock_vector_db():
    """Mock Vector DB client for testing."""
    vector_mock = Mock()
    vector_mock.add = Mock(return_value=True)
    vector_mock.query = Mock(return_value=[])
    vector_mock.delete = Mock(return_value=True)
    vector_mock.create_collection = Mock(return_value=True)
    return vector_mock


@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic API client."""
    client_mock = Mock()
    response_mock = Mock()
    response_mock.content = [Mock(text="Generated test code")]
    response_mock.usage = Mock(input_tokens=100, output_tokens=200)
    client_mock.messages.create = Mock(return_value=response_mock)
    return client_mock


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI API client."""
    client_mock = Mock()
    return client_mock


@pytest.fixture
def sample_task():
    """Sample task for testing."""
    return {
        "task_id": "test_task_123",
        "description": "Write a test for user login with email and password",
        "feature": "authentication",
        "scope": "happy path"
    }


@pytest.fixture
def sample_test_result():
    """Sample test execution result."""
    return {
        "browser_launched": True,
        "test_executed": True,
        "test_passed": True,
        "screenshots": ["/path/to/screenshot1.png"],
        "console_errors": [],
        "network_failures": [],
        "execution_time_ms": 3500
    }


@pytest.fixture
def temp_test_file():
    """Create a temporary test file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.spec.ts', delete=False) as f:
        f.write("""
import { test, expect } from '@playwright/test';

test('sample test', async ({ page }) => {
    await page.goto('https://example.com');
    await expect(page).toHaveTitle(/Example/);
});
""")
        temp_path = f.name

    yield temp_path

    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def mock_subprocess():
    """Mock subprocess for test execution."""
    process_mock = Mock()
    process_mock.returncode = 0
    process_mock.stdout = "1 passed"
    process_mock.stderr = ""
    return process_mock


@pytest.fixture
def sample_playwright_output():
    """Sample Playwright test output."""
    return """
Running 1 test using 1 worker

  ✓  login.spec.ts:5:1 › user login happy path (3.2s)

  1 passed (3.2s)
"""


@pytest.fixture
def sample_playwright_failure():
    """Sample Playwright test failure output."""
    return """
Running 1 test using 1 worker

  ✗  login.spec.ts:5:1 › user login happy path (2.1s)

    Error: Locator [data-testid="login-button"] not found

      at login.spec.ts:12:40

  1 failed (2.1s)
"""
