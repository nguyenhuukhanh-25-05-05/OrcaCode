"""Code Quality Checkers — deterministic quality analysis.

Architecture Rules, Complexity Budget, Refactor Debt Tracker, Duplicate Detector.
All deterministic, 100% stable, no LLM calls.
"""
from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from core.services.signal import Signal, Priority

logger = logging.getLogger("orca.quality")


# ── Shared Types ──────────────────────────────────────────────────────

# ── Weight penalty map ─────────────────────────────────────────────

QUALITY_WEIGHTS: dict[str, int] = {
    "architecture": -30,
    "duplicate":    -20,
    "complexity":   -10,
    "debt":          -5,
    "design":        -2,
}

QUALITY_CHECKER_LABELS: dict[str, str] = {
    "architecture": "Architecture",
    "duplicate":    "Duplicate",
    "complexity":   "Complexity",
    "debt":         "Debt",
    "design":       "Design",
}


@dataclass
class QualityIssue:
    """Một vấn đề chất lượng code phát hiện được."""
    checker: str       # "architecture", "complexity", "debt", "duplicate", "design"
    severity: str      # "error", "warning", "info"
    message: str
    file_path: str = ""
    line: int = 0
    symbol: str = ""

    @property
    def weight(self) -> int:
        """Điểm penalty cho issue này (âm)."""
        return QUALITY_WEIGHTS.get(self.checker, -5)


@dataclass
class QualityReport:
    """Tổng hợp tất cả quality issues cho một iteration.

    Score tính theo weighted penalty:
      - Architecture violation: -30 mỗi issue
      - Duplicate block:        -20
      - Complexity violation:   -10
      - Debt increase:          -5
      - Design warning:         -2

    Score range: 0-100. Start = 100, subtract each penalty.
    """
    issues: list[QualityIssue] = field(default_factory=list)
    score: int = 100  # 0-100
    iteration: int = 0

    def compute_score(self) -> int:
        """Base 100, trừ weighted penalty."""
        penalty = sum(i.weight for i in self.issues)
        self.score = max(0, 100 + penalty)
        return self.score

    def has_issues(self) -> bool:
        return len(self.issues) > 0

    def has_errors(self) -> bool:
        return any(i.severity == "error" for i in self.issues)

    def breakdown(self) -> list[tuple[str, int]]:
        """[(checker, total_penalty), ...] aggregated by checker."""
        from collections import defaultdict
        totals: dict[str, int] = defaultdict(int)
        for issue in self.issues:
            totals[issue.checker] += issue.weight
        return sorted(totals.items(), key=lambda x: x[1])

    def summary(self) -> str:
        if not self.issues:
            return f"  [OK] Code quality: {self.score}/100 (OK)"
        parts = [f"  📊 Quality Score: {self.score}/100"]
        by_checker = self.breakdown()
        for checker, penalty in by_checker:
            label = QUALITY_CHECKER_LABELS.get(checker, checker)
            count = sum(1 for i in self.issues if i.checker == checker)
            icon = "[ERR]" if penalty <= -30 else "[WARN]" if penalty <= -10 else "ℹ️"
            parts.append(f"    {icon} {label}: {count} issue(s) → {penalty}")
        return "\n".join(parts)

    def to_signals(self) -> list[Signal]:
        """Convert issues → observation-only Signal objects.

        Detector chỉ cung cấp category + observation + evidence_level + confidence.
        Priority do SignalRanker gán — không set ở đây.
        """
        _EVIDENCE_MAP: dict[str, int] = {
            "architecture": 1,  # structural
            "duplicate":    0,  # heuristic
            "complexity":   0,  # heuristic
            "debt":         0,  # heuristic
            "design":       0,  # heuristic
        }
        if not self.issues:
            return []
        signals: list[Signal] = []
        for issue in self.issues:
            evidence = _EVIDENCE_MAP.get(issue.checker, 0)
            signals.append(Signal(
                category=issue.checker,
                evidence_level=evidence,
                observation=issue.message,
                detail=f"{issue.file_path}:{issue.line}" if issue.file_path else "",
                confidence=0.9 if issue.severity == "error" else 0.7,
                severity_hint=0.7 if issue.severity == "error" else 0.4,
            ))
        return signals


