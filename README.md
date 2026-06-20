
Terminal-native AI coding agent. Reads, edits, and generates code directly in your project — with a full TUI, multi-provider AI, automatic error correction, and long-running task memory.

<img width="968" height="710" alt="image" src="https://github.com/user-attachments/assets/a29cf6d6-ca16-40e2-8bca-4e430a774770" />

<img width="1365" height="899" alt="image" src="https://github.com/user-attachments/assets/111edbeb-5c52-4143-bb1e-973b90e2a825" />

<img width="1348" height="900" alt="image" src="https://github.com/user-attachments/assets/62e2d2bc-4378-4ffb-8171-dbb4a1b10009" />

---

## Quick Start

```bash
git clone https://github.com/nguyenhuukhanh-25-05-05/OrcaCode.git
cd OrcaCode
pip install -r requirements.txt
python orca.py setup          # enter your API key when prompted
orca tui                      # start coding
```

That's it. The setup wizard handles provider selection, API key, and model choice automatically.

---

## What It Does

OrcaCode is an AI agent that lives in your terminal and works directly on your files. You describe what you want, it plans the work, asks for approval, then executes — writing code, running commands, fixing errors, and verifying results.

**Key differentiators from other coding agents:**

- **Doesn't forget.** After 200+ iterations, most agents lose context. OrcaCode saves structured snapshots of goals, decisions, and failures to disk, then rebuilds context losslessly.
- **Catches plan mistakes before writing code.** A spec review phase checks for missing edge cases, error handling gaps, security risks, and dependency issues before a single line is changed.
- **Typed output contracts.** AI responses are parsed into structured data (not free text), so the planner, reviewer, and executor communicate with data instead of prose.

---

## Features

### TUI Interface

Full terminal UI with Ocean Blue theme, four panels:

| Panel | What it shows |
|-------|--------------|
| Chat | Markdown-rendered AI responses with syntax highlighting |
| Architecture Graph | Live dependency tree, color-coded by file activity |
| System Logs | Timestamped event stream of all tool executions |
| Top Bar | Provider/model selector, mode indicator |

**Keyboard shortcuts:** `@` triggers file autocomplete in the chat input. Full clipboard support (Ctrl+C/V/X/A). Security modal pops up for destructive command approval.

### Modes

| Mode | Behavior | Best for |
|------|----------|----------|
| **Plan** | AI generates plan → you approve → executes step-by-step | Complex multi-file tasks |
| **Build** | Full autonomous execution, no per-step approval | Quick fixes, well-defined tasks |
| **Chat** | Conversational only, no file modifications | Questions, code explanations |
| **Loop Pro** | Plan approved upfront, AI writes tests and auto-fixes until all pass | Test-driven development |

### Error Pipeline

When builds or tests fail, OrcaCode automatically fixes errors without wasting AI tokens:

```
Build → Parse Error → Rule Engine → Auto Fix → Rebuild → AI Fallback (only if needed)
```

20 built-in rules handle common fixes:

| Error | Auto-fix |
|-------|----------|
| Missing semicolons / formatting | `eslint --fix` or `prettier --write` |
| Missing npm/pip packages | `npm install` or `pip install` |
| Unused variables/imports | Auto-delete the offending line |
| Missing module imports | Search project and fix import path |
| Type mismatch, syntax errors | Escalate to AI with focused context |

Context filtering compresses a 100K-line project into ~17 lines of relevant error context before hitting the AI.

### Long-Term Memory

SQLite database with full-text search tracks everything across sessions:

- **Event Log:** Every file edit, command run, tool call
- **Task Memory:** Completed tasks with results and lessons
- **Knowledge Base:** Auto-extracted patterns from repeated work

Search across all three tiers simultaneously, sub-second even with millions of events.

### Architecture Graph

Static import scanner builds a live dependency map of your project:

```
ARCH DEP GRAPH
  orca.py (7)
    core/agent.py (5)
      core/services/error_pipeline.py (2)
      core/services/rule_engine.py (1)
```

Files currently being edited glow blue. Entry points marked green. The graph is fed into AI context so the model understands your project structure without re-reading files.

### Fuzzy File Patching

Three-tier matching preserves existing code without full-file overwrites:

1. **Exact match** — find and replace the precise block
2. **Fuzzy match** (≥85% similarity via rapidfuzz) — handles whitespace/formatting drift
3. **Line-by-line fallback** — keeps unchanged lines, only swaps what's different

Multi-file edits use atomic rollback: if any patch in a batch fails, all previous patches in that batch are reverted.

### Context Memory (Checkpoint Writer)

For tasks running 100-500+ iterations, the LLM context window inevitably fills up. Most agents solve this by compacting old messages — which loses information. OrcaCode instead saves structured state to disk:

**What's saved every checkpoint:**
- Original goal and approved plan
- Architecture decisions (e.g. "chose Redux", "used JWT auth")
- Recent failures and what was tried
- Modified files list
- Execution progress ("Step 3/7: fixing auth")

