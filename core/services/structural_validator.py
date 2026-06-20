"""Structural Validator – kiểm tra tính toàn vẹn cấu trúc file sau khi ghi."""
import ast
import re
import json
from pathlib import Path


class StructuralValidator:
    """Validates structural integrity of files after write operations.

    Dispatches to language-specific validators based on file extension.
    Each validator returns a list of warning/error strings (empty = all OK).

    Mode:
        FULL_DOCUMENT  — Kiểm tra DOCTYPE, html/head/body, tag balance (cho .html/.htm)
        FRAGMENT       — Chỉ check tag balance, bỏ qua structural tags (cho partial HTML, template)
    """

    # ── Extension mapping ───────────────────────────────────────────────
    _EXTENSION_MAP: dict[str, str] = {
        ".html": "_validate_html",
        ".htm": "_validate_html",
        ".py": "_validate_python",
        ".js": "_validate_js",
        ".jsx": "_validate_js",
        ".ts": "_validate_js",
        ".tsx": "_validate_js",
        ".mjs": "_validate_js",
        ".cjs": "_validate_js",
        ".css": "_validate_css",
        ".scss": "_validate_css",
        ".json": "_validate_json",
    }

    # Tags cần kiểm tra balance trong FULL_DOCUMENT mode
    _HTML_TAGS = (
        "html", "head", "body", "div", "section", "main", "header",
        "footer", "nav", "article", "aside", "table", "tr", "td", "th",
        "ul", "ol", "li", "form", "select",
    )
    # Tags chỉ check balance trong FRAGMENT mode (bỏ qua structural: html/head/body)
    _FRAGMENT_TAGS = (
        "div", "section", "main", "header", "footer", "nav", "article",
        "aside", "table", "tr", "td", "th", "ul", "ol", "li", "form", "select",
    )

    # Pattern trích xuất tên symbol trong JS/TS
    _JS_SYMBOL_RE = re.compile(
        r"(?:function|const|let|var|class|export\s+(?:default\s+)?"
        r"(?:function|class|const|let|var)?)\s+(\w+)"
    )

    # Pattern trích xuất selector CSS (top-level, trước dấu {)
    _CSS_SELECTOR_RE = re.compile(
        r"^\s*([^\s{@/][^{]*?)\s*\{", re.MULTILINE
    )

    # ── Public API ──────────────────────────────────────────────────────

    # ── Modes ──────────────────────────────────────────────────────────
    MODE_FULL = "full_document"
    MODE_FRAGMENT = "fragment"

    def validate(
        self,
        path: str,
        old_content: str | None,
        new_content: str,
        mode: str = "auto",
    ) -> list[str]:
        """Validate structural integrity of *new_content* written to *path*.

        Parameters
        ----------
        path:
            File path (used to determine file extension).
        old_content:
            Previous content of the file, or ``None`` for new files.
        new_content:
            Content that was just written.
        mode:
            ``"full_document"`` — full structural checks (DOCTYPE, html/head/body).
            ``"fragment"`` — chỉ check tag balance, bỏ qua structural tags.
            ``"auto"`` (default) — FULL_DOCUMENT cho .html/.htm, FRAGMENT cho mọi ext khác.

        Returns
        -------
        list[str]
            Warning/error messages. Empty list means everything is OK.
        """
        ext = Path(path).suffix.lower()
        if mode == "auto":
            mode = self.MODE_FULL if ext in (".html", ".htm") else self.MODE_FRAGMENT

        method_name = self._EXTENSION_MAP.get(ext)
        if method_name is None:
            return []

        method = getattr(self, method_name)

        # _validate_json chỉ nhận new_content
        if method_name == "_validate_json":
            return method(new_content)

        return method(old_content, new_content, mode=mode)

    # ── HTML ────────────────────────────────────────────────────────────

    def _validate_html(
        self, old: str | None, new: str, mode: str = "full_document"
    ) -> list[str]:
        """Validate HTML structural integrity.

        Parameters
        ----------
        mode:
            ``"full_document"`` — check DOCTYPE, html/head/body, tag balance (default).
            ``"fragment"`` — chỉ check tag balance cho non-structural tags (div/header/…),
                            bỏ qua DOCTYPE và html/head/body.
        """
        errors: list[str] = []
        is_full = mode == self.MODE_FULL

        # ── FULL_DOCUMENT checks ──
        if is_full:
            # DOCTYPE bị mất
            if old is not None:
                if re.search(r"<!DOCTYPE", old, re.IGNORECASE) and not re.search(
                    r"<!DOCTYPE", new, re.IGNORECASE
                ):
                    errors.append("DOCTYPE declaration was removed")

            # <script> section bị mất
            if old is not None:
                if re.search(r"<script[\s>]", old, re.IGNORECASE) and not re.search(
                    r"<script[\s>]", new, re.IGNORECASE
                ):
                    errors.append("<script> section was removed")

            # <style> section bị mất
            if old is not None:
                if re.search(r"<style[\s>]", old, re.IGNORECASE) and not re.search(
                    r"<style[\s>]", new, re.IGNORECASE
                ):
                    errors.append("<style> section was removed")

        # ── Tag balance (cho cả FULL và FRAGMENT) ──
        tags = self._HTML_TAGS if is_full else self._FRAGMENT_TAGS
        for tag in tags:
            open_count = len(
                re.findall(rf"<{tag}[\s>/]", new, re.IGNORECASE)
            )
            close_count = len(
                re.findall(rf"</{tag}\s*>", new, re.IGNORECASE)
            )
            if open_count != close_count:
                errors.append(
                    f"Unbalanced <{tag}>: {open_count} opening "
                    f"vs {close_count} closing"
                )

        # ── P5: Broken attribute detection ──
        # Check for unclosed quotes in HTML attributes: class="foo
        broken_attrs = re.findall(
            r'<\w+\s+[^>]*\w+=["\'][^"\'>]*$', new, re.MULTILINE
        )
        if broken_attrs:
            errors.append(
                f"Broken attribute string(s) detected ({len(broken_attrs)}): "
                "unclosed quote in HTML attribute (possible truncation)"
            )

        # ── P5: Incomplete/truncated tag detection ──
        # Check for tags that start but never close: <div class="...
        truncated_tags = re.findall(
            r'<\w+\s+[^>]*\.\.\.\s*$', new, re.MULTILINE
        )
        if truncated_tags:
            errors.append(
                f"Truncated tag(s) detected ({len(truncated_tags)}): "
                "tag ends with '...' (AI output likely cut off)"
            )

        # ── P5: Check for incomplete final tag ──
        # If the file ends with an unclosed tag (no >)
        stripped = new.rstrip()
        if stripped and stripped[-1] != '>' and re.search(r'<\w+\s*[^>]*$', stripped):
            errors.append(
                "File ends with unclosed HTML tag (possible truncation)"
            )

        # ── P5: Section marker completeness ──
        if old is not None:
            # Check if section markers in old are preserved in new
            old_sections = re.findall(
                r'<!--\s*(?:SECTION|END\s+SECTION):\s*(\S+)\s*-->', old, re.IGNORECASE
            )
            new_sections = re.findall(
                r'<!--\s*(?:SECTION|END\s+SECTION):\s*(\S+)\s*-->', new, re.IGNORECASE
            )
            old_set = set(s.lower() for s in old_sections)
            new_set = set(s.lower() for s in new_sections)
            missing = old_set - new_set
            if missing:
                errors.append(
                    f"Section marker(s) removed: {', '.join(sorted(missing))}"
                )

        # ── P5: File completeness check ──
        # Check for significant line count reduction (>30%)
        if old is not None:
            old_lines = len(old.splitlines())
            new_lines = len(new.splitlines())
            if old_lines > 20 and new_lines < old_lines * 0.7:
                errors.append(
                    f"File shortened significantly: {old_lines} → {new_lines} lines "
                    f"({100 - int(new_lines / old_lines * 100)}% reduction, possible truncation)"
                )

        return errors

    # ── Python ──────────────────────────────────────────────────────────

    def _validate_python(
        self, old: str | None, new: str, mode: str = "full_document"
    ) -> list[str]:
        """Validate Python structural integrity via AST."""
        errors: list[str] = []

        # Kiểm tra cú pháp
        try:
            new_tree = ast.parse(new)
        except SyntaxError as exc:
            errors.append(
                f"SyntaxError: {exc.msg} (line {exc.lineno})"
            )
            return errors

        # So sánh top-level definitions nếu có old content
        if old is not None:
            try:
                old_tree = ast.parse(old)
            except SyntaxError:
                # Old content đã lỗi sẵn – không cần so sánh
                return errors

            old_names = self._extract_toplevel_names(old_tree)
            new_names = self._extract_toplevel_names(new_tree)

            missing = old_names - new_names
            for name in sorted(missing):
                errors.append(f"Top-level definition removed: {name}")

        return errors

    @staticmethod
    def _extract_toplevel_names(tree: ast.Module) -> set[str]:
        """Extract top-level function/class names from an AST module."""
        names: set[str] = set()
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(node.name)
        return names

    # ── JavaScript / TypeScript ─────────────────────────────────────────

    def _validate_js(
        self, old: str | None, new: str, mode: str = "full_document"
    ) -> list[str]:
        """Validate JS/TS structural integrity."""
        errors: list[str] = []

        # Bracket balance
        for open_ch, close_ch, label in (
            ("{", "}", "curly braces"),
            ("(", ")", "parentheses"),
            ("[", "]", "square brackets"),
        ):
            diff = new.count(open_ch) - new.count(close_ch)
            if diff != 0:
                errors.append(
                    f"Unbalanced {label}: "
                    f"{new.count(open_ch)} '{open_ch}' vs "
                    f"{new.count(close_ch)} '{close_ch}'"
                )

        # Symbol comparison (>30% mất → cảnh báo)
        if old is not None:
            old_symbols = set(self._JS_SYMBOL_RE.findall(old))
            new_symbols = set(self._JS_SYMBOL_RE.findall(new))

            if old_symbols:
                missing = old_symbols - new_symbols
                ratio = len(missing) / len(old_symbols)
                if ratio > 0.30:
                    errors.append(
                        f"{len(missing)}/{len(old_symbols)} symbols removed "
                        f"({ratio:.0%}): {', '.join(sorted(missing))}"
                    )

        return errors

    # ── CSS / SCSS ──────────────────────────────────────────────────────

    def _validate_css(
        self, old: str | None, new: str, mode: str = "full_document"
    ) -> list[str]:
        """Validate CSS/SCSS structural integrity."""
        errors: list[str] = []

        # Bracket balance
        open_count = new.count("{")
        close_count = new.count("}")
        if open_count != close_count:
            errors.append(
                f"Unbalanced braces: {open_count} '{{' vs {close_count} '}}'"
            )

        # Kiểm tra selector bị mất
        if old is not None:
            old_selectors = set(
                m.strip() for m in self._CSS_SELECTOR_RE.findall(old)
            )
            new_selectors = set(
                m.strip() for m in self._CSS_SELECTOR_RE.findall(new)
            )

            missing = old_selectors - new_selectors
            for sel in sorted(missing):
                errors.append(f"CSS selector removed: {sel}")

        return errors

    # ── JSON ────────────────────────────────────────────────────────────

    def _validate_json(self, new: str) -> list[str]:
        """Validate JSON syntax."""
        errors: list[str] = []
        try:
            json.loads(new)
        except json.JSONDecodeError as exc:
            errors.append(
                f"JSONDecodeError: {exc.msg} "
                f"(line {exc.lineno}, col {exc.colno})"
            )
        return errors
