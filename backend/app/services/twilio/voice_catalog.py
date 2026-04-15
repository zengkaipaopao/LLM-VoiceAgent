import asyncio
import logging
import re
import time

import httpx
from fastapi import HTTPException, status

from app.core.config import settings
from app.services.twilio.normalizers import (
    _normalize_gemini_voice_names,
    _normalize_twilio_tts_provider,
    _normalize_twilio_voice_ids,
)

logger = logging.getLogger(__name__)

_TWILIO_TTS_DOC_URL = "https://www.twilio.com/docs/voice/twiml/say/text-speech.md"
_TWILIO_CONVERSATIONRELAY_VOICE_CONFIG_DOC_URL = (
    "https://www.twilio.com/docs/voice/conversationrelay/voice-configuration.md"
)
_GEMINI_VOICE_CACHE_TTL_SECONDS = 1800

_voice_catalog_lock = asyncio.Lock()
_voice_catalog_cache: dict[tuple[str, str], dict[str, object]] = {}
_conversationrelay_defaults_cache: dict[str, object] = {
    "settings": {},
    "source": "uninitialized",
    "fetched_at": 0.0,
}


def _extract_twilio_tts_voice_ids(
    markdown_doc: str,
    *,
    language_code: str,
    provider: str,
) -> list[str]:
    normalized_provider = _normalize_twilio_tts_provider(provider)
    if not normalized_provider:
        return []

    blocks = [block.strip() for block in markdown_doc.split("***")]
    voices: list[str] = []
    for block in blocks:
        if not block:
            continue
        if f"Language code: {language_code}" not in block:
            continue
        if f"Provider: {normalized_provider}" not in block:
            continue
        matched = re.search(r"Voice:\s*([A-Za-z0-9_.-]+)", block)
        if not matched:
            continue
        voices.append(matched.group(1).strip())
    return _normalize_twilio_voice_ids(voices)


def _extract_twilio_google_voice_names(markdown_doc: str, *, language_code: str) -> list[str]:
    voices: list[str] = []
    for voice_id in _extract_twilio_tts_voice_ids(
        markdown_doc,
        language_code=language_code,
        provider="Google",
    ):
        if "-Chirp3-HD-" not in voice_id:
            continue
        _, short_name = voice_id.split("-Chirp3-HD-", 1)
        voices.append(short_name.strip())
    return _normalize_gemini_voice_names(voices)


def _extract_twilio_conversationrelay_default_voice_settings(
    markdown_doc: str,
) -> dict[str, dict[str, str]]:
    settings_by_language: dict[str, dict[str, str]] = {}
    for raw_line in markdown_doc.splitlines():
        line = raw_line.strip()
        if not line.startswith("|") or line.startswith("| Language ") or line.startswith("| --------"):
            continue
        columns = [column.strip() for column in line.strip("|").split("|")]
        if len(columns) < 5:
            continue
        language, voice_id, tts_provider, speech_model, transcription_provider = columns[:5]
        if not language or not voice_id or not tts_provider:
            continue
        settings_by_language[language] = {
            "voice_id": voice_id,
            "tts_provider": tts_provider,
            "speech_model": speech_model,
            "transcription_provider": transcription_provider,
        }
    return settings_by_language


async def _load_twilio_conversationrelay_default_voice_settings(
    *,
    force_refresh: bool = False,
) -> tuple[dict[str, dict[str, str]], str, float]:
    now_ts = time.time()
    cached_settings = _conversationrelay_defaults_cache.get("settings")
    cached_source = str(_conversationrelay_defaults_cache.get("source") or "cache")
    cached_fetched_at = float(_conversationrelay_defaults_cache.get("fetched_at") or 0.0)
    if (
        not force_refresh
        and isinstance(cached_settings, dict)
        and cached_settings
        and (now_ts - cached_fetched_at) < _GEMINI_VOICE_CACHE_TTL_SECONDS
    ):
        return dict(cached_settings), cached_source, cached_fetched_at

    async with _voice_catalog_lock:
        now_ts = time.time()
        cached_settings = _conversationrelay_defaults_cache.get("settings")
        cached_source = str(_conversationrelay_defaults_cache.get("source") or "cache")
        cached_fetched_at = float(_conversationrelay_defaults_cache.get("fetched_at") or 0.0)
        if (
            not force_refresh
            and isinstance(cached_settings, dict)
            and cached_settings
            and (now_ts - cached_fetched_at) < _GEMINI_VOICE_CACHE_TTL_SECONDS
        ):
            return dict(cached_settings), cached_source, cached_fetched_at

        try:
            async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
                response = await client.get(_TWILIO_CONVERSATIONRELAY_VOICE_CONFIG_DOC_URL)
                response.raise_for_status()
                markdown_doc = response.text
            defaults = _extract_twilio_conversationrelay_default_voice_settings(markdown_doc)
            if not defaults:
                raise ValueError("No default ConversationRelay voice settings parsed from official source.")
            fetched_at = time.time()
            _conversationrelay_defaults_cache["settings"] = defaults
            _conversationrelay_defaults_cache["source"] = "twilio_conversationrelay_voice_config_live"
            _conversationrelay_defaults_cache["fetched_at"] = fetched_at
            return defaults, "twilio_conversationrelay_voice_config_live", fetched_at
        except Exception as exc:
            logger.warning(
                "Failed to refresh Twilio ConversationRelay default voice settings from official source: %s",
                exc,
            )
            if isinstance(cached_settings, dict) and cached_settings:
                return dict(cached_settings), "cache_stale", cached_fetched_at
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to load Twilio ConversationRelay default voice settings from official source.",
            ) from exc


