"""Tests for Validation models."""

from core.validator.models import ValidationCategory, ValidationIssue, ValidationResult, ValidationSeverity


def test_validation_issue_defaults():
    issue = ValidationIssue(category=ValidationCategory.TEST, severity=ValidationSeverity.ERROR, message="fail")
    assert issue.file == ""
    assert issue.line == 0
    assert issue.expected == ""
    assert issue.actual == ""


def test_validation_result_passed():
    assert ValidationResult().passed is True
    assert ValidationResult.ok().passed is True


def test_validation_result_failed():
    r = ValidationResult.error("something broke", category=ValidationCategory.BUILD)
    assert r.passed is False
    assert r.count == 1
    assert r.error_count == 1


def test_validation_result_warning():
    r = ValidationResult.warning("check this", category=ValidationCategory.LINT)
    assert r.passed is False
    assert r.count == 1
    assert r.warning_count == 1


def test_validation_result_merge():
    r1 = ValidationResult.error("err1")
    r2 = ValidationResult.warning("warn2")
    merged = r1.merge(r2)
    assert merged.count == 2
    assert merged.error_count == 1
    assert merged.warning_count == 1


def test_validation_result_by_severity():
    r = ValidationResult()
    r.issues.append(ValidationIssue(category=ValidationCategory.OUTPUT, severity=ValidationSeverity.ERROR, message="e1"))
    r.issues.append(ValidationIssue(category=ValidationCategory.OUTPUT, severity=ValidationSeverity.WARNING, message="w1"))
    by_sev = r.by_severity()
    assert len(by_sev[ValidationSeverity.ERROR]) == 1
    assert len(by_sev[ValidationSeverity.WARNING]) == 1


def test_validation_result_by_category():
    r = ValidationResult()
    r.issues.append(ValidationIssue(category=ValidationCategory.TEST, severity=ValidationSeverity.ERROR, message="e1"))
    r.issues.append(ValidationIssue(category=ValidationCategory.BUILD, severity=ValidationSeverity.WARNING, message="w1"))
    by_cat = r.by_category()
    assert len(by_cat[ValidationCategory.TEST]) == 1
    assert len(by_cat[ValidationCategory.BUILD]) == 1


def test_summary_no_issues():
    assert "No validation issues." in ValidationResult.ok().summary()


def test_summary_with_issues():
    r = ValidationResult.error("test error", category=ValidationCategory.TEST)
    s = r.summary()
    assert "ERROR" in s
    assert "test" in s
    assert "1 issue" in s


def test_severity_enum_values():
    assert ValidationSeverity.ERROR.value == "error"
    assert ValidationSeverity.WARNING.value == "warning"
    assert ValidationSeverity.INFO.value == "info"


def test_category_enum_values():
    assert ValidationCategory.DIFF.value == "diff"
    assert ValidationCategory.SAFETY.value == "safety"
    assert ValidationCategory.SCHEMA.value == "schema"
