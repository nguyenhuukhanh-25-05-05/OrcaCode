"""Tests for ReviewerAgent and review models."""

from core.reviewer.agent import ReviewerAgent
from core.reviewer.models import (
    ReviewCategory,
    ReviewIssue,
    ReviewResult,
    ReviewSeverity,
    make_issue,
)


def test_review_result_empty():
    result = ReviewResult()
    assert result.passed
    assert result.count == 0
    assert "No issues" in result.summary()


def test_review_result_with_issues():
    result = ReviewResult(issues=[
        make_issue("bug", "high", "Null reference", "main.py", 10),
    ])
    assert not result.passed
    assert result.count == 1
    assert result.high_count == 1
    assert "Null reference" in result.summary()


def test_review_result_critical_count():
    result = ReviewResult(issues=[
        make_issue("security", "critical", "SQL injection", "db.py", 5),
        make_issue("bug", "high", "Off by one", "util.py", 20),
        make_issue("style", "low", "Print statement", "main.py", 1),
    ])
    assert result.critical_count == 1
    assert result.high_count == 1
    assert result.count == 3


def test_review_result_merge():
    r1 = ReviewResult(issues=[make_issue("bug", "high", "Issue 1", "a.py")])
    r2 = ReviewResult(issues=[make_issue("bug", "low", "Issue 2", "b.py")])
    merged = r1.merge(r2)
    assert merged.count == 2


def test_review_result_by_severity():
    result = ReviewResult(issues=[
        make_issue("bug", "high", "Bug 1"),
        make_issue("bug", "low", "Bug 2"),
    ])
    by_sev = result.by_severity()
    assert len(by_sev[ReviewSeverity.HIGH]) == 1
    assert len(by_sev[ReviewSeverity.LOW]) == 1


def test_review_result_by_category():
    result = ReviewResult(issues=[
        make_issue("bug", "high", "Bug 1"),
        make_issue("security", "critical", "Security 1"),
    ])
    by_cat = result.by_category()
    assert len(by_cat[ReviewCategory.BUG]) == 1
    assert len(by_cat[ReviewCategory.SECURITY]) == 1


def test_make_issue_defaults():
    issue = make_issue("bug", "high", "Test message")
    assert issue.category == ReviewCategory.BUG
    assert issue.severity == ReviewSeverity.HIGH
    assert issue.message == "Test message"
    assert issue.file == ""
    assert issue.line == 0


def test_make_issue_full():
    issue = make_issue(
        category="security",
        severity="critical",
        message="SQL injection risk",
        file="db.py",
        line=42,
        column=5,
        suggestion="Use parameterized queries",
        code="execute(f'SELECT * FROM users WHERE id = {id}')",
    )
    assert issue.file == "db.py"
    assert issue.line == 42
    assert issue.column == 5
    assert issue.suggestion == "Use parameterized queries"


def test_issue_short_label():
    issue = make_issue("bug", "high", "Very long message that should be truncated somewhere")
    assert issue.short_label.endswith("...") or len(issue.short_label) <= 100


def test_issue_location():
    issue = make_issue("bug", "low", "test", "file.py", 10)
    assert issue.location == "file.py:10"
    issue2 = make_issue("bug", "low", "test", "file.py")
    assert issue2.location == "file.py"
    issue3 = make_issue("bug", "low", "test")
    assert issue3.location == ""


def test_reviewer_agent_init():
    agent = ReviewerAgent()
    assert agent is not None
    assert agent.pattern_detector is not None
    assert agent.security_scanner is not None


def test_reviewer_static_analysis():
    agent = ReviewerAgent()
    files = {
        "test.py": "def foo(items=[]):\n    pass\n",
    }
    import asyncio
    result = asyncio.run(agent.review(files=files))
    assert result.count >= 1


def test_reviewer_parse_no_issues():
    agent = ReviewerAgent()
    result = agent._parse_response("OK: No issues found.")
    assert result.passed


def test_reviewer_parse_single_issue():
    agent = ReviewerAgent()
    text = """ISSUE: bug | high | main.py:10 | Null reference error
SUGGESTION: Check for None before dereferencing"""
    result = agent._parse_response(text)
    assert result.count == 1
    assert result.issues[0].file == "main.py"
    assert result.issues[0].line == 10


def test_reviewer_parse_multiple_issues():
    agent = ReviewerAgent()
    text = """ISSUE: bug | high | a.py:1 | Bug one
ISSUE: security | critical | b.py:2 | Security issue"""
    result = agent._parse_response(text)
    assert result.count == 2


def test_reviewer_build_prompt():
    agent = ReviewerAgent()
    prompt = agent._build_review_prompt(
        diff_info="+ def foo(): pass",
        spec_summary="Add foo function",
        rules="- Use type hints",
    )
    assert "Add foo function" in prompt
    assert "Use type hints" in prompt
    assert "+ def foo(): pass" in prompt
