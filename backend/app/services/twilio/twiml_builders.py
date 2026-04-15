import html
import logging
from urllib.parse import urlunsplit

from fastapi import Request, WebSocket, status
from twilio.request_validator import RequestValidator

from app.core.config import settings
from app.services.twilio.normalizers import _normalize_twilio_tts_provider

logger = logging.getLogger(__name__)


def _to_websocket_url(url: str) -> str:
    if url.startswith("https://"):
        return "wss://" + url[len("https://") :]
    if url.startswith("http://"):
        return "ws://" + url[len("http://") :]
    return url


def _build_twilio_media_stream_url(
    *,
    request: Request,
) -> str:
    return _to_websocket_url(str(request.url_for("twilio_voice_media_stream")))


def _build_twilio_media_stream_twiml(
    *,
    request: Request,
    prompt_code: str | None,
    from_number: str | None,
    to_number: str | None,
    voice_name: str | None,
    opening_text: str | None = None,
) -> str:
    stream_url = _build_twilio_media_stream_url(request=request)
    parameters: list[tuple[str, str]] = []
    if (prompt_code or "").strip():
        parameters.append(("prompt_code", prompt_code.strip()))
    if (from_number or "").strip():
        parameters.append(("from", from_number.strip()))
    if (to_number or "").strip():
        parameters.append(("to", to_number.strip()))
    if (voice_name or "").strip():
        parameters.append(("voice_name", voice_name.strip()))

    parameter_xml = "".join(
        f'<Parameter name="{html.escape(name, quote=True)}" value="{html.escape(value, quote=True)}" />'
        for name, value in parameters
    )
    opening_xml = ""
    opening = (opening_text or "").strip()
    if opening:
        opening_xml = f'<Say language="{html.escape(settings.twilio_agent_language, quote=True)}">{html.escape(opening)}</Say>'
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f"<Response>{opening_xml}<Connect>"
        f'<Stream url="{html.escape(stream_url, quote=True)}">{parameter_xml}</Stream>'
        "</Connect></Response>"
    )


def _build_public_websocket_url(websocket: WebSocket) -> str:
    forwarded_proto = (websocket.headers.get("x-forwarded-proto") or "").split(",", 1)[0].strip()
    forwarded_host = (websocket.headers.get("x-forwarded-host") or "").split(",", 1)[0].strip()

    scheme = forwarded_proto or websocket.url.scheme
    netloc = forwarded_host or websocket.headers.get("host") or websocket.url.netloc
    return _to_websocket_url(urlunsplit((scheme, netloc, websocket.url.path, websocket.url.query, "")))


def _candidate_websocket_signature_urls(websocket: WebSocket) -> list[str]:
    public_url = _build_public_websocket_url(websocket)
    candidates: list[str] = []

    def _append(value: str) -> None:
        token = value.strip()
        if token and token not in candidates:
            candidates.append(token)

    _append(public_url)
    if not public_url.endswith("/"):
        _append(public_url + "/")

    if public_url.startswith("wss://"):
        https_url = "https://" + public_url[len("wss://") :]
        _append(https_url)
        _append(https_url + "/" if not https_url.endswith("/") else https_url)
    elif public_url.startswith("ws://"):
        http_url = "http://" + public_url[len("ws://") :]
        _append(http_url)
        _append(http_url + "/" if not http_url.endswith("/") else http_url)

    return candidates


async def _verify_websocket_or_close(websocket: WebSocket) -> bool:
    if not settings.twilio_validate_webhooks:
        return True

    auth_token = (settings.twilio_auth_token or "").strip()
    if settings.environment == "local" and not auth_token:
        return True
    if not auth_token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return False

    signature = (websocket.headers.get("x-twilio-signature") or "").strip()
    if not signature:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return False

    validator = RequestValidator(auth_token)
    candidate_urls = _candidate_websocket_signature_urls(websocket)
    if not any(validator.validate(candidate_url, {}, signature) for candidate_url in candidate_urls):
        logger.warning(
            "Twilio websocket signature verification failed. candidates=%s",
            candidate_urls,
        )
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return False

    return True


def _build_twilio_conversation_relay_url(
    *,
    request: Request,
) -> str:
    return _to_websocket_url(str(request.url_for("twilio_voice_conversation_relay")))


def _build_twilio_conversation_relay_twiml(
    *,
    request: Request,
    prompt_code: str | None,
    from_number: str | None,
    to_number: str | None,
    tts_provider: str | None,
    voice_name: str | None,
    opening_text: str | None = None,
) -> str:
    relay_url = _build_twilio_conversation_relay_url(request=request)
    action_url = str(request.url_for("voice_status_callback"))
    language_code = (settings.twilio_agent_language or "ja-JP").strip() or "ja-JP"
    normalized_tts_provider = _normalize_twilio_tts_provider(tts_provider) or "ElevenLabs"
    conversation_relay_voice = (voice_name or "").strip()
    parameters: list[tuple[str, str]] = []
    if (prompt_code or "").strip():
        parameters.append(("prompt_code", prompt_code.strip()))
    if (from_number or "").strip():
        parameters.append(("from", from_number.strip()))
    if (to_number or "").strip():
        parameters.append(("to", to_number.strip()))
    if normalized_tts_provider:
        parameters.append(("tts_provider", normalized_tts_provider))
    if (voice_name or "").strip():
        parameters.append(("voice_name", voice_name.strip()))

    parameter_xml = "".join(
        f'<Parameter name="{html.escape(name, quote=True)}" value="{html.escape(value, quote=True)}" />'
        for name, value in parameters
    )
    welcome_greeting = (opening_text or "").strip()
    welcome_attribute = (
        f' welcomeGreeting="{html.escape(welcome_greeting, quote=True)}"' if welcome_greeting else ""
    )
    voice_attribute = (
        f' voice="{html.escape(conversation_relay_voice, quote=True)}"'
        if conversation_relay_voice
        else ""
    )
    debug_attribute = ""
    if settings.debug or (settings.environment or "").strip().lower() == "local":
        debug_attribute = ' debug="debugging speaker-events tokens-played"'
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<Response><Connect action="{html.escape(action_url, quote=True)}">'
        f'<ConversationRelay url="{html.escape(relay_url, quote=True)}"'
        f'{welcome_attribute}'
        ' welcomeGreetingInterruptible="none"'
        f' language="{html.escape(language_code, quote=True)}"'
        f' ttsLanguage="{html.escape(language_code, quote=True)}"'
        f' transcriptionLanguage="{html.escape(language_code, quote=True)}"'
        f' ttsProvider="{html.escape(normalized_tts_provider, quote=True)}"'
        ' transcriptionProvider="Google"'
        ' speechModel="telephony"'
        ' interruptible="speech"'
        ' interruptSensitivity="high"'
        f"{debug_attribute}"
        f"{voice_attribute}>"
        f"{parameter_xml}</ConversationRelay>"
        "</Connect><Hangup/></Response>"
    )


def _extract_stream_custom_parameters(payload: dict[str, object] | None) -> dict[str, str]:
    start = payload.get("start") if isinstance(payload, dict) else None
    if not isinstance(start, dict):
        return {}
    custom_parameters = start.get("customParameters")
    if not isinstance(custom_parameters, dict):
        return {}
    normalized: dict[str, str] = {}
    for key, value in custom_parameters.items():
        key_text = str(key or "").strip()
        value_text = str(value or "").strip()
        if key_text and value_text:
            normalized[key_text] = value_text
    return normalized
