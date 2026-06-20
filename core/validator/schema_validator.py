"""SchemaValidator — validates file structure, response format, and data schemas."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Optional

from core.validator.models import ValidationCategory, ValidationIssue, ValidationResult, ValidationSeverity


class SchemaValidator:
    """Validates schemas, formats, and structural integrity of files and responses."""

    # AI response section markers
    REQUIRED_DONE_SECTIONS = ["<DONE", "<TASK_REVIEW", "<PLAN_REVIEW"]
    REQUIRED_TASK_REVIEW_FIELDS = ["files", "checks", "issues", "status"]

    def validate_json_string(self, text: str, file: str = "") -> ValidationResult:
        """Parse and validate a JSON string."""
        try:
            json.loads(text)
            return ValidationResult.ok()
        except json.JSONDecodeError as e:
            return ValidationResult.error(
                f"Invalid JSON: {e.msg}",
                category=ValidationCategory.SCHEMA,
                file=file,
                line=e.lineno,
            )

    def validate_json_file(self, path: str) -> ValidationResult:
        """Read and validate a JSON file."""
        try:
            content = Path(path).read_text(encoding="utf-8")
            return self.validate_json_string(content, file=path)
        except FileNotFoundError:
            return ValidationResult.error(f"File not found: {path}", category=ValidationCategory.CONSISTENCY, file=path)
        except UnicodeDecodeError:
            return ValidationResult.error(f"File is not valid UTF-8: {path}", category=ValidationCategory.FORMAT, file=path)

    def validate_json_schema(self, data: Any, schema: dict, file: str = "") -> ValidationResult:
        """Validate data against a JSON schema (basic type/required checks)."""
        issues: list[ValidationIssue] = []

        required = schema.get("required", [])
        properties = schema.get("properties", {})

        for field in required:
            if field not in data:
                issues.append(ValidationIssue(
                    category=ValidationCategory.SCHEMA,
                    severity=ValidationSeverity.ERROR,
                    message=f"Missing required field: {field}",
                    file=file,
                ))

        for key, value in data.items() if isinstance(data, dict) else []:
            if key in properties:
                expected_type = properties[key].get("type", "")
                if expected_type == "string" and not isinstance(value, str):
                    issues.append(ValidationIssue(
                        category=ValidationCategory.SCHEMA,
                        severity=ValidationSeverity.ERROR,
                        message=f"Field '{key}' should be string, got {type(value).__name__}",
                        file=file,
                    ))
                elif expected_type == "integer" and not isinstance(value, int):
                    issues.append(ValidationIssue(
                        category=ValidationCategory.SCHEMA,
                        severity=ValidationSeverity.ERROR,
                        message=f"Field '{key}' should be integer, got {type(value).__name__}",
                        file=file,
                    ))
                elif expected_type == "array" and not isinstance(value, (list, tuple)):
                    issues.append(ValidationIssue(
                        category=ValidationCategory.SCHEMA,
                        severity=ValidationSeverity.ERROR,
                        message=f"Field '{key}' should be array, got {type(value).__name__}",
                        file=file,
                    ))
                elif expected_type == "boolean" and not isinstance(value, bool):
                    issues.append(ValidationIssue(
                        category=ValidationCategory.SCHEMA,
                        severity=ValidationSeverity.ERROR,
                        message=f"Field '{key}' should be boolean, got {type(value).__name__}",
                        file=file,
                    ))

        if issues:
            return ValidationResult(issues=issues)
        return ValidationResult.ok()

    def validate_response_format(self, text: str, required_sections: Optional[list[str]] = None) -> ValidationResult:
        """Check AI response contains required section markers."""
        sections = required_sections or self.REQUIRED_DONE_SECTIONS
        missing = [s for s in sections if s not in text]

        if missing:
            return ValidationResult.error(
                f"Missing required sections: {', '.join(missing)}",
                category=ValidationCategory.FORMAT,
            )
        return ValidationResult.ok()

    def validate_done_format(self, text: str) -> ValidationResult:
        """Validate <DONE/> tag format."""
        if not re.search(r'<DONE\s*/?>', text, re.IGNORECASE):
            return ValidationResult.error(
                "Missing <DONE/> tag in AI response",
                category=ValidationCategory.FORMAT,
            )
        return ValidationResult.ok()

    def validate_task_review_format(self, text: str) -> ValidationResult:
        """Check that <TASK_REVIEW> block has all required fields."""
        match = re.search(r'<TASK_REVIEW>(.*?)</TASK_REVIEW>', text, re.DOTALL | re.IGNORECASE)
        if not match:
            return ValidationResult.error(
                "Missing <TASK_REVIEW> block",
                category=ValidationCategory.FORMAT,
            )

        block = match.group(1)
        missing = [f for f in self.REQUIRED_TASK_REVIEW_FIELDS if f not in block.lower()]

        if missing:
            return ValidationResult.warning(
                f"TASK_REVIEW missing fields: {', '.join(missing)}",
                category=ValidationCategory.FORMAT,
            )
        return ValidationResult.ok()

    def validate_file_extension(self, path: str, allowed_extensions: Optional[list[str]] = None) -> ValidationResult:
        """Check file has an allowed extension."""
        if allowed_extensions is None:
            return ValidationResult.ok()

        ext = os.path.splitext(path)[1].lower()
        if ext and ext not in allowed_extensions:
            return ValidationResult.warning(
                f"File extension '{ext}' not in allowed list: {allowed_extensions}",
                category=ValidationCategory.SCHEMA,
                file=path,
            )
        return ValidationResult.ok()

    def validate_section_markers(self, content: str, file: str = "") -> ValidationResult:
        """Check that generated files have proper section markers (HTML, Python, etc.)."""
        ext = os.path.splitext(file)[1].lower() if file else ""
        issues: list[ValidationIssue] = []

        if ext == ".html":
            if "<!DOCTYPE HTML>" not in content.upper():
                issues.append(ValidationIssue(
                    category=ValidationCategory.STRUCTURE,
                    severity=ValidationSeverity.WARNING,
                    message="HTML file missing DOCTYPE declaration",
                    file=file,
                ))
            if "<html" not in content.lower():
                issues.append(ValidationIssue(
                    category=ValidationCategory.STRUCTURE,
                    severity=ValidationSeverity.ERROR,
                    message="HTML file missing <html> tag",
                    file=file,
                ))
            if "</html>" not in content.lower():
                issues.append(ValidationIssue(
                    category=ValidationCategory.STRUCTURE,
                    severity=ValidationSeverity.ERROR,
                    message="HTML file missing </html> closing tag",
                    file=file,
                ))

        elif ext == ".py":
            if "def " not in content and "class " not in content:
                issues.append(ValidationIssue(
                    category=ValidationCategory.STRUCTURE,
                    severity=ValidationSeverity.WARNING,
                    message="Python file has no function or class definitions",
                    file=file,
                ))

        if issues:
            return ValidationResult(issues=issues)
        return ValidationResult.ok()
