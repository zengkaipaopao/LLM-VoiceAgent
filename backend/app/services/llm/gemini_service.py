"""
Google Gemini LLM service implementation.
"""
import json
import logging
import re
from typing import Any, AsyncIterator, Dict, List, Optional

from google.genai import types

from app.core.model_defaults import DEFAULT_GENERATE_MODEL
from app.services.google_genai_client import create_google_genai_client

from .base import BaseLLMService
from .exceptions import LLMAPIError, LLMInvalidResponseError, LLMRateLimitError

logger = logging.getLogger(__name__)


class GeminiService(BaseLLMService):
    """Google Gemini LLM service implementation."""

    def __init__(self, api_key: str, model: str = DEFAULT_GENERATE_MODEL):
        super().__init__(api_key, model)
        self.client = create_google_genai_client()

    def _build_generation_config(
        self,
        temperature: float,
        max_tokens: Optional[int],
        response_format: str,
        output_schema: Optional[Dict[str, Any]],
    ) -> types.GenerateContentConfig:
        config: Dict[str, Any] = {
            "temperature": temperature,
        }

        if max_tokens:
            config["max_output_tokens"] = max_tokens

        if response_format == "json_object":
            config["response_mime_type"] = "application/json"
            if output_schema:
                normalized_schema = self._normalize_schema_for_gemini(output_schema)
                if normalized_schema:
                    config["response_schema"] = normalized_schema

        return types.GenerateContentConfig(**config)

    @staticmethod
    def _map_schema_type(raw_type: Any) -> Optional[str]:
        if not isinstance(raw_type, str):
            return None
        mapping = {
            "string": "STRING",
            "number": "NUMBER",
            "integer": "INTEGER",
            "boolean": "BOOLEAN",
            "array": "ARRAY",
            "object": "OBJECT",
            "null": "NULL",
            "type_unspecified": "TYPE_UNSPECIFIED",
        }
        return mapping.get(raw_type.lower(), raw_type.upper())

    @classmethod
    def _normalize_schema_node(cls, node: Any) -> Any:
        if isinstance(node, list):
            return [cls._normalize_schema_node(item) for item in node]
        if not isinstance(node, dict):
            return node

        normalized: Dict[str, Any] = {}
        nullable = False

        raw_type = node.get("type")
        if isinstance(raw_type, list):
            mapped_types = [cls._map_schema_type(item) for item in raw_type if isinstance(item, str)]
            mapped_types = [item for item in mapped_types if item]
            if "NULL" in mapped_types:
                nullable = True
                mapped_types = [item for item in mapped_types if item != "NULL"]
            if mapped_types:
                normalized["type"] = mapped_types[0]
            elif nullable:
                normalized["type"] = "NULL"
        elif raw_type is not None:
            mapped_type = cls._map_schema_type(raw_type)
            if mapped_type:
                normalized["type"] = mapped_type

        if nullable:
            normalized["nullable"] = True

        for key, value in node.items():
            if key in {"type", "$schema"}:
                continue

            normalized_key = key
            if key == "$ref":
                normalized_key = "ref"
            elif key == "$defs":
                normalized_key = "defs"
            elif key == "any_of":
                normalized_key = "anyOf"
            elif key in {"additional_properties", "additionalProperties"}:
                # Gemini response_schema currently rejects this field.
                continue

            if normalized_key in {"properties", "defs"} and isinstance(value, dict):
                normalized[normalized_key] = {
                    prop_name: cls._normalize_schema_node(prop_schema)
                    for prop_name, prop_schema in value.items()
                }
                continue

            if normalized_key == "items" and isinstance(value, dict):
                normalized[normalized_key] = cls._normalize_schema_node(value)
                continue

            if normalized_key in {"anyOf", "any_of"} and isinstance(value, list):
                normalized[normalized_key] = [cls._normalize_schema_node(item) for item in value]
                continue

            if normalized_key == "required" and isinstance(value, list):
                normalized[normalized_key] = [item for item in value if isinstance(item, str)]
                continue

            normalized[normalized_key] = value

        return normalized

    @classmethod
    def _normalize_schema_for_gemini(cls, schema: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            normalized = cls._normalize_schema_node(schema)
            if not isinstance(normalized, dict):
                return None

            # Validate compatibility against SDK schema model before sending request.
            validated = types.Schema(**normalized)
            return validated.model_dump(mode="json", by_alias=True, exclude_none=True)
        except Exception as exc:
            logger.warning("Failed to normalize Gemini response schema; fallback to no schema: %s", exc)
            return None

    @staticmethod
    def _is_rate_limit_error(error: Exception) -> bool:
        text = str(error).lower()
        return any(
            keyword in text
            for keyword in ["quota", "rate", "429", "resource exhausted", "too many requests"]
        )

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        response_format: str = "text",
        output_schema: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> str:
        """Get complete chat response from Gemini."""
        try:
            prompt = self._convert_messages(messages)
            config = self._build_generation_config(
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
                output_schema=output_schema,
            )

            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )

            return response.text or ""

        except Exception as e:
            if self._is_rate_limit_error(e):
                raise LLMRateLimitError(f"Gemini rate limit exceeded: {e}")
            raise LLMAPIError(f"Gemini API error: {e}")

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        response_format: str = "text",
        output_schema: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Get streaming chat response from Gemini."""
        try:
            prompt = self._convert_messages(messages)
            config = self._build_generation_config(
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
                output_schema=output_schema,
            )

            stream = await self.client.aio.models.generate_content_stream(
                model=self.model,
                contents=prompt,
                config=config,
            )

            async for chunk in stream:
                text = chunk.text or ""
                if text:
                    yield text

        except Exception as e:
            if self._is_rate_limit_error(e):
                raise LLMRateLimitError(f"Gemini rate limit exceeded: {e}")
            raise LLMAPIError(f"Gemini API error: {e}")

    async def chat_with_json(
        self,
        messages: List[Dict[str, str]],
        schema: Optional[Dict[str, Any]] = None,
        temperature: float = 0.7,
        **kwargs,
    ) -> Dict[str, Any]:
        """Get JSON-formatted response from Gemini."""
        try:
            response_text = await self.chat_completion(
                messages=messages,
                temperature=temperature,
                response_format="json_object",
                output_schema=schema,
            )
            return json.loads(response_text)

        except json.JSONDecodeError as e:
            raise LLMInvalidResponseError(f"Invalid JSON response: {e}")
        except LLMInvalidResponseError:
            raise
        except Exception as e:
            if self._is_rate_limit_error(e):
                raise LLMRateLimitError(f"Gemini rate limit exceeded: {e}")
            raise LLMAPIError(f"Gemini API error: {e}")

    async def list_models(self) -> List[str]:
        """List available Gemini models."""
        catalog = await self.list_models_catalog()
        return [item["name"] for item in catalog]

    @staticmethod
    def _normalize_action_name(action: str) -> str:
        return re.sub(r"[^a-z]", "", (action or "").lower())

    async def list_models_catalog(self) -> List[Dict[str, Any]]:
        """List Gemini models with capability metadata for UI grouping."""
        try:
            pager = await self.client.aio.models.list()
            models: List[Dict[str, Any]] = []

            async for model in pager:
                name = (model.name or "").replace("models/", "")
                if not name or "gemini" not in name.lower():
                    continue

                supported_actions = [
                    str(action).strip()
                    for action in (model.supported_actions or [])
                    if str(action).strip()
                ]
                normalized_actions = {self._normalize_action_name(action) for action in supported_actions}
                is_generate = "generatecontent" in normalized_actions
                is_live = "bidigeneratecontent" in normalized_actions or "live" in name.lower()

                capability = "other"
                if is_generate and is_live:
                    capability = "both"
                elif is_generate:
                    capability = "generate"
                elif is_live:
                    capability = "live"

                models.append(
                    {
                        "name": name,
                        "capability": capability,
                        "is_generate": is_generate,
                        "is_live": is_live,
                        "supported_actions": sorted(set(supported_actions)),
                    }
                )

            unique_by_name: Dict[str, Dict[str, Any]] = {}
            for item in models:
                unique_by_name[item["name"]] = item

            capability_order = {"both": 0, "generate": 1, "live": 2, "other": 3}
            return sorted(
                unique_by_name.values(),
                key=lambda item: (capability_order.get(str(item.get("capability")), 9), str(item.get("name", "")).lower()),
            )
        except Exception as e:
            raise LLMAPIError(f"Gemini list models error: {e}")

    def _convert_messages(self, messages: List[Dict[str, str]]) -> str:
        """Convert standard message format to a single Gemini prompt."""
        prompt_parts: List[str] = []

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
