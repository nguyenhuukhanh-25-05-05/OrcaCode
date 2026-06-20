"""Tests for DiffValidator."""

from core.validator.diff_validator import DiffValidator


def setup_module():
    global _validator
    _validator = DiffValidator()


SIMPLE_DIFF = """--- a/app.py
+++ b/app.py
@@ -1,3 +1,4 @@
 hello world
+new line
 old line
-end line
+end line updated
"""

INVALID_DIFF = """some random text
not a diff at all
"""

DANGEROUS_DIFF = """--- a/../etc/passwd
+++ b/../etc/passwd
@@ -1,1 +1,1 @@
-root:x:0:0:root:/root:/bin/bash
+evil:x:0:0:evil:/root:/bin/bash
"""


class TestParseDiff:
    def test_parse_valid(self):
        parsed = _validator.parse_diff(SIMPLE_DIFF)
        assert parsed is not None
        assert parsed.old_path == "a/app.py"
        assert parsed.new_path == "b/app.py"
        assert len(parsed.hunks) == 1
        assert parsed.is_valid

    def test_parse_invalid(self):
        parsed = _validator.parse_diff(INVALID_DIFF)
        assert parsed is not None
        assert parsed.is_valid is False

    def test_parse_empty(self):
        parsed = _validator.parse_diff("")
        assert parsed is None

    def test_parse_none(self):
        parsed = _validator.parse_diff(None)  # type: ignore
        assert parsed is None


class TestValidateDiffFormat:
    def test_valid_format(self):
        r = _validator.validate_diff_format(SIMPLE_DIFF)
        assert r.passed is True

    def test_invalid_format(self):
        r = _validator.validate_diff_format(INVALID_DIFF)
        assert r.passed is False
        assert r.error_count >= 1

    def test_empty_diff(self):
        r = _validator.validate_diff_format("")
        assert r.passed is False

    def test_missing_hunk(self):
        r = _validator.validate_diff_format("--- a/x\n+++ b/x\n")
        assert r.passed is False


class TestValidateDiffPaths:
    def test_valid_paths(self, tmp_path):
        p = tmp_path / "app.py"
        p.write_text("")
        diff = f"--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-old\n+new"
        r = _validator.validate_diff_paths(diff, project_root=str(tmp_path))
        assert r.passed is True

    def test_dev_null(self):
        diff = "--- /dev/null\n+++ b/new.py\n@@ -0,0 +1 @@\n+new file"
        r = _validator.validate_diff_paths(diff)
        assert r.passed is True

    def test_non_existent_path(self, tmp_path):
        diff = "--- a/nonexistent/deep/file.py\n+++ b/nonexistent/deep/file.py\n@@ -1 +1 @@\n-old\n+new"
        r = _validator.validate_diff_paths(diff, project_root=str(tmp_path))
        assert r.passed is False  # parent dir doesn't exist


class TestValidateDiffNoDangerous:
    def test_safe_diff(self):
        r = _validator.validate_diff_no_dangerous(SIMPLE_DIFF)
        assert r.passed is True

    def test_dangerous_diff(self):
        r = _validator.validate_diff_no_dangerous(DANGEROUS_DIFF)
        assert r.passed is False
        assert r.error_count >= 1


class TestValidateDiffComplete:
    def test_covers_expected(self):
        parsed = _validator.parse_diff(SIMPLE_DIFF)
        r = _validator.validate_diff_complete(parsed, {"app.py"})
        assert r.passed is True

    def test_unexpected_file(self):
        parsed = _validator.parse_diff(SIMPLE_DIFF)
        r = _validator.validate_diff_complete(parsed, {"other.py"})
        assert r.passed is False

    def test_invalid_parsed(self):
        parsed = _validator.parse_diff(INVALID_DIFF)
        r = _validator.validate_diff_complete(parsed, {"other.py"})
        assert r.passed is False


class TestValidateDiff:
    def test_full_validation_valid(self, tmp_path):
        p = tmp_path / "app.py"
        p.write_text("")
        diff = f"--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-old\n+new"
        r = _validator.validate_diff(diff, project_root=str(tmp_path), expected_files={"app.py"})
        assert r.passed is True

    def test_full_validation_dangerous(self):
        r = _validator.validate_diff(DANGEROUS_DIFF)
        assert r.passed is False

    def test_full_validation_invalid(self, tmp_path):
        r = _validator.validate_diff(INVALID_DIFF, project_root=str(tmp_path))
        assert r.passed is False


class TestDiffHunkHander:
    def test_parse_with_line_counts(self):
        diff = """--- a/test.txt
+++ b/test.txt
@@ -1,5 +1,7 @@
 line1
 line2
+inserted1
+inserted2
 line3
 line4
 line5
"""
        parsed = _validator.parse_diff(diff)
        assert parsed is not None
        assert len(parsed.hunks) == 1
        assert parsed.hunks[0].old_start == 1
        assert parsed.hunks[0].old_count == 5
        assert parsed.hunks[0].new_start == 1
        assert parsed.hunks[0].new_count == 7

    def test_parse_multiple_hunks(self):
        diff = """--- a/file.txt
+++ b/file.txt
@@ -1,3 +1,4 @@
 a
 b
+c
@@ -10,5 +10,6 @@
 d
 e
+f
 g
"""
        parsed = _validator.parse_diff(diff)
        assert parsed is not None
        assert len(parsed.hunks) == 2
