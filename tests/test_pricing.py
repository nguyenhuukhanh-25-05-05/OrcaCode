import pytest

from config.settings import AppConfig
from core.pricing import callback_accepts_token_context, estimate_token_cost
from core.tui import OrcaTUI


def test_openrouter_routed_model_uses_underlying_provider_price():
    cost = estimate_token_cost("openrouter", "openai/gpt-4o", 1_000, 1_000)
    assert cost == pytest.approx(0.0125)


def test_deepseek_model_specific_price():
    flash_cost = estimate_token_cost("deepseek", "deepseek-chat", 1_000_000, 1_000_000)
    pro_cost = estimate_token_cost("deepseek", "deepseek-v4-pro", 1_000_000, 1_000_000)

    assert flash_cost == pytest.approx(0.42)
    assert pro_cost == pytest.approx(1.305)


def test_9router_reports_zero_external_cost():
    assert estimate_token_cost("9router", "any-local-model", 1_000_000, 1_000_000) == 0.0


def test_topbar_cost_accumulates_each_call_without_repricing_old_tokens():
    cfg = AppConfig()
    cfg.model.provider = "deepseek"
    cfg.model.model = "deepseek-chat"
    app = OrcaTUI(config=cfg)

    app._record_token_usage(1_000_000, 0)
    cfg.model.provider = "openai"
    cfg.model.model = "gpt-4o"
    app._record_token_usage(0, 1_000_000)

    assert app.total_prompt_tokens == 1_000_000
    assert app.total_completion_tokens == 1_000_000
    assert app.total_cost == pytest.approx(10.14)


def test_token_callback_context_detection_keeps_legacy_callbacks():
    assert not callback_accepts_token_context(lambda prompt, completion: None)
    assert callback_accepts_token_context(
        lambda prompt, completion, provider="", model="": None
    )
    assert callback_accepts_token_context(lambda *args: None)
