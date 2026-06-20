"""Tests for LLM streaming functionality."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.llm.providers import LLMStreamChunk


class _AsyncIterable:
    """Helper to create async iterables from regular iterables."""

    def __init__(self, iterable):
        self._iterator = iter(iterable)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._iterator)
        except StopIteration:
            raise StopAsyncIteration


class TestOpenAIStreaming:
    """OpenAI streaming tests."""

    @patch("core.llm.providers.OpenAIProvider._build_client")
    async def test_streaming_yields_chunks(self, mock_build):
        from core.llm.providers import OpenAIProvider

        provider = OpenAIProvider(api_key="sk-test", model="gpt-4o")

        chunk1 = MagicMock()
        chunk1.choices = [MagicMock()]
        chunk1.choices[0].delta.content = "Hello"
        chunk1.choices[0].finish_reason = None
        chunk1.usage = None

        chunk2 = MagicMock()
        chunk2.choices = [MagicMock()]
        chunk2.choices[0].delta.content = " world"
        chunk2.choices[0].finish_reason = None
        chunk2.usage = None

        chunk3 = MagicMock()
        chunk3.choices = [MagicMock()]
        chunk3.choices[0].delta.content = ""
        chunk3.choices[0].finish_reason = "stop"
        chunk3.usage = MagicMock()
        chunk3.usage.prompt_tokens = 10

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_AsyncIterable([chunk1, chunk2, chunk3]))
        provider._client = mock_client

        chunks = []
        async for chunk in provider.generate_stream([{"role": "user", "content": "Hi"}]):
            chunks.append(chunk)

        assert len(chunks) == 3
        assert chunks[0].delta == "Hello"
        assert chunks[1].delta == " world"
        assert chunks[2].finish_reason == "stop"

    @patch("core.llm.providers.OpenAIProvider._build_client")
    async def test_streaming_handles_empty_chunks(self, mock_build):
        from core.llm.providers import OpenAIProvider

        provider = OpenAIProvider(api_key="sk-test", model="gpt-4o")

        chunk = MagicMock()
        chunk.choices = [MagicMock()]
        chunk.choices[0].delta.content = None
        chunk.choices[0].finish_reason = None
        chunk.usage = None

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_AsyncIterable([chunk]))
        provider._client = mock_client

        chunks = []
        async for chunk in provider.generate_stream([{"role": "user", "content": "Hi"}]):
            chunks.append(chunk)

        assert len(chunks) == 1
        assert chunks[0].delta == ""

    @patch("core.llm.providers.OpenAIProvider._build_client")
    async def test_streaming_auth_error(self, mock_build):
        from core.llm.providers import OpenAIProvider, LLMAuthError

        provider = OpenAIProvider(api_key="sk-test", model="gpt-4o")
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=Exception("401 Unauthorized"))
        provider._client = mock_client

        with pytest.raises(LLMAuthError):
            async for _ in provider.generate_stream([{"role": "user", "content": "Hi"}]):
                pass


class TestStreamChunkModel:
    """LLMStreamChunk data class tests."""

    def test_chunk_defaults(self):
        chunk = LLMStreamChunk()
        assert chunk.delta == ""
        assert chunk.finish_reason is None
        assert chunk.prompt_tokens == 0
        assert chunk.completion_tokens == 0

    def test_chunk_with_values(self):
        chunk = LLMStreamChunk(delta="Hello", finish_reason="stop", prompt_tokens=10, completion_tokens=20)
        assert chunk.delta == "Hello"
        assert chunk.finish_reason == "stop"
        assert chunk.prompt_tokens == 10
        assert chunk.completion_tokens == 20
