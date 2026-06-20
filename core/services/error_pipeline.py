"""Error Pipeline - Orchestrates the full 5-layer error handling pipeline.

Pipeline flow:
    Build (run build command)
        ↓
    Parse errors (ErrorParser → structured JSON)
        ↓
    Rule Engine (match patterns → auto-fix actions)
        ↓
    Auto Fix (run eslint --fix, delete unused imports, etc.)
        ↓
    Rebuild (run build command again)
        ↓
    If still errors → collect remaining for AI
        ↓
    Return { auto_fixed, remaining_errors, context_for_ai }

This allows the agent to handle 80% of errors automatically and only
spend AI tokens on the 20% that truly need reasoning.
"""
import re
import subprocess
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Callable

from core.services.error_parser import ErrorParser, ParsedError
from core.services.rule_engine import RuleEngine, RuleMatch, ActionType, Rule
from core.services.patch_service import _write_with_retry


@dataclass
class PipelineResult:
    """Result of running the error pipeline."""
    build_success: bool
    total_errors_found: int = 0
    auto_fixed_count: int = 0
    remaining_count: int = 0
    build_output: str = ""
    fixed_details: list[dict] = field(default_factory=list)
    remaining_errors: list[dict] = field(default_factory=list)
    context_for_ai: str = ""
    rounds: int = 0  # How many build-fix-rebuild cycles

    def to_summary(self) -> str:
        lines = [f"Error Pipeline Results ({self.rounds} round(s)):"]
        lines.append(f"  Total errors found: {self.total_errors_found}")
        lines.append(f"  Auto-fixed: {self.auto_fixed_count}")
        lines.append(f"  Remaining (needs AI): {self.remaining_count}")
        lines.append(f"  Build success: {self.build_success}")
        if self.fixed_details:
            lines.append("  Fixed:")
            for d in self.fixed_details:
                lines.append(f"    - [{d.get('rule', '?')}] {d.get('file', '?')}:{d.get('line', '?')} — {d.get('action', '?')}")
        return "\n".join(lines)


@dataclass
class BuildConfig:
    """Configuration for a build/lint step."""
    command: str
    tool: str  # Hint for the error parser (e.g. "tsc", "eslint")
    cwd: str = ""
    timeout: int = 120


