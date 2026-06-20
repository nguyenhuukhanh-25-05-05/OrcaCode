"""Tests for SchemaValidator."""

import tempfile
from pathlib import Path

from core.validator.schema_validator import SchemaValidator


def setup_module():
    global _validator
    _validator = SchemaValidator()


class TestValidateJson:
    def test_valid_json(self):
        r = _validator.validate_json_string('{"a": 1}')
        assert r.passed is True

    def test_invalid_json(self):
        r = _validator.validate_json_string('{invalid}')
        assert r.passed is False

    def test_json_file_valid(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w") as f:
            f.write('{"valid": true}')
            path = f.name
        try:
            r = _validator.validate_json_file(path)
            assert r.passed is True
        finally:
            Path(path).unlink(missing_ok=True)

    def test_json_file_not_found(self):
        r = _validator.validate_json_file("/nonexistent/file.json")
        assert r.passed is False


class TestJsonSchema:
    def test_valid_against_schema(self):
        data = {"name": "test", "count": 5, "items": []}
        schema = {
            "required": ["name", "count"],
            "properties": {
                "name": {"type": "string"},
                "count": {"type": "integer"},
                "items": {"type": "array"},
            },
        }
        r = _validator.validate_json_schema(data, schema)
        assert r.passed is True

    def test_missing_required(self):
        data = {"name": "test"}
        schema = {"required": ["name", "count"]}
        r = _validator.validate_json_schema(data, schema)
        assert r.passed is False

    def test_wrong_type(self):
        data = {"name": 123}
        schema = {"properties": {"name": {"type": "string"}}}
        r = _validator.validate_json_schema(data, schema)
        assert r.passed is False


class TestResponseFormat:
    def test_has_sections(self):
        r = _validator.validate_response_format("some text <DONE/> <TASK_REVIEW>ok</TASK_REVIEW> done", required_sections=["<DONE/>", "<TASK_REVIEW"])
        assert r.passed is True

    def test_missing_sections(self):
        r = _validator.validate_response_format("just text without markers")
        assert r.passed is False

    def test_custom_sections(self):
        r = _validator.validate_response_format("hello <FOO/> world", required_sections=["<FOO/>"])
        assert r.passed is True


class TestDoneFormat:
    def test_valid_done(self):
        r = _validator.validate_done_format("we are done <DONE/>")
        assert r.passed is True

    def test_missing_done(self):
        r = _validator.validate_done_format("no done here")
        assert r.passed is False

    def test_self_closing_variant(self):
        r = _validator.validate_done_format("<DONE />")
        assert r.passed is True


class TestTaskReviewFormat:
    def test_complete_review(self):
        text = "<TASK_REVIEW> Files: app.py. Checks: passed. Issues: none. Status: done. </TASK_REVIEW>"
        r = _validator.validate_task_review_format(text)
        assert r.passed is True

    def test_missing_review(self):
        r = _validator.validate_task_review_format("no review here")
        assert r.passed is False

    def test_missing_fields(self):
        text = "<TASK_REVIEW> just some text </TASK_REVIEW>"
        r = _validator.validate_task_review_format(text)
        assert r.passed is False
        assert r.warning_count >= 1


class TestFileExtension:
    def test_allowed(self):
        r = _validator.validate_file_extension("app.py", [".py", ".js"])
        assert r.passed is True

    def test_not_allowed(self):
        r = _validator.validate_file_extension("app.exe", [".py", ".js"])
        assert r.passed is False
        assert r.warning_count >= 1

    def test_no_allowed_list(self):
        r = _validator.validate_file_extension("app.exe")
        assert r.passed is True


class TestSectionMarkers:
    def test_html_full(self):
        r = _validator.validate_section_markers(
            "<!DOCTYPE HTML><HTML><body></body></HTML>",
            file="index.html",
        )
        assert r.passed is True

    def test_html_missing_doctype(self):
        r = _validator.validate_section_markers(
            "<html><body></body></html>",
            file="index.html",
        )
        assert r.passed is False
        assert r.warning_count >= 1

    def test_html_missing_html_tag(self):
        r = _validator.validate_section_markers(
            "<!DOCTYPE html><body></body>",
            file="index.html",
        )
        assert r.passed is False

    def test_python_with_def(self):
        r = _validator.validate_section_markers("def foo(): pass", file="test.py")
        assert r.passed is True

    def test_python_empty(self):
        r = _validator.validate_section_markers("x = 1", file="test.py")
        assert r.passed is False

    def test_unknown_ext(self):
        r = _validator.validate_section_markers("some content", file="data.bin")
        assert r.passed is True
