"""
Unit tests for Voice Intent Parser

Tests intent classification, slot extraction, ambiguity handling,
and edge cases for all supported voice command intents.
"""

import pytest
from agent_system.voice.intent_parser import (
    IntentParser,
    VoiceIntent,
    parse_voice_command
)


class TestIntentParser:
    """Test suite for IntentParser class."""

    @pytest.fixture
    def parser(self):
        """Provide a fresh IntentParser instance for each test."""
        return IntentParser()


class TestCreateTestIntent(TestIntentParser):
    """Test CREATE_TEST intent parsing and slot extraction."""

    def test_write_test_for_pattern(self, parser):
        """Test 'write a test for X' pattern."""
        result = parser.parse("Kaya, write a test for user login")
        assert result.type == "create_test"
        assert result.slots["feature"] == "user login"
        assert result.confidence == 0.9
        assert not result.needs_clarification

    def test_create_test_for_pattern(self, parser):
        """Test 'create a test for X' pattern."""
        result = parser.parse("create a test for checkout happy path")
        assert result.type == "create_test"
        assert result.slots["feature"] == "checkout happy path"
        assert result.confidence == 0.9

    def test_generate_test_about_pattern(self, parser):
        """Test 'generate a test about X' pattern."""
        result = parser.parse("generate a test about password reset")
        assert result.type == "create_test"
        assert result.slots["feature"] == "password reset"

    def test_test_the_feature_pattern(self, parser):
        """Test 'write test for X feature' pattern."""
        # Use proper phrasing with "for" keyword
        result = parser.parse("write a test for the shopping cart feature")
        assert result.type == "create_test"
        assert "shopping cart" in result.slots["feature"]

    def test_create_test_with_scope(self, parser):
        """Test scope extraction from feature description."""
        result = parser.parse("write a test for user login scope: happy path")
        assert result.type == "create_test"
        assert result.slots["feature"] == "user login"
        assert "scope" in result.slots
        assert result.slots["scope"] == "happy path"

    def test_create_test_case_insensitive(self, parser):
        """Test case-insensitive matching."""
        result = parser.parse("WRITE A TEST FOR USER LOGIN")
        assert result.type == "create_test"
        assert result.slots["feature"] == "user login"

    def test_create_test_without_kaya_prefix(self, parser):
        """Test parsing without 'Kaya' prefix."""
        result = parser.parse("create test for authentication")
        assert result.type == "create_test"
        assert result.slots["feature"] == "authentication"


class TestRunTestIntent(TestIntentParser):
    """Test RUN_TEST intent parsing and slot extraction."""

    def test_run_test_with_spec_file(self, parser):
        """Test running a specific .spec.ts file."""
        result = parser.parse("Kaya, run tests/cart.spec.ts")
        assert result.type == "run_test"
        assert result.slots["test_path"] == "tests/cart.spec.ts"
        assert result.confidence == 0.9

    def test_execute_the_test(self, parser):
        """Test 'execute the X test' pattern."""
        result = parser.parse("execute the login test")
        assert result.type == "run_test"
        # Pattern captures "the login" from "execute the (the login) test"
        assert "login" in result.slots["test_path"]

    def test_run_all_tests_pattern(self, parser):
        """Test 'run all X tests' pattern."""
        result = parser.parse("run all authentication tests")
        assert result.type == "run_test"
        assert result.slots["test_path"] == "authentication"

    def test_start_test_pattern(self, parser):
        """Test 'start X test' pattern."""
        result = parser.parse("start the checkout test")
        assert result.type == "run_test"
        # Pattern captures "the checkout" from "start the (the checkout) test"
        assert "checkout" in result.slots["test_path"]

    def test_run_test_without_extension(self, parser):
        """Test running test with partial path."""
        result = parser.parse("run tests/auth")
        assert result.type == "run_test"
        # Should normalize path to include .spec.ts
        assert result.slots["test_path"] == "tests/auth.spec.ts"

    def test_run_multiple_tests(self, parser):
        """Test running multiple tests."""
        result = parser.parse("run the authentication tests")
        assert result.type == "run_test"
        assert "authentication" in result.slots["test_path"]


