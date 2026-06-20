"""Symbol Dependency Graph — function→function call tracking.

Thay vì chỉ biết file A import file B, giờ biết function X gọi function Y
ở dòng nào. Cho phép semantic damage surface chính xác call sites.
"""
from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("orca.symdep")


@dataclass
class CallSite:
    """Một nơi gọi function."""
    caller_name: str       # Function name chứa call
    caller_file: str       # File chứa caller
    callee_name: str       # Function được gọi
    line: int = 0
    kind: str = "call"     # "call", "method_call", "attribute_call"


@dataclass
class SymbolCaller:
    """Thông tin về một caller của symbol."""
    caller_name: str
    caller_file: str
    line: int = 0


class SymbolDepGraph:
    """Symbol-level dependency graph.

    Maps: callee_name → danh sách các caller gọi nó.
    Cho phép trả lời "function X bị gọi bởi những ai ở đâu".

    Usage:
        sdg = SymbolDepGraph()
        sdg.build(project_root)
        callers = sdg.get_callers("parse_config")
        # → [SymbolCaller('load_config', 'core/config.py', 42), ...]
    """

    def __init__(self):
        self._callers_of: dict[str, list[SymbolCaller]] = {}  # callee → callers
        self._callees_of: dict[str, list[CallSite]] = {}      # caller → callees
        self._callee_file_count: dict[str, set[str]] = {}     # callee → set các file
        self._broad_callees: set[str] = set()                 # callee xuất hiện trong ≥ BROAD_THRESHOLD files
        self._built = False

    BROAD_THRESHOLD = 15  # Nếu callee xuất hiện trong >= threshold files → không còn là project-specific

    # ── Public API ──────────────────────────────────────────────────────

    def build(self, project_root: Path, extensions: Optional[set[str]] = None) -> int:
        """Quét toàn bộ project, parse call sites, xây graph.

        Trả về số file đã scan.
        """
        self._callers_of.clear()
        self._callees_of.clear()
        self._callee_file_count.clear()
        self._broad_callees.clear()

        exts = extensions or {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
        count = 0
        for f in project_root.rglob("*"):
            if f.suffix.lower() not in exts:
                continue
            if any(p.startswith(".") or p in ("node_modules", "vendor", "__pycache__") for p in f.parts):
                continue
            rel = f.relative_to(project_root).as_posix()
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
                calls = self._parse_calls(content, rel, f.suffix.lower())
                for cs in calls:
                    self._add_call(cs, file_path=rel)
                if calls:
                    count += 1
            except Exception as e:
                logger.debug("SymbolDepGraph skip %s: %s", rel, e)

        # Mark broad callees (xuất hiện trong >= BROAD_THRESHOLD files)
        for callee, files_set in self._callee_file_count.items():
            if len(files_set) >= self.BROAD_THRESHOLD:
                self._broad_callees.add(callee)
                self._callers_of.pop(callee, None)

        self._built = True
        logger.info("SymbolDepGraph built: %d files with calls, %d broad callees filtered",
                     count, len(self._broad_callees))
        return count

    def get_callers(self, callee_name: str) -> list[SymbolCaller]:
        """Trả về tất cả caller của *callee_name* (ai gọi function này)."""
        if callee_name in self._broad_callees:
            return []
        return self._callers_of.get(callee_name, [])

    def get_callees(self, caller_name: str) -> list[CallSite]:
        """Trả về tất cả callee của *caller_name* (function này gọi ai)."""
        return self._callees_of.get(caller_name, [])

    def caller_count(self, callee_name: str) -> int:
        """Số lượng call sites của *callee_name*."""
        return len(self._callers_of.get(callee_name, []))

    def caller_files(self, callee_name: str) -> set[str]:
        """Tập hợp các file chứa caller của *callee_name*."""
        return {c.caller_file for c in self._callers_of.get(callee_name, [])}

    def format_call_site_context(self, callee_name: str) -> str:
        """Format context string: 'X được gọi bởi Y tại dòng Z'."""
        callers = self._callers_of.get(callee_name, [])
        if not callers:
            return ""
        # Nhóm theo file
        by_file: dict[str, list[SymbolCaller]] = {}
        for c in callers:
            by_file.setdefault(c.caller_file, []).append(c)

        parts = []
        for file_path, cs in sorted(by_file.items()):
            names = sorted(set(c.caller_name for c in cs))
            lines = sorted(c.line for c in cs)
            parts.append(f"{file_path} ({', '.join(names)} tại dòng {', '.join(str(l) for l in lines[:5])}{'...' if len(lines) > 5 else ''})")

        total = len(callers)
        unique_files = len(by_file)
        text = "; ".join(parts[:5])
        if len(parts) > 5:
            text += f"; ... và {len(parts) - 5} nhóm khác"
        return f"CALL-SITE: '{callee_name}' được gọi bởi {total} lần trong {unique_files} file: {text}"

    def get_affected_symbols(self, symbol_name: str, depth: int = 2) -> set[str]:
        """Transitive: tìm tất cả caller (và caller của caller) của *symbol_name*.

        Trả về set các function names bị ảnh hưởng khi symbol này thay đổi.
        """
        affected: set[str] = set()
        frontier = {symbol_name}
        for _ in range(depth):
            if not frontier:
                break
            new_frontier: set[str] = set()
            for sym in frontier:
                for caller in self.get_callers(sym):
                    if caller.caller_name not in affected:
                        affected.add(caller.caller_name)
                        new_frontier.add(caller.caller_name)
            frontier = new_frontier
        return affected

    # ── Python call extraction ─────────────────────────────────────────

    def _parse_calls(self, content: str, file_path: str, ext: str) -> list[CallSite]:
        """Extract call sites từ file content."""
        if ext == ".py":
            return self._parse_python_calls(content, file_path)
        elif ext in (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"):
            return self._parse_js_calls(content, file_path)
        return []

    # ── Python parser ──────────────────────────────────────────────────

    _SKIP_CALLEES = {"range", "len", "int", "str", "list", "dict", "set", "tuple",
                     "bool", "float", "type", "isinstance", "hasattr", "getattr",
                     "setattr", "print", "open", "super", "enumerate", "zip", "map",
                     "filter", "sorted", "reversed", "min", "max", "sum", "any", "all",
                     "repr", "format", "iter", "next", "property", "staticmethod",
                     "classmethod", "Exception", "ValueError", "TypeError", "KeyError",
                     "IndexError", "AttributeError", "ImportError", "RuntimeError",
                     "NotImplementedError", "StopIteration", "FileNotFoundError",
                     "PermissionError", "OSError", "IOError", "Warning", "DeprecationWarning",
                     # Common stdlib / built-in method names (noise)
                     "append", "extend", "insert", "remove", "pop", "clear", "copy",
                     "sort", "reverse", "split", "join", "strip", "lstrip", "rstrip",
                     "lower", "upper", "capitalize", "title", "swapcase", "replace",
                     "startswith", "endswith", "find", "index", "count", "encode",
                     "decode", "items", "keys", "values", "update", "get", "setdefault",
                     "read", "write", "close", "seek", "tell", "flush", "readline",
                     "readlines", "writelines", "name", "parent", "mkdir", "glob",
                     "iterdir", "rglob", "read_text", "write_text", "resolve",
                     "relative_to", "is_dir", "is_file", "suffix", "stem", "as_posix",
                     "cwd", "home", "exists", "stat", "lstat", "chmod", "rename",
                     "unlink", "rmdir", "absolute", "iter", "next", "format", "hash",
                     "help", "dir", "vars", "id", "callable", "delattr", "locals",
                     "globals", "input", "eval", "exec", "compile", "ord", "chr",
                     "bin", "hex", "oct", "abs", "round", "pow", "divmod",
                      "strftime", "strptime", "now", "utcnow", "today", "date",
                      "time", "timedelta", "total_seconds", "combine", "fromtimestamp",
                      "debug", "info", "warning", "error", "critical", "exception",
                      "basicConfig", "getLogger", "Path"}

    def _parse_python_calls(self, content: str, file_path: str) -> list[CallSite]:
        """Parse Python call sites using AST."""
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return []

        calls: list[CallSite] = []
        current_function: Optional[str] = None

        def _walk(node, func_name: Optional[str]) -> None:
            nonlocal current_function
            old = current_function
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                current_function = node.name
                for child in ast.iter_child_nodes(node):
                    _walk(child, current_function)
                current_function = old
                return
            if isinstance(node, ast.ClassDef):
                for child in ast.iter_child_nodes(node):
                    _walk(child, func_name)
                return

            if isinstance(node, ast.Call):
                callee = _extract_callee_name(node.func)
                if callee and callee not in self._SKIP_CALLEES and current_function:
                    calls.append(CallSite(
                        caller_name=current_function,
                        caller_file=file_path,
                        callee_name=callee,
                        line=getattr(node, 'lineno', 0),
                    ))

            for child in ast.iter_child_nodes(node):
                _walk(child, current_function)

        _walk(tree, None)
        return calls

    # ── JS/TS parser ───────────────────────────────────────────────────

    _JS_CALL_RE = re.compile(r'(\w+)\s*\(')
    _JS_SKIP = {"if", "while", "for", "switch", "catch", "function", "return",
                "else", "try", "typeof", "delete", "throw", "case", "new",
                "import", "export", "default", "class", "extends", "yield",
                "await", "async", "var", "let", "const", "this", "in", "of",
                "from", "as", "instanceof", "void", "with", "do"}

    def _parse_js_calls(self, content: str, file_path: str) -> list[CallSite]:
        """Parse JS/TS call sites using regex — basic approximation."""
        calls: list[CallSite] = []
        # Track current function scope via `function name(`, `name = (`, `name = function(`
        func_pattern = re.compile(r'(?:function\s+(\w+)|(\w+)\s*=\s*(?:async\s+)?function|(\w+)\s*=\s*(?:async\s+)?\()')
        lines = content.split('\n')
        current_function: Optional[str] = None

        for lineno, line in enumerate(lines, 1):
            # Detect function definitions
            fm = func_pattern.search(line)
            if fm:
                current_function = fm.group(1) or fm.group(2) or fm.group(3)

            # Detect calls
            for m in self._JS_CALL_RE.finditer(line):
                callee = m.group(1)
                if callee and callee not in self._JS_SKIP and current_function and callee != current_function:
                    calls.append(CallSite(
                        caller_name=current_function,
                        caller_file=file_path,
                        callee_name=callee,
                        line=lineno,
                    ))

        return calls

    # ── Internal ───────────────────────────────────────────────────────

    def _add_call(self, cs: CallSite, file_path: str = "") -> None:
        """Add a CallSite to the graph."""
        if cs.callee_name not in self._callers_of:
            self._callers_of[cs.callee_name] = []
            self._callee_file_count[cs.callee_name] = set()
        self._callers_of[cs.callee_name].append(SymbolCaller(
            caller_name=cs.caller_name,
            caller_file=cs.caller_file,
            line=cs.line,
        ))
        self._callee_file_count[cs.callee_name].add(cs.caller_file)

        if cs.caller_name not in self._callees_of:
            self._callees_of[cs.caller_name] = []
        self._callees_of[cs.caller_name].append(cs)


def _extract_callee_name(node: ast.AST) -> Optional[str]:
    """Extract function name from a Call node's func field.

    - func(args) -> "func"
    - obj.method(args) -> "method"
    - module.func(args) -> "func"
    - obj.attr.method(args) -> "method"
    """
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Lambda):
        return None
    # Could be more complex (generator, comprehension, etc.) — skip
    return None
