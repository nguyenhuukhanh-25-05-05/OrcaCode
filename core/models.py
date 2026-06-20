from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PlanTask:
    description: str
    file: str = ""
    status: str = "pending"  # pending | running | done | skipped | failed


@dataclass
class PlanMilestone:
    title: str
    description: str = ""
    tasks: list[PlanTask] = field(default_factory=list)
    status: str = "pending"  # pending | running | done | failed


@dataclass
class HierarchicalPlan:
    epic: str  # Bất biến — mục tiêu tối cao
    milestones: list[PlanMilestone] = field(default_factory=list)
    current_milestone_index: int = 0  # -1 = chưa bắt đầu

    @property
    def current_milestone(self) -> PlanMilestone | None:
        if 0 <= self.current_milestone_index < len(self.milestones):
            return self.milestones[self.current_milestone_index]
        return None

    @property
    def active_tasks(self) -> list[PlanTask]:
        ms = self.current_milestone
        return ms.tasks if ms else []

    @property
    def is_complete(self) -> bool:
        return all(ms.status == "done" for ms in self.milestones)


class ExecutionMode(Enum):
    CHAT = auto()       # Simple conversation, no tools
    PLAN = auto()       # Plan + step-by-step approval (default)
    AUTO = auto()       # Full auto, no approval, max iterations


class AgentState(Enum):
    IDLE = auto()
    INTENT = auto()     # Phân tích ý định người dùng
    EVIDENCE = auto()   # Thu thập bằng chứng (đọc file liên quan)
    CONFIDENCE = auto() # Đánh giá độ chắc chắn dựa trên evidence (0-100%)
    CLARIFY = auto()    # Làm rõ yêu cầu
    RE_SCORE = auto()   # Đánh giá lại sau clarify
    VALIDATE = auto()   # Kiểm tra prerequisites, constraints
    PLAN = auto()       # Tạo kế hoạch thực thi
    SPEC_REVIEW = auto() # Review spec/plan trước khi approve (Two-Phase Review Phase 1)
    DONE_CONDITION = auto() # Định nghĩa điều kiện hoàn thành
    APPROVE = auto()    # Chờ người dùng phê duyệt
    RISK_CHECK = auto() # Đánh giá rủi ro của action
    EXECUTE = auto()    # Thực thi tools
    RETRY = auto()      # Phân tích lỗi + retry
    VERIFY = auto()     # Kiểm tra kết quả (lint, build, review)
    DONE = auto()


@dataclass
class ConfidenceScore:
    score: int  # 0-100
    reason: str = ""
    needs_clarification: bool = False
    suggested_questions: list[str] = field(default_factory=list)


@dataclass
class RiskLevel:
    level: str  # "low", "medium", "high", "critical"
    reason: str = ""
    requires_approval: bool = True


@dataclass
class SearchResult:
    file_path: str
    line_start: int
    line_end: int
    content: str
    relevance_score: float = 0.0


@dataclass
class PatchOperation:
    file_path: str
    search_lines: list[str]
    replace_lines: list[str]
    operation_id: str = ""


@dataclass
class PatchResult:
    success: bool
    file_path: str
    message: str
    diff: Optional[str] = None
    score: float = 0.0

    @property
    def summary(self) -> str:
        return self.message


@dataclass
class ApprovalRequest:
    operation_type: str
    description: str
    content: str
    risk_level: str = "medium"
    requires_approval: bool = True


@dataclass
class CommandRule:
    command: str
    auto_approve: bool = False
    risk_level: str = "medium"


@dataclass
class DiffLine:
    type: str
    content: str
    old_line_no: int | None = None
    new_line_no: int | None = None


@dataclass
class SessionState:
    conversation_history: list[dict] = field(default_factory=list)
    current_context: list[SearchResult] = field(default_factory=list)
    approved_commands: set[str] = field(default_factory=set)
    consecutive_auto_approve: int = 0
    current_project: str = ""
    execution_messages: list[dict] = field(default_factory=list)
    execution_modified_files: list[str] = field(default_factory=list)
    execution_approved_plan: str = ""
    execution_mode: str = ""
    pending_clarification: dict = field(default_factory=dict)  # {"original_prompt": str, "suggested_questions": list, "clarify_text": str}
    # Hierarchical Plan (phân tầng)
    hierarchical_plan_json: str = ""  # Raw JSON từ LLM
    current_milestone_index: int = -1  # -1 = chưa bắt đầu
