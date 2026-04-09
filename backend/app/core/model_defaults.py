"""
Shared model defaults and transport-aware model resolution helpers.
"""
from __future__ import annotations

DEFAULT_GENERATE_MODEL = "gemini-2.5-flash"
DEFAULT_LIVE_MODEL = "gemini-2.5-flash-native-audio-latest"
_PROVIDER_ALIASES = {
    "google": "gemini",
    "gemini": "gemini",
    "gpt": "openai",
    "openai": "openai",
    "anthropic": "claude",
    "claude": "claude",
}
_KNOWN_PROVIDER_PREFIXES = set(_PROVIDER_ALIASES.values())


def normalize_provider_token(provider: str | None) -> str | None:
    token = (provider or "").strip().lower()
    if not token:
        return None
    return _PROVIDER_ALIASES.get(token, token)


def split_provider_model(model: str | None) -> tuple[str | None, str | None]:
    token = (model or "").strip()
    if not token:
        return None, None
    if "/" not in token:
        return None, token

    raw_prefix, remainder = token.split("/", 1)
    normalized_prefix = normalize_provider_token(raw_prefix)
    normalized_model = remainder.strip()
    if not normalized_prefix or normalized_prefix not in _KNOWN_PROVIDER_PREFIXES or not normalized_model:
        return None, token
    return normalized_prefix, normalized_model


def normalize_model_selection(provider: str | None, model: str | None) -> tuple[str | None, str | None]:
    explicit_provider = normalize_provider_token(provider)
    inferred_provider, normalized_model = split_provider_model(model)
    return explicit_provider or inferred_provider, normalized_model


def normalize_model_id(model: str | None) -> str | None:
    _, normalized_model = split_provider_model(model)
    return normalized_model


def is_live_model(model: str | None) -> bool:
    token = (normalize_model_id(model) or (model or "").strip()).lower()
    if not token:
        return False
    return "live" in token or "realtime" in token or "native-audio" in token


def resolve_generate_model(model: str | None, *, fallback_model: str | None = None) -> str:
    candidate = (normalize_model_id(model) or (model or "").strip()).strip()
    if candidate and not is_live_model(candidate):
        return candidate

    fallback = (normalize_model_id(fallback_model) or (fallback_model or "").strip()).strip()
    if fallback and not is_live_model(fallback):
        return fallback

    return DEFAULT_GENERATE_MODEL


def resolve_live_model(model: str | None, *, fallback_model: str | None = None) -> str:
    candidate = (normalize_model_id(model) or (model or "").strip()).strip()
    if candidate and is_live_model(candidate):
        return candidate

    fallback = (normalize_model_id(fallback_model) or (fallback_model or "").strip()).strip()
    if fallback and is_live_model(fallback):
        return fallback

    return DEFAULT_LIVE_MODEL


def require_generate_model(model: str | None, *, source: str = "Selected model") -> str:
    token = (normalize_model_id(model) or (model or "").strip()).strip()
    if not token:
        return DEFAULT_GENERATE_MODEL
    if is_live_model(token):
        raise ValueError(
            f"{source} '{token}' is a live-only model and cannot be used in text testing. "
            "Please switch to the voice test tab or choose a generate-capable model in the prompt."
        )
    return token


def require_live_model(model: str | None, *, source: str = "Selected model") -> str:
    token = (normalize_model_id(model) or (model or "").strip()).strip()
    if not token:
        return DEFAULT_LIVE_MODEL
    if not is_live_model(token):
        raise ValueError(
            f"{source} '{token}' is not a live model and cannot be used in voice testing. "
            "Please choose a Gemini Live model in the prompt or override the voice test model explicitly."
        )
    return token
