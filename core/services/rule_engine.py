"""Rule Engine - Layer 4: Pattern-match errors to automatic fix actions.

Each rule has:
    - pattern: regex or substring to match against error text
    - action: what to do automatically (run command, search file, etc.)
    - priority: higher = try first

Examples:
    "Cannot find module './config'" → search_file → fix import
    "unused variable"               → auto_delete
    "missing semicolon"             → run "eslint --fix"
"""
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from pathlib import Path


class ActionType(str, Enum):
    RUN_COMMAND = "run_command"       # Run a shell command (e.g. eslint --fix)
    SEARCH_FILE = "search_file"       # Search for a missing file/module
    DELETE_LINE = "delete_line"       # Remove an unused line
    ADD_IMPORT = "add_import"         # Add missing import
    FIX_IMPORT = "fix_import"         # Fix broken import path
    SKIP = "skip"                     # Ignore this error (suppression)
    NEEDS_AI = "needs_ai"            # Cannot auto-fix, needs AI reasoning


@dataclass
class Rule:
    """A single auto-fix rule."""
    name: str
    pattern: str                     # Regex pattern or plain substring
    action: ActionType
    command: str = ""                # For RUN_COMMAND: the shell command
    replacement: str = ""            # For ADD_IMPORT/FIX_IMPORT: what to insert
    severity_filter: str = ""        # Only match if severity matches ("error", "warning", "")
    source_filter: str = ""          # Only match if source matches ("eslint", "tsc", "")
    priority: int = 0                # Higher = try first
    is_regex: bool = True            # If False, use plain substring matching
    description: str = ""            # Human-readable description

    def matches(self, error_text: str, severity: str = "", source: str = "") -> bool:
        """Check if this rule matches the given error."""
        if self.severity_filter and severity != self.severity_filter:
            return False
        if self.source_filter and source != self.source_filter:
            return False

        if self.is_regex:
            return bool(re.search(self.pattern, error_text, re.IGNORECASE))
        else:
            return self.pattern.lower() in error_text.lower()


@dataclass
class RuleMatch:
    """Result of a rule matching an error."""
    rule: Rule
    error_file: str
    error_line: int
    error_text: str
    confidence: float = 0.8  # 0-1, how confident we are this fix will work


# ─── Built-in rules ──────────────────────────────────────────────────────────

DEFAULT_RULES: list[Rule] = [
    # ── Layer 3: Auto-fix tools (eslint --fix, prettier, etc.) ──
    Rule(
        name="eslint_auto_fix",
        pattern=r"(eslint|lint)\s+(error|warning)",
        action=ActionType.RUN_COMMAND,
        command="npx eslint --fix {file}",
        source_filter="eslint",
        priority=90,
        description="Run eslint --fix on the file",
    ),
    Rule(
        name="prettier_format",
        pattern=r"prettier|format\s+error|Formatting\s+differ",
        action=ActionType.RUN_COMMAND,
        command="npx prettier --write {file}",
        priority=85,
        description="Run prettier --write to fix formatting",
    ),
    Rule(
        name="black_format",
        pattern=r"black|formatting|would\s+reformat",
        action=ActionType.RUN_COMMAND,
        command="black {file}",
        source_filter="pylint",
        priority=85,
        description="Run black to fix Python formatting",
    ),

    # ── Layer 4: Rule-based auto-fix ──

    # Missing module / import
    Rule(
        name="cannot_find_module",
        pattern=r"Cannot find module|ModuleNotFoundError|No module named|not found.*import",
        action=ActionType.SEARCH_FILE,
        priority=70,
        description="Search for the missing module file and fix import path",
    ),
    Rule(
        name="missing_npm_package",
        pattern=r"Cannot find package|Module not found.*npm|Cannot resolve '.*' in",
        action=ActionType.RUN_COMMAND,
        command="npm install {module_name}",
        priority=75,
        description="Install missing npm package",
    ),
    Rule(
        name="missing_pip_package",
        pattern=r"ModuleNotFoundError.*No module named|ImportError.*No module named",
        action=ActionType.RUN_COMMAND,
        command="pip install {module_name}",
        priority=75,
        description="Install missing pip package",
    ),

    # Unused variables
    Rule(
        name="unused_variable_generic",
        pattern=r"unused variable|'(.+?)'\s+is\s+defined\s+but\s+never\s+used|no-unused-vars",
        action=ActionType.DELETE_LINE,
        priority=60,
        description="Remove unused variable",
    ),
    Rule(
        name="unused_import_python",
        pattern=r"(.+?)\s+(is|are)\s+unused|F401.*imported but unused",
        action=ActionType.DELETE_LINE,
        source_filter="pylint",
        priority=60,
        description="Remove unused import",
    ),

    # Missing semicolons / formatting
    Rule(
        name="missing_semicolon",
        pattern=r"Missing semicolon|semi.*missing|expected.*;.*before",
        action=ActionType.RUN_COMMAND,
        command="npx eslint --fix {file}",
        source_filter="eslint",
        priority=80,
        description="Auto-fix missing semicolons via eslint",
    ),
    Rule(
        name="unexpected_token",
        pattern=r"Unexpected token|SyntaxError.*unexpected|expected.*got",
        action=ActionType.NEEDS_AI,
        priority=10,
        description="Syntax error that needs AI reasoning to fix",
    ),

    # TypeScript specific
    Rule(
        name="ts_property_not_exist",
        pattern=r"Property ['\"]?\w+['\"]? does not exist|Property '(.*?)' does not exist|TS\d+:\s*Property",
        action=ActionType.NEEDS_AI,
        priority=5,
        description="TS property error — needs AI to determine correct fix",
    ),
    Rule(
        name="ts_cannot_find",
        pattern=r"Cannot find name|TS\d+:\s*Cannot find",
        action=ActionType.SEARCH_FILE,
        priority=40,
        description="TS cannot find — search for definition or fix import",
    ),

    # Go
    Rule(
        name="go_undefined",
        pattern=r"undefined:\s+(\w+)",
        action=ActionType.SEARCH_FILE,
        priority=50,
        description="Go undefined — search for definition or fix import",
    ),

    # Rust
    Rule(
        name="rust_unused_import",
        pattern=r"unused import|W\d+.*unused",
        action=ActionType.DELETE_LINE,
        source_filter="cargo",
        priority=60,
        description="Remove unused Rust import",
    ),

    # Python common
    Rule(
        name="python_name_undefined",
        pattern=r"undefined name '(\w+)'|name '(\w+)' is not defined",
        action=ActionType.SEARCH_FILE,
        priority=50,
        description="Python undefined name — search for definition or fix import",
    ),
    Rule(
        name="python_type_error",
        pattern=r"TypeError.*(?:object|NoneType|str|int|list)",
        action=ActionType.NEEDS_AI,
        priority=10,
        description="Type error — needs AI reasoning",
    ),
    Rule(
        name="python_index_error",
        pattern=r"IndexError.*out of range|list index out of range",
        action=ActionType.NEEDS_AI,
        priority=15,
        description="Index error — needs AI reasoning about bounds",
    ),
    Rule(
        name="python_key_error",
        pattern=r"KeyError.*'(.+?)'",
        action=ActionType.NEEDS_AI,
        priority=15,
        description="Key error — needs AI to find the right key",
    ),

    # Race condition / async
    Rule(
        name="race_condition",
        pattern=r"race\s+condition|deadlock|concurrent.*modification",
        action=ActionType.NEEDS_AI,
        priority=5,
        description="Concurrency issue — needs deep AI analysis",
    ),

    # Business logic
    Rule(
        name="test_failure",
        pattern=r"FAILED|AssertionError|assert.*==|assert.*!=|FAIL",
        action=ActionType.NEEDS_AI,
        priority=20,
        description="Test failure — needs AI to analyze expected vs actual",
    ),
]


