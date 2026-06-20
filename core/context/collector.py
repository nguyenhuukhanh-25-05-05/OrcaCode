"""Context Collector — unified context interface for the execution loop.

Wraps existing context services (ContextService, SmartContext, ArchGraph,
BlueprintService, MemoryManager) and maintains project memory files.
Provides step-specific context filtering for the Planner-driven execution.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from core.context.project_memory import ProjectMemory
from core.planner import PlanStep


class ContextCollector:
    """Unified context interface for the execution loop.

    Usage:
        collector = ContextCollector(
            project_root=".",
            context_svc=context_service_instance,
            smart_context=smart_context_instance,
            arch_graph=arch_graph_instance,
            blueprint_svc=blueprint_service_instance,
        )
        # Refresh memory files after changes
        collector.refresh_memory_files()

        # Get step-specific context
        context = collector.collect_step_context(step, user_prompt)
    """

    def __init__(
        self,
        project_root: str = ".",
        context_svc=None,
        smart_context=None,
        arch_graph=None,
        blueprint_svc=None,
        memory=None,
    ):
        self.root = Path(project_root)
        self.context_svc = context_svc
        self.smart_context = smart_context
        self.arch_graph = arch_graph
        self.blueprint_svc = blueprint_svc
        self.memory = memory
        self.project_memory = ProjectMemory(str(self.root))

    # ── Context gathering ─────────────────────────────────────────────────

    def collect_step_context(self, step: PlanStep, user_prompt: str = "") -> str:
        """Collect context relevant to a single plan step.

        Includes:
          - Relevant file contents (via SmartContext for smart splitting)
          - Project memory files (map, architecture, rules)
          - Memory instructions
        """
        parts = []

        # 1. Step-specific file context
        if step.files:
            file_sections = []
            for file_path in step.files:
                content = self._read_file_for_ai(file_path, user_prompt)
                if content:
                    file_sections.append(content)
            if file_sections:
                parts.append("## Relevant Files")
                parts.append("")
                parts.extend(file_sections)

        # 2. Project memory context
        memory_context = self.project_memory.load_all()
        if memory_context:
            parts.append("## Project Memory")
            parts.append("")
            parts.append(memory_context)

        # 3. Memory instructions
        if self.memory:
            instructions = self.memory.load_instructions(user_prompt)
            if instructions:
                parts.append("## Rules")
                parts.append("")
                parts.append(instructions)

        return "\n\n".join(parts)

    def get_full_context(self, user_prompt: str = "") -> str:
        """Get full project context (equivalent to old `_build_context`).

        Uses ContextService for broad search + ArchGraph + Blueprint.
        """
        parts = []

        # 1. Primary context via ContextService
        if self.context_svc:
            try:
                ctx = self.context_svc.build_context(user_prompt)
                if ctx:
                    parts.append(ctx)
            except Exception:
                pass

        # 2. Architecture graph
        if self.arch_graph:
            try:
                arch_ctx = self.arch_graph.get_context_for_ai()
                if arch_ctx:
                    parts.append(arch_ctx)
            except Exception:
                pass

        # 3. Blueprint RAG (lazy-build — get_relevant_blueprint auto-builds if cache missing)
        if self.blueprint_svc:
            try:
                bp_ctx = self.blueprint_svc.get_relevant_blueprint(user_prompt)
                if bp_ctx:
                    parts.append(bp_ctx)
            except Exception:
                pass

        # 4. Project memory files
        memory_context = self.project_memory.load_all()
        if memory_context:
            parts.append(memory_context)

        return "\n\n".join(parts)

    # ── Memory file management ────────────────────────────────────────────

    def refresh_memory_files(self) -> None:
        """Regenerate all project memory files from current services."""
        blueprint_data = None
        if self.blueprint_svc:
            try:
                blueprint_data = self.blueprint_svc.build_blueprint()
            except Exception:
                pass

        arch_summary = ""
        dep_graph = ""
        if self.arch_graph:
            try:
                arch_summary = self.arch_graph.get_context_for_ai() or ""
                dep_graph_text = getattr(self.arch_graph, "render_tree", None)
                if dep_graph_text:
                    dep_graph = dep_graph_text() or ""
            except Exception:
                pass

        rules = None
        if self.memory:
            try:
                instructions = self.memory.load_instructions("")
                if instructions:
                    rules = [line for line in instructions.split("\n") if line.strip()]
            except Exception:
                pass

        self.project_memory.refresh(
            blueprint_data=blueprint_data,
            arch_summary=arch_summary,
            dep_graph=dep_graph,
            rules=rules,
        )

    # ── Helpers ───────────────────────────────────────────────────────────

    def _read_file_for_ai(self, file_path: str, user_prompt: str = "") -> str:
        """Read a file, using SmartContext for smart splitting if available."""
        full_path = self.root / file_path
        if not full_path.exists():
            return f"*File `{file_path}` not found.*"

        if self.smart_context:
            try:
                return self.smart_context.build_file_context(
                    file_path, user_prompt=user_prompt
                )
            except Exception:
                pass

        # Fallback: plain read
        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
            return f"### `{file_path}`\n\n```\n{content[:3000]}\n```"
        except Exception as e:
            return f"*Error reading `{file_path}`: {e}*"

    def clear_memory_files(self) -> None:
        """Delete all project memory files."""
        for path in [self.project_memory.project_map_path,
                     self.project_memory.architecture_path,
                     self.project_memory.rules_path]:
            if path.exists():
                path.unlink()
