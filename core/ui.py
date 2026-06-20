"""Terminal UI - Interactive prompt, status display, diff viewer, progress spinner."""

import os
import sys
import time
import threading
from pathlib import Path
from typing import Optional, Callable

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.table import Table
from rich.rule import Rule
from rich.text import Text
from rich.layout import Layout
from rich.live import Live
from rich import box

console = Console()


# ═══════════════════════════════════════════
#  BANNER
# ═══════════════════════════════════════════

BANNER = """
╔══════════════════════════════════════════╗
║     🐋 OrcaCode — Terminal AI Agent     ║
║     Read. Think. Edit. Repeat.           ║
╚══════════════════════════════════════════╝
"""

TOOL_CALL_ICONS = {
    "write_file": "📝",
    "patch_file": "✏️",
    "run_command": "💻",
}


def print_banner():
    """Print the OrcaCode banner."""
    console.print(BANNER, style="cyan")


# ═══════════════════════════════════════════
#  STATUS BAR
# ═══════════════════════════════════════════

class StatusBar:
    """A thin status bar showing current iteration/state with elapsed time."""

    def __init__(self):
        self.message = ""
        self.spinner_chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        self.spinner_idx = 0
        self._running = False
        self._thread = None
        self._start_time = 0.0

    def start(self, message: str = ""):
        """Start showing a spinner with message."""
        self.message = message
        self._start_time = time.perf_counter()
        self._running = True
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def _format_elapsed(self, seconds: float) -> str:
        if seconds < 1:
            return f"{int(seconds * 1000)}ms"
        elif seconds < 60:
            return f"{seconds:.1f}s"
        else:
            mins = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{mins}m{secs}s"

    def _spin(self):
        """Spinner loop with elapsed time."""
        while self._running:
            char = self.spinner_chars[self.spinner_idx % len(self.spinner_chars)]
            self.spinner_idx += 1
            elapsed = self._format_elapsed(time.perf_counter() - self._start_time)
            try:
                sys.stdout.write(f"\r{char} {self.message} ({elapsed})    ")
                sys.stdout.flush()
            except UnicodeEncodeError:
                sys.stdout.write(f"\r* {self.message} ({elapsed})    ")
                sys.stdout.flush()
            time.sleep(0.1)
        # Clear the spinner line
        try:
            sys.stdout.write("\r" + " " * (len(self.message) + 20) + "\r")
            sys.stdout.flush()
        except UnicodeEncodeError:
            pass

    def stop(self, message: str = ""):
        """Stop spinner and optionally show completion with duration."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=0.5)
        if message:
            elapsed = self._format_elapsed(time.perf_counter() - self._start_time)
            console.print(f"[green]✓[/green] {message} [dim]({elapsed})[/dim]")

    def update(self, message: str):
        """Update the spinner message."""
        self.message = message


# ═══════════════════════════════════════════
#  DIFF VIEWER
# ═══════════════════════════════════════════

def show_diff_summary(file_path: str, old_content: str, new_content: str) -> str:
    """Show a compact diff summary, returns the diff text."""
    from utils.diff import format_diff_simple
    diff_text = format_diff_simple(old_content, new_content, file_path)
    # Colorize with +/- diff colors
    colored_lines = []
    for line in diff_text.splitlines():
        if line.startswith("+ "):
            colored_lines.append(f"[green]{line}[/green]")
        elif line.startswith("- "):
            colored_lines.append(f"[red]{line}[/red]")
        else:
            colored_lines.append(line)
    colored = "\n".join(colored_lines)
    return colored


def show_tool_call(tc: dict, index: int = 0, total: int = 0):
    """Display a tool call in a nice panel."""
    icons = TOOL_CALL_ICONS
    kind = tc["type"]
    icon = icons.get(kind, "🔧")

    if index > 0:
        console.print()

    if kind == "write_file":
        path = tc.get("path", "?")
        console.print(Panel(
            f"[bold #00FFFF]{icon} WRITE FILE[/bold #00FFFF]\n[dim #00AAAA]{path}[/dim #00AAAA]",
            border_style="#00FFFF",
            padding=(0, 1),
        ))

    elif kind == "patch_file":
        path = tc.get("path", "?")
        console.print(Panel(
            f"[bold #00FFFF]{icon} PATCH FILE[/bold #00FFFF]\n[dim #00AAAA]{path}[/dim #00AAAA]",
            border_style="#00FFFF",
            padding=(0, 1),
        ))

    elif kind == "run_command":
        cmd = tc.get("command", "")
        console.print(Panel(
            f"[bold #00FFFF]{icon} RUN COMMAND[/bold #00FFFF]\n[dim #00AAAA]$ {cmd}[/dim #00AAAA]",
            border_style="#00FFFF",
            padding=(0, 1),
        ))


def show_result(success: bool, msg: str):
    """Show a tool execution result."""
    if success:
        # Truncate long success messages
        if len(msg) > console.width - 20:
            msg = msg[:console.width - 23] + "..."
        console.print(f"  [green]✓[/green] {msg}")
    else:
        console.print(f"  [red]✗[/red] {msg}")


# ═══════════════════════════════════════════
#  ITERATION HEADER
# ═══════════════════════════════════════════

_iter_start_time = 0.0


def show_iteration(iteration: int, max_iterations: int):
    """Show iteration header with a rule and elapsed time."""
    global _iter_start_time
    now = time.perf_counter()
    if iteration > 1 and _iter_start_time:
        elapsed = now - _iter_start_time
        if elapsed < 60:
            detail = f" ({elapsed:.1f}s)"
        else:
            mins = int(elapsed // 60)
            secs = int(elapsed % 60)
            detail = f" ({mins}m{secs}s)"
    else:
        detail = ""
    _iter_start_time = now
    label = f"Iteration {iteration}/{max_iterations}{detail}"
    console.print(Rule(f"[bold #00FFFF]{label}[/bold #00FFFF]", style="#00AAAA"))


# ═══════════════════════════════════════════
#  AI RESPONSE DISPLAY
# ═══════════════════════════════════════════

def show_ai_response(text: str):
    """Display AI's text response in a cyan panel."""
    if not text.strip():
        return
    try:
        md = Markdown(text)
        console.print(Panel(md, border_style="#00FFFF"))
    except Exception:
        console.print(Panel(text, border_style="#00FFFF"))


