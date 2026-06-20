"""Structured Subagent Contracts — typed delegation & validation.

Convention: every subagent output conforms to a named contract (schema + validation
rules). The main agent delegates tasks to subagents, receives structured results,
and validates them before consuming.

Contracts replace ad-hoc regex parsing of AI outputs with typed dataclasses.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from enum import Enum
from typing import Any, Callable, Optional, TypeVar

T = TypeVar("T")


# ── Contract Status ──────────────────────────────────────

class ContractStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    FAILED = "failed"
    REJECTED = "rejected"  # Validation failed


class ContractSeverity(Enum):
    BLOCKING = "blocking"  # Must fix before proceeding
    WARNING = "warning"    # Should fix but can continue
    INFO = "info"          # Advisory


# ── Contract Violation ───────────────────────────────────

@dataclass
class ContractViolation:
    field: str
    message: str
    severity: ContractSeverity = ContractSeverity.BLOCKING
    expected: Any = None
    actual: Any = None

    def __str__(self) -> str:
        return f"[{self.severity.value.upper()}] {self.field}: {self.message}"


# ── Validation Result ────────────────────────────────────

@dataclass
class ContractValidation:
    violations: list[ContractViolation] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not any(
            v.severity == ContractSeverity.BLOCKING for v in self.violations
        )

    @property
    def has_warnings(self) -> bool:
        return any(
            v.severity == ContractSeverity.WARNING for v in self.violations
        )

    def blocking_issues(self) -> list[str]:
        return [str(v) for v in self.violations
                if v.severity == ContractSeverity.BLOCKING]

    def format_report(self) -> str:
        if not self.violations:
            return "[✓] Contract validation passed"
        lines = ["Contract validation issues:"]
        for v in self.violations:
            lines.append(f"  {v}")
        return "\n".join(lines)


# ── Base Subagent Contract (typed delegation) ────────────

@dataclass
class SubagentTask:
    """A typed contract defining what a subagent should do.

    This is what the MAIN agent sends to a subagent.
    """
    task_id: str
    goal: str
    contract_type: str  # e.g., "refactor", "test_gen", "security_audit"

    # Structured inputs
    files: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    expected_output: dict[str, str] = field(default_factory=dict)

    # Execution params
    max_iterations: int = 10
    timeout_seconds: int = 120
    priority: str = "normal"  # low | normal | high | critical

    # ── Serialization ────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "contract_type": self.contract_type,
            "files": self.files,
            "constraints": self.constraints,
            "context": self.context,
            "expected_output": self.expected_output,
            "max_iterations": self.max_iterations,
            "timeout_seconds": self.timeout_seconds,
            "priority": self.priority,
        }

    def to_prompt(self) -> str:
        """Render as an AI prompt block for subagent consumption."""
        lines = [
            f"<SUBTASK contract=\"{self.contract_type}\" id=\"{self.task_id}\">",
            f"## Goal\n{self.goal}",
        ]
        if self.files:
            lines.append(f"\n## Files to modify\n" + "\n".join(f"  - {f}" for f in self.files))
        if self.constraints:
            lines.append(f"\n## Constraints\n" + "\n".join(f"  - {c}" for c in self.constraints))
        if self.expected_output:
            lines.append(f"\n## Expected output fields\n" + "\n".join(
                f"  - {k}: {v}" for k, v in self.expected_output.items()
            ))
        lines.append("</SUBTASK>")
        return "\n".join(lines)


# ── Subagent Result (typed output) ──────────────────────

@dataclass
class SubagentResult:
    """A typed contract for subagent output.

    This is what the subagent RETURNS to the main agent.
    All subagent outputs should conform to this or a subclass.
    """
    task_id: str
    status: ContractStatus = ContractStatus.PENDING
    contract_type: str = ""

    # Structured output
    summary: str = ""
    modified_files: list[str] = field(default_factory=list)
    created_files: list[str] = field(default_factory=list)
    deleted_files: list[str] = field(default_factory=list)

    # Completion evidence
    checks_performed: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    remaining_issues: list[str] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)

    # Stats
    iterations_used: int = 0
    n_llm_calls: int = 0
    n_tool_calls: int = 0
    elapsed_seconds: float = 0.0

    # Raw output (for debugging)
    raw_output: str = ""

    # ── Computed ──────────────────────────────────────

    @property
    def all_files_touched(self) -> set[str]:
        return set(self.modified_files) | set(self.created_files) | set(self.deleted_files)

    @property
    def passed(self) -> bool:
        return self.status == ContractStatus.COMPLETE and not self.failures

    @property
    def worth_keeping(self) -> bool:
        """Partial results that are useful even on failure."""
        return bool(self.all_files_touched) or bool(self.findings)

    # ── Serialization ─────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "contract_type": self.contract_type,
            "summary": self.summary[:300],
            "modified_files": self.modified_files,
            "created_files": self.created_files,
            "deleted_files": self.deleted_files,
            "checks_performed": self.checks_performed,
            "failures": self.failures,
            "remaining_issues": self.remaining_issues,
            "findings": self.findings,
            "iterations_used": self.iterations_used,
            "n_llm_calls": self.n_llm_calls,
            "n_tool_calls": self.n_tool_calls,
            "elapsed_seconds": round(self.elapsed_seconds, 1),
        }

    def format_for_review(self) -> str:
        """Render as a reviewable report block."""
        lines = [
            f"<SUBTASK_RESULT contract=\"{self.contract_type}\" id=\"{self.task_id}\" status=\"{self.status.value}\">",
            f"Summary: {self.summary[:200]}",
        ]
        if self.modified_files:
            lines.append(f"Modified: {', '.join(self.modified_files)}")
        if self.created_files:
            lines.append(f"Created: {', '.join(self.created_files)}")
        if self.failures:
            lines.append(f"Failures: {', '.join(self.failures[:5])}")
        if self.remaining_issues:
            lines.append(f"Remaining: {', '.join(self.remaining_issues[:5])}")
        lines.append(f"Iterations: {self.iterations_used} | LLM calls: {self.n_llm_calls}")
        lines.append("</SUBTASK_RESULT>")
        return "\n".join(lines)


# ── Contract Validator ──────────────────────────────────

class ContractValidator:
    """Validate subagent results against contract expectations."""

    @staticmethod
    def validate(result: SubagentResult,
                 expected_files: Optional[list[str]] = None,
                 required_checks: Optional[list[str]] = None) -> ContractValidation:
        """Validate a subagent result.

        - Checks status is COMPLETE
        - Checks expected files were touched
        - Checks required_checks were performed
        """
        v = ContractValidation()

        if result.status != ContractStatus.COMPLETE:
            v.violations.append(ContractViolation(
                field="status",
                message=f"Expected COMPLETE, got {result.status.value}",
                severity=ContractSeverity.BLOCKING,
                expected="COMPLETE",
                actual=result.status.value,
            ))

        if expected_files:
            touched = result.all_files_touched
            for ef in expected_files:
                if ef not in touched:
                    v.violations.append(ContractViolation(
                        field="files",
                        message=f"Expected file '{ef}' not touched",
                        severity=ContractSeverity.BLOCKING if result.status != ContractStatus.FAILED else ContractSeverity.WARNING,
                        expected=ef,
                        actual="not in result",
                    ))

        if required_checks:
            checks_str = "\n".join(result.checks_performed).lower()
            for rc in required_checks:
                if rc.lower() not in checks_str:
                    v.violations.append(ContractViolation(
                        field="checks_performed",
                        message=f"Missing required check: {rc}",
                        severity=ContractSeverity.WARNING,
                    ))

        if result.failures and result.status == ContractStatus.COMPLETE:
            v.violations.append(ContractViolation(
                field="failures",
                message=f"Status COMPLETE but {len(result.failures)} failures reported",
                severity=ContractSeverity.WARNING,
                actual=result.failures[:3],
            ))

        return v

    @staticmethod
    def validate_batch(results: list[SubagentResult],
                       contract_type: str = "") -> ContractValidation:
        """Validate a batch of subagent results from the same contract type."""
        v = ContractValidation()
        for i, r in enumerate(results):
            if r.status != ContractStatus.COMPLETE:
                v.violations.append(ContractViolation(
                    field=f"result[{i}].status",
                    message=f"Subagent {r.task_id} not complete ({r.status.value})",
                    severity=ContractSeverity.BLOCKING,
                ))
        return v


# ── Contract Registry ───────────────────────────────────

class ContractRegistry:
    """Registry of known subagent contract types and their validators."""

    def __init__(self):
        self._validators: dict[str, Callable[[SubagentResult], ContractValidation]] = {}
        self._schemas: dict[str, dict] = {}

    def register(self, contract_type: str,
                 validator: Callable[[SubagentResult], ContractValidation],
                 schema: Optional[dict] = None):
        self._validators[contract_type] = validator
        if schema:
            self._schemas[contract_type] = schema

    def validate(self, contract_type: str, result: SubagentResult) -> Optional[ContractValidation]:
        validator = self._validators.get(contract_type)
        if validator is None:
            return None
        return validator(result)

    def list_contracts(self) -> list[str]:
        return sorted(self._validators.keys())


# ── Pre-built Contract Types ────────────────────────────

@dataclass
class CodeReviewContract(SubagentResult):
    """Specialized contract for code review subagent output."""
    review_issues: list[dict] = field(default_factory=list)
    quality_score: float = 0.0

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["review_issues"] = self.review_issues[:20]
        d["quality_score"] = self.quality_score
        return d


@dataclass
class TestGenContract(SubagentResult):
    """Specialized contract for test generation subagent output."""
    test_files: list[str] = field(default_factory=list)
    test_count: int = 0
    coverage_estimate: float = 0.0
    tests_pass: bool = False

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["test_files"] = self.test_files
        d["test_count"] = self.test_count
        d["coverage_estimate"] = self.coverage_estimate
        d["tests_pass"] = self.tests_pass
        return d


@dataclass
class RefactorContract(SubagentResult):
    """Specialized contract for refactoring subagent output."""
    refactored_symbols: list[str] = field(default_factory=list)
    behavioral_changes: list[str] = field(default_factory=list)
    backward_compatible: bool = True

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["refactored_symbols"] = self.refactored_symbols[:30]
        d["behavioral_changes"] = self.behavioral_changes[:10]
        d["backward_compatible"] = self.backward_compatible
        return d


@dataclass
class SecurityAuditContract(SubagentResult):
    """Specialized contract for security audit subagent output."""
    vulnerabilities: list[dict] = field(default_factory=list)
    risk_level: str = "low"  # low | medium | high | critical
    patch_applied: bool = False

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["vulnerabilities"] = self.vulnerabilities[:20]
        d["risk_level"] = self.risk_level
        d["patch_applied"] = self.patch_applied
        return d


# ── Parsing: extract contract from AI text ──────────────

def parse_subagent_result(raw_text: str) -> Optional[SubagentResult]:
    """Extract a SubagentResult from AI-generated text with SUBTASK_RESULT block."""
    import re
    import json

    # Look for structured JSON block first (preferred)
    json_match = re.search(
        r'```json\s*\n(.*?)```',
        raw_text, re.DOTALL | re.IGNORECASE,
    )
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            if "task_id" in data and "contract_type" in data:
                return _result_from_dict(data)
        except (json.JSONDecodeError, TypeError):
            pass

    # Fallback: SUBTASK_RESULT XML block
    block_match = re.search(
        r'<SUBTASK_RESULT\s+contract="(\w+)"\s+id="([^"]+)"\s+status="(\w+)"\s*>(.*?)</SUBTASK_RESULT>',
        raw_text, re.DOTALL,
    )
    if block_match:
        contract_type, task_id, status, body = block_match.groups()
        result = SubagentResult(
            task_id=task_id,
            contract_type=contract_type,
            status=_parse_status(status),
            summary=body.strip()[:500],
            raw_output=raw_text,
        )
        # Extract lists from body
        result.modified_files = _extract_list(body, "Modified:", "modified")
        result.checks_performed = _extract_list(body, "Checks:", "checks")
        result.failures = _extract_list(body, "Failures:", "failures")
        return result

    return None


def _parse_status(s: str) -> ContractStatus:
    try:
        return ContractStatus(s.lower())
    except ValueError:
        return ContractStatus.PENDING


def _result_from_dict(data: dict) -> SubagentResult:
    return SubagentResult(
        task_id=data.get("task_id", ""),
        contract_type=data.get("contract_type", ""),
        status=_parse_status(data.get("status", "pending")),
        summary=data.get("summary", ""),
        modified_files=data.get("modified_files", []),
        created_files=data.get("created_files", []),
        deleted_files=data.get("deleted_files", []),
        checks_performed=data.get("checks_performed", []),
        failures=data.get("failures", []),
        remaining_issues=data.get("remaining_issues", []),
        findings=data.get("findings", []),
        iterations_used=data.get("iterations_used", 0),
        n_llm_calls=data.get("n_llm_calls", 0),
        n_tool_calls=data.get("n_tool_calls", 0),
        elapsed_seconds=data.get("elapsed_seconds", 0.0),
    )


def _extract_list(body: str, prefix: str, key_lower: str) -> list[str]:
    """Extract a comma-separated list after a prefix label in text."""
    import re
    pattern = rf'{re.escape(prefix)}\s*(.*?)(?:\n|$)'
    match = re.search(pattern, body, re.IGNORECASE)
    if match:
        items = match.group(1).strip()
        if items and items.lower() not in ("none", "n/a", "-"):
            return [i.strip() for i in items.split(",") if i.strip()]
    return []
