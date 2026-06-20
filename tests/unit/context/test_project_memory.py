"""Tests for ProjectMemory — auto-maintained memory files."""

import tempfile
from pathlib import Path

from core.context.project_memory import ProjectMemory


def test_init_creates_dir():
    with tempfile.TemporaryDirectory() as tmp:
        pm = ProjectMemory(tmp)
        assert pm.memory_dir.exists()
        assert pm.memory_dir.name == ".orca"


def test_update_project_map_with_data():
    with tempfile.TemporaryDirectory() as tmp:
        pm = ProjectMemory(tmp)
        blueprint = {
            "src/main.py": {
                "classes": [{"name": "App", "doc": "Main application class"}],
                "functions": [{"name": "run", "doc": "Entry point"}],
            }
        }
        content = pm.update_project_map(blueprint)
        assert "App" in content
        assert "src/main.py" in content
        assert pm._map_path.exists()
        assert "Main application class" in content


def test_update_project_map_empty():
    with tempfile.TemporaryDirectory() as tmp:
        pm = ProjectMemory(tmp)
        content = pm.update_project_map()
        assert "No blueprint data" in content


def test_update_architecture():
    with tempfile.TemporaryDirectory() as tmp:
        pm = ProjectMemory(tmp)
        content = pm.update_architecture(
            arch_summary="React SPA with Flask backend",
            dep_graph="src/App.tsx -> src/hooks/useTheme.ts",
        )
        assert "React SPA" in content
        assert "src/App.tsx" in content
        assert pm.architecture_path.exists()


def test_update_architecture_empty():
    with tempfile.TemporaryDirectory() as tmp:
        pm = ProjectMemory(tmp)
        content = pm.update_architecture()
        assert "not yet generated" in content


def test_update_rules_with_list():
    with tempfile.TemporaryDirectory() as tmp:
        pm = ProjectMemory(tmp)
        rules = ["Use named exports", "No `any` type"]
        content = pm.update_rules(rules)
        assert "Use named exports" in content
        assert "No `any` type" in content
        assert pm.rules_path.exists()


def test_update_rules_preserves_existing():
    with tempfile.TemporaryDirectory() as tmp:
        pm = ProjectMemory(tmp)
        pm._rules_path.write_text("# Rules\n- Keep it clean\n", encoding="utf-8")
        content = pm.update_rules(None)
        assert "Keep it clean" in content


def test_update_rules_template():
    with tempfile.TemporaryDirectory() as tmp:
        pm = ProjectMemory(tmp)
        content = pm.update_rules()
        assert "No rules defined yet" in content


def test_load_all():
    with tempfile.TemporaryDirectory() as tmp:
        pm = ProjectMemory(tmp)
        pm.update_project_map({"src/main.py": {"classes": [], "functions": [{"name": "main", "doc": ""}]}})
        pm.update_architecture(arch_summary="CLI tool")
        pm.update_rules(["No print statements"])
        combined = pm.load_all()
        assert "src/main.py" in combined
        assert "CLI tool" in combined
        assert "No print statements" in combined


def test_load_all_empty():
    with tempfile.TemporaryDirectory() as tmp:
        pm = ProjectMemory(tmp)
        assert pm.load_all() == ""


def test_refresh_updates_all():
    with tempfile.TemporaryDirectory() as tmp:
        pm = ProjectMemory(tmp)
        pm.refresh(
            blueprint_data={"src/main.py": {"classes": [], "functions": [{"name": "main", "doc": ""}]}},
            arch_summary="CLI",
            dep_graph="main.py -> utils.py",
            rules=["No print"],
        )
        assert pm._map_path.exists()
        assert pm._arch_path.exists()
        assert pm._rules_path.exists()
        assert "src/main.py" in pm.load_project_map()
        assert "CLI" in pm.load_architecture()
        assert "No print" in pm.load_rules()


def test_custom_orca_dir():
    with tempfile.TemporaryDirectory() as tmp:
        custom = Path(tmp) / "custom_dir"
        pm = ProjectMemory(tmp, orca_dir=str(custom))
        assert pm.memory_dir == custom
        assert custom.exists()
