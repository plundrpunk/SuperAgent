"""
pytest configuration for E2E tests.

Sets up mock environment variables and shared fixtures for E2E testing.
"""
import pytest
import os
from unittest.mock import Mock, patch


@pytest.fixture(autouse=True)
def mock_environment(monkeypatch):
    """Mock environment variables for all E2E tests."""
    # Mock API keys to allow agent initialization
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'mock-key-for-testing')
    monkeypatch.setenv('OPENAI_API_KEY', 'mock-key-for-testing')
    monkeypatch.setenv('GEMINI_API_KEY', 'mock-key-for-testing')

    # Mock Redis/DB URLs if needed
    monkeypatch.setenv('REDIS_HOST', 'localhost')
    monkeypatch.setenv('REDIS_PORT', '6379')


@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client for Medic and Scribe tests."""
    client_mock = Mock()
    response_mock = Mock()
    response_mock.content = [Mock(text="Generated test code")]
    response_mock.usage = Mock(input_tokens=100, output_tokens=200)
    client_mock.messages.create = Mock(return_value=response_mock)
    return client_mock
