"""Architecture Graph Service — builds and maintains a dependency graph of the project.

Scans import/require statements to build a DAG (Directed Acyclic Graph).
When CodeGraph is available, uses it for richer symbol-level dependency graph.
Renders as ASCII/Unicode tree with live highlighting of active files.

Usage:
    graph = ArchGraph(project_root=".")
    graph.build_graph()  # Scan all files for imports
    graph.highlight_file("core/agent.py")  # AI is reading this
    graph.unhighlight_file("core/agent.py")  # AI is done
    tree_str = graph.render_tree()  # Get ASCII/Unicode tree string
"""
import re
import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Node:
    """A file node in the architecture graph."""
    path: str                    # Relative path to project root
    imports: list[str] = field(default_factory=list)  # Files this node imports
    imported_by: list[str] = field(default_factory=list)  # Files that import this
    is_active: bool = False      # AI is currently reading/editing this
    is_entry_point: bool = False # Is this an entry point (no imports from project)?
    depth: int = 0              # Depth in the dependency tree
    file_type: str = ""         # "python", "javascript", "typescript", "html", "css", "other"
    activity_state: str = ""    # "reading", "writing", "completed", ""
    last_activity: Optional[datetime] = None  # Timestamp of last activity


class ArchGraph:
    """Builds and renders a live dependency graph of the project."""

    # Regex patterns for import detection
    IMPORT_PATTERNS = {
        ".py": [
            re.compile(r'(?:from|import)\s+([\w.]+)'),
        ],
        ".js": [
            re.compile(r'(?:import|require)\s*\(?["\']([^"\']+)["\']\)?'),
            re.compile(r'from\s+["\']([^"\']+)["\']'),
        ],
        ".ts": [
            re.compile(r'(?:import|require)\s*\(?["\']([^"\']+)["\']\)?'),
            re.compile(r'from\s+["\']([^"\']+)["\']'),
        ],
        ".jsx": [
            re.compile(r'(?:import|require)\s*\(?["\']([^"\']+)["\']\)?'),
        ],
        ".tsx": [
            re.compile(r'(?:import|require)\s*\(?["\']([^"\']+)["\']\)?'),
        ],
        ".vue": [
            re.compile(r'import\s+.*?from\s+["\']([^"\']+)["\']'),
            re.compile(r'require\s*\(["\']([^"\']+)["\']\)'),
        ],
        ".css": [
            re.compile(r'@import\s+(?:url\()?["\']([^"\']+)["\']\)?'),
            re.compile(r'@import\s+["\']([^"\']+)["\']'),
        ],
        ".scss": [
            re.compile(r'@(?:import|use|forward)\s+(?:url\()?["\']([^"\']+)["\']\)?'),
        ],
    }

    # File type mapping
    SCRIPT_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".vue", ".mjs", ".cjs", ".mts", ".cts"}
    STYLE_EXTENSIONS = {".css", ".scss", ".sass", ".less"}
    MARKUP_EXTENSIONS = {".html", ".htm", ".xml", ".md", ".mdx"}
    SKIP_DIRS = {"__pycache__", "node_modules", "venv", "env", ".git", ".orca", ".idea", ".vscode",
                 "dist", "build", "target", ".next", ".nuxt", "coverage"}
    SKIP_EXTENSIONS = {".pyc", ".pyo", ".pyd", ".class", ".o", ".exe", ".dll", ".so",
                       ".dylib", ".cache", ".log", ".lock", ".gitignore"}

    def __init__(self, project_root: str = ".", use_codegraph: bool = True):
        self.project_root = Path(project_root).resolve()
        self.nodes: dict[str, Node] = {}
        self.file_to_module: dict[str, str] = {}
        self.module_to_file: dict[str, str] = {}
        self.active_files: set[str] = set()
        self._last_build: Optional[datetime] = None

        self._codegraph = None
        self._codegraph_available = None
        if use_codegraph:
            try:
                from core.services.codegraph_service import CodeGraphService
                self._codegraph = CodeGraphService(str(project_root))
                self._codegraph_available = self._codegraph.available
            except Exception:
                self._codegraph_available = False

    def _get_file_type(self, ext: str) -> str:
        ext_lower = ext.lower()
        if ext_lower in self.SCRIPT_EXTENSIONS:
            return "script"
        elif ext_lower in self.STYLE_EXTENSIONS:
            return "style"
        elif ext_lower in self.MARKUP_EXTENSIONS:
            return "markup"
        return "other"

    def _resolve_import(self, from_file: Path, import_name: str) -> Optional[str]:
        """Resolve an import string to an actual file path.

        Example: `from core.agent import ...` in Python could resolve to `core/agent.py`.
        """
        from_dir = from_file.parent

        # Check if it's a relative import (starts with .)
        if import_name.startswith("."):
            parts = import_name.split(".")
            level = len(parts[0])  # Number of leading dots
            target_dir = from_dir
            for _ in range(level - 1):
                target_dir = target_dir.parent
            rest = parts[1:] if len(parts) > 0 and parts[0] == "" * level else parts
            rel_path = "/".join(rest) if rest else ""
        else:
            # Absolute import — try relative to project root
            # Python: core.agent → core/agent.py
            parts = import_name.replace(".", "/").split("/")
            rel_path = "/".join(parts)
            target_dir = self.project_root

        # Try common extensions
        for ext in [".py", ".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs", "/__init__.py", "/index.js", "/index.ts"]:
            candidate = target_dir / f"{rel_path}{ext}"
            if candidate.exists() and candidate.is_relative_to(self.project_root):
                try:
                    return str(candidate.relative_to(self.project_root))
                except ValueError:
                    pass

        # Try relative to from_file directory
        for ext in [".py", ".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs"]:
            candidate = from_dir / f"{import_name}{ext}"
            candidate_rel = from_dir / f"{import_name}/__init__.py"
            if candidate.exists():
                try:
                    return str(candidate.relative_to(self.project_root))
                except ValueError:
                    pass
            if candidate_rel.exists():
                try:
                    return str(candidate_rel.relative_to(self.project_root))
                except ValueError:
                    pass

        # CSS/SCSS relative imports
        if from_file.suffix in self.STYLE_EXTENSIONS:
            candidate = from_dir / import_name
            if candidate.exists():
                try:
                    return str(candidate.relative_to(self.project_root))
                except ValueError:
                    pass
            for ext in self.STYLE_EXTENSIONS:
                candidate = from_dir / f"{import_name}{ext}"
                if candidate.exists():
                    try:
                        return str(candidate.relative_to(self.project_root))
                    except ValueError:
                        pass

        return None

    def build_graph(self, max_files: int = 500) -> int:
        """Scan all project files and build the dependency graph.
        Returns the number of files scanned.
        
        Args:
            max_files: Stop scanning after this many files (prevents timeout on huge projects)
        """
        if self._codegraph_available and self._codegraph.is_project_initialized():
            cg_count = self._build_graph_codegraph(max_files)
            if cg_count > 0:
                self._last_build = datetime.now()
                return cg_count

        self.nodes.clear()
        count = 0
        skipped_dirs = 0

        for file_path in self.project_root.rglob("*"):
            if count >= max_files:
                break
            if file_path.is_dir():
                continue

            # Skip hidden and ignored dirs
            parts = file_path.relative_to(self.project_root).parts
            if any(p.startswith(".") for p in parts):
                continue
            if any(p in self.SKIP_DIRS for p in parts):
                continue

            ext = file_path.suffix.lower()
            if ext in self.SKIP_EXTENSIONS:
                continue

            try:
                rel_path = str(file_path.relative_to(self.project_root))
            except ValueError:
                continue

            file_type = self._get_file_type(ext)
            node = Node(path=rel_path, file_type=file_type)
            count += 1

            # Parse imports
            if ext in self.IMPORT_PATTERNS:
                try:
                    content = file_path.read_text(encoding="utf-8", errors="replace")
                    for pattern in self.IMPORT_PATTERNS.get(ext, []):
                        for match in pattern.finditer(content):
                            import_name = match.group(1)
                            resolved = self._resolve_import(file_path, import_name)
                            if resolved and resolved != rel_path:
                                node.imports.append(resolved)
                except (PermissionError, OSError, UnicodeDecodeError):
                    pass  # Skip unreadable files

            # Deduplicate imports
            node.imports = list(set(node.imports))
            self.nodes[rel_path] = node

        # Build reverse edges (imported_by)
        for file_path, node in self.nodes.items():
            for imp in node.imports:
                if imp in self.nodes:
                    self.nodes[imp].imported_by.append(file_path)

        # Deduplicate imported_by
        for node in self.nodes.values():
            node.imported_by = list(set(node.imported_by))

        # Mark entry points (files with no incoming edges, or that import others but aren't imported)
        for node in self.nodes.values():
            if not node.imported_by:
                node.is_entry_point = True

        # Calculate depths from entry points (with cycle protection)
        self._calculate_depths(max_nodes=min(max_files, len(self.nodes)))

        self._last_build = datetime.now()
        return count

    def _calculate_depths(self, max_nodes: int = 500):
        """BFS from entry points to compute depth for each node."""
        visited = set()
        
        # Mark entry points and leaf nodes as depth 0
        for node in list(self.nodes.values())[:max_nodes]:
            if node.is_entry_point or not node.imports:
                node.depth = 0
                visited.add(node.path)
        
        # One-pass propagation (avoid infinite BFS on large graphs)
        for _ in range(5):  # Max depth 5
            changed = False
            for node in list(self.nodes.values())[:max_nodes]:
                if node.path in visited:
                    continue
                # Check if any importer is already visited
                for importer in node.imported_by:
                    if importer in visited and importer in self.nodes:
                        self.nodes[node.path].depth = self.nodes[importer].depth + 1
                        visited.add(node.path)
                        changed = True
                        break
            if not changed:
                break

    def _build_graph_codegraph(self, max_files: int = 500) -> int:
        self.nodes.clear()
        try:
            files = self._codegraph.get_files(str(self.project_root))
        except Exception:
            return 0

        count = 0
        for file_path in files[:max_files]:
            try:
                p = Path(file_path)
                if not p.is_absolute():
                    p = self.project_root / file_path
                rel_path = str(p.relative_to(self.project_root)) if p.is_relative_to(self.project_root) else file_path
            except (ValueError, OSError):
                rel_path = file_path

            ext = Path(file_path).suffix.lower()
            file_type = self._get_file_type(ext)
            node = Node(path=rel_path, file_type=file_type)
            count += 1

            try:
                node_info = self._codegraph.get_node(file_path)
                if node_info:
                    for caller in node_info.callers:
                        if caller.file_path:
                            try:
                                caller_rel = str(Path(caller.file_path).relative_to(self.project_root))
                            except ValueError:
                                caller_rel = caller.file_path
                            if caller_rel != rel_path:
                                node.imports.append(caller_rel)
                    for callee in node_info.callees:
                        if callee.file_path:
                            try:
                                callee_rel = str(Path(callee.file_path).relative_to(self.project_root))
                            except ValueError:
                                callee_rel = callee.file_path
                            if callee_rel != rel_path:
                                node.imports.append(callee_rel)
            except Exception:
                pass

            node.imports = list(set(node.imports))
            self.nodes[rel_path] = node

        for file_path, node in self.nodes.items():
            for imp in node.imports:
                if imp in self.nodes:
                    self.nodes[imp].imported_by.append(file_path)

        for node in self.nodes.values():
            node.imported_by = list(set(node.imported_by))

        for node in self.nodes.values():
            if not node.imported_by:
                node.is_entry_point = True

        self._calculate_depths(max_nodes=min(max_files, len(self.nodes)))
        return count

    def highlight_file(self, rel_path: str, activity: str = "reading"):
        """Mark a file as currently active (AI is reading/editing).
        
        Args:
            rel_path: Relative path to file
            activity: "reading" (blue), "writing" (green), or "completed" (yellow fade)
        """
        # Normalize path
        rel_path = rel_path.replace("\\", "/")
        self.active_files.add(rel_path)
        
        # Update activity state
        if rel_path in self.nodes:
            self.nodes[rel_path].activity_state = activity
            self.nodes[rel_path].last_activity = datetime.now()
        
        # Also try relative resolution
        for node_path in self.nodes:
            if node_path.endswith(rel_path) or rel_path.endswith(node_path):
                self.active_files.add(node_path)
                self.nodes[node_path].activity_state = activity
                self.nodes[node_path].last_activity = datetime.now()

    def unhighlight_file(self, rel_path: str):
        """Unmark a file as active, set to 'completed' state for fade effect."""
        rel_path = rel_path.replace("\\", "/")
        
        # Instead of removing, mark as completed for fade effect
        if rel_path in self.nodes:
            self.nodes[rel_path].activity_state = "completed"
            self.nodes[rel_path].last_activity = datetime.now()
        
        # Remove from active set after 3 seconds (will be cleaned up on next render)
        # For now, just mark as completed - the render will show yellow fade
        self.active_files.discard(rel_path)

    def get_context_for_ai(self, focus_files: list[str] = None, max_lines: int = 60) -> str:
        """Generate a focused context string for AI.

        Includes: the dependency graph centered on files being edited,
        with import chains and related files.

        Args:
            focus_files: Files the AI is currently working on
            max_lines: Maximum output lines

        Returns:
            String suitable for appending to AI context
        """
        if not self.nodes:
            self.build_graph()

        focus = set(focus_files or [])
        focus.update(self.active_files)

        lines = []
        lines.append("## Architecture Context (Dependency Graph)")
        lines.append("")

        if not focus:
            # Show entry points summary
            entry_points = [n for n in self.nodes.values() if n.is_entry_point]
            if entry_points:
                lines.append("### Entry Points (root files, not imported by others):")
                for ep in entry_points[:10]:
                    dep_count = len(ep.imports)
                    lines.append(f"- {ep.path} ({dep_count} dependencies)")
            lines.append("")
            lines.append(f"### Total Files: {len(self.nodes)}")
            return "\n".join(lines)

        # Show focused files and their dependency chains
        shown = set()
        for f in list(focus)[:5]:
            if f in shown:
                continue

            lines.append(f"### Active: {f}")
            node = self.nodes.get(f)
            if not node:
                lines.append(f"  (not in graph yet)")
                shown.add(f)
                continue

            # What does this file import?
            if node.imports:
                lines.append(f"  Imports ({len(node.imports)}):")
                for imp in node.imports[:8]:
                    shown.add(imp)
                    imp_node = self.nodes.get(imp)
                    status = ""
                    if imp_node:
                        children = len(imp_node.imports)
                        status = f" (→ {children} deps)" if children else ""
                    lines.append(f"    └─ {imp}{status}")

            # What imports this file?
            if node.imported_by:
                lines.append(f"  Imported by ({len(node.imported_by)}):")
                for ib in node.imported_by[:5]:
                    shown.add(ib)
                    ib_node = self.nodes.get(ib)
                    status = ""
                    if ib_node:
                        parents = len(ib_node.imported_by)
                        status = f" (imported by {parents} others)" if parents else ""
                    lines.append(f"    ┌─ {ib}{status}")

            shown.add(f)
            lines.append("")

        # Summary stats
        lines.append(f"### Stats: {len(self.nodes)} files, {sum(len(n.imports) for n in self.nodes.values())} edges")
        lines.append(f"Focus: {len(focus)} files")

        result = "\n".join(lines)
        if len(result.split("\n")) > max_lines:
            result = "\n".join(result.split("\n")[:max_lines]) + "\n... (truncated)"

        return result

    def render_tree(self, max_depth: int = 4, max_nodes: int = 50) -> str:
        """Render the architecture graph as an ASCII/Unicode tree.

        Entry points are at the top, with their dependencies indented below.
        Active files (being read/edited) are marked with special markers.

        Args:
            max_depth: Maximum depth to render
            max_nodes: Maximum nodes to render (to prevent huge output)

        Returns:
            Formatted string with box-drawing characters
        """
        if self._last_build is None:
            self.build_graph()

        lines = []
        entry_points = sorted(
            [n for n in self.nodes.values() if n.is_entry_point or not n.imported_by],
            key=lambda n: (-len(n.imports or []), n.path)
        )

        # If no clear entry points, start with files that have imports
        if not entry_points:
            entry_points = sorted(
                [n for n in self.nodes.values() if n.imports],
                key=lambda n: (-len(n.imports or []), n.path)
            )[:10]

        if not entry_points:
            return "  (no import relationships found)"

        count = 0
        for ep in entry_points[:15]:
            if count >= max_nodes:
                lines.append("  ... (more files)")
                break
            count += self._render_node(ep, lines, "", True, set(), count, max_nodes, max_depth, 0)

        header = "  [bold #38bdf8]ARCH DEP GRAPH[/]"
        if self.active_files:
            active_str = ", ".join(sorted(self.active_files)[:3])
            header += f"  [bold #00abf0]AI reading:[/] {active_str}"

        return header + "\n" + "\n".join(lines)

    def _render_node(self, node: Node, lines: list, prefix: str,
                     is_last: bool, visited: set, count: int,
                     max_nodes: int, max_depth: int, depth: int) -> int:
        """Recursively render a node and its dependencies."""
        if node.path in visited or count >= max_nodes or depth > max_depth:
            return count

        visited.add(node.path)
        connector = "└─" if is_last else "├─"
        indent = "   " if is_last else "│  "

        # Color and marker based on activity state (NEW: prioritize activity over type)
        now = datetime.now()
        marker = ""
        blink = ""
        
        if node.activity_state == "reading":
            # 🔵 Blue blinking circle = AI is reading
            import time
            blink_phase = int(time.time() * 2) % 2  # Blink every 0.5s
            if blink_phase == 0:
                marker = "[bold #00abf0 blink]●[/bold #00abf0 blink] "
            else:
                marker = "[bold #00abf0]◉[/bold #00abf0] "  # Alternate symbol
        elif node.activity_state == "writing":
            # 🟢 Green pulsing circle = AI is writing/editing
            marker = "[bold #22c55e blink]●[/bold #22c55e blink] "
        elif node.activity_state == "completed" and node.last_activity:
            # 🟡 Yellow fade = just completed (show for 3 seconds)
            elapsed = (now - node.last_activity).total_seconds()
            if elapsed < 3:
                marker = "[#eab308]●[/] "  # Yellow solid for 3 seconds
            else:
                # Reset to normal after 3 seconds
                node.activity_state = ""
                marker = self._get_type_marker(node)
        elif node.path in self.active_files:
            # Fallback: generic active (shouldn't happen with new system)
            marker = "[bold #00abf0]●[/bold #00abf0] "
        else:
            # Default markers based on file type
            marker = self._get_type_marker(node)

        dep_count = len(node.imports)
        dep_str = f" ({dep_count})" if dep_count > 0 else ""
        lines.append(f"{prefix}{connector}{marker}{node.path}{dep_str}")
        count += 1

        # Render dependencies
        deps = [d for d in node.imports if d in self.nodes and d not in visited]
        deps = sorted(deps, key=lambda d: (-len(self.nodes[d].imports or []), d))[:5]

        for i, dep in enumerate(deps):
            if count >= max_nodes or depth + 1 > max_depth:
                break
            dep_node = self.nodes[dep]
            count = self._render_node(
                dep_node, lines, prefix + indent,
                i == len(deps) - 1, visited, count,
                max_nodes, max_depth, depth + 1
            )

        return count
    
    def _get_type_marker(self, node: Node) -> str:
        """Get marker based on file type (for inactive files)."""
        if node.is_entry_point:
            return "[#22c55e]◆[/] "  # Green diamond = entry point
        elif node.file_type == "script":
            return "[#38bdf8]○[/] "  # Cyan circle = regular script
        elif node.file_type == "style":
            return "[#eab308]◇[/] "  # Yellow diamond = style
        elif node.file_type == "markup":
            return "[#f59e0b]□[/] "  # Amber square = markup
        else:
            return "· "  # Plain dot = other