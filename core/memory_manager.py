"""Memory Manager - Handles chat history, diffs, and context caching for OrcaCode."""

import json
import os
import re
from pathlib import Path
from datetime import datetime
from typing import Optional

from rich.console import Console

console = Console()

ORCA_DIR = Path(".orca")
MEMORY_DIR = ORCA_DIR / "memory"
DIFFS_DIR = MEMORY_DIR / "diffs"
HISTORY_FILE = MEMORY_DIR / "chat_history.json"
INSTRUCTIONS_FILE = ORCA_DIR / "instructions.md"
UI_TASK_RE = re.compile(
    r"\b(ui|ux|frontend|tailwind|css|html|component|layout|responsive|animation|anime\.js|design|giao diện)\b",
    re.IGNORECASE,
)


class MemoryManager:
    """Manages OrcaCode's memory system."""

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.orca_dir = self.project_root / ".orca"
        self.memory_dir = self.orca_dir / "memory"
        self.diffs_dir = self.memory_dir / "diffs"
        self.history_file = self.memory_dir / "chat_history.json"
        self.execution_context_file = self.memory_dir / "execution_context.json"
        self.instructions_file = self.orca_dir / "instructions.md"
        self._ensure_dirs()

    def _ensure_dirs(self):
        """Create memory directories if they don't exist."""
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.diffs_dir.mkdir(parents=True, exist_ok=True)

    def _read_optional_markdown(self, relative_path: str) -> Optional[str]:
        """Read an optional markdown file from the .orca directory."""
        file_path = self.orca_dir / relative_path
        if not file_path.exists():
            return None
        try:
            return file_path.read_text(encoding="utf-8")
        except Exception:
            return None

    def _is_ui_task(self, task_hint: Optional[str]) -> bool:
        """Return True when the task is likely UI/frontend related."""
        if not task_hint:
            return False
        return bool(UI_TASK_RE.search(task_hint))

    def load_instructions(self, task_hint: Optional[str] = None) -> Optional[str]:
        """Load the curated instruction pack for the current task."""
        sections: list[str] = []

        instructions = self._read_optional_markdown("instructions.md")
        if instructions:
            sections.append(f"## Instructions\n{instructions}")

        runtime_contract = self._read_optional_markdown("runtime_contract.md")
        if runtime_contract:
            sections.append(f"## Runtime Contract\n{runtime_contract}")

        project_stack = self._read_optional_markdown("project_stack.md")
        if project_stack:
            sections.append(f"## Project Stack\n{project_stack}")

        if self._is_ui_task(task_hint):
            ui_rules = self._read_optional_markdown("ui_runtime_rules.md")
            if ui_rules:
                sections.append(f"## UI Runtime Rules\n{ui_rules}")

            design_system = self._read_optional_markdown("design_system.md")
            if design_system:
                sections.append(f"## Design System (Mandatory Styles)\n{design_system}")

        return "\n\n".join(sections) if sections else None

    def load_skills(self) -> str:
        """Load all skill files from .orca/skills/ directory."""
        skills_dir = self.orca_dir / "skills"
        if not skills_dir.exists():
            return ""
        skills = []
        for skill_file in sorted(skills_dir.glob("*.md")):
            try:
                content = skill_file.read_text(encoding="utf-8")
                skills.append(f"### Skill: {skill_file.stem}\n{content}")
            except Exception:
                continue
        return "\n\n".join(skills) if skills else ""

    def save_execution_context(self, exec_data: dict) -> None:
        """Persist execution context so it survives a crash/restart."""
        try:
            with open(self.execution_context_file, "w", encoding="utf-8") as f:
                json.dump(exec_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            console.print(f"[yellow]Warning: Could not save execution context: {e}[/yellow]")

    def load_execution_context(self) -> dict | None:
        """Load saved execution context (None if no saved state)."""
        if self.execution_context_file.exists():
            try:
                with open(self.execution_context_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def clear_execution_context(self) -> None:
        """Remove saved execution context after resume is complete."""
        try:
            if self.execution_context_file.exists():
                self.execution_context_file.unlink()
        except Exception:
            pass

    def save_chat_history(self, messages: list[dict]):
        """Save chat history to JSON file."""
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(messages, f, ensure_ascii=False, indent=2)
        except Exception as e:
            console.print(f"[yellow]Warning: Could not save chat history: {e}[/yellow]")

    def load_chat_history(self) -> list[dict]:
        """Load chat history from JSON file."""
        if self.history_file.exists():
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def save_diff(self, file_path: str, old_content: str, new_content: str, reason: str = ""):
        """Save a diff snapshot before applying changes."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = Path(file_path).name.replace("/", "_").replace("\\", "_")
        diff_file = self.diffs_dir / f"{timestamp}_{safe_name}.json"

        try:
            diff_data = {
                "file_path": file_path,
                "timestamp": timestamp,
                "reason": reason,
                "old_content": old_content,
                "new_content": new_content,
            }
            with open(diff_file, "w", encoding="utf-8") as f:
                json.dump(diff_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            console.print(f"[yellow]Warning: Could not save diff: {e}[/yellow]")

    def get_latest_diff(self, file_path: str = None) -> Optional[dict]:
        """Get the most recent diff snapshot, optionally filtered by file path."""
        diffs = sorted(self.diffs_dir.glob("*.json"), reverse=True)
        for diff_file in diffs:
            try:
                with open(diff_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if file_path is None or data.get("file_path") == file_path:
                    return data
            except Exception:
                continue
        return None

    def list_diffs(self, limit: int = 10) -> list[dict]:
        """List recent diff snapshots."""
        diffs = sorted(self.diffs_dir.glob("*.json"), reverse=True)[:limit]
        results = []
        for diff_file in diffs:
            try:
                with open(diff_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                results.append({
                    "file": data.get("file_path", "?"),
                    "time": data.get("timestamp", "?"),
                    "reason": data.get("reason", ""),
                })
            except Exception:
                continue
        return results

    def clear_memory(self):
        """Clear all memory (chat history, diffs, cache)."""
        import shutil
        if self.memory_dir.exists():
            shutil.rmtree(self.memory_dir)
        self._ensure_dirs()
        console.print("[green]Memory cleared.[/green]")

    def get_memory_stats(self) -> dict:
        """Get memory usage statistics."""
        history = self.load_chat_history()
        diffs = list(self.diffs_dir.glob("*.json"))
        history_size = self.history_file.stat().st_size if self.history_file.exists() else 0
        diffs_size = sum(f.stat().st_size for f in diffs)

        return {
            "chat_messages": len(history),
            "history_size_kb": round(history_size / 1024, 1),
            "diff_snapshots": len(diffs),
            "diffs_size_kb": round(diffs_size / 1024, 1),
        }
