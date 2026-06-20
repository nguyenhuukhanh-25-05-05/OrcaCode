"""Evidence-based completion checking — trust tools, not the model."""

from core.evidence.conditions import ConditionResult, DoneConditions, ConditionType
from core.evidence.manager import EvidenceManager
from core.evidence.project_detector import ProjectDetector, ProjectType
from core.evidence.runners import BuildRunner, LintRunner, TestRunner, ToolRunner, TypeCheckRunner

__all__ = [
    "EvidenceManager",
    "ProjectDetector",
    "ProjectType",
    "ToolRunner",
    "BuildRunner",
    "LintRunner",
    "TypeCheckRunner",
    "TestRunner",
    "DoneConditions",
    "ConditionType",
    "ConditionResult",
]
