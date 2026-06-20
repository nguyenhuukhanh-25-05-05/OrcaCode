"""Error Classifier – phân loại lỗi thành ENVIRONMENT / DIAGNOSTIC / CODE / UNKNOWN.

Pipeline:
  Tool Result / Error Text
       ↓
  ErrorClassifier.classify()
       ↓
  { category, actionable, should_stop, should_ask, action }
"""
from __future__ import annotations

import re
import ast
import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class ErrorCategory(str, Enum):
    """Phân cấp lỗi 3 mức: nhóm → lớp → chi tiết."""

    # ── ENVIRONMENT ──────────────────────────────────────────────────────
    ENVIRONMENT = "environment"
    ENV_FILESYSTEM = "environment.filesystem"
    ENV_FILESYSTEM_PERMISSION = "environment.filesystem.permission"
    ENV_FILESYSTEM_LOCKED = "environment.filesystem.locked"
    ENV_FILESYSTEM_ONEDRIVE = "environment.filesystem.onedrive"
    ENV_FILESYSTEM_ENCODING = "environment.filesystem.encoding"
    ENV_FILESYSTEM_DISK_FULL = "environment.filesystem.disk_full"
    ENV_RUNTIME = "environment.runtime"
    ENV_RUNTIME_MISSING = "environment.runtime.missing_interpreter"
    ENV_RUNTIME_VERSION = "environment.runtime.version_mismatch"
    ENV_RUNTIME_ENV = "environment.runtime.env_not_activated"
    ENV_DEPENDENCY = "environment.dependency"
    ENV_DEPENDENCY_MISSING = "environment.dependency.missing_package"
    ENV_DEPENDENCY_BROKEN = "environment.dependency.broken_package"
    ENV_DEPENDENCY_CONFLICT = "environment.dependency.conflict"

    # ── DIAGNOSTIC ───────────────────────────────────────────────────────
    DIAGNOSTIC = "diagnostic"
    DIAG_COMMAND = "diagnostic.command"
    DIAG_COMMAND_WRONG = "diagnostic.command.wrong_tool"
    DIAG_COMMAND_MISSING = "diagnostic.command.missing"
    DIAG_CONFIG = "diagnostic.config"
    DIAG_CONFIG_MISSING = "diagnostic.config.missing"
    DIAG_TEST = "diagnostic.test"
    DIAG_TEST_WRONG = "diagnostic.test.wrong_framework"

    # ── CODE ─────────────────────────────────────────────────────────────
    CODE = "code"
    CODE_SYNTAX = "code.syntax"
    CODE_SYNTAX_PYTHON = "code.syntax.python"
    CODE_SYNTAX_JS = "code.syntax.javascript"
    CODE_SYNTAX_HTML = "code.syntax.html"
    CODE_IMPORT = "code.import"
    CODE_IMPORT_MISSING = "code.import.missing"
    CODE_IMPORT_CIRCULAR = "code.import.circular"
    CODE_TYPE = "code.type"
    CODE_TYPE_MISMATCH = "code.type.mismatch"
    CODE_STRUCTURE = "code.structure"
    CODE_STRUCTURE_UNBALANCED = "code.structure.unbalanced_tag"
    CODE_LOGIC = "code.logic"
    CODE_LOGIC_RUNTIME = "code.logic.runtime_exception"
    CODE_LOGIC_REFERENCE = "code.logic.undefined_reference"

    # ── UNKNOWN ──────────────────────────────────────────────────────────
    UNKNOWN = "unknown"


@dataclass
class Classification:
    """Kết quả phân loại lỗi."""

    category: ErrorCategory
    root_cause: str = ""
    suggested_action: str = ""
    severity: str = "medium"
    confidence: float = 1.0  # 0.0 - 1.0

    @property
    def should_stop(self) -> bool:
        """ENVIRONMENT lỗi → STOP, không sửa code."""
        return self.category.value.startswith("environment")

    @property
    def should_ask(self) -> bool:
        """UNKNOWN hoặc confidence < 60% → hỏi user."""
        return self.category == ErrorCategory.UNKNOWN or self.confidence < 0.6

    @property
    def actionable(self) -> bool:
        """CODE lỗi + confidence đủ cao → có thể tự sửa."""
        return self.category.value.startswith("code") and self.confidence >= 0.6

    @property
    def is_diagnostic(self) -> bool:
        """DIAGNOSTIC → sửa command/tool, không sửa code."""
        return self.category.value.startswith("diagnostic")


# ── Patterns ──────────────────────────────────────────────────────────

# Pattern tuple: (regex, category, root_cause, action, confidence)
_ConfPattern = tuple[re.Pattern, ErrorCategory, str, str, float]

