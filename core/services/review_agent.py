"""Design Review Agent — advisory code review powered by LLM.

Chỉ advisory mode:
  - Đưa ra nhận xét về thiết kế, architecture, code style
  - KHÔNG có quyền block DONE, rollback, hay sửa code
  - Kết quả chỉ là QualityScore reduction + cảnh báo trong context

Vai trò:
  Thay vì LLM builder vừa code vừa tự review (conflict of interest),
  tách riêng một agent chuyên đọc diff và đưa ra góc nhìn độc lập.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from core.services.signal import Signal, Priority

logger = logging.getLogger("orca.review")


@dataclass
class ReviewFinding:
    """Một phát hiện của Review Agent."""
    category: str      # "design", "architecture", "naming", "style", "robustness"
    severity: str      # "major", "minor", "suggestion"
    message: str
    file_path: str = ""
    line: int = 0
    checker: str = "design"  # mapped to QUALITY_WEIGHTS for unified scoring


@dataclass
class ReviewReport:
    """Kết quả review của Design Review Agent."""
    findings: list[ReviewFinding] = field(default_factory=list)
    quality_penalty: int = 0   # 0-20 điểm trừ từ quality score
    summary: str = ""
    reviewed_files: int = 0

    def has_findings(self) -> bool:
        return len(self.findings) > 0

    @property
    def major_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "major")

    @property
    def minor_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "minor")

    def to_context(self) -> str:
        if not self.findings:
            return "  [OK] Design review: no issues found"
        lines = ["  Design Review Report:"]
        for f in self.findings[:8]:
            icon = "[ERR]" if f.severity == "major" else "[WARN]" if f.severity == "minor" else "💡"
            loc = f" [{f.file_path}:{f.line}]" if f.file_path else ""
            lines.append(f"    {icon} [{f.category}] {f.message}{loc}")
        if len(self.findings) > 8:
            lines.append(f"    ... +{len(self.findings)-8} more")
        lines.append(f"  Quality penalty: -{self.quality_penalty}")
        return "\n".join(lines)

    def to_signals(self) -> list[Signal]:
        """Convert findings → observation-only Signal objects.

        Detector chỉ cung cấp category + observation.
        Priority do SignalRanker gán.
        """
        signals: list[Signal] = []
        for finding in self.findings:
            signals.append(Signal(
                category="design",
                evidence_level=0,
                observation=finding.message,
                detail=f"{finding.file_path}:{finding.line}" if finding.file_path else "",
                confidence=0.7 if finding.severity == "major" else 0.5,
                severity_hint=0.7 if finding.severity == "major" else 0.4,
            ))
        return signals


# ══════════════════════════════════════════════════════════════════════
# Deterministic Design Rules (no LLM)
# ══════════════════════════════════════════════════════════════════════

_DESIGN_RULES: list[tuple[str, str, str, re.Pattern]] = [
    ("Mutability: function with mutable default arg (list/dict literal)",
     "robustness", "major", re.compile(r"def \w+\([^)]*=\s*[\[{][^}\]]*[\]}]")),
    ("Exception handling: bare except clause (catches KeyboardInterrupt etc)",
     "robustness", "major", re.compile(r"\bexcept\s*:")),
    ("Exception handling: except Exception without specified type",
     "robustness", "minor", re.compile(r"except Exception\s*:")),
    ("Output: print() call instead of logger",
     "style", "minor", re.compile(r"\bprint\s*\(")),
    ("Nesting: 4+ levels deep (if inside if inside if inside if)",
     "design", "major", re.compile(r"(?:    ){4,}(?:if |elif )")),
    ("Line length: > 120 chars",
     "style", "suggestion", re.compile(r"^.{121,}$", re.MULTILINE)),
    ("Imports: from X import *",
     "style", "minor", re.compile(r"from \S+ import \*")),
    ("Typing: # type: ignore without justification comment",
     "style", "suggestion", re.compile(r"# type: ignore(?!.*#)")),
    ("Returns: > 5 return statements in function",
     "design", "suggestion", None),
]


class DesignReviewer:
    """Deterministic design rules (không cần LLM).

    Dùng pattern matching thay vì LLM — ổn định 10/10 như Architectural Rules.
    LLM-based review là optional extension cho sau.
    """

    def __init__(self):
        self._rules = _DESIGN_RULES.copy()
        self._last_reported: dict[str, set[str]] = {}

    def add_rule(self, message: str, category: str, severity: str, pattern: str) -> None:
        """Add custom rule."""
        self._rules.append((message, category, severity, re.compile(pattern)))

    def review_file(self, file_path: str, content: str) -> list[ReviewFinding]:
        """Review một file với deterministic rules."""
        findings: list[ReviewFinding] = []
        lines = content.split("\n")

        for msg, cat, sev, pattern in self._rules:
            if pattern is None:
                # Rules that need counting, not single-pattern match
                if msg.startswith("Nhiều return"):
                    count = content.count("return ")
                    if count > 5:
                        findings.append(ReviewFinding(
                            category=cat, severity=sev, message=msg,
                            file_path=file_path, line=1,
                        ))
                continue

            matched = False
            for lineno, line in enumerate(lines, 1):
                if pattern.search(line):
                    matched = True
                    if file_path not in self._last_reported.get(pattern.pattern, set()):
                        self._last_reported.setdefault(pattern.pattern, set()).add(file_path)
                        findings.append(ReviewFinding(
                            category=cat, severity=sev, message=msg,
                            file_path=file_path, line=lineno,
                        ))
                        break

        return findings

    def review_diffs(self, modified_files: set[str], project_root: Path) -> ReviewReport:
        """Review all modified files and produce report."""
        report = ReviewReport()
        all_findings: list[ReviewFinding] = []

        for f in modified_files:
            try:
                content = (project_root / f).read_text(encoding="utf-8", errors="replace")
                findings = self.review_file(f, content)
                all_findings.extend(findings)
            except Exception:
                pass

        report.findings = all_findings
        report.reviewed_files = len(modified_files)

        # Quality score penalty
        majors = report.major_count
        minors = report.minor_count
        penalty = min(20, majors * 5 + minors * 2)
        report.quality_penalty = penalty

        # Summary
        if all_findings:
            others = len(all_findings) - majors - minors
            report.summary = (f"Found {len(all_findings)} issues "
                              f"({majors} major, {minors} minor, {others} suggestion)")
        else:
            report.summary = "No design issues found"

        return report
