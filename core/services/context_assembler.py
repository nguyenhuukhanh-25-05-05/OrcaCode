"""ContextAssembler — relevance-based context budgeting with pressure awareness.

Instead of appending everything to every iteration, the ContextAssembler:
1. Tracks what context has already been provided (deduplication)
2. Filters by relevance to current files / task
3. Enforces a token budget per context type, scaled by context pressure level
4. Prevents stale context from accumulating across iterations
"""

import logging
from typing import Optional

logger = logging.getLogger("orca.context")


class ContextBudget:
    """Token budget for a single context block."""
    __slots__ = ("max_tokens", "used_tokens")

    def __init__(self, max_tokens: int = 2000):
        self.max_tokens = max_tokens
        self.used_tokens = 0

    @property
    def remaining(self) -> int:
        return self.max_tokens - self.used_tokens

    @property
    def exhausted(self) -> bool:
        return self.remaining <= 0


class ContextAssembler:
    """Assembles relevant context for each iteration, budgeting by type.

    Usage in execution loop:
        assembler = ContextAssembler()
        assembler.reset()

        # Before injecting context:
        if assembler.should_include("scratchpad", sp_text, iteration, modified_files):
            messages.append(...)
            assembler.consume_budget("scratchpad", sp_text)
    """

    # Max tokens per context type (rough estimate: ~4 chars/token)
    CONTEXT_BUDGETS = {
        "scratchpad": 800,
        "exec_log": 1500,
        "dep_impact": 1000,
        "quality": 1500,
        "freshness": 500,
        "goal_drift": 500,
        "adr_override": 400,
    }

    # Importance weights for relevance scoring (0.0 - 1.0)
    CONTEXT_IMPORTANCE = {
        "scratchpad": 1.0,
        "exec_log": 0.9,
        "dep_impact": 0.7,
        "quality": 0.6,
        "freshness": 0.5,
        "goal_drift": 0.4,
        "adr_override": 0.3,
    }

    # Scale factor for budgets at each pressure level
    PRESSURE_BUDGET_SCALE = {0: 1.0, 1: 0.8, 2: 0.5, 3: 0.25}

    # Context types that are critical and should always be included
    CRITICAL_TYPES = frozenset({"scratchpad", "exec_log"})

    def __init__(self):
        self._provided: set[str] = set()
        self._pressure_level: int = 0
        self._budgets: dict[str, ContextBudget] = {
            k: ContextBudget(v) for k, v in self.CONTEXT_BUDGETS.items()
        }

    def set_pressure(self, level: int):
        """Set the context pressure level for budget scaling."""
        self._pressure_level = max(0, min(3, level))

    def reset(self):
        """Reset for a new execution session."""
        self._provided.clear()
        self._pressure_level = 0
        for budget in self._budgets.values():
            budget.used_tokens = 0

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return len(text) // 4

    def _effective_budget(self, context_type: str) -> int:
        """Return the pressure-scaled budget for a context type."""
        budget = self._budgets.get(context_type)
        if budget is None:
            return 0
        scale = self.PRESSURE_BUDGET_SCALE.get(self._pressure_level, 1.0)
        return max(200, int(budget.max_tokens * scale))

    def compute_relevance(self, context_type: str, text: str, iteration: int,
                          modified_files: Optional[set[str]] = None) -> float:
        """Score relevance of a context block (0.0-1.0) based on type, files, and recency."""
        score = self.CONTEXT_IMPORTANCE.get(context_type, 0.5)
        if modified_files and text:
            file_mentions = sum(1 for f in modified_files if f in text)
            if file_mentions:
                score = min(1.0, score + 0.1 * file_mentions)
        return min(1.0, max(0.0, score))

    def mark_provided(self, key: str):
        self._provided.add(key)

    def was_provided(self, key: str) -> bool:
        return key in self._provided

    def should_include(self, context_type: str, text: str, iteration: int,
                       modified_files: Optional[set[str]] = None) -> bool:
        """Check if this context should be included based on budget and relevance.

        Returns True if the context should be included, False if budget exceeded
        or irrelevant.
        """
        if not text or not text.strip():
            return False

        budget = self._budgets.get(context_type)
        if budget is None:
            return True

        effective = self._effective_budget(context_type)

        if context_type in self.CRITICAL_TYPES:
            return True

        if budget.used_tokens >= effective:
            if self._pressure_level >= 2:
                relevance = self.compute_relevance(context_type, text, iteration, modified_files)
                base = self.CONTEXT_IMPORTANCE.get(context_type, 0.5)
                threshold = base + (0.05 if self._pressure_level == 2 else 0.15)
                return relevance >= threshold
            return False

        return True

    def consume_budget(self, context_type: str, text: str):
        """Record that this context was included, consuming budget."""
        budget = self._budgets.get(context_type)
        if budget is not None:
            budget.used_tokens += self._estimate_tokens(text)

    def get_header(self) -> str:
        """Return a summary of current budget usage for debugging."""
        parts = []
        for ctype, budget in self._budgets.items():
            pct = (budget.used_tokens / budget.max_tokens * 100) if budget.max_tokens else 0
            parts.append(f"{ctype}: {budget.used_tokens}/{budget.max_tokens} ({pct:.0f}%)")
        return "Context budget: " + ", ".join(parts)
