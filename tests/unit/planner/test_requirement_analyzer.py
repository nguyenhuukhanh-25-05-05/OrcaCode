"""Tests for RequirementAnalyzer."""

from core.planner.requirement_analyzer import RequirementAnalyzer


def test_analyze_simple():
    spec = RequirementAnalyzer.analyze("Add dark mode to Settings page")
    assert spec.summary == "Add dark mode to Settings page"
    assert spec.is_valid is True


def test_analyze_with_file():
    spec = RequirementAnalyzer.analyze("Modify src/pages/Settings.tsx to add dark mode")
    assert "src/pages/Settings.tsx" in spec.files_involved
    assert "Files" in str(spec.scope)


def test_analyze_ui_scope():
    spec = RequirementAnalyzer.analyze("Create a new React component for the dashboard")
    assert any("UI" in s for s in spec.scope)


def test_analyze_api_scope():
    spec = RequirementAnalyzer.analyze("Add a new API endpoint for user authentication")
    assert any("API" in s for s in spec.scope)


def test_analyze_security_scope():
    spec = RequirementAnalyzer.analyze("Add authentication and permission system")
    assert any("Security" in s for s in spec.scope)


def test_analyze_constraints():
    spec = RequirementAnalyzer.analyze("Add new feature but don't break existing tests")
    assert len(spec.constraints) > 0


def test_analyze_risks():
    spec = RequirementAnalyzer.analyze("Refactor the complex payment processing system")
    assert len(spec.risks) > 0
