
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
python orca.py tui            # start the terminal UI
```

---

## What It Does

OrcaCode is an AI agent that lives in your terminal and works directly on your files. You describe what you want, it plans the work, asks for approval, then executes — writing code, running commands, fixing errors, and verifying results.

**Key differentiators:**

- **Doesn't forget.** After 200+ iterations, most agents lose context. OrcaCode saves structured snapshots of goals, decisions, and failures to disk, then rebuilds context losslessly (checkpoint.py).
- **Catches plan mistakes before writing code.** A spec review phase (spec_reviewer.py) checks for missing edge cases, error handling gaps, security risks, and dependency issues before a single line is changed.
- **Typed output contracts.** AI responses are parsed into structured data (not free text), so the planner, reviewer, and executor communicate with data instead of prose.

---

## Features

### Three Execution Modes

The agent has exactly three modes (core/models.py:ExecutionMode):

| Mode | Behavior | Use case |
|------|----------|----------|
| **PLAN** (default) | AI generates plan → you approve → executes step-by-step | Complex multi-file tasks |
| **AUTO** | Full autonomous, no per-step approval | Quick fixes, well-defined tasks |
| **CHAT** | Conversational only, no file modifications | Questions, code explanations |

### TUI Interface

Full terminal UI with Ocean Blue theme, four panels:

| Panel | Shows |
|-------|-------|
| Chat | Markdown-rendered AI responses with syntax highlighting |
| Architecture Graph | Live dependency tree, color-coded by file activity |
| System Logs | Timestamped event stream of tool executions |
| Top Bar | Provider/model selector, mode indicator |

Keyboard shortcuts: `@` triggers file autocomplete in the chat input. Full clipboard support (Ctrl+C/V/X/A). Security modal pops up for destructive command approval.

### Error Pipeline

When builds or tests fail, OrcaCode auto-fixes errors without wasting AI tokens:

```
Build → Parse Error → Rule Engine → Auto Fix → Rebuild → AI Fallback (only if needed)
```

20 built-in rules (rule_engine.py) handle: missing semicolons, missing npm/pip packages, unused variables/imports, missing module imports, type mismatch, syntax errors. Context filtering compresses a 100K-line project into ~17 lines of relevant error context before hitting the AI.

### Long-Term Memory

SQLite + FTS5 (long_memory.py) tracks across sessions:

- **Event Log:** Every file edit, command run, tool call
- **Task Memory:** Completed tasks with results and lessons
- **Knowledge Base:** Auto-extracted patterns from repeated work

Search across all three tiers simultaneously, sub-second even with millions of events.

### Architecture Graph

Static import scanner (arch_graph.py, dependency_graph.py) builds a live dependency map:

```
ARCH DEP GRAPH
  orca.py (7)
    core/agent.py (5)
      core/services/error_pipeline.py (2)
      core/services/rule_engine.py (1)
