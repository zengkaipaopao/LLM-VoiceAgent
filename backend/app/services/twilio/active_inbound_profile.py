import asyncio

from app.services.twilio.normalizers import (
    _normalize_e164_number,
    _normalize_prompt_code_token,
    _normalize_twilio_voice_route,
    _normalize_voice_engine,
    _normalize_voice_name_token,
)

_active_inbound_profile_lock = asyncio.Lock()
_active_inbound_profile_by_number: dict[str, dict[str, str | None]] = {}


async def _set_active_inbound_profile_for_number(
    *,
    number: str | None,
    prompt_code: str | None,
    voice_route: str | None,
    voice_engine: str | None,
    voice_name: str | None,
) -> dict[str, str | None] | None:
    normalized_number = _normalize_e164_number(number)
    if not normalized_number:
        return None

    normalized_prompt = _normalize_prompt_code_token(prompt_code)
    normalized_route = _normalize_twilio_voice_route(voice_route)
    normalized_engine = None
    if (voice_engine or "").strip():
        resolved_engine = _normalize_voice_engine(voice_engine)
        if resolved_engine in {"twilio", "gemini"}:
            normalized_engine = resolved_engine
    normalized_voice = _normalize_voice_name_token(voice_name)

    if not any([normalized_prompt, normalized_route, normalized_engine, normalized_voice]):
        return None

    profile = {
        "prompt_code": normalized_prompt,
        "voice_route": normalized_route,
        "voice_engine": normalized_engine,
        "voice_name": normalized_voice,
    }
    async with _active_inbound_profile_lock:
        _active_inbound_profile_by_number[normalized_number] = profile
    return profile


async def _get_active_inbound_profile_for_number(number: str | None) -> dict[str, str | None] | None:
    normalized_number = _normalize_e164_number(number)
    if not normalized_number:
        return None
    async with _active_inbound_profile_lock:
        profile = _active_inbound_profile_by_number.get(normalized_number)
        if not profile:
            return None
        return dict(profile)