class TestFixFailureIntent(TestIntentParser):
    """Test FIX_FAILURE intent parsing and slot extraction."""

    def test_fix_task_with_id(self, parser):
        """Test 'fix task X' with task ID."""
        result = parser.parse("Kaya, fix task t_abc123")
        assert result.type == "fix_failure"
        assert result.slots["task_id"] == "t_abc123"
        assert result.confidence == 0.9

    def test_patch_task_and_retry(self, parser):
        """Test 'patch task X and retry' pattern."""
        result = parser.parse("patch task t_xyz789 and retry")
        assert result.type == "fix_failure"
        assert result.slots["task_id"] == "t_xyz789"

    def test_repair_failed_test(self, parser):
        """Test 'repair the failed X test' pattern."""
        result = parser.parse("repair the failed checkout test")
        assert result.type == "fix_failure"
        assert result.slots["task_id"] == "checkout"

    def test_fix_failure_in_feature(self, parser):
        """Test 'fix the failure in X' pattern."""
        result = parser.parse("fix the failure in login")
        assert result.type == "fix_failure"
        assert result.slots["task_id"] == "login"

    def test_fix_with_underscore_id(self, parser):
        """Test task ID with underscores."""
        result = parser.parse("fix task t_user_login_123")
        assert result.type == "fix_failure"
        assert result.slots["task_id"] == "t_user_login_123"


class TestValidateIntent(TestIntentParser):
    """Test VALIDATE intent parsing and slot extraction."""

    def test_validate_with_critical_flag(self, parser):
        """Test validate with 'critical' priority."""
        result = parser.parse("Kaya, validate payment flow - critical")
        assert result.type == "validate"
        assert result.slots["test_path"] == "payment flow"
        assert result.slots.get("high_priority") == "true"
        assert result.confidence == 0.9

    def test_verify_test(self, parser):
        """Test 'verify the X test' pattern."""
        result = parser.parse("verify the login test")
        assert result.type == "validate"
        assert result.slots["test_path"] == "login test"

    def test_validate_with_gemini(self, parser):
        """Test 'validate X with Gemini' pattern."""
        result = parser.parse("validate checkout with Gemini")
        assert result.type == "validate"
        assert result.slots["test_path"] == "checkout"

    def test_check_test_pattern(self, parser):
        """Test 'check the X test' pattern."""
        result = parser.parse("check the authentication test")
        assert result.type == "validate"
        assert result.slots["test_path"] == "authentication test"

    def test_validate_important_priority(self, parser):
        """Test validate with 'important' priority."""
        result = parser.parse("validate auth flow - important")
        assert result.type == "validate"
        assert result.slots.get("high_priority") == "true"

    def test_validate_high_priority_keyword(self, parser):
        """Test validate with 'high priority' keyword."""
        result = parser.parse("validate checkout - high priority")
        assert result.type == "validate"
        assert result.slots.get("high_priority") == "true"


class TestStatusIntent(TestIntentParser):
    """Test STATUS intent parsing and slot extraction."""

    def test_whats_status_of_task(self, parser):
        """Test 'what's the status of task X' pattern."""
        result = parser.parse("Kaya, what's the status of task t_123?")
        assert result.type == "status"
        assert result.slots["task_id"] == "t_123"
        assert result.confidence == 0.9

    def test_show_status_pattern(self, parser):
        """Test 'show status of task X' pattern."""
        result = parser.parse("show status of task t_456")
        assert result.type == "status"
        assert result.slots["task_id"] == "t_456"

    def test_what_happening_with_task(self, parser):
        """Test 'what is happening with task X' pattern."""
        result = parser.parse("what is happening with task t_789")
        assert result.type == "status"
        assert result.slots["task_id"] == "t_789"

    def test_get_task_status(self, parser):
        """Test 'get task X status' pattern."""
        result = parser.parse("get task t_abc status")
        assert result.type == "status"
        assert result.slots["task_id"] == "t_abc"

    def test_status_without_task_word(self, parser):
        """Test status query without 'task' word."""
        result = parser.parse("status of t_xyz")
        assert result.type == "status"
        assert result.slots["task_id"] == "t_xyz"


