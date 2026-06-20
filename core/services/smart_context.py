"""Smart Context – sends only relevant sections to AI instead of entire files.

When a file is large (>100 lines), instead of sending the entire file:
1. Parse the file into sections (using section markers if present)
2. Identify which sections are relevant to the user's request
3. Send only those sections + a summary of the file structure

This prevents AI context truncation and improves patch accuracy.
"""
import re
from pathlib import Path
from typing import Optional

from core.services.section_parser import SectionParser, ParsedFile, FileSection


# Maximum lines to send to AI per file before triggering smart split
SMART_CONTEXT_THRESHOLD = 100

# Maximum lines per section to send (if a section is huge, truncate it)
MAX_SECTION_LINES = 150


class SmartContext:
    """Intelligent context builder that splits large files into sections."""

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.parser = SectionParser()

    def build_file_context(
        self,
        file_path: str,
        user_prompt: str = "",
        max_lines: int = SMART_CONTEXT_THRESHOLD,
        full_content: str | None = None,
    ) -> str:
        """Build context for a single file, using smart section splitting.

        Args:
            file_path: Relative path to the file.
            user_prompt: The user's request (used for relevance matching).
            max_lines: If file is shorter than this, send entire content.
            full_content: Pre-loaded file content (optional).

        Returns:
            Formatted context string for the AI.
        """
        if full_content is None:
            full_path = self.project_root / file_path
            try:
                full_content = full_path.read_text(encoding="utf-8", errors="replace")
            except (FileNotFoundError, OSError):
                return f"[{file_path}] (file not found)"

        lines = full_content.splitlines()
        total_lines = len(lines)

        # Short file: send everything
        if total_lines <= max_lines:
            return f"[{file_path}] ({total_lines} lines)\n{full_content}"

        # Large file: use section-based splitting
        parsed = self.parser.parse(file_path, full_content)

        if parsed.has_markers and len(parsed.sections) > 1:
            return self._build_sectioned_context(parsed, user_prompt, file_path)
        else:
            return self._build_split_context(full_content, user_prompt, file_path)

    def _build_sectioned_context(
        self,
        parsed: ParsedFile,
        user_prompt: str,
        file_path: str,
    ) -> str:
        """Build context from a file that has section markers."""
        parts = []
        total_lines = len(parsed.raw_content.splitlines())

        # File header with section listing
        section_names = parsed.get_section_names()
        parts.append(
            f"[{file_path}] ({total_lines} lines, {len(section_names)} sections: "
            f"{', '.join(section_names)})"
        )

        # Relevance scoring for each section
        prompt_lower = user_prompt.lower()
        prompt_words = set(re.findall(r'\w+', prompt_lower))

        scored_sections = []
        for section in parsed.sections:
            if section.is_preamble:
                # Always include preamble (imports, headers)
                scored_sections.append((section, 1.0))
                continue

            # Calculate relevance score
            score = self._score_section_relevance(section, prompt_words, prompt_lower)
            scored_sections.append((section, score))

        # Sort by relevance, include all sections but truncate low-relevance ones
        scored_sections.sort(key=lambda x: x[1], reverse=True)

        for section, score in scored_sections:
            if section.is_preamble:
                # Include preamble but limit lines
                content = section.content
                content_lines = content.splitlines()
                if len(content_lines) > 30:
                    content = "\n".join(content_lines[:30]) + f"\n... ({len(content_lines)} lines total, truncated)"
                parts.append(f"\n--- Section: {section.name} (preamble) ---\n{content}")
                continue

            content_lines = section.content.splitlines()
            section_line_count = len(content_lines)

            if score >= 0.3:
                # High relevance: send full section (capped at MAX_SECTION_LINES)
                if section_line_count > MAX_SECTION_LINES:
                    head = "\n".join(content_lines[:MAX_SECTION_LINES // 2])
                    tail = "\n".join(content_lines[-(MAX_SECTION_LINES // 2):])
                    content = f"{head}\n... (truncated, {section_line_count} lines) ...\n{tail}"
                else:
                    content = section.content
                parts.append(
                    f"\n--- Section: {section.name} "
                    f"(lines {section.start_line}-{section.end_line}, "
                    f"{section_line_count} lines, relevance: {score:.1f}) ---\n{content}"
                )
            elif score >= 0.1:
                # Medium relevance: send first N lines + summary
                preview_lines = min(30, section_line_count)
                preview = "\n".join(content_lines[:preview_lines])
                parts.append(
                    f"\n--- Section: {section.name} "
                    f"({section_line_count} lines, relevance: {score:.1f}, "
                    f"showing first {preview_lines} lines) ---\n{preview}"
                )
            else:
                # Low relevance: send summary only
                parts.append(
                    f"\n--- Section: {section.name} "
                    f"({section_line_count} lines, low relevance) ---"
                    f"\n[{section.name}: {section_line_count} lines, "
                    f"not shown - use @{file_path}:{section.start_line} to target]"
                )

        return "\n".join(parts)

    def _build_split_context(
        self,
        content: str,
        user_prompt: str,
        file_path: str,
    ) -> str:
        """Build context for a large file without section markers.

        Splits by logical blocks (blank line separated) and scores relevance.
        """
        lines = content.splitlines()
        total_lines = len(lines)

        prompt_words = set(re.findall(r'\w+', user_prompt.lower()))

        # Split into blocks by blank lines
        blocks = []
        current_block = []
        block_start = 1  # 1-based line number

        for i, line in enumerate(lines):
            if line.strip() == "" and current_block:
                blocks.append({
                    "content": "\n".join(current_block),
                    "start": block_start,
                    "end": block_start + len(current_block) - 1,
                    "line_count": len(current_block),
                })
                current_block = []
                block_start = i + 2  # next line (1-based)
            else:
                current_block.append(line)

        if current_block:
            blocks.append({
                "content": "\n".join(current_block),
                "start": block_start,
                "end": block_start + len(current_block) - 1,
                "line_count": len(current_block),
            })

        # Score each block
        for block in blocks:
            block_lower = block["content"].lower()
            block_words = set(re.findall(r'\w+', block_lower))
            if prompt_words and block_words:
                overlap = len(prompt_words & block_words)
                block["relevance"] = overlap / max(len(prompt_words), 1)
            else:
                block["relevance"] = 0.0

        # Sort by relevance
        blocks.sort(key=lambda b: b["relevance"], reverse=True)

        # Build output
        parts = [f"[{file_path}] ({total_lines} lines, {len(blocks)} blocks)"]

        included_lines = 0
        max_total = max_lines = 200  # Total lines budget for this file

        for block in blocks:
            if included_lines >= max_total:
                break

            remaining = max_total - included_lines
            block_lines = block["line_count"]

            if block["relevance"] >= 0.2 or block == blocks[0]:
                # Include block
                if block_lines <= remaining:
                    content = block["content"]
                    included_lines += block_lines
                else:
                    content = "\n".join(block["content"].splitlines()[:remaining])
                    included_lines = max_total

                parts.append(
                    f"\n--- Lines {block['start']}-{block['end']} "
                    f"(relevance: {block['relevance']:.1f}) ---\n{content}"
                )
            else:
                parts.append(
                    f"\n--- Lines {block['start']}-{block['end']} "
                    f"(low relevance, {block_lines} lines) ---"
                    f"\n[Not shown - use @{file_path}:{block['start']} to target]"
                )

        return "\n".join(parts)

    def _score_section_relevance(
        self,
        section: FileSection,
        prompt_words: set[str],
        prompt_lower: str,
    ) -> float:
        """Score how relevant a section is to the user's prompt.

        Returns 0.0 to 1.0.
        """
        if not prompt_words:
            return 0.5  # No prompt context, treat all as medium relevance

        # Check section name match
        name_lower = section.name.lower()
        name_words = set(re.findall(r'\w+', name_lower))
        name_overlap = len(prompt_words & name_words)

        # Check content match
        content_lower = section.content.lower()
        content_words = set(re.findall(r'\w+', content_lower))
        # Sample first 500 chars for quick matching
        content_sample = content_lower[:500]
        content_overlap = sum(1 for w in prompt_words if w in content_sample)

        # Weighted score
        name_score = min(name_overlap / max(len(prompt_words), 1), 1.0) * 0.4
        content_score = min(content_overlap / max(len(prompt_words), 1), 1.0) * 0.6

        return name_score + content_score

    def get_section_summary(self, file_path: str) -> str:
        """Get a brief summary of all sections in a file.

        Useful for giving AI an overview without sending full content.
        """
        full_path = self.project_root / file_path
        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
        except (FileNotFoundError, OSError):
            return f"[{file_path}] (file not found)"

        parsed = self.parser.parse(file_path, content)

        if not parsed.has_markers:
            lines = content.splitlines()
            return f"[{file_path}] ({len(lines)} lines, no section markers)"

        total_lines = len(content.splitlines())
        section_names = parsed.get_section_names()

        lines = [f"[{file_path}] ({total_lines} lines, {len(section_names)} sections):"]
        for section in parsed.sections:
            if not section.is_preamble:
                lines.append(
                    f"  - {section.name} (lines {section.start_line}-{section.end_line}, "
                    f"{section.end_line - section.start_line + 1} lines)"
                )

        return "\n".join(lines)

    def format_for_ai(
        self,
        file_path: str,
        section_name: str | None = None,
        user_prompt: str = "",
        full_content: str | None = None,
    ) -> str:
        """Format file content for sending to AI.

        If section_name is specified, only that section is sent.
        Otherwise, uses smart context splitting.
        """
        if full_content is None:
            full_path = self.project_root / file_path
            try:
                full_content = full_path.read_text(encoding="utf-8", errors="replace")
            except (FileNotFoundError, OSError):
                return f"[{file_path}] (file not found)"

        if section_name:
            parsed = self.parser.parse(file_path, full_content)
            section = parsed.get_section(section_name)
            if section:
                return (
                    f"[{file_path}] Section: {section_name} "
                    f"(lines {section.start_line}-{section.end_line})\n"
                    f"{section.content}"
                )
            else:
                return f"[{file_path}] Section '{section_name}' not found"

        return self.build_file_context(file_path, user_prompt, full_content=full_content)