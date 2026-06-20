"""Tests for tool runners."""

from core.evidence.runners import BuildRunner, LintRunner, TestRunner, ToolRunner


def test_tool_runner_basic():
    runner = ToolRunner("echo hello")
    result = runner.run()
    assert result.exit_code == 0
    assert "hello" in result.stdout
    assert result.passed is True


def test_tool_runner_failure():
    runner = ToolRunner("cmd_that_does_not_exist_xyz123")
    result = runner.run()
    assert result.exit_code != 0
    assert result.passed is False


def test_tool_runner_timeout():
    runner = ToolRunner("ping 127.0.0.1 -n 10", timeout=1)
    result = runner.run()
    assert result.passed is False


def test_run_result_truncate():
    result = ToolRunner("echo line1 & echo line2 & echo line3").run()
    truncated = result.truncate(max_lines=2)
    assert "..." in truncated
    assert "line1" in truncated


def test_build_runner_detects_npm(tmp_path):
    """BuildRunner should detect package.json and suggest npm run build."""
    (tmp_path / "package.json").write_text('{"name":"test"}', encoding="utf-8")
    cmd = BuildRunner._detect_build_command(str(tmp_path))
    assert "npm run build" in cmd


def test_lint_runner_detects_ruff(tmp_path):
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    (tmp_path / ".ruff.toml").write_text("", encoding="utf-8")
    cmd = LintRunner._detect_lint_command(str(tmp_path))
    assert "ruff" in cmd


def test_test_runner_detects_python(tmp_path):
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    cmd = TestRunner._detect_test_command(str(tmp_path))
    assert "pytest" in cmd
