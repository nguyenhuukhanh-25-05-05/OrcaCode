"""ResultValidator — validates task outputs, test results, build logs, and file integrity."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

from core.validator.models import ValidationCategory, ValidationIssue, ValidationResult, ValidationSeverity


class ResultValidator:
    """Validates task execution outputs — test results, build logs, file consistency."""

    TEST_PASS_PATTERNS = [
        re.compile(r"(?:^|\n)\s*(?:ok|PASS|✓|√|passed)\s*\d", re.IGNORECASE),
        re.compile(r"(?:^|\n)\s*\d+\s*(?:passed|succeeded)", re.IGNORECASE),
        re.compile(r"tests?\s+(?:passed|complete)", re.IGNORECASE),
    ]

    TEST_FAIL_PATTERNS = [
        re.compile(r"(?:^|\n)\s*(?:FAIL|✗|×|failed|error)", re.IGNORECASE),
        re.compile(r"(?:^|\n)\s*\d+\s*(?:failed|errors?)", re.IGNORECASE),
    ]

    TEST_SKIP_PATTERNS = [
        re.compile(r"(?:^|\n)\s*(?:skip|SKIP|skipped)", re.IGNORECASE),
        re.compile(r"no\s+tests?\s+(?:found|ran|run)", re.IGNORECASE),
    ]

    BUILD_SUCCESS_PATTERNS = [
        re.compile(r"(?:^|\n)\s*(?:build\s+(?:succeeded|successful|complete|done|passed))", re.IGNORECASE),
        re.compile(r"(?:^|\n)\s*(?:compilation\s+succeeded)", re.IGNORECASE),
        re.compile(r"(?:^|\n)\s*(?:compiled\s+successfully)", re.IGNORECASE),
        re.compile(r"exit.code\s*0", re.IGNORECASE),
    ]

    BUILD_ERROR_PATTERNS = [
        re.compile(r"(?:^|\n)\s*(?:build\s+(?:failed|error|aborted))", re.IGNORECASE),
        re.compile(r"(?:^|\n)\s*(?:compilation\s+(?:error|failed))", re.IGNORECASE),
        re.compile(r"(?:^|\n)\s*error:", re.IGNORECASE),
    ]

    WARNING_PATTERNS = [
        re.compile(r"(?:^|\n)\s*warning:", re.IGNORECASE),
    ]

    def validate_test_output(self, output: str, tool_name: str = "") -> ValidationResult:
        """Check test output for pass/fail signals."""
        issues: list[ValidationIssue] = []
        category = ValidationCategory.TEST

        if not output or not output.strip():
            return ValidationResult.error("No test output produced.", category=category, file=tool_name)

        has_pass = any(p.search(output) for p in self.TEST_PASS_PATTERNS)
        has_fail = any(p.search(output) for p in self.TEST_FAIL_PATTERNS)
        has_skip = any(p.search(output) for p in self.TEST_SKIP_PATTERNS)

        if has_skip and not has_pass and not has_fail:
            return ValidationResult.warning("Tests found but all skipped.", category=category, file=tool_name)

        if has_fail:
            return ValidationResult.error("Test output contains failures.", category=category, file=tool_name)

        if not has_pass:
            return ValidationResult.warning("No clear pass signal in test output.", category=category, file=tool_name)

        return ValidationResult.ok()

    def validate_build_output(self, output: str, tool_name: str = "") -> ValidationResult:
        """Check build output for success/error signals."""
        if not output or not output.strip():
            return ValidationResult.warning("No build output produced.", category=ValidationCategory.BUILD, file=tool_name)

        has_success = any(p.search(output) for p in self.BUILD_SUCCESS_PATTERNS)
        has_error = any(p.search(output) for p in self.BUILD_ERROR_PATTERNS)

        if has_error:
            return ValidationResult.error("Build output contains errors.", category=ValidationCategory.BUILD, file=tool_name)

        warning_count = len([p for p in self.WARNING_PATTERNS if p.search(output)])
        result = ValidationResult.ok()
        if warning_count > 0:
            result = result.merge(
                ValidationResult.warning(f"{warning_count} warning(s) in build output.", category=ValidationCategory.BUILD, file=tool_name)
            )
        if not has_success:
            result = result.merge(
                ValidationResult.warning("No clear success signal in build output.", category=ValidationCategory.BUILD, file=tool_name)
            )
        return result

    def validate_output_contains(self, output: str, expected: str, message: str = "", file: str = "") -> ValidationResult:
        """Check that output contains an expected string."""
        if expected not in output:
            return ValidationResult.error(
                message or f"Output should contain: {expected[:80]}",
                category=ValidationCategory.OUTPUT,
                file=file,
            )
        return ValidationResult.ok()

    def validate_output_lacks(self, output: str, forbidden: str, message: str = "", file: str = "") -> ValidationResult:
        """Check that output does NOT contain a forbidden string."""
        if forbidden in output:
            return ValidationResult.error(
                message or f"Output should not contain: {forbidden[:80]}",
                category=ValidationCategory.OUTPUT,
                file=file,
            )
        return ValidationResult.ok()

    def validate_exit_code(self, exit_code: int, tool_name: str = "") -> ValidationResult:
        """Check exit code is 0."""
        if exit_code != 0:
            return ValidationResult.error(
                f"Exit code {exit_code} (expected 0)",
                category=ValidationCategory.OUTPUT,
                file=tool_name,
            )
        return ValidationResult.ok()

    def validate_file_exists(self, path: str) -> ValidationResult:
        """Check that a file exists on disk."""
        if not Path(path).exists():
            return ValidationResult.error(
                f"File does not exist: {path}",
                category=ValidationCategory.CONSISTENCY,
                file=path,
            )
        return ValidationResult.ok()

    def validate_file_not_empty(self, path: str) -> ValidationResult:
        """Check that a file is not empty."""
        p = Path(path)
        if not p.exists():
            return ValidationResult.error(
                f"File does not exist: {path}",
                category=ValidationCategory.CONSISTENCY,
                file=path,
            )
        if p.stat().st_size == 0:
            return ValidationResult.warning(
                f"File is empty: {path}",
                category=ValidationCategory.CONSISTENCY,
                file=path,
            )
        return ValidationResult.ok()

    def validate_file_encoding(self, path: str, expected_encoding: str = "utf-8") -> ValidationResult:
        """Check that a file is valid in the expected encoding."""
        try:
            Path(path).read_text(encoding=expected_encoding)
            return ValidationResult.ok()
        except UnicodeDecodeError:
            return ValidationResult.error(
                f"File is not valid {expected_encoding}: {path}",
                category=ValidationCategory.FORMAT,
                file=path,
            )
        except FileNotFoundError:
            return ValidationResult.error(f"File not found: {path}", category=ValidationCategory.CONSISTENCY, file=path)

    def validate_task_summary(self, summary: str, modified_files: set[str]) -> ValidationResult:
        """Validate that the AI task summary is consistent with actual changes."""
        issues: list[ValidationIssue] = []

        for f in modified_files:
            fname = os.path.basename(f)
            if fname and fname not in summary:
                issues.append(ValidationIssue(
                    category=ValidationCategory.CONSISTENCY,
                    severity=ValidationSeverity.WARNING,
                    message=f"Modified file '{f}' not mentioned in task summary.",
                    file=f,
                ))

        if issues:
            return ValidationResult(issues=issues)
        return ValidationResult.ok()

    def validate_results_consistency(self, results: list[dict], modified_files: set[str]) -> ValidationResult:
        """Check that execution results reference actually modified files."""
        issues: list[ValidationIssue] = []

        for r in results:
            path = r.get("path", "")
            if path and path not in modified_files:
                issues.append(ValidationIssue(
                    category=ValidationCategory.CONSISTENCY,
                    severity=ValidationSeverity.WARNING,
                    message=f"Result references '{path}' but it was not modified.",
                    file=path,
                ))

        if issues:
            return ValidationResult(issues=issues)
        return ValidationResult.ok()
