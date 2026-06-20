"""Tests for Planner and MasterPlan."""

from core.planner.planner import MasterPlan, PlanStep, Planner
from core.planner.requirement_analyzer import RequirementAnalyzer


def test_plan_add_step():
    plan = MasterPlan(summary="test")
    plan.add_step(PlanStep(id=1, description="Step 1"))
    assert len(plan.steps) == 1


def test_plan_dependency():
    plan = MasterPlan(summary="test")
    plan.add_step(PlanStep(id=1, description="Step 1"))
    plan.add_step(PlanStep(id=2, description="Step 2", depends_on=[1]))

    completed = set()
    assert plan.next_ready(completed) is not None
    assert plan.next_ready(completed).id == 1

    completed.add(1)
    assert plan.next_ready(completed).id == 2


def test_plan_all_done():
    plan = MasterPlan(summary="test")
    plan.add_step(PlanStep(id=1, description="Step 1"))
    assert plan.all_done({1}) is True
    assert plan.all_done(set()) is False


def test_plan_remaining():
    plan = MasterPlan(summary="test")
    plan.add_step(PlanStep(id=1, description="Step 1"))
    plan.add_step(PlanStep(id=2, description="Step 2"))
    remaining = plan.remaining({1})
    assert len(remaining) == 1
    assert remaining[0].id == 2


def test_step_is_ready():
    step = PlanStep(id=3, description="Step 3", depends_on=[1, 2])
    assert step.is_ready({1, 2}) is True
    assert step.is_ready({1}) is False
    assert step.is_ready(set()) is False


def test_validate_valid():
    plan = MasterPlan(summary="test")
    plan.add_step(PlanStep(id=1, description="Step 1"))
    plan.add_step(PlanStep(id=2, description="Step 2", depends_on=[1]))
    errors = plan.validate()
    assert len(errors) == 0


def test_validate_missing_dep():
    plan = MasterPlan(summary="test")
    plan.add_step(PlanStep(id=1, description="Step 1", depends_on=[99]))
    errors = plan.validate()
    assert len(errors) == 1
    assert "non-existent" in errors[0]


def test_create_plan_with_files():
    spec = RequirementAnalyzer.analyze("Modify src/file1.ts and src/file2.ts")
    plan = Planner.create_plan(spec)
    assert len(plan.steps) >= 2  # at least 2 file steps + verification

    steps_with_files = [s for s in plan.steps if s.files]
    assert len(steps_with_files) >= 1


def test_create_plan_no_files():
    spec = RequirementAnalyzer.analyze("What is the current architecture?")
    plan = Planner.create_plan(spec)
    assert len(plan.steps) == 1
    assert "Analyze" in plan.steps[0].description
