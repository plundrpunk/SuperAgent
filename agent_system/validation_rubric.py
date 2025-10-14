"""
Validation Rubric for SuperAgent
Validates Gemini test execution results against strict schema.
"""
import jsonschema
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


# JSON Schema for validation results
VALIDATION_SCHEMA = {
    "type": "object",
    "required": [
        "browser_launched",
        "test_executed",
        "test_passed",
        "screenshots",
        "console_errors",
        "network_failures",
        "execution_time_ms"
    ],
    "properties": {
        "browser_launched": {"type": "boolean"},
        "test_executed": {"type": "boolean"},
        "test_passed": {"type": "boolean"},
        "screenshots": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1
        },
        "console_errors": {
            "type": "array",
            "items": {"type": "string"}
        },
        "network_failures": {
            "type": "array",
            "items": {"type": "string"}
        },
        "execution_time_ms": {
            "type": "integer",
            "minimum": 0,
            "maximum": 45000
        }
    }
}


@dataclass
class ValidationResult:
    """Result of validation check."""
    passed: bool
    errors: List[str]
    warnings: List[str]
    data: Dict[str, Any]


class ValidationRubric:
    """
    Validates test execution results against strict criteria.

    Required for passing:
    - browser_launched: true
    - test_executed: true
    - test_passed: true
    - screenshots: at least 1
    - execution_time_ms: ≤ 45000

    Tracked but allowed:
    - console_errors: logged but not failing
    - network_failures: logged but not failing
    """

    def __init__(self, schema: Optional[Dict] = None):
        """
        Initialize validator with optional custom schema.

        Args:
            schema: JSON schema dict (uses default if not provided)
        """
        self.schema = schema or VALIDATION_SCHEMA
        self.validator = jsonschema.Draft7Validator(self.schema)

    def validate(self, result: Dict[str, Any]) -> ValidationResult:
        """
        Validate a test execution result.

        Args:
            result: Test execution result dict

        Returns:
            ValidationResult with pass/fail, errors, warnings
        """
        errors = []
        warnings = []

        # 1. Validate schema
        schema_errors = list(self.validator.iter_errors(result))
        if schema_errors:
            for error in schema_errors:
                errors.append(f"Schema validation error: {error.message} at {'.'.join(str(p) for p in error.path)}")

        # If schema validation fails, return early
        if errors:
            return ValidationResult(
                passed=False,
                errors=errors,
                warnings=warnings,
                data=result
            )

        # 2. Check business logic requirements

        # Browser must have launched
        if not result.get('browser_launched', False):
            errors.append("Browser failed to launch")

        # Test must have executed
        if not result.get('test_executed', False):
            errors.append("Test did not execute")

        # Test must have passed
        if not result.get('test_passed', False):
            errors.append("Test failed (test_passed=false)")

        # Must have at least one screenshot
        screenshots = result.get('screenshots', [])
        if len(screenshots) < 1:
            errors.append("No screenshots captured (minimum 1 required)")

        # Execution time must be within limit
        execution_time = result.get('execution_time_ms', 0)
        if execution_time > 45000:
            errors.append(f"Execution time {execution_time}ms exceeds 45000ms limit")

        # 3. Check for warnings (tracked but not failing)

        console_errors = result.get('console_errors', [])
        if console_errors:
            warnings.append(f"Console errors detected: {len(console_errors)} errors")

        network_failures = result.get('network_failures', [])
        if network_failures:
            warnings.append(f"Network failures detected: {len(network_failures)} failures")

        # Determine pass/fail
        passed = len(errors) == 0

        return ValidationResult(
            passed=passed,
            errors=errors,
            warnings=warnings,
            data=result
        )

    def validate_batch(self, results: List[Dict[str, Any]]) -> Dict[str, ValidationResult]:
        """
        Validate multiple test results.

        Args:
            results: List of test result dicts with 'test_id' key

        Returns:
            Dict mapping test_id to ValidationResult
        """
        validated = {}
        for result in results:
            test_id = result.get('test_id', result.get('id', 'unknown'))
            validated[test_id] = self.validate(result)
        return validated


def validate_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function for single result validation.

    Args:
        result: Test execution result dict

    Returns:
        Dict with passed, errors, warnings, data
    """
    rubric = ValidationRubric()
    validation = rubric.validate(result)
    return {
        'passed': validation.passed,
        'errors': validation.errors,
        'warnings': validation.warnings,
        'data': validation.data
    }
