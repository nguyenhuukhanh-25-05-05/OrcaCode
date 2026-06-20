"""Requirement analysis — parse user request into structured spec."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RequirementSpec:
    summary: str = ""
    scope: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    files_involved: list[str] = field(default_factory=list)
    raw_prompt: str = ""

    @property
    def is_valid(self) -> bool:
        return bool(self.summary) and len(self.scope) > 0


class RequirementAnalyzer:
    """Analyze user request and produce a structured requirement spec.

    In the current version, parsing is rule-based.
    In future versions, this will use an LLM call to extract structured info.
    """

    @staticmethod
    def analyze(prompt: str) -> RequirementSpec:
        """Parse a user prompt into a structured requirement spec."""
        lines = prompt.strip().splitlines()
        summary = lines[0] if lines else prompt[:120]

        spec = RequirementSpec(
            summary=summary[:200],
            raw_prompt=prompt,
        )

        # Rule-based extraction of file references
        import re
        file_refs = re.findall(r'(?:in |file |modify |update |create |delete )([\w./\\-]+\.[\w]+)', prompt, re.IGNORECASE)
        if file_refs:
            spec.files_involved = list(set(file_refs))
            spec.scope.append(f"Files: {', '.join(spec.files_involved)}")

        # Detect scope keywords
        scope_keywords = [
            ("UI|frontend|component|page|screen|view", "UI/Frontend"),
            ("API|endpoint|route|controller|service", "API/Backend"),
            ("database|DB|model|schema|migration", "Database"),
            ("test|spec|e2e|integration|unit test", "Testing"),
            ("config|setup|env|deploy|docker", "Configuration"),
            ("security|auth|permission|role|login", "Security"),
        ]
        for pattern, label in scope_keywords:
            if re.search(pattern, prompt, re.IGNORECASE):
                spec.scope.append(label)

        # Detect constraints
        constraint_keywords = [
            r"don'?t (break|change|modify)",
            r"must (not|never)",
            r"should (not|never)",
            r"maintain (compatibility|backward)",
            r"keep (existing|current)",
            r"without (breaking|changing)",
        ]
        for pattern in constraint_keywords:
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match:
                spec.constraints.append(prompt[max(0, match.start()-30):match.end()+30].strip())

        # Detect risks
        if re.search(r"complex|large|critical|dangerous|risky|experimental", prompt, re.IGNORECASE):
            spec.risks.append("Prompt contains complexity/risk keywords — review carefully")

        return spec
