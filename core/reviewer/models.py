"""Review models — structured issues and results for code review."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ReviewSeverity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ReviewCategory(Enum):
    BUG = "bug"
    SECURITY = "security"
    PERFORMANCE = "performance"
    EDGE_CASE = "edge_case"
    ARCHITECTURE = "architecture"
    STYLE = "style"
    REQUIREMENT = "requirement"
    ACCESSIBILITY = "accessibility"


@dataclass
class ReviewIssue:
    category: ReviewCategory
    severity: ReviewSeverity
    message: str
    file: str = ""
    line: int = 0
    column: int = 0
    suggestion: str = ""
    code: str = ""

    @property
    def short_label(self) -> str:
        return f"[{self.severity.value.upper()}] {self.message[:80]}"

    @property
    def location(self) -> str:
        if self.file and self.line:
            return f"{self.file}:{self.line}"
        if self.file:
            return self.file
        return ""


@dataclass
class ReviewResult:
    issues: list[ReviewIssue] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return len(self.issues) == 0

    @property
    def count(self) -> int:
        return len(self.issues)

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == ReviewSeverity.CRITICAL)

    @property
    def high_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == ReviewSeverity.HIGH)

    def by_severity(self) -> dict[ReviewSeverity, list[ReviewIssue]]:
        result: dict[ReviewSeverity, list[ReviewIssue]] = {}
        for issue in self.issues:
            result.setdefault(issue.severity, []).append(issue)
        return result

    def by_category(self) -> dict[ReviewCategory, list[ReviewIssue]]:
        result: dict[ReviewCategory, list[ReviewIssue]] = {}
        for issue in self.issues:
            result.setdefault(issue.category, []).append(issue)
        return result

    def summary(self, include_passed: bool = True) -> str:
        if not self.issues:
            return "[OK] No issues found."
        lines = [f"## Review Result — {self.count} issue(s)"]
        for severity in (ReviewSeverity.CRITICAL, ReviewSeverity.HIGH, ReviewSeverity.MEDIUM, ReviewSeverity.LOW, ReviewSeverity.INFO):
            items = [i for i in self.issues if i.severity == severity]
            if not items:
                continue
            lines.append(f"\n### {severity.value.upper()} ({len(items)})")
            for issue in items:
                loc = f" `{issue.location}`" if issue.location else ""
                lines.append(f"- [{issue.category.value}]{loc} {issue.message}")
                if issue.suggestion:
                    lines.append(f"  → {issue.suggestion}")
        return "\n".join(lines)

    def merge(self, other: ReviewResult) -> ReviewResult:
        return ReviewResult(issues=self.issues + other.issues)


def make_issue(
    category: str,
    severity: str,
    message: str,
    file: str = "",
    line: int = 0,
    column: int = 0,
    suggestion: str = "",
    code: str = "",
) -> ReviewIssue:
    return ReviewIssue(
        category=ReviewCategory(category),
        severity=ReviewSeverity(severity),
        message=message,
        file=file,
        line=line,
        column=column,
        suggestion=suggestion,
        code=code,
    )
