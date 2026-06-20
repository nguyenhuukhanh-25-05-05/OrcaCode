#!/usr/bin/env python3
"""
OrcaCode — Terminal AI Agent CLI
================================
Công cụ CLI cho phép AI đọc, sửa file và chạy lệnh terminal.

Cách dùng:
    orca run "yêu cầu"           Chạy AI với yêu cầu
    orca chat                    Chế độ interactive
    orca setup                   Thiết lập API key
    orca model                   Xem/thay đổi model
    orca diff                    Xem git diff
    orca undo                    Hoàn tác git commit
    orca commit "msg"            Git commit
    orca ls                      Liệt kê file
    orca version                 Xem version
"""
import os
import sys

# Support vendored dependencies as fallback (system packages take priority)
vendor_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor")
if os.path.exists(vendor_dir):
    sys.path.append(vendor_dir)

import argparse
from pathlib import Path

# Force UTF-8 output encoding on Windows to support emojis and box-drawing chars
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
        sys.stdin.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

VERSION = "0.2.0"

BANNER = """
╔══════════════════════════════════════════╗
║     🐋 OrcaCode — Terminal AI Agent     ║
║     Read. Think. Edit. Repeat.          ║
╚══════════════════════════════════════════╝
"""


def show_banner():
    console.print(BANNER, style="cyan")



def _auto_init_codegraph(project_root: str) -> None:
    try:
        from core.services.codegraph_service import CodeGraphService
        cg = CodeGraphService(project_root)
        if cg.available and not cg.is_project_initialized():
            console.print("[cyan]🐋 Đang khởi tạo CodeGraph (code intelligence)...[/cyan]")
            if cg.ensure_initialized(force_index=True):
                status = cg.get_status()
                console.print(f"[green]✅ CodeGraph đã sẵn sàng — {status.total_files} files, {status.total_nodes} nodes, {status.total_edges} edges[/green]")
            else:
                console.print("[yellow]⚠️ CodeGraph khởi tạo thất bại, sẽ dùng built-in thay thế.[/yellow]")
    except Exception:
        pass

def check_project_initialization(project_root: str) -> bool:
    import shutil
    
    install_dir = Path(__file__).parent.absolute()
    source_orca = install_dir / ".orca"
    target_orca = Path(project_root) / ".orca"
    
    # If .orca folder already exists in the target project, it's initialized.
    if target_orca.exists() and target_orca.is_dir():
        return True
        
    # If the user is running the tool directly inside the installation directory, it's initialized.
    if Path(project_root).resolve() == install_dir.resolve():
        return True

    # Auto-init .orca silently
    try:
        target_orca.mkdir(parents=True, exist_ok=True)
        src_inst = source_orca / "instructions.md"
        if src_inst.exists():
            shutil.copy2(src_inst, target_orca / "instructions.md")
        _auto_init_codegraph(project_root)
        return True
    except Exception as e:
        console.print(f"[red]❌ Could not init .orca: {e}[/red]")
        return False


def cmd_setup(args):
    """Thiết lập API key và provider."""
    from config.settings import get_api_base_url
    show_banner()
    console.print(Panel("[bold]Setup Wizard[/bold]", border_style="cyan"))

    console.print("\n[bold cyan]Step 1: API Key[/bold cyan]")
    api_key = input("  Enter your API key (or press Enter to skip): ").strip()
    if not api_key:
        console.print("[yellow]⚠️ Skip entering API key.[/yellow]")
        return

    console.print("\n[bold cyan]Step 2: Provider[/bold cyan]")
    console.print("  1) DeepSeek (default)")
    console.print("  2) OpenAI (GPT-4o)")
    console.print("  3) Anthropic (Claude)")
    console.print("  4) Gemini")
    console.print("  5) OpenRouter")
    choice = input("  Select [1/2/3/4/5]: ").strip()
    providers = {
        "1": "deepseek",
        "2": "openai",
        "3": "anthropic",
        "4": "gemini",
        "5": "openrouter",
    }
    provider = providers.get(choice, "deepseek")

    # Save globally to ~/.orcacode/config.toml
    global_dir = Path.home() / ".orcacode"
    global_dir.mkdir(parents=True, exist_ok=True)
    global_path = global_dir / "config.toml"
    try:
        with open(global_path, "w", encoding="utf-8") as f:
            f.write("[model]\n")
            f.write(f'provider = "{provider}"\n')
            f.write(f'model = "deepseek-chat"\n')
            f.write(f'api_key = "{api_key}"\n')
            f.write(f'base_url = "{get_api_base_url(provider)}"\n')
        try:
            os.chmod(global_path, 0o600)
        except (OSError, NotImplementedError):
            pass
        console.print(f"[green]✅ Global config saved to {global_path}[/green]")
    except Exception as e:
        console.print(f"[red]❌ Could not save global config: {e}[/red]")

    # Ask whether to save project .env
    save_local = input("  Save to project .env file as well? (y/N): ").strip().lower()
    if save_local == "y":
        try:
            with open(".env", "w", encoding="utf-8") as f:
                f.write(f"ORCA_API_KEY={api_key}\n")
                f.write(f"ORCA_PROVIDER={provider}\n")
                f.write("ORCA_MODEL=deepseek-chat\n")
            console.print("[green]✅ Local .env saved in current directory[/green]")
        except Exception as e:
            console.print(f"[red]❌ Could not save local .env: {e}[/red]")
    else:
        console.print("[dim]⏭ Skipped project .env[/dim]")


