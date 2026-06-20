"""Evidence Reference Validator — verify LLM justification refs against git & metrics.

LLM muốn override ADR phải nộp justification với evidence_ref trỏ đến
commit thật hoặc metric thật. Module này validate ref đó có tồn tại không.
"""

from __future__ import annotations

import fnmatch
import json
import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from core.validator.models import (
    ValidationCategory,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)

logger = logging.getLogger("orca.evidence_validator")

# ── Schema ───────────────────────────────────────────────────────────────
# LLM phải điền schema này khi override ADR.
# evidence_type: enum — loại bằng chứng
# evidence_ref: string — commit:<hash>:<glob> hoặc metric:<name>:<value>
# predicted_side_effects: list[str] — tự dự đoán hệ quả
OVERRIDE_SCHEMA: dict[str, Any] = {
    "trigger": "str",
    "evidence_type": "enum['commit', 'metric']",
    "evidence_ref": "str",
    "predicted_side_effects": ["str"],
}


def validate_evidence_ref(ref: str, repo_root: str | Path,
                          metrics_file: str | Path | None = None) -> ValidationResult:
    """Validate an evidence reference against git or metrics.

    Supports:
      - commit:<hash>:<glob>  → verify commit exists + glob matches changed files
      - metric:<name>:<value> → verify metric exists + value matches baseline
    """
    repo_root = Path(repo_root)

    if not ref or ":" not in ref:
        return _issue(f"evidence_ref must be 'commit:<hash>:<glob>' or 'metric:<name>:<value>', got '{ref}'")

    parts = ref.split(":", 2)
    ref_type, target = parts[0], parts[1]

    if ref_type == "commit":
        return _validate_commit_ref(target, parts[2] if len(parts) > 2 else "*", repo_root)
    elif ref_type == "metric":
        return _validate_metric_ref(target, parts[2] if len(parts) > 2 else "", metrics_file)
    else:
        return _issue(f"Unknown evidence_type '{ref_type}'. Must be 'commit' or 'metric'.")


def _validate_commit_ref(commit_hash: str, glob_pattern: str, repo_root: Path) -> ValidationResult:
    """Check commit exists and glob matches files changed in that commit."""
    # 1. Verify commit exists
    try:
        subprocess.run(
            ["git", "cat-file", "-e", commit_hash],
            capture_output=True, encoding="utf-8", cwd=repo_root,
            timeout=30, check=True,
        )
    except subprocess.TimeoutExpired:
        return _issue(f"git cat-file timed out for {commit_hash}")
    except subprocess.CalledProcessError:
        return _issue(f"Commit '{commit_hash}' does not exist")
    except Exception as exc:
        return _issue(f"git error: {exc}")

    # 2. Get files changed in commit
    try:
        proc = subprocess.run(
            ["git", "diff", "--name-only", f"{commit_hash}^..{commit_hash}"],
            capture_output=True, encoding="utf-8", cwd=repo_root,
            timeout=30, check=False,
        )
    except subprocess.TimeoutExpired:
        return _issue(f"git diff timed out for {commit_hash}")
    except Exception as exc:
        return _issue(f"git error: {exc}")

    if proc.returncode != 0:
        return _issue(f"git diff failed: {proc.stderr.strip()}")

    files_changed = [f for f in proc.stdout.strip().split("\n") if f]
    if not files_changed:
        return _issue(f"Commit {commit_hash} has no changed files")

    # 3. Check glob matches at least one changed file (fnmatch = safe, no ReDoS)
    matched = [f for f in files_changed if fnmatch.fnmatch(f, glob_pattern)]
    if not matched:
        sample = ", ".join(files_changed[:5])
        return _issue(f"Glob '{glob_pattern}' matches no files in commit {commit_hash}. "
                      f"Changed: {sample}{'...' if len(files_changed) > 5 else ''}")

    # 4. Warn if glob is too broad (match_score < 30%)
    match_score = len(matched) / len(files_changed)
    if match_score < 0.3:
        sample = ", ".join(matched[:3])
        return ValidationResult(issues=[
            ValidationIssue(
                category=ValidationCategory.CONSISTENCY,
                severity=ValidationSeverity.WARNING,
                message=f"Glob '{glob_pattern}' too broad: {len(matched)}/{len(files_changed)} "
                        f"files matched ({match_score:.0%}). Narrow it. Matched: {sample}",
            )
        ])

    return ValidationResult.ok()


def _validate_metric_ref(metric_name: str, claimed_value: str,
                         metrics_file: Path | str | None) -> ValidationResult:
    """Check metric exists and claimed value matches actual baseline."""
    metrics_path = os.path.join(str(metrics_file)) if metrics_file else os.path.join(".opencode", "metrics.json")

    if not os.path.exists(metrics_path):
        return _issue(f"Metrics file not found at '{metrics_path}'")

    try:
        with open(metrics_path, encoding="utf-8") as _f:
            baseline = json.loads(_f.read())
    except (json.JSONDecodeError, OSError) as exc:
        return _issue(f"Failed to read metrics file: {exc}")

    if metric_name not in baseline:
        available = ", ".join(sorted(baseline.keys()))
        return _issue(f"Metric '{metric_name}' not tracked. Available: {available}")

    actual_raw = (
        str(baseline[metric_name]["current"])
        if isinstance(baseline[metric_name], dict)
        else str(baseline[metric_name])
    )

    if _normalize(actual_raw) != _normalize(claimed_value):
        return _issue(f"Metric '{metric_name}' mismatch: claimed '{claimed_value}', actual '{actual_raw}'")

    return ValidationResult.ok()


def _normalize(v: str) -> str:
    """Normalize metric string: lowercase, strip spaces/underscores/dashes."""
    return re.sub(r"[\s_\-]+", "", v).lower()


def _issue(message: str) -> ValidationResult:
    return ValidationResult(issues=[
        ValidationIssue(
            category=ValidationCategory.CONSISTENCY,
            severity=ValidationSeverity.ERROR,
            message=message,
        )
    ])


def validate_override_justification(justification: dict, repo_root: str | Path,
                                     metrics_file: str | Path | None = None) -> ValidationResult:
    """Validate a full override justification against OVERRIDE_SCHEMA.

    Checks:
      1. Required fields exist
      2. evidence_type is valid enum value
      3. evidence_ref resolves to real git/metric data
      4. predicted_side_effects is non-empty list
    """
    issues: list[ValidationIssue] = []

    for field in ("trigger", "evidence_type", "evidence_ref", "predicted_side_effects"):
        if field not in justification:
            issues.append(ValidationIssue(
                category=ValidationCategory.SCHEMA,
                severity=ValidationSeverity.ERROR,
                message=f"Missing required field: '{field}'",
            ))

    if issues:
        return ValidationResult(issues=issues)

    if justification["evidence_type"] not in ("commit", "metric"):
        issues.append(ValidationIssue(
            category=ValidationCategory.SCHEMA,
            severity=ValidationSeverity.ERROR,
            message=f"evidence_type must be 'commit' or 'metric', got '{justification['evidence_type']}'",
        ))

    effects = justification.get("predicted_side_effects", [])
    if not isinstance(effects, list) or len(effects) == 0:
        issues.append(ValidationIssue(
            category=ValidationCategory.SCHEMA,
            severity=ValidationSeverity.WARNING,
            message="predicted_side_effects should be a non-empty list of strings",
        ))

    if issues:
        return ValidationResult(issues=issues)

    return validate_evidence_ref(justification["evidence_ref"], repo_root, metrics_file)
