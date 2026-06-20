import re
from pathlib import Path
from typing import Optional


class EvidenceCollector:
    def __init__(self, project_root: str | Path):
        self.project_root = Path(project_root)

    def collect(self, prompt: str) -> dict:
        """Find and read files relevant to the user's request."""
        evidence = {
            "files_read": [],
            "file_contents": {},
            "error_logs": [],
            "findings": [],
            "summary": "",
        }
        p = prompt.lower()

        # 1. Find error logs or stack traces in the prompt
        evidence["error_logs"] = self._extract_errors(prompt)

        # 2. Find specific file paths mentioned
        mentioned_files = self._find_mentioned_files(prompt)
        for f in mentioned_files:
            content = self._read_file(f)
            if content is not None:
                evidence["files_read"].append(f)
                evidence["file_contents"][f] = content

        # 3. Search for files matching keywords
        keywords = self._extract_keywords(prompt)
        matched = self._search_files(keywords, exclude=mentioned_files)
        for f, content in matched.items():
            evidence["files_read"].append(f)
            evidence["file_contents"][f] = content

        # 4. Build summary
        evidence["findings"] = self._analyze(evidence)
        evidence["summary"] = self._summarize(evidence)
        return evidence

    def _extract_errors(self, prompt: str) -> list[str]:
        errors = []
        patterns = [
            r"Error:\s*(.+?)[\n\r]",
            r"Traceback.*?:\s*(.+?)[\n\r]",
            r"Exception:\s*(.+?)[\n\r]",
            r"Failed:\s*(.+?)[\n\r]",
            r"lỗi:\s*(.+?)[\n\r]",
        ]
        for pat in patterns:
            errors.extend(m.group(0).strip() for m in re.finditer(pat, prompt, re.IGNORECASE))
        return errors

    def _find_mentioned_files(self, prompt: str) -> list[str]:
        files = []
        pat = r'(?:file|đường dẫn|path|src|import|require|from)\s+["\']?([\w./\\-]+\.[a-zA-Z]+)["\']?'
        for m in re.finditer(pat, prompt, re.IGNORECASE):
            path = m.group(1).strip()
            if self._exists(path):
                files.append(path)
        return list(set(files))

    def _extract_keywords(self, prompt: str) -> list[str]:
        stopwords = {"và", "của", "cho", "với", "các", "một", "những", "được", "có",
                     "the", "a", "an", "in", "on", "at", "to", "for", "of", "with", "is"}
        words = re.findall(r'\b[a-zA-Z_]\w{2,}\b', prompt)
        return [w.lower() for w in words if w.lower() not in stopwords][:10]

    def _search_files(self, keywords: list[str], exclude: list[str] | None = None) -> dict[str, str]:
        if not keywords:
            return {}
        exclude = exclude or []
        results = {}
        exts = {".py", ".js", ".ts", ".html", ".css", ".json", ".toml",
                ".jsx", ".tsx", ".vue", ".go", ".java", ".rs", ".rb", ".php"}
        try:
            for ext in exts:
                for f in self.project_root.rglob(f"*{ext}"):
                    if f.name.startswith(".") or ".git" in str(f) or ".orca" in str(f):
                        continue
                    rel = str(f.relative_to(self.project_root))
                    if rel in exclude:
                        continue
                    try:
                        content = f.read_text(encoding="utf-8", errors="ignore")[:2000]
                        content_lower = content.lower()
                        score = sum(1 for kw in keywords if kw in content_lower)
                        if score >= 2:
                            results[rel] = content
                            if len(results) >= 5:
                                return results
                    except (OSError, UnicodeDecodeError):
                        continue
        except OSError:
            pass
        return results

    def _read_file(self, path: str) -> Optional[str]:
        candidates = [
            self.project_root / path,
            self.project_root / "src" / path,
            self.project_root / "app" / path,
        ]
        for p in candidates:
            if p.exists() and p.is_file():
                try:
                    return p.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    return None
        return None

    def _exists(self, path: str) -> bool:
        candidates = [
            self.project_root / path,
            self.project_root / "src" / path,
            self.project_root / "app" / path,
        ]
        return any(p.exists() for p in candidates)

    def _analyze(self, evidence: dict) -> list[str]:
        findings = []
        if evidence["error_logs"]:
            findings.append(f"Phát hiện {len(evidence['error_logs'])} error log(s). Cần phân tích stack trace.")
        if evidence["files_read"]:
            findings.append(f"Đã tìm thấy {len(evidence['files_read'])} file liên quan.")
        return findings

    def _summarize(self, evidence: dict) -> str:
        parts = []
        if evidence["error_logs"]:
            parts.append(f"Error logs: {len(evidence['error_logs'])}")
        if evidence["files_read"]:
            parts.append(f"Files read: {', '.join(evidence['files_read'][:5])}")
        return " | ".join(parts) if parts else "No evidence collected"