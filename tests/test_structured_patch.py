"""Tests for the Structured Patch Architecture.

Covers:
- Section Parser (parse, replace, inject markers)
- Anchor Patcher (replace_between, find_anchors)
- Enhanced Structural Validator (broken attrs, truncated tags, section markers)
- Smart Context (context splitting, relevance scoring)
- Patch Service anchor_patch parsing
"""
import os
import tempfile
import textwrap

import pytest

from core.services.section_parser import SectionParser, ParsedFile, FileSection
from core.services.anchor_patcher import AnchorPatcher
from core.services.structural_validator import StructuralValidator
from core.services.smart_context import SmartContext
from core.services.patch_service import PatchService
from core.models import PatchResult


# ═══════════════════════════════════════════════════════════════════════════════
# Section Parser Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestSectionParser:
    """Test SectionParser parsing, replacement, and marker injection."""

    def setup_method(self):
        self.parser = SectionParser()

    def test_parse_no_markers_returns_full_section(self):
        """File without section markers should be treated as one section."""
        content = "<html><body>Hello</body></html>"
        parsed = self.parser.parse("index.html", content)

        assert not parsed.has_markers
        assert len(parsed.sections) == 1
        assert parsed.sections[0].name == "__full__"
        assert parsed.sections[0].content == content

    def test_parse_html_section_markers(self):
        """Parse HTML section markers correctly."""
        content = textwrap.dedent("""\
            <!DOCTYPE html>
            <html>
            <!-- SECTION: NAVBAR -->
            <nav>Menu</nav>
            <!-- END SECTION: NAVBAR -->
            <!-- SECTION: HERO -->
            <div class="hero">Hero content</div>
            <!-- END SECTION: HERO -->
            </html>
        """)
        parsed = self.parser.parse("index.html", content)

        assert parsed.has_markers
        # 3 sections: preamble + NAVBAR + HERO
        assert len(parsed.sections) == 3
        navbar = parsed.get_section("NAVBAR")
        assert navbar is not None
        assert "<nav>Menu</nav>" in navbar.content
        hero = parsed.get_section("HERO")
        assert hero is not None
        assert "Hero content" in hero.content

    def test_parse_python_hash_markers(self):
        """Parse Python-style hash section markers."""
        content = textwrap.dedent("""\
            # SECTION: imports
            import os
            import sys
            # END SECTION: imports

            # SECTION: main
            def main():
                pass
            # END SECTION: main
        """)
        parsed = self.parser.parse("app.py", content)

        assert parsed.has_markers
        assert len(parsed.sections) == 2
        assert parsed.sections[0].name == "imports"
        assert "import os" in parsed.sections[0].content
        assert parsed.sections[1].name == "main"
        assert "def main():" in parsed.sections[1].content

    def test_get_section_case_insensitive(self):
        """Section lookup should be case-insensitive."""
        content = textwrap.dedent("""\
            <!-- SECTION: Hero -->
            <div>Hero</div>
            <!-- END SECTION: Hero -->
        """)
        parsed = self.parser.parse("index.html", content)
        assert parsed.get_section("hero") is not None
        assert parsed.get_section("HERO") is not None
        assert parsed.get_section("Hero") is not None

    def test_get_section_names(self):
        """Get section names should return non-preamble names in order."""
        content = textwrap.dedent("""\
            <!DOCTYPE html>
            <!-- SECTION: NAV -->
            <nav>Menu</nav>
            <!-- END SECTION: NAV -->
            <!-- SECTION: FOOTER -->
            <footer>Footer</footer>
            <!-- END SECTION: FOOTER -->
        """)
        parsed = self.parser.parse("index.html", content)
        names = parsed.get_section_names()
        assert names == ["NAV", "FOOTER"]

    def test_rebuild_with_section(self):
        """Rebuild file with replaced section content."""
        content = textwrap.dedent("""\
            <!DOCTYPE html>
            <!-- SECTION: CTA -->
            <div>Old CTA</div>
            <!-- END SECTION: CTA -->
            <footer>Footer</footer>
        """)
        parsed = self.parser.parse("index.html", content)
        result = parsed.rebuild_with_section("CTA", "<div>New CTA</div>\n")

        assert result is not None
        assert "<div>New CTA</div>" in result
        assert "Old CTA" not in result
        assert "<footer>Footer</footer>" in result
        assert "<!-- SECTION: CTA -->" in result
        assert "<!-- END SECTION: CTA -->" in result

    def test_rebuild_preserves_surrounding_code(self):
        """Rebuilding should preserve all code outside the target section."""
        content = textwrap.dedent("""\
            line1
            <!-- SECTION: A -->
            old_a
            <!-- END SECTION: A -->
            line2
            <!-- SECTION: B -->
            old_b
            <!-- END SECTION: B -->
            line3
        """)
        parsed = self.parser.parse("test.txt", content)
        result = parsed.rebuild_with_section("A", "new_a\n")

        assert "line1" in result
        assert "new_a" in result
        assert "old_a" not in result
        assert "line2" in result
        assert "old_b" in result
        assert "line3" in result

    def test_inject_section_markers_html(self):
        """Inject HTML section markers."""
        content = "<div>Hello</div>"
        result = self.parser.inject_section_markers(content, "MAIN", "html")
        assert "<!-- SECTION: MAIN -->" in result
        assert "<!-- END SECTION: MAIN -->" in result
        assert "<div>Hello</div>" in result

    def test_inject_section_markers_python(self):
        """Inject Python section markers."""
        content = "x = 1"
        result = self.parser.inject_section_markers(content, "CONSTANTS", "py")
        assert "# SECTION: CONSTANTS" in result
        assert "# END SECTION: CONSTANTS" in result

    def test_unclosed_section_extends_to_eof(self):
        """Unclosed section should extend to end of file."""
        content = textwrap.dedent("""\
            <!-- SECTION: OPEN -->
            line1
            line2
        """)
        parsed = self.parser.parse("test.html", content)
        assert parsed.has_markers
        assert len(parsed.sections) == 1
        assert "line1" in parsed.sections[0].content
        assert "line2" in parsed.sections[0].content

    def test_preamble_before_first_section(self):
        """Content before first section marker should be a preamble."""
        content = textwrap.dedent("""\
            <!DOCTYPE html>
            <html>
            <!-- SECTION: BODY -->
            <body>Hello</body>
            <!-- END SECTION: BODY -->
        """)
        parsed = self.parser.parse("index.html", content)
        assert parsed.has_markers
        # Should have preamble + body section
        preamble = [s for s in parsed.sections if s.is_preamble]
        assert len(preamble) == 1
        assert "DOCTYPE" in preamble[0].content


