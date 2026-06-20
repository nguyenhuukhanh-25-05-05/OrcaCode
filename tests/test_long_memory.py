"""Unit tests for Long-term Memory System (SQLite + FTS5)."""
import pytest
from core.services.long_memory import LongMemory, Event, Task, Knowledge


@pytest.fixture
def mem(tmp_path):
    """Create a fresh LongMemory instance in a temp directory."""
    m = LongMemory(project_root=str(tmp_path))
    yield m
    m.close()


# ═══════════════════════════════════════════════════════════════════════════════
# Event Log Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestEventLog:
    def test_log_event(self, mem):
        eid = mem.log_event("edit_file", file="app.py", summary="Fixed login")
        assert eid > 0

    def test_log_event_returns_id(self, mem):
        eid1 = mem.log_event("edit_file", file="a.py", summary="first")
        eid2 = mem.log_event("edit_file", file="b.py", summary="second")
        assert eid2 > eid1

    def test_log_file_event(self, mem):
        eid = mem.log_file_event("create_file", "new.py", summary="Created")
        assert eid > 0
        events = mem.get_events(action="create_file")
        assert len(events) == 1
        assert events[0].file == "new.py"

    def test_log_command_event(self, mem):
        eid = mem.log_command_event("npm test", summary="All passed")
        events = mem.get_events(action="run_command")
        assert len(events) == 1
        assert events[0].command == "npm test"

    def test_get_events(self, mem):
        for i in range(5):
            mem.log_event("edit_file", file=f"file{i}.py", summary=f"edit {i}")
        events = mem.get_events(limit=3)
        assert len(events) == 3
        # Most recent first
        assert events[0].summary == "edit 4"

    def test_get_events_filter_action(self, mem):
        mem.log_event("edit_file", file="a.py")
        mem.log_event("run_command", command="ls")
        mem.log_event("edit_file", file="b.py")
        events = mem.get_events(action="edit_file")
        assert len(events) == 2

    def test_get_events_filter_file(self, mem):
        mem.log_event("edit_file", file="a.py")
        mem.log_event("edit_file", file="b.py")
        events = mem.get_events(file="a.py")
        assert len(events) == 1

    def test_count_events(self, mem):
        assert mem.count_events() == 0
        mem.log_event("edit_file", file="a.py")
        mem.log_event("edit_file", file="b.py")
        assert mem.count_events() == 2

    def test_event_with_task_id(self, mem):
        tid = mem.start_task("Fix bug")
        mem.log_event("edit_file", file="a.py", task_id=tid)
        events = mem.get_events(task_id=tid)
        assert len(events) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Task Memory Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestTaskMemory:
    def test_start_task(self, mem):
        tid = mem.start_task("Fix login", files=["Login.vue", "auth.js"])
        assert tid > 0
        task = mem.get_task(tid)
        assert task.name == "Fix login"
        assert task.result == "pending"
        assert "Login.vue" in task.files

    def test_complete_task(self, mem):
        tid = mem.complete_task(
            "Fix login",
            files=["Login.vue"],
            result="success",
            lessons="Token refresh needed",
        )
        task = mem.get_task(tid)
        assert task.result == "success"
        assert task.lessons == "Token refresh needed"
        assert task.time_end != ""

    def test_complete_existing_task(self, mem):
        tid = mem.start_task("Fix bug")
        tid2 = mem.complete_task("Fix bug", result="success")
        assert tid == tid2
        assert mem.count_tasks() == 1

    def test_get_tasks(self, mem):
        mem.complete_task("Task 1", result="success")
        mem.complete_task("Task 2", result="failure")
        mem.complete_task("Task 3", result="success")
        tasks = mem.get_tasks()
        assert len(tasks) == 3

    def test_get_tasks_filter_result(self, mem):
        mem.complete_task("Task 1", result="success")
        mem.complete_task("Task 2", result="failure")
        tasks = mem.get_tasks(result="success")
        assert len(tasks) == 1
        assert tasks[0].name == "Task 1"

    def test_count_tasks(self, mem):
        assert mem.count_tasks() == 0
        mem.complete_task("Task 1")
        assert mem.count_tasks() == 1

    def test_task_event_count(self, mem):
        tid = mem.start_task("Test task")
        mem.log_event("edit_file", file="a.py", task_id=tid)
        mem.log_event("edit_file", file="b.py", task_id=tid)
        mem.complete_task("Test task", result="success")
        task = mem.get_task(tid)
        assert task.event_count == 2