# ══════════════════════════════════════════════════════════════════════
# 1. Architecture Rules
# ══════════════════════════════════════════════════════════════════════

class ArchitectureRules:
    """Kiểm tra file imports vi phạm layering rules.

    Rules mặc định:
      - core/domain/  không được import core/infra/
      - core/domain/  không được import core/ui/
      - core/service/ không được import core/ui/
      - core/models/  không được import core/agent/

    Usage:
        ar = ArchitectureRules()
        ar.load_default_rules()
        issues = ar.check("core/agent.py", "from core.models import X")
    """

    def __init__(self):
        self._rules: list[tuple[re.Pattern, re.Pattern]] = []
        self._loaded = False

    def load_default_rules(self) -> None:
        """Load rules mặc định (phù hợp project Python DDD-style)."""
        self._rules = [
            # domain/ không import infra/
            (re.compile(r"^core/domain/"), re.compile(r"^core/infra/")),
            # domain/ không import ui/
            (re.compile(r"^core/domain/"), re.compile(r"^core/ui/|^core/tui/")),
            # domain/ không import services/
            (re.compile(r"^core/domain/"), re.compile(r"^core/services/")),
            # service/ không import ui/
            (re.compile(r"^core/services/"), re.compile(r"^core/ui/|^core/tui/")),
            # models/ không import agent/
            (re.compile(r"^core/models/"), re.compile(r"^core/agent/")),
            # evidence/ không import agent/
            (re.compile(r"^core/evidence/"), re.compile(r"^core/agent/")),
            # domain/ không import services/
            (re.compile(r"^core/domain/"), re.compile(r"^core/viewmodels/")),
            # viewmodels/ không import ui/tui
            (re.compile(r"^core/viewmodels/"), re.compile(r"^core/ui/|^core/tui/")),
        ]
        self._loaded = True

    def add_rule(self, source_pattern: str, target_pattern: str) -> None:
        """Add custom rule. Patterns are regex strings."""
        self._rules.append((re.compile(source_pattern), re.compile(target_pattern)))

    def check_file(self, file_path: str, content: str) -> list[QualityIssue]:
        """Check một file có vi phạm architecture rules không."""
        if not self._loaded:
            self.load_default_rules()

        issues: list[QualityIssue] = []

        # Strip comments trước — tránh false positive từ docstring/ví dụ
        no_comments = re.sub(r'#.*$', '', content, flags=re.MULTILINE)

        # Extract imports (chỉ từ dòng bắt đầu bằng import/from)
        import_pattern = re.compile(r'^(?:from\s+(\S+)\s+import|import\s+(\S+))', re.MULTILINE)
        for m in import_pattern.finditer(no_comments):
            imp = m.group(1) or m.group(2)
            if not imp or imp.startswith("."):
                continue
            # Normalize: core.models.agent → core/models/agent
            imp_path = imp.replace(".", "/")

            # Check against rules
            for src_re, tgt_re in self._rules:
                if src_re.search(file_path) and tgt_re.search(imp_path):
                    issues.append(QualityIssue(
                        checker="architecture",
                        severity="error",
                        message=f"Observed import: {file_path} → {imp}",
                        file_path=file_path,
                        line=content[:m.start()].count("\n") + 1,
                    ))
                    break  # One violation per import

        return issues

    def check_all(self, project_root: Path, modified_files: set[str]) -> list[QualityIssue]:
        """Check tất cả modified files."""
        all_issues: list[QualityIssue] = []
        for f in modified_files:
            try:
                content = (project_root / f).read_text(encoding="utf-8", errors="replace")
                all_issues.extend(self.check_file(f, content))
            except Exception:
                pass
        return all_issues


# ══════════════════════════════════════════════════════════════════════
# 2. Complexity Budget
# ══════════════════════════════════════════════════════════════════════

