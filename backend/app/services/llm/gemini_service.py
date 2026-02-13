"""
Google Gemini LLM service implementation.
"""
import json
import google.generativeai as genai
from typing import AsyncIterator, Dict, Any, Optional, List

from .base import BaseLLMService
from .exceptions import LLMAPIError, LLMRateLimitError, LLMInvalidResponseError


class GeminiService(BaseLLMService):
    """Google Gemini LLM service implementation."""
    
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        """
        Initialize Gemini service.
        
        Args:
            api_key: Google API key
            model: Gemini model name
        """
        super().__init__(api_key, model)
        genai.configure(api_key=api_key)
        self.client = genai.GenerativeModel(model)
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        response_format: str = "text",
        output_schema: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> str:
        """Get complete chat response from Gemini."""
        try:
            # Convert messages to Gemini format
            prompt = self._convert_messages(messages)
            
            # Configure generation
            generation_config = {
                "temperature": temperature,
            }
            if max_tokens:
                generation_config["max_output_tokens"] = max_tokens
            
            if response_format == "json_object":
                generation_config["response_mime_type"] = "application/json"
                if output_schema:
                    generation_config["response_schema"] = output_schema
            
            # Generate response
            response = await self.client.generate_content_async(
                prompt,
                generation_config=generation_config
            )
            
            return response.text
            
        except Exception as e:
            if "quota" in str(e).lower() or "rate" in str(e).lower():
                raise LLMRateLimitError(f"Gemini rate limit exceeded: {e}")
            raise LLMAPIError(f"Gemini API error: {e}")
    
    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        response_format: str = "text",
        output_schema: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """Get streaming chat response from Gemini."""
        try:
            # Convert messages to Gemini format
            prompt = self._convert_messages(messages)
            
            # Configure generation
            generation_config = {
                "temperature": temperature,
            }
            if max_tokens:
                generation_config["max_output_tokens"] = max_tokens
            
            if response_format == "json_object":
                generation_config["response_mime_type"] = "application/json"
                if output_schema:
                    generation_config["response_schema"] = output_schema
            
            # Generate streaming response
            response = await self.client.generate_content_async(
                prompt,
                generation_config=generation_config,
                stream=True
            )
            
            async for chunk in response:
                if chunk.text:
                    yield chunk.text
                    
        except Exception as e:
            if "quota" in str(e).lower() or "rate" in str(e).lower():
                raise LLMRateLimitError(f"Gemini rate limit exceeded: {e}")
            raise LLMAPIError(f"Gemini API error: {e}")
    
    async def chat_with_json(
        self,
        messages: List[Dict[str, str]],
        schema: Optional[Dict[str, Any]] = None,
        temperature: float = 0.7,
        **kwargs
    ) -> Dict[str, Any]:
        """Get JSON-formatted response from Gemini."""
        try:
            # Convert messages to Gemini format
            prompt = self._convert_messages(messages)
            
            # Configure for JSON output
            generation_config = {
                "temperature": temperature,
                "response_mime_type": "application/json"
            }
            
            # Generate response
            response = await self.client.generate_content_async(
                prompt,
                generation_config=generation_config
            )
            
            # Parse JSON
            try:
                return json.loads(response.text)
            except json.JSONDecodeError as e:
                raise LLMInvalidResponseError(f"Invalid JSON response: {e}")
                
        except LLMInvalidResponseError:
            raise
        except Exception as e:
            if "quota" in str(e).lower() or "rate" in str(e).lower():
                raise LLMRateLimitError(f"Gemini rate limit exceeded: {e}")
            raise LLMAPIError(f"Gemini API error: {e}")

    async def list_models(self) -> List[str]:
        """
        List available Gemini models.
        """
        try:
            models = []
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    # Filter for gemini models (optional, but good practice)
                    if "gemini" in m.name.lower():
                        # m.name is like 'models/gemini-pro', we want just 'gemini-pro'
                        name = m.name.replace("models/", "")
                        models.append(name)
            return sorted(models)
        except Exception as e:
             raise LLMAPIError(f"Gemini list models error: {e}")
    
    def _convert_messages(self, messages: List[Dict[str, str]]) -> str:
        """
        Convert standard message format to Gemini prompt format.
        
        Gemini uses a simple string prompt, so we concatenate messages.
        """
        prompt_parts = []
        
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                prompt_parts.append(f"System: {content}")
            elif role == "user":
                prompt_parts.append(f"User: {content}")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")
        
        return "\n\n".join(prompt_parts)
