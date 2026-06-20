"""Tests for prompt templates."""

from core.prompts import CHAT_SYSTEM_PROMPT, SYSTEM_PROMPT_EXECUTE, SYSTEM_PROMPT_PLAN


class TestChatSystemPrompt:
    def test_contains_modes(self):
        assert "chat mode" in CHAT_SYSTEM_PROMPT.lower()

    def test_mentions_plan_and_auto(self):
        assert "Plan" in CHAT_SYSTEM_PROMPT or "plan" in CHAT_SYSTEM_PROMPT
        assert "Auto" in CHAT_SYSTEM_PROMPT or "auto" in CHAT_SYSTEM_PROMPT


class TestSystemPromptPlan:
    def test_contains_core_identity(self):
        assert "OrcaCode" in SYSTEM_PROMPT_PLAN

    def test_contains_plan_done_tag(self):
        assert "<PLAN_DONE/>" in SYSTEM_PROMPT_PLAN

    def test_contains_planning_rules(self):
        assert "LUẬT THAY ĐỔI RÕ RỆT + QUY TẮC KẾ HOẠCH" in SYSTEM_PROMPT_PLAN
        assert "<PLAN_DONE/>" in SYSTEM_PROMPT_PLAN
        assert "KHÔNG viết code thực tế" in SYSTEM_PROMPT_PLAN


class TestSystemPromptExecute:
    def test_contains_core_identity(self):
        assert "OrcaCode" in SYSTEM_PROMPT_EXECUTE

    def test_contains_done_tag(self):
        assert "<DONE/>" in SYSTEM_PROMPT_EXECUTE

    def test_contains_tool_tags(self):
        assert "WRITE_FILE" in SYSTEM_PROMPT_EXECUTE
        assert "PATCH_FILE" in SYSTEM_PROMPT_EXECUTE
        assert "RUN_COMMAND" in SYSTEM_PROMPT_EXECUTE

    def test_contains_code_rule(self):
        assert "KHÔNG" in SYSTEM_PROMPT_EXECUTE
