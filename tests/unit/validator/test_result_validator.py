"""Tests for ResultValidator."""

import tempfile
from pathlib import Path

from core.validator.result_validator import ResultValidator


def setup_module():
    global _validator
    _validator = ResultValidator()


class TestTestOutput:
    def test_pass_output(self):
        r = _validator.validate_test_output("ok 1 passed\nPASS\n")
        assert r.passed is True

    def test_fail_output(self):
        r = _validator.validate_test_output("FAIL: test_foo failed\nerrors: 1")
        assert r.passed is False
        assert r.error_count >= 1

    def test_empty_output(self):
        r = _validator.validate_test_output("")
        assert r.passed is False

    def test_skipped_only(self):
        r = _validator.validate_test_output("SKIP: no tests ran\nNo tests found")
        assert r.passed is False
        assert r.warning_count >= 1

    def test_pass_with_numbers(self):
        r = _validator.validate_test_output("3 passed, 2 warnings")
        assert r.passed is True

    def test_mixed_pass_fail(self):
        r = _validator.validate_test_output("\n1 failed\n10 passed")
        assert r.passed is False  # has failure


class TestBuildOutput:
    def test_success(self):
        r = _validator.validate_build_output("Build succeeded.\n")
        assert r.passed is True

    def test_error(self):
        r = _validator.validate_build_output("Build failed.\nerror: syntax error")
        assert r.passed is False
        assert r.error_count >= 1

    def test_empty_output(self):
        r = _validator.validate_build_output("")
        assert r.passed is False
        assert r.warning_count >= 1

    def test_with_warnings(self):
        r = _validator.validate_build_output("Build succeeded.\nwarning: unused variable")
        assert r.warning_count >= 1

    def test_compilation_success(self):
        r = _validator.validate_build_output("Compilation succeeded")
        assert r.passed is True


class TestOutputContains:
    def test_contains(self):
        r = _validator.validate_output_contains("hello world", "world")
        assert r.passed is True

    def test_not_contains(self):
        r = _validator.validate_output_contains("hello world", "foo")
        assert r.passed is False


class TestOutputLacks:
    def test_lacks(self):
        r = _validator.validate_output_lacks("hello world", "error")
        assert r.passed is True

    def test_contains_forbidden(self):
        r = _validator.validate_output_lacks("something error happened", "error")
        assert r.passed is False


class TestExitCode:
    def test_zero(self):
        r = _validator.validate_exit_code(0)
        assert r.passed is True

    def test_nonzero(self):
        r = _validator.validate_exit_code(1)
        assert r.passed is False


class TestFileExists:
    def test_exists(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            path = f.name
        try:
            r = _validator.validate_file_exists(path)
            assert r.passed is True
        finally:
            Path(path).unlink(missing_ok=True)

    def test_not_exists(self):
        r = _validator.validate_file_exists("/nonexistent/path/file.txt")
        assert r.passed is False


class TestFileNotEmpty:
    def test_not_empty(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w") as f:
            f.write("content")
            path = f.name
        try:
            r = _validator.validate_file_not_empty(path)
            assert r.passed is True
        finally:
            Path(path).unlink(missing_ok=True)

    def test_empty(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            path = f.name
        try:
            r = _validator.validate_file_not_empty(path)
            assert r.passed is False
            assert r.warning_count >= 1
        finally:
            Path(path).unlink(missing_ok=True)

    def test_not_exists(self):
        r = _validator.validate_file_not_empty("/nonexistent/file.txt")
        assert r.passed is False


class TestFileEncoding:
    def test_valid_utf8(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".py", mode="w", encoding="utf-8") as f:
            f.write("# coding: utf-8\nprint('hello')")
            path = f.name
        try:
            r = _validator.validate_file_encoding(path)
            assert r.passed is True
        finally:
            Path(path).unlink(missing_ok=True)

    def test_not_found(self):
        r = _validator.validate_file_encoding("/nonexistent/file.txt")
        assert r.passed is False


class TestTaskSummary:
    def test_mentions_files(self):
        r = _validator.validate_task_summary("modified app.py and test_app.py", {"app.py", "test_app.py"})
        assert r.passed is True

    def test_missing_file(self):
        r = _validator.validate_task_summary("only mentioned app.py", {"app.py", "secret.py"})
        assert r.passed is False
        assert r.warning_count >= 1


class TestResultsConsistency:
    def test_all_referenced(self):
        results = [{"path": "app.py", "status": "ok"}]
        r = _validator.validate_results_consistency(results, {"app.py"})
        assert r.passed is True

    def test_unreferenced_file(self):
        results = [{"path": "other.py", "status": "ok"}]
        r = _validator.validate_results_consistency(results, {"app.py"})
        assert r.passed is False
        assert r.warning_count >= 1
