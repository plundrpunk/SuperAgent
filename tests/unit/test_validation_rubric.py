"""
Unit tests for validation_rubric.py

Tests JSON schema validation and business logic checks for Playwright test results.
"""
import pytest
from agent_system.validation_rubric import (
    ValidationRubric,
    ValidationResult,
    validate_result,
    VALIDATION_SCHEMA
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def valid_result():
    """A fully valid test result that should pass all checks."""
    return {
        "browser_launched": True,
        "test_executed": True,
        "test_passed": True,
        "screenshots": ["screenshot1.png", "screenshot2.png"],
        "console_errors": [],
        "network_failures": [],
        "execution_time_ms": 5000
    }


@pytest.fixture
def rubric():
    """Fresh ValidationRubric instance."""
    return ValidationRubric()


# ============================================================================
# Schema Validation Tests
# ============================================================================

class TestSchemaValidation:
    """Test JSON schema validation rules."""

    def test_valid_result_passes_schema(self, rubric, valid_result):
        """Valid result should pass schema validation."""
        result = rubric.validate(valid_result)
        assert result.passed is True
        assert len(result.errors) == 0

    def test_missing_browser_launched_fails(self, rubric, valid_result):
        """Missing browser_launched field should fail schema validation."""
        del valid_result["browser_launched"]
        result = rubric.validate(valid_result)
        assert result.passed is False
        assert any("browser_launched" in err for err in result.errors)

    def test_missing_test_executed_fails(self, rubric, valid_result):
        """Missing test_executed field should fail schema validation."""
        del valid_result["test_executed"]
        result = rubric.validate(valid_result)
        assert result.passed is False
        assert any("test_executed" in err for err in result.errors)

    def test_missing_test_passed_fails(self, rubric, valid_result):
        """Missing test_passed field should fail schema validation."""
        del valid_result["test_passed"]
        result = rubric.validate(valid_result)
        assert result.passed is False
        assert any("test_passed" in err for err in result.errors)

    def test_missing_screenshots_fails(self, rubric, valid_result):
        """Missing screenshots field should fail schema validation."""
        del valid_result["screenshots"]
        result = rubric.validate(valid_result)
        assert result.passed is False
        assert any("screenshots" in err or "required" in err.lower() for err in result.errors)

    def test_missing_console_errors_fails(self, rubric, valid_result):
        """Missing console_errors field should fail schema validation."""
        del valid_result["console_errors"]
        result = rubric.validate(valid_result)
        assert result.passed is False
        assert any("console_errors" in err for err in result.errors)

    def test_missing_network_failures_fails(self, rubric, valid_result):
        """Missing network_failures field should fail schema validation."""
        del valid_result["network_failures"]
        result = rubric.validate(valid_result)
        assert result.passed is False
        assert any("network_failures" in err for err in result.errors)

    def test_missing_execution_time_ms_fails(self, rubric, valid_result):
        """Missing execution_time_ms field should fail schema validation."""
        del valid_result["execution_time_ms"]
        result = rubric.validate(valid_result)
        assert result.passed is False
        assert any("execution_time_ms" in err for err in result.errors)

    def test_invalid_browser_launched_type_fails(self, rubric, valid_result):
        """browser_launched must be boolean."""
        valid_result["browser_launched"] = "true"  # string instead of bool
        result = rubric.validate(valid_result)
        assert result.passed is False
        assert any("browser_launched" in err for err in result.errors)

    def test_invalid_test_executed_type_fails(self, rubric, valid_result):
        """test_executed must be boolean."""
        valid_result["test_executed"] = 1  # int instead of bool
        result = rubric.validate(valid_result)
        assert result.passed is False
        assert any("test_executed" in err for err in result.errors)

    def test_invalid_test_passed_type_fails(self, rubric, valid_result):
        """test_passed must be boolean."""
        valid_result["test_passed"] = "false"  # string instead of bool
        result = rubric.validate(valid_result)
        assert result.passed is False
        assert any("test_passed" in err for err in result.errors)

    def test_invalid_screenshots_type_fails(self, rubric, valid_result):
        """screenshots must be an array."""
        valid_result["screenshots"] = "screenshot.png"  # string instead of array
        result = rubric.validate(valid_result)
        assert result.passed is False
        assert any("screenshots" in err for err in result.errors)

    def test_invalid_screenshot_item_type_fails(self, rubric, valid_result):
        """screenshot items must be strings."""
        valid_result["screenshots"] = [123, 456]  # ints instead of strings
        result = rubric.validate(valid_result)
        assert result.passed is False
        assert any("screenshots" in err or "type" in err.lower() for err in result.errors)

    def test_invalid_console_errors_type_fails(self, rubric, valid_result):
        """console_errors must be an array."""
        valid_result["console_errors"] = "error message"  # string instead of array
        result = rubric.validate(valid_result)
        assert result.passed is False
        assert any("console_errors" in err for err in result.errors)

    def test_invalid_network_failures_type_fails(self, rubric, valid_result):
        """network_failures must be an array."""
        valid_result["network_failures"] = {"error": "timeout"}  # object instead of array
        result = rubric.validate(valid_result)
        assert result.passed is False
        assert any("network_failures" in err for err in result.errors)

    def test_invalid_execution_time_type_fails(self, rubric, valid_result):
        """execution_time_ms must be an integer."""
        valid_result["execution_time_ms"] = "5000"  # string instead of int
        result = rubric.validate(valid_result)
        assert result.passed is False
        assert any("execution_time_ms" in err for err in result.errors)

    def test_negative_execution_time_fails(self, rubric, valid_result):
        """execution_time_ms must be non-negative."""
        valid_result["execution_time_ms"] = -100
        result = rubric.validate(valid_result)
        assert result.passed is False
        assert any("execution_time_ms" in err or "-100" in err for err in result.errors)


# ============================================================================
# Business Logic Tests
# ============================================================================

class TestBusinessLogicChecks:
    """Test business logic validation rules."""

    def test_browser_not_launched_fails(self, rubric, valid_result):
        """browser_launched=false should fail validation."""
        valid_result["browser_launched"] = False
        result = rubric.validate(valid_result)
        assert result.passed is False
        assert "Browser failed to launch" in result.errors

    def test_test_not_executed_fails(self, rubric, valid_result):
        """test_executed=false should fail validation."""
        valid_result["test_executed"] = False
        result = rubric.validate(valid_result)
        assert result.passed is False
        assert "Test did not execute" in result.errors

    def test_test_not_passed_fails(self, rubric, valid_result):
        """test_passed=false should fail validation."""
        valid_result["test_passed"] = False
        result = rubric.validate(valid_result)
        assert result.passed is False
        assert "Test failed (test_passed=false)" in result.errors

    def test_empty_screenshots_fails(self, rubric, valid_result):
        """Empty screenshots array should fail (minItems: 1)."""
        valid_result["screenshots"] = []
        result = rubric.validate(valid_result)
        assert result.passed is False
        # Could fail at schema level or business logic level
        assert any("screenshot" in err.lower() for err in result.errors)

    def test_one_screenshot_passes(self, rubric, valid_result):
        """Exactly one screenshot should pass."""
        valid_result["screenshots"] = ["screenshot.png"]
        result = rubric.validate(valid_result)
        assert result.passed is True
        assert len(result.errors) == 0

    def test_multiple_screenshots_passes(self, rubric, valid_result):
        """Multiple screenshots should pass."""
        valid_result["screenshots"] = ["s1.png", "s2.png", "s3.png"]
        result = rubric.validate(valid_result)
        assert result.passed is True
        assert len(result.errors) == 0

    def test_execution_time_at_limit_passes(self, rubric, valid_result):
        """execution_time_ms exactly at 45000ms should pass."""
        valid_result["execution_time_ms"] = 45000
        result = rubric.validate(valid_result)
        assert result.passed is True
        assert len(result.errors) == 0

    def test_execution_time_over_limit_fails(self, rubric, valid_result):
        """execution_time_ms over 45000ms should fail."""
        valid_result["execution_time_ms"] = 45001
        result = rubric.validate(valid_result)
        assert result.passed is False
        assert any("45001" in err and "45000" in err for err in result.errors)

    def test_execution_time_way_over_limit_fails(self, rubric, valid_result):
        """execution_time_ms significantly over 45000ms should fail."""
        valid_result["execution_time_ms"] = 60000
        result = rubric.validate(valid_result)
        assert result.passed is False
        assert any("60000" in err and "45000" in err for err in result.errors)

    def test_zero_execution_time_passes(self, rubric, valid_result):
        """execution_time_ms of 0 should pass (edge case)."""
        valid_result["execution_time_ms"] = 0
        result = rubric.validate(valid_result)
        assert result.passed is True
        assert len(result.errors) == 0


# ============================================================================
# Warning Tests (Tracked but Not Failing)
# ============================================================================

class TestWarnings:
    """Test that console_errors and network_failures generate warnings, not errors."""

    def test_console_errors_generates_warning(self, rubric, valid_result):
        """console_errors should generate warning but not fail test."""
        valid_result["console_errors"] = [
            "TypeError: undefined is not a function",
            "ReferenceError: foo is not defined"
        ]
        result = rubric.validate(valid_result)
        assert result.passed is True  # Still passes
        assert len(result.errors) == 0
        assert len(result.warnings) > 0
        assert any("Console errors detected: 2 errors" in w for w in result.warnings)

    def test_network_failures_generates_warning(self, rubric, valid_result):
        """network_failures should generate warning but not fail test."""
        valid_result["network_failures"] = [
            "Failed to load resource: net::ERR_CONNECTION_REFUSED",
            "504 Gateway Timeout"
        ]
        result = rubric.validate(valid_result)
        assert result.passed is True  # Still passes
        assert len(result.errors) == 0
        assert len(result.warnings) > 0
        assert any("Network failures detected: 2 failures" in w for w in result.warnings)

    def test_both_warnings_together(self, rubric, valid_result):
        """Both console_errors and network_failures should generate separate warnings."""
        valid_result["console_errors"] = ["Error 1"]
        valid_result["network_failures"] = ["Failure 1", "Failure 2"]
        result = rubric.validate(valid_result)
        assert result.passed is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 2
        assert any("Console errors" in w for w in result.warnings)
        assert any("Network failures" in w for w in result.warnings)

    def test_empty_console_errors_no_warning(self, rubric, valid_result):
        """Empty console_errors array should not generate warning."""
        valid_result["console_errors"] = []
        result = rubric.validate(valid_result)
        assert result.passed is True
        assert len(result.warnings) == 0

    def test_empty_network_failures_no_warning(self, rubric, valid_result):
        """Empty network_failures array should not generate warning."""
        valid_result["network_failures"] = []
        result = rubric.validate(valid_result)
        assert result.passed is True
        assert len(result.warnings) == 0


# ============================================================================
# Multiple Failure Tests
# ============================================================================

class TestMultipleFailures:
    """Test scenarios with multiple validation failures."""

    def test_all_failures_combined(self, rubric, valid_result):
        """Test with all possible failures should list all errors."""
        invalid_result = {
            "browser_launched": False,
            "test_executed": False,
            "test_passed": False,
            "screenshots": [],
            "console_errors": [],
            "network_failures": [],
            "execution_time_ms": 50000
        }
        result = rubric.validate(invalid_result)
        assert result.passed is False
        # Schema validation catches empty screenshots and over-limit execution_time
        # Note: When schema fails, business logic checks don't run (early return)
        assert len(result.errors) >= 2  # At least screenshots and execution_time schema errors

    def test_schema_and_business_logic_failures(self, rubric, valid_result):
        """Test with both schema and business logic failures."""
        valid_result["test_passed"] = False
        valid_result["execution_time_ms"] = 60000
        result = rubric.validate(valid_result)
        assert result.passed is False
        # Schema validation catches execution_time first (early return)
        assert len(result.errors) >= 1
        assert any("60000" in err for err in result.errors)


# ============================================================================
# ValidationResult Tests
# ============================================================================

class TestValidationResult:
    """Test ValidationResult dataclass."""

    def test_validation_result_structure(self, rubric, valid_result):
        """ValidationResult should have correct structure."""
        result = rubric.validate(valid_result)
        assert isinstance(result, ValidationResult)
        assert hasattr(result, 'passed')
        assert hasattr(result, 'errors')
        assert hasattr(result, 'warnings')
        assert hasattr(result, 'data')
        assert isinstance(result.passed, bool)
        assert isinstance(result.errors, list)
        assert isinstance(result.warnings, list)
        assert isinstance(result.data, dict)

    def test_validation_result_data_preserved(self, rubric, valid_result):
        """ValidationResult.data should contain original result."""
        result = rubric.validate(valid_result)
        assert result.data == valid_result


# ============================================================================
# Batch Validation Tests
# ============================================================================

class TestBatchValidation:
    """Test batch validation functionality."""

    def test_validate_batch_with_test_id(self, rubric):
        """Batch validation should use test_id as key."""
        results = [
            {
                "test_id": "test_1",
                "browser_launched": True,
                "test_executed": True,
                "test_passed": True,
                "screenshots": ["s1.png"],
                "console_errors": [],
                "network_failures": [],
                "execution_time_ms": 5000
            },
            {
                "test_id": "test_2",
                "browser_launched": True,
                "test_executed": True,
                "test_passed": False,  # This one fails
                "screenshots": ["s2.png"],
                "console_errors": [],
                "network_failures": [],
                "execution_time_ms": 6000
            }
        ]
        validated = rubric.validate_batch(results)
        assert len(validated) == 2
        assert "test_1" in validated
        assert "test_2" in validated
        assert validated["test_1"].passed is True
        assert validated["test_2"].passed is False

    def test_validate_batch_with_id_fallback(self, rubric):
        """Batch validation should fall back to 'id' field."""
        results = [
            {
                "id": "test_a",
                "browser_launched": True,
                "test_executed": True,
                "test_passed": True,
                "screenshots": ["sa.png"],
                "console_errors": [],
                "network_failures": [],
                "execution_time_ms": 5000
            }
        ]
        validated = rubric.validate_batch(results)
        assert "test_a" in validated
        assert validated["test_a"].passed is True

    def test_validate_batch_with_unknown_fallback(self, rubric):
        """Batch validation should use 'unknown' if no id field."""
        results = [
            {
                "browser_launched": True,
                "test_executed": True,
                "test_passed": True,
                "screenshots": ["s.png"],
                "console_errors": [],
                "network_failures": [],
                "execution_time_ms": 5000
            }
        ]
        validated = rubric.validate_batch(results)
        assert "unknown" in validated

    def test_validate_batch_empty_list(self, rubric):
        """Batch validation should handle empty list."""
        validated = rubric.validate_batch([])
        assert validated == {}


# ============================================================================
# Convenience Function Tests
# ============================================================================

class TestConvenienceFunction:
    """Test the validate_result convenience function."""

    def test_validate_result_returns_dict(self, valid_result):
        """validate_result should return dict with correct keys."""
        result = validate_result(valid_result)
        assert isinstance(result, dict)
        assert "passed" in result
        assert "errors" in result
        assert "warnings" in result
        assert "data" in result

    def test_validate_result_passing(self, valid_result):
        """validate_result should return passed=True for valid result."""
        result = validate_result(valid_result)
        assert result["passed"] is True
        assert result["errors"] == []
        assert result["data"] == valid_result

    def test_validate_result_failing(self, valid_result):
        """validate_result should return passed=False for invalid result."""
        valid_result["test_passed"] = False
        result = validate_result(valid_result)
        assert result["passed"] is False
        assert len(result["errors"]) > 0


# ============================================================================
# Custom Schema Tests
# ============================================================================

class TestCustomSchema:
    """Test ValidationRubric with custom schema."""

    def test_custom_schema_initialization(self):
        """ValidationRubric should accept custom schema."""
        custom_schema = {
            "type": "object",
            "required": ["test_passed"],
            "properties": {
                "test_passed": {"type": "boolean"}
            }
        }
        rubric = ValidationRubric(schema=custom_schema)
        assert rubric.schema == custom_schema

    def test_default_schema_used_when_none(self):
        """ValidationRubric should use default schema when none provided."""
        rubric = ValidationRubric()
        assert rubric.schema == VALIDATION_SCHEMA


# ============================================================================
# Edge Case Tests
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_result_dict_fails(self, rubric):
        """Empty result dict should fail validation."""
        result = rubric.validate({})
        assert result.passed is False
        assert len(result.errors) > 0

    def test_null_values_fail(self, rubric, valid_result):
        """None/null values should fail validation."""
        valid_result["browser_launched"] = None
        result = rubric.validate(valid_result)
        assert result.passed is False

    def test_large_screenshot_array(self, rubric, valid_result):
        """Large screenshot array should pass."""
        valid_result["screenshots"] = [f"screenshot_{i}.png" for i in range(100)]
        result = rubric.validate(valid_result)
        assert result.passed is True

    def test_very_fast_execution(self, rubric, valid_result):
        """Very fast execution (1ms) should pass."""
        valid_result["execution_time_ms"] = 1
        result = rubric.validate(valid_result)
        assert result.passed is True

    def test_execution_time_just_under_limit(self, rubric, valid_result):
        """execution_time_ms just under limit (44999ms) should pass."""
        valid_result["execution_time_ms"] = 44999
        result = rubric.validate(valid_result)
        assert result.passed is True
