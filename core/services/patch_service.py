"""Patch Service - intelligent file patching with fuzzy matching + anchor patches."""
import re
import os
import time
import random
import subprocess
from pathlib import Path
from core.models import PatchOperation, PatchResult
from utils.normalize import normalize_line
from utils.diff import format_diff_simple
from core.services.anchor_patcher import AnchorPatcher

from core.constants import PATCH_PARTIAL_TIMEOUT


_RETRY_MAX_ATTEMPTS = 5
_RETRY_BASE_DELAY = 1.0


def _write_with_retry(full_path: Path, content: str, mode: str = "w") -> None:
    """Write file with exponential backoff when OneDrive/AV locks the file.
    Retry chỉ trên lỗi filesystem (PermissionError, OSError), không retry lỗi logic.
    """
    import io
    last_exc = None
    for attempt in range(_RETRY_MAX_ATTEMPTS):
        try:
            if mode == "a":
                with full_path.open("a", encoding="utf-8") as f:
                    f.write("\n" + content)
            else:
                full_path.write_text(content, encoding="utf-8")
            return
        except PermissionError as e:
            last_exc = e
        except OSError as e:
            last_exc = e
        except io.UnsupportedOperation as e:
            raise e  # Không retry lỗi logic
        if attempt < _RETRY_MAX_ATTEMPTS - 1:
            delay = _RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 0.5)
            time.sleep(delay)
    raise last_exc  # type: ignore[misc]


def _get_fuzz():
    from rapidfuzz import fuzz
    return fuzz


_fuzz = _get_fuzz

FUZZY_THRESHOLD = 85
MAX_LINES_FOR_PARTIAL = 5000