class TestAmbiguousCommands(TestIntentParser):
    """Test handling of ambiguous commands requiring clarification."""

    def test_vague_test_command(self, parser):
        """Test ambiguous 'test something' command."""
        result = parser.parse("Kaya, test something")
        assert result.type == "unknown"
        assert result.needs_clarification
        # Should ask for clarification with examples
        assert "try rephrasing" in result.clarification_prompt.lower()
        assert result.clarification_prompt is not None

    def test_fix_without_task_id(self, parser):
        """Test fix command without task ID."""
        result = parser.parse("fix it")
        assert result.type == "unknown"
        assert result.needs_clarification
        assert "task ID" in result.clarification_prompt
        assert "t_123" in result.clarification_prompt

    def test_status_without_task_id(self, parser):
        """Test status command without task ID."""
        result = parser.parse("status please")
        assert result.type == "unknown"
        assert result.needs_clarification
        assert "task ID" in result.clarification_prompt

    def test_very_short_command(self, parser):
        """Test very short, unclear command."""
        result = parser.parse("do it")
        assert result.type == "unknown"
        assert result.needs_clarification
        assert "try rephrasing" in result.clarification_prompt

    def test_no_action_keywords(self, parser):
        """Test command with no recognizable action."""
        result = parser.parse("hello there")
        assert result.type == "unknown"
        assert result.needs_clarification


class TestEdgeCases(TestIntentParser):
    """Test edge cases and boundary conditions."""

    def test_empty_command(self, parser):
        """Test empty command string."""
        result = parser.parse("")
        assert result.type == "unknown"
        assert result.needs_clarification

    def test_whitespace_only_command(self, parser):
        """Test command with only whitespace."""
        result = parser.parse("   \n\t  ")
        assert result.type == "unknown"

    def test_special_characters_in_command(self, parser):
        """Test command with special characters."""
        result = parser.parse("write a test for user@login#flow!")
        assert result.type == "create_test"
        assert "user@login#flow" in result.slots["feature"]

    def test_very_long_feature_name(self, parser):
        """Test with very long feature description."""
        long_feature = "user authentication with OAuth 2.0 integration including token refresh"
        result = parser.parse(f"create test for {long_feature}")
        assert result.type == "create_test"
        # Normalized to lowercase
        assert result.slots["feature"] == long_feature.lower()

    def test_unicode_characters(self, parser):
        """Test command with unicode characters."""
        result = parser.parse("write a test for user login 测试")
        assert result.type == "create_test"
        assert "测试" in result.slots["feature"]

    def test_multiple_kaya_mentions(self, parser):
        """Test command with multiple 'Kaya' mentions."""
        result = parser.parse("Kaya, hey Kaya, write a test for login")
        assert result.type == "create_test"

    def test_task_id_with_numbers_only(self, parser):
        """Test task ID with only numbers."""
        result = parser.parse("fix task t_12345")
        assert result.type == "fix_failure"
        assert result.slots["task_id"] == "t_12345"

    def test_mixed_case_task_id(self, parser):
        """Test task ID with mixed case (should be normalized)."""
        result = parser.parse("fix task T_ABC123")
        # Pattern should match case-insensitively
        assert result.type == "fix_failure"


