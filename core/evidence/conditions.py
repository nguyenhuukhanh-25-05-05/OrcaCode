"""Done conditions — the checklist that must be satisfied for task completion."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ConditionType(Enum):
    BUILD = "build"
    LINT = "lint"
    TYPE_CHECK = "type_check"
    TEST = "test"
    E2E = "e2e"
    CUSTOM = "custom"


@dataclass
class ConditionResult:
    type: ConditionType
    name: str
    passed: bool
    exit_code: Optional[int] = None
    output_summary: str = ""
    details: str = ""

    @property
    def status_icon(self) -> str:
        return "PASS" if self.passed else "FAIL"


@dataclass
class DoneConditions:
    conditions: list[ConditionResult] = field(default_factory=list)

    def add(self, result: ConditionResult) -> None:
        self.conditions.append(result)

    def all_pass(self) -> bool:
        return all(c.passed for c in self.conditions)

    def failures(self) -> list[ConditionResult]:
        return [c for c in self.conditions if not c.passed]

    def summary(self) -> str:
        lines = ["Done Conditions:"]
        for c in self.conditions:
            icon = "✓" if c.passed else "✗"
            lines.append(f"  {icon} [{c.status_icon}] {c.name}")
            if c.output_summary:
                lines.append(f"      {c.output_summary}")
        lines.append(f"  ──> {'ALL PASS' if self.all_pass() else 'SOME FAILED'}")
        return "\n".join(lines)

    def reset(self) -> None:
        self.conditions.clear()
