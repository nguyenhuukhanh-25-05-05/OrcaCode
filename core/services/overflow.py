"""Model context limits and graduated pressure level detection.

Learns from MiMo's overflow.ts pattern:
1. Reserve output buffer + compaction buffer from context window
2. Compute pressure level (0-3) based on usage ratio
3. Trigger progressively aggressive actions the fuller context gets
"""

import json
import logging
from typing import Optional

logger = logging.getLogger("orca.overflow")

# Known model context limits (tokens) — source: official model cards
MODEL_CONTEXT_LIMITS: dict[str, dict[str, int]] = {
    "deepseek": {
        "deepseek-chat": 65536,
        "deepseek-coder": 65536,
        "deepseek-reasoner": 65536,
    },
    "anthropic": {
        "claude-3-5-sonnet-*": 200000,
        "claude-3-opus-*": 200000,
        "claude-3-haiku-*": 200000,
        "claude-4-*": 200000,
        "claude-*-*": 200000,
    },
    "openai": {
        "gpt-4o": 128000,
        "gpt-4o-*": 128000,
        "gpt-4-turbo": 128000,
        "gpt-4-*": 8192,
        "gpt-3.5-turbo": 16385,
        "o1-*": 200000,
        "o3-*": 200000,
    },
    "gemini": {
        "gemini-2.0-*": 1048576,
        "gemini-1.5-*": 2097152,
    },
    "openrouter": "passthrough",
    "9router": "passthrough",
}

DEFAULT_CONTEXT_LIMIT = 200_000  # Conservative default for modern models

# Provider-level defaults when model pattern doesn't match
PROVIDER_DEFAULTS: dict[str, int] = {
    "deepseek": 65536,
    "anthropic": 200000,
    "openai": 128000,
    "gemini": 1048576,
    "openrouter": 200000,
    "9router": 200000,
}

OUTPUT_RESERVE_RATIO = 0.15       # Reserve 15% of context for output tokens
COMPACTION_RESERVE_RATIO = 0.10   # Reserve 10% for compaction output


def get_context_limit(provider: str, model: str, override: int = 0) -> int:
    """Get the context window size for a given provider/model combination.
    
    Lookup order:
    1. override > 0 (from config)
    2. Exact model match in MODEL_CONTEXT_LIMITS
    3. Wildcard pattern match (claude-*-* → 200000)
    4. Provider default (deepseek → 65536)
    5. Fallback to DEFAULT_CONTEXT_LIMIT (200000)
    """
    if override > 0:
        return override
    limits = MODEL_CONTEXT_LIMITS.get(provider)
    if limits is not None and limits != "passthrough":
        if model in limits:
            return limits[model]
        for pattern, limit in limits.items():
            if pattern.endswith("*") and model.startswith(pattern.rstrip("*")):
                return limit
    fallback = PROVIDER_DEFAULTS.get(provider)
    if fallback:
        return fallback
    return DEFAULT_CONTEXT_LIMIT


def estimate_tokens(messages: list[dict]) -> int:
    """Estimate token count of messages list (~3 chars per token for mixed content)."""
    if not messages:
        return 0
    text = json.dumps(messages, ensure_ascii=False)
    return max(1, len(text) // 3)


def usable_context(context_limit: int, max_output_tokens: int = 8192) -> int:
    """Compute usable input context after reserving output + compaction buffers.
    
    Reservation is proportional to context window:
    - Output reserve: 15% of context window (but at least output_tokens)
    - Compaction reserve: 10% of context window
    """
    if context_limit <= 0:
        return 0
    output_reserve = min(int(context_limit * OUTPUT_RESERVE_RATIO), max(max_output_tokens, 4096))
    compact_reserve = max(int(context_limit * COMPACTION_RESERVE_RATIO), 4096)
    total_reserve = output_reserve + compact_reserve
    usable = context_limit - total_reserve
    return max(4096, usable)


def pressure_level(tokens_used: int, context_limit: int, max_output: int = 8192) -> int:
    """Return graduated pressure level (0-3) based on context usage ratio.
    
    0: <50%  of usable — no action needed
    1: 50-70% — soft-trim old tool outputs (head+tail)
    2: 70-85% — hard-prune old tool outputs (compacted placeholders)
    3: >85%  — full compaction (keep recent turns, compact rest)
    """
    usable = usable_context(context_limit, max_output)
    if usable <= 0:
        return 0
    ratio = tokens_used / usable
    if ratio < 0.50:
        return 0
    if ratio < 0.70:
        return 1
    if ratio < 0.85:
        return 2
    return 3


def is_overflow(tokens_used: int, context_limit: int, max_output: int = 8192) -> bool:
    """Check if context has overflowed the usable window."""
    usable = usable_context(context_limit, max_output)
    return usable > 0 and tokens_used >= usable
