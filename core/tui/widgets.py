"""Widget components for OrcaCode TUI."""

import re
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widget import Widget
from textual.widgets import Button, Label, ListView, ListItem, RichLog, Select, Static, TextArea

from core.tui.css import CANONICAL_PROVIDERS, PROVIDER_MODELS
from core.tui.utils import get_clipboard_text, set_clipboard_text


class SafeCollapsible(Vertical):
    DEFAULT_CSS = """
    SafeCollapsible {
        height: auto;
        margin-bottom: 1;
    }
    .safe-collapsible-title {
        width: 1fr;
        color: #eab308;
        height: auto;
        padding: 0;
    }
    .safe-collapsible-title:hover {
        text-style: bold;
    }
    .safe-collapsible-content {
        height: auto;
        display: none;
        padding: 0 0 0 2;
    }
    """
    def __init__(self, content_widget, title="Toggle"):
        super().__init__()
        self.content_widget = content_widget
        self._title = title
        self._is_collapsed = True
        
    def compose(self) -> ComposeResult:
        from textual.widgets import Static
        yield Static(f"+ {self._title}", id="toggle-label", classes="safe-collapsible-title")
        self.content_widget.add_class("safe-collapsible-content")
        yield self.content_widget
        
    def on_click(self, event) -> None:
        if getattr(event.control, "id", None) == "toggle-label":
            self._is_collapsed = not self._is_collapsed
            event.control.update(f"- {self._title}" if not self._is_collapsed else f"+ {self._title}")
            self.content_widget.display = not self._is_collapsed


class TopBar(Widget):
    """Top status bar showing version, model, project, mode and token cost."""
    def __init__(self, model: str = "deepseek-chat", provider: str = "deepseek", mode: str = "Review"):
        super().__init__(id="status-bar")
        self.model_name = model
        self.provider_name = provider
        self.mode_name = mode

    def compose(self) -> ComposeResult:
        with Horizontal(id="topbar-left"):
            yield Label("🐋 OrcaCode", id="topbar-logo")
            yield Button(f"Mode: {self.mode_name}", id="btn-toggle-mode", classes="topbar-btn")
            yield Button("Settings", id="btn-topbar-settings", classes="topbar-btn")

        with Horizontal(id="topbar-right"):
            yield Label("Cost: $0.000000 | Tok: 0", id="topbar-cost", classes="topbar-item")

            yield Select(
                options=[(p, p) for p in CANONICAL_PROVIDERS],
                value=self.provider_name if self.provider_name in CANONICAL_PROVIDERS else CANONICAL_PROVIDERS[0],
                id="topbar-select-provider",
                allow_blank=False
            )

            prov = self.provider_name.lower().strip()
            models = PROVIDER_MODELS.get(prov, ["deepseek-chat"])
            if self.model_name in models:
                model_value = self.model_name
                model_options = list(models)
            else:
                model_value = models[0] if models else self.model_name
                model_options = [model_value] + [m for m in models if m != model_value]

            display_models = []
            for m in model_options:
                if len(m) > 25:
                    display_models.append((f"{m[:25]}...", m))
                else:
                    display_models.append((m, m))
            yield Select(
                options=display_models,
                value=model_value,
                id="topbar-select-model",
                allow_blank=False
            )
            yield Label("Status: Ready", id="status-inner", classes="topbar-item")


