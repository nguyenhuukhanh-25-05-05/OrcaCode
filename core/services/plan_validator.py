"""Plan Validator – đánh giá chất lượng plan trước khi trình user approve.

Kiểm tra:
  1. Mỗi task có file path cụ thể không?
  2. File path có tồn tại trong project không?
  3. Task description có cụ thể không (action verb + output)?
  4. Có task bị duplicate/conflict không?
  5. Milestone ordering có hợp lý không?

Kết quả: quality score + danh sách vấn đề.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("orca.plan_validator")

# ── Action verbs giúp đánh giá độ cụ thể của task ──
_ACTION_VERBS = {
    "create", "add", "implement", "build", "develop", "write", "define",
    "refactor", "extract", "rename", "move", "delete", "remove",
    "modify", "update", "change", "fix", "repair", "correct",
    "configure", "setup", "install", "migrate", "convert",
    "integrate", "connect", "wire", "register", "plug",
    "test", "verify", "validate", "assert", "check",
    "optimize", "improve", "enhance", "clean", "simplify",
    "document", "annotate", "comment",
    "tạo", "thêm", "sửa", "xóa", "cập nhật", "viết", "xây dựng",
    "implement", "triển khai", "cài đặt", "tích hợp", "kết nối",
    "kiểm tra", "test", "xác thực", "tối ưu", "refactor",
}

# ── File extensions patterns ──
_FILE_EXT_PATTERN = re.compile(r'\.[a-zA-Z]{1,6}\b')
# ── Path pattern (relative file paths) ──
_PATH_PATTERN = re.compile(r'[\w/\\-]+\.(py|js|ts|jsx|tsx|html|htm|css|scss|less|json|toml|yaml|yml|md|vue|svelte|go|rs|java|kt|swift)')


@dataclass
class PlanIssue:
    """Một vấn đề phát hiện trong plan."""
    severity: str  # "error", "warning", "info"
    category: str  # "missing_file", "vague_task", "duplicate", "ordering", "specificity"
    message: str
    task_index: Optional[int] = None
    milestone_index: Optional[int] = None


@dataclass
class PlanValidationResult:
    """Kết quả validation của toàn bộ plan."""
    score: float  # 0.0 - 1.0
    issues: list[PlanIssue] = field(default_factory=list)
    passed: bool = True

    def merge(self, other: PlanValidationResult) -> PlanValidationResult:
        self.score = min(self.score, other.score)
        self.issues.extend(other.issues)
        self.passed = self.passed and other.passed
        return self


class PlanValidator:
    """Validate chất lượng plan trước khi trình user."""

    def __init__(self, project_root: str):
        self._root = Path(project_root)

    def validate_plan(self, plan_data: dict) -> PlanValidationResult:
        """Validate toàn bộ plan từ JSON data.
        *plan_data* format: {"epic": "...", "milestones": [...]}
        """
        result = PlanValidationResult(score=1.0)
        milestones = plan_data.get("milestones", [])
        if not milestones:
            result.issues.append(PlanIssue(
                severity="error", category="ordering",
                message="Plan không có milestone nào.",
            ))
            result.score = 0.0
            result.passed = False
            return result

        for mi, ms in enumerate(milestones):
            ms_result = self._validate_milestone(ms, mi)
            result = result.merge(ms_result)

        # Heuristic score
        error_count = sum(1 for i in result.issues if i.severity == "error")
        warning_count = sum(1 for i in result.issues if i.severity == "warning")
        if error_count > 0:
            result.score = max(0.0, 1.0 - (error_count * 0.25 + warning_count * 0.05))
        result.passed = error_count == 0
        return result

    def _validate_milestone(self, ms: dict, mi: int) -> PlanValidationResult:
        result = PlanValidationResult(score=1.0)
        title = ms.get("title", f"Milestone {mi+1}")
        tasks = ms.get("tasks", [])

        if not tasks:
            result.issues.append(PlanIssue(
                severity="warning", category="specificity",
                message=f"Milestone '{title}' không có task nào.",
                milestone_index=mi,
            ))
            result.score = 0.7
            return result

        seen_descriptions: set[str] = set()
        seen_files: set[str] = set()

        for ti, task in enumerate(tasks):
            task_result = self._validate_task(task, mi, ti)
            result = result.merge(task_result)

            desc = task.get("description", "").lower().strip()
            file_path = task.get("file", "")

            # Detect duplicate descriptions
            if desc:
                if desc in seen_descriptions:
                    result.issues.append(PlanIssue(
                        severity="warning", category="duplicate",
                        message=f"Task '{desc[:50]}...' xuất hiện 2 lần trong milestone '{title}'.",
                        milestone_index=mi, task_index=ti,
                    ))
                    result.score = min(result.score, 0.8)
                seen_descriptions.add(desc)

            # Detect duplicate/conflicting file targets
            if file_path:
                if file_path in seen_files:
                    result.issues.append(PlanIssue(
                        severity="info", category="duplicate",
                        message=f"File '{file_path}' được nhắm đến bởi nhiều task trong milestone '{title}'.",
                        milestone_index=mi, task_index=ti,
                    ))
                seen_files.add(file_path)

        return result

    def _validate_task(self, task: dict, mi: int, ti: int) -> PlanValidationResult:
        result = PlanValidationResult(score=1.0)
        desc = task.get("description", "").strip()
        file_path = task.get("file", "").strip()

        # ── Check 1: Task có description không? ──
        if not desc:
            result.issues.append(PlanIssue(
                severity="error", category="specificity",
                message=f"Task {ti+1} trong milestone {mi+1} không có description.",
                milestone_index=mi, task_index=ti,
            ))
            result.score = 0.5
            return result

        desc_lower = desc.lower()

        # ── Check 2: Task có file path không? ──
        if not file_path:
            # Tự động trích xuất file path từ description nếu có
            file_match = _PATH_PATTERN.search(desc)
            if file_match:
                file_path = file_match.group(0)
            else:
                result.issues.append(PlanIssue(
                    severity="warning", category="missing_file",
                    message=f"Task '{desc[:60]}...' không chỉ định file sẽ sửa.",
                    milestone_index=mi, task_index=ti,
                ))
                result.score = min(result.score, 0.8)

        # ── Check 3: Task description có action verb không? ──
        has_action = any(f" {v} " in f" {desc_lower} " or desc_lower.startswith(v) for v in _ACTION_VERBS)
        if not has_action:
            result.issues.append(PlanIssue(
                severity="warning", category="specificity",
                message=f"Task '{desc[:60]}...' không có action verb cụ thể (create/add/implement/...). Có thể quá mơ hồ.",
                milestone_index=mi, task_index=ti,
            ))
            result.score = min(result.score, 0.75)

        # ── Check 4: Description có quá ngắn/không đủ thông tin? ──
        if len(desc) < 15:
            result.issues.append(PlanIssue(
                severity="warning", category="specificity",
                message=f"Task '{desc[:60]}...' quá ngắn ({len(desc)} ký tự). Thiếu thông tin triển khai.",
                milestone_index=mi, task_index=ti,
            ))
            result.score = min(result.score, 0.7)

        # ── Check 5: File path có tồn tại? ──
        if file_path:
            full_path = self._resolve(file_path)
            if not full_path.exists():
                # File mới (chưa tồn tại) là OK — chỉ warning nếu description không nói "create" rõ ràng
                is_create = any(v in desc_lower for v in ("create", "tạo", "thêm", "new", "add", "viết"))
                if not is_create:
                    result.issues.append(PlanIssue(
                        severity="info", category="missing_file",
                        message=f"File '{file_path}' chưa tồn tại. "
                                f"Nếu là file mới, nên thêm 'create' vào description.",
                        milestone_index=mi, task_index=ti,
                    ))

        # ── Check 6: Description có vague keyword? ──
        vague_patterns = [
            r"\bsetup\b", r"\bconfig\b", r"\bdo it\b", r"\blàm\b",
            r"\bimplement\b(?!.*(?:function|class|method|file|module))",
        ]
        for pat in vague_patterns:
            if re.search(pat, desc_lower) and len(desc) < 30:
                pat_clean = pat.strip("\\b")
                result.issues.append(PlanIssue(
                    severity="info", category="specificity",
                    message=f"Task '{desc[:60]}...' dùng từ mơ hồ '{pat_clean}' mà không có chi tiết.",
                    milestone_index=mi, task_index=ti,
                ))

        return result

    def _resolve(self, path: str) -> Path:
        p = Path(path)
        if p.is_absolute():
            return p
        return self._root / path

    # ── Summary helpers ────────────────────────────────────────────────

    def format_summary(self, result: PlanValidationResult) -> str:
        """Tạo human-readable summary từ kết quả validation."""
        lines = [
            f"📊 Plan Quality Score: {result.score:.0%}",
        ]
        if result.score < 0.5:
            lines.append("   🛑 CRITICAL — Plan có vấn đề nghiêm trọng, nên revise.")
        elif result.score < 0.8:
            lines.append("   [WARN]  MODERATE — Plan tạm được, nhưng có thể cải thiện.")
        else:
            lines.append("   [OK] GOOD — Plan đủ chi tiết để thực thi.")

        if result.issues:
            lines.append("")
            for level in ("error", "warning", "info"):
                level_issues = [i for i in result.issues if i.severity == level]
                if not level_issues:
                    continue
                icon = {"error": "[ERR]", "warning": "[WARN]", "info": "💡"}[level]
                lines.append(f"  {icon} {level.upper()} ({len(level_issues)}):")
                for issue in level_issues:
                    loc = ""
                    if issue.milestone_index is not None:
                        loc = f"MS{issue.milestone_index+1}"
                    if issue.task_index is not None:
                        loc += f".{issue.task_index+1}"
                    prefix = f"[{loc}] " if loc else ""
                    lines.append(f"     - {prefix}{issue.message}")

        return "\n".join(lines)
