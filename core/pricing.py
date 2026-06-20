"""Token pricing helpers for topbar usage estimates."""

from dataclasses import dataclass
from typing import Callable, Dict, Optional, Tuple


@dataclass(frozen=True)
class TokenPrice:
    """USD token price per one million input/output tokens."""

    input_per_million: float
    output_per_million: float


PriceKey = Tuple[str, str]
PriceRule = Tuple[str, str, TokenPrice]


MODEL_PRICES: Dict[PriceKey, TokenPrice] = {
    # DeepSeek V4 pricing. DeepSeek reports cache-hit/cache-miss prompt tokens,
    # but OrcaCode currently receives only aggregate prompt tokens, so use the
    # cache-miss rate to avoid under-reporting cost.
    ("deepseek", "deepseek-v4-flash"): TokenPrice(0.14, 0.28),
    ("deepseek", "deepseek-chat"): TokenPrice(0.14, 0.28),
    ("deepseek", "deepseek-reasoner"): TokenPrice(0.14, 0.28),
    ("deepseek", "deepseek-v4-pro"): TokenPrice(0.435, 0.87),

    # OpenAI text model pricing used by the TUI presets and common legacy IDs.
    ("openai", "gpt-5.5"): TokenPrice(5.0, 30.0),
    ("openai", "gpt-5.5-pro"): TokenPrice(5.0, 30.0),
    ("openai", "gpt-5.5-instant"): TokenPrice(0.75, 4.5),
    ("openai", "gpt-5"): TokenPrice(1.25, 10.0),
    ("openai", "gpt-4o"): TokenPrice(2.5, 10.0),
    ("openai", "gpt-4o-mini"): TokenPrice(0.15, 0.60),
    ("openai", "o1-mini"): TokenPrice(1.10, 4.40),

    # Anthropic / Claude pricing. The UI accepts both "claude" and
    # "anthropic" provider names; normalization maps both to anthropic.
    ("anthropic", "claude-fable-5"): TokenPrice(10.0, 50.0),
    ("anthropic", "claude-opus-4.8"): TokenPrice(5.0, 25.0),
    ("anthropic", "claude-opus-4.6"): TokenPrice(5.0, 25.0),
    ("anthropic", "claude-sonnet-4.6"): TokenPrice(3.0, 15.0),
    ("anthropic", "claude-haiku-4.5"): TokenPrice(1.0, 5.0),
    ("anthropic", "claude-3-5-sonnet-latest"): TokenPrice(3.0, 15.0),
    ("anthropic", "claude-3-5-haiku-latest"): TokenPrice(0.80, 4.0),

    # Gemini preset estimates. Google pricing can vary by context length for
    # some models; these entries use the standard <=200K-token tier.
    ("gemini", "gemini-3.5-pro"): TokenPrice(2.0, 12.0),
    ("gemini", "gemini-3.5-flash"): TokenPrice(1.5, 9.0),
    ("gemini", "gemini-3-deep-think"): TokenPrice(2.0, 12.0),
    ("gemini", "gemini-3.1-pro"): TokenPrice(2.0, 12.0),
    ("gemini", "gemini-2.0-flash"): TokenPrice(0.10, 0.40),
    ("gemini", "gemini-1.5-flash"): TokenPrice(0.075, 0.30),
    ("gemini", "gemini-1.5-pro"): TokenPrice(1.25, 5.0),
}