class TestBatchProcessing(TestIntentParser):
    """Test batch command parsing."""

    def test_parse_batch_returns_list(self, parser):
        """Test that parse_batch returns list of intents."""
        commands = [
            "write a test for login",
            "run tests/cart.spec.ts",
            "fix task t_123"
        ]
        results = parser.parse_batch(commands)
        assert isinstance(results, list)
        assert len(results) == 3
        assert all(isinstance(r, VoiceIntent) for r in results)

    def test_batch_preserves_order(self, parser):
        """Test that batch processing preserves command order."""
        commands = [
            "create test for feature A",
            "create test for feature B",
            "create test for feature C"
        ]
        results = parser.parse_batch(commands)
        assert results[0].slots["feature"] == "feature a"
        assert results[1].slots["feature"] == "feature b"
        assert results[2].slots["feature"] == "feature c"

    def test_batch_handles_mixed_intents(self, parser):
        """Test batch with different intent types."""
        commands = [
            "write test for login",
            "run tests/auth.spec.ts",
            "validate checkout",
            "status of t_456"
        ]
        results = parser.parse_batch(commands)
        assert results[0].type == "create_test"
        assert results[1].type == "run_test"
        assert results[2].type == "validate"
        assert results[3].type == "status"

    def test_batch_empty_list(self, parser):
        """Test batch processing with empty list."""
        results = parser.parse_batch([])
        assert results == []


class TestHelperMethods(TestIntentParser):
    """Test parser helper methods."""

    def test_get_supported_intents(self, parser):
        """Test getting list of supported intents."""
        intents = parser.get_supported_intents()
        assert isinstance(intents, list)
        assert "create_test" in intents
        assert "run_test" in intents
        assert "fix_failure" in intents
        assert "validate" in intents
        assert "status" in intents
        assert len(intents) == 5

    def test_get_intent_examples_create_test(self, parser):
        """Test getting examples for create_test intent."""
        examples = parser.get_intent_examples("create_test")
        assert isinstance(examples, list)
        assert len(examples) > 0
        assert any("write" in ex.lower() for ex in examples)

    def test_get_intent_examples_run_test(self, parser):
        """Test getting examples for run_test intent."""
        examples = parser.get_intent_examples("run_test")
        assert isinstance(examples, list)
        assert any("run" in ex.lower() for ex in examples)

    def test_get_intent_examples_unknown_intent(self, parser):
        """Test getting examples for unknown intent type."""
        examples = parser.get_intent_examples("nonexistent")
        assert examples == []


class TestVoiceIntentClass:
    """Test VoiceIntent dataclass functionality."""

    def test_voice_intent_creation(self):
        """Test creating VoiceIntent object."""
        intent = VoiceIntent(
            type="create_test",
            slots={"feature": "login"},
            raw_command="write test for login",
            confidence=0.9
        )
        assert intent.type == "create_test"
        assert intent.slots["feature"] == "login"
        assert intent.confidence == 0.9

    def test_voice_intent_to_dict(self):
        """Test converting VoiceIntent to dictionary."""
        intent = VoiceIntent(
            type="run_test",
            slots={"test_path": "tests/auth.spec.ts"},
            raw_command="run tests/auth.spec.ts",
            confidence=0.9
        )
        result = intent.to_dict()
        assert isinstance(result, dict)
        assert result["type"] == "run_test"
        assert result["slots"]["test_path"] == "tests/auth.spec.ts"
        assert result["confidence"] == 0.9

    def test_voice_intent_with_clarification(self):
        """Test VoiceIntent with clarification needed."""
        intent = VoiceIntent(
            type="unknown",
            needs_clarification=True,
            clarification_prompt="Could you clarify?",
            raw_command="test it"
        )
        assert intent.needs_clarification
        assert intent.clarification_prompt == "Could you clarify?"

    def test_voice_intent_default_values(self):
        """Test VoiceIntent default values."""
        intent = VoiceIntent(type="status")
        assert intent.slots == {}
        assert intent.raw_command == ""
        assert intent.confidence == 0.0
        assert not intent.needs_clarification
        assert intent.clarification_prompt is None


class TestConvenienceFunction:
    """Test the parse_voice_command convenience function."""

    def test_parse_voice_command_returns_intent(self):
        """Test that convenience function returns VoiceIntent."""
        result = parse_voice_command("write a test for login")
        assert isinstance(result, VoiceIntent)
        assert result.type == "create_test"
        assert result.slots["feature"] == "login"

    def test_parse_voice_command_matches_parser(self):
        """Test that convenience function matches parser behavior."""
        command = "run tests/cart.spec.ts"
        parser = IntentParser()

        parser_result = parser.parse(command)
        function_result = parse_voice_command(command)

        assert parser_result.type == function_result.type
        assert parser_result.slots == function_result.slots
        assert parser_result.confidence == function_result.confidence


