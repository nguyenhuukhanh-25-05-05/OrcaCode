"""ContextFidelityTracker — measure how much critical context survives compaction.

Tracks what the agent remembers across iterations:
- Goal / objective keywords
- Active plan steps
- Architecture decisions (ADRs)
- Recent failures (scratchpad)
- Execution commitments

Usage:
    tracker = ContextFidelityTracker()
    snapshot = tracker.snapshot(messages, plan="", decision_log=None)
    # ... after compaction ...
    score = tracker.measure(messages, snapshot)
    print(f"Context fidelity: {score:.0%}")
"""

import logging
import re
from typing import Optional

logger = logging.getLogger("orca.fidelity")


def _extract_keywords(text: str, max_words: int = 20) -> set[str]:
    """Extract significant keywords from text."""
    words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
    # Filter common stopwords
    stopwords = {"this", "that", "with", "from", "have", "been", "were", "what",
                 "which", "their", "them", "they", "will", "would", "could",
                 "should", "about", "there", "these", "those", "into", "also",
                 "than", "then", "some", "more", "file", "code", "line", "need"}
    significant = [w for w in words if w not in stopwords]
    return set(significant[:max_words])


def _compute_score(snapshot: dict, text_after: str) -> float:
    """Compute fidelity score (0.0-1.0) for a single snapshot category."""
    items = snapshot.get("items", [])
    if not items:
        return 1.0
    survived = sum(1 for item in items if item in text_after)
    return survived / len(items)


class ContextFidelityTracker:
    """Measure context retention across compaction/pruning events."""

    def measure_fidelity(self, messages_before: list[dict],
                         messages_after: list[dict],
                         plan: str = "",
                         decision_log=None,
                         scratchpad: Optional[list[str]] = None,
                         exec_log: Optional[list[str]] = None) -> dict:
        """Compare messages before/after and return fidelity scores.

        Returns dict with:
            - overall: float (0.0-1.0)
            - goal: float
            - plan: float
            - decisions: float
            - failures: float
            - execution: float
            - n_before: int (messages count before)
            - n_after: int (messages count after)
        """
        text_before = "\n".join(m.get("content", "") for m in messages_before)
        text_after = "\n".join(m.get("content", "") for m in messages_after)

        scores = {
            "n_before": len(messages_before),
            "n_after": len(messages_after),
        }

        # 1. Goal fidelity: keywords from the first few user messages
        goal_texts = []
        for m in messages_before[:6]:
            if m.get("role") == "user":
                goal_texts.append(m.get("content", ""))
        goal_kw = _extract_keywords(" ".join(goal_texts))
        goal_survival = sum(1 for kw in goal_kw if kw in text_after.lower())
        scores["goal"] = goal_survival / max(len(goal_kw), 1)

        # 2. Plan fidelity: plan steps mentioned in messages
        if plan:
            plan_lines = [l.strip() for l in plan.split("\n") if l.strip()]
            plan_survival = sum(1 for p in plan_lines if p[:60] in text_after)
            scores["plan"] = plan_survival / max(len(plan_lines), 1)
        else:
            scores["plan"] = 1.0

        # 3. Decision fidelity: ADR decisions
        decision_texts = []
        if decision_log is not None:
            try:
                adrs = getattr(decision_log, "adrs", []) or decision_log.get("adrs", []) if isinstance(decision_log, dict) else []
                if not adrs and hasattr(decision_log, "get_active_adrs"):
                    adrs = decision_log.get_active_adrs()
                for adr in (adrs or []):
                    if isinstance(adr, dict):
                        decision_texts.append(adr.get("decision", adr.get("choice", "")))
            except Exception:
                pass
        # Also find ADR references in messages directly
        for m in messages_before:
            content = m.get("content", "")
            for match in re.finditer(r'ADR-\d+', content):
                decision_texts.append(match.group())
        decision_survival = sum(1 for d in set(decision_texts) if d in text_after)
        scores["decisions"] = decision_survival / max(len(set(decision_texts)), 1)

        # 4. Failure fidelity: scratchpad errors
        if scratchpad:
            fail_terms = _extract_keywords(" ".join(scratchpad[-10:]), max_words=15)
            fail_survival = sum(1 for f in fail_terms if f in text_after.lower())
            scores["failures"] = fail_survival / max(len(fail_terms), 1)
        else:
            scores["failures"] = 1.0

        # 5. Execution fidelity: recent tool call patterns
        if exec_log:
            exec_text = "\n".join(exec_log[-10:])
            exec_kw = _extract_keywords(exec_text, max_words=10)
            exec_survival = sum(1 for e in exec_kw if e in text_after.lower())
            scores["execution"] = exec_survival / max(len(exec_kw), 1)
        else:
            scores["execution"] = 1.0

        weights = {"goal": 0.30, "plan": 0.25, "decisions": 0.20, "failures": 0.15, "execution": 0.10}
        overall = sum(scores[k] * weights[k] for k in weights if k in scores)
        scores["overall"] = overall

        return scores

    def format_report(self, scores: dict, iteration: int) -> str:
        """Format fidelity scores for chat output."""
        parts = [f"[#888888]📋 Context fidelity (iter {iteration}):"]
        for key in ("goal", "plan", "decisions", "failures", "execution"):
            if key in scores:
                val = scores[key]
                color = "#22c55e" if val >= 0.8 else ("#f59e0b" if val >= 0.5 else "#ff4444")
                parts.append(f"  [{color}]{key}: {val:.0%}[/{color}]")
        parts.append(f"  overall: {scores.get('overall', 0):.0%}[/#888888]")
        return "\n".join(parts)
