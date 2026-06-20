"""Provider-specific LLM adapters.

Each provider implements the BaseProvider ABC with:
- Lazy import of provider SDK (only loaded when first used)
- Async generation with optional streaming
- Proper token tracking
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional

from core.llm.exceptions import LLMError, LLMAuthError, LLMConfigurationError, LLMRateLimitError, LLMTimeoutError
from core.constants import MAX_RESPONSE_CHARS, RESPONSE_TRUNCATED_MSG


@dataclass
class LLMResponse:
    """Structured response from any provider."""
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    finish_reason: Optional[str] = None
    truncated: bool = False
    elapsed_ms: float = 0.0


@dataclass
class LLMStreamChunk:
    """A single chunk during streaming."""
    delta: str = ""
    finish_reason: Optional[str] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0


class BaseProvider(ABC):
    """Abstract base for all LLM providers."""

    def __init__(self, api_key: str, model: str, base_url: str = "", temperature: float = 0.3, max_tokens: int = 65536):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._client = None

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g. 'openai', 'anthropic')."""

    @abstractmethod
    def _build_client(self):
        """Lazily create the underlying SDK client."""

    @abstractmethod
    def _format_messages(self, messages: list[dict]) -> tuple:
        """Convert generic messages to provider-specific format."""

    @abstractmethod
    async def generate(self, messages: list[dict]) -> LLMResponse:
        """Non-streaming generation."""

    @abstractmethod
    async def generate_stream(self, messages: list[dict]) -> AsyncIterator[LLMStreamChunk]:
        """Streaming generation — yields chunks as they arrive."""

    def get_client(self):
        if self._client is None:
            self._client = self._build_client()
        return self._client


class OpenAIProvider(BaseProvider):
    """OpenAI-compatible providers (OpenAI, DeepSeek, OpenRouter, 9Router)."""

    @property
    def name(self) -> str:
        return "openai"

    def _build_client(self):
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise LLMConfigurationError("openai package not installed. Run: pip install openai")
        return AsyncOpenAI(api_key=self.api_key, base_url=self.base_url or None)

    def _format_messages(self, messages: list[dict]) -> list[dict]:
        return messages  # OpenAI format is the default

    async def generate(self, messages: list[dict]) -> LLMResponse:
        client = self.get_client()
        start = time.monotonic()
        try:
            response = await client.chat.completions.create(
                model=self.model,
                messages=self._format_messages(messages),
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                timeout=300.0,
            )
        except Exception as e:
            raise _map_openai_error(e)

        elapsed = (time.monotonic() - start) * 1000
        usage = response.usage
        choice = response.choices[0]
        finish = getattr(choice, "finish_reason", None)
        truncated = str(finish or "").lower() in {"length", "max_tokens", "model_length"}
        text = (choice.message.content or "").strip()

        if len(text) > 50000:
            text = text[:50000] + "\n\n[Response truncated after 50,000 chars]"
            truncated = True

        return LLMResponse(
            text=text,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            finish_reason=finish,
            truncated=truncated,
            elapsed_ms=elapsed,
        )

    async def generate_stream(self, messages: list[dict]) -> AsyncIterator[LLMStreamChunk]:
        client = self.get_client()
        try:
            stream = await client.chat.completions.create(
                model=self.model,
                messages=self._format_messages(messages),
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                timeout=300.0,
                stream=True,
                stream_options={"include_usage": True},
            )
        except Exception as e:
            raise _map_openai_error(e)

        prompt_tokens = 0
        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            finish = chunk.choices[0].finish_reason if chunk.choices else None

            if chunk.usage:
                prompt_tokens = chunk.usage.prompt_tokens or 0

            yield LLMStreamChunk(
                delta=delta.content or "" if delta else "",
                finish_reason=finish,
                prompt_tokens=prompt_tokens,
                completion_tokens=0,
            )


