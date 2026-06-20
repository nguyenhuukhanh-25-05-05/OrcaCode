"""Main Agent Controller - orchestrates AI, services, and UI."""
import os
import re
import json
import time
import hashlib
import logging
import asyncio
import threading
import traceback
from pathlib import Path
from typing import Optional

logger = logging.getLogger("orca.agent")
from rich.console import Console
from rich.panel import Panel

from config.settings import AppConfig
from core.cache import ConversationCache
from core.models import SessionState, ExecutionMode, AgentState, HierarchicalPlan, PlanMilestone, PlanTask
from core.prompts import CHAT_SYSTEM_PROMPT, SYSTEM_PROMPT_EXECUTE, SYSTEM_PROMPT_PLAN, SYSTEM_PROMPT_DESIGN
from core.services.intent_router import IntentRouter, IntentResult

from core.ui import StatusBar
from core.pricing import callback_accepts_token_context
from core.evidence import EvidenceManager, ProjectDetector, BuildRunner, LintRunner, TypeCheckRunner, TestRunner, DoneConditions
from core.agent_utils import AppCallbacks, _create_client, _call_ai, _call_ai_stream, _unpack_ai_result, CallCounter, llm_call_counter
from core.constants import (MAX_EXECUTE_ITERATIONS, MAX_FIX_ITERATIONS, MAX_CONSECUTIVE_FAILURES,
                             TOOL_TAG_RE, TOOL_TAG_OPEN_RE, ANGLE_BRACKET_RE,
                             DONE_TAG_RE, PLAN_DONE_TAG_RE, CODE_BLOCK_RE, MULTI_NEWLINE_RE)

_MAX_BUILD_FAILURES = 3
from core.agent_tools import ToolExecutorMixin
from core.diagnostic_mixin import DiagnosticMixin
from core.reviewer import ReviewerAgent
from core.reviewer.security import SecurityScanner
from core.validator import SchemaValidator, ValidationResult, ResultValidator
from core.services.error_classifier import ErrorClassifier, ErrorCategory
from core.services.loop_detector import LoopDetector
from core.services.recovery import CheckpointManager
from core.services.dependency_graph import DependencyGraph

console = Console()




