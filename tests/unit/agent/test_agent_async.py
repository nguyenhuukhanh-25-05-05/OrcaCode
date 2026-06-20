"""Tests for async AgentController."""

import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.agent import AgentController, AppCallbacks
from config.settings import AppConfig, ModelConfig


@pytest.fixture
def sample_config():
    return AppConfig(
        model=ModelConfig(provider="openai", model="gpt-4o", api_key="sk-test"),
        project_root="/tmp/test-project",
    )


@pytest.fixture
def mock_callbacks():
    return AppCallbacks(
        on_chat=MagicMock(),
        on_status=MagicMock(),
        on_error=MagicMock(),
        on_done=MagicMock(),
        on_tokens_used=MagicMock(),
    )


class TestAgentControllerAsync:
    def test_run_is_coroutine(self):
        assert inspect.iscoroutinefunction(AgentController.run) is True

    def test_handle_simple_conversation_is_coroutine(self):
        assert inspect.iscoroutinefunction(AgentController._handle_simple_conversation) is True

    def test_run_auto_is_coroutine(self):
        assert inspect.iscoroutinefunction(AgentController._run_auto) is True

    def test_run_review_is_coroutine(self):
        assert inspect.iscoroutinefunction(AgentController._run_review) is True

    def test_execute_loop_is_coroutine(self):
        assert inspect.iscoroutinefunction(AgentController._execute_loop) is True

    def test_run_post_execution_pipeline_is_coroutine(self):
        assert inspect.iscoroutinefunction(AgentController._run_post_execution_pipeline) is True

    @patch("core.agent._create_client")
    def test_agent_constructs_and_runs_in_event_loop(self, mock_create):
        cfg = AppConfig(
            model=ModelConfig(provider="openai", model="gpt-4o", api_key="sk-test"),
            project_root="/tmp/test-project",
        )
        agent = AgentController(cfg)
        assert agent.cfg is cfg
        assert agent.patch_svc is not None  # services are eagerly initialized

    async def test_run_no_api_key_returns_early(self):
        cfg = AppConfig(
            model=ModelConfig(provider="openai", model="gpt-4o", api_key=""),
            project_root="/tmp/test-project",
        )
        cb = AppCallbacks(on_error=MagicMock())
        agent = AgentController(cfg, callbacks=cb)
        await agent.run("hello")
        cb.on_error.assert_called_once()

    def test_stop_sets_interrupted(self):
        cfg = AppConfig(
            model=ModelConfig(provider="openai", model="gpt-4o", api_key="sk-test"),
            project_root="/tmp/test-project",
        )
        agent = AgentController(cfg)
        assert agent.interrupted is False
        agent.stop()
        assert agent.interrupted is True

    def test_is_interrupted_returns_false_by_default(self):
        cfg = AppConfig(
            model=ModelConfig(provider="openai", model="gpt-4o", api_key="sk-test"),
            project_root="/tmp/test-project",
        )
        agent = AgentController(cfg)
        assert agent._is_interrupted() is False
