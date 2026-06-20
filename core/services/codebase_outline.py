"""Codebase Outline — quét dự án trả về bản đồ file + class/function.

Không chứa code chi tiết, chỉ có tên file + tên symbol.
AI dùng outline này để biết cần đọc file nào, không phải đọc bừa.
"""
import re
import os
from pathlib import Path
from typing import Optional

SYMBOL_PATTERNS: dict[str, list[tuple[str, str]]] = {
    ".py": [
        (r'^\s*class\s+(\w+)', "class"),
        (r'^\s*async\s+def\s+(\w+)', "async_function"),
        (r'^\s*def\s+(\w+)', "function"),
        (r'^\s*@\w+', "decorator"),
    ],
    ".js": [
        (r'(?:export\s+)?(?:default\s+)?(?:class|function)\s+(\w+)', "class_or_function"),
        (r'^\s*(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:function|\(|=>)', "function_var"),
        (r'^\s*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=', "variable"),
    ],
    ".ts": [
        (r'(?:export\s+)?(?:default\s+)?(?:class|function|interface|type|enum)\s+(\w+)', "class_or_function"),
        (r'^\s*(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:function|\(|=>)', "function_var"),
    ],
    ".tsx": [
        (r'(?:export\s+)?(?:default\s+)?(?:class|function|interface|type|enum)\s+(\w+)', "class_or_function"),
        (r'^\s*(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:function|\(|=>)', "function_var"),
    ],
    ".jsx": [
        (r'(?:export\s+)?(?:default\s+)?(?:class|function)\s+(\w+)', "class_or_function"),
        (r'^\s*(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:function|\(|=>)', "function_var"),
    ],
    ".go": [
        (r'^\s*func\s+(\w+)', "function"),
        (r'^\s*type\s+(\w+)\s+struct', "struct"),
        (r'^\s*type\s+(\w+)\s+interface', "interface"),
    ],
    ".rs": [
        (r'^\s*(?:pub\s+)?(?:async\s+)?fn\s+(\w+)', "function"),
        (r'^\s*(?:pub\s+)?struct\s+(\w+)', "struct"),
        (r'^\s*(?:pub\s+)?enum\s+(\w+)', "enum"),
        (r'^\s*(?:pub\s+)?trait\s+(\w+)', "trait"),
        (r'^\s*(?:pub\s+)?impl(?:\s+<\w+>)?\s+(\w+)', "impl"),
    ],
    ".java": [
        (r'^\s*(?:public|private|protected)?\s*(?:abstract|final|static)?\s*class\s+(\w+)', "class"),
        (r'^\s*(?:public|private|protected)?\s*(?:static)?\s*\w+\s+(\w+)\s*\(', "method"),
        (r'^\s*(?:public|private|protected)?\s*interface\s+(\w+)', "interface"),
    ],
    ".kt": [
        (r'^\s*(?:class|data\s+class|sealed\s+class|open\s+class)\s+(\w+)', "class"),
        (r'^\s*fun\s+(\w+)', "function"),
        (r'^\s*(?:interface|object)\s+(\w+)', "interface_or_object"),
    ],
    ".swift": [
        (r'^\s*(?:class|struct|enum|protocol)\s+(\w+)', "type"),
        (r'^\s*func\s+(\w+)', "function"),
        (r'^\s*var\s+(\w+)\s*:', "property"),
    ],
    ".rb": [
        (r'^\s*class\s+(\w+)', "class"),
        (r'^\s*def\s+(\w+)', "method"),
        (r'^\s*module\s+(\w+)', "module"),
    ],
    ".php": [
        (r'^\s*(?:abstract\s+)?class\s+(\w+)', "class"),
        (r'^\s*(?:public|private|protected)?\s*function\s+(\w+)', "method"),
        (r'^\s*interface\s+(\w+)', "interface"),
    ],
}


IGNORE_DIRS = {".git", ".orca", "node_modules", "__pycache__", "venv", ".venv", "dist", "build", ".next", "target", "bin", "obj", ".env", ".vscode", ".idea"}
TEXT_EXTENSIONS = {".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".kt", ".swift", ".rb", ".php", ".vue", ".svelte", ".html", ".css", ".scss", ".sql", ".yaml", ".yml", ".json", ".md", ".txt", ".toml", ".cfg", ".ini", ".env.example"}


class CodebaseOutline:
    """Scans project and returns a structured outline of files + symbols."""

    def __init__(self, project_root: str):
        self.root = Path(project_root).resolve()

    def get_outline(self, max_files: int = 200) -> str:
        """Return a text outline: path + symbols per file."""
        lines: list[str] = [f"# Codebase Outline — {self.root.name}", ""]
        file_count = 0

        for dirpath, dirnames, filenames in os.walk(self.root):
            # Skip ignored dirs
            dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS and not d.startswith(".")]
            # Sort for deterministic output
            dirnames.sort()

            for fname in sorted(filenames):
                if file_count >= max_files:
                    break
                ext = Path(fname).suffix.lower()
                if ext not in TEXT_EXTENSIONS:
                    continue

                fpath = Path(dirpath) / fname
                rel = str(fpath.relative_to(self.root))
                try:
                    symbols = self._extract_symbols(fpath, ext)
                except Exception:
                    symbols = []

                if not symbols and ext not in (".html", ".css", ".scss", ".sql", ".md", ".txt", ".yaml", ".yml", ".json", ".toml", ".cfg", ".ini", ".env.example"):
                    continue  # Skip files with no symbols unless they're data/UI files

                line = f"📄 {rel}"
                if symbols:
                    sym_str = ", ".join(f"{kind}:{name}" for kind, name in symbols[:8])
                    line += f"  [{sym_str}]"
                lines.append(line)
                file_count += 1

            if file_count >= max_files:
                lines.append(f"\n... và nhiều file khác (giới hạn {max_files})")

        return "\n".join(lines) if lines else "(empty project)"

    def _extract_symbols(self, fpath: Path, ext: str) -> list[tuple[str, str]]:
        """Extract (kind, name) pairs from a source file using regex."""
        patterns = SYMBOL_PATTERNS.get(ext, [])
        if not patterns:
            return []

        symbols: list[tuple[str, str]] = []
        try:
            text = fpath.read_text(encoding="utf-8", errors="replace")
            for pattern, kind in patterns:
                for m in re.finditer(pattern, text, re.MULTILINE):
                    name = m.group(1)
                    if len(name) <= 40:  # Sanity: skip generated names
                        symbols.append((kind, name))
        except Exception:
            pass

        return symbols
