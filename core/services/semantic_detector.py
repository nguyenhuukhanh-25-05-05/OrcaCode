"""Semantic Damage Detector — phát hiện function/class bị xoá hoặc đổi signature.

So sánh AST trước và sau khi write. Syntax OK nhưng thiếu function → DETECTED.
"""
from __future__ import annotations

import ast
import logging
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("orca.semantic")


@dataclass
class SymbolDef:
    """Một symbol (function/class/...) trong source code."""
    name: str
    kind: str          # "function", "class", "method", "async_function", "const", "export"
    params: int = 0     # Tổng số parameters (cho function)
    optional_params: int = 0  # Số params có default value (trailing)
    line_start: int = 0
    line_end: int = 0
    parent: str = ""    # Class name nếu là method

    def required_params(self) -> int:
        return self.params - self.optional_params

    def signature_key(self) -> str:
        return f"{self.kind}:{self.name}:{self.required_params}"


@dataclass
class FileSymbols:
    """Tất cả symbols trong một file."""
    path: str
    symbols: list[SymbolDef] = field(default_factory=list)

    def by_name(self) -> dict[str, SymbolDef]:
        return {s.name: s for s in self.symbols}

    def by_kind(self, kind: str) -> list[SymbolDef]:
        return [s for s in self.symbols if s.kind == kind]

    def count(self) -> int:
        return len(self.symbols)


@dataclass
class ChangeRecord:
    """Một thay đổi duy nhất: delete / rename / param_removed / param_added_optional / param_added_required / signature_changed."""
    change_type: str  # "deleted", "renamed", "param_removed", "param_added_optional", "param_added_required", "param_added", "signature_changed"
    old_sym: SymbolDef
    new_sym: Optional[SymbolDef] = None
    file_path: str = ""


@dataclass
class SemanticIssue:
    """Một vấn đề semantic phát hiện được."""
    severity: str       # "error", "warning"
    message: str
    symbol_name: str
    kind: str
    file_path: str
    change_type: str = ""  # "deleted", "export_removed", ...