_ENV_PATTERNS: list[_ConfPattern] = [
    # Permission
    (re.compile(r"permission denied|access denied|eacces", re.IGNORECASE),
     ErrorCategory.ENV_FILESYSTEM_PERMISSION, "Permission denied",
     "Kiểm tra quyền ghi file. Không sửa code.", 0.98),
    # File locked
    (re.compile(r"file.*(?:locked|in use|being used|another process)", re.IGNORECASE),
     ErrorCategory.ENV_FILESYSTEM_LOCKED, "File is locked by another process",
     "Đợi OneDrive/antivirus nhả file. Không sửa code.", 0.95),
    # OneDrive
    (re.compile(r"onedrive|cloud.*sync", re.IGNORECASE),
     ErrorCategory.ENV_FILESYSTEM_ONEDRIVE, "OneDrive syncing conflict",
     "Tạm dừng OneDrive hoặc move project ra ngoài. Không sửa code.", 0.92),
    # Disk full
    (re.compile(r"disk full|no space left|disk quota", re.IGNORECASE),
     ErrorCategory.ENV_FILESYSTEM_DISK_FULL, "Disk full",
     "Giải phóng dung lượng ổ đĩa. Không sửa code.", 0.97),
    # Encoding
    (re.compile(r"unicodeencodeerror|unicodedecodeerror|character.*map|encoding", re.IGNORECASE),
     ErrorCategory.ENV_FILESYSTEM_ENCODING, "Path or file encoding issue",
     "Kiểm tra encoding của file/path. Không sửa code.", 0.88),
    # Missing interpreter
    (re.compile(r"(?:python|node|java|dotnet|go|rust).*(?:not found|not recognized|no such)",
     re.IGNORECASE),
     ErrorCategory.ENV_RUNTIME_MISSING, "Interpreter not found",
     "Cài đặt runtime. Không sửa code.", 0.95),
    # venv
    (re.compile(r"(?:virtualenv|venv|virtual environment).*(?:activate|not found)", re.IGNORECASE),
     ErrorCategory.ENV_RUNTIME_ENV, "Virtual env not activated",
     "Kích hoạt virtual environment. Không sửa code.", 0.90),
    # Missing package (ModuleNotFoundError, etc.)
    (re.compile(r"(?:modulenotfounderror|cannot find module|no module named|not found:.*package"
                r"|npm err.*not found|pip.*could not find)", re.IGNORECASE),
     ErrorCategory.ENV_DEPENDENCY_MISSING, "Missing package",
     "Cài đặt package: pip install / npm install. Không sửa code.", 0.95),
    # Broken package
    (re.compile(r"(?:broken|corrupt|incompatible|conflict|version.*not satisfied)", re.IGNORECASE),
     ErrorCategory.ENV_DEPENDENCY_BROKEN, "Broken or incompatible package",
     "Reinstall package. Không sửa code.", 0.85),
]

_DIAG_PATTERNS: list[_ConfPattern] = [
    # Wrong command
    (re.compile(r"(?:command not found|not a valid command|unknown command|bash:.*:)", re.IGNORECASE),
     ErrorCategory.DIAG_COMMAND_MISSING, "Command not found on system",
     "Kiểm tra lại command — có thể sai tên hoặc chưa cài tool.", 0.97),
    # Wrong test
    (re.compile(r"(?:no test|test failed|pytest.*error|npm test.*fail)", re.IGNORECASE),
     ErrorCategory.DIAG_TEST_WRONG, "Test command failed or misconfigured",
     "Kiểm tra test config (pytest.ini, jest.config). Có thể dùng sai framework.", 0.75),
    # Config not found
    (re.compile(r"(?:config.*not found|missing.*config|no.*tsconfig|no.*pytest)", re.IGNORECASE),
     ErrorCategory.DIAG_CONFIG_MISSING, "Required config file missing",
     "Tạo file config phù hợp hoặc chỉnh command.", 0.80),
]

