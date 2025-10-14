#!/usr/bin/env python3
"""
YAML Configuration Validator for SuperAgent

Validates all YAML configs against the schemas defined in The_Bible.
"""

import yaml
import sys
from pathlib import Path
from typing import Dict, List, Tuple

class YAMLValidator:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.success_count = 0

    def validate_agent_config(self, filepath: Path, data: Dict) -> bool:
        """Validate agent configuration file."""
        agent_name = filepath.stem
        issues = []

        # Required fields
        required = ['name', 'role', 'model', 'tools', 'description']
        for field in required:
            if field not in data:
                issues.append(f"Missing required field: {field}")

        # Validate name matches filename
        if 'name' in data and data['name'] != agent_name:
            issues.append(f"Name mismatch: config says '{data['name']}' but file is '{agent_name}.yaml'")

        # Validate tools is a list
        if 'tools' in data and not isinstance(data['tools'], list):
            issues.append(f"'tools' must be a list, got {type(data['tools']).__name__}")

        # Agent-specific validations
        if agent_name == 'medic':
            if 'contracts' not in data:
                issues.append("Medic must have 'contracts' field")
            elif 'regression_scope' not in data['contracts']:
                issues.append("Medic contracts must include 'regression_scope'")
            elif data['contracts']['regression_scope'].get('max_new_failures') != 0:
                issues.append("Medic must have max_new_failures: 0 (Hippocratic Oath)")

        if agent_name == 'critic':
            if 'contracts' not in data:
                issues.append("Critic must have 'contracts' field")
            elif 'rejection_criteria' not in data['contracts']:
                issues.append("Critic contracts must include 'rejection_criteria'")

        if agent_name == 'gemini':
            if 'contracts' not in data:
                issues.append("Gemini must have 'contracts' field")
            elif 'browser' not in data['contracts']:
                issues.append("Gemini contracts must include 'browser' settings")

        if issues:
            self.errors.append((str(filepath), issues))
            return False
        else:
            self.success_count += 1
            return True

    def validate_router_policy(self, filepath: Path, data: Dict) -> bool:
        """Validate router_policy.yaml."""
        issues = []

        # Required top-level fields
        required = ['version', 'routing', 'cost_targets', 'cost_overrides', 'fallbacks']
        for field in required:
            if field not in data:
                issues.append(f"Missing required field: {field}")

        # Validate routing rules
        if 'routing' in data:
            if not isinstance(data['routing'], list):
                issues.append("'routing' must be a list")
            else:
                required_route_fields = ['task', 'complexity', 'agent', 'model', 'reason']
                for i, rule in enumerate(data['routing']):
                    for field in required_route_fields:
                        if field not in rule:
                            issues.append(f"Route rule {i} missing field: {field}")

        # Validate cost_targets
        if 'cost_targets' in data:
            if 'use_haiku_ratio' not in data['cost_targets']:
                issues.append("cost_targets missing 'use_haiku_ratio'")
            if 'max_cost_per_feature_usd' not in data['cost_targets']:
                issues.append("cost_targets missing 'max_cost_per_feature_usd'")

        # Validate cost overrides structure
        if 'cost_overrides' in data:
            if 'critical_paths' not in data['cost_overrides']:
                self.warnings.append((str(filepath), ["cost_overrides has no 'critical_paths' defined"]))

        if issues:
            self.errors.append((str(filepath), issues))
            return False
        else:
            self.success_count += 1
            return True

    def validate_observability(self, filepath: Path, data: Dict) -> bool:
        """Validate observability.yaml."""
        issues = []

        # Required fields
        required = ['version', 'events', 'destinations', 'metrics']
        for field in required:
            if field not in data:
                issues.append(f"Missing required field: {field}")

        # Validate events
        if 'events' in data:
            if not isinstance(data['events'], list):
                issues.append("'events' must be a list")
            else:
                for i, event in enumerate(data['events']):
                    if 'on' not in event:
                        issues.append(f"Event {i} missing 'on' field")
                    if 'emit' not in event:
                        issues.append(f"Event {i} missing 'emit' field")

        # Validate destinations
        if 'destinations' in data:
            if not isinstance(data['destinations'], list):
                issues.append("'destinations' must be a list")
            else:
                for i, dest in enumerate(data['destinations']):
                    if 'type' not in dest:
                        issues.append(f"Destination {i} missing 'type' field")

        if issues:
            self.errors.append((str(filepath), issues))
            return False
        else:
            self.success_count += 1
            return True

    def validate_file(self, filepath: Path) -> bool:
        """Validate a single YAML file."""
        try:
            # Load YAML
            with open(filepath, 'r') as f:
                data = yaml.safe_load(f)

            if data is None:
                self.errors.append((str(filepath), ["File is empty or contains only comments"]))
                return False

            # Route to appropriate validator
            if filepath.parent.name == 'agents':
                return self.validate_agent_config(filepath, data)
            elif filepath.name == 'router_policy.yaml':
                return self.validate_router_policy(filepath, data)
            elif filepath.name == 'observability.yaml':
                return self.validate_observability(filepath, data)
            else:
                # Generic validation (syntax only)
                self.success_count += 1
                return True

        except yaml.YAMLError as e:
            self.errors.append((str(filepath), [f"YAML syntax error: {str(e)}"]))
            return False
        except Exception as e:
            self.errors.append((str(filepath), [f"Unexpected error: {str(e)}"]))
            return False

    def validate_all(self, base_path: Path) -> Tuple[int, int, int]:
        """Validate all YAML files in .claude directory."""
        yaml_files = list(base_path.glob('**/*.yaml'))

        if not yaml_files:
            print(f"⚠️  No YAML files found in {base_path}")
            return 0, 0, 0

        print(f"🔍 Validating {len(yaml_files)} YAML files...\n")

        for filepath in sorted(yaml_files):
            self.validate_file(filepath)

        return self.success_count, len(self.errors), len(self.warnings)

    def print_report(self):
        """Print validation report."""
        print("\n" + "="*70)
        print("YAML VALIDATION REPORT")
        print("="*70)

        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)} files with issues):")
            for filepath, issues in self.errors:
                print(f"\n  {filepath}")
                for issue in issues:
                    print(f"    • {issue}")

        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)} files with warnings):")
            for filepath, warnings in self.warnings:
                print(f"\n  {filepath}")
                for warning in warnings:
                    print(f"    • {warning}")

        print(f"\n✅ SUCCESS: {self.success_count} files validated")

        if not self.errors and not self.warnings:
            print("\n🎉 All YAML configurations are valid!")
            return 0
        elif not self.errors:
            print("\n✓ All YAML files have valid syntax (warnings only)")
            return 0
        else:
            print(f"\n❌ {len(self.errors)} file(s) have errors that need fixing")
            return 1


def main():
    # Find .claude directory
    project_root = Path(__file__).parent
    claude_dir = project_root / '.claude'

    if not claude_dir.exists():
        print(f"❌ .claude directory not found at {claude_dir}")
        return 1

    validator = YAMLValidator()
    success, errors, warnings = validator.validate_all(claude_dir)
    exit_code = validator.print_report()

    return exit_code


if __name__ == '__main__':
    sys.exit(main())
