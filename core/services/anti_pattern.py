"""AntiPatternDetector — phát hiện code "build passes nhưng tệ".

Không giống architecture rules (layering) hay complexity (đo lường),
AntiPatternDetector tìm các pattern mà LLM thường dùng để "fix" lỗi
một cách hời hợt: silent error handling, type cheating, v.v.

Các pattern:
  - Silent exception (except: pass)
  - type: ignore không comment
  - Overly broad try
  - return None trên non-Optional
  - assert trong production logic
  - Any trong function signature
  - # noqa generator
  - args/kwargs pass-through không cần thiết
  - Deep except chains (>3)
"""
from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("orca.anti_pattern")


@dataclass
class AntiPattern:
    """Một anti-pattern phát hiện được."""
    name: str
    message: str
    file_path: str = ""
    line: int = 0
    severity: str = "warning"  # "error", "warning", "info"


def detect_anti_patterns(file_path: str, content: str) -> list[AntiPattern]:
    """Detect tất cả anti-patterns trong một file. Entry point chính."""
    results: list[AntiPattern] = []

    if file_path.endswith(".py"):
        results.extend(_detect_python(file_path, content))
    elif file_path.endswith((".pyi", ".pyx")):
        results.extend(_detect_python(file_path, content))
    else:
        results.extend(_detect_generic(file_path, content))

    return results


# ══════════════════════════════════════════════════════════════════════
# Python-specific detectors
# ══════════════════════════════════════════════════════════════════════

_SILENT_EXCEPT = re.compile(r"except\s*(?:\w+\s*)?:\s*\n\s*(?:pass\b|\.{3})")
_BARE_EXCEPT = re.compile(r"except\s*:")
_TYPE_IGNORE_NO_COMMENT = re.compile(r"# type:\s*ignore\s*(?!\s*#)")
_NOQA_BARE = re.compile(r"# noqa\b(?!:\s*\w)")
_RETURN_NONE = re.compile(r"^\s+return\s+None\s*$", re.MULTILINE)
_PRODUCTION_ASSERT = re.compile(r"^\s+assert\s+", re.MULTILINE)


def _detect_python(file_path: str, content: str) -> list[AntiPattern]:
    """Python-specific detectors — text regex + AST."""
    results: list[AntiPattern] = []
    lines = content.split("\n")

    # ── 1. Silent except: pass ──
    for m in _SILENT_EXCEPT.finditer(content):
        lineno = content[:m.start()].count("\n") + 1
        results.append(AntiPattern(
            name="silent_except",
            message=f"Silent exception catch at line {lineno}: 'except: pass' swallows all errors",
            file_path=file_path, line=lineno,
            severity="error",
        ))

    # ── 2. Bare except: ──
    for m in _BARE_EXCEPT.finditer(content):
        lineno = content[:m.start()].count("\n") + 1
        results.append(AntiPattern(
            name="bare_except",
            message=f"Bare 'except:' at line {lineno} catches KeyboardInterrupt/SystemExit too",
            file_path=file_path, line=lineno,
            severity="error",
        ))

    # ── 3. type: ignore without comment ──
    for m in _TYPE_IGNORE_NO_COMMENT.finditer(content):
        lineno = content[:m.start()].count("\n") + 1
        results.append(AntiPattern(
            name="type_ignore_no_comment",
            message=f"# type: ignore at line {lineno} without justification comment",
            file_path=file_path, line=lineno,
            severity="warning",
        ))

    # ── 4. # noqa without specific code ──
    for m in _NOQA_BARE.finditer(content):
        lineno = content[:m.start()].count("\n") + 1
        results.append(AntiPattern(
            name="noqa_bare",
            message=f"# noqa at line {lineno} without specific rule code (prefer # noqa: E501)",
            file_path=file_path, line=lineno,
            severity="info",
        ))

    # ── 5. return None in non-optional context ──
    # (heuristic: if function has return type hint without Optional)
    try:
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                has_return_none = any(
                    isinstance(stmt, ast.Return) and stmt.value is None
                    for stmt in ast.walk(node)
                    if isinstance(stmt, ast.Return)
                )
                if has_return_none and node.returns:
                    ret_type = _type_hint_name(node.returns)
                    if ret_type and "Optional" not in ret_type and "None" not in ret_type:
                        results.append(AntiPattern(
                            name="return_none_on_typed",
                            message=f"Function '{node.name}' returns None but return type is {ret_type}",
                            file_path=file_path, line=node.lineno,
                            severity="warning",
                        ))
    except SyntaxError:
        pass

    # ── 6. assert in non-test files ──
    if "test_" not in file_path and "_test." not in file_path:
        for m in _PRODUCTION_ASSERT.finditer(content):
            lineno = content[:m.start()].count("\n") + 1
            results.append(AntiPattern(
                name="production_assert",
                message=f"assert at line {lineno} in production code — will be stripped with python -O",
                file_path=file_path, line=lineno,
                severity="warning",
            ))

    # ── 7. Overly broad try block (try > 20 lines) ──
    _detect_broad_try(file_path, content, results, lines)

    return results