class SemanticDamageResult:
    """Kết quả scan semantic damage + risk scoring.

    Risk Score Formula:
      Symbol weights:
        exported_symbol   +50  (name không bắt đầu _)
        public_class      +30  (kind == class)
        entrypoint        +60  (name == run/main/start/execute/serve/launch…)
        public_method     +20  (kind == method, parent public)

      Change weights:
        DELETE_SYMBOL           +40
        RENAME_SYMBOL           +35
        PARAM_REMOVED           +25
        PARAM_ADDED_REQUIRED    +25
        PARAM_ADDED_OPTIONAL    +5
        SIGNATURE_CHANGED       +15

      Affected score: min(30, affected_files)

    Thresholds:
      >= 90  CRITICAL → block DONE
      >= 60  HIGH     → block DONE
      >= 30  MEDIUM   → warn
      < 30   LOW      → info
    """
    def __init__(self):
        self.issues: list[SemanticIssue] = []
        self.changes: list[ChangeRecord] = []  # Unified change list
        # Legacy accessors (populated from changes)
        self.deleted: list[SymbolDef] = []
        self.changed_signatures: list[tuple[SymbolDef, SymbolDef]] = []
        self.new_symbols: list[SymbolDef] = []
        # Call-site risk
        self.affected_files: set[str] = set()
        self.risk_score: int = 0
        self.risk_level: str = "LOW"
        self.symbol_callers: dict[str, list] = {}  # Symbol-level: name → callers

    _ENTRYPOINT_NAMES = {"run", "main", "start", "execute", "serve", "launch", "boot", "entry"}

    @property
    def has_damage(self) -> bool:
        if self.changes:
            return True
        for i in self.issues:
            if getattr(i, "change_type", "") == "export_removed":
                return True
        return False

    @property
    def summary(self) -> str:
        lines = []
        if self.risk_level == "CRITICAL":
            lines.append(f"  🚨 CRITICAL (score={self.risk_score}) — public contract break")
        elif self.risk_level == "HIGH":
            lines.append(f"  [WARN] HIGH (score={self.risk_score}) — widespread impact")
        elif self.risk_level == "MEDIUM":
            lines.append(f"  [WARN] MEDIUM (score={self.risk_score}) — limited impact")
        for c in self.changes:
            icon = {"deleted": "[ERR]", "renamed": "🏷️", "param_removed": "[WARN]", "param_added": "ℹ️", "param_added_required": "[WARN]", "param_added_optional": "ℹ️", "signature_changed": "[WARN]"}.get(c.change_type, "•")
            if c.change_type == "deleted":
                lines.append(f"  {icon} DELETED {c.old_sym.kind} '{c.old_sym.name}'")
            elif c.change_type == "renamed":
                lines.append(f"  {icon} RENAMED {c.old_sym.kind} '{c.old_sym.name}' → '{c.new_sym.name if c.new_sym else '?'}'")
            elif c.change_type in ("param_removed", "param_added", "param_added_required", "param_added_optional", "signature_changed"):
                old_p = c.old_sym.params
                new_p = c.new_sym.params if c.new_sym else 0
                old_r = c.old_sym.required_params()
                new_r = c.new_sym.required_params() if c.new_sym else 0
                if c.change_type == "param_added_optional":
                    lines.append(f"  {icon} ADDED OPTIONAL {c.old_sym.kind} '{c.old_sym.name}': {old_r} req +{new_r - old_r} opt ({old_p}→{new_p})")
                elif c.change_type == "param_added_required":
                    lines.append(f"  {icon} ADDED REQUIRED {c.old_sym.kind} '{c.old_sym.name}': {old_p}→{new_p} params (+{new_r - old_r} required)")
                else:
                    lines.append(f"  {icon} {c.change_type.upper()} {c.old_sym.kind} '{c.old_sym.name}': {old_p} → {new_p} params")
        # Export removal issues (from API registry)
        for i in self.issues:
            if getattr(i, "change_type", "") == "export_removed":
                lines.append(f"  🚫 EXPORT REMOVED '{i.symbol_name}' ({i.kind}) — was public API")
        # Symbol-level call sites
        for sym_name, callers in self.symbol_callers.items():
            by_file: dict[str, list] = {}
            for c in callers:
                by_file.setdefault(c.caller_file, []).append(c.caller_name)
            parts = [f"{f} ({', '.join(sorted(set(n)))[:3]})" for f, n in sorted(by_file.items())[:3]]
            extra = f" ... +{len(by_file) - 3}" if len(by_file) > 3 else ""
            lines.append(f"  📞 '{sym_name}' called by {len(callers)}× in {len(by_file)} files: {'; '.join(parts)}{extra}")
        if self.affected_files:
            sorted_af = sorted(self.affected_files)[:5]
            extra = f" ... +{len(self.affected_files) - 5}" if len(self.affected_files) > 5 else ""
            lines.append(f"  📦 Affected files: {len(self.affected_files)} — {', '.join(sorted_af)}{extra}")
        if self.new_symbols:
            for s in self.new_symbols[:5]:
                lines.append(f"  ➕ NEW {s.kind} '{s.name}'")
        return "\n".join(lines)

    @property
    def should_block(self) -> bool:
        if self.risk_level in ("CRITICAL", "HIGH"):
            return True
        for i in self.issues:
            if getattr(i, "change_type", "") == "export_removed":
                return True
        return False

    def analyze_call_site_risk(self, dep_graph, file_path: str = "", symbol_dep_graph=None) -> None:
        """Tính risk score với formula mới + call-site context.

        affected_score = min(30, affected_files)  # log scale
        change_weight  = DELETE +40 / RENAME +35 / PARAM_REMOVED +25 / PARAM_ADDED +10
        symbol_weight  = exported +50 / class +30 / entrypoint +60 / method_on_public_class +20

        Nếu symbol_dep_graph được cung cấp, thêm precision score:
        - Mỗi call site thực tế = +5 (thay vì flat file count)
        """
        score = 0
        affected: set[str] = set()
        self.symbol_callers: dict[str, list] = {}  # symbol_name → callers

        if not file_path:
            for issue in self.issues:
                if issue.file_path:
                    file_path = issue.file_path
                    break

        if file_path:
            try:
                deps = dep_graph.get_all_dependents(file_path, depth=1)
                affected.update(deps)
            except Exception:
                pass
        self.affected_files = affected

        # Log-scale affected score
        af_count = len(affected)
        affected_score = min(30, af_count)
        score += affected_score

        # Score từ mỗi change
        for c in self.changes:
            sym = c.old_sym
            name = sym.name

            # Symbol metadata weights
            if not name.startswith("_"):
                score += 50
            if sym.kind == "class":
                score += 30
            if name.lower() in self._ENTRYPOINT_NAMES:
                score += 60
            if sym.kind in ("method", "async_method") and sym.parent and not sym.parent.startswith("_"):
                score += 20

            # Change type weights
            if c.change_type == "deleted":
                score += 40
            elif c.change_type == "renamed":
                score += 35
            elif c.change_type == "param_removed":
                score += 25
            elif c.change_type == "param_added_required":
                score += 25
            elif c.change_type == "param_added_optional":
                score += 5
            elif c.change_type == "param_added":
                score += 10
            elif c.change_type == "signature_changed":
                score += 15

            # Symbol-level call-site precision score
            if symbol_dep_graph is not None:
                try:
                    callers = symbol_dep_graph.get_callers(name)
                    if callers:
                        self.symbol_callers[name] = callers
                        # +5 per actual call site, max 30
                        precision = min(30, len(callers))
                        score += precision
                except Exception:
                    pass

        self.risk_score = score

        if score >= 90:
            self.risk_level = "CRITICAL"
        elif score >= 60:
            self.risk_level = "HIGH"
        elif score >= 30:
            self.risk_level = "MEDIUM"
        else:
            self.risk_level = "LOW"


