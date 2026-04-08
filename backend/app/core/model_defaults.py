"""
Shared model defaults and transport-aware model resolution helpers.
"""
from __future__ import annotations

DEFAULT_GENERATE_MODEL = "gemini-2.5-flash"
DEFAULT_LIVE_MODEL = "gemini-2.5-flash-native-audio-latest"


def is_live_model(model: str | None) -> bool:
    token = (model or "").strip().lower()
    if not token:
        return False
    return "live" in token or "realtime" in token or "native-audio" in token


def resolve_generate_model(model: str | None, *, fallback_model: str | None = None) -> str:
    candidate = (model or "").strip()
    if candidate and not is_live_model(candidate):
        return candidate

    fallback = (fallback_model or "").strip()
    if fallback and not is_live_model(fallback):
        return fallback

    return DEFAULT_GENERATE_MODEL


def resolve_live_model(model: str | None, *, fallback_model: str | None = None) -> str:
    candidate = (model or "").strip()
    if candidate and is_live_model(candidate):
        return candidate

    fallback = (fallback_model or "").strip()
    if fallback and is_live_model(fallback):
        return fallback

    return DEFAULT_LIVE_MODEL


def require_generate_model(model: str | None, *, source: str = "Selected model") -> str:
    token = (model or "").strip()
    if not token:
        return DEFAULT_GENERATE_MODEL
    if is_live_model(token):
        raise ValueError(
            f"{source} '{token}' is a live-only model and cannot be used in text testing. "
            "Please switch to the voice test tab or choose a generate-capable model in the prompt."
        )
    return token


def require_live_model(model: str | None, *, source: str = "Selected model") -> str:
    token = (model or "").strip()
    if not token:
        return DEFAULT_LIVE_MODEL
    if not is_live_model(token):
        raise ValueError(
            f"{source} '{token}' is not a live model and cannot be used in voice testing. "
            "Please choose a Gemini Live model in the prompt or override the voice test model explicitly."
        )
    return token