When context pressure hits, instead of lossy compression, OrcaCode rebuilds the message list from the checkpoint data plus the last 8 conversation exchanges. The AI remembers what matters.

### Plan Review Before Execution

Before writing any code, OrcaCode runs 9 deterministic checks on the plan:

| Check | What it catches |
|-------|----------------|
| Edge case coverage | Empty inputs, large files, timeouts |
| Error handling | Missing try/catch, no fallback for I/O |
| Consistency | Contradictory actions (create + delete same file) |
| Completeness | User asked for tests — plan has no test step |
| Risk | `rm -rf`, `DROP TABLE`, force push detected |
| Dependencies | Unnecessary new packages |
| Testability | Code changes without verification criteria |
| Sensitive files | Modifying `package.json`, `.env`, config files |
| Security | User input without validation, auth without review |

Blocking issues are shown before you approve the plan — catching mistakes before code is written.

### Security

- Blocks destructive commands: `rm -rf`, `format`, `dd`, `shutdown`
- Auto-approves safe read-only: `ls`, `cat`, `git diff`, `pip list`
- One-time approval for build commands
- Path traversal protection — can't access files outside your workspace

### Recovery & Rollback

Three layers of safety:
1. **Recovery Checkpoint** — snapshots file contents before edits; auto-rolls back if build quality worsens
2. **Context Checkpoint** — saves agent mental state to disk for lossless context rebuild
3. **Workspace Checkpoint** — full zip snapshots for manual time-travel

### Supported Languages & Tools

Linters/compilers: TypeScript (tsc), ESLint, Pylint, Pytest, Cargo (Rust), Go, MSVC, PHP

Project analysis: Python, JavaScript, TypeScript, Vue, CSS, SCSS, PHP, Ruby

---

## Installation

### Requirements

| Requirement | Minimum | Notes |
|------------|---------|-------|
| Python | 3.8+ | 3.11+ recommended |
| pip | Latest | Included with Python |
| Git | Any version | Optional — needed for `git diff`, rollback |
| Disk space | ~2 GB | Mostly from vendored ML libraries (torch, scipy, easyocr) |
| RAM | 4 GB | 8 GB recommended if using OCR features |
| OS | Windows, macOS, Linux | Tested on all three |
| Node.js | Not required | Only needed if working on JS/TS projects |

### Setup

```bash
git clone https://github.com/nguyenhuukhanh-25-05-05/OrcaCode.git
cd OrcaCode
pip install -r requirements.txt
```

**First-time setup wizard:**
```bash
python orca.py setup
```
Walks you through provider selection, API key entry, and model choice.

### Configuration

OrcaCode stores configuration in two places:

**`.env` file in the project root** — your API keys and provider settings:
```ini
ORCA_API_KEY=sk-your-api-key-here
ORCA_PROVIDER=deepseek
ORCA_MODEL=deepseek-chat
```

**`~/.orca/` directory** — global settings, history, and cached data:
```
~/.orca/
  config.json       # Provider, model, theme preferences
  memory/           # Long-term memory SQLite database
  checkpoints/      # Workspace snapshots
  traces/           # Execution trace logs
```

**API keys** — you need an API key from at least one provider:

| Provider | Get API key at | Env variable |
|----------|---------------|--------------|
| DeepSeek | platform.deepseek.com | `ORCA_API_KEY` |
| OpenAI | platform.openai.com/api-keys | `ORCA_API_KEY` or `OPENAI_API_KEY` |
| Anthropic | console.anthropic.com | `ORCA_API_KEY` or `ANTHROPIC_API_KEY` |
| Google Gemini | aistudio.google.com | `ORCA_API_KEY` or `GEMINI_API_KEY` |
| OpenRouter | openrouter.ai/keys | `ORCA_API_KEY` or `OPENROUTER_API_KEY` |

OrcaCode automatically detects which provider your key belongs to. You only need one key — the default `ORCA_API_KEY` works for all providers.

**Supported providers:** DeepSeek, OpenAI, Anthropic (Claude), Google Gemini, OpenRouter

**Swarm mode (separate keys per agent role, optional):**
```ini
ORCA_SWARM_ARCHITECT_API_KEY=sk-...
ORCA_SWARM_ARCHITECT_MODEL=claude-3-5-sonnet
ORCA_SWARM_DEVELOPER_API_KEY=sk-...
ORCA_SWARM_DEVELOPER_MODEL=deepseek-chat
ORCA_SWARM_QA_API_KEY=sk-...
ORCA_SWARM_QA_MODEL=gpt-4o-mini
```

---

## Usage

```bash
# Launch the TUI
orca tui

# CLI mode — AI plans, you approve, executes
orca "Add user authentication with JWT"

# CLI mode — full auto, no approval prompts
orca --auto "Fix all TypeScript errors in src/"

# Chat mode — no file modifications
orca --chat "Explain how the error pipeline works"

# Specify model per command
orca --model claude-sonnet-4-20250514 "Refactor auth.py"
```

