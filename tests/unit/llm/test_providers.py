"""Tests for individual provider implementations."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.llm.exceptions import LLMAuthError, LLMConfigurationError
from core.llm.providers import LLMResponse, AnthropicProvider, GeminiProvider, OpenAIProvider


class TestOpenAIProvider:
    """OpenAI-compatible provider tests."""

    def test_name(self):
        provider = OpenAIProvider(api_key="sk-test", model="gpt-4o")
        assert provider.name == "openai"

    def test_build_client_lazy(self):
        provider = OpenAIProvider(api_key="sk-test", model="gpt-4o")
        assert provider._client is None
        with patch("core.llm.providers.OpenAIProvider._build_client") as mock_build:
            mock_build.return_value = "fake_client"
            client = provider.get_client()
            assert client == "fake_client"

    def test_build_client_missing_dependency(self):
        provider = OpenAIProvider(api_key="sk-test", model="gpt-4o")
        with patch("builtins.__import__", side_effect=ImportError("no module named openai")):
            with pytest.raises(LLMConfigurationError, match="openai package not installed"):
                provider._build_client()

    @patch("core.llm.providers.OpenAIProvider._build_client")
    def test_format_messages(self, mock_build):
        provider = OpenAIProvider(api_key="sk-test", model="gpt-4o")
        messages = [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Hello"},
        ]
        result = provider._format_messages(messages)
        assert result == messages  # OpenAI uses the default format

    @patch("core.llm.providers.OpenAIProvider._build_client")
    def test_generate_returns_response(self, mock_build):
        provider = OpenAIProvider(api_key="sk-test", model="gpt-4o")
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        provider._client = mock_client

        import asyncio
        result = asyncio.run(provider.generate([{"role": "user", "content": "Hi"}]))

        assert isinstance(result, LLMResponse)
        assert result.text == "Test response"
        assert result.prompt_tokens == 10
        assert result.completion_tokens == 20
        assert result.finish_reason == "stop"
        assert result.truncated is False

    @patch("core.llm.providers.OpenAIProvider._build_client")
    def test_generate_truncated_long_text(self, mock_build):
        provider = OpenAIProvider(api_key="sk-test", model="gpt-4o")
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "A" * 60000
        mock_response.choices[0].finish_reason = "length"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 60000
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        provider._client = mock_client

        import asyncio
        result = asyncio.run(provider.generate([{"role": "user", "content": "Hi"}]))

        assert result.truncated is True
        assert len(result.text) <= 50000 + 50  # 50000 + suffix

    @patch("core.llm.providers.OpenAIProvider._build_client")
    def test_generate_auth_error(self, mock_build):
        provider = OpenAIProvider(api_key="sk-test", model="gpt-4o")
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=Exception("401 Unauthorized"))
        provider._client = mock_client

        import asyncio
        with pytest.raises(LLMAuthError):
            asyncio.run(provider.generate([{"role": "user", "content": "Hi"}]))


class TestAnthropicProvider:
    """Anthropic/Claude provider tests."""

    def test_name(self):
        provider = AnthropicProvider(api_key="sk-ant-test", model="claude-sonnet-4-20250514")
        assert provider.name == "anthropic"

    def test_build_client_missing_dependency(self):
        provider = AnthropicProvider(api_key="sk-ant-test", model="claude-sonnet-4-20250514")
        with patch("builtins.__import__", side_effect=ImportError("no module named anthropic")):
            with pytest.raises(LLMConfigurationError, match="anthropic package not installed"):
                provider._build_client()

    def test_format_messages_system(self):
        provider = AnthropicProvider(api_key="sk-ant-test", model="claude-sonnet-4-20250514")
        messages = [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Hello"},
        ]
        system, msgs = provider._format_messages(messages)
        assert system == "You are a helpful assistant"
        assert msgs == [{"role": "user", "content": "Hello"}]

    def test_format_messages_no_system(self):
        provider = AnthropicProvider(api_key="sk-ant-test", model="claude-sonnet-4-20250514")
        messages = [
            {"role": "user", "content": "Hello"},
        ]
        system, msgs = provider._format_messages(messages)
        assert system == ""
        assert msgs == [{"role": "user", "content": "Hello"}]


class TestGeminiProvider:
    """Google Gemini provider tests."""

    def test_name(self):
        provider = GeminiProvider(api_key="AIza-test", model="gemini-2.0-flash")
        assert provider.name == "gemini"

    def test_build_client_missing_dependency(self):
        provider = GeminiProvider(api_key="AIza-test", model="gemini-2.0-flash")
        with patch("builtins.__import__", side_effect=ImportError("no module named google.generativeai")):
            with pytest.raises(LLMConfigurationError, match="google-generativeai package not installed"):
                provider._build_client()

    def test_format_messages(self):
        provider = GeminiProvider(api_key="AIza-test", model="gemini-2.0-flash")
        messages = [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Hello"},
        ]
        parts = provider._format_messages(messages)
        assert "[System: You are a helpful assistant]" in parts[0]
        assert "[user]: Hello" in parts[1]
