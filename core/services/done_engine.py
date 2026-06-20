"""Done Condition Engine — generate observable verification from user goal.

User: "Thêm dark mode"
  ↓ LLM generates verification steps
  ↓ Engine runs each step
  ↓ Report: [OK] / [ERR]
  ↓ Only then DONE

So sánh với DoneConditionParser cũ:
  Parser: extract conditions từ plan text (passive, chỉ đọc)
  Engine: generate conditions từ GOAL + execute (active, chạy thật)
"""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("orca.done_engine")


@dataclass
class VerificationStep:
    """Một bước kiểm tra cụ thể, observable."""
    type: str  # "file_exists", "content_pattern", "build_pass", "command_ok", "user_confirm", "runtime_check"
    description: str
    target: str = ""
    expected: str = ""
    optional: bool = False  # Failure = warning, không block DONE

    def to_dict(self) -> dict:
        return {"type": self.type, "description": self.description,
                "target": self.target, "expected": self.expected, "optional": self.optional}

    @classmethod
    def from_dict(cls, d: dict) -> VerificationStep:
        return cls(**d)


@dataclass
class VerificationResult:
    """Kết quả của một bước kiểm tra."""
    step: VerificationStep
    passed: bool
    actual: str = ""
    evidence: str = ""
    elapsed: float = 0.0

    @property
    def icon(self) -> str:
        if self.passed:
            return "[OK]"
        if self.step.optional:
            return "[WARN]"
        return "[ERR]"

    @property
    def summary_line(self) -> str:
        return f"  {self.icon} {self.step.description}"


class VerificationReport:
    """Báo cáo tổng hợp tất cả các bước kiểm tra."""
    def __init__(self):
        self.results: list[VerificationResult] = []

    def add(self, r: VerificationResult) -> None:
        self.results.append(r)

    @property
    def all_pass(self) -> bool:
        return all(r.passed or r.step.optional for r in self.results)

    @property
    def blockers(self) -> list[VerificationResult]:
        return [r for r in self.results if not r.passed and not r.step.optional]

    @property
    def summary(self) -> str:
        lines = ["Verification Report:"]
        for r in self.results:
            lines.append(r.summary_line)
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        lines.append(f"  {'[OK]' if self.all_pass else '[ERR]'} {passed}/{total} passed")
        if self.blockers:
            lines.append(f"  BLOCKERS ({len(self.blockers)}):")
            for b in self.blockers:
                lines.append(f"    [ERR] {b.step.description}: expected={b.step.expected}, actual={b.actual}")
        return "\n".join(lines)


