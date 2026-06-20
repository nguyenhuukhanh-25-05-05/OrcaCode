"""Tool execution mixin for AgentController.

Provides _execute_tool dispatcher plus specialized executors for each tool type:
write_file, patch_file, line_patch, anchor_patch, run_command, read_file,
search_code, debug_error, and refactor (multi-file with atomic rollback).
"""

import ast
import json
import logging
import re
from pathlib import Path

from core.services.section_parser import SectionParser
from core.services.tool_registry import ToolRegistry, ToolNotFoundError

logger = logging.getLogger("orca.tools")


class ToolExecutorMixin:
    """Mixin providing _execute_tool via ToolRegistry + individual executors.

    This mixin is inherited by AgentController and relies on the services
    that AgentController exposes via its __getattr__ delegation to the
    ServiceContainer: patch_svc, anchor_patcher, security_svc, debug_svc.
    """

    # ── Registry-backed Dispatcher ───────────────────────────────────────────

    def _init_tool_registry(self) -> ToolRegistry:
        """Create and populate the ToolRegistry with all known tools."""
        registry = ToolRegistry()
        registry.register("write_file", self._execute_write_file, "Write/create a file with content")
        registry.register("patch_file", self._execute_patch_file, "Apply a SEARCH/REPLACE block to an existing file")
        registry.register("anchor_patch", self._execute_anchor_patch, "Patch content between anchor markers")
        registry.register("line_patch", self._execute_line_patch, "Patch specific lines by line number")
        registry.register("run_command", self._execute_run_command, "Execute a shell command (60s timeout)")
        registry.register("refactor", self._execute_refactor, "Multi-file refactor with atomic rollback")
        registry.register("debug_error", self._execute_debug_error, "Parse and analyze error stack traces")
        registry.register("read_file", self._execute_read_file, "Read content from a file")
        registry.register("search_code", self._execute_search_code, "Search codebase for a pattern")
        registry.register("search_replace_block", self._execute_search_replace_block,
                         "Aider-style SEARCH/REPLACE block: <<<<<<< SEARCH ... ======= ... >>>>>>> REPLACE")
        registry.register("rollback", self._execute_rollback, "Undo last write_file/patch_file — restore snapshot")
        registry.register("codebase_outline", self._execute_codebase_outline,
                         "Get project outline: files + classes/functions (no code)")
        return registry

    def _execute_tool(self, tc: dict) -> dict:
        """Execute a single tool call via the ToolRegistry.

        Returns a dict with at minimum:
            summary (str): Human-readable result description.
            success (bool): Whether the tool succeeded.

        If the tool is not registered, returns an error with available tool list
        so the LLM can self-correct instead of crashing.
        """
        t = tc.get("type", "")
        registry: ToolRegistry = getattr(self, "_tool_registry", None)
        if registry is None:
            return {"summary": "ToolRegistry chưa được khởi tạo", "success": False}
        try:
            return registry.execute(t, tc)
        except ToolNotFoundError as e:
            available = registry.list_tools()
            tool_list = ", ".join(f"'{t['name']}'" for t in available)
            return {
                "summary": f"Tool '{t}' không tồn tại. Các tool khả dụng: {tool_list}",
                "success": False,
                "error_type": "tool_not_found",
            }

    # ── File Write ───────────────────────────────────────────────────────────

    def _validated_write(self, path: str, content: str) -> dict | None:
        """Pre-commit validation: parse AST/syntax TRƯỚC khi ghi file.
        Trả về dict lỗi nếu validation fail, None nếu OK.
        """
        ext = Path(path).suffix.lower()
        try:
            if ext == ".py":
                ast.parse(content)
            elif ext == ".json":
                json.loads(content)
            elif ext in (".html", ".htm"):
                from collections import Counter
                VOID_TAGS = frozenset({"br", "hr", "img", "input", "meta", "link", "area", "base", "col", "embed", "source", "track", "wbr"})
                opens = Counter()
                closes = Counter()
                for m in re.finditer(r'</?(\w+)[^>]*>', content):
                    tag = m.group(1).lower()
                    if m.group(0)[1] == '/':
                        closes[tag] += 1
                    elif tag not in VOID_TAGS:
                        opens[tag] += 1
                for tag, cnt in opens.items():
                    if cnt != closes.get(tag, 0):
                        return {
                            "summary": f"PRE-COMMIT VALIDATION FAILED: {path} — tag <{tag}> mở={cnt} đóng={closes.get(tag, 0)} (thiếu thẻ đóng). Sửa trước khi ghi.",
                            "success": False,
                        }
        except SyntaxError as e:
            return {
                "summary": f"PRE-COMMIT VALIDATION FAILED: {path} — Python syntax error: {e}. Sửa trước khi ghi.",
                "success": False,
            }
        except json.JSONDecodeError as e:
            return {
                "summary": f"PRE-COMMIT VALIDATION FAILED: {path} — JSON parse error: {e}. Sửa trước khi ghi.",
                "success": False,
            }
        return None

    def _execute_write_file(self, tc: dict) -> dict:
        path = tc["path"]
        content = tc.get("content", "")

        if not content.strip():
            return {
                "summary": f"Write skipped: {path} (empty)",
                "success": False,
            }

        # Pre-commit validation: parse syntax TRƯỚC khi ghi
        validated = self._validated_write(path, content)
        if validated is not None:
            return validated

        # Truncation guard: block WRITE_FILE for existing files > 50 lines
        # to prevent accidental data loss from truncated AI responses
        mode = tc.get("mode", "overwrite")
        if mode != "append":
            existing_content = self.patch_svc.read_file(path)
            if existing_content is not None:
                existing_lines = existing_content.count("\n") + 1
                if existing_lines > 50:
                    logger.warning(
                        "WRITE_FILE BLOCKED: %s has %d lines (>50). Use PATCH_FILE instead.",
                        path, existing_lines
                    )
                    return {
                        "summary": f"WRITE_FILE BLOCKED: {path} has {existing_lines} lines. "
                                   f"Use PATCH_FILE or LINE_PATCH to edit large files safely.",
                        "success": False,
                    }

        if not self.security_svc.approve_write_file(path, content):
            return {"summary": f"Write declined: {path}", "success": False, "skipped": True}

        # Snapshot for Time Machine
        self._snapshot_before_write(path)

        is_truncated = tc.get("_truncated", False)

        # Truncated or append → use append path (no auto-split)
        if mode == "append" or is_truncated:
            result = self.patch_svc.append_file(path, content)
            kind = "Appended-partial" if is_truncated else "Appended"
            logger.info("write_file(%s) %s success=%s", kind, path, result.success)
            summary = result.summary
            if is_truncated:
                summary += " [PARTIAL - file chưa hoàn chỉnh, cần append thêm]"
                return {"summary": summary, "success": True, "_incomplete": True}
            return {"summary": summary, "success": result.success}

        # Normal write — check if content is large enough to auto-split
        lines = content.splitlines()
        if len(lines) > 200 or len(content) > 15000:
            sections = self._write_file_chunked(path, content)
            if sections:
                return {
                    "summary": f"Written (chunked: {len(sections)} sections): {path}",
                    "success": True,
                    "_chunked": True,
                    "sections": sections,
                    "path": path,
                }

        # Normal write for small files
        result = self.patch_svc.write_file(path, content)
        logger.info("write_file %s success=%s", path, result.success)
        return {"summary": result.summary, "success": result.success}

    def _write_file_chunked(self, path: str, content: str) -> list[dict]:
        """Split large content into section-marked chunks, write skeleton + each section."""
        parser = SectionParser()
        sections = parser.auto_section_content(content, path)
        if not sections:
            return []  # content not large enough

        # 1. Write skeleton file with only section markers
        skeleton = parser.build_skeleton(sections)
        self.patch_svc.write_file(path, skeleton)
        logger.info("write_file(skeleton) %s: %d sections", path, len(sections))

        # 2. Write each section via anchor patch (uses relative path)
        for sec in sections:
            self.anchor_patcher.replace_between(
                path,
                sec["start_marker"],
                sec["end_marker"],
                sec["content"],
            )
            logger.info("write_file(chunk) %s section=%s len=%d", path, sec["name"], len(sec["content"]))

        return sections

    # ── File Patches ─────────────────────────────────────────────────────────

    def _execute_patch_file(self, tc: dict) -> dict:
        path = tc["path"]
        search = tc.get("search", "")
        replace = tc.get("replace", "")

        if tc.get("_truncated"):
            return {
                "summary": f"Patch skipped: {path} (truncated)",
                "success": False,
                "_incomplete": True,
            }

        # Snapshot for Time Machine
        self._snapshot_before_write(path)

        result = self.patch_svc.apply_patch(path, search, replace)
        logger.info("patch_file %s success=%s score=%.2f", path, result.success, result.score)
        return {"summary": result.summary, "success": result.success}

    def _execute_line_patch(self, tc: dict) -> dict:
        path = tc["path"]
        start_line = tc["start_line"]
        end_line = tc.get("end_line")
        content = tc.get("content", "")

        result = self.patch_svc.apply_line_patch(path, start_line, end_line, content)
        logger.info("line_patch %s L%d-%s success=%s", path, start_line, end_line or start_line, result.success)
        return {"summary": result.summary, "success": result.success}

    # ── Anchor Patch ─────────────────────────────────────────────────────────

    def _execute_anchor_patch(self, tc: dict) -> dict:
        """Execute an anchor-based patch — safe section replacement."""
        path = tc["path"]
        start = tc["start"]
        end = tc["end"]
        content = tc.get("content", "")

        result = self.anchor_patcher.replace_between(path, start, end, content)
        logger.info("anchor_patch %s success=%s", path, result.success)
        return {"summary": result.summary, "success": result.success}

    # ── Run Command ──────────────────────────────────────────────────────────

    def _execute_run_command(self, tc: dict) -> dict:
        command = tc.get("command", "")

        returncode, stdout, stderr = self.security_svc.run_command(command)
        output = stdout.strip() if stdout.strip() else stderr.strip()
        summary = output[:500] if output else "(no output)"

        if returncode != 0:
            summary = f"[exit {returncode}] {summary}"
            logger.warning("run_command exit=%d: %s", returncode, command[:80])
        else:
            logger.info("run_command ok: %s", command[:80])

        return {"summary": summary, "success": returncode == 0}

    # ── Read & Search ────────────────────────────────────────────────────────

    def _execute_read_file(self, tc: dict) -> dict:
        path = tc.get("path", "")
        content = self.patch_svc.read_file(path)

        if content is None:
            return {"summary": f"File not found or binary: {path}", "success": False}

        return {"summary": f"Read {path} ({len(content)} chars)", "success": True}

    def _execute_search_code(self, tc: dict) -> dict:
        pattern = tc.get("pattern", "")
        file_pattern = tc.get("file_pattern", "")

        results = self.patch_svc.search_code(pattern, file_pattern)
        if not results:
            return {"summary": f"No matches for: {pattern[:60]}", "success": True}

        lines = [f"{r['file']}:{r['line']}: {r['text'][:100]}" for r in results[:20]]
        suffix = f" ({len(results) - 20} more)" if len(results) > 20 else ""
        return {
            "summary": f"Found {len(results)} matches{suffix}:\n" + "\n".join(lines),
            "success": True,
        }

    # ── Debug Error ──────────────────────────────────────────────────────────

    def _execute_debug_error(self, tc: dict) -> dict:
        content = tc.get("content", "")
        frames = self.debug_svc.parse_stack_trace(content)
        error_type = self.debug_svc.extract_error_type(content)
        suggestion = self.debug_svc.suggest_fix_command(content)

        parts = []
        if error_type:
            parts.append(f"Error: {error_type}")
        if frames:
            parts.append(f"Found {len(frames)} stack frame(s):")
            for f in frames[:5]:
                parts.append(f"  {f['file']}:{f['line']} in {f['func']}")
        if suggestion:
            parts.append(f"Suggestion: {suggestion}")

        return {
            "summary": "\n".join(parts) if parts else "No error patterns detected",
            "success": True,
        }

    # ── Refactor ─────────────────────────────────────────────────────────────

    def _execute_refactor(self, tc: dict) -> dict:
        """Execute a multi-file refactor with atomic rollback.

        Parses PATCH_FILE blocks from the refactor content and applies each
        one. If any patch fails, rolls back all modified files to their
        original state.
        """
        description = tc.get("description", "")
        content = tc.get("content", "")
        files = tc.get("files", [])

        if not content.strip():
            return {"summary": "Refactor: no content", "success": False}

        # Parse PATCH_FILE blocks from the refactor content
        import re
        patch_block_re = re.compile(
            r'<PATCH_FILE\s+path=["\']([^"\']+)["\'][^>]*>(.*?)</PATCH_FILE>',
            re.DOTALL | re.IGNORECASE,
        )
        search_replace_re = re.compile(
            r'(?:-{3,}|<{3,})\s*SEARCH\s*\n(.*?)\n\s*={3,}\s*\n(.*?)\n\s*(?:\+{3,}|>{3,})\s*REPLACE',
            re.DOTALL | re.IGNORECASE,
        )

        patches = []
        for m in patch_block_re.finditer(content):
            file_path = m.group(1).strip()
            block = m.group(2)
            pairs = search_replace_re.findall(block)
            for search_text, replace_text in pairs:
                patches.append({
                    "path": file_path,
                    "search": search_text.strip(),
                    "replace": replace_text.strip(),
                })

        if not patches:
            return {"summary": "Refactor: no patches found in content", "success": False}

        # Backup for atomic rollback
        backups = {}
        modified_paths = set()

        for p in patches:
            path = p["path"]
            modified_paths.add(path)
            if path not in backups:
                old = self.patch_svc.read_file(path)
                if old is not None:
                    backups[path] = old

        # Apply patches sequentially; rollback all on any failure
        applied = []
        try:
            for p in patches:
                result = self.patch_svc.apply_patch(p["path"], p["search"], p["replace"])
                if not result.success:
                    logger.error("refactor patch failed: %s — rolling back %d files", p["path"], len(applied))
                    self._rollback_refactor(backups)
                    return {
                        "summary": f"Refactor failed at {p['path']}: {result.summary} — all changes rolled back",
                        "success": False,
                    }
                applied.append(p)
        except Exception as e:
            logger.exception("refactor exception — rolling back")
            self._rollback_refactor(backups)
            return {"summary": f"Refactor error: {e} — all changes rolled back", "success": False}

        logger.info("refactor applied %d patches to %d files", len(applied), len(modified_paths))
        return {
            "summary": f"Refactor: {description[:100]} ({len(applied)} patches, {len(modified_paths)} files)",
            "success": True,
            "patches": [{"path": p} for p in sorted(modified_paths)],
        }

    def _rollback_refactor(self, backups: dict) -> None:
        """Restore files to their pre-refactor state."""
        for path, original in backups.items():
            try:
                self.patch_svc.write_file(path, original)
                logger.info("rollback: restored %s", path)
            except Exception:
                logger.exception("rollback failed for %s", path)

    # ── Snapshot: Time Machine ──────────────────────────────────────────────

    def _snapshot_before_write(self, path: str) -> None:
        """Snapshot current file content before modification."""
        try:
            old = self.patch_svc.read_file(path)
            if old is not None:
                stack: list = getattr(self, "_rollback_stack", [])
                stack.append({path: (old, "")})
        except Exception:
            pass

    def _execute_rollback(self, tc: dict) -> dict:
        """Restore the most recent snapshot from rollback stack."""
        stack: list = getattr(self, "_rollback_stack", [])
        if not stack:
            return {"summary": "Không có snapshot nào để rollback", "success": False}
        snapshot = stack.pop()
        restored = []
        for path, (old_content, _new_content) in snapshot.items():
            try:
                self.patch_svc.write_file(path, old_content)
                restored.append(path)
                logger.info("rollback: restored %s", path)
            except Exception as e:
                logger.exception("rollback failed for %s", path)
                return {"summary": f"Rollback thất bại cho {path}: {e}", "success": False}
        return {
            "summary": f"Rollback thành công: {', '.join(restored)}",
            "success": True,
        }

    # ── Codebase Outline ────────────────────────────────────────────────────

    def _execute_codebase_outline(self, tc: dict) -> dict:
        """Return project outline: file paths + classes/functions (no code)."""
        outline_svc = getattr(self, "_codebase_outline", None)
        if outline_svc is None:
            return {"summary": "CodebaseOutline chưa được khởi tạo", "success": False}
        try:
            outline = outline_svc.get_outline(max_files=200)
            return {"summary": outline, "success": True}
        except Exception as e:
            return {"summary": f"Codebase outline error: {e}", "success": False}

    # ── SEARCH/REPLACE Block (Aider/Cline format) ──────────────────────────

    def _execute_search_replace_block(self, tc: dict) -> dict:
        """Parse Aider-style SEARCH/REPLACE blocks and apply each as a patch.

        Format in tc['content']:
            <<<<<<< SEARCH
            old code
            =======
            new code
            >>>>>>> REPLACE
        """
        content = tc.get("content", "")
        path = tc.get("path", "")
        if not content.strip():
            return {"summary": "SEARCH/REPLACE block trống", "success": False}

        if not self.security_svc.approve_write_file(path, content):
            return {"summary": f"SEARCH/REPLACE declined: {path}", "success": False, "skipped": True}

        # Parse blocks
        block_pattern = re.compile(
            r'<<<<<<< SEARCH\s*\n(.*?)\n=======\s*\n(.*?)\n>>>>>>> REPLACE',
            re.DOTALL
        )
        blocks = block_pattern.findall(content)

        if not blocks:
            # Try without newlines (inline format)
            block_pattern2 = re.compile(
                r'<<<<<<< SEARCH\s+(.*?)\s+=======\s+(.*?)\s+>>>>>>> REPLACE',
                re.DOTALL
            )
            blocks = block_pattern2.findall(content)

        if not blocks:
            return {"summary": "Không tìm thấy SEARCH/REPLACE block hợp lệ trong content", "success": False}

        # Snapshot before first write
        self._snapshot_before_write(path)

        applied = 0
        for search_text, replace_text in blocks:
            result = self.patch_svc.apply_patch(path, search_text.strip(), replace_text.strip())
            if not result.success:
                return {
                    "summary": f"SEARCH/REPLACE thất bại ở block #{applied + 1}: {result.summary}. "
                               f"Tìm không thấy đoạn:\n```\n{search_text.strip()[:200]}\n```",
                    "success": False,
                }
            applied += 1

        return {
            "summary": f"SEARCH/REPLACE: {applied} block(s) applied to {path}",
            "success": True,
        }
