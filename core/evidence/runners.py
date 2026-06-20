"""Tool runners — execute real tools and capture evidence.

Every runner returns stdout, stderr, exit_code, and elapsed time.
The EvidenceManager stores this output — never trust the model's report.
"""

from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class RunResult:
    exit_code: int
    stdout: str
    stderr: str
    elapsed: float
    command: str

    @property
    def passed(self) -> bool:
        return self.exit_code == 0

    @property
    def full_output(self) -> str:
        parts = []
        if self.stdout:
            parts.append(self.stdout)
        if self.stderr:
            parts.append(self.stderr)
        return "\n".join(parts)

    def truncate(self, max_lines: int = 50) -> str:
        lines = self.full_output.splitlines()
        if len(lines) <= max_lines:
            return self.full_output
        return "\n".join(lines[:max_lines] + [f"... ({len(lines) - max_lines} more lines)"])


class ToolRunner:
    """Base class for tool runners."""

    def __init__(self, command: str, cwd: Optional[str] = None, timeout: int = 120):
        self.command = command
        self.cwd = cwd
        self.timeout = timeout

    def _resolve_args(self) -> list[str]:
        """Split command into args; use shell if metacharacters or builtins present."""
        shell_chars = {"|", "&", ";", "<", ">", "$", "`"}
        if any(c in self.command for c in shell_chars):
            return [self.command]
        name = self.command.split()[0].lower()
        shell_builtins = {"echo", "cd", "exit", "export", "set", "source", "."}
        if name in shell_builtins:
            return [self.command]
        import shlex
        return shlex.split(self.command)

    def run(self) -> RunResult:
        t0 = time.perf_counter()
        args = self._resolve_args()
        use_shell = len(args) == 1 and args[0] == self.command
        try:
            proc = subprocess.run(
                self.command if use_shell else args,
                shell=use_shell,
                capture_output=True,
                text=True,
                cwd=self.cwd,
                timeout=self.timeout,
            )
            elapsed = time.perf_counter() - t0
            return RunResult(
                exit_code=proc.returncode,
                stdout=proc.stdout or "",
                stderr=proc.stderr or "",
                elapsed=elapsed,
                command=self.command,
            )
        except subprocess.TimeoutExpired:
            elapsed = time.perf_counter() - t0
            return RunResult(
                exit_code=-1,
                stdout="",
                stderr=f"Command timed out after {self.timeout}s",
                elapsed=elapsed,
                command=self.command,
            )
        except FileNotFoundError:
            elapsed = time.perf_counter() - t0
            return RunResult(
                exit_code=-2,
                stdout="",
                stderr=f"Command not found: {self.command.split()[0]}",
                elapsed=elapsed,
                command=self.command,
            )
        except Exception as e:
            elapsed = time.perf_counter() - t0
            return RunResult(
                exit_code=-3,
                stdout="",
                stderr=str(e),
                elapsed=elapsed,
                command=self.command,
            )


class BuildRunner(ToolRunner):
    """Runs a build command. Discovers package.json / pyproject.toml commands if not specified."""
    __test__ = False

    def __init__(self, cwd: Optional[str] = None, command: str = "", timeout: int = 180):
        if not command:
            command = self._detect_build_command(cwd or ".")
        super().__init__(command, cwd=cwd, timeout=timeout)

    @staticmethod
    def _detect_build_command(root: str) -> str:
        root_path = Path(root)
        if (root_path / "package.json").exists():
            return "npm run build 2>&1"
        if (root_path / "pyproject.toml").exists() or (root_path / "setup.py").exists():
            return "python -m compileall . -q 2>&1"
        if (root_path / "Cargo.toml").exists():
            return "cargo build 2>&1"
        if (root_path / "go.mod").exists():
            return "go build ./... 2>&1"
        return ""


