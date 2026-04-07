"""
Provider resolution helpers for realtime live gateway.
"""
from __future__ import annotations

from app.core.config import settings

_PROVIDER_ALIASES = {
    "google": "gemini",
    "gemini": "gemini",
    "gpt": "openai",
    "openai": "openai",
}


def normalize_provider(provider: str | None) -> str:
    token = (provider or "").strip().lower()
    return _PROVIDER_ALIASES.get(token, token or "gemini")


def infer_provider_from_model(model: str | None) -> str | None:
    token = (model or "").strip().lower()
    if not token:
        return None
    if "gemini" in token:
        return "gemini"
    if token.startswith("gpt-") or "realtime" in token and "gpt" in token:
        return "openai"
    return None


def resolve_live_provider(provider: str | None, model: str | None) -> str:
    explicit = normalize_provider(provider) if provider else ""
    inferred = infer_provider_from_model(model) or ""
    fallback = normalize_provider(settings.default_live_provider)
    return explicit or inferred or fallback or "gemini"


def provider_available(provider: str) -> tuple[bool, str | None]:
    normalized = normalize_provider(provider)
    if normalized == "gemini":
        if (settings.google_api_key or "").strip():
            return True, None
        return False, "GOOGLE_API_KEY is not configured."
    if normalized == "openai":
        if (settings.openai_api_key or "").strip():
            return False, "OpenAI live gateway adapter is not implemented yet."
        return False, "OPENAI_API_KEY is not configured."
    return False, f"Unsupported live provider: {provider}"


def supported_live_providers() -> list[str]:
    return ["gemini", "openai"]

