"""Security Service - approval workflow and command filtering."""
import subprocess
import os
import sys
import re
import logging
import inspect
import threading
import asyncio
from pathlib import Path
from typing import Callable, Awaitable
from dataclasses import dataclass
from rich.console import Console
from rich.panel import Panel

@dataclass
class CommandRequest:
    command: str
    risk_level: str
    requires_approval: bool

console = Console()
logger = logging.getLogger("orca.security")


class SecurityService:
    REDIRECT_PATTERN = re.compile(r'(?:^|[|;&])\s*(?:[<>]{1,2}|>>?|nul\s*>)')
    BLOCKED_PATTERNS = [
        # ── POSIX destructive ──
        re.compile(r'\brm\b.*[-][-]?[aibdfRrv]*f', re.IGNORECASE),
        re.compile(r'\brm\b.*/\s*$', re.IGNORECASE),
        re.compile(r'\brm\b.*--(?:recursive|force)', re.IGNORECASE),
        re.compile(r'[>|]\s*/dev/\w+'),
        re.compile(r'\bdd\b'),
        re.compile(r'>\s*[\\/]?(?:dev|proc|sys|etc|boot)', re.IGNORECASE),

        # ── Windows destructive ──
        re.compile(r'\bdel\s+/[a-z]*[fsq]', re.IGNORECASE),
        re.compile(r'\berase\s+/[a-z]*[fsq]', re.IGNORECASE),
        re.compile(r'\brmdir\s+/[a-z]*[sq]', re.IGNORECASE),
        re.compile(r'\brd\s+/[a-z]*[sq]', re.IGNORECASE),
        re.compile(r'\bformat\b', re.IGNORECASE),
        re.compile(r'\bshutdown\b', re.IGNORECASE),
        re.compile(r'\breboot\b', re.IGNORECASE),
        re.compile(r'\bdiskpart\b', re.IGNORECASE),
        re.compile(r'\bbcdedit\b', re.IGNORECASE),

        # ── Registry ──
        re.compile(r'\breg\s+(?:delete|add|import|restore)', re.IGNORECASE),

        # ── Ownership / permissions ──
        re.compile(r'\btakeown\b', re.IGNORECASE),
        re.compile(r'\bicacls\s+.*\b(?:grant|deny|reset|revoke)', re.IGNORECASE),
        re.compile(r'\bcacls\s+', re.IGNORECASE),

        # ── Volume / disk ──
        re.compile(r'\bvssadmin\s+delete\s+shadows', re.IGNORECASE),
        re.compile(r'\bcipher\s+/w', re.IGNORECASE),
        re.compile(r'\bfsutil\s+', re.IGNORECASE),

        # ── User / service management ──
        re.compile(r'\bnet\s+(?:user|localgroup|accounts)\s', re.IGNORECASE),
        re.compile(r'\bsc\s+delete\b', re.IGNORECASE),

        # ── Task scheduler ──
        re.compile(r'\bschtasks\s+/delete', re.IGNORECASE),

        # ── PowerShell destructive ──
        re.compile(r'\bpower[Ss]hell\b.*\bRemove-Item\b', re.IGNORECASE),
        re.compile(r'\bpower[Ss]hell\b.*\bClear-Item\b', re.IGNORECASE),
        re.compile(r'\bpower[Ss]hell\b.*\bRemove-ItemProperty\b', re.IGNORECASE),
    ]
    READONLY_PREFIXES = [
        "rg ", "ls ", "head ", "tail ", "pwd ", "which ", "where ",
        "git status", "git diff", "git log", "git branch", "dir ",
    ]
    READONLY_DANGEROUS = ["echo ", "cat ", "type "]
    BUILD_PREFIXES = [
        "npm ", "yarn ", "pnpm ", "pip ", "cargo ", "go build", "make",
        "dotnet build", "mvn ", "python ", "node ",
    ]

    def __init__(self, approval_callback: Callable[[str, str], Awaitable[bool]] | None = None):
        self.session_approved_build = False
        self._auto_approve = False
        self._approval_callback = approval_callback
        self._lock = threading.Lock()

    def is_command_blocked(self, command: str) -> tuple[bool, str]:
        for p in self.BLOCKED_PATTERNS:
            if p.search(command):
                return True, f"blocked pattern: '{p.pattern[:50]}'"
        return False, ""

    def _has_shell_redirect(self, command: str) -> bool:
        return bool(self.REDIRECT_PATTERN.search(command))

    def is_readonly(self, command: str) -> bool:
        cmd = command.lower().strip()
        for p in self.READONLY_PREFIXES:
            if cmd.startswith(p):
                return not self._has_shell_redirect(command)
        for p in self.READONLY_DANGEROUS:
            if cmd.startswith(p):
                return not self._has_shell_redirect(command)
        return False

    def is_build(self, command: str) -> bool:
        cmd = command.lower().strip()
        return any(cmd.startswith(p) for p in self.BUILD_PREFIXES)

    def classify_command(self, command: str) -> CommandRequest:
        blocked, _ = self.is_command_blocked(command)
        if blocked:
            return CommandRequest(command, "high", True)
        if self.is_readonly(command):
            return CommandRequest(command, "low", False)
        if self.is_build(command):
            return CommandRequest(command, "medium", not self.session_approved_build)
        return CommandRequest(command, "medium", True)

    def ask_approval(self, title: str, detail: str) -> bool:
        """Request approval. Thread-safe: works both from main thread and worker threads."""
        if self._auto_approve:
            logger.info(f"Auto-approved: {title}")
            return True

        if self._approval_callback is not None:
            return self._invoke_approval_callback(title, detail)

        return self._cli_approval(title, detail)

    def _invoke_approval_callback(self, title: str, detail: str) -> bool:
        """Invoke the approval callback, supporting both sync and async callbacks."""
        callback = self._approval_callback
        try:
            if inspect.iscoroutinefunction(callback):
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None

                if loop is not None and loop.is_running():
                    future = asyncio.run_coroutine_threadsafe(callback(title, detail), loop)
                    result = future.result(timeout=300)
                else:
                    result = asyncio.run(callback(title, detail))
            else:
                result = callback(title, detail)
        except Exception:
            result = False

        return result

    def _cli_approval(self, title: str, detail: str) -> bool:
        """CLI-mode approval (when not running inside TUI)."""
        console.print()
        console.print(Panel(
            detail[:2000],
            title=f"[bold yellow]{title}[/bold yellow]",
            border_style="yellow",
            subtitle="[Y]es / [N]o"
        ))
        while True:
            try:
                choice = input("  Apply? [Y]es / [N]o: ").strip().lower()
                if choice in ("y", "yes"):
                    return True
                if choice in ("n", "no", ""):
                    return False
            except (EOFError, KeyboardInterrupt):
                return False

    def approve_write_file(self, file_path: str, content: str, old_content: str | None = None) -> bool:
        if self._auto_approve:
            logger.info(f"Auto-approved file write: {file_path}")
            return True
        resolved = self._resolve_safe_path(file_path)
        if resolved is None:
            logger.warning(f"Path traversal denied: {file_path}")
            return False
        if old_content:
            from utils.diff import format_diff_simple
            diff = format_diff_simple(old_content, content, file_path)
            return self.ask_approval(f"PATCH FILE: {file_path}", diff)
        return self.ask_approval(f"CREATE FILE: {file_path}", f"{file_path}\n\n{content[:1000]}")

    def approve_run_command(self, command: str) -> bool:
        blocked, reason = self.is_command_blocked(command)
        if blocked:
            logger.warning(f"Blocked command: {command} ({reason})")
            # Do NOT use console.print() — it writes to stdout and corrupts the TUI display.
            # The TUI will surface the block reason through the callback system.
            return False
        if self.is_readonly(command):
            logger.info(f"Auto-approved readonly: {command[:80]}")
            return True
        with self._lock:
            if self.is_build(command) and self.session_approved_build:
                logger.info(f"Auto-approved build: {command[:80]}")
                return True
            result = self.ask_approval("RUN COMMAND", f"{command}")
            if result and self.is_build(command):
                self.session_approved_build = True
                logger.info(f"Build session approved: {command[:80]}")
            return result

    def run_command(self, command: str, cwd: str | None = None) -> tuple[int, str, str]:
        """Run command with approval check."""
        if not self.approve_run_command(command):
            return -1, "", "Rejected"
        return self.run_command_direct(command, cwd)

    @staticmethod
    def _split_command(command: str) -> list[str]:
        """Split command string into args — OS-aware.
        
        On Windows, uses posix=False to avoid treating \\ as escape
        and to handle drive letters (C:\...) correctly.
        """
        import shlex
        return shlex.split(command, posix=False) if os.name == "nt" else shlex.split(command)

    def run_command_direct(self, command: str, cwd: str | None = None) -> tuple[int, str, str]:
        """Run command directly without approval check.
        
        Includes: 60s timeout, SSRF protection, auto-kill on timeout.
        """
        # SSRF Protection: block localhost IPs in curl/wget/fetch commands
        ssrf_patterns = [
            r'(curl|wget|fetch|httpie|invoke-http|aria2c)\s+.*(127\.0\.0\.1|localhost|169\.254\.169\.254|0\.0\.0\.0|\[::1\])',
            r'(curl|wget|fetch)\s+https?://(127\.|192\.168\.|10\.|172\.1[6-9]\.|172\.2[0-9]\.|172\.3[0-1]\.)',
            r'(curl|wget|fetch)\s+https?://[^/]*metadata\.google\.internal',
            r'(curl|wget|fetch)\s+https?://[^/]*169\.254\.169\.254',
        ]
        for pattern in ssrf_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                logger.warning(f"SSRF blocked: {command[:80]}")
                return -1, "", "SSRF BLOCKED: localhost/internal IP không được phép gọi từ tool"

        try:
            args = self._split_command(command)
            kwargs = dict(
                capture_output=True,
                encoding="utf-8", errors="replace",
                cwd=cwd or os.getcwd(), timeout=60,
            )
            if os.name == "nt":
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            proc = subprocess.run(args, **kwargs)
            return proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "Timed out (60s)"
        except Exception as e:
            return -1, "", str(e)

    def _resolve_safe_path(self, file_path: str, project_root: str = None) -> str | None:
        """Resolve and validate file path, preventing traversal outside project root."""
        from pathlib import Path as PPath
        try:
            resolved = PPath(file_path).resolve()
            # If project_root is given, enforce containment
            if project_root:
                root = PPath(project_root).resolve()
                if not resolved.is_relative_to(root):
                    logger.warning(f"Path traversal blocked: {file_path} resolves to {resolved}, outside {root}")
                    return None
            return str(resolved)
        except (ValueError, OSError):
            return None


