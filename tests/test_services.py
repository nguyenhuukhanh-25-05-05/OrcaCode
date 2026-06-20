"""Unit tests for PluginService, DebugService, MemoryManager, GitRepo."""
import os
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# ═══════════════════════════════════════════════════════════════════════════════
# PluginService Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestPluginService:
    def _svc(self):
        from core.services.plugin_service import PluginService
        return PluginService()

    def test_register_and_get(self):
        svc = self._svc()
        handler = lambda **kw: {"result": kw.get("x", 0) + 1}
        svc.register("adder", "Add one to x", handler)
        tool = svc.get("adder")
        assert tool is not None
        assert tool.name == "adder"
        assert tool.description == "Add one to x"

    def test_get_nonexistent(self):
        svc = self._svc()
        assert svc.get("nope") is None

    def test_unregister(self):
        svc = self._svc()
        svc.register("temp", "temp tool", lambda **kw: {})
        svc.unregister("temp")
        assert svc.get("temp") is None

    def test_unregister_nonexistent(self):
        svc = self._svc()
        svc.unregister("nope")  # Should not raise

    def test_list_tools(self):
        svc = self._svc()
        svc.register("a", "tool A", lambda **kw: {})
        svc.register("b", "tool B", lambda **kw: {})
        tools = svc.list_tools()
        names = {t.name for t in tools}
        assert names == {"a", "b"}

    def test_execute_success(self):
        svc = self._svc()
        svc.register("double", "double x", lambda **kw: {"value": kw.get("x", 0) * 2})
        result = svc.execute("double", x=5)
        assert result["success"] is True
        assert result["summary"] is not None

    def test_execute_failure(self):
        svc = self._svc()
        svc.register("boom", "always fails", lambda **kw: 1 / 0)
        result = svc.execute("boom")
        assert result["success"] is False
        assert "division by zero" in result["summary"] or "Error" in result["summary"]

    def test_execute_nonexistent(self):
        svc = self._svc()
        result = svc.execute("nope")
        assert result["success"] is False

    def test_format_for_prompt(self):
        svc = self._svc()
        svc.register("my_tool", "Does something cool", lambda **kw: {})
        prompt = svc.format_for_prompt()
        assert "my_tool" in prompt
        assert "Does something cool" in prompt

    def test_format_for_prompt_empty(self):
        svc = self._svc()
        assert svc.format_for_prompt() == ""

    def test_auto_approve_flag(self):
        svc = self._svc()
        svc.register("fast", "auto approve", lambda **kw: {}, auto_approve=True)
        tool = svc.get("fast")
        assert tool.auto_approve is True


# ═══════════════════════════════════════════════════════════════════════════════
# DebugService Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestDebugService:
    def _svc(self, root="."):
        from core.services.debug_service import DebugService
        return DebugService(root)

    def test_parse_stack_trace_python(self):
        svc = self._svc()
        trace = '''Traceback (most recent call last):
  File "app.py", line 10, in main
    result = compute(x)
  File "utils.py", line 42, in compute
    return x / zero
ZeroDivisionError: division by zero'''
        frames = svc.parse_stack_trace(trace)
        assert len(frames) == 2
        assert frames[0]["file"] == "app.py"
        assert frames[0]["line"] == 10
        assert frames[0]["func"] == "main"
        assert frames[1]["file"] == "utils.py"
        assert frames[1]["line"] == 42

    def test_parse_stack_trace_js(self):
        svc = self._svc()
        trace = "    at processRequest (src/server.ts:55:10)\n    at handler (src/handler.ts:20:5)"
        frames = svc.parse_stack_trace(trace)
        assert len(frames) >= 2
        files = [f["file"] for f in frames]
        assert "src/server.ts" in files
        assert "src/handler.ts" in files

    def test_extract_error_type(self):
        svc = self._svc()
        assert "ValueError" in svc.extract_error_type("ValueError: bad input")
        assert "KeyError" in svc.extract_error_type("KeyError: 'name'")
        assert "TypeError" in svc.extract_error_type("TypeError: NoneType")

    def test_extract_error_type_empty(self):
        svc = self._svc()
        assert svc.extract_error_type("") == ""
        assert svc.extract_error_type("no error here") == ""

    def test_read_error_context(self, tmp_path):
        svc = self._svc(str(tmp_path))
        (tmp_path / "test.py").write_text("line1\nline2\nline3\nline4\nline5\nline6\nline7\n")
        ctx = svc.read_error_context("test.py", 4, context=2)
        assert ">>>" in ctx
        assert "line4" in ctx

    def test_read_error_context_missing(self):
        svc = self._svc()
        assert svc.read_error_context("nonexistent.py", 1) == ""

    def test_suggest_fix_module_not_found(self):
        svc = self._svc()
        suggestion = svc.suggest_fix_command("ModuleNotFoundError: No module named 'requests'")
        assert suggestion is not None
        assert "pip install requests" in suggestion

    def test_suggest_fix_file_not_found(self):
        svc = self._svc()
        suggestion = svc.suggest_fix_command("FileNotFoundError: config.json")
        assert suggestion is not None

    def test_suggest_fix_none(self):
        svc = self._svc()
        assert svc.suggest_fix_command("random error") is None


