import html
import logging
from urllib.parse import urlunsplit

from fastapi import Request, WebSocket, status
from twilio.request_validator import RequestValidator

from app.core.config import settings

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
    status_callback_url = str(request.url_for("twilio_voice_stream_status_callback"))
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
        f'<Stream url="{html.escape(stream_url, quote=True)}"'
        f' statusCallback="{html.escape(status_callback_url, quote=True)}"'
        ' statusCallbackMethod="POST">'
        f"{parameter_xml}</Stream>"
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