```

Files currently being edited glow blue. Entry points marked green. The graph is fed into AI context so the model understands project structure.

### Fuzzy File Patching

Three-tier matching (patch_service.py) preserves existing code:

1. **Exact match** — find and replace the precise block
2. **Fuzzy match** (>=85% similarity via rapidfuzz) — handles whitespace/formatting drift
3. **Line-by-line fallback** — keeps unchanged lines, only swaps what's different

Multi-file edits use atomic rollback: if any patch in a batch fails, all prior patches revert.

### Context Memory (Checkpoint Writer)

For tasks running 100-500+ iterations, the LLM context window fills up. Instead of lossy compaction, OrcaCode saves structured state to disk every N iterations (checkpoint.py):

- Original goal and approved plan
- Architecture decisions (e.g., "chose Redux", "used JWT auth")
- Recent failures and what was tried
- Modified files list + execution progress

When context pressure hits, rebuilds the message list from checkpoint data + last 8 exchanges.

### Plan Review Before Execution

Before writing code, 9 deterministic checks (spec_reviewer.py) run against the plan:

- Edge case coverage, error handling, consistency, completeness
- Risk detection (`rm -rf`, `DROP TABLE`, force push)
- Dependency analysis, testability, sensitive file protection, security

Blocking issues are shown **before** you approve — catching mistakes before code is written.

### Security

- Blocks destructive commands: `rm -rf`, `format`, `dd`, `shutdown`
- Auto-approves safe read-only: `ls`, `cat`, `git diff`, `pip list`
- Path traversal protection — can't access files outside workspace
- 21-pattern security scanner for code review (reviewer/security.py)

### Recovery & Rollback

Three layers:

1. **Recovery Checkpoint** (recovery.py) — snapshots files before edits; auto-rolls back if build quality worsens
2. **Context Checkpoint** (checkpoint.py) — saves agent mental state to disk for lossless rebuild
3. **Workspace Checkpoint** (checkpoint_service.py) — full zip snapshots for manual time-travel

### Review & Merge Pipeline (5-Step Reliability Stack)

OrcaCode has a systematic pipeline for accepting agent changes:

| Step | Module | What it does |
|------|--------|-------------|
| **1. Review & Merge** | merge_gate.py, merge_decision.py | Formal merge decision with deterministic hash, audit trail, and recoverability |
| **2. Observability** | trace_analytics.py, trend_detector.py | Per-iteration metrics, pattern detection (failure bursts, rollback clusters, stalls) |
| **3. Reliability** | reliability_engine.py, reliability_sla.py, reviewer_effectiveness.py | SLA enforcement (10 thresholds), reviewer quality (precision/recall/F1), checkpoint integrity |
| **4. Commitment Enforcer** | commitment_enforcer.py, commitment_chain.py | Immutable ADR compliance audit trail, tiered enforcement (INFO/WARN/CHALLENGE/BLOCK) |
| **5. Decision Quality** | decision_quality.py | 6-dimension quality scoring, archetype classification, architectural memory |

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
| Git | Any version | Required for `git diff`, rollback |
| Disk space | ~2 GB | Mostly from vendored libraries (torch, scipy) |
| RAM | 4 GB | 8 GB recommended |

### Setup

```bash
git clone https://github.com/nguyenhuukhanh-25-05-05/OrcaCode.git
cd OrcaCode
pip install -r requirements.txt
python orca.py setup
```

The setup wizard prompts for provider, API key, and model.

### Configuration

Config priority: env vars > `~/.orcacode/config.toml` > `.orcacode/config.toml` > `.env`

**`.env`** (project root):
```ini
ORCA_API_KEY=sk-your-key
ORCA_PROVIDER=deepseek
ORCA_MODEL=deepseek-chat
ORCA_BASE_URL=https://api.deepseek.com/v1
```

**`.orcacode/config.toml`** (TOML format):
```toml
api_key = "sk-your-key"
provider = "deepseek"
default_text_model = "deepseek-chat"
```

**`~/.orcacode/config.toml`** (global, canonical storage).

**Supported providers:** DeepSeek, OpenAI, Anthropic (Claude), Google Gemini, OpenRouter, and any OpenAI-compatible endpoint (use `ORCA_BASE_URL`).

---

## Usage

```bash
# Plan mode (default) — AI plans, you approve, executes
orca run "Add user authentication with JWT"

# Auto mode — select from TUI or set config
orca run "Fix all TypeScript errors in src/"

# Chat mode — selects automatically for simple questions
orca chat

# TUI with full interface
orca tui

# Override model per command
orca run -m gpt-4o "Refactor auth.py"

# View trace analytics & trends
orca stats

# Check SLA compliance, reviewer quality, checkpoint integrity
orca reliability

# View architectural commitment chain
orca commitments

