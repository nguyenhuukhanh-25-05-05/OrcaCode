"""Tests for ContextCollector — unified context interface."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from core.context.collector import ContextCollector
from core.planner import PlanStep


def _make_tmp_project():
    tmp = Path(tempfile.mkdtemp())
    (tmp / "src").mkdir()
    (tmp / "src" / "main.py").write_text("def main():\n    pass\n", encoding="utf-8")
    return tmp


class _MockMemory:
    def load_instructions(self, prompt):
        return "- Rule 1\n- Rule 2"


class _MockContextSvc:
    def build_context(self, prompt):
        return "Mock context from ContextService"


class _MockBlueprint:
    def build_blueprint(self):
        return {"src/main.py": {"classes": [], "functions": [{"name": "main", "doc": ""}]}}

    def get_relevant_blueprint(self, prompt):
        return "Relevant: main()"


class _MockArchGraph:
    def get_context_for_ai(self):
        return "Arch: main.py -> utils.py"

    def render_tree(self):
        return "src/main.py\n  └── src/utils.py"


class _MockSmartContext:
    def build_file_context(self, file_path, user_prompt=""):
        return f"### `{file_path}`\n\n```\ndef main():\n    pass\n```"


def test_init():
    with tempfile.TemporaryDirectory() as tmp:
        c = ContextCollector(project_root=tmp)
        assert c.root == Path(tmp)
        assert c.project_memory is not None


def test_collect_step_context_with_files():
    tmp = _make_tmp_project()
    c = ContextCollector(
        project_root=str(tmp),
        smart_context=_MockSmartContext(),
        memory=_MockMemory(),
    )
    step = PlanStep(id=1, description="Add main", files=["src/main.py"])
    result = c.collect_step_context(step)
    assert "src/main.py" in result
    assert "Rule 1" in result
    assert "Relevant Files" in result


def test_collect_step_context_no_files():
    tmp = _make_tmp_project()
    c = ContextCollector(project_root=str(tmp), memory=_MockMemory())
    step = PlanStep(id=1, description="Analyze only", files=[])
    result = c.collect_step_context(step)
    assert "Rule 1" in result  # instructions still included


def test_collect_step_context_no_files_minimal():
    """Without memory service, no files yields empty context."""
    tmp = _make_tmp_project()
    c = ContextCollector(project_root=str(tmp))
    step = PlanStep(id=1, description="Analyze only", files=[])
    result = c.collect_step_context(step)
    assert result == ""


def test_collect_step_context_file_missing():
    with tempfile.TemporaryDirectory() as tmp:
        c = ContextCollector(project_root=tmp)
        step = PlanStep(id=1, description="Missing file", files=["not_here.py"])
        result = c.collect_step_context(step)
        assert "not found" in result


def test_get_full_context():
    tmp = _make_tmp_project()
    c = ContextCollector(
        project_root=str(tmp),
        context_svc=_MockContextSvc(),
        arch_graph=_MockArchGraph(),
        blueprint_svc=_MockBlueprint(),
    )
    result = c.get_full_context("add feature")
    assert "Mock context" in result
    assert "Arch:" in result
    assert "Relevant:" in result


def test_get_full_context_minimal():
    with tempfile.TemporaryDirectory() as tmp:
        c = ContextCollector(project_root=tmp)
        result = c.get_full_context("test")
        assert result == ""


def test_refresh_memory_files():
    tmp = _make_tmp_project()
    c = ContextCollector(
        project_root=str(tmp),
        arch_graph=_MockArchGraph(),
        blueprint_svc=_MockBlueprint(),
        memory=_MockMemory(),
    )
    c.refresh_memory_files()
    assert c.project_memory._map_path.exists()
    assert c.project_memory._arch_path.exists()
    assert c.project_memory._rules_path.exists()


def test_refresh_memory_files_partial():
    """Should not crash when some services are missing."""
    with tempfile.TemporaryDirectory() as tmp:
        c = ContextCollector(project_root=tmp)
        c.refresh_memory_files()  # no exception
        # Files should exist (empty templates)
        assert c.project_memory._map_path.exists()
        assert c.project_memory._arch_path.exists()
        assert c.project_memory._rules_path.exists()


def test_clear_memory_files():
    with tempfile.TemporaryDirectory() as tmp:
        c = ContextCollector(project_root=tmp)
        c.refresh_memory_files()
        assert c.project_memory._map_path.exists()
        c.clear_memory_files()
        assert not c.project_memory._map_path.exists()
        assert not c.project_memory._arch_path.exists()
        assert not c.project_memory._rules_path.exists()


def test_read_file_for_ai_smart_context():
    tmp = _make_tmp_project()
    c = ContextCollector(
        project_root=str(tmp),
        smart_context=_MockSmartContext(),
    )
    result = c._read_file_for_ai("src/main.py")
    assert "def main():" in result


def test_read_file_for_ai_fallback():
    tmp = _make_tmp_project()
    c = ContextCollector(project_root=str(tmp))  # no smart_context
    result = c._read_file_for_ai("src/main.py")
    assert "def main():" in result


def test_read_file_for_ai_missing():
    with tempfile.TemporaryDirectory() as tmp:
        c = ContextCollector(project_root=tmp)
        result = c._read_file_for_ai("nonexistent.py")
        assert "not found" in result