def _is_binary(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        with open(path, "rb") as f:
            return b"\0" in f.read(8192)
    except Exception:
        return True


class PatchService:
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)

    def apply_operation(self, operation: PatchOperation) -> PatchResult:
        return self.apply_patch(operation.file_path, "\n".join(operation.search_lines), "\n".join(operation.replace_lines))

    def apply_patch(self, file_path: str, search_text: str, replace_text: str, threshold: int = FUZZY_THRESHOLD) -> PatchResult:
        fuzz = _fuzz()
        full_path = self.project_root / file_path
        if not full_path.exists():
            return PatchResult(False, file_path, "File not found")
        if _is_binary(full_path):
            return PatchResult(False, file_path, "Cannot patch binary file")
        old_content = full_path.read_text(encoding="utf-8", errors="replace")
        old_lines = old_content.splitlines()
        search_lines = search_text.splitlines()
        replace_lines = replace_text.splitlines()
        if not search_lines or not search_lines[0]:
            return PatchResult(False, file_path, "Empty SEARCH block")
        old_norm = [normalize_line(l) for l in old_lines]
        search_norm = [normalize_line(l) for l in search_lines]
        n_search = len(search_lines)
        n_old = len(old_lines)
        best_idx = -1
        best_score = 0
        for i in range(n_old - n_search + 1):
            window_norm = old_norm[i:i + n_search]
            total = sum(fuzz.ratio(search_norm[j], window_norm[j]) for j in range(n_search))
            avg = total / n_search
            if avg > best_score:
                best_score = avg
                best_idx = i
                if best_score >= 100:
                    break
        if best_score >= threshold:
            new_lines = old_lines[:best_idx] + replace_lines + old_lines[best_idx + n_search:]
            new_content = "\n".join(new_lines)
            _write_with_retry(full_path, new_content)
            diff = format_diff_simple(old_content, new_content, file_path)
            return PatchResult(True, file_path, f"Patched ({best_score:.0f}% match)", diff=diff, score=best_score / 100)
        result = self._try_partial(old_lines, old_norm, search_lines, search_norm, replace_lines, file_path, old_content, threshold)
        if result:
            return result

        # Auto LINE_PATCH fallback: find approximate location of SEARCH lines
        for i, line in enumerate(search_text.splitlines()):
            norm_line = normalize_line(line)
            for j, ol in enumerate(old_norm):
                if fuzz.ratio(norm_line, ol) >= 90:
                    start = max(1, j)
                    end = min(len(old_lines), start + len(search_lines) - 1)
                    try:
                        return self.apply_line_patch(file_path, start, end, replace_text)
                    except Exception:
                        pass
                    break

        return PatchResult(False, file_path, f"No match found (best {best_score:.0f}% < {threshold}%)", score=best_score / 100)

    def _try_partial(self, old_lines, old_norm, search_lines, search_norm, replace_lines, file_path, old_content, threshold) -> PatchResult | None:
        n_search = len(search_lines)
        n_old = len(old_lines)
        if n_old > MAX_LINES_FOR_PARTIAL:
            return None
        deadline = time.monotonic() + PATCH_PARTIAL_TIMEOUT
        for chunk_size in (min(3, n_search), min(2, n_search), 1):
            if chunk_size < 1:
                continue
            if time.monotonic() > deadline:
                return None
            best_idx = -1
            best_score = 0
            best_search_start = 0
            for s in range(n_search - chunk_size + 1):
                if time.monotonic() > deadline:
                    return None
                chunk_search = search_norm[s:s + chunk_size]
                for i in range(n_old - chunk_size + 1):
                    if time.monotonic() > deadline:
                        return None
                    chunk_old = old_norm[i:i + chunk_size]
                    total = sum(fuzz.ratio(chunk_search[j], chunk_old[j]) for j in range(chunk_size))
                    avg = total / chunk_size
                    if avg > best_score:
                        best_score = avg
                        best_idx = i
                        best_search_start = s
            if best_score >= threshold:
                # Calculate the corresponding replacement lines based on the matched search position
                # If we matched a chunk starting at search position best_search_start,
                # we need to figure out the proportional replacement
                if chunk_size == len(search_lines):
                    # Full search matched → use all replace lines
                    actual_replace = replace_lines
                else:
                    # Partial match → use all replace lines but log a warning
                    # This is the best we can do since the SEARCH/REPLACE blocks
                    # are meant to be used together
                    actual_replace = replace_lines
                new_lines = old_lines[:best_idx] + actual_replace + old_lines[best_idx + chunk_size:]
                new_content = "\n".join(new_lines)
                full_path = self.project_root / file_path
                _write_with_retry(full_path, new_content)
                diff = format_diff_simple("\n".join(old_lines), new_content, file_path)
                return PatchResult(True, file_path, f"Patched (partial {chunk_size}/{len(search_lines)} lines, {best_score:.0f}%)", diff=diff, score=best_score / 100)
        return None

    def write_file(self, file_path: str, content: str) -> PatchResult:
        return self._write_file_impl(file_path, content, append=False)

    def append_file(self, file_path: str, content: str) -> PatchResult:
        return self._write_file_impl(file_path, content, append=True)

    def _write_file_impl(self, file_path: str, content: str, append: bool = False) -> PatchResult:
        full_path = self.project_root / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        if _is_binary(full_path):
            return PatchResult(False, file_path, "Cannot overwrite binary file")
        if append and full_path.exists():
            _write_with_retry(full_path, content, mode="a")
            return PatchResult(True, file_path, f"Appended ({len(content)} bytes)")
        _write_with_retry(full_path, content)
        return PatchResult(True, file_path, f"Written ({len(content)} bytes)")

    def read_file(self, file_path: str) -> str | None:
        full_path = self.project_root / file_path
        try:
            if not full_path.exists():
                return None
            if _is_binary(full_path):
                return None
            return full_path.read_text(encoding="utf-8", errors="replace")
        except (FileNotFoundError, OSError):
            return None

    LINE_PATTERN = re.compile(
        r'<LINE_PATCH\s+path=["\']([^"\']+)["\']\s+start=["\'](\d+)["\']'
        r'(?:\s+end=["\'](\d+)["\'])?[^>]*>\s*(.*?)\s*</LINE_PATCH>', re.DOTALL | re.IGNORECASE
    )
    PATCH_BLOCK_PATTERN = re.compile(r'<PATCH_FILE\s+path=["\']([^"\']+)["\'][^>]*>(.*?)</PATCH_FILE>', re.DOTALL | re.IGNORECASE)
    SEARCH_REPLACE_PATTERN = re.compile(
        r'(?:-{3,}|<{3,})\s*SEARCH\s*\n(.*?)\n\s*={3,}\s*\n(.*?)\n\s*(?:\+{3,}|>{3,})\s*REPLACE', re.DOTALL | re.IGNORECASE
    )
    WRITE_PATTERN = re.compile(r'<WRITE_FILE\s+path=["\']([^"\']+)["\'][^>]*>\s*(.*?)\s*</WRITE_FILE>', re.DOTALL | re.IGNORECASE)
    READ_PATTERN = re.compile(r'<READ_FILE[^>]*>\s*(.*?)\s*</READ_FILE>', re.DOTALL | re.IGNORECASE)
    SEARCH_PATTERN = re.compile(r'<SEARCH_CODE[^>]*>\s*(.*?)\s*</SEARCH_CODE>', re.DOTALL | re.IGNORECASE)
    RUN_PATTERN = re.compile(r'<RUN_COMMAND[^>]*>\s*(.*?)\s*</RUN_COMMAND>', re.DOTALL | re.IGNORECASE)
    REFACTOR_PATTERN = re.compile(r'<REFACTOR[^>]*>\s*(.*?)\s*</REFACTOR>', re.DOTALL | re.IGNORECASE)
    DEBUG_PATTERN = re.compile(r'<DEBUG_ERROR[^>]*>\s*(.*?)\s*</DEBUG_ERROR>', re.DOTALL | re.IGNORECASE)
    ANCHOR_PATTERN = re.compile(
        r'<ANCHOR_PATCH\s+path=["\']([^"\']+)["\'][^>]*>'
        r'(.*?)</ANCHOR_PATCH>', re.DOTALL | re.IGNORECASE
    )

    def search_code(self, pattern: str, file_pattern: str = "") -> list[dict]:
        results = []
        root = str(self.project_root)
        if not pattern.strip():
            return results
        cmd = ["rg", "-n", "--no-heading", "--color=never", "--", pattern]
        if file_pattern:
            cmd.extend(["-g", file_pattern])
        try:
            out = subprocess.check_output(cmd, cwd=root, stderr=subprocess.DEVNULL, timeout=10).decode("utf-8", errors="replace")
            for line in out.splitlines():
                parts = line.split(":", 2)
                if len(parts) == 3:
                    results.append({"file": parts[0], "line": int(parts[1]), "text": parts[2]})
                elif len(parts) == 2:
                    results.append({"file": parts[0], "line": int(parts[1]), "text": ""})
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            pass
        return results

    def apply_line_patch(self, file_path: str, start_line: int, end_line: int | None, content: str) -> PatchResult:
        full_path = self.project_root / file_path
        if not full_path.exists():
            return PatchResult(False, file_path, "File not found")
        if _is_binary(full_path):
            return PatchResult(False, file_path, "Cannot patch binary file")
        old_content = full_path.read_text(encoding="utf-8", errors="replace")
        old_lines = old_content.splitlines()
        if start_line < 1:
            return PatchResult(False, file_path, "start_line must be >= 1")
        n = len(old_lines)
        end = end_line if end_line is not None else start_line
        if end < start_line:
            return PatchResult(False, file_path, "end_line must be >= start_line")
        new_lines = content.splitlines()
        if start_line > n:
            old_lines.extend([""] * (start_line - n - 1))
            old_lines.extend(new_lines)
        elif end >= n:
            old_lines = old_lines[:start_line - 1] + new_lines
        else:
            old_lines = old_lines[:start_line - 1] + new_lines + old_lines[end:]
        new_content = "\n".join(old_lines)
        _write_with_retry(full_path, new_content)
        diff = format_diff_simple(old_content, new_content, file_path)
        from_line = start_line
        to_line = min(end, n)
        return PatchResult(True, file_path, f"Line-patched: {from_line}-{to_line}", diff=diff, score=1.0)

    def parse_tool_calls(self, ai_response: str) -> list[dict]:
        calls = []
        
        # 0. Parse LINE_PATCH blocks (most precise — by line number)
        for m in self.LINE_PATTERN.finditer(ai_response):
            calls.append({
                "type": "line_patch",
                "path": m.group(1).strip(),
                "start_line": int(m.group(2)),
                "end_line": int(m.group(3)) if m.group(3) else None,
                "content": m.group(4).strip(),
            })

        # 1. Parse PATCH_FILE blocks (supports multiple SEARCH/REPLACE pairs per tag)
        for m in self.PATCH_BLOCK_PATTERN.finditer(ai_response):
            file_path = m.group(1).strip()
            block_content = m.group(2)
            pairs = self.SEARCH_REPLACE_PATTERN.findall(block_content)
            for search_text, replace_text in pairs:
                calls.append({
                    "type": "patch_file", 
                    "path": file_path, 
                    "search": search_text.strip(), 
                    "replace": replace_text.strip()
                })
                
        # 2. Parse WRITE_FILE blocks
        for m in self.WRITE_PATTERN.finditer(ai_response):
            tag = m.group(0)
            mode_m = re.search(r'\bmode=(["\'])(append)\1', tag)
            entry = {"type": "write_file", "path": m.group(1).strip(), "content": m.group(2).strip()}
            if mode_m:
                entry["mode"] = mode_m.group(2)
            calls.append(entry)
            
        # 2b. Parse READ_FILE blocks
        for m in self.READ_PATTERN.finditer(ai_response):
            path = m.group(1).strip()
            calls.append({"type": "read_file", "path": path})

        # 2c. Parse SEARCH_CODE blocks
        for m in self.SEARCH_PATTERN.finditer(ai_response):
            content = m.group(1).strip()
            parts = content.split("\n", 1)
            pattern = parts[0].strip()
            file_pattern = parts[1].strip() if len(parts) > 1 else ""
            calls.append({"type": "search_code", "pattern": pattern, "file_pattern": file_pattern})

        # 3. Parse RUN_COMMAND blocks
        for m in self.RUN_PATTERN.finditer(ai_response):
            calls.append({"type": "run_command", "command": m.group(1).strip()})
            
        # 4. Parse REFACTOR blocks
        for m in self.REFACTOR_PATTERN.finditer(ai_response):
            text = m.group(1).strip()
            files = re.findall(r'(?:File\s*\d+|-\s*)\s*:?\s*(.+?)$', text, re.MULTILINE)
            calls.append({"type": "refactor", "content": text, "files": files, "description": text.split('\n')[0] if text else ""})
            
        # 5. Parse DEBUG blocks
        for m in self.DEBUG_PATTERN.finditer(ai_response):
            calls.append({"type": "debug_error", "content": m.group(1).strip()})
            
        # 6. Parse ANCHOR_PATCH blocks (section-based safe editing)
        for m in self.ANCHOR_PATTERN.finditer(ai_response):
            file_path = m.group(1).strip()
            block = m.group(2)
            # Parse start/end/content from the anchor block
            start_m = re.search(r'<START>(.*?)</START>', block, re.DOTALL)
            end_m = re.search(r'<END>(.*?)</END>', block, re.DOTALL)
            content_m = re.search(r'<CONTENT>(.*?)</CONTENT>', block, re.DOTALL)
            if start_m and end_m and content_m:
                calls.append({
                    "type": "anchor_patch",
                    "path": file_path,
                    "start": start_m.group(1).strip(),
                    "end": end_m.group(1).strip(),
                    "content": content_m.group(1).strip(),
                })

        # 7. Fallback: Parse unclosed WRITE_FILE if it was truncated/forgot closing tag
        if "<WRITE_FILE" in ai_response and "</WRITE_FILE>" not in ai_response:
            unclosed = re.search(r'<WRITE_FILE\s+path=["\']([^"\']+)["\'][^>]*>\s*(.*)', ai_response, re.DOTALL | re.IGNORECASE)
            if unclosed:
                path = unclosed.group(1).strip()
                content = unclosed.group(2).strip()
                # Strip trailing AI explanation text that got captured
                # Look for common markers that indicate end of file content
                for marker in ['<DONE', '<PATCH_FILE', '<RUN_COMMAND', '<WRITE_FILE']:
                    idx = content.find(marker)
                    if idx > 0:
                        content = content[:idx].strip()
                        break
                if not any(c.get("type") == "write_file" and c.get("path") == path for c in calls):
                    calls.append({"type": "write_file", "path": path, "content": content, "_truncated": True})
                    
        # 8. Fallback: Parse unclosed PATCH_FILE with search/replace pairs
        if "<PATCH_FILE" in ai_response and "</PATCH_FILE>" not in ai_response:
            unclosed = re.search(r'<PATCH_FILE\s+path=["\']([^"\']+)["\'][^>]*>(.*)', ai_response, re.DOTALL | re.IGNORECASE)
            if unclosed:
                path = unclosed.group(1).strip()
                block_content = unclosed.group(2)
                pairs = self.SEARCH_REPLACE_PATTERN.findall(block_content)
                for search_text, replace_text in pairs:
                    if not any(c.get("type") == "patch_file" and c.get("path") == path and c.get("search") == search_text.strip() for c in calls):
                        calls.append({
                            "type": "patch_file", 
                            "path": path, 
                            "search": search_text.strip(), 
                            "replace": replace_text.strip(),
                            "_truncated": True,
                        })
                        
        # 9. Fallback: model didn't use any tool tags → detect code blocks as WRITE_FILE
        if not calls and ("```" in ai_response or "`" in ai_response):
            calls = self._parse_codeblock_fallback(ai_response)

        return calls

    def _parse_codeblock_fallback(self, ai_response: str) -> list[dict]:
        """Fallback for models that output code as markdown/literal instead of tool tags.

        Detects patterns like:
          - `file: path/to/file.ext` followed by ```code```
          - `create path/to/file.ext` followed by code block
          - Plain fenced code blocks with language hints as extensions
        """
        import re
        calls = []

        # Pattern 1: filename hint before code block
        #   file: src/app.py
        #   files: a.js, b.css
        #   ```python
        #   code here
        #   ```
        # Match single file hint
        file_hint = re.findall(
            r'(?:files?|path|tạo|create|write|ghi|viết)\s*[:=]\s*([\w/\-\.]+\.\w{1,6})',
            ai_response, re.IGNORECASE,
        )
        # Also match comma/and-separated file lists: files: a.js, b.css, c.html
        multi_file = re.search(
            r'(?:files?|path)\s*[:=]\s*(.+?)(?:\n|$)',
            ai_response, re.IGNORECASE,
        )
        if multi_file:
            extra = re.findall(r'([\w/\-\.]+\.\w{1,6})', multi_file.group(1))
            for f in extra:
                if f not in file_hint:
                    file_hint.append(f)

        # Find all fenced code blocks: ```lang\n code \n```
        code_blocks = re.findall(
            r'```(?:\w+)?\s*\n(.*?)```',
            ai_response, re.DOTALL,
        )

        if file_hint and code_blocks:
            # Pair first file hint with first code block
            for i, path in enumerate(file_hint):
                if i < len(code_blocks):
                    content = code_blocks[i].strip()
                    if content and len(content) > 10:  # Skip trivial inline snippets
                        calls.append({
                            "type": "write_file",
                            "path": path.strip(),
                            "content": content,
                            "_fallback": True,
                        })
            return calls

        # Pattern 2: "Here is the code for X" → try to extract filename from nearby text
        named_blocks = re.findall(
            r'(?:for|cho|cho file)\s+[`"]?([\w/\-\.]+\.\w{1,6})[`"]?',
            ai_response, re.IGNORECASE,
        )
        if named_blocks and code_blocks:
            for i, path in enumerate(named_blocks):
                if i < len(code_blocks):
                    content = code_blocks[i].strip()
                    if content and len(content) > 20:
                        calls.append({
                            "type": "write_file",
                            "path": path.strip(),
                            "content": content,
                            "_fallback": True,
                        })

        return calls