# Assess historical decision quality
orca quality
```

---

## How It Works

### Agent Lifecycle

```
User Request
  → Intent Classification (intent_router.py)
  → Evidence Gathering (evidence_collector.py)
  → Confidence Scoring (confidence_scorer.py, 0-100%)
  → Plan Generation (AI step-by-step plan)
  → Spec Review (spec_reviewer.py, 9 checks)
  → User Approval
  → Execution Loop
       → AI tool calls (WRITE_FILE, PATCH_FILE, RUN_COMMAND)
       → Error auto-fix (error_pipeline.py)
       → Context checkpointing under memory pressure
       → DONE when complete
  → Code Review (reviewer/agent.py + security scanner)
  → Evidence Verification (build, lint, test)
  → Merge Gate (merge_gate.py — deterministic accept/reject)
  → DONE
```

### AI Providers

Single Python client adapts to any provider:

- DeepSeek / OpenAI / OpenRouter: OpenAI-compatible API
- Anthropic: Messages API
- Google Gemini: Generative AI SDK
- Custom: any OpenAI-compatible endpoint via `ORCA_BASE_URL`

---

## Architecture

```
orca.py                          CLI entry point (15 subcommands)
config/settings.py               Config loading (.env, TOML, env vars)
core/
  agent.py                       Main agent controller (+ ToolExecutorMixin)
  agent_tools.py                 Tool execution
  tui.py / tui/                  Textual TUI (Ocean Blue theme)
  models.py                      State machine, ExecutionMode, SessionState
  prompts/system.py              AI prompts (CHAT, PLAN, EXECUTE, DESIGN)
  services/                      65 service modules
    merge_gate.py                Step 1: Merge decision gate
    trace_analytics.py           Step 2: Aggregate analytics
    trend_detector.py            Step 2: Anomaly detection
    reliability_engine.py        Step 3: Unified reliability
    reliability_sla.py           Step 3: SLA definitions
    reviewer_effectiveness.py    Step 3: Reviewer quality metrics
    commitment_enforcer.py       Step 4: ADR enforcement
    commitment_chain.py          Step 4: Immutable audit trail
    decision_quality.py          Step 5: Historical quality scoring
    spec_reviewer.py             Pre-execution plan review (9 checks)
    trace_fingerprint.py         Per-iteration observability log
    error_pipeline.py            5-layer auto-fix pipeline
    rule_engine.py               20 deterministic fix rules
    long_memory.py               SQLite + FTS5 memory store
    arch_commitment.py           ADR (Architecture Decision Records)
    patch_service.py             Fuzzy file patching (3 tiers)
    security_service.py          Command blocking, path safety
    recovery.py                  Build-quality auto-rollback
    checkpoint.py                Lossless context memory
    checkpoint_service.py        Full workspace snapshots
    plan_drift.py                Architectural drift detection
    goal_drift.py                Goal drift detection
    loop_detector.py             Infinite loop prevention
    subagent_contract.py         Typed delegation contracts
    fidelity.py                  Context information retention
    structural_validator.py      Per-language file integrity
  reviewer/
    agent.py                     LLM-powered code reviewer
    security.py                  21-pattern security scanner
    patterns.py                  Bug pattern detection
  validator/
    schema_validator.py          JSON/format validation
    result_validator.py          Tool result consistency
  llm/
    client.py                    Multi-provider client
    providers.py                 Provider adapters
vendor/                          Bundled Python dependencies
tests/                           33 test suites (97+ tests)
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

OrcaCode's architecture was built by studying and integrating techniques from:

| Project | Contribution |
|---------|-------------|
| **Aider** | Map-reduce context assembly, repository map generation, edit formats |
| **OpenCode** | Terminal-native agent patterns, subagent architecture, plan-review-execute flow |
| **OpenHands** | Autonomous agent orchestration, sandboxed execution |
| **Cline** | Multi-mode execution, terminal integration, tool chaining |
| **CodeGraph** by Colby McHenry | Codebase indexing and symbol-level dependency graph (MIT, integrated via codegraph_service.py) |

UI design references: shadcn/ui, Radix UI, Headless UI, daisyUI, Chakra UI, Framer Motion, GSAP.

---

## License

MIT — see [LICENSE](LICENSE).
