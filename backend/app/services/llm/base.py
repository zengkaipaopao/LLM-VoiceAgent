"""
Base LLM service interface.

All LLM providers must implement this interface to ensure compatibility.
"""
from abc import ABC, abstractmethod
from typing import AsyncIterator, Dict, Any, Optional, List


class BaseLLMService(ABC):
    """
    Abstract base class for LLM services.
    
    All LLM providers (Gemini, OpenAI, Claude, etc.) must implement this interface.
    """
    
    def __init__(self, api_key: str, model: str):
        """
        Initialize LLM service.
        
        Args:
            api_key: API key for the LLM provider
            model: Model name to use
        """
        self.api_key = api_key
        self.model = model
    
    @abstractmethod
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        response_format: str = "text",
        output_schema: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> str:
        """
        Get a complete chat response.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
            response_format: "text" or "json_object"
            output_schema: JSON schema for validation
            **kwargs: Additional provider-specific parameters
            
        Returns:
            Complete response text
            
        Raises:
            LLMAPIError: If API call fails
            LLMRateLimitError: If rate limit exceeded
        """
        pass
    
    @abstractmethod
    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        response_format: str = "text",
        output_schema: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        Get a streaming chat response.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
            response_format: "text" or "json_object"
            output_schema: JSON schema for validation
            **kwargs: Additional provider-specific parameters
            
        Yields:
            Response text chunks
            
        Raises:
            LLMAPIError: If API call fails
            LLMRateLimitError: If rate limit exceeded
        """
        pass
    
    @abstractmethod
    async def chat_with_json(
        self,
        messages: List[Dict[str, str]],
        schema: Optional[Dict[str, Any]] = None,
        temperature: float = 0.7,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Get a JSON-formatted response.
        
        Useful for structured data extraction.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            schema: Optional JSON schema for validation
            temperature: Sampling temperature (0-1)
            **kwargs: Additional provider-specific parameters
            
        Returns:
            Parsed JSON response
            
        Raises:
            LLMAPIError: If API call fails
            LLMInvalidResponseError: If response is not valid JSON
        """
        pass
        
    @abstractmethod
    async def list_models(self) -> List[str]:
        """
        List available models for this provider.
        
        Returns:
            List of model names (e.g. ['gemini-pro', 'gemini-flash'])
        """
        pass
    
    def _convert_messages(self, messages: List[Dict[str, str]]) -> Any:
        """
        Convert standard message format to provider-specific format.
        
        Override this method if the provider uses a different message format.
        
        Args:
            messages: Standard message format
            
        Returns:
            Provider-specific message format
        """
        return messages
