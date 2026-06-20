"""Project Blueprint & Auxiliary Memory Service — parses classes, methods, and functions.

Builds a detailed index of the codebase and provides a focused RAG retrieval for AI context.
When CodeGraph is available, uses it for richer AST-based extraction across 20+ languages.
"""

import os
import ast
import re
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger("orca.blueprint")


class BlueprintService:
    def __init__(self, project_root: str = ".", use_codegraph: bool = True):
        self.project_root = Path(project_root).resolve()
        self.orca_dir = self.project_root / ".orca"
        self.orca_dir.mkdir(parents=True, exist_ok=True)
        self.map_path = self.orca_dir / "project_map.json"
        self.blueprint_path = self.orca_dir / "project_blueprint.md"

        self._codegraph = None
        self._codegraph_available = None
        if use_codegraph:
            try:
                from core.services.codegraph_service import CodeGraphService
                self._codegraph = CodeGraphService(str(project_root))
                self._codegraph_available = self._codegraph.available
            except Exception as e:
                logger.debug(f"CodeGraph init failed: {e}")
                self._codegraph_available = False

    def build_blueprint(self) -> dict:
        """Scan project files, parse symbols (classes, functions, docs), and save the map."""
        if self._codegraph_available and self._codegraph.is_project_initialized():
            project_map = self._build_blueprint_codegraph()
            if project_map:
                self._save_blueprint(project_map)
                return project_map

        project_map = self._build_blueprint_builtin()
        self._save_blueprint(project_map)
        return project_map

    def _build_blueprint_codegraph(self) -> dict:
        project_map = {}
        search_queries = [
            "class", "function", "method", "interface", "struct",
            "enum", "type", "const", "route", "component",
        ]
        seen_files = set()
        for query in search_queries:
            try:
                symbols = self._codegraph.search(query, limit=200)
                for sym in symbols:
                    if not sym.file_path:
                        continue
                    rel_path = sym.file_path
                    seen_files.add(rel_path)
                    if rel_path not in project_map:
                        project_map[rel_path] = {"classes": [], "functions": []}
                    entry = {"name": sym.name, "args": [], "doc": sym.signature or ""}
                    if sym.kind in ("class", "struct", "interface", "trait",
                                    "enum", "component", "route"):
                        project_map[rel_path].setdefault("classes", []).append(entry)
                    else:
                        project_map[rel_path].setdefault("functions", []).append(entry)
            except Exception as e:
                logger.debug(f"CodeGraph search '{query}' failed: {e}")

        for rel_path in project_map:
            classes = project_map[rel_path].get("classes", [])
            seen = set()
            project_map[rel_path]["classes"] = [c for c in classes
                                                if not (c["name"] in seen or seen.add(c["name"]))]
            functions = project_map[rel_path].get("functions", [])
            seen = set()
            project_map[rel_path]["functions"] = [f for f in functions
                                                  if not (f["name"] in seen or seen.add(f["name"]))]

        return project_map if project_map else {}

    def _build_blueprint_builtin(self) -> dict:
        project_map = {}
        skip_dirs = {".git", ".orca", "node_modules", "vendor", "venv", ".venv", "env", "__pycache__", ".pytest_cache"}
        skip_extensions = {".pyc", ".pyo", ".pyd", ".exe", ".dll", ".so", ".png", ".jpg", ".zip", ".tar.gz"}

        for root, dirs, files in os.walk(self.project_root):
            dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(".")]

            for file in files:
                file_path = Path(root) / file
                if file_path.suffix.lower() in skip_extensions:
                    continue

                try:
                    rel_path = file_path.relative_to(self.project_root).as_posix()
                except ValueError:
                    continue

                symbols = self._parse_file_symbols(file_path)
                if symbols:
                    project_map[rel_path] = symbols

        return project_map

    def _save_blueprint(self, project_map: dict):
        try:
            with open(self.map_path, "w", encoding="utf-8") as f:
                json.dump(project_map, f, ensure_ascii=False, indent=2)
        except (OSError, TypeError) as e:
            logger.warning(f"Failed to save blueprint JSON: {e}")
        self._write_markdown_blueprint(project_map)

    def _parse_file_symbols(self, file_path: Path) -> Optional[dict]:
        """Parses classes, methods, and functions based on file extension."""
        ext = file_path.suffix.lower()
        if ext == ".py":
            return self._parse_python(file_path)
        elif ext in (".js", ".ts", ".jsx", ".tsx", ".vue"):
            return self._parse_js_ts(file_path)
        return None

    def _parse_python(self, file_path: Path) -> Optional[dict]:
        """Use Python AST to extract classes, methods, functions, and docstrings."""
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(content)
        except Exception:
            return None

        classes = []
        functions = []

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                cls_doc = ast.get_docstring(node) or ""
                cls_methods = []
                for sub in node.body:
                    if isinstance(sub, ast.FunctionDef):
                        method_doc = ast.get_docstring(sub) or ""
                        args = [a.arg for a in sub.args.args]
                        cls_methods.append({
                            "name": sub.name,
                            "args": args,
                            "doc": method_doc.split("\n")[0] if method_doc else ""
                        })
                classes.append({
                    "name": node.name,
                    "doc": cls_doc.split("\n")[0] if cls_doc else "",
                    "methods": cls_methods
                })
            elif isinstance(node, ast.FunctionDef):
                fn_doc = ast.get_docstring(node) or ""
                args = [a.arg for a in node.args.args]
                functions.append({
                    "name": node.name,
                    "args": args,
                    "doc": fn_doc.split("\n")[0] if fn_doc else ""
                })

        if not classes and not functions:
            return None

        return {"classes": classes, "functions": functions}

    def _parse_js_ts(self, file_path: Path) -> Optional[dict]:
        """Use simple regex patterns to extract classes and functions from JS/TS."""
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return None

        classes = []
        functions = []

        # Find classes
        class_matches = re.finditer(r'class\s+([a-zA-Z0-9_$]+)', content)
        for match in class_matches:
            class_name = match.group(1)
            classes.append({
                "name": class_name,
                "doc": f"Class {class_name}",
                "methods": []
            })

        # Find functions
        fn_matches = re.finditer(r'(?:function\s+([a-zA-Z0-9_$]+)|const\s+([a-zA-Z0-9_$]+)\s*=\s*(?:\([^)]*\)|[a-zA-Z0-9_$]+)\s*=>)', content)
        for match in fn_matches:
            fn_name = match.group(1) or match.group(2)
            if fn_name:
                functions.append({
                    "name": fn_name,
                    "args": [],
                    "doc": f"Function {fn_name}"
                })

        if not classes and not functions:
            return None

        return {"classes": classes, "functions": functions}

    def _write_markdown_blueprint(self, project_map: dict):
        """Generates a clean project_blueprint.md file."""
        lines = [
            "# Project Design Blueprint & Code Symbols",
            "This file lists classes, methods, and functions in the codebase. It acts as an auxiliary memory for the AI.",
            ""
        ]

        for file_path, symbols in sorted(project_map.items()):
            lines.append(f"## File: `{file_path}`")
            
            if symbols.get("classes"):
                lines.append("### Classes")
                for cls in symbols["classes"]:
                    doc_str = f" - *{cls['doc']}*" if cls['doc'] else ""
                    lines.append(f"- **`class {cls['name']}`**{doc_str}")
                    for method in cls["methods"]:
                        m_args = ", ".join(method["args"])
                        m_doc = f" - *{method['doc']}*" if method['doc'] else ""
                        lines.append(f"  * `def {method['name']}({m_args})`{m_doc}")
                lines.append("")

            if symbols.get("functions"):
                lines.append("### Functions")
                for fn in symbols["functions"]:
                    fn_args = ", ".join(fn["args"])
                    fn_doc = f" - *{fn['doc']}*" if fn['doc'] else ""
                    lines.append(f"- `def {fn['name']}({fn_args})`{fn_doc}")
                lines.append("")

        try:
            self.blueprint_path.write_text("\n".join(lines), encoding="utf-8")
        except OSError as e:
            logger.warning(f"Failed to write blueprint markdown: {e}")

    def get_relevant_blueprint(self, query: str) -> str:
        """Retrieves focused code symbols blueprint related to the query.

        If a file mentioned in query matches a file path, we retrieve its detailed symbols list.
        Otherwise, returns a high-level summary.
        """
        if not self.map_path.exists():
            self.build_blueprint()

        try:
            with open(self.map_path, "r", encoding="utf-8") as f:
                project_map = json.load(f)
        except Exception:
            return ""

        # Check if query mentions any file in our map
        relevant_files = []
        for file_path in project_map:
            name = Path(file_path).name
            if name.lower() in query.lower() or file_path.lower() in query.lower():
                relevant_files.append(file_path)

        lines = ["## Auxiliary Code Symbols Memory"]
        if not relevant_files:
            lines.append("### Code Overview (Main Classes & Functions)")
            count = 0
            for file_path, symbols in sorted(project_map.items()):
                if count >= 8:
                    break
                cls_list = [c["name"] for c in symbols.get("classes", [])]
                fn_list = [f["name"] for f in symbols.get("functions", [])]
                parts = []
                if cls_list:
                    parts.append("Classes: " + ", ".join(cls_list[:3]))
                if fn_list:
                    parts.append("Functions: " + ", ".join(fn_list[:3]))
                
                if parts:
                    lines.append(f"- `{file_path}`: {'; '.join(parts)}")
                    count += 1
            lines.append("Use @filename to read full file contents if detail is required.")
        else:
            for file_path in relevant_files[:3]:
                symbols = project_map[file_path]
                lines.append(f"### File: `{file_path}` symbols")
                if symbols.get("classes"):
                    for cls in symbols["classes"]:
                        lines.append(f"- `class {cls['name']}`")
                        for method in cls["methods"]:
                            lines.append(f"  * `def {method['name']}({', '.join(method['args'])})`")
                if symbols.get("functions"):
                    for fn in symbols["functions"]:
                        lines.append(f"- `def {fn['name']}({', '.join(fn['args'])})`")

        return "\n".join(lines)
