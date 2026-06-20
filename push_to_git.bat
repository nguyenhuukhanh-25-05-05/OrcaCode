@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
title OrcaCode - Git Push
color 07

echo ============================================================
echo    OrcaCode -- Git Push
echo ============================================================
echo.

echo [1/7] Initializing Git repository...
git init
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Git initialization failed.
    pause
    exit /b
)

echo.
echo [2/7] Removing excluded directories from staging...
git rm -r --cached aider-main 2>nul
git rm -r --cached MiMo-Code-main 2>nul
git rm -r --cached codegraph-main 2>nul
git rm -r --cached vendor/torch 2>nul
git rm -r --cached vendor/torchvision 2>nul
git rm -r --cached vendor/scipy 2>nul
git rm -r --cached vendor/cv2 2>nul
git rm -r --cached .orca/checkpoints 2>nul
git rm -r --cached .orca/traces 2>nul
git rm -r --cached .orca/memory 2>nul
git rm -r --cached .orcacode 2>nul
git rm -r --cached PLAN.md 2>nul
git rm -r --cached PROGRESS.md 2>nul

echo.
echo [3/7] Security check -- scanning for secrets...
set HAS_SECRET=0

:: Check .env files
git status --porcelain | findstr /R "\.env$" >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo [SECURITY ERROR] .env file detected in staging area.
    set HAS_SECRET=1
)

:: Check for real API keys (sk- with 30+ chars, not test keys)
for /f "delims=" %%f in ('git ls-files --cached --others --exclude-standard 2^>nul') do (
    findstr /R /C:"sk-[a-zA-Z0-9]\{30,\}" "%%f" >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        echo [SECURITY ERROR] Real API key detected in: %%f
        set HAS_SECRET=1
    )
)

if %HAS_SECRET% equ 1 (
    echo.
    echo Aborting push for security reasons.
    echo Remove real API keys or add files to .gitignore.
    pause
    exit /b
)
echo [OK] No sensitive files or secrets detected.

echo.
echo [4/7] Adding files to staging...
git add .
if %ERRORLEVEL% neq 0 (
    echo [WARNING] Some files could not be added.
)

echo.
echo [5/7] Creating commit...
git commit -m "feat: OrcaCode v2.1 - Checkpoint Writer, Subagent Contracts, Two-Phase Review, Trace Analytics" ^
    -m "=== Context & Memory ===" ^
    -m "- Checkpoint Writer: lossless externalized memory for 500+ iteration tasks" ^
    -m "- Structured agent state (goal, plan, decisions, failures, files) saved to JSON" ^
    -m "- Context rebuild from checkpoint + recent working memory tail (replaces lossy compact)" ^
    -m "- Integrated at pressure level >=2 and at 40+ message condensation points" ^
    -m "" ^
    -m "=== Subagent Contracts ===" ^
    -m "- Typed SubagentTask / SubagentResult dataclasses for structured delegation" ^
    -m "- ContractValidator with blocking/warning/info severity levels" ^
    -m "- ContractRegistry for pluggable per-type validators" ^
    -m "- Specialized contracts: CodeReview, TestGen, Refactor, SecurityAudit" ^
    -m "- JSON + XML parser for extracting structured results from AI text" ^
    -m "" ^
    -m "=== Two-Phase Review ===" ^
    -m "- SPEC_REVIEW state between PLAN and APPROVE in execution flow" ^
    -m "- SpecReviewer: 9 deterministic checks (edge case, error handling, consistency," ^
    -m "  completeness, risk, dependency, testability, sensitive files, security)" ^
    -m "- Delegates risk checking to centralized RiskChecker (deduplication)" ^
    -m "" ^
    -m "=== Trace Fingerprint ===" ^
    -m "- Per-iteration JSONL observability (.orca/traces/fingerprint.jsonl)" ^
    -m "- Metrics: decision hash, messages hash, fidelity, pressure, contract violations" ^
    -m "- Auto-rotation at 5000 lines" ^
    -m "" ^
    -m "=== Bug Fixes ===" ^
    -m "- Fix: messages rebuild uses in-place mutation to prevent self._exec_messages stale" ^
    -m "- Fix: CheckpointWriter.clear() scoped to cp_*.json only (was destructive rmtree)" ^
    -m "- Remove: _progressive_context_condense dead code (replaced by checkpoint rebuild)" ^
    -m "" ^
    -m "=== Architecture ===" ^
    -m "- 5-layer Error Pipeline: build -^> parse -^> rule engine -^> auto-fix -^> AI fallback" ^
    -m "- Agent Swarm Teamwork: Architect/Developer/QA agents with separate API keys" ^
    -m "- Long-term Memory: SQLite + FTS5 full-text search for events, tasks, knowledge" ^
    -m "- Live Architecture Graph: import scanner + ASCII dependency tree" ^
    -m "- Textual TUI: Ocean Blue theme with chat panel, work panel, model selector" ^
    -m "- Multi-provider: DeepSeek, OpenAI, Anthropic, Gemini, OpenRouter" ^
    -m "- Fuzzy file patcher with atomic rollback and git integration" ^
    -m "- Security guard: command blocking, path traversal protection, workspace trust" ^
    -m "- 17 test suites with 100+ unit and integration tests"

if %ERRORLEVEL% neq 0 (
    echo.
    echo [INFO] Nothing to commit.
    goto PUSH
)

echo.
echo [6/7] Pushing to GitHub...
git branch -M main

:PUSH
git remote remove origin 2>nul
git remote add origin https://github.com/nguyenhuukhanh-25-05-05/OrcaCode.git
echo.
echo [7/7] Pushing to GitHub...
git push -u origin main --force
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Push failed.
    echo.
    echo Troubleshooting:
    echo   1. Remove large directories (MiMo-Code-main, codegraph-main)
    echo   2. Check internet connection
    echo   3. Verify GitHub token validity
    echo   4. Confirm repository exists on GitHub
    pause
    exit /b
)

echo.
echo ============================================================
echo    Complete -- Code pushed to GitHub
echo    https://github.com/nguyenhuukhanh-25-05-05/OrcaCode
echo.
echo    Latest commit:
echo ============================================================
echo.
git log --oneline -1
echo.
pause
