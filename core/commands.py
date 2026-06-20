"""Interactive CLI commands - /help, /add, /drop, /undo, /diff, /clear, /tokens, /git, /commit, /ls, /exit"""

import os
import re
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table

console = Console()

COMMANDS = {
    "/help":      "Show help (this message)",
    "/suggest":   "Suggest commands based on current context",
    "/ls":        "List files in project",
    "/add":       "Add file to chat context: /add <file>",
    "/drop":      "Remove file from context: /drop <file>",
    "/diff":      "Show diff of changes since last commit",
    "/undo":      "Undo last OrcaCode commit",
    "/commit":    "Commit current changes: /commit [message]",
    "/clear":     "Clear chat history",
    "/tokens":    "Show token usage estimate",
    "/git":       "Run git command: /git status",
    "/model":     "Show current model",
    "/set":       "Set config: /set provider=deepseek",
    "/reset":     "Reset all config to defaults",
    "/version":   "Show OrcaCode version",
    "/memory":    "Show memory stats",
    "/diffs":     "Show recent diffs",
    "/clear-memory": "Clear all memory",
    "/codegraph": "CodeGraph intelligence: /codegraph [search|explore|callers|callees|impact|status|init] <query>",
    "/exit":      "Exit OrcaCode (alias: /quit, /q)",
}


def show_help():
    """Show help table."""
    table = Table(title="OrcaCode Commands", show_header=True)
    table.add_column("Command", style="cyan", width=20)
    table.add_column("Description", style="white")
    for cmd, desc in COMMANDS.items():
        table.add_row(cmd, desc)
    console.print(table)


