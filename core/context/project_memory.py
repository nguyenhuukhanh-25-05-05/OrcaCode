"""Project Memory — auto-maintained PROJECT_MAP.md, ARCHITECTURE.md, RULES.md.

Every execution loop iteration can trigger `refresh()` to keep memory files
in sync with the current state of the codebase.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional


class ProjectMemory:
    """Manage the three project memory files: map, architecture, rules.

    Files are stored in .orca/ directory:
      - .orca/PROJECT_MAP.md     → directory tree + symbol index
      - .orca/ARCHITECTURE.md    → high-level architecture + dependency graph
      - .orca/RULES.md           → coding conventions & constraints
    """

    def __init__(self, project_root: str = ".", orca_dir: Optional[str] = None):
        self.root = Path(project_root)
        self._dir = Path(orca_dir) if orca_dir else (self.root / ".orca")
        self._dir.mkdir(parents=True, exist_ok=True)

        self._map_path = self._dir / "PROJECT_MAP.md"
        self._arch_path = self._dir / "ARCHITECTURE.md"
        self._rules_path = self._dir / "RULES.md"

    # ── update ────────────────────────────────────────────────────────────

    def update_project_map(self, blueprint_data: Optional[dict] = None) -> str:
        """Regenerate PROJECT_MAP.md from blueprint data (symbol index).

        `blueprint_data` format (same as BlueprintService output):
          { "relative/path.py": {"classes": [...], "functions": [...]}, ... }
        """
        lines = ["# Project Map", "", "## Files & Symbols", ""]
        if blueprint_data:
            for file_path in sorted(blueprint_data):
                symbols = blueprint_data[file_path]
                classes = symbols.get("classes", [])
                functions = symbols.get("functions", [])
                if not classes and not functions:
                    continue
                lines.append(f"### `{file_path}`")
                for cls in classes:
                    lines.append(f"- **class** `{cls['name']}` — {cls.get('doc', '')[:80]}")
                for fn in functions:
                    lines.append(f"- **function** `{fn['name']}` — {fn.get('doc', '')[:80]}")
                lines.append("")
        else:
            lines.append("*No blueprint data available — run `build_blueprint()` first.*")
            lines.append("")

        content = "\n".join(lines)
        self._map_path.write_text(content, encoding="utf-8")
        return content

    def update_architecture(self, arch_summary: str = "", dep_graph: str = "") -> str:
        """Regenerate ARCHITECTURE.md."""
        lines = ["# Architecture", ""]
        if arch_summary:
            lines.append(arch_summary)
            lines.append("")
        if dep_graph:
            lines.append("## Dependency Graph")
            lines.append("")
            lines.append("```text")
            lines.append(dep_graph)
            lines.append("```")
            lines.append("")
        if not arch_summary and not dep_graph:
            lines.append("*Architecture document not yet generated.*")
            lines.append("")

        content = "\n".join(lines)
        self._arch_path.write_text(content, encoding="utf-8")
        return content

    def update_rules(self, rules: Optional[list[str]] = None) -> str:
        """Regenerate RULES.md.

        If `rules` is None, preserves existing content if any, otherwise
        writes a template.
        """
        if rules is None and self._rules_path.exists():
            return self._rules_path.read_text(encoding="utf-8")

        lines = ["# Rules", ""]
        if rules:
            for rule in rules:
                rule = rule.strip()
                if rule:
                    lines.append(f"- {rule}")
        else:
            lines.append("*No rules defined yet.*")
            lines.append("- Add coding conventions as list items above.")
        lines.append("")

        content = "\n".join(lines)
        self._rules_path.write_text(content, encoding="utf-8")
        return content

    def refresh(self, blueprint_data: Optional[dict] = None,
                arch_summary: str = "", dep_graph: str = "",
                rules: Optional[list[str]] = None) -> None:
        """Refresh all three memory files in one call."""
        self.update_project_map(blueprint_data)
        self.update_architecture(arch_summary, dep_graph)
        self.update_rules(rules)

    # ── load ──────────────────────────────────────────────────────────────

    def load_project_map(self) -> str:
        if self._map_path.exists():
            return self._map_path.read_text(encoding="utf-8")
        return ""

    def load_architecture(self) -> str:
        if self._arch_path.exists():
            return self._arch_path.read_text(encoding="utf-8")
        return ""

    def load_rules(self) -> str:
        if self._rules_path.exists():
            return self._rules_path.read_text(encoding="utf-8")
        return ""

    def load_all(self) -> str:
        """Load all three files as a single block for AI context."""
        parts = []
        pm = self.load_project_map()
        if pm:
            parts.append(pm)
        arch = self.load_architecture()
        if arch:
            parts.append(arch)
        rules = self.load_rules()
        if rules:
            parts.append(rules)
        return "\n\n---\n\n".join(parts)

    # ── paths ─────────────────────────────────────────────────────────────

    @property
    def project_map_path(self) -> Path:
        return self._map_path

    @property
    def architecture_path(self) -> Path:
        return self._arch_path

    @property
    def rules_path(self) -> Path:
        return self._rules_path

    @property
    def memory_dir(self) -> Path:
        return self._dir