# ═══════════════════════════════════════════════════════════════════════════════
# Anchor Patcher Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestAnchorPatcher:
    """Test AnchorPatcher replace_between and find_anchors."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def _make_file(self, name, content):
        path = os.path.join(self.tmpdir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return name

    def test_replace_between_basic(self):
        """Basic anchor patch: replace content between two markers."""
        content = textwrap.dedent("""\
            line1
            <!-- START -->
            old content
            <!-- END -->
            line3
        """)
        path = self._make_file("test.html", content)
        patcher = AnchorPatcher(self.tmpdir)

        result = patcher.replace_between(path, "<!-- START -->", "<!-- END -->", "new content\n")

        assert result.success
        patched = open(os.path.join(self.tmpdir, path), encoding="utf-8").read()
        assert "new content" in patched
        assert "old content" not in patched
        assert "line1" in patched
        assert "line3" in patched
        assert "<!-- START -->" in patched
        assert "<!-- END -->" in patched

    def test_replace_between_preserves_anchors(self):
        """Anchor markers should be preserved in the output."""
        content = '<!-- CTA_START -->\n<p>Old</p>\n<!-- CTA_END -->\n'
        path = self._make_file("cta.html", content)
        patcher = AnchorPatcher(self.tmpdir)

        result = patcher.replace_between(path, "<!-- CTA_START -->", "<!-- CTA_END -->", "<p>New</p>\n")

        assert result.success
        patched = open(os.path.join(self.tmpdir, path), encoding="utf-8").read()
        assert "<!-- CTA_START -->" in patched
        assert "<!-- CTA_END -->" in patched
        assert "<p>New</p>" in patched
        assert "<p>Old</p>" not in patched

    def test_replace_between_file_not_found(self):
        """Should fail gracefully when file doesn't exist."""
        patcher = AnchorPatcher(self.tmpdir)
        result = patcher.replace_between("nonexistent.html", "<!-- S -->", "<!-- E -->", "x")
        assert not result.success
        assert "not found" in result.message

    def test_replace_between_anchor_not_found(self):
        """Should fail when anchors don't exist in file."""
        content = "line1\nline2\n"
        path = self._make_file("test.html", content)
        patcher = AnchorPatcher(self.tmpdir)

        result = patcher.replace_between(path, "<!-- MISSING_START -->", "<!-- MISSING_END -->", "x")
        assert not result.success
        assert "Anchor not found" in result.message

    def test_replace_between_multiple_sections(self):
        """Should only replace content between the specified anchors."""
        content = textwrap.dedent("""\
            <!-- SECTION: A -->
            content A
            <!-- END SECTION: A -->
            <!-- SECTION: B -->
            content B
            <!-- END SECTION: B -->
        """)
        path = self._make_file("multi.html", content)
        patcher = AnchorPatcher(self.tmpdir)

        result = patcher.replace_between(
            path,
            "<!-- SECTION: B -->",
            "<!-- END SECTION: B -->",
            "new B content\n"
        )

        assert result.success
        patched = open(os.path.join(self.tmpdir, path), encoding="utf-8").read()
        assert "content A" in patched  # Section A untouched
        assert "new B content" in patched
        assert "content B" not in patched

    def test_find_anchors(self):
        """Find all anchor pairs in a file."""
        content = textwrap.dedent("""\
            <!-- SECTION: HERO -->
            <div>Hero</div>
            <!-- END SECTION: HERO -->
            <!-- SECTION: FOOTER -->
            <footer>Footer</footer>
            <!-- END SECTION: FOOTER -->
        """)
        path = self._make_file("index.html", content)
        patcher = AnchorPatcher(self.tmpdir)

        anchors = patcher.find_anchors(path)
        assert len(anchors) == 2
        assert anchors[0]["name"] == "HERO"
        assert anchors[1]["name"] == "FOOTER"

    def test_validate_anchor_exists(self):
        """Validate that anchors exist in file."""
        content = "<!-- START -->\nhello\n<!-- END -->\n"
        path = self._make_file("test.html", content)
        patcher = AnchorPatcher(self.tmpdir)

        exists, msg = patcher.validate_anchor_exists(path, "<!-- START -->", "<!-- END -->")
        assert exists
        assert "found" in msg.lower()

        exists, msg = patcher.validate_anchor_exists(path, "<!-- MISSING -->", "<!-- END -->")
        assert not exists

    def test_replace_between_end_to_end(self):
        """Replace with content that has multiple lines."""
        content = textwrap.dedent("""\
            header
            <!-- SECTION: BODY -->
            old line 1
            old line 2
            old line 3
            <!-- END SECTION: BODY -->
            footer
        """)
        path = self._make_file("page.html", content)
        patcher = AnchorPatcher(self.tmpdir)

        new_content = "new line 1\nnew line 2\n"
        result = patcher.replace_between(
            path, "<!-- SECTION: BODY -->", "<!-- END SECTION: BODY -->", new_content
        )

        assert result.success
        patched = open(os.path.join(self.tmpdir, path), encoding="utf-8").read()
        assert "new line 1" in patched
        assert "new line 2" in patched
        assert "old line 1" not in patched
        assert "header" in patched
        assert "footer" in patched


