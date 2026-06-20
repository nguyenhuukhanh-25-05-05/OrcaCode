"""Tests for ProjectDetector."""

from core.evidence.project_detector import ProjectDetector, ProjectType


def test_detect_node(tmp_path):
    (tmp_path / "package.json").write_text('{"name":"test"}', encoding="utf-8")
    cfg = ProjectDetector.detect(str(tmp_path))
    assert cfg.type == ProjectType.NODE


def test_detect_python(tmp_path):
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    cfg = ProjectDetector.detect(str(tmp_path))
    assert cfg.type == ProjectType.PYTHON


def test_detect_setup_py(tmp_path):
    (tmp_path / "setup.py").write_text("", encoding="utf-8")
    cfg = ProjectDetector.detect(str(tmp_path))
    assert cfg.type == ProjectType.PYTHON


def test_detect_rust(tmp_path):
    (tmp_path / "Cargo.toml").write_text("", encoding="utf-8")
    cfg = ProjectDetector.detect(str(tmp_path))
    assert cfg.type == ProjectType.RUST


def test_detect_go(tmp_path):
    (tmp_path / "go.mod").write_text("", encoding="utf-8")
    cfg = ProjectDetector.detect(str(tmp_path))
    assert cfg.type == ProjectType.GO


def test_detect_unknown(tmp_path):
    cfg = ProjectDetector.detect(str(tmp_path))
    assert cfg.type == ProjectType.UNKNOWN


def test_python_config_has_build(tmp_path):
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    cfg = ProjectDetector.detect(str(tmp_path))
    assert cfg.has_build() is True
    assert cfg.has_test() is True
    assert cfg.has_lint() is True


def test_node_without_modules_has_no_build(tmp_path):
    (tmp_path / "package.json").write_text('{"name":"test"}', encoding="utf-8")
    cfg = ProjectDetector.detect(str(tmp_path))
    # No node_modules → no build command
    assert cfg.has_build() is False
