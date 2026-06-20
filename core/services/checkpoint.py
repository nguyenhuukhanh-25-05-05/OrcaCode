"""Checkpoint Writer — lossless externalized memory for long-running agents.

Thay vì compact mất context khi overflow, Checkpoint Writer:
1. Định kỳ ghi structured state ra file .json
2. Khi context pressure ≥ 2, rebuild messages từ checkpoint + recent tail
3. Giúp agent nhớ goal/plan/decisions/failures sau 500+ iterations

Usage:
    cw = CheckpointWriter(project_root)
    cw.save(iteration=250, goal=..., plan=..., decisions=...)
    messages = cw.rebuild_messages(system_prompt, recent_tail)
"""

import json
import logging
import shutil
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

logger = logging.getLogger("orca.checkpoint")

CHECKPOINT_DIR = ".orca/checkpoints"
MAX_CHECKPOINTS = 30
CHECKPOINT_INTERVAL = 10  # Save every N iterations


@dataclass
class Checkpoint:
    """Structured snapshot of agent state at a given iteration."""
    iteration: int
    timestamp: float = 0.0
    checkpoint_id: int = 0

    goal: str = ""
    plan: str = ""
    plan_progress: str = ""  # e.g., "Step 2/5: fixing auth"

    decisions: list[dict] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    modified_files: list[str] = field(default_factory=list)
    execution_summary: list[str] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)

    n_llm_calls: int = 0
    n_tool_calls: int = 0


