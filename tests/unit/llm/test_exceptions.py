"""Tests for LLM exception hierarchy."""

from core.llm.exceptions import (
    LLMError,
    LLMAuthError,
    LLMConfigurationError,
    LLMRateLimitError,
    LLMTimeoutError,
)


class TestLLMExceptions:
    """LLM exception hierarchy tests."""

    def test_llm_error_base(self):
        err = LLMError("Something went wrong", code="TEST", recoverable=True)
        assert err.message == "Something went wrong"
        assert err.code == "TEST"
        assert err.recoverable is True
        assert str(err) == "Something went wrong"

    def test_llm_error_defaults(self):
        err = LLMError("Default error")
        assert err.code == "LLM_ERROR"
        assert err.recoverable is False

    def test_llm_auth_error(self):
        err = LLMAuthError()
        assert err.code == "AUTH_ERROR"
        assert err.recoverable is True
        assert "API key" in err.message

        err_custom = LLMAuthError("Custom auth message")
        assert err_custom.message == "Custom auth message"

    def test_llm_rate_limit_error(self):
        err = LLMRateLimitError()
        assert err.code == "RATE_LIMIT"
        assert err.recoverable is True
        assert "Rate limit" in err.message

    def test_llm_timeout_error(self):
        err = LLMTimeoutError()
        assert err.code == "TIMEOUT"
        assert err.recoverable is True
        assert "timed out" in err.message.lower()

    def test_llm_configuration_error(self):
        err = LLMConfigurationError("Unknown provider: foo")
        assert err.code == "CONFIG_ERROR"
        assert err.recoverable is False

    def test_inheritance(self):
        assert issubclass(LLMAuthError, LLMError)
        assert issubclass(LLMRateLimitError, LLMError)
        assert issubclass(LLMTimeoutError, LLMError)
        assert issubclass(LLMConfigurationError, LLMError)
        assert isinstance(LLMAuthError(), LLMError)
        assert isinstance(LLMRateLimitError(), LLMError)
