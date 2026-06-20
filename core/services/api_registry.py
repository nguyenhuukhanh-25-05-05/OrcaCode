"""Exported API Registry — tracks the public surface across the entire project.

Detects when previously exported symbols become unavailable (contract break).
"""
from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("orca.api_registry")


@dataclass
class ExportedSymbol:
    """Một symbol được export/public từ một module."""
    name: str
    kind: str          # "function", "class", "const", "variable", "interface", "type"
    source: str        # "__all__", "public_convention", "export_keyword", "init_reexport"
    file_path: str     # Relative path
    line: int = 0


class ApiRegistry:
    """Duy trì danh sách tất cả exported symbols trong project.

    Usage:
        registry = ApiRegistry()
        registry.build(project_root)
        # After AI writes files:
        issues = registry.check_exports(symbols_by_file)
        if issues:
            for issue in issues:
                print(f"Export broken: {issue.symbol_name} in {issue.file_path}")
        # Update after each write:
        registry.update("core/foo.py", symbols)
    """

    def __init__(self):
        self.exported: dict[str, list[ExportedSymbol]] = {}  # file_path → symbols

    def build(self, project_root: Path) -> None:
        """Full scan: tìm tất cả exported symbols trong project."""
        project_root = Path(project_root)
        self.exported.clear()
        if not project_root.exists():
            return

        for py_file in project_root.rglob("*.py"):
            try:
                rel = py_file.relative_to(project_root).as_posix()
                content = py_file.read_text(encoding="utf-8", errors="replace")
                exports = self._extract_python_exports(content, rel)
                if exports:
                    self.exported[rel] = exports
            except Exception as e:
                logger.debug("Skip %s: %s", py_file, e)

        for js_ext in ("*.js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"):
            for js_file in project_root.rglob(js_ext):
                try:
                    rel = js_file.relative_to(project_root).as_posix()
                    content = js_file.read_text(encoding="utf-8", errors="replace")
                    exports = self._extract_js_exports(content, rel)
                    if exports:
                        self.exported[rel] = exports
                except Exception as e:
                    logger.debug("Skip %s: %s", js_file, e)

    def build_from_snapshot(self, symbols_by_file: dict[str, list]) -> None:
        """Build registry from existing FileSymbols snapshots."""
        self.exported.clear()
        for file_path, symbols in symbols_by_file.items():
            exports: list[ExportedSymbol] = []
            for s in symbols:
                name = getattr(s, "name", "")
                kind = getattr(s, "kind", "")
                line = getattr(s, "line_start", 0)
                if name and not name.startswith("_"):
                    exports.append(ExportedSymbol(
                        name=name, kind=kind,
                        source="public_convention",
                        file_path=file_path, line=line,
                    ))
            if exports:
                self.exported[file_path] = exports

    def check_exports(self, current_symbols: dict[str, list]) -> list:
        """So sánh current symbols với registry.

        Trả về danh sách SemanticIssue cho các export bị missing.
        """
        from core.services.semantic_detector import SemanticIssue
        issues: list = []
        for file_path, expected in self.exported.items():
            current = current_symbols.get(file_path, [])
            current_names = {getattr(s, "name", "") for s in current}
            for exp in expected:
                if exp.name not in current_names:
                    source_desc = {"__all__": "listed in __all__", "public_convention": "public symbol",
                                   "export_keyword": "exported", "init_reexport": "re-exported via __init__"}
                    issues.append(SemanticIssue(
                        severity="error",
                        message=(f"BREAK: exported {exp.kind} '{exp.name}' ({source_desc.get(exp.source, '')}) "
                                 f"no longer exists in {exp.file_path}"),
                        symbol_name=exp.name,
                        kind=exp.kind,
                        file_path=exp.file_path,
                        change_type="export_removed",
                    ))
        return issues

    def update(self, file_path: str, symbols: list) -> None:
        """Cập nhật registry sau khi AI write file mới."""
        exports: list[ExportedSymbol] = []
        for s in symbols:
            name = getattr(s, "name", "")
            kind = getattr(s, "kind", "")
            line = getattr(s, "line_start", 0)
            if name and not name.startswith("_"):
                exports.append(ExportedSymbol(
                    name=name, kind=kind,
                    source="public_convention",
                    file_path=file_path, line=line,
                ))
        if exports:
            self.exported[file_path] = exports
        elif file_path in self.exported:
            del self.exported[file_path]

    # ── Python export extraction ─────────────────────────────────────

    def _extract_python_exports(self, content: str, rel_path: str) -> list[ExportedSymbol]:
        """Extract exported symbols từ Python file."""
        exports: list[ExportedSymbol] = []
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return exports

        # 1. __all__ list
        all_names = _extract_all_names(tree)
        all_seen = set()
        if all_names:
            for name in all_names:
                exports.append(ExportedSymbol(
                    name=name, kind="symbol",
                    source="__all__", file_path=rel_path,
                ))
                all_seen.add(name)

        # 2. In __init__.py: re-exports via import statements
        if rel_path.endswith("__init__.py"):
            for node in ast.walk(tree):
                if isinstance(node, (ast.ImportFrom, ast.Import)):
                    for alias in (node.names if isinstance(node, ast.ImportFrom) else node.names):
                        if alias.name and alias.name not in all_seen and not alias.name.startswith("_"):
                            exports.append(ExportedSymbol(
                                name=alias.name, kind="module",
                                source="init_reexport", file_path=rel_path,
                            ))

        # 3. Public convention: top-level def/class/const không bắt đầu bằng _
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                kind = "function" if isinstance(node, ast.FunctionDef) else "async_function"
                if node.name not in all_seen and not node.name.startswith("_"):
                    exports.append(ExportedSymbol(
                        name=node.name, kind=kind,
                        source="public_convention", file_path=rel_path,
                        line=node.lineno,
                    ))
            elif isinstance(node, ast.ClassDef):
                if node.name not in all_seen and not node.name.startswith("_"):
                    exports.append(ExportedSymbol(
                        name=node.name, kind="class",
                        source="public_convention", file_path=rel_path,
                        line=node.lineno,
                    ))
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        if target.id not in all_seen and not target.id.startswith("_"):
                            exports.append(ExportedSymbol(
                                name=target.id, kind="variable",
                                source="public_convention", file_path=rel_path,
                                line=node.lineno,
                            ))

        return exports

    # ── JS/TS export extraction ─────────────────────────────────────

    _EXPORT_NAMED_RE = re.compile(
        r'export\s+(?:default\s+)?(?:async\s+)?(?:function|class|const|let|var|interface|type)\s+(\w+)',
    )
    _EXPORT_OBJECT_RE = re.compile(
        r'export\s*\{\s*([^}]+)\s*\}',
    )

    def _extract_js_exports(self, content: str, rel_path: str) -> list[ExportedSymbol]:
        """Extract exported symbols từ JS/TS file."""
        exports: list[ExportedSymbol] = []
        seen: set[str] = set()

        # `export function name` / `export class name` / `export const name` / `export default function name`
        for m in self._EXPORT_NAMED_RE.finditer(content):
            name = m.group(1)
            if name not in seen:
                lineno = content[:m.start()].count("\n") + 1
                exports.append(ExportedSymbol(
                    name=name, kind="symbol",
                    source="export_keyword", file_path=rel_path,
                    line=lineno,
                ))
                seen.add(name)

        # `export { name1, name2 }`
        for m in self._EXPORT_OBJECT_RE.finditer(content):
            raw = m.group(1)
            for token in raw.split(","):
                token = token.strip()
                if not token:
                    continue
                # Handle `name as alias`
                alias = token.split(" as ")[-1].strip()
                if alias and alias not in seen and not alias.startswith("_"):
                    lineno = content[:m.start()].count("\n") + 1
                    exports.append(ExportedSymbol(
                        name=alias, kind="symbol",
                        source="export_keyword", file_path=rel_path,
                        line=lineno,
                    ))
                    seen.add(alias)

        return exports


def _extract_all_names(tree: ast.AST) -> list[str]:
    """Extract names from `__all__ = [...]` assignment."""
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    if isinstance(node.value, (ast.List, ast.Tuple)):
                        names = []
                        for elt in node.value.elts:
                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                names.append(elt.value)
                        return names
    return []
