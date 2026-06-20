"""Independent Reviewer — finds bugs, security issues, and code quality problems.

Reviewer NEVER writes code. It only finds issues.
Uses static analysis (patterns + security scanner) + optional LLM review.
"""

from core.reviewer.agent import ReviewerAgent
from core.reviewer.models import (
    ReviewCategory,
    ReviewIssue,
    ReviewResult,
    ReviewSeverity,
    make_issue,
)
from core.reviewer.patterns import BugPatternDetector
from core.reviewer.security import SecurityScanner

__all__ = [
    "ReviewerAgent",
    "ReviewCategory",
    "ReviewIssue",
    "ReviewResult",
    "ReviewSeverity",
    "BugPatternDetector",
    "SecurityScanner",
    "make_issue",
]