class AnthropicProvider(BaseProvider):
    """Anthropic/Claude provider."""

    @property
    def name(self) -> str:
        return "anthropic"

    def _build_client(self):
        try:
            from anthropic import AsyncAnthropic
        except ImportError:
            raise LLMConfigurationError("anthropic package not installed. Run: pip install anthropic")
        return AsyncAnthropic(api_key=self.api_key)

    def _format_messages(self, messages: list[dict]) -> tuple:
        system = ""
        msgs = []
        for m in messages:
            if m.get("role") == "system":
                system = m.get("content", "")
            else:
                msgs.append({"role": m["role"], "content": m.get("content", "")})
        return system, msgs

    async def generate(self, messages: list[dict]) -> LLMResponse:
        client = self.get_client()
        system, msgs = self._format_messages(messages)
        start = time.monotonic()
        try:
            response = await client.messages.create(
                model=self.model,
                system=system or None,
                messages=msgs,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
        except Exception as e:
            raise _map_anthropic_error(e)

        elapsed = (time.monotonic() - start) * 1000
        usage = response.usage
        finish = getattr(response, "stop_reason", None)
        truncated = str(finish or "").lower() in {"max_tokens", "model_context_window_exceeded"}
        text = (response.content[0].text if response.content else "").strip()

        if len(text) > MAX_RESPONSE_CHARS:
            text = text[:MAX_RESPONSE_CHARS] + RESPONSE_TRUNCATED_MSG
            truncated = True

        return LLMResponse(
            text=text,
            prompt_tokens=usage.input_tokens if usage else 0,
            completion_tokens=usage.output_tokens if usage else 0,
            finish_reason=finish,
            truncated=truncated,
            elapsed_ms=elapsed,
        )

    async def generate_stream(self, messages: list[dict]) -> AsyncIterator[LLMStreamChunk]:
        client = self.get_client()
        system, msgs = self._format_messages(messages)
        try:
            stream = await client.messages.create(
                model=self.model,
                system=system or None,
                messages=msgs,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                stream=True,
            )
        except Exception as e:
            raise _map_anthropic_error(e)

        async for chunk in stream:
            if chunk.type == "content_block_delta":
                yield LLMStreamChunk(delta=chunk.delta.text or "")
            elif chunk.type == "message_delta":
                yield LLMStreamChunk(
                    finish_reason=chunk.delta.stop_reason,
                )


class GeminiProvider(BaseProvider):
    """Google Gemini provider."""

    @property
    def name(self) -> str:
        return "gemini"

    def _build_client(self):
        try:
            import google.generativeai as genai
        except ImportError:
            raise LLMConfigurationError("google-generativeai package not installed. Run: pip install google-generativeai")
        genai.configure(api_key=self.api_key)
        return genai.GenerativeModel(self.model)

    def _format_messages(self, messages: list[dict]) -> list[str]:
        prompt_parts = []
        for m in messages:
            content = m.get("content", "")
            if m.get("role") == "system":
                prompt_parts.insert(0, f"[System: {content}]")
            else:
                prompt_parts.append(f"[{m['role']}]: {content}")
        return prompt_parts

    async def generate(self, messages: list[dict]) -> LLMResponse:
        client = self.get_client()
        prompt = "\n".join(self._format_messages(messages))
        start = time.monotonic()
        try:
            response = await client.generate_content_async(
                prompt,
                request_options={"timeout": 300.0},
            )
        except Exception as e:
            raise _map_gemini_error(e)

        elapsed = (time.monotonic() - start) * 1000
        text = response.text.strip() if response else ""
        usage = getattr(response, "usage_metadata", None)
        prompt_tokens = usage.prompt_token_count if usage else 0
        completion_tokens = usage.candidates_token_count if usage else 0
        finish = None
        try:
            finish = response.candidates[0].finish_reason.name if response.candidates else None
        except Exception:
            pass
        truncated = str(finish or "").lower() in {"max_tokens", "length"}

        if len(text) > MAX_RESPONSE_CHARS:
            text = text[:MAX_RESPONSE_CHARS] + RESPONSE_TRUNCATED_MSG
            truncated = True

        return LLMResponse(
            text=text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            finish_reason=finish,
            truncated=truncated,
            elapsed_ms=elapsed,
        )

    async def generate_stream(self, messages: list[dict]) -> AsyncIterator[LLMStreamChunk]:
        client = self.get_client()
        prompt = "\n".join(self._format_messages(messages))
        try:
            response = await client.generate_content_async(prompt, stream=True)
        except Exception as e:
            raise _map_gemini_error(e)

        async for chunk in response:
            if chunk.text:
                yield LLMStreamChunk(delta=chunk.text)
            try:
                if chunk.candidates[0].finish_reason.name:
                    yield LLMStreamChunk(finish_reason=chunk.candidates[0].finish_reason.name)
            except Exception:
                pass


# ─── Error mapping helpers ─────────────────────────────────────────


def _map_openai_error(exc: Exception) -> LLMError:
    msg = str(exc)
    if "401" in msg or "unauthorized" in msg.lower() or "api key" in msg.lower():
        return LLMAuthError(msg)
    if "429" in msg or "rate limit" in msg.lower():
        return LLMRateLimitError(msg)
    if "timeout" in msg.lower() or "timed out" in msg.lower():
        return LLMTimeoutError(msg)
    return LLMError(msg, recoverable=True)


def _map_anthropic_error(exc: Exception) -> LLMError:
    msg = str(exc)
    if "401" in msg or "api key" in msg.lower() or "authentication" in msg.lower():
        return LLMAuthError(msg)
    if "429" in msg or "rate" in msg.lower():
        return LLMRateLimitError(msg)
    if "timeout" in msg.lower():
        return LLMTimeoutError(msg)
    return LLMError(msg, recoverable=True)


def _map_gemini_error(exc: Exception) -> LLMError:
    msg = str(exc)
    if "api key" in msg.lower() or "unauthorized" in msg.lower() or "permission" in msg.lower():
        return LLMAuthError(msg)
    if "rate" in msg.lower() or "quota" in msg.lower() or "429" in msg:
        return LLMRateLimitError(msg)
    if "timeout" in msg.lower():
        return LLMTimeoutError(msg)
    return LLMError(msg, recoverable=True)