def handle_command(user_input: str, ctx: dict) -> Optional[str]:
    """
    Handle slash commands in interactive mode.
    Returns: None to continue, 'exit' to quit, or a string to send to AI.
    """
    parts = user_input.strip().split(maxsplit=1)
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    if cmd in ("/exit", "/quit", "/q"):
        console.print("[dim]Bye![/dim]")
        return "exit"

    elif cmd == "/help":
        show_help()
        return None

    elif cmd == "/suggest":
        _handle_suggest(ctx)
        return None

    elif cmd == "/ls":
        cwd = ctx.get("project_root", ".")
        files = sorted(Path(cwd).rglob("*"))
        count = 0
        for f in files:
            if f.is_file() and not any(p.startswith(".") for p in f.relative_to(cwd).parts):
                console.print(f"  {f.relative_to(cwd)}")
                count += 1
                if count > 30:
                    console.print(f"  ... (showing first 30)")
                    break
        return None

    elif cmd == "/add":
        if not args:
            console.print("[yellow]Usage: /add <file_path>[/yellow]")
            return None
        ctx.setdefault("editable_files", []).append(args)
        console.print(f"[green]Added {args} to editable files[/green]")
        return None

    elif cmd == "/drop":
        if not args:
            ctx["editable_files"] = []
            ctx["read_only_files"] = []
            console.print("[green]Dropped all files[/green]")
        else:
            files = ctx.get("editable_files", [])
            if args in files:
                files.remove(args)
                console.print(f"[green]Removed {args} from editable[/green]")
            else:
                console.print(f"[yellow]{args} not found in context[/yellow]")
        return None

    elif cmd == "/diff":
        try:
            from core.git_repo import GitRepo
            repo = GitRepo(ctx.get("project_root", "."))
            if not repo.available:
                console.print("[yellow]Not a git repository[/yellow]")
                return None
            diff = repo.get_diff()
            if diff:
                console.print(diff)
            else:
                console.print("[dim]No changes to show[/dim]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
        return None

    elif cmd == "/undo":
        try:
            from core.git_repo import GitRepo
            repo = GitRepo(ctx.get("project_root", "."))
            repo.undo()
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
        return None

    elif cmd == "/commit":
        try:
            from core.git_repo import GitRepo
            repo = GitRepo(ctx.get("project_root", "."))
            if not repo.available:
                console.print("[yellow]Not a git repository[/yellow]")
                return None
            message = args if args else "OrcaCode update"
            repo.commit(message)
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
        return None

    elif cmd == "/clear":
        ctx["messages"] = []
        from core.memory_manager import MemoryManager
        MemoryManager(ctx.get("project_root", ".")).save_chat_history([])
        console.print("[green]Chat history cleared[/green]")
        return None

    elif cmd == "/tokens":
        msgs = ctx.get("messages", [])
        tokens = sum(len(str(m)) // 3 for m in msgs)
        console.print(f"[cyan]Chat history: ~{tokens} tokens ({len(msgs)} messages)[/cyan]")
        return None

    elif cmd == "/git":
        if not args:
            console.print("[yellow]Usage: /git <command> (e.g., /git status)[/yellow]")
            return None
        import subprocess
        import shlex
        try:
            cmd_list = ["git"] + shlex.split(args)
            result = subprocess.run(
                cmd_list,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                cwd=ctx.get("project_root", "."),
                timeout=15,
            )
            if result.stdout:
                console.print(result.stdout)
            if result.stderr:
                console.print(result.stderr)
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
        return None

    elif cmd == "/model":
        provider = ctx.get("provider", "deepseek")
        model = ctx.get("model", "deepseek-chat")
        console.print(f"[cyan]{provider}/{model}[/cyan]")
        return None

    elif cmd == "/set":
        if not args or "=" not in args:
            console.print("[yellow]Usage: /set key=value (e.g., /set provider=openai)[/yellow]")
            return None
        key, value = args.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key == "provider":
            ctx["provider"] = value
            console.print(f"[green]Provider set to {value}[/green]")
        elif key == "model":
            ctx["model"] = value
            console.print(f"[green]Model set to {value}[/green]")
        elif key == "api_key":
            ctx["api_key"] = value
            os.environ[f"{value.upper()}_API_KEY"] = value
            console.print(f"[green]API key set[/green]")
        else:
            console.print(f"[yellow]Unknown setting: {key}[/yellow]")
        return None

    elif cmd == "/memory":
        from core.memory_manager import MemoryManager
        mm = MemoryManager(ctx.get("project_root", "."))
        stats = mm.get_memory_stats()
        console.print(f"[cyan]Memory stats:[/cyan]")
        console.print(f"  Chat messages: {stats['chat_messages']}")
        console.print(f"  History size: {stats['history_size_kb']} KB")
        console.print(f"  Diff snapshots: {stats['diff_snapshots']}")
        console.print(f"  Diffs size: {stats['diffs_size_kb']} KB")
        return None

    elif cmd == "/diffs":
        from core.memory_manager import MemoryManager
        mm = MemoryManager(ctx.get("project_root", "."))
        diffs = mm.list_diffs()
        if not diffs:
            console.print("[dim]No diffs saved yet[/dim]")
        else:
            for d in diffs:
                console.print(f"  {d['time']} | {d['file']} | {d['reason']}")
        return None

    elif cmd == "/clear-memory":
        from core.memory_manager import MemoryManager
        mm = MemoryManager(ctx.get("project_root", "."))
        mm.clear_memory()
        return None

    elif cmd == "/codegraph":
        return _handle_codegraph(args, ctx)


    elif cmd == "/reset":
        ctx.clear()
        ctx.update({"messages": [], "editable_files": [], "read_only_files": []})
        console.print("[green]Reset all settings[/green]")
        return None

    elif cmd == "/version":
        console.print("[cyan]OrcaCode v0.1.0 (Terminal AI Agent)[/cyan]")
        return None

    else:
        console.print(f"[yellow]Unknown command: {cmd}[/yellow]")
        console.print("[dim]Type /help to see available commands[/dim]")
        return None


def is_command(text: str) -> bool:
    """Check if input is a command (starts with /)."""
    return text.strip().startswith("/")


def _handle_codegraph(args: str, ctx: dict) -> Optional[str]:
    """Handle /codegraph commands."""
    from core.services.codegraph_service import CodeGraphService
    from rich.table import Table
    from rich.panel import Panel
    from rich.syntax import Syntax

    project_root = ctx.get("project_root", ".")
    cg = CodeGraphService(project_root)

    if not cg.available:
        console.print("[yellow]CodeGraph CLI không khả dụng.[/yellow]")
        console.print("[dim]Cài đặt: npm install -g @colbymchenry/codegraph[/dim]")
        console.print("[dim]Hoặc build từ thư mục codegraph-main trong dự án.[/dim]")
        return None

    parts = args.strip().split(maxsplit=1) if args.strip() else ["status"]
    sub_cmd = parts[0].lower()
    sub_args = parts[1] if len(parts) > 1 else ""

    if sub_cmd == "status":
        status = cg.get_status()
        table = Table(title="CodeGraph Status")
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="white")
        table.add_row("Available", "Yes")
        table.add_row("Initialized", "Yes" if status.initialized else "No")
        table.add_row("Indexed", "Yes" if status.indexed else "No")
        table.add_row("Files", str(status.total_files))
        table.add_row("Nodes", str(status.total_nodes))
        table.add_row("Edges", str(status.total_edges))
        table.add_row("Languages", ", ".join(status.languages) if status.languages else "N/A")
        table.add_row("Version", status.version or "N/A")
        console.print(table)
        return None

    if sub_cmd == "init":
        console.print("[cyan]Đang khởi tạo CodeGraph...[/cyan]")
        success = cg.ensure_initialized(force_index=True)
        if success:
            console.print("[green]CodeGraph đã được khởi tạo và index xong![/green]")
        else:
            console.print("[red]Khởi tạo CodeGraph thất bại.[/red]")
        return None

    if not cg.is_project_initialized():
        console.print("[yellow]Dự án chưa được index. Chạy /codegraph init trước.[/yellow]")
        return None

    if sub_cmd == "search":
        if not sub_args:
            console.print("[yellow]Usage: /codegraph search <từ khóa>[/yellow]")
            return None
        results = cg.search(sub_args, limit=20)
        if not results:
            console.print("[dim]Không tìm thấy kết quả.[/dim]")
            return None
        table = Table(title=f"Search: {sub_args}")
        table.add_column("Name", style="cyan")
        table.add_column("Kind", style="green")
        table.add_column("File", style="white")
        for r in results:
            table.add_row(r.name, r.kind, f"{r.file_path}:{r.line}")
        console.print(table)
        return None

    if sub_cmd == "explore":
        if not sub_args:
            console.print("[yellow]Usage: /codegraph explore <câu hỏi>[/yellow]")
            return None
        console.print(f"[cyan]Đang khám phá: {sub_args}...[/cyan]")
        result = cg.explore(sub_args)
        if result.flow:
            console.print(Panel(result.flow, title="Flow", border_style="cyan"))
        if result.symbols:
            console.print(f"\n[bold]Symbols ({len(result.symbols)}):[/bold]")
            for sym in result.symbols[:10]:
                loc = f"{sym.file_path}:{sym.line}" if sym.file_path else "?"
                console.print(f"  [cyan]{sym.name}[/cyan] [{sym.kind}] @ {loc}")
                if sym.signature:
                    console.print(f"    {sym.signature}")
        if result.blast_radius:
            console.print(f"\n[bold yellow]Blast Radius ({len(result.blast_radius)}):[/bold yellow]")
            for sym in result.blast_radius[:15]:
                console.print(f"  [yellow]{sym.name}[/yellow] [{sym.kind}] @ {sym.file_path}")
        if not result.symbols and not result.flow:
            console.print("[dim]Không tìm thấy kết quả phù hợp.[/dim]")
        return None

    if sub_cmd == "callers":
        if not sub_args:
            console.print("[yellow]Usage: /codegraph callers <symbol>[/yellow]")
            return None
        results = cg.get_callers(sub_args)
        if not results:
            console.print(f"[dim]Không tìm thấy caller nào cho '{sub_args}'.[/dim]")
            return None
        console.print(f"\n[bold]Callers của '{sub_args}' ({len(results)}):[/bold]")
        for r in results:
            console.print(f"  [cyan]{r.name}[/cyan] [{r.kind}] @ {r.file_path}:{r.line}")
        return None

    if sub_cmd == "callees":
        if not sub_args:
            console.print("[yellow]Usage: /codegraph callees <symbol>[/yellow]")
            return None
        results = cg.get_callees(sub_args)
        if not results:
            console.print(f"[dim]Không tìm thấy callee nào cho '{sub_args}'.[/dim]")
            return None
        console.print(f"\n[bold]Callees của '{sub_args}' ({len(results)}):[/bold]")
        for r in results:
            console.print(f"  [cyan]{r.name}[/cyan] [{r.kind}] @ {r.file_path}:{r.line}")
        return None

    if sub_cmd == "impact":
        if not sub_args:
            console.print("[yellow]Usage: /codegraph impact <symbol>[/yellow]")
            return None
        results = cg.get_impact(sub_args, depth=3)
        if not results:
            console.print(f"[dim]Không tìm thấy impact nào cho '{sub_args}'.[/dim]")
            return None
        console.print(f"\n[bold yellow]Impact của '{sub_args}' ({len(results)}):[/bold yellow]")
        for r in results:
            console.print(f"  [yellow]{r.name}[/yellow] [{r.kind}] @ {r.file_path}:{r.line}")
        return None

    if sub_cmd == "affected":
        if not sub_args:
            console.print("[yellow]Usage: /codegraph affected <file1> <file2> ...[/yellow]")
            return None
        files = sub_args.split()
        results = cg.get_affected_tests(files)
        if not results:
            console.print("[dim]Không tìm thấy test files bị ảnh hưởng.[/dim]")
            return None
        console.print(f"\n[bold]Test files bị ảnh hưởng ({len(results)}):[/bold]")
        for f in results:
            console.print(f"  [cyan]{f}[/cyan]")
        return None

    console.print(f"[yellow]Không rõ sub-command: {sub_cmd}[/yellow]")
    console.print("[dim]Dùng: /codegraph [status|init|search|explore|callers|callees|impact|affected] <query>[/dim]")
    return None


def _handle_suggest(ctx: dict) -> None:
    """Suggest commands based on current context."""
    from rich.panel import Panel
    from rich.table import Table

    project_root = ctx.get("project_root", ".")
    messages = ctx.get("messages", [])
    editable_files = ctx.get("editable_files", [])
    has_errors = False
    has_recent_changes = False
    has_recent_tool_output = False

    # Analyze recent messages for context clues
    recent = [m.get("content", "") for m in messages[-20:]]
    combined = " ".join(recent[-10:]).lower()

    if any(w in combined for w in ("error", "fail", "exception", "traceback", "crash")):
        has_errors = True
    if any(w in combined for w in ("wrote", "modified", "patched", "created", "written")):
        has_recent_changes = True
    if any("Tool Results" in m for m in recent[-10:]):
        has_recent_tool_output = True

    # Check git repo
    has_git = False
    try:
        has_git = (Path(project_root) / ".git").exists()
    except Exception:
        pass

    # Build suggestion groups
    suggestions = []

    # Code group (related to recent edits)
    code_actions = []
    if has_recent_changes or editable_files:
        code_actions.append(("/diff", "Xem thay đổi chưa commit"))
        code_actions.append(("/commit", "Commit thay đổi"))
    if editable_files:
        code_actions.append(("/add <file>", "Thêm file vào context"))
        code_actions.append(("/drop <file>", "Bỏ file khỏi context"))
    if has_errors:
        code_actions.append(("/clear", "Xoá chat và thử lại"))
    if has_recent_tool_output:
        code_actions.append(("/undo", "Hoàn tác thay đổi cuối"))
    if code_actions:
        suggestions.append(("📝 Code", code_actions))

    # Explore group
    explore_actions = []
    explore_actions.append(("/ls", "Danh sách file trong project"))
    explore_actions.append(("/codegraph search <query>", "Tìm code với CodeGraph"))
    explore_actions.append(("/codegraph explore <file>", "Khám phá cấu trúc file"))
    if has_git:
        explore_actions.append(("/git status", "Xem trạng thái git"))
    suggestions.append(("🔍 Explore", explore_actions))

    # Debug group
    debug_actions = []
    debug_actions.append(("/tokens", "Xem token usage estimate"))
    debug_actions.append(("/memory", "Xem memory stats"))
    debug_actions.append(("/model", "Xem model hiện tại"))
    if has_errors:
        debug_actions.append(("/clear-memory", "Xoá long-term memory"))
    suggestions.append(("⚙️ Debug", debug_actions))

    # Manage group
    manage_actions = []
    manage_actions.append(("/set provider=...", "Đổi provider"))
    manage_actions.append(("/set model=...", "Đổi model"))
    manage_actions.append(("/reset", "Reset config"))
    if has_git:
        manage_actions.append(("/diffs", "Xem lịch sử diffs"))
    suggestions.append(("🔧 Manage", manage_actions))

    # Render
    table = Table(title="[bold]Gợi ý lệnh theo context[/bold]", show_header=False, box=None)
    table.add_column("", style="cyan", no_wrap=True)
    for group_name, actions in suggestions:
        rows = [f"  {cmd:25s} {desc}" for cmd, desc in actions]
        table.add_row(f"\n[bold]{group_name}[/bold]")
        for row in rows:
            table.add_row(row)

    console.print(table)
    console.print("\n[dim]Mẹo: Gõ /help để xem tất cả lệnh[/dim]")