# ═══════════════════════════════════════════════════════════════════════════════
# Enhanced Structural Validator Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestEnhancedStructuralValidator:
    """Test the new P5 validation checks."""

    def setup_method(self):
        self.sv = StructuralValidator()

    def test_broken_attribute_detection(self):
        """Detect unclosed quotes in HTML attributes."""
        bad = '<div class="broken\n<p>text</p>'
        errors = self.sv.validate("index.html", None, bad)
        assert any("Broken attribute" in e for e in errors)

    def test_truncated_tag_detection(self):
        """Detect tags ending with '...' (truncation)."""
        bad = '<div class="hero-glow bg-purple...\n'
        errors = self.sv.validate("index.html", None, bad)
        assert any("Truncated tag" in e for e in errors)

    def test_unclosed_final_tag(self):
        """Detect file ending with unclosed HTML tag."""
        bad = '<div class="content"\n'
        errors = self.sv.validate("index.html", None, bad)
        assert any("unclosed HTML tag" in e for e in errors)

    def test_section_marker_removal(self):
        """Detect when section markers are removed."""
        old = textwrap.dedent("""\
            <!-- SECTION: HERO -->
            <div>Hero</div>
            <!-- END SECTION: HERO -->
            <!-- SECTION: CTA -->
            <div>CTA</div>
            <!-- END SECTION: CTA -->
        """)
        new = '<div>Hero</div>\n<div>CTA</div>\n'
        errors = self.sv.validate("index.html", old, new)
        assert any("Section marker" in e for e in errors)

    def test_section_marker_preservation_no_error(self):
        """No error when section markers are preserved."""
        old = textwrap.dedent("""\
            <!-- SECTION: HERO -->
            <div>Hero</div>
            <!-- END SECTION: HERO -->
        """)
        new = textwrap.dedent("""\
            <!-- SECTION: HERO -->
            <div>New Hero</div>
            <!-- END SECTION: HERO -->
        """)
        errors = self.sv.validate("index.html", old, new)
        # Should NOT have section marker errors (may have other warnings)
        assert not any("Section marker" in e for e in errors)

    def test_significant_line_reduction(self):
        """Detect when file is shortened significantly."""
        old = "\n".join(f"line {i}" for i in range(100))
        new = "\n".join(f"line {i}" for i in range(20))
        errors = self.sv.validate("index.html", old, new)
        assert any("shortened significantly" in e for e in errors)

    def test_existing_checks_still_work(self):
        """Verify existing HTML tag balance check still works."""
        bad = "<html><body><div></body></html>"
        errors = self.sv.validate("index.html", None, bad)
        assert any("div" in e and "Unbalanced" in e for e in errors)


