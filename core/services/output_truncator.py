"""Tool output truncation — head+tail with error-aware allocation.

Learns from MiMo's tool/truncate.ts pattern:
1. Dual limits: MAX_LINES (2000) and MAX_CHARS (50K)
2. Head+tail truncation with "[... truncated ...]" marker
3. Error-aware: if tail contains error keywords, allocate 50/50 instead of 70/30
4. File spill: full output saved to file, path included in hint
"""

import logging
import os
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger("orca.truncator")

MAX_OUTPUT_LINES = 2000
MAX_OUTPUT_CHARS = 50000
TRUNCATED_MARKER = "\n[... truncated ({} chars -> {}) ...]\n"
TRUNCATION_DIR_NAME = ".orca_truncated"

# Error keywords that shift allocation toward tail
ERROR_KEYWORDS = frozenset({
    "error", "fail", "traceback", "exception",
    "lỗi", "warning", "syntaxerror", "importerror",
    "valueerror", "typeerror", "attributeerror", "keyerror",
    "assertionerror", "runtimeerror", "modulenotfounderror",
})


class OutputTruncator:
    """Truncates tool output at point of insertion into messages."""

    def __init__(self, project_root: str = "", max_chars: int = MAX_OUTPUT_CHARS,
                 max_lines: int = MAX_OUTPUT_LINES, pressure_caps: bool = False):
        self.project_root = project_root
        self.max_chars = max_chars // 2 if pressure_caps else max_chars
        self.max_lines = max_lines // 2 if pressure_caps else max_lines

    def truncate(self, text: str, tool_name: str = "", path: str = "") -> str:
        """Truncate tool output preserving head+tail with error-aware allocation.
        
        Returns truncated text with hint for reading full output.
        If text is within limits, returns unchanged.
        """
        if not text:
            return text

        chars = len(text)
        lines = text.count("\n") + 1

        if chars <= self.max_chars and lines <= self.max_lines:
            return text

        # Error-aware tail analysis
        tail_region = text[-min(2048, chars):].lower()
        has_errors = any(kw in tail_region for kw in ERROR_KEYWORDS)
        head_ratio = 0.50 if has_errors else 0.70

        # Compute char budget — cap at actual text length to avoid duplication
        budget = min(self.max_chars, chars)
        head_chars = int(budget * head_ratio)
        marker_len = len(TRUNCATED_MARKER.format(chars, self.max_chars))
        tail_chars = budget - head_chars - marker_len
        if tail_chars < 0:
            tail_chars = 0
            head_chars = budget - marker_len

        # Ensure minimum tail for error info
        if has_errors and tail_chars < 1024 and chars > head_chars + 1024:
            tail_chars = min(1024, chars - head_chars)
            head_chars = int(budget * 0.50)

        # Truncate at line boundaries
        if head_chars >= chars:
            # Line overflow only (chars within budget) — trim middle lines
            head = self._truncate_lines(text, self.max_lines)
            marker = TRUNCATED_MARKER.format(chars, self.max_chars)
            tail = ""
        else:
            head = text[:head_chars]
            head_last_nl = head.rfind("\n")
            if head_last_nl > 0:
                head = head[:head_last_nl]

            if tail_chars > 0:
                tail = text[-tail_chars:]
                tail_first_nl = tail.find("\n")
                if 0 < tail_first_nl < len(tail):
                    tail = tail[tail_first_nl + 1:]
            else:
                tail = ""

            marker = TRUNCATED_MARKER.format(chars, self.max_chars)

        result = head + marker + tail

        # Only spill when actually truncated
        if self.project_root and result != text and len(result) < len(text):
            try:
                spill_path = self._spill_to_file(text, tool_name, path)
                hint = self._build_hint(spill_path)
                result = result + hint
            except Exception as e:
                logger.debug("Spill failed: %s", e)

        return result

    @staticmethod
    def _truncate_lines(text: str, max_lines: int) -> str:
        """Truncate by keeping first N/2 and last N/2 lines when only line limit exceeded."""
        lines = text.split("\n")
        if len(lines) <= max_lines:
            return text
        n = max_lines // 2
        head = "\n".join(lines[:n])
        tail = "\n".join(lines[-n:])
        return head + f"\n[... truncated {len(lines)} -> {max_lines} lines ...]\n" + tail

    def _spill_to_file(self, text: str, tool_name: str, path: str) -> str:
        """Write full tool output to a file in .orca_truncated/."""
        trunc_dir = Path(self.project_root) / TRUNCATION_DIR_NAME
        trunc_dir.mkdir(parents=True, exist_ok=True)

        # Clean old files (>1 day)
        self._cleanup_old(trunc_dir)

        safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in (tool_name or "tool"))
        file_id = uuid.uuid4().hex[:8]
        filename = f"{safe_name}_{file_id}.txt"
        filepath = trunc_dir / filename
        filepath.write_text(text, encoding="utf-8")
        return str(filepath)

    def _cleanup_old(self, trunc_dir: Path, max_age_seconds: int = 86400):
        """Remove spill files older than max_age_seconds."""
        import time
        now = time.time()
        for f in trunc_dir.iterdir():
            if f.is_file() and f.suffix == ".txt":
                age = now - f.stat().st_mtime
                if age > max_age_seconds:
                    try:
                        f.unlink()
                    except OSError:
                        pass

    def _build_hint(self, spill_path: str) -> str:
        """Build hint for the model to access full output."""
        if spill_path:
            return f"\n[Full output saved to {spill_path}. Use Read tool to view if needed.]"
        return ""