class ChatPanel(VerticalScroll):
    """Main chat log showing AI responses and diffs."""
    _WRAP_LIMIT = 160
    _ANSI_RE = re.compile(
        r'\x1b(?:\[[0-9;:<=>?]*[a-zA-Z]|\][^\x07]*(?:\x07|\x1b\\)|[@-Z\\-_.])'
        r'|\x9b[0-9;:<=>?]*[a-zA-Z]'
        r'|[\x80-\x9a\x9c-\x9f]'
    )
    _CTRL_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0d\x0e-\x1f\x7f-\x9f]')
    _MARKUP_RE = re.compile(r'\[(?:/|#|bold\b|italic\b|underline\b|strike\b|reverse\b|dim\b|on\s|rgb\()')

    def __init__(self, *args, **kwargs):
        kwargs.pop("wrap", None)
        kwargs.pop("max_lines", None)
        super().__init__(*args, **kwargs)
        self.styles.overflow_x = "hidden"
        self.styles.overflow_y = "scroll"
        self.styles.scrollbar_size_horizontal = 0
        self.styles.scrollbar_size_vertical = 0
        self._current_tools_collapsible = None
        self._current_tools_static = None
        self._current_tools_text = ""
        self._in_startup = True

    def scroll_end(self, *args, **kwargs) -> None:
        """Override scroll_end to prevent scrolling to bottom during startup."""
        if getattr(self, "_in_startup", False):
            return
        super().scroll_end(*args, **kwargs)

    @staticmethod
    def _sanitize(text: str) -> str:
        text = ChatPanel._ANSI_RE.sub('', text)
        text = ChatPanel._CTRL_RE.sub('', text)
        return text

    def _clean_ai_response(self, text: str) -> str:
        text = re.sub(r"<(?:thought|TASK_REVIEW|PLAN_REVIEW)>.*?</(?:thought|TASK_REVIEW|PLAN_REVIEW)>", "", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"</?(?:DONE|PLAN_DONE)\s*/?>", "", text, flags=re.IGNORECASE)
        text = re.sub(r"^\s*Done\.?\s*$", "", text, flags=re.IGNORECASE | re.MULTILINE)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def write_ai_response(self, text: str, title: str = "AI") -> None:
        self._current_tools_collapsible = None
        text = self._sanitize(text)
        
        import re
        from rich.markdown import Markdown
        from rich.padding import Padding
        from textual.widgets import Static
        
        # Extract special blocks into collapsibles
        for tag in ["thought", "TASK_REVIEW", "PLAN_REVIEW", "SPEC_REVIEW"]:
            match = re.search(fr"<{tag}>(.*?)</{tag}>", text, flags=re.IGNORECASE | re.DOTALL)
            if match:
                content = match.group(1).strip()
                if content:
                    title = tag.replace("_", " ").title()
                    self.mount(SafeCollapsible(Static(Markdown(content, code_theme="monokai")), title=title))
        
        clean = self._clean_ai_response(text)
        
        if clean:
            self.mount(Static(Padding(Markdown(clean, code_theme="monokai"), (1, 0, 1, 2))))
            
        self.scroll_end(animate=False)

    def write_user_message(self, text: str) -> None:
        self._current_tools_collapsible = None
        text = self._sanitize(text)
        from rich.text import Text
        from textual.widgets import Static
        
        widget = Static(Text(text, style="#E0E0E0"), classes="user-message")
        self.mount(widget)
        self.scroll_end(animate=False)

    def write_tool_log(self, text: str) -> None:
        text = self._sanitize(text)
        from textual.widgets import Static, Label
        from rich.text import Text
        from rich.markup import escape as rich_escape
        
        if text.startswith("--- Iteration"):
            self._current_tools_collapsible = None
            lbl = Label(text, classes="iteration-header")
            lbl.styles.width = "1fr"
            lbl.styles.content_align = ("center", "middle")
            lbl.styles.color = "#3498db"
            self.mount(lbl)
            return
 
        if "[" in text and "]" in text:
            if not self._MARKUP_RE.search(text):
                text = rich_escape(text)
        else:
            text = rich_escape(text)
 
        if self._current_tools_collapsible is None:
            self._current_tools_text = text
            self._current_tools_static = Static(Text.from_markup(self._current_tools_text))
            self._current_tools_collapsible = SafeCollapsible(self._current_tools_static, title="Tool Executions & Logs")
            self.mount(self._current_tools_collapsible)
        else:
            self._current_tools_text += "\n" + text
            self._current_tools_static.update(Text.from_markup(self._current_tools_text))
        
        self.scroll_end(animate=False)

    def on_key(self, event) -> None:
        if event.key == "ctrl+a":
            event.prevent_default()
            event.stop()
            if hasattr(self.screen, "_select_all_in_widget"):
                self.screen._select_all_in_widget(self)
                self.write("[#FFFFFF]✔ Đã bôi đen toàn bộ nội dung Chat![/]")
        elif event.key == "ctrl+c":
            event.prevent_default()
            event.stop()
            selected = self.screen.get_selected_text()
            if selected:
                from .utils import set_clipboard_text
                set_clipboard_text(selected)
                self.write("[#FFFFFF]✔ Đã sao chép nội dung bôi đen vào Clipboard![/]")
 
    def write(self, content, *args, **kwargs) -> None:
        self._current_tools_collapsible = None
        if isinstance(content, str):
            content = self._sanitize(content)
            if "[" in content and "]" in content:
                from rich.text import Text
                from rich.markup import escape as rich_escape
                if self._MARKUP_RE.search(content):
                    try:
                        content = Text.from_markup(content)
                    except Exception:
                        content = rich_escape(content)
                else:
                    content = rich_escape(content)
        
        from textual.widgets import Static
        self.mount(Static(content))
        self.scroll_end(animate=False)

    def write_logo(self, content: str) -> None:
        """Mount centered startup logo text — never overflows horizontally."""
        from textual.widgets import Static
        from rich.text import Text
        from rich.align import Align
        try:
            text = Text.from_markup(self._sanitize(content))
            widget = Static(Align.center(text))
        except Exception:
            widget = Static(content)
        widget.add_class("startup-logo")
        # Force layout constraints so double-width chars can't expand the parent
        widget.styles.width = "100%"
        widget.styles.max_width = "100%"
        widget.styles.min_width = 0
        widget.styles.height = "100%"
        widget.styles.overflow_x = "hidden"
        self.mount(widget)
        self.scroll_end(animate=False)
        
    def clear(self) -> None:
        self._current_tools_collapsible = None
        for child in list(self.children):
            child.remove()