def verify_workspace_trust(project_root: str = None) -> bool:
    """Check if the current workspace directory is trusted.
    If not, prompt the user for trust. Saves trusted workspaces to ~/.orca/global_config.json.
    """
    import json

    cwd = Path(project_root or os.getcwd()).resolve()
    cwd_str = str(cwd)

    install_dir = Path(__file__).parent.parent.parent.resolve()
    if cwd == install_dir:
        return True

    global_dir = Path.home() / ".orca"
    global_config_file = global_dir / "global_config.json"
    global_dir.mkdir(parents=True, exist_ok=True)

    trusted_list = []
    if global_config_file.exists():
        try:
            with open(global_config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                trusted_list = data.get("trusted_workspaces", [])
        except Exception:
            trusted_list = []

    if cwd_str in trusted_list:
        return True

    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text

    con = Console()
    con.print()
    panel_content = Text()
    panel_content.append("Trust Workspace\n\n", style="bold #00abf0")
    panel_content.append("Do you trust the contents of this directory?\n", style="bold white")
    panel_content.append(f"You are in {cwd_str}\n\n", style="cyan")
    panel_content.append(
        "Working with untrusted contents comes with a higher risk of prompt injection.\n"
        "Trusting this directory records it in global config.\n\n",
        style="dim white"
    )
    panel_content.append("Press ", style="white")
    panel_content.append("1/Y", style="bold #22c55e")
    panel_content.append(" to trust, ", style="white")
    panel_content.append("2/N", style="bold #f43f5e")
    panel_content.append(" to quit", style="white")

    panel = Panel(panel_content, title="OrcaCode", border_style="#00abf0", expand=False, padding=(1, 3))
    con.print(panel)

    while True:
        try:
            choice = input().strip().lower()
            if choice in ("1", "y", "yes"):
                trusted_list.append(cwd_str)
                with open(global_config_file, "w", encoding="utf-8") as f:
                    json.dump({"trusted_workspaces": trusted_list}, f, ensure_ascii=False, indent=2)
                con.print("[green]Workspace trusted. Continuing...[/green]\n")
                return True
            elif choice in ("2", "n", "no"):
                con.print("[red]Workspace untrusted. Exiting.[/red]")
                sys.exit(0)
            else:
                con.print("[red]Please enter Y or N[/red]")
        except (KeyboardInterrupt, EOFError):
            con.print("\n[red]Aborted. Exiting.[/red]")
            sys.exit(0)