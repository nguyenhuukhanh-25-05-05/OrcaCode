"""LLM-specific exceptions."""


class LLMError(Exception):
    """Base exception for all LLM-related errors."""

    def __init__(self, message: str, code: str = "LLM_ERROR", recoverable: bool = False):
        self.message = message
        self.code = code
        self.recoverable = recoverable
        super().__init__(message)


class LLMAuthError(LLMError):
    """Authentication failed (invalid/missing API key)."""

    def __init__(self, message: str = "API key is missing or invalid"):
        super().__init__(message, code="AUTH_ERROR", recoverable=True)


class LLMRateLimitError(LLMError):
    """Rate limit exceeded."""

    def __init__(self, message: str = "Rate limit exceeded. Retry after backoff."):
        super().__init__(message, code="RATE_LIMIT", recoverable=True)


class LLMTimeoutError(LLMError):
    """Request timed out."""

    def __init__(self, message: str = "LLM request timed out"):
        super().__init__(message, code="TIMEOUT", recoverable=True)


class LLMConfigurationError(LLMError):
    """Invalid configuration (unknown provider, missing fields)."""

    def __init__(self, message: str):
        super().__init__(message, code="CONFIG_ERROR", recoverable=False)