class WorkPanel(Vertical):
    """Right sidebar — Active Work, Timeline & System Logs."""
    def compose(self) -> ComposeResult:
        with Vertical(id="sidebar-container"):
            with Vertical(id="work-section"):
                yield Static("[bold]ARCH DEP GRAPH[/bold]", id="work-title")
                with VerticalScroll(id="arch-graph-scroll"):
                    yield Static("  Scanning...", id="arch-graph")
            with Vertical(id="timeline-section"):
                yield Static("[bold]TIMELINE[/bold]", id="timeline-title")
                yield ListView(id="timeline-list")
                with Horizontal(id="timeline-actions"):
                    yield Button("Rollback", id="btn-timeline-rollback", variant="error")
                    yield Button("Xem code", id="btn-timeline-viewcode")
            with Vertical(id="logs-section"):
                yield Static("[bold]SYSTEM LOGS[/bold]", id="logs-title")
                with VerticalScroll(id="logs-list-scroll"):
                    yield Static("No logs yet", id="logs-list")


class FileSuggestions(ListView):
    """Dropdown list for file autocomplete suggestions."""
    def __init__(self):
        super().__init__(id="file-suggestions")
        self.display = False


class _TelexEngine:
    """Vietnamese Telex engine - syllable-aware tone placement."""

    DOUBLE = {
        ('a', 'a'): 'â', ('A', 'A'): 'Â', ('a', 'A'): 'Â', ('A', 'a'): 'Â',
        ('e', 'e'): 'ê', ('E', 'E'): 'Ê', ('e', 'E'): 'Ê', ('E', 'e'): 'Ê',
        ('o', 'o'): 'ô', ('O', 'O'): 'Ô', ('o', 'O'): 'Ô', ('O', 'o'): 'Ô',
        ('d', 'd'): 'đ', ('D', 'D'): 'Đ', ('d', 'D'): 'Đ', ('D', 'd'): 'Đ',
    }

    W_MAP = {
        'a': 'ă', 'A': 'Ă',
        'o': 'ơ', 'O': 'Ơ',
        'u': 'ư', 'U': 'Ư',
    }

    TONE_MAP = {
        'a': {'s': 'á', 'f': 'à', 'r': 'ả', 'x': 'ã', 'j': 'ạ'},
        'e': {'s': 'é', 'f': 'è', 'r': 'ẻ', 'x': 'ẽ', 'j': 'ẹ'},
        'i': {'s': 'í', 'f': 'ì', 'r': 'ỉ', 'x': 'ĩ', 'j': 'ị'},
        'o': {'s': 'ó', 'f': 'ò', 'r': 'ỏ', 'x': 'õ', 'j': 'ọ'},
        'u': {'s': 'ú', 'f': 'ù', 'r': 'ủ', 'x': 'ũ', 'j': 'ụ'},
        'y': {'s': 'ý', 'f': 'ỳ', 'r': 'ỷ', 'x': 'ỹ', 'j': 'ỵ'},
        'â': {'s': 'ấ', 'f': 'ầ', 'r': 'ẩ', 'x': 'ẫ', 'j': 'ậ'},
        'ă': {'s': 'ắ', 'f': 'ằ', 'r': 'ẳ', 'x': 'ẵ', 'j': 'ặ'},
        'ê': {'s': 'ế', 'f': 'ề', 'r': 'ể', 'x': 'ễ', 'j': 'ệ'},
        'ô': {'s': 'ố', 'f': 'ồ', 'r': 'ổ', 'x': 'ỗ', 'j': 'ộ'},
        'ơ': {'s': 'ớ', 'f': 'ờ', 'r': 'ở', 'x': 'ỡ', 'j': 'ợ'},
        'ư': {'s': 'ứ', 'f': 'ừ', 'r': 'ử', 'x': 'ữ', 'j': 'ự'},
    }

    _BASE_VOWEL = {}
    for _b, _ts in TONE_MAP.items():
        for _k, _t in _ts.items():
            _BASE_VOWEL[_t] = _b
    del _b, _ts, _k, _t

    TONE_KEYS = frozenset('sfrxjSFRXJ')
    VOWELS = frozenset('aăâeêioôơuưy')
    _WB = frozenset(' \t\n.,;:!?()[]{}"\'/\\@#$%^&*+=<>~`')

    @classmethod
    def is_vowel(cls, ch: str) -> bool:
        low = ch.lower()
        return low in cls.VOWELS or low in cls._BASE_VOWEL

    @classmethod
    def base(cls, ch: str) -> str:
        return cls._BASE_VOWEL.get(ch.lower(), ch.lower())

    @classmethod
    def apply_tone(cls, vowel: str, key: str) -> str | None:
        b = cls.base(vowel)
        t = key.lower()
        if b in cls.TONE_MAP and t in cls.TONE_MAP[b]:
            r = cls.TONE_MAP[b][t]
            return r.upper() if vowel.isupper() else r
        return None

    @classmethod
    def find_target(cls, word: str) -> int | None:
        vp = [i for i, c in enumerate(word) if cls.is_vowel(c)]
        if not vp:
            return None
        if len(vp) >= 2:
            s = ''.join(cls.base(c) for c in word).lower()
            if (s.startswith('gi') or s.startswith('qu')) and vp[0] == 1:
                vp = vp[1:]
        if len(vp) == 1:
            return vp[0]
        last = word[-1].lower()
        last2 = word[-2:].lower() if len(word) >= 2 else ''
        closed = last2 in ('ch', 'nh', 'ng') or (last in 'cmnpt' and not cls.is_vowel(word[-1]))
        if closed:
            return vp[-1]
        if len(vp) >= 2:
            pair = cls.base(word[vp[-2]]) + cls.base(word[vp[-1]])
            if pair in ('oa', 'oe', 'uê'):
                return vp[-1]
        return vp[-2]

    @classmethod
    def process_tone(cls, word: str, key: str) -> tuple[str, bool]:
        if not word or not any(cls.is_vowel(c) for c in word):
            return word, False
        pos = cls.find_target(word)
        if pos is None:
            return word, False
        toned = cls.apply_tone(word[pos], key)
        if toned is None:
            return word, False
        return word[:pos] + toned + word[pos + 1:], True

    @classmethod
    def process_dia(cls, prev: str, curr: str) -> str | None:
        pair = (prev, curr)
        if pair in cls.DOUBLE:
            return cls.DOUBLE[pair]
        if curr.lower() == 'w' and prev in cls.W_MAP:
            return cls.W_MAP[prev]
        return None


