# OrcaCode

Terminal AI agent that reads, patches, and generates code directly in your project. Built in Python with a Textual TUI, supporting five AI providers with autonomous multi-agent orchestration, automatic error correction, and long-term memory.
---

## Overview

OrcaCode is a terminal-native AI coding agent designed to operate directly on your project files. It combines a rich Textual TUI with a modular backend capable of autonomous execution across four modes: Plan, Build, Chat, and Loop Pro.

Every feature was built by studying and integrating techniques from leading open-source projects across the AI coding, animation, and design tooling ecosystems. The agent's design philosophy emphasizes local-first execution, minimal token waste, and maximum automation before escalating to AI reasoning.
<img width="1487" height="840" alt="image" src="https://github.com/user-attachments/assets/4b506620-1210-4a74-b537-263731cdf636" />
<img width="1483" height="841" alt="image" src="https://github.com/user-attachments/assets/ad3c4162-ff93-4e47-a442-b3747df2a67c" />
<img width="1483" height="836" alt="image" src="https://github.com/user-attachments/assets/ca8bd8e7-2257-48bc-b2bd-212d4061000b" />
---

## Capabilities

### Five-Layer Error Pipeline

The agent automatically detects, parses, and fixes compiler and linter errors without involving the AI model for routine corrections. Only complex semantic errors reach the AI layer.

```
Build -> Parse -> Rule Engine -> Auto Fix -> Rebuild -> AI Fallback
```

**Supported linters and compilers:** TypeScript (tsc), ESLint, Pylint, Pytest, Cargo (Rust), Go, MSVC, PHP.

**Rule Engine** provides 20 built-in rules:

| Error Pattern | Action | AI Needed |
|--------------|--------|-----------|
| Missing semicolons, formatting | Run `eslint --fix` or `prettier --write` | No |
| Missing npm/pip packages | Run `npm install` or `pip install` | No |
| Unused variables/imports | Auto-delete the line | No |
| Missing module (cannot find) | Search file and fix import path | No |
| Type mismatch, syntax errors | Send focused context to AI | Yes |

Context filtering reduces a 100,000-line project to approximately 17 lines of focused error context before sending to AI.

### Agent Swarm Teamwork

Three specialized agents operate in sequence, each independently configurable with a different AI provider and model for cost optimization:

```
Architect (planning and test design) -> Developer (code generation) -> QA (test execution)
                                       \                             /
                                        <------- retry loop -------->
```

**Architect:** Analyzes the request, reads the codebase, creates a step-by-step implementation plan with specific test cases. Default: deepseek-reasoner or claude-3-5-sonnet.

**Developer:** Implements the plan using WRITE_FILE and PATCH_FILE tools. Fixes bugs reported by QA. Default: deepseek-chat or gpt-4o.

**QA:** Writes and executes automated tests, parses results, and produces detailed bug reports with file, line number, and error message. Default: gpt-4o-mini or gemini-2.0-flash.

### Textual TUI

A full terminal interface with Ocean Blue dark theme, rounded corners, and four-panel layout:

- **Chat Panel:** Markdown rendering with syntax highlighting for AI responses
- **Architecture Graph Sidebar:** Live dependency tree with color-coded active files
- **System Logs Panel:** Timestamped event stream for all tool execution
- **Model Selector:** Provider and model switching in the top bar
- **File Autocomplete:** Type `@` to trigger project file suggestions
- **Security Modal:** Popup approval for destructive commands
- **Clipboard Support:** Full Ctrl+C/V/X/A integration

**Modes:**

| Mode | Behavior |
|------|----------|
| Plan | AI generates plan; user reviews and approves before execution |
| Build | Full autonomous execution without per-step approval |
| Chat | Conversational only; AI explains but does not modify files |
| Loop Pro | Infinite autonomous loop: plan approval upfront, AI writes tests and auto-fixes until all pass |

### Long-Term Memory

SQLite database with FTS5 full-text search across three tiers, designed for millions of events with sub-second retrieval:

| Tier | Table | Content |
|------|-------|---------|
| Event Log | `events` | Every file edit, command execution, and tool call |
| Task Memory | `tasks` | Lifecycle tracking with files, results, and lessons learned |
| Knowledge Base | `knowledge` | Auto-extracted patterns from repeated tasks with occurrence counting |

Search pipeline: `FTS5 query -> keyword fallback -> score ranking -> knowledge boost -> top 5 results`

### Live Architecture Graph

Static import scanner for Python, JavaScript, TypeScript, Vue, CSS, and SCSS files. Builds a directed graph of project dependencies and renders as an ASCII/Unicode tree:

```
ARCH DEP GRAPH
  orca.py (7)
    core/agent.py (5)
      core/services/error_pipeline.py (2)
      core/services/rule_engine.py (1)
```

Files currently being read or edited by the AI are highlighted with a blue circle marker. Entry points marked in green. The graph is fed into AI context so the model understands project structure without re-scanning files.

### Fuzzy File Patcher

Three-tier matching algorithm preserves existing code without full-file overwrites:

1. **Exact match:** Find the precise code block to replace
2. **Fuzzy match (rapidfuzz >= 85%):** Handle whitespace and formatting differences  
3. **Line-by-line fallback:** Compare individual lines; keep unchanged lines

Multi-file edits use atomic rollback: if any patch in a batch fails, all previous patches in that batch are reverted.

### OCR Service

Extracts text from images using EasyOCR (deep learning, supports Vietnamese and English) with PyTesseract fallback. Returns word-level bounding boxes with coordinates. Integrated into the TUI composer: paste an image and the extracted text appears inline.

### Project Blueprint

