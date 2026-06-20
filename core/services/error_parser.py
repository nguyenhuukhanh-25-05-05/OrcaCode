"""Error Parser - Layer 2: Parse compiler/linter output into structured error objects.

Parses raw command output (tsc, eslint, pylint, pytest, cargo, go, etc.)
into a uniform format:

    {
        "file": "src/login.ts",
        "line": 42,
        "col": 5,
        "error": "Property 'token' does not exist",
        "severity": "error" | "warning" | "info",
        "code": "TS2339",
        "source": "tsc" | "eslint" | "pylint" | ...
    }
"""
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ParsedError:
    file: str
    line: int
    col: int = 0
    error: str = ""
    severity: str = "error"
    code: str = ""
    source: str = ""

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "line": self.line,
            "col": self.col,
            "error": self.error,
            "severity": self.severity,
            "code": self.code,
            "source": self.source,
        }


# ─── Regex patterns per tool ─────────────────────────────────────────────────

# TypeScript:  src/file.ts(42,5): error TS2339: Property 'foo' does not exist
_TS_PATTERN = re.compile(
    r'^(?P<file>[^\s(]+)\((?P<line>\d+)(?:,(?P<col>\d+))?\):\s*'
    r'(?P<severity>error|warning|info)\s+(?P<code>TS\d+):\s*(?P<error>.+)$',
    re.MULTILINE,
)

# Also handle:  src/file.ts:42:5 - error TS2339: ...
_TS_PATTERN2 = re.compile(
    r'^(?P<file>[^:]+):(?P<line>\d+)(?::(?P<col>\d+))?\s*-\s*'
    r'(?P<severity>error|warning|info)\s+(?P<code>TS\d+):\s*(?P<error>.+)$',
    re.MULTILINE,
)

# ESLint:  src/file.ts
#    42:5  error  'token' is defined but never used  no-unused-vars
# Compact:  /path/file.ts:42:5: error - message (rule)
_ESLINT_STYISH = re.compile(
    r'^(?P<file>[^\s:]+):\s*'
    r'(?P<line>\d+)(?::(?P<col>\d+))?:\s*'
    r'(?P<severity>error|warning|info)\s+'
    r'(?P<error>.+?)\s+'
    r'\((?P<code>[a-z\-/]+)\)\s*$',
    re.MULTILINE,
)

# ESLint JSON output (when using -f json)
_ESLINT_JSON = True  # handled specially in parse_json

# Pylint:  src/file.py:42:0: E0001: message
_PYLINT = re.compile(
    r'^(?P<file>[^:]+):(?P<line>\d+):(?P<col>\d+):\s*'
    r'(?P<code>[CRFWIE]\d{4}):\s*(?P<error>.+)$',
    re.MULTILINE,
)

# Pyflakes:  src/file.py:42: undefined name 'foo'
_PYFLAKES = re.compile(
    r'^(?P<file>[^:]+):(?P<line>\d+):\s*(?P<error>.+)$',
    re.MULTILINE,
)

# Pytest:  FAILED src/test.py::test_foo - ExceptionType: message
#          src/file.py:42: ExceptionType: message
_PYTEST_FAIL = re.compile(
    r'^(?:FAILED\s+)?(?P<file>[^:\s]+):(?P<line>\d+)(?::(?P<col>\d+))?:\s*'
    r'(?P<error>.+)$',
    re.MULTILINE,
)

# Cargo (Rust):  error[E0599]: no method named `foo` found
#   --> src/main.rs:42:5
_CARGO_ERR = re.compile(
    r'^(?:error|warning)\[(?P<code>E\d+|W\d+)\]:\s*(?P<error>.+)$',
    re.MULTILINE,
)
_CARGO_LOC = re.compile(
    r'^\s*-->\s+(?P<file>[^:]+):(?P<line>\d+)(?::(?P<col>\d+))?$',
    re.MULTILINE,
)

# Go:  # pkg
# ./file.go:42:5: undefined: foo
_GO = re.compile(
    r'^(?:#\s*\S+\n)?(?P<file>[^:]+):(?P<line>\d+)(?::(?P<col>\d+))?:\s*(?P<error>.+)$',
    re.MULTILINE,
)