class LintRunner(ToolRunner):
    """Runs a lint command."""
    __test__ = False

    def __init__(self, cwd: Optional[str] = None, command: str = "", timeout: int = 120):
        if not command:
            command = self._detect_lint_command(cwd or ".")
        super().__init__(command, cwd=cwd, timeout=timeout)

    @staticmethod
    def _detect_lint_command(root: str) -> str:
        root_path = Path(root)
        if (root_path / "package.json").exists():
            return "npx eslint . --format stylish 2>&1"
        if (root_path / "pyproject.toml").exists():
            if (root_path / ".ruff.toml").exists() or (root_path / "ruff.toml").exists():
                return "ruff check . 2>&1"
            return "python -m flake8 . 2>&1"
        if (root_path / "Cargo.toml").exists():
            return "cargo clippy -- -D warnings 2>&1"
        if (root_path / "go.mod").exists():
            return "go vet ./... 2>&1"
        return ""


class TypeCheckRunner(ToolRunner):
    """Runs a type checker."""
    __test__ = False

    def __init__(self, cwd: Optional[str] = None, command: str = "", timeout: int = 120):
        if not command:
            command = self._detect_typecheck_command(cwd or ".")
        super().__init__(command, cwd=cwd, timeout=timeout)

    @staticmethod
    def _detect_typecheck_command(root: str) -> str:
        root_path = Path(root)
        if (root_path / "tsconfig.json").exists() or (root_path / "package.json").exists():
            return "npx tsc --noEmit 2>&1"
        if (root_path / "pyproject.toml").exists():
            return "python -m mypy . 2>&1"
        return ""


