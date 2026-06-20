"""Tests for LLMClient factory and basic functionality."""

import pytest
from config.settings import AppConfig, ModelConfig
from core.llm import LLMClient
from core.llm.exceptions import LLMAuthError, LLMConfigurationError
from core.llm.providers import OpenAIProvider, AnthropicProvider, GeminiProvider


class TestLLMClientInit:
    """LLMClient.from_config() factory."""

    def test_from_config_openai(self):
        cfg = AppConfig(model=ModelConfig(provider="openai", model="gpt-4o", api_key="sk-test"))
        client = LLMClient.from_config(cfg)
        assert isinstance(client._provider, OpenAIProvider)
        assert client.provider_name == "openai"
        assert client.model == "gpt-4o"

    def test_from_config_deepseek(self):
        cfg = AppConfig(model=ModelConfig(provider="deepseek", model="deepseek-chat", api_key="sk-test"))
        client = LLMClient.from_config(cfg)
        assert isinstance(client._provider, OpenAIProvider)

    def test_from_config_anthropic(self):
        cfg = AppConfig(model=ModelConfig(provider="anthropic", model="claude-sonnet-4-20250514", api_key="sk-ant-test"))
        client = LLMClient.from_config(cfg)
        assert isinstance(client._provider, AnthropicProvider)
        assert client.provider_name == "anthropic"

    def test_from_config_claude_alias(self):
        cfg = AppConfig(model=ModelConfig(provider="claude", model="claude-sonnet-4-20250514", api_key="sk-ant-test"))
        client = LLMClient.from_config(cfg)
        assert isinstance(client._provider, AnthropicProvider)

    def test_from_config_gemini(self):
        cfg = AppConfig(model=ModelConfig(provider="gemini", model="gemini-2.0-flash", api_key="AIza-test"))
        client = LLMClient.from_config(cfg)
        assert isinstance(client._provider, GeminiProvider)

    def test_from_config_openrouter(self):
        cfg = AppConfig(model=ModelConfig(provider="openrouter", model="openai/gpt-4o", api_key="sk-test"))
        client = LLMClient.from_config(cfg)
        assert isinstance(client._provider, OpenAIProvider)

    def test_from_config_missing_api_key(self):
        cfg = AppConfig(model=ModelConfig(provider="openai", model="gpt-4o", api_key=""))
        with pytest.raises(LLMAuthError, match="API key not found"):
            LLMClient.from_config(cfg)

    def test_from_config_unsupported_provider(self):
        cfg = AppConfig(model=ModelConfig(provider="unknown-xyz", model="test", api_key="sk-test"))
        with pytest.raises(LLMConfigurationError, match="Unsupported provider"):
            LLMClient.from_config(cfg)

    def test_from_config_sets_base_url(self):
        cfg = AppConfig(
            model=ModelConfig(provider="openai", model="gpt-4o", api_key="sk-test", base_url="https://custom.api.com/v1")
        )
        client = LLMClient.from_config(cfg)
        assert client._provider.base_url == "https://custom.api.com/v1"

    def test_provider_properties(self):
        cfg = AppConfig(model=ModelConfig(provider="openai", model="gpt-4o", api_key="sk-test"))
        client = LLMClient.from_config(cfg)
        assert client.provider_name == "openai"
        assert client.model == "gpt-4o"
