"""DiffValidator — validates diff correctness, format, and safety."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from core.validator.models import ValidationCategory, ValidationIssue, ValidationResult, ValidationSeverity


@dataclass
class DiffHunk:
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    content: str


@dataclass
class ParsedDiff:
    old_path: str = ""
    new_path: str = ""
    hunks: list[DiffHunk] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return bool(self.old_path) and bool(self.hunks)


class DiffValidator:
    """Validates unified diffs for correctness, completeness, and safety."""

    DIFF_HEADER = re.compile(r'^---\s+(.+)$')
    DIFF_HEADER2 = re.compile(r'^\+\+\+\s+(.+)$')
    HUNK_HEADER = re.compile(r'^@@\s+-(\d+),?(\d*)\s+\+(\d+),?(\d*)\s+@@')

    DANGEROUS_PATTERNS = [
        re.compile(r'\.\./'),       # Path traversal
        re.compile(r'^~'),          # Home directory
        re.compile(r'[\\/]etc[\\/]'),  # /etc/ references
        re.compile(r'[\\/]dev[\\/]'),  # /dev/ references
    ]

    def parse_diff(self, diff_text: str) -> Optional[ParsedDiff]:
        """Parse a unified diff string into structured hunks."""
        if not diff_text or not diff_text.strip():
            return None

        result = ParsedDiff()
        current_hunk: Optional[DiffHunk] = None
        hunk_lines: list[str] = []

        for line in diff_text.splitlines():
            header_match = self.DIFF_HEADER.match(line)
            header2_match = self.DIFF_HEADER2.match(line)
            hunk_match = self.HUNK_HEADER.match(line)

            if header_match:
                result.old_path = header_match.group(1).strip()
            elif header2_match:
                result.new_path = header2_match.group(1).strip()
            elif hunk_match:
                if current_hunk and hunk_lines:
                    current_hunk.content = "\n".join(hunk_lines)
                    result.hunks.append(current_hunk)
                old_start = int(hunk_match.group(1))
                old_count = int(hunk_match.group(2)) if hunk_match.group(2) else 1
                new_start = int(hunk_match.group(3))
                new_count = int(hunk_match.group(4)) if hunk_match.group(4) else 1
                current_hunk = DiffHunk(
                    old_start=old_start, old_count=old_count,
                    new_start=new_start, new_count=new_count,
                    content="",
                )
                hunk_lines = [line]
            elif current_hunk is not None:
                hunk_lines.append(line)

        if current_hunk and hunk_lines:
            current_hunk.content = "\n".join(hunk_lines)
            result.hunks.append(current_hunk)

        return result

    def validate_diff_format(self, diff_text: str) -> ValidationResult:
        """Check diff has valid unified format."""
        issues: list[ValidationIssue] = []

        if not diff_text or not diff_text.strip():
            return ValidationResult.error("Diff is empty", category=ValidationCategory.DIFF)

        lines = diff_text.splitlines()
        has_old = any(self.DIFF_HEADER.match(l) for l in lines)
        has_new = any(self.DIFF_HEADER2.match(l) for l in lines)
        has_hunk = any(self.HUNK_HEADER.match(l) for l in lines)

        if not has_old and not has_new:
            issues.append(ValidationIssue(
                category=ValidationCategory.DIFF,
                severity=ValidationSeverity.ERROR,
                message="Diff missing file headers (---/+++)",
            ))
        if not has_hunk:
            issues.append(ValidationIssue(
                category=ValidationCategory.DIFF,
                severity=ValidationSeverity.ERROR,
                message="Diff missing hunk headers (@@ ... @@)",
            ))

        # Check for unbalanced context
        for i, line in enumerate(lines, 1):
            if line.startswith('+') and not line.startswith('+++'):
                pass
            elif line.startswith('-') and not line.startswith('---'):
                pass
            elif line.startswith(' '):
                pass
            elif line.startswith('\\') and 'No newline' in line:
                pass
            elif line.startswith('@@'):
                pass
            elif line.startswith('---') or line.startswith('+++'):
                pass
            elif not line.strip():
                pass
            else:
                issues.append(ValidationIssue(
                    category=ValidationCategory.DIFF,
                    severity=ValidationSeverity.WARNING,
                    message=f"Unexpected diff content at line {i}: {line[:60]}",
                ))

        if issues:
            return ValidationResult(issues=issues)
        return ValidationResult.ok()

    def validate_diff_paths(self, diff_text: str, project_root: str = "") -> ValidationResult:
        """Check that diff file paths exist in the project."""
        issues: list[ValidationIssue] = []

        for line in diff_text.splitlines():
            m = self.DIFF_HEADER2.match(line)
            if m:
                path = m.group(1).strip()
                if path.startswith('b/'):
                    path = path[2:]

                if path == "/dev/null":
                    continue

                full_path = Path(project_root, path) if project_root else Path(path)
                if not full_path.exists() and not full_path.parent.exists():
                    issues.append(ValidationIssue(
                        category=ValidationCategory.DIFF,
                        severity=ValidationSeverity.WARNING,
                        message=f"Diff references non-existent directory: {path}",
                        file=path,
                    ))

        if issues:
            return ValidationResult(issues=issues)
        return ValidationResult.ok()

    def validate_diff_no_dangerous(self, diff_text: str) -> ValidationResult:
        """Check diff for dangerous paths (traversal, system files)."""
        issues: list[ValidationIssue] = []

        for line in diff_text.splitlines():
            for m in self.DANGEROUS_PATTERNS:
                if m.search(line):
                    issues.append(ValidationIssue(
                        category=ValidationCategory.SAFETY,
                        severity=ValidationSeverity.ERROR,
                        message=f"Diff contains dangerous path pattern: {line.strip()}",
                    ))

        if issues:
            return ValidationResult(issues=issues)
        return ValidationResult.ok()

    def validate_diff_complete(self, parsed: ParsedDiff, expected_files: set[str]) -> ValidationResult:
        """Check that a parsed diff covers all expected files."""
        if not parsed or not parsed.is_valid:
            return ValidationResult.error("Cannot validate empty/invalid diff", category=ValidationCategory.DIFF)

        diff_file = parsed.new_path
        if diff_file.startswith('b/'):
            diff_file = diff_file[2:]
        if diff_file == "/dev/null":
            diff_file = ""

        issues: list[ValidationIssue] = []
        if diff_file and diff_file not in expected_files:
            issues.append(ValidationIssue(
                category=ValidationCategory.DIFF,
                severity=ValidationSeverity.WARNING,
                message=f"Diff modifies '{diff_file}' which was not in expected files",
                file=diff_file,
            ))

        if issues:
            return ValidationResult(issues=issues)
        return ValidationResult.ok()

    def validate_diff(self, diff_text: str, project_root: str = "", expected_files: Optional[set[str]] = None) -> ValidationResult:
        """Run all diff validations."""
        result = ValidationResult.ok()

        result = result.merge(self.validate_diff_format(diff_text))
        result = result.merge(self.validate_diff_no_dangerous(diff_text))
        result = result.merge(self.validate_diff_paths(diff_text, project_root))

        if expected_files:
            parsed = self.parse_diff(diff_text)
            if parsed:
                result = result.merge(self.validate_diff_complete(parsed, expected_files))

        return result