# Generic:  file.ext:LINE:COL: message  or  file.ext:LINE: message
_GENERIC = re.compile(
    r'^(?P<file>[^\s:]+):(?P<line>\d+)(?::(?P<col>\d+))?:\s*(?P<error>.+)$',
    re.MULTILINE,
)

# Severity inference keywords
_ERROR_KEYWORDS = frozenset([
    "error", "fatal", "cannot", "could not", "failed", "expected",
    "unexpected", "missing", "undefined", "not found", "unresolved",
    "no module", "no such", "import error", "syntaxerror", "typeerror",
    "valueerror", "keyerror", "attributeerror", "indexerror",
])
_WARNING_KEYWORDS = frozenset([
    "warning", "warn", "deprecated", "unused", "never used",
    "may be undefined", "might be undefined",
])


def _infer_severity(text: str) -> str:
    low = text.lower()
    for kw in _ERROR_KEYWORDS:
        if kw in low:
            return "error"
    for kw in _WARNING_KEYWORDS:
        if kw in low:
            return "warning"
    return "error"


class ErrorParser:
    """Parse raw command output into structured ParsedError objects."""

    def __init__(self, tool_hint: str = ""):
        self.tool_hint = tool_hint.lower().strip()

    def parse(self, stdout: str, stderr: str = "", tool: str = "") -> list[ParsedError]:
        """Parse combined stdout/stderr into structured errors."""
        tool = (tool or self.tool_hint).lower().strip()
        combined = (stderr + "\n" + stdout).strip()

        if not combined:
            return []

        # Try tool-specific parsers first
        if tool in ("tsc", "typescript", "tsc --noEmit"):
            errors = self._parse_tsc(combined)
            if errors:
                return errors

        if tool in ("eslint",):
            errors = self._parse_eslint(combined)
            if errors:
                return errors

        if tool in ("pylint",):
            errors = self._parse_pylint(combined)
            if errors:
                return errors

        if tool in ("pyflakes",):
            errors = self._parse_pyflakes(combined)
            if errors:
                return errors

        if tool in ("pytest", "py.test"):
            errors = self._parse_pytest(combined)
            if errors:
                return errors

        if tool in ("cargo", "rustc"):
            errors = self._parse_cargo(combined)
            if errors:
                return errors

        if tool in ("go", "go build", "go vet"):
            errors = self._parse_go(combined)
            if errors:
                return errors

        # Auto-detect tool from output patterns
        errors = self._parse_tsc(combined)
        if errors:
            return errors

        errors = self._parse_eslint(combined)
        if errors:
            return errors

        errors = self._parse_pylint(combined)
        if errors:
            return errors

        errors = self._parse_cargo(combined)
        if errors:
            return errors

        errors = self._parse_go(combined)
        if errors:
            return errors

        errors = self._parse_pytest(combined)
        if errors:
            return errors

        # Fallback: generic file:line:message
        errors = self._parse_generic(combined)
        return errors

    def parse_json(self, json_data: list[dict], tool: str = "") -> list[ParsedError]:
        """Parse JSON-format output (e.g. eslint -f json, tsc --pretty false)."""
        tool = tool.lower().strip()
        errors: list[ParsedError] = []

        if tool in ("eslint",) or (json_data and "filePath" in json_data[0] if json_data else False):
            for entry in json_data:
                fpath = entry.get("filePath", "")
                for msg in entry.get("messages", []):
                    errors.append(ParsedError(
                        file=fpath,
                        line=msg.get("line", 0),
                        col=msg.get("column", 0),
                        error=msg.get("message", ""),
                        severity=msg.get("severity", 2) == 2 and "error" or "warning",
                        code=str(msg.get("ruleId", "")),
                        source="eslint",
                    ))

        return errors

    # ─── Tool-specific parsers ────────────────────────────────────────────────

    def _parse_tsc(self, text: str) -> list[ParsedError]:
        errors: list[ParsedError] = []
        for pat in (_TS_PATTERN, _TS_PATTERN2):
            for m in pat.finditer(text):
                errors.append(ParsedError(
                    file=m.group("file"),
                    line=int(m.group("line")),
                    col=int(m.group("col")) if m.group("col") else 0,
                    error=m.group("error"),
                    severity=m.group("severity"),
                    code=m.group("code"),
                    source="tsc",
                ))
        return errors

    def _parse_eslint(self, text: str) -> list[ParsedError]:
        errors: list[ParsedError] = []
        current_file = ""
        for line in text.splitlines():
            line = line.rstrip()

            # Check if this is a file header line (no leading whitespace, ends with colon or is a path)
            if line and not line[0].isspace() and not line.startswith("✖"):
                # Could be a file path line:  /path/to/file.ts
                stripped = line.rstrip(":").strip()
                if "/" in stripped or "\\" in stripped or "." in stripped:
                    current_file = stripped
                    continue

            # Indented rule line:  42:5  error  message  rule-name
            m = re.match(r'\s+(\d+):(\d+)\s+(error|warning|info)\s+(.+?)\s{2,}(\S+)\s*$', line)
            if m and current_file:
                errors.append(ParsedError(
                    file=current_file,
                    line=int(m.group(1)),
                    col=int(m.group(2)),
                    error=m.group(4),
                    severity=m.group(3),
                    code=m.group(5),
                    source="eslint",
                ))
                continue

            # Also try compact format inline
            m2 = _ESLINT_STYISH.match(line)
            if m2:
                errors.append(ParsedError(
                    file=m2.group("file"),
                    line=int(m2.group("line")),
                    col=int(m2.group("col")) if m2.group("col") else 0,
                    error=m2.group("error"),
                    severity=m2.group("severity"),
                    code=m2.group("code"),
                    source="eslint",
                ))

        return errors

    def _parse_pylint(self, text: str) -> list[ParsedError]:
        errors: list[ParsedError] = []
        for m in _PYLINT.finditer(text):
            code = m.group("code")
            severity = "error" if code[0] in ("E", "F") else "warning"
            errors.append(ParsedError(
                file=m.group("file"),
                line=int(m.group("line")),
                col=int(m.group("col")),
                error=m.group("error"),
                severity=severity,
                code=code,
                source="pylint",
            ))
        return errors

    def _parse_pyflakes(self, text: str) -> list[ParsedError]:
        errors: list[ParsedError] = []
        for m in _PYFLAKES.finditer(text):
            errors.append(ParsedError(
                file=m.group("file"),
                line=int(m.group("line")),
                error=m.group("error"),
                severity=_infer_severity(m.group("error")),
                source="pyflakes",
            ))
        return errors

    def _parse_pytest(self, text: str) -> list[ParsedError]:
        errors: list[ParsedError] = []
        for m in _PYTEST_FAIL.finditer(text):
            errors.append(ParsedError(
                file=m.group("file"),
                line=int(m.group("line")),
                col=int(m.group("col")) if m.group("col") else 0,
                error=m.group("error"),
                severity="error",
                source="pytest",
            ))
        return errors

    def _parse_cargo(self, text: str) -> list[ParsedError]:
        errors: list[ParsedError] = []

        # Collect all error/warning blocks
        blocks = list(_CARGO_ERR.finditer(text))
        locations = list(_CARGO_LOC.finditer(text))

        for i, m in enumerate(blocks):
            loc = locations[i] if i < len(locations) else None
            file = loc.group("file") if loc else "?"
            line = int(loc.group("line")) if loc else 0
            col = int(loc.group("col")) if loc and loc.group("col") else 0
            severity = "error" if m.group("code").startswith("E") else "warning"
            errors.append(ParsedError(
                file=file, line=line, col=col,
                error=m.group("error"),
                severity=severity,
                code=m.group("code"),
                source="cargo",
            ))
        return errors

    def _parse_go(self, text: str) -> list[ParsedError]:
        errors: list[ParsedError] = []
        for m in _GO.finditer(text):
            errors.append(ParsedError(
                file=m.group("file"),
                line=int(m.group("line")),
                col=int(m.group("col")) if m.group("col") else 0,
                error=m.group("error"),
                severity=_infer_severity(m.group("error")),
                source="go",
            ))
        return errors

    def _parse_generic(self, text: str) -> list[ParsedError]:
        errors: list[ParsedError] = []
        seen = set()
        for m in _GENERIC.finditer(text):
            f = m.group("file")
            line = int(m.group("line"))
            key = (f, line, m.group("error"))
            if key in seen:
                continue
            seen.add(key)
            errors.append(ParsedError(
                file=f,
                line=line,
                col=int(m.group("col")) if m.group("col") else 0,
                error=m.group("error"),
                severity=_infer_severity(m.group("error")),
                source="generic",
            ))
        return errors