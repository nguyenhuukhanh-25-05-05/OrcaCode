"""Tests for truncation guard and PATCH enforcement in _execute_tool."""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
from core.services.patch_service import PatchService
from core.models import PatchResult


class TestTruncationGuard:
    """Test that WRITE_FILE is blocked when content is suspiciously shorter."""

    def setup_method(self):
        self.callbacks = MagicMock()
        self.callbacks.on_chat = MagicMock()
        self.callbacks.on_result = MagicMock()
        self.callbacks.on_error = MagicMock()

    def _make_agent(self, tmp_path):
        """Create a minimal AgentController mock for testing _execute_tool."""
        from config.settings import AppConfig
        cfg = AppConfig()
        cfg.project_root = str(tmp_path)
        cfg.model.api_key = "test-key"

        from core.agent import AgentController
        agent = AgentController(cfg, callbacks=MagicMock())
        agent.callbacks = self.callbacks
        agent.continuous = False
        agent.security_svc._auto_approve = True
        return agent

    def test_block_write_large_file(self, tmp_path):
        """WRITE_FILE should be blocked for existing files > 50 lines."""
        agent = self._make_agent(tmp_path)
        # Create a file with 60 lines
        big_file = tmp_path / "big.py"
        big_file.write_text("\n".join(f"line {i}" for i in range(60)), encoding="utf-8")

        tc = {
            "type": "write_file",
            "path": "big.py",
            "content": "# completely new content\nprint('hello')\n",
        }
        result = agent._execute_tool(tc)
        assert not result.get("success", True)
        assert "BLOCKED" in result["summary"]

    def test_allow_write_small_file(self, tmp_path):
        """WRITE_FILE should be allowed for existing files <= 50 lines."""
        agent = self._make_agent(tmp_path)
        small_file = tmp_path / "small.py"
        small_file.write_text("\n".join(f"line {i}" for i in range(30)), encoding="utf-8")

        tc = {
            "type": "write_file",
            "path": "small.py",
            "content": "\n".join(f"new line {i}" for i in range(30)),
        }
        result = agent._execute_tool(tc)
        assert result.get("success", False)

    def test_allow_write_new_file(self, tmp_path):
        """WRITE_FILE should always be allowed for new files."""
        agent = self._make_agent(tmp_path)
        tc = {
            "type": "write_file",
            "path": "new_file.py",
            "content": "print('hello world')\n",
        }
        result = agent._execute_tool(tc)
        assert result.get("success", False)

    def test_patch_always_allowed(self, tmp_path):
        """PATCH_FILE should always be allowed regardless of file size."""
        agent = self._make_agent(tmp_path)
        big_file = tmp_path / "big.py"
        lines = [f"line {i}" for i in range(100)]
        big_file.write_text("\n".join(lines), encoding="utf-8")

        tc = {
            "type": "patch_file",
            "path": "big.py",
            "search": "line 50",
            "replace": "modified line 50",
        }
        result = agent._execute_tool(tc)
        assert result.get("success", False)


class TestEnforcePatch:
    """Test enforcement of PATCH_FILE over WRITE_FILE for large files."""

    def test_write_blocked_returns_error_summary(self, tmp_path):
        """Blocked WRITE_FILE should return clear error message for AI feedback."""
        from config.settings import AppConfig
        cfg = AppConfig()
        cfg.project_root = str(tmp_path)
        cfg.model.api_key = "test-key"

        from core.agent import AgentController
        agent = AgentController(cfg, callbacks=MagicMock())
        agent.security_svc._auto_approve = True

        # Create 80-line file
        big_file = tmp_path / "routes.py"
        big_file.write_text("\n".join(f"route_{i} = None" for i in range(80)), encoding="utf-8")

        result = agent._execute_tool({
            "type": "write_file",
            "path": "routes.py",
            "content": "# truncated content\n",
        })
        assert "PATCH_FILE" in result["summary"]
        assert not result.get("success", True)