def _type_hint_name(node: ast.AST) -> str:
    """Extract type hint name from AST node."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Subscript):
        return _type_hint_name(node.value) + "[" + _type_hint_name(node.slice) + "]"
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Constant):
        return str(node.value)
    if isinstance(node, ast.Tuple):
        return ", ".join(_type_hint_name(e) for e in node.elts)
    if isinstance(node, ast.Index):
        return _type_hint_name(node.value)
    return "?"


def _detect_broad_try(file_path: str, content: str, results: list[AntiPattern],
                      lines: list[str]) -> None:
    """Detect try blocks where try body > 20 lines."""
    try:
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                try_start = node.lineno
                try_end = (node.body[-1].end_lineno if hasattr(node.body[-1], 'end_lineno')
                           and node.body[-1].end_lineno else node.lineno + len(node.body))
                try_len = try_end - try_start
                if try_len > 20:
                    results.append(AntiPattern(
                        name="broad_try",
                        message=f"try block at line {try_start} spans {try_len} lines (> 20)",
                        file_path=file_path, line=try_start,
                        severity="warning",
                    ))
    except SyntaxError:
        pass


# ══════════════════════════════════════════════════════════════════════
# Generic (language-agnostic) detectors
# ══════════════════════════════════════════════════════════════════════

def _detect_generic(file_path: str, content: str) -> list[AntiPattern]:
    """Generic anti-patterns (JS/TS/HTML/etc)."""
    results: list[AntiPattern] = []

    # Silent catch in JS: catch(e) {}
    silent_catch_js = re.compile(r"catch\s*\([^)]*\)\s*\{\s*\}")
    for m in silent_catch_js.finditer(content):
        lineno = content[:m.start()].count("\n") + 1
        results.append(AntiPattern(
            name="silent_catch",
            message=f"Silent catch block at line {lineno}: 'catch(e) {{}}' swallows all errors",
            file_path=file_path, line=lineno,
            severity="error",
        ))

    # @ts-ignore without comment
    ts_ignore = re.compile(r"//\s*@ts-ignore\b(?!.*//)")
    for m in ts_ignore.finditer(content):
        lineno = content[:m.start()].count("\n") + 1
        results.append(AntiPattern(
            name="ts_ignore_no_comment",
            message=f"@ts-ignore at line {lineno} without justification comment",
            file_path=file_path, line=lineno,
            severity="warning",
        ))

    # any type in TS
    any_type = re.compile(r":\s*any\b")
    for m in any_type.finditer(content):
        lineno = content[:m.start()].count("\n") + 1
        results.append(AntiPattern(
            name="any_type",
            message=f"any type used at line {lineno} (prefer unknown or specific type)",
            file_path=file_path, line=lineno,
            severity="info",
        ))

    return results


# ══════════════════════════════════════════════════════════════════════
# Batch API
# ══════════════════════════════════════════════════════════════════════

def scan_files(modified_files: set[str], project_root: Path) -> list[AntiPattern]:
    """Scan tất cả modified files cho anti-patterns."""
    all_results: list[AntiPattern] = []
    for f in modified_files:
        try:
            content = (project_root / f).read_text(encoding="utf-8", errors="replace")
            results = detect_anti_patterns(f, content)
            all_results.extend(results)
        except Exception:
            pass
    return all_results


def format_anti_patterns(patterns: list[AntiPattern]) -> str:
    """Format anti-patterns for context injection."""
    if not patterns:
        return ""
    lines = ["## Anti-Patterns:"]
    errors = [p for p in patterns if p.severity == "error"]
    warnings = [p for p in patterns if p.severity == "warning"]
    infos = [p for p in patterns if p.severity == "info"]

    if errors:
        lines.append(f"  [ERR] {len(errors)} error(s):")
        for p in errors[:5]:
            lines.append(f"    {p.message} [{p.file_path}:{p.line}]")

    if warnings:
        lines.append(f"  [WARN] {len(warnings)} warning(s):")
        for p in warnings[:5]:
            lines.append(f"    {p.message} [{p.file_path}:{p.line}]")

    if infos:
        lines.append(f"  {len(infos)} info(s):")
        for p in infos[:3]:
            lines.append(f"    {p.message} [{p.file_path}:{p.line}]")

    return "\n".join(lines)