def cmd_run(args):
    """Chạy AI với 1 yêu cầu."""
    from config.settings import load_config
    from core.agent import AgentController

    cfg = load_config()
    if not check_project_initialization(cfg.project_root):
        return

    if args.model:
        cfg.model.model = args.model
    if args.provider:
        cfg.model.provider = args.provider

    show_banner()
    agent = AgentController(cfg)
    agent.run(args.prompt)


def cmd_chat(args):
    """Chế độ interactive."""
    from config.settings import load_config
    from core.agent import AgentController
    from core.ui import get_interactive_input, show_config, show_error
    from core.commands import handle_command, is_command

    cfg = load_config()
    if not check_project_initialization(cfg.project_root):
        return

    if args.model:
        cfg.model.model = args.model
    if args.provider:
        cfg.model.provider = args.provider

    show_banner()
    show_config(cfg)
    console.print("[dim]Type /help to see commands, or just ask me anything.[/dim]\n")

    agent = AgentController(cfg)

    while True:
        try:
            user_input = get_interactive_input("orca> ")
            if user_input is None or not user_input.strip():
                break
            if is_command(user_input):
                result = handle_command(user_input, {"project_root": cfg.project_root})
                if result == "exit":
                    break
                continue
            agent.run(user_input)
            console.print()
        except KeyboardInterrupt:
            console.print("\n[dim]Ctrl+C — type /exit to quit[/dim]")
        except Exception as e:
            show_error(f"Error: {e}")


def cmd_model(args):
    """Xem/thay đổi model."""
    from config.settings import load_config, get_api_base_url

    cfg = load_config()
    if args.set_provider:
        cfg.model.provider = args.set_provider
        console.print(f"[green]✅ Provider: {cfg.model.provider}[/green]")
    if args.set_model:
        cfg.model.model = args.set_model
        console.print(f"[green]✅ Model: {cfg.model.model}[/green]")

    if not args.set_provider and not args.set_model:
        table = Table(title="🤖 Current Model")
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="white")
        table.add_row("Provider", cfg.model.provider)
        table.add_row("Model", cfg.model.model)
        api_display = "NOT SET"
        if cfg.model.api_key and len(cfg.model.api_key) >= 12:
            api_display = f"{cfg.model.api_key[:8]}...{cfg.model.api_key[-4:]}"
        elif cfg.model.api_key:
            api_display = f"{cfg.model.api_key[:4]}..."
        table.add_row("API Key", api_display)
        table.add_row("Base URL", get_api_base_url(cfg.model.provider))
        console.print(table)


def cmd_diff(args):
    """Xem git diff."""
    from core.git_repo import GitRepo
    repo = GitRepo()
    if not repo.available:
        console.print("[yellow]Not a git repository[/yellow]")
        return
    diff = repo.get_diff()
    if diff:
        console.print(diff)
    else:
        console.print("[dim]No changes to show[/dim]")


def cmd_undo(args):
    """Hoàn tác git commit cuối."""
    from core.git_repo import GitRepo
    repo = GitRepo()
    if not repo.available:
        console.print("[yellow]Not a git repository[/yellow]")
        return
    repo.undo()


