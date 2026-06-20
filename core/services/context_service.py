"""Context Service - search and context building via CodeGraph + ripgrep fallback."""
import subprocess
import re
import shutil
import time
import logging
from pathlib import Path
from core.models import SearchResult

logger = logging.getLogger("orca.context")


class ContextService:
    LEVEL_FILE = 1
    LEVEL_SYMBOL = 2
    LEVEL_CONTENT = 3

    def __init__(self, project_root: str = ".", max_files: int = 5, max_lines: int = 100,
                 use_codegraph: bool = True):
        self.project_root = Path(project_root)
        self.max_files = max_files
        self.max_lines = max_lines
        
        import sys
        local_rg = self.project_root / "rg.exe"
        bundled_rg = Path(sys._MEIPASS) / "rg.exe" if hasattr(sys, '_MEIPASS') else None
        self.rg_available = (
            bool(shutil.which("rg")) 
            or local_rg.exists() 
            or (bundled_rg is not None and bundled_rg.exists())
        )

        self._walk_cache: list[Path] | None = None
        self._walk_cache_time: float = 0
        self._walk_cache_ttl: float = 5.0

        self._codegraph = None
        self._codegraph_available = None
        if use_codegraph:
            try:
                from core.services.codegraph_service import CodeGraphService
                self._codegraph = CodeGraphService(project_root)
                self._codegraph_available = self._codegraph.available
            except Exception as e:
                logger.debug(f"CodeGraph init failed: {e}")
                self._codegraph_available = False

    def search(self, keyword: str, level: int = 2) -> list[SearchResult]:
        if level == self.LEVEL_FILE:
            return self._search_by_filename(keyword)
        elif level == self.LEVEL_SYMBOL:
            return self._search_by_symbol(keyword)
        return self._search_by_content(keyword)

    def _get_all_files(self, max_depth: int = 4, max_files: int = 500) -> list[Path]:
        now = time.monotonic()
        if self._walk_cache and (now - self._walk_cache_time) < self._walk_cache_ttl:
            return self._walk_cache
        files = []
        ignored_dirs = {
            ".git", ".orca", "node_modules", "venv", "env", 
            "__pycache__", ".pytest_cache", ".idea", ".vscode", 
            "build", "dist", "vendor", ".agents",
        }
        stack: list[tuple[Path, int]] = [(self.project_root, 0)]
        while stack and len(files) < max_files:
            curr, depth = stack.pop()
            if depth > max_depth:
                continue
            try:
                for entry in curr.iterdir():
                    if len(files) >= max_files:
                        break
                    if entry.is_dir():
                        if entry.name not in ignored_dirs and not entry.name.startswith("."):
                            stack.append((entry, depth + 1))
                    elif entry.is_file():
                        files.append(entry)
            except PermissionError:
                continue
        self._walk_cache = files
        self._walk_cache_time = time.monotonic()
        return files

    def build_context(self, prompt: str) -> str:
        parts = [f"Dự án: {self.project_root}\n"]
        found: list[SearchResult] = []

        if self._codegraph_available and self._codegraph.is_project_initialized() and prompt.strip():
            cg_context = self._build_codegraph_context(prompt)
            if cg_context:
                parts.append(cg_context)
                return "\n".join(parts)

        # 1. Scan prompt for @filename or @path references (Cursor-style @file targeting)
        at_paths = re.findall(r'@([a-zA-Z0-9_\-./\\]+\.[a-zA-Z0-9]+)', prompt)
        for p_str in at_paths:
            try:
                p = Path(p_str)
                if not p.is_absolute():
                    full_p = self.project_root / p
                else:
                    full_p = p
                
                # If not found directly, search recursively for a file with the same name
                if not full_p.is_file():
                    filename = p.name
                    all_files = self._get_all_files()
                    for f in all_files:
                        if f.name.lower() == filename.lower():
                            full_p = f
                            break
                            
                if full_p.is_file():
                    proj_res = self.project_root.resolve()
                    file_res = full_p.resolve()
                    if proj_res in file_res.parents or file_res == proj_res:
                        rel_path = str(file_res.relative_to(proj_res))
                        if rel_path not in [f.file_path for f in found]:
                            # High score 1.0 and large max_lines to prioritize and load fully
                            found.append(SearchResult(rel_path, 1, self.max_lines * 10, "", 1.0))
            except Exception as e:
                logger.debug(f"Keyword extraction error: {e}")
                continue

        # 2. Scan prompt for explicit files (without @) that exist in the project
        potential_paths = re.findall(r'[a-zA-Z0-9_\-./\\]+\.[a-zA-Z0-9]+', prompt)
        for p_str in potential_paths:
            if p_str in at_paths:
                continue
            try:
                p = Path(p_str)
                if not p.is_absolute():
                    full_p = self.project_root / p
                else:
                    full_p = p
                if full_p.is_file():
                    proj_res = self.project_root.resolve()
                    file_res = full_p.resolve()
                    if proj_res in file_res.parents or file_res == proj_res:
                        rel_path = str(file_res.relative_to(proj_res))
                        if rel_path not in [f.file_path for f in found]:
                            found.append(SearchResult(rel_path, 1, self.max_lines, "", 0.9))
            except Exception:
                continue

        # 3. Extract keywords and search
        keywords = self._extract_keywords(prompt)
        for kw in keywords[:3]:
            if len(found) >= self.max_files:
                break
            for level in (1, 2, 3):
                results = self.search(kw, level)
                for r in results:
                    if r.file_path not in [f.file_path for f in found]:
                        found.append(r)
                if len(found) >= self.max_files:
                    break

        # 4. Fallback: if nothing found, load all files in the project root (up to max_files)
        if not found:
            all_files = self._get_all_files()
            priority_exts = {".html", ".htm", ".py", ".js", ".ts", ".css", ".json"}
            all_files.sort(key=lambda p: (p.suffix.lower() not in priority_exts, p.name.lower()))
            for p in all_files:
                if len(found) >= self.max_files:
                    break
                try:
                    rel_path = str(p.relative_to(self.project_root))
                    if not self._is_binary(p):
                        found.append(SearchResult(rel_path, 1, self.max_lines, "", 0.1))
                except Exception:
                    continue

        if not found:
            parts.append("(Không tìm thấy file liên quan. Dùng lệnh xem cấu trúc dự án.)")
            return "\n".join(parts)
        parts.append(f"File liên quan ({len(found)} files):\n")
        for r in found:
            content = self.read_file_context(r.file_path)
            if content:
                parts.append(f"[{r.file_path}]")
                parts.append(content)
                parts.append("")
        return "\n".join(parts)

    def _build_codegraph_context(self, prompt: str) -> str:
        if not self._codegraph or not self._codegraph_available:
            return ""
        if not prompt.strip():
            return ""

        try:
            if not self._codegraph.is_project_initialized():
                return ""
            explore_result = self._codegraph.explore(prompt)
        except Exception:
            return ""

        if not explore_result.symbols and not explore_result.raw:
            return ""

        lines = ["[CodeGraph Intelligence]", ""]

        if explore_result.flow:
            lines.append(f"Flow: {explore_result.flow}")
            lines.append("")

        lines.append("Symbols liên quan:")
        for sym in explore_result.symbols[:self.max_files * 3]:
            loc = f"{sym.file_path}:{sym.line}" if sym.file_path else "?"
            kind = f" [{sym.kind}]" if sym.kind else ""
            lines.append(f"  - `{sym.name}`{kind} @ {loc}")
            if sym.signature:
                lines.append(f"    {sym.signature}")
            if sym.body:
                body = sym.body[:self.max_lines * 2]
                lines.append(f"    ```")
                lines.append(body)
                lines.append(f"    ```")
            lines.append("")

        if explore_result.blast_radius:
            lines.append("Phạm vi ảnh hưởng:")
            for sym in explore_result.blast_radius[:10]:
                lines.append(f"  - `{sym.name}` [{sym.kind}] @ {sym.file_path}")

        if not lines[2:]:
            return ""

        return "\n".join(lines)

    def has_codegraph(self) -> bool:
        return self._codegraph_available and self._codegraph is not None

    def get_codegraph_status(self) -> dict:
        if not self.has_codegraph():
            return {"available": False}
        status = self._codegraph.get_status()
        return {
            "available": True,
            "initialized": status.initialized,
            "indexed": status.indexed,
            "total_files": status.total_files,
            "total_nodes": status.total_nodes,
            "total_edges": status.total_edges,
            "languages": status.languages,
            "version": status.version,
        }

    def ensure_codegraph_ready(self, auto_init: bool = False) -> bool:
        if not self.has_codegraph():
            return False
        if not self._codegraph.is_project_initialized():
            if auto_init:
                return self._codegraph.ensure_initialized(force_index=True)
            return False
        return True

    def read_file_context(self, file_path: str, start_line: int = 1, max_lines: int = 0) -> str:
        max_lines = max_lines or self.max_lines
        full_path = self.project_root / file_path
        try:
            lines = full_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except (FileNotFoundError, OSError):
            return ""
        total = len(lines)
        if total <= max_lines:
            return "\n".join(lines)
        head = "\n".join(lines[:max_lines // 2])
        tail = "\n".join(lines[-(max_lines // 2):])
        return f"{head}\n... (truncated, {total} lines total) ...\n{tail}"

    def _search_by_filename(self, keyword: str) -> list[SearchResult]:
        if self.rg_available:
            output = self._run_rg(["--files", "--iglob", f"*{keyword}*"])
            files = [f.strip() for f in output.splitlines() if f.strip()]
        else:
            files = []
            keyword_lower = keyword.lower()
            all_files = self._get_all_files()
            for p in all_files:
                rel_path = str(p.relative_to(self.project_root))
                if keyword_lower in rel_path.lower():
                    files.append(rel_path)
        return [SearchResult(f, 1, self.max_lines, "", 0.5) for f in files[:self.max_files]]

    def _search_by_symbol(self, keyword: str) -> list[SearchResult]:
        if self.rg_available:
            pattern = rf"(def |class |function |const |let |var |fn ){re.escape(keyword)}"
            output = self._run_rg(["-n", "-i", "--type-add", "code:*.{py,js,ts,jsx,tsx,java,rs,go,c,cpp,h}", "-t", "code", "--", pattern])
            return self._parse_matches(output)
        else:
            results = []
            keyword_lower = keyword.lower()
            pattern = re.compile(rf"(def |class |function |const |let |var |fn ){re.escape(keyword)}", re.IGNORECASE)
            code_extensions = {".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".rs", ".go", ".c", ".cpp", ".h", ".html", ".css"}
            all_files = self._get_all_files()
            for p in all_files:
                if p.suffix.lower() not in code_extensions:
                    continue
                if self._is_binary(p):
                    continue
                try:
                    content = p.read_text(encoding="utf-8", errors="replace")
                    lines = content.splitlines()
                    matching_lines = []
                    for idx, line in enumerate(lines):
                        if pattern.search(line):
                            matching_lines.append(idx + 1)
                    if matching_lines:
                        rel_path = str(p.relative_to(self.project_root))
                        min_l = max(1, min(matching_lines) - 3)
                        max_l = min(len(lines), max(matching_lines) + 3)
                        results.append(SearchResult(rel_path, min_l, max_l, "", 0.0))
                except Exception:
                    continue
            return results[:self.max_files]

    def _search_by_content(self, keyword: str) -> list[SearchResult]:
        if self.rg_available:
            output = self._run_rg(["-n", "-i", "--", keyword])
            return self._parse_matches(output)
        else:
            results = []
            keyword_lower = keyword.lower()
            all_files = self._get_all_files()
            for p in all_files:
                if self._is_binary(p):
                    continue
                try:
                    content = p.read_text(encoding="utf-8", errors="replace")
                    lines = content.splitlines()
                    matching_lines = []
                    for idx, line in enumerate(lines):
                        if keyword_lower in line.lower():
                            matching_lines.append(idx + 1)
                    if matching_lines:
                        rel_path = str(p.relative_to(self.project_root))
                        min_l = max(1, min(matching_lines) - 3)
                        max_l = min(len(lines), max(matching_lines) + 3)
                        results.append(SearchResult(rel_path, min_l, max_l, "", 0.0))
                except Exception:
                    continue
            return results[:self.max_files]

    def _parse_matches(self, output: str) -> list[SearchResult]:
        file_map: dict[str, list[int]] = {}
        for line in output.splitlines():
            parts = line.strip().split(":", 2)
            if len(parts) >= 2:
                try:
                    fp, ln = parts[0], int(parts[1])
                    file_map.setdefault(fp, []).append(ln)
                except ValueError:
                    continue
        results = []
        for fp, lines in file_map.items():
            if self._is_binary(self.project_root / fp):
                continue
            min_l = max(1, min(lines) - 3)
            max_l = max(lines) + 3
            results.append(SearchResult(fp, min_l, max_l, "", 0.0))
        return results[:self.max_files]

    def _run_rg(self, args: list[str]) -> str:
        import sys
        local_rg = self.project_root / "rg.exe"
        bundled_rg = Path(sys._MEIPASS) / "rg.exe" if hasattr(sys, '_MEIPASS') else None
        
        if bundled_rg and bundled_rg.exists():
            rg_path = bundled_rg
        elif local_rg.exists():
            rg_path = local_rg
        else:
            rg_path = Path("rg")
            
        try:
            proc = subprocess.run([str(rg_path)] + args, capture_output=True, encoding="utf-8", errors="replace", cwd=self.project_root, timeout=15)
            return proc.stdout
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return ""

    def _extract_keywords(self, prompt: str) -> list[str]:
        stopwords = {"sửa", "tạo", "thêm", "xóa", "file", "trong", "cho", "với", "của",
                     "sua", "them", "xoa", "voi", "cua", "va", "hoac", "cac", "mot", "nhung",
                     "fix", "add", "remove", "create", "update", "change", "the", "a", "an",
                     "và", "hoặc", "các", "một", "những", "ở", "tại", "vào", "ra"}
        words = re.findall(r'[a-zA-Z0-9_./\\-]+', prompt)
        keywords = [w for w in words if w.lower() not in stopwords and len(w) > 2]
        keywords.sort(key=lambda w: (not ("." in w or "/" in w or "\\" in w)), reverse=True)
        return keywords

    def _is_binary(self, filepath: Path) -> bool:
        try:
            with open(filepath, "rb") as f:
                return b"\0" in f.read(8192)
        except Exception:
            return True

    def format_context(self, results: list[SearchResult]) -> str:
        parts = [f"Project: {self.project_root}\n"]
        for r in results[:self.max_files]:
            parts.append(f"- {r.file_path} (lines {r.line_start}-{r.line_end})")
        parts.append("")
        for r in results[:self.max_files]:
            content = self.read_file_context(r.file_path, r.line_start)
            if content:
                parts.append(f"[{r.file_path}]\n{content}\n")
        return "\n".join(parts)
