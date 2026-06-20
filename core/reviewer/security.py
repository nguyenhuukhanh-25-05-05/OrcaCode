"""Security Scanner — static analysis for security vulnerabilities.

Scans source files for common security issues:
  - Hardcoded secrets (API keys, passwords, tokens)
  - SQL injection (string interpolation in queries)
  - Command injection (shell=True, os.system)
  - Path traversal
  - XSS (dangerous innerHTML, document.write)
  - Insecure deserialization (pickle, eval, yaml.load)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from core.reviewer.models import (
    ReviewCategory,
    ReviewIssue,
    ReviewResult,
    ReviewSeverity,
    make_issue,
)


@dataclass
class SecurityPattern:
    name: str
    severity: str
    pattern: str
    message: str
    suggestion: str
    extensions: list[str] = field(default_factory=lambda: [".py", ".js", ".ts", ".jsx", ".tsx"])
    flags: int = re.IGNORECASE

    def to_issue(self, file_path: str, line_num: int = 0, match: str = "") -> ReviewIssue:
        return make_issue(
            category="security",
            severity=self.severity,
            message=self.message,
            file=file_path,
            line=line_num,
            suggestion=self.suggestion,
            code=match[:200],
        )


SECURITY_PATTERNS: list[SecurityPattern] = [
    # ── Hardcoded secrets ──────────────────────────────────────────────
    SecurityPattern(
        name="api-key",
        severity="critical",
        pattern=r"""(?i)(?:api[_-]?key|apikey|secret|password|passwd|pwd|token|credential)\s*[:=]\s*['\"][A-Za-z0-9_\-+=/]{16,}['\"]""",
        message="Hardcoded API key or secret detected",
        suggestion="Use environment variable or .env file instead",
    ),
    SecurityPattern(
        name="aws-key",
        severity="critical",
        pattern=r"(?i)AKIA[0-9A-Z]{16}",
        message="Hardcoded AWS Access Key ID detected",
        suggestion="Remove key and use IAM roles or environment variables",
    ),
    SecurityPattern(
        name="private-key",
        severity="critical",
        pattern=r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
        message="Private key hardcoded in source",
        suggestion="Remove private key and use a secrets manager",
        extensions=[".py", ".js", ".ts", ".jsx", ".tsx", ".md", ".yaml", ".yml", ".json", ".pem", ".key"],
    ),

    # ── SQL injection ──────────────────────────────────────────────────
    SecurityPattern(
        name="sql-injection-f-string",
        severity="critical",
        pattern=r"(execute|cursor\.execute|executescript|run|query)\s*\(\s*[fF]['\"]",
        message="SQL query with f-string interpolation — SQL injection risk",
        suggestion="Use parameterized queries (execute with ? or %s placeholders)",
        flags=re.IGNORECASE,
    ),
    SecurityPattern(
        name="sql-injection-concat",
        severity="critical",
        pattern=r"(execute|cursor\.execute|executescript|run|query)\s*\([^)]*\+",
        message="SQL query built with string concatenation — SQL injection risk",
        suggestion="Use parameterized queries",
        flags=re.IGNORECASE,
    ),
    SecurityPattern(
        name="sql-injection-format",
        severity="critical",
        pattern=r"(execute|cursor\.execute|executescript|run|query)\s*\([^)]*\.format\(",
        message="SQL query uses .format() — SQL injection risk",
        suggestion="Use parameterized queries",
        flags=re.IGNORECASE,
    ),

    # ── Command injection ──────────────────────────────────────────────
    SecurityPattern(
        name="shell-true",
        severity="critical",
        pattern=r"subprocess\.(?:run|Popen|call|check_call|check_output)\s*\([^)]*shell\s*=\s*True",
        message="subprocess with shell=True — command injection risk",
        suggestion="Avoid shell=True; pass command as a list instead",
        extensions=[".py"],
    ),
    SecurityPattern(
        name="os-system",
        severity="high",
        pattern=r"os\.system\s*\(",
        message="os.system() called — command injection risk",
        suggestion="Use subprocess.run() with a command list",
        extensions=[".py"],
    ),
    SecurityPattern(
        name="os-popen",
        severity="high",
        pattern=r"os\.popen\s*\(",
        message="os.popen() called — command injection risk",
        suggestion="Use subprocess.run() with a command list",
        extensions=[".py"],
    ),

    # ── Path traversal ─────────────────────────────────────────────────
    SecurityPattern(
        name="path-traversal-join",
        severity="high",
        pattern=r"""os\.path\.join\s*\([^)]*request""",
        message="Path constructed with user input — path traversal risk",
        suggestion="Validate and sanitize user input before path construction",
    ),
    SecurityPattern(
        name="open-user-input",
        severity="high",
        pattern=r"""open\s*\(\s*(?:request|args|kwargs)""",
        message="Opening file with user-controlled path — path traversal risk",
        suggestion="Validate file path against an allowlist",
    ),

    # ── XSS ────────────────────────────────────────────────────────────
    SecurityPattern(
        name="innerHTML",
        severity="high",
        pattern=r"""\.innerHTML\s*= """,
        message="Setting innerHTML with user data — XSS risk",
        suggestion="Use textContent or sanitize input before setting innerHTML",
        extensions=[".js", ".ts", ".jsx", ".tsx"],
    ),
    SecurityPattern(
        name="document-write",
        severity="high",
        pattern=r"""document\.write\s*\(""",
        message="document.write() — can introduce XSS vulnerabilities",
        suggestion="Use DOM manipulation methods instead",
        extensions=[".js", ".ts", ".jsx", ".tsx"],
    ),
    SecurityPattern(
        name="dangerouslySetInnerHTML",
        severity="high",
        pattern=r"""dangerouslySetInnerHTML""",
        message="React dangerouslySetInnerHTML used — XSS risk",
        suggestion="Sanitize HTML with DOMPurify or use a safer approach",
        extensions=[".jsx", ".tsx"],
    ),

    # ── Insecure deserialization ───────────────────────────────────────
    SecurityPattern(
        name="pickle-load",
        severity="critical",
        pattern=r"""pickle\.(load|loads)\s*\(""",
        message="pickle.load/loads — insecure deserialization can execute arbitrary code",
        suggestion="Use a safer format like JSON for untrusted data",
        extensions=[".py"],
    ),
    SecurityPattern(
        name="yaml-load",
        severity="high",
        pattern=r"""yaml\.load\s*\((?!.*Loader=yaml\.SafeLoader)""",
        message="yaml.load() without SafeLoader — can execute arbitrary code",
        suggestion="Use yaml.safe_load() instead",
        extensions=[".py"],
    ),
    SecurityPattern(
        name="eval-used",
        severity="critical",
        pattern=r"""\beval\s*\(""",
        message="eval() called — arbitrary code execution risk",
        suggestion="Avoid eval(); use safer alternatives",
    ),
    SecurityPattern(
        name="exec-used",
        severity="critical",
        pattern=r"""\bexec\s*\(""",
        message="exec() called — arbitrary code execution risk",
        suggestion="Avoid exec(); use safer alternatives",
        extensions=[".py"],
    ),

    # ── Insecure request ───────────────────────────────────────────────
    SecurityPattern(
        name="requests-verify-false",
        severity="high",
        pattern=r'requests\.(?:get|post|put|delete|patch|head)\s*\([^)]*verify\s*=\s*False',
        message="SSL/TLS verification disabled for HTTP request",
        suggestion="Remove verify=False to enable certificate verification",
        extensions=[".py"],
    ),
]


class SecurityScanner:
    """Static analysis for security vulnerabilities.

    Scans source files for hardcoded secrets, injection risks, XSS, etc.
    """

    def scan_file(self, file_path: str, content: str) -> list[ReviewIssue]:
        """Scan a single file for security issues."""
        import os
        ext = os.path.splitext(file_path)[1].lower()
        issues: list[ReviewIssue] = []

        for pattern_def in SECURITY_PATTERNS:
            if ext not in pattern_def.extensions:
                continue
            for match in re.finditer(pattern_def.pattern, content, pattern_def.flags):
                line_num = content[:match.start()].count("\n") + 1
                issues.append(pattern_def.to_issue(file_path, line_num, match.group()))

        return issues

    def scan_files(self, files: dict[str, str]) -> ReviewResult:
        """Scan multiple files. `files` is {relative_path: content_string}."""
        all_issues: list[ReviewIssue] = []
        for file_path, content in files.items():
            all_issues.extend(self.scan_file(file_path, content))
        return ReviewResult(issues=all_issues)
