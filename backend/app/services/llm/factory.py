"""
LLM service factory.

Creates the appropriate LLM service based on provider name.
"""
from typing import Optional

from .base import BaseLLMService
from .gemini_service import GeminiService


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
            except Exception as e:
                # Fallback if API fails
                print(f"Failed to list Gemini models: {e}")
                return ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash", "gemini-1.0-pro"]
                
        elif provider == "openai":
            return ["gpt-4-turbo", "gpt-4o", "gpt-3.5-turbo"]
            
        elif provider == "claude":
            return ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"]
            
        return []

    @staticmethod
    def get_supported_providers() -> list[str]:
        """Get list of supported providers."""
        return ["gemini", "openai (coming soon)", "claude (coming soon)"]
