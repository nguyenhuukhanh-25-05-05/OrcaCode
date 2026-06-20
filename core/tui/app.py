"""OrcaCode TUI — Main Application."""

import asyncio
import os
import re
import threading
import time

from rich.markup import escape
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Label, ListItem, ListView, Select, Static, TextArea

from config.settings import (
    get_api_base_url,
    get_provider_package,
    get_provider_pip_package,
    load_config,
)
from core.agent import AgentController, AppCallbacks
from core.models import ExecutionMode
from core.pricing import estimate_token_cost
from core.services.arch_graph import ArchGraph
from core.tui.css import CANONICAL_PROVIDERS, OCEAN_CSS, PROVIDER_MODELS
from core.tui.modals import (
    ApprovalModal,
    AutopilotWarningModal,
    InstallPromptModal,
    PlanReviewModal,
    SetupModal,
)
from core.tui.utils import _format_duration, get_clipboard_text, set_clipboard_text
from core.tui.widgets import ChatPanel, Composer, TopBar, WorkPanel


class OrcaTUI(App):
    """OrcaCode TUI — Ocean Blue Theme."""

    CSS = OCEAN_CSS
    TITLE = "🐋 OrcaCode TUI v0.2.0"
    SUB_TITLE = "Ocean Blue Theme"
    BINDINGS = [
        Binding("ctrl+j", "submit", "Send", show=True),
        Binding("ctrl+d", "stop_execution", "Stop", show=True),
        Binding("ctrl+l", "clear_chat", "Clear Chat"),
        Binding("ctrl+s", "save_session", "Save Session"),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self, config=None):
        super().__init__()
        self.config = config or load_config()
        self.chat_history = []
        self.is_processing = False
        self._agent: AgentController | None = None
        self.loaded_files = set()
        self.active_plan = []
        self.current_step_idx = -1
        self.mode = ExecutionMode.PLAN
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_cost = 0.0
        self.system_logs = []
        self.processed_images = set()
        self.current_iteration_str = ""
        self._syncing_select = False
        self._agent_start = [time.perf_counter()]
        self.arch_graph = ArchGraph(self.config.project_root or ".")

    def _update_work_list_ui(self) -> None:
        try:
            lines = []
            if hasattr(self, "current_iteration_str") and self.current_iteration_str:
                lines.append(f"[bold #00FFFF]✦ {escape(self.current_iteration_str)}[/]")
                lines.append("")

            if not self.active_plan:
                if not lines:
                    self.query_one("#work-list").update("No active work")
                else:
                    self.query_one("#work-list").update("\n".join(lines))
                return
            
            for i, step in enumerate(self.active_plan):
                status = step["status"]
                desc = step["desc"]
                
                if status == "pending":
                    icon = "[#AAAAAA]○[/]"
                    style = "[#AAAAAA]"
                elif status == "running":
                    icon = "[#FFFFFF]●[/]"
                    style = "[bold #00FFFF]"
                elif status == "ok":
                    icon = "[#E0E0E0]✓[/]"
                    style = "[#E0E0E0]"
                else:
                    icon = "[#f43f5e]✗[/]"
                    style = "[#f43f5e]"
                    
                lines.append(f"{icon} {style}{escape(desc)}[/]")
                
            self.query_one("#work-list").update("\n".join(lines))
        except Exception:
            pass

    def _update_files_list_ui(self) -> None:
        pass

    def _update_timeline_ui(self) -> None:
        try:
            timeline_list = self.query_one("#timeline-list", ListView)
        except Exception:
            return

        timeline_list.clear()

        from core.services.checkpoint_service import CheckpointService
        svc = CheckpointService(self.config.project_root)
        try:
            checkpoints = svc.list_checkpoints()
        except Exception:
            checkpoints = []

        if not checkpoints:
            timeline_list.append(ListItem(Static("Chưa có checkpoint nào.")))
            return

        for cp in checkpoints:
            action_str = cp.get("action_type", "AI")
            text = f"● [{cp.get('time_display', '??:??')}] {cp.get('description', '')} ({action_str})"
            item = ListItem(Static(text))
            timeline_list.append(item)

    def _add_system_log(self, message: str) -> None:
        try:
            from datetime import datetime
            ts = datetime.now().strftime("%H:%M:%S")
            self.system_logs.append(f"[#AAAAAA]{ts}[/] {message}")
            if len(self.system_logs) > 50:
                self.system_logs.pop(0)
            self.query_one("#logs-list").update("\n".join(self.system_logs))
            self.query_one("#logs-list-scroll").scroll_end(animate=False)
        except Exception:
            pass

    def _load_project_files(self) -> None:
        try:
            from pathlib import Path
            cwd = self.config.project_root or "."
            files = sorted(Path(cwd).rglob("*"))
            count = 0
            for f in files:
                if not f.is_file():
                    continue
                rel_parts = f.relative_to(cwd).parts
                if any(p.startswith(".") for p in rel_parts):
                    continue
                if any(p in ("__pycache__", "build", "dist", "node_modules", "venv", "env") for p in rel_parts):
                    continue
                if f.suffix in (".pyc", ".pyo", ".pyd", ".class", ".o", ".exe", ".dll", ".so", ".cache"):
                    continue
                self.loaded_files.add(str(f.relative_to(cwd)))
                count += 1
                if count >= 50:
                    break
        except Exception:
            pass

    def compose(self) -> ComposeResult:
        yield TopBar(model=self.config.model.model, provider=self.config.model.provider, mode=self.mode.name.title())
        with Horizontal(id="main-layout"):
            with Vertical(id="chat-area"):
                yield ChatPanel(id="chat-log")
                yield Composer()
            yield WorkPanel(id="sidebar")

    def on_mount(self) -> None:
        chat = self.query_one(ChatPanel)
        # ── Block-art ORCA CODE logo ──
        LOGO = (
            "\n"
            "[#3498db] ██████╗ ██████╗  ██████╗ █████╗ [/] [#888888] ██████╗ ██████╗ ██████╗ ███████╗[/]\n"
            "[#3498db]██╔═══██╗██╔══██╗██╔════╝██╔══██╗[/] [#888888]██╔════╝██╔═══██╗██╔══██╗██╔════╝[/]\n"
            "[#3498db]██║   ██║██████╔╝██║     ███████║[/] [#888888]██║     ██║   ██║██║  ██║█████╗  [/]\n"
            "[#3498db]██║   ██║██╔══██╗██║     ██╔══██║[/] [#888888]██║     ██║   ██║██║  ██║██╔══╝  [/]\n"
            "[#3498db]╚██████╔╝██║  ██║╚██████╗██║  ██║[/] [#888888]╚██████╗╚██████╔╝██████╔╝███████╗[/]\n"
            "[#3498db] ╚═════╝ ╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝[/] [#888888] ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝[/]\n"
        )
        chat.write_logo(LOGO)
        chat.write("[#AAAAAA]OrcaCode TUI v0.2.0 starting...[/]")
        self._add_system_log("[#E0E0E0]OrcaTUI started.[/]")
        self._update_files_list_ui()
        self._update_timeline_ui()
        self.set_timer(0.1, self._check_setup)
        self._init_blueprint_worker()
        
        def _end_startup() -> None:
            chat._in_startup = False
            chat.scroll_to(y=0, animate=False)
        self.set_timer(0.8, _end_startup)

    def _init_codegraph(self) -> None:
        try:
            from core.services.codegraph_service import CodeGraphService
            cg = CodeGraphService(self.config.project_root or ".")
            if cg.available and not cg.is_project_initialized():
                self._update_status("Initializing CodeGraph...")
                if cg.ensure_initialized(force_index=True):
                    status = cg.get_status()
                    chat = self.query_one(ChatPanel)
                    chat.write(f"[#E0E0E0]CodeGraph ready — {status.total_files} files, {status.total_nodes} nodes, {status.total_edges} edges[/]")
                    self._update_status("Ready")
                else:
                    self._update_status("Ready (no CodeGraph)")
            elif cg.available:
                status = cg.get_status()
                chat = self.query_one(ChatPanel)
                chat.write(f"[#AAAAAA]CodeGraph: {status.total_files} files, {status.total_nodes} nodes[/]")
        except Exception:
            pass

    def _run_pip_install(self, pip_pkg: str) -> bool:
        import subprocess, sys
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", pip_pkg],
                capture_output=True, encoding="utf-8", errors="replace",
                timeout=120,
            )
            if result.returncode == 0:
                chat = self.query_one(ChatPanel)
                chat.write(f"[#E0E0E0]Đã cài đặt {pip_pkg} thành công![/]")
                return True
            else:
                chat = self.query_one(ChatPanel)
                chat.write(f"[#CCCCCC]Cài đặt {pip_pkg} thất bại: {result.stderr[:200]}[/]")
                return False
        except Exception as e:
            chat = self.query_one(ChatPanel)
            chat.write(f"[#f43f5e]Lỗi khi cài {pip_pkg}: {e}[/]")
            return False

    def _on_install_done(self, ok: bool, new_provider: str, pip_pkg: str) -> None:
        if not ok:
            return
        if self._run_pip_install(pip_pkg):
            self._syncing_select = True
            try:
                select_provider = self.query_one("#topbar-select-provider")
                select_provider.value = new_provider
            except Exception:
                pass
            finally:
                self._syncing_select = False
            self._do_provider_switch(new_provider)

    def _do_welcome(self) -> None:
        chat = self.query_one(ChatPanel)
        model_name = f"{self.config.model.provider}/{self.config.model.model}"
        chat.write(f"[bold #22c55e]◆ OrcaCode TUI ready — Model:[/] [#E0E0E0]{model_name}[/]")
        chat.write("[#AAAAAA]Type your request or /help for commands.[/]")
        self._update_status("Ready")
        self.set_timer(0.5, self._init_codegraph)

    def _update_status(self, text: str) -> None:
        status = self.query_one("#status-inner")
        status.update(f"Status: {text}  ")

    def _record_token_usage(self, p_tokens: int, c_tokens: int,
                            provider: str = "", model: str = "") -> None:
        prompt_tokens = max(int(p_tokens or 0), 0)
        completion_tokens = max(int(c_tokens or 0), 0)
        pricing_provider = provider or self.config.model.provider
        pricing_model = model or self.config.model.model

        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        self.total_cost += estimate_token_cost(
            pricing_provider,
            pricing_model,
            prompt_tokens,
            completion_tokens,
        )

    def _format_topbar_cost(self) -> str:
        total_tokens = self.total_prompt_tokens + self.total_completion_tokens
        if total_tokens >= 1_000_000:
            token_text = f"{total_tokens / 1_000_000:.2f}M"
        elif total_tokens >= 1_000:
            token_text = f"{total_tokens / 1_000:.1f}k"
        else:
            token_text = str(total_tokens)

        if self.total_cost >= 1:
            cost_text = f"${self.total_cost:.2f}"
        elif self.total_cost >= 0.01:
            cost_text = f"${self.total_cost:.4f}"
        else:
            cost_text = f"${self.total_cost:.6f}"

        return f"Cost: {cost_text} | Tok: {token_text}"

    def _do_provider_switch(self, new_provider: str) -> None:
        self.config.model.provider = new_provider
        self.config.model.base_url = get_api_base_url(new_provider)
        prov_lower = new_provider.lower().strip()
        models = PROVIDER_MODELS.get(prov_lower, ["deepseek-chat"])
        current_model = self.config.model.model
        if current_model in models:
            default_model = current_model
            model_options = list(models)
        else:
            default_model = models[0] if models else current_model
            model_options = [default_model] + [m for m in models if m != default_model]
        self.config.model.model = default_model
        try:
            select_model = self.query_one("#topbar-select-model")
            select_model.set_options([(m, m) for m in model_options])
            if select_model.value != default_model:
                select_model.value = default_model
            select_model.remove_class("hidden")
        except Exception:
            pass
        self._save_config(
            api_key=self.config.model.api_key,
            provider=new_provider,
            apply_project=False,
            base_url=self.config.model.base_url,
            model=default_model,
        )
        chat = self.query_one(ChatPanel)
        chat.write(f"[#FFFFFF]Đã chuyển đổi provider sang: {new_provider} (model: {default_model})[/]")

    def _refresh_topbar_cost(self) -> None:
        try:
            cost_widget = self.query_one("#topbar-cost")
            cost_widget.update(self._format_topbar_cost())
        except Exception:
            pass

    def _save_config(self, api_key: str, provider: str, apply_project: bool,
                      base_url: str = "", model: str = "", temperature: float = None) -> None:
        chat = self.query_one(ChatPanel)
        from pathlib import Path
        if temperature is None:
            temperature = getattr(self.config.model, "temperature", 0.2)
        # Always save to ~/.orcacode/config.toml (persists across projects)
        orcacode_dir = Path.home() / ".orcacode"
        try:
            orcacode_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        toml_path = orcacode_dir / "config.toml"
        try:
            with open(toml_path, "w", encoding="utf-8") as f:
                f.write("[model]\n")
                f.write(f'api_key = "{api_key}"\n')
                f.write(f'provider = "{provider}"\n')
                f.write(f'model = "{model or "deepseek-chat"}"\n')
                f.write(f'temperature = {temperature}\n')
                if base_url:
                    f.write(f'base_url = "{base_url}"\n')
            try:
                os.chmod(toml_path, 0o600)
            except (OSError, NotImplementedError):
                pass
            chat.write(f"[#E0E0E0]Config saved to {toml_path}[/]")
        except Exception as e:
            chat.write(f"[#CCCCCC]Could not save config: {e}[/]")

        project_root = self.config.project_root or "."
        # Only write project .env when user explicitly opts in
        if apply_project:
            env_path = os.path.join(project_root, ".env")
            try:
                with open(env_path, "w", encoding="utf-8") as f:
                    f.write(f"ORCA_API_KEY={api_key}\n")
                    f.write(f"ORCA_PROVIDER={provider}\n")
                    f.write(f"ORCA_MODEL={model or 'deepseek-chat'}\n")
                    f.write(f"ORCA_TEMPERATURE={temperature}\n")
                    if base_url:
                        f.write(f"ORCA_BASE_URL={base_url}\n")
                chat.write(f"[#E0E0E0]Synced .env with new config[/]")
            except Exception as e:
                chat.write(f"[#CCCCCC]Could not sync .env: {e}[/]")

            gitignore_path = os.path.join(project_root, ".gitignore")
            try:
                existing = []
                if os.path.exists(gitignore_path):
                    with open(gitignore_path, "r", encoding="utf-8") as gf:
                        existing = [l.strip() for l in gf.readlines()]
                if ".env" not in existing:
                    with open(gitignore_path, "a", encoding="utf-8") as gf:
                        if existing and existing[-1] != "":
                            gf.write("\n")
                        gf.write("# OrcaCode — keep API keys out of git\n.env\n")
                    chat.write("[#E0E0E0]Added .env to .gitignore[/]")
            except Exception:
                pass

    def _check_setup(self) -> None:
        if self.config.model.api_key:
            self._do_welcome()
            self.query_one("#composer-input").focus()
            return
        chat = self.query_one(ChatPanel)
        chat.write("[#CCCCCC]No API key found. Opening setup wizard...[/]")
        
        def handle_initial_setup(result: dict) -> None:
            if result and result.get("api_key"):
                self.config.model.api_key = result["api_key"]
                self.config.model.provider = result.get("provider", "deepseek")
                base_url = result.get("base_url", "")
                if base_url:
                    self.config.model.base_url = base_url
                prov = self.config.model.provider.lower().strip()
                models = PROVIDER_MODELS.get(prov, ["deepseek-chat"])
                user_model = result.get("model", "")
                default_model = user_model if user_model else (models[0] if models else "custom-model")
                self.config.model.model = default_model
                if result.get("temperature"):
                    try:
                        self.config.model.temperature = float(result["temperature"])
                    except ValueError:
                        pass
                self._save_config(
                    result["api_key"],
                    result.get("provider", "deepseek"),
                    result.get("apply_project", True),
                    base_url,
                    default_model,
                    temperature=self.config.model.temperature,
                )
                self._syncing_select = True
                try:
                    select_provider = self.query_one("#topbar-select-provider")
                    select_provider.set_options([(p, p) for p in CANONICAL_PROVIDERS])
                    select_provider.value = self.config.model.provider
                except Exception:
                    pass
                if default_model not in models:
                    model_options = [default_model] + list(models)
                else:
                    model_options = list(models)
                try:
                    select_model = self.query_one("#topbar-select-model")
                    select_model.set_options([(m, m) for m in model_options])
                    if select_model.value != default_model:
                        select_model.value = default_model
                    select_model.remove_class("hidden")
                except Exception:
                    pass
                finally:
                    self._syncing_select = False
                self._do_welcome()
                self.query_one("#composer-input").focus()
                self.set_timer(0.5, self._init_codegraph)
            else:
                chat.write("[#CCCCCC]Setup skipped. Type /setup to configure later.[/]")
                self._update_status("No API key")
                self.query_one("#composer-input").focus()

        self.push_screen(SetupModal(self.config), callback=handle_initial_setup)

    def _safe_call_from_thread(self, callback, *args, **kwargs):
        """Call callback on app thread, or directly if already on it."""
        if self._thread_id == threading.get_ident():
            callback(*args, **kwargs)
        else:
            self.call_from_thread(callback, *args, **kwargs)

    # ─── Callback builders ───

    def _make_callbacks(self) -> AppCallbacks:
        chat = self.query_one(ChatPanel)
        status = self.query_one("#status-inner")
        logs = self.query_one("#logs-list")

        def request_approval(title: str, detail: str) -> bool:
            import queue
            q = queue.Queue()
            def push_modal():
                modal = ApprovalModal(title, detail)
                self.push_screen(modal, callback=lambda res: q.put(res if res is not None else False))
            self.call_from_thread(push_modal)
            while True:
                try:
                    return q.get(timeout=0.5)
                except queue.Empty:
                    if self._agent and getattr(self._agent, "_interrupt_event", threading.Event()).is_set():
                        return False

        def request_plan_approval(plan_text: str) -> str:
            import queue
            q = queue.Queue()
            def push_plan_modal():
                modal = PlanReviewModal(plan_text)
                self.push_screen(modal, callback=lambda res: q.put(res if res is not None else "cancel"))
            self.call_from_thread(push_plan_modal)
            while True:
                try:
                    return q.get(timeout=0.5)
                except queue.Empty:
                    if self._agent and getattr(self._agent, "_interrupt_event", threading.Event()).is_set():
                        return "cancel"

        _streaming_buf = [0]

        def write_chunk(delta: str):
            if not delta:
                return
            _streaming_buf[0] += len(delta)
            self._safe_call_from_thread(status.update, f"Status: AI is responding ({_streaming_buf[0]} chars received)  ")

        def write_chat(text: str):
            stripped = (text or "").strip()
            if not stripped:
                return

            # Strip ANSI escape codes early — before any Rich object wrapping.
            # Otherwise Text/Panel objects bypass ChatPanel._sanitize later.
            stripped = ChatPanel._sanitize(stripped)
            if not stripped:
                return

            import re
            is_tool_log = bool(
                re.match(r'^(?:---|DEBUG:|INFO:|\[/?(?:#|bold|italic|green|red|yellow|blue|magenta|cyan|white|blink|dim|reverse))', stripped)
                or stripped.startswith("  ")
            )
            if is_tool_log:
                # Send to write_tool_log to group into Collapsible
                self._safe_call_from_thread(chat.write_tool_log, stripped)
            else:
                self._safe_call_from_thread(chat.write_ai_response, stripped)

        def write_status(text: str):
            safe_text = ChatPanel._sanitize(text)
            self._safe_call_from_thread(status.update, f"Status: {safe_text}  ")
            if safe_text.strip():
                self._safe_call_from_thread(self._add_system_log, f"[#AAAAAA]INFO:[/] {escape(safe_text[:100])}")

        def write_tokens(p_tokens: int, c_tokens: int, provider: str = "", model: str = ""):
            self._record_token_usage(p_tokens, c_tokens, provider, model)
            self._safe_call_from_thread(self._refresh_topbar_cost)

        def write_tool_plan(plans: list[dict]):
            self.active_plan = []
            for tc in plans:
                t = tc.get("type", "")
                path_val = tc.get("path")
                if path_val:
                    try:
                        from pathlib import Path
                        cwd = self.config.project_root or "."
                        rel = Path(path_val).relative_to(cwd)
                        path_str = str(rel)
                    except Exception:
                        from pathlib import Path
                        path_str = Path(path_val).name
                else:
                    path_str = ""

                if t == "write_file":
                    desc = f"Write: {path_str}"
                elif t == "patch_file":
                    desc = f"Patch: {path_str}"
                elif t == "run_command":
                    desc = f"Run: {tc.get('command', '')[:25]}"
                elif t == "refactor":
                    desc = "Refactor plan"
                elif t == "debug_error":
                    desc = "Analyze stack trace"
                else:
                    desc = f"Tool: {t}"
                self.active_plan.append({"desc": desc, "status": "pending", "tc": tc})
            self.current_step_idx = -1
            self._safe_call_from_thread(self._update_work_list_ui)
            self._safe_call_from_thread(self._add_system_log, f"[#FFFFFF]PLAN:[/] Generated {len(plans)} steps")

        def write_tool_start(tc: dict, idx: int, total: int):
            self.current_step_idx = idx
            if idx < len(self.active_plan):
                self.active_plan[idx]["status"] = "running"
            self._safe_call_from_thread(self._update_work_list_ui)
            desc = self.active_plan[idx]["desc"] if idx < len(self.active_plan) else str(tc)
            self._safe_call_from_thread(self._add_system_log, f"[#FFFFFF]TOOL:[/] Running {desc}...")

        def write_result(ok: bool, msg: str):
            idx = self.current_step_idx
            if idx >= 0 and idx < len(self.active_plan):
                self.active_plan[idx]["status"] = "ok" if ok else "failed"
                tc = self.active_plan[idx]["tc"]
                if tc.get("type") in ("write_file", "patch_file") and tc.get("path"):
                    try:
                        from pathlib import Path
                        cwd = self.config.project_root or "."
                        rel = Path(tc["path"]).relative_to(cwd)
                        self.loaded_files.add(str(rel))
                    except Exception:
                        from pathlib import Path
                        self.loaded_files.add(Path(tc["path"]).name)
                    self._project_files_cached = None
            
            color = "#22c55e" if ok else "#f59e0b"
            self._safe_call_from_thread(chat.write, f"[{color}]{'[OK]' if ok else '⏭'} {escape(msg[:300])}[/]")
            self._safe_call_from_thread(self._add_system_log, f"[{color}]{'SUCCESS' if ok else 'SKIP'}:[/] {escape(msg[:100])}")
            self._safe_call_from_thread(self._update_work_list_ui)
            self._safe_call_from_thread(self._update_files_list_ui)

        def write_error(msg: str):
            safe_msg = ChatPanel._sanitize(msg)
            self._safe_call_from_thread(chat.write, f"[#f43f5e]Error: {escape(safe_msg[:500])}[/]")
            self._safe_call_from_thread(self._add_system_log, f"[#f43f5e]ERROR:[/] {escape(safe_msg[:200])}")

        def write_done(elapsed: float):
            if elapsed:
                elapsed_str = _format_duration(elapsed)
                done_text = f" [#22c55e]■[/#22c55e]  [#38bdf8]Done[/#38bdf8] [#AAAAAA]• OrcaCode • {elapsed_str}[/#AAAAAA]"
                log_text = f"[#E0E0E0]SUCCESS:[/] Run completed in {elapsed_str}"
            else:
                done_text = " [#22c55e]■[/#22c55e]  [#38bdf8]Done[/#38bdf8] [#AAAAAA]• OrcaCode[/#AAAAAA]"
                log_text = "[#E0E0E0]SUCCESS:[/] Run completed successfully"
            self._safe_call_from_thread(chat.write, done_text)
            self._safe_call_from_thread(status.update, "Status: Ready  ")
            self._safe_call_from_thread(self._add_system_log, log_text)
            self.current_iteration_str = ""
            if self.active_plan:
                for step in self.active_plan:
                    if step["status"] == "running":
                        step["status"] = "ok"
                self._safe_call_from_thread(self._update_work_list_ui)
            self._safe_call_from_thread(self._update_timeline_ui)
            self._safe_call_from_thread(self.query_one("#composer-input").focus)

        _iter_start = [None]

        def write_iteration(cur: int, total: int):
            now = time.perf_counter()
            if _iter_start[0] is not None:
                prev_dur = _format_duration(now - _iter_start[0])
                elapsed_str = _format_duration(now - self._agent_start[0])
                self._safe_call_from_thread(chat.write_tool_log, f"   Iteration {cur-1} took {prev_dur} ({elapsed_str} total)")
            _iter_start[0] = now
            self._safe_call_from_thread(chat.write_tool_log, f"--- Iteration {cur}/{total} ---")
            self._safe_call_from_thread(self._add_system_log, f"[#AAAAAA]ITER:[/] Starting iteration {cur}/{total}")
            self.current_iteration_str = f"Vòng lặp {cur}/{total}: Đang chạy..."
            self._safe_call_from_thread(self._update_work_list_ui)

        def on_plan_created(plan_path: str):
            self._safe_call_from_thread(chat.write, f"[#E0E0E0]Kế hoạch đã được tạo: {plan_path}[/]")
            self._safe_call_from_thread(self._add_system_log, f"[#E0E0E0]PLAN:[/] Plan file created at {plan_path}")
            from pathlib import Path
            plan_full = Path(self.config.project_root) / plan_path if self.config.project_root else Path(plan_path)
            if not plan_full.is_absolute():
                plan_full = Path(self.config.project_root) / plan_path if self.config.project_root else Path.cwd() / plan_path
            try:
                if plan_full.exists():
                    content = plan_full.read_text(encoding="utf-8")
                    from rich.markdown import Markdown
                    self._safe_call_from_thread(chat.write, Markdown(f"## Nội dung Kế hoạch\n\n{content[:3000]}"))
                    if len(content) > 3000:
                        self._safe_call_from_thread(chat.write, "[#AAAAAA]... (nội dung bị cắt, xem đầy đủ trong file kế hoạch)[/]")
                    self._safe_call_from_thread(chat.write, "[#CCCCCC]👉 Bạn có thể duyệt kế hoạch này. Chuyển sang chế độ Auto để thực thi, hoặc chỉnh sửa file .md rồi yêu cầu lại.[/]")
            except Exception as e:
                self._safe_call_from_thread(chat.write, f"[#CCCCCC]Không thể đọc file kế hoạch: {e}[/]")

        return AppCallbacks(
            on_chat=write_chat,
            on_chunk=write_chunk,
            on_status=write_status,
            on_tool_start=write_tool_start,
            on_tool_plan=write_tool_plan,
            on_tokens_used=write_tokens,
            on_result=write_result,
            on_error=write_error,
            on_done=write_done,
            on_iteration=write_iteration,
            request_approval=request_approval,
            request_plan_approval=request_plan_approval,
            on_plan_created=on_plan_created,
        )

    # ─── Input Handling ───

    async def _submit_prompt(self, user_input: str) -> None:
        self._agent_start[0] = time.perf_counter()
        chat = self.query_one(ChatPanel)

        if user_input.startswith("/"):
            self.handle_command(user_input)
            return

        self.chat_history.append({"role": "user", "content": user_input})
        if len(self.chat_history) > 200:
            self.chat_history = self.chat_history[-100:]
        chat.write_user_message(user_input)

        if not self.is_processing:
            self.is_processing = True
            inp = self.query_one("#composer-input")
            inp.text = "AI đang xử lý tác vụ... Nhấn Ctrl+D để dừng chạy."
            inp.disabled = True
            inp.border_subtitle = "Thinking...  |  Ctrl+D Stop"
            try:
                self.current_iteration_str = "Đang phân tích dự án..."
                self.active_plan = [{"desc": "Thinking & analyzing project...", "status": "running"}]
                self._update_work_list_ui()
                self._update_timeline_ui()
                await self.run_agent(user_input)
            except Exception as e:
                err_msg = str(e)
                if "No module named" in err_msg:
                    pkg = err_msg.split("'")[1] if "'" in err_msg else err_msg
                    chat.write(f"[#CCCCCC]Thiếu package: {pkg}. Cài đặt: pip install {pkg.split('.')[0]}[/]")
                else:
                    chat.write(f"[#f43f5e]Lỗi: {err_msg[:300]}[/]")
                self._update_status("Error")
            finally:
                inp.disabled = False
                inp.text = ""
                inp.border_subtitle = "Ctrl+Enter Send  |  Ctrl+D Stop  |  Ctrl+L Clear  |  Ctrl+Q Quit"
                inp.focus()
                self.is_processing = False
                self.current_iteration_str = ""

    def trigger_submit(self) -> None:
        if self.is_processing:
            return
        inp = self.query_one("#composer-input")
        val = inp.text.strip()
        if val:
            inp.text = ""
            self.run_worker(self._submit_prompt(val))

    def handle_command(self, cmd: str) -> None:
        chat = self.query_one(ChatPanel)
        parts = cmd.split(maxsplit=1)
        command = parts[0].lower()

        help_map = {
            "/help": "Show available commands",
            "/setup": "Open setup wizard (API key, provider)",
            "/clear": "Clear chat log",
            "/files": "Show loaded files",
            "/model": "Show current model",
            "/session": "Save session",
            "/checkpoint": "Tạo checkpoint thủ công cho workspace",
            "/blueprint": "Cập nhật và hiển thị sơ đồ thiết kế chi tiết (symbols map)",
            "/quit": "Exit TUI",
        }

        if command == "/help":
            lines = ["[bold #00FFFF]Available Commands:[/]"]
            for k, v in help_map.items():
                lines.append(f"  {k} — {v}")
            chat.write("\n".join(lines))

        elif command == "/setup":
            def save_setup_config(result: dict) -> None:
                if result and result.get("api_key"):
                    self.config.model.api_key = result["api_key"]
                    self.config.model.provider = result.get("provider", "deepseek")
                    base_url = result.get("base_url", "")
                    if base_url:
                        self.config.model.base_url = base_url
                    prov = self.config.model.provider.lower().strip()
                    models = PROVIDER_MODELS.get(prov, ["deepseek-chat"])
                    user_model = result.get("model", "")
                    default_model = user_model if user_model else (models[0] if models else "custom-model")
                    self.config.model.model = default_model
                    if result.get("temperature"):
                        try:
                            self.config.model.temperature = float(result["temperature"])
                        except ValueError:
                            pass
                    self._save_config(
                        result["api_key"],
                        result.get("provider", "deepseek"),
                        result.get("apply_project", True),
                        base_url,
                        default_model,
                        temperature=self.config.model.temperature,
                    )
                    chat.write(f"[#E0E0E0]Setup complete — Provider: {self.config.model.provider}[/]")
                    self._syncing_select = True
                    try:
                        select_provider = self.query_one("#topbar-select-provider")
                        select_provider.set_options([(p, p) for p in CANONICAL_PROVIDERS])
                        select_provider.value = self.config.model.provider
                    except Exception:
                        pass
                    if default_model not in models:
                        model_options = [default_model] + list(models)
                    else:
                        model_options = list(models)
                    try:
                        select_model = self.query_one("#topbar-select-model")
                        select_model.set_options([(m, m) for m in model_options])
                        if select_model.value != default_model:
                            select_model.value = default_model
                        select_model.remove_class("hidden")
                    except Exception:
                        pass
                    finally:
                        self._syncing_select = False
                    self._update_status("Ready")
                    self.set_timer(0.5, self._init_codegraph)
                else:
                    chat.write("[#CCCCCC]Setup cancelled.[/]")

            self.push_screen(SetupModal(self.config), callback=save_setup_config)

        elif command == "/clear":
            chat.clear()
            self.chat_history = []
            from core.memory_manager import MemoryManager
            MemoryManager(self.config.project_root or ".").save_chat_history([])
            chat.write("[#AAAAAA]Chat history cleared.[/]")

        elif command == "/model":
            chat.write(f"[#FFFFFF]Model: {self.config.model.provider}/{self.config.model.model}[/]")

        elif command == "/files":
            self._update_files_list_ui()

        elif command == "/session":
            from core.memory_manager import MemoryManager
            mm = MemoryManager(self.config.project_root or ".")
            mm.save_chat_history(self.chat_history)
            chat.write("[#E0E0E0]Session saved.[/]")

        elif command == "/quit":
            self.exit()

        elif command == "/checkpoint":
            desc = parts[1].strip() if len(parts) > 1 else "Checkpoint thủ công"
            chat.write(f"[#FFFFFF]>> Đang tạo checkpoint: {desc}...[/]")
            try:
                from core.services.checkpoint_service import CheckpointService
                svc = CheckpointService(self.config.project_root)
                cp_id = svc.create_checkpoint(desc, "USER")
                if cp_id:
                    chat.write(f"[#E0E0E0]✔ Đã tạo checkpoint {cp_id} thành công![/]")
                    self._update_timeline_ui()
                else:
                    chat.write("[#f43f5e][ERR] Tạo checkpoint thất bại![/]")
            except Exception as e:
                chat.write(f"[#f43f5e][ERR] Lỗi tạo checkpoint: {e}[/]")

        elif command == "/blueprint":
            chat.write("[#FFFFFF]>> Đang phân tích mã nguồn và cập nhật Bản thiết kế (Project Blueprint)...[/]")
            try:
                from core.services.blueprint_service import BlueprintService
                svc = BlueprintService(self.config.project_root)
                proj_map = svc.build_blueprint()
                chat.write(f"[#E0E0E0]✔ Đã cập nhật Bản thiết kế thành công! Đã lập chỉ mục {len(proj_map)} file chứa Class/Function.[/#E0E0E0]")
                chat.write("Xem chi tiết tại tệp tin: [cyan].orca/project_blueprint.md[/cyan]")
            except Exception as e:
                chat.write(f"[#f43f5e][ERR] Lỗi cập nhật Bản thiết kế: {e}[/]")

        else:
            chat.write(f"[#CCCCCC]Unknown command: {command}[/]")

    async def run_agent(self, user_prompt: str) -> None:
        if self._agent is None:
            callbacks = self._make_callbacks()
            self._agent = AgentController(self.config, callbacks=callbacks)
        else:
            self._agent.callbacks = self._make_callbacks()

        self._agent.mode = self.mode
        self._agent.security_svc._auto_approve = (self.mode == ExecutionMode.AUTO)

        loop = asyncio.get_running_loop()
        self._agent_task = loop.run_in_executor(
            None,
            lambda: asyncio.run(self._agent.run(user_prompt))
        )
        try:
            await self._agent_task
        except asyncio.CancelledError:
            pass
        finally:
            self._agent_task = None

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-toggle-mode":
            if self.mode == ExecutionMode.PLAN:
                self.mode = ExecutionMode.AUTO
            elif self.mode == ExecutionMode.AUTO:
                self.mode = ExecutionMode.CHAT
            else:
                self.mode = ExecutionMode.PLAN

            mode_labels = {
                ExecutionMode.PLAN: ("Mode: Plan", "[#CCCCCC]Chế độ Plan được BẬT. AI sẽ lập kế hoạch và đợi bạn duyệt từng bước trước khi thực hiện.[/]"),
                ExecutionMode.AUTO: ("Mode: Auto", "[#E0E0E0]Chế độ Auto được BẬT. AI toàn quyền tự động đọc/ghi file, chạy lệnh — không cần hỏi.[/]"),
                ExecutionMode.CHAT: ("Mode: Chat", "[#FFFFFF]Chế độ Chat được BẬT. AI chỉ thảo luận, hướng dẫn — không thay đổi file.[/]"),
            }
            label, msg = mode_labels.get(self.mode, (f"Mode: {self.mode.name.title()}", ""))
            event.button.label = label
            chat = self.query_one(ChatPanel)
            if msg:
                chat.write(msg)
                
        elif event.button.id == "btn-topbar-settings":
            self.handle_command("/setup")

        elif event.button.id == "btn-send":
            self.trigger_submit()

        elif event.button.id == "btn-stop":
            if self.is_processing and self._agent:
                self._agent.stop()
                self._add_system_log("[#CCCCCC]USER:[/] Stopped agent execution request")
                self.query_one(ChatPanel).write("[#CCCCCC]Stopping agent...[/]")

        elif event.button.id == "btn-timeline-rollback":
            if self.is_processing:
                self.query_one(ChatPanel).write("[#f43f5e][ERR] Không thể rollback khi AI đang chạy![/]")
                return
            
            try:
                timeline_list = self.query_one("#timeline-list", ListView)
                selected_index = timeline_list.index
                if selected_index is None or selected_index < 0:
                    self.query_one(ChatPanel).write("[#CCCCCC][WARN] Vui lòng chọn một Checkpoint từ danh sách TIMELINE.[/]")
                    return
                
                from core.services.checkpoint_service import CheckpointService
                svc = CheckpointService(self.config.project_root)
                checkpoints = svc.list_checkpoints()
                if selected_index >= len(checkpoints):
                    return
                cp = checkpoints[selected_index]
                cp_id = cp["id"]
            except Exception as e:
                self._add_system_log(f"[#f43f5e]ERROR:[/] timeline selection error: {e}")
                return

            try:
                svc.create_checkpoint(f"Trước khi rollback về [{cp.get('time_display')}]", "USER")
            except Exception:
                pass

            def close_dbs():
                if self._agent:
                    self._agent.long_memory.close()
                self.long_memory = None
                
            chat = self.query_one(ChatPanel)
            chat.write(f"[#CCCCCC]>> Đang khôi phục Workspace về Checkpoint [{cp.get('time_display')}]...[/]")
            
            try:
                success = svc.rollback_to(cp_id, on_db_close_callback=close_dbs)
            except Exception as exc:
                chat.write(f"[#f43f5e][ERR] Lỗi rollback: {exc}[/]")
                success = False

            if success:
                from core.memory_manager import MemoryManager
                mm = MemoryManager(self.config.project_root)
                self.chat_history = mm.load_chat_history()
                
                # Reset agent in-memory state to prevent context poisoning
                if self._agent:
                    self._agent.conversation_cache.clear()
                    self._agent.session_vm.clear_history()
                    try:
                        self._agent.long_memory._ensure_schema()
                    except Exception:
                        pass
                
                chat.clear()
                chat.write("[#E0E0E0]✔ Đã phục hồi Workspace & Lịch sử hội thoại thành công![/]")
                for msg in self.chat_history:
                    role = msg.get("role")
                    content = msg.get("content")
                    if role == "user":
                        chat.write_user_message(content)
                    elif role == "assistant":
                        chat.write_ai_response(content)
                
                self._update_timeline_ui()
                self._update_files_list_ui()
                self._add_system_log(f"[#E0E0E0]ROLLBACK:[/] Rolled back to checkpoint {cp_id}")
            else:
                chat.write("[#f43f5e][ERR] Khôi phục Workspace thất bại![/]")

        elif event.button.id == "btn-timeline-viewcode":
            try:
                timeline_list = self.query_one("#timeline-list", ListView)
                selected_index = timeline_list.index
                if selected_index is None or selected_index < 0:
                    self.query_one(ChatPanel).write("[#CCCCCC][WARN] Vui lòng chọn một Checkpoint từ danh sách TIMELINE.[/]")
                    return
                
                from core.services.checkpoint_service import CheckpointService
                svc = CheckpointService(self.config.project_root)
                checkpoints = svc.list_checkpoints()
                if selected_index >= len(checkpoints):
                    return
                cp = checkpoints[selected_index]
            except Exception:
                return

            chat = self.query_one(ChatPanel)
            chat.write(f"[#FFFFFF]Checkpoint [{cp.get('time_display')}] chứa các file:[/#FFFFFF]")
            files = cp.get("workspace_files", [])
            if not files:
                chat.write("  (Không có file nào hoặc danh sách trống)")
            else:
                for f in files[:30]:
                    chat.write(f"  * [cyan]{f}[/cyan]")
                if len(files) > 30:
                    chat.write(f"  ... và {len(files) - 30} file khác.")

    def on_select_changed(self, event: Select.Changed) -> None:
        if getattr(self, "_syncing_select", False):
            return
        if event.select.id == "topbar-select-provider" and event.value is not None:
            new_provider = str(event.value)
            if new_provider == "claude":
                new_provider = "anthropic"
            if new_provider == self.config.model.provider:
                return
            if new_provider != str(event.select.value):
                return
            pip_pkg = get_provider_pip_package(new_provider)
            if pip_pkg:
                import_name = get_provider_package(new_provider) or pip_pkg
                try:
                    __import__(import_name)
                except ImportError:
                    try:
                        select_provider = self.query_one("#topbar-select-provider")
                        select_provider.value = self.config.model.provider
                    except Exception:
                        pass
                    modal = InstallPromptModal(new_provider, pip_pkg)
                    self.push_screen(modal, callback=lambda ok: self._on_install_done(ok, new_provider, pip_pkg))
                    return
            self._do_provider_switch(new_provider)
        elif event.select.id == "topbar-select-model" and event.value is not None:
            try:
                if self.query_one("#topbar-select-model").has_class("hidden"):
                    return
            except Exception:
                pass
            new_model = str(event.value)
            if new_model == self.config.model.model:
                return
            self.config.model.model = new_model
            self._save_config(
                api_key=self.config.model.api_key,
                provider=self.config.model.provider,
                apply_project=False,
                base_url=self.config.model.base_url,
                model=new_model,
            )
            chat = self.query_one(ChatPanel)
            chat.write(f"[#FFFFFF]Đã chuyển đổi mô hình AI sang: {new_model}[/]")

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if event.text_area.id == "composer-input":
            text_val = event.text_area.text
            if len(text_val) > 5000:
                event.text_area.clear()
                event.text_area.insert(text_val[:5000])
                return
            self.handle_autocomplete(event.text_area)

    def get_project_files(self) -> list[str]:
        if hasattr(self, "_project_files_cached") and self._project_files_cached is not None:
            return self._project_files_cached
        
        try:
            from pathlib import Path
            from core.services.context_service import ContextService
            ctx_svc = ContextService(self.config.project_root or ".")
            files = ctx_svc._get_all_files()
            root = Path(self.config.project_root or ".").resolve()
            rel_files = []
            for f in files:
                try:
                    rel = str(f.resolve().relative_to(root)).replace("\\", "/")
                    rel_files.append(rel)
                except Exception:
                    pass
            self._project_files_cached = sorted(rel_files)
            return self._project_files_cached
        except Exception:
            return []

    def get_command_list(self) -> list[str]:
        """Return available slash commands for autocomplete."""
        from core.commands import COMMANDS
        return sorted(COMMANDS.keys())

    def handle_autocomplete(self, text_area: TextArea) -> None:
        try:
            row, col = text_area.cursor_location
            line_text = text_area.document.get_line(row)
            prefix = line_text[:col]
            
            suggestions = self.query_one("#file-suggestions", ListView)
            
            # Try @file autocomplete first (mid-line or start)
            file_match = re.search(r'(?:(?<=^)|(?<=\s))@([a-zA-Z0-9_\-./\\]*)$', prefix)
            if file_match:
                query = file_match.group(1)
                files = self.get_project_files()
                matching_files = [f for f in files if query.lower() in f.lower()]
                matching_files = matching_files[:15]
                
                if matching_files:
                    suggestions.clear()
                    for f in matching_files:
                        suggestions.append(ListItem(Label(f)))
                    suggestions.display = True
                    suggestions.index = 0
                else:
                    suggestions.display = False
                return
            
            # Try /command autocomplete (only at start of line)
            cmd_match = re.match(r'^/([a-zA-Z-]*)$', prefix)
            if cmd_match:
                query = cmd_match.group(1).lower()
                commands = self.get_command_list()
                matching_cmds = [c for c in commands if query in c.lower()]
                matching_cmds = matching_cmds[:15]
                
                if matching_cmds:
                    suggestions.clear()
                    for cmd in matching_cmds:
                        from core.commands import COMMANDS
                        desc = COMMANDS.get(cmd, "")
                        suggestions.append(ListItem(Label(f"{cmd}  —  {desc}")))
                    suggestions.display = True
                    suggestions.index = 0
                else:
                    suggestions.display = False
                return
            
            suggestions.display = False
        except Exception as e:
            self._add_system_log(f"Autocomplete error: {e}")

    def select_suggestion(self) -> None:
        try:
            suggestions = self.query_one("#file-suggestions", ListView)
            if not suggestions.display or suggestions.index is None:
                return
            selected_item = suggestions.children[suggestions.index]
            label = selected_item.query_one(Label)
            filename = label.content
            self.insert_selected_suggestion(filename)
        except Exception as e:
            self._add_system_log(f"Failed to select suggestion: {e}")

    def insert_selected_suggestion(self, label_text: str) -> None:
        try:
            text_area = self.query_one("#composer-input", TextArea)
            row, col = text_area.cursor_location
            line_text = text_area.document.get_line(row)
            prefix = line_text[:col]
            
            # Detect if it's a command suggestion or file suggestion
            cmd_match = re.match(r'^/([a-zA-Z-]*)$', prefix)
            file_match = re.search(r'(?:(?<=^)|(?<=\s))@([a-zA-Z0-9_\-./\\]*)$', prefix)
            
            if cmd_match:
                # Command — extract just the command name from "`/command` — desc"
                cmd_name = label_text.split()[0]
                start_col = 0
                end_col = col
                replacement = cmd_name + " "
                text_area.replace(replacement, (row, start_col), (row, end_col))
                text_area.move_cursor((row, start_col + len(replacement)))
            elif file_match:
                start_col = file_match.start()
                end_col = col
                replacement = f"@{label_text} "
                text_area.replace(replacement, (row, start_col), (row, end_col))
                text_area.move_cursor((row, start_col + len(replacement)))
            
            suggestions = self.query_one("#file-suggestions", ListView)
            suggestions.display = False
            
            text_area.focus()
        except Exception as e:
            self._add_system_log(f"Failed to insert suggestion: {e}")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id == "file-suggestions":
            label = event.item.query_one(Label)
            self.insert_selected_suggestion(label.content)

    def action_clear_chat(self) -> None:
        self.query_one(ChatPanel).clear()

    def action_save_session(self) -> None:
        from core.memory_manager import MemoryManager
        mm = MemoryManager(self.config.project_root or ".")
        mm.save_chat_history(self.chat_history)
        self.query_one(ChatPanel).write("[#E0E0E0]Session saved.[/]")

    def action_submit(self) -> None:
        self.trigger_submit()

    def action_stop_execution(self) -> None:
        if self.is_processing and self._agent:
            self._agent.stop()
            if hasattr(self, '_agent_task') and self._agent_task:
                self._agent_task.cancel()
            self._add_system_log("[#CCCCCC]USER:[/] Stopped agent execution request")
            self.query_one(ChatPanel).write("[#CCCCCC]Stopping agent...[/]")

    def on_key(self, event) -> None:
        if event.key == "ctrl+d":
            event.prevent_default()
            event.stop()
            self.action_stop_execution()

    @work
    async def _init_blueprint_worker(self) -> None:
        self._add_system_log("[#AAAAAA]>> Đang khởi tạo Bản thiết kế dự án (Project Blueprint)...[/]")
        try:
            from core.services.blueprint_service import BlueprintService
            import asyncio
            svc = BlueprintService(self.config.project_root)
            loop = asyncio.get_event_loop()
            proj_map = await loop.run_in_executor(None, svc.build_blueprint)
            self._add_system_log(f"[#E0E0E0]✔ Bản thiết kế dự án đã sẵn sàng! Đã quét {len(proj_map)} file chứa Class/Function.[/]")
        except Exception as e:
            self._add_system_log(f"[#f43f5e][ERR] Lỗi tạo Bản thiết kế: {e}[/]")




# ───────────────────────────────────────────
#  ENTRY POINT
# ───────────────────────────────────────────

def run_tui(config=None):
    """Launch the TUI application."""
    import sys
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.kernel32.SetConsoleCP(65001)
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        # Enable ANSI escape sequence processing (Virtual Terminal).
        # Without this, Textual's ANSI sequences may not render correctly
        # on Windows consoles, causing garbled display after extended use.
        try:
            STD_OUTPUT_HANDLE = -11
            handle = ctypes.windll.kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
            ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            mode = ctypes.c_uint32()
            ctypes.windll.kernel32.GetConsoleMode(handle, ctypes.byref(mode))
            ctypes.windll.kernel32.SetConsoleMode(handle, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING)
        except Exception:
            pass

    app = OrcaTUI(config=config)
    app.run()