class AgentController(ToolExecutorMixin, DiagnosticMixin):
    def __init__(self, cfg: AppConfig, callbacks: AppCallbacks | None = None):
        self.cfg = cfg
        self.callbacks = callbacks or AppCallbacks()
        self.session = SessionState(current_project=cfg.project_root)
        self.client = None
        self.conversation_cache = ConversationCache(max_size=50, ttl=3600)
        self.spinner = StatusBar()
        self.mode = ExecutionMode.PLAN
        self.interrupted = False
        self._agent_state = AgentState.IDLE
        self._interrupt_event = threading.Event()
        self._cached_project_tree: str | None = None
        self._cached_project_tree_mtime: float = 0
        self._init_services()

    @property
    def _project_root(self) -> Path:
        return Path(self.cfg.project_root) if self.cfg.project_root else Path(".")

    def _init_services(self):
        """Explicitly initialize all service attributes — no magic __getattr__ delegation."""
        root = self.cfg.project_root
        cb = self.callbacks

        self.context_svc = self._import_and_build("core.services.context_service", "ContextService",
            root, self.cfg.patch.max_search_files, self.cfg.patch.max_context_lines)
        self.checkpoint_svc = self._import_and_build("core.services.checkpoint_service", "CheckpointService", root)
        self.blueprint_svc = self._import_and_build("core.services.blueprint_service", "BlueprintService", root)
        self.patch_svc = self._import_and_build("core.services.patch_service", "PatchService", root)
        self.anchor_patcher = self._import_and_build("core.services.anchor_patcher", "AnchorPatcher", root)
        self.section_parser = self._import_and_build("core.services.section_parser", "SectionParser")
        self.smart_context = self._import_and_build("core.services.smart_context", "SmartContext", root)
        self.security_svc = self._import_and_build("core.services.security_service", "SecurityService",
            approval_callback=cb.request_approval)
        self.session_vm = self._import_and_build("core.viewmodels.session_vm", "SessionViewModel", self.session)
        self.patch_vm = self._import_and_build("core.viewmodels.patch_vm", "PatchViewModel")
        self.memory = self._import_and_build("core.memory_manager", "MemoryManager", root)
        self.long_memory = self._import_and_build("core.services.long_memory", "LongMemory", root)
        self.plugin_svc = self._import_and_build("core.services.plugin_service", "PluginService")
        self.debug_svc = self._import_and_build("core.services.debug_service", "DebugService", root)
        self.confidence_scorer = self._import_and_build("core.services.confidence_scorer", "ConfidenceScorer")
        self.risk_checker = self._import_and_build("core.services.risk_checker", "RiskChecker")
        self.evidence_collector = self._import_and_build("core.services.evidence_collector", "EvidenceCollector", root)
        self.done_condition_parser = self._import_and_build("core.services.done_condition", "DoneConditionParser")
        self.done_condition_verifier = self._import_and_build("core.services.done_condition", "DoneConditionVerifier")
        self.retry_strategy = self._import_and_build("core.services.retry_contract", "RetryStrategy")
        self.intent_router = IntentRouter()
        self.world_model = self._import_and_build("core.services.world_model", "WorldModel", root)
        self.error_pipeline = self._import_and_build("core.services.error_pipeline", "ErrorPipeline",
            project_root=root, max_fix_rounds=3,
            on_status=lambda s: cb.on_status(s), on_log=lambda s: None,
        )
        self.file_backup = self._import_and_build("core.services.file_backup", "FileBackup", root)
        self.structural_validator = self._import_and_build("core.services.structural_validator", "StructuralValidator")
        self.evidence_manager = EvidenceManager(root)
        self.security_scanner = SecurityScanner()
        self._tool_registry = self._init_tool_registry()
        self._rollback_stack: list[dict[str, tuple[str, str]]] = []  # [{filename: (old_content, new_content)}]
        self._codebase_outline = self._import_and_build("core.services.codebase_outline", "CodebaseOutline", root)
        # Recovery Checkpoint + Dependency Graph
        self.checkpoint_mgr = CheckpointManager(project_root=root)
        self.dep_graph = DependencyGraph(project_root=root)
        self._dep_graph_built = False
        # Plan Validator
        self._plan_validator = self._import_and_build("core.services.plan_validator", "PlanValidator", root)
        # Semantic Damage Detector
        self.semantic_detector = self._import_and_build("core.services.semantic_detector", "SemanticDetector")
        # Evidence Baseline
        self.evidence_baseline = self._import_and_build("core.evidence.baseline", "EvidenceBaseline", root)
        # Done Condition Engine
        self.done_engine = self._import_and_build("core.services.done_engine", "DoneConditionEngine", root)
        self._verification_plan: list = []
        # Exported API Registry
        from core.services.api_registry import ApiRegistry
        self.api_registry = ApiRegistry()
        self.api_registry.build(root)
        # Symbol-level Dependency Graph
        from core.services.symbol_dep_graph import SymbolDepGraph
        self.symbol_dep_graph = SymbolDepGraph()
        self._symdep_built = False
        # Iteration Quality Scorer
        from core.services.iteration_scorer import IterationScorer
        self.iteration_scorer = IterationScorer()
        # Goal Drift Detector
        from core.services.goal_drift import GoalDriftDetector
        self.goal_drift = GoalDriftDetector()
        # Code Quality Checker (Architecture Rules + Complexity + Debt + Duplicate)
        from core.services.code_quality import CodeQualityChecker
        self.code_quality = CodeQualityChecker()
        self._last_quality_scan_iteration = 0
        self._last_qc_report = None
        # Design Review Agent (advisory only, deterministic)
        from core.services.review_agent import DesignReviewer
        self.design_reviewer = DesignReviewer()
        self._last_dr_report = None
        # Knowledge Freshness (stale detection for dep_graph/symdep/api)
        from core.services.knowledge_freshness import KnowledgeFreshness
        self.knowledge_freshness = KnowledgeFreshness(
            project_root=self._project_root,
            dep_graph=self.dep_graph,
            symbol_dep_graph=self.symbol_dep_graph,
            api_registry=self.api_registry,
        )
        # Architecture Decision Log (ADR)
        from core.services.arch_commitment import DecisionLog
        self.decision_log = DecisionLog(path=self._project_root / ".opencode" / "adr.json")
        # Plan Drift Detector
        from core.services.plan_drift import PlanDriftDetector
        self.plan_drift = PlanDriftDetector()
        # Anti-Pattern Detector
        from core.services.anti_pattern import scan_files, format_anti_patterns
        self._anti_pattern_scan = scan_files
        self._anti_pattern_format = format_anti_patterns

    @staticmethod
    def _import_and_build(module_path: str, class_name: str, *args, **kwargs):
        import importlib
        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name)
        return cls(*args, **kwargs)

    def _emit_tokens_used(self, prompt_tokens: int, completion_tokens: int,
                          provider: str, model: str) -> None:
        callback = self.callbacks.on_tokens_used
        if callback_accepts_token_context(callback):
            callback(prompt_tokens, completion_tokens, provider, model)
        else:
            callback(prompt_tokens, completion_tokens)

    def stop(self):
        """Interrupt and stop agent execution."""
        self.interrupted = True
        # Persist execution state for potential resume
        try:
            exec_msgs = getattr(self, "_exec_messages", None)
            if exec_msgs is not None:
                modified = getattr(self, "_exec_modified_files_holder", set()) or set()
                plan = getattr(self.session, "execution_approved_plan", "")
                self.session_vm.save_execution_context(
                    exec_msgs, modified,
                    getattr(self, "mode", ExecutionMode.PLAN).name,
                    plan
                )
        except Exception:
            pass
        # Signal interrupt event to unblock any waiting modal queues
        if hasattr(self, "_interrupt_event"):
            self._interrupt_event.set()

    def _is_interrupted(self) -> bool:
        return getattr(self, "interrupted", False)

    def shutdown(self):
        """Release service resources (DB connections, etc.)."""
        try:
            self.long_memory.close()
        except Exception:
            pass
        self.client = None

    def _transition_to(self, new_state: AgentState, reason: str = "") -> None:
        """Transition agent to a new state with logging."""
        if self._agent_state == new_state:
            return
        old = self._agent_state.name
        self._agent_state = new_state
        cb = getattr(self, "callbacks", None)
        if cb and hasattr(cb, "on_status"):
            msg = f"State: {old} → {new_state.name}"
            if reason:
                msg += f" ({reason})"
            cb.on_status(msg)

    async def run(self, user_prompt: str) -> None:
        """Entry point: classifies intent, then dispatches to the right handler."""
        self._transition_to(AgentState.IDLE, "bắt đầu task mới")
        if not self.cfg.model.api_key:
            msg = "API key not found! Set ORCA_API_KEY in .env or run 'orca setup'"
            self.callbacks.on_error(msg)
            return

        self.interrupted = False
        self.security_svc.session_approved_build = False
        if hasattr(self, "_interrupt_event"):
            self._interrupt_event.clear()
        self.client = _create_client(self.cfg)
        self._skip_classification = False

        # ── Crash recovery: check for saved execution context ──
        saved_ctx = self.memory.load_execution_context()
        if saved_ctx and saved_ctx.get("messages") and len(saved_ctx["messages"]) > 2:
            cb = self.callbacks
            cb.on_chat("[#f59e0b]⚡ Phát hiện execution context đã lưu từ phiên trước (có thể do crash).[/#f59e0b]")
            try:
                plan_callback = getattr(cb, "request_plan_approval", None)
                import inspect
                if plan_callback is not None:
                    result = plan_callback(
                        f"Resume previous execution?\n\n"
                        f"Mode: {saved_ctx.get('mode', '?')}\n"
                        f"Files modified: {len(saved_ctx.get('modified_files', []))}\n"
                        f"Messages: {len(saved_ctx['messages'])}"
                    )
                    if inspect.isawaitable(result):
                        loop = asyncio.get_running_loop()
                        future = asyncio.run_coroutine_threadsafe(result, loop)
                        decision = future.result(timeout=600)
                    else:
                        decision = result
                else:
                    choice = input("  Resume previous execution? [Y]es / [N]o: ").strip().lower()
                    decision = "resume" if choice in ("y", "yes", "") else "cancel"

                if decision not in ("cancel", "no", "n"):
                    cb.on_chat("[#22c55e][OK] Resuming previous execution...[/#22c55e]")
                    self.memory.clear_execution_context()
                    # Restore state
                    self.session.execution_approved_plan = saved_ctx.get("approved_plan", "")
                    modified_files = set(saved_ctx.get("modified_files", []))
                    # NOTICE: Không restore mode từ saved context — giữ nguyên mode TUI đã set
                    # Mode TUI (PLAN/AUTO/CHAT) là lựa chọn chủ động của user, không bị ghi đè
                    saved_messages = saved_ctx["messages"]
                    # Add resume marker
                    saved_messages.append({
                        "role": "system",
                        "content": "[RESUME] Execution was interrupted. Continue from where you left off. Re-check file states before making changes."
                    })
                    self._skip_classification = True
                    self.resume_messages = saved_messages
                    cb.on_chat("[#888888]Đã khôi phục execution context. Đang tiếp tục...[/#888888]")
            except Exception as e:
                cb.on_chat(f"[#f59e0b][WARN] Resume failed: {e}, starting fresh.[/#f59e0b]")

        # LongMemory replaces raw execution context — load relevant history via FTS5 search
        self._prev_execution_messages = None
        self._prev_modified_files = None
        self._prev_approved_plan = None

        # Auto-generate .gitignore entries for OrcaCode directories
        try:
            proj_root = self._project_root
            gitignore = proj_root / ".gitignore"
            entries = {"# OrcaCode", ".orca/", "specs/", ".codegraph/"}
            existing = {".orca/", "specs/", ".codegraph/"}
            if gitignore.exists():
                text = gitignore.read_text(encoding="utf-8")
                missing = [e for e in entries if e not in text]
            else:
                missing = list(entries)
            if missing:
                with gitignore.open("a", encoding="utf-8") as f:
                    f.write("\n".join(["\n# OrcaCode auto-generated"] + missing + ["\n"]))
        except OSError:
            pass

        # ── Handle pending clarification from previous round ──
        if self.session.pending_clarification:
            original = self.session.pending_clarification.get("original_prompt", user_prompt)
            clarify_text = self.session.pending_clarification.get("clarify_text", "")
            self.session.pending_clarification = {}  # Clear it

            # Combine original prompt + user's answer → refined prompt
            cb = self.callbacks
            cb.on_chat(f"[#f59e0b]✏️ Đang tổng hợp yêu cầu của bạn...[/#f59e0b]")
            try:
                from core.agent_utils import _call_ai, _unpack_ai_result
                refine_prompt = (
                    f"Original request: {original}\n\n"
                    f"Clarifying question asked: {clarify_text}\n\n"
                    f"User's answer: {user_prompt}\n\n"
                    "Combine the original request and the user's answer into ONE clear, complete, "
                    "and actionable request. Include all files, technologies, and goals mentioned. "
                    "Output ONLY the combined request, no explanations."
                )
                combined, _, _, _ = _unpack_ai_result(
                    await _call_ai(self.client, self.cfg, [
                        {"role": "system", "content": "You combine user requests with clarification answers into a single clear prompt."},
                        {"role": "user", "content": refine_prompt},
                    ], on_status=lambda s: None)
                )
                user_prompt = combined.strip()
                cb.on_chat(f"[#888888]Yêu cầu đã làm rõ: {user_prompt[:200]}...[/#888888]")
            except Exception as e:
                cb.on_chat(f"[#f59e0b][WARN] Không thể tổng hợp: {e}, dùng nguyên bản.[/#f59e0b]")
                user_prompt = f"{original}\n\nBổ sung: {user_prompt}"

            # Skip intent classification — go straight to execute
            self._skip_classification = True
            # Continue to mode dispatch below

        # ── Build context from recent conversation for LLM classifier ──
        classify_context = ""
        try:
            history = self.session_vm._state.conversation_history
            if history:
                recent = history[-4:]  # Last 4 messages (2 user + 2 assistant)
                lines = []
                for msg in recent:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")[:200]
                    lines.append(f"{role}: {content}")
                if lines:
                    classify_context = "\n".join(lines)
        except Exception:
            pass

        # ── Intent routing: fast path (n-gram) → LLM (JSON + context) → CLARIFY safety net ──
        if not getattr(self, "_skip_classification", False):
            intent = self.intent_router.classify(user_prompt)
            if intent.confidence < 0.5 and self.client is not None:
                try:
                    llm_intent = await self._classify_intent_with_llm(user_prompt, classify_context)
                    if llm_intent:
                        intent = llm_intent
                except Exception:
                    pass
            self._skip_classification = False
        else:
            intent = IntentResult(intent="execute", confidence=0.9, reason="Clarified prompt — skip classification")

        # CLARIFY safety net: if confidence < 0.6, force CLARIFY to avoid wrong execution
        if intent.confidence < 0.6 and intent.intent not in ("clarify", "chat"):
            self.callbacks.on_chat(f"[#f59e0b]Em chưa rõ ý anh/chị lắm (độ chắc chắn {intent.confidence:.0%}). "
                                   f"Anh/chị muốn em tạo mới, sửa file, hay chỉ hỏi thông tin ạ?[/#f59e0b]")
            self._transition_to(AgentState.DONE, "cần clarify từ user")
            self._persist_run_state(user_prompt)
            return

        self.callbacks.on_status(f"Intent: {intent.intent} ({intent.confidence:.0%}) — {intent.reason}")

        # ── Restate & Confirm: AI paraphrases the request for user confirmation ──
        if intent.intent in ("execute", "plan") and self.client is not None:
            confirmed = await self._restate_and_confirm(user_prompt, intent)
            if not confirmed:
                self.callbacks.on_chat("[#f59e0b]Đã hủy — hãy mô tả rõ hơn yêu cầu của bạn.[/#f59e0b]")
                self._transition_to(AgentState.DONE, "user huỷ sau restate")
                self._persist_run_state(user_prompt)
                return

        if intent.intent in ("chat", "clarify"):
            if self.mode == ExecutionMode.CHAT:
                await self._handle_simple_conversation(user_prompt, intent)
            else:
                # Chat/clarify detected but not in Chat mode — still respond directly
                # instead of falling through to execution loop (wasteful).
                # The conversation log will show the intent was chat, not execute.
                self.callbacks.on_chat(f"[#888888]Intent: {intent.intent} ({intent.confidence:.0%}) — trả lời trực tiếp, không vào execution loop.[/#888888]")
                await self._handle_simple_conversation(user_prompt, intent)
            self._transition_to(AgentState.DONE, "hoàn thành tác vụ")
            self._persist_run_state(user_prompt)
            return

        if intent.intent == "undo":
            self.callbacks.on_chat("[bold #22c55e]⏪ Đang rollback thay đổi gần nhất...[/bold #22c55e]")
            result = self._tool_registry.execute("rollback", {})
            if result.get("success"):
                self.callbacks.on_chat(f"[green][OK] {result['summary']}[/green]")
            else:
                self.callbacks.on_chat(f"[#f59e0b][WARN] {result['summary']}[/#f59e0b]")
            self._transition_to(AgentState.DONE, "hoàn tác")
            self._persist_run_state(user_prompt)
            return

        if intent.intent == "plan":
            await self._generate_and_show_plan(user_prompt)
            self._transition_to(AgentState.DONE, "hoàn thành tác vụ")
            self._persist_run_state(user_prompt)
            return

        if intent.intent == "ask_permission":
            msg = f"[#ff4444][WARN] HÀNH ĐỘNG NGUY HIỂM: {intent.danger_reason}[/#ff4444]\n[#f59e0b]Bạn có chắc muốn thực hiện hành động này?[/#f59e0b]"
            self.callbacks.on_chat(msg)
            self._transition_to(AgentState.APPROVE, "chờ xác nhận hành động nguy hiểm")
            self.callbacks.on_status("⛔ Chờ user xác nhận hành động nguy hiểm...")
            try:
                plan_callback = getattr(self.callbacks, "request_plan_approval", None)
                if plan_callback is not None:
                    import inspect
                    result = plan_callback(f"Hành động nguy hiểm: {intent.danger_reason}\n\nPrompt: {user_prompt}")
                    if inspect.isawaitable(result):
                        loop = asyncio.get_running_loop()
                        decision = await asyncio.wait_for(asyncio.wrap_future(asyncio.run_coroutine_threadsafe(result, loop)), timeout=300) if loop.is_running() else await result
                    else:
                        decision = result
                else:
                    decision = self._cli_plan_approval(f"[DANGER] {intent.danger_reason}")
                if decision in ("approve", "approve_auto", "approve_step"):
                    self.callbacks.on_chat("[#22c55e][OK] User xác nhận — tiếp tục thực thi.[/#22c55e]")
                else:
                    self.callbacks.on_chat("[#f59e0b]🛑 User từ chối — hủy tác vụ.[/#f59e0b]")
                    self._transition_to(AgentState.DONE, "user từ chối")
                    self._persist_run_state(user_prompt)
                    return
            except Exception as e:
                self.callbacks.on_status(f"Permission error: {e}")
                self._transition_to(AgentState.DONE, "lỗi xác nhận")
                self._persist_run_state(user_prompt)
                return

        # ── Resume from saved execution context ──
        if getattr(self, "resume_messages", None):
            cb = self.callbacks
            cb.on_chat(f"[bold #22c55e]--- Tiếp tục thực thi từ context đã lưu ---[/bold #22c55e]")
            approved_plan = self.session.execution_approved_plan
            approved_steps = self._extract_plan_steps(approved_plan)
            max_steps = MAX_EXECUTE_ITERATIONS if self.mode == ExecutionMode.AUTO else max(25, len(approved_steps) * 4 or 10)
            self._transition_to(AgentState.EXECUTE, "resume execution")
            await self._execute_loop(self.resume_messages, max_iter=max_steps, approved_plan=approved_plan)
            self._transition_to(AgentState.VERIFY, "hậu kiểm resume")
            await self._run_post_execution_pipeline(user_prompt)
            self._transition_to(AgentState.DONE, "hoàn thành tác vụ resume")
            self._persist_run_state(user_prompt, has_execution=True)
            return

        # intent == "execute" → mode-based dispatch
        if self.mode == ExecutionMode.CHAT:
            self.callbacks.on_chat("[#f59e0b]Đang ở chế độ Chat — chỉ thảo luận, không thực thi. Chuyển sang Plan hoặc Auto để thực hiện thay đổi.[/#f59e0b]")
            await self._handle_simple_conversation(user_prompt, intent)
            self._transition_to(AgentState.DONE, "hoàn thành tác vụ")
            self._persist_run_state(user_prompt)
            return

        # ── If there's an existing plan waiting, resolve user intent ──
        try:
            if self.session.execution_approved_plan:
                resolved = await self._resolve_plan_intent(user_prompt)
                if resolved == "execute":
                    await self._execute_existing_plan(user_prompt)
                    self._transition_to(AgentState.DONE, "hoàn thành tác vụ")
                    self._persist_run_state(user_prompt, has_execution=True)
                    return
                elif resolved == "modify":
                    cb = self.callbacks
                    cb.on_chat(f"[bold #f59e0b]✏️ Cập nhật kế hoạch theo yêu cầu của bạn...[/bold #f59e0b]")
                    await self._modify_existing_plan(user_prompt)
                    self._transition_to(AgentState.DONE, "hoàn thành tác vụ")
                    self._persist_run_state(user_prompt, has_execution=True)
                    return
                elif resolved == "cancel":
                    self.callbacks.on_chat("[#f59e0b]🗑 Đã hủy kế hoạch cũ.[/#f59e0b]")
                    self.session.execution_approved_plan = ""
                else:
                    await self._handle_simple_conversation(user_prompt, intent)
                    self._transition_to(AgentState.DONE, "hoàn thành tác vụ")
                    self._persist_run_state(user_prompt)
                    return
        except Exception as exc:
            self.callbacks.on_chat(f"[#ff4444][WARN] Internal error in plan resolution: {exc}[/#ff4444]")
            logger.exception("Plan resolution failed")
            self.session.execution_approved_plan = ""

        try:
            self.checkpoint_svc.create_checkpoint(f"Trước khi chạy prompt: {user_prompt[:30]}...", "USER")
        except Exception:
            pass

        try:
            if self.mode == ExecutionMode.AUTO:
                await self._run_auto(user_prompt)
            else:
                await self._run_review(user_prompt)
        except Exception as exc:
            self.callbacks.on_chat(f"[#ff4444][WARN] Internal error: {exc} — đã log và tiếp tục.[/#ff4444]")
            logger.exception("Agent internal error in run()")

        self._transition_to(AgentState.DONE, "hoàn thành tác vụ")
        self._persist_run_state(user_prompt, has_execution=True)

    def _persist_run_state(self, user_prompt: str, has_execution: bool = False) -> None:
        """Persist long-term memory (structured, no raw tool output) + conversation history."""
        # Log execution to long-term memory only — structured, no raw ANSI/logs
        try:
            if has_execution:
                modified_files = getattr(self, "_exec_modified_files_holder", set()) or set()
                exec_summary_parts = []
                if modified_files:
                    exec_summary_parts.append("Files: " + ", ".join(sorted(modified_files)))
                if hasattr(self, "_total_tool_calls"):
                    exec_summary_parts.append(f"Tool calls: {self._total_tool_calls}")
                _llm_counter = llm_call_counter.get()
                if _llm_counter is not None and _llm_counter.count > 0:
                    llm_count = _llm_counter.count
                    exec_summary_parts.append(f"LLM calls: {llm_count}")
                    try:
                        metric_str = f"[#888888]📊 {llm_count} LLM calls · {self._total_tool_calls} tool calls"
                        self.callbacks.on_chat(metric_str + "[/#888888]")
                    except Exception:
                        pass
                summary_md = " — ".join(exec_summary_parts) if exec_summary_parts else f"Executed in {self.mode.name} mode"
                self.long_memory.complete_task(
                    name=user_prompt[:120],
                    files=list(modified_files),
                    result="success" if modified_files else "info",
                    summary_md=summary_md,
                )
        except Exception:
            pass

        # Persist conversation (user/assistant only — no tool output, no ANSI codes)
        try:
            conversation = self.session_vm._state.conversation_history
            if conversation:
                self.conversation_cache.set("chat_history", conversation)
                self.memory.save_chat_history(conversation)
        except Exception:
            pass

    # ── Direct responses for very common chat patterns (skips LLM call) ────────
    _GREETING_RESPONSES: dict[str, str] = {
        "hi": "Hi! Mình có thể giúp gì cho bạn hôm nay?",
        "hello": "Hello! How can I help you today?",
        "hey": "Hey! What can I do for you?",
        "xin chào": "Xin chào! Mình có thể giúp gì cho bạn?",
        "cảm ơn": "Không có gì ạ! Nếu có gì cần, bạn cứ nói nhé.",
        "cám ơn": "Không có gì ạ! Nếu có gì cần, bạn cứ nói nhé.",
        "thanks": "You're welcome! Let me know if you need anything else.",
        "thank you": "You're welcome! Let me know if you need anything else.",
        "bye": "Goodbye! Have a great day!",
        "tạm biệt": "Tạm biệt! Chúc bạn một ngày tốt lành!",
        "ok": "Ok! Bạn cần mình làm gì tiếp theo?",
        "okay": "Okay! What's next?",
        "ừ": "Dạ vâng ạ! Mình có thể giúp gì cho bạn?",
        "vâng": "Vâng ạ! Mình có thể giúp gì cho bạn?",
    }

    async def _handle_simple_conversation(self, user_prompt: str, intent: IntentResult | None = None) -> None:
        cb = self.callbacks

        # ── Direct response for common greetings (no LLM call) ──
        clean_prompt = user_prompt.lower().strip().rstrip(".,!?;:")
        if clean_prompt in self._GREETING_RESPONSES:
            response = self._GREETING_RESPONSES[clean_prompt]
            cb.on_status("")
            cb.on_chat(response)
            self.session_vm.add_message("user", user_prompt)
            self.session_vm.add_message("assistant", response)
            cb.on_done(0.0)
            return

        cb.on_status("AI thinking...")

        system_prompt = CHAT_SYSTEM_PROMPT

        # Load long-term memory context first (structured, not fake messages)
        memory_context = self.long_memory.build_context_for_query(user_prompt, max_tokens=1000)

        cache_key = "chat_history"
        cached = self.conversation_cache.get(cache_key)
        saved_history = cached if cached is not None else self.memory.load_chat_history()
        if cached is None:
            self.conversation_cache.set(cache_key, saved_history)
        messages = [{"role": "system", "content": system_prompt}]
        if memory_context:
            messages.append({"role": "system", "content": f"## Long-term Memory (từ các tác vụ trước):\n{memory_context}"})
        if saved_history:
            messages.extend(saved_history[-10:])
        messages.append({"role": "user", "content": user_prompt})

        try:
            provider_for_call = self.cfg.model.provider
            model_for_call = self.cfg.model.model
            response_text, prompt_tokens, completion_tokens, _meta = _unpack_ai_result(
                await _call_ai_stream(self.client, self.cfg, messages, on_chunk=cb.on_chunk, on_status=cb.on_status)
            )
            self._emit_tokens_used(prompt_tokens, completion_tokens, provider_for_call, model_for_call)
            
            # Print response to chat
            cb.on_chat(response_text)
            self.session_vm.add_message("user", user_prompt)
            self.session_vm.add_message("assistant", response_text)
        except Exception as e:
            cb.on_status(f"API error: {e}")
            cb.on_error(str(e))
        finally:
            cb.on_status("")
            cb.on_done(0.0)

    # ─── Auto Mode ────────────────────────────────────────────────────────────

    async def _run_auto(self, user_prompt: str) -> None:
        """Auto mode: full permissions, no approval needed."""
        cb = self.callbacks
        self.security_svc._auto_approve = True

        # ── Set original goal for drift detection ──
        try:
            self.goal_drift.set_goal(user_prompt)
        except Exception:
            pass

        # ── Phase 1: Intent Detection + Evidence Collection + Confidence Scoring ──
        self._transition_to(AgentState.INTENT, "phân tích ý định")
        context = ""  # will build later if needed

        # World model: understand affected components
        try:
            world = self.world_model.analyze(user_prompt)
            if world["components"]:
                cb.on_chat(f"[#888888]🌍 Phạm vi: {world['scope']} — {world['components_summary'](world['components'])}[/]")
                if world["dependencies"]:
                    cb.on_chat(f"[#888888]📦 Dependencies: {', '.join(world['dependencies'])}[/]")
        except Exception:
            pass

        # Collect evidence BEFORE scoring confidence
        self._transition_to(AgentState.EVIDENCE, "thu thập bằng chứng")
        try:
            evidence = self.evidence_collector.collect(user_prompt)
            if evidence["files_read"]:
                cb.on_chat(f"[#888888]📄 Đã đọc {len(evidence['files_read'])} file: {', '.join(evidence['files_read'][:5])}[/]")
            if evidence["error_logs"]:
                cb.on_chat(f"[#ff4444]🔴 Phát hiện {len(evidence['error_logs'])} error log[/#ff4444]")
        except Exception:
            evidence = {"files_read": [], "file_contents": {}, "error_logs": [], "findings": [], "summary": ""}

        # Score confidence based on evidence + prompt
        self._transition_to(AgentState.CONFIDENCE, "đánh giá độ chắc chắn")
        evidence_context = evidence["summary"] if evidence["files_read"] or evidence["error_logs"] else ""
        confidence = self.confidence_scorer.score_request(user_prompt, evidence_context)
        cb.on_chat(f"[#888888]📊 Độ chắc chắn: {confidence.score}% — {confidence.reason}[/]")

        # ── Phase 2: Clarify if confidence < 60% ──
        clarify_rounds = 0
        while confidence.needs_clarification and clarify_rounds < 2:
            self._transition_to(AgentState.CLARIFY, f"lần {clarify_rounds + 1}")
            cb.on_chat(f"[#f59e0b][WARN] Cần làm rõ thêm (độ chắc chắn {confidence.score}%).[/#f59e0b]")
            clarified = await self._clarify_request(user_prompt, confidence.suggested_questions)
            if clarified == "":
                # Pending clarification — waiting for user's next message
                cb.on_done(0.0)
                return
            if clarified is None:
                cb.on_done(0.0)
                return
            user_prompt = clarified
            self._transition_to(AgentState.RE_SCORE, "đánh giá lại sau clarify")
            confidence = self.confidence_scorer.score_request(user_prompt, context)
            cb.on_chat(f"[#888888]📊 Độ chắc chắn sau clarify: {confidence.score}%[/]")
            clarify_rounds += 1

        if confidence.needs_clarification:
            cb.on_chat(f"[#f59e0b]Vẫn chưa rõ yêu cầu (độ chắc chắn {confidence.score}%). Hãy nhập yêu cầu cụ thể hơn ở lượt tiếp theo.[/#f59e0b]")
            cb.on_done(0.0)
            return

        self._transition_to(AgentState.VALIDATE, "kiểm tra prerequisites")
        cb.on_status("Building context...")
        context = self._build_context(user_prompt)

        instructions = self.memory.load_instructions(user_prompt)
        mode_header = "## 🟢 CHẾ ĐỘ HIỆN TẠI: AUTO MODE — Bạn có TOÀN QUYỀN tự động, không cần hỏi user."
        system_prompt = mode_header + "\n\n" + SYSTEM_PROMPT_EXECUTE
        if instructions:
            system_prompt += f"\n\n## RULES:\n{instructions}"
        if self._should_load_design_system():
            system_prompt += f"\n\n{SYSTEM_PROMPT_DESIGN}"

        messages = [{"role": "system", "content": system_prompt}]

        # Inject previous execution context for continuity
        if self._prev_execution_messages:
            prev_summary = self._summarize_previous_execution(self._prev_execution_messages, self._prev_modified_files)
            messages.append({
                "role": "user",
                "content": f"## Previous execution context (for reference):\n{prev_summary}\n\nThis is from a previous run. Continue from where you left off."
            })

        # Detect user error reports and inject diagnostic instructions
        diagnostic_hint = self._detect_error_report(user_prompt)
        augmented_prompt = user_prompt
        if diagnostic_hint:
            augmented_prompt = f"{user_prompt}\n\n{diagnostic_hint}"

        completion_guard_prompt = self._build_completion_guard_prompt()
        messages.append({
            "role": "user",
            "content": (
                f"## Context:\n{context}\n\n"
                f"## Request:\n{augmented_prompt}\n\n"
                f"{completion_guard_prompt}"
            ),
        })
        self.session_vm.add_message("user", user_prompt)

        # ── Capture Evidence Baseline ──
        try:
            count = self.evidence_baseline.capture()
            if count > 0:
                cb = self.callbacks
                cb.on_chat(f"[#888888]📸 Evidence baseline: {count} tools captured.[/#888888]")
        except Exception:
            pass

        # In auto/continuous mode, allow up to 100 loop iterations for deep autonomous tasks.
        self._transition_to(AgentState.EXECUTE, "chạy vòng lặp thực thi")
        await self._execute_loop(messages, max_iter=MAX_EXECUTE_ITERATIONS)

        # ── Compare with baseline ──
        try:
            if self.evidence_baseline.captured:
                cb = self.callbacks
                diff = self.evidence_baseline.compare_with_current()
                if diff.has_regression():
                    for r in diff.regressions():
                        cb.on_chat(f"[#ff4444][ERR] REGRESSION: {r.tool_name} từng PASS ({r.baseline.exit_code}), giờ FAIL ({r.current.exit_code})[/#ff4444]")
        except Exception:
            pass

        # ── Run error pipeline to auto-fix remaining issues ──
        self._transition_to(AgentState.VERIFY, "chạy pipeline hậu kiểm")
        await self._run_post_execution_pipeline(user_prompt)

        # Trigger checkpoint after task completion
        try:
            self.checkpoint_svc.create_checkpoint("Sau khi hoàn thành tác vụ", "AI")
        except Exception:
            pass

    # ─── Review Mode ──────────────────────────────────────────────────────────

    async def _run_review(self, user_prompt: str) -> None:
        """Review mode: plan first, get approval, then execute step-by-step."""
        cb = self.callbacks
        self.security_svc._auto_approve = False
        self._transition_to(AgentState.VALIDATE, "kiểm tra prerequisites")

        # ── Phase 1: Generate plan ──
        self._transition_to(AgentState.PLAN, "tạo kế hoạch thực thi")
        cb.on_status("Building context...")
        context = self._build_context(user_prompt)

        instructions = self.memory.load_instructions(user_prompt)
        plan_system = SYSTEM_PROMPT_PLAN
        if instructions:
            plan_system += f"\n\n## RULES:\n{instructions}"

        diagnostic_hint = self._detect_error_report(user_prompt)
        augmented_prompt = user_prompt
        if diagnostic_hint:
            augmented_prompt = f"{user_prompt}\n\n{diagnostic_hint}"

        plan_messages = [
            {"role": "system", "content": plan_system},
            {"role": "user", "content": f"## Context:\n{context}\n\n## User request:\n{augmented_prompt}"},
        ]

        revision_count = 0
        approved_plan = None

        while not self._is_interrupted():
            cb.on_status("AI is planning..." if revision_count == 0 else "AI is revising plan...")
            try:
                provider_for_call = self.cfg.model.provider
                model_for_call = self.cfg.model.model
                ai_plan, p_tok, c_tok, _meta = _unpack_ai_result(
                    await _call_ai(self.client, self.cfg, plan_messages, on_status=cb.on_status)
                )
                self._emit_tokens_used(p_tok, c_tok, provider_for_call, model_for_call)
            except Exception as e:
                logger.error("AI error during planning: %s\n%s", e, traceback.format_exc())
                cb.on_error(f"AI error during planning: {e}")
                cb.on_done(0.0)
                return

            # Strip <PLAN_DONE/> tag for display
            plan_text = re.sub(r'\s*<PLAN_DONE\s*/>\s*', '', ai_plan, flags=re.IGNORECASE).strip()

            # Show plan in chat
            cb.on_chat(f"[bold #38bdf8]--- Ke hoach thuc thi (lan {revision_count + 1}) ---[/bold #38bdf8]")
            cb.on_chat(plan_text)

            # ── Two-Phase Review: Phase 1 — Spec Review ──
            self._transition_to(AgentState.SPEC_REVIEW, "đánh giá spec/plan trước khi phê duyệt")
            try:
                from core.services.spec_reviewer import SpecReviewer
                _spec_reviewer = SpecReviewer()
                _spec_report = _spec_reviewer.review_plan(plan_text, user_prompt)
                _spec_msg = _spec_report.format_compact()
                if _spec_msg:
                    cb.on_chat(f"<SPEC_REVIEW>{_spec_msg}</SPEC_REVIEW>")
                if not _spec_report.passed:
                    cb.on_chat(
                        f"[#ff4444]⚠️ Spec review found {_spec_report.blocking_count} blocking issue(s). "
                        f"Consider revising the plan.[/#ff4444]"
                    )
            except Exception:
                logger.exception("Spec review failed (non-fatal)")

            # ── Phase 2: Ask user to approve or revise ──
            self._transition_to(AgentState.APPROVE, "chờ người dùng phê duyệt kế hoạch")
            cb.on_status("Waiting for plan approval...")
            try:
                plan_callback = getattr(cb, "request_plan_approval", None)
                if plan_callback is not None:
                    import inspect
                    result = plan_callback(plan_text)
                    if inspect.isawaitable(result):
                        try:
                            loop = asyncio.get_running_loop()
                        except RuntimeError:
                            loop = None

                        if loop is not None and loop.is_running():
                            future = asyncio.run_coroutine_threadsafe(result, loop)
                            decision = future.result(timeout=600)
                        else:
                            decision = asyncio.run(result)
                    else:
                        decision = result
                else:
                    decision = self._cli_plan_approval(plan_text)
            except Exception as e:
                cb.on_status(f"Plan approval error: {e}")
                cb.on_error(f"Plan approval error: {e}")
                cb.on_done(0.0)
                return

            if decision in ("approve", "approve_step", "approve_auto"):
                approved_plan = plan_text
                self.mode = ExecutionMode.AUTO if decision == "approve_auto" else ExecutionMode.PLAN
                break
            elif decision == "cancel":
                cb.on_chat("[#f59e0b]Task cancelled by user.[/#f59e0b]")
                cb.on_done(0.0)
                return
            else:
                revision_count += 1
                plan_messages.append({"role": "assistant", "content": ai_plan})
                plan_messages.append({
                    "role": "user",
                    "content": f"Please revise the plan based on this feedback:\n{decision}"
                })
                continue

        if self._is_interrupted() or approved_plan is None:
            cb.on_chat("[#f59e0b]Task interrupted.[/#f59e0b]")
            cb.on_done(0.0)
            return

        # ── Phase 3: Risk check on approved plan ──
        self._transition_to(AgentState.RISK_CHECK, "kiểm tra rủi ro kế hoạch")
        try:
            risks = self.risk_checker.check_plan(approved_plan)
            high_risks = [r for r in risks if r.level in ("high", "critical")]
            if high_risks:
                for r in high_risks:
                    cb.on_chat(f"[#ff4444][WARN] RỦI RO: {r.reason}[/#ff4444]")
                cb.on_chat(f"[#f59e0b]Kế hoạch có {len(high_risks)} rủi ro cao. Đã thông báo.[/#f59e0b]")
        except Exception:
            pass

        # ── Phase 4: Define Done Conditions ──
        self._transition_to(AgentState.DONE_CONDITION, "xác định điều kiện hoàn thành")
        try:
            done_conditions = self.done_condition_parser.extract_from_plan(approved_plan)
            if done_conditions:
                cb.on_chat(f"[#888888]🎯 Done conditions ({len(done_conditions)}):[/#888888]")
                for dc in done_conditions:
                    cb.on_chat(f"[#888888]  - {dc.description} ({dc.check_type})[/#888888]")
                self._done_conditions = done_conditions
            else:
                self._done_conditions = []
                cb.on_chat(f"[#888888]🎯 Không phát hiện done condition trong plan — sẽ dùng TASK_REVIEW làm tiêu chí.[/#888888]")
        except Exception:
            self._done_conditions = []

        # ── Phase 5: Execute the approved plan ──
        try:
            self.checkpoint_svc.create_checkpoint("Sau khi duyệt kế hoạch", "USER")
        except OSError:
            pass

        cb.on_chat("[bold #22c55e]Plan approved! Starting execution...[/bold #22c55e]")
        cb.on_status("Executing plan...")

        if self.mode == ExecutionMode.AUTO:
            self.security_svc._auto_approve = True
            cb.on_chat("[#22c55e]Chế độ tự động thực thi (Auto) được BẬT. AI sẽ tự động chạy tất cả các bước.[/]")
        else:
            self.security_svc._auto_approve = False
            cb.on_chat("[#f59e0b]Chế độ duyệt từng bước (Step-by-Step) được BẬT. Mỗi bước sửa đổi sẽ cần bạn phê duyệt.[/]")

        instructions = self.memory.load_instructions(user_prompt)
        mode_header = "## 🔴 CHẾ ĐỘ HIỆN TẠI: PLAN MODE — Thực thi từng bước, mỗi bước đều được user duyệt."
        exec_system = mode_header + "\n\n" + SYSTEM_PROMPT_EXECUTE
        if instructions:
            exec_system += f"\n\n## RULES:\n{instructions}"
        if self._should_load_design_system():
            exec_system += f"\n\n{SYSTEM_PROMPT_DESIGN}"

        context = self._build_context(user_prompt)
        completion_guard_prompt = self._build_completion_guard_prompt()
        plan_guard_prompt = self._build_plan_guard_prompt(approved_plan)
        exec_messages = [
            {"role": "system", "content": exec_system},
        ]

        # Inject previous execution context for continuity
        if self._prev_execution_messages:
            prev_summary = self._summarize_previous_execution(self._prev_execution_messages, self._prev_modified_files)
            exec_messages.append({
                "role": "user",
                "content": f"## Previous execution context (for reference):\n{prev_summary}\n\nThis is from a previous run. Continue from where you left off."
            })

        exec_messages.append({"role": "user", "content": (
            f"## Context:\n{context}\n\n"
            f"## Original request:\n{self._smart_truncate(user_prompt)}\n\n"
            f"## Approved plan:\n{self._format_plan_window(approved_plan)}\n\n"
            f"{completion_guard_prompt}\n\n"
            f"{plan_guard_prompt}\n\n"
            "Now execute this plan step by step using the tool tags."
        )})
        self.session_vm.add_message("user", user_prompt)
        # Set initial milestone nếu chưa bắt đầu
        if getattr(self.session, "current_milestone_index", -1) < 0:
            self.session.current_milestone_index = 0
        approved_steps = self._extract_plan_steps(approved_plan)
        max_steps = MAX_EXECUTE_ITERATIONS if self.mode == ExecutionMode.AUTO else max(25, len(approved_steps) * 4 or 10)
        self._transition_to(AgentState.EXECUTE, "thực thi kế hoạch")
        await self._execute_loop(exec_messages, max_iter=max_steps, approved_plan=approved_plan)

        # ── Phase 4: Run error pipeline to auto-fix remaining issues ──
        self._transition_to(AgentState.VERIFY, "chạy pipeline hậu kiểm")
        await self._run_post_execution_pipeline(user_prompt)

        # Trigger checkpoint after task completion
        try:
            self.checkpoint_svc.create_checkpoint("Sau khi hoàn thành tác vụ", "AI")
        except Exception:
            pass


    # ─── Error Pipeline Integration ────────────────────────────────────────────

    def _configure_pipeline(self):
        """Auto-detect build/lint commands from the project (legacy — kept for backward compat)."""
        from core.services.error_pipeline import BuildConfig
        root = str(self._project_root)
        cfg = ProjectDetector.detect(root)
        self.error_pipeline._build_steps.clear()

        if cfg.build_command:
            self.error_pipeline.add_build_step(BuildConfig(
                command=cfg.build_command, tool="generic", timeout=120,
            ))
        if cfg.typecheck_command:
            self.error_pipeline.add_build_step(BuildConfig(
                command=cfg.typecheck_command, tool="typecheck", timeout=120,
            ))
        if cfg.lint_command:
            self.error_pipeline.add_build_step(BuildConfig(
                command=cfg.lint_command, tool="linter", timeout=120,
            ))
        if cfg.test_command:
            self.error_pipeline.add_build_step(BuildConfig(
                command=cfg.test_command, tool="test", timeout=120,
            ))

    async def _run_post_execution_pipeline(self, user_prompt: str) -> None:
        """Verify task completion using evidence-based tool runners."""
        cb = self.callbacks

        # Try error pipeline first (legacy auto-fix)
        self._configure_pipeline()
        if self.error_pipeline._build_steps:
            cb.on_status("Running error pipeline...")
            cb.on_chat("[bold #38bdf8]🔄 Error Pipeline: auto-detecting and fixing...[/bold #38bdf8]")
            result = self.error_pipeline.run()
            if result.auto_fixed_count > 0:
                cb.on_chat(f"[green][OK] Pipeline auto-fixed {result.auto_fixed_count} error(s):[/green]")
                for d in result.fixed_details:
                    cb.on_chat(f"  • [{d.get('rule', '?')}] {d.get('file', '?')}:{d.get('line', '?')} — {d.get('description', d.get('action', '?'))}")
            if result.build_success:
                cb.on_chat("[green][OK] Pipeline build passed after auto-fix![/green]")
            else:
                cb.on_chat("[#f59e0b][WARN] Pipeline could not fix all errors — checking evidence...[/#f59e0b]")

        # Evidence-based verification
        conditions = await self._verify_with_evidence()
        if conditions.all_pass():
            cb.on_chat("[green][OK] All evidence checks pass![/green]")
            cb.on_done(0.0)
            return

        failures = conditions.failures()
        cb.on_chat(f"[yellow][WARN] {len(failures)} evidence check(s) failed — feeding to AI...[/yellow]")
        cb.on_status("Feeding evidence failures to AI...")

        instructions = self.memory.load_instructions(user_prompt)
        fix_context = self._build_context(user_prompt)
        completion_guard_prompt = self._build_completion_guard_prompt()
        fix_messages = [
            {"role": "system", "content": SYSTEM_PROMPT_EXECUTE + (f"\n\n## RULES:\n{instructions}" if instructions else "") + (f"\n\n{SYSTEM_PROMPT_DESIGN}" if self._should_load_design_system() else "")},
            {"role": "user", "content": (
                f"The following evidence checks failed after execution:\n\n"
                f"{conditions.summary()}\n\n"
                f"## Original request:\n{self._smart_truncate(user_prompt)}\n\n"
                f"## Context:\n{fix_context}\n\n"
                "Fix the issues above and ensure all checks pass. "
                "Use <PATCH_FILE> or <WRITE_FILE> to fix them. "
                f"{completion_guard_prompt}\n\n"
                "End with <DONE/> when complete."
            )},
        ]
        await self._execute_loop(fix_messages, max_iter=MAX_FIX_ITERATIONS)
        cb.on_done(0.0)

    def _runtime_verify_files(self, modified_files: set[str]) -> list[str]:
        """Per-file runtime verification: syntax + import check cho từng file.
        Trả về list lỗi (empty = pass).
        """
        import py_compile
        import subprocess
        # Tags tự đóng — không cần kiểm tra cân bằng
        VOID_TAGS = frozenset({"br", "hr", "img", "input", "meta", "link", "area", "base", "col", "embed", "source", "track", "wbr"})
        errors = []
        for f in sorted(modified_files):
            fpath = Path(self._project_root, f)
            if not fpath.exists():
                continue
            ext = Path(f).suffix.lower()
            try:
                if ext == ".py":
                    py_compile.compile(str(fpath), doraise=True)
                elif ext == ".js":
                    result = subprocess.run(
                        ["node", "--check", str(fpath)],
                        capture_output=True, text=True, timeout=30
                    )
                    if result.returncode != 0:
                        errors.append(f"{f}: {result.stderr.strip()[:200]}")
                elif ext == ".json":
                    with open(str(fpath), "r", encoding="utf-8") as fh:
                        json.load(fh)
                elif ext == ".ts":
                    tsconfig = Path(self._project_root, "tsconfig.json")
                    cmd = ["npx", "tsc", "--noEmit", "--lib", "es2020,dom", str(fpath)]
                    if tsconfig.exists():
                        cmd = ["npx", "tsc", "--noEmit", str(fpath)]
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                    if result.returncode != 0:
                        errors.append(f"{f}: {result.stderr.strip()[:300]}")
                elif ext == ".html":
                    text = fpath.read_text(encoding="utf-8", errors="replace")
                    # Tag balance: single pass với Counter
                    from collections import Counter
                    opens = Counter()
                    closes = Counter()
                    for m in re.finditer(r'</?(\w+)[^>]*>', text):
                        tag = m.group(1).lower()
                        if m.group(0)[1] == '/':
                            closes[tag] += 1
                        elif tag not in VOID_TAGS:
                            opens[tag] += 1
                    for tag, cnt in opens.items():
                        if cnt != closes.get(tag, 0):
                            errors.append(f"{f}: tag <{tag}> mở={cnt} đóng={closes.get(tag, 0)}")
                            break
            except py_compile.PyCompileError as e:
                errors.append(f"{f}: {e}")
            except json.JSONDecodeError as e:
                errors.append(f"{f}: JSON lỗi — {e.msg}")
            except subprocess.TimeoutExpired:
                errors.append(f"{f}: timeout khi verify")
            except (ImportError, FileNotFoundError):
                pass  # node/npx không có sẵn
            except Exception as e:
                errors.append(f"{f}: {e}")
        return errors

    async def _verify_with_evidence(self, focused_files: Optional[list[str]] = None) -> DoneConditions:
        """Run project tools, record evidence, return conditions (async to avoid blocking event loop).
        focused_files: nếu cung cấp, chạy focused tests liên quan đến các file đã sửa + impacted files từ dep graph.
        """
        root = str(self._project_root)
        evidence = EvidenceManager(root)
        project = ProjectDetector.detect(root)
        cb = self.callbacks

        # Compute impacted files from dependency graph
        impacted: list[str] = []
        if focused_files and self._dep_graph_built:
            try:
                for f in focused_files:
                    deps = self.dep_graph.get_all_dependents(f, depth=1)
                    impacted.extend(d for d in deps if d not in impacted and d not in focused_files)
            except Exception:
                pass

        runners: list[tuple[str, ToolRunner]] = []
        if project.build_command:
            runners.append(("build", BuildRunner(cwd=root, command=project.build_command)))
        if project.lint_command:
            runners.append(("lint", LintRunner(cwd=root, command=project.lint_command)))
        if project.typecheck_command:
            runners.append(("typecheck", TypeCheckRunner(cwd=root, command=project.typecheck_command)))
        if project.test_command:
            runners.append(("test", TestRunner(cwd=root, command=project.test_command,
                           focused_files=focused_files, impacted_files=impacted)))

        if not runners:
            return DoneConditions()

        self._last_test_fail_count = 0
        self._last_test_total_count = 0

        for name, runner in runners:
            cb.on_status(f"Running {name}...")
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, runner.run)
            entry = evidence.record(name, result)
            # Attach test metadata if applicable
            if name == "test" and isinstance(runner, TestRunner):
                entry.test_pass_count = runner._pass_count
                entry.test_fail_count = runner._fail_count
                entry.test_total_count = runner._total_count
                entry.test_failures = runner._failures[:5]
                self._last_test_fail_count = runner._fail_count
                self._last_test_total_count = runner._total_count
                if runner._focused_files and runner._total_count:
                    cb.on_chat(f"[#38bdf8]🧪 Focused tests ({runner._total_count} tests in {len(runner._focused_files)} files): {runner.test_summary}[/#38bdf8]")
                else:
                    cb.on_chat(f"[#38bdf8]🧪 {runner.test_summary}[/#38bdf8]")
            else:
                cb.on_chat(f"[#38bdf8]🔧 {entry.summary}[/#38bdf8]")

        return evidence.build_conditions()

    # ─── Shared execution loop ────────────────────────────────────────────────

    _LEAKED_CODE_RE = re.compile(r'```[a-zA-Z0-9+#\-]*\n(?:.*\n){4,}?```', re.MULTILINE)
    _CORRECTION_MSG = (
        "CẢNH BÁO: Response vừa rồi vi phạm quy tắc — bạn đã in code vào chat dạng ```...```. "
        "Đây là nghiêm cấm và gây lãng phí token.\n"
        "Hãy làm lại NGAY BÂY GIỜ: đặt toàn bộ code vào thẻ <WRITE_FILE path=\"...\"> hoặc "
        "<PATCH_FILE path=\"...\"> và kết thúc bằng <DONE/>. "
        "KHÔNG được in bất kỳ khối ``` nào."
    )
    _NO_TOOL_MSG = (
        "CẢNH BÁO: Bạn chưa dùng công cụ nào (như <WRITE_FILE> hay <RUN_COMMAND>) và cũng chưa kết thúc bằng <DONE/>.\n"
        "Nếu bạn đang định thực thi công việc, HÃY DÙNG CÔNG CỤ NGAY BÂY GIỜ.\n"
        "Nếu đã hoàn thành TOÀN BỘ kế hoạch, hãy phản hồi với đúng 1 thẻ <DONE/>. "
        "Nếu bạn đang chờ user trả lời hoặc chọn option, hãy dùng <WAITING_USER/> thay vì im lặng."
    )
    _WAITING_USER_RE = re.compile(
        r'<WAITING_USER\s*/?>|'
        r'(?:bạn (?:muốn|chọn|nghĩ|cần)|chọn\s*(?:\d|một|loại)|vui lòng chọn|'
        r'hãy chọn|bạn thích|loại project|kiểu project|'
        r'which (?:option|type|kind)|please (?:choose|select)|would you like|'
        r'pick (?:one|an|a)|select (?:one|an|a))',
        re.IGNORECASE,
    )
    _CONVERSATIONAL_RE = re.compile(
        r'^(?:xin chào|hello|hi\b|hey|chào|vâng|dạ|ok|okay|cảm ơn|thanks|'
        r'tôi (?:là|có thể|sẵn sàng)|mình (?:là|có thể)|'
        r'I(?:\'m| am) (?:ready|here|happy)|how can I|what can I)',
        re.IGNORECASE,
    )
    _PLAN_REVIEW_RE = re.compile(r"<PLAN_REVIEW>(.*?)</PLAN_REVIEW>", re.IGNORECASE | re.DOTALL)
    _TASK_REVIEW_RE = re.compile(r"<TASK_REVIEW>(.*?)</TASK_REVIEW>", re.IGNORECASE | re.DOTALL)

    def _has_leaked_code(self, text: str) -> bool:
        """Return True if AI response contains large markdown code blocks or raw HTML source instead of tool tags."""
        if bool(self._LEAKED_CODE_RE.search(text)):
            return True
        if re.search(r'^<(div|html|body|script|style|nav|main|footer|header)\b[^>]*>\s*$', text, re.IGNORECASE | re.MULTILINE):
            return True
        return False

    def _is_awaiting_user_input(self, text: str) -> bool:
        """Detect if AI is asking user a question or waiting for selection."""
        return bool(self._WAITING_USER_RE.search(text))

    def _is_conversational_response(self, text: str, modified_files: set[str]) -> bool:
        """Detect if AI response is purely conversational (greeting, explanation) with no actionable work."""
        if modified_files:
            return False
        if self._has_leaked_code(text):
            return False
        if any(tag in text for tag in ('<WRITE_FILE', '<PATCH_FILE', '<RUN_COMMAND', '<READ_FILE', '<DONE', '<PLAN_DONE')):
            return False
        lines = [l for l in text.strip().splitlines() if l.strip()]
        if len(lines) > 20:
            return False
        if self._CONVERSATIONAL_RE.search(text):
            return True
        if text.count('?') >= 1 and len(lines) <= 8:
            return True
        return False

    def _extract_plan_steps(self, approved_plan: Optional[str]) -> list[str]:
        """Parse top-level plan steps — ưu tiên hierarchical plan (active milestone tasks)."""
        # Ưu tiên active milestone tasks
        active = self._get_active_tasks_text()
        if active:
            lines = active.splitlines()
            steps = []
            for line in lines:
                match = re.match(r"^\s*\d+\.\s*(?:`[^`]+`\s*—\s*)?(.+)$", line)
                if match:
                    steps.append(match.group(1).strip())
            return steps[:12]

        # Fallback: parse từ text plan
        if not approved_plan:
            return []
        steps: list[str] = []
        for raw_line in approved_plan.splitlines():
            stripped = raw_line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith("```"):
                continue
            match = re.match(r"^(?:[-*]|\d+[.)])\s+(.+)$", stripped)
            if not match:
                continue
            step = match.group(1).strip()
            if len(step) >= 5:
                steps.append(step)
        if not steps:
            steps = [line.strip() for line in approved_plan.splitlines() if line.strip()][:8]
        return steps[:12]

    def _build_plan_review_retry_message(self, plan_steps: list[str], reason: str) -> str:
        """Ask the AI to reconcile actual work against the approved plan before DONE."""
        checklist = "\n".join(f"- [ ] {step} | evidence: file or command" for step in plan_steps)
        return (
            f"PLAN GUARD FAILED: {reason}\n\n"
            "Trước khi dùng <DONE/>, bạn PHẢI đối chiếu Approved plan với kết quả thực tế.\n"
            "Hãy phản hồi lại theo format sau:\n"
            "<PLAN_REVIEW>\n"
            f"{checklist}\n"
            "</PLAN_REVIEW>\n\n"
            "Quy tắc:\n"
            "1. Chỉ đổi [ ] thành [x] khi bước đó đã thực sự hoàn tất.\n"
            "2. Mỗi dòng phải có evidence là file path hoặc command đã chạy.\n"
            "3. Nếu còn bất kỳ bước nào chưa xong, tiếp tục dùng tool để làm tiếp.\n"
            "4. Chỉ được dùng <DONE/> khi TẤT CẢ bước đều là [x]."
        )

    def _validate_plan_review(self, ai_msg: str, plan_steps: list[str], modified_files: set[str] | None = None) -> tuple[bool, str]:
        """Validate whether the AI reconciled the approved plan before finishing."""
        if not plan_steps:
            return True, ""
        if modified_files is not None and not modified_files and len(plan_steps) <= 3:
            return True, ""

        match = self._PLAN_REVIEW_RE.search(ai_msg)
        if not match:
            return False, self._build_plan_review_retry_message(
                plan_steps,
                "Thiếu block <PLAN_REVIEW>...</PLAN_REVIEW>.",
            )

        review_lines = [line.strip() for line in match.group(1).splitlines() if line.strip()]
        completed = [
            line for line in review_lines
            if re.search(r"\[\s*x\s*\]|\bDONE\b|\bHOÀN THÀNH\b", line, re.IGNORECASE)
        ]
        pending = [
            line for line in review_lines
            if re.search(r"\[\s*\]|\bPENDING\b|\bTODO\b|\bCHƯA\b", line, re.IGNORECASE)
        ]

        if pending or len(completed) < len(plan_steps):
            return False, self._build_plan_review_retry_message(
                plan_steps,
                "Kế hoạch chưa được reconcile đủ hoặc vẫn còn bước pending.",
            )

        return True, ""

    def _build_plan_guard_prompt(self, approved_plan: Optional[str]) -> str:
        """Build upfront execution instructions for plan reconciliation."""
        plan_steps = self._extract_plan_steps(approved_plan)
        if not plan_steps:
            return ""

        checklist = "\n".join(f"- {step}" for step in plan_steps)
        return (
            "## Plan Guard\n"
            "Bạn đang thực thi một approved plan. Không được DONE sớm.\n"
            "Trước khi dùng <DONE/>, bạn BẮT BUỘC phải thêm block sau:\n"
            "<PLAN_REVIEW>\n"
            "- [x] step | evidence: file or command\n"
            "</PLAN_REVIEW>\n\n"
            "Chỉ được đánh dấu [x] cho bước đã thật sự hoàn tất.\n"
            "Nếu còn bước chưa xong thì tiếp tục dùng tool, chưa được DONE.\n\n"
            "Approved steps to reconcile:\n"
            f"{checklist}"
        )

    def _build_task_review_retry_message(self, modified_files: set[str], reason: str) -> str:
        """Ask the AI to provide a concrete completion review before DONE."""
        file_lines = "\n".join(f"- {path}" for path in sorted(modified_files)) or "- none"
        return (
            f"DONE CONTRACT FAILED: {reason}\n\n"
            "Trước khi dùng <DONE/>, bạn PHẢI cung cấp block sau:\n"
            "<TASK_REVIEW>\n"
            "- changed_files: ...\n"
            "- checks_performed: ...\n"
            "- remaining_issues: none\n"
            "- done_condition_met: yes\n"
            "</TASK_REVIEW>\n\n"
            "Các file đã sửa trong task này:\n"
            f"{file_lines}\n\n"
            "Quy tắc:\n"
            "1. `checks_performed` phải nêu rõ bạn đã kiểm cái gì.\n"
            "2. `remaining_issues` phải là `none` nếu muốn DONE.\n"
            "3. Nếu vẫn còn lỗi hay bước thiếu, tiếp tục dùng tool để sửa, chưa được DONE."
        )

    def _validate_task_review(self, ai_msg: str, modified_files: set[str], results: list[dict]) -> tuple[bool, str]:
        """Validate the generic completion contract before accepting DONE."""
        if not modified_files and not results:
            return True, ""

        match = self._TASK_REVIEW_RE.search(ai_msg)
        if not match:
            return False, self._build_task_review_retry_message(
                modified_files,
                "Thiếu block <TASK_REVIEW>...</TASK_REVIEW>.",
            )

        review = match.group(1)
        normalized = review.lower()
        has_checks = "checks_performed:" in normalized and not re.search(
            r"checks_performed:\s*(none|n/a)?\s*$",
            review,
            re.IGNORECASE | re.MULTILINE,
        )
        no_remaining = bool(re.search(r"remaining_issues:\s*(none|không|khong)\b", review, re.IGNORECASE))
        done_met = bool(re.search(r"done_condition_met:\s*(yes|true|đạt|dat)\b", review, re.IGNORECASE))

        if not has_checks or not no_remaining or not done_met:
            return False, self._build_task_review_retry_message(
                modified_files,
                "TASK_REVIEW chưa đủ checks hoặc vẫn còn issue pending.",
            )

        if modified_files:
            mentioned = sum(1 for path in modified_files if path in review)
            if mentioned == 0:
                return False, self._build_task_review_retry_message(
                    modified_files,
                    "TASK_REVIEW không nhắc tới file nào đã sửa.",
                )

        return True, ""

    def _build_completion_guard_prompt(self) -> str:
        """Build the generic DONE contract prompt."""
        return (
            "## Completion Contract\n"
            "Trước khi DONE, nếu bạn đã sửa file hoặc chạy lệnh, hãy thêm block sau:\n"
            "<TASK_REVIEW>\n"
            "- changed_files: file1, file2 (ghi rõ component/view/service nào)\n"
            "- checks_performed: command/diagnostic/read-back đã chạy\n"
            "- remaining_issues: none\n"
            "- done_condition_met: yes\n"
            "</TASK_REVIEW>\n\n"
            "NẾU KHÔNG có file nào được sửa và không có lệnh nào chạy, bạn chỉ cần <DONE/> mà không cần TASK_REVIEW.\n\n"
            "[WARN] Mỗi file chỉ nên ≤ 200 dòng. Nếu file quá dài, dùng `mode=\"append\"` ở lượt kế tiếp để ghi tiếp. "
            "Mỗi lần chỉ nên ghi 1 component/file."
        )

    def _summarize_previous_execution(self, prev_messages: list[dict], prev_modified_files: set | None) -> str:
        try:
            parts = []
            if prev_modified_files:
                parts.append("Files đã sửa trong lần chạy trước: " + ", ".join(sorted(prev_modified_files)))
            tool_count = sum(1 for m in prev_messages if "tool_calls" in m or "results" in m.get("content", ""))
            if tool_count:
                parts.append(f"Số tool calls đã thực hiện: {tool_count}")
            last_msgs = [m.get("content", "")[:500] for m in prev_messages[-4:] if m.get("content")]
            if last_msgs:
                parts.append("Nội dung gần đây:\n" + "\n---\n".join(last_msgs))
            return "\n\n".join(parts) if parts else "Không có context từ lần chạy trước."
        except Exception:
            return "Không có context từ lần chạy trước."

    async def _classify_intent_with_llm(self, prompt: str, context: str = "") -> IntentResult | None:
        """LLM classifies intent with conversation context + JSON output validation."""
        from core.services.intent_router import LLM_CLASSIFY_PROMPT
        messages = [{"role": "system", "content": LLM_CLASSIFY_PROMPT}]
        if context:
            messages.append({"role": "user", "content": f"Conversation history:\n{context}\n\nCurrent message: {prompt}"})
        else:
            messages.append({"role": "user", "content": f"Current message: {prompt}"})
        try:
            raw, _, _, _ = _unpack_ai_result(
                await _call_ai(self.client, self.cfg, messages, on_status=lambda s: None)
            )
            return self.intent_router.parse_llm_response(raw)
        except Exception:
            pass
        return None

    async def _restate_and_confirm(self, user_prompt: str, intent: IntentResult) -> bool:
        """AI restates its understanding of the request and asks for confirmation.

        Returns True if user confirms, False if they want to revise.
        Only for execute/plan intents — prevents jumping to code without understanding.
        """
        cb = self.callbacks
        restate_prompt = (
            "Người dùng vừa yêu cầu: " + user_prompt + "\n\n"
            "Hãy diễn đạt lại yêu cầu này bằng 2-3 câu ngắn gọn để xác nhận bạn đã hiểu đúng. "
            "Kết thúc bằng câu hỏi: 'Có đúng ý bạn không?' hoặc 'Bạn muốn tôi làm gì khác không?'\n"
            "QUAN TRỌNG: Chỉ paraphrase, không code, không giải thích dài, không lên kế hoạch."
        )
        try:
            raw, _, _, _ = _unpack_ai_result(
                await _call_ai(self.client, self.cfg,
                    [{"role": "user", "content": restate_prompt}],
                    on_status=lambda s: None)
            )
            restated = raw.strip()
            if not restated:
                return True  # Fallback: proceed anyway

            cb.on_chat(f"[#38bdf8]🤔 {restated}[/#38bdf8]")

            # Ask user to confirm via the approval callback
            plan_callback = getattr(cb, "request_plan_approval", None)
            if plan_callback is not None:
                import inspect
                result = plan_callback(f"Xác nhận yêu cầu:\n\n{restated}")
                if inspect.isawaitable(result):
                    try:
                        loop = asyncio.get_running_loop()
                    except RuntimeError:
                        loop = None
                    if loop is not None and loop.is_running():
                        future = asyncio.run_coroutine_threadsafe(result, loop)
                        decision = await asyncio.wait_for(future, timeout=120)
                    else:
                        decision = await result
                else:
                    decision = result
                return decision in ("approve", "approve_step", "approve_auto")
            return True  # No callback → auto-confirm
        except Exception:
            logger.exception("Restate & Confirm failed (non-fatal)")
            return True  # Fallback: proceed

    async def _generate_and_show_plan(self, user_prompt: str) -> None:
        """Generate a plan from user prompt and display it in chat. Does NOT execute."""
        cb = self.callbacks
        plan_context = self._build_context(user_prompt)
        plan_instructions = self.memory.load_instructions(user_prompt)
        plan_system = SYSTEM_PROMPT_PLAN
        if plan_instructions:
            plan_system += f"\n\n## RULES:\n{plan_instructions}"
        plan_messages = [
            {"role": "system", "content": plan_system},
            {"role": "user", "content": f"## Context:\n{plan_context}\n\n## User request:\n{user_prompt}"},
        ]
        cb.on_status("AI is planning...")
        try:
            provider_for_call = self.cfg.model.provider
            model_for_call = self.cfg.model.model
            ai_plan, p_tok, c_tok, _meta = _unpack_ai_result(
                await _call_ai(self.client, self.cfg, plan_messages, on_status=cb.on_status)
            )
            self._emit_tokens_used(p_tok, c_tok, provider_for_call, model_for_call)
            plan_text = re.sub(r'\s*<PLAN_DONE\s*/>\s*', '', ai_plan, flags=re.IGNORECASE).strip()
        except Exception as e:
            logger.error("AI error during planning: %s\n%s", e, traceback.format_exc())
            cb.on_error(f"AI error during planning: {e}")
            cb.on_done(0.0)
            return
        # Parse hierarchical plan (JSON)
        hp, raw_json = self._extract_hierarchical_plan(ai_plan)
        if hp and raw_json:
            self.session.hierarchical_plan_json = raw_json
            self.session.current_milestone_index = -1
            display_text = self._render_hierarchical_plan(hp)
            self.session.execution_approved_plan = display_text

            # ── Plan Quality Validation ──
            try:
                plan_data = json.loads(raw_json)
                pv_result = self._plan_validator.validate_plan(plan_data)
                pv_summary = self._plan_validator.format_summary(pv_result)
                cb.on_chat(f"[#888888]{pv_summary}[/#888888]")
                if not pv_result.passed:
                    cb.on_chat(f"[#f59e0b][WARN] Plan có vấn đề nghiêm trọng. Vui lòng kiểm tra trước khi approve.[/#f59e0b]")
            except Exception:
                pass

            # ── Auto-generate done conditions ──
            try:
                plan_data = json.loads(raw_json)
                auto_conditions = self.done_condition_parser.auto_generate_from_plan_json(plan_data)
                if auto_conditions:
                    lines = ["[bold #888888]Auto-generated verification conditions:[/bold #888888]"]
                    for i, cond in enumerate(auto_conditions):
                        icon = {"file_exists": "📄", "file_contains": "🔍", "test_pass": "🧪", "command_ok": "", "manual": "[OK]"}.get(cond.check_type, "•")
                        lines.append(f"  {icon} {cond.description}")
                    cb.on_chat("\n".join(lines))
                    self._done_conditions = auto_conditions
                else:
                    self._done_conditions = []
            except Exception:
                self._done_conditions = []

            # ── Done Condition Engine: verification plan ──
            try:
                plan_data = json.loads(raw_json)
                epic = plan_data.get("epic", user_prompt)
                v_steps = self.done_engine.generate_steps(goal=epic, context=user_prompt)
                if v_steps:
                    lines = ["[bold #888888]Verification Plan (sẽ kiểm tra sau execution):[/bold #888888]"]
                    for vs in v_steps:
                        icon = {"file_exists": "📄", "content_pattern": "🔍", "build_pass": "", "command_ok": "💻", "user_confirm": "👤", "runtime_check": "🌐"}.get(vs.type, "•")
                        lines.append(f"  {icon} {vs.description}")
                    cb.on_chat("\n".join(lines))
                    self._verification_plan = v_steps
                else:
                    self._verification_plan = []
            except Exception:
                self._verification_plan = []

            cb.on_chat(f"[bold #38bdf8]--- Ke hoach (Phan tang) ---[/bold #38bdf8]")
            cb.on_chat(display_text)
            cb.on_chat(f'[#888888]📌 {len(hp.milestones)} chang, {sum(len(m.tasks) for m in hp.milestones)} tasks. Noi "thuc thi di" de bat dau.[/#888888]')
            plan_text = display_text
        else:
            # Fallback: text plan cũ
            plan_text = re.sub(r'\s*<PLAN_DONE\s*/>\s*', '', ai_plan, flags=re.IGNORECASE).strip()
            self.session.execution_approved_plan = plan_text
            cb.on_chat(f"[bold #38bdf8]--- Ke hoach ---[/bold #38bdf8]")
            cb.on_chat(plan_text)
            cb.on_chat('[#888888]Nếu muốn thực thi, hãy nói "thực thi đi" hoặc "bắt đầu thực hiện".[/#888888]')
        self.session_vm.add_message("user", user_prompt)
        self.session_vm.add_message("assistant", plan_text)
        cb.on_done(0.0)

    async def _run_plan_only(self, user_prompt: str) -> None:
        """Plan-only mode (user gọi là 'Review'): lên kế hoạch, thảo luận, hỏi đáp — KHÔNG thực thi."""
        cb = self.callbacks
        self.security_svc._auto_approve = False
        self._transition_to(AgentState.PLAN, "tạo kế hoạch (chế độ Review)")

        cb.on_status("Building context...")
        context = self._build_context(user_prompt)

        instructions = self.memory.load_instructions(user_prompt)
        plan_system = SYSTEM_PROMPT_PLAN
        if instructions:
            plan_system += f"\n\n## RULES:\n{instructions}"

        diagnostic_hint = self._detect_error_report(user_prompt)
        augmented_prompt = user_prompt
        if diagnostic_hint:
            augmented_prompt = f"{user_prompt}\n\n{diagnostic_hint}"

        plan_messages = [
            {"role": "system", "content": plan_system},
            {"role": "user", "content": f"## Context:\n{context}\n\n## User request:\n{augmented_prompt}"},
        ]

        cb.on_status("AI is planning...")
        try:
            provider_for_call = self.cfg.model.provider
            model_for_call = self.cfg.model.model
            ai_plan, p_tok, c_tok, _meta = _unpack_ai_result(
                await _call_ai(self.client, self.cfg, plan_messages, on_status=cb.on_status)
            )
            self._emit_tokens_used(p_tok, c_tok, provider_for_call, model_for_call)
        except Exception as e:
            logger.error("AI error during planning: %s\n%s", e, traceback.format_exc())
            cb.on_error(f"AI error during planning: {e}")
            cb.on_done(0.0)
            return

        # Parse hierarchical plan (JSON)
        hp, raw_json = self._extract_hierarchical_plan(ai_plan)
        if hp and raw_json:
            self.session.hierarchical_plan_json = raw_json
            self.session.current_milestone_index = -1
            plan_text = self._render_hierarchical_plan(hp)

            # ── Plan Quality Validation ──
            try:
                plan_data = json.loads(raw_json)
                pv_result = self._plan_validator.validate_plan(plan_data)
                pv_summary = self._plan_validator.format_summary(pv_result)
                cb.on_chat(f"[#888888]{pv_summary}[/#888888]")
            except Exception:
                pass

            # ── Auto-generated done conditions ──
            try:
                plan_data = json.loads(raw_json)
                auto_conditions = self.done_condition_parser.auto_generate_from_plan_json(plan_data)
                if auto_conditions:
                    lines = ["[bold #888888]Auto-generated verification conditions:[/bold #888888]"]
                    for cond in auto_conditions:
                        icon = {"file_exists": "📄", "file_contains": "🔍", "test_pass": "🧪", "command_ok": "", "manual": "[OK]"}.get(cond.check_type, "•")
                        lines.append(f"  {icon} {cond.description}")
                    cb.on_chat("\n".join(lines))
            except Exception:
                pass

            cb.on_chat(f"[bold #38bdf8]--- Ke hoach (Phân tầng, Review Mode) ---[/bold #38bdf8]")
            cb.on_chat(plan_text)
            cb.on_chat(f'[#888888]📌 {len(hp.milestones)} chặng, {sum(len(m.tasks) for m in hp.milestones)} tasks. Nói "thực thi đi" để bắt đầu.[/#888888]')
        else:
            plan_text = re.sub(r'\s*<PLAN_DONE\s*/>\s*', '', ai_plan, flags=re.IGNORECASE).strip()
            cb.on_chat(f"[bold #38bdf8]--- Ke hoach (Review Mode - Khong thuc thi) ---[/bold #38bdf8]")
            cb.on_chat(plan_text)
            cb.on_chat('[#888888]Nói "thực thi đi" để bắt đầu thực hiện kế hoạch này.[/#888888]')

        self.session.execution_approved_plan = plan_text
        self.session_vm.add_message("user", user_prompt)
        self.session_vm.add_message("assistant", plan_text)

        cb.on_done(0.0)

    async def _execute_existing_plan(self, user_prompt: str) -> None:
        """Execute a plan that was already saved in session state (from a previous 'plan' intent).
        Skips re-approval since _resolve_plan_intent() already confirmed user intent.
        """
        cb = self.callbacks
        approved_plan = self.session.execution_approved_plan

        # ── Set original goal for drift detection ──
        try:
            self.goal_drift.set_goal(user_prompt)
        except Exception:
            pass

        cb.on_status("Preparing to execute existing plan...")

        # ── Plan Quality Validation ──
        try:
            hp_json = getattr(self.session, "hierarchical_plan_json", "")
            if hp_json:
                plan_data = json.loads(hp_json)
                pv_result = self._plan_validator.validate_plan(plan_data)
                pv_summary = self._plan_validator.format_summary(pv_result)
                cb.on_chat(f"[#888888]{pv_summary}[/#888888]")
        except Exception:
            pass

        # ── Risk check ──
        self._transition_to(AgentState.RISK_CHECK, "kiểm tra rủi ro kế hoạch")
        try:
            risks = self.risk_checker.check_plan(approved_plan)
            high_risks = [r for r in risks if r.level in ("high", "critical")]
            if high_risks:
                for r in high_risks:
                    cb.on_chat(f"[#ff4444][WARN] RỦI RO: {r.reason}[/#ff4444]")
        except Exception:
            pass

        # ── Define Done Conditions ──
        self._transition_to(AgentState.DONE_CONDITION, "xác định điều kiện hoàn thành")
        try:
            # Từ hierarchical plan JSON → auto conditions
            hp_json = getattr(self.session, "hierarchical_plan_json", "")
            if hp_json:
                try:
                    plan_data = json.loads(hp_json)
                    auto_conditions = self.done_condition_parser.auto_generate_from_plan_json(plan_data)
                    if auto_conditions:
                        cb.on_chat(f"[#888888]Auto-generated ({len(auto_conditions)} conditions):[/#888888]")
                        for cond in auto_conditions:
                            cb.on_chat(f"[#888888]  • {cond.description}[/#888888]")
                        self._done_conditions = auto_conditions
                    else:
                        self._done_conditions = []
                except (json.JSONDecodeError, Exception):
                    self._done_conditions = []
            else:
                done_conditions = self.done_condition_parser.extract_from_plan(approved_plan)
                if done_conditions:
                    cb.on_chat(f"[#888888]🎯 Done conditions ({len(done_conditions)}):[/#888888]")
                    for dc in done_conditions:
                        cb.on_chat(f"[#888888]  - {dc.description} ({dc.check_type})[/#888888]")
                    self._done_conditions = done_conditions
                else:
                    self._done_conditions = []
        except Exception:
            self._done_conditions = []

        # ── Gatekeeper: show execution summary and confirm before going AUTO ──
        plan_summary = approved_plan[:300]
        plan_steps = self._extract_plan_steps(approved_plan)
        steps_summary = "\n".join(f"  • {s}" for s in plan_steps[:5])
        if len(plan_steps) > 5:
            steps_summary += f"\n  • ... and {len(plan_steps) - 5} more steps"

        cb.on_chat(f"[bold #22c55e]OrcaCode sẽ thực thi:[/bold #22c55e]")
        cb.on_chat(f"[#888888]{steps_summary}[/#888888]")

        # Ask for final confirmation before execution
        if self.mode == ExecutionMode.AUTO:
            cb.on_chat("[#f59e0b][WARN] Chế độ AUTO: AI sẽ tự động chạy tất cả các bước. Xác nhận?[/#f59e0b]")
        else:
            cb.on_chat("[#f59e0b][WARN] Chế độ PLAN: AI sẽ chạy từng bước và xin duyệt mỗi bước.[/#f59e0b]")

        try:
            plan_callback = getattr(cb, "request_plan_approval", None)
            if plan_callback is not None:
                import inspect
                result = plan_callback(f"Execute plan?\n\n{plan_summary}")
                if inspect.isawaitable(result):
                    try:
                        loop = asyncio.get_running_loop()
                    except RuntimeError:
                        loop = None
                    if loop is not None and loop.is_running():
                        future = asyncio.run_coroutine_threadsafe(result, loop)
                        decision = future.result(timeout=600)
                    else:
                        decision = asyncio.run(result)
                else:
                    decision = result
            else:
                choice = input("  Execute plan? [Y]es / [S]tep-by-step / [C]ancel: ").strip().lower()
                decision = "approve_auto" if choice in ("y", "yes", "") else "approve_step" if choice in ("s", "step") else "cancel"

            if decision == "cancel":
                cb.on_chat("[#f59e0b]🛑 Execution cancelled by user.[/#f59e0b]")
                cb.on_done(0.0)
                return
            elif decision == "approve_auto":
                self.mode = ExecutionMode.AUTO
                self.security_svc._auto_approve = True
                cb.on_chat("[#22c55e][OK] Đã xác nhận. Chế độ AUTO — AI sẽ tự động chạy tất cả các bước.[/]")
            else:
                self.mode = ExecutionMode.PLAN
                self.security_svc._auto_approve = False
                cb.on_chat("[#f59e0b][OK] Đã xác nhận. Chế độ PLAN — mỗi bước sẽ cần bạn duyệt.[/]")
        except Exception:
            cb.on_chat("[#22c55e]⏩ Tiếp tục thực thi...[/#22c55e]")
            self.mode = ExecutionMode.PLAN
            self.security_svc._auto_approve = False

        # ── Execute ──
        try:
            self.checkpoint_svc.create_checkpoint("Sau khi duyệt kế hoạch", "USER")
        except OSError:
            pass

        instructions = self.memory.load_instructions(user_prompt)
        mode_header = "## 🔴 CHẾ ĐỘ HIỆN TẠI: PLAN MODE — Thực thi từng bước, mỗi bước đều được user duyệt."
        exec_system = mode_header + "\n\n" + SYSTEM_PROMPT_EXECUTE
        if instructions:
            exec_system += f"\n\n## RULES:\n{instructions}"
        if self._should_load_design_system():
            exec_system += f"\n\n{SYSTEM_PROMPT_DESIGN}"

        context = self._build_context(user_prompt)
        completion_guard_prompt = self._build_completion_guard_prompt()
        plan_guard_prompt = self._build_plan_guard_prompt(approved_plan)
        exec_messages = [
            {"role": "system", "content": exec_system},
            {"role": "user", "content": (
                f"## Context:\n{context}\n\n"
                f"## Original request:\n{self._smart_truncate(user_prompt)}\n\n"
                f"## Approved plan:\n{self._format_plan_window(approved_plan)}\n\n"
                f"{completion_guard_prompt}\n\n"
                f"{plan_guard_prompt}\n\n"
                "Now execute this plan step by step using the tool tags."
            )},
        ]
        self.session_vm.add_message("user", user_prompt)
        # Set initial milestone nếu chưa bắt đầu
        if getattr(self.session, "current_milestone_index", -1) < 0:
            self.session.current_milestone_index = 0
        approved_steps = self._extract_plan_steps(approved_plan)
        max_steps = MAX_EXECUTE_ITERATIONS if self.mode == ExecutionMode.AUTO else max(25, len(approved_steps) * 4 or 10)
        self._transition_to(AgentState.EXECUTE, "thực thi kế hoạch")

        # ── Capture Evidence Baseline trước khi chạy ──
        try:
            cb.on_status("📸 Capturing evidence baseline...")
            count = self.evidence_baseline.capture()
            if count > 0:
                cb.on_chat(f"[#888888]📸 Evidence baseline: {count} tools captured.[/#888888]")
        except Exception:
            pass

        await self._execute_loop(exec_messages, max_iter=max_steps, approved_plan=approved_plan)

        # ── Compare with baseline ──
        try:
            if self.evidence_baseline.captured:
                diff = self.evidence_baseline.compare_with_current()
                if diff.has_regression():
                    for r in diff.regressions():
                        cb.on_chat(f"[#ff4444][ERR] REGRESSION: {r.tool_name} từng PASS ({r.baseline.exit_code}), giờ FAIL ({r.current.exit_code})[/#ff4444]")
                    cb.on_chat("[#f59e0b][WARN] Phát hiện regression sau execution — kiểm tra kết quả.[/#f59e0b]")
                else:
                    cb.on_chat(f"[#888888]{diff.summary()}[/#888888]")
        except Exception:
            pass

        # ── Run Verification Plan ──
        try:
            if getattr(self, "_verification_plan", None):
                report = self.done_engine.execute(self._verification_plan)
                cb.on_chat(f"[#888888]{report.summary}[/#888888]")
                if not report.all_pass:
                    blockers = [b.step.description for b in report.blockers]
                    cb.on_chat(f"[#f59e0b][WARN] Verification blockers ({len(blockers)}): {', '.join(blockers[:3])}[/#f59e0b]")
        except Exception:
            pass

        # ── Run post-execution pipeline ──
        self._transition_to(AgentState.VERIFY, "chạy pipeline hậu kiểm")
        await self._run_post_execution_pipeline(user_prompt)

        try:
            self.checkpoint_svc.create_checkpoint("Sau khi hoàn thành tác vụ", "AI")
        except Exception:
            pass

    async def _resolve_plan_intent(self, user_prompt: str) -> str:
        """Classify user's intent toward the existing plan using LLM semantic understanding.
        Injects chat history + system state so LLM understands context.
        Returns one of: 'execute', 'modify', 'cancel', 'other'.
        """
        plan_summary = self.session.execution_approved_plan[:500]
        cb = self.callbacks

        # Fast path first
        fast_intent, _ = self.intent_router.classify_plan_continuation(user_prompt, plan_summary)
        if fast_intent in ("execute", "cancel"):
            cb.on_chat(f"[#888888]🧠 Intent: {fast_intent} (fast path)[/#888888]")
            return fast_intent

        # ── Build context for LLM: chat history + system state ──
        # Current system state
        current_state = "WAITING_FOR_PLAN_APPROVAL"

        # Chat history: last 2 assistant messages (so LLM knows what user is responding to)
        chat_history_lines = []
        try:
            history = self.session_vm._state.conversation_history
            for msg in history[-4:]:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")[:200]
                chat_history_lines.append(f"{role}: {content}")
        except Exception:
            pass
        chat_history = "\n".join(chat_history_lines[-4:]) or "(no recent conversation)"

        # LLM path with full context
        try:
            from core.services.intent_router import PLAN_CONTINUATION_PROMPT
            from core.agent_utils import _call_ai, _unpack_ai_result

            plan_truncated = self.session.execution_approved_plan[:800]

            # Fill the prompt template
            sys_prompt = (
                PLAN_CONTINUATION_PROMPT
                .replace("{current_state}", current_state)
                .replace("{chat_history}", chat_history)
            )

            llm_messages = [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": (
                    f"Existing plan:\n{plan_truncated}\n\n"
                    f"User says: {user_prompt}\n\n"
                    "What is the user's intent?"
                )},
            ]
            raw, _, _, _ = _unpack_ai_result(
                await _call_ai(self.client, self.cfg, llm_messages, on_status=lambda s: None)
            )
            intent = self.intent_router.parse_plan_continuation(raw)
            cb.on_chat(f"[#888888]🧠 Intent: {intent} (LLM, state={current_state})[/#888888]")
            return intent
        except Exception as e:
            cb.on_chat(f"[#f59e0b][WARN] Không thể phân loại ý định ({e}), mặc định 'execute'[/#f59e0b]")
            return "execute"

    async def _patch_plan(self, user_prompt: str) -> bool:
        """Delta-Plan Update: apply minimal changes to existing plan instead of regenerating.
        Returns True if patch was applied, False if full regeneration is needed.
        """
        cb = self.callbacks
        old_plan = self.session.execution_approved_plan

        cb.on_chat("[bold #38bdf8]--- Đang áp dụng thay đổi vào kế hoạch hiện tại ---[/bold #38bdf8]")

        try:
            from core.agent_utils import _call_ai, _unpack_ai_result

            patch_messages = [
                {"role": "system", "content": (
                    "You are a plan patcher. You have an existing plan and a user's change request. "
                    "Output ONLY the changes needed — new steps to ADD, steps to REMOVE, or steps to MODIFY. "
                    "Use this format:\n"
                    "ADD: <new step description>\n"
                    "REMOVE: <step to remove>\n"
                    "MODIFY: <old step> → <new step>\n\n"
                    "If the changes are too complex for this format, output exactly: FULL_REGENERATE_NEEDED"
                )},
                {"role": "user", "content": (
                    f"Existing plan:\n{old_plan}\n\n"
                    f"User's change request:\n{user_prompt}\n\n"
                    "What minimal changes are needed?"
                )},
            ]

            cb.on_status("AI is patching plan...")
            ai_response, _, _, _ = _unpack_ai_result(
                await _call_ai(self.client, self.cfg, patch_messages, on_status=cb.on_status)
            )
            ai_text = ai_response.strip()

            if "FULL_REGENERATE_NEEDED" in ai_text:
                cb.on_chat("[#f59e0b][WARN] Thay đổi phức tạp, cần tạo lại toàn bộ kế hoạch.[/#f59e0b]")
                return False

            # Apply changes: mark additions/removals/modifications on the plan
            lines = old_plan.splitlines()
            adds = re.findall(r'^ADD:\s*(.+)$', ai_text, re.MULTILINE | re.IGNORECASE)
            removes = re.findall(r'^REMOVE:\s*(.+)$', ai_text, re.MULTILINE | re.IGNORECASE)
            modifies = re.findall(r'^MODIFY:\s*(.+?)\s*→\s*(.+)$', ai_text, re.MULTILINE | re.IGNORECASE)

            # Remove steps
            for remove_desc in removes:
                lines = [l for l in lines if remove_desc.lower() not in l.lower()]

            # Modify steps
            for old_desc, new_desc in modifies:
                lines = [new_desc if old_desc.lower() in l.lower() else l for l in lines]

            # Add steps at end (before any trailing blank lines or markers)
            if adds:
                # Find insertion point — before trailing blank lines or DONE markers
                insert_at = len(lines)
                for i in range(len(lines) - 1, -1, -1):
                    if lines[i].strip() and not lines[i].strip().startswith("<"):
                        insert_at = i + 1
                        break
                for add_desc in adds:
                    lines.insert(insert_at, f"- {add_desc}")
                    insert_at += 1

            new_plan = "\n".join(lines)
            self.session.execution_approved_plan = new_plan

            cb.on_chat(f"[bold #22c55e]--- Kế hoạch đã được vá ---[/bold #22c55e]")
            cb.on_chat(ai_text)
            cb.on_chat('[#888888]Nói "thực thi đi" để chạy kế hoạch đã cập nhật.[/#888888]')
            self.session_vm.add_message("user", user_prompt)
            self.session_vm.add_message("assistant", new_plan)
            cb.on_done(0.0)
            return True

        except Exception as e:
            cb.on_chat(f"[#f59e0b][WARN] Patch failed ({e}), thử tạo lại toàn bộ...[/#f59e0b]")
            return False

    async def _modify_existing_plan(self, user_prompt: str) -> None:
        """Take existing plan + user's modification request, create updated plan via LLM.
        Full regeneration — used when _patch_plan() determines changes are too complex.
        """
        cb = self.callbacks
        old_plan = self.session.execution_approved_plan

        cb.on_chat("[bold #38bdf8]--- Đang tạo lại kế hoạch theo yêu cầu mới ---[/bold #38bdf8]")

        try:
            from core.prompts import SYSTEM_PROMPT_PLAN
            from core.agent_utils import _call_ai, _unpack_ai_result

            context = self._build_context(user_prompt)
            instructions = self.memory.load_instructions(user_prompt)
            plan_system = SYSTEM_PROMPT_PLAN
            if instructions:
                plan_system += f"\n\n## RULES:\n{instructions}"

            plan_messages = [
                {"role": "system", "content": plan_system},
                {"role": "user", "content": (
                    f"## Context:\n{context}\n\n"
                    f"## Existing plan:\n{old_plan}\n\n"
                    f"## User modification request:\n{user_prompt}\n\n"
                    "The user wants to CHANGE the existing plan above. "
                    "Keep what's still relevant, modify what needs changing, "
                    "and output the COMPLETE updated plan. "
                    "End with <PLAN_DONE/> when done."
                )},
            ]

            cb.on_status("AI is updating plan...")
            ai_plan, p_tok, c_tok, _meta = _unpack_ai_result(
                await _call_ai(self.client, self.cfg, plan_messages, on_status=cb.on_status)
            )

            # Parse hierarchical plan
            hp, raw_json = self._extract_hierarchical_plan(ai_plan)
            if hp and raw_json:
                self.session.hierarchical_plan_json = raw_json
                self.session.current_milestone_index = -1
                display_text = self._render_hierarchical_plan(hp)
                self.session.execution_approved_plan = display_text
                cb.on_chat(f"[bold #22c55e]--- Kế hoạch đã cập nhật (Phân tầng) ---[/bold #22c55e]")
                cb.on_chat(display_text)
                cb.on_chat(f'[#888888]📌 {len(hp.milestones)} chặng, {sum(len(m.tasks) for m in hp.milestones)} tasks.[/#888888]')
            else:
                new_plan = re.sub(r'\s*<PLAN_DONE\s*/>\s*', '', ai_plan, flags=re.IGNORECASE).strip()
                self.session.execution_approved_plan = new_plan
                cb.on_chat(f"[bold #22c55e]--- Kế hoạch đã cập nhật ---[/bold #22c55e]")
                cb.on_chat(new_plan)

            cb.on_chat('[#888888]Nói "thực thi đi" để chạy kế hoạch mới này.[/#888888]')
            self.session_vm.add_message("user", user_prompt)
            self.session_vm.add_message("assistant", self.session.execution_approved_plan)
            cb.on_done(0.0)
        except Exception as e:
            cb.on_error(f"AI error during plan modification: {e}")
            cb.on_done(0.0)

    async def _execute_loop(self, messages: list[dict], max_iter: int = 10, approved_plan: Optional[str] = None) -> set:
        """Core execution loop — calls AI, parses tool calls, executes them.
        Returns the set of modified files.
        """
        cb = self.callbacks
        _loop_start = time.perf_counter()
        self._exec_messages = messages
        self._exec_modified_files_holder = modified_files = set()
        plan_steps = self._extract_plan_steps(approved_plan)

        _consecutive_failures = 0
        _total_tokens_used = 0
        _MAX_TOKENS_PER_TASK = 10_000_000  # Hard cap per task (10M tokens for long autonomous tasks)
        _total_build_failures = 0
        _last_modified_count = 0
        _stall_count = 0
        _stalled_hash_count = 0
        _file_hashes: dict[str, str] = {}
        self._total_tool_calls = 0
        _iteration_count = 0
        _llm_call_counter = CallCounter()
        llm_call_counter.set(_llm_call_counter)
        from core.services.checkpoint import CheckpointWriter
        _checkpointer = CheckpointWriter(str(self._project_root))

        # ── Execution Trace Fingerprint (per-iteration metrics for long-run analysis) ──
        from core.services.trace_fingerprint import TraceFingerprint
        _trace = TraceFingerprint(str(self._project_root))

        # ── Context budget tracker (relevance-based filtering) ──
        from core.services.context_assembler import ContextAssembler
        _ctx = ContextAssembler()
        _ctx.reset()

        # ── Persistent execution log (không bị condense mất) ──
        _exec_log: list[str] = []
        _exec_log_counter = 0

        # ── Loop pattern detection ──
        _tool_call_history: list[tuple[str, str]] = []  # [(tool_type, file_path), ...]
        _pattern_warned = False

        # ── Scratchpad: tóm tắt failures giữa các iteration, không xóa trắng ──
        _scratchpad: list[str] = []
        from core.services.retry_contract import RetryContract, RetryStrategy
        _retry_contract = RetryContract(max_retries=3)
        _retry_strategy = getattr(self, "retry_strategy", RetryStrategy())
        # Error Classifier + Loop Detector (thay thế logic retry cũ)
        _error_classifier = ErrorClassifier()
        _loop_detector = LoopDetector()
        self._loop_detector = _loop_detector

        # ── Dependency Graph: build once tại đầu execution loop ──
        if not self._dep_graph_built:
            try:
                count = self.dep_graph.build()
                if count > 0:
                    cb.on_chat(f"[#888888]📊 Dependency graph built: {count} files parsed[/#888888]")
                    self._dep_graph_built = True
            except Exception:
                logger.exception("DepGraph build failed (non-fatal)")

        # ── Symbol Dependency Graph ──
        if not self._symdep_built:
            try:
                sym_count = self.symbol_dep_graph.build(self._project_root)
                if sym_count > 0:
                    cb.on_chat(f"[#888888]Symbol dep graph built: {sym_count} files with calls[/#888888]")
                    self._symdep_built = True
            except Exception:
                logger.exception("SymbolDepGraph build failed (non-fatal)")

        # ── Knowledge Freshness: record build state ──
        try:
            self.knowledge_freshness.record_build(iteration=0)
        except Exception:
            pass

        # ── Recovery Checkpoint: reset state ──
        try:
            self.checkpoint_mgr.reset()
            self._last_checkpoint_snapshot: set[str] = set()
        except Exception:
            pass

        for iteration in range(1, max_iter + 1):
            _iteration_count = iteration
            if self._is_interrupted():
                cb.on_status("Stopped by user")
                if modified_files:
                    report_lines = ["\n[#22c55e]✦ Các tệp đã chỉnh sửa (trước khi dừng):[/#22c55e]"]
                    for f in sorted(modified_files):
                        report_lines.append(f"  * [cyan]{f}[/cyan]")
                    cb.on_chat("\n".join(report_lines))
                cb.on_done(time.perf_counter() - _loop_start)
                return

            # ── Graduated context pruning — pressure-based BEFORE AI call ──
            messages_before_prune = None
            p_level = 0  # default, updated in try block below
            try:
                from core.services.overflow import estimate_tokens, get_context_limit, pressure_level
                est_tokens = estimate_tokens(messages)
                model_limit = get_context_limit(self.cfg.model.provider, self.cfg.model.model, self.cfg.model.context_limit)
                p_level = pressure_level(est_tokens, model_limit, self.cfg.model.max_tokens)
                _ctx.set_pressure(p_level)
                if p_level >= 1 and iteration > 2:
                    from core.services.context_pruner import compute_pressure_prune
                    messages_before_prune = messages.copy()

                    # Levels 2+: save checkpoint + rebuild (lossless) instead of compact
                    if p_level >= 2:
                        _decision_list = []
                        try:
                            if hasattr(self, "decision_log"):
                                _adrs = getattr(self.decision_log, "adrs", []) or []
                                _decision_list = [{"decision": getattr(a, "decision", str(a))[:200]} for a in (_adrs[-10:] if _adrs else [])]
                        except Exception:
                            pass
                        _checkpointer.save(
                            iteration,
                            goal=messages[0].get("content", "")[:300] if messages else "",
                            plan=approved_plan or "",
                            plan_progress=f"Iter {iteration}/{max_iter}",
                            decisions=_decision_list,
                            failures=_scratchpad[-10:] if _scratchpad else None,
                            modified_files=modified_files,
                            execution_summary=_exec_log[-10:] if _exec_log else None,
                            n_llm_calls=_llm_call_counter.count,
                            n_tool_calls=self._total_tool_calls,
                            force=True,
                        )
                        # Determine system prompt from messages
                        _system_prompt = messages[0].get("content", "") if messages else ""
                        # Rebuild from checkpoint + last 16 messages (working memory)
                        messages[:] = _checkpointer.rebuild_messages(
                            _system_prompt, messages[-16:]
                        )
                        cb.on_chat(
                            f"[yellow]⚠ Context pressure level {p_level}. "
                            f"Checkpoint rebuild: {len(messages_before_prune)} → {len(messages)} messages.[/yellow]"
                        )
                        # Fidelity measurement
                        try:
                            from core.services.fidelity import ContextFidelityTracker
                            _fid = ContextFidelityTracker()
                            _fid_scores = _fid.measure_fidelity(
                                messages_before_prune, messages, plan=approved_plan or "",
                                decision_log=self.decision_log if hasattr(self, "decision_log") else None,
                                scratchpad=_scratchpad if _scratchpad else None,
                                exec_log=_exec_log if _exec_log else None,
                            )
                            if _fid_scores.get("overall", 1.0) < 0.7:
                                cb.on_chat(_fid.format_report(_fid_scores, iteration))
                        except Exception:
                            pass
                    else:
                        # Level 1: soft-trim (acceptable loss for old tool output)
                        pruned = compute_pressure_prune(messages, p_level)
                        if pruned is not None and len(pruned) < len(messages):
                            old_len = len(messages)
                            messages[:] = pruned
                            cb.on_chat(
                                f"[yellow]⚠ Context pressure level {p_level} (soft-trim). "
                                f"Đã nén từ {old_len} → {len(pruned)} messages.[/yellow]"
                            )
                            # ── Fidelity measurement ──
                            try:
                                from core.services.fidelity import ContextFidelityTracker
                                _fid = ContextFidelityTracker()
                                _fid_scores = _fid.measure_fidelity(
                                    messages_before_prune, messages, plan=approved_plan or "",
                                    decision_log=self.decision_log if hasattr(self, "decision_log") else None,
                                    scratchpad=_scratchpad if _scratchpad else None,
                                    exec_log=_exec_log if _exec_log else None,
                                )
                                if _fid_scores.get("overall", 1.0) < 0.7:
                                    cb.on_chat(_fid.format_report(_fid_scores, iteration))
                            except Exception:
                                pass
            except Exception:
                logger.exception("Context pruning failed (non-fatal)")

            # ── Token hard limit: không cho vượt quá 50k tokens cho 1 task ──
            if _total_tokens_used > _MAX_TOKENS_PER_TASK:
                limit_display = f"{_MAX_TOKENS_PER_TASK // 1_000_000}M" if _MAX_TOKENS_PER_TASK >= 1_000_000 else f"{_MAX_TOKENS_PER_TASK // 1000}k"
                cb.on_chat(f"[#ff4444]⛔ Đã vượt quá {limit_display} tokens cho tác vụ này ({_total_tokens_used}). Dừng để tránh tốn phí.[/#ff4444]")
                cb.on_status("Stopping — token limit exceeded")
                break

            # ── Scratchpad: inject failure context giữa các iteration ──
            if _scratchpad and _ctx.should_include("scratchpad", "\n".join(_scratchpad), iteration, modified_files):
                sp_text = "\n".join(_scratchpad[-5:])
                scratch_msg = {
                    "role": "system",
                    "content": f"[Scratchpad - tổng kết failures từ các iteration trước:\n{sp_text}\n\nMục đích: giúp bạn không lặp lại lỗi cũ. Nếu đã học được từ lỗi, hãy dùng cách tiếp cận khác.]"
                }
                sp_idx = next((i for i, m in enumerate(messages) if m.get("role") == "system" and m["content"].startswith("[Scratchpad")), None)
                if sp_idx is not None:
                    messages[sp_idx] = scratch_msg
                else:
                    messages.insert(1, scratch_msg)
                _ctx.consume_budget("scratchpad", sp_text)

            # ── Inject persistent execution log (biên niên sử) ──
            if _exec_log and _ctx.should_include("exec_log", "\n".join(_exec_log[-20:]), iteration, modified_files):
                log_text = "## Biên niên sử thực thi (Execution Log):\n" + "\n".join(_exec_log[-20:])
                log_idx = next((i for i, m in enumerate(messages) if m.get("role") == "system" and "Biên niên sử thực thi" in m.get("content", "")), None)
                log_msg = {"role": "system", "content": log_text}
                if log_idx is not None:
                    messages[log_idx] = log_msg
                else:
                    messages.insert(2, log_msg)
                _ctx.consume_budget("exec_log", log_text)

            # ── Loop pattern detection ──
            if len(_tool_call_history) >= 6 and not _pattern_warned:
                recent = _tool_call_history[-6:]
                # Detect: same 3 pairs repeating (e.g., read A → patch A → read A → patch A)
                pairs = [(recent[i], recent[i+1]) for i in range(0, len(recent)-1, 2)]
                if len(pairs) >= 2 and all(p == pairs[0] for p in pairs[1:]):
                    cb.on_chat(f"[#f59e0b]🔄 Phát hiện loop pattern: {pairs[0][0]} {pairs[0][1]} lặp lại {len(pairs)} lần. Yêu cầu AI thay đổi cách tiếp cận.[/#f59e0b]")
                    messages.append({
                        "role": "user",
                        "content": f"[WARN] Bạn đang lặp lại pattern: {pairs[0][0]} → {pairs[0][1]} liên tục. DỪNG pattern này và thử cách khác. Đọc lại file, phân tích lỗi, và thay đổi chiến lược."
                    })
                    _pattern_warned = True

            # ── Goal Drift Detection ──
            try:
                drift_result = self.goal_drift.check(
                    recent_messages=messages, modified_files=modified_files,
                    iteration=iteration,
                )
                if drift_result.is_drifting:
                    drift_ctx = self.goal_drift.format_context()
                    if drift_ctx:
                        cb.on_chat(f"[#ff4444]🧭 Goal Drift Warning:[/#ff4444]")
                        for line in drift_ctx.split("\n"):
                            cb.on_chat(f"  {line}")
                        messages.append({
                            "role": "user",
                            "content": (
                                f"[WARN] GOAL DRIFT DETECTED:\n{drift_ctx}\n\n"
                                f"Hãy dừng việc đang làm và quay lại mục tiêu gốc. "
                                f"Nếu đã hoàn thành mục tiêu, dùng <DONE/>."
                            ),
                        })
            except Exception:
                pass

            # ── ADR Override Validation — check justification file ──
            try:
                override_path = os.path.join(str(self._project_root), ".opencode", "override_justification.json")
                if os.path.exists(override_path):
                    with open(override_path, encoding="utf-8") as _f:
                        content = json.loads(_f.read())
                    valid, err = self.decision_log.validate_override(
                        category=content.get("category", ""),
                        proposed_decision=content.get("proposed_decision", ""),
                        justification=content,
                        repo_root=str(self._project_root),
                        metrics_file=os.path.join(str(self._project_root), ".opencode", "metrics.json"),
                    )
                    if not valid:
                        cb.on_chat(f"[#ff4444]⛔ ADR Override REJECTED: {err}[/#ff4444]")
                        messages.append({
                            "role": "user",
                            "content": (
                                f"[WARN] ADR OVERRIDE REJECTED: {err}\n\n"
                                f"Override at `{override_path}` is invalid.\n"
                                f"Fix and try again, or abandon the override.\n"
                                f"Schema: trigger=<ADR-ID> violation, evidence_type=commit|metric, "
                                f"evidence_ref=commit:<hash>:<glob>|metric:<name>:<value>"
                            ),
                        })
                        try:
                            os.remove(override_path)
                        except OSError:
                            pass
            except Exception:
                pass

            cb.on_iteration(iteration, max_iter)
            cb.on_status("AI thinking...")
            try:
                provider_for_call = self.cfg.model.provider
                model_for_call = self.cfg.model.model
                ai_msg, p_tokens, c_tokens, meta = _unpack_ai_result(
                    await _call_ai_stream(self.client, self.cfg, messages,
                                          on_chunk=cb.on_chunk, on_status=cb.on_status)
                )
                self._emit_tokens_used(p_tokens, c_tokens, provider_for_call, model_for_call)
                _total_tokens_used += p_tokens + c_tokens
            except Exception as e:
                cb.on_status(f"API error: {e}")
                cb.on_error(str(e))
                cb.on_done(time.perf_counter() - _loop_start)
                return

            cb.on_status("")

            # ── Context overflow handling (post-facto: API reported truncated) ──
            if meta.get("truncated"):
                reason = meta.get("finish_reason") or "unknown"
                cb.on_chat(f"[yellow]⚠ Context overflow ({reason}). Nén lịch sử hội thoại để giữ bộ nhớ.[/yellow]")
                try:
                    from core.services.context_pruner import smart_compact
                    compacted = smart_compact(messages, keep_turns=2)
                    if compacted is not None and len(compacted) < len(messages):
                        messages[:] = compacted
                except Exception:
                    logger.exception("Compaction failed (non-fatal)")
                    # Fallback: keep system message + last 5 messages (~2 turns)
                    if len(messages) > 6:
                        messages[:] = [messages[0]] + messages[-5:]

            # Save raw AI response to debug file (only when ORCACODE_DEBUG is set)
            if os.environ.get("ORCACODE_DEBUG"):
                try:
                    debug_file = self.memory.memory_dir / "debug_ai_msg.txt"
                    debug_file.write_text(ai_msg, encoding="utf-8")
                except OSError:
                    pass

            # ── Compliance check & Tool Parsing ──
            tool_calls = self.patch_svc.parse_tool_calls(ai_msg)

            if not tool_calls:
                if self._is_conversational_response(ai_msg, modified_files):
                    cb.on_chat(ai_msg.strip())
                    cb.on_status("Conversation complete")
                    cb.on_done(time.perf_counter() - _loop_start)
                    return

                if self._is_awaiting_user_input(ai_msg):
                    cb.on_chat(ai_msg.strip())
                    cb.on_status(">> Chờ bạn nhập câu trả lời...")
                    cb.on_done(time.perf_counter() - _loop_start)
                    return

                if self._has_leaked_code(ai_msg):
                    _consecutive_failures += 1
                    if _consecutive_failures > MAX_CONSECUTIVE_FAILURES:
                        cb.on_chat("[#f59e0b]⏭ AI lặp lại lỗi quá nhiều lần — dừng để tránh tiêu tốn token.[/#f59e0b]")
                        cb.on_status("Stopping — repeated compliance violations")
                        break
                    cb.on_status("Compliance violation — retrying (code leak)...")
                    cb.on_chat(f"[red]AI đang bị cảnh cáo do in code sai luật (Code Leak):[/red]\n{ai_msg}")
                    messages.append({"role": "assistant", "content": ai_msg})
                    messages.append({"role": "user", "content": self._CORRECTION_MSG})
                    continue
                
                if "<DONE" not in ai_msg.upper() and "<PLAN_DONE" not in ai_msg.upper():
                    _consecutive_failures += 1
                    if _consecutive_failures > MAX_CONSECUTIVE_FAILURES:
                        cb.on_chat("[#f59e0b]⏭ AI liên tục không dùng công cụ — dừng vòng lặp để tránh tiêu tốn token.[/#f59e0b]")
                        cb.on_status("Stopping — AI unresponsive to corrections")
                        break
                    cb.on_status(f"Compliance violation — retrying (no tools used, attempt {_consecutive_failures}/{MAX_CONSECUTIVE_FAILURES})...")
                    cb.on_chat(f"[red]AI đang bị hệ thống cảnh cáo do lỗi format (Không dùng tool):[/red]\n{ai_msg[:200]}")
                    messages.append({"role": "assistant", "content": ai_msg})
                    messages.append({"role": "user", "content": self._NO_TOOL_MSG})
                    continue

            self.session_vm.add_message("assistant", ai_msg)

            # Build clean explanation text (strip tool tags and code blocks)
            clean = TOOL_TAG_RE.sub('', ai_msg)
            clean = TOOL_TAG_OPEN_RE.sub('', clean)
            clean = ANGLE_BRACKET_RE.sub('', clean)
            clean = DONE_TAG_RE.sub('', clean)
            clean = PLAN_DONE_TAG_RE.sub('', clean)
            clean = CODE_BLOCK_RE.sub('', clean)
            clean = MULTI_NEWLINE_RE.sub('\n\n', clean).strip()

            if tool_calls:
                _consecutive_failures = 0  # AI is responsive — reset dead-loop guard
                action_lines = ["[bold #38bdf8]Agent thuc thi:[/bold #38bdf8]"]
                if clean:
                    explanation = "\n".join(clean.split('\n')[:2])
                    action_lines.append(f"[italic #94a3b8]{explanation}[/italic #94a3b8]")
                for tc in tool_calls:
                    t = tc["type"]
                    if t == "write_file":
                        action_lines.append(f"  * [green]TAO/GHI DE[/green] -> [cyan]{tc['path']}[/cyan]")
                    elif t == "patch_file":
                        action_lines.append(f"  * [yellow]PATCH[/yellow] -> [cyan]{tc['path']}[/cyan]")
                    elif t == "anchor_patch":
                        action_lines.append(f"  * [blue]ANCHOR PATCH[/blue] -> [cyan]{tc['path']}[/cyan]")
                    elif t == "line_patch":
                        action_lines.append(f"  * [green]LINE PATCH[/green] -> [cyan]{tc['path']} L{tc['start_line']}-{tc.get('end_line') or tc['start_line']}[/cyan]")
                    elif t == "run_command":
                        action_lines.append(f"  * [magenta]LENH[/magenta] -> [white]{tc['command']}[/white]")
                    elif t == "refactor":
                        action_lines.append("  * [blue]REFACTOR MULTI-FILE[/blue]")
                    elif t == "read_file":
                        action_lines.append(f"  * [cyan]DOC FILE[/cyan] -> [white]{tc['path']}[/white]")
                    elif t == "search_code":
                        action_lines.append(f"  * [cyan]TIM KIEM[/cyan] -> [white]{tc['pattern'][:60]}[/white]")
                    elif t == "debug_error":
                        action_lines.append("  * [red]PHAN TICH LOI[/red]")
                cb.on_chat("\n".join(action_lines))
            else:
                plan_ok, plan_retry_msg = self._validate_plan_review(ai_msg, plan_steps, modified_files)
                if not plan_ok:
                    _consecutive_failures += 1
                    if _consecutive_failures > MAX_CONSECUTIVE_FAILURES:
                        cb.on_chat("[#f59e0b]⏭ AI không thể hoàn tất review sau nhiều lần — chấp nhận DONE để thoát vòng lặp.[/#f59e0b]")
                        cb.on_done(time.perf_counter() - _loop_start)
                        return
                    cb.on_chat("[#f59e0b][WARN] Agent attempted to finish without reconciling the approved plan — forcing another iteration.[/#f59e0b]")
                    messages.append({"role": "assistant", "content": ai_msg})
                    messages.append({"role": "user", "content": plan_retry_msg})
                    continue
                task_ok, task_retry_msg = self._validate_task_review(ai_msg, modified_files, results=[])
                if not task_ok:
                    _consecutive_failures += 1
                    if _consecutive_failures > MAX_CONSECUTIVE_FAILURES:
                        cb.on_chat("[#f59e0b]⏭ AI không thể hoàn tất review sau nhiều lần — chấp nhận DONE để thoát vòng lặp.[/#f59e0b]")
                        cb.on_done(time.perf_counter() - _loop_start)
                        return
                    cb.on_chat("[#f59e0b][WARN] Agent attempted to finish without a valid completion review — forcing another iteration.[/#f59e0b]")
                    messages.append({"role": "assistant", "content": ai_msg})
                    messages.append({"role": "user", "content": task_retry_msg})
                    continue
                if clean:
                    cb.on_chat(clean)
                if modified_files:
                    report_lines = ["\n[#22c55e]✦ Các tệp đã chỉnh sửa trong tác vụ này:[/#22c55e]"]
                    for f in sorted(modified_files):
                        report_lines.append(f"  * [cyan]{f}[/cyan]")
                    cb.on_chat("\n".join(report_lines))
                cb.on_done(time.perf_counter() - _loop_start)
                return

            cb.on_tool_plan(tool_calls)
            results = []
            task_cancelled = False

            # ── Recovery Checkpoint: snapshot files chuẩn bị ghi ──
            write_paths = {
                tc.get("path", "")
                for tc in tool_calls
                if tc.get("type") in ("write_file", "patch_file", "anchor_patch", "line_patch", "refactor")
            }
            if write_paths:
                # Thêm cả files sẽ bị ảnh hưởng (dependents)
                affected: set[str] = set()
                for p in list(write_paths):
                    try:
                        affected.update(self.dep_graph.get_all_dependents(p, depth=1))
                    except Exception:
                        pass
                snapshot_paths = write_paths | affected
                try:
                    cp = self.checkpoint_mgr.snapshot(snapshot_paths, iteration)
                    self._last_checkpoint_snapshot = snapshot_paths
                except Exception:
                    pass

            for idx, tc in enumerate(tool_calls):
                if self._is_interrupted():
                    cb.on_status("Interrupted by user")
                    task_cancelled = True
                    break
                cb.on_tool_start(tc, idx, len(tool_calls))
                try:
                    loop = asyncio.get_running_loop()
                    result = await loop.run_in_executor(None, lambda: self._execute_tool(tc))
                except Exception as e:
                    cb.on_error(f"Tool execution failed: {e}")
                    result = {"summary": f"Tool error: {e}", "success": False}

                # Error Classifier + Loop Detector: phân loại & phát hiện loop
                if not result.get("success") and not result.get("skipped"):
                    try:
                        # Phân loại lỗi
                        cls = _error_classifier.classify_from_result(result, tool_type=tc.get("type", ""))
                        error_text = result.get("summary", "")
                        loop = _loop_detector.record(
                            error_text=error_text,
                            category=cls.category.value,
                            attempt=iteration,
                            root_cause=cls.root_cause,
                        )
                        # Ghi vào scratchpad
                        _scratchpad.append(f"[iter {iteration}] {cls.category.value}: {cls.root_cause}")
                        if len(_scratchpad) > 10:
                            _scratchpad.pop(0)

                        if cls.should_stop:
                            cb.on_chat(f"[#ff4444]⛔ ENVIRONMENT ERROR — DỪNG: {cls.root_cause}[/#ff4444]")
                            cb.on_chat(f"[#888888]  → {cls.suggested_action}[/#888888]")
                            cb.on_status("Stopped — environment error")
                            task_cancelled = True
                            break
                        if cls.should_ask:
                            cb.on_chat(f"[#f59e0b]❓ UNKNOWN ERROR — Cần user xác nhận: {cls.root_cause}[/#f59e0b]")
                        if loop.should_stop:
                            cb.on_chat(f"[#ff4444]⛔ LOOP DETECTED — {loop.reason}[/#ff4444]")
                            cb.on_chat(f"[#888888]  Đã thử {_loop_detector.total_attempts} lần, không tiến triển. Dừng để tránh lãng phí.[/#888888]")
                            task_cancelled = True
                            break
                        if not cls.should_stop and not loop.should_stop:
                            cb.on_chat(f"[#f59e0b]🔄 [{cls.category.value}] {cls.root_cause} — {cls.suggested_action}[/#f59e0b]")
                    except Exception as exc:
                        logger.warning("Error classifier failed: %s", exc)

                results.append(result)
                if result.get("success"):
                    if tc.get("type") in ("write_file", "patch_file", "anchor_patch", "line_patch"):
                        modified_files.add(tc["path"])
                        # ── DepGraph: refresh file sau khi ghi thành công ──
                        try:
                            self.dep_graph.refresh_file(tc["path"])
                        except Exception:
                            pass
                    elif tc.get("type") == "refactor":
                        for p in tc.get("patches", []):
                            if p.get("path"):
                                modified_files.add(p["path"])
                                try:
                                    self.dep_graph.refresh_file(p["path"])
                                except Exception:
                                    pass
                if result.get("_incomplete"):
                    cb.on_chat(f"[#f59e0b]File {tc.get('path', 'unknown')} chưa hoàn chỉnh, cần ghi tiếp.[/#f59e0b]")
                if result.get("skipped"):
                    cb.on_chat("[#f59e0b]Task stopped: user declined action.[/#f59e0b]")
                    task_cancelled = True
                    break

                # ── Auto-Linter: validate ALL modified files, not just last ──
                _syntax_errors_found = False
                for fpath in sorted(modified_files):
                    if not _syntax_errors_found:
                        try:
                            loop = asyncio.get_running_loop()
                            linter_errors = await loop.run_in_executor(None, self._check_syntax, fpath)
                        except Exception:
                            logger.exception("Linter failed (non-fatal)")
                            linter_errors = ""
                        if linter_errors:
                            _syntax_errors_found = True
                            cb.on_status(f"Syntax error detected in {fpath} — feeding back to AI...")
                            cb.on_chat(f"[#f59e0b]Linter phát hiện lỗi cú pháp trong {fpath}:[/#f59e0b]")
                            cb.on_chat(linter_errors[:500])
                            cb.on_error("Linter error:\n" + linter_errors[:300])
                            result["summary"] += "\n[LINTER ERROR]\n" + linter_errors[:300]
                            messages.append({"role": "assistant", "content": ai_msg})
                            linter_feedback = (
                                f"LINTER ERROR — File bị lỗi cú pháp sau khi bạn sửa:\n\n"
                                f"```\n{linter_errors[:1000]}\n```\n\n"
                                f"Hãy dùng <PATCH_FILE path=\"{fpath}\"> để SỬA NGAY lỗi cú pháp này. "
                                f"Đây là lỗi do bạn gây ra khi sửa file, bạn PHẢI sửa nó."
                            )
                            messages.append({"role": "user", "content": linter_feedback})

                # Security Scan: check patched file for vulnerabilities ──
                if not _syntax_errors_found and result.get("success") and tc["type"] in ("write_file", "patch_file", "anchor_patch", "line_patch"):
                    file_content = self.patch_svc.read_file(tc["path"])
                    if file_content and file_content is not None:
                        sec_issues = self.security_scanner.scan_file(tc["path"], file_content)
                        for issue in sec_issues[:5]:
                            cb.on_chat(f"[red]🔒 Security: {issue.message} ({tc['path']}:{issue.line})[/red]")
                            cb.on_status(f"Security issue in {tc['path']}")
                            logger.warning("Security scan: %s in %s:%d", issue.message, tc["path"], issue.line)

            if task_cancelled:
                if modified_files:
                    report_lines = ["\n[#22c55e]✦ Các tệp đã chỉnh sửa (trước khi dừng):[/#22c55e]"]
                    for f in sorted(modified_files):
                        report_lines.append(f"  * [cyan]{f}[/cyan]")
                    cb.on_chat("\n".join(report_lines))
                cb.on_done(0.0)
                return

            summaries = "\n".join(r.get("summary", "") for r in results if r.get("summary"))

            # ── Dependency impact analysis: inject affected files warning ──
            dep_warnings: list[str] = []
            for tc in tool_calls:
                fp = tc.get("path", "")
                if fp and tc.get("type") in ("write_file", "patch_file", "anchor_patch", "line_patch", "refactor"):
                    try:
                        ctx = self.dep_graph.format_affected_context(fp)
                        if ctx:
                            dep_warnings.append(ctx)
                    except Exception:
                        pass
            if dep_warnings:
                dep_msg = "📦 " + "  ".join(dep_warnings[:3])
                if _ctx.should_include("dep_impact", dep_msg, iteration, modified_files):
                    summaries = (dep_msg + "\n\n" + summaries) if summaries else dep_msg
                    _ctx.consume_budget("dep_impact", dep_msg)

            # ── Truncate tool output before injecting into messages ──
            try:
                from core.services.output_truncator import OutputTruncator
                truncator = OutputTruncator(project_root=str(self._project_root))
                _tool_name = tool_calls[0].get("type", "tool") if tool_calls else "tool"
                summaries = truncator.truncate(summaries, tool_name=_tool_name)
            except Exception:
                logger.exception("Output truncation failed (non-fatal)")

            # ── Update execution log ──
            _exec_log_counter += 1
            for tc in tool_calls:
                t = tc["type"]
                path = tc.get("path", tc.get("command", ""))[:60]
                # Track tool call pattern for loop detection
                _tool_call_history.append((t, path))
                if len(_tool_call_history) > 20:
                    _tool_call_history.pop(0)
                # Build log entry
                status = "success" if any(r.get("success") and r.get("summary", "").startswith("Wrote") or r.get("summary", "").startswith("Patched") for r in results) else "info"
                if t in ("write_file", "patch_file", "anchor_patch", "line_patch"):
                    entry = f"Iter {iteration}: {t} {path}"
                    if entry not in _exec_log:
                        _exec_log.append(entry)
                elif t == "run_command":
                    _exec_log.append(f"Iter {iteration}: run {tc.get('command', '')[:50]}")
                elif t == "read_file":
                    _exec_log.append(f"Iter {iteration}: read {tc.get('path', '')}")
            # Giới hạn log
            if len(_exec_log) > 100:
                _exec_log = _exec_log[-80:]

            # ── Knowledge Freshness: verify after tool calls (auto-refresh stale graphs) ──
            try:
                if modified_files:
                    self.knowledge_freshness.verify(iteration, modified_files)
            except Exception:
                pass

            messages.append({"role": "assistant", "content": ai_msg})

            # Track total tool calls for memory logging
            self._total_tool_calls = (getattr(self, "_total_tool_calls", 0) or 0) + len(tool_calls)

            # Check if any file write was incomplete (truncated / missing content)
            incomplete_files = [r for r in results if r.get("_incomplete")]

            # ── Stall guard: chỉ count iteration có ý định WRITE (không count read-only) ──
            _WRITE_TOOLS = {"write_file", "patch_file", "anchor_patch", "line_patch", "refactor"}
            has_write_attempts = any(tc.get("type") in _WRITE_TOOLS for tc in tool_calls)

            # Hash-based stall: chỉ check khi AI cố gắng ghi file
            if has_write_attempts:
                current_hashes: dict[str, str] = {}
                _hash_loop = asyncio.get_running_loop()
                _hash_tasks = []
                for f in sorted(modified_files):
                    p = Path(self._project_root) / f
                    if p.exists():
                        _hash_tasks.append(_hash_loop.run_in_executor(
                            None, lambda fname=f, fp=p: (fname, hashlib.sha256(fp.read_bytes()).hexdigest())
                        ))
                if _hash_tasks:
                    for _result in await asyncio.gather(*_hash_tasks, return_exceptions=True):
                        if isinstance(_result, tuple):
                            fname, hval = _result
                            current_hashes[fname] = hval
                content_changed = any(
                    _file_hashes.get(f) != h for f, h in current_hashes.items()
                ) if _file_hashes else bool(current_hashes)

                if content_changed:
                    _stalled_hash_count = 0
                    _file_hashes = current_hashes
                else:
                    _stalled_hash_count += 1
                    _MAX_WRITE_STALL = 8  # Cho phép 8 lần write fail trước khi kết luận stall
                    if _stalled_hash_count >= _MAX_WRITE_STALL:
                        cb.on_chat(f"[#ff4444]⛔ Agent cố gắng ghi file {_MAX_WRITE_STALL} lần nhưng nội dung không thay đổi — dừng để chờ chủ nhân cứu viện.[/#ff4444]")
                        cb.on_status("Stopping — write attempts not persisting")
                        break
            else:
                # Read-only iterations (đọc, tìm kiếm, chạy lệnh): không tính là stall
                # Cho phép tối đa 30 iteration đọc liên tiếp, sau đó chỉ warn chứ không kill
                if iteration % 30 == 0 and iteration > 0:
                    cb.on_chat(f"[#888888]📖 Đã đọc/ phân tích {iteration} iterations, chưa có thay đổi file nào. Vẫn đang làm việc...[/#888888]")

            # Loop Detector plateau check: thay thế legacy stall guard
            plateau_result = _loop_detector.record_modified_count(len(modified_files))
            if plateau_result and plateau_result.should_stop:
                cb.on_chat(f"[#ff4444]⏭ {plateau_result.reason}[/#ff4444]")
                cb.on_status("Stopping — write plateau")
                break

            # ── Scratchpad: ghi nhớ failures với phân loại và gợi ý sửa ──
            failures = [r for r in results if not r.get("success") and not r.get("skipped")]
            if failures:
                briefs = []
                for f in failures:
                    s = f.get("summary", "")[:120]
                    if s:
                        # Analyze with RetryStrategy for root cause
                        rca = self.retry_strategy.analyze_failure(
                            f.get("tool_type", ""), f, {}
                        )
                        cause = rca.get("root_cause", "unknown")
                        fix = rca.get("suggested_fix", "")
                        briefs.append(f"[{cause}] {s[:80]}" + (f" → {fix[:60]}" if fix else ""))
                if briefs:
                    entry = f"Iteration {iteration}: {len(failures)} failure(s) — {'; '.join(briefs[:3])}"
                    _scratchpad.append(entry)
                    # Log to long-term memory for cross-session learning
                    try:
                        for f in failures:
                            rca = self.retry_strategy.analyze_failure(
                                f.get("tool_type", ""), f, {}
                            )
                            detail = f"root_cause={rca.get('root_cause', 'unknown')} | fix={rca.get('suggested_fix', '')}"
                            self.long_memory.log_event(
                                "failure",
                                summary=f"[{rca.get('root_cause', 'unknown')}] {f.get('summary', '')[:100]}",
                                details=detail,
                            )
                    except Exception:
                        pass

            if incomplete_files:
                incomplete_paths = []
                incomplete_details = []
                for r in incomplete_files:
                    incomplete_paths.append(r.get("summary", "").split(":")[1].strip() if ":" in r.get("summary", "") else "unknown")
                    incomplete_details.append(r.get("summary", ""))
                paths_str = ", ".join(incomplete_paths)
                detail_str = "\n".join(incomplete_details)
                retry_msg = (
                    f"[WARN] FILE INCOMPLETE — Các file sau bị thiếu nội dung (do response bị cắt):\n\n"
                    f"{detail_str}\n\n"
                    f"Phần code đã viết được SAVE vào file. Dùng mode=\"append\" để TIẾP TỤC:\n"
                    f"  <WRITE_FILE path=\"...\" mode=\"append\">[phan code con thieu]</WRITE_FILE>\n"
                    f"Lặp lại cho đến khi file hoàn chỉnh, rồi <DONE/>."
                )
                messages.append({"role": "user", "content": retry_msg})
                cb.on_chat(f"[#f59e0b][WARN] Phát hiện file thiếu nội dung: {paths_str} — yêu cầu AI viết lại...[/#f59e0b]")
                continue  # Skip DONE check, force retry

            # ── Chunked file: verify each section independently ──
            chunked_results = [r for r in results if r.get("_chunked")]
            section_fix_requested = False
            for chunked in chunked_results:
                chunk_path = chunked.get("path", "")
                for sec in chunked.get("sections", []):
                    errors = self.structural_validator.validate(chunk_path, None, sec["content"])
                    if errors:
                        cb.on_chat(f"[yellow]⚠ Section '{sec['name']}' trong {chunk_path} có vấn đề:[/yellow]")
                        for err in errors:
                            cb.on_chat(f"  [red]• {err}[/red]")
                        fix_msg = (
                            f"[WARN] SECTION '{sec['name']}' TRONG {chunk_path} CÓ LỖI:\n\n"
                            + "\n".join(errors) + "\n\n"
                            f"Dùng <ANCHOR_PATCH path=\"{chunk_path}\">"
                            f"<START>{sec['start_marker']}</START>"
                            f"<END>{sec['end_marker']}</END>"
                            f"<CONTENT>[nội dung sửa cho section '{sec['name']}']</CONTENT>"
                            f"</ANCHOR_PATCH> để SỬA NGAY."
                        )
                        messages.append({"role": "user", "content": fix_msg})
                        cb.on_chat(f"[#f59e0b]🔄 Yêu cầu AI sửa section '{sec['name']}' trong {chunk_path}...[/#f59e0b]")
                        section_fix_requested = True
                        break
                if section_fix_requested:
                    break
            if section_fix_requested:
                cb.on_chat(f"[#f59e0b]⏭ Bỏ qua DONE — chờ AI sửa section lỗi trước.[/#f59e0b]")
                continue

            # If AI already said DONE, run final verification before accepting
            if re.search(r'<DONE\s*/>', ai_msg, re.IGNORECASE):
                # ── Run deep diagnostic on modified files ──
                deep_issues = []
                for f in sorted(modified_files)[:3]:
                    try:
                        report = self._diagnose_file(f)
                        if report:
                            # Check for [ERR] markers in report
                            if '[ERR]' in report:
                                deep_issues.append(f)
                                cb.on_chat(f"[#f59e0b][WARN] Diagnostic found issues in {f} — forcing fix...[/#f59e0b]")
                    except Exception:
                        pass

                if deep_issues:
                    # Files still have issues — force AI to fix them
                    files_str = ", ".join(deep_issues)
                    fix_msg = (
                        f"[WARN] POST-DIAGNOSTIC — Các file sau VẪN CÒN LỖI sau khi bạn DONE:\n"
                        f"{files_str}\n\n"
                        f"Hệ thống đã chạy chẩn đoán và phát hiện lỗi cấu trúc (thiếu thẻ đóng, lệch ngoặc,...). "
                        f"Hãy ĐỌC LẠI các file này, TÌM lỗi cụ thể, và SỬA NGAY.\n"
                        f"KHÔNG được DONE khi file còn lỗi!"
                    )
                    messages.append({"role": "user", "content": fix_msg})
                    cb.on_chat(f"[#f59e0b]🔄 Post-DONE diagnostic found {len(deep_issues)} file(s) with issues — retrying...[/#f59e0b]")
                    try:
                        self.iteration_scorer.record_simple(
                            iteration=iteration, build_pass=False,
                            runtime_error_count=len(deep_issues))
                    except Exception:
                        pass
                    continue  # Force another iteration

                # ── Evidence-based verification + Runtime file check ──
                if modified_files:
                    # Runtime verify: syntax + parse check từng file
                    rt_errors = self._runtime_verify_files(modified_files)
                    if rt_errors:
                        cb.on_chat(f"[#ff4444][ERR] Runtime verification thất bại:[/#ff4444]")
                        for err in rt_errors[:5]:
                            cb.on_chat(f"  [red]• {err}[/red]")
                        _total_build_failures += 1
                        if _total_build_failures >= _MAX_BUILD_FAILURES:
                            cb.on_chat(f"[red]⛔ Runtime fail {_total_build_failures} lần — dừng.[/red]")
                            break
                        messages.append({"role": "user", "content": (
                            f"[WARN] RUNTIME VERIFICATION FAILED ({_total_build_failures}/{_MAX_BUILD_FAILURES}):\n"
                            + "\n".join(f"- {e}" for e in rt_errors[:5])
                            + "\n\nSửa các lỗi syntax/parse này trước khi DONE."
                        )})
                        try:
                            self.iteration_scorer.record_simple(
                                iteration=iteration, build_pass=False,
                                runtime_error_count=len(rt_errors))
                        except Exception:
                            pass
                        continue
                    # ── Semantic Damage Detection ──
                    try:
                        semantic_issues = self._check_semantic_damage(modified_files, iteration)
                        if semantic_issues:
                            cb.on_chat(f"[#ff4444][ERR] Semantic damage detected — {len(semantic_issues.deleted)} deletions, {len(semantic_issues.changed_signatures)} signature changes[/#ff4444]")
                            cb.on_chat(f"[#f59e0b]{semantic_issues.summary}[/#f59e0b]")
                            if semantic_issues.should_block:
                                messages.append({"role": "user", "content": (
                                    f"[WARN] SEMANTIC DAMAGE DETECTED:\n"
                                    f"{semantic_issues.summary[:500]}\n\n"
                                    f"Bạn ĐÃ XOÁ function/class quan trọng. Khôi phục lại các symbol này ngay lập tức.\n"
                                    f"KHÔNG được DONE nếu còn thiếu function."
                                )})
                                try:
                                    self.iteration_scorer.record_simple(
                                        iteration=iteration, build_pass=False,
                                        semantic_damage_count=len(semantic_issues.deleted),
                                        semantic_blocked=True)
                                except Exception:
                                    pass
                                continue
                    except Exception:
                        pass
                    # Evidence-based check
                    evidence_conditions = await self._verify_with_evidence(focused_files=list(modified_files) if modified_files else None)
                    if not evidence_conditions.all_pass():
                        _total_build_failures += 1
                        # ── Recovery Checkpoint: compare build quality ──
                        try:
                            current_error_count = len(evidence_conditions.failures())
                            self.checkpoint_mgr.record_build_result(current_error_count)
                            if self.checkpoint_mgr.compare_build_quality(current_error_count):
                                # Build WORSENED → auto-rollback
                                restored = self.checkpoint_mgr.rollback(iteration)
                                if restored:
                                    cb.on_chat(f"[#ff4444]⏪ Build worsened — rollback {len(restored)} files. Yêu cầu AI thử cách khác.[/#ff4444]")
                                    messages.append({"role": "user", "content": (
                                        f"🛑 BUILD REGRESSED — Rollback về checkpoint (trước iteration {iteration}).\n"
                                        f"Số lỗi tăng từ {self.checkpoint_mgr._checkpoints[-1].build_error_count if len(self.checkpoint_mgr._checkpoints) > 1 else 0} → {current_error_count}.\n"
                                        f"Các file đã restore: {', '.join(restored[:5])}\n\n"
                                        f"Bạn PHẢI thay đổi cách tiếp cận. Đọc lại file, hiểu rõ cấu trúc trước khi ghi.\n"
                                        f"KHÔNG lặp lại code cũ đã gây lỗi."
                                    )})
                                    try:
                                        self.iteration_scorer.record_simple(
                                            iteration=iteration, build_pass=False,
                                            rollback_count=len(restored))
                                    except Exception:
                                        pass
                                    continue
                        except Exception:
                            pass
                        if _total_build_failures >= _MAX_BUILD_FAILURES:
                            cb.on_chat(f"[red]⛔ Build thất bại {_total_build_failures} lần liên tiếp — dừng để tránh loop.[/red]")
                            cb.on_status("Stopping — repeated build failures")
                            break
                        fail_summary = "\n".join(
                            f"  ✗ [{c.status_icon}] {c.name}: {c.output_summary}"
                            for c in evidence_conditions.failures()
                        )
                        retry_msg = (
                            f"[WARN] EVIDENCE FAILURE ({_total_build_failures}/{_MAX_BUILD_FAILURES}) — Các kiểm tra sau KHÔNG ĐẠT:\n"
                            f"{fail_summary}\n\n"
                            f"Hãy SỬA các lỗi này và chạy lại. "
                            f"KHÔNG được DONE cho đến khi TẤT CẢ check đều pass!"
                        )
                        messages.append({"role": "user", "content": retry_msg})
                        cb.on_chat(
                            f"[#f59e0b]🔄 Evidence check: {len(evidence_conditions.failures())} failure(s) — retrying ({_total_build_failures}/{_MAX_BUILD_FAILURES})...[/#f59e0b]"
                        )
                        try:
                            err_count = len(evidence_conditions.failures())
                            tf_count = getattr(self, '_last_test_fail_count', 0)
                            tt_count = getattr(self, '_last_test_total_count', 0)
                            self.iteration_scorer.record_simple(
                                iteration=iteration, build_pass=False,
                                runtime_error_count=err_count,
                                test_fail_count=tf_count,
                                test_total_count=tt_count)
                        except Exception:
                            pass
                        continue

                     # ── Evidence PASSED — record good build state ──
                    try:
                        self.checkpoint_mgr.record_build_result(0)
                    except Exception:
                        pass
                    # ── Record iteration quality score — PASS ──
                    try:
                        sem_count = len(semantic_issues.deleted) if semantic_issues else 0
                        sem_blocked = semantic_issues.should_block if semantic_issues else False
                        tf_count = getattr(self, '_last_test_fail_count', 0)
                        tt_count = getattr(self, '_last_test_total_count', 0)
                        self.iteration_scorer.record_simple(
                            iteration=iteration, build_pass=True,
                            semantic_damage_count=sem_count,
                            semantic_blocked=sem_blocked,
                            runtime_error_count=0, rollback_count=0,
                            export_removed_count=0,
                            test_fail_count=tf_count,
                            test_total_count=tt_count,
                        )
                    except Exception:
                        pass

                # ── Static code review (patterns + security) ──
                file_contents = {}
                if modified_files:
                    try:
                        reviewer = ReviewerAgent()
                        for f in modified_files:
                            p = Path(self.cfg.project_root, f) if self.cfg.project_root else Path(f)
                            if p.exists():
                                file_contents[f] = p.read_text(encoding="utf-8", errors="replace")
                        if file_contents:
                            review_result = await reviewer.review(files=file_contents, llm_client=self.client)
                            if not review_result.passed:
                                critical = sum(1 for i in review_result.issues if i.severity.value in ("critical", "high"))
                                issue_lines = [
                                    f"  [{i.severity.value.upper()}] {i.message}"
                                    + (f" ({i.file}:{i.line})" if i.file else "")
                                    for i in review_result.issues[:10]
                                ]
                                extra = f"\n  ...and {len(review_result.issues) - 10} more" if len(review_result.issues) > 10 else ""
                                retry_msg = (
                                    f"[WARN] CODE REVIEW — Phát hiện {len(review_result.issues)} vấn đề ("
                                    f"{critical} critical/high):\n"
                                    f"{chr(10).join(issue_lines)}{extra}\n\n"
                                    f"Hãy SỬA các vấn đề này trước khi DONE."
                                )
                                messages.append({"role": "user", "content": retry_msg})
                                cb.on_chat(
                                    f"[#f59e0b]🔄 Code review: {len(review_result.issues)} issue(s) found — retrying...[/#f59e0b]"
                                )
                                continue
                    except Exception as exc:
                        cb.on_chat(f"[#888888][WARN] Code review skipped: {exc}[/]")

                # ── Code Quality Scan (advisory only, periodic) ──
                if modified_files and (self._last_quality_scan_iteration == 0 or
                                       iteration - self._last_quality_scan_iteration >= 5):
                    try:
                        # Run all independent scans in parallel for speed
                        _loop = asyncio.get_running_loop()
                        _gathered = await asyncio.gather(
                            asyncio.to_thread(self.code_quality.check_all, self._project_root, modified_files, iteration=iteration),
                            asyncio.to_thread(self.design_reviewer.review_diffs, modified_files, self._project_root),
                            asyncio.to_thread(self.plan_drift.check, modified_files, iteration),
                            asyncio.to_thread(self._anti_pattern_scan, modified_files, self._project_root),
                            return_exceptions=True,
                        )
                        qc_report = _gathered[0]
                        dr_report = _gathered[1]
                        dr_result = _gathered[2]
                        ap_results = _gathered[3]

                        if isinstance(qc_report, Exception):
                            logger.warning("Code quality scan failed: %s", qc_report)
                            qc_report = None
                        if isinstance(dr_report, Exception):
                            logger.warning("Design review failed: %s", dr_report)
                            dr_report = None
                        if isinstance(dr_result, Exception):
                            dr_result = None
                        if isinstance(ap_results, Exception):
                            ap_results = None

                        if qc_report is not None:
                            self._last_qc_report = qc_report
                        if dr_report is not None:
                            self._last_dr_report = dr_report

                        # Merge design review findings into quality report for unified scoring
                        if qc_report is not None and dr_report is not None:
                            for finding in dr_report.findings:
                                from core.services.code_quality import QualityIssue
                                qc_report.issues.append(QualityIssue(
                                    checker="design", severity="warning" if finding.severity == "major" else "info",
                                    message=finding.message, file_path=finding.file_path, line=finding.line,
                                ))
                            qc_report.compute_score()
                            if qc_report.has_issues():
                                cb.on_chat(f"[#888888]📊 Code quality scan: score {qc_report.score}/100[/#888888]")
                                for line in qc_report.summary().split("\n"):
                                    if line.strip():
                                        cb.on_chat(f"[#888888]{line}[/#888888]")
                            if dr_report.has_findings():
                                cb.on_chat(f"[#888888]Design review: {len(dr_report.findings)} issues[/#888888]")
                            # Feed quality score into iteration scorer (unified, non-blocking)
                            try:
                                self.iteration_scorer.record_simple(
                                    iteration=iteration, build_pass=True,
                                    quality_score=qc_report.score,
                                )
                            except Exception:
                                pass

                        # ── Plan Drift check ──
                        if dr_result is not None and dr_result.is_drifting:
                            cb.on_chat(f"[#f59e0b][WARN] Plan drift detected: {dr_result.warning[:100]}[/#f59e0b]")

                        # ── Anti-pattern scan ──
                        if ap_results:
                            errors = [p for p in ap_results if p.severity == "error"]
                            warnings = [p for p in ap_results if p.severity == "warning"]
                            if errors or warnings:
                                cb.on_chat(f"[#888888]Anti-pattern scan: {len(errors)} errors, {len(warnings)} warnings[/#888888]")

                        self._last_quality_scan_iteration = iteration
                    except Exception as exc:
                        cb.on_chat(f"[#888888][WARN] Code quality scan skipped: {exc}[/]")

                # ── Lightweight file validation (Phase D) ──
                if modified_files and file_contents:
                    try:
                        sv = SchemaValidator()
                        validation_issues = ValidationResult.ok()

                        for f, content in file_contents.items():
                            validation_issues = validation_issues.merge(
                                sv.validate_section_markers(content, file=f)
                            )

                        # Check results consistency
                        validation_issues = validation_issues.merge(
                            ResultValidator().validate_results_consistency(results, modified_files)
                        )

                        if not validation_issues.passed:
                            issue_lines = [
                                f"  {'[ERROR]' if i.severity.value == 'error' else '[WARN]'} {i.message}"
                                + (f" ({i.file})" if i.file else "")
                                for i in validation_issues.issues[:10]
                            ]
                            extra = f"\n  ...and {len(validation_issues.issues) - 10} more" if len(validation_issues.issues) > 10 else ""
                            retry_msg = (
                                f"[WARN] VALIDATION — Phát hiện {validation_issues.count} vấn đề:\n"
                                f"{chr(10).join(issue_lines)}{extra}\n\n"
                                f"Hãy SỬA trước khi DONE."
                            )
                            messages.append({"role": "user", "content": retry_msg})
                            cb.on_chat(
                                f"[#f59e0b]🔄 Validation: {validation_issues.count} issue(s) — retrying...[/#f59e0b]"
                            )
                            continue
                    except Exception as exc:
                        cb.on_chat(f"[#888888][WARN] Validation skipped: {exc}[/]")

                plan_ok, plan_retry_msg = self._validate_plan_review(ai_msg, plan_steps, modified_files)
                if not plan_ok:
                    _consecutive_failures += 1
                    if _consecutive_failures > MAX_CONSECUTIVE_FAILURES:
                        cb.on_chat("[#f59e0b]⏭ AI không thể hoàn tất review sau nhiều lần — chấp nhận DONE để thoát vòng lặp.[/#f59e0b]")
                        cb.on_done(time.perf_counter() - _loop_start)
                        return
                    messages.append({"role": "user", "content": plan_retry_msg})
                    cb.on_chat("[#f59e0b]🔄 Approved plan is not fully reconciled yet — retrying instead of accepting DONE.[/#f59e0b]")
                    continue

                task_ok, task_retry_msg = self._validate_task_review(ai_msg, modified_files, results)
                if not task_ok:
                    _consecutive_failures += 1
                    if _consecutive_failures > MAX_CONSECUTIVE_FAILURES:
                        cb.on_chat("[#f59e0b]⏭ AI không thể hoàn tất review sau nhiều lần — chấp nhận DONE để thoát vòng lặp.[/#f59e0b]")
                        cb.on_done(time.perf_counter() - _loop_start)
                        return
                    messages.append({"role": "user", "content": task_retry_msg})
                    cb.on_chat("[#f59e0b]🔄 Completion review is incomplete — retrying instead of accepting DONE.[/#f59e0b]")
                    continue

                self._transition_to(AgentState.VERIFY, "DONE signal — kiểm tra kết quả cuối cùng")

                # Verify against done conditions
                try:
                    if hasattr(self, "_done_conditions") and self._done_conditions:
                        # Build richer context for verification
                        dc_file_contents = {}
                        for f in modified_files:
                            try:
                                p = Path(self._project_root, f)
                                if p.exists():
                                    dc_file_contents[f] = p.read_text(encoding="utf-8", errors="replace")
                            except Exception:
                                pass
                        dc_context = {
                            "modified_files": modified_files,
                            "file_contents": dc_file_contents,
                            "project_root": str(self._project_root),
                        }
                        verified = self.done_condition_verifier.verify_all(self._done_conditions, dc_context)
                        dc_summary = self.done_condition_verifier.summary(verified)
                        cb.on_chat(f"[#888888]{dc_summary}[/#888888]")
                        if not self.done_condition_verifier.all_met(verified):
                            unmet = [d.description for d in verified if not d.met]
                            cb.on_chat(f"[#f59e0b][WARN] Done conditions chưa đạt: {', '.join(unmet)}. Retrying...[/#f59e0b]")
                            messages.append({"role": "user", "content": f"Chưa đạt done conditions: {', '.join(unmet)}. Tiếp tục cho đến khi hoàn thành."})
                            continue
                except Exception:
                    pass

                # ── Cross-file consistency check (multi-file refactor validation) ──
                if len(modified_files) >= 2:
                    try:
                        cross_issues = self._check_cross_file_consistency(modified_files)
                        if cross_issues:
                            for issue in cross_issues:
                                cb.on_chat(f"[#f59e0b][WARN] Cross-file: {issue}[/#f59e0b]")
                            cb.on_chat("[#f59e0b][WARN] Cross-file consistency issues detected. Retrying...[/#f59e0b]")
                            messages.append({"role": "user", "content": (
                                "Cross-file consistency issues detected after refactoring:\n"
                                + "\n".join(f"- {i}" for i in cross_issues[:5])
                                + "\n\nFix these issues before DONE."
                            )})
                            continue
                    except Exception:
                        pass

                # ── Milestone advancement: check if current milestone is done ──
                hp_json = getattr(self.session, "hierarchical_plan_json", "")
                if hp_json:
                    idx = getattr(self.session, "current_milestone_index", -1)
                    try:
                        data = json.loads(hp_json)
                        milestones = data.get("milestones", [])
                        if 0 <= idx < len(milestones):
                            # Get/Create retry counter cho milestone verification
                            ms_retry = getattr(self, "_milestone_retry_count", 0)
                            cb.on_chat(f"[#38bdf8]🔎 Kiểm tra Milestone {idx+1}/{len(milestones)}...[/#38bdf8]")
                            ev_ok = True
                            try:
                                # Runtime file verification trước
                                rt_errors = self._runtime_verify_files(modified_files)
                                if rt_errors:
                                    ms_retry += 1
                                    self._milestone_retry_count = ms_retry
                                    rt_fail = "\n".join(f"  ✗ {e}" for e in rt_errors[:5])
                                    cb.on_chat(f"[#f59e0b][WARN] Runtime verify thất bại (lần {ms_retry}/3):\n{rt_fail}[/#f59e0b]")
                                    if ms_retry >= 3:
                                        cb.on_chat(f"[#ff4444]⛔ Milestone {idx+1} thất bại sau 3 lần retry. Dừng thực thi.[/#ff4444]")
                                        break
                                    messages.append({"role": "user", "content": f"Runtime verification failed for milestone (attempt {ms_retry}/3):\n{rt_fail}\n\nFix syntax/parse errors before DONE."})
                                    continue
                                evidence_conditions = await self._verify_with_evidence()
                                if not evidence_conditions.all_pass():
                                    ms_retry += 1
                                    self._milestone_retry_count = ms_retry
                                    fails = "\n".join(f"  ✗ {c.name}: {c.output_summary}" for c in evidence_conditions.failures())
                                    cb.on_chat(f"[#f59e0b][WARN] Evidence check thất bại (lần {ms_retry}/3):\n{fails}[/#f59e0b]")
                                    if ms_retry >= 3:
                                        cb.on_chat(f"[#ff4444]⛔ Milestone {idx+1} thất bại sau 3 lần retry. Dừng thực thi.[/#ff4444]")
                                        break
                                    ev_ok = False
                            except Exception:
                                pass
                            if not ev_ok:
                                messages.append({"role": "user", "content": f"Evidence check failed for milestone (attempt {ms_retry}/3). Fix ALL issues before DONE."})
                                continue
                            # Fix #4: Human verification gate — hỏi user trước khi advance
                            self._milestone_retry_count = 0
                            cb.on_chat(f"[bold #22c55e]🎯 Milestone {idx+1}/{len(milestones)} hoàn thành![/bold #22c55e]")
                            cb.on_chat(f"[#888888]Vui lòng kiểm tra giao diện/kết quả trước khi chuyển sang milestone tiếp theo.[/#888888]")
                            cb.on_status(">> Chờ user xác nhận milestone...")
                            user_ok = True
                            try:
                                plan_callback = getattr(cb, "request_plan_approval", None)
                                import inspect
                                if plan_callback is not None:
                                    result = plan_callback(f"Milestone {idx+1} hoàn thành. Tiếp tục sang milestone tiếp theo?")
                                    if inspect.isawaitable(result):
                                        loop = asyncio.get_running_loop()
                                        future = asyncio.run_coroutine_threadsafe(result, loop)
                                        decision = future.result(timeout=600)
                                    else:
                                        decision = result
                                else:
                                    choice = input(f"  Milestone {idx+1} done. Continue to next? [Y]es / [R]etry / [C]ancel: ").strip().lower()
                                    decision = "approve" if choice in ("y", "yes", "") else "retry" if choice == "r" else "cancel"
                                if decision in ("cancel", "no", "n"):
                                    cb.on_chat(f"[#f59e0b]⏸ User tạm dừng tại Milestone {idx+1}.[/#f59e0b]")
                                    break
                                if decision in ("retry", "r"):
                                    cb.on_chat(f"[#f59e0b]🔄 User yêu cầu sửa thêm ở Milestone {idx+1}...[/#f59e0b]")
                                    messages.append({"role": "user", "content": "User wants more changes in current milestone before advancing. Continue working."})
                                    continue
                            except Exception:
                                pass
                            # Fix #3: Build milestone summary trước khi advance
                            ms_summary_lines = [
                                f"## Milestone {idx+1} Summary",
                                f"- Files modified: {len(modified_files)}",
                                f"- Key changes: {summaries[:300] if summaries else 'completed'}",
                            ]
                            # Advance to next milestone
                            has_next = self._advance_milestone()
                            if has_next:
                                new_idx = getattr(self.session, "current_milestone_index", -1)
                                ms = milestones[new_idx]
                                cb.on_chat(f"[bold #22c55e][OK] Milestone {idx+1} done → Milestone {new_idx+1}: {ms.get('title', '')}[/bold #22c55e]")
                                plan_steps = [t.get("description", "") for t in ms.get("tasks", [])]
                                # Re-inject với summary + new milestone
                                new_tasks = self._get_active_tasks_text()
                                new_epic = self._get_epic_anchor()
                                milestone_msg = (
                                    f"[MILESTONE ADVANCED] Đã hoàn thành milestone {idx+1}.\n"
                                    + "\n".join(ms_summary_lines) + "\n\n"
                                    f"[PROJECT OBJECTIVE]: {new_epic}\n\n"
                                    f"Milestone hiện tại ({new_idx+1}):\n{new_tasks}\n\n"
                                    f"Tiếp tục thực thi các tasks của milestone mới. "
                                    f"KHÔNG được sửa lại code của milestone trước trừ khi cần thiết."
                                )
                                messages.append({"role": "system", "content": milestone_msg})
                                cb.on_chat(f"[bold #22c55e]Tiếp tục với milestone {new_idx+1}...[/bold #22c55e]")
                                continue
                    except (json.JSONDecodeError, KeyError):
                        pass

                messages.append({"role": "user", "content": f"## Results:\n{summaries}"})
                cb.on_chat("[#22c55e][OK] Task complete per AI signal.[/]")
                if modified_files:
                    report_lines = ["\n[#22c55e]✦ Các tệp đã chỉnh sửa trong tác vụ này:[/#22c55e]"]
                    for f in sorted(modified_files):
                        report_lines.append(f"  * [cyan]{f}[/cyan]")
                    cb.on_chat("\n".join(report_lines))
                cb.on_done(time.perf_counter() - _loop_start)
                return

            messages.append({"role": "user", "content": f"## Results:\n{summaries}\n\nContinue if needed, or output <DONE/> if complete."})

            # Log tool calls to long-term memory
            for idx, tc in enumerate(tool_calls):
                try:
                    t = tc["type"]
                    if t == "write_file":
                        self.long_memory.log_file_event("edit_file", tc["path"],
                            summary=f"Write: {tc['path']}")
                    elif t == "patch_file":
                        self.long_memory.log_file_event("edit_file", tc["path"],
                            summary=f"Patch: {tc['path']}")
                    elif t == "run_command":
                        self.long_memory.log_command_event(tc["command"],
                            summary=f"Run: {tc['command'][:80]}")
                    elif t == "refactor":
                        self.long_memory.log_event("refactor",
                            summary=f"Refactor: {tc.get('description', '')[:80]}")
                    elif t == "debug_error":
                        self.long_memory.log_event("debug_error",
                            summary=f"Debug error: {tc.get('content', '')[:80]}")
                except Exception:
                    logger.exception("LongMemory log failed (non-fatal)")

            # ── Execution Trace Fingerprint — record per-iteration metrics ──
            try:
                from core.services.trace_fingerprint import Fingerprint, hash_messages, hash_decisions, hash_files
                # Get decisions from decision_log if available
                _trace_decisions = []
                if hasattr(self, "decision_log"):
                    _adrs = getattr(self.decision_log, "adrs", []) or []
                    _trace_decisions = [{"decision": getattr(a, "decision", str(a))[:200]} for a in (_adrs[-10:] if _adrs else [])]
                _fp = Fingerprint(
                    iteration=iteration,
                    decision_hash=hash_decisions(_trace_decisions),
                    messages_hash=hash_messages(messages),
                    files_hash=hash_files(modified_files),
                    pressure_level=p_level,
                    n_llm_calls=_llm_call_counter.count,
                    n_tool_calls=self._total_tool_calls,
                    n_modified_files=len(modified_files),
                    n_scratchpad_entries=len(_scratchpad),
                    consecutive_failures=_consecutive_failures,
                    build_failures=_total_build_failures,
                    estimated_tokens=sum(len(m.get("content", "")) for m in messages) // 4,
                )
                if _checkpointer.load_latest():
                    _fp.checkpoint_available = True
                    _fp.checkpoint_iteration = _checkpointer.load_latest().iteration
                _trace.record(_fp)
            except Exception:
                pass

            # ── Context condensation: growth-based + token-based ──
            # Điều kiện: messages > 40 HOẶC estimated tokens > 60k (phòng log/tail siêu dài)
            # Luôn giữ 16 messages cuối (8 exchanges) làm working memory — không bao giờ nén
            _est_tokens = sum(len(m.get("content", "")) for m in messages) // 4
            if iteration > 0 and (len(messages) > 40 or _est_tokens > 60000):
                # Save checkpoint first, then rebuild from checkpoint + tail (lossless)
                _decision_list = []
                try:
                    if hasattr(self, "decision_log"):
                        _adrs = getattr(self.decision_log, "adrs", []) or []
                        _decision_list = [{"decision": getattr(a, "decision", str(a))[:200]} for a in (_adrs[-10:] if _adrs else [])]
                except Exception:
                    pass
                _checkpointer.save(
                    iteration,
                    goal=messages[0].get("content", "")[:300] if messages else "",
                    plan=approved_plan or "",
                    plan_progress=f"Iter {iteration}/{max_iter}",
                    decisions=_decision_list,
                    failures=_scratchpad[-10:] if _scratchpad else None,
                    modified_files=modified_files,
                    execution_summary=_exec_log[-10:] if _exec_log else None,
                    n_llm_calls=_llm_call_counter.count,
                    n_tool_calls=self._total_tool_calls,
                    force=True,
                )
                condense_before = messages.copy()
                _system_prompt = messages[0].get("content", "") if messages else ""
                messages[:] = _checkpointer.rebuild_messages(
                    _system_prompt, messages[-16:]
                )
                if len(messages) < len(condense_before):
                    try:
                        from core.services.fidelity import ContextFidelityTracker
                        _fid = ContextFidelityTracker()
                        _fid_scores = _fid.measure_fidelity(
                            condense_before, messages, plan=approved_plan or "",
                            decision_log=self.decision_log if hasattr(self, "decision_log") else None,
                            scratchpad=_scratchpad if _scratchpad else None,
                            exec_log=_exec_log if _exec_log else None,
                        )
                        if _fid_scores.get("overall", 1.0) < 0.7:
                            cb.on_chat(_fid.format_report(_fid_scores, iteration))
                    except Exception:
                        pass
        else:
            self._transition_to(AgentState.DONE, "hết số lần lặp tối đa")
            cb.on_status("Max iterations reached")
            if modified_files:
                report_lines = ["\n[#22c55e]✦ Các tệp đã chỉnh sửa trong tác vụ này:[/#22c55e]"]
                for f in sorted(modified_files):
                    report_lines.append(f"  * [cyan]{f}[/cyan]")
                cb.on_chat("\n".join(report_lines))
            cb.on_done(time.perf_counter() - _loop_start)

    # ─── Cross-file consistency check ──────────────────────────────────────────

    def _check_cross_file_consistency(self, modified_files: set[str]) -> list[str]:
        """Check that multi-file edits haven't broken cross-file references.
        Returns a list of issues found.
        """
        if len(modified_files) < 2:
            return []

        issues = []
        file_contents: dict[str, str] = {}

        for f in modified_files:
            try:
                p = Path(self._project_root, f)
                if p.exists():
                    file_contents[f] = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                pass

        if not file_contents:
            return []

        # Check 1: Python/JS/TS imports — for each file, verify referenced files exist in project
        import_patterns = [
            (r'from\s+([.\w/\\-]+)\s+import', ".py"),        # Python: from X import Y
            (r'import\s+([.\w/\\-]+)', ".py"),                # Python: import X
            (r'(?:import|require)\s*\(?\s*[\"\'](.+?)[\"\']', ".js"),   # JS: import/require
            (r'from\s+[\"\'](.+?)[\"\']', ".ts"),             # TS: from '...'
        ]

        for f, content in file_contents.items():
            ext = Path(f).suffix
            for pattern, lang_ext in import_patterns:
                if ext == lang_ext or (ext in (".tsx", ".jsx") and lang_ext in (".ts", ".js")):
                    for m in re.finditer(pattern, content):
                        imp_path = m.group(1)
                        # Skip stdlib, packages, relative parent refs
                        if imp_path.startswith(".") and ".." not in imp_path:
                            # Resolve relative import
                            base = Path(f).parent
                            resolved = (base / imp_path).resolve()
                            # Check if target file exists
                            for try_ext in ["", ".py", ".ts", ".tsx", ".js", ".jsx"]:
                                target = self._project_root / f"{resolved}{try_ext}"
                                if target.exists():
                                    break
                            else:
                                # Not found — might be an issue if the target was supposed to be modified
                                # Check if it's one of the other modified files
                                rel_str = str(resolved.relative_to(self._project_root)) if resolved.is_relative_to(self._project_root) else str(resolved)
                                if not any(rel_str in mf for mf in modified_files):
                                    # File not found and not in modified list — could be pre-existing issue
                                    pass  # Don't flag pre-existing issues

        # Check 2: Look for stub/TODO markers that suggest incomplete refactoring
        stub_patterns = [
            r'\bTODO\b', r'\bFIXME\b', r'\bXXX\b', r'\bHACK\b',
            r'\braise\s+NotImplementedError\b', r'\bpass\s*#\s*TODO\b',
        ]
        for f, content in file_contents.items():
            for pattern in stub_patterns:
                for m in re.finditer(pattern, content):
                    line_num = content[:m.start()].count("\n") + 1
                    issues.append(f"{f}:{line_num} — {m.group(0)} marker found (possibly incomplete)")
                    break  # One issue per file per pattern

        # Check 3: Check for files that reference each other's exports
        if len(modified_files) >= 2:
            modified_set = set(modified_files)
            for f, content in file_contents.items():
                base = Path(f).stem
                for other_f in modified_files:
                    if other_f == f:
                        continue
                    other_base = Path(other_f).stem
                    # If this file references the other file's module name
                    if other_base in content and other_base != base:
                        # Could be a valid reference — just log it
                        pass

        return issues

    # ─── Context builder ──────────────────────────────────────────────────────

    @staticmethod
    def _smart_truncate(text: str, max_len: int = 4000) -> str:
        """Cắt text tại ranh giới tự nhiên (paragraph/line), không cắt giữa code block."""
        if len(text) <= max_len:
            return text
        # Ưu tiên cắt tại ranh giới paragraph (double newline)
        para_break = text.rfind('\n\n', 0, max_len)
        if para_break > max_len // 2:  # Chỉ cắt nếu tìm thấy break ở nửa sau
            return text[:para_break] + '\n\n...[trimmed]'
        # Fallback: cắt tại line boundary
        line_break = text.rfind('\n', 0, max_len)
        if line_break > 0:
            return text[:line_break] + '\n...[trimmed]'
        # Fallback cuối: cắt tại word boundary
        space = text.rfind(' ', 0, max_len)
        if space > 0:
            return text[:space] + ' ...[trimmed]'
        return text[:max_len] + '...[trimmed]'

    # ─── Hierarchical Plan (Phân tầng Milestones/Tasks) ────────────────────────

    @staticmethod
    def _repair_json(raw: str) -> str | None:
        """Sửa lỗi JSON phổ biến của LLM: trailing comma, missing quotes, etc.
        Trả về JSON string đã sửa, hoặc None nếu không sửa được.
        """
        # Bước 1: loại bỏ comment (//, #)
        text = re.sub(r'//[^\n]*', '', raw)
        text = re.sub(r'#[^\n]*', '', text)
        # Bước 2: thử parse trực tiếp
        try:
            json.loads(text)
            return text
        except json.JSONDecodeError:
            pass
        # Bước 3: sửa trailing comma trong object/array
        text = re.sub(r',\s*([}\]])', r'\1', text)
        # Bước 4: thêm quotes cho unquoted keys
        text = re.sub(r'(?<!")(\b[a-zA-Z_][a-zA-Z0-9_]*\b)(\s*:)', r'"\1"\2', text)
        # Bước 5: sửa single quotes → double quotes
        text = re.sub(r"'", '"', text)
        # Bước 6: loại bỏ trailing comma ở cuối
        text = text.rstrip().rstrip(',')
        # Bước 7: thử parse lại
        try:
            json.loads(text)
            return text
        except json.JSONDecodeError:
            pass
        # Bước 8: cắt text tại dấu ngoặc đóng cuối cùng
        for close_char in ['}', ']']:
            idx = text.rfind(close_char)
            if idx > 0:
                candidate = text[:idx+1]
                try:
                    json.loads(candidate)
                    return candidate
                except json.JSONDecodeError:
                    pass
        return None

    def _extract_hierarchical_plan(self, plan_text: str) -> tuple[HierarchicalPlan | None, str]:
        """Parse JSON từ response LLM → (HierarchicalPlan, raw_json_string).
        Dùng _repair_json để xử lý lỗi cấu trúc JSON phổ biến.
        Trả về (None, '') nếu hoàn toàn không parse được → fallback flat-plan.
        """
        json_str = None
        # Pattern 1: ```json ... ``` block
        for m in re.finditer(r'```(?:json)?\s*\n?(\{[\s\S]*?\n?\})\s*\n?```', plan_text, re.DOTALL):
            candidate = self._repair_json(m.group(1))
            if candidate:
                json_str = candidate
                break
        if not json_str:
            # Pattern 2: raw JSON object with epic + milestones
            m = re.search(r'(\{[\s\S]*?"epic"[\s\S]*?"milestones"[\s\S]*?\})', plan_text, re.DOTALL)
            if m:
                candidate = self._repair_json(m.group(1))
                if candidate:
                    json_str = candidate
        if not json_str:
            return None, ""
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return None, ""
        if "milestones" not in data or not isinstance(data["milestones"], list):
            return None, ""
        milestones = []
        for ms in data["milestones"]:
            if not isinstance(ms, dict):
                continue
            tasks = []
            for t in ms.get("tasks", []):
                if not isinstance(t, dict):
                    continue
                tasks.append(PlanTask(
                    description=t.get("description", ""),
                    file=t.get("file", ""),
                    status="pending",
                ))
            milestones.append(PlanMilestone(
                title=ms.get("title", ""),
                description=ms.get("description", ""),
                tasks=tasks,
            ))
        if not milestones:
            return None, ""
        hp = HierarchicalPlan(
            epic=data.get("epic", ""),
            milestones=milestones,
            current_milestone_index=-1,
        )
        return hp, json_str

    def _render_hierarchical_plan(self, hp: HierarchicalPlan) -> str:
        """Chuyển HierarchicalPlan → Markdown hiển thị cho user."""
        lines = [f"## 🎯 Mục tiêu: {hp.epic}", ""]
        for i, ms in enumerate(hp.milestones):
            prefix = "[OK]" if ms.status == "done" else "🔄" if ms.status == "running" else ">>"
            lines.append(f"### {prefix} {ms.title}")
            if ms.description:
                lines.append(f"_{ms.description}_")
            for j, task in enumerate(ms.tasks):
                t_prefix = "  ☑" if task.status == "done" else "  🔲"
                task_file = f" (`{task.file}`)" if task.file else ""
                lines.append(f"{t_prefix} {j+1}.{task_file} — {task.description}")
            lines.append("")
        return "\n".join(lines)

    def _get_epic_anchor(self) -> str:
        """Lấy Epic (mục tiêu tối cao) để ghim vào context."""
        hp_json = getattr(self.session, "hierarchical_plan_json", "")
        if not hp_json:
            return ""
        try:
            data = json.loads(hp_json)
            return data.get("epic", "")
        except json.JSONDecodeError:
            return ""

    def _get_active_tasks_text(self) -> str:
        """Lấy tasks của milestone hiện tại để inject vào context."""
        idx = getattr(self.session, "current_milestone_index", -1)
        hp_json = getattr(self.session, "hierarchical_plan_json", "")
        if idx < 0 or not hp_json:
            return ""
        try:
            data = json.loads(hp_json)
            milestones = data.get("milestones", [])
            if idx >= len(milestones):
                return ""
            ms = milestones[idx]
            lines = [f"**Milestone hiện tại:** {ms.get('title', '')}"]
            for j, task in enumerate(ms.get("tasks", [])):
                lines.append(f"  {j+1}. `{task.get('file', '')}` — {task.get('description', '')}")
            return "\n".join(lines)
        except (json.JSONDecodeError, KeyError):
            return ""

    def _advance_milestone(self) -> bool:
        """Chuyển sang milestone tiếp theo. Trả về True nếu còn milestone, False nếu hết."""
        idx = getattr(self.session, "current_milestone_index", -1)
        hp_json = getattr(self.session, "hierarchical_plan_json", "")
        if not hp_json:
            return False
        try:
            data = json.loads(hp_json)
            milestones = data.get("milestones", [])
            if idx + 1 < len(milestones):
                self.session.current_milestone_index = idx + 1
                return True
            return False
        except (json.JSONDecodeError, KeyError):
            return False

    def _format_plan_window(self, plan_text: str, max_steps_display: int = 10) -> str:
        """If using hierarchical plan: show Epic + only current milestone's tasks.
        If using flat plan: show windowed version. Always include full plan as reference.
        """
        # Ưu tiên hierarchical plan
        active = self._get_active_tasks_text()
        epic = self._get_epic_anchor()
        if active and epic:
            hp_json = getattr(self.session, "hierarchical_plan_json", "")
            idx = getattr(self.session, "current_milestone_index", -1)
            total_ms = 0
            try:
                data = json.loads(hp_json)
                total_ms = len(data.get("milestones", []))
            except Exception:
                pass
            epilogue = f"\n\nFull plan ({total_ms} milestones total):\n{plan_text}" if total_ms > 1 else ""
            return f"[PROJECT OBJECTIVE]: {epic}\n\n{active}{epilogue}"

        # Fallback: flat plan windowing
        steps = self._extract_plan_steps(plan_text)
        if len(steps) <= max_steps_display:
            return plan_text

        head = steps[:5]
        tail = steps[-5:]
        hidden = len(steps) - 10
        window = "\n".join(f"  • {s}" for s in head)
        window += f"\n  • ... ({hidden} steps omitted, see full plan below) ...\n"
        window += "\n".join(f"  • {s}" for s in tail)
        window += f"\n\nFull plan ({len(steps)} steps total):\n{plan_text}"
        return window

    # _progressive_context_condense removed — replaced by CheckpointWriter.rebuild_messages()
    # See lines ~2130 and ~3306 for the lossless checkpoint-based rebuild approach

    def _build_signal_context(self, quality_report=None) -> str:
        """Collect all signals → rank → cap → format context string.

        Unified signal injection via SignalRanker.
        Replaces individual context sections for iteration_scorer, goal_drift,
        code_quality, design_review, loop_detector.
        """
        from core.services.signal import Signal, Priority, SignalRanker

        ranker = SignalRanker()

        # 1. IterationScorer signals (build, semantic, test, rollback)
        try:
            for sig in self.iteration_scorer.to_signals():
                ranker.add(sig)
        except Exception:
            pass

        # 2. GoalDrift signals
        try:
            for sig in self.goal_drift.to_signals():
                ranker.add(sig)
        except Exception:
            pass

        # 3. CodeQuality signals (architecture, complexity, debt, duplicate)
        if quality_report and quality_report.issues:
            try:
                for sig in quality_report.to_signals():
                    ranker.add(sig)
            except Exception:
                pass

        # 4. Design Review signals
        try:
            dr_report = getattr(self, '_last_dr_report', None)
            if dr_report and dr_report.findings:
                for sig in dr_report.to_signals():
                    ranker.add(sig)
        except Exception:
            pass

        # 5. Loop Detector state (if active)
        try:
            from core.services.loop_detector import LoopDetector
            ld = getattr(self, '_loop_detector', None)
            if ld and ld._stop_reason:
                is_escalation = 'ESCALATION' in ld._stop_reason
                ranker.add(Signal(
                    category="loop",
                    evidence_level=1,
                    observation=f"Loop detected: {ld._stop_reason}",
                    confidence=1.0,
                    severity_hint=1.0 if is_escalation else 0.6,
                ))
        except Exception:
            pass

        formatted = ranker.format_context()
        return formatted

    def _build_context(self, user_prompt: str) -> str:
        """Build project context with long-term memory from past tasks."""
        parts = [
            "## FRESH STATE — ĐÂY LÀ HIỆN TRẠNG DỰ ÁN (các message log cũ bên dưới là quá khứ):"
        ]

        try:
            tree = self._get_project_tree()
            if tree:
                parts.append(tree)
        except Exception:
            pass

        try:
            ctx = self.context_svc.build_context(user_prompt)
            if ctx:
                parts.append(ctx)
        except Exception:
            pass

        try:
            health = self._workspace_health_scan(user_prompt)
            if health:
                parts.append(health)
        except Exception:
            pass

        # ── Inject long-term memory from past sessions ──
        try:
            memory_ctx = self.long_memory.build_context_for_query(user_prompt, max_tokens=1500)
            if memory_ctx:
                parts.append(f"## Long-term Memory (từ các tác vụ trước):\n{memory_ctx}")
        except Exception:
            pass

        # ── Inject short-term chat history ──
        try:
            history = self.session_vm._state.conversation_history
            if history:
                recent = history[-6:]  # Last 3 exchanges (user + assistant)
                chat_lines = ["## Recent conversation:"]
                for msg in recent:
                    role = msg.get("role", "?")
                    content = msg.get("content", "")
                    content = content[:600]
                    chat_lines.append(f"  {role}: {content}")
                parts.append("\n".join(chat_lines))
        except Exception:
            pass

        # ── Inject Dependency Graph context ──
        try:
            if self._dep_graph_built:
                dg_context = self._format_depgraph_context(user_prompt)
                if dg_context:
                    parts.append(dg_context)
        except Exception:
            pass

        # ── Unified Signal Injection (monitoring layer → reasoning layer) ──
        try:
            qc_report = getattr(self, '_last_qc_report', None)
            signal_ctx = self._build_signal_context(quality_report=qc_report)
            if signal_ctx:
                parts.append(signal_ctx)
        except Exception:
            pass

        # ── Quality Score Trend (dashboard only, separate from signals) ──
        try:
            trend_ctx = self.code_quality.format_trend_context()
            if trend_ctx:
                parts.append(trend_ctx)
        except Exception:
            pass

        # ── Architecture Decision Records (ADR) — memory of decisions ──
        try:
            adr_ctx = self.decision_log.format_context(current_iteration=0)
            if adr_ctx:
                parts.append(adr_ctx)
        except Exception:
            pass

        # ── ADR Override — Cognitive Friction rule ──
        parts.append(
            "## Rule:\n"
            "To override an active ADR decision, create `.opencode/override_justification.json` "
            "with: trigger (<ADR-ID> violation), evidence_type (commit|metric), "
            "evidence_ref (commit:<hash>:<glob>|metric:<name>:<value>), "
            "predicted_side_effects ([str]). System validates evidence_ref against real git/metric data."
        )

        # ── Decision Outcomes — historical results ──
        try:
            oc_ctx = self.decision_log.format_outcomes_context()
            if oc_ctx:
                parts.append(oc_ctx)
        except Exception:
            pass

        # ── Plan Drift — architectural intent status ──
        try:
            pd_ctx = self.plan_drift.format_context()
            if pd_ctx:
                parts.append(pd_ctx)
        except Exception:
            pass

        # ── Knowledge Freshness — stale data warnings ──
        try:
            kf_ctx = self.knowledge_freshness.format_context()
            if kf_ctx:
                parts.append(kf_ctx)
        except Exception:
            pass

        return "\n\n".join(parts)

    def _format_depgraph_context(self, user_prompt: str) -> str:
        """Dependency Graph context injection — tìm file liên quan đến prompt,
        thông báo cho AI biết các file bị ảnh hưởng."""
        if not self._dep_graph_built:
            return ""
        # Tìm file paths trong prompt
        file_candidates = re.findall(r'[\w/\\]+\.\w+', user_prompt)
        seen: set[str] = set()
        lines: list[str] = []
        for fc in file_candidates:
            norm = fc.replace("\\", "/")
            if norm in seen:
                continue
            seen.add(norm)
            affected = self.dep_graph.get_all_dependents(norm, depth=1)
            if affected:
                sorted_a = sorted(affected)[:8]
                text = ", ".join(sorted_a)
                if len(affected) > 8:
                    text += f" ... +{len(affected) - 8} file"
                lines.append(f"  {norm} → ảnh hưởng {len(affected)} file: {text}")
            deps = self.dep_graph.get_dependencies(norm)
            if deps:
                sorted_d = sorted(deps)[:5]
                lines.append(f"  {norm} ← phụ thuộc {len(deps)} file: {', '.join(sorted_d)}")
        if lines:
            return "## Dependency Graph Impact:\n" + "\n".join(lines)
        return ""

    def _check_semantic_damage(self, modified_files: set[str], iteration: int):
        """So sánh AST trước và sau khi write, phát hiện function/class bị xoá + export break."""
        from core.services.semantic_detector import SemanticDamageResult
        result = SemanticDamageResult()
        # Lấy old content từ checkpoint gần nhất
        if not self.checkpoint_mgr._checkpoints:
            return None
        cp = self.checkpoint_mgr._checkpoints[-1]
        current_symbols: dict[str, list] = {}
        for f in sorted(modified_files):
            old_content = cp.files.get(f)
            if old_content is None:
                continue
            try:
                p = Path(self._project_root) / f
                if not p.exists():
                    continue
                new_content = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            try:
                fr = self.semantic_detector.check_file_changes(f, old_content, new_content)
                if fr:
                    result.issues.extend(fr.issues)
                    result.deleted.extend(fr.deleted)
                    result.changed_signatures.extend(fr.changed_signatures)
                # Collect current symbols for API registry
                fs = self.semantic_detector.extract_symbols(f, new_content)
                if fs:
                    current_symbols[f] = fs.symbols
            except Exception:
                pass
        # ── Exported API Registry check ──
        try:
            export_issues = self.api_registry.check_exports(current_symbols)
            for ei in export_issues:
                result.issues.append(ei)
            # Update registry for modified files
            for f, symbols in current_symbols.items():
                self.api_registry.update(f, symbols)
        except Exception:
            pass
        # ── Call-site risk analysis via Dependency Graph + Symbol Dep Graph ──
        if result.deleted or result.changed_signatures:
            try:
                # Pass file paths from checkpoint for dep graph query
                for f in modified_files:
                    if f in cp.files:
                        result.analyze_call_site_risk(self.dep_graph, file_path=f, symbol_dep_graph=self.symbol_dep_graph)
                        break
            except Exception:
                pass
        if result.issues:
            return result
        return None

    def _should_load_design_system(self) -> bool:
        """Check if the project has web UI files (HTML, TSX, JSX, CSS)."""
        root = self._project_root
        web_extensions = (".html", ".tsx", ".jsx", ".css", ".scss", ".less")
        try:
            for entry in root.rglob("*"):
                if entry.suffix.lower() in web_extensions:
                    return True
        except Exception:
            pass
        return False

    _cached_project_tree: str | None = None

    def _get_project_tree(self, max_depth: int = 3) -> str:
        """Build a compact project tree (depth 3) showing directory structure."""
        if self._cached_project_tree is not None:
            return self._cached_project_tree
        root = self._project_root
        ignored = {".git", ".orca", "node_modules", "venv", "env", "__pycache__",
                   ".pytest_cache", ".idea", ".vscode", "build", "dist", "vendor",
                   ".agents", "__pycache__", "egg-info"}
        lines = ["## Cấu trúc dự án:\n"]
        def _walk(path: Path, depth: int):
            if depth > max_depth:
                return
            try:
                entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
            except PermissionError:
                return
            for entry in entries:
                if entry.name.startswith(".") or entry.name in ignored:
                    continue
                indent = "  " * depth
                if entry.is_dir():
                    lines.append(f"{indent}📁 {entry.name}/")
                    _walk(entry, depth + 1)
                else:
                    lines.append(f"{indent}📄 {entry.name}")
        _walk(root, 0)
        result = "\n".join(lines[:80])
        self._cached_project_tree = result
        return result

    def _is_vague_request(self, prompt: str) -> bool:
        """Check if a request is too vague for auto execution.
        Returns True if the prompt doesn't contain enough actionable information."""
        p = prompt.strip().lower()

        # Rule 1: ≤5 từ → luôn vague (chỉ chào hỏi)
        if len(p.split()) <= 5:
            return True

        # Rule 2: ≤15 từ và không có action keyword → vague
        action_keywords = (
            "tạo", "sửa", "xóa", "thêm", "chạy", "run",
            "viết", "ghi", "đọc", "fix", "create", "add", "delete",
            "install", "config", "setup", "làm", "build", "deploy",
            "tìm", "đổi", "chỉnh", "code", "file",
        )
        has_action = any(kw in p for kw in action_keywords)
        if len(p) < 15 and not has_action:
            return True

        # Rule 3: No file paths, no specific commands, no code keywords
        has_specificity = any(pat in p for pat in (
            ".py", ".js", ".ts", ".html", ".css", ".json", ".toml",
            ".txt", ".md", ".vue", ".tsx", ".jsx",
        ))
        if not has_specificity and not has_action:
            return True

        return False

    # ─── Clarify vague requests ──────────────────────────────────────────────

    async def _clarify_request(self, prompt: str, suggested_questions: list[str] | None = None) -> str | None:
        """Ask AI to generate clarifying questions, present to user.
        Saves pending clarification state so next user message continues the flow.
        """
        cb = self.callbacks
        suggestions = ""
        if suggested_questions:
            suggestions = "Gợi ý câu hỏi:\n" + "\n".join(f"- {q}" for q in suggested_questions) + "\n\n"
        clarify_prompt = (
            f"User đưa ra yêu cầu: \"{prompt}\"\n\n"
            "Yêu cầu này quá chung chung. Hãy đưa ra 1-2 câu hỏi ngắn để làm rõ:\n"
            "- Họ muốn tạo/sửa file nào?\n"
            "- Dùng công nghệ gì?\n"
            "- Mục tiêu cụ thể là gì?\n\n"
            f"{suggestions}"
            "Chỉ đưa ra câu hỏi, KHÔNG thực thi gì cả."
        )
        try:
            response, _, _, _ = _unpack_ai_result(
                await _call_ai(self.client, self.cfg, [
                    {"role": "system", "content": "Bạn là trợ lý làm rõ yêu cầu."},
                    {"role": "user", "content": clarify_prompt},
                ], on_status=cb.on_status)
            )
        except Exception:
            return None

        clarify_text = response.strip()
        cb.on_chat(f"[#f59e0b]❓ {clarify_text}[/#f59e0b]")
        cb.on_status("Chờ phản hồi từ user...")

        # Save pending clarification state for next user message
        self.session.pending_clarification = {
            "original_prompt": prompt,
            "suggested_questions": suggested_questions or [],
            "clarify_text": clarify_text,
        }
        cb.on_done(0.0)

        # Return empty string to signal "awaiting user input" (not None which means error)
        return ""

    # ─── CLI fallback for plan approval ───────────────────────────────────────

    def _cli_plan_approval(self, plan_text: str) -> str:
        """CLI fallback plan approval (used outside TUI)."""
        console.print(Panel(plan_text, title="[bold #38bdf8]Agent Plan[/bold #38bdf8]", border_style="cyan"))
        console.print("\n[bold]Review the plan above.[/bold]")
        while True:
            try:
                choice = input("  Approve: [S]tep-by-step / [A]utopilot | [R]evise / [C]ancel: ").strip().lower()
                if choice in ("s", "step"):
                    return "approve_step"
                elif choice in ("a", "auto", "autopilot", "y", "yes", ""):
                    return "approve_auto"
                elif choice in ("c", "cancel", "n", "no", "q", "quit"):
                    return "cancel"
                elif choice in ("r", "revise", "e", "edit"):
                    feedback = input("  Your revision request: ").strip()
                    if not feedback:
                        console.print("[yellow]No revision provided. Choose again.[/yellow]")
                        continue
                    return feedback
            except (EOFError, KeyboardInterrupt):
                return "cancel"

