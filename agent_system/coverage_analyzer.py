"""
Test Coverage Analyzer
Analyzes test coverage for Playwright tests using Istanbul/NYC.
"""
import json
import subprocess
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


class CoverageAnalyzer:
    """
    Analyzes test coverage for Playwright tests.

    Supports:
    - Running tests with coverage enabled
    - Parsing Istanbul/NYC coverage reports
    - Generating coverage summaries
    - Identifying uncovered lines
    """

    def __init__(self, project_dir: Optional[str] = None):
        """
        Initialize coverage analyzer.

        Args:
            project_dir: Project directory (default: current directory)
        """
        self.project_dir = Path(project_dir) if project_dir else Path.cwd()
        self.coverage_dir = self.project_dir / 'coverage'

    def analyze_project_coverage(self, test_pattern: str = '**/*.spec.ts') -> Dict[str, Any]:
        """
        Analyze coverage for all tests matching pattern.

        Args:
            test_pattern: Test file pattern (default: **/*.spec.ts)

        Returns:
            Coverage analysis result
        """
        try:
            # Run tests with coverage
            logger.info(f"Running tests with coverage: {test_pattern}")
            result = subprocess.run(
                [
                    'npx', 'playwright', 'test',
                    test_pattern,
                    '--reporter=json'
                ],
                cwd=str(self.project_dir),
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            # Check if coverage directory exists
            if not self.coverage_dir.exists():
                return {
                    'success': False,
                    'error': 'Coverage directory not found. Ensure Playwright coverage is enabled.',
                    'help': 'Add coverage settings to playwright.config.ts'
                }

            # Parse coverage report
            coverage_summary = self._parse_coverage_report()

            return {
                'success': True,
                'coverage': coverage_summary,
                'test_pattern': test_pattern,
                'coverage_dir': str(self.coverage_dir)
            }

        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'Test execution timed out after 5 minutes'
            }
        except Exception as e:
            logger.error(f"Coverage analysis failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def analyze_file_coverage(self, file_path: str) -> Dict[str, Any]:
        """
        Analyze coverage for a specific file.

        Args:
            file_path: Path to source file

        Returns:
            File coverage analysis
        """
        try:
            coverage_json = self.coverage_dir / 'coverage-final.json'

            if not coverage_json.exists():
                return {
                    'success': False,
                    'error': 'No coverage data found. Run tests with coverage first.',
                    'file': file_path
                }

            # Parse coverage JSON
            with open(coverage_json, 'r') as f:
                coverage_data = json.load(f)

            # Find file in coverage data
            file_coverage = None
            for path, data in coverage_data.items():
                if file_path in path or Path(path).name == Path(file_path).name:
                    file_coverage = data
                    break

            if not file_coverage:
                return {
                    'success': False,
                    'error': f'File not found in coverage report: {file_path}',
                    'available_files': list(coverage_data.keys())[:10]  # Show first 10
                }

            # Calculate line coverage
            statement_map = file_coverage.get('statementMap', {})
            statements = file_coverage.get('s', {})

            total_statements = len(statements)
            covered_statements = sum(1 for count in statements.values() if count > 0)

            # Find uncovered lines
            uncovered_lines = []
            for stmt_id, count in statements.items():
                if count == 0 and stmt_id in statement_map:
                    line = statement_map[stmt_id].get('start', {}).get('line')
                    if line:
                        uncovered_lines.append(line)

            coverage_pct = (covered_statements / total_statements * 100) if total_statements > 0 else 0

            return {
                'success': True,
                'file': file_path,
                'coverage_percentage': round(coverage_pct, 2),
                'total_statements': total_statements,
                'covered_statements': covered_statements,
                'uncovered_statements': total_statements - covered_statements,
                'uncovered_lines': sorted(uncovered_lines)[:20]  # Limit to first 20
            }

        except Exception as e:
            logger.error(f"File coverage analysis failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'file': file_path
            }

    def _parse_coverage_report(self) -> Dict[str, Any]:
        """
        Parse Istanbul coverage report.

        Returns:
            Coverage summary
        """
        try:
            # Look for coverage-summary.json
            summary_file = self.coverage_dir / 'coverage-summary.json'

            if summary_file.exists():
                with open(summary_file, 'r') as f:
                    summary_data = json.load(f)

                # Extract totals
                totals = summary_data.get('total', {})

                return {
                    'statements': self._format_coverage_metric(totals.get('statements', {})),
                    'branches': self._format_coverage_metric(totals.get('branches', {})),
                    'functions': self._format_coverage_metric(totals.get('functions', {})),
                    'lines': self._format_coverage_metric(totals.get('lines', {})),
                    'files_covered': len(summary_data) - 1,  # Exclude 'total' key
                    'report_path': str(self.coverage_dir / 'index.html')
                }

            # Fallback: Parse coverage-final.json
            final_file = self.coverage_dir / 'coverage-final.json'
            if final_file.exists():
                with open(final_file, 'r') as f:
                    coverage_data = json.load(f)

                # Calculate aggregated metrics
                total_statements = 0
                covered_statements = 0

                for file_data in coverage_data.values():
                    statements = file_data.get('s', {})
                    total_statements += len(statements)
                    covered_statements += sum(1 for count in statements.values() if count > 0)

                coverage_pct = (covered_statements / total_statements * 100) if total_statements > 0 else 0

                return {
                    'statements': {
                        'total': total_statements,
                        'covered': covered_statements,
                        'skipped': 0,
                        'pct': round(coverage_pct, 2)
                    },
                    'files_covered': len(coverage_data),
                    'note': 'Detailed metrics unavailable - run with --coverage flag'
                }

            return {
                'error': 'No coverage report found',
                'coverage_dir': str(self.coverage_dir)
            }

        except Exception as e:
            logger.error(f"Failed to parse coverage report: {e}")
            return {
                'error': str(e)
            }

    def _format_coverage_metric(self, metric: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format coverage metric for readability.

        Args:
            metric: Raw metric data

        Returns:
            Formatted metric
        """
        return {
            'total': metric.get('total', 0),
            'covered': metric.get('covered', 0),
            'skipped': metric.get('skipped', 0),
            'pct': metric.get('pct', 0.0)
        }

    def generate_coverage_report(self) -> Dict[str, Any]:
        """
        Generate human-readable coverage report.

        Returns:
            Coverage report with recommendations
        """
        summary = self._parse_coverage_report()

        if 'error' in summary:
            return {
                'success': False,
                'error': summary['error']
            }

        statements = summary.get('statements', {})
        coverage_pct = statements.get('pct', 0)

        # Generate recommendations
        recommendations = []
        if coverage_pct < 70:
            recommendations.append('Coverage is below 70%. Consider adding more tests.')
        elif coverage_pct < 85:
            recommendations.append('Good coverage! Aim for 85%+ for critical paths.')
        else:
            recommendations.append('Excellent coverage! Maintain this level.')

        # Check for completely uncovered files
        if 'files_covered' in summary and summary['files_covered'] == 0:
            recommendations.append('No files have test coverage. Start by testing critical paths.')

        return {
            'success': True,
            'summary': summary,
            'overall_coverage': coverage_pct,
            'grade': self._get_coverage_grade(coverage_pct),
            'recommendations': recommendations,
            'report_html': summary.get('report_path', 'Not available')
        }

    def _get_coverage_grade(self, pct: float) -> str:
        """
        Get letter grade for coverage percentage.

        Args:
            pct: Coverage percentage

        Returns:
            Letter grade (A-F)
        """
        if pct >= 90:
            return 'A'
        elif pct >= 80:
            return 'B'
        elif pct >= 70:
            return 'C'
        elif pct >= 60:
            return 'D'
        else:
            return 'F'


def analyze_coverage(project_dir: Optional[str] = None, file_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Convenience function to analyze coverage.

    Args:
        project_dir: Project directory
        file_path: Optional specific file to analyze

    Returns:
        Coverage analysis result
    """
    analyzer = CoverageAnalyzer(project_dir)

    if file_path:
        return analyzer.analyze_file_coverage(file_path)
    else:
        return analyzer.generate_coverage_report()
