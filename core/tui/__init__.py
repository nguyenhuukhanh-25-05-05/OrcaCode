"""OrcaCode TUI package — modular Textual-based terminal UI."""

from core.tui.app import OrcaTUI, run_tui
from core.tui.css import CANONICAL_PROVIDERS, OCEAN_CSS, PROVIDER_MODELS
from core.tui.modals import (
    ApprovalModal,
    AutopilotWarningModal,
    InstallPromptModal,
    PlanReviewModal,
    SetupModal,
)
from core.tui.utils import _format_duration, get_clipboard_text, set_clipboard_text
from core.tui.widgets import (
    ChatPanel,
    Composer,
    ComposerInput,
    FileSuggestions,
    TopBar,
    WorkPanel,
)

__all__ = [
    "OrcaTUI",
    "run_tui",
    "OCEAN_CSS",
    "PROVIDER_MODELS",
    "CANONICAL_PROVIDERS",
    "InstallPromptModal",
    "SetupModal",
    "ApprovalModal",
    "AutopilotWarningModal",
    "PlanReviewModal",
    "_format_duration",
    "get_clipboard_text",
    "set_clipboard_text",
    "TopBar",
    "ChatPanel",
    "WorkPanel",
    "FileSuggestions",
    "ComposerInput",
    "Composer",
]