class ComplexityBudget:
    """Kiểm tra độ phức tạp của function.

    Checks:
      - Cyclomatic complexity (McCabe) > threshold → warning
      - Function lines > threshold → warning
      - Too many parameters > threshold → info
    """

    MAX_COMPLEXITY = 15
    MAX_LINES = 80
    MAX_PARAMS = 8

    def check_file(self, file_path: str, content: str) -> list[QualityIssue]:
        """Check complexity of all functions in a file."""
        if not file_path.endswith(".py"):
            return self._check_js_file(file_path, content)
        return self._check_python_file(file_path, content)

    def _check_python_file(self, file_path: str, content: str) -> list[QualityIssue]:
        """Check Python file complexity via AST."""
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return []

        issues: list[QualityIssue] = []
        lines = content.split("\n")

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_lines = (getattr(node, 'end_lineno', node.lineno) or node.lineno) - node.lineno + 1
                complexity = self._compute_cyclomatic(node)

                if func_lines > self.MAX_LINES:
                    issues.append(QualityIssue(
                        checker="complexity",
                        severity="warning",
                        message=f"Function {node.name}: {func_lines} lines",
                        file_path=file_path, line=node.lineno, symbol=node.name,
                    ))
                if complexity > self.MAX_COMPLEXITY:
                    issues.append(QualityIssue(
                        checker="complexity",
                        severity="warning",
                        message=f"Function {node.name}: cyclomatic_complexity={complexity}",
                        file_path=file_path, line=node.lineno, symbol=node.name,
                    ))
                if node.args and len(node.args.args) > self.MAX_PARAMS:
                    issues.append(QualityIssue(
                        checker="complexity",
                        severity="info",
                        message=f"Function {node.name}: {len(node.args.args)} params",
                        file_path=file_path, line=node.lineno, symbol=node.name,
                    ))

            elif isinstance(node, ast.ClassDef):
                class_lines = (getattr(node, 'end_lineno', node.lineno) or node.lineno) - node.lineno + 1
                if class_lines > self.MAX_LINES * 2:
                    issues.append(QualityIssue(
                        checker="complexity",
                        severity="warning",
                        message=f"Class {node.name}: {class_lines} lines",
                        file_path=file_path, line=node.lineno, symbol=node.name,
                    ))

        return issues

    def _compute_cyclomatic(self, node: ast.AST) -> int:
        """McCabe cyclomatic complexity: 1 + number of decision points."""
        decisions = 0
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor)):
                decisions += 1
            elif isinstance(child, ast.ExceptHandler):
                decisions += 1
            elif isinstance(child, ast.BoolOp):
                # AND/OR each add complexity
                decisions += len(child.values) - 1
            elif isinstance(child, ast.Assert):
                decisions += 1
        return 1 + decisions

    def _check_js_file(self, file_path: str, content: str) -> list[QualityIssue]:
        """Basic JS/TS complexity check via regex."""
        issues: list[QualityIssue] = []
        lines = content.split("\n")

        func_re = re.compile(r'(?:function\s+(\w+)|(\w+)\s*=\s*(?:async\s+)?function|(\w+)\s*:\s*(?:async\s+)?\()')
        for lineno, line in enumerate(lines, 1):
            fm = func_re.search(line)
            if fm:
                name = fm.group(1) or fm.group(2) or fm.group(3)
                # Count lines in function (approximate)
                func_end = self._find_block_end(lines, lineno)
                func_len = func_end - lineno + 1
                if func_len > self.MAX_LINES:
                    issues.append(QualityIssue(
                        checker="complexity",
                        severity="warning",
                        message=f"Function {name}: ~{func_len} lines",
                        file_path=file_path, line=lineno, symbol=name,
                    ))

        return issues

    def _find_block_end(self, lines: list[str], start: int) -> int:
        """Find matching closing brace for block starting at start (1-indexed)."""
        depth = 0
        for i in range(start - 1, len(lines)):
            depth += lines[i].count("{") - lines[i].count("}")
            if depth <= 0 and i > start - 1:
                return i + 1
        return len(lines)


# ══════════════════════════════════════════════════════════════════════
# 3. Refactor Debt Tracker
# ══════════════════════════════════════════════════════════════════════