class CheckpointWriter:
    """Persist and rebuild agent state across long execution loops."""

    def __init__(self, project_root: str):
        self._root = Path(project_root).resolve()
        self._cp_dir = self._root / CHECKPOINT_DIR
        self._cp_dir.mkdir(parents=True, exist_ok=True)
        self._counter: int = 0
        self._last_save_iter: int = 0

    # ── Save ──────────────────────────────────────────────

    def save(self, iteration: int, *,
             goal: str = "",
             plan: str = "",
             plan_progress: str = "",
             decisions: Optional[list[dict]] = None,
             failures: Optional[list[str]] = None,
             modified_files: Optional[set[str]] = None,
             execution_summary: Optional[list[str]] = None,
             findings: Optional[list[str]] = None,
             open_questions: Optional[list[str]] = None,
             n_llm_calls: int = 0,
             n_tool_calls: int = 0,
             force: bool = False) -> Optional[str]:
        """Save a checkpoint. Returns path or None if skipped (interval not reached).

        Pass force=True to save regardless of interval (e.g., before destructive ops).
        """
        if not force and (iteration - self._last_save_iter) < CHECKPOINT_INTERVAL:
            return None
        if iteration <= self._last_save_iter:
            return None

        self._counter += 1
        self._last_save_iter = iteration

        cp = Checkpoint(
            iteration=iteration,
            timestamp=time.time(),
            checkpoint_id=self._counter,
            goal=goal[:500],
            plan=plan[:2000] if plan else "",
            plan_progress=plan_progress[:300],
            decisions=[d for d in (decisions or []) if isinstance(d, dict)][:20],
            failures=(failures or [])[-30:],
            modified_files=sorted(modified_files or [])[:100],
            execution_summary=(execution_summary or [])[-20:],
            findings=(findings or [])[-20:],
            open_questions=(open_questions or [])[-10:],
            n_llm_calls=n_llm_calls,
            n_tool_calls=n_tool_calls,
        )

        path = self._cp_dir / f"cp_{self._counter:04d}_iter_{iteration:04d}.json"
        try:
            path.write_text(
                json.dumps(asdict(cp), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self._clean_old()
            return str(path)
        except Exception as e:
            logger.warning("Failed to write checkpoint: %s", e)
            return None

    # ── Load ──────────────────────────────────────────────

    def load_latest(self) -> Optional[Checkpoint]:
        """Load the most recent checkpoint."""
        cps = self.list_checkpoints()
        if not cps:
            return None
        return self._load_file(cps[-1])

    def load_before_iteration(self, iteration: int) -> Optional[Checkpoint]:
        """Load the most recent checkpoint at or before the given iteration."""
        cps = [p for p in self.list_checkpoints()
               if self._parse_iteration(p) <= iteration]
        if not cps:
            return None
        return self._load_file(cps[-1])

    def _load_file(self, path: Path) -> Optional[Checkpoint]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return Checkpoint(**data)
        except Exception as e:
            logger.warning("Failed to load checkpoint %s: %s", path, e)
            return None

    # ── Rebuild messages ──────────────────────────────────

    def rebuild_messages(self, system_prompt: str,
                         recent_tail: list[dict],
                         checkpoint: Optional[Checkpoint] = None) -> list[dict]:
        """Build a minimal message list from checkpoint + working memory tail.

        Use this instead of lossy compaction when context pressure is high.
        The checkpoint preserves all structured state; the tail preserves
        the last N messages of working memory.
        """
        cp = checkpoint or self.load_latest()
        messages = [{"role": "system", "content": system_prompt}]

        if cp is not None:
            ctx_parts = [
                f"[Checkpoint — iteration {cp.iteration}]",
            ]
            if cp.goal:
                ctx_parts.append(f"\n## Original goal\n{cp.goal}")
            if cp.plan:
                ctx_parts.append(f"\n## Active plan\n{cp.plan}")
            if cp.plan_progress:
                ctx_parts.append(f"\n## Progress\n{cp.plan_progress}")
            if cp.decisions:
                lines = [f"  - {d.get('decision', d.get('choice', ''))[:200]}"
                         for d in cp.decisions if d.get('decision') or d.get('choice')]
                if lines:
                    ctx_parts.append("\n## Architecture decisions\n" + "\n".join(lines))
            if cp.failures:
                ctx_parts.append("\n## Recent failures\n" + "\n".join(f"  - {f[:200]}" for f in cp.failures[-10:]))
            if cp.modified_files:
                ctx_parts.append("\n## Modified files\n" + "\n".join(f"  - {f}" for f in cp.modified_files[-30:]))
            if cp.findings:
                ctx_parts.append("\n## Key findings\n" + "\n".join(f"  - {f[:200]}" for f in cp.findings[-10:]))
            if cp.n_llm_calls:
                ctx_parts.append(f"\n## Stats\n{cp.n_llm_calls} LLM calls · {cp.n_tool_calls} tool calls")

            messages.append({"role": "system", "content": "\n".join(ctx_parts)})

        # Append working memory tail (last 16 messages = ~8 exchanges)
        messages.extend(recent_tail[-16:])

        return messages

    # ── Listing & Cleanup ─────────────────────────────────

    def list_checkpoints(self) -> list[Path]:
        """Return sorted list of checkpoint files (oldest first)."""
        try:
            paths = sorted(self._cp_dir.glob("cp_*.json"))
            return paths
        except Exception:
            return []

    def _parse_iteration(self, path: Path) -> int:
        try:
            parts = path.stem.split("_")
            return int(parts[-1])
        except (IndexError, ValueError):
            return 0

    def _clean_old(self):
        """Keep only the MAX_CHECKPOINTS most recent checkpoints."""
        paths = self.list_checkpoints()
        if len(paths) > MAX_CHECKPOINTS:
            for p in paths[:-MAX_CHECKPOINTS]:
                try:
                    p.unlink()
                except Exception:
                    pass

    def get_stats(self) -> dict:
        """Return checkpoint statistics."""
        cps = self.list_checkpoints()
        return {
            "total": len(cps),
            "latest_iter": self._parse_iteration(cps[-1]) if cps else 0,
            "directory": str(self._cp_dir),
            "disk_usage_kb": sum(p.stat().st_size for p in cps) // 1024 if cps else 0,
        }

    def clear(self):
        """Remove only CheckpointWriter files (cp_*.json), preserving other services."""
        if self._cp_dir.exists():
            for f in self._cp_dir.glob("cp_*.json"):
                try:
                    f.unlink()
                except Exception:
                    pass
        self._counter = 0
        self._last_save_iter = 0