_CODE_PATTERNS: list[_ConfPattern] = [
    # Python syntax
    (re.compile(r"(?:syntaxerror|invalid syntax|unexpected indent|unindent)", re.IGNORECASE),
     ErrorCategory.CODE_SYNTAX_PYTHON, "Python syntax error",
     "Sửa lỗi indent/cú pháp Python.", 0.98),
    # JS syntax
    (re.compile(r"(?:unexpected token|expected.*but found|parse error|syntax error)", re.IGNORECASE),
     ErrorCategory.CODE_SYNTAX_JS, "JavaScript syntax error",
     "Sửa lỗi cú pháp JS/TS.", 0.95),
    # HTML parse
    (re.compile(r"(?:html parse error|unclosed tag|unbalanced.*tag)", re.IGNORECASE),
     ErrorCategory.CODE_SYNTAX_HTML, "HTML structure error",
     "Sửa thẻ HTML không cân bằng.", 0.95),
    # Import error
    (re.compile(r"(?:importerror|import.*error|cannot import|cannot find name)", re.IGNORECASE),
     ErrorCategory.CODE_IMPORT_MISSING, "Import not found",
     "Thêm import hoặc sửa đường dẫn import.", 0.92),
    # Circular import
    (re.compile(r"(?:circular import|import.*circular)", re.IGNORECASE),
     ErrorCategory.CODE_IMPORT_CIRCULAR, "Circular import detected",
     "Tái cấu trúc module để tránh circular import.", 0.88),
    # NameError
    (re.compile(r"(?:nameerror|referenceerror|is not defined)", re.IGNORECASE),
     ErrorCategory.CODE_LOGIC_REFERENCE, "Undefined variable/function",
     "Khai báo hoặc import symbol còn thiếu.", 0.90),
    # TypeError
    (re.compile(r"(?:typeerror|type mismatch|cannot read property|cannot call)", re.IGNORECASE),
     ErrorCategory.CODE_TYPE_MISMATCH, "Type error",
     "Sửa kiểu dữ liệu hoặc thêm type check.", 0.85),
    # Unbalanced HTML tag
    (re.compile(r"(?:unbalanced|mở=.*đóng=|opening vs closing)", re.IGNORECASE),
     ErrorCategory.CODE_STRUCTURE_UNBALANCED, "Unbalanced HTML/JSX tag",
     "Đóng thẻ HTML/JSX bị thiếu.", 0.95),
]


class ErrorClassifier:
    """Central error classifier — phân loại lỗi từ tool result hoặc error text."""

    def classify(
        self,
        error_text: str = "",
        stderr: str = "",
        stdout: str = "",
        tool_type: str = "",
        file_path: str = "",
    ) -> Classification:
        combined = f"{error_text} {stderr} {stdout}"

        # 1. Thử ENVIRONMENT patterns
        for pat, cat, cause, action, conf in _ENV_PATTERNS:
            if pat.search(combined):
                return Classification(category=cat, root_cause=cause, suggested_action=action, severity="high", confidence=conf)

        # 2. Thử DIAGNOSTIC patterns
        for pat, cat, cause, action, conf in _DIAG_PATTERNS:
            if pat.search(combined):
                return Classification(category=cat, root_cause=cause, suggested_action=action, severity="medium", confidence=conf)

        # 3. Thử CODE patterns
        for pat, cat, cause, action, conf in _CODE_PATTERNS:
            if pat.search(combined):
                return Classification(category=cat, root_cause=cause, suggested_action=action, severity="medium", confidence=conf)

        # 4. File-specific checks (confidence cao vì dùng AST thật)
        if file_path and Path(file_path).exists():
            cls = self._classify_by_file(file_path)
            if cls:
                return cls

        # 5. Unknown
        return Classification(
            category=ErrorCategory.UNKNOWN,
            root_cause="Unrecognized error",
            suggested_action="Hỏi user để xác định nguyên nhân.",
            severity="unknown",
            confidence=0.0,
        )

    def classify_from_result(self, result: dict, tool_type: str = "") -> Classification:
        """Phân loại từ tool execution result dict."""
        error_text = result.get("summary", "")
        stderr = result.get("stderr", "")
        stdout = result.get("stdout", "")
        file_path = result.get("path", "")
        return self.classify(
            error_text=error_text,
            stderr=stderr,
            stdout=stdout,
            tool_type=tool_type,
            file_path=file_path,
        )

    def _classify_by_file(self, file_path: str) -> Optional[Classification]:
        """Phân loại dựa trên nội dung file thực tế (syntax check)."""
        full_path = Path(file_path)
        ext = full_path.suffix.lower()
        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return None

        try:
            if ext == ".py":
                ast.parse(content)
            elif ext in (".js", ".mjs", ".cjs"):
                import subprocess
                r = subprocess.run(
                    ["node", "--check", str(full_path)],
                    capture_output=True, text=True, timeout=10,
                )
                if r.returncode != 0:
                    return Classification(
                        category=ErrorCategory.CODE_SYNTAX_JS,
                        root_cause="JavaScript syntax error from node --check",
                        suggested_action=r.stderr.strip()[:200],
                        severity="medium",
                        confidence=0.98,
                    )
            elif ext == ".json":
                json.loads(content)
            return None  # Syntax OK
        except SyntaxError as e:
            return Classification(
                category=ErrorCategory.CODE_SYNTAX_PYTHON,
                root_cause=f"Python syntax error: {e}",
                suggested_action="Sửa lỗi cú pháp.",
                severity="medium",
                confidence=0.98,
            )
        except json.JSONDecodeError as e:
            return Classification(
                category=ErrorCategory.CODE_SYNTAX_HTML,
                root_cause=f"JSON parse error: {e}",
                suggested_action="Sửa JSON.",
                severity="medium",
                confidence=0.98,
            )
        except Exception:
            return None
