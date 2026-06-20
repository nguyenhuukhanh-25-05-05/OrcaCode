"""Diagnostic mixin — file analysis, syntax checking, health scans, deep diagnosis."""

import re
import json
import subprocess
import py_compile
from pathlib import Path
from html.parser import HTMLParser


class DiagnosticMixin:
    """Mixin providing file diagnostics, syntax checking, and workspace health scanning.

    Relies on self._project_root, self.callbacks, self.patch_svc being available.
    """

    def _check_syntax(self, file_path: str) -> str:
        """Check a patched file for syntax/linter errors. Returns error text or empty string."""
        proj_root = self._project_root
        full_path = proj_root / file_path
        if not full_path.is_absolute():
            full_path = proj_root / file_path
        ext = full_path.suffix.lower()

        if ext == ".py":
            try:
                py_compile.compile(str(full_path), doraise=True)
                return ""
            except py_compile.PyCompileError as e:
                return str(e)
            except Exception as e:
                return f"Python syntax check failed: {e}"
        elif ext in (".js", ".mjs", ".cjs"):
            try:
                r = subprocess.run(
                    ["node", "--check", str(full_path)],
                    capture_output=True, text=True, timeout=10
                )
                return r.stderr.strip() if r.returncode != 0 else ""
            except FileNotFoundError:
                return ""
            except Exception as e:
                return str(e)
        elif ext in (".html", ".htm"):
            try:
                class StrictParser(HTMLParser):
                    def __init__(self):
                        super().__init__()
                        self.errors = []
                parser = StrictParser()
                with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                parser.feed(content)
                content_lower = content.lower()
                issues = []
                if '<!doctype' not in content_lower[:500] and '<html' not in content_lower[:500]:
                    issues.append("missing <!DOCTYPE>/<html>")
                if '<html' in content_lower and '</html>' not in content_lower[-200:]:
                    issues.append("missing </html> (file may be truncated)")
                if '<body' in content_lower and '</body>' not in content_lower[-200:]:
                    issues.append("missing </body> (file may be truncated)")
                if issues:
                    return "HTML structural issues: " + ", ".join(issues)
                return ""
            except Exception as e:
                return f"HTML parse error: {e}"
        elif ext == ".json":
            try:
                with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                    json.load(f)
                return ""
            except json.JSONDecodeError as e:
                return f"JSON error: {e}"
            except Exception as e:
                return str(e)
        elif ext == ".css":
            try:
                content = full_path.read_text(encoding="utf-8", errors="replace")
                open_braces = content.count('{')
                close_braces = content.count('}')
                if open_braces != close_braces:
                    return f"CSS bracket mismatch: {open_braces} open vs {close_braces} close"
                return ""
            except Exception as e:
                return str(e)
        return ""

    def _check_file_completeness(self, file_path: str, actual: str, expected: str) -> list[str]:
        """Check a newly created file for completeness / truncation issues."""
        issues = []
        ext = Path(file_path).suffix.lower()

        if expected:
            if len(actual) < len(expected) * 0.8:
                issues.append(
                    f"Kích thước file ({len(actual)} bytes) nhỏ hơn đáng kể so với nội dung AI tạo "
                    f"({len(expected)} bytes) — có thể file bị ghi thiếu."
                )

        stripped = actual.rstrip()
        if stripped.endswith(('...', '# ...', '// ...', '/* ... */')):
            issues.append("File kết thúc bằng dấu '...' — có thể bị cắt dở.")

        if ext in ('.html', '.htm'):
            actual_lower = actual.lower()
            if '<!doctype' not in actual_lower[:500] and '<html' not in actual_lower[:500]:
                issues.append("HTML thiếu <!DOCTYPE> hoặc thẻ <html> mở đầu.")
            if '<html' in actual_lower and '</html>' not in actual_lower[-200:]:
                issues.append("HTML thiếu thẻ đóng </html> — file có thể bị cắt.")
            if '<body' in actual_lower and '</body>' not in actual_lower[-200:]:
                issues.append("HTML thiếu thẻ đóng </body> — file có thể bị cắt.")
            if '<head' in actual_lower and '</head>' not in actual_lower[-500:]:
                issues.append("HTML thiếu thẻ đóng </head>.")

        if ext == '.css':
            open_braces = actual.count('{')
            close_braces = actual.count('}')
            if open_braces > 0 and open_braces != close_braces:
                issues.append(f"CSS mất cân bằng dấu ngoặc: {open_braces} `{{` vs {close_braces} `}}` — có thể bị thiếu code.")

        lines = actual.splitlines()
        if len(lines) < 3 and len(actual) < 100:
            issues.append(f"File quá ngắn ({len(lines)} dòng, {len(actual)} ký tự) — gần như chắc chắn bị cắt.")

        return issues

    def _detect_error_report(self, user_prompt: str) -> str:
        """Detect if the user is reporting a broken/missing file and return diagnostic report."""
        prompt_lower = user_prompt.lower()
        error_keywords = [
            "lỗi", "thiếu", "không chạy", "bể", "hỏng", "mất code", "mất đoạn",
            "sai", "không đúng", "chưa đủ", "còn thiếu", "bị cắt", "không hoạt động",
            "error", "missing", "broken", "bug", "doesn't work", "not working",
            "incomplete", "truncated", "cut off"
        ]
        file_keywords = ["file", "trang", "page", "html", "css", "js", "code", "web", "index", "admin", "landing"]

        has_error = any(kw in prompt_lower for kw in error_keywords)
        has_file = any(kw in prompt_lower for kw in file_keywords)
        if not (has_error and has_file):
            return ""

        mentioned_files = self._find_diagnostic_targets(user_prompt)
        diagnostic_reports = []
        for f in list(mentioned_files)[:5]:
            try:
                report = self._deep_diagnose(f)
                if report:
                    diagnostic_reports.append(report)
            except Exception:
                try:
                    report = self._diagnose_file(f)
                    if report:
                        diagnostic_reports.append(report)
                except Exception:
                    pass

        parts = [
            "[WARN] SYSTEM DIAGNOSTIC (ẩn với user): User đang báo lỗi file. "
            "Hệ thống đã tự động chạy chẩn đoán. Dưới đây là kết quả phân tích chi tiết:\n",
        ]
        if diagnostic_reports:
            parts.append("\n---\n".join(diagnostic_reports))
            parts.append("\n\nDựa trên chẩn đoán trên, hãy:")
            parts.append("1. Xác định chính xác file nào bị lỗi và vị trí lỗi")
            parts.append("2. SỬA bằng PATCH_FILE để thêm phần thiếu, hoặc WRITE_FILE nếu file hỏng nặng")
            parts.append("3. Nếu file bị cắt (thiếu thẻ đóng) → VIẾT LẠI TOÀN BỘ file đó")
            parts.append("4. VERIFY: sau khi sửa, đọc lại file để chắc chắn đã đủ")
        else:
            parts.append("(Không tìm thấy file cụ thể nào để chẩn đoán tự động)")
            parts.append("Hãy ĐỌC LẠI nội dung thực tế của file được nhắc đến, SO SÁNH CẤU TRÚC, và TÌM ĐIỂM GÃY.")

        return "\n".join(parts)

    def _find_diagnostic_targets(self, user_prompt: str, limit: int = 5) -> list[str]:
        """Pick likely files to diagnose from vague repair prompts."""
        proj_root = self._project_root
        prompt_lower = user_prompt.lower()
        targets: list[str] = []

        def add(path: str):
            path = path.strip().strip('"\'').replace("\\", "/")
            if path and path not in targets and (proj_root / path).exists():
                targets.append(path)

        file_patterns = [
            r'(?:file|trang|page|html|css|js)\s+["\']?([a-zA-Z0-9_\-./]+\.[a-z]{2,5})["\']?',
            r'["\']([a-zA-Z0-9_\-./]+\.[a-z]{2,5})["\']',
            r'\b([a-zA-Z0-9_\-./]+\.(?:html|css|js|htm|py|ts|jsx|tsx|json))\b',
        ]
        for pat in file_patterns:
            for match in re.findall(pat, user_prompt, re.IGNORECASE):
                add(match)

        for stem in re.findall(r'\b([a-zA-Z][a-zA-Z0-9_-]{1,40})\b', user_prompt):
            stem_l = stem.lower()
            if stem_l in {"file", "page", "trang", "html", "css", "js", "code", "web", "loi", "fix", "sua"}:
                continue
            for ext in (".html", ".htm", ".css", ".js"):
                add(stem_l + ext)
                add(stem + ext)

        if "index" in prompt_lower:
            add("index.html")
        if "admin" in prompt_lower:
            add("admin.html")
        if any(k in prompt_lower for k in ("landing", "trang", "page", "web")):
            add("landing.html")
            add("index.html")

        if len(targets) >= limit:
            return targets[:limit]

        candidates = []
        for pattern in ("index.html", "*.html", "*.css", "*.js"):
            candidates.extend(proj_root.glob(pattern))
        candidates = [p for p in candidates if p.is_file() and ".orca" not in p.parts and ".git" not in p.parts]
        candidates.sort(key=lambda p: (p.name != "index.html", -p.stat().st_mtime))
        for p in candidates:
            try:
                rel = str(p.relative_to(proj_root)).replace("\\", "/")
                content = p.read_text(encoding="utf-8", errors="replace")
                if self._deep_structure_check(content, p.suffix.lower(), rel) or self._check_file_completeness(rel, content, ""):
                    add(rel)
            except Exception:
                pass
            if len(targets) >= limit:
                break

        return targets[:limit]

    def _workspace_health_scan(self, user_prompt: str, limit: int = 5) -> str:
        """Return a compact report of obviously broken project files.
        Only runs when the prompt explicitly mentions errors or broken files."""
        proj_root = self._project_root
        prompt_lower = user_prompt.lower()
        error_intent = any(k in prompt_lower for k in (
            "fix", "loi", "lỗi", "sửa", "thiếu", "hong", "hỏng",
            "error", "bug", "broken", "missing", "khong chay", "không chạy",
            "not working", "doesn't work", "failed", "crash", "sai",
            "mất", "mã", "code loi", "code loix",
        ))
        if not error_intent:
            return ""

        files = [p for p in proj_root.iterdir()
                 if p.is_file() and p.suffix.lower() in (".html", ".css", ".js")]
        unique = []
        seen = set()
        for p in files:
            if not p.is_file() or p in seen or ".orca" in p.parts or ".git" in p.parts:
                continue
            seen.add(p)
            unique.append(p)
        unique.sort(key=lambda p: (p.name != "index.html", -p.stat().st_mtime))

        reports = []
        for p in unique[:20]:
            try:
                rel = str(p.relative_to(proj_root)).replace("\\", "/")
                content = p.read_text(encoding="utf-8", errors="replace")
                issues = self._deep_structure_check(content, p.suffix.lower(), rel)
                issues.extend(self._check_file_completeness(rel, content, ""))
                if issues:
                    content_lines = content.splitlines()
                    start_line = max(1, len(content_lines) - 4)
                    tail = "\n".join(
                        f"    {start_line + i}: {line[:160]}"
                        for i, line in enumerate(content_lines[-5:])
                    )
                    reports.append(
                        f"### {rel}\n"
                        f"- Size: {len(content_lines)} lines, {len(content)} chars\n"
                        f"- Issues:\n  - " + "\n  - ".join(issues[:8]) + "\n"
                        f"- Last lines:\n{tail}"
                    )
            except Exception:
                pass
            if len(reports) >= limit:
                break

        if not reports:
            return ""
        return (
            "## AUTO WORKSPACE HEALTH SCAN\n"
            "The system found files that already look structurally broken before editing. "
            "Treat these as high-priority evidence when the user request is vague.\n\n"
            + "\n\n".join(reports)
        )

    def _diagnose_file(self, file_path: str) -> str:
        """Comprehensive file diagnosis — read, analyze, check dependencies, run tools.

        Returns a structured diagnostic report for the AI to understand what's wrong.
        """
        proj_root = self._project_root
        full_path = proj_root / file_path

        report_lines = [f"## DIAGNOSTIC REPORT: {file_path}"]
        if not full_path.exists():
            report_lines.append(f"[ERR] FILE NOT FOUND: {full_path}")
            return "\n".join(report_lines)

        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            report_lines.append(f"[ERR] Cannot read file: {e}")
            return "\n".join(report_lines)

        total_lines = len(content.splitlines())
        total_chars = len(content)
        ext = full_path.suffix.lower()
        report_lines.append(f"**File:** {full_path}")
        report_lines.append(f"**Size:** {total_lines} lines, {total_chars} chars, {full_path.stat().st_size} bytes")
        report_lines.append(f"**Type:** {ext}")

        last_lines = content.splitlines()[-3:]
        report_lines.append(f"**Last 3 lines:**")
        for i, line in enumerate(last_lines):
            report_lines.append(f"  {total_lines - 2 + i}: `{line[:120]}`")

        report_lines.append("")
        report_lines.append("### Structure Analysis")

        if ext in ('.html', '.htm'):
            c = content.lower()
            tags_to_check = [
                ('<!doctype', 'DOCTYPE declaration'),
                ('<html', '</html>', 'HTML root'),
                ('<head', '</head>', 'HEAD section'),
                ('<body', '</body>', 'BODY section'),
                ('<header', '</header>', 'HEADER element'),
                ('<nav', '</nav>', 'NAV element'),
                ('<main', '</main>', 'MAIN content'),
                ('<footer', '</footer>', 'FOOTER section'),
                ('<script', '</script>', 'SCRIPT tag'),
                ('<style', '</style>', 'STYLE tag'),
            ]
            for tag_info in tags_to_check:
                if len(tag_info) == 2:
                    open_tag, desc = tag_info
                    close_tag = None
                else:
                    open_tag, close_tag, desc = tag_info
                has_open = open_tag in c
                has_close = close_tag in c if close_tag else True
                if has_open and not has_close:
                    report_lines.append(f"  [ERR] **{desc}**: có `{open_tag}` nhưng THIẾU `{close_tag}` — FILE BỊ CẮT!")
                elif has_open:
                    report_lines.append(f"  [OK] {desc}: đầy đủ")
                else:
                    report_lines.append(f"  [WARN] {desc}: không có (có thể không cần)")

            section_count = len(re.findall(r'<!--\s*SECTION:', content))
            report_lines.append(f"  📐 Section markers: {section_count}")

        elif ext == '.css':
            open_b = content.count('{')
            close_b = content.count('}')
            report_lines.append(f"  Curly braces: {open_b} `{{` vs {close_b} `}}` {'[OK]' if open_b == close_b else '[ERR] MISMATCH'}")
            rule_count = len(re.findall(r'[^{}]+\{[^}]*\}', content))
            report_lines.append(f"  CSS rules: ~{rule_count}")
            media_count = len(re.findall(r'@media', content))
            report_lines.append(f"  @media queries: {media_count}")

        elif ext in ('.js', '.mjs', '.jsx'):
            open_b = content.count('{')
            close_b = content.count('}')
            report_lines.append(f"  Curly braces: {open_b} `{{` vs {close_b} `}}` {'[OK]' if open_b == close_b else '[ERR] MISMATCH'}")
            paren_open = content.count('(')
            paren_close = content.count(')')
            report_lines.append(f"  Parentheses: {paren_open} `(` vs {paren_close} `)` {'[OK]' if paren_open == paren_close else '[WARN]'}")
            func_count = len(re.findall(r'function\s+\w+|const\s+\w+\s*=\s*\(.*\)\s*=>|=>', content))
            report_lines.append(f"  Functions/arrows: ~{func_count}")

        report_lines.append("")
        report_lines.append("### Dependencies (related files)")
        deps = self._find_dependencies(content, ext, proj_root, file_path)
        if deps:
            for dep_type, dep_files in deps.items():
                report_lines.append(f"  **{dep_type}:**")
                for df in dep_files[:10]:
                    dep_full = proj_root / df
                    exists = "[OK]" if dep_full.exists() else "[ERR] MISSING"
                    size = f"({dep_full.stat().st_size} bytes)" if dep_full.exists() else ""
                    report_lines.append(f"    {exists} `{df}` {size}")
        else:
            report_lines.append("  No external dependencies detected.")

        report_lines.append("")
        report_lines.append("### Syntax Check")
        syntax_result = self._check_syntax(str(full_path.relative_to(proj_root)))
        if syntax_result:
            report_lines.append(f"  [ERR] **Syntax errors found:**\n  ```\n  {syntax_result}\n  ```")
        else:
            report_lines.append("  [OK] No syntax errors detected.")

        report_lines.append("")
        report_lines.append("### Completeness Check")
        completeness = self._check_file_completeness(file_path, content, "")
        if completeness:
            for issue in completeness:
                report_lines.append(f"  [WARN] {issue}")
        else:
            report_lines.append("  [OK] File appears structurally complete.")

        if deps:
            report_lines.append("")
            report_lines.append("### Related File Scan")
            for dep_type, dep_files in deps.items():
                for df in dep_files[:5]:
                    dep_full = proj_root / df
                    if dep_full.exists():
                        dep_syntax = self._check_syntax(df)
                        if dep_syntax:
                            report_lines.append(f"  [ERR] `{df}` has syntax errors!")
                        dep_content = dep_full.read_text(encoding="utf-8", errors="replace")
                        dep_completeness = self._check_file_completeness(df, dep_content, "")
                        for issue in dep_completeness:
                            report_lines.append(f"  [WARN] `{df}`: {issue}")

        return "\n".join(report_lines)

    def _deep_diagnose(self, file_path: str, visited: set = None, depth: int = 0) -> str:
        """Maximum-depth recursive diagnostic — read all related files, run tools, find everything."""
        if visited is None:
            visited = set()
        if depth > 3 or file_path in visited:
            return ""
        visited.add(file_path)

        proj_root = self._project_root
        full_path = proj_root / file_path
        ext = full_path.suffix.lower()

        if not full_path.exists():
            return f"[ERR] FILE NOT FOUND: {file_path}\n"

        content = full_path.read_text(encoding="utf-8", errors="replace")
        total_lines = len(content.splitlines())

        lines = [f"{'  ' * depth}📄 {file_path} ({total_lines} lines, {len(content)} chars)"]

        issues = self._deep_structure_check(content, ext, file_path)
        for issue in issues:
            lines.append(f"{'  ' * depth}  {issue}")

        syntax = self._check_syntax(str(full_path.relative_to(proj_root)))
        if syntax:
            lines.append(f"{'  ' * depth}  [ERR] SYNTAX: {syntax[:200]}")

        tool_results = self._run_external_tools(full_path, ext)
        for tool_name, result in tool_results:
            if result:
                lines.append(f"{'  ' * depth}  🔧 {tool_name}: {result[:200]}")

        deps = self._find_dependencies(content, ext, proj_root, file_path)
        if deps and depth < 3:
            lines.append(f"{'  ' * depth}  🔗 Dependencies ({sum(len(v) for v in deps.values())} files):")
            for dep_type, dep_files in deps.items():
                for df in dep_files[:5]:
                    dep_lines = self._deep_diagnose(df, visited, depth + 1)
                    if dep_lines:
                        lines.append(dep_lines)

        return "\n".join(lines) if depth == 0 else "\n".join(lines)

    def _deep_structure_check(self, content: str, ext: str, file_path: str) -> list[str]:
        """Aggressive structure analysis — find every possible issue."""
        issues = []
        total_lines = len(content.splitlines())

        if ext in ('.html', '.htm'):
            c = content.lower()
            checks = [
                ('<!doctype', None, 'DOCTYPE'),
                ('<html', '</html>', 'html'),
                ('<head', '</head>', 'head'),
                ('<title', '</title>', 'title'),
                ('<meta', None, 'meta charset/viewport'),
                ('<body', '</body>', 'body'),
                ('<header', '</header>', 'header'),
                ('<nav', '</nav>', 'nav'),
                ('<main', '</main>', 'main'),
                ('<section', None, 'section'),
                ('<article', None, 'article'),
                ('<footer', '</footer>', 'footer'),
                ('<script', '</script>', 'script'),
                ('<style', '</style>', 'style'),
            ]
            for open_tag, close_tag, name in checks:
                has_open = open_tag in c
                has_close = close_tag in c if close_tag else True
                if has_open and not has_close:
                    for i, line in enumerate(content.splitlines()):
                        if open_tag in line.lower():
                            issues.append(f"[ERR] <{name}> mở ở dòng {i+1} nhưng THIẾU thẻ đóng — FILE BỊ CẮT!")
                            break

            for i, line in enumerate(content.splitlines()[-5:]):
                line_num = total_lines - 4 + i
                stripped = line.strip()
                if re.search(r'<[a-zA-Z][^>]*$', stripped):
                    issues.append(f"[ERR] HTML tag/attribute bị cắt ở dòng {line_num}: `{stripped[:120]}`")
                elif re.search(r'=\s*["\'][^"\'>]*$', stripped):
                    issues.append(f"[ERR] HTML attribute quote chưa đóng ở dòng {line_num}: `{stripped[:120]}`")

            stripped_all = content.rstrip()
            if stripped_all and not stripped_all.endswith(">") and re.search(r'<[a-zA-Z][^>]*$', stripped_all):
                issues.append("[ERR] File kết thúc giữa một thẻ HTML — gần như chắc chắn bị cắt output.")

            img_tags = re.findall(r'<img[^>]+>', content, re.IGNORECASE)
            for tag in img_tags:
                if 'alt=' not in tag.lower():
                    issues.append("[WARN] <img> thiếu thuộc tính alt (accessibility)")
                if 'loading=' not in tag.lower():
                    issues.append("[WARN] <img> thiếu loading=lazy")

        elif ext == '.css':
            open_brace = content.count('{')
            close_brace = content.count('}')
            if open_brace != close_brace:
                issues.append(f"[ERR] CSS lệch ngoặc: {open_brace} `{{` vs {close_brace} `}}` — THIẾU {abs(open_brace - close_brace)} dấu")
            if '@media' not in content:
                issues.append("[WARN] Không có @media query — thiếu responsive design")
            if ':root' not in content and '--' not in content:
                issues.append("[WARN] Không dùng CSS custom properties")
            important_count = content.count('!important')
            if important_count > 3:
                issues.append(f"[WARN] {important_count} lần dùng !important — nên tăng specificity thay vào đó")

        elif ext in ('.js', '.mjs', '.jsx'):
            open_brace = content.count('{')
            close_brace = content.count('}')
            open_paren = content.count('(')
            close_paren = content.count(')')
            if open_brace != close_brace:
                issues.append(f"[ERR] JS lệch ngoặc: {open_brace} `{{` vs {close_brace} `}}`")
            if open_paren != close_paren:
                issues.append(f"[ERR] JS lệch ngoặc: {open_paren} `(` vs {close_paren} `)`")
            if 'console.log' in content:
                issues.append("[WARN] Còn console.log trong production code")
            if 'TODO' in content or 'FIXME' in content:
                issues.append("[WARN] Còn TODO/FIXME trong code")

        if total_lines < 5:
            issues.append(f"[ERR] File quá ngắn ({total_lines} dòng) — gần như chắc chắn bị cắt hoặc lỗi")

        return issues

    def _run_external_tools(self, full_path, ext: str) -> list[tuple]:
        """Run external tools (HTML validators, CSS linters, JS checkers) and return results."""
        results = []

        try:
            if ext in ('.html', '.htm'):
                try:
                    class Validator(HTMLParser):
                        def __init__(self):
                            super().__init__()
                            self.errors = []
                    v = Validator()
                    content = full_path.read_text(encoding="utf-8", errors="replace")
                    v.feed(content)
                    results.append(("html.parser", "[OK] Valid HTML"))
                except Exception as e:
                    results.append(("html.parser", f"[ERR] {str(e)[:150]}"))

            elif ext == '.css':
                content = full_path.read_text(encoding="utf-8", errors="replace")
                open_b = content.count('{')
                close_b = content.count('}')
                if open_b == close_b:
                    results.append(("CSS braces", f"[OK] Balanced ({open_b} pairs)"))
                else:
                    results.append(("CSS braces", f"[ERR] Mismatch: {open_b} vs {close_b}"))

            elif ext in ('.js', '.mjs'):
                try:
                    r = subprocess.run(
                        ["node", "--check", str(full_path)],
                        capture_output=True, text=True, timeout=10
                    )
                    if r.returncode == 0:
                        results.append(("node --check", "[OK] Valid JS"))
                    else:
                        results.append(("node --check", f"[ERR] {r.stderr.strip()[:200]}"))
                except FileNotFoundError:
                    pass
                except Exception:
                    pass

            size = full_path.stat().st_size
            if size == 0:
                results.append(("file size", "[ERR] EMPTY FILE (0 bytes)"))
            elif size < 100 and ext in ('.html', '.css', '.js'):
                results.append(("file size", f"[WARN] Very small ({size} bytes) — likely incomplete"))

        except Exception as e:
            results.append(("tools", f"Error: {e}"))

        return results

    def _find_dependencies(self, content: str, ext: str, proj_root, current_file: str) -> dict:
        """Find all external files referenced by this file (CSS, JS, images, etc)."""
        deps = {}

        if ext in ('.html', '.htm'):
            css_files = re.findall(r'href=["\']([^"\']+\.css)["\']', content, re.IGNORECASE)
            if css_files:
                deps['CSS'] = sorted(set(css_files))
            js_files = re.findall(r'src=["\']([^"\']+\.js)["\']', content, re.IGNORECASE)
            if js_files:
                deps['JavaScript'] = sorted(set(js_files))

        elif ext == '.css':
            imports = re.findall(r'@import\s+["\']([^"\']+)["\']', content)
            if imports:
                deps['CSS imports'] = sorted(set(imports))
            urls = re.findall(r'url\(["\']?([^"\'\)]+)["\']?\)', content)
            if urls:
                deps['URL references'] = sorted(set([u for u in urls if not u.startswith('data:')]))

        elif ext in ('.js', '.mjs'):
            imports = re.findall(r'(?:import|require)\s*\(?["\']([^"\']+)["\']\)?', content)
            if imports:
                deps['JS imports'] = sorted(set(imports))

        return deps
