import re

from app.core.config import settings

_VOICE_ENGINE_ALIASES = {
    "twilio": "twilio",
    "twilio_tts": "twilio",
    "legacy": "twilio",
    "gemini": "gemini",
    "google": "gemini",
    "gemini_live": "gemini",
}
_TWILIO_VOICE_ROUTE_ALIASES = {
    "gather": "gather",
    "gather_agent": "gather",
    # Backward-compatibility aliases for removed ConversationRelay routes.
    "conversationrelay": "media_stream_live",
    "conversation_relay": "media_stream_live",
    "conversationrelay_generate": "media_stream_live",
    "media_stream": "media_stream_live",
    "media_stream_live": "media_stream_live",
    "mediastream": "media_stream_live",
    "official_demo": "official_demo_live",
    "official_demo_live": "official_demo_live",
    "officialdemo": "official_demo_live",
    "official_baseline": "official_demo_live",
    "baseline_demo": "official_demo_live",
    "official_ca": "official_conversational_agents",
    "official_ca_live": "official_conversational_agents",
    "official_conversational_agents": "official_conversational_agents",
    "conversational_agents": "official_conversational_agents",
    "cx_agent_studio": "official_conversational_agents",
    "ces_adapter": "official_conversational_agents",
    "stream": "media_stream_live",
}
_E164_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")
_PROMPT_CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_VOICE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_ELEVENLABS_VOICE_ID_PATTERN = re.compile(
    r"^[A-Za-z0-9]{20}(?:-[A-Za-z0-9_.]+)?(?:-[0-9.]+(?:_[0-9.]+){2})?$"
)
_KNOWN_GEMINI_LIVE_VOICE_NAMES = (
    "Zephyr",
    "Puck",
    "Charon",
    "Kore",
    "Fenrir",
    "Leda",
    "Orus",
    "Aoede",
    "Callirrhoe",
    "Autonoe",
    "Enceladus",
    "Iapetus",
    "Umbriel",
    "Algieba",
    "Despina",
    "Erinome",
    "Algenib",
    "Rasalgethi",
    "Laomedeia",
    "Achernar",
    "Alnilam",
    "Schedar",
    "Gacrux",
    "Pulcherrima",
    "Achird",
    "Zubenelgenubi",
    "Vindemiatrix",
    "Sadachbia",
    "Sadaltager",
    "Sulafat",
)


def _normalize_e164_number(value: str | None) -> str | None:
    normalized = re.sub(r"[\s\u3000\-()]", "", (value or "").strip())
    if not normalized:
        return None
    return normalized if _E164_PATTERN.fullmatch(normalized) else None


def _normalize_prompt_code_token(value: str | None) -> str | None:
    token = (value or "").strip()
    if not token:
        return None
    return token if _PROMPT_CODE_PATTERN.fullmatch(token) else None


def _normalize_voice_engine(value: str | None) -> str:
    token = (value or "").strip().lower()
    if not token:
        token = (settings.twilio_incoming_voice_engine or "twilio").strip().lower()
    return _VOICE_ENGINE_ALIASES.get(token, token)


def _normalize_twilio_voice_route(value: str | None) -> str | None:
    token = (value or "").strip().lower()
    if not token:
        return None
    return _TWILIO_VOICE_ROUTE_ALIASES.get(token)


def _resolve_twilio_inbound_voice_route(
    *,
    voice_route: str | None,
    voice_engine: str | None,
) -> str | None:
    explicit_route = (voice_route or "").strip()
    if explicit_route:
        return _normalize_twilio_voice_route(explicit_route)

    engine = _normalize_voice_engine(voice_engine)
    if engine == "twilio":
        return "gather"
    if engine == "gemini":
        return "media_stream_live"
    return None


def _normalize_voice_name_token(value: str | None) -> str | None:
    token = (value or "").strip()
    if not token:
        return None
    return token if _VOICE_NAME_PATTERN.fullmatch(token) else None


def _normalize_gemini_live_voice_name(
    value: str | None,
    *,
    voice_provider: str | None = None,
    default_voice: str | None = None,
) -> str:
    fallback = (
        _match_case_insensitive_voice(default_voice or "", list(_KNOWN_GEMINI_LIVE_VOICE_NAMES))
        or "Aoede"
    )
    provider_token = (voice_provider or "").strip().lower()
    if provider_token and provider_token not in {"google", "gemini"}:
        return fallback

    token = (value or "").strip()
    if not token:
        return fallback
    if token.startswith("Google."):
        token = token.replace("Google.", "", 1).strip()
    if token.startswith("Amazon.") or token.startswith("ElevenLabs."):
        return fallback
    if "-Chirp3-HD-" in token:
        token = token.split("-Chirp3-HD-", 1)[1].strip() or token
    if _ELEVENLABS_VOICE_ID_PATTERN.fullmatch(token):
        return fallback

    matched = _match_case_insensitive_voice(token, list(_KNOWN_GEMINI_LIVE_VOICE_NAMES))
    return matched or fallback


def _normalize_gemini_voice_names(candidates: list[str]) -> list[str]:
    ordered_unique: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        name = item.strip()
        if not name:
            continue
        lowered = name.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        ordered_unique.append(name)
    return ordered_unique


def _normalize_twilio_voice_ids(candidates: list[str]) -> list[str]:
    ordered_unique: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        voice_id = item.strip()
        if not voice_id:
            continue
        lowered = voice_id.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        ordered_unique.append(voice_id)
    return ordered_unique


def _match_case_insensitive_voice(candidate: str, official_voices: list[str]) -> str | None:
    lookup = {voice.strip().lower(): voice for voice in official_voices if voice.strip()}
    return lookup.get(candidate.strip().lower())