# ═══════════════════════════════════════════════════════════════════════════════
# Knowledge Base Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestKnowledgeBase:
    def test_add_knowledge(self, mem):
        kid = mem.add_knowledge("auth_pattern", "Always refresh JWT tokens")
        assert kid > 0
        knowledge = mem.get_knowledge()
        assert len(knowledge) == 1
        assert knowledge[0].pattern_name == "auth_pattern"

    def test_add_knowledge_increments(self, mem):
        mem.add_knowledge("auth_pattern", "Always refresh tokens")
        mem.add_knowledge("auth_pattern", "Always refresh tokens v2")
        knowledge = mem.get_knowledge()
        assert len(knowledge) == 1
        assert knowledge[0].occurrence_count == 2
        assert knowledge[0].pattern_text == "Always refresh tokens v2"

    def test_knowledge_with_source_tasks(self, mem):
        tid = mem.complete_task("Task 1", result="success")
        mem.add_knowledge("pattern_a", "text", source_task_id=tid)
        knowledge = mem.get_knowledge()
        assert tid in knowledge[0].source_tasks

    def test_count_knowledge(self, mem):
        assert mem.count_knowledge() == 0
        mem.add_knowledge("p1", "text1")
        mem.add_knowledge("p2", "text2")
        assert mem.count_knowledge() == 2


# ═══════════════════════════════════════════════════════════════════════════════
# Search Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestSearch:
    def test_search_events(self, mem):
        mem.log_event("edit_file", file="Login.vue", summary="Added token refresh")
        mem.log_event("edit_file", file="Auth.js", summary="Fixed session handling")
        results = mem.search("token refresh")
        assert len(results) > 0
        assert any("token" in r["name"].lower() for r in results)

    def test_search_tasks(self, mem):
        mem.complete_task("Fix Login", files=["Login.vue"], lessons="Token refresh needed")
        mem.complete_task("Fix Auth", files=["Auth.js"], lessons="Session management")
        results = mem.search("login token")
        assert len(results) > 0
        task_results = [r for r in results if r["type"] == "task"]
        assert len(task_results) > 0

    def test_search_knowledge(self, mem):
        mem.add_knowledge("auth_pattern", "Always refresh JWT tokens before expiry")
        results = mem.search("authentication JWT")
        assert len(results) > 0
        knowledge_results = [r for r in results if r["type"] == "knowledge"]
        assert len(knowledge_results) > 0

    def test_search_empty(self, mem):
        results = mem.search("nonexistent query xyz123")
        assert len(results) == 0

    def test_search_ranking(self, mem):
        """Knowledge should rank higher than events."""
        mem.log_event("edit_file", file="auth.py", summary="edit authentication")
        mem.add_knowledge("auth_rule", "authentication requires JWT validation")
        results = mem.search("authentication")
        if len(results) >= 2:
            # Knowledge should have better (lower) score
            knowledge_scores = [r["score"] for r in results if r["type"] == "knowledge"]
            event_scores = [r["score"] for r in results if r["type"] == "event"]
            if knowledge_scores and event_scores:
                assert min(knowledge_scores) <= min(event_scores)

    def test_search_limit(self, mem):
        for i in range(20):
            mem.log_event("edit_file", file=f"f{i}.py", summary=f"test file {i}")
        results = mem.search("test file", limit=5)
        assert len(results) <= 5


# ═══════════════════════════════════════════════════════════════════════════════
# Context Building Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestContextBuilding:
    def test_build_context(self, mem):
        mem.add_knowledge("auth", "JWT tokens must be refreshed")
        mem.complete_task("Fix Login", lessons="Refresh token before expiry")
        mem.log_event("edit_file", file="Login.vue", summary="Added refresh")
        context = mem.build_context_for_query("authentication login")
        assert "auth" in context.lower() or "login" in context.lower()

    def test_build_context_empty(self, mem):
        context = mem.build_context_for_query("nonexistent xyz")
        assert context == ""

    def test_build_context_truncation(self, mem):
        # Add lots of data
        for i in range(100):
            mem.log_event("edit_file", file=f"f{i}.py",
                         summary=f"edit {i} " + "x" * 200)
        context = mem.build_context_for_query("edit", max_tokens=100)
        assert len(context) <= 100 * 4 + 100  # Some buffer for header


