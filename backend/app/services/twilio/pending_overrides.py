import asyncio
import time

from app.services.twilio.normalizers import (
    _normalize_e164_number,
    _normalize_prompt_code_token,
    _normalize_twilio_tts_provider,
    _normalize_twilio_voice_route,
    _normalize_voice_engine,
    _normalize_voice_name_token,
)

_PENDING_PROMPT_TTL_SECONDS = 180.0

_pending_prompt_lock = asyncio.Lock()
_pending_inbound_override_by_number: dict[
    str,
    tuple[str | None, str | None, str | None, str | None, str | None, float],
] = {}


async def _set_pending_inbound_override_for_number(
    *,
    number: str | None,
    prompt_code: str | None,
    voice_route: str | None,
    voice_engine: str | None,
    tts_provider: str | None,
    voice_name: str | None,
) -> bool:
    normalized_number = _normalize_e164_number(number)
    if not normalized_number:
        return False

    normalized_prompt = _normalize_prompt_code_token(prompt_code)
    normalized_route = _normalize_twilio_voice_route(voice_route)
    normalized_engine = None
    if (voice_engine or "").strip():
        resolved_engine = _normalize_voice_engine(voice_engine)
        if resolved_engine in {"twilio", "gemini"}:
            normalized_engine = resolved_engine
    normalized_tts_provider = _normalize_twilio_tts_provider(tts_provider)
    normalized_voice = _normalize_voice_name_token(voice_name)

    if not any([normalized_prompt, normalized_route, normalized_engine, normalized_tts_provider, normalized_voice]):
        return False

    expires_at = time.monotonic() + _PENDING_PROMPT_TTL_SECONDS
    async with _pending_prompt_lock:
        _pending_inbound_override_by_number[normalized_number] = (
            normalized_prompt,
            normalized_route,
            normalized_engine,
            normalized_tts_provider,
            normalized_voice,
            expires_at,
        )
    return True


async def _consume_pending_inbound_override_for_number(number: str | None) -> dict[str, str | None] | None:
    normalized_number = _normalize_e164_number(number)
    if not normalized_number:
        return None
    now_ts = time.monotonic()
    async with _pending_prompt_lock:
        expired_keys = [
            key
            for key, (_, _, _, _, _, expiry) in _pending_inbound_override_by_number.items()
            if expiry <= now_ts
        ]
        for key in expired_keys:
            _pending_inbound_override_by_number.pop(key, None)
        matched = _pending_inbound_override_by_number.pop(normalized_number, None)
    if not matched:
        return None
    prompt_code, voice_route, voice_engine, tts_provider, voice_name, expiry = matched
    if expiry <= now_ts:
        return None
    payload = {
        "prompt_code": prompt_code,
        "voice_engine": voice_engine,
        "tts_provider": tts_provider,
        "voice_name": voice_name,
    }
    if voice_route:
        payload["voice_route"] = voice_route
    return payload