# ═══════════════════════════════════════════════════════════════════════════════
# Smart Context Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestSmartContext:
    """Test SmartContext splitting and relevance scoring."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def _make_file(self, name, content):
        path = os.path.join(self.tmpdir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return name

    def test_short_file_sends_everything(self):
        """Files under threshold should be sent in full."""
        content = "line1\nline2\nline3\n"
        path = self._make_file("small.txt", content)
        sc = SmartContext(self.tmpdir)

        result = sc.build_file_context(path, "test", max_lines=100)
        assert "line1" in result
        assert "line2" in result
        assert "line3" in result

    def test_large_file_with_sections_splits(self):
        """Large file with section markers should be split."""
        sections = []
        for i in range(5):
            sections.append(f"<!-- SECTION: PART{i} -->\n")
            for j in range(30):
                sections.append(f"  part{i} line{j}\n")
            sections.append(f"<!-- END SECTION: PART{i} -->\n")
        content = "<!DOCTYPE html>\n" + "".join(sections)

        path = self._make_file("big.html", content)
        sc = SmartContext(self.tmpdir)

        result = sc.build_file_context(path, "PART2", max_lines=20)
        assert "PART" in result  # Should mention sections
        assert "big.html" in result

    def test_section_summary(self):
        """Section summary should list all sections."""
        content = textwrap.dedent("""\
            <!-- SECTION: A -->
            <div>A</div>
            <!-- END SECTION: A -->
            <!-- SECTION: B -->
            <div>B</div>
            <!-- END SECTION: B -->
        """)
        path = self._make_file("index.html", content)
        sc = SmartContext(self.tmpdir)

        summary = sc.get_section_summary(path)
        assert "A" in summary
        assert "B" in summary

    def test_format_for_ai_specific_section(self):
        """format_for_ai with section name returns only that section."""
        content = textwrap.dedent("""\
            <!-- SECTION: HERO -->
            <div class="hero">Hero</div>
            <!-- END SECTION: HERO -->
            <!-- SECTION: FOOTER -->
            <footer>Footer</footer>
            <!-- END SECTION: FOOTER -->
        """)
        path = self._make_file("index.html", content)
        sc = SmartContext(self.tmpdir)

        result = sc.format_for_ai(path, section_name="HERO")
        assert "Hero" in result
        assert "Footer" not in result

    def test_format_for_ai_missing_section(self):
        """format_for_ai with nonexistent section returns error message."""
        content = "<!-- SECTION: A -->\nx\n<!-- END SECTION: A -->\n"
        path = self._make_file("index.html", content)
        sc = SmartContext(self.tmpdir)

        result = sc.format_for_ai(path, section_name="NONEXISTENT")
        assert "not found" in result.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Patch Service Anchor Parsing Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestPatchServiceAnchorParsing:
    """Test that PatchService correctly parses ANCHOR_PATCH from AI responses."""

    def setup_method(self):
        self.ps = PatchService(".")

    def test_parse_anchor_patch(self):
        """Parse a well-formed ANCHOR_PATCH block."""
        resp = textwrap.dedent("""\
            <ANCHOR_PATCH path="index.html">
            <START><!-- SECTION: CTA --></START>
            <END><!-- END SECTION: CTA --></END>
            <CONTENT>
            <div class="cta">New CTA</div>
            </CONTENT>
            </ANCHOR_PATCH>
            <DONE/>
        """)
        calls = self.ps.parse_tool_calls(resp)
        anchor_calls = [c for c in calls if c["type"] == "anchor_patch"]
        assert len(anchor_calls) == 1
        assert anchor_calls[0]["path"] == "index.html"
        assert "SECTION: CTA" in anchor_calls[0]["start"]
        assert "END SECTION: CTA" in anchor_calls[0]["end"]
        assert "New CTA" in anchor_calls[0]["content"]

    def test_parse_anchor_patch_with_other_tools(self):
        """Parse ANCHOR_PATCH alongside other tool calls."""
        resp = textwrap.dedent("""\
            <ANCHOR_PATCH path="index.html">
            <START><!-- SECTION: NAV --></START>
            <END><!-- END SECTION: NAV --></END>
            <CONTENT><nav>New Nav</nav></CONTENT>
            </ANCHOR_PATCH>
            <RUN_COMMAND>
            echo done
            </RUN_COMMAND>
            <DONE/>
        """)
        calls = self.ps.parse_tool_calls(resp)
        types = [c["type"] for c in calls]
        assert "anchor_patch" in types
        assert "run_command" in types

    def test_parse_multiple_anchor_patches(self):
        """Parse multiple ANCHOR_PATCH blocks in one response."""
        resp = textwrap.dedent("""\
            <ANCHOR_PATCH path="index.html">
            <START><!-- SECTION: A --></START>
            <END><!-- END SECTION: A --></END>
            <CONTENT>New A</CONTENT>
            </ANCHOR_PATCH>
            <ANCHOR_PATCH path="style.css">
            <START>/* SECTION: COLORS */</START>
            <END>/* END SECTION: COLORS */</END>
            <CONTENT>body { color: red; }</CONTENT>
            </ANCHOR_PATCH>
            <DONE/>
        """)
        calls = self.ps.parse_tool_calls(resp)
        anchor_calls = [c for c in calls if c["type"] == "anchor_patch"]
        assert len(anchor_calls) == 2
        assert anchor_calls[0]["path"] == "index.html"
        assert anchor_calls[1]["path"] == "style.css"