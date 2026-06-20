"""Tests for AI streaming and real-time token tracking."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.agent import _call_ai_stream, _call_ai
from core.llm.providers import LLMResponse, LLMStreamChunk


class _AsyncIter:
    def __init__(self, items):
        self._items = items
        self._idx = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._idx >= len(self._items):
            raise StopAsyncIteration
        val = self._items[self._idx]
        self._idx += 1
        return val


class TestCallAiStream:
    @patch("core.agent._create_client")
    async def test_stream_calls_on_chunk(self, mock_create):
        client = MagicMock()
        client.generate_stream.return_value = _AsyncIter([
            LLMStreamChunk(delta="Hello "),
            LLMStreamChunk(delta="world"),
            LLMStreamChunk(finish_reason="stop", prompt_tokens=10),
        ])
        cfg = MagicMock()

        chunks = []
        text, p, c, meta = await _call_ai_stream(client, cfg, [{"role": "user", "content": "Hi"}], on_chunk=chunks.append)

        assert text == "Hello world"
        assert p == 10
        assert chunks == ["Hello ", "world"]

    @patch("core.agent._create_client")
    async def test_stream_returns_correct_meta(self, mock_create):
        client = MagicMock()
        client.generate_stream.return_value = _AsyncIter([
            LLMStreamChunk(delta="test", finish_reason="stop", prompt_tokens=5, completion_tokens=10),
        ])
        cfg = MagicMock()

        text, p, c, meta = await _call_ai_stream(client, cfg, [])

        assert text == "test"
        assert p == 5
        assert c == 10
        assert meta["finish_reason"] == "stop"
        assert meta["truncated"] is False

    @patch("core.agent._create_client")
    async def test_stream_truncates_long_text(self, mock_create):
        client = MagicMock()
        client.generate_stream.return_value = _AsyncIter([
            LLMStreamChunk(delta="A" * 60000, finish_reason="length"),
        ])
        cfg = MagicMock()

        text, p, c, meta = await _call_ai_stream(client, cfg, [])

        assert len(text) <= 50000 + 50
        assert meta["truncated"] is True

    @patch("core.agent._create_client")
    async def test_stream_accumulates_tokens(self, mock_create):
        client = MagicMock()
        client.generate_stream.return_value = _AsyncIter([
            LLMStreamChunk(delta="a", prompt_tokens=5),
            LLMStreamChunk(delta="b", completion_tokens=3),
            LLMStreamChunk(delta="c", finish_reason="stop"),
        ])
        cfg = MagicMock()

        text, p, c, meta = await _call_ai_stream(client, cfg, [])

        assert text == "abc"
        assert p == 5
        assert c == 3

    @patch("core.agent._create_client")
    async def test_stream_without_chunk_callback(self, mock_create):
        client = MagicMock()
        client.generate_stream.return_value = _AsyncIter([
            LLMStreamChunk(delta="hello"),
            LLMStreamChunk(finish_reason="stop"),
        ])
        cfg = MagicMock()

        text, p, c, meta = await _call_ai_stream(client, cfg, [], on_chunk=None)
        assert text == "hello"


class TestCallAiNonStream:
    @patch("core.agent._create_client")
    async def test_call_ai_returns_correct_data(self, mock_create):
        client = AsyncMock()
        client.generate = AsyncMock(return_value=LLMResponse(
            text="test response",
            prompt_tokens=10,
            completion_tokens=20,
            finish_reason="stop",
        ))
        cfg = MagicMock()

        text, p, c, meta = await _call_ai(client, cfg, [])

        assert text == "test response"
        assert p == 10
        assert c == 20
        assert meta["finish_reason"] == "stop"
