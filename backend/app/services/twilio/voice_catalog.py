import asyncio
import logging
import re
import time

import httpx
from fastapi import HTTPException, status

from app.core.config import settings
from app.services.twilio.normalizers import _normalize_gemini_voice_names, _normalize_twilio_voice_ids

logger = logging.getLogger(__name__)

_TWILIO_TTS_DOC_URL = "https://www.twilio.com/docs/voice/twiml/say/text-speech.md"
_GEMINI_VOICE_CACHE_TTL_SECONDS = 1800

_voice_catalog_lock = asyncio.Lock()
_voice_catalog_cache: dict[str, object] = {
    "voices": [],
    "source": "uninitialized",
    "fetched_at": 0.0,
}


def _normalize_tts_doc_provider(value: str | None) -> str | None:
    token = (value or "").strip().lower()
    if not token:
        return None
    if token in {"google", "gemini"}:
        return "Google"
    if token in {"amazon", "amazonpolly", "amazon_polly"}:
        return "Amazon"
    if token == "elevenlabs":
        return "ElevenLabs"
    return None


def _extract_twilio_tts_voice_ids(
    markdown_doc: str,
    *,
    language_code: str,
    provider: str,
) -> list[str]:
    normalized_provider = _normalize_tts_doc_provider(provider)
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


async def _load_official_gemini_voices(*, force_refresh: bool = False) -> tuple[list[str], str, float]:
    now_ts = time.time()
    cached_voices = _voice_catalog_cache.get("voices")
    cached_source = str(_voice_catalog_cache.get("source") or "cache")
    cached_fetched_at = float(_voice_catalog_cache.get("fetched_at") or 0.0)
    if (
        not force_refresh
        and isinstance(cached_voices, list)
        and cached_voices
        and (now_ts - cached_fetched_at) < _GEMINI_VOICE_CACHE_TTL_SECONDS
    ):
        return list(cached_voices), cached_source, cached_fetched_at

    async with _voice_catalog_lock:
        now_ts = time.time()
        cached_voices = _voice_catalog_cache.get("voices")
        cached_source = str(_voice_catalog_cache.get("source") or "cache")
        cached_fetched_at = float(_voice_catalog_cache.get("fetched_at") or 0.0)
        if (
            not force_refresh
            and isinstance(cached_voices, list)
            and cached_voices
            and (now_ts - cached_fetched_at) < _GEMINI_VOICE_CACHE_TTL_SECONDS
        ):
            return list(cached_voices), cached_source, cached_fetched_at

        try:
            async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
                response = await client.get(_TWILIO_TTS_DOC_URL)
                response.raise_for_status()
                markdown_doc = response.text
            voices = _extract_twilio_google_voice_names(
                markdown_doc,
                language_code=(settings.twilio_agent_language or "ja-JP").strip() or "ja-JP",
            )
            if not voices:
                raise ValueError("No Google Chirp3-HD voices parsed from official source.")
            fetched_at = time.time()
            _voice_catalog_cache["voices"] = voices
            _voice_catalog_cache["source"] = "twilio_tts_docs_live"
            _voice_catalog_cache["fetched_at"] = fetched_at
            return voices, "twilio_tts_docs_live", fetched_at
        except Exception as exc:
            logger.warning("Failed to refresh Gemini voice list from official source: %s", exc)
            if isinstance(cached_voices, list) and cached_voices:
                return list(cached_voices), "cache_stale", cached_fetched_at
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to load Gemini voice options from official source.",
            ) from exc
