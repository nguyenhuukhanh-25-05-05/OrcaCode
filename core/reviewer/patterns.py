"""Bug Pattern Detector — static analysis for common coding bugs.

Scans source files for known problematic patterns using regex and simple AST.
Each pattern has name, severity, category, message, suggestion, and optional
file-extension filter.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Optional

from core.reviewer.models import (
    ReviewCategory,
    ReviewIssue,
    ReviewResult,
    ReviewSeverity,
    make_issue,
)


@dataclass
class PatternDef:
    name: str
    severity: str
    category: str
    pattern: str  # regex pattern
    message: str
    suggestion: str
    extensions: list[str] = field(default_factory=lambda: [".py", ".js", ".ts", ".jsx", ".tsx"])
    flags: int = re.IGNORECASE

    def to_issue(self, file_path: str, line_num: int = 0, match: str = "") -> ReviewIssue:
        return make_issue(
            category=self.category,
            severity=self.severity,
            message=self.message,
            file=file_path,
            line=line_num,
            suggestion=self.suggestion,
            code=match[:200],
        )


# ── Generic regex-based patterns ───────────────────────────────────────

REGEX_PATTERNS: list[PatternDef] = [
    PatternDef(
        name="empty-except",
        severity="medium",
        category="bug",
        pattern=r"except\s*[^:]*:\s*\n\s*pass\b",
        message="Empty except block — silently swallows all errors",
        suggestion="Catch specific exceptions or at least log the error",
        extensions=[".py"],
    ),
    PatternDef(
        name="bare-except",
        severity="medium",
        category="bug",
        pattern=r"except\s*:",
        message="Bare except clause catches ALL exceptions including SystemExit",
        suggestion="Use `except Exception:` instead of bare `except:`",
        extensions=[".py"],
    ),
    PatternDef(
        name="mutable-default",
        severity="high",
        category="bug",
        pattern=r"def\s+\w+\([^)]*=\s*(\[\]|\{\}|set\(\))",
        message="Mutable default argument — shared across all calls",
        suggestion="Use `None` as default and create a new instance inside the function",
        extensions=[".py"],
    ),
    PatternDef(
        name="none-comparison",
        severity="low",
        category="style",
        pattern=r"(==\s*None|None\s*==|!=\s*None|None\s*!=)",
        message="Use `is None` / `is not None` for identity comparison instead of `==` / `!=`",
        suggestion="Use `x is None` instead of `x == None`",
        extensions=[".py"],
    ),
    PatternDef(
        name="print-statement",
        severity="low",
        category="style",
        pattern=r"^\s*print\s*\(",
        message="print() in non-debug code — use logging instead",
        suggestion="Replace print() with logger.debug() or logger.info()",
        extensions=[".py"],
        flags=re.MULTILINE,
    ),
    PatternDef(
        name="console-log",
        severity="info",
        category="style",
        pattern=r"console\.log\s*\(",
        message="console.log() left in code — remove before production",
        suggestion="Remove console.log() or replace with a proper logger",
        extensions=[".js", ".ts", ".jsx", ".tsx"],
    ),
    PatternDef(
        name="todo-fixme",
        severity="info",
        category="style",
        pattern=r"(TODO|FIXME|HACK|XXX|WORKAROUND)[\s:]",
        message="Code contains TODO/FIXME markers — incomplete work",
        suggestion="Address the marked item before considering this done",
        extensions=[".py", ".js", ".ts", ".jsx", ".tsx"],
    ),
    PatternDef(
        name="debugger-statement",
        severity="medium",
        category="bug",
        pattern=r"\b(?:debugger|breakpoint)\s*\(",
        message="Debugger/breakpoint statement left in production code",
        suggestion="Remove debugger/breakpoint statement",
        extensions=[".py", ".js", ".ts", ".jsx", ".tsx"],
    ),
    PatternDef(
        name="hardcoded-path",
        severity="low",
        category="security",
        pattern=r"['\"](?:/var|/etc|/usr|C:\\)",
        message="Hardcoded absolute path — may break on different systems",
        suggestion="Use path from config, environment variable, or os.path.join()",
        extensions=[".py", ".js", ".ts"],
    ),
]

# ── Python AST-based patterns ──────────────────────────────────────────


def _check_python_ast(file_path: str, content: str) -> list[ReviewIssue]:
    """Run AST-based checks on Python files."""
    issues: list[ReviewIssue] = []
    try:
        tree = ast.parse(content, filename=file_path)
    except SyntaxError:
        return issues  # handled elsewhere

    for node in ast.walk(tree):
        # Check for try/except with just `raise` or `pass`
        if isinstance(node, ast.Try):
            for handler in node.handlers:
                if handler.type is None and handler.name is None:
                    issues.append(make_issue(
                        category="bug",
                        severity="medium",
                        message="Bare except clause catches ALL exceptions",
                        file=file_path,
                        line=getattr(handler, 'lineno', 0),
                        suggestion="Use `except Exception:` instead",
                    ))

        # Check for assert without message
        if isinstance(node, ast.Assert):
            if node.msg is None:
                issues.append(make_issue(
                    category="style",
                    severity="low",
                    message="Assert without error message — hard to debug failures",
                    file=file_path,
                    line=getattr(node, 'lineno', 0),
                    suggestion='Add message: `assert condition, "helpful message"`',
                ))

    return issues


# ── Public API ─────────────────────────────────────────────────────────


class BugPatternDetector:
    """Static analysis for common bug patterns using regex + AST."""

    def scan_file(self, file_path: str, content: str) -> list[ReviewIssue]:
        """Scan a single file for bug patterns."""
        import os
        ext = os.path.splitext(file_path)[1].lower()
        issues: list[ReviewIssue] = []

        # Regex patterns
        for pattern_def in REGEX_PATTERNS:
            if ext not in pattern_def.extensions:
                continue
            for match in re.finditer(pattern_def.pattern, content, pattern_def.flags):
                line_num = content[:match.start()].count("\n") + 1
                issues.append(pattern_def.to_issue(file_path, line_num, match.group()))

        # AST patterns (Python only)
        if ext == ".py":
            issues.extend(_check_python_ast(file_path, content))

        return issues

    def scan_files(self, files: dict[str, str]) -> ReviewResult:
        """Scan multiple files. `files` is {relative_path: content_string}."""
        all_issues: list[ReviewIssue] = []
        for file_path, content in files.items():
            all_issues.extend(self.scan_file(file_path, content))
        return ReviewResult(issues=all_issues)