def cmd_commit(args):
    """Git commit."""
    from core.git_repo import GitRepo
    repo = GitRepo()
    if not repo.available:
        console.print("[yellow]Not a git repository[/yellow]")
        return
    repo.commit(args.message)


def cmd_ls(args):
    """Liệt kê files."""
    cwd = args.path or "."
    count = 0
    try:
        for entry in Path(cwd).iterdir():
            if entry.is_file() and not entry.name.startswith("."):
                console.print(f"  {entry.relative_to(cwd)}")
                count += 1
                if count >= 30:
                    console.print(f"  ... (showing first 30)")
                    break
            elif entry.is_dir() and not entry.name.startswith("."):
                console.print(f"  [dim]{entry.relative_to(cwd)}/[/]")
    except PermissionError:
        pass
    if count == 0:
        console.print("[dim]No files found[/dim]")


def cmd_tui(args):
    """Launch TUI (Ocean Blue Theme)."""
    from config.settings import load_config
    from core.tui import run_tui
    cfg = load_config()
    if not check_project_initialization(cfg.project_root):
        return

    if args.model:
        cfg.model.model = args.model
    if args.provider:
        cfg.model.provider = args.provider
    run_tui(config=cfg)


def cmd_codegraph(args):
    """CodeGraph integration commands."""
    from core.services.codegraph_service import CodeGraphService

    cg = CodeGraphService(args.path or ".")

    if not cg.available:
        console.print("[yellow]CodeGraph CLI không khả dụng.[/yellow]")
        console.print("[dim]Cài đặt: npm install -g @colbymchenry/codegraph[/dim]")
        console.print("[dim]Hoặc build từ thư mục codegraph-main: cd codegraph-main && npm install && npm run build[/dim]")
        return

    if args.subcommand == "init":
        console.print("[cyan]Đang khởi tạo CodeGraph...[/cyan]")
        if cg.ensure_initialized(force_index=True):
            console.print("[green]Đã khởi tạo và index xong![/green]")
        else:
            console.print("[red]Khởi tạo thất bại.[/red]")

    elif args.subcommand == "status":
        status = cg.get_status()
        from rich.table import Table
        table = Table(title="CodeGraph Status")
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="white")
        table.add_row("Initialized", "Yes" if status.initialized else "No")
        table.add_row("Indexed", "Yes" if status.indexed else "No")
        table.add_row("Files", str(status.total_files))
        table.add_row("Nodes", str(status.total_nodes))
        table.add_row("Edges", str(status.total_edges))
        table.add_row("Languages", ", ".join(status.languages) if status.languages else "N/A")
        table.add_row("DB Size", status.db_size or "N/A")
        table.add_row("Version", status.version or "N/A")
        console.print(table)

    elif args.subcommand == "search":
        results = cg.search(args.query, limit=args.limit or 20)
        if results:
            from rich.table import Table
            table = Table(title=f"Symbols: {args.query}")
            table.add_column("Name", style="cyan")
            table.add_column("Kind", style="green")
            table.add_column("File", style="white")
            for r in results:
                table.add_row(r.name, r.kind, f"{r.file_path}:{r.line}")
            console.print(table)
        else:
            console.print("[dim]Không tìm thấy.[/dim]")

    elif args.subcommand == "explore":
        result = cg.explore(args.query)
        if result.symbols:
            for sym in result.symbols[:15]:
                loc = f"{sym.file_path}:{sym.line}" if sym.file_path else "?"
                console.print(f"[cyan]{sym.name}[/cyan] [{sym.kind}] @ {loc}")
        else:
            console.print("[dim]Không tìm thấy.[/dim]")

    elif args.subcommand == "callers":
        results = cg.get_callers(args.query)
        for r in results:
            console.print(f"[cyan]{r.name}[/cyan] [{r.kind}] @ {r.file_path}:{r.line}")

    elif args.subcommand == "callees":
        results = cg.get_callees(args.query)
        for r in results:
            console.print(f"[cyan]{r.name}[/cyan] @ {r.file_path}:{r.line}")

    elif args.subcommand == "impact":
        results = cg.get_impact(args.query, depth=args.depth or 3)
        for r in results:
            console.print(f"[yellow]{r.name}[/yellow] [{r.kind}] @ {r.file_path}:{r.line}")

    elif args.subcommand == "affected":
        files = args.files or []
        results = cg.get_affected_tests(files)
        for f in results:
            console.print(f"[cyan]{f}[/cyan]")


