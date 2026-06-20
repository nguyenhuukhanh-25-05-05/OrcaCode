"""Recovery Checkpoint – auto-snapshot + auto-rollback khi build worse.

Luồng:
  Before write → snapshot_all_modified()
  After build  → compare_build_quality()
                  ↓
              Worse? → rollback_to_checkpoint()
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("orca.recovery")


@dataclass
class Checkpoint:
    """Snapshot of file contents tại một thời điểm."""
    iteration: int
    files: dict[str, str] = field(default_factory=dict)  # path → content
    build_error_count: int = 0
    build_output: str = ""


class CheckpointManager:
    """Quản lý checkpoint + auto-rollback."""

    def __init__(self, project_root: str, max_rollbacks: int = 3):
        self._project_root = Path(project_root)
        self._checkpoints: list[Checkpoint] = []
        self._max_rollbacks = max_rollbacks
        self._rollback_count = 0
        self._last_error_count = 0

    # ── Public API ──────────────────────────────────────────────────────

    def snapshot(self, file_paths: set[str], iteration: int) -> Checkpoint:
        """Snapshot nội dung hiện tại của các file được chỉ định."""
        cp = Checkpoint(iteration=iteration)
        for f in sorted(file_paths):
            full = self._resolve(f)
            if full.exists():
                try:
                    cp.files[f] = full.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    pass
        self._checkpoints.append(cp)
        # Chỉ giữ 5 checkpoint gần nhất
        if len(self._checkpoints) > 5:
            self._checkpoints = self._checkpoints[-5:]
        logger.info("Checkpoint %d: snapshot %d files", iteration, len(cp.files))
        return cp

    def compare_build_quality(self, current_error_count: int, build_output: str = "") -> bool:
        """So sánh số lỗi build hiện tại với checkpoint trước đó.
        Trả về True nếu build WORSENED (cần rollback).
        """
        if not self._checkpoints or current_error_count == 0:
            self._last_error_count = current_error_count
            return False

        prev = self._checkpoints[-1]
        worsened = current_error_count > prev.build_error_count

        if worsened:
            logger.warning(
                "Build worsened: %d → %d errors. Rollback available.",
                prev.build_error_count, current_error_count,
            )
        self._last_error_count = current_error_count
        return worsened

    def record_build_result(self, error_count: int, output: str = "") -> None:
        """Ghi nhận kết quả build vào checkpoint cuối cùng."""
        if self._checkpoints:
            self._checkpoints[-1].build_error_count = error_count
            self._checkpoints[-1].build_output = output[:500]
        self._last_error_count = error_count

    def rollback(self, iteration: int) -> Optional[list[str]]:
        """Rollback về checkpoint gần nhất. Trả về danh sách file đã rollback."""
        if not self._checkpoints:
            return None
        if self._rollback_count >= self._max_rollbacks:
            logger.warning("Max rollbacks (%d) reached.", self._max_rollbacks)
            return None

        cp = self._checkpoints[-1]
        restored: list[str] = []
        for f, content in cp.files.items():
            full = self._resolve(f)
            try:
                full.parent.mkdir(parents=True, exist_ok=True)
                full.write_text(content, encoding="utf-8")
                restored.append(f)
            except Exception as e:
                logger.error("Rollback failed for %s: %s", f, e)

        self._rollback_count += 1
        logger.info("Rollback iteration %d → restored %d files (attempt %d/%d)",
                     iteration, len(restored), self._rollback_count, self._max_rollbacks)
        return restored

    def can_rollback(self) -> bool:
        return self._rollback_count < self._max_rollbacks and bool(self._checkpoints)

    @property
    def rollback_remaining(self) -> int:
        return self._max_rollbacks - self._rollback_count

    def reset(self) -> None:
        self._checkpoints.clear()
        self._rollback_count = 0
        self._last_error_count = 0

    def _resolve(self, path: str) -> Path:
        p = Path(path)
        if p.is_absolute():
            return p
        return self._project_root / p
