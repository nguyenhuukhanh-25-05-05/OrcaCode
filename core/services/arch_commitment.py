"""Architecture Decision Record (ADR) Log — persist tech decisions, prevent plan drift.

Vấn đề:
  Ở iteration 50: "Dùng Redux"
  Ở iteration 80: "Dùng Context"
  Ở iteration 120: "Dùng Zustand"
  Ở iteration 160: "Dùng Redux lại"

  Goal không drift, nhưng architecture dao động.
  Nguyên nhân: context loss — iteration 80 không biết iteration 50 đã chọn Redux vì sao.

ADR pattern:
  Mỗi quyết định kiến trúc được ghi lại như một ADR (Architecture Decision Record):
    id: ADR-007
    choice: JWT
    alternatives: [Session, OAuth only]
    rationale: Stateless, mobile friendly
    iteration: 58

  Khi agent muốn đổi sang Session ở iteration 240, nó thấy:
    "ADR-007: chọn JWT vì stateless. Điều gì thay đổi?"
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.services.signal import Signal, Priority
from core.validator.evidence_validator import (
    OVERRIDE_SCHEMA,
    validate_override_justification,
)

logger = logging.getLogger("orca.adr")


_CATEGORY_ICONS: dict[str, str] = {
    "state_management":    "state",
    "routing":            "route",
    "styling":            "style",
    "testing":            "test",
    "database":           "data",
    "api_design":         "api",
    "caching":            "cache",
    "architecture":       "arch",
    "authentication":     "auth",
    "deployment":         "deploy",
    "monitoring":         "monitor",
    "data_model":         "model",
    "error_handling":     "errors",
    "logging":            "log",
    "other":              "other",
}


@dataclass
class ADR:
    """Architecture Decision Record."""
    iteration: int
    category: str               # "state_management", "routing", ...
    decision: str               # "Redux Toolkit"
    rationale: str              # "Stateless, mobile friendly"
    alternatives_considered: list[str] = field(default_factory=list)
    status: str = "active"      # "active", "superseded", "deprecated"
    adr_id: str = ""            # "ADR-007" — auto-assigned
    timestamp: str = ""
    outcome: str = ""           # "good", "bad", "mixed", "" (chưa đánh giá)
    outcome_evidence: list[str] = field(default_factory=list)


@dataclass
class DecisionOutcome:
    """Record kết quả của một quyết định kiến trúc sau nhiều iterations.

    Ví dụ:
        DecisionOutcome(
            adr_id="ADR-001",
            outcome="good",
            evidence=["0 migration", "5 modules reused", "stable"],
            evaluation_iteration=300,
        )
    """
    adr_id: str
    outcome: str                # "good", "bad", "mixed"
    evidence: list[str]         # Evidence cụ thể
    evaluation_iteration: int
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat(timespec="seconds")

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat(timespec="seconds")


class DecisionLog:
    """Persistent Architecture Decision Record log.

    Usage:
        dl = DecisionLog(Path(".opencode/adr.json"))
        dl.record(ADR(
            iteration=50,
            category="state_management",
            decision="Redux Toolkit",
            rationale="Ecosystem lớn, team quen",
            alternatives_considered=["Context API", "Zustand"],
        ))
        context = dl.format_context(current_iteration=120)
        # → "ADR-001 iter 50: state_management → Redux Toolkit (active)"
        #   "  Rationale: Ecosystem lớn, team quen"

        # When proposing change:
        challenge = dl.get_context_for_proposal("state_management", "Zustand")
        # → "Previous ADR-001 chose Redux Toolkit (active) because Ecosystem lớn, team quen."
        #   "What changed since the decision?"
    """

    def __init__(self, path: Optional[Path] = None):
        self._path = path or Path(".opencode/adr.json")
        self._records: list[ADR] = []
        self._outcomes: list[DecisionOutcome] = []
        self._counter: int = 0
        self._load()

    # ── Persistence ──────────────────────────────────────────────────

    def _load(self) -> None:
        try:
            if self._path.exists():
                data = json.loads(self._path.read_text(encoding="utf-8"))
                self._counter = data.get("counter", 0)
                for item in data.get("records", []):
                    self._records.append(ADR(**item))
                for item in data.get("outcomes", []):
                    self._outcomes.append(DecisionOutcome(**item))
                logger.debug("ADR: loaded %d records, %d outcomes (counter=%d)",
                             len(self._records), len(self._outcomes), self._counter)
        except Exception as exc:
            logger.warning("ADR: load failed (%s), starting fresh", exc)
            self._records = []
            self._outcomes = []
            self._counter = 0

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "counter": self._counter,
                "records": [asdict(r) for r in self._records],
                "outcomes": [asdict(o) for o in self._outcomes],
            }
            self._path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("ADR: save failed: %s", exc)

    def _next_id(self) -> str:
        self._counter += 1
        return f"ADR-{self._counter:03d}"

    # ── Public API ───────────────────────────────────────────────────

    def record(self, adr: ADR) -> ADR:
        """Ghi một ADR. Tự động gán ID và mark old ADRs as superseded."""
        # Mark old active decisions in same category as superseded
        for existing in self._records:
            if (existing.category == adr.category
                    and existing.decision != adr.decision
                    and existing.status == "active"):
                existing.status = "superseded"

        adr.adr_id = self._next_id()
        self._records.append(adr)
        self._save()
        logger.info("ADR: %s — %s → %s (iter %d)",
                     adr.adr_id, adr.category, adr.decision, adr.iteration)
        return adr

    def get_by_id(self, adr_id: str) -> Optional[ADR]:
        for r in self._records:
            if r.adr_id == adr_id:
                return r
        return None

    def get_by_category(self, category: str) -> list[ADR]:
        return [r for r in self._records if r.category == category]

    def get_active(self, category: str) -> Optional[ADR]:
        """Get active (latest) decision for a category."""
        matched = [r for r in self._records
                   if r.category == category and r.status == "active"]
        if not matched:
            return None
        return max(matched, key=lambda r: r.iteration)

    def has_oscillation(self, category: str) -> bool:
        """Kiểm tra category có đổi ý ≥ 2 lần không."""
        decisions = set()
        for r in self._records:
            if r.category == category:
                decisions.add(r.decision)
                if len(decisions) >= 2:
                    return True
        return False

    def get_all_categories(self) -> set[str]:
        return {r.category for r in self._records}

    # ── Context injection ────────────────────────────────────────────

    def format_context(self, current_iteration: int = 0) -> str:
        """Inject ADR context cho planner.

        Bao gồm:
          - Active decisions (luôn hiển thị)
          - Gần đây (last 100 iter)
          - Categories bị oscillation
        """
        if not self._records:
            return ""

        lines = ["## Architecture Decisions:"]
        recent_threshold = max(0, current_iteration - 100)

        # Active decisions (show all, regardless of age)
        active = [r for r in self._records if r.status == "active"]
        if active:
            lines.append(f"  Active ({len(active)}):")
            for r in sorted(active, key=lambda x: x.iteration, reverse=True):
                icon = _CATEGORY_ICONS.get(r.category, "•")
                lines.append(f"    {r.adr_id} iter {r.iteration}: [{icon} {r.category}] {r.decision}")
                lines.append(f"      → {r.rationale[:120]}")

        # Recent decisions (within last 100 iterations)
        recent = [r for r in self._records
                  if r.iteration >= recent_threshold and r.status != "active"]
        if recent:
            lines.append(f"  Recent (last 100 iterations):")
            for r in sorted(recent, key=lambda x: x.iteration, reverse=True)[:3]:
                lines.append(f"    {r.adr_id} iter {r.iteration}: [{r.category}] {r.decision} ({r.status})")

        # Oscillating categories
        oscillating = [cat for cat in self.get_all_categories()
                       if self.has_oscillation(cat)]
        if oscillating:
            lines.append("  ⚡ Categories with changing decisions:")
            for cat in sorted(oscillating):
                records = self.get_by_category(cat)
                chain = " → ".join(
                    f"{r.adr_id}({r.decision})" for r in records
                )
                lines.append(f"    [{cat}] {chain}")

        return "\n".join(lines)

    def get_context_for_proposal(self, category: str, proposed_decision: str) -> str:
        """Khi planner đề xuất thay đổi, inject context với ADR cũ.

        Returns:
            Empty string nếu proposal khớp active decision.
            Warning string nếu proposal khác active decision:
              "ADR-007 (active): chose JWT because Stateless.
               Proposed: Session.
               What changed since iteration 58?"
        """
        active = self.get_active(category)
        if active is None:
            return ""
        if active.decision == proposed_decision:
            return ""

        # Count decisions since the active one (how much has changed?)
        subsequent = [r for r in self._records
                      if r.iteration > active.iteration]
        since_then = f" ({len(subsequent)} decisions since)" if subsequent else ""

        return (
            f"[WARN] {active.adr_id} ({active.status}, iter {active.iteration}): "
            f"chose '{active.decision}' because {active.rationale[:100]}. "
            f"Proposed: '{proposed_decision}'. "
            f"What changed{since_then}?"
        )

    def what_changed_since(self, adr_id: str) -> str:
        """Liệt kê mọi thay đổi sau một ADR cụ thể.

        Useful khi agent cần đánh giá "điều gì đã thay đổi kể từ ADR-007"
        trước khi quyết định có đảo ngược decision hay không.
        """
        anchor = self.get_by_id(adr_id)
        if anchor is None:
            return f"  ADR not found: {adr_id}"

        subsequent = [r for r in self._records
                      if r.iteration > anchor.iteration]
        if not subsequent:
            return f"  No decisions since {adr_id}"

        parts = [f"  Decisions since {adr_id} (iter {anchor.iteration}):"]
        for r in subsequent:
            parts.append(f"    {r.adr_id} iter {r.iteration}: [{r.category}] {r.decision} → {r.rationale[:80]}")
        return "\n".join(parts)

    # ── Outcome tracking ────────────────────────────────────────────

    def record_outcome(self, adr_id: str, outcome: str, evidence: list[str],
                       evaluation_iteration: int) -> Optional[DecisionOutcome]:
        """Ghi kết quả của một ADR sau nhiều iterations.

        Args:
            adr_id: "ADR-007"
            outcome: "good", "bad", "mixed"
            evidence: ["bundle size giảm", "state duplication resolved"]
            evaluation_iteration: iteration đánh giá
        """
        if outcome not in ("good", "bad", "mixed"):
            logger.warning("ADR: invalid outcome '%s' for %s", outcome, adr_id)
            return None

        adr = self.get_by_id(adr_id)
        if adr is None:
            logger.warning("ADR: cannot record outcome for unknown %s", adr_id)
            return None

        # Update ADR itself
        adr.outcome = outcome
        adr.outcome_evidence = evidence

        # Record in outcomes list
        o = DecisionOutcome(
            adr_id=adr_id,
            outcome=outcome,
            evidence=evidence,
            evaluation_iteration=evaluation_iteration,
        )
        self._outcomes.append(o)
        self._save()
        logger.info("ADR: outcome %s=%s at iter %d (%s)",
                     adr_id, outcome, evaluation_iteration, "; ".join(evidence[:2]))
        return o

    def get_outcomes(self, category: Optional[str] = None) -> list[DecisionOutcome]:
        """Get outcomes, optionally filtered by category."""
        if category is None:
            return list(self._outcomes)
        adr_ids = {r.adr_id for r in self._records if r.category == category}
        return [o for o in self._outcomes if o.adr_id in adr_ids]

    def format_outcomes_context(self) -> str:
        """Format outcome history for context injection.

        Shows:
          - Outcome distribution (good/bad/mixed per category)
          - Notable outcomes (bad or mixed)
        """
        if not self._outcomes:
            return ""

        lines = ["## Decision Outcomes (historical):"]

        # Count by category
        categories = {r.category for r in self._records if r.adr_id in {o.adr_id for o in self._outcomes}}
        for cat in sorted(categories):
            cat_outcomes = self.get_outcomes(cat)
            good = sum(1 for o in cat_outcomes if o.outcome == "good")
            bad = sum(1 for o in cat_outcomes if o.outcome == "bad")
            mixed = sum(1 for o in cat_outcomes if o.outcome == "mixed")
            total = len(cat_outcomes)
            if total > 0:
                icon = "[OK]" if bad == 0 else "[WARN]" if bad <= mixed else "[ERR]"
                lines.append(f"  {icon} [{cat}] {good}/{total} good, {bad} bad, {mixed} mixed")

        # Show bad/mixed with evidence
        problem_outcomes = [o for o in self._outcomes if o.outcome in ("bad", "mixed")]
        if problem_outcomes:
            lines.append("  ⚡ Decisions with negative outcomes:")
            for o in problem_outcomes:
                adr = self.get_by_id(o.adr_id)
                if adr:
                    evidence_text = "; ".join(o.evidence[:3])
                    lines.append(f"    {o.adr_id} ({adr.decision}): {o.outcome} — {evidence_text}")

        # Show good outcomes: decisions that worked
        good_outcomes = [o for o in self._outcomes if o.outcome == "good"]
        if good_outcomes:
            lines.append("  [OK] Decisions with positive outcomes:")
            for o in good_outcomes[:3]:
                adr = self.get_by_id(o.adr_id)
                if adr:
                    evidence_text = "; ".join(o.evidence[:2])
                    lines.append(f"    {o.adr_id} ({adr.decision}): {evidence_text}")

        return "\n".join(lines)

    # ── Override validation (Cognitive Friction) ─────────────────────

    def validate_override(self, category: str, proposed_decision: str,
                          justification: dict, repo_root: str | Path = "",
                          metrics_file: str | Path | None = None) -> tuple[bool, str]:
        """Validate an ADR override justification.

        Cognitive Friction mechanism: LLM muốn override ADR phải nộp
        justification với evidence_ref thật (commit hash hoặc metric).

        Returns:
            (True, "") nếu hợp lệ.
            (False, error_message) nếu không hợp lệ.
        """
        from core.validator.models import ValidationSeverity

        active = self.get_active(category)
        if active is None:
            return False, f"No active ADR for category '{category}' to override"

        # Check 'trigger' matches the ADR being violated
        expected_trigger = f"{active.adr_id} violation"
        if justification.get("trigger", "") != expected_trigger:
            return (False,
                    f"trigger must be '{expected_trigger}', "
                    f"got '{justification.get('trigger')}'")

        result = validate_override_justification(justification, repo_root, metrics_file)
        if result.passed:
            return True, ""

        errors = [i.message for i in result.issues
                  if i.severity == ValidationSeverity.ERROR]
        return False, "; ".join(errors[:3])

    # ── Signals ──────────────────────────────────────────────────────

    def to_signals(self) -> list[Signal]:
        """Emit signal nếu có oscillation (plan drift)."""
        signals: list[Signal] = []
        oscillating = [cat for cat in self.get_all_categories()
                       if self.has_oscillation(cat)]
        if oscillating:
            for cat in oscillating:
                records = self.get_by_category(cat)
                if len(records) >= 2:
                    latest = records[-1]
                    prev = records[-2]
                    signals.append(Signal(
                        category="architecture",
                        evidence_level=1,
                        observation=(
                            f"Category '{cat}' changed: "
                            f"{prev.adr_id}({prev.decision}) → "
                            f"{latest.adr_id}({latest.decision})"
                        ),
                        confidence=0.7,
                        severity_hint=0.7,
                    ))
        return signals