async def _load_twilio_conversationrelay_voice_catalog(
    *,
    provider: str | None,
    language_code: str,
    force_refresh: bool = False,
) -> tuple[str, list[str], str, str, float]:
    normalized_provider = _normalize_twilio_tts_provider(provider) or "ElevenLabs"
    normalized_language = (language_code or settings.twilio_agent_language or "ja-JP").strip() or "ja-JP"
    cache_key = (normalized_provider, normalized_language)
    now_ts = time.time()
    cached = _voice_catalog_cache.get(cache_key)
    if (
        not force_refresh
        and isinstance(cached, dict)
        and cached.get("voices")
        and (now_ts - float(cached.get("fetched_at") or 0.0)) < _GEMINI_VOICE_CACHE_TTL_SECONDS
    ):
        return (
            normalized_provider,
            list(cached.get("voices") or []),
            str(cached.get("source") or "cache"),
            str(cached.get("default_voice") or ""),
            float(cached.get("fetched_at") or 0.0),
        )

    defaults_by_language, defaults_source, defaults_fetched_at = await _load_twilio_conversationrelay_default_voice_settings(
        force_refresh=force_refresh,
    )
    language_defaults = defaults_by_language.get(normalized_language) or {}

    if normalized_provider == "ElevenLabs":
        default_voice = str(language_defaults.get("voice_id") or "").strip()
        if str(language_defaults.get("tts_provider") or "").strip() != "ElevenLabs":
            default_voice = ""
        if not default_voice:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Official Twilio ConversationRelay defaults do not expose an ElevenLabs voice for this language.",
            )
        fetched_at = defaults_fetched_at
        voices = [default_voice]
        _voice_catalog_cache[cache_key] = {
            "voices": voices,
            "source": defaults_source,
            "default_voice": default_voice,
            "fetched_at": fetched_at,
        }
        return normalized_provider, voices, defaults_source, default_voice, fetched_at

    async with _voice_catalog_lock:
        now_ts = time.time()
        cached = _voice_catalog_cache.get(cache_key)
        if (
            not force_refresh
            and isinstance(cached, dict)
            and cached.get("voices")
            and (now_ts - float(cached.get("fetched_at") or 0.0)) < _GEMINI_VOICE_CACHE_TTL_SECONDS
        ):
            return (
                normalized_provider,
                list(cached.get("voices") or []),
                str(cached.get("source") or "cache"),
                str(cached.get("default_voice") or ""),
                float(cached.get("fetched_at") or 0.0),
            )

        try:
            async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
                response = await client.get(_TWILIO_TTS_DOC_URL)
                response.raise_for_status()
                markdown_doc = response.text
            voices = _extract_twilio_tts_voice_ids(
                markdown_doc,
                language_code=normalized_language,
                provider=normalized_provider,
            )
            if not voices:
                raise ValueError("No voice IDs parsed from official source.")
            default_voice = ""
            if str(language_defaults.get("tts_provider") or "").strip() == normalized_provider:
                default_voice = str(language_defaults.get("voice_id") or "").strip()
            if not default_voice and normalized_provider == "Google":
                default_voice = next(
                    (voice for voice in voices if voice.lower().endswith("-chirp3-hd-aoede")),
                    voices[0],
                )
            elif not default_voice:
                default_voice = voices[0]
            fetched_at = time.time()
            _voice_catalog_cache[cache_key] = {
                "voices": voices,
                "source": "twilio_tts_docs_live",
                "default_voice": default_voice,
                "fetched_at": fetched_at,
            }
            return normalized_provider, voices, "twilio_tts_docs_live", default_voice, fetched_at
        except Exception as exc:
            logger.warning(
                "Failed to refresh Twilio ConversationRelay %s voice list from official source: %s",
                normalized_provider,
                exc,
            )
            cached = _voice_catalog_cache.get(cache_key)
            if isinstance(cached, dict) and cached.get("voices"):
                return (
                    normalized_provider,
                    list(cached.get("voices") or []),
                    "cache_stale",
                    str(cached.get("default_voice") or ""),
                    float(cached.get("fetched_at") or 0.0),
                )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to load Twilio ConversationRelay voice options from official source.",
            ) from exc


async def _load_official_gemini_voices(*, force_refresh: bool = False) -> tuple[list[str], str, float]:
    _, voice_ids, source, _, fetched_at = await _load_twilio_conversationrelay_voice_catalog(
        provider="Google",
        language_code=(settings.twilio_agent_language or "ja-JP").strip() or "ja-JP",
        force_refresh=force_refresh,
    )
    voices = _normalize_gemini_voice_names(
        [
            voice_id.split("-Chirp3-HD-", 1)[1].strip()
            for voice_id in voice_ids
            if "-Chirp3-HD-" in voice_id
        ]
    )
    if not voices:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to load Twilio ConversationRelay voice options from official source.",
        )
    return voices, source, fetched_at