_DEBT_PATTERNS = [
    (re.compile(r'\bTODO\b'), "todo"),
    (re.compile(r'\bFIXME\b'), "fixme"),
    (re.compile(r'\bHACK\b'), "hack"),
    (re.compile(r'\bWORKAROUND\b'), "workaround"),
    (re.compile(r'\bXXX\b'), "xxx"),
    (re.compile(r'\bTEMP\b'), "temp"),
    (re.compile(r'\bHARDCODED\b'), "hardcoded"),
    (re.compile(r'\bMAGIC\s+NUMBER\b'), "magic_number"),
    (re.compile(r'#\s*TODO'), "todo_comment"),
    (re.compile(r'//\s*TODO'), "todo_comment_js"),
    (re.compile(r'<!--\s*TODO'), "todo_comment_html"),
]


@dataclass
class DebtCount:
    total: int = 0
    by_type: dict[str, int] = field(default_factory=dict)


class RefactorDebtTracker:
    """Đếm số lượng TODO/FIXME/HACK/WORKAROUND trong codebase.

    Usage:
        tracker = RefactorDebtTracker()
        debts = tracker.scan_file("core/service.py", content)
        total = tracker.get_total()
        if total > previous_total + 5:
            warning("Technical debt increasing!")
    """

    def __init__(self):
        self._baseline: dict[str, DebtCount] = {}

    def scan_file(self, file_path: str, content: str) -> DebtCount:
        """Đếm tất cả debt markers trong một file."""
        dc = DebtCount()
        for pattern, dtype in _DEBT_PATTERNS:
            count = len(pattern.findall(content))
            if count:
                dc.by_type[dtype] = dc.by_type.get(dtype, 0) + count
                dc.total += count
        return dc

    def scan_files(self, modified_files: set[str], project_root: Path) -> list[QualityIssue]:
        """Scan modified files và trả về issues nếu debt tăng so với baseline."""
        issues: list[QualityIssue] = []
        for f in modified_files:
            try:
                content = (project_root / f).read_text(encoding="utf-8", errors="replace")
                dc = self.scan_file(f, content)
                dc_old = self._baseline.get(f, DebtCount())
                if dc.total > dc_old.total:
                    added = dc.total - dc_old.total
                    issues.append(QualityIssue(
                        checker="debt",
                        severity="warning" if added > 2 else "info",
                        message=f"Debt markers in {f}: {dc.total} ({added} new)",
                        file_path=f,
                    ))
                self._baseline[f] = dc
            except Exception:
                pass
        return issues


# ══════════════════════════════════════════════════════════════════════
# 4. Duplicate Detector
# ══════════════════════════════════════════════════════════════════════

