"""Project type detection — auto-configure tool runners per project."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class ProjectType(Enum):
    NODE = "node"
    PYTHON = "python"
    RUST = "rust"
    GO = "go"
    UNKNOWN = "unknown"


@dataclass
class ProjectConfig:
    type: ProjectType
    root: str
    build_command: str = ""
    lint_command: str = ""
    typecheck_command: str = ""
    test_command: str = ""

    def has_build(self) -> bool:
        return bool(self.build_command)

    def has_lint(self) -> bool:
        return bool(self.lint_command)

    def has_typecheck(self) -> bool:
        return bool(self.typecheck_command)

    def has_test(self) -> bool:
        return bool(self.test_command)


class ProjectDetector:
    """Detect project type and configure appropriate tool runners."""

    @staticmethod
    def detect(root: str) -> ProjectConfig:
        root_path = Path(root)

        if (root_path / "package.json").exists():
            return ProjectDetector._detect_node(root_path)

        if (root_path / "pyproject.toml").exists() or (root_path / "setup.py").exists():
            return ProjectDetector._detect_python(root_path)

        if (root_path / "Cargo.toml").exists():
            return ProjectDetector._detect_rust(root_path)

        if (root_path / "go.mod").exists():
            return ProjectDetector._detect_go(root_path)

        return ProjectConfig(type=ProjectType.UNKNOWN, root=root)

    @staticmethod
    def _detect_node(root_path: Path) -> ProjectConfig:
        cfg = ProjectConfig(type=ProjectType.NODE, root=str(root_path))
        has_modules = (root_path / "node_modules").exists()

        cfg.build_command = "npm run build" if has_modules else ""
        cfg.lint_command = "npx eslint . --format stylish" if has_modules else ""
        cfg.typecheck_command = "npx tsc --noEmit" if has_modules and (root_path / "tsconfig.json").exists() else ""
        cfg.test_command = "npm test" if has_modules else ""

        return cfg

    @staticmethod
    def _detect_python(root_path: Path) -> ProjectConfig:
        cfg = ProjectConfig(type=ProjectType.PYTHON, root=str(root_path))
        cfg.build_command = "python -m compileall . -q -x 'vendor|\\.git|__pycache__|node_modules'"

        if (root_path / ".ruff.toml").exists() or (root_path / "ruff.toml").exists():
            cfg.lint_command = "ruff check ."
        else:
            cfg.lint_command = "python -m flake8 ."

        cfg.typecheck_command = "python -m mypy ."
        cfg.test_command = "python -m pytest --tb=short -q"

        return cfg

    @staticmethod
    def _detect_rust(root_path: Path) -> ProjectConfig:
        return ProjectConfig(
            type=ProjectType.RUST,
            root=str(root_path),
            build_command="cargo build",
            lint_command="cargo clippy -- -D warnings",
            typecheck_command="",
            test_command="cargo test",
        )

    @staticmethod
    def _detect_go(root_path: Path) -> ProjectConfig:
        return ProjectConfig(
            type=ProjectType.GO,
            root=str(root_path),
            build_command="go build ./...",
            lint_command="go vet ./...",
            typecheck_command="",
            test_command="go test ./...",
        )