# ═══════════════════════════════════════════════════════════════════════════════
# Export Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestExport:
    def test_export_task_markdown(self, mem):
        tid = mem.start_task("Fix Bug", files=["a.py"])
        mem.log_event("edit_file", file="a.py", task_id=tid, summary="Fix")
        mem.complete_task("Fix Bug", result="success", lessons="Check imports")
        md = mem.export_task_markdown(tid)
        assert "Fix Bug" in md
        assert "success" in md
        assert "Check imports" in md

    def test_export_knowledge_markdown(self, mem):
        mem.add_knowledge("auth", "Always validate tokens")
        md = mem.export_knowledge_markdown()
        assert "auth" in md
        assert "Knowledge Base" in md

    def test_export_empty_knowledge(self, mem):
        md = mem.export_knowledge_markdown()
        assert "No patterns learned yet" in md


# ═══════════════════════════════════════════════════════════════════════════════
# Stats Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestStats:
    def test_get_stats(self, mem):
        mem.log_event("edit_file", file="a.py")
        mem.complete_task("Task 1")
        mem.add_knowledge("p1", "text")
        stats = mem.get_stats()
        assert stats["events"] == 1
        assert stats["tasks"] == 1
        assert stats["knowledge"] == 1
        assert stats["db_size_kb"] > 0


# ═══════════════════════════════════════════════════════════════════════════════
# Integration: Full Workflow
# ═══════════════════════════════════════════════════════════════════════════════

class TestFullWorkflow:
    def test_full_task_workflow(self, mem):
        """Test a complete task lifecycle: start → events → complete → search."""
        # Start task
        tid = mem.start_task("Fix authentication", files=["auth.py", "login.vue"])

        # Log events during task
        mem.log_event("read_file", file="auth.py", task_id=tid, summary="Reading auth code")
        mem.log_event("edit_file", file="auth.py", task_id=tid, summary="Fixed token validation")
        mem.log_event("edit_file", file="login.vue", task_id=tid, summary="Updated login form")
        mem.log_event("run_command", command="npm test", task_id=tid, summary="Tests passed")

        # Complete task
        mem.complete_task(
            "Fix authentication",
            result="success",
            lessons="Always validate JWT tokens before expiry",
        )

        # Add knowledge
        mem.add_knowledge(
            "jwt_validation",
            "JWT tokens must be validated on every request",
            source_task_id=tid,
        )

        # Search for it
        results = mem.search("authentication JWT token")
        assert len(results) > 0

        # Check stats
        stats = mem.get_stats()
        assert stats["events"] == 4
        assert stats["tasks"] == 1
        assert stats["knowledge"] == 1

        # Export
        md = mem.export_task_markdown(tid)
        assert "Fix authentication" in md

    def test_multiple_tasks_knowledge(self, mem):
        """Test knowledge extraction from multiple similar tasks."""
        # Task 1
        tid1 = mem.complete_task("Fix Login", files=["login.py"],
                                 result="success", lessons="Use bcrypt for passwords")
        mem.add_knowledge("password_hashing", "Use bcrypt for password hashing",
                         source_task_id=tid1)

        # Task 2
        tid2 = mem.complete_task("Fix Registration", files=["register.py"],
                                 result="success", lessons="Hash passwords with bcrypt")
        mem.add_knowledge("password_hashing", "Use bcrypt for password hashing",
                         source_task_id=tid2)

        # Task 3
        tid3 = mem.complete_task("Fix Password Reset", files=["reset.py"],
                                 result="success", lessons="Always bcrypt hash")
        mem.add_knowledge("password_hashing", "Use bcrypt for password hashing",
                         source_task_id=tid3)

        # Knowledge should have high occurrence count
        knowledge = mem.get_knowledge()
        pw_knowledge = [k for k in knowledge if k.pattern_name == "password_hashing"]
        assert len(pw_knowledge) == 1
        assert pw_knowledge[0].occurrence_count == 3
        assert len(pw_knowledge[0].source_tasks) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])