class ComposerInput(TextArea):
    """Sleek multi-line input with built-in Vietnamese Telex support."""

    def __init__(self):
        super().__init__(id="composer-input")
        self.highlight_cursor_line = False
        self.vietnamese_telex_enabled = False
        self._telex_skip = False

    def on_key(self, event) -> None:
        try:
            suggestions = self.app.query_one("#file-suggestions", ListView)
        except Exception:
            suggestions = None

        if suggestions and suggestions.display:
            if event.key == "down":
                event.prevent_default(); event.stop()
                suggestions.action_cursor_down(); return
            elif event.key == "up":
                event.prevent_default(); event.stop()
                suggestions.action_cursor_up(); return
            elif event.key in ("enter", "tab"):
                event.prevent_default(); event.stop()
                self.app.select_suggestion(); return
            elif event.key == "escape":
                event.prevent_default(); event.stop()
                suggestions.display = False; return

        if event.key in ("ctrl+enter", "ctrl+j"):
            event.prevent_default(); event.stop()
            if not self.disabled:
                self.app.trigger_submit()
        elif event.key == "ctrl+d":
            event.prevent_default(); event.stop()
            try: self.app.action_stop_execution()
            except Exception: pass
        elif event.key == "ctrl+v":
            clip_text = get_clipboard_text()
            if clip_text:
                event.prevent_default(); event.stop()
                self._telex_skip = True
                start, end = self.selection
                self.replace(clip_text, start, end)
        elif event.key == "ctrl+c":
            event.prevent_default(); event.stop()
            selected = self.selected_text
            if selected:
                set_clipboard_text(selected)
        elif event.key == "ctrl+x":
            selected = self.selected_text
            if selected:
                event.prevent_default(); event.stop()
                set_clipboard_text(selected)
                self._telex_skip = True
                start, end = self.selection
                self.replace("", start, end)
        elif event.key == "ctrl+a":
            event.prevent_default(); event.stop()
            self.select_all()
        elif event.key == "ctrl+t":
            event.prevent_default(); event.stop()
            self.toggle_vietnamese_telex()

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if not self.vietnamese_telex_enabled or self.disabled:
            return
        if self._telex_skip:
            self._telex_skip = False
            return

        row, col = self.cursor_location
        line = self.document.get_line(row)
        if col == 0 or col > len(line):
            return

        last = line[col - 1]

        if col >= 2:
            prev = line[col - 2]
            dia = _TelexEngine.process_dia(prev, last)
            if dia is not None:
                self._telex_skip = True
                self.replace(dia, (row, col - 2), (row, col))
                return

        if last in _TelexEngine.TONE_KEYS:
            ws = col - 1
            while ws > 0 and line[ws - 1] not in _TelexEngine._WB:
                ws -= 1
            word = line[ws:col - 1]
            if word and any(_TelexEngine.is_vowel(c) for c in word):
                new_word, ok = _TelexEngine.process_tone(word, last)
                if ok:
                    self._telex_skip = True
                    self.replace(new_word, (row, ws), (row, col))

    def toggle_vietnamese_telex(self) -> None:
        self.vietnamese_telex_enabled = not self.vietnamese_telex_enabled
        try:
            help_label = self.app.query_one("#composer-help", Static)
            if self.vietnamese_telex_enabled:
                help_label.update("[Telex ON] Ctrl+Enter Send  |  Ctrl+D Stop  |  Ctrl+T Toggle")
            else:
                help_label.update("Ctrl+Enter Send  |  Ctrl+D Stop  |  Ctrl+L Clear  |  Ctrl+T Telex  |  Ctrl+Q Quit")
        except Exception:
            pass


class Composer(Vertical):
    """Bottom bar with input field."""
    def __init__(self):
        super().__init__(id="composer")

    def compose(self) -> ComposeResult:
        yield FileSuggestions()
        yield ComposerInput()
        yield Static("Ctrl+Enter Send  |  Ctrl+D Stop  |  Ctrl+L Clear  |  Ctrl+T Telex  |  Ctrl+Q Quit", id="composer-help")
