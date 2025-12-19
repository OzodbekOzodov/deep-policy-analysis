class LLMClientError(Exception):
    """Base exception for LLM client errors."""
    pass

class LLMConnectionError(LLMClientError):
    """Failed to connect to LLM Gateway."""
    pass

class LLMResponseError(LLMClientError):
    """LLM Gateway returned an error."""
    pass
