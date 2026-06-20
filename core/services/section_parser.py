"""Section Parser – parses files into named sections using comment markers.

Supports multiple languages:
  - HTML:  <!-- SECTION: name --> ... <!-- END SECTION: name -->
  - Python/JS/CSS:  # SECTION: name ... # END SECTION: name
  - Generic: /* SECTION: name */ ... /* END SECTION: name */

When a file has no section markers, the entire file is treated as one section.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# Patterns for section markers (language-agnostic approach)
_SECTION_PATTERNS = [
    # HTML comments: <!-- SECTION: name --> and <!-- END SECTION: name -->
    (
        re.compile(r'<!--\s*SECTION:\s*(\S+)\s*-->', re.IGNORECASE),
        re.compile(r'<!--\s*END\s+SECTION:\s*(\S+)\s*-->', re.IGNORECASE),
    ),
    # Hash comments: # SECTION: name and # END SECTION: name
    (
        re.compile(r'#\s*SECTION:\s*(\S+)', re.IGNORECASE),
        re.compile(r'#\s*END\s+SECTION:\s*(\S+)', re.IGNORECASE),
    ),
    # C-style comments: /* SECTION: name */ and /* END SECTION: name */
    (
        re.compile(r'/\*\s*SECTION:\s*(\S+)\s*\*/', re.IGNORECASE),
        re.compile(r'/\*\s*END\s+SECTION:\s*(\S+)\s*\*/', re.IGNORECASE),
    ),
    # Double-slash comments: // SECTION: name and // END SECTION: name
    (
        re.compile(r'//\s*SECTION:\s*(\S+)', re.IGNORECASE),
        re.compile(r'//\s*END\s+SECTION:\s*(\S+)', re.IGNORECASE),
    ),
]


@dataclass
class FileSection:
    """A named section within a file."""
    name: str
    content: str
    start_line: int  # 1-based line number where section content starts
    end_line: int    # 1-based line number where section content ends
    start_marker: str = ""  # The full start marker line
    end_marker: str = ""    # The full end marker line
    is_preamble: bool = False  # True for content before first section marker


@dataclass
class ParsedFile:
    """A file parsed into sections."""
    file_path: str
    raw_content: str
    sections: list[FileSection] = field(default_factory=list)
    has_markers: bool = False  # True if file actually has section markers

    def get_section(self, name: str) -> Optional[FileSection]:
        """Get a section by name (case-insensitive)."""
        name_lower = name.lower()
        for s in self.sections:
            if s.name.lower() == name_lower:
                return s
        return None

    def get_section_names(self) -> list[str]:
        """Return list of all section names in order."""
        return [s.name for s in self.sections if not s.is_preamble]

    def replace_section(self, name: str, new_content: str) -> Optional[str]:
        """Replace a section's content and return the full file content.

        If the section is not found, returns None.
        Preserves the start and end markers.
        """
        section = self.get_section(name)
        if section is None:
            return None

        lines = self.raw_content.splitlines(keepends=True)

        # Calculate line ranges (0-based indexing)
        # Section content is between start_marker and end_marker
        start_idx = section.start_line - 1  # line after start marker
        end_idx = section.end_line - 1       # line before end marker

        # Build new content lines
        new_lines = new_content.splitlines(keepends=True)
        if not new_lines or not new_lines[-1].endswith('\n'):
            pass  # keep as-is

        # Replace: keep everything before section content, insert new, keep after
        result_lines = lines[:start_idx] + new_lines + lines[end_idx:]
        return ''.join(result_lines)

    def rebuild_with_section(self, name: str, new_content: str) -> Optional[str]:
        """Replace section content, preserving markers and surrounding code.

        This is the primary API for anchor patching.
        Returns the full rebuilt file content, or None if section not found.

        Internal layout:
          start_line = 1-based line index of the start marker
          end_line   = 0-based exclusive end index (the end marker or EOF line)
        """
        section = self.get_section(name)
        if section is None:
            return None

        lines = self.raw_content.splitlines(keepends=True)
        # start_line is 1-based → convert to 0-based index of start marker
        start_idx = section.start_line - 1  # 0-based index of start marker line
        # end_line is already 0-based exclusive end index
        end_idx = section.end_line  # 0-based index of end marker line (or len(lines) for EOF)

        # Build result:
        # 1. Keep everything up to and including start marker
        before = lines[:start_idx + 1]
        # 2. Insert new content
        new_lines = new_content.splitlines(keepends=True)
        # 3. Keep everything from end marker onwards
        after = lines[end_idx:]

        return ''.join(before + new_lines + after)


class SectionParser:
    """Parses files into named sections using comment markers."""

    def __init__(self):
        pass

    def parse(self, file_path: str, content: str | None = None) -> ParsedFile:
        """Parse a file's content into sections.

        Args:
            file_path: Path to the file (used for extension detection).
            content: File content. If None, reads from disk.

        Returns:
            ParsedFile with sections extracted.
        """
        if content is None:
            try:
                content = Path(file_path).read_text(encoding="utf-8", errors="replace")
            except (FileNotFoundError, OSError):
                return ParsedFile(file_path=file_path, raw_content="", sections=[])

        lines = content.splitlines(keepends=True)
        sections = []
        has_markers = False

        # Try each pattern set
        for start_pat, end_pat in _SECTION_PATTERNS:
            start_matches = []
            end_matches = []

            for i, line in enumerate(lines):
                sm = start_pat.search(line)
                if sm:
                    start_matches.append((i, sm.group(1), line.strip()))
                em = end_pat.search(line)
                if em:
                    end_matches.append((i, em.group(1), line.strip()))

            if start_matches:
                has_markers = True

                # Add preamble if there's content before first section
                if start_matches and start_matches[0][0] > 0:
                    preamble_content = ''.join(lines[:start_matches[0][0]])
                    if preamble_content.strip():
                        sections.append(FileSection(
                            name="__preamble__",
                            content=preamble_content,
                            start_line=1,
                            end_line=start_matches[0][0],
                            is_preamble=True,
                        ))

                # Match start/end markers
                for idx, (start_i, sec_name, start_line_text) in enumerate(start_matches):
                    # Find matching end marker
                    end_i = None
                    end_line_text = ""
                    for ei, ename, eltext in end_matches:
                        if ei > start_i and ename.lower() == sec_name.lower():
                            end_i = ei
                            end_line_text = eltext
                            break

                    if end_i is None:
                        # Unclosed section - treat as extending to end of file
                        end_i = len(lines)  # exclusive end index (past last line)
                        end_line_text = ""

                    # Content is between start marker (exclusive) and end marker (exclusive)
                    sec_content = ''.join(lines[start_i + 1:end_i])
                    sections.append(FileSection(
                        name=sec_name,
                        content=sec_content,
                        start_line=start_i + 1,  # 1-based line of start marker
                        end_line=end_i,          # 0-based exclusive end (lines[end_i] is end marker or EOF)
                        start_marker=start_line_text,
                        end_marker=end_line_text,
                    ))

                break  # Use first matching pattern set

        if not has_markers:
            # No markers found - entire file is one section
            sections.append(FileSection(
                name="__full__",
                content=content,
                start_line=1,
                end_line=len(lines),
                is_preamble=False,
            ))

        return ParsedFile(
            file_path=file_path,
            raw_content=content,
            sections=sections,
            has_markers=has_markers,
        )

    def inject_section_markers(self, content: str, section_name: str, language: str = "html") -> str:
        """Add section markers around the entire content (for first-time setup).

        Args:
            content: The file content to wrap.
            section_name: Name for the section.
            language: Language hint for comment style.

        Returns:
            Content with section markers injected.
        """
        if language in ("html", "htm"):
            start = f"<!-- SECTION: {section_name} -->"
            end = f"<!-- END SECTION: {section_name} -->"
        elif language in ("py",):
            start = f"# SECTION: {section_name}"
            end = f"# END SECTION: {section_name}"
        elif language in ("js", "ts", "jsx", "tsx", "css", "scss", "java", "c", "cpp"):
            start = f"/* SECTION: {section_name} */"
            end = f"/* END SECTION: {section_name} */"
        else:
            start = f"<!-- SECTION: {section_name} -->"
            end = f"<!-- END SECTION: {section_name} -->"

        return f"{start}\n{content}\n{end}\n"

    def suggest_sections(self, file_path: str, content: str) -> list[str]:
        """Analyze a file and suggest logical section names.

        For HTML: looks for common section patterns (hero, nav, footer, etc.)
        For Python: looks for class/function definitions.
        """
        ext = Path(file_path).suffix.lower()
        suggestions = []

        if ext in (".html", ".htm"):
            # Look for HTML comment sections
            comment_sections = re.findall(r'<!--\s*(?:SECTION\s*:)?\s*(\w[\w\s]*)\s*-->', content, re.IGNORECASE)
            suggestions.extend(comment_sections)

            # Look for common HTML patterns
            if re.search(r'<nav[\s>]', content, re.IGNORECASE):
                suggestions.append("NAVBAR")
            if re.search(r'class=["\'].*hero', content, re.IGNORECASE):
                suggestions.append("HERO")
            if re.search(r'<footer[\s>]', content, re.IGNORECASE):
                suggestions.append("FOOTER")
            if re.search(r'<header[\s>]', content, re.IGNORECASE):
                suggestions.append("HEADER")
            if re.search(r'<main[\s>]', content, re.IGNORECASE):
                suggestions.append("MAIN")

        elif ext == ".py":
            # Look for class definitions
            classes = re.findall(r'^class\s+(\w+)', content, re.MULTILINE)
            for cls in classes:
                suggestions.append(cls)
            # Look for if __name__ == "__main__" block
            if re.search(r'if\s+__name__\s*==\s*["\']__main__["\']', content):
                suggestions.append("main")

        return suggestions

    def auto_section_content(self, content: str, file_path: str,
                             min_lines: int = 200, min_chars: int = 15000) -> list[dict]:
        """Auto-split large content into named sections with markers.

        Returns list of dicts: [{"name": ..., "content": ..., "start_marker": ..., "end_marker": ...}]
        Returns empty list if content is under threshold (no splitting needed).
        """
        lines = content.splitlines()
        if len(lines) < min_lines and len(content) < min_chars:
            return []

        ext = Path(file_path).suffix.lower()
        lang_hint = self._ext_to_lang(ext)
        sections = []

        if ext in (".html", ".htm"):
            sections = self._sectionize_html(content, lines)
        elif ext == ".py":
            sections = self._sectionize_python(content, lines)
        elif ext in (".css", ".scss", ".less"):
            sections = self._sectionize_css(content, lines)
        elif ext in (".js", ".ts", ".jsx", ".tsx"):
            sections = self._sectionize_js(content, lines)

        # Fallback: no sections detected → split by line count
        if not sections:
            sections = self._sectionize_by_size(content, lines)

        # Fix markers to match language
        for sec in sections:
            sec["start_marker"] = self._marker_line(sec["name"], "start", lang_hint)
            sec["end_marker"] = self._marker_line(sec["name"], "end", lang_hint)

        return sections

    @staticmethod
    def _ext_to_lang(ext: str) -> str:
        ext = ext.lower()
        if ext in (".html", ".htm"):
            return "html"
        if ext == ".py":
            return "py"
        if ext in (".js", ".ts", ".jsx", ".tsx", ".css", ".scss", ".less", ".java", ".c", ".cpp"):
            return "cstyle"
        return "html"

    @staticmethod
    def _marker_line(name: str, kind: str, lang: str) -> str:
        """Generate a section marker line for the given language."""
        if lang == "html":
            return f"<!-- {kind.upper()} SECTION: {name} -->"
        elif lang == "py":
            return f"# {kind.upper()} SECTION: {name}"
        elif lang == "cstyle":
            return f"/* {kind.upper()} SECTION: {name} */"
        return f"<!-- {kind.upper()} SECTION: {name} -->"

    MAX_SECTIONS = 12

    def _sectionize_html(self, content: str, lines: list[str]) -> list[dict]:
        """Split HTML into sections at major structural tags only."""
        sections = []
        current_name = "HEADER"
        current_lines = []
        section_idx = 0

        # Only split at top-level structural tags, not every <section>
        tag_split = re.compile(
            r'<(header|nav|main|footer|article|aside)'
            r'[^>]*(?:class\s*=\s*["\']([^"\']+)["\'])?',
            re.IGNORECASE
        )

        for line in lines:
            sm = tag_split.search(line)
            if sm:
                if current_lines and section_idx < self.MAX_SECTIONS:
                    sections.append(self._make_section(current_name, current_lines, section_idx))
                    section_idx += 1
                tag = sm.group(1).upper()
                cls = sm.group(2)
                current_name = f"{tag}_{cls}" if cls else tag
                current_lines = [line]
            elif current_lines:
                current_lines.append(line)

        if current_lines:
            sections.append(self._make_section(current_name, current_lines, section_idx))

        return sections

    def _sectionize_python(self, content: str, lines: list[str]) -> list[dict]:
        """Split Python into sections at top-level class/function definitions."""
        sections = []
        current_name = "__file_header__"
        current_lines = []

        for line in lines:
            tm = re.match(r'^(class\s+\w+|def\s+\w+)\s*[\(:]', line)
            if tm:
                if current_lines:
                    sections.append(self._make_section(current_name, current_lines))
                name = tm.group(1).replace(" ", "_").upper()
                current_name = name
                current_lines = [line]
            else:
                current_lines.append(line)

        if current_lines:
            sections.append(self._make_section(current_name, current_lines))

        return sections

    def _sectionize_css(self, content: str, lines: list[str]) -> list[dict]:
        """Split CSS into sections at comment blocks or major rulesets."""
        sections = []
        current_name = "STYLES"
        current_lines = []

        for line in lines:
            cm = re.match(r'/\*\s*(.+?)\s*\*/', line)
            if cm:
                if current_name and current_lines:
                    sections.append(self._make_section(current_name, current_lines))
                current_name = cm.group(1).strip().replace(" ", "_").upper()[:30]
                current_lines = []
            else:
                current_lines.append(line)

        if current_lines:
            sections.append(self._make_section(current_name, current_lines))

        return sections

    def _sectionize_js(self, content: str, lines: list[str]) -> list[dict]:
        """Split JS/TS into sections at top-level function/class/export."""
        sections = []
        current_name = "__file_header__"
        current_lines = []

        for line in lines:
            tm = re.match(
                r'^(export\s+)?(function\s+\w+|class\s+\w+|const\s+\w+|let\s+\w+|var\s+\w+)\s*',
                line
            )
            if tm:
                if current_lines:
                    sections.append(self._make_section(current_name, current_lines))
                name = tm.group(0).strip().replace(" ", "_").upper()[:30]
                current_name = name
                current_lines = [line]
            else:
                current_lines.append(line)

        if current_lines:
            sections.append(self._make_section(current_name, current_lines))

        return sections

    def _sectionize_by_size(self, content: str, lines: list[str]) -> list[dict]:
        """Fallback: split by line count when no semantic sections found."""
        sections = []
        chunk_size = max(1, len(lines) // 5)  # target ~5 sections
        for i in range(0, len(lines), chunk_size):
            chunk = lines[i:i + chunk_size]
            name = f"SECTION_{i // chunk_size + 1}"
            sections.append(self._make_section(name, chunk))
        return sections

    def _make_section(self, name: str, lines: list[str], idx: int = 0) -> dict:
        """Build a section dict from lines (markers added later by language)."""
        content = "".join(lines)
        clean_name = re.sub(r'[^A-Za-z0-9_]', '_', name).upper().strip('_')
        if not clean_name:
            clean_name = f"SECTION_{idx}"
        return {
            "name": clean_name,
            "content": content,
        }

    def build_skeleton(self, sections: list[dict]) -> str:
        """Build a skeleton file with only section markers."""
        parts = []
        for sec in sections:
            parts.append(sec["start_marker"])
            parts.append(sec["end_marker"])
        return "\n".join(parts) + "\n"