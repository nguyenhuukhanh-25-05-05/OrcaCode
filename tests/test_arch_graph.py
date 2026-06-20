"""Tests for Architecture Graph service."""
import pytest
from core.services.arch_graph import ArchGraph, Node
from pathlib import Path


@pytest.fixture
def simple_project(tmp_path):
    """Create a simple project with import relationships."""
    # app.py imports utils.py
    (tmp_path / "app.py").write_text("from utils import helper\n\ndef main():\n    helper.run()\n")
    # utils.py imports models.py  
    (tmp_path / "utils.py").write_text("from models import User\n\nclass helper:\n    def run(): pass\n")
    # models.py is a leaf (no imports)
    (tmp_path / "models.py").write_text("class User:\n    pass\n")
    # styles.css imports base.css
    (tmp_path / "styles.css").write_text('@import "base.css";\n\nbody { color: blue; }\n')
    # base.css is a style leaf
    (tmp_path / "base.css").write_text("body { margin: 0; }\n")
    return str(tmp_path)


class TestBuildGraph:
    def test_basic_scan(self, simple_project):
        g = ArchGraph(simple_project)
        n = g.build_graph()
        assert n >= 5  # At least 5 files found
        assert "app.py" in g.nodes
        assert "utils.py" in g.nodes
        assert "models.py" in g.nodes

    def test_python_imports(self, simple_project):
        g = ArchGraph(simple_project)
        g.build_graph()
        app = g.nodes["app.py"]
        # app.py should import utils.py
        assert "utils.py" in app.imports

    def test_reverse_edges(self, simple_project):
        g = ArchGraph(simple_project)
        g.build_graph()
        utils = g.nodes["utils.py"]
        # utils.py should be imported by app.py
        assert "app.py" in utils.imported_by

    def test_css_imports(self, simple_project):
        g = ArchGraph(simple_project)
        g.build_graph()
        styles = g.nodes["styles.css"]
        assert "base.css" in styles.imports

    def test_entry_points(self, simple_project):
        g = ArchGraph(simple_project)
        g.build_graph()
        # app.py is imported by nothing -> entry point
        app = g.nodes["app.py"]
        assert app.is_entry_point

    def test_models_is_leaf(self, simple_project):
        g = ArchGraph(simple_project)
        g.build_graph()
        models = g.nodes["models.py"]
        assert len(models.imports) == 0  # Leaf node, no imports

    def test_max_files_limit(self, simple_project):
        g = ArchGraph(simple_project)
        n = g.build_graph(max_files=3)
        assert n <= 3


class TestRender:
    def test_render_tree(self, simple_project):
        g = ArchGraph(simple_project)
        g.build_graph()
        tree = g.render_tree()
        # Should contain entry point files
        assert "app.py" in tree
        assert "ARCH DEP GRAPH" in tree

    def test_render_empty(self, tmp_path):
        g = ArchGraph(str(tmp_path))
        g.build_graph()
        tree = g.render_tree()
        # In a truly empty dir, there should be no relationships found
        assert "no import relationships found" in tree.lower() or "ARCH DEP GRAPH" in tree

    def test_render_depth_limit(self, simple_project):
        """Deep chains should be truncated."""
        g = ArchGraph(simple_project)
        g.build_graph()
        tree = g.render_tree(max_depth=1, max_nodes=10)
        # Should not crash with max_depth
        assert "app.py" in tree


class TestHighlight:
    def test_highlight_file(self, simple_project):
        g = ArchGraph(simple_project)
        g.build_graph()
        g.highlight_file("app.py")
        assert g.active_files  

    def test_highlight_shows_in_tree(self, simple_project):
        g = ArchGraph(simple_project)
        g.build_graph()
        g.highlight_file("app.py")
        tree = g.render_tree()
        assert "●" in tree or "◉" in tree or "active" in tree.lower()

    def test_unhighlight(self, simple_project):
        g = ArchGraph(simple_project)
        g.build_graph()
        g.highlight_file("app.py")
        assert g.active_files
        g.unhighlight_file("app.py")
        assert "app.py" not in g.active_files


class TestAIContext:
    def test_context_for_ai(self, simple_project):
        g = ArchGraph(simple_project)
        g.build_graph()
        g.highlight_file("app.py")
        ctx = g.get_context_for_ai()
        assert "Architecture Context" in ctx
        assert "app.py" in ctx
        assert "utils.py" in ctx  # Should include import chains

    def test_context_empty(self, simple_project):
        g = ArchGraph(simple_project)
        g.build_graph()
        ctx = g.get_context_for_ai(focus_files=["nonexistent.py"])
        assert "Architecture Context" in ctx

    def test_context_truncation(self, simple_project):
        g = ArchGraph(simple_project)
        for i in range(20):
            g.nodes[f"file{i}.py"] = Node(path=f"file{i}.py")
        g.build_graph()
        ctx = g.get_context_for_ai(max_lines=10)
        lines = ctx.split("\n")
        assert len(lines) <= 12  # A few extra for header/footer


class TestNode:
    def test_node_defaults(self):
        n = Node(path="test.py")
        assert n.imports == []
        assert n.imported_by == []
        assert n.depth == 0
        assert n.file_type == ""
        assert not n.is_active


if __name__ == "__main__":
    pytest.main([__file__, "-v"])