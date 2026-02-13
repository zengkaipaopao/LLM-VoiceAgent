"""
LLM service exceptions.
"""

class LLMServiceError(Exception):
    """Base exception for LLM service errors."""
    pass


class LLMAPIError(LLMServiceError):
    """API call failed."""
    pass


class LLMRateLimitError(LLMServiceError):
    """Rate limit exceeded."""
    pass


class LLMInvalidResponseError(LLMServiceError):
    """Invalid response from LLM."""
    pass
