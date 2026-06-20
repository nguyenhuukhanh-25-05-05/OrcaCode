"""Validation models — structured issues and results for output/task validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ValidationSeverity(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ValidationCategory(Enum):
    OUTPUT = "output"
    TEST = "test"
    BUILD = "build"
    LINT = "lint"
    SCHEMA = "schema"
    FORMAT = "format"
    DIFF = "diff"
    CONSISTENCY = "consistency"
    STRUCTURE = "structure"
    SAFETY = "safety"


@dataclass
class ValidationIssue:
    category: ValidationCategory
    severity: ValidationSeverity
    message: str
    file: str = ""
    line: int = 0
    expected: str = ""
    actual: str = ""

    @property
    def short_label(self) -> str:
        return f"[{self.severity.value.upper()}] {self.message[:80]}"


@dataclass
class ValidationResult:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return len(self.issues) == 0

    @property
    def count(self) -> int:
        return len(self.issues)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.WARNING)

    def by_severity(self) -> dict[ValidationSeverity, list[ValidationIssue]]:
        result: dict[ValidationSeverity, list[ValidationIssue]] = {}
        for issue in self.issues:
            result.setdefault(issue.severity, []).append(issue)
        return result

    def by_category(self) -> dict[ValidationCategory, list[ValidationIssue]]:
        result: dict[ValidationCategory, list[ValidationIssue]] = {}
        for issue in self.issues:
            result.setdefault(issue.category, []).append(issue)
        return result

    def summary(self, include_passed: bool = True) -> str:
        if not self.issues:
            return "No validation issues."
        lines = [f"## Validation — {self.count} issue(s)"]
        for severity in (ValidationSeverity.ERROR, ValidationSeverity.WARNING, ValidationSeverity.INFO):
            items = [i for i in self.issues if i.severity == severity]
            if not items:
                continue
            lines.append(f"\n### {severity.value.upper()} ({len(items)})")
            for issue in items:
                loc = f" `{issue.file}`" if issue.file else ""
                lines.append(f"- [{issue.category.value}]{loc} {issue.message}")
        return "\n".join(lines)

    def merge(self, other: ValidationResult) -> ValidationResult:
        return ValidationResult(issues=self.issues + other.issues)

    @staticmethod
    def error(message: str, category: ValidationCategory = ValidationCategory.OUTPUT, file: str = "", line: int = 0) -> ValidationResult:
        return ValidationResult(issues=[
            ValidationIssue(category=category, severity=ValidationSeverity.ERROR, message=message, file=file, line=line)
        ])

    @staticmethod
    def warning(message: str, category: ValidationCategory = ValidationCategory.OUTPUT, file: str = "", line: int = 0) -> ValidationResult:
        return ValidationResult(issues=[
            ValidationIssue(category=category, severity=ValidationSeverity.WARNING, message=message, file=file, line=line)
        ])

    @staticmethod
    def ok() -> ValidationResult:
        return ValidationResult()
