"""Evidence Baseline — capture pre-execution state + detect regressions.

Luồng:
  1. capture_baseline() → chạy build/lint/typecheck/test, lưu kết quả
  2. compare_to_baseline() → so sánh kết quả hiện tại với baseline
  3. has_regressed() → True nếu tool từng PASS giờ FAIL

Khác với EvidenceManager chỉ ghi log, Baseline biết "trước đó thế nào".
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from core.evidence.manager import EvidenceEntry, EvidenceManager
from core.evidence.conditions import ConditionResult, ConditionType, DoneConditions
from core.evidence.runners import BuildRunner, LintRunner, TestRunner, TypeCheckRunner, ToolRunner

logger = logging.getLogger("orca.evidence.baseline")


@dataclass
class BaselineEntry:
    """Kết quả của một tool tại thời điểm baseline."""
    tool_name: str
    passed: bool
    exit_code: int
    stdout_summary: str  # Chỉ lưu 200 bytes để tránh tốn disk
    stderr_summary: str
    elapsed: float
    timestamp: float = 0.0
    test_pass_count: int = 0
    test_fail_count: int = 0
    test_total_count: int = 0
    test_failures: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> BaselineEntry:
        return cls(**data)


@dataclass
class BaselineComparison:
    """Kết quả so sánh hiện tại vs baseline."""
    tool_name: str
    baseline: BaselineEntry
    current: EvidenceEntry
    regressed: bool  # baseline PASS, current FAIL
    improved: bool   # baseline FAIL, current PASS
    unchanged: bool  # same status

    @property
    def summary(self) -> str:
        if self.regressed:
            base = f"⬇ {self.tool_name}: PASS → FAIL (REGRESSION!)"
        elif self.improved:
            base = f"⬆ {self.tool_name}: FAIL → PASS"
        else:
            status = "PASS" if self.current.passed else "FAIL"
            base = f"  {self.tool_name}: {status} (unchanged)"
        # Add test details
        if self.tool_name == "test" and self.current.passed:
            tc = getattr(self.current, "test_total_count", 0)
            if tc:
                base += f" ({tc} tests)"
        elif self.tool_name == "test":
            tc = getattr(self.current, "test_total_count", 0)
            pc = getattr(self.current, "test_pass_count", 0)
            fc = getattr(self.current, "test_fail_count", 0)
            if tc:
                failures = getattr(self.current, "test_failures", [])
                fails_str = "; ".join(failures[:3])
                extra = f" ... +{len(failures)-3}" if len(failures) > 3 else ""
                base += f" ({pc}/{tc} passed, {fc} failed: {fails_str}{extra})"
        return base


class EvidenceBaseline:
    """Evidence baseline — biết trạng thái "trước khi sửa" của dự án.

    Usage:
        bl = EvidenceBaseline(project_root)
        bl.capture()  # chạy build/lint/typecheck/test → lưu baseline

        # ... sau khi agent sửa code ...

        comparison = bl.compare_with_current()
        if comparison.has_regression():
            print("FAIL: build từng pass giờ fail!")
    """

    def __init__(self, project_root: str):
        self._root = Path(project_root)
        self._baseline_dir = self._root / ".orca" / "baseline"
        self._baseline_dir.mkdir(parents=True, exist_ok=True)
        self._entries: dict[str, BaselineEntry] = {}
        self._captured = False

    # ── Capture ────────────────────────────────────────────────────────

    def capture(self, tools: Optional[list[str]] = None) -> int:
        """Chạy các tool và capture baseline.
        tools: list tên tool để chạy (mặc định: build, lint, typecheck, test)
        Returns số tool đã capture.
        """
        default_tools = ["build", "lint", "typecheck", "test"]
        tool_names = tools or default_tools
        runner_map = {
            "build": lambda: BuildRunner(cwd=str(self._root)),
            "lint": lambda: LintRunner(cwd=str(self._root)),
            "typecheck": lambda: TypeCheckRunner(cwd=str(self._root)),
            "test": lambda: TestRunner(cwd=str(self._root)),
        }

        count = 0
        for name in tool_names:
            factory = runner_map.get(name)
            if not factory:
                logger.warning("Unknown tool: %s", name)
                continue
            try:
                runner = factory()
                if not runner.command:
                    logger.info("No command for %s — skipping", name)
                    continue
                result = runner.run()
                entry = BaselineEntry(
                    tool_name=name,
                    passed=result.passed,
                    exit_code=result.exit_code,
                    stdout_summary=result.stdout[:200],
                    stderr_summary=result.stderr[:200],
                    elapsed=result.elapsed,
                )
                # Extract test-specific metadata
                if name == "test" and isinstance(runner, TestRunner):
                    entry.test_pass_count = runner._pass_count
                    entry.test_fail_count = runner._fail_count
                    entry.test_total_count = runner._total_count
                    entry.test_failures = runner._failures[:5]
                self._entries[name] = entry
                self._save_entry(entry)
                status = "PASS" if result.passed else "FAIL"
                logger.info("Baseline %s: %s (exit=%d, %.1fs)", name, status, result.exit_code, result.elapsed)
                count += 1
            except Exception as e:
                logger.warning("Baseline capture failed for %s: %s", name, e)

        self._captured = True
        return count

    def load(self) -> bool:
        """Load baseline từ disk (nếu đã có baseline từ lần chạy trước)."""
        baseline_file = self._baseline_dir / "baseline.json"
        if not baseline_file.exists():
            return False
        try:
            with open(baseline_file, encoding="utf-8") as f:
                data = json.load(f)
            for key, val in data.items():
                self._entries[key] = BaselineEntry(**val)
            self._captured = bool(self._entries)
            return self._captured
        except Exception:
            return False

    # ── Comparison ─────────────────────────────────────────────────────

    def compare_with_current(self) -> BaselineDiff:
        """So sánh baseline với kết quả hiện tại (chạy lại tools).
        Returns BaselineDiff với list comparisons + regression detection.
        """
        comparisons: list[BaselineComparison] = []
        for name, baseline_entry in self._entries.items():
            try:
                current = self._run_tool(name)
            except Exception as e:
                logger.warning("Compare failed for %s: %s", name, e)
                continue

            comparisons.append(BaselineComparison(
                tool_name=name,
                baseline=baseline_entry,
                current=current,
                regressed=baseline_entry.passed and not current.passed,
                improved=not baseline_entry.passed and current.passed,
                unchanged=baseline_entry.passed == current.passed,
            ))

        return BaselineDiff(comparisons=comparisons)

    def has_regression_since(self, tool_name: str) -> Optional[bool]:
        """Kiểm tra nhanh: tool *tool_name* có bị regression không?
        Returns True nếu từng PASS giờ FAIL, False nếu vẫn PASS, None nếu chưa có baseline.
        """
        baseline_entry = self._entries.get(tool_name)
        if baseline_entry is None:
            return None
        if not baseline_entry.passed:
            return False  # Đã FAIL từ baseline, không phải regression
        try:
            current = self._run_tool(tool_name)
        except Exception:
            return None
        return not current.passed

    # ── Internal ───────────────────────────────────────────────────────

    def _run_tool(self, name: str) -> EvidenceEntry:
        """Chạy một tool và trả về EvidenceEntry."""
        runner_map = {
            "build": BuildRunner(cwd=str(self._root)),
            "lint": LintRunner(cwd=str(self._root)),
            "typecheck": TypeCheckRunner(cwd=str(self._root)),
            "test": TestRunner(cwd=str(self._root)),
        }
        runner = runner_map.get(name)
        if runner is None:
            raise ValueError(f"Unknown tool: {name}")
        # Use existing EvidenceManager to record
        mgr = EvidenceManager(str(self._root))
        # Run the tool
        result = runner.run()
        entry = mgr.record(name, result)
        # Attach test metadata if applicable
        if name == "test" and isinstance(runner, TestRunner):
            entry.test_pass_count = runner._pass_count
            entry.test_fail_count = runner._fail_count
            entry.test_total_count = runner._total_count
            entry.test_failures = runner._failures[:5]
        return entry

    def _save_entry(self, entry: BaselineEntry) -> None:
        baseline_file = self._baseline_dir / "baseline.json"
        try:
            existing = {}
            if baseline_file.exists():
                with open(baseline_file, encoding="utf-8") as f:
                    existing = json.load(f)
            existing[entry.tool_name] = entry.to_dict()
            with open(baseline_file, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning("Failed to save baseline: %s", e)

    @property
    def captured(self) -> bool:
        return self._captured

    def clear(self) -> None:
        self._entries.clear()
        self._captured = False
        bf = self._baseline_dir / "baseline.json"
        if bf.exists():
            bf.unlink()


class BaselineDiff:
    """Kết quả so sánh baseline vs current."""
    def __init__(self, comparisons: list[BaselineComparison]):
        self.comparisons = comparisons

    def has_regression(self) -> bool:
        return any(c.regressed for c in self.comparisons)

    def regressions(self) -> list[BaselineComparison]:
        return [c for c in self.comparisons if c.regressed]

    def improvements(self) -> list[BaselineComparison]:
        return [c for c in self.comparisons if c.improved]

    def all_ok(self) -> bool:
        """Không regression, và tất cả tools đều pass."""
        return not self.has_regression() and all(c.current.passed for c in self.comparisons)

    def has_performance_regression(self) -> bool:
        """Phát hiện performance regression: duration tăng > 2x baseline."""
        for c in self.comparisons:
            base_dur = c.baseline.elapsed
            cur_dur = c.current.elapsed
            if base_dur > 1.0 and cur_dur > base_dur * 2 and c.current.passed:
                return True
        return False

    def performance_regressions(self) -> list[BaselineComparison]:
        """Trả về các tool bị performance regression."""
        result = []
        for c in self.comparisons:
            base_dur = c.baseline.elapsed
            cur_dur = c.current.elapsed
            if base_dur > 1.0 and cur_dur > base_dur * 2 and c.current.passed:
                result.append(c)
        return result

    def summary(self) -> str:
        lines = ["📊 Evidence Baseline Comparison:"]
        if not self.comparisons:
            lines.append("  (no baseline data)")
            return "\n".join(lines)
        for c in self.comparisons:
            lines.append(f"  {c.summary}")
        if self.has_regression():
            regressed_names = [c.tool_name for c in self.regressions()]
            lines.append(f"  [ERR] REGRESSION in: {', '.join(regressed_names)}")
        else:
            lines.append("  [OK] No regressions")
        # Performance regression
        perf = self.performance_regressions()
        if perf:
            for c in perf:
                ratio = c.current.elapsed / c.baseline.elapsed
                lines.append(f"  🐌 PERF REGRESSION: {c.tool_name} {c.baseline.elapsed:.1f}s → {c.current.elapsed:.1f}s ({ratio:.1f}x)")
        return "\n".join(lines)

    def to_conditions(self) -> DoneConditions:
        """Convert sang DoneConditions để tích hợp với evidence check flow."""
        conditions = DoneConditions()
        for c in self.comparisons:
            conditions.add(ConditionResult(
                type=ConditionType.CUSTOM,
                name=f"baseline/{c.tool_name}",
                passed=not c.regressed,
                output_summary=c.summary,
            ))
        return conditions
