"""Tests for DoneConditions."""

from core.evidence.conditions import ConditionResult, ConditionType, DoneConditions


def test_all_pass():
    conditions = DoneConditions()
    conditions.add(ConditionResult(type=ConditionType.BUILD, name="build", passed=True, exit_code=0))
    conditions.add(ConditionResult(type=ConditionType.TEST, name="test", passed=True, exit_code=0))
    assert conditions.all_pass() is True


def test_some_fail():
    conditions = DoneConditions()
    conditions.add(ConditionResult(type=ConditionType.BUILD, name="build", passed=True, exit_code=0))
    conditions.add(ConditionResult(type=ConditionType.TEST, name="test", passed=False, exit_code=1))
    assert conditions.all_pass() is False


def test_failures():
    conditions = DoneConditions()
    conditions.add(ConditionResult(type=ConditionType.BUILD, name="build", passed=True))
    conditions.add(ConditionResult(type=ConditionType.LINT, name="lint", passed=False))
    failures = conditions.failures()
    assert len(failures) == 1
    assert failures[0].name == "lint"


def test_empty_all_pass():
    conditions = DoneConditions()
    assert conditions.all_pass() is True


def test_reset():
    conditions = DoneConditions()
    conditions.add(ConditionResult(type=ConditionType.BUILD, name="build", passed=True))
    assert len(conditions.conditions) == 1
    conditions.reset()
    assert len(conditions.conditions) == 0


def test_summary():
    conditions = DoneConditions()
    conditions.add(ConditionResult(type=ConditionType.BUILD, name="build", passed=True))
    summary = conditions.summary()
    assert "PASS" in summary
    assert "ALL PASS" in summary
