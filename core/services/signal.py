"""Signal Protocol — unified signal ranking for context injection.

Cấp độ ưu tiên:
  CRITICAL → chắc chắn nghiêm trọng, cần can thiệp ngay
  HIGH     → rất đáng quan tâm, nên ưu tiên
  MEDIUM   → vấn đề đáng biết, có thể cần action
  LOW      → dấu hiệu nhẹ, nên biết
  INFO     → thông tin bổ sung, ít quan trọng

Evidence level:
  0 = Heuristic (duplicate detector, complexity, debt, design rules)
  1 = Structural (dependency graph, semantic, API impact)
  2 = Runtime (build fail, test fail, runtime verification)
  3 = User (goal achieved, user confirms)

Nguyên tắc kiến trúc:
  Detector:  cung cấp category + observation + evidence_level + confidence
  Ranker:    là nơi DUY NHẤT được phép gán priority
  Reasoner:  tự kết luận dựa trên signal

  Ba trách nhiệm tách biệt hoàn toàn.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import IntEnum
from typing import Optional

logger = logging.getLogger("orca.signal")


class Priority(IntEnum):
    INFO = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


PRIORITY_LABEL: dict[Priority, str] = {
    Priority.INFO: "INFO",
    Priority.LOW: "LOW",
    Priority.MEDIUM: "MEDIUM",
    Priority.HIGH: "HIGH",
    Priority.CRITICAL: "CRITICAL",
}

PRIORITY_ICON: dict[Priority, str] = {
    Priority.INFO: "ℹ️",
    Priority.LOW: "💡",
    Priority.MEDIUM: "🔶",
    Priority.HIGH: "[WARN]",
    Priority.CRITICAL: "🚨",
}


# ══════════════════════════════════════════════════════════════════════
# Signal — chỉ chứa observation, KHÔNG chứa priority
# ══════════════════════════════════════════════════════════════════════

@dataclass
class Signal:
    """Một tín hiệu từ Monitoring Layer, chứa observation thuần.

    Detector chỉ cung cấp dữ liệu (category, observation, evidence_level, confidence).
    Priority được Ranker gán — detector không có quyền đặt priority.

    severity_hint: 0.0-1.0, cho phép detector gợi ý mức độ nghiêm trọng
    trong cùng category (vd: drift ở 0.2 khác drift ở 0.4).
    Ranker dùng hint này để modulate priority.
    """
    category: str             # "architecture", "complexity", "duplicate", "debt", "design", "loop", "drift", "semantic", "build", "test", "rollback"
    observation: str          # dữ liệu thô, không phán quyết
    evidence_level: int       # 0=heuristic, 1=structural, 2=runtime, 3=user
    confidence: float = 1.0   # 0.0-1.0
    severity_hint: float = 0.5  # 0.0=thấp nhất → 1.0=cao nhất trong category
    detail: str = ""


# ══════════════════════════════════════════════════════════════════════
# Priority Table — SINGLE SOURCE OF TRUTH
# ══════════════════════════════════════════════════════════════════════

_PRIORITY_TABLE: dict[str, Priority] = {
    # Runtime evidence — fixed CRITICAL
    "build":              Priority.CRITICAL,
    "rollback":           Priority.CRITICAL,
    # Structural — có thể CRITICAL (export removed) hoặc HIGH (regular semantic damage)
    "semantic":           Priority.HIGH,
    # Heuristic/Runtime — có thể HIGH (severe) hoặc MEDIUM (mild)
    "test":               Priority.MEDIUM,
    "drift":              Priority.MEDIUM,
    "loop":               Priority.MEDIUM,
    "architecture":       Priority.MEDIUM,
    "iteration":          Priority.MEDIUM,
    # Heuristic — fixed LOW
    "complexity":         Priority.LOW,
    "duplicate":          Priority.LOW,
    "design":             Priority.LOW,
    # Heuristic — fixed INFO
    "debt":               Priority.INFO,
    "quality_score":      Priority.INFO,
}


def resolve_priority(category: str, evidence_level: int, severity_hint: float) -> Priority:
    """Gán priority — SignalRanker là nơi DUY NHẤT gọi hàm này.

    Rule:
      - severity_hint < 0.3 → de-escalate 1 bậc (mild case)
      - severity_hint >= 0.9 → escalate 1 bậc (severe case)
      - otherwise → base priority

    Escalation không vượt CRITICAL. De-escalation không xuống dưới INFO.
    """
    base = _PRIORITY_TABLE.get(category, Priority.INFO)
    if severity_hint >= 0.9 and base.value < Priority.CRITICAL.value:
        return Priority(base.value + 1)
    if severity_hint < 0.3 and base.value > Priority.INFO.value:
        return Priority(base.value - 1)
    return base


# ══════════════════════════════════════════════════════════════════════
# Context Budget
# ══════════════════════════════════════════════════════════════════════

DEFAULT_BUDGET: dict[Priority, int] = {
    Priority.CRITICAL: 5,
    Priority.HIGH:     5,
    Priority.MEDIUM:   8,
    Priority.LOW:      8,
    Priority.INFO:     5,
}


# ══════════════════════════════════════════════════════════════════════
# SignalRanker — nơi DUY NHẤT gán priority
# ══════════════════════════════════════════════════════════════════════

class SignalRanker:
    """Xếp hạng, lọc, format signals cho context injection.

    Usage:
        ranker = SignalRanker()
        ranker.add(signal)          # detector gửi signal KHÔNG có priority
        context = ranker.format_context()  # ranker gán priority + cap + format

    Ba trách nhiệm:
      - Detector:  cung cấp observation
      - Ranker:    gán priority + sắp xếp + cắt budget
      - Reasoner:  tự kết luận
    """

    def __init__(self, budget: Optional[dict[Priority, int]] = None):
        self._signals: list[Signal] = []
        self._budget = budget or DEFAULT_BUDGET

    def add(self, signal: Signal) -> None:
        self._signals.append(signal)

    def add_many(self, signals: list[Signal]) -> None:
        self._signals.extend(signals)

    def clear(self) -> None:
        self._signals.clear()

    @property
    def count(self) -> int:
        return len(self._signals)

    @property
    def has_critical(self) -> bool:
        return any(self._get_priority(s) == Priority.CRITICAL for s in self._signals)

    @property
    def has_high(self) -> bool:
        return any(self._get_priority(s) >= Priority.HIGH for s in self._signals)

    # ── Priority: ranker là nơi duy nhất gán ──

    @staticmethod
    def _get_priority(signal: Signal) -> Priority:
        return resolve_priority(signal.category, signal.evidence_level, signal.severity_hint)

    @staticmethod
    def _sort_key(signal: Signal) -> tuple:
        return (SignalRanker._get_priority(signal).value, signal.evidence_level, signal.confidence)

    def sorted_signals(self) -> list[Signal]:
        """Sort by priority descending → evidence_level descending → confidence descending."""
        return sorted(self._signals, key=self._sort_key, reverse=True)

    def capped_signals(self) -> list[Signal]:
        """Sorted + capped per priority level."""
        sorted_sigs = self.sorted_signals()
        capped: list[Signal] = []
        counts: dict[Priority, int] = {}
        for sig in sorted_sigs:
            prio = self._get_priority(sig)
            if counts.get(prio, 0) >= self._budget.get(prio, 99):
                continue
            capped.append(sig)
            counts[prio] = counts.get(prio, 0) + 1
        return capped

    # ── Format ──

    def format_context(self, max_total: int = 30) -> str:
        """Format all signals → context string, sorted, capped, observation-only.

        Returns empty string if no signals.
        """
        capped = self.capped_signals()
        if not capped:
            return ""
        if len(capped) > max_total:
            capped = capped[:max_total]

        lines = ["## Signals (Monitoring Layer):"]
        for sig in capped:
            prio = self._get_priority(sig)
            icon = PRIORITY_ICON.get(prio, "•")
            ev_label = ["heuristic", "structural", "runtime", "user"]
            ev = ev_label[sig.evidence_level] if sig.evidence_level < 4 else "?"
            cat_label = sig.category.ljust(12)
            lines.append(f"  {icon} [{cat_label}] [{ev}] {sig.observation}")
            if sig.detail:
                lines.append(f"    {sig.detail}")

        result = "\n".join(lines)
        if len(result) > 6000:
            lines = lines[:len(lines)//2]
            lines.append("  ... (signals truncated)")
            result = "\n".join(lines)
        return result

    def as_dict(self) -> dict[str, int]:
        """Counts per priority for dashboard."""
        counts: dict[str, int] = {}
        for sig in self._signals:
            label = PRIORITY_LABEL.get(self._get_priority(sig), "?")
            counts[label] = counts.get(label, 0) + 1
        return counts