### TUI Commands

Inside the TUI:
- Type your request and press Enter to send
- `@` triggers file path autocomplete
- `Ctrl+C` interrupts the current operation
- `Ctrl+V` paste (including images for OCR)
- Switch provider/model from the top bar dropdown

---

## How It Works

### Execution Flow

```
User Request
  → Intent Classification (what does the user want?)
  → Evidence Gathering (read relevant files)
  → Confidence Scoring (is this clear enough?)
  → Plan Generation (AI creates step-by-step plan)
  → Spec Review (9 checks before approval)
  → User Approval (review, revise, or cancel)
  → Execution Loop
       → AI generates tool calls (WRITE_FILE, PATCH_FILE, RUN_COMMAND)
       → Tools execute, results fed back
       → Error pipeline auto-fixes failures
       → Context checkpointing when memory pressure is high
       → Loop until DONE or max iterations
  → Code Review (static analysis + security scan)
  → Evidence Verification (build, lint, test)
  → DONE
```

### AI Providers

Single Python client adapts to any provider:
```python
# OpenAI / DeepSeek (OpenAI-compatible API)
# Anthropic (Messages API)
# Google Gemini (Generative AI SDK)
# OpenRouter (OpenAI-compatible proxy)
```

---

## Architecture

```
orca.py                         CLI entry point
config/                         Configuration (env, settings)
core/
  agent.py                      Main agent controller
  agent_tools.py                Tool execution (WRITE_FILE, PATCH_FILE, etc.)
  tui.py                        Textual terminal interface
  models.py                     State machine, plan structures
  prompts/system.py             AI system prompts (CHAT, PLAN, EXECUTE, DESIGN)
  services/
    checkpoint.py               Lossless context memory
    spec_reviewer.py            Pre-execution plan review (9 checks)
    subagent_contract.py        Typed delegation contracts
    trace_fingerprint.py        Per-iteration observability log
    error_pipeline.py           5-layer auto-fix pipeline
    rule_engine.py             20 deterministic fix rules
    long_memory.py              SQLite + FTS5 event/task/knowledge store
    arch_graph.py               Import dependency scanner + ASCII tree
    dependency_graph.py         File-level dependency resolution
    recovery.py                 Build-quality auto-rollback
    patch_service.py            Fuzzy file patching
    security_service.py         Command blocking, path safety
    risk_checker.py             Centralized risk assessment
    plan_validator.py           Plan quality scoring
    plan_drift.py               Detects execution drift from plan
    semantic_detector.py        Detects deleted/changed symbols
    fidelity.py                 Measures context information retention
    structural_validator.py     Per-language file integrity checks
  reviewer/
    agent.py                    LLM-powered code reviewer
    security.py                 21-pattern security scanner
    patterns.py                 Bug pattern detection
  validator/
    schema_validator.py         JSON/format validation
    result_validator.py         Tool result consistency
  llm/
    client.py                   Multi-provider client
    providers.py                Provider adapters
vendor/                         Bundled Python dependencies
tests/                          17+ test suites
```

---

## Docker

```bash
docker build -t orcacode .
docker run -it --rm \
  -v $(pwd):/workspace \
  -e ORCA_API_KEY=$ORCA_API_KEY \
  orcacode
```

---

## Credits

OrcaCode's architecture was built by studying and integrating techniques from these open-source projects:

| Project | What was learned |
|---------|-----------------|
| **Aider** | Map-reduce context assembly, repository map generation, edit formats |
| **OpenCode** | Terminal-native agent patterns, subagent architecture, plan-review-execute flow |
| **OpenHands** (formerly OpenDevin) | Autonomous agent orchestration, sandboxed execution |
| **Cline** (formerly Claude Dev) | Multi-mode execution, terminal integration, tool chaining |
| **CodeWhale** | Terminal-based coding agent with streaming responses |
| **CodeGraph** by Colby McHenry | Codebase indexing and symbol-level dependency graph. OrcaCode integrates CodeGraph CLI (MIT) via `core/services/codegraph_service.py` for code intelligence queries (symbol search, caller/callee analysis, semantic exploration). |

UI design references: shadcn/ui, Radix UI, Headless UI, daisyUI, Chakra UI, Framer Motion, GSAP.

---

## License

MIT — see [LICENSE](LICENSE).

### Third-Party Notices

- **CodeGraph** (`codegraph-main/`) is copyright (c) 2026 Colby McHenry, licensed under MIT. OrcaCode integrates it as an optional external CLI tool via `core/services/codegraph_service.py`. CodeGraph source is not redistributed in this repository.
- Vendored Python libraries under `vendor/` retain their original licenses. See each `*.dist-info/licenses/` directory for details.
