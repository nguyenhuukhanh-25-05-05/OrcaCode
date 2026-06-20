"""Evidence Manager — stores, retrieves, and verifies tool execution evidence.

All evidence is stored as files in .evidence/ directory.
The agent NEVER reports pass/fail — evidence files are the only source of truth.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from core.evidence.conditions import ConditionResult, ConditionType, DoneConditions
from core.evidence.runners import RunResult


@dataclass
class EvidenceEntry:
    tool_name: str
    exit_code: int
    passed: bool
    stdout: str
    stderr: str
    elapsed: float
    timestamp: float = 0.0
    command: str = ""
    test_pass_count: int = 0
    test_fail_count: int = 0
    test_total_count: int = 0
    test_failures: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()

    @property
    def summary(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return f"[{status}] {self.tool_name} (exit={self.exit_code}, {self.elapsed:.1f}s)"

    def to_condition(self, name: str = "") -> ConditionResult:
        return ConditionResult(
            type=ConditionType(self.tool_name),
            name=name or self.tool_name,
            passed=self.passed,
            exit_code=self.exit_code,
            output_summary=self.summary,
            details=self.full_output[:500],
        )

    @property
    def full_output(self) -> str:
        parts = []
        if self.stdout:
            parts.append(self.stdout)
        if self.stderr:
            parts.append(self.stderr)
        return "\n".join(parts)


class EvidenceManager:
    """Stores and verifies evidence from tool executions.

    Evidence directory structure:
        .orca/evidence/
            build.log       # JSON lines — one EvidenceEntry per line
            lint.log
            typecheck.log
            test.log
    """

    def __init__(self, project_root: str = "."):
        self.root = Path(project_root)
        self._evidence_dir = self.root / ".orca" / "evidence"
        self._evidence_dir.mkdir(parents=True, exist_ok=True)

    def _log_path(self, tool_name: str) -> Path:
        return self._evidence_dir / f"{tool_name}.log"

    def record(self, tool_name: str, result: RunResult) -> EvidenceEntry:
        """Record tool execution result as evidence."""
        entry = EvidenceEntry(
            tool_name=tool_name,
            exit_code=result.exit_code,
            passed=result.passed,
            stdout=result.stdout,
            stderr=result.stderr,
            elapsed=result.elapsed,
            command=result.command,
        )
        self._append_entry(entry)
        return entry

    def _append_entry(self, entry: EvidenceEntry) -> None:
        path = self._log_path(entry.tool_name)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")

    def get_latest(self, tool_name: str) -> Optional[EvidenceEntry]:
        """Get the most recent evidence entry for a tool."""
        path = self._log_path(tool_name)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            if not lines:
                return None
            return EvidenceEntry(**json.loads(lines[-1]))
        except (json.JSONDecodeError, KeyError, TypeError):
            return None

    def get_all(self, tool_name: str) -> list[EvidenceEntry]:
        """Get all evidence entries for a tool."""
        path = self._log_path(tool_name)
        if not path.exists():
            return []
        entries = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(EvidenceEntry(**json.loads(line)))
                    except (json.JSONDecodeError, KeyError, TypeError):
                        pass
        return entries

    def latest_passed(self, tool_name: str) -> bool:
        """Check if the latest run of a tool passed."""
        entry = self.get_latest(tool_name)
        return entry is not None and entry.passed

    def run_and_record(self, runner) -> EvidenceEntry:
        """Run a tool and record its result as evidence."""
        result = runner.run()
        return self.record(runner.command.split()[0] if " " in runner.command else runner.command, result)

    def build_conditions(self) -> DoneConditions:
        """Build a DoneConditions from latest evidence."""
        conditions = DoneConditions()
        for tool_name in ["build", "lint", "typecheck", "test"]:
            entry = self.get_latest(tool_name)
            if entry is not None:
                conditions.add(entry.to_condition())
        return conditions

    def clear(self) -> None:
        """Remove all evidence files."""
        for path in self._evidence_dir.iterdir():
            if path.suffix == ".log":
                path.unlink()

    @property
    def evidence_dir(self) -> Path:
        return self._evidence_dir