Indexes project symbols through AST parsing (Python) and regex patterns (JavaScript, TypeScript, PHP, Ruby). Provides function, class, and method listings with file locations for context building.

### Security Guard

- **Blocked commands:** `rm -rf`, `format`, `dd`, `shutdown`, `del /f /s`, and destructive patterns
- **Auto-approved read-only:** `ls`, `cat`, `git diff`, `pip list`
- **One-time approval:** Build commands (`npm run build`, `python setup.py`)
- **Path traversal protection:** Prevents file access outside workspace
- **Thread-safe:** `threading.Lock` for concurrent access

### Checkpoint System

Snapshot the entire workspace before major operations. Roll back to any checkpoint if the agent makes unwanted changes. Stored in `.orca/checkpoints/`.

### Plugin System

Register and unregister custom tools dynamically. Plugins can intercept any tool call type and provide custom execution logic.

### Debug Service

Parses Python and JavaScript stack traces. Extracts error type, file, line number, and function name. Reads surrounding source code context and suggests fix commands.

---

## Installation

**Prerequisites:** Python 3.8+, Git (optional)

```bash
git clone https://github.com/nguyenhuukhanh-25-05-05/OrcaCode.git
cd OrcaCode
pip install -r requirements.txt
```

**Setup wizard:**

```bash
python orca.py setup
```

**Environment configuration (.env):**

```ini
ORCA_API_KEY=sk-your-api-key-here
ORCA_PROVIDER=deepseek
ORCA_MODEL=deepseek-chat
```

**Swarm mode configuration (optional, for separate API keys per agent):**

```ini
ORCA_SWARM_ARCHITECT_API_KEY=sk-anthropic-...
ORCA_SWARM_ARCHITECT_MODEL=claude-3-5-sonnet
ORCA_SWARM_DEVELOPER_API_KEY=sk-deepseek-...
ORCA_SWARM_DEVELOPER_MODEL=deepseek-chat
ORCA_SWARM_QA_API_KEY=sk-openai-...
ORCA_SWARM_QA_MODEL=gpt-4o-mini
```

---

## Usage

```bash
orca tui                              # Launch the TUI
orca "Build a dark-mode login page"   # CLI mode
orca "Fix the auth bug in login.py"   # CLI mode
```

---

## Architecture

```
orca.py                         Entry point
config/                         Configuration system
core/
  agent.py                      Main agent controller
  tui.py                        Textual TUI (1970 lines)
  ui.py                         UI helpers and status bar
  commands.py                   CLI commands
  memory_manager.py             Session history and diff storage
  git_repo.py                   Git integration
  summarizer.py                 Chat conversation summarization
  services/
    error_parser.py             Parse compiler/linter output from 8 tools
    rule_engine.py              20 auto-fix rules with priority ordering
    error_pipeline.py           5-layer pipeline with context filtering
    long_memory.py              SQLite + FTS5 memory system
    arch_graph.py               Import dependency graph with ASCII rendering
    swarm_service.py            Multi-agent orchestration
    context_service.py          File discovery and keyword matching
    patch_service.py            Fuzzy patching with atomic rollback
    security_service.py         Command blocking and path traversal protection
    plugin_service.py           Extensible tool plugin system
    debug_service.py            Stack trace parsing and analysis
    ocr_service.py              Image text extraction
    blueprint_service.py        AST-based symbol indexing
    checkpoint_service.py       Workspace snapshots
  viewmodels/                   MVVM pattern for UI state management
utils/                          Diff generation, text normalization, token counting
tests/                          17 test suites
.orca/instructions.md           Agent instructions loaded into every system prompt
```

---

## Open Source Projects Studied

OrcaCode's architecture was informed by analyzing and learning from these projects:

- **Aider** — AI pair programming tool with map-reduce context assembly and repository map generation
- **Cline (VS Code)** — Autonomous coding agent with multi-mode execution and terminal integration
- **Claude Code** — Anthropic's agentic coding tool with workspace-level understanding
- **Roo Code** — VS Code extension with customizable agent behaviors and mode switching
- **CodeWhale** — Terminal-based AI coding assistant with streaming response support
- **OpenHands** — Platform for autonomous software development agents
- **Anime.js** — JavaScript animation engine used for UI motion design patterns
- **Three.js / React Three Fiber** — 3D rendering reference for spatial UI concepts

---

## Design Reference Ecosystem

OrcaCode's UI design rules draw from these tools and communities:

**Component libraries referenced:** shadcn/ui, Headless UI, Radix UI, daisyUI, Ant Design, Chakra UI, Mantine

**Design tool generators:** Uiverse.io, Glassmorphism.com, Neumorphism.io, cssgradient.io, Animista, cubic-bezier.com, Coolors.co, Adobe Color

**Animation libraries referenced:** Framer Motion, GSAP, AOS, Lottie Web, Motion One, Swiper, Particles.js, Vanta.js, Locomotive Scroll

**Design styles cataloged:** Brutalism, Glassmorphism, Swiss Minimal, Dark Premium, Organic/Biophilic, Retro Wave/Synthwave, Bauhaus, Editorial/Magazine, Holographic/Chrome, Claymorphism, Y2K, Industrial Tech, Motion-Driven, Spatial Depth

---

## Python Libraries Integrated

`openai` `rich` `textual` `rapidfuzz` `python-dotenv` `prompt-toolkit` `Pillow` `easyocr` `pytesseract` `pyinstaller` `setuptools` `pytest`

---

## Docker

```bash
docker build -t orcacode .
docker run -it --rm -v $(pwd):/workspace -e ORCA_API_KEY=$ORCA_API_KEY orcacode
```

---

## License

MIT
