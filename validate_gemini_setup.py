#!/usr/bin/env python3
"""
Gemini Agent Setup Validation Script

Validates that the Gemini agent is properly configured and ready to use.
Checks configuration, dependencies, API access, and integration points.
"""
import sys
import os
from pathlib import Path


def check_files():
    """Check that all required files exist."""
    print("=" * 60)
    print("1. Checking Required Files")
    print("=" * 60)

    required_files = [
        ".claude/agents/gemini.yaml",
        "agent_system/agents/gemini.py",
        "agent_system/validation_rubric.py",
        "tests/test_gemini_agent.py",
        "requirements.txt",
        "agent_system/agents/GEMINI_AGENT_IMPLEMENTATION.md",
        "agent_system/agents/GEMINI_QUICK_START.md",
    ]

    all_exist = True
    for file_path in required_files:
        full_path = Path(file_path)
        exists = full_path.exists()
        status = "✓" if exists else "✗"
        print(f"  {status} {file_path}")
        if not exists:
            all_exist = False

    return all_exist


def check_dependencies():
    """Check that required Python packages are installed."""
    print("\n" + "=" * 60)
    print("2. Checking Python Dependencies")
    print("=" * 60)

    required_packages = [
        ("yaml", "pyyaml"),
        ("jsonschema", "jsonschema"),
        ("google.genai", "google-genai"),
        ("playwright", "playwright"),
    ]

    all_installed = True
    for import_name, package_name in required_packages:
        try:
            __import__(import_name)
            print(f"  ✓ {package_name}")
        except ImportError:
            print(f"  ✗ {package_name} (not installed)")
            all_installed = False

    if not all_installed:
        print("\n  Install missing packages:")
        print("  pip install -r requirements.txt")

    return all_installed


def check_config():
    """Check gemini.yaml configuration."""
    print("\n" + "=" * 60)
    print("3. Checking Configuration")
    print("=" * 60)

    try:
        import yaml

        config_path = Path(".claude/agents/gemini.yaml")
        with open(config_path) as f:
            config = yaml.safe_load(f)

        # Check key fields
        checks = [
            ("name", config.get("name") == "gemini"),
            ("model", "gemini-2.5-pro" in str(config.get("model", ""))),
            ("contracts.gemini_api", "gemini_api" in config.get("contracts", {})),
            (
                "cost_estimate",
                "estimated_cost_per_validation" in config.get("cost_estimate", {}),
            ),
        ]

        for check_name, result in checks:
            status = "✓" if result else "✗"
            print(f"  {status} {check_name}")

        return all(result for _, result in checks)

    except Exception as e:
        print(f"  ✗ Error reading config: {e}")
        return False


def check_api_key():
    """Check if Gemini API key is set."""
    print("\n" + "=" * 60)
    print("4. Checking API Key")
    print("=" * 60)

    api_key = os.getenv("GEMINI_API_KEY")

    if api_key:
        print(f"  ✓ GEMINI_API_KEY is set ({len(api_key)} chars)")
        masked = api_key[:8] + "..." + api_key[-4:]
        print(f"    Value: {masked}")
        return True
    else:
        print("  ✗ GEMINI_API_KEY not set")
        print("\n  To enable Gemini API:")
        print("  1. Get API key: https://aistudio.google.com/apikey")
        print("  2. Set environment variable:")
        print("     export GEMINI_API_KEY='your-key-here'")
        print("\n  Note: Gemini agent works without API key (Playwright-only mode)")
        return False


def check_agent_initialization():
    """Try to initialize the Gemini agent."""
    print("\n" + "=" * 60)
    print("5. Testing Agent Initialization")
    print("=" * 60)

    try:
        from agent_system.agents.gemini import GeminiAgent

        agent = GeminiAgent()
        print(f"  ✓ Agent initialized")
        print(f"    Name: {agent.name}")
        print(f"    Gemini API enabled: {agent.gemini_enabled}")
        print(f"    Config loaded: {bool(agent.config)}")
        print(f"    Validator: {agent.validator is not None}")

        return True

    except Exception as e:
        print(f"  ✗ Initialization failed: {e}")
        return False


def check_integration_points():
    """Check integration with other components."""
    print("\n" + "=" * 60)
    print("6. Checking Integration Points")
    print("=" * 60)

    checks = []

    # Check if Kaya can import Gemini
    try:
        from agent_system.agents.kaya import KayaAgent

        kaya = KayaAgent()
        gemini = kaya._get_agent("gemini")
        print(f"  ✓ Kaya can load Gemini agent")
        checks.append(True)
    except Exception as e:
        print(f"  ✗ Kaya integration failed: {e}")
        checks.append(False)

    # Check ValidationRubric
    try:
        from agent_system.validation_rubric import ValidationRubric

        rubric = ValidationRubric()
        test_result = {
            "browser_launched": True,
            "test_executed": True,
            "test_passed": True,
            "screenshots": ["test.png"],
            "console_errors": [],
            "network_failures": [],
            "execution_time_ms": 30000,
        }
        validation = rubric.validate(test_result)
        print(f"  ✓ ValidationRubric working (passed: {validation.passed})")
        checks.append(True)
    except Exception as e:
        print(f"  ✗ ValidationRubric failed: {e}")
        checks.append(False)

    return all(checks)


def print_summary(results):
    """Print overall summary."""
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)

    check_names = [
        "Files",
        "Dependencies",
        "Configuration",
        "API Key",
        "Initialization",
        "Integration",
    ]

    for name, result in zip(check_names, results):
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {name}")

    all_passed = all(results)
    print("\n" + "=" * 60)

    if all_passed:
        print("✓ ALL CHECKS PASSED - Gemini agent is ready to use!")
        print("\nNext steps:")
        print("  1. Read: agent_system/agents/GEMINI_QUICK_START.md")
        print("  2. Test: pytest tests/test_gemini_agent.py -v")
        print("  3. Run: from agent_system.agents.gemini import GeminiAgent")
    else:
        print("✗ SOME CHECKS FAILED - Review errors above")
        print("\nRefer to documentation:")
        print("  - agent_system/agents/GEMINI_QUICK_START.md")
        print("  - agent_system/agents/GEMINI_AGENT_IMPLEMENTATION.md")

    print("=" * 60)

    return all_passed


def main():
    """Run all validation checks."""
    print("\nGemini Agent Setup Validation")
    print("SuperAgent - Voice-Controlled Multi-Agent Testing System\n")

    results = [
        check_files(),
        check_dependencies(),
        check_config(),
        check_api_key(),
        check_agent_initialization(),
        check_integration_points(),
    ]

    success = print_summary(results)

    # Exit code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
