"""PlanDriftDetector — phát hiện agent đang lệch khỏi architectural intent.

Khác GoalDriftDetector:
  Goal Drift:   "Add dark mode" → sửa eslint (SAI VIỆC)
  Plan Drift:   Plugin Architecture → chuyển sang Microservice (SAI HƯỚNG)

  Goal Drift = đang làm cái khác.
  Plan Drift = cùng goal nhưng dao động kiến trúc.

Plan Drift xuất hiện khi build/tests/quality đều PASS nhưng
agent đã thay đổi hướng thiết kế 3-4 lần trong 300 iterations.

Usage:
    pdd = PlanDriftDetector()
    pdd.set_intent("Plugin Architecture", {
        "expected": ["core/plugins/", "core/registry.py"],
        "unexpected": ["core/microservice/", "infra/"],
    })
    result = pdd.check(modified_files, iteration)
    if result.is_drifting:
        print(result.warning)
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from core.services.signal import Signal, Priority

logger = logging.getLogger("orca.plan_drift")


@dataclass
class PlanDriftCheckpoint:
    """Kết quả kiểm tra plan drift tại một iteration."""
    iteration: int
    focus_area: str              # Domain/area agent đang làm
    matched_expected: int        # Số file khớp với expected patterns
    matched_unexpected: int      # Số file khớp với unexpected patterns
    drift_score: float           # 0.0 (aligned) → 1.0 (drift)
    warning: str = ""


@dataclass
class PlanDriftResult:
    is_drifting: bool = False
    score: float = 0.0
    warning: str = ""


class PlanDriftDetector:
    """Phát hiện plan drift dựa trên file patterns.

    Lightweight, deterministic — không cần LLM.
    Dựa trên observation: file paths là dấu hiệu của architectural intent.
    """

    def __init__(self, check_interval: int = 10):
        self._intent_name: str = ""              # "Plugin Architecture"
        self._expected_patterns: list[re.Pattern] = []   # Files nên có
        self._unexpected_patterns: list[re.Pattern] = []  # Files không nên có
        self._checkpoints: list[PlanDriftCheckpoint] = []
        self._check_interval = check_interval
        self._last_check_iteration: int = -1
        self._drifting = False
        self._last_warning: str = ""

    # ── Set architectural intent ──

    def set_intent(self, name: str, expected: Optional[list[str]] = None,
                   unexpected: Optional[list[str]] = None) -> None:
        """Set architectural intent cho task hiện tại.

        Args:
            name: Tên architecture ("Plugin Architecture")
            expected: File patterns nên xuất hiện ("core/plugins/*.py")
            unexpected: File patterns không nên xuất hiện ("core/microservice/")
        """
        self._intent_name = name
        self._expected_patterns = [re.compile(p.replace("*", r".*")) for p in (expected or [])]
        self._unexpected_patterns = [re.compile(p.replace("*", r".*")) for p in (unexpected or [])]
        self._checkpoints.clear()
        self._drifting = False
        logger.info("PlanDrift: intent='%s', expected=%d patterns, unexpected=%d patterns",
                     name, len(self._expected_patterns), len(self._unexpected_patterns))

    # ── Check ──

    def check(self, modified_files: set[str], iteration: int) -> PlanDriftResult:
        """Kiểm tra plan drift dựa trên modified files.

        Score tính từ:
          - unexpected file matches (+0.3 mỗi file, tối đa 1.0)
          - expected file misses (giảm penalty nếu không có file nào khớp expected)
        """
        result = PlanDriftResult()

        if not self._intent_name:
            return result  # Chưa set intent

        # Chỉ check mỗi N iterations
        if self._last_check_iteration >= 0 and \
           iteration - self._last_check_iteration < self._check_interval:
            return result
        self._last_check_iteration = iteration

        # Phân tích files
        matched_expected = 0
        matched_unexpected = 0
        for f in modified_files:
            norm_f = f.replace("\\", "/")
            for pat in self._expected_patterns:
                if pat.search(norm_f):
                    matched_expected += 1
                    break
            for pat in self._unexpected_patterns:
                if pat.search(norm_f):
                    matched_unexpected += 1
                    break

        # Drift score: unexpected dominates
        score = 0.0
        if modified_files:
            if matched_unexpected > 0:
                score = min(1.0, matched_unexpected * 0.3)
            elif matched_expected == 0 and self._expected_patterns:
                score = 0.2  # Không khớp expected cũng đáng ngờ

        result.score = score

        # Determine focus area từ modified files
        focus = self._describe_focus(modified_files)

        cp = PlanDriftCheckpoint(
            iteration=iteration,
            focus_area=focus,
            matched_expected=matched_expected,
            matched_unexpected=matched_unexpected,
            drift_score=score,
        )

        if score >= 0.5:
            cp.warning = (
                f"PLAN DRIFT: {matched_unexpected} file(s) không phù hợp với "
                f"architecture intent '{self._intent_name}' (score={score:.1f}). "
                f"Files: {focus}"
            )
            result.is_drifting = True
            result.warning = cp.warning
            self._drifting = True
            self._last_warning = cp.warning
        elif score >= 0.3:
            cp.warning = (
                f"Plan drift nhẹ: files đang đi lệch khỏi '{self._intent_name}'"
            )
            result.warning = cp.warning

        self._checkpoints.append(cp)
        return result

    # ── Context ──

    def format_context(self) -> str:
        """Format plan drift status cho context injection."""
        if not self._intent_name:
            return ""
        lines = [f"  Architecture intent: {self._intent_name}"]
        if self._drifting and self._last_warning:
            lines.append(f"  [WARN] {self._last_warning}")
        elif self._checkpoints:
            last = self._checkpoints[-1]
            if last.drift_score > 0:
                lines.append(f"  Drift score: {last.drift_score:.1f} "
                             f"(+{last.matched_unexpected} unexpected files)")
        return f"## Architectural Intent:\n" + "\n".join(lines)

    def to_signals(self) -> list[Signal]:
        """Convert plan drift → Signal objects (advisory only)."""
        if not self._drifting or not self._last_warning:
            return []
        last = self._checkpoints[-1] if self._checkpoints else None
        return [Signal(
            category="architecture",
            evidence_level=1,
            observation=self._last_warning[:120],
            confidence=0.7,
            severity_hint=0.7 if last and last.drift_score >= 0.5 else 0.4,
        )]

    # ── Internal ──

    @staticmethod
    def _describe_focus(modified_files: set[str]) -> str:
        """Mô tả ngắn domain agent đang làm dựa trên file paths."""
        if not modified_files:
            return "?"
        # Group by first 2 path components
        prefixes: dict[str, int] = {}
        for f in modified_files:
            parts = f.replace("\\", "/").split("/")
            prefix = "/".join(parts[:2]) if len(parts) >= 2 else parts[0]
            prefixes[prefix] = prefixes.get(prefix, 0) + 1
        sorted_p = sorted(prefixes.items(), key=lambda x: -x[1])
        return ", ".join(f"{p}({c})" for p, c in sorted_p[:3])
