"""Tests that services are eagerly initialized in AgentController constructor."""

from unittest.mock import MagicMock, patch

from core.agent import AgentController
from config.settings import AppConfig, ModelConfig


def _make_cfg():
    return AppConfig(
        model=ModelConfig(provider="openai", model="gpt-4o", api_key="sk-test"),
        project_root="/tmp/test-project",
    )


@patch("core.agent._create_client")
def test_constructor_eagerly_resolves_services(mock_create):
    cfg = _make_cfg()
    agent = AgentController(cfg)
    service_names = [
        "context_svc", "checkpoint_svc", "blueprint_svc", "patch_svc",
        "anchor_patcher", "section_parser", "smart_context", "security_svc",
        "session_vm", "patch_vm", "memory", "long_memory", "plugin_svc",
        "debug_svc", "error_pipeline", "file_backup", "structural_validator",
    ]
    for name in service_names:
        assert name in agent.__dict__, f"{name} was not eagerly resolved"
        assert getattr(agent, name) is not None, f"{name} resolved to None"


@patch("core.agent._create_client")
def test_service_resolved_on_first_access(mock_create):
    cfg = _make_cfg()
    agent = AgentController(cfg)
    svc = agent.patch_svc
    assert svc is not None


@patch("core.agent._create_client")
def test_unregistered_service_raises_attribute_error(mock_create):
    cfg = _make_cfg()
    agent = AgentController(cfg)
    import pytest
    with pytest.raises(AttributeError):
        _ = agent.nonexistent_service


def test_lazy_import_not_in_agent_module_globals():
    import core.agent as agent_mod
    heavy_names = [
        "ContextService", "PatchService", "SecurityService",
        "SessionViewModel", "PatchViewModel", "PluginService",
        "DebugService", "ErrorPipeline", "LongMemory",
        "AnchorPatcher", "SectionParser", "SmartContext",
        "MemoryManager",
    ]
    for name in heavy_names:
        assert not hasattr(agent_mod, name), f"{name} found in agent module globals"


@patch("core.agent._create_client")
def test_service_is_singleton(mock_create):
    cfg = _make_cfg()
    agent = AgentController(cfg)
    svc1 = agent.patch_svc
    svc2 = agent.patch_svc
    assert svc1 is svc2


@patch("core.agent._create_client")
def test_conversation_cache_is_stored_in_dict(mock_create):
    cfg = _make_cfg()
    agent = AgentController(cfg)
    assert "conversation_cache" in agent.__dict__
    assert agent.conversation_cache is not None
