# OrcaCode

> Terminal AI coding agent — created by **Nguyễn Hữu Khánh** (25/05/2005)

OrcaCode operates directly on your project files with a Textual TUI, five AI providers, autonomous multi-agent orchestration, automatic error correction, lossless context memory, and long-term project awareness across 500+ iteration tasks.

---

## What's New in v2.1

### Checkpoint Writer — Lossless Externalized Memory
The biggest architectural leap. Instead of lossy context compaction that destroys information, OrcaCode periodically saves structured agent state (goal, plan, decisions, failures, modified files) to disk and rebuilds context from checkpoint + working memory tail when the LLM context window fills up.

```
Before (lossy):          Messages → Compact → Information Loss
After  (lossless):       Messages → Checkpoint → Rebuild Context
```

This enables stable execution across 300-500+ iterations without forgetting architectural decisions, known failures, or open issues.

### Structured Subagent Contracts
Typed delegation protocol between Planner, Reviewer, Executor, and future subagents. Every subagent output conforms to a named contract with field-level validation:

- `SubagentTask` / `SubagentResult` – base typed contracts
- `ContractValidator` – blocking/warning/info severity levels
- `ContractRegistry` – pluggable per-type validators
- Specialized contracts: `CodeReviewContract`, `TestGenContract`, `RefactorContract`, `SecurityAuditContract`
- JSON + XML parser for extracting structured results from AI text

### Two-Phase Review
New `SPEC_REVIEW` state between PLAN and APPROVE catches architectural issues before code is written:

- **Phase 1 (Spec Review):** 9 deterministic checks — edge case coverage, error handling, consistency, completeness, risk, dependencies, testability, sensitive files, security. Delegates risk checking to centralized `RiskChecker`.
- **Phase 2 (Code Review):** Existing `ReviewerAgent` + security scanner + semantic detector + evidence verification.

### Trace Fingerprint
Per-iteration JSONL observability for long-run diagnostics. Each iteration logs: decision hash, messages hash, pressure level, LLM/tool counts, contract violations, consecutive failures, build failures. Auto-rotates at 5000 lines. Stored in `.orca/traces/fingerprint.jsonl`.

---

## Capabilities

### Five-Layer Error Pipeline

```
Build -> Parse -> Rule Engine -> Auto Fix -> Rebuild -> AI Fallback
```

20 built-in rules for automatic fix without AI. Context filtering reduces 100K-line projects to ~17 lines of focused error context.

### Agent Swarm Teamwork

```
Architect (planning) -> Developer (code) -> QA (testing)
                          \                  /
                           <-- retry loop -->
```

Each agent independently configurable with different AI providers and models.

### Textual TUI

Ocean Blue dark theme, four-panel layout: Chat Panel, Architecture Graph Sidebar, System Logs, Model Selector. Full security modal, clipboard support, file autocomplete with `@`.

### Long-Term Memory

SQLite + FTS5 across three tiers (events, tasks, knowledge). Sub-second full-text search across millions of events.

### Live Architecture Graph

Static import scanner for Python/JS/TS/Vue/CSS/SCSS. ASCII dependency tree with color-coded active files, fed into AI context.

### Fuzzy File Patcher

Three-tier matching: exact → fuzzy (rapidfuzz ≥85%) → line-by-line. Atomic multi-file rollback.

### Security Guard

Command blocking, path traversal protection, workspace trust zones, thread-safe access.

### Recovery & Checkpoint System

- **Recovery Checkpoint:** In-memory file snapshots with automatic rollback when build quality worsens.
- **Checkpoint Writer:** Disk-based structured agent state for lossless context rebuild at high pressure.
- **Workspace Checkpoint:** Full zip snapshots for user-facing time-travel.

---

## Installation

```bash
git clone https://github.com/nguyenhuukhanh-25-05-05/OrcaCode.git
cd OrcaCode
pip install -r requirements.txt
python orca.py setup
```