class RuleEngine:
    """Match parsed errors against rules and return actionable results."""

    def __init__(self, rules: list[Rule] | None = None):
        self.rules = rules or list(DEFAULT_RULES)
        self.rules.sort(key=lambda r: r.priority, reverse=True)

    def add_rule(self, rule: Rule):
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority, reverse=True)

    def match_errors(self, errors: list[dict]) -> list[RuleMatch]:
        """Match a list of parsed error dicts against rules.
        Returns matches sorted by priority (highest first)."""
        matches: list[RuleMatch] = []

        for err in errors:
            for rule in self.rules:
                if rule.matches(
                    err.get("error", ""),
                    err.get("severity", ""),
                    err.get("source", ""),
                ):
                    matches.append(RuleMatch(
                        rule=rule,
                        error_file=err.get("file", ""),
                        error_line=err.get("line", 0),
                        error_text=err.get("error", ""),
                    ))
                    break  # Only first (highest priority) match per error

        matches.sort(key=lambda m: m.rule.priority, reverse=True)
        return matches

    def get_ai_needed_errors(self, errors: list[dict]) -> list[dict]:
        """Filter errors that need AI reasoning (no auto-fix rule matched)."""
        ai_errors = []
        for err in errors:
            matched = False
            for rule in self.rules:
                if rule.action != ActionType.NEEDS_AI and rule.matches(
                    err.get("error", ""),
                    err.get("severity", ""),
                    err.get("source", ""),
                ):
                    matched = True
                    break
            if not matched:
                ai_errors.append(err)
        return ai_errors

    def format_command(self, command: str, file_path: str, error: dict) -> str:
        """Fill placeholders in a command template."""
        cmd = command.replace("{file}", file_path)
        cmd = cmd.replace("{line}", str(error.get("line", "")))
        cmd = cmd.replace("{col}", str(error.get("col", "")))

        # Extract module name from error text (sanitized to prevent injection)
        err_text = error.get("error", "")
        module_match = re.search(r"['\"]([^'\"]+)['\"]", err_text)
        if module_match:
            module_name = module_match.group(1)
            # Sanitize: only allow safe package name characters
            module_name = re.sub(r'[^a-zA-Z0-9_\-\.]', '', module_name)
            cmd = cmd.replace("{module_name}", module_name)
        else:
            cmd = cmd.replace("{module_name}", "")

        return cmd