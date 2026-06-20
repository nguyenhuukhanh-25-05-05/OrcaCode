"""Two-Phase Review — Phase 1: SpecReviewer (pre-execution plan review).

Phase 1 (Spec Review) runs BEFORE code execution. It independently evaluates the
plan/spec for:
  1. Coverage — edge cases, error handling, dependencies
  2. Consistency — no contradictions between steps
  3. Completeness — all user requirements addressed
  4. Risk — high-risk operations identified
  5. Testability — verifiable done conditions

Phase 2 (Code Review) is handled by the existing ReviewerAgent + validators.

Flow: PLAN → SPEC_REVIEW → APPROVE → EXECUTE → CODE_REVIEW → DONE
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import ClassVar, Optional

logger = logging.getLogger("orca.spec_reviewer")


class SpecIssueSeverity(Enum):
    BLOCKING = "blocking"   # Must fix before execution
    HIGH = "high"           # Significant gap, should fix
    MEDIUM = "medium"       # Potential issue, recommend fix
    LOW = "low"             # Minor concern
    INFO = "info"           # Advisory suggestion


class SpecIssueCategory(Enum):
    COVERAGE = "coverage"           # Missing edge cases or scenarios
    CONSISTENCY = "consistency"     # Contradictions between steps
    COMPLETENESS = "completeness"   # Missing steps or requirements
    RISK = "risk"                   # High-risk operations
    DEPENDENCY = "dependency"       # Missing or unclear dependencies
    TESTABILITY = "testability"     # Unclear how to verify completion
    ARCHITECTURE = "architecture"   # Architectural concerns
    SECURITY = "security"           # Security implications
    PERFORMANCE = "performance"     # Performance implications
    MAINTAINABILITY = "maintainability"  # Long-term maintenance


@dataclass
class SpecIssue:
    """A single issue found during spec review."""
    severity: SpecIssueSeverity
    category: SpecIssueCategory
    message: str
    suggestion: str = ""
    references: list[str] = field(default_factory=list)  # Plan steps/files

    def format_rich(self) -> str:
        icon = {
            SpecIssueSeverity.BLOCKING: "🛑",
            SpecIssueSeverity.HIGH: "🔴",
            SpecIssueSeverity.MEDIUM: "🟡",
            SpecIssueSeverity.LOW: "🔵",
            SpecIssueSeverity.INFO: "⚪",
        }[self.severity]
        lines = [
            f"{icon} [{self.severity.value.upper()}] [{self.category.value}] {self.message}",
        ]
        if self.suggestion:
            lines.append(f"   💡 Suggestion: {self.suggestion}")
        if self.references:
            lines.append(f"   📎 Refs: {', '.join(self.references)}")
        return "\n".join(lines)


@dataclass
class SpecReviewReport:
    """Complete spec review report with pass/fail and all issues."""
    issues: list[SpecIssue] = field(default_factory=list)
    plan_summary: str = ""
    coverage_score: float = 1.0      # 0.0-1.0

    @property
    def passed(self) -> bool:
        return not any(i.severity == SpecIssueSeverity.BLOCKING for i in self.issues)

    @property
    def blocking_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == SpecIssueSeverity.BLOCKING)

    @property
    def high_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == SpecIssueSeverity.HIGH)

    def format_compact(self) -> str:
        blocking = self.blocking_count
        high = self.high_count
        medium = sum(1 for i in self.issues if i.severity == SpecIssueSeverity.MEDIUM)

        status = "❌ BLOCKED" if blocking > 0 else "⚠️ REVIEW" if high > 0 else "✅ PASSED"
        lines = [
            f"## Spec Review: {status}",
            f"Score: {self.coverage_score:.0%} | "
            f"Issues: {blocking} blocking, {high} high, {medium} medium",
            "",
        ]

        for issue in self.issues[:15]:
            lines.append(issue.format_rich())
            lines.append("")

        if len(self.issues) > 15:
            lines.append(f"... and {len(self.issues) - 15} more issues")

        return "\n".join(lines)


# ── Deterministic Rule Set ──────────────────────────────

class SpecReviewer:
    """Deterministic spec/plan reviewer — no LLM required for core checks.

    Reviews plans for structural and semantic quality before execution.
    Augments the existing PlanValidator (mechanical checks) with semantic
    analysis.
    """

    # High-risk patterns now delegated to RiskChecker.check_plan() (avoiding duplication)
    # See _check_high_risk() below.

    # Keywords suggesting missing error handling
    ERROR_HANDLING_KEYWORDS: ClassVar[list[str]] = [
        "handle error", "handle errors", "error handling",
        "exception handling", "fallback", "retry",
        "validation", "validate input", "input validation",
        "xử lý lỗi", "bắt lỗi", "kiểm tra đầu vào",
    ]

    # Keywords suggesting missing edge case consideration
    EDGE_CASE_KEYWORDS: ClassVar[list[str]] = [
        "edge case", "empty input", "null", "undefined",
        "timeout", "concurrent", "race condition",
        "large file", "large input", "many users",
        "trường hợp biên", "đầu vào rỗng",
    ]

    # Keywords suggesting missing testing consideration
    TESTING_KEYWORDS: ClassVar[list[str]] = [
        "test", "unit test", "integration test", "e2e test",
        "pytest", "jest", "vitest", "coverage",
        "kiểm thử", "test case", "unit test", "integration test",
    ]

    # File types that should be backed up before modification
    SENSITIVE_FILES: ClassVar[tuple[str, ...]] = (
        ".env", "package.json", "pyproject.toml", "Cargo.toml",
        "Dockerfile", "docker-compose.yml", "Makefile",
        ".gitignore", ".gitlab-ci.yml", ".github/workflows",
        "config.py", "settings.py", "constants.py", "types.py",
    )

    def __init__(self):
        pass

    def review_plan(self, plan_text: str,
                    user_prompt: str = "",
                    modified_files: Optional[list[str]] = None) -> SpecReviewReport:
        """Review a plan text for spec-quality issues.

        Args:
            plan_text: The AI-generated plan (JSON or text).
            user_prompt: Original user request (for completeness checking).
            modified_files: Files mentioned in the plan.

        Returns:
            SpecReviewReport with all issues found.
        """
        report = SpecReviewReport(plan_summary=plan_text[:200])

        plan_lower = plan_text.lower()
        user_lower = user_prompt.lower() if user_prompt else ""

        # ── 1. Coverage: Missing edge cases ──
        report.issues.extend(self._check_edge_case_coverage(plan_text, plan_lower))

        # ── 2. Coverage: Missing error handling ──
        report.issues.extend(self._check_error_handling(plan_text, plan_lower, user_prompt))

        # ── 3. Consistency: Contradictions ──
        report.issues.extend(self._check_consistency(plan_text, plan_lower))

        # ── 4. Completeness: Missing requirements ──
        report.issues.extend(self._check_completeness(plan_text, user_prompt))

        # ── 5. Risk: High-risk operations ──
        report.issues.extend(self._check_high_risk(plan_text, plan_lower))

        # ── 6. Dependency: Missing dependency consideration ──
        report.issues.extend(self._check_dependencies(plan_text))

        # ── 7. Testability: Missing done conditions ──
        report.issues.extend(self._check_testability(plan_text, plan_lower))

        # ── 8. Architecture: Sensitive file changes ──
        report.issues.extend(self._check_sensitive_files(plan_text, modified_files or []))

        # ── 9. Security: Input validation ──
        report.issues.extend(self._check_security_concerns(plan_text, plan_lower))

        # ── Compute coverage score ──
        blocking = sum(1 for i in report.issues if i.severity == SpecIssueSeverity.BLOCKING)
        high = sum(1 for i in report.issues if i.severity == SpecIssueSeverity.HIGH)
        medium = sum(1 for i in report.issues if i.severity == SpecIssueSeverity.MEDIUM)
        total = max(1, len(report.issues))
        report.coverage_score = max(0.0, 1.0 - (blocking * 0.3 + high * 0.15 + medium * 0.05) / total)

        return report

    # ── Individual checks ───────────────────────────────

    def _check_edge_case_coverage(self, plan_text: str, plan_lower: str) -> list[SpecIssue]:
        issues = []
        if not any(kw in plan_lower for kw in self.EDGE_CASE_KEYWORDS):
            # Check if plan involves operations that typically need edge cases
            risky_ops = ["input", "user", "file", "api", "parse", "convert", "migrate"]
            triggered = [op for op in risky_ops if op in plan_lower]
            if len(triggered) >= 2:
                issues.append(SpecIssue(
                    severity=SpecIssueSeverity.MEDIUM,
                    category=SpecIssueCategory.COVERAGE,
                    message=f"Plan involves {', '.join(triggered)} but no edge case consideration detected",
                    suggestion="Consider adding: empty input, large files, timeout, error responses",
                ))
        return issues

    def _check_error_handling(self, plan_text: str, plan_lower: str,
                              user_prompt: str) -> list[SpecIssue]:
        issues = []
        has_error_keywords = any(kw in plan_lower for kw in self.ERROR_HANDLING_KEYWORDS)

        # Detect operations that typically need error handling
        io_ops = ["read", "write", "fetch", "connect", "query", "execute", "run"]
        has_io = any(op in plan_lower for op in io_ops)

        if has_io and not has_error_keywords:
            issues.append(SpecIssue(
                severity=SpecIssueSeverity.HIGH,
                category=SpecIssueCategory.COVERAGE,
                message="Plan involves I/O operations but no error handling specified",
                suggestion="Add error handling for: network failures, file not found, permission denied",
            ))

        return issues

    def _check_consistency(self, plan_text: str, plan_lower: str) -> list[SpecIssue]:
        issues = []
        # Check for create+delete of same file (might be fine, flag as info)
        created_files = set(re.findall(r'(?:create|add|tạo|thêm)\s+["\']?([\w/\-\.]+)', plan_lower))
        deleted_files = set(re.findall(r'(?:delete|remove|xóa|remove)\s+["\']?([\w/\-\.]+)', plan_lower))
        conflict = created_files & deleted_files
        for f in conflict:
            issues.append(SpecIssue(
                severity=SpecIssueSeverity.MEDIUM,
                category=SpecIssueCategory.CONSISTENCY,
                message=f"File '{f}' appears in both create and delete actions — verify intent",
                references=[f],
            ))

        # Check for contradictory actions on same resource
        if "rename" in plan_lower and "create" in plan_lower:
            # Might rename old and create new — flag for verification
            pass

        return issues

    def _check_completeness(self, plan_text: str, user_prompt: str) -> list[SpecIssue]:
        issues = []
        if not user_prompt:
            return issues

        user_lower = user_prompt.lower()
        plan_lower = plan_text.lower()

        # Check if user mentioned testing but plan doesn't
        test_keywords_in_user = [
            kw for kw in ("test", "kiểm thử", "unit test", "integration test")
            if kw in user_lower
        ]
        test_keywords_in_plan = [
            kw for kw in ("test", "kiểm thử", "unit test", "integration test")
            if kw in plan_lower
        ]
        if test_keywords_in_user and not test_keywords_in_plan:
            issues.append(SpecIssue(
                severity=SpecIssueSeverity.HIGH,
                category=SpecIssueCategory.COMPLETENESS,
                message="User mentioned testing requirements but plan has no test steps",
                suggestion="Add testing step(s) for the changes",
            ))

        # Check if user mentioned documentation but plan doesn't
        doc_keywords = ["documentation", "readme", "docs", "tài liệu", "hướng dẫn"]
        if any(kw in user_lower for kw in doc_keywords) and not any(kw in plan_lower for kw in doc_keywords):
            issues.append(SpecIssue(
                severity=SpecIssueSeverity.MEDIUM,
                category=SpecIssueCategory.COMPLETENESS,
                message="User mentioned documentation but plan has no documentation steps",
                suggestion="Add documentation update step",
            ))

        return issues

    def _check_high_risk(self, plan_text: str, plan_lower: str) -> list[SpecIssue]:
        """Delegate plan risk checking to RiskChecker (single source of truth)."""
        from core.services.risk_checker import RiskChecker
        checker = RiskChecker()
        risk_levels = checker.check_plan(plan_text)
        issues = []
        for rl in risk_levels:
            if rl.level in ("critical", "high"):
                severity = SpecIssueSeverity.BLOCKING if rl.level == "critical" else SpecIssueSeverity.HIGH
                issues.append(SpecIssue(
                    severity=severity,
                    category=SpecIssueCategory.RISK,
                    message=f"High-risk operation: {rl.reason}",
                    suggestion="Ensure backup exists before proceeding. Consider adding a rollback step.",
                ))
        return issues

    def _check_dependencies(self, plan_text: str) -> list[SpecIssue]:
        issues = []
        plan_lower = plan_text.lower()

        # Extract module/package names from plan
        imports = set(re.findall(r'(?:import|from)\s+["\']?(\w+)', plan_lower))
        installs = set(re.findall(r'(?:install|pip install|npm install|add)\s+["\']?(\S+)', plan_lower))

        if installs and len(installs) > 2:
            issues.append(SpecIssue(
                severity=SpecIssueSeverity.LOW,
                category=SpecIssueCategory.DEPENDENCY,
                message=f"Plan adds {len(installs)} new dependencies — review necessity",
                suggestion="Consider if existing deps can serve the same purpose",
            ))

        return issues

    def _check_testability(self, plan_text: str, plan_lower: str) -> list[SpecIssue]:
        issues = []

        has_testing = any(kw in plan_lower for kw in self.TESTING_KEYWORDS)
        has_done_condition = "<PLAN_DONE" in plan_text or "done condition" in plan_lower

        # Modifying code without testing plan
        file_actions = ["modify", "create", "write", "edit", "refactor", "patch"]
        has_code_action = any(f" {a} " in f" {plan_lower} " for a in file_actions)

        if has_code_action and not has_testing and not has_done_condition:
            issues.append(SpecIssue(
                severity=SpecIssueSeverity.MEDIUM,
                category=SpecIssueCategory.TESTABILITY,
                message="Plan includes code changes but no testing or verification criteria",
                suggestion="Add test steps or done conditions to verify changes work correctly",
            ))

        return issues

    def _check_sensitive_files(self, plan_text: str,
                               modified_files: list[str]) -> list[SpecIssue]:
        issues = []
        for f in modified_files:
            basename = f.split("/")[-1].split("\\")[-1]
            if basename in self.SENSITIVE_FILES:
                issues.append(SpecIssue(
                    severity=SpecIssueSeverity.HIGH,
                    category=SpecIssueCategory.ARCHITECTURE,
                    message=f"Plan modifies sensitive file: '{f}'",
                    suggestion="This file affects project-wide configuration. Verify changes carefully before applying.",
                    references=[f],
                ))
        return issues

    def _check_security_concerns(self, plan_text: str, plan_lower: str) -> list[SpecIssue]:
        issues = []

        # Input validation
        input_patterns = ["input", "user input", "form", "request body", "query param"]
        has_input = any(p in plan_lower for p in input_patterns)
        has_validation = any(kw in plan_lower for kw in [
            "validate", "sanitize", "escape", "xác thực", "kiểm tra",
            "validation", "sanitization",
        ])

        if has_input and not has_validation:
            issues.append(SpecIssue(
                severity=SpecIssueSeverity.HIGH,
                category=SpecIssueCategory.SECURITY,
                message="Plan handles user input but no input validation is mentioned",
                suggestion="Add input validation steps: type checking, sanitization, length limits",
            ))

        # Auth/permission changes
        auth_patterns = ["auth", "login", "permission", "role", "token", "password"]
        has_auth = any(p in plan_lower for p in auth_patterns)
        has_security_review = "security" in plan_lower or "review" in plan_lower

        if has_auth and not has_security_review:
            issues.append(SpecIssue(
                severity=SpecIssueSeverity.HIGH,
                category=SpecIssueCategory.SECURITY,
                message="Plan modifies auth/permission logic but no security review step",
                suggestion="Add a security review step: verify token handling, check OWASP guidelines",
            ))

        return issues


# ── Quick pre-flight check ──────────────────────────────

def quick_spec_check(plan_text: str, user_prompt: str = "",
                     files: Optional[list[str]] = None) -> tuple[bool, str]:
    """Lightweight spec check — returns (ok, message) for simple gate decisions.

    Use this before calling full SpecReviewer for plans that need BLOCKING
    gate check.
    """
    reviewer = SpecReviewer()
    report = reviewer.review_plan(plan_text, user_prompt, files or [])

    if not report.passed:
        return False, report.format_compact()

    if report.high_count > 0:
        return True, f"⚠️ Spec review passed with {report.high_count} high-severity suggestions:\n" + report.format_compact()

    return True, "✅ Spec review passed"
