"""Debug Service - stack trace parsing, error analysis, auto-fix suggestions."""
import re
import subprocess
from pathlib import Path


class DebugService:
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)

    def parse_stack_trace(self, text: str) -> list[dict]:
        frames = []
        patterns = [
            r'File\s+"([^"]+)",\s*line\s+(\d+)(?:,\s*in\s+(\w+))?',
            r'\s+at\s+(.+?)\((.+?):(\d+):(\d+)\)',
            r'\s+at\s+(.+?)\((.+?):(\d+)\)',
        ]
        for pat in patterns:
            for m in re.finditer(pat, text):
                if pat.startswith(r'File'):
                    frames.append({
                        "file": m.group(1), "line": int(m.group(2)),
                        "func": m.group(3) or "?", "type": "python"
                    })
                elif pat.startswith(r'\s+at'):
                    frames.append({
                        "file": m.group(2), "line": int(m.group(3)),
                        "func": m.group(1), "type": "js"
                    })
        return frames

    def extract_error_type(self, text: str) -> str:
        for pat in [
            r'(\w+(?:Error|Exception|Warning)):\s*(.*)',
            r'(SyntaxError):\s*(.*)',
            r'(RuntimeError):\s*(.*)',
            r'(TypeError):\s*(.*)',
            r'(ValueError):\s*(.*)',
            r'(ImportError):\s*(.*)',
            r'(ModuleNotFoundError):\s*(.*)',
            r'(FileNotFoundError):\s*(.*)',
            r'(KeyError):\s*(.*)',
            r'(AttributeError):\s*(.*)',
            r'(IndexError):\s*(.*)',
            r'(ZeroDivisionError):\s*(.*)',
            r'(AssertionError):\s*(.*)',
        ]:
            m = re.search(pat, text)
            if m:
                return f"{m.group(1)}: {m.group(2)}"
        return ""

    def read_error_context(self, file_path: str, line_no: int, context: int = 5) -> str:
        full_path = self.project_root / file_path
        try:
            lines = full_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except (FileNotFoundError, OSError):
            return ""
        start = max(0, line_no - context - 1)
        end = min(len(lines), line_no + context)
        result = []
        for i in range(start, end):
            prefix = ">>>" if i == line_no - 1 else "   "
            result.append(f"{prefix} {i+1}: {lines[i]}")
        return "\n".join(result)

    def suggest_fix_command(self, error_text: str) -> str | None:
        if "ModuleNotFoundError" in error_text or "ImportError" in error_text:
            m = re.search(r"'(.*?)'", error_text)
            if m:
                return f"pip install {m.group(1)}"
        if "SyntaxError" in error_text and "unterminated" in error_text.lower():
            return "Check for missing closing quotes, brackets, or parentheses."
        if "FileNotFoundError" in error_text:
            return "Check file path existence. Use Path.exists() before opening."
        if "TypeError" in error_text and "NoneType" in error_text:
            return "A function returned None unexpectedly. Check if the return value is being assigned correctly."
        if "KeyError" in error_text:
            return "Use dict.get(key) instead of dict[key] for safe access, or check if the key exists first."
        return None
