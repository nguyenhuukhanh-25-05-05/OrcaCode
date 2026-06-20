from dataclasses import dataclass, field
from typing import Optional
import time


@dataclass
class RetryAttempt:
    iteration: int
    action: str
    error: str
    root_cause: str = ""
    resolution: str = ""
    timestamp: float = 0.0


@dataclass
class RetryContract:
    max_retries: int = 3
    attempts: list[RetryAttempt] = field(default_factory=list)
    cooldown_seconds: float = 2.0

    @property
    def exhausted(self) -> bool:
        return len(self.attempts) >= self.max_retries

    @property
    def last_error(self) -> Optional[str]:
        if self.attempts:
            return self.attempts[-1].error
        return None

    @property
    def consecutive_same_error(self) -> int:
        if not self.attempts:
            return 0
        last = self.attempts[-1].error
        count = 0
        for a in reversed(self.attempts):
            if a.error == last:
                count += 1
            else:
                break
        return count

    def should_retry(self) -> bool:
        if self.exhausted:
            return False
        if self.consecutive_same_error >= 2:
            return False  # Same error twice → need new approach
        return True

    def record(self, action: str, error: str, root_cause: str = "", resolution: str = "") -> RetryAttempt:
        attempt = RetryAttempt(
            iteration=len(self.attempts) + 1,
            action=action,
            error=error,
            root_cause=root_cause,
            resolution=resolution,
            timestamp=time.time(),
        )
        self.attempts.append(attempt)
        return attempt

    def suggest_strategy(self) -> str:
        if not self.attempts:
            return "first_try"
        last = self.attempts[-1]
        if self.consecutive_same_error >= 2:
            root_cause = last.root_cause or "unknown"
            resolution = last.resolution or "Try a completely different approach"
            return f"change_approach (root_cause={root_cause}, resolution=Try something else)"
        if last.root_cause:
            resolution = last.resolution or "Fix the root cause and retry"
            return f"fix_root_cause ({resolution})"
        return "retry_same"

    def summary(self) -> str:
        if not self.attempts:
            return "No retries yet"
        lines = [f"Retries: {len(self.attempts)}/{self.max_retries}"]
        for a in self.attempts:
            lines.append(f"  #{a.iteration}: {a.action} → {a.error[:80]}")
            if a.root_cause:
                lines.append(f"    Root cause: {a.root_cause}")
            if a.resolution:
                lines.append(f"    Resolution: {a.resolution}")
        return "\n".join(lines)


class RetryStrategy:
    # ── Failure taxonomy ──
    FAILURE_PATTERNS: list[tuple[list[str], str, str, str]] = [
        # (keywords, root_cause_label, suggested_fix_template, severity)
        (["not found", "command not found", "no such file", "cannot find"],
         "missing_dependency", "Install missing dependency or check PATH/source", "high"),
        (["syntax error", "syntaxerror", "unexpected token", "unterminated"],
         "syntax_error", "Fix syntax error in the source file", "medium"),
        (["permission denied", "eacces", "access denied"],
         "permission", "Check file permissions or run as administrator", "high"),
        (["timeout", "timed out", "time out"],
         "timeout", "Increase timeout or simplify the operation", "medium"),
        (["module", "import", "cannot find module", "module not found", "no module named"],
         "missing_import", "Add missing import or install the package", "high"),
        (["undefined", "is not defined", "cannot find name", "undeclared"],
         "undefined_reference", "Define or import the missing symbol", "high"),
        (["type", "typeerror", "cannot be", "is not assignable", "incompatible"],
         "type_error", "Fix type mismatch — check function signature and types", "medium"),
        (["lint", "linting", "eslint", "pylint", "ruff"],
         "lint_error", "Fix lint rule violation in source file", "low"),
        (["attribute", "has no attribute", "no attribute"],
         "attribute_error", "Check object type — attribute does not exist", "high"),
        (["indent", "unexpected indent", "inconsistent", "dedent"],
         "indent_error", "Fix indentation in source file", "medium"),
        (["eof", "unexpected eof", "unexpected end of file", "unclosed"],
         "unclosed_block", "Close unclosed block (bracket/paren/string) in source", "medium"),
        (["conflict", "merge conflict", "conflict marker"],
         "merge_conflict", "Resolve merge conflict markers in file", "high"),
        (["exist", "already exists", "file already", "already exist"],
         "file_exists", "Use different path or remove existing file first", "low"),
        (["empty", "no content", "nothing", "truncated", "capped"],
         "incomplete_output", "Response was truncated — retry with smaller scope", "medium"),
    ]

    def classify_error(self, error_text: str, stderr: str = "", stdout: str = "") -> tuple[str, str, str]:
        """Classify error into (root_cause, suggested_fix, severity) using pattern matching."""
        combined = f"{error_text} {stderr} {stdout}".lower()

        for keywords, cause, fix, sev in self.FAILURE_PATTERNS:
            if any(kw in combined for kw in keywords):
                return (cause, fix, sev)

        return ("unknown", "Review the error and adjust approach", "medium")

    def analyze_failure(self, action: str, result: dict, context: dict) -> dict:
        """Analyze a failed action to determine root cause and suggest next steps."""
        error = result.get("summary", "Unknown error")
        success = result.get("success", False)
        stdout = result.get("stdout", "")
        stderr = result.get("stderr", "")

        analysis = {
            "error": error[:300],
            "root_cause": "",
            "suggested_fix": "",
            "severity": "unknown",
            "category": "",
        }

        # Command failure — classify via patterns
        if result.get("returncode") is not None and result["returncode"] != 0:
            cause, fix, sev = self.classify_error(error, stderr, stdout)
            analysis["root_cause"] = cause
            analysis["suggested_fix"] = fix
            analysis["severity"] = sev
            analysis["category"] = "command"

        # Write/patch failure
        if not success and not result.get("skipped"):
            path = result.get("path", "")
            cause, fix, sev = self.classify_error(error, stderr, stdout)
            if cause == "unknown":
                cause = "write_failed"
                fix = f"Check path '{path}' permissions or disk space"
            analysis["root_cause"] = cause
            analysis["suggested_fix"] = fix
            analysis["severity"] = sev
            analysis["category"] = "write"

        # Linter failure
        if result.get("linter_errors"):
            analysis["root_cause"] = "lint_violation"
            analysis["suggested_fix"] = "Fix lint errors listed in the linter output"
            analysis["severity"] = "low"
            analysis["category"] = "lint"

        return analysis