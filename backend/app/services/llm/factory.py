"""
LLM service factory.

Creates the appropriate LLM service based on provider name.
"""
import logging
from typing import Optional

from .base import BaseLLMService
from .gemini_service import GeminiService

logger = logging.getLogger(__name__)


class LLMFactory:
    """Factory for creating LLM service instances."""
    
    @staticmethod
    def create(
        provider: str,
        api_key: str,
        model: Optional[str] = None
    ) -> BaseLLMService:
        """
        Create an LLM service instance.
        
        Args:
            provider: Provider name ('gemini', 'openai', 'claude')
            api_key: API key for the provider
            model: Model name (optional, uses default if not specified)
            
        Returns:
            LLM service instance
            
        Raises:
            ValueError: If provider is unknown
        """
        provider = provider.lower()
        
        if provider == "gemini":
            model = model or "gemini-2.0-flash"
            return GeminiService(api_key, model)
        
        elif provider == "openai":
            # TODO: Implement OpenAI service
            raise NotImplementedError(
                "OpenAI support coming soon. "
                "Please use 'gemini' for now."
            )
        
        elif provider == "claude":
            # TODO: Implement Claude service
            raise NotImplementedError(
                "Claude support coming soon. "
                "Please use 'gemini' for now."
            )
        
        else:
            raise ValueError(
                f"Unknown LLM provider: {provider}. "
                f"Supported providers: gemini, openai (coming soon), claude (coming soon)"
            )
    
    @staticmethod
    async def get_models(provider: str, api_key: str) -> list[str]:
        """
        Get available models for a provider.
        """
        provider = provider.lower()
        
        if provider == "gemini":
            try:
                # We interpret api_key as needed for instantiation
                service = GeminiService(api_key)
                return await service.list_models()
            except Exception:
                # Fallback if API fails
                logger.exception("Failed to list Gemini models from API; using fallback models.")
                return ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash", "gemini-1.0-pro"]

        if provider == "openai":
            raise NotImplementedError("OpenAI provider is planned but not enabled in this build.")

        if provider == "claude":
            raise NotImplementedError("Claude provider is planned but not enabled in this build.")
            
        return []

    @staticmethod
    def get_supported_providers() -> list[str]:
        """Get list of supported providers."""
        return ["gemini", "openai (coming soon)", "claude (coming soon)"]
