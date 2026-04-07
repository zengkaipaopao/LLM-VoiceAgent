"""
Provider-agnostic voice turn runtime contracts.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class VoiceTurnRequest:
    provider: str
    model: str
    system_prompt: str
    messages: list[dict[str, str]]
    temperature: float
    max_tokens: int


class VoiceTurnRuntimeError(Exception):
    """Base error for voice turn runtime."""


class VoiceProviderUnavailableError(VoiceTurnRuntimeError):
    """Provider is known but not configured or currently unavailable."""


class VoiceProviderNotImplementedError(VoiceTurnRuntimeError):
    """Provider is planned but not implemented in this build."""


class BaseVoiceTurnEngine(ABC):
    """Abstract provider adapter used by telephony voice turn loops."""

    provider: str

    @abstractmethod
    def is_available(self) -> tuple[bool, str | None]:
        """Return availability status and optional reason."""

    @abstractmethod
    async def generate_reply(self, request: VoiceTurnRequest) -> str:
        """Generate one assistant turn for current provider."""
