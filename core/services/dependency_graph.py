"""Dependency Graph – parse project imports + query affected files.

Khi sửa file A, agent biết ngay file B, C bị ảnh hưởng mà không cần đọc lại toàn repo.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("orca.depgraph")


@dataclass
class FileNode:
    """Một file trong dependency graph."""
    path: str
    imports: set[str] = field(default_factory=set)      # file này import những ai
    exported_symbols: set[str] = field(default_factory=set)  # file này export gì
    is_source: bool = True


# ── Parsers ──────────────────────────────────────────────────────────

_PYTHON_IMPORT_RE = re.compile(
    r'(?:from\s+(\S+)\s+import|\bimport\s+(\S+))'
)
_PYTHON_FROM_IMPORT_RE = re.compile(
    r'from\s+(\S+)\s+import\s+(.+)$', re.MULTILINE
)
_JS_IMPORT_RE = re.compile(
    r'(?:import\s+.*?\s+from\s+[\'"](\S+?)[\'"]|require\s*\(\s*[\'"](\S+?)[\'"])'
)
_HTML_IMPORT_RE = re.compile(
    r'<(?:link|script)\s+[^>]*(?:href|src)\s*=\s*[\'"](\S+?)[\'"]'
)
_CSS_IMPORT_RE = re.compile(
    r'@import\s+[\'"](\S+?)[\'"]'
)


def _parse_python(content: str, file_path: str) -> set[str]:
    """Extract import paths từ Python file."""
    imports: set[str] = set()
    for m in _PYTHON_FROM_IMPORT_RE.finditer(content):
        module = m.group(1)
        if module and not module.startswith("."):
            imports.add(module.replace(".", "/") + ".py")
    for m in _PYTHON_IMPORT_RE.finditer(content):
        module = m.group(1) or m.group(2)
        if module and not module.startswith("."):
            imports.add(module.replace(".", "/") + ".py")
    return imports


def _parse_js(content: str, file_path: str) -> set[str]:
    """Extract import paths từ JS/TS file."""
    imports: set[str] = set()
    for m in _JS_IMPORT_RE.finditer(content):
        mod = m.group(1) or m.group(2)
        if mod and not mod.startswith("."):
            imports.add(mod + (".js" if "." not in mod.split("/")[-1] else ""))
    return imports


def _parse_html(content: str, file_path: str) -> set[str]:
    """Extract resource paths từ HTML file."""
    imports: set[str] = set()
    for m in _HTML_IMPORT_RE.finditer(content):
        src = m.group(1)
        if src and not src.startswith(("http", "//", "data:")):
            imports.add(src.split("?")[0].split("#")[0])
    return imports


def _parse_css(content: str, file_path: str) -> set[str]:
    """Extract import paths từ CSS/SCSS file."""
    imports: set[str] = set()
    for m in _CSS_IMPORT_RE.finditer(content):
        src = m.group(1)
        if src:
            imports.add(src.split("?")[0])
    return imports


_EXT_PARSER = {
    ".py": _parse_python,
    ".js": _parse_js,
    ".jsx": _parse_js,
    ".ts": _parse_js,
    ".tsx": _parse_js,
    ".mjs": _parse_js,
    ".cjs": _parse_js,
    ".html": _parse_html,
    ".htm": _parse_html,
    ".css": _parse_css,
    ".scss": _parse_css,
}


class DependencyGraph:
    """Dependency graph for a project — parsed from imports.

    Usage:
        dg = DependencyGraph(project_root)
        dg.build()  # parse all source files
        affected = dg.get_affected_files("src/user/service.py")
        # → {"src/app/controller.py", "src/api/route.py"}
    """

    def __init__(self, project_root: str):
        self._root = Path(project_root)
        self._nodes: dict[str, FileNode] = {}
        self._dependents_cache: dict[str, set[str]] = {}  # file → who depends on it
        self._built = False

    # ── Public API ──────────────────────────────────────────────────────

    def build(self, extensions: Optional[set[str]] = None) -> int:
        """Quét toàn bộ project, parse imports, xây graph.
        Trả về số file đã parse.
        """
        self._nodes.clear()
        self._dependents_cache.clear()

        exts = extensions or set(_EXT_PARSER.keys())
        count = 0
        for f in self._root.rglob("*"):
            if f.suffix.lower() in exts and not any(
                p.startswith(".") or p == "node_modules" or p == "vendor" or p == "__pycache__"
                for p in f.parts
            ):
                rel = f.relative_to(self._root).as_posix()
                try:
                    content = f.read_text(encoding="utf-8", errors="replace")
                    imports = self._parse_file(content, rel, f.suffix.lower())
                    self._nodes[rel] = FileNode(path=rel, imports=imports)
                    count += 1
                except Exception:
                    pass

        self._built = True
        logger.info("DependencyGraph built: %d files parsed", count)
        return count

    def get_affected_files(self, file_path: str) -> set[str]:
        """Trả về set các file bị ảnh hưởng nếu *file_path* thay đổi.
        Ví dụ: sửa service.py → controller.py, route.py bị ảnh hưởng.
        """
        if not self._built:
            return set()
        if file_path not in self._dependents_cache:
            self._dependents_cache[file_path] = self._compute_dependents(file_path)
        return self._dependents_cache.get(file_path, set())

    def get_dependencies(self, file_path: str) -> set[str]:
        """Trả về set các file mà *file_path* phụ thuộc vào."""
        node = self._nodes.get(file_path)
        if node is None:
            return set()
        resolved: set[str] = set()
        for imp in node.imports:
            match = self._resolve_import(imp, file_path)
            if match:
                resolved.add(match)
        return resolved

    def get_all_dependents(self, file_path: str, depth: int = 2) -> set[str]:
        """Trả về tất cả file bị ảnh hưởng (recursive, tối đa *depth* cấp)."""
        affected: set[str] = set()
        frontier = {file_path}
        for _ in range(depth):
            if not frontier:
                break
            new_frontier: set[str] = set()
            for f in frontier:
                deps = self.get_affected_files(f)
                for d in deps:
                    if d not in affected:
                        affected.add(d)
                        new_frontier.add(d)
            frontier = new_frontier
        return affected

    def refresh_file(self, file_path: str) -> None:
        """Refresh node cho một file sau khi nó được sửa."""
        full = self._root / file_path
        if not full.exists():
            self._nodes.pop(file_path, None)
            self._dependents_cache.pop(file_path, None)
            return
        try:
            content = full.read_text(encoding="utf-8", errors="replace")
            imports = self._parse_file(content, file_path, full.suffix.lower())
            self._nodes[file_path] = FileNode(path=file_path, imports=imports)
            # Xoá cache vì dependents có thể thay đổi
            self._dependents_cache.pop(file_path, None)
            for node in self._nodes.values():
                self._dependents_cache.pop(node.path, None)
        except Exception:
            pass

    def format_affected_context(self, file_path: str) -> str:
        """Trả về context string: 'Changing X affects Y, Z' để inject vào prompt."""
        affected = self.get_all_dependents(file_path, depth=1)
        if not affected:
            return ""
        sorted_files = sorted(affected)[:10]
        text = ", ".join(sorted_files)
        if len(affected) > 10:
            text += f" ... và {len(affected) - 10} file khác"
        return f"CẢNH BÁO: Sửa {file_path} ảnh hưởng đến {len(affected)} file: {text}"

    # ── Internal ────────────────────────────────────────────────────────

    def _parse_file(self, content: str, file_path: str, ext: str) -> set[str]:
        """Parse imports từ content dựa trên extension."""
        parser = _EXT_PARSER.get(ext)
        if parser is None:
            return set()
        return parser(content, file_path)

    def _compute_dependents(self, file_path: str) -> set[str]:
        """Tìm tất cả file import *file_path*."""
        dependents: set[str] = set()
        for path, node in self._nodes.items():
            if path == file_path:
                continue
            for imp in node.imports:
                resolved = self._resolve_import(imp, path)
                if resolved == file_path:
                    dependents.add(path)
                    break
        return dependents

    def _resolve_import(self, imp: str, from_file: str) -> Optional[str]:
        """Resolve import path thành file path thực tế trong project."""
        # Thử exact match
        if imp in self._nodes:
            return imp
        # Thử với prefix là thư mục chứa from_file
        base = Path(from_file).parent
        candidates = [
            (base / imp).as_posix(),
            (base / imp).resolve().as_posix() if not (base / imp).is_absolute() else imp,
            imp,
        ]
        # Normalize
        for c in candidates:
            rel = c.replace("\\", "/")
            if rel in self._nodes:
                return rel
            # Thử các extension variants
            for ext in _EXT_PARSER:
                if rel + ext in self._nodes:
                    return rel + ext
                if rel.replace("/", ".") + ext in self._nodes:
                    return rel.replace("/", ".") + ext
        return None
