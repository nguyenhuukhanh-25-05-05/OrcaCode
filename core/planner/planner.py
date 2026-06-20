"""Master planner — break requirements into executable steps with dependency DAG."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from core.planner.requirement_analyzer import RequirementSpec


@dataclass
class PlanStep:
    id: int
    description: str
    files: list[str] = field(default_factory=list)
    depends_on: list[int] = field(default_factory=list)
    done_conditions: list[str] = field(default_factory=list)

    def is_ready(self, completed: set[int]) -> bool:
        return all(dep in completed for dep in self.depends_on)


@dataclass
class MasterPlan:
    steps: list[PlanStep] = field(default_factory=list)
    summary: str = ""

    def add_step(self, step: PlanStep) -> None:
        self.steps.append(step)

    def next_ready(self, completed: set[int]) -> Optional[PlanStep]:
        """Get the next step whose dependencies are all completed."""
        for step in self.steps:
            if step.id in completed:
                continue
            if step.is_ready(completed):
                return step
        return None

    def remaining(self, completed: set[int]) -> list[PlanStep]:
        return [s for s in self.steps if s.id not in completed]

    def all_done(self, completed: set[int]) -> bool:
        return len(self.remaining(completed)) == 0

    def dependency_graph(self) -> str:
        lines = ["Dependency Graph:"]
        for step in self.steps:
            deps = ", ".join(str(d) for d in step.depends_on) if step.depends_on else "none"
            lines.append(f"  Step {step.id}: {step.description[:60]}")
            lines.append(f"    depends on: {deps}")
        return "\n".join(lines)

    def validate(self) -> list[str]:
        """Validate the plan — check for cycles, missing deps, etc."""
        errors = []
        ids = {s.id for s in self.steps}

        for step in self.steps:
            for dep in step.depends_on:
                if dep not in ids:
                    errors.append(f"Step {step.id} depends on non-existent step {dep}")

        # Check for cycles via DFS
        visited = set()
        stack = set()

        def has_cycle(node: int) -> bool:
            visited.add(node)
            stack.add(node)
            step_map = {s.id: s for s in self.steps}
            s = step_map.get(node)
            if s:
                for dep in s.depends_on:
                    if dep not in visited:
                        if has_cycle(dep):
                            return True
                    elif dep in stack:
                        errors.append(f"Cycle detected: step {node} -> step {dep}")
                        return True
            stack.discard(node)
            return False

        for s in self.steps:
            if s.id not in visited:
                has_cycle(s.id)

        return errors


class Planner:
    """Generates a master plan from a requirement spec."""

    @staticmethod
    def create_plan(spec: RequirementSpec) -> MasterPlan:
        """Create a master plan from a requirement spec.

        Currently uses rule-based planning.
        Future: LLM-based plan generation.
        """
        plan = MasterPlan(summary=spec.summary)
        files = spec.files_involved

        if not files:
            plan.add_step(PlanStep(id=1, description="Analyze codebase and identify relevant files"))
            return plan

        step_id = 1
        prev_id = None

        for file_path in files:
            step = PlanStep(
                id=step_id,
                description=f"Implement changes in {file_path}",
                files=[file_path],
                depends_on=[prev_id] if prev_id is not None else [],
                done_conditions=[f"{file_path} updated correctly"],
            )
            plan.add_step(step)
            prev_id = step_id
            step_id += 1

        # Add verification step
        plan.add_step(PlanStep(
            id=step_id,
            description="Run full verification (build, lint, test)",
            files=[],
            depends_on=list(range(1, step_id)),
            done_conditions=[
                "Build passes",
                "Lint passes",
                "All tests pass",
            ],
        ))

        return plan