class TestRunner(ToolRunner):
    """Runs a test suite — focused on files related to modified code."""
    __test__ = False  # prevent pytest from collecting this as a test class

    def __init__(self, cwd: Optional[str] = None, command: str = "",
                 timeout: int = 300, focused_files: Optional[list[str]] = None,
                 impacted_files: Optional[list[str]] = None):
        if not command:
            command = self._detect_test_command(cwd or ".")
        # Merge modified files + impacted files for focused testing
        all_focused: list[str] = list(focused_files or [])
        if impacted_files:
            for f in impacted_files:
                if f not in all_focused:
                    all_focused.append(f)
        if all_focused and command:
            command = self._build_focused_command(command, all_focused, cwd or ".")
        super().__init__(command, cwd=cwd, timeout=timeout)
        self._focused_files = all_focused or focused_files
        self._pass_count: int = 0
        self._fail_count: int = 0
        self._total_count: int = 0
        self._failures: list[str] = []

    @staticmethod
    def _detect_test_command(root: str) -> str:
        root_path = Path(root)
        if (root_path / "package.json").exists():
            return "npm test 2>&1"
        if (root_path / "pyproject.toml").exists() or (root_path / "setup.py").exists():
            return "python -m pytest --tb=short --no-header -q 2>&1"
        if (root_path / "Cargo.toml").exists():
            return "cargo test 2>&1"
        if (root_path / "go.mod").exists():
            return "go test ./... 2>&1"
        return ""

    @staticmethod
    def _build_focused_command(base_command: str, focused_files: list[str], root: str) -> str:
        """Convert 'python -m pytest -q' to 'python -m pytest -q test_a.py test_b.py'
        bằng cách tìm test file tương ứng với mỗi modified file.
        """
        root_path = Path(root)
        test_files: list[str] = []

        for mod_file in focused_files:
            mod = Path(mod_file)
            # Guess test paths
            candidates = []
            if mod.suffix == ".py":
                # src/service/user.py → tests/test_service/test_user.py
                parts = mod.parts
                # Strip src/ prefix, add tests/ prefix
                cleaned = [p for p in parts if p not in ("src", "app", "lib", ".")]
                test_path = Path("tests") / ("test_" + "_".join(cleaned))
                test_path2 = root_path / "tests" / mod.stem.replace(".", "/") / f"test_{mod.name}"
                test_path3 = root_path / "tests" / mod.stem.replace(".", "/") / f"test_{mod.stem}.py"
                candidates = [
                    root_path / f"tests/test_{mod.stem}.py",
                    test_path2,
                    test_path3,
                    root_path / f"tests/{mod.stem}_test.py",
                ]
                # Also check inline tests in the file itself
                if mod.name.startswith("test_"):
                    candidates.append(root_path / mod_file)
            elif mod.suffix in (".js", ".ts", ".jsx", ".tsx"):
                # src/service/user.ts → src/service/__tests__/user.test.ts
                base = mod.stem
                parent = mod.parent
                candidates = [
                    root_path / parent / f"{base}.test{mod.suffix}",
                    root_path / parent / f"{base}.spec{mod.suffix}",
                    root_path / parent / "__tests__" / f"{base}.test{mod.suffix}",
                    root_path / parent / "__tests__" / f"{base}.spec{mod.suffix}",
                ]

            for c in candidates:
                if c.exists() and str(c) not in test_files:
                    rel = c.relative_to(root_path).as_posix()
                    test_files.append(rel)

        if not test_files:
            return base_command

        # Build focused command
        if "pytest" in base_command:
            files_str = " ".join(test_files[:10])  # max 10 files
            return f"python -m pytest --tb=short --no-header -q {files_str} 2>&1"
        elif "npm test" in base_command or "jest" in base_command:
            files_str = " ".join(test_files[:10])
            return f"npx jest --no-coverage {files_str} 2>&1"
        else:
            return base_command

    def run(self) -> RunResult:
        result = super().run()
        # Parse test output for structured results
        self._parse_test_output(result.stdout + result.stderr)
        return result

    def _parse_test_output(self, output: str) -> None:
        """Parse pytest/jest output to extract pass/fail counts."""
        lines = output.splitlines()

        # Pytest format: "X passed, Y failed" (either order)
        # Match "X passed" and/or "Y failed" in any order
        passed_m = re.search(r'(\d+)\s+passed', output)
        failed_m = re.search(r'(\d+)\s+failed', output)
        errors_m = re.search(r'(\d+)\s+errors?', output)
        if passed_m or failed_m:
            self._pass_count = int(passed_m.group(1)) if passed_m else 0
            self._fail_count = (int(failed_m.group(1)) if failed_m else 0) + (int(errors_m.group(1)) if errors_m else 0)
            self._total_count = self._pass_count + self._fail_count
            # Extract failed test names (FAILED lines)
            for line in lines:
                if line.startswith("FAILED "):
                    self._failures.append(line[len("FAILED "):].strip())
            return

        # Jest format: "Tests: X failed, Y passed, Z total"
        jest_summary = re.search(r'Tests:\s*(?:(\d+)\s+failed,\s*)?(?:(\d+)\s+passed,\s*)?(\d+)\s+total', output)
        if jest_summary:
            self._fail_count = int(jest_summary.group(1) or 0)
            self._pass_count = int(jest_summary.group(2) or 0)
            self._total_count = int(jest_summary.group(3) or 0)
            # Extract FAIL lines
            for line in lines:
                if "●" in line and "›" not in line:
                    self._failures.append(line.strip().lstrip("● "))
            return

        # Generic: check for "FAIL" in output
        fail_lines = [l.strip() for l in lines if "FAIL" in l.upper() and len(l) > 10]
        self._failures = fail_lines[:5]

    @property
    def test_summary(self) -> str:
        if self._total_count == 0:
            return ""
        if self._fail_count == 0:
            return f"All {self._pass_count} passed"
        fails = "; ".join(self._failures[:3])
        extra = f" ... +{len(self._failures)-3}" if len(self._failures) > 3 else ""
        summary = f"Tests: {self._pass_count}/{self._total_count} passed, {self._fail_count} failed"
        if fails:
            summary += f" [{fails}{extra}]"
        return summary