MODEL_PREFIX_RULES: Tuple[PriceRule, ...] = (
    ("anthropic", "claude-fable-5", TokenPrice(10.0, 50.0)),
    ("anthropic", "claude-opus", TokenPrice(5.0, 25.0)),
    ("anthropic", "claude-sonnet", TokenPrice(3.0, 15.0)),
    ("anthropic", "claude-haiku-4.5", TokenPrice(1.0, 5.0)),
    ("anthropic", "claude-3-5-haiku", TokenPrice(0.80, 4.0)),
    ("anthropic", "claude-3-5-sonnet", TokenPrice(3.0, 15.0)),
    ("openai", "gpt-5.5-instant", TokenPrice(0.75, 4.5)),
    ("openai", "gpt-5.5", TokenPrice(5.0, 30.0)),
    ("openai", "gpt-5", TokenPrice(1.25, 10.0)),
    ("openai", "gpt-4o-mini", TokenPrice(0.15, 0.60)),
    ("openai", "gpt-4o", TokenPrice(2.5, 10.0)),
    ("deepseek", "deepseek-v4-pro", TokenPrice(0.435, 0.87)),
    ("deepseek", "deepseek-v4-flash", TokenPrice(0.14, 0.28)),
    ("deepseek", "deepseek-chat", TokenPrice(0.14, 0.28)),
    ("deepseek", "deepseek-reasoner", TokenPrice(0.14, 0.28)),
    ("gemini", "gemini-3.5-flash", TokenPrice(1.5, 9.0)),
    ("gemini", "gemini-3.5-pro", TokenPrice(2.0, 12.0)),
    ("gemini", "gemini-3-deep-think", TokenPrice(2.0, 12.0)),
    ("gemini", "gemini-3.1-pro", TokenPrice(2.0, 12.0)),
)


PROVIDER_FALLBACKS: Dict[str, TokenPrice] = {
    "deepseek": TokenPrice(0.14, 0.28),
    "openai": TokenPrice(2.5, 10.0),
    "anthropic": TokenPrice(3.0, 15.0),
    "gemini": TokenPrice(0.30, 2.50),
}


OPENROUTER_PROVIDER_PREFIXES: Dict[str, str] = {
    "anthropic": "anthropic",
    "claude": "anthropic",
    "deepseek": "deepseek",
    "google": "gemini",
    "google-gemini": "gemini",
    "openai": "openai",
}


def _clean(value: object) -> str:
    return str(value or "").strip().lower()


def normalize_pricing_target(provider: str, model: str) -> Tuple[str, str]:
    """Return canonical provider/model names for pricing lookups."""

    clean_provider = _clean(provider)
    clean_model = _clean(model)

    if clean_provider == "claude":
        clean_provider = "anthropic"

    if clean_provider == "openrouter" and "/" in clean_model:
        route_provider, route_model = clean_model.split("/", 1)
        mapped_provider = OPENROUTER_PROVIDER_PREFIXES.get(route_provider)
        if mapped_provider:
            return mapped_provider, route_model

    return clean_provider, clean_model


def resolve_token_price(provider: str, model: str) -> Optional[TokenPrice]:
    """Find the best token price for a provider/model pair."""

    clean_provider, clean_model = normalize_pricing_target(provider, model)

    if clean_provider == "9router":
        return TokenPrice(0.0, 0.0)

    exact = MODEL_PRICES.get((clean_provider, clean_model))
    if exact:
        return exact

    for rule_provider, model_prefix, price in MODEL_PREFIX_RULES:
        if clean_provider == rule_provider and clean_model.startswith(model_prefix):
            return price

    return PROVIDER_FALLBACKS.get(clean_provider)


def estimate_token_cost(provider: str, model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Estimate USD cost for one model call."""

    price = resolve_token_price(provider, model)
    if not price:
        return 0.0

    prompt_count = max(int(prompt_tokens or 0), 0)
    completion_count = max(int(completion_tokens or 0), 0)
    return (
        prompt_count * price.input_per_million
        + completion_count * price.output_per_million
    ) / 1_000_000


def callback_accepts_token_context(callback: Callable) -> bool:
    """Return True when a token callback accepts provider/model context."""

    try:
        import inspect

        signature = inspect.signature(callback)
    except (TypeError, ValueError):
        return True

    positional_count = 0
    for parameter in signature.parameters.values():
        if parameter.kind == parameter.VAR_POSITIONAL:
            return True
        if parameter.kind in (parameter.POSITIONAL_ONLY, parameter.POSITIONAL_OR_KEYWORD):
            positional_count += 1
    return positional_count >= 4