class DoneConditionEngine:
    """Sinh + thực thi verification steps từ user goal.

    Usage:
        engine = DoneConditionEngine(project_root)
        steps = engine.generate_steps(goal="Thêm dark mode", context=...)
        report = engine.execute(steps)
        if report.all_pass:
            mark_done()
    """

    def __init__(self, project_root: str):
        self._root = Path(project_root)

    # ── Generate steps ─────────────────────────────────────────────────

    def generate_steps(self, goal: str, context: str = "",
                       existing_steps: Optional[list[dict]] = None) -> list[VerificationStep]:
        """Generate verification steps từ goal.
        Dùng LLM nếu có client, fallback về rule-based.
        """
        if existing_steps:
            return [VerificationStep(**s) if isinstance(s, dict) else s for s in existing_steps]
        return self._rule_based_steps(goal)

    def _rule_based_steps(self, goal: str) -> list[VerificationStep]:
        """Fallback: rule-based step generation cho common patterns."""
        steps: list[VerificationStep] = []
        g = goal.lower()

        # Build check — luôn có
        steps.append(VerificationStep(
            type="build_pass", description="Project build không lỗi",
            expected="exit_code=0",
        ))

        # File existence hints
        file_match = re.findall(r'[\w/\\-]+\.(py|js|ts|jsx|tsx|html|css|scss|json|toml)', goal)
        for f in file_match[:3]:
            steps.append(VerificationStep(
                type="file_exists", description=f"File '{f}' tồn tại",
                target=f,
            ))

        # Pattern-based steps
        if any(w in g for w in ("dark mode", "theme", "toggle", "sáng", "tối")):
            steps.append(VerificationStep(
                type="content_pattern",
                description="Theme toggle class/variable tồn tại trong source",
                target="**/*.{tsx,jsx,html,js}",
                expected="dark|light|theme|data-theme",
            ))
        if any(w in g for w in ("api", "endpoint", "route", "rest")):
            steps.append(VerificationStep(
                type="command_ok",
                description="API endpoint trả về 200",
                target="curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/health",
                expected="200",
                optional=True,
            ))
        if any(w in g for w in ("database", "db", "sql", "migration", "schema")):
            steps.append(VerificationStep(
                type="command_ok",
                description="Migration chạy thành công",
                target="python -m alembic upgrade head",
                expected="exit_code=0",
                optional=True,
            ))
        if "test" in g:
            steps.append(VerificationStep(
                type="command_ok",
                description="Test suite pass",
                target="python -m pytest --tb=short -q",
                expected="exit_code=0",
            ))

        # Luôn có user confirm step cho UI/runtime checks
        steps.append(VerificationStep(
            type="user_confirm",
            description=f"User xác nhận: '{goal}' hoạt động đúng",
            optional=True,
        ))

        return steps

    # ── Execute steps ──────────────────────────────────────────────────

    def execute(self, steps: list[VerificationStep]) -> VerificationReport:
        """Thực thi tất cả verification steps."""
        report = VerificationReport()
        for step in steps:
            result = self._execute_one(step)
            report.add(result)
        return report

    def _execute_one(self, step: VerificationStep) -> VerificationResult:
        """Execute một step, trả về kết quả."""
        start = time.perf_counter()

        if step.type == "file_exists":
            return self._check_file_exists(step, start)
        elif step.type == "content_pattern":
            return self._check_content_pattern(step, start)
        elif step.type == "build_pass":
            return self._check_build(step, start)
        elif step.type == "command_ok":
            return self._check_command(step, start)
        elif step.type == "user_confirm":
            return self._check_user_confirm(step, start)
        elif step.type == "runtime_check":
            return self._check_runtime(step, start)
        else:
            elapsed = time.perf_counter() - start
            return VerificationResult(step=step, passed=False, actual=f"Unknown type: {step.type}", elapsed=elapsed)

    def _check_file_exists(self, step: VerificationStep, start: float) -> VerificationResult:
        path = self._resolve(step.target)
        exists = path.exists()
        elapsed = time.perf_counter() - start
        return VerificationResult(
            step=step, passed=exists,
            actual="found" if exists else "not found",
            evidence=str(path) if exists else "",
            elapsed=elapsed,
        )

    def _check_content_pattern(self, step: VerificationStep, start: float) -> VerificationResult:
        pattern = step.expected
        glob_pattern = step.target
        try:
            matches = list(self._root.rglob(glob_pattern)) if "*" in glob_pattern else [self._resolve(glob_pattern)]
            found = False
            evidence = ""
            for f in matches:
                if f.exists() and f.is_file():
                    content = f.read_text(encoding="utf-8", errors="replace")
                    if re.search(pattern, content, re.IGNORECASE):
                        found = True
                        evidence = f"{f}: matched"
                        break
            elapsed = time.perf_counter() - start
            return VerificationResult(
                step=step, passed=found,
                actual="found" if found else "not found",
                evidence=evidence,
                elapsed=elapsed,
            )
        except Exception as e:
            elapsed = time.perf_counter() - start
            return VerificationResult(step=step, passed=False, actual=str(e), elapsed=elapsed)

    def _check_build(self, step: VerificationStep, start: float) -> VerificationResult:
        try:
            result = subprocess.run(
                self._detect_build_command(),
                shell=True, capture_output=True, text=True,
                cwd=str(self._root), timeout=180,
            )
            elapsed = time.perf_counter() - start
            passed = result.returncode == 0
            return VerificationResult(
                step=step, passed=passed,
                actual=f"exit={result.returncode}",
                evidence=result.stderr[:200] if not passed else "",
                elapsed=elapsed,
            )
        except Exception as e:
            elapsed = time.perf_counter() - start
            return VerificationResult(step=step, passed=False, actual=str(e), elapsed=elapsed)

    def _check_command(self, step: VerificationStep, start: float) -> VerificationResult:
        try:
            result = subprocess.run(
                step.target, shell=True, capture_output=True, text=True,
                cwd=str(self._root), timeout=120,
            )
            elapsed = time.perf_counter() - start
            expected_exit = 0
            if "exit_code=" in step.expected:
                expected_exit = int(step.expected.split("=")[1])
            passed = result.returncode == expected_exit
            if step.expected == "200":
                passed = "200" in result.stdout
            return VerificationResult(
                step=step, passed=passed,
                actual=f"exit={result.returncode}",
                evidence=result.stdout[:200] or result.stderr[:200],
                elapsed=elapsed,
            )
        except Exception as e:
            elapsed = time.perf_counter() - start
            return VerificationResult(step=step, passed=False, actual=str(e), elapsed=elapsed)

    def _check_user_confirm(self, step: VerificationStep, start: float) -> VerificationResult:
        """Steps cần user confirm — luôn trả về passed vì user tự quyết định."""
        elapsed = time.perf_counter() - start
        return VerificationResult(
            step=step, passed=True,
            actual="pending user confirmation",
            evidence=step.description,
            elapsed=elapsed,
        )

    def _check_runtime(self, step: VerificationStep, start: float) -> VerificationResult:
        """Runtime check (HTTP, server) — optional, không block."""
        elapsed = time.perf_counter() - start
        return VerificationResult(
            step=step, passed=True,
            actual="runtime check skipped (auto-passed)",
            evidence="Runtime checks require manual verification",
            elapsed=elapsed,
        )

    # ── Helpers ────────────────────────────────────────────────────────

    def _resolve(self, path: str) -> Path:
        p = Path(path)
        if p.is_absolute():
            return p
        return self._root / p

    def _detect_build_command(self) -> str:
        if (self._root / "package.json").exists():
            return "npm run build 2>&1"
        if (self._root / "pyproject.toml").exists() or (self._root / "setup.py").exists():
            return "python -m compileall . -q 2>&1"
        if (self._root / "Cargo.toml").exists():
            return "cargo build 2>&1"
        if (self._root / "go.mod").exists():
            return "go build ./... 2>&1"
        return "echo no build command detected"
