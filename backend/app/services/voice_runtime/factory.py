"""
Factory for provider-agnostic voice turn runtime engines.
"""
from __future__ import annotations

from .base import BaseVoiceTurnEngine, VoiceProviderUnavailableError
from .engines import GeminiVoiceTurnEngine, OpenAIVoiceTurnEngine


class VoiceTurnEngineFactory:
    _registry: dict[str, type[BaseVoiceTurnEngine]] = {
        "gemini": GeminiVoiceTurnEngine,
        "openai": OpenAIVoiceTurnEngine,
    }

    @classmethod
    def create(cls, provider: str) -> BaseVoiceTurnEngine:
        key = (provider or "").strip().lower()
        engine_cls = cls._registry.get(key)
        if not engine_cls:
            raise VoiceProviderUnavailableError(f"Unsupported voice provider: {provider}")
        return engine_cls()

    @classmethod
    def supported_providers(cls) -> list[str]:
        return sorted(cls._registry.keys())