class TestRealWorldScenarios(TestIntentParser):
    """Test realistic voice command scenarios."""

    def test_natural_language_create_test(self, parser):
        """Test natural language test creation."""
        result = parser.parse("Hey Kaya, can you write a test for the user registration flow?")
        assert result.type == "create_test"
        assert "user registration flow" in result.slots["feature"]

    def test_casual_run_test_command(self, parser):
        """Test casual test execution command."""
        result = parser.parse("Kaya run the authentication tests")
        assert result.type == "run_test"
        assert "authentication" in result.slots["test_path"]

    def test_urgent_validation_request(self, parser):
        """Test urgent validation with priority."""
        result = parser.parse("Kaya, validate the payment integration - this is critical!")
        assert result.type == "validate"
        assert "payment integration" in result.slots["test_path"]
        assert result.slots.get("high_priority") == "true"

    def test_follow_up_status_check(self, parser):
        """Test status check as follow-up."""
        result = parser.parse("What's happening with t_abc123?")
        assert result.type == "status"
        assert result.slots["task_id"] == "t_abc123"

    def test_complex_feature_description(self, parser):
        """Test complex multi-word feature."""
        result = parser.parse(
            "create a test for the OAuth 2.0 authentication flow with token refresh"
        )
        assert result.type == "create_test"
        assert "oauth 2.0 authentication flow with token refresh" in result.slots["feature"]


class TestSlotNormalization(TestIntentParser):
    """Test slot value normalization and post-processing."""

    def test_test_path_normalization_with_slash(self, parser):
        """Test path normalization adds .spec.ts extension."""
        result = parser.parse("run tests/login")
        assert result.type == "run_test"
        assert result.slots["test_path"].endswith(".spec.ts")

    def test_priority_extraction_from_path(self, parser):
        """Test priority extraction from test path."""
        result = parser.parse("validate payment - critical")
        assert result.type == "validate"
        assert result.slots.get("high_priority") == "true"
        # Critical should be removed from path
        assert "critical" not in result.slots["test_path"]

    def test_scope_extraction_from_feature(self, parser):
        """Test scope extraction from feature description."""
        result = parser.parse("write test for login scope: edge cases")
        assert result.type == "create_test"
        assert result.slots.get("scope") == "edge cases"
        # Scope should be removed from feature
        assert "scope:" not in result.slots["feature"]


# Integration test: Full workflow
class TestFullWorkflow:
    """Test complete voice command workflow."""

    def test_create_run_validate_workflow(self):
        """Test full workflow: create → run → validate."""
        parser = IntentParser()

        # Step 1: Create test
        create_intent = parser.parse("write a test for user login")
        assert create_intent.type == "create_test"
        assert create_intent.slots["feature"] == "user login"

        # Step 2: Run test
        run_intent = parser.parse("run tests/login.spec.ts")
        assert run_intent.type == "run_test"
        assert "login.spec.ts" in run_intent.slots["test_path"]

        # Step 3: Validate test
        validate_intent = parser.parse("validate the login test - critical")
        assert validate_intent.type == "validate"
        assert validate_intent.slots.get("high_priority") == "true"

    def test_create_fix_rerun_workflow(self):
        """Test workflow with bug fix: create → run → fix → rerun."""
        parser = IntentParser()

        # Create test
        create = parser.parse("create test for checkout")
        assert create.type == "create_test"

        # Run fails, need to fix
        fix = parser.parse("fix task t_checkout_001")
        assert fix.type == "fix_failure"
        assert fix.slots["task_id"] == "t_checkout_001"

        # Check status
        status = parser.parse("what's the status of t_checkout_001")
        assert status.type == "status"
        assert status.slots["task_id"] == "t_checkout_001"
