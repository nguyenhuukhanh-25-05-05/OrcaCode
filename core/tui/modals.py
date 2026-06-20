"""Modal screens for OrcaCode TUI."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Collapsible, Input, Label, RadioButton, RadioSet, Static

from core.tui.css import PROVIDER_MODELS
from config.settings import get_provider_package, get_provider_pip_package


class InstallPromptModal(ModalScreen[bool]):
    '''Ask user to install a missing pip package.'''
    def __init__(self, provider: str, pip_pkg: str):
        super().__init__()
        self.provider = provider
        self.pip_pkg = pip_pkg

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("[bold #FFFFFF]Thiếu package![/]", id="install-title"),
            Label(
                f"Provider [cyan]{self.provider}[/] cần package [yellow]{self.pip_pkg}[/].\n"
                f"Cài đặt ngay? (pip install {self.pip_pkg})",
                id="install-desc",
            ),
            Horizontal(
                Button("Install", id="btn-install-yes"),
                Button("Cancel", id="btn-install-no"),
                classes="install-buttons",
            ),
            id="install-container",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "btn-install-yes":
            self.dismiss(True)
        elif event.button.id == "btn-install-no":
            self.dismiss(False)

    CSS = '''
    InstallPromptModal {
        align: center middle;
    }
    #install-container {
        width: 66;
        height: auto;
        padding: 1 3;
        background: #111111;
        border: round #444444;
    }
    #install-title {
        text-style: bold;
        text-align: center;
        width: 100%;
        margin-bottom: 1;
        color: #ffffff;
    }
    #install-desc {
        margin-bottom: 1;
        color: #e0e0e0;
        padding: 1 2;
        background: #000000;
        border: round #333333;
    }
    .install-buttons {
        height: auto;
        min-height: 2;
        align: center middle;
        margin-top: 1;
        padding-top: 1;
    }
    .install-buttons Button {
        margin: 0 2;
        min-width: 16;
        padding: 0 2;
        height: 1;
        border: none;
        text-style: bold;
    }
    #btn-install-yes {
        background: #059669;
        color: #ffffff;
    }
    #btn-install-yes:hover {
        background: #10b981;
    }
    #btn-install-no {
        background: #dc2626;
        color: #ffffff;
    }
    #btn-install-no:hover {
        background: #ef4444;
    }
    '''


class SetupModal(ModalScreen):
    """Full-screen setup wizard for API keys."""
    def __init__(self, config=None):
        super().__init__()
        self.provider = "deepseek"
        self.api_key = ""
        self.model_name = ""
        self.base_url = ""
        self.temperature = "0.2"
        self.max_tokens = "65536"
        self.apply_project = False

        from core.tui.css import CANONICAL_PROVIDERS, PROVIDER_MODELS
        from config.settings import get_api_base_url
        import os

        # Prefill default settings for all canonical providers
        self.provider_settings = {}
        for p in CANONICAL_PROVIDERS:
            models = PROVIDER_MODELS.get(p.lower().strip(), [])
            default_model = models[0] if models else ""

            env_vars = {
                "deepseek": "DEEPSEEK_API_KEY",
                "openai": "OPENAI_API_KEY",
                "anthropic": "ANTHROPIC_API_KEY",
                "gemini": "GEMINI_API_KEY",
                "openrouter": "OPENROUTER_API_KEY",
                "9router": "9ROUTER_API_KEY",
            }
            env_var = env_vars.get(p.lower().strip(), "")
            api_key = os.getenv(env_var, "")

            base_url = get_api_base_url(p)
            if p == "deepseek" and base_url == "https://api.deepseek.com":
                base_url = "https://api.deepseek.com/v1"
            elif p == "openai":
                base_url = "https://api.openai.com/v1"
            elif p == "anthropic":
                base_url = "https://api.anthropic.com"
            elif p == "gemini":
                base_url = "https://generativelanguage.googleapis.com"
            elif p == "openrouter":
                base_url = "https://openrouter.ai/api/v1"
            elif p == "9router":
                base_url = "http://localhost:20128/v1"

            self.provider_settings[p] = {
                "model": default_model,
                "api_key": api_key,
                "base_url": base_url,
            }

        # Override active provider settings using existing configuration
        if config and hasattr(config, "model"):
            m = config.model
            self.provider = getattr(m, "provider", "deepseek") or "deepseek"
            self.api_key = getattr(m, "api_key", "") or ""
            self.model_name = getattr(m, "model", "") or ""
            self.base_url = getattr(m, "base_url", "") or ""
            self.temperature = str(getattr(m, "temperature", "0.2"))
            self.max_tokens = str(getattr(m, "max_tokens", "65536"))

            self.provider_settings[self.provider] = {
                "model": self.model_name,
                "api_key": self.api_key,
                "base_url": self.base_url,
            }

    def compose(self) -> ComposeResult:
        from core.tui.css import CANONICAL_PROVIDERS
        try:
            pressed_idx = CANONICAL_PROVIDERS.index(self.provider.lower().strip())
        except ValueError:
            pressed_idx = 0

        yield Vertical(
            Label("OrcaCode Setup", id="setup-title"),
            Label("Configure your AI provider and API key", id="setup-desc"),
            Label("Provider:"),
            RadioSet(
                *[RadioButton(p, value=(i == pressed_idx)) for i, p in enumerate(CANONICAL_PROVIDERS)],
                id="setup-provider",
            ),
            Label("Model:"),
            Input(value=self.model_name, placeholder="e.g. deepseek-chat", id="setup-model"),
            Label("API Key:"),
            Input(value=self.api_key, placeholder="sk-...", id="setup-api-key", password=True),
            Label("Base URL (optional):"),
            Input(value=self.base_url, placeholder="https://api.deepseek.com/v1", id="setup-base-url"),
            Collapsible(
                Vertical(
                    Label("Temperature:"),
                    Input(value=self.temperature, id="setup-temperature"),
                ),
                title="Advanced Settings",
                id="setup-advanced-collapsible"
            ),
            Checkbox("Apply .env to project directory", value=self.apply_project, id="setup-apply-env"),
            Horizontal(
                Button("Save", id="btn-setup-save"),
                Button("Skip", id="btn-setup-skip"),
                classes="setup-buttons",
            ),
            id="setup-container",
        )

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        from core.tui.css import CANONICAL_PROVIDERS
        if event.radio_set.id == "setup-provider":
            # 1. Save currently displayed settings for the old provider
            try:
                old_model = self.query_one("#setup-model", Input).value.strip()
                old_api_key = self.query_one("#setup-api-key", Input).value.strip()
                old_base_url = self.query_one("#setup-base-url", Input).value.strip()
                self.provider_settings[self.provider] = {
                    "model": old_model,
                    "api_key": old_api_key,
                    "base_url": old_base_url,
                }
            except Exception:
                pass

            # 2. Get the new provider
            idx = event.radio_set.pressed_index
            if idx < 0 or idx >= len(CANONICAL_PROVIDERS):
                return
            new_provider = CANONICAL_PROVIDERS[idx]
            self.provider = new_provider

            # 3. Retrieve settings for the new provider from dictionary
            settings = self.provider_settings.get(new_provider, {
                "model": "",
                "api_key": "",
                "base_url": "",
            })

            # 4. Update the input values in UI
            try:
                self.query_one("#setup-model", Input).value = settings["model"]
                self.query_one("#setup-api-key", Input).value = settings["api_key"]
                self.query_one("#setup-base-url", Input).value = settings["base_url"]
            except Exception:
                pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "btn-setup-save":
            try:
                from core.tui.css import CANONICAL_PROVIDERS
                provider_set = self.query_one("#setup-provider", RadioSet)
                provider_idx = provider_set.pressed_index if provider_set.pressed_index >= 0 else 0
                provider = CANONICAL_PROVIDERS[provider_idx]
            except Exception:
                provider = self.provider

            config = {
                "provider": provider,
                "model": self.query_one("#setup-model", Input).value.strip(),
                "api_key": self.query_one("#setup-api-key", Input).value.strip(),
                "base_url": self.query_one("#setup-base-url", Input).value.strip(),
                "temperature": self.query_one("#setup-temperature", Input).value.strip(),
                "max_tokens": self.max_tokens,
                "apply_project": self.query_one("#setup-apply-env", Checkbox).value,
            }
            self.dismiss(config)
        elif event.button.id == "btn-setup-skip":
            self.dismiss(None)

    CSS = """
    SetupModal {
        align: center middle;
    }
    #setup-container {
        width: 66;
        height: auto;
        padding: 1 3;
        background: #111111;
        border: round #444444;
    }
    #setup-title {
        text-style: bold;
        text-align: center;
        content-align: center middle;
        width: 100%;
        color: #ffffff;
        padding-bottom: 1;
    }
    #setup-desc {
        text-align: center;
        content-align: center middle;
        width: 100%;
        color: #aaaaaa;
        padding-bottom: 2;
    }
    .setup-buttons {
        height: auto;
        min-height: 2;
        align: center middle;
        padding-top: 1;
        margin-top: 1;
    }
    .hidden {
        display: none;
    }
    .setup-buttons Button {
        margin: 0 2;
        min-width: 16;
        padding: 0 2;
        height: 1;
        border: none;
        text-style: bold;
    }
    #btn-setup-save {
        background: #059669;
        color: #ffffff;
    }
    #btn-setup-save:hover {
        background: #10b981;
    }
    #btn-setup-skip {
        background: #475569;
        color: #ffffff;
    }
    #btn-setup-skip:hover {
        background: #64748b;
    }
    #setup-container Label {
        color: #e0e0e0;
        text-style: bold;
        margin-top: 1;
    }
    #setup-container Input {
        background: #000000;
        border: round #333333;
        color: #ffffff;
        margin-bottom: 1;
        padding: 0 1;
    }
    #setup-container Input:focus {
        border: round #666666;
        background: #0a0a0a;
    }
    #setup-container Checkbox {
        background: transparent;
        border: none;
        color: #ffffff;
        margin-top: 1;
    }
    #setup-container Checkbox:focus {
        text-style: bold;
        color: #e0e0e0;
    }
    #setup-container RadioSet {
        background: transparent;
        border: none;
        padding: 0;
        margin-bottom: 1;
    }
    #setup-container RadioButton {
        background: transparent;
        border: none;
        color: #FFFFFF;
        padding: 0 1;
    }
    #setup-container RadioButton:focus {
        text-style: bold;
        color: #00DDFF;
    }
    #setup-container Collapsible {
        background: transparent;
        border: none;
        margin-top: 1;
        padding: 0;
    }
    #setup-container CollapsibleTitle {
        color: #aaaaaa;
        background: transparent;
        text-style: bold;
        padding: 0 1;
    }
    #setup-container CollapsibleTitle:hover {
        color: #ffffff;
        background: #1a1a1a;
    }
    #setup-container CollapsibleTitle:focus {
        color: #ffffff;
        background: #1a1a1a;
    }
    #setup-container Collapsible > Vertical {
        padding: 0 1;
        background: transparent;
        height: auto;
    }
    """


class ApprovalModal(ModalScreen[bool]):
    """Modal for approving or skipping a tool call."""
    def __init__(self, title: str, detail: str = ""):
        super().__init__()
        self.title_text = title
        self.detail_text = detail

    def compose(self) -> ComposeResult:
        display_text = f"{self.title_text}\n\n{self.detail_text}" if self.detail_text else self.title_text
        yield Vertical(
            Label("[bold #FFFFFF]XÁC NHẬN THỰC THI CÔNG CỤ[/]", id="modal-title"),
            Static(display_text, id="modal-detail", markup=False),
            Horizontal(
                Button("Approve", id="btn-approve"),
                Button("Skip", id="btn-skip"),
                Button("Detail", id="btn-detail"),
                classes="modal-buttons",
            ),
            id="modal-container",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "btn-approve":
            self.dismiss(True)
        elif event.button.id == "btn-skip":
            self.dismiss(False)
        elif event.button.id == "btn-detail":
            pass

    CSS = """
    ApprovalModal {
        align: center middle;
    }
    #modal-container {
        width: 76;
        height: auto;
        padding: 1 3;
        background: #111111;
        border: round #444444;
    }
    #modal-title {
        text-style: bold;
        text-align: center;
        content-align: center middle;
        width: 100%;
        color: #ffffff;
        padding-bottom: 1;
    }
    #modal-detail {
        padding: 1 2;
        max-height: 20;
        background: #000000;
        border: round #333333;
        color: #e0e0e0;
        overflow-y: auto;
        overflow-x: hidden;
        margin-bottom: 1;
    }
    .modal-buttons {
        height: auto;
        min-height: 2;
        align: center middle;
        padding-top: 1;
    }
    .modal-buttons Button {
        margin: 0 1;
        min-width: 16;
        padding: 0 2;
        height: 1;
        border: none;
        text-style: bold;
    }
    #btn-approve {
        background: #059669;
        color: #ffffff;
    }
    #btn-approve:hover {
        background: #10b981;
    }
    #btn-skip {
        background: #dc2626;
        color: #ffffff;
    }
    #btn-skip:hover {
        background: #ef4444;
    }
    #btn-detail {
        background: #3498db;
        color: #ffffff;
    }
    #btn-detail:hover {
        background: #54b4eb;
    }
    """


class AutopilotWarningModal(ModalScreen[bool]):
    """Warning modal before entering full autopilot mode."""
    def __init__(self, warning_info: str = ""):
        super().__init__()
        self.warning_info = warning_info

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("[bold #FFFFFF]CẢNH BÁO: CHẾ ĐỘ AUTO-PILOT[/]", id="warning-title"),
            Static(self.warning_info if self.warning_info else "", id="warning-detail", markup=False),
            Horizontal(
                Button("Tôi hiểu, tiếp tục", id="btn-warning-agree"),
                Button("Quay lại", id="btn-warning-back"),
                classes="warning-buttons",
            ),
            id="warning-container",
        )

    CSS = """
    AutopilotWarningModal {
        align: center middle;
    }
    #warning-container {
        width: 70;
        height: auto;
        padding: 1 3;
        background: #111111;
        border: round #444444;
    }
    #warning-title {
        text-style: bold;
        text-align: center;
        width: 100%;
        color: #ffffff;
        padding-bottom: 1;
    }
    #warning-detail {
        padding: 1 2;
        max-height: 18;
        min-height: 6;
        background: #000000;
        border: round #333333;
        color: #e0e0e0;
        overflow-y: auto;
        overflow-x: hidden;
        margin-bottom: 1;
    }
    .warning-buttons {
        height: auto;
        min-height: 2;
        align: center middle;
        padding-top: 1;
    }
    .warning-buttons Button {
        margin: 0 2;
        min-width: 16;
        padding: 0 2;
        height: 1;
        border: none;
        text-style: bold;
    }
    #btn-warning-agree {
        background: #dc2626;
        color: #ffffff;
    }
    #btn-warning-agree:hover {
        background: #ef4444;
    }
    #btn-warning-back {
        background: #475569;
        color: #ffffff;
    }
    #btn-warning-back:hover {
        background: #64748b;
    }
    """

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "btn-warning-agree":
            self.dismiss(True)
        elif event.button.id == "btn-warning-back":
            self.dismiss(False)


class PlanReviewModal(ModalScreen[str]):
    """Modal for reviewing and approving an execution plan."""
    def __init__(self, plan_content: str):
        super().__init__()
        self.plan_content = plan_content
        self.revision_prompt = ""

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("[bold #FFFFFF]KẾ HOẠCH THỰC THI[/]", id="plan-title"),
            Static(self.plan_content, id="plan-detail", markup=False),
            Label("Yêu cầu chỉnh sửa (nếu cần):", id="plan-hint"),
            Input(placeholder="Nhập yêu cầu chỉnh sửa kế hoạch...", id="plan-revision-input"),
            Horizontal(
                Button("Approve Step", id="btn-plan-approve-step"),
                Button("Approve Auto", id="btn-plan-approve-auto"),
                Button("Revise", id="btn-plan-revise"),
                Button("Cancel", id="btn-plan-cancel"),
                classes="plan-buttons",
            ),
            id="plan-container",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        btn_id = event.button.id
        if btn_id == "btn-plan-approve-step":
            self.dismiss("approve_step")
        elif btn_id == "btn-plan-approve-auto":
            self.dismiss("approve_auto")
        elif btn_id == "btn-plan-revise":
            revision = self.query_one("#plan-revision-input", Input).value.strip()
            self.dismiss(f"revise:{revision}" if revision else "revise")
        elif btn_id == "btn-plan-cancel":
            self.dismiss("cancel")

    CSS = """
    PlanReviewModal {
        align: center middle;
    }
    #plan-container {
        width: 94;
        height: auto;
        max-height: 42;
        padding: 1 3;
        background: #111111;
        border: round #444444;
    }
    #plan-title {
        text-style: bold;
        text-align: center;
        width: 100%;
        color: #ffffff;
        padding-bottom: 1;
    }
    #plan-hint {
        color: #aaaaaa;
        margin-top: 1;
        margin-bottom: 0;
    }
    #plan-detail {
        padding: 1 2;
        max-height: 20;
        background: #000000;
        border: round #333333;
        color: #e0e0e0;
        overflow-y: auto;
        overflow-x: hidden;
        margin-bottom: 1;
    }
    #plan-revision-input {
        background: #000000;
        border: round #333333;
        color: #ffffff;
        margin-bottom: 1;
        padding: 0 1;
    }
    #plan-revision-input:focus {
        border: round #666666;
        background: #0a0a0a;
    }
    .plan-buttons {
        height: auto;
        min-height: 2;
        align: center middle;
        padding-top: 1;
    }
    .plan-buttons Button {
        margin: 0 1;
        min-width: 16;
        padding: 0 2;
        height: 1;
        border: none;
        text-style: bold;
    }
    #btn-plan-approve-step {
        background: #059669;
        color: #ffffff;
    }
    #btn-plan-approve-step:hover {
        background: #10b981;
    }
    #btn-plan-approve-auto {
        background: #3498db;
        color: #ffffff;
    }
    #btn-plan-approve-auto:hover {
        background: #54b4eb;
    }
    #btn-plan-revise {
        background: #d97706;
        color: #ffffff;
    }
    #btn-plan-revise:hover {
        background: #f59e0b;
    }
    #btn-plan-cancel {
        background: #dc2626;
        color: #ffffff;
    }
    #btn-plan-cancel:hover {
        background: #ef4444;
    }
    #plan-container Label {
        color: #aaaaaa;
        text-style: bold;
        margin-top: 1;
    }
    """