# ═══════════════════════════════════════════════════════════════════════════════
# MemoryManager Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestMemoryManager:
    def _mm(self, tmp_path):
        from core.memory_manager import MemoryManager
        return MemoryManager(str(tmp_path))

    def test_init_creates_dirs(self, tmp_path):
        mm = self._mm(tmp_path)
        assert (tmp_path / ".orca" / "memory").is_dir()
        assert (tmp_path / ".orca" / "memory" / "diffs").is_dir()

    def test_save_and_load_chat_history(self, tmp_path):
        mm = self._mm(tmp_path)
        messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]
        mm.save_chat_history(messages)
        loaded = mm.load_chat_history()
        assert len(loaded) == 2
        assert loaded[0]["role"] == "user"
        assert loaded[1]["content"] == "hi there"

    def test_load_empty_history(self, tmp_path):
        mm = self._mm(tmp_path)
        loaded = mm.load_chat_history()
        assert loaded == []

    def test_save_diff_and_list(self, tmp_path):
        mm = self._mm(tmp_path)
        mm.save_diff("test.py", "old content", "new content", "write_file")
        diffs = mm.list_diffs()
        assert len(diffs) == 1
        assert diffs[0]["file"] == "test.py"

    def test_load_instructions(self, tmp_path):
        mm = self._mm(tmp_path)
        instructions_dir = tmp_path / ".orca"
        instructions_dir.mkdir(parents=True, exist_ok=True)
        (instructions_dir / "instructions.md").write_text("Always use types")
        (instructions_dir / "runtime_contract.md").write_text("Retry until checks pass")
        result = mm.load_instructions()
        assert "Always use types" in result
        assert "Retry until checks pass" in result

    def test_load_instructions_ui_task(self, tmp_path):
        mm = self._mm(tmp_path)
        instructions_dir = tmp_path / ".orca"
        instructions_dir.mkdir(parents=True, exist_ok=True)
        (instructions_dir / "instructions.md").write_text("Base rules")
        (instructions_dir / "ui_runtime_rules.md").write_text("UI must look deliberate")
        result = mm.load_instructions("fix frontend ui")
        assert "Base rules" in result
        assert "UI must look deliberate" in result

    def test_load_instructions_missing(self, tmp_path):
        mm = self._mm(tmp_path)
        assert mm.load_instructions() is None

    def test_load_skills(self, tmp_path):
        mm = self._mm(tmp_path)
        skills_dir = tmp_path / ".orca" / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        (skills_dir / "python.md").write_text("Python skill")
        result = mm.load_skills()
        assert "Python skill" in result

    def test_load_skills_empty(self, tmp_path):
        mm = self._mm(tmp_path)
        assert mm.load_skills() == ""

    def test_get_memory_stats(self, tmp_path):
        mm = self._mm(tmp_path)
        mm.save_chat_history([{"role": "user", "content": "test"}])
        stats = mm.get_memory_stats()
        assert stats["chat_messages"] == 1
        assert stats["history_size_kb"] >= 0
        assert stats["diff_snapshots"] == 0

    def test_clear_memory(self, tmp_path):
        mm = self._mm(tmp_path)
        mm.save_chat_history([{"role": "user", "content": "test"}])
        mm.clear_memory()
        assert mm.load_chat_history() == []


# ═══════════════════════════════════════════════════════════════════════════════
# GitRepo Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestGitRepo:
    def _repo(self, tmp_path):
        """Create a real git repo for testing."""
        from core.git_repo import GitRepo
        # Init git repo
        import subprocess
        subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(tmp_path), capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=str(tmp_path), capture_output=True)
        return GitRepo(str(tmp_path))

    def test_available(self, tmp_path):
        repo = self._repo(tmp_path)
        assert repo.available is True

    def test_not_available(self, tmp_path):
        from core.git_repo import GitRepo
        repo = GitRepo(str(tmp_path))
        assert repo.available is False

    def test_is_dirty_initial(self, tmp_path):
        repo = self._repo(tmp_path)
        # Empty repo is not dirty
        assert repo.is_dirty() is False

    def test_is_dirty_after_edit(self, tmp_path):
        repo = self._repo(tmp_path)
        (tmp_path / "test.txt").write_text("hello")
        repo.add("test.txt")
        assert repo.is_dirty() is True

    def test_commit(self, tmp_path):
        repo = self._repo(tmp_path)
        (tmp_path / "test.txt").write_text("hello")
        sha = repo.commit("initial commit", add_all=True)
        assert sha is not None
        assert len(sha) >= 7

    def test_get_head_sha(self, tmp_path):
        repo = self._repo(tmp_path)
        (tmp_path / "test.txt").write_text("hello")
        repo.commit("initial", add_all=True)
        sha = repo.get_head_sha()
        assert sha is not None
        assert len(sha) >= 7

    def test_get_head_commit_message(self, tmp_path):
        repo = self._repo(tmp_path)
        (tmp_path / "test.txt").write_text("hello")
        repo.commit("my commit message", add_all=True)
        msg = repo.get_head_commit_message()
        assert msg == "my commit message"

    def test_undo(self, tmp_path):
        repo = self._repo(tmp_path)
        (tmp_path / "test.txt").write_text("hello")
        repo.commit("initial", add_all=True)
        (tmp_path / "test.txt").write_text("modified")
        repo.commit("modify", add_all=True)
        repo.undo()
        msg = repo.get_head_commit_message()
        assert msg == "initial"

    def test_get_diff(self, tmp_path):
        repo = self._repo(tmp_path)
        (tmp_path / "a.txt").write_text("hello")
        repo.add("a.txt")
        repo.commit("first", add_all=True)
        (tmp_path / "a.txt").write_text("modified")
        diff = repo.get_diff()
        assert "modified" in diff or diff is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