class ErrorPipeline:
    """5-layer error handling pipeline.

    Usage:
        pipeline = ErrorPipeline(project_root="/path/to/project")
        pipeline.add_build_step(BuildConfig(command="npx tsc --noEmit", tool="tsc"))
        pipeline.add_build_step(BuildConfig(command="npx eslint .", tool="eslint"))
        result = pipeline.run()
    """

    def __init__(
        self,
        project_root: str = ".",
        max_fix_rounds: int = 3,
        on_status: Callable[[str], None] | None = None,
        on_log: Callable[[str], None] | None = None,
    ):
        self.project_root = Path(project_root)
        self.max_fix_rounds = max_fix_rounds
        self.parser = ErrorParser()
        self.engine = RuleEngine()
        self.on_status = on_status or (lambda s: None)
        self.on_log = on_log or (lambda s: None)
        self._build_steps: list[BuildConfig] = []

    def add_build_step(self, config: BuildConfig):
        """Add a build/lint command to run at the start of each round."""
        self._build_steps.append(config)

    def add_rule(self, rule: Rule):
        """Add a custom rule to the rule engine."""
        self.engine.add_rule(rule)

    def run(self, extra_context_files: list[str] | None = None) -> PipelineResult:
        """Run the full pipeline: Build → Parse → Fix → Rebuild → ... → AI."""
        result = PipelineResult(build_success=False)
        accumulated_errors: list[dict] = []

        for round_num in range(1, self.max_fix_rounds + 1):
            result.rounds = round_num
            self.on_status(f"Pipeline round {round_num}: building...")

            # ── Step 1: Run build commands ──
            all_errors = self._run_build_steps()
            result.total_errors_found = max(result.total_errors_found, len(all_errors))

            if not all_errors:
                result.build_success = True
                self.on_log("Build passed with no errors!")
                break

            self.on_log(f"Found {len(all_errors)} errors")

            # ── Step 2: Match errors against rules ──
            matches = self.engine.match_errors(all_errors)

            auto_fixable = [m for m in matches if m.rule.action != ActionType.NEEDS_AI]
            needs_ai = [m for m in matches if m.rule.action == ActionType.NEEDS_AI]

            # Also include errors that didn't match any rule
            matched_files_lines = {(m.error_file, m.error_line) for m in matches}
            unmatched = [
                e for e in all_errors
                if (e.get("file", ""), e.get("line", "")) not in matched_files_lines
            ]

            self.on_log(
                f"Auto-fixable: {len(auto_fixable)}, "
                f"Needs AI: {len(needs_ai)}, "
                f"Unmatched (defaulting to AI): {len(unmatched)}"
            )

            # ── Step 3: Execute auto-fixes ──
            fixed_any = False
            for match in auto_fixable:
                success = self._execute_fix(match, result)
                if success:
                    fixed_any = True

            # ── Step 4: If nothing was fixed, stop looping ──
            if not fixed_any:
                self.on_log("No auto-fixes applied in this round, stopping pipeline")
                accumulated_errors = all_errors
                break

            # If we fixed something, loop back to rebuild
            if fixed_any:
                self.on_log(f"Fixed {len(result.fixed_details)} errors, rebuilding...")

        # ── Step 5: Collect remaining errors for AI ──
        if accumulated_errors:
            # Deduplicate
            seen = set()
            unique = []
            for e in accumulated_errors:
                key = (e.get("file", ""), e.get("line", ""), e.get("error", ""))
                if key not in seen:
                    seen.add(key)
                    unique.append(e)

            result.remaining_errors = unique
            result.remaining_count = len(unique)
            result.context_for_ai = self._build_ai_context(unique, extra_context_files)

        return result

    def _run_build_steps(self) -> list[dict]:
        """Run all build commands and collect parsed errors."""
        all_errors: list[dict] = []

        for step in self._build_steps:
            self.on_log(f"Running: {step.command}")
            cwd = str(self.project_root / step.cwd) if step.cwd else str(self.project_root)

            try:
                import shlex
                cmd_list = shlex.split(step.command)
                proc = subprocess.run(
                    cmd_list, capture_output=True,
                    encoding="utf-8", errors="replace",
                    cwd=cwd, timeout=step.timeout,
                )
                stdout = proc.stdout
                stderr = proc.stderr
            except subprocess.TimeoutExpired:
                self.on_log(f"Command timed out: {step.command}")
                continue
            except Exception as e:
                self.on_log(f"Command failed: {e}")
                continue

            # Parse errors from this tool
            parser = ErrorParser(tool_hint=step.tool)
            parsed = parser.parse(stdout, stderr, tool=step.tool)

            for p in parsed:
                err_dict = p.to_dict()
                err_dict["_build_command"] = step.command
                all_errors.append(err_dict)

            # If process exited with non-zero but no parseable errors were found,
            # create a generic error so the pipeline doesn't falsely report success.
            if proc.returncode != 0 and not parsed:
                fallback_stderr = stderr.strip() or stdout.strip()
                if fallback_stderr:
                    all_errors.append({
                        "file": "",
                        "line": 0,
                        "col": 0,
                        "error": fallback_stderr[:500],
                        "severity": "error",
                        "code": f"EXIT_{proc.returncode}",
                        "source": step.tool or "generic",
                        "_build_command": step.command,
                    })

        return all_errors

    def _execute_fix(self, match: RuleMatch, result: PipelineResult) -> bool:
        """Execute a single auto-fix. Returns True if something was changed."""
        rule = match.rule
        file_path = match.error_file

        detail = {
            "rule": rule.name,
            "file": file_path,
            "line": match.error_line,
            "action": rule.action.value,
            "description": rule.description,
        }

        try:
            if rule.action == ActionType.RUN_COMMAND:
                return self._fix_run_command(rule, file_path, match.error_text, detail, result)
            elif rule.action == ActionType.DELETE_LINE:
                return self._fix_delete_line(rule, file_path, match.error_line, match.error_text, detail, result)
            elif rule.action == ActionType.SEARCH_FILE:
                return self._fix_search_file(rule, file_path, match.error_text, detail, result)
            elif rule.action == ActionType.ADD_IMPORT:
                return self._fix_add_import(rule, file_path, match.error_line, detail, result)
            elif rule.action == ActionType.FIX_IMPORT:
                return self._fix_import(rule, file_path, match.error_line, match.error_text, detail, result)
            elif rule.action == ActionType.SKIP:
                self.on_log(f"Skipping error: {match.error_text}")
                result.fixed_details.append(detail)
                return True
        except Exception as e:
            self.on_log(f"Fix failed for {rule.name}: {e}")
            detail["error"] = str(e)

        return False

    def _fix_run_command(self, rule, file_path, error_text, detail, result) -> bool:
        """Run a shell command to fix an error."""
        cmd = self.engine.format_command(rule.command, file_path, {"error": error_text, "line": 0, "col": 0})

        if not cmd or "{module_name}" in cmd and not re.search(r"['\"]([^'\"]+)['\"]", error_text):
            self.on_log(f"Cannot determine module name for command: {cmd}")
            return False

        self.on_log(f"Running fix command: {cmd}")
        try:
            import shlex
            cmd_list = shlex.split(cmd)
            proc = subprocess.run(
                cmd_list, capture_output=True,
                encoding="utf-8", errors="replace",
                cwd=str(self.project_root), timeout=60,
            )
            if proc.returncode == 0:
                result.fixed_details.append(detail)
                self.on_log(f"Fix command succeeded: {cmd}")
                return True
            else:
                self.on_log(f"Fix command failed (exit {proc.returncode}): {proc.stderr[:200]}")
                return False
        except Exception as e:
            self.on_log(f"Fix command error: {e}")
            return False

    def _fix_delete_line(self, rule, file_path, line_no, error_text, detail, result) -> bool:
        """Delete an unused line (unused import/variable)."""
        full_path = self.project_root / file_path
        if not full_path.exists():
            return False

        try:
            lines = full_path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
            if line_no < 1 or line_no > len(lines):
                return False

            # Extract the name that's unused
            name_match = re.search(r"['\"]?(\w+)['\"]?\s+(is|are)\s+unused", error_text)
            if not name_match:
                name_match = re.search(r"unused\s+(?:import|variable)\s+['\"]?(\w+)", error_text, re.IGNORECASE)
            if not name_match:
                name_match = re.search(r"F401\s+.*'(\w+)'", error_text)

            if name_match:
                unused_name = name_match.group(1)
                target_line = lines[line_no - 1]

                # For Python imports, try to remove just the name from a multi-import
                if file_path.endswith(".py") and "import" in target_line:
                    new_line = self._remove_name_from_import(target_line, unused_name)
                    if new_line is not None:
                        lines[line_no - 1] = new_line
                        _write_with_retry(full_path, "".join(lines))
                        detail["action"] = "remove_name_from_import"
                        result.fixed_details.append(detail)
                        return True

                # Otherwise, remove the entire line
                del lines[line_no - 1]
                _write_with_retry(full_path, "".join(lines))
                detail["action"] = "delete_line"
                result.fixed_details.append(detail)
                self.on_log(f"Deleted line {line_no} in {file_path}")
                return True
            else:
                # Just remove the whole line if we can't identify the name
                del lines[line_no - 1]
                _write_with_retry(full_path, "".join(lines))
                detail["action"] = "delete_line"
                result.fixed_details.append(detail)
                return True

        except Exception as e:
            self.on_log(f"Delete line failed: {e}")
            return False

    def _remove_name_from_import(self, line: str, name: str) -> str | None:
        """Remove a specific name from a Python import line.

        'from os import path, getcwd' + remove 'path' → 'from os import getcwd'
        'import os, sys' + remove 'os' → 'import sys'
        'from os import path' + remove 'path' → '' (remove entire line)
        """
        stripped = line.strip()

        # from X import a, b, c
        m = re.match(r'^(from\s+\S+\s+import\s+)(.+)$', stripped)
        if m:
            prefix = m.group(1)
            imports = [i.strip() for i in m.group(2).split(",")]
            imports = [i for i in imports if i != name and i != name + " as " + name.split(".")[-1]]
            if not imports:
                return ""  # Remove entire line — nothing left to import
            return prefix + ", ".join(imports) + "\n"

        # import a, b, c
        m = re.match(r'^(import\s+)(.+)$', stripped)
        if m:
            prefix = m.group(1)
            imports = [i.strip() for i in m.group(2).split(",")]
            imports = [i for i in imports if i != name]
            if not imports:
                return ""
            return prefix + ", ".join(imports) + "\n"

        return None

    def _fix_search_file(self, rule, file_path, error_text, detail, result) -> bool:
        """Search for a missing file/module. This is informational for the AI,
        but we can try to find the correct path."""
        # Extract the missing name
        name_match = re.search(r"['\"]([^'\"]+)['\"]", error_text)
        if not name_match:
            return False

        missing = name_match.group(1)

        # Search for the file in the project
        found = self._find_file_in_project(missing)
        if found:
            detail["found_file"] = str(found)
            detail["action"] = "found_missing_file"
            result.fixed_details.append(detail)
            self.on_log(f"Found missing file: {missing} → {found}")
            return True  # Found it, AI can use this info

        return False  # Can't find it, needs AI

    def _find_file_in_project(self, name: str) -> Path | None:
        """Search for a file by name in the project."""
        # Try exact name
        for ext in ["", ".ts", ".tsx", ".js", ".jsx", ".py", ".go", ".rs", ".json"]:
            path = self.project_root / f"{name}{ext}"
            if path.exists():
                return path

        # Try basename search
        basename = Path(name).name
        for ext in ["", ".ts", ".tsx", ".js", ".jsx", ".py"]:
            for found in self.project_root.rglob(f"{basename}{ext}"):
                if ".git" not in str(found) and "node_modules" not in str(found):
                    return found

        return None

    def _fix_add_import(self, rule, file_path, line_no, detail, result) -> bool:
        """Add a missing import line. Extracts module name from error, finds file, adds import."""
        error_text = detail.get("description", "") or rule.description
        name_match = re.search(r"['\"]([^'\"]+)['\"]", error_text)
        if not name_match:
            return False

        missing = name_match.group(1)
        if missing.endswith(".ts") or missing.endswith(".js") or missing.endswith(".py"):
            missing = missing.rsplit(".", 1)[0].replace("/", ".")

        # Read the target file
        full_path = self.project_root / file_path
        if not full_path.exists():
            return False

        try:
            content = full_path.read_text(encoding="utf-8")
        except OSError:
            return False

        # Skip if import already exists
        if missing in content:
            self.on_log(f"Import '{missing}' already exists in {file_path}")
            detail["action"] = "import_already_exists"
            result.fixed_details.append(detail)
            return True

        # Search for the module file in project
        found = self._find_file_in_project(missing)
        if found:
            rel = found.relative_to(self.project_root)
            # Determine import syntax based on file extension
            if file_path.endswith(".py"):
                import_line = f"from {str(rel.parent).replace(chr(92), '.')} import {rel.stem}\n" if str(rel.parent) != "." else f"import {rel.stem}\n"
            elif file_path.endswith((".ts", ".tsx")):
                import_line = f"import {{ {rel.stem} }} from '{str(rel.parent).replace(chr(92), '/')}/{rel.stem}';\n" if str(rel.parent) != "." else f"import {{ {rel.stem} }} from './{rel.stem}';\n"
            else:
                import_line = f"import {{ {rel.stem} }} from '{str(rel.parent).replace(chr(92), '/')}/{rel.stem}';\n" if str(rel.parent) != "." else f"import {{ {rel.stem} }} from './{rel.stem}';\n"

            # Find insertion point: after existing imports / shebang / docstring
            lines = content.splitlines(keepends=True)
            insert_idx = 0
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith("#!") or stripped.startswith('"""') or stripped.startswith("'''") or stripped.startswith("// ") or stripped.startswith("/*"):
                    continue
                if stripped.startswith(("import ", "from ", "require(", "const ", "let ", "var ")):
                    insert_idx = i + 1
                else:
                    break

            lines.insert(insert_idx, import_line)
            _write_with_retry(full_path, "".join(lines))
            detail["action"] = f"added_import_{missing}"
            result.fixed_details.append(detail)
            self.on_log(f"Added import '{missing}' to {file_path}")
            return True

        return False  # Can't find module, needs AI

    def _fix_import(self, rule, file_path, line_no, error_text, detail, result) -> bool:
        """Fix a broken import path. Finds the correct path and replaces."""
        name_match = re.search(r"['\"]([^'\"]+)['\"]", error_text)
        if not name_match:
            return False

        wrong_path = name_match.group(1)
        basename = Path(wrong_path).name

        # Search for the correct file
        found = self._find_file_in_project(basename)
        if not found:
            return False

        correct_path = str(found.relative_to(self.project_root)).replace("\\", "/")
        if correct_path.endswith((".ts", ".tsx", ".js", ".jsx", ".py")):
            correct_path = correct_path.rsplit(".", 1)[0]

        # Read and fix
        full_path = self.project_root / file_path
        if not full_path.exists():
            return False

        try:
            content = full_path.read_text(encoding="utf-8")
        except OSError:
            return False

        new_content = content.replace(wrong_path, correct_path)
        if new_content == content:
            return False

        _write_with_retry(full_path, new_content)
        detail["action"] = f"fixed_import_{wrong_path}_to_{correct_path}"
        result.fixed_details.append(detail)
        self.on_log(f"Fixed import '{wrong_path}' → '{correct_path}' in {file_path}")
        return True

    def _build_ai_context(self, errors: list[dict], extra_files: list[str] | None = None) -> str:
        """Build a focused context string for AI to process remaining errors.

        This is the key filtering step:
        100,000 lines of code → ~100 lines of actual relevant code
        """
        lines = ["## Auto-fix pipeline results", ""]
        lines.append(f"Pipeline auto-fixed {len(errors)} remaining error(s) that need AI reasoning.")
        lines.append("")

        # Group errors by file
        by_file: dict[str, list[dict]] = {}
        for err in errors:
            f = err.get("file", "unknown")
            by_file.setdefault(f, []).append(err)

        lines.append("## Remaining errors by file:")
        for f, errs in by_file.items():
            lines.append(f"\n### {f}")
            for e in errs:
                severity = e.get("severity", "error")
                line = e.get("line", "?")
                col = e.get("col", "")
                error_text = e.get("error", "")
                code = e.get("code", "")
                loc = f"line {line}" + (f":{col}" if col else "")
                lines.append(f"  - [{severity}] {loc}: {error_text}" + (f" ({code})" if code else ""))

        # Read the actual error file contents for context (focused read)
        lines.append("\n## File contents (error regions):")
        for f in by_file:
            file_errors = by_file[f]
            full_path = self.project_root / f
            if not full_path.exists():
                lines.append(f"\n### {f} — FILE NOT FOUND")
                continue

            try:
                content = full_path.read_text(encoding="utf-8", errors="replace")
                file_lines = content.splitlines()
            except Exception:
                continue

            lines.append(f"\n### {f} ({len(file_lines)} lines total)")

            # Extract context around each error line (±5 lines)
            shown_ranges: list[tuple[int, int]] = []
            for e in file_errors:
                err_line = e.get("line", 0)
                if err_line < 1:
                    continue
                start = max(0, err_line - 6)
                end = min(len(file_lines), err_line + 5)

                # Merge overlapping ranges
                merged = False
                for i, (rs, re_) in enumerate(shown_ranges):
                    if start <= re_ + 1 and end >= rs - 1:
                        shown_ranges[i] = (min(rs, start), max(re_, end))
                        merged = True
                        break
                if not merged:
                    shown_ranges.append((start, end))

            shown_ranges.sort()

            for start, end in shown_ranges:
                lines.append(f"\n  Lines {start+1}-{end+1}:")
                for i in range(start, end):
                    prefix = ">>>" if any(e.get("line", 0) == i + 1 for e in file_errors) else "   "
                    lines.append(f"  {prefix} {i+1}: {file_lines[i]}")

        # Extra files requested
        if extra_files:
            lines.append("\n## Extra context files:")
            for f in extra_files:
                full_path = self.project_root / f
                if full_path.exists():
                    try:
                        content = full_path.read_text(encoding="utf-8", errors="replace")
                        lines.append(f"\n### {f}")
                        lines.append(f"```\n{content[:3000]}\n```")
                    except Exception:
                        pass

        return "\n".join(lines)