def cmd_version(args):
    """Xem version."""
    console.print(f"[cyan]OrcaCode v{VERSION} (Terminal AI Agent)[/cyan]")


def main():
    from core.services.security_service import verify_workspace_trust
    verify_workspace_trust()

    parser = argparse.ArgumentParser(
        prog="orca",
        description="OrcaCode - Terminal AI Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=True,
        epilog="""
Examples:
  orca run "Create hello.txt"       Run AI with a request
  orca chat                         Interactive mode
  orca setup                        Setup API key & provider
  orca model                        View model info
  orca model -p openai -m gpt-4o    Change model
  orca diff                         Git diff
  orca undo                         Undo last commit
  orca commit "update readme"       Git commit
  orca ls                           List files
  orca version                      Show version
        """,
    )
    parser.add_argument("-v", "--version", action="version", version=f"OrcaCode v{VERSION}")
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # orca run
    p_run = subparsers.add_parser("run", help="Chạy AI với yêu cầu")
    p_run.add_argument("prompt", help="Yêu cầu cho AI")
    p_run.add_argument("-m", "--model", help="Override AI model")
    p_run.add_argument("-p", "--provider", help="Override provider")
    p_run.set_defaults(func=cmd_run)

    # orca chat
    p_chat = subparsers.add_parser("chat", help="Interactive mode")
    p_chat.add_argument("-m", "--model", help="Override AI model")
    p_chat.add_argument("-p", "--provider", help="Override provider")
    p_chat.set_defaults(func=cmd_chat)

    # orca setup
    p_setup = subparsers.add_parser("setup", help="Setup API key & provider")
    p_setup.set_defaults(func=cmd_setup)

    # orca model
    p_model = subparsers.add_parser("model", help="View/change model")
    p_model.add_argument("-m", "--set-model", help="Set model")
    p_model.add_argument("-p", "--set-provider", help="Set provider")
    p_model.set_defaults(func=cmd_model)

    # orca diff
    p_diff = subparsers.add_parser("diff", help="Git diff")
    p_diff.set_defaults(func=cmd_diff)

    # orca undo
    p_undo = subparsers.add_parser("undo", help="Undo last git commit")
    p_undo.set_defaults(func=cmd_undo)

    # orca commit
    p_commit = subparsers.add_parser("commit", help="Git commit")
    p_commit.add_argument("message", nargs="?", default="OrcaCode update", help="Commit message")
    p_commit.set_defaults(func=cmd_commit)

    # orca ls
    p_ls = subparsers.add_parser("ls", help="List files in project")
    p_ls.add_argument("path", nargs="?", default=".", help="Path to list")
    p_ls.set_defaults(func=cmd_ls)

    # orca tui
    p_tui = subparsers.add_parser("tui", help="Launch TUI (Ocean Blue Theme)")
    p_tui.add_argument("-m", "--model", help="Override AI model")
    p_tui.add_argument("-p", "--provider", help="Override provider")
    p_tui.set_defaults(func=cmd_tui)

    # orca codegraph
    p_cg = subparsers.add_parser("codegraph", help="CodeGraph intelligence (init, search, explore, callers, callees, impact)")
    p_cg.add_argument("subcommand", nargs="?", default="status",
                       choices=["init", "status", "search", "explore", "callers", "callees", "impact", "affected"],
                       help="CodeGraph subcommand")
    p_cg.add_argument("query", nargs="?", default="",
                       help="Search query or symbol name")
    p_cg.add_argument("--path", "-d", default=".", help="Project path")
    p_cg.add_argument("--limit", "-n", type=int, default=None, help="Result limit")
    p_cg.add_argument("--depth", type=int, default=None, help="Impact depth")
    p_cg.add_argument("--files", nargs="*", default=None, help="Files for affected analysis")
    p_cg.set_defaults(func=cmd_codegraph)

    # orca version
    p_version = subparsers.add_parser("version", help="Show version")
    p_version.set_defaults(func=cmd_version)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()