class DuplicateDetector:
    """Phát hiện function/class giống nhau giữa các file.

    Dùng structural fingerprinting (normalized AST hash).
    Không so sánh text — so sánh cấu trúc, nên đổi tên biến vẫn phát hiện được.
    """

    SIMILARITY_THRESHOLD = 0.80  # 80%+ overlap = duplicate

    def __init__(self):
        self._fingerprints: dict[str, list[tuple[str, str, int, int]]] = {}
        """{file_path: [(func_name, fingerprint, line, body_lines)]}"""

    def scan_file(self, file_path: str, content: str) -> None:
        """Scan file, compute fingerprints cho mọi function."""
        if file_path.endswith(".py"):
            entries = self._scan_python(file_path, content)
        elif file_path.endswith((".js", ".ts", ".jsx", ".tsx")):
            entries = self._scan_js(file_path, content)
        else:
            return
        self._fingerprints[file_path] = entries

    def find_duplicates(self, file_path: str, content: str) -> list[QualityIssue]:
        """Tìm duplicates giữa file này và tất cả file đã scan trước đó."""
        issues: list[QualityIssue] = []

        # Scan current file
        if file_path.endswith(".py"):
            current = self._scan_python(file_path, content)
        elif file_path.endswith((".js", ".ts", ".jsx", ".tsx")):
            current = self._scan_js(file_path, content)
        else:
            return issues
        self._fingerprints[file_path] = current

        # Compare against all existing fingerprints
        for name, fp, line, body_len in current:
            if body_len < 3:
                continue  # Skip tiny functions
            for other_fp, other_entries in self._fingerprints.items():
                if other_fp == file_path:
                    continue
                for other_name, other_fp_str, other_line, other_len in other_entries:
                    if other_len < 3:
                        continue
                    similarity = self._jaccard_similarity(fp, other_fp_str)
                    if similarity >= self.SIMILARITY_THRESHOLD:
                        issues.append(QualityIssue(
                            checker="duplicate",
                            severity="warning",
                            message=f"Similarity={similarity:.0%}: {name} ↔ {other_name} ({other_fp}:{other_line})",
                            file_path=file_path, line=line, symbol=name,
                        ))
                        # Only report once per pair
                        break

        return issues

    # ── Python AST fingerprinting ──

    def _is_descriptive_enough(self, node: ast.FunctionDef) -> bool:
        """Filter out functions too small or generic for duplicate detection.

        - Dunder methods (__init__, __repr__, etc.) are boilerplate
        - Body < 5 AST nodes or < 3 source lines is too generic
        """
        if node.name.startswith("__") and node.name.endswith("__"):
            return False
        body_nodes = len(node.body)
        if body_nodes < 3:
            return False
        end_line = getattr(node, 'end_lineno', node.lineno) or node.lineno
        body_lines = end_line - node.lineno
        if body_lines < 3:
            return False
        return True

    def _scan_python(self, file_path: str, content: str) -> list[tuple[str, str, int, int]]:
        """Trích xuất function fingerprints từ Python file."""
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return []
        entries: list[tuple[str, str, int, int]] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not self._is_descriptive_enough(node):
                    continue
                fp = self._compute_fingerprint(node)
                body_len = (getattr(node, 'end_lineno', node.lineno) or node.lineno) - node.lineno
                entries.append((node.name, fp, node.lineno, body_len))
        return entries

    def _compute_fingerprint(self, node: ast.FunctionDef) -> str:
        """Compute structural fingerprint: normalize names, keep structure."""
        class Normalizer(ast.NodeTransformer):
            def visit_Name(self, n):
                n.id = "_"
                return n
            def visit_FunctionDef(self, n):
                n.name = "_"
                return self.generic_visit(n)
            def visit_ClassDef(self, n):
                n.name = "_"
                return self.generic_visit(n)
            def visit_arg(self, n):
                n.arg = "_"
                return n
            def visit_Attribute(self, n):
                n.attr = "_"
                return self.generic_visit(n)

        normalizer = Normalizer()
        copy = ast.copy_location(normalizer.visit(node), node)
        try:
            return ast.dump(copy, indent=0)
        except Exception:
            return ""

    # ── JS/TS fingerprinting (basic) ──

    def _scan_js(self, file_path: str, content: str) -> list[tuple[str, str, int, int]]:
        """Basic JS fingerprint — normalize identifiers, compare structure."""
        entries: list[tuple[str, str, int, int]] = []
        func_re = re.compile(r'(?:function\s+(\w+)|(\w+)\s*=\s*(?:async\s+)?(?:function)?\s*\()')
        for m in func_re.finditer(content):
            name = m.group(1) or m.group(2)
            # Normalize: replace all word tokens with _
            normalized = re.sub(r'\b[a-zA-Z_]\w*\b', '_', m.string[m.start():m.start()+200])
            entries.append((name, normalized[:100], content[:m.start()].count("\n") + 1, 0))
        return entries

    @staticmethod
    def _jaccard_similarity(a: str, b: str) -> float:
        """Jaccard similarity of bigram sets."""
        if not a or not b:
            return 0.0
        def bigrams(s: str) -> set[str]:
            return {s[i:i+2] for i in range(len(s)-1)}
        set_a, set_b = bigrams(a), bigrams(b)
        if not set_a or not set_b:
            return 0.0
        return len(set_a & set_b) / len(set_a | set_b)


# ══════════════════════════════════════════════════════════════════════
# 5. Unified CodeQuality Checker
# ══════════════════════════════════════════════════════════════════════

class CodeQualityChecker:
    """Unified interface — chạy tất cả deterministic checkers.

    Tracks quality score history across iterations for trend detection.

    Usage:
        cqc = CodeQualityChecker()
        report = cqc.check_all(project_root, modified_files, iteration=42)
        print(f"Score: {report.score}/100")
        print(f"Trend: {cqc.trend_text}")
    """

    def __init__(self):
        self.architecture = ArchitectureRules()
        self.complexity = ComplexityBudget()
        self.debt_tracker = RefactorDebtTracker()
        self.duplicate_detector = DuplicateDetector()
        self._previous_debt_total: int = 0
        # Quality score history: {iteration: score}
        self._score_history: dict[int, int] = {}
        self._trend_text: str = ""

    @property
    def score_history(self) -> dict[int, int]:
        return dict(self._score_history)

    @property
    def trend_text(self) -> str:
        return self._trend_text

    def _update_trend(self, current_iteration: int) -> None:
        """Cập nhật trend text dựa trên history."""
        scores = sorted(self._score_history.items())
        if len(scores) < 3:
            if len(scores) == 1:
                self._trend_text = f"Quality score: {scores[0][1]}/100"
            return

        recent = [s for i, s in scores if i >= current_iteration - 50]
        if not recent:
            recent = [s for _, s in scores[-10:]]

        current = recent[-1]
        first = recent[0]
        # DECLINING: giảm >= 15 so với 50 iteration trước
        if current < first - 14:
            self._trend_text = (
                f"Quality score: {current}/100 (⬇️ giảm {first - current} điểm trong "
                f"{min(50, len(recent))} iterations — codebase đang mục dần)"
            )
        # FLATLINE under 60
        elif len(recent) >= 5 and all(s < 60 for s in recent[-5:]) and max(recent[-5:]) - min(recent[-5:]) <= 10:
            self._trend_text = f"Quality score: {current}/100 ([WARN] stuck dưới 60 — cần cải thiện)"
        # IMPROVING: tăng >= 10 trong gần đây
        elif len(recent) >= 5 and current > recent[-5] + 9:
            self._trend_text = f"Quality score: {current}/100 (đang cải thiện)"
        else:
            self._trend_text = f"Quality score: {current}/100"

    def format_trend_context(self) -> str:
        """Format quality trend for context injection.

        Example:
          📊 Quality Score Trend:
            Iter 20 → 92/100
            Iter 50 → 89/100
            Iter 100 → 85/100
            Iter 200 → 71/100 ⬇️ giảm 21 điểm — codebase đang mục dần
        """
        if not self._score_history:
            return ""
        scores = sorted(self._score_history.items())
        lines = ["📊 Quality Score Trend:"]
        # Show milestones
        for i, s in scores:
            if i <= 10 or i % 50 == 0 or i == scores[-1][0]:
                marker = " ⬅️ current" if i == scores[-1][0] else ""
                lines.append(f"  Iter {i:>4} → {s}/100{marker}")
        if self._trend_text:
            lines.append(f"  {self._trend_text}")
        return "\n".join(lines)

    def check_all(self, project_root: Path, modified_files: set[str], iteration: int = 0) -> QualityReport:
        """Chạy tất cả checkers trên modified files.

        Vẫn quét duplicate trên toàn bộ codebase (scan files duy nhất một lần).
        """
        report = QualityReport()
        report.iteration = iteration

        try:
            issues = self.architecture.check_all(project_root, modified_files)
            report.issues.extend(issues)
        except Exception:
            pass

        for f in modified_files:
            try:
                content = (project_root / f).read_text(encoding="utf-8", errors="replace")
                issues = self.complexity.check_file(f, content)
                report.issues.extend(issues)
            except Exception:
                pass

        try:
            debt_issues = self.debt_tracker.scan_files(modified_files, project_root)
            report.issues.extend(debt_issues)
        except Exception:
            pass

        for f in modified_files:
            try:
                content = (project_root / f).read_text(encoding="utf-8", errors="replace")
                # Scan file for fingerprinting (happens once)
                self.duplicate_detector.scan_file(f, content)
            except Exception:
                pass

        for f in modified_files:
            try:
                content = (project_root / f).read_text(encoding="utf-8", errors="replace")
                dup_issues = self.duplicate_detector.find_duplicates(f, content)
                report.issues.extend(dup_issues)
            except Exception:
                pass

        report.compute_score()
        # Record score history
        if report.iteration > 0:
            self._score_history[report.iteration] = report.score
            self._update_trend(report.iteration)
        return report
