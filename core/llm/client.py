"""Unified LLM client — provider-agnostic interface.

Usage:
    client = LLMClient.from_config(app_config)
    response = await client.generate(messages)
    async for chunk in client.generate_stream(messages):
        print(chunk.delta)
"""

from __future__ import annotations

import os
from typing import AsyncIterator, Optional

from config.settings import AppConfig, get_api_base_url
from core.llm.exceptions import LLMAuthError, LLMConfigurationError
from core.llm.providers import (
    LLMResponse,
    LLMStreamChunk,
    AnthropicProvider,
    BaseProvider,
    GeminiProvider,
    OpenAIProvider,
)


class LLMClient:
    """Unified LLM client. Auto-selects provider based on config."""

    PROVIDER_MAP = {
        "openai": OpenAIProvider,
        "deepseek": OpenAIProvider,
        "openrouter": OpenAIProvider,
        "9router": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "claude": AnthropicProvider,
        "gemini": GeminiProvider,
    }

    def __init__(self, provider: BaseProvider):
        self._provider = provider

    @property
    def provider_name(self) -> str:
        return self._provider.name

    @property
    def model(self) -> str:
        return self._provider.model

    @classmethod
    def from_config(cls, cfg: AppConfig) -> "LLMClient":
        """Create client from AppConfig. Validates config first."""
        if not cfg.model.api_key:
            raise LLMAuthError(
                "API key not found! Set ORCA_API_KEY in .env or run 'orca setup'"
            )

        provider_cls = cls.PROVIDER_MAP.get(cfg.model.provider.lower())
        if provider_cls is None:
            raise LLMConfigurationError(
                f"Unsupported provider: {cfg.model.provider}. "
                f"Supported: {', '.join(cls.PROVIDER_MAP.keys())}"
            )

        base_url = cfg.model.base_url or get_api_base_url(cfg.model.provider)
        provider = provider_cls(
            api_key=cfg.model.api_key,
            model=cfg.model.model,
            base_url=base_url,
            temperature=cfg.model.temperature,
            max_tokens=cfg.model.max_tokens,
        )
        return cls(provider)

    async def generate(self, messages: list[dict]) -> LLMResponse:
        """Full response generation (non-streaming)."""
        return await self._provider.generate(messages)

    async def generate_stream(self, messages: list[dict]) -> AsyncIterator[LLMStreamChunk]:
        """Streaming response — yields chunks incrementally."""
        async for chunk in self._provider.generate_stream(messages):
            yield chunk
