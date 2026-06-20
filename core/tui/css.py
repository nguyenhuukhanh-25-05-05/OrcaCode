"""Ocean Blue Theme — Original OrcaCode TUI."""

PROVIDER_MODELS = {
    "deepseek": ["deepseek-v4-pro", "deepseek-v4-flash", "deepseek-chat", "deepseek-reasoner"],
    "openai": ["gpt-5.5-pro", "gpt-5.5", "gpt-5.5-instant", "gpt-5", "gpt-4o", "gpt-4o-mini", "o1-mini"],
    "anthropic": ["claude-fable-5", "claude-opus-4.8", "claude-sonnet-4.6", "claude-haiku-4.5", "claude-3-5-sonnet-latest", "claude-3-5-haiku-latest"],
    "gemini": ["gemini-3.5-pro", "gemini-3.5-flash", "gemini-3-deep-think", "gemini-3.1-pro", "gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash"],
    "openrouter": ["meta-llama/llama-3.3-70b-instruct", "deepseek/deepseek-chat", "openai/gpt-4o"],
    "9router": [],
}

CANONICAL_PROVIDERS = ["deepseek", "openai", "anthropic", "gemini", "openrouter", "9router"]

OCEAN_CSS = """
Screen {
    background: #080808;
    color: #E0E0E0;
}

* {
    scrollbar-size: 1 0;
    scrollbar-color: #555555;
    scrollbar-color-hover: #777777;
    scrollbar-color-active: #E0E0E0;
    scrollbar-background: #080808;
    scrollbar-background-hover: #0d0d0d;
    scrollbar-background-active: #111111;
    scrollbar-corner-color: #080808;
}

.hidden {
    display: none;
}

/* ==================== LAYOUT ==================== */

#main-layout {
    height: 1fr;
    layout: horizontal;
    padding: 0;
    margin: 0;
}

#chat-area {
    height: 1fr;
    width: 1fr;
    min-width: 0;
}

/* ==================== SIDEBAR ==================== */

#sidebar {
    width: 42;
    min-width: 32;
    height: 1fr;
    background: #0a0a0a;
    border-left: heavy #555555;
    padding: 0;
}

#sidebar-container {
    height: 1fr;
    padding: 0;
    margin: 0;
    border-left: none;
    background: #1e1e1e;
}

/* --- Section base --- */
#work-section {
    padding-top: 1;
}

#work-section,
#timeline-section,
#logs-section {
    height: 1fr;
    min-height: 5;
    margin: 0;
    background: #0a0a0a;
    border: none;
    padding: 0;
}

/* --- Section titles (1 line only) --- */
#work-title,
#timeline-title,
#logs-title {
    text-style: bold;
    color: #FFFFFF;
    padding: 0 1;
    height: 1;
    border: none;
    margin: 0;
    background: #1e1e1e;
    width: 100%;
}

/* --- Arch Dep Graph --- */
#arch-graph-scroll {
    height: 1fr;
    overflow-y: auto;
    overflow-x: hidden;
    padding: 0 1;
}

#arch-graph {
    color: #BBBBBB;
}

#work-list {
    padding: 0 1;
    color: #BBBBBB;
}

/* --- Timeline --- */
#timeline-list {
    height: 1fr;
    background: transparent;
    color: #BBBBBB;
    margin: 0;
    padding: 0 1;
    overflow-y: auto;
    overflow-x: hidden;
}

#timeline-list > ListItem {
    padding: 0 1;
    background: transparent;
    color: #BBBBBB;
}

#timeline-list > ListItem:hover {
    background: #222222;
}

#timeline-list > ListItem.-highlight {
    background: #444444;
    color: #FFFFFF;
    text-style: bold;
}

#timeline-actions {
    height: 3;
    margin: 0;
    padding: 0 1;
    align: center middle;
    border-top: none;
}

#timeline-actions Button {
    height: 1;
    margin: 0 1;
    min-width: 14;
    padding: 0 2;
    border: none;
    background: #3498db;
    color: #ffffff;
    text-style: bold;
}

#timeline-actions Button:hover {
    background: #54b4eb;
    color: #ffffff;
}

#timeline-actions #btn-timeline-rollback {
    background: #dc2626;
    color: #ffffff;
}

#timeline-actions #btn-timeline-rollback:hover {
    background: #ef4444;
    color: #ffffff;
}

/* --- System Logs --- */
#logs-list-scroll {
    height: 1fr;
    overflow-y: auto;
    overflow-x: hidden;
    padding: 0 1;
}

#system-logs {
    height: auto;
    background: #0a0a0a;
    border: none;
    padding: 0;
    overflow-y: auto;
    overflow-x: hidden;
    color: #AAAAAA;
}

/* ==================== STATUS BAR ==================== */

#status-bar {
    dock: top;
    height: auto;
    background: transparent;
    border-bottom: heavy #555555;
    layout: grid;
    grid-size: 2;
    grid-columns: 1fr auto;
    padding: 0 1;
}

#topbar-left, #topbar-right {
    height: auto;
    layout: horizontal;
}

#topbar-right {
    align: right middle;
}

.topbar-sep {
    color: #555555;
    padding: 0 1;
}

.topbar-item {
    padding: 0 1;
    height: 1;
    content-align: center middle;
    color: #AAAAAA;
}

.topbar-btn {
    border: none;
    min-width: 4;
    height: 1;
    background: transparent;
    color: #E0E0E0;
    padding: 0 1;
}

Button.topbar-btn {
    background: transparent;
    color: #E0E0E0;
    border: none;
    height: 1;
    min-width: 0;
    padding: 0 1;
    margin: 0;
    text-style: bold;
}

Button.topbar-btn:hover {
    color: #88FFCC;
    background: #111111;
}

#status-inner {
    max-width: 25;
    overflow: hidden;
    text-overflow: ellipsis;
    content-align: left middle;
}

#btn-toggle-mode {
    min-width: 15;
}

#topbar-logo {
    background: transparent;
    color: #FFFFFF;
    text-style: bold;
    padding: 0 1;
    height: 1;
    margin-right: 1;
}

/* ==================== SELECT DROPDOWNS ==================== */

#topbar-select-provider {
    border: none;
    height: 1;
    background: transparent;
    color: #E0E0E0;
    padding: 0 1;
    margin: 0 1;
    min-width: 16;
}

#topbar-select-provider > SelectCurrent {
    border: none;
    background: transparent;
    height: 1;
    padding: 0 1;
}

#topbar-select-provider > SelectCurrent:focus {
    border: none;
    background: #080808;
}

#topbar-select-provider > SelectOverlay {
    background: #0d0d0d;
    border: none;
    color: #E0E0E0;
}

#topbar-select-provider > SelectOverlay > OptionList > Option {
    color: #E0E0E0;
}

#topbar-select-provider > SelectOverlay > OptionList > Option:hover {
    background: #444444;
    color: #FFFFFF;
}

#topbar-select-provider > SelectOverlay > OptionList > Option.-highlighted {
    background: #444444;
    color: #FFFFFF;
}

#topbar-select-model {
    border: none;
    height: 1;
    background: transparent;
    color: #E0E0E0;
    padding: 0 1;
    margin: 0 1;
    min-width: 25;
    max-width: 28;
    overflow-x: hidden;
}

#topbar-select-model > SelectCurrent {
    border: none;
    background: transparent;
    height: 1;
    padding: 0 1;
    overflow: hidden;
    text-overflow: ellipsis;
}

#topbar-select-model > SelectCurrent:focus {
    border: none;
    background: #080808;
}

#topbar-select-model > SelectOverlay {
    background: #0d0d0d;
    border: none;
    color: #E0E0E0;
}

#topbar-select-model > SelectOverlay > OptionList > Option {
    color: #E0E0E0;
}

#topbar-select-model > SelectOverlay > OptionList > Option:hover {
    background: #444444;
    color: #FFFFFF;
}

#topbar-select-model > SelectOverlay > OptionList > Option.-highlighted {
    background: #444444;
    color: #FFFFFF;
}

/* ==================== CHAT LOG ==================== */

#chat-log {
    background: #000000;
    border: none;
    padding: 1 2;
    height: 1fr;
    min-width: 0;
    overflow-y: scroll;
    overflow-x: hidden;
    scrollbar-visibility: hidden;
}

.startup-logo {
    width: 100%;
    max-width: 100%;
    min-width: 0;
    height: 100%;
    text-align: center;
    content-align: center middle;
    color: #3498db;
    overflow: hidden;
}

.user-message {
    background: #111111;
    border-left: heavy #3498db;
    width: 1fr;
    padding: 1 2;
    color: #E0E0E0;
    margin-top: 1;
    margin-bottom: 1;
}

Collapsible {
    padding: 0 1;
    margin-bottom: 1;
}

Collapsible CollapsibleTitle {
    color: #eab308; /* yellow for Thought */
    background: transparent;
}

Collapsible CollapsibleTitle:focus, Collapsible CollapsibleTitle:hover {
    background: #222222;
}

/* ==================== COMPOSER ==================== */

#composer {
    dock: bottom;
    height: auto;
    background: transparent;
    padding: 0 0 1 0;
}

#file-suggestions {
    display: none;
    height: auto;
    max-height: 8;
    background: #111111;
    border: none;
    border-left: heavy #3498db;
    color: #E0E0E0;
    margin-bottom: 1;
}

#file-suggestions > ListItem {
    padding: 0 1;
    background: transparent;
    color: #E0E0E0;
}

#file-suggestions > ListItem.-highlight {
    background: #3498db;
    color: #ffffff;
    text-style: bold;
}

#file-suggestions > ListItem.-highlight Label {
    color: #ffffff;
    text-style: bold;
}

#composer-input {
    width: 1fr;
    background: #1e1e1e;
    border: none;
    border-left: heavy #555555;
    color: #E0E0E0;
    height: 5;
}

#composer-input > .text-area--cursor {
    background: #E0E0E0;
    color: #FFFFFF;
}

#composer-input:focus {
    border: none;
    border-left: heavy #3498db;
    background: #2a2a2a;
}

#composer-input:disabled {
    background: #1e1e1e;
    border: none;
    border-left: heavy #333333;
    color: #999999;
}

#composer-help {
    color: #888888;
    padding: 0 1;
    text-align: right;
}

#tui-footer-guide {
    display: none;
}

/* ==================== WORK PANEL ==================== */



/* ==================== UTILITY ==================== */

.file-tag {
    background: #111111;
    color: #E0E0E0;
    padding: 0 1;
    margin: 0 1;
}

.user-msg {
    color: #FFFFFF;
    text-style: bold;
}

.ai-msg {
    color: #E0E0E0;
}

.diff-add {
    color: #4ade80;
}

.diff-del {
    color: #FF6666;
}

.system-msg {
    color: #AAAAAA;
    text-style: italic;
}
"""