**Environment (.env):**
```ini
ORCA_API_KEY=sk-your-api-key-here
ORCA_PROVIDER=deepseek
ORCA_MODEL=deepseek-chat
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
  agent.py                      Main agent controller (4,000+ lines)
  agent_tools.py                Tool executor mixin (WRITE_FILE, PATCH_FILE, etc.)
  tui.py                        Textual TUI
  commands.py                   CLI commands
  models.py                     AgentState, Plan, ExecutionMode enums
  prompts/
    system.py                   CHAT, PLAN, EXECUTE, DESIGN system prompts
  services/
    checkpoint.py               CheckpointWriter — lossless context memory
    spec_reviewer.py            Two-Phase Review Phase 1 (9 deterministic checks)
    subagent_contract.py        Typed SubagentTask/SubagentResult contracts
    trace_fingerprint.py        Per-iteration JSONL observability
    error_pipeline.py           5-layer error detection and auto-fix
    rule_engine.py              20 auto-fix rules
    error_parser.py             Compiler/linter output parser (8 tools)
    long_memory.py              SQLite + FTS5 memory system
    arch_graph.py               Import dependency graph
    dependency_graph.py         File-level dependency resolution
    recovery.py                 Build-quality rollback (CheckpointManager)
    patch_service.py            Fuzzy patching with atomic rollback
    security_service.py         Command blocking and path safety
    risk_checker.py             Centralized risk assessment
    plan_validator.py           Plan quality scoring
    plan_drift.py               Plan vs. reality drift detection
    semantic_detector.py        Deleted/changed symbol detection
    confidence_scorer.py        Request confidence scoring
    intent_router.py            User intent classification
    retry_contract.py           Failure analysis and retry logic
    loop_detector.py            Repetitive pattern detection
    fidelity.py                 Context fidelity measurement
    context_assembler.py        Relevance-based context filtering
    context_pruner.py           Pressure-graduated message pruning
    overflow.py                 Token estimation and context pressure
    signal.py                   Signal observation and ranking
    code_quality.py             Architecture rules and debt tracking
    done_engine.py              LLM-generated verification conditions
    done_condition.py           Done condition extraction and verification
    knowledge_freshness.py      Stale dependency tracking
    checkpoint_service.py       Workspace zip snapshots
    blueprint_service.py        AST-based symbol indexing
    structural_validator.py     Per-language structural integrity checks
    anti_pattern.py             Anti-pattern detection
  reviewer/
    agent.py                    LLM-based code reviewer
    models.py                   ReviewResult, ReviewIssue, ReviewCategory
    patterns.py                 Bug pattern detection
    security.py                 Security scanning (21 patterns)
  validator/
    schema_validator.py         JSON/format/section validation
    result_validator.py         Tool result consistency
    evidence_validator.py       Evidence validation
  llm/
    client.py                   Multi-provider LLM client
    providers.py                OpenAI, Anthropic, Gemini adapters
    context_assembler.py        Token budget management
utils/                          Diff, text normalization, token counting
tests/                          17+ test suites
```

---

## Open Source Projects Studied

Aider, Cline, Claude Code, Roo Code, CodeWhale, OpenHands, Anime.js, Three.js, React Three Fiber.

---

## Design Reference Ecosystem

**Component libraries:** shadcn/ui, Headless UI, Radix UI, daisyUI, Ant Design, Chakra UI, Mantine

**14 design styles cataloged:** Brutalism, Glassmorphism, Swiss Minimal, Dark Premium, Organic/Biophilic, Retro Wave/Synthwave, Bauhaus, Editorial/Magazine, Holographic/Chrome, Claymorphism, Y2K, Industrial Tech, Motion-Driven, Spatial Depth

---

## Docker

```bash
docker build -t orcacode .
docker run -it --rm -v $(pwd):/workspace -e ORCA_API_KEY=$ORCA_API_KEY orcacode
```

---

## License

MIT
