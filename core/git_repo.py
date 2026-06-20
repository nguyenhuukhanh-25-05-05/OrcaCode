"""Git Repository integration - commit, undo, diff, status tracking."""

import os
import subprocess
from pathlib import Path
from typing import Optional, Union

from rich.console import Console

console = Console()


class GitError(Exception):
    """Raised on git operations failure."""
    pass


class GitRepo:
    """Thin wrapper around git CLI for basic operations."""

    def __init__(self, project_root: str = None):
        self.root = Path(project_root or os.getcwd()).resolve()
        self._git_dir = self._find_git_dir()
        self.aider_commit_hashes = set()  # Track commits made by orca

    def _find_git_dir(self) -> Optional[Path]:
        """Find the .git directory by walking up."""
        path = self.root
        while path.parent != path:
            git_dir = path / ".git"
            if git_dir.exists():
                return git_dir
            path = path.parent
        return None

    def _run_git(self, *args: str, check: bool = True) -> tuple[int, str, str]:
        """Run a git command. Returns (returncode, stdout, stderr)."""
        if not self._git_dir:
            raise GitError("Not a git repository")
        try:
            proc = subprocess.run(
                ["git"] + list(args),
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                cwd=self.root,
                timeout=30,
            )
            if check and proc.returncode != 0:
                raise GitError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
            return proc.returncode, proc.stdout, proc.stderr
        except FileNotFoundError:
            raise GitError("git not found. Install git: https://git-scm.com/")
        except subprocess.TimeoutExpired:
            raise GitError("git command timed out")

    @property
    def available(self) -> bool:
        """Check if we're in a git repo."""
        try:
            return self._git_dir is not None
        except GitError:
            return False

    def is_dirty(self) -> bool:
        """Check if working directory has uncommitted changes."""
        _, stdout, _ = self._run_git("status", "--porcelain", check=False)
        return bool(stdout.strip())

    def get_head_sha(self, short: bool = True) -> Optional[str]:
        """Get current commit hash."""
        try:
            _, stdout, _ = self._run_git("rev-parse", "--short" if short else "", "HEAD")
            return stdout.strip()
        except GitError:
            return None

    def get_head_commit_message(self) -> str:
        """Get last commit message."""
        try:
            _, stdout, _ = self._run_git("log", "-1", "--pretty=%s")
            return stdout.strip()
        except GitError:
            return ""

    def get_diff(self, since: str = "HEAD") -> str:
        """Get diff of uncommitted changes or since a ref."""
        try:
            if self.is_dirty():
                _, stdout, _ = self._run_git("diff", "--no-color", since)
            else:
                # Show diff of last commit vs previous
                _, stdout, _ = self._run_git("diff", "--no-color", f"{since}~1", since)
            return stdout
        except GitError:
            return ""

    def add(self, *paths: str) -> None:
        """Stage file(s) for commit."""
        if paths:
            self._run_git("add", "--", *paths)
        else:
            self._run_git("add", "-A")

    def commit(self, message: str, add_all: bool = True) -> Optional[str]:
        """
        Commit changes with a message.
        Returns commit hash or None on failure.
        """
        try:
            if add_all and self.is_dirty():
                self._run_git("add", "-A")

            # Check if there's anything to commit
            if not self.is_dirty():
                console.print("[yellow]⏭ Nothing to commit.[/yellow]")
                return None

            self._run_git("commit", "-m", message)
            sha = self.get_head_sha()
            if sha:
                self.aider_commit_hashes.add(sha)
                console.print(f"[green][OK] Commit {sha}: {message}[/green]")
            return sha
        except GitError as e:
            console.print(f"[red][ERR] Commit failed: {e}[/red]")
            return None

    def undo(self) -> bool:
        """Undo last aider commit. Returns True on success."""
        sha = self.get_head_sha()
        if not sha:
            console.print("[yellow]No commits to undo.[/yellow]")
            return False

        if sha not in self.aider_commit_hashes:
            console.print("[yellow]Last commit was not made by OrcaCode in this session.[/yellow]")
            return False

        try:
            self._run_git("reset", "--soft", "HEAD~1")
            console.print(f"[green]↩ Undid commit {sha}[/green]")
            self.aider_commit_hashes.discard(sha)
            return True
        except GitError as e:
            console.print(f"[red][ERR] Undo failed: {e}[/red]")
            return False

    def get_tracked_files(self) -> set[str]:
        """Get list of tracked files (relative to repo root)."""
        try:
            _, stdout, _ = self._run_git("ls-files")
            return set(stdout.strip().splitlines()) if stdout.strip() else set()
        except GitError:
            return set()

    def get_changed_files(self) -> list[str]:
        """Get list of files changed since last commit."""
        try:
            _, stdout, _ = self._run_git("diff", "--name-only", "HEAD")
            return [f for f in stdout.strip().splitlines() if f.strip()]
        except GitError:
            return []

    def get_staged_files(self) -> list[str]:
        """Get list of staged files."""
        try:
            _, stdout, _ = self._run_git("diff", "--cached", "--name-only")
            return [f for f in stdout.strip().splitlines() if f.strip()]
        except GitError:
            return []

    def file_in_repo(self, filepath: Union[str, Path]) -> bool:
        """Check if a file is tracked in git."""
        rel = self.get_rel_path(filepath)
        if not rel:
            return False
        try:
            _, stdout, _ = self._run_git("ls-files", rel)
            return bool(stdout.strip())
        except GitError:
            return False

    def get_rel_path(self, filepath: Union[str, Path]) -> str:
        """Convert absolute path to repo-relative path."""
        try:
            return str(Path(filepath).resolve().relative_to(self.root))
        except ValueError:
            return str(filepath)

    def init(self) -> bool:
        """Initialize a new git repo if one doesn't exist."""
        if self.available:
            return True
        try:
            self._run_git("init")
            self._git_dir = self.root / ".git"
            console.print(f"[green][OK] Git repo initialized at {self.root}[/green]")
            return True
        except GitError as e:
            console.print(f"[red][ERR] Failed to init git repo: {e}[/red]")
            return False