class SemanticDetector:
    """Phát hiện semantic damage bằng cách so sánh AST trước và sau write.

    Usage:
        sd = SemanticDetector()
        before = sd.extract_symbols("core/service.py", old_content)
        # ... AI writes new content ...
        after = sd.extract_symbols("core/service.py", new_content)
        result = sd.compare(before, after)
        if result.has_damage:
            print(result.summary)
    """

    def __init__(self):
        self._snapshots: dict[str, FileSymbols] = {}

    # ── Public API ──────────────────────────────────────────────────────

    def snapshot_before(self, file_path: str, content: str) -> Optional[FileSymbols]:
        """Capture symbol state trước khi write. Lưu vào cache để sau này compare."""
        symbols = self.extract_symbols(file_path, content)
        if symbols:
            self._snapshots[file_path] = symbols
        return symbols

    def check_after(self, file_path: str, new_content: str) -> Optional[SemanticDamageResult]:
        """So sánh state mới với snapshot. Trả về kết quả damage nếu có."""
        old = self._snapshots.pop(file_path, None)
        if old is None:
            return None
        new = self.extract_symbols(file_path, new_content)
        if new is None:
            return None
        return self.compare(old, new)

    def extract_symbols(self, file_path: str, content: str) -> Optional[FileSymbols]:
        """Parse file content và extract tất cả symbols."""
        ext = Path(file_path).suffix.lower()
        try:
            if ext == ".py":
                return self._extract_python(file_path, content)
            elif ext in (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"):
                return self._extract_js(file_path, content)
            else:
                return None
        except Exception as e:
            logger.debug("Symbol extraction failed for %s: %s", file_path, e)
            return None

    def compare(self, old: FileSymbols, new: FileSymbols) -> SemanticDamageResult:
        """So sánh symbols cũ và mới — phát hiện delete, rename, param change."""
        result = SemanticDamageResult()

        old_map = old.by_name()
        new_map = new.by_name()

        # Deletions + Renames
        deleted_names = set(old_map.keys()) - set(new_map.keys())
        added_names = set(new_map.keys()) - set(old_map.keys())

        for name in deleted_names:
            old_sym = old_map[name]
            if old_sym.kind not in ("function", "class", "method", "async_function"):
                continue

            # Detect rename: deleted + new symbol cùng kind xuất hiện
            renamed_to = None
            for added_name in added_names:
                new_sym = new_map[added_name]
                if new_sym.kind == old_sym.kind:
                    # Candidate rename — cùng kind
                    if old_sym.params == new_sym.params or abs(old_sym.params - new_sym.params) <= 1:
                        renamed_to = new_sym
                        break

            if renamed_to:
                added_names.discard(renamed_to.name)
                result.changes.append(ChangeRecord(
                    change_type="renamed",
                    old_sym=old_sym, new_sym=renamed_to,
                    file_path=old.path,
                ))
                result.deleted.append(old_sym)
                result.changed_signatures.append((old_sym, renamed_to))
                result.issues.append(SemanticIssue(
                    severity="error",
                    message=f"Renamed {old_sym.kind} '{old_sym.name}' → '{renamed_to.name}'",
                    symbol_name=old_sym.name, kind=old_sym.kind,
                    file_path=old.path,
                ))
            else:
                result.changes.append(ChangeRecord(
                    change_type="deleted",
                    old_sym=old_sym, file_path=old.path,
                ))
                result.deleted.append(old_sym)
                result.issues.append(SemanticIssue(
                    severity="error",
                    message=f"Deleted {old_sym.kind} '{old_sym.name}'",
                    symbol_name=old_sym.name, kind=old_sym.kind,
                    file_path=old.path,
                ))

        # Signature changes (param added/removed)
        for name, old_sym in old_map.items():
            new_sym = new_map.get(name)
            if new_sym and old_sym.params != new_sym.params:
                if old_sym.params > new_sym.params:
                    ct = "param_removed"
                    sev = "warning"
                else:
                    # Params added: check if all new params are optional
                    old_required = old_sym.required_params()
                    new_required = new_sym.required_params()
                    if new_required <= old_required and new_sym.optional_params > old_sym.optional_params:
                        ct = "param_added_optional"
                        sev = "info"
                    else:
                        ct = "param_added_required"
                        sev = "warning"
                result.changes.append(ChangeRecord(
                    change_type=ct, old_sym=old_sym, new_sym=new_sym,
                    file_path=old.path,
                ))
                result.changed_signatures.append((old_sym, new_sym))
                result.issues.append(SemanticIssue(
                    severity=sev,
                    message=f"{ct.upper()} {old_sym.kind} '{old_sym.name}': {old_sym.params}→{new_sym.params} params",
                    symbol_name=old_sym.name, kind=old_sym.kind,
                    file_path=old.path,
                ))

        # New symbols
        for name in added_names:
            result.new_symbols.append(new_map[name])

        return result

    def check_file_changes(self, file_path: str, old_content: str, new_content: str) -> Optional[SemanticDamageResult]:
        """Convenience: check semantic damage between old và new content trực tiếp, không qua cache."""
        old = self.extract_symbols(file_path, old_content)
        new = self.extract_symbols(file_path, new_content)
        if old is None or new is None:
            return None
        return self.compare(old, new)

    # ── Python parser ──────────────────────────────────────────────────

    def _extract_python(self, file_path: str, content: str) -> FileSymbols:
        """Parse Python symbol definitions using ast module."""
        tree = ast.parse(content)
        symbols = FileSymbols(path=file_path)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                total = len(node.args.args) if node.args else 0
                opt = len(node.args.defaults) if node.args else 0
                symbols.symbols.append(SymbolDef(
                    name=node.name,
                    kind="function",
                    params=total,
                    optional_params=opt,
                    line_start=node.lineno,
                    line_end=getattr(node, 'end_lineno', node.lineno),
                ))
            elif isinstance(node, ast.AsyncFunctionDef):
                total = len(node.args.args) if node.args else 0
                opt = len(node.args.defaults) if node.args else 0
                symbols.symbols.append(SymbolDef(
                    name=node.name,
                    kind="async_function",
                    params=total,
                    optional_params=opt,
                    line_start=node.lineno,
                    line_end=getattr(node, 'end_lineno', node.lineno),
                ))
            elif isinstance(node, ast.ClassDef):
                symbols.symbols.append(SymbolDef(
                    name=node.name,
                    kind="class",
                    params=0,
                    line_start=node.lineno,
                    line_end=getattr(node, 'end_lineno', node.lineno),
                ))
                # Extract methods inside class
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        kind = "method" if isinstance(item, ast.FunctionDef) else "async_method"
                        total_m = len(item.args.args) if item.args else 0
                        opt_m = len(item.args.defaults) if item.args else 0
                        symbols.symbols.append(SymbolDef(
                            name=item.name,
                            kind=kind,
                            params=total_m,
                            optional_params=opt_m,
                            line_start=item.lineno,
                            line_end=getattr(item, 'end_lineno', item.lineno),
                            parent=node.name,
                        ))

        return symbols

    # ── JS/TS parser ───────────────────────────────────────────────────

    # Regex patterns for JS/TS declarations
    _JS_FUNCTION_RE = re.compile(
        r'(?:export\s+)?(?:async\s+)?function\s+\*?\s*(\w+)\s*\(([^)]*)\)',
    )
    _JS_CLASS_RE = re.compile(
        r'(?:export\s+)?class\s+(\w+)\s*(?:extends\s+\w+)?\s*\{',
    )
    _JS_ARROW_RE = re.compile(
        r'(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(([^)]*)\)\s*=>',
    )
    _JS_METHOD_RE = re.compile(
        r'(?:async\s+)?(\w+)\s*\(([^)]*)\)\s*\{',
    )
    _JS_ARROW_NAMED_RE = re.compile(
        r'(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?function\s*\(([^)]*)\)',
    )

    def _extract_js(self, file_path: str, content: str) -> FileSymbols:
        """Parse JS/TS symbol definitions using regex + dedup."""
        symbols = FileSymbols(path=file_path)
        seen: dict[str, SymbolDef] = {}  # name → first occurrence

        def _add(name: str, kind: str, params: int, lineno: int) -> None:
            if name not in seen:
                sd = SymbolDef(name=name, kind=kind, params=params, line_start=lineno)
                seen[name] = sd
                symbols.symbols.append(sd)
            elif seen[name].kind == "method" and kind != "method":
                # Function declaration overrides method
                seen[name].kind = kind
                seen[name].params = params

        SKIP = {"if", "while", "for", "switch", "catch", "function", "return", "else", "try", "class"}

        # Functions: `function name(params)`
        for m in self._JS_FUNCTION_RE.finditer(content):
            lineno = content[:m.start()].count("\n") + 1
            name = m.group(1)
            if name in SKIP: continue
            params = len([p for p in m.group(2).split(",") if p.strip()]) if m.group(2).strip() else 0
            _add(name, "function", params, lineno)

        # Classes: `class Name {`
        for m in self._JS_CLASS_RE.finditer(content):
            lineno = content[:m.start()].count("\n") + 1
            _add(m.group(1), "class", 0, lineno)

        # Arrow functions: `const name = (params) =>`
        for m in self._JS_ARROW_RE.finditer(content):
            lineno = content[:m.start()].count("\n") + 1
            name = m.group(1)
            if name in SKIP: continue
            params = len([p for p in m.group(2).split(",") if p.strip()]) if m.group(2).strip() else 0
            _add(name, "function", params, lineno)

        # Named arrow: `const name = function(params)`
        for m in self._JS_ARROW_NAMED_RE.finditer(content):
            lineno = content[:m.start()].count("\n") + 1
            name = m.group(1)
            if name in SKIP: continue
            params = len([p for p in m.group(2).split(",") if p.strip()]) if m.group(2).strip() else 0
            _add(name, "function", params, lineno)

        # Methods: `name(params) { ... }` — chỉ thêm nếu chưa có
        for m in self._JS_METHOD_RE.finditer(content):
            lineno = content[:m.start()].count("\n") + 1
            name = m.group(1)
            if name in SKIP: continue
            params = len([p for p in m.group(2).split(",") if p.strip()]) if m.group(2).strip() else 0
            if name not in seen:
                seen[name] = SymbolDef(name=name, kind="method", params=params, line_start=lineno)
                symbols.symbols.append(seen[name])

        return symbols
