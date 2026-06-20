"""Tests for path traversal security fix and WRITE/PATCH enforcement."""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from core.services.security_service import SecurityService


class TestPathTraversal:
    """Test that _resolve_safe_path properly blocks paths outside project root."""

    def test_valid_path_within_project(self, tmp_path):
        svc = SecurityService()
        project_root = str(tmp_path)
        file_path = str(tmp_path / "src" / "main.py")
        result = svc._resolve_safe_path(file_path, project_root=project_root)
        assert result is not None

    def test_traversal_blocked(self, tmp_path):
        svc = SecurityService()
        project_root = str(tmp_path / "project")
        # Path that escapes project root
        file_path = str(tmp_path / "project" / ".." / "etc" / "passwd")
        result = svc._resolve_safe_path(file_path, project_root=project_root)
        assert result is None

    def test_traversal_double_dot(self, tmp_path):
        svc = SecurityService()
        project_root = str(tmp_path / "myproject")
        file_path = str(tmp_path / "myproject" / ".." / ".." / "secret.txt")
        result = svc._resolve_safe_path(file_path, project_root=project_root)
        assert result is None

    def test_no_project_root_allows_any_path(self, tmp_path):
        """When project_root is None, path resolution should succeed."""
        svc = SecurityService()
        file_path = str(tmp_path / "any" / "file.txt")
        result = svc._resolve_safe_path(file_path, project_root=None)
        assert result is not None

    def test_exact_project_root_path(self, tmp_path):
        svc = SecurityService()
        project_root = str(tmp_path)
        file_path = str(tmp_path / "file.txt")
        result = svc._resolve_safe_path(file_path, project_root=project_root)
        assert result is not None

    def test_subdirectory_is_valid(self, tmp_path):
        svc = SecurityService()
        project_root = str(tmp_path)
        file_path = str(tmp_path / "a" / "b" / "c" / "deep.py")
        result = svc._resolve_safe_path(file_path, project_root=project_root)
        assert result is not None
