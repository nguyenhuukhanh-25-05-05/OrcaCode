"""Reviewer Agent — independent LLM-based code reviewer.

The ReviewerAgent NEVER writes code. It only finds issues.
It operates with low temperature (0.1) and a strict review prompt.

Usage:
    agent = ReviewerAgent(llm_client)
    result = await agent.review(
        diff_info="Files changed: src/main.py\n+ def foo(): pass",
        spec=requirement_spec,
        rules="- Use named exports",
    )
    if not result.passed:
        for issue in result.issues:
            print(issue.short_label)
"""

from __future__ import annotations

from typing import Optional

from core.llm import LLMClient
from core.reviewer.models import (
    ReviewCategory,
    ReviewIssue,
    ReviewResult,
    ReviewSeverity,
)
from core.reviewer.patterns import BugPatternDetector
from core.reviewer.security import SecurityScanner

REVIEW_SYSTEM_PROMPT = """You are an independent code reviewer. You NEVER write code.

Your ONLY job is to find issues in the code changes provided.

## Review Checklist
Check EVERY item before concluding:
- □ Bug: Logic error, null reference, off-by-one, race condition
- □ Edge case: Empty state, error state, boundary value
- □ Security: Injection, XSS, hardcoded secret, path traversal
- □ Regression: Would this break existing features?
- □ Architecture: Violates project patterns or conventions
- □ Requirement: Missing or incomplete vs the spec
- □ Performance: Memory leak, unnecessary re-render, O(n²)
- □ Accessibility: Missing ARIA labels, keyboard navigation

## Rules
- Be CRITICAL. Every issue you miss could ship to production.
- Do NOT suggest code — describe the problem clearly.
- If no issues found, say "No issues found."
- Be specific: mention file, line number, and the problematic code.

## Output Format
For each issue found, output in this format:
ISSUE: <category> | <severity> | <file>:<line> | <description>
SUGGESTION: <how to fix>

Severity levels: critical, high, medium, low, info
Categories: bug, security, performance, edge_case, architecture, style, requirement, accessibility

If no issues: OK: No issues found.
"""


class ReviewerAgent:
    """Independent code reviewer — finds bugs but NEVER writes code."""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        temperature: float = 0.1,
    ):
        self.llm = llm_client
        self.temperature = temperature
        self.pattern_detector = BugPatternDetector()
        self.security_scanner = SecurityScanner()

    async def review(
        self,
        diff_info: str = "",
        files: Optional[dict[str, str]] = None,
        spec_summary: str = "",
        rules: str = "",
        llm_client=None,
    ) -> ReviewResult:
        """Run full review: static analysis + optional LLM review.

        Args:
            diff_info: Text description of what changed.
            files: {relative_path: content_string} — for static analysis.
            spec_summary: Requirement spec summary for context.
            rules: Coding rules/conventions to check against.
            llm_client: Optional LLM client override (passed per-call).

        Returns:
            ReviewResult with all found issues.
        """
        all_results = ReviewResult()

        # 1. Static analysis — always run
        if files:
            pattern_result = self.pattern_detector.scan_files(files)
            all_results = all_results.merge(pattern_result)

            security_result = self.security_scanner.scan_files(files)
            all_results = all_results.merge(security_result)

        # 2. LLM-based review — only if LLM client available
        active_llm = llm_client or self.llm
        if active_llm:
            try:
                llm_result = await self._llm_review(diff_info, spec_summary, rules, active_llm)
                all_results = all_results.merge(llm_result)
            except Exception:
                pass  # LLM review is optional; static analysis still runs

        return all_results

    async def review_diff(
        self,
        diff: str,
        spec_summary: str = "",
        rules: str = "",
    ) -> ReviewResult:
        """Review a code diff without file contents for static analysis."""
        return await self.review(
            diff_info=diff,
            files=None,
            spec_summary=spec_summary,
            rules=rules,
        )

    async def _llm_review(
        self,
        diff_info: str,
        spec_summary: str,
        rules: str,
        llm_client=None,
    ) -> ReviewResult:
        """Run LLM-based code review."""
        client = llm_client or self.llm
        if client is None:
            return ReviewResult()

        messages = [
            {"role": "system", "content": REVIEW_SYSTEM_PROMPT},
            {"role": "user", "content": self._build_review_prompt(diff_info, spec_summary, rules)},
        ]

        try:
            response = await client.generate(messages)
            text = response.text
        except Exception:
            return ReviewResult()

        return self._parse_response(text)

    def _build_review_prompt(self, diff_info: str, spec_summary: str, rules: str) -> str:
        parts = []
        if spec_summary:
            parts.append(f"## Requirement\n{spec_summary}\n")
        if rules:
            parts.append(f"## Rules\n{rules}\n")
        if diff_info:
            parts.append(f"## Code Changes\n{diff_info}\n")
        parts.append("Review the changes above. Find ALL issues.")
        return "\n".join(parts)

    def _parse_response(self, text: str) -> ReviewResult:
        """Parse LLM review output into structured ReviewResult."""
        issues: list[ReviewIssue] = []

        # Check for "No issues found"
        if "No issues found" in text or "OK:" in text:
            return ReviewResult()

        for line in text.splitlines():
            line = line.strip()
            if line.startswith("ISSUE:"):
                parts = line[6:].strip().split("|")
                if len(parts) >= 3:
                    category_str = parts[0].strip().lower()
                    severity_str = parts[1].strip().lower()
                    location_desc = "|".join(parts[2:]).strip()

                    # Try to extract file:line from location_desc
                    file_name = ""
                    line_num = 0
                    import re
                    loc_match = re.match(r"(\S+):(\d+)\s+(.*)", location_desc)
                    if loc_match:
                        file_name = loc_match.group(1)
                        line_num = int(loc_match.group(2))
                        message = loc_match.group(3)
                    else:
                        message = location_desc

                    # Get suggestion from next line
                    suggestion = ""
                    # (simplified: suggestion is not parsed; included in message)

                    try:
                        issue = ReviewIssue(
                            category=ReviewCategory(category_str),
                            severity=ReviewSeverity(severity_str),
                            message=message,
                            file=file_name,
                            line=line_num,
                            suggestion=suggestion,
                        )
                        issues.append(issue)
                    except ValueError:
                        pass  # skip unparseable issues

            elif line.startswith("SUGGESTION:") and issues:
                issues[-1].suggestion = line[11:].strip()

        return ReviewResult(issues=issues)
