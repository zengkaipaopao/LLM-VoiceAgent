"""
Provider adapters for voice turn runtime.
"""
from __future__ import annotations

from app.core.config import settings
from app.services.llm.factory import LLMFactory

from .base import (
    BaseVoiceTurnEngine,
    VoiceProviderNotImplementedError,
    VoiceProviderUnavailableError,
    VoiceTurnRequest,
)


class GeminiVoiceTurnEngine(BaseVoiceTurnEngine):
    provider = "gemini"

    def is_available(self) -> tuple[bool, str | None]:
        if not (settings.google_api_key or "").strip():
            return False, "GOOGLE_API_KEY is not configured."
        return True, None

    async def generate_reply(self, request: VoiceTurnRequest) -> str:
        available, reason = self.is_available()
        if not available:
            raise VoiceProviderUnavailableError(reason or "Gemini provider unavailable.")

        llm_service = LLMFactory.create(
            provider=self.provider,
            api_key=settings.google_api_key,
            model=request.model,
        )
        return await llm_service.chat_completion(
            messages=[{"role": "system", "content": request.system_prompt}, *request.messages],
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )


class OpenAIVoiceTurnEngine(BaseVoiceTurnEngine):
    provider = "openai"

    def is_available(self) -> tuple[bool, str | None]:
        if not (settings.openai_api_key or "").strip():
            return False, "OPENAI_API_KEY is not configured."
        return True, None

    async def generate_reply(self, request: VoiceTurnRequest) -> str:
        available, reason = self.is_available()
        if not available:
            raise VoiceProviderUnavailableError(reason or "OpenAI provider unavailable.")

        # Keep this adapter entry so provider switching is a config change later.
        # Actual OpenAI runtime implementation can replace this section without
        # changing telephony orchestration.
        raise VoiceProviderNotImplementedError(
            "OpenAI voice turn runtime is reserved but not implemented in this build."
        )

