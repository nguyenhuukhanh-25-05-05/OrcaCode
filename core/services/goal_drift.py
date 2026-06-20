"""Goal Drift Detector — phát hiện agent đang lệch khỏi mục tiêu gốc.

Khi user nói "add dark mode", 40 iterations sau vẫn chưa có.
Mọi build/tests pass, nhưng goal không hoàn thành.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from core.services.signal import Signal, Priority

logger = logging.getLogger("orca.goaldrift")


@dataclass
class DriftCheckpoint:
    """Kết quả kiểm tra drift tại một thời điểm."""
    iteration: int
    relevance_score: float       # 0.0 (hoàn toàn lệch) → 1.0 (đang đúng hướng)
    current_focus: str           # Mô tả ngắn agent đang làm gì
    warning: str = ""


@dataclass
class GoalDriftResult:
    """Kết quả phân tích drift."""
    is_drifting: bool = False
    score: float = 1.0
    warnings: list[str] = field(default_factory=list)


class GoalDriftDetector:
    """Phát hiện agent đang lệch khỏi original goal.

    Dùng keyword matching + heuristic scoring.
    Không cần LLM call — lightweight, chạy mỗi N iterations.

    Usage:
        gd = GoalDriftDetector()
        gd.set_goal("Add dark mode toggle to settings page")
        # Mỗi vài iterations:
        result = gd.check(messages, modified_files, iteration)
        if result.is_drifting:
            print(result.warnings)
    """

    def __init__(self, check_interval: int = 5):
        self._original_goal: str = ""
        self._goal_keywords: set[str] = set()
        self._goal_domains: list[str] = []
        self._checkpoints: list[DriftCheckpoint] = []
        self._check_interval = check_interval
        self._last_check_iteration: int = -1
        self._aligned_domains: set[str] = set()  # Domains đã được xử lý

    # ── Public API ──────────────────────────────────────────────────────

    def set_goal(self, goal: str) -> None:
        """Set original goal từ user prompt."""
        self._original_goal = goal
        self._goal_keywords = self._extract_keywords(goal)
        self._goal_domains = self._categorize_domains(goal)
        logger.debug("Goal drift: goal=%s, keywords=%s, domains=%s",
                     goal[:80], self._goal_keywords, self._goal_domains)

    def check(self, recent_messages: list[dict], modified_files: set[str],
              iteration: int, summary: str = "") -> GoalDriftResult:
        """Kiểm tra drift tại iteration hiện tại.

        Trả về GoalDriftResult:
        - score: 0.0 (drift) → 1.0 (aligned)
        - is_drifting: True nếu score dưới threshold
        - warnings: lý do
        """
        result = GoalDriftResult()

        # Chỉ check mỗi N iterations
        if iteration - self._last_check_iteration < self._check_interval:
            return result
        self._last_check_iteration = iteration

        if not self._goal_keywords:
            return result

        # 1. Compute keyword coverage từ recent messages
        msg_coverage = self._compute_keyword_coverage(recent_messages)

        # 2. Compute file relevance
        file_relevance = self._compute_file_relevance(modified_files)

        # 3. Combined score
        score = msg_coverage * 0.6 + file_relevance * 0.4
        score = max(0.0, min(1.0, score))

        # Current focus description
        focus = self._describe_current_focus(recent_messages, modified_files)

        cp = DriftCheckpoint(
            iteration=iteration,
            relevance_score=score,
            current_focus=focus,
        )

        # Detect drift patterns
        if score < 0.3:
            cp.warning = (
                f"GOAL DRIFT: relevance score={score:.1f}. Focus '{focus}' "
                f"khong con lien quan den muc tieu goc '{self._original_goal[:60]}...'"
            )
            result.is_drifting = True
            result.warnings.append(cp.warning)
        elif score < 0.5 and len(self._checkpoints) >= 2:
            # Check if declining
            prev = self._checkpoints[-1]
            if prev.relevance_score - score > 0.15:
                cp.warning = (
                    f"GOAL DRIFTING: score giam {prev.relevance_score:.1f} -> {score:.1f}. "
                    f"Agent dang chuyen huong tu '{focus}' ?"
                )
                result.is_drifting = True
                result.warnings.append(cp.warning)

        result.score = score
        self._checkpoints.append(cp)
        return result

    def format_context(self) -> str:
        """Format context inject vào prompt — nhắc agent về goal nếu đang drift."""
        if not self._checkpoints:
            return ""
        last = self._checkpoints[-1]
        if last.relevance_score >= 0.5:
            return ""  # Đang ổn, không cần nhắc

        lines = [f"  Original goal: {self._original_goal[:100]}"]
        lines.append(f"  Relevance score: {last.relevance_score:.1f}")
        lines.append(f"  Current focus: {last.current_focus[:80]}")
        if last.warning:
            lines.append(f"  {last.warning[:120]}")
        # Remind unaddressed domains
        unaddressed = [d for d in self._goal_domains if d not in self._aligned_domains]
        if unaddressed:
            lines.append(f"  Unaddressed domains: {', '.join(unaddressed)}")
        return "\n".join(lines)

    def to_signals(self) -> list[Signal]:
        """Convert drift state → Signal objects.

        Detector chỉ cung cấp category + observation + evidence_level + confidence.
        severity_hint thể hiện mức độ drift nghiêm trọng.
        Priority do SignalRanker gán.
        """
        signals: list[Signal] = []
        if not self._checkpoints:
            return signals
        last = self._checkpoints[-1]
        if last.relevance_score >= 0.5:
            return signals  # No drift, no signal

        if last.relevance_score < 0.3:
            signals.append(Signal(
                category="drift",
                evidence_level=0,
                observation=(
                    f"Goal relevance {last.relevance_score:.1f}. "
                    f"Current: '{last.current_focus[:60]}' vs goal: '{self._original_goal[:60]}'"
                ),
                confidence=0.8,
                severity_hint=0.9,
            ))
        elif len(self._checkpoints) >= 2:
            prev = self._checkpoints[-2]
            if prev.relevance_score - last.relevance_score > 0.15:
                signals.append(Signal(
                    category="drift",
                    evidence_level=0,
                    observation=(
                        f"Goal relevance declining: {prev.relevance_score:.1f} → {last.relevance_score:.1f}. "
                        f"Agent moving to '{last.current_focus[:40]}'"
                    ),
                    confidence=0.7,
                    severity_hint=0.6,
                ))
        return signals

    def mark_domain_done(self, domain: str) -> None:
        """Đánh dấu một domain đã được xử lý (giảm warning về sau)."""
        self._aligned_domains.add(domain)

    # ── Internal ────────────────────────────────────────────────────────

    _STOPWORDS = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                  "have", "has", "had", "do", "does", "did", "will", "would",
                  "could", "should", "may", "might", "shall", "can", "need",
                  "to", "for", "of", "in", "on", "at", "by", "with", "from",
                  "and", "or", "but", "not", "no", "so", "if", "then", "else",
                  "this", "that", "these", "those", "it", "its", "them", "their",
                  "và", "của", "trong", "cho", "với", "một", "các", "những",
                  "được", "không", "có", "là", "ở", "từ", "đến", "về",
                  "này", "kia", "đó", "bạn", "tôi", "nó", "họ", "cũng",
                  "lại", "ra", "vào", "lên", "xuống", "qua", "khi"}

    _DOMAIN_PATTERNS = [
        ("ui/ux", {"button", "modal", "dialog", "layout", "widget", "panel",
                    "color", "theme", "font", "icon", "tooltip", "popup",
                    "css", "style", "template", "giao diện", "màn hình"}),
        ("data/storage", {"database", "db", "sql", "query", "migration",
                           "schema", "model", "entity", "repository",
                           "cache", "file", "store", "persist", "backup"}),
        ("api/network", {"api", "endpoint", "route", "http", "request",
                          "response", "rest", "graphql", "socket", "websocket",
                          "middleware", "controller"}),
        ("auth", {"login", "logout", "session", "token", "jwt", "oauth",
                   "password", "permission", "role", "user", "authenticate",
                   "authorize"}),
        ("testing", {"test", "pytest", "jest", "spec", "assert", "mock",
                      "fixture", "coverage"}),
        ("build/deploy", {"build", "deploy", "ci", "cd", "docker", "container",
                           "pipeline", "config", "env", "environment"}),
        ("docs", {"doc", "readme", "comment", "documentation", "guide",
                   "tutorial", "example"}),
        ("refactor", {"refactor", "cleanup", "format", "lint", "rename",
                       "extract", "inline", "move", "restructure"}),
    ]

    def _extract_keywords(self, text: str) -> set[str]:
        """Extract meaningful keywords from goal text."""
        # Remove non-alphanumeric (keep spaces)
        clean = re.sub(r'[^\w\s]', ' ', text.lower())
        words = clean.split()
        # Keep meaningful words (length > 2, not stopwords)
        return {w for w in words if len(w) > 2 and w not in self._STOPWORDS}

    def _categorize_domains(self, goal: str) -> list[str]:
        """Determine which domains the goal belongs to."""
        goal_lower = goal.lower()
        matched = []
        for domain, keywords in self._DOMAIN_PATTERNS:
            for kw in keywords:
                if kw in goal_lower:
                    matched.append(domain)
                    break
        return matched if matched else ["general"]

    def _compute_keyword_coverage(self, messages: list[dict]) -> float:
        """Compute what fraction of goal keywords appear in recent messages."""
        if not self._goal_keywords or not messages:
            return 0.0

        # Combine recent messages
        text = " ".join(
            m.get("content", "") for m in messages[-6:]  # Last 3 exchanges
        ).lower()

        covered = sum(1 for kw in self._goal_keywords if kw in text)
        return covered / len(self._goal_keywords)

    def _compute_file_relevance(self, modified_files: set[str]) -> float:
        """Score whether modified files are relevant to the goal."""
        if not modified_files or not self._goal_keywords:
            return 0.5  # Neutral — không có dữ liệu

        # Check file names + paths for goal keywords
        combined = " ".join(modified_files).lower()
        covered = sum(1 for kw in self._goal_keywords if kw in combined)
        score = covered / max(1, len(self._goal_keywords))
        return min(1.0, score * 1.5)  # Boost a bit

    def _describe_current_focus(self, messages: list[dict],
                                 modified_files: set[str]) -> str:
        """Short description of what the agent is currently doing."""
        # From modified files
        if modified_files:
            files = list(modified_files)[:3]
            return ", ".join(files)

        # From last message content
        if messages:
            last = messages[-1].get("content", "")
            # Extract first meaningful sentence
            sentences = re.split(r'[.!?\n]', last)
            for s in sentences:
                s = s.strip()
                if len(s) > 20 and len(s) < 150:
                    return s[:100]

        return "unknown"
