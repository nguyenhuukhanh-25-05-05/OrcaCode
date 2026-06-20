"""OrcaCode Core — public API.

Usage:
    from core import AgentController, load_config, AppConfig
"""

from core.agent import AgentController, SYSTEM_PROMPT_EXECUTE as SYSTEM_PROMPT
from core.git_repo import GitRepo, GitError
from core.summarizer import ChatSummarizer
from core.commands import handle_command, is_command
from core.models import SearchResult, PatchOperation, PatchResult, DiffLine, SessionState
from core.tui import run_tui
from core.ui import StatusBar, show_diff_summary, show_tool_call, show_result, show_error, show_warning, show_config

from config.settings import AppConfig, ModelConfig, PatchConfig, SecurityConfig, CodeGraphConfig, load_config
from core.constants import (
    MAX_RESPONSE_CHARS, MAX_EXECUTE_ITERATIONS, MAX_PLAN_ITERATIONS, MAX_FIX_ITERATIONS,
    MAX_CONSECUTIVE_FAILURES, SUBPROCESS_DEFAULT_TIMEOUT, SUBPROCESS_LONG_TIMEOUT,
)

__all__ = [
    "AgentController", "SYSTEM_PROMPT",
    "GitRepo", "GitError",
    "ChatSummarizer", "handle_command", "is_command",
    "SearchResult", "PatchOperation", "PatchResult", "DiffLine", "SessionState",
    "run_tui",
    "StatusBar", "show_diff_summary", "show_tool_call", "show_result", "show_error", "show_warning", "show_config",
    "AppConfig", "ModelConfig", "PatchConfig", "SecurityConfig", "CodeGraphConfig", "load_config",
    "MAX_RESPONSE_CHARS", "MAX_EXECUTE_ITERATIONS", "MAX_PLAN_ITERATIONS", "MAX_FIX_ITERATIONS",
    "MAX_CONSECUTIVE_FAILURES", "SUBPROCESS_DEFAULT_TIMEOUT", "SUBPROCESS_LONG_TIMEOUT",
]
