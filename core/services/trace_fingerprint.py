"""Execution Trace Fingerprint — lightweight per-iteration observability.

Logs key metrics per iteration to a structured JSON file (.orca/trace_fingerprint.jsonl)
so long-run validation (100-200 iterations) produces machine-readable diagnostic data.

Non-intrusive: does not modify agent logic, only observes and records.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

TRACE_DIR = ".orca/traces"
MAX_LINES = 5000  # Auto-rotate after this many entries


@dataclass
class Fingerprint:
    """Snapshot of key metrics at a single iteration."""
    iteration: int
    timestamp: float = 0.0

    # Hashes (stability indicators)
    decision_hash: str = ""     # sha1 of concatenated decision strings
    messages_hash: str = ""     # sha1 of serialized messages (detects context drift)
    files_hash: str = ""        # sha1 of sorted modified_files paths

    # Quality metrics
    spec_score: float = -1.0    # -1 = not computed this iteration
    fidelity_overall: float = -1.0
    fidelity_goal: float = -1.0
    fidelity_plan: float = -1.0
    fidelity_decisions: float = -1.0

    # Contract metrics
    contract_violations: int = 0
    contract_warnings: int = 0

    # Execution metrics
    pressure_level: int = 0
    n_llm_calls: int = 0
    n_tool_calls: int = 0
    n_modified_files: int = 0
    n_scratchpad_entries: int = 0

    # Checkpoint
    checkpoint_available: bool = False
    checkpoint_iteration: int = 0

    # Failure indicators
    consecutive_failures: int = 0
    build_failures: int = 0
    rollback_triggered: bool = False

    # Loop health
    estimated_tokens: int = 0

    def to_dict(self) -> dict:
        return {
            "i": self.iteration,
            "ts": round(self.timestamp, 2),
            "h_dec": self.decision_hash[:8],
            "h_msg": self.messages_hash[:8],
            "h_files": self.files_hash[:8],
            "spec": round(self.spec_score, 2) if self.spec_score >= 0 else None,
            "fid": round(self.fidelity_overall, 2) if self.fidelity_overall >= 0 else None,
            "fid_g": round(self.fidelity_goal, 2) if self.fidelity_goal >= 0 else None,
            "fid_p": round(self.fidelity_plan, 2) if self.fidelity_plan >= 0 else None,
            "fid_d": round(self.fidelity_decisions, 2) if self.fidelity_decisions >= 0 else None,
            "cv": self.contract_violations,
            "cw": self.contract_warnings,
            "p": self.pressure_level,
            "llm": self.n_llm_calls,
            "tool": self.n_tool_calls,
            "files": self.n_modified_files,
            "spad": self.n_scratchpad_entries,
            "ckpt": self.checkpoint_iteration if self.checkpoint_available else None,
            "cf": self.consecutive_failures,
            "bf": self.build_failures,
            "rb": 1 if self.rollback_triggered else 0,
            "tok": self.estimated_tokens,
        }


class TraceFingerprint:
    """Append-only structured trace logger for long-run diagnostics."""

    def __init__(self, project_root: str):
        self._root = Path(project_root).resolve()
        self._trace_dir = self._root / TRACE_DIR
        self._trace_dir.mkdir(parents=True, exist_ok=True)
        self._file = self._trace_dir / "fingerprint.jsonl"
        self._line_count = 0

    def record(self, fp: Fingerprint) -> None:
        """Append a fingerprint entry. Auto-rotates if line count exceeds MAX_LINES."""
        fp.timestamp = time.time()
        try:
            if self._line_count >= MAX_LINES:
                self._rotate()

            line = json.dumps(fp.to_dict(), ensure_ascii=False)
            with open(self._file, "a", encoding="utf-8") as f:
                f.write(line + "\n")
            self._line_count += 1
        except Exception:
            pass  # Non-fatal — trace logging must never crash the agent

    def read_all(self) -> list[Fingerprint]:
        """Read all fingerprint entries (for post-run analysis)."""
        entries = []
        if not self._file.exists():
            return entries
        try:
            with open(self._file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                        entries.append(self._from_dict(d))
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass
        return entries

    def get_stats(self) -> dict:
        """Quick stats from trace data."""
        entries = self.read_all()
        if not entries:
            return {"total_iterations": 0}

        fid_values = [e.fidelity_overall for e in entries if e.fidelity_overall >= 0]
        spec_values = [e.spec_score for e in entries if e.spec_score >= 0]
        pressure_counts = {0: 0, 1: 0, 2: 0, 3: 0}
        for e in entries:
            if e.pressure_level in pressure_counts:
                pressure_counts[e.pressure_level] += 1

        return {
            "total_iterations": len(entries),
            "max_fidelity": round(max(fid_values), 3) if fid_values else None,
            "min_fidelity": round(min(fid_values), 3) if fid_values else None,
            "avg_fidelity": round(sum(fid_values) / len(fid_values), 3) if fid_values else None,
            "max_spec_score": round(max(spec_values), 3) if spec_values else None,
            "avg_spec_score": round(sum(spec_values) / len(spec_values), 3) if spec_values else None,
            "pressure_distribution": pressure_counts,
            "rollback_count": sum(1 for e in entries if e.rollback_triggered),
            "max_consecutive_failures": max((e.consecutive_failures for e in entries), default=0),
        }

    def clear(self) -> None:
        """Remove all trace files."""
        if self._file.exists():
            self._file.unlink()
        self._line_count = 0

    def _rotate(self) -> None:
        """Rotate: rename current file, start fresh."""
        if not self._file.exists():
            self._line_count = 0
            return
        ts = int(time.time())
        archive = self._trace_dir / f"fingerprint_{ts}.jsonl"
        try:
            self._file.rename(archive)
        except Exception:
            pass
        self._line_count = 0

    @staticmethod
    def _from_dict(d: dict) -> Fingerprint:
        return Fingerprint(
            iteration=d.get("i", 0),
            timestamp=d.get("ts", 0),
            decision_hash=d.get("h_dec", ""),
            messages_hash=d.get("h_msg", ""),
            files_hash=d.get("h_files", ""),
            spec_score=d.get("spec", -1.0) or -1.0,
            fidelity_overall=d.get("fid", -1.0) or -1.0,
            fidelity_goal=d.get("fid_g", -1.0) or -1.0,
            fidelity_plan=d.get("fid_p", -1.0) or -1.0,
            fidelity_decisions=d.get("fid_d", -1.0) or -1.0,
            contract_violations=d.get("cv", 0),
            contract_warnings=d.get("cw", 0),
            pressure_level=d.get("p", 0),
            n_llm_calls=d.get("llm", 0),
            n_tool_calls=d.get("tool", 0),
            n_modified_files=d.get("files", 0),
            n_scratchpad_entries=d.get("spad", 0),
            checkpoint_available=d.get("ckpt") is not None,
            checkpoint_iteration=d.get("ckpt", 0) or 0,
            consecutive_failures=d.get("cf", 0),
            build_failures=d.get("bf", 0),
            rollback_triggered=bool(d.get("rb", 0)),
            estimated_tokens=d.get("tok", 0),
        )


# ── Hash helpers ────────────────────────────────────────

def hash_messages(messages: list[dict]) -> str:
    """Produce a stable SHA1 of message list for drift detection."""
    text = "||".join(
        f"{m.get('role','')}:{str(m.get('content',''))[:100]}"
        for m in messages[-8:]  # Last 8 messages only
    )
    return hashlib.sha1(text.encode("utf-8", errors="replace")).hexdigest()


def hash_decisions(decisions: list[dict]) -> str:
    """Produce a SHA1 of recent decisions."""
    text = "||".join(
        d.get("decision", "")[:80] for d in (decisions or [])[-10:]
    )
    return hashlib.sha1(text.encode("utf-8", errors="replace")).hexdigest()


def hash_files(files: set[str]) -> str:
    """Produce a SHA1 of sorted file paths."""
    text = ",".join(sorted(files or []))
    return hashlib.sha1(text.encode("utf-8", errors="replace")).hexdigest()