# ═══════════════════════════════════════════
#  ERROR / WARNING DISPLAY
# ═══════════════════════════════════════════

def show_error(msg: str):
    """Show an error message."""
    console.print(f"[red][ERR] {msg}[/red]")


def show_warning(msg: str):
    """Show a warning message."""
    console.print(f"[yellow][WARN] {msg}[/yellow]")


def show_info(msg: str):
    """Show an info message."""
    console.print(f"[dim]ℹ {msg}[/dim]")


def show_success(msg: str):
    """Show a success message."""
    console.print(f"[green][OK] {msg}[/green]")


# ═══════════════════════════════════════════
#  CONFIG SUMMARY DISPLAY
# ═══════════════════════════════════════════

def show_config(cfg):
    """Show configuration summary."""
    table = Table.grid(padding=(0, 2))
    table.add_column(style="#00AAAA")
    table.add_column(style="#00FFFF")
    table.add_row("Provider", cfg.model.provider)
    table.add_row("Model", cfg.model.model)
    table.add_row("API Key", f"{cfg.model.api_key[:8]}...{cfg.model.api_key[-4:]}" if cfg.model.api_key else "[red]NOT SET[/red]")
    console.print(Panel(table, title="Configuration", border_style="#00FFFF"))


# ═══════════════════════════════════════════
#  INTERACTIVE PROMPT
# ═══════════════════════════════════════════

def get_interactive_input(prompt: str = "> ") -> Optional[str]:
    """
    Get user input in interactive mode.
    Uses prompt_toolkit if available, falls back to raw input.
    """
    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.history import InMemoryHistory
        from prompt_toolkit.styles import Style

        style = Style.from_dict({
            "prompt": "#00FFFF bold",
        })

        session = PromptSession(
            history=InMemoryHistory(),
            style=style,
        )
        return session.prompt(prompt)
    except ImportError:
        pass
    except Exception as e:
        logger = logging.getLogger("orca.ui")
        logger.debug(f"PromptSession failed: {e}")

    try:
        inp = input(prompt)
        return inp.strip()
    except (EOFError, KeyboardInterrupt):
        return None


def confirm_action(question: str, default: str = "y") -> bool:
    """
    Ask user for confirmation with rich formatting.
    Returns True if confirmed.
    """
    choices = "(Y/n)" if default == "y" else "(y/N)"
    console.print(f"\n[yellow]❓ {question} {choices}[/yellow]")
    try:
        inp = input().strip().lower()
        if not inp:
            inp = default
        return inp.startswith("y")
    except (EOFError, KeyboardInterrupt):
        return False


# ═══════════════════════════════════════════
#  FILE LIST DISPLAY
# ═══════════════════════════════════════════

def show_file_list(editable_files: list[str], read_only_files: list[str] = None):
    """Show list of editable and read-only files."""
    if not editable_files and not read_only_files:
        return

    console.print()
    if editable_files:
        text = Text("📄 Editable: ")
        text += Text(", ".join(editable_files), style="#00FFFF")
        console.print(text)
    if read_only_files:
        text = Text("Read-only: ")
        text += Text(", ".join(read_only_files), style="#00AAAA")
        console.print(text)
    console.print()


# ═══════════════════════════════════════════
#  MAIN CHAT LOOP INTERFACE
# ═══════════════════════════════════════════

def chat_prompt(files: list[str] = None, edit_format: str = None) -> Optional[str]:
    """
    Show the chat input prompt with contextual info.
    Returns the user input string.
    """
    if files:
        show_file_list(files)

    prefix = ""
    if edit_format:
        prefix = f"[{edit_format}] "
    prompt_str = f"{prefix}> "

    return get_interactive_input(prompt_str)