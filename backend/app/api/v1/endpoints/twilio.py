import asyncio
import audioop
import base64
from collections import deque
import html
import json
import logging
import re
import time
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, WebSocket, WebSocketDisconnect, status
from fastapi.responses import Response
from google import genai
from google.genai import types
import httpx
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_api_key
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.schemas.base import ResponseBase
from app.schemas.twilio import TwilioTokenResponse
from app.services.live_gateway import provider_available, resolve_live_provider
from app.services.prompt_service import PromptService
from app.services.twilio_webcall_service import TwilioWebCallService
from app.services.twilio_voice_agent_service import twilio_voice_agent_service
from app.utils.datetime_utils import now_tokyo_naive
from app.utils.twilio_security import verify_twilio_webhook_request

router = APIRouter()
logger = logging.getLogger(__name__)
_VOICE_ENGINE_ALIASES = {
    "twilio": "twilio",
    "twilio_tts": "twilio",
    "legacy": "twilio",
    "gemini": "gemini",
    "google": "gemini",
    "gemini_live": "gemini",
}
_AUDIO_RATE_PATTERN = re.compile(r"rate=(\d+)")
_E164_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")
_PROMPT_CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_VOICE_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
_TWILIO_FRAME_BYTES = 160  # 20ms at 8kHz G.711 mu-law
_GEMINI_OPENING_HINT = (
    "通話を開始してください。まずはシステム指示に従って、"
    "冒頭挨拶のみを1文で話してください。"
)
_VAD_RMS_THRESHOLD = 55
_VAD_SILENCE_END_MS = 1100
_VAD_NOISE_MULTIPLIER = 1.9
_VAD_MAX_TURN_MS = 6000
_VAD_ADAPTIVE_THRESHOLD_MAX = 420
_VAD_ADAPTIVE_SMOOTHING = 0.2
_VAD_START_CONSEC_FRAMES = 3
_ASSISTANT_OUTPUT_LOCK_TIMEOUT_MS = 7000
_OPENING_SUPPRESS_MS = 3500
_VAD_PRE_ROLL_FRAMES = 15  # 15 * 20ms = 300ms
_MANUAL_INJECT_MEDIA_SUPPRESS_MS = 8000
_TRACE_MAX_CALLS = 200
_TRACE_MAX_EVENTS_PER_CALL = 300
_GEMINI_VOICE_DOC_URL = "https://ai.google.dev/gemini-api/docs/speech-generation"
_GEMINI_VOICE_NAME_PATTERN = re.compile(r"<td><b>([A-Za-z][A-Za-z0-9]+)</b>\s*--\s*<em>", flags=re.I)
_GEMINI_VOICE_CACHE_TTL_SECONDS = 1800
_trace_lock = asyncio.Lock()
_trace_events: dict[str, deque[dict[str, object]]] = {}
_trace_seq: dict[str, int] = {}
_trace_call_order: deque[str] = deque()
_voice_catalog_lock = asyncio.Lock()
_voice_catalog_cache: dict[str, object] = {
    "voices": [],
    "source": "uninitialized",
    "fetched_at": 0.0,
}
_manual_audio_lock = asyncio.Lock()
_manual_audio_queues: dict[str, deque[bytes]] = {}
_active_stream_calls: set[str] = set()
_pending_prompt_lock = asyncio.Lock()
_pending_inbound_override_by_number: dict[str, tuple[str | None, str | None, str | None, float]] = {}
_PENDING_PROMPT_TTL_SECONDS = 180.0


class TwilioManualAudioInjectRequest(BaseModel):
    call_sid: str = Field(min_length=1)
    audio_base64: str = Field(min_length=1, description="PCM16 mono audio (16kHz) base64 payload.")
    mime_type: str = Field(default="audio/pcm;rate=16000")


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


async def _append_call_trace(
    call_sid: str | None,
    *,
    event_type: str,
    text: str | None = None,
    final: bool | None = None,
    level: str = "info",
) -> None:
    sid = (call_sid or "").strip()
    if not sid:
        return

    snippet = (text or "").strip()
    async with _trace_lock:
        if sid not in _trace_events:
            _trace_events[sid] = deque(maxlen=_TRACE_MAX_EVENTS_PER_CALL)
            _trace_call_order.append(sid)
            while len(_trace_call_order) > _TRACE_MAX_CALLS:
                stale = _trace_call_order.popleft()
                _trace_events.pop(stale, None)
                _trace_seq.pop(stale, None)

        next_seq = _trace_seq.get(sid, 0) + 1
        _trace_seq[sid] = next_seq
        payload: dict[str, object] = {
            "seq": next_seq,
            "ts": int(time.time() * 1000),
            "type": event_type,
            "level": level,
        }
        if snippet:
            payload["text"] = snippet
        if final is not None:
            payload["final"] = final
        _trace_events[sid].append(payload)


async def _read_call_trace(call_sid: str, since: int) -> tuple[list[dict[str, object]], int]:
    sid = (call_sid or "").strip()
    if not sid:
        return [], 0

    async with _trace_lock:
        events = list(_trace_events.get(sid, []))
        last_seq = _trace_seq.get(sid, 0)

    if since > 0:
        events = [item for item in events if int(item.get("seq", 0)) > since]
    return events, last_seq


async def _read_latest_trace_call_sid() -> str | None:
    async with _trace_lock:
        if not _trace_call_order:
            return None
        return _trace_call_order[-1]


async def _mark_stream_active(call_sid: str | None) -> None:
    sid = (call_sid or "").strip()
    if not sid:
        return
    async with _manual_audio_lock:
        _active_stream_calls.add(sid)
        _manual_audio_queues.setdefault(sid, deque())


async def _mark_stream_inactive(call_sid: str | None) -> None:
    sid = (call_sid or "").strip()
    if not sid:
        return
    async with _manual_audio_lock:
        _active_stream_calls.discard(sid)
        _manual_audio_queues.pop(sid, None)


async def _is_stream_active(call_sid: str | None) -> bool:
    sid = (call_sid or "").strip()
    if not sid:
        return False
    async with _manual_audio_lock:
        return sid in _active_stream_calls


async def _enqueue_manual_audio(call_sid: str, audio_bytes: bytes) -> int:
    sid = call_sid.strip()
    async with _manual_audio_lock:
        queue = _manual_audio_queues.setdefault(sid, deque())
        queue.append(audio_bytes)
        return len(queue)


async def _drain_manual_audio(call_sid: str | None) -> list[bytes]:
    sid = (call_sid or "").strip()
    if not sid:
        return []
    async with _manual_audio_lock:
        queue = _manual_audio_queues.get(sid)
        if not queue:
            return []
        items = list(queue)
        queue.clear()
        return items


def _pcm16_audio_stats(audio_bytes: bytes, *, sample_rate: int = 16000) -> dict[str, int]:
    aligned = audio_bytes if len(audio_bytes) % 2 == 0 else audio_bytes[:-1]
    if not aligned:
        return {"bytes": 0, "samples": 0, "duration_ms": 0, "rms": 0, "peak": 0}
    samples = len(aligned) // 2
    duration_ms = int((samples * 1000) / max(sample_rate, 1))
    try:
        rms = int(audioop.rms(aligned, 2))
    except Exception:
        rms = 0
    try:
        peak = int(audioop.max(aligned, 2))
    except Exception:
        peak = 0
    return {
        "bytes": len(aligned),
        "samples": samples,
        "duration_ms": duration_ms,
        "rms": rms,
        "peak": peak,
    }


async def _list_active_stream_calls() -> list[str]:
    async with _manual_audio_lock:
        return sorted(_active_stream_calls)


def _normalize_voice_name_token(value: str | None) -> str | None:
    token = (value or "").strip()
    if not token:
        return None
    return token if _VOICE_NAME_PATTERN.fullmatch(token) else None


async def _set_pending_inbound_override_for_number(
    *,
    number: str | None,
    prompt_code: str | None,
    voice_engine: str | None,
    voice_name: str | None,
) -> bool:
    normalized_number = _normalize_e164_number(number)
    if not normalized_number:
        return False

    normalized_prompt = _normalize_prompt_code_token(prompt_code)
    normalized_engine = None
    if (voice_engine or "").strip():
        resolved_engine = _normalize_voice_engine(voice_engine)
        if resolved_engine in {"twilio", "gemini"}:
            normalized_engine = resolved_engine
    normalized_voice = _normalize_voice_name_token(voice_name)

    if not any([normalized_prompt, normalized_engine, normalized_voice]):
        return False

    expires_at = time.monotonic() + _PENDING_PROMPT_TTL_SECONDS
    async with _pending_prompt_lock:
        _pending_inbound_override_by_number[normalized_number] = (
            normalized_prompt,
            normalized_engine,
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
            key for key, (_, _, _, expiry) in _pending_inbound_override_by_number.items() if expiry <= now_ts
        ]
        for key in expired_keys:
            _pending_inbound_override_by_number.pop(key, None)
        matched = _pending_inbound_override_by_number.pop(normalized_number, None)
    if not matched:
        return None
    prompt_code, voice_engine, voice_name, expiry = matched
    if expiry <= now_ts:
        return None
    return {
        "prompt_code": prompt_code,
        "voice_engine": voice_engine,
        "voice_name": voice_name,
    }


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
                response = await client.get(_GEMINI_VOICE_DOC_URL)
                response.raise_for_status()
                html_doc = response.text
            raw_voices = _GEMINI_VOICE_NAME_PATTERN.findall(html_doc)
            voices = _normalize_gemini_voice_names(raw_voices)
            if not voices:
                raise ValueError("No voice names parsed from official source.")
            fetched_at = time.time()
            _voice_catalog_cache["voices"] = voices
            _voice_catalog_cache["source"] = "google_ai_docs_live"
            _voice_catalog_cache["fetched_at"] = fetched_at
            return voices, "google_ai_docs_live", fetched_at
        except Exception as exc:
            logger.warning("Failed to refresh Gemini voice list from official source: %s", exc)
            if isinstance(cached_voices, list) and cached_voices:
                return list(cached_voices), "cache_stale", cached_fetched_at
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to load Gemini voice options from official source.",
            ) from exc


def _resolve_gemini_live_model(candidate_model: str | None) -> str:
    selected = (candidate_model or "").strip()
    if selected and "live" in selected.lower():
        return selected
    fallback = (settings.default_live_model or "").strip()
    if fallback:
        return fallback
    return "gemini-3.1-flash-live-preview"


def _use_manual_vad_control() -> bool:
    mode = (settings.twilio_gemini_activity_mode or "auto").strip().lower()
    return mode in {"manual", "manual_vad", "explicit"}


def _extract_audio_rate(mime_type: str | None, default: int = 24000) -> int:
    text = (mime_type or "").strip().lower()
    if not text:
        return default
    matched = _AUDIO_RATE_PATTERN.search(text)
    if not matched:
        return default
    try:
        return int(matched.group(1))
    except ValueError:
        return default


def _build_gemini_opening_hint(system_instruction: str | None) -> str:
    text = (system_instruction or "").strip()
    if text:
        # Prefer explicit "first utterance" quote from template instructions.
        patterns = [
            r"最初のアシスタント発話.*?「([^」]{8,200})」",
            r"会話開始.*?「([^」]{8,200})」",
            r"必ず次の一文.*?「([^」]{8,200})」",
        ]
        for pattern in patterns:
            matched = re.search(pattern, text, flags=re.S)
            if matched:
                first_sentence = matched.group(1).strip()
                if first_sentence:
                    return (
                        "通話を開始してください。最初の発話は次の一文をそのまま話してください。"
                        f"「{first_sentence}」"
                    )
    return _GEMINI_OPENING_HINT


def _chunk_bytes(buffer: bytes, chunk_size: int) -> list[bytes]:
    if not buffer or chunk_size <= 0:
        return []
    return [buffer[index : index + chunk_size] for index in range(0, len(buffer), chunk_size)]


def _to_websocket_url(url: str) -> str:
    if url.startswith("https://"):
        return "wss://" + url[len("https://") :]
    if url.startswith("http://"):
        return "ws://" + url[len("http://") :]
    return url


def _build_twilio_media_stream_url(
    *,
    request: Request,
    prompt_code: str | None,
    voice_name: str | None,
) -> str:
    base_url = _to_websocket_url(str(request.url_for("twilio_voice_media_stream")))
    query_params: dict[str, str] = {}
    code = (prompt_code or "").strip()
    if code:
        query_params["prompt_code"] = code
    voice = (voice_name or "").strip()
    if voice:
        query_params["voice_name"] = voice
    if not query_params:
        return base_url
    return f"{base_url}?{urlencode(query_params)}"


async def _resolve_prompt_runtime(
    *,
    db: AsyncSession,
    prompt_code: str | None,
) -> dict[str, str | None]:
    code = (prompt_code or "").strip()
    effective_code = (
        code
        or (settings.twilio_default_prompt_code or "").strip()
        or "general_appointment"
    )

    prompt_service = PromptService(db)
    template = await prompt_service.get_template(effective_code)
    fallback_code = "general_appointment"
    if not template and effective_code != fallback_code:
        template = await prompt_service.get_template(fallback_code)
    if not template:
        fallback_instruction = (
            "あなたは日本語のコールセンター受付AIです。"
            "丁寧に自然な会話を行い、推測せず不足情報は確認質問してください。"
            "最初の発話は必ず次の一文で開始してください。"
            "「いつもお世話になっております。光洲産業の自動受付AIです。"
            "本日はどのようなご用件でしょうか。」"
        )
        return {
            "prompt_code": effective_code,
            "system_instruction": fallback_instruction,
            "llm_provider": None,
            "llm_model": None,
            "voice_name": None,
            "notice": f"Prompt template '{effective_code}' not found or inactive. Applied fallback runtime instruction.",
        }

    rendered_prompt = prompt_service.render_prompt(
        template,
        {"current_time": now_tokyo_naive().isoformat()},
    )
    return {
        "prompt_code": template.code,
        "system_instruction": rendered_prompt,
        "llm_provider": (template.llm_provider or "").strip() or None,
        "llm_model": (template.llm_model or "").strip() or None,
        "voice_name": (template.voice_id or "").strip() or None,
        "notice": f"Loaded prompt template: {template.name} ({template.code})",
    }


def _build_gemini_live_config(
    *,
    system_instruction: str | None,
    voice_name: str | None,
    manual_vad: bool,
) -> types.LiveConnectConfig:
    payload: dict[str, object] = {
        "response_modalities": ["AUDIO"],
        "input_audio_transcription": {},
        "output_audio_transcription": {},
    }
    if voice_name:
        payload["speech_config"] = {
            "voice_config": {
                "prebuilt_voice_config": {
                    "voice_name": voice_name,
                }
            }
        }
    if system_instruction:
        payload["system_instruction"] = system_instruction

    payload["realtime_input_config"] = types.RealtimeInputConfig(
        automatic_activity_detection=types.AutomaticActivityDetection(
            disabled=manual_vad,
        ),
    )
    return types.LiveConnectConfig(**payload)


async def _verify_webhook_or_raise(request: Request) -> None:
    if not settings.twilio_validate_webhooks:
        return

    # Keep local DX intact when Twilio auth token is not configured.
    auth_token = (settings.twilio_auth_token or "").strip()
    if settings.environment == "local" and not auth_token:
        return
    if not auth_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Twilio webhook verification is not configured.",
        )

    form = await request.form()
    form_payload: dict[str, object] = {}
    for key in form.keys():
        values = form.getlist(key)
        if not values:
            form_payload[key] = ""
            continue
        form_payload[key] = values if len(values) > 1 else values[0]

    is_valid, reason = verify_twilio_webhook_request(
        request=request,
        auth_token=auth_token,
        form_data=form_payload,
        tolerance_seconds=settings.twilio_webhook_tolerance_seconds,
    )
    if is_valid:
        return

    logger.warning("Twilio webhook verification failed: %s", reason)
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid webhook signature.",
    )


@router.get("/token", response_model=ResponseBase[TwilioTokenResponse])
async def create_voice_sdk_token(
    _auth: None = Depends(require_api_key),
    identity: str = Query("webcall-tester", min_length=1, max_length=128),
    ttl_seconds: int = Query(3600, ge=60, le=86_400),
):
    service = TwilioWebCallService()
    token, normalized_identity, expires_in = service.create_voice_access_token(identity, ttl_seconds)
    return ResponseBase(
        success=True,
        data=TwilioTokenResponse(
            token=token,
            identity=normalized_identity,
            expires_in=expires_in,
            twiml_app_sid=settings.twilio_twiml_app_sid,
        ),
    )


@router.get("/voice/voices", response_model=ResponseBase[dict])
async def list_gemini_prebuilt_voices(
    force_refresh: bool = Query(default=False, description="Force refresh from official source."),
):
    """
    Gemini voice options loaded from official Google source at runtime.
    """
    voices, source, fetched_at = await _load_official_gemini_voices(force_refresh=force_refresh)
    return ResponseBase(
        success=True,
        data={
            "provider": "gemini",
            "source": source,
            "fetched_at": int(fetched_at),
            "voices": voices,
            "default_voice": "Aoede",
        },
    )


@router.post("/voice/twiml")
async def twiml_app_voice_webhook(
    request: Request,
    To: Optional[str] = Form(None),  # noqa: N803 (Twilio form field casing)
    From: Optional[str] = Form(None),  # noqa: N803
    CallSid: Optional[str] = Form(None),  # noqa: N803
    prompt_code: Optional[str] = Form(None),
    voice_engine: Optional[str] = Form(None),
    voice_name: Optional[str] = Form(None),
):
    await _verify_webhook_or_raise(request)
    service = TwilioWebCallService()
    queued_override = await _set_pending_inbound_override_for_number(
        number=To,
        prompt_code=prompt_code,
        voice_engine=voice_engine,
        voice_name=voice_name,
    )
    if queued_override:
        logger.info(
            (
                "Queued pending inbound override for outbound->inbound bridge. "
                "to=%s prompt_code=%s voice_engine=%s voice_name=%s"
            ),
            _normalize_e164_number(To),
            _normalize_prompt_code_token(prompt_code),
            _normalize_voice_engine(voice_engine),
            _normalize_voice_name_token(voice_name),
        )
    xml = service.build_outbound_twiml(To or "")
    logger.info(
        (
            "Twilio TwiML app webhook called. "
            "CallSid=%s From=%s To=%s prompt_code=%s voice_engine=%s voice_name=%s"
        ),
        CallSid,
        From,
        To,
        prompt_code,
        voice_engine,
        voice_name,
    )
    return Response(content=xml, media_type="application/xml")


@router.post("/voice/incoming")
async def incoming_voice_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    identity: str = Query("webcall-tester", min_length=1, max_length=128),
    prompt_code: Optional[str] = Query(None),
    mode: Optional[str] = Query(None),
    voice_engine: Optional[str] = Query(
        default=None,
        description="Inbound AI voice engine: twilio or gemini.",
    ),
    voice_name: Optional[str] = Query(
        default=None,
        description="Optional Gemini prebuilt voice name override (e.g. Aoede).",
    ),
    To: Optional[str] = Form(None),  # noqa: N803
    From: Optional[str] = Form(None),  # noqa: N803
    CallSid: Optional[str] = Form(None),  # noqa: N803
):
    await _verify_webhook_or_raise(request)
    service = TwilioWebCallService()
    pending_override = await _consume_pending_inbound_override_for_number(To)
    pending_prompt = pending_override.get("prompt_code") if pending_override else None
    pending_engine = pending_override.get("voice_engine") if pending_override else None
    pending_voice_name = pending_override.get("voice_name") if pending_override else None
    effective_prompt = prompt_code or pending_prompt
    resolved_prompt_code = service.resolve_incoming_prompt_code(prompt_code=effective_prompt, to_number=To)
    mode_value = ((mode or settings.twilio_incoming_default_mode or "agent").strip().lower())
    effective_engine = voice_engine or pending_engine
    engine_value = _normalize_voice_engine(effective_engine)
    effective_voice_name = voice_name or pending_voice_name
    if engine_value not in {"twilio", "gemini"}:
        logger.warning(
            "Twilio inbound voice engine invalid. value=%s call_sid=%s to=%s",
            engine_value,
            CallSid,
            To,
        )
        xml = twilio_voice_agent_service.build_hangup_twiml(
            say_text="音声エンジン設定が不正です。設定を確認してください。",
            language=settings.twilio_agent_language,
        )
        return Response(content=xml, media_type="application/xml")

    if mode_value == "agent":
        if engine_value == "gemini":
            runtime = await _resolve_prompt_runtime(db=db, prompt_code=resolved_prompt_code)
            selected_model = _resolve_gemini_live_model(runtime["llm_model"])
            selected_provider = resolve_live_provider(runtime["llm_provider"], selected_model)
            available, reason = provider_available(selected_provider)
            if selected_provider != "gemini":
                logger.warning(
                    "Twilio inbound requested unsupported stream provider. provider=%s prompt=%s",
                    selected_provider,
                    resolved_prompt_code,
                )
                xml = twilio_voice_agent_service.build_hangup_twiml(
                    say_text="現在この音声エンジンには未対応です。担当者にお問い合わせください。",
                    language=settings.twilio_agent_language,
                )
            elif not available:
                logger.warning(
                    "Twilio inbound gemini stream unavailable. reason=%s prompt=%s",
                    reason,
                    resolved_prompt_code,
                )
                xml = twilio_voice_agent_service.build_hangup_twiml(
                    say_text="現在AI音声エンジンを利用できません。時間をおいてお試しください。",
                    language=settings.twilio_agent_language,
                )
            else:
                stream_url = _build_twilio_media_stream_url(
                    request=request,
                    prompt_code=resolved_prompt_code,
                    voice_name=effective_voice_name,
                )
                xml = (
                    '<?xml version="1.0" encoding="UTF-8"?>'
                    "<Response><Connect>"
                    f"<Stream url=\"{html.escape(stream_url, quote=True)}\" track=\"inbound_track\" />"
                    "</Connect></Response>"
                )
        else:
            turn_url = str(request.url_for("twilio_voice_agent_turn"))
            action_url = twilio_voice_agent_service.build_turn_action_url(turn_url, resolved_prompt_code)
            call_sid = (CallSid or "").strip()
            if call_sid:
                await twilio_voice_agent_service.ensure_session(
                    db=db,
                    call_sid=call_sid,
                    prompt_code=resolved_prompt_code,
                )
            xml = twilio_voice_agent_service.build_gather_twiml(
                say_text=twilio_voice_agent_service.opening_text(),
                action_url=action_url,
                language=settings.twilio_agent_language,
            )
    else:
        xml = service.build_incoming_to_client_twiml(identity, prompt_code=resolved_prompt_code)

    logger.info(
        (
            "Twilio inbound webhook called. "
            "CallSid=%s From=%s To=%s mode=%s engine=%s identity=%s prompt_code=%s"
        ),
        CallSid,
        From,
        To,
        mode_value,
        engine_value,
        identity,
        resolved_prompt_code,
    )
    if pending_override and not any([(prompt_code or "").strip(), (voice_engine or "").strip(), (voice_name or "").strip()]):
        logger.info(
            (
                "Applied pending inbound override for inbound call. "
                "CallSid=%s To=%s prompt_code=%s voice_engine=%s voice_name=%s"
            ),
            CallSid,
            _normalize_e164_number(To),
            pending_prompt,
            pending_engine,
            pending_voice_name,
        )
    return Response(content=xml, media_type="application/xml")


@router.post("/voice/agent/turn", name="twilio_voice_agent_turn")
async def twilio_voice_agent_turn(
    request: Request,
    db: AsyncSession = Depends(get_db),
    prompt_code: Optional[str] = Query(None),
    CallSid: Optional[str] = Form(None),  # noqa: N803
    To: Optional[str] = Form(None),  # noqa: N803
    SpeechResult: Optional[str] = Form(None),  # noqa: N803
):
    await _verify_webhook_or_raise(request)
    call_sid = (CallSid or "").strip() or "unknown-call"
    service = TwilioWebCallService()
    resolved_prompt_code = service.resolve_incoming_prompt_code(prompt_code=prompt_code, to_number=To)
    turn_url = str(request.url_for("twilio_voice_agent_turn"))
    action_url = twilio_voice_agent_service.build_turn_action_url(turn_url, resolved_prompt_code)
    user_text = (SpeechResult or "").strip()

    if not user_text:
        xml = twilio_voice_agent_service.build_gather_twiml(
            say_text=twilio_voice_agent_service.retry_text(),
            action_url=action_url,
            language=settings.twilio_agent_language,
        )
        return Response(content=xml, media_type="application/xml")

    if twilio_voice_agent_service.is_end_intent(user_text):
        await twilio_voice_agent_service.clear_session(call_sid)
        xml = twilio_voice_agent_service.build_hangup_twiml(
            say_text=twilio_voice_agent_service.closing_text(),
            language=settings.twilio_agent_language,
        )
        return Response(content=xml, media_type="application/xml")

    reply = await twilio_voice_agent_service.generate_reply(
        db=db,
        call_sid=call_sid,
        prompt_code=resolved_prompt_code,
        user_text=user_text,
    )
    xml = twilio_voice_agent_service.build_gather_twiml(
        say_text=reply,
        action_url=action_url,
        language=settings.twilio_agent_language,
    )
    return Response(content=xml, media_type="application/xml")


@router.websocket("/voice/stream", name="twilio_voice_media_stream")
async def twilio_voice_media_stream(
    websocket: WebSocket,
    prompt_code: str | None = Query(default=None),
    voice_name: str | None = Query(default=None),
):
    await websocket.accept()

    runtime_notice = None
    async with AsyncSessionLocal() as db:
        runtime = await _resolve_prompt_runtime(db=db, prompt_code=prompt_code)
        runtime_notice = runtime["notice"]

    selected_model = _resolve_gemini_live_model(runtime["llm_model"])
    selected_provider = resolve_live_provider(runtime["llm_provider"], selected_model)
    available, reason = provider_available(selected_provider)
    if selected_provider != "gemini":
        logger.warning(
            "Twilio media stream provider unsupported. provider=%s model=%s prompt=%s",
            selected_provider,
            selected_model,
            runtime["prompt_code"],
        )
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    if not available:
        logger.warning("Twilio media stream unavailable. provider=%s reason=%s", selected_provider, reason)
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    selected_voice = (voice_name or runtime["voice_name"] or settings.default_live_voice or "Aoede").strip() or "Aoede"
    manual_vad_control = _use_manual_vad_control()
    opening_hint = _build_gemini_opening_hint(runtime["system_instruction"])
    live_config = _build_gemini_live_config(
        system_instruction=runtime["system_instruction"],
        voice_name=selected_voice,
        manual_vad=manual_vad_control,
    )
    client = genai.Client(api_key=settings.google_api_key)

    stream_sid: str | None = None
    current_call_sid: str | None = None
    twilio_started = asyncio.Event()
    stream_done = asyncio.Event()
    in_resample_state: tuple[object, object] | None = None
    out_resample_state: tuple[object, object] | None = None
    assistant_speaking = False
    assistant_last_output_at: float | None = None
    opening_suppress_until: float | None = None
    speaking_active = False
    silence_started_at: float | None = None
    last_voice_at: float | None = None
    turn_started_at: float | None = None
    awaiting_model_response = False
    awaiting_model_since: float | None = None
    awaiting_model_retry_count = 0
    awaiting_manual_turn = False
    manual_inject_lock_until: float | None = None
    voice_frame_streak = 0
    pre_roll_frames: deque[bytes] = deque(maxlen=_VAD_PRE_ROLL_FRAMES)
    rms_window: deque[int] = deque(maxlen=80)
    adaptive_threshold = _VAD_RMS_THRESHOLD
    media_frames = 0
    last_media_stats_at = 0.0
    decode_fail_count = 0
    last_decode_error_at = 0.0
    logged_non_inbound_track = False
    send_lock = asyncio.Lock()

    async def _send_twilio_event(payload: dict[str, object]) -> None:
        async with send_lock:
            await websocket.send_text(json.dumps(payload))

    try:
        async with client.aio.live.connect(model=selected_model, config=live_config) as session:
            logger.info(
                "Twilio media stream connected. provider=%s model=%s voice=%s prompt=%s notice=%s activity_mode=%s",
                selected_provider,
                selected_model,
                selected_voice,
                runtime["prompt_code"],
                runtime_notice,
                "manual" if manual_vad_control else "auto",
            )

            async def twilio_to_live() -> None:
                nonlocal stream_sid
                nonlocal current_call_sid
                nonlocal in_resample_state
                nonlocal assistant_speaking
                nonlocal assistant_last_output_at
                nonlocal opening_suppress_until
                nonlocal speaking_active
                nonlocal silence_started_at
                nonlocal last_voice_at
                nonlocal turn_started_at
                nonlocal awaiting_model_response
                nonlocal awaiting_model_since
                nonlocal awaiting_model_retry_count
                nonlocal awaiting_manual_turn
                nonlocal manual_inject_lock_until
                nonlocal voice_frame_streak
                nonlocal pre_roll_frames
                nonlocal adaptive_threshold
                nonlocal media_frames
                nonlocal last_media_stats_at
                nonlocal decode_fail_count
                nonlocal last_decode_error_at
                nonlocal logged_non_inbound_track
                while True:
                    raw = await websocket.receive_text()
                    try:
                        payload = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    event_type = str(payload.get("event") or "").strip().lower()
                    if event_type in {"connected", "mark"}:
                        continue

                    if event_type == "start":
                        start = payload.get("start") or {}
                        stream_sid = str(start.get("streamSid") or payload.get("streamSid") or "").strip() or None
                        current_call_sid = (
                            str(start.get("callSid") or payload.get("callSid") or "").strip() or None
                        )
                        await _mark_stream_active(current_call_sid)
                        twilio_started.set()
                        await _append_call_trace(
                            current_call_sid,
                            event_type="stream_start",
                            text=(
                                f"prompt={runtime['prompt_code'] or '-'} voice={selected_voice} "
                                f"activity_mode={'manual' if manual_vad_control else 'auto'}"
                            ),
                            level="success",
                        )
                        # Force half-duplex opening turn: prevent early noise from interrupting greeting.
                        assistant_speaking = True
                        opening_suppress_until = time.monotonic() + (_OPENING_SUPPRESS_MS / 1000.0)
                        await session.send_realtime_input(text=opening_hint)
                        if manual_vad_control:
                            await session.send_realtime_input(activity_end=types.ActivityEnd())
                        continue

                    if event_type == "media":
                        media = payload.get("media") or {}
                        track = str(media.get("track") or "").strip().lower()
                        if track and "inbound" not in track:
                            if not logged_non_inbound_track:
                                logged_non_inbound_track = True
                                await _append_call_trace(
                                    current_call_sid,
                                    event_type="media_track_ignored",
                                    text=f"track={track}",
                                    level="info",
                                )
                            continue
                        encoded = media.get("payload")
                        if not isinstance(encoded, str) or not encoded.strip():
                            continue
                        try:
                            encoded_clean = encoded.strip()
                            padding = (-len(encoded_clean)) % 4
                            if padding:
                                encoded_clean += "=" * padding
                            ulaw_bytes = base64.b64decode(encoded_clean.encode("ascii"), validate=False)
                            pcm8 = audioop.ulaw2lin(ulaw_bytes, 2)
                            pcm16k, in_resample_state = audioop.ratecv(
                                pcm8,
                                2,
                                1,
                                8000,
                                16000,
                                in_resample_state,
                            )
                        except Exception:
                            decode_fail_count += 1
                            now_ts = time.monotonic()
                            if (now_ts - last_decode_error_at) >= 2.0:
                                last_decode_error_at = now_ts
                                await _append_call_trace(
                                    current_call_sid,
                                    event_type="media_decode_error",
                                    text=f"count={decode_fail_count}",
                                    level="warning",
                                )
                            continue

                        rms = 0
                        try:
                            rms = audioop.rms(pcm8, 2)
                        except Exception:
                            rms = 0
                        rms_window.append(rms)
                        if len(rms_window) >= 12:
                            sorted_window = sorted(rms_window)
                            # Use lower percentile as noise floor to avoid speech bursts inflating threshold.
                            noise_floor = sorted_window[(len(sorted_window) * 3) // 10]
                            target_threshold = int(noise_floor * _VAD_NOISE_MULTIPLIER)
                            target_threshold = max(_VAD_RMS_THRESHOLD, min(_VAD_ADAPTIVE_THRESHOLD_MAX, target_threshold))
                            adaptive_threshold = int(
                                adaptive_threshold * (1.0 - _VAD_ADAPTIVE_SMOOTHING)
                                + target_threshold * _VAD_ADAPTIVE_SMOOTHING
                            )
                            adaptive_threshold = max(
                                _VAD_RMS_THRESHOLD,
                                min(_VAD_ADAPTIVE_THRESHOLD_MAX, adaptive_threshold),
                            )
                        else:
                            adaptive_threshold = _VAD_RMS_THRESHOLD

                        now_ts = time.monotonic()
                        media_frames += 1

                        if manual_inject_lock_until and now_ts < manual_inject_lock_until:
                            voice_frame_streak = 0
                            pre_roll_frames.clear()
                            if (now_ts - last_media_stats_at) >= 2.0:
                                last_media_stats_at = now_ts
                                await _append_call_trace(
                                    current_call_sid,
                                    event_type="media_stats",
                                    text=(
                                        f"frames={media_frames} rms={rms} threshold={adaptive_threshold} "
                                        "mode=manual_inject_lock"
                                    ),
                                    level="info",
                                )
                            continue

                        if not manual_vad_control:
                            if opening_suppress_until and now_ts < opening_suppress_until:
                                if (now_ts - last_media_stats_at) >= 2.0:
                                    last_media_stats_at = now_ts
                                    await _append_call_trace(
                                        current_call_sid,
                                        event_type="media_stats",
                                        text=(
                                            f"frames={media_frames} rms={rms} threshold={adaptive_threshold} "
                                            "mode=suppressed_opening_auto"
                                        ),
                                        level="info",
                                    )
                                continue

                            if assistant_speaking:
                                if (
                                    assistant_last_output_at is not None
                                    and ((now_ts - assistant_last_output_at) * 1000) >= _ASSISTANT_OUTPUT_LOCK_TIMEOUT_MS
                                ):
                                    assistant_speaking = False
                                    await _append_call_trace(
                                        current_call_sid,
                                        event_type="assistant_output_lock_timeout",
                                        text=f"released_ms={_ASSISTANT_OUTPUT_LOCK_TIMEOUT_MS}",
                                        level="warning",
                                    )
                                else:
                                    if (now_ts - last_media_stats_at) >= 2.0:
                                        last_media_stats_at = now_ts
                                        await _append_call_trace(
                                            current_call_sid,
                                            event_type="media_stats",
                                            text=(
                                                f"frames={media_frames} rms={rms} threshold={adaptive_threshold} "
                                                "mode=assistant_output_lock_auto"
                                            ),
                                            level="info",
                                        )
                                    continue

                            ready_for_manual = (
                                not assistant_speaking
                                and not awaiting_model_response
                                and (not opening_suppress_until or now_ts >= opening_suppress_until)
                            )
                            if ready_for_manual:
                                injected_segments = await _drain_manual_audio(current_call_sid)
                                if injected_segments:
                                    combined_manual_audio = b"".join(injected_segments)
                                    stats = _pcm16_audio_stats(combined_manual_audio, sample_rate=16000)
                                await _append_call_trace(
                                    current_call_sid,
                                    event_type="manual_audio_injecting",
                                    text=(
                                        f"segments={len(injected_segments)} bytes={stats['bytes']} "
                                        f"duration_ms={stats['duration_ms']} rms={stats['rms']} peak={stats['peak']} "
                                        "mode=auto_vad"
                                    ),
                                    level="info",
                                )
                                for segment in injected_segments:
                                    for packet in _chunk_bytes(segment, 640):
                                        await session.send_realtime_input(
                                            audio=types.Blob(data=packet, mime_type="audio/pcm;rate=16000")
                                        )
                                awaiting_model_response = True
                                awaiting_model_since = now_ts
                                awaiting_model_retry_count = 0
                                awaiting_manual_turn = True
                                lock_seconds = min(
                                    12.0,
                                    max(2.5, (stats["duration_ms"] / 1000.0) + 1.5),
                                )
                                manual_inject_lock_until = now_ts + lock_seconds
                                continue

                            await session.send_realtime_input(
                                audio=types.Blob(data=pcm16k, mime_type="audio/pcm;rate=16000")
                            )
                            if (now_ts - last_media_stats_at) >= 2.0:
                                last_media_stats_at = now_ts
                                await _append_call_trace(
                                    current_call_sid,
                                    event_type="media_stats",
                                    text=f"frames={media_frames} rms={rms} threshold={adaptive_threshold} mode=auto_stream",
                                    level="info",
                                )
                            continue

                        ready_for_manual = (
                            not awaiting_model_response
                            and not assistant_speaking
                            and (not opening_suppress_until or now_ts >= opening_suppress_until)
                        )
                        if ready_for_manual:
                            injected_segments = await _drain_manual_audio(current_call_sid)
                            if injected_segments:
                                combined_manual_audio = b"".join(injected_segments)
                                stats = _pcm16_audio_stats(combined_manual_audio, sample_rate=16000)
                                await _append_call_trace(
                                    current_call_sid,
                                    event_type="manual_audio_injecting",
                                    text=(
                                        f"segments={len(injected_segments)} bytes={stats['bytes']} "
                                        f"duration_ms={stats['duration_ms']} rms={stats['rms']} peak={stats['peak']}"
                                    ),
                                    level="info",
                                )
                                for segment in injected_segments:
                                    for packet in _chunk_bytes(segment, 640):
                                        await session.send_realtime_input(
                                            audio=types.Blob(data=packet, mime_type="audio/pcm;rate=16000")
                                        )
                                await session.send_realtime_input(activity_end=types.ActivityEnd())
                                awaiting_model_response = True
                                awaiting_model_since = now_ts
                                awaiting_model_retry_count = 0
                                awaiting_manual_turn = True
                                manual_inject_lock_until = now_ts + (_MANUAL_INJECT_MEDIA_SUPPRESS_MS / 1000.0)
                                speaking_active = False
                                turn_started_at = None
                                silence_started_at = None
                                voice_frame_streak = 0
                                pre_roll_frames.clear()
                                continue

                        if opening_suppress_until and now_ts < opening_suppress_until:
                            if speaking_active:
                                speaking_active = False
                                turn_started_at = None
                                silence_started_at = None
                            if (now_ts - last_media_stats_at) >= 2.0:
                                last_media_stats_at = now_ts
                                await _append_call_trace(
                                    current_call_sid,
                                    event_type="media_stats",
                                    text=f"frames={media_frames} rms={rms} threshold={adaptive_threshold} mode=suppressed_opening",
                                    level="info",
                                )
                            continue

                        # After a turn is committed, keep a short lock window so ambient noise
                        # does not immediately open a new turn and cancel the pending response.
                        if awaiting_model_response:
                            voice_frame_streak = 0
                            pre_roll_frames.clear()
                            if (now_ts - last_media_stats_at) >= 2.0:
                                last_media_stats_at = now_ts
                                await _append_call_trace(
                                    current_call_sid,
                                    event_type="media_stats",
                                    text=f"frames={media_frames} rms={rms} threshold={adaptive_threshold} mode=awaiting_response",
                                    level="info",
                                )
                            continue

                        # Keep a short pre-roll so first syllables are not clipped when speech starts.
                        pre_roll_frames.append(pcm16k)

                        if (now_ts - last_media_stats_at) >= 2.0:
                            last_media_stats_at = now_ts
                            await _append_call_trace(
                                current_call_sid,
                                event_type="media_stats",
                                text=f"frames={media_frames} rms={rms} threshold={adaptive_threshold}",
                                level="info",
                            )

                        if rms >= adaptive_threshold:
                            voice_frame_streak += 1
                            last_voice_at = now_ts
                            silence_started_at = None

                            if speaking_active:
                                # Keep streaming voiced frames while the turn is active.
                                await session.send_realtime_input(
                                    audio=types.Blob(data=pcm16k, mime_type="audio/pcm;rate=16000")
                                )
                                if turn_started_at and ((now_ts - turn_started_at) * 1000) >= _VAD_MAX_TURN_MS:
                                    # Hard cap for long/noisy turns that never reach silence.
                                    speaking_active = False
                                    turn_started_at = None
                                    silence_started_at = None
                                    voice_frame_streak = 0
                                    pre_roll_frames.clear()
                                    logger.info("Twilio VAD forced end by max turn window.")
                                    await session.send_realtime_input(activity_end=types.ActivityEnd())
                                    awaiting_model_response = True
                                    awaiting_model_since = now_ts
                                    awaiting_model_retry_count = 0
                                    awaiting_manual_turn = False
                                    await _append_call_trace(
                                        current_call_sid,
                                        event_type="vad_forced_end",
                                        text=f"max_turn_ms={_VAD_MAX_TURN_MS}",
                                        level="warning",
                                    )
                                continue

                            if voice_frame_streak >= _VAD_START_CONSEC_FRAMES:
                                speaking_active = True
                                turn_started_at = now_ts
                                logger.info(
                                    "Twilio VAD start detected. rms=%s threshold=%s",
                                    rms,
                                    adaptive_threshold,
                                )
                                await _append_call_trace(
                                    current_call_sid,
                                    event_type="vad_start",
                                    text=(
                                        f"rms={rms} threshold={adaptive_threshold} "
                                        f"streak={voice_frame_streak}"
                                    ),
                                    level="info",
                                )
                                # Flush pre-roll plus current frame to Gemini once turn starts.
                                for buffered in pre_roll_frames:
                                    await session.send_realtime_input(
                                        audio=types.Blob(data=buffered, mime_type="audio/pcm;rate=16000")
                                    )
                                pre_roll_frames.clear()
                            continue

                        if speaking_active:
                            await session.send_realtime_input(
                                audio=types.Blob(data=pcm16k, mime_type="audio/pcm;rate=16000")
                            )
                            if silence_started_at is None:
                                silence_started_at = now_ts
                            silence_ms = (now_ts - silence_started_at) * 1000
                            if silence_ms >= _VAD_SILENCE_END_MS:
                                speaking_active = False
                                turn_started_at = None
                                silence_started_at = None
                                pre_roll_frames.clear()
                                logger.info(
                                    "Twilio VAD end detected by silence frame. threshold=%s silence_ms=%.1f",
                                    adaptive_threshold,
                                    silence_ms,
                                )
                                await session.send_realtime_input(activity_end=types.ActivityEnd())
                                awaiting_model_response = True
                                awaiting_model_since = now_ts
                                awaiting_model_retry_count = 0
                                awaiting_manual_turn = False
                                await _append_call_trace(
                                    current_call_sid,
                                    event_type="vad_end",
                                    text=f"silence_ms={int(silence_ms)} threshold={adaptive_threshold}",
                                    level="info",
                                )
                                voice_frame_streak = 0
                            continue
                        else:
                            voice_frame_streak = 0

                        if last_voice_at is not None and (now_ts - last_voice_at) > 5:
                            last_voice_at = None

                    if event_type == "stop":
                        try:
                            if manual_vad_control and speaking_active:
                                speaking_active = False
                                turn_started_at = None
                                logger.info("Twilio stream stop: closing active turn.")
                                await session.send_realtime_input(activity_end=types.ActivityEnd())
                                awaiting_model_response = False
                                awaiting_model_since = None
                                awaiting_model_retry_count = 0
                                awaiting_manual_turn = False
                            await session.send_realtime_input(audio_stream_end=True)
                        except Exception:
                            pass
                        await _append_call_trace(current_call_sid, event_type="stream_stop", level="info")
                        await _mark_stream_inactive(current_call_sid)
                        stream_done.set()
                        return

            async def turn_watchdog() -> None:
                nonlocal assistant_speaking
                nonlocal opening_suppress_until
                nonlocal speaking_active
                nonlocal silence_started_at
                nonlocal turn_started_at
                nonlocal awaiting_model_response
                nonlocal awaiting_model_since
                nonlocal awaiting_model_retry_count
                nonlocal awaiting_manual_turn
                nonlocal manual_inject_lock_until
                nonlocal voice_frame_streak
                nonlocal pre_roll_frames
                while not stream_done.is_set():
                    await asyncio.sleep(0.2)
                    now_ts = time.monotonic()
                    if not manual_vad_control:
                        if assistant_speaking:
                            continue
                        if awaiting_model_response and awaiting_model_since:
                            waited_ms = (now_ts - awaiting_model_since) * 1000
                            if waited_ms >= 15000:
                                awaiting_model_response = False
                                awaiting_model_since = None
                                awaiting_model_retry_count = 0
                                awaiting_manual_turn = False
                                await _append_call_trace(
                                    current_call_sid,
                                    event_type="auto_model_wait_timeout",
                                    text="No model output after 15000ms in auto activity mode.",
                                    level="warning",
                                )
                        ready_for_manual = (
                            not assistant_speaking
                            and not awaiting_model_response
                            and (not opening_suppress_until or now_ts >= opening_suppress_until)
                        )
                        if ready_for_manual:
                            injected_segments = await _drain_manual_audio(current_call_sid)
                            if injected_segments:
                                combined_manual_audio = b"".join(injected_segments)
                                stats = _pcm16_audio_stats(combined_manual_audio, sample_rate=16000)
                                await _append_call_trace(
                                    current_call_sid,
                                    event_type="manual_audio_injecting",
                                    text=(
                                        f"segments={len(injected_segments)} bytes={stats['bytes']} "
                                        f"duration_ms={stats['duration_ms']} rms={stats['rms']} peak={stats['peak']} "
                                        "via=watchdog mode=auto_vad"
                                    ),
                                    level="info",
                                )
                                try:
                                    for segment in injected_segments:
                                        for packet in _chunk_bytes(segment, 640):
                                            await session.send_realtime_input(
                                                audio=types.Blob(data=packet, mime_type="audio/pcm;rate=16000")
                                            )
                                    awaiting_model_response = True
                                    awaiting_model_since = now_ts
                                    awaiting_model_retry_count = 0
                                    awaiting_manual_turn = True
                                    lock_seconds = min(
                                        12.0,
                                        max(2.5, (stats["duration_ms"] / 1000.0) + 1.5),
                                    )
                                    manual_inject_lock_until = now_ts + lock_seconds
                                except Exception:
                                    return
                        continue

                    ready_for_manual = (
                        not assistant_speaking
                        and not awaiting_model_response
                        and (not opening_suppress_until or now_ts >= opening_suppress_until)
                    )
                    if ready_for_manual:
                        injected_segments = await _drain_manual_audio(current_call_sid)
                        if injected_segments:
                            combined_manual_audio = b"".join(injected_segments)
                            stats = _pcm16_audio_stats(combined_manual_audio, sample_rate=16000)
                            await _append_call_trace(
                                current_call_sid,
                                event_type="manual_audio_injecting",
                                text=(
                                    f"segments={len(injected_segments)} bytes={stats['bytes']} "
                                    f"duration_ms={stats['duration_ms']} rms={stats['rms']} peak={stats['peak']} "
                                    "via=watchdog"
                                ),
                                level="info",
                            )
                            try:
                                for segment in injected_segments:
                                    for packet in _chunk_bytes(segment, 640):
                                        await session.send_realtime_input(
                                            audio=types.Blob(data=packet, mime_type="audio/pcm;rate=16000")
                                        )
                                await session.send_realtime_input(activity_end=types.ActivityEnd())
                            except Exception:
                                return
                            awaiting_model_response = True
                            awaiting_model_since = now_ts
                            awaiting_model_retry_count = 0
                            awaiting_manual_turn = True
                            manual_inject_lock_until = now_ts + (_MANUAL_INJECT_MEDIA_SUPPRESS_MS / 1000.0)
                            speaking_active = False
                            turn_started_at = None
                            silence_started_at = None
                            voice_frame_streak = 0
                            pre_roll_frames.clear()
                            continue

                    if assistant_speaking:
                        continue
                    if not speaking_active:
                        if awaiting_model_response and awaiting_model_since:
                            waited_ms = (now_ts - awaiting_model_since) * 1000
                            if awaiting_manual_turn:
                                if waited_ms >= 15000:
                                    awaiting_model_response = False
                                    awaiting_model_since = None
                                    awaiting_model_retry_count = 0
                                    awaiting_manual_turn = False
                                    await _append_call_trace(
                                        current_call_sid,
                                        event_type="manual_turn_timeout",
                                        text="No model output after 15000ms for manual injected audio.",
                                        level="warning",
                                    )
                                continue
                            if waited_ms >= 2000 and awaiting_model_retry_count < 2:
                                awaiting_model_retry_count += 1
                                awaiting_model_since = now_ts
                                try:
                                    await session.send_realtime_input(activity_end=types.ActivityEnd())
                                    await _append_call_trace(
                                        current_call_sid,
                                        event_type="vad_commit_retry",
                                        text=f"retry={awaiting_model_retry_count} waited_ms={int(waited_ms)}",
                                        level="warning",
                                    )
                                except Exception:
                                    return
                            elif waited_ms >= 6000:
                                awaiting_model_response = False
                                awaiting_model_since = None
                                awaiting_model_retry_count = 0
                                awaiting_manual_turn = False
                                await _append_call_trace(
                                    current_call_sid,
                                    event_type="vad_commit_timeout",
                                    text="No model output after retries.",
                                    level="warning",
                                )
                        continue

                    now_ts = time.monotonic()
                    last_activity = last_voice_at
                    if last_activity is None:
                        continue

                    # Fallback for transports that do not continuously send silence frames.
                    idle_ms = (now_ts - last_activity) * 1000
                    if idle_ms < _VAD_SILENCE_END_MS:
                        if turn_started_at and ((now_ts - turn_started_at) * 1000) >= (_VAD_MAX_TURN_MS + 1200):
                            speaking_active = False
                            turn_started_at = None
                            silence_started_at = None
                            logger.info("Twilio VAD end detected by watchdog max window.")
                            try:
                                await session.send_realtime_input(activity_end=types.ActivityEnd())
                                awaiting_model_response = True
                                awaiting_model_since = now_ts
                                awaiting_model_retry_count = 0
                                awaiting_manual_turn = False
                                await _append_call_trace(
                                    current_call_sid,
                                    event_type="vad_watchdog_end",
                                    text=f"max_turn_ms={_VAD_MAX_TURN_MS}",
                                    level="warning",
                                )
                            except Exception:
                                return
                        continue

                    speaking_active = False
                    turn_started_at = None
                    silence_started_at = None
                    logger.info("Twilio VAD end detected by inactivity watchdog.")
                    try:
                        await session.send_realtime_input(activity_end=types.ActivityEnd())
                        awaiting_model_response = True
                        awaiting_model_since = now_ts
                        awaiting_model_retry_count = 0
                        awaiting_manual_turn = False
                    except Exception:
                        return

            async def live_to_twilio() -> None:
                nonlocal out_resample_state
                nonlocal assistant_speaking
                nonlocal assistant_last_output_at
                nonlocal awaiting_model_response
                nonlocal awaiting_model_since
                nonlocal awaiting_model_retry_count
                nonlocal awaiting_manual_turn
                await twilio_started.wait()
                async for message in session.receive():
                    content = message.server_content
                    if not content:
                        continue

                    if content.input_transcription and content.input_transcription.text:
                        assistant_last_output_at = time.monotonic()
                        await _append_call_trace(
                            current_call_sid,
                            event_type="input_transcript",
                            text=content.input_transcription.text,
                            final=bool(content.input_transcription.finished),
                            level="info",
                        )

                    if content.output_transcription and content.output_transcription.text:
                        assistant_last_output_at = time.monotonic()
                        awaiting_model_response = False
                        awaiting_model_since = None
                        awaiting_model_retry_count = 0
                        awaiting_manual_turn = False
                        await _append_call_trace(
                            current_call_sid,
                            event_type="output_transcript",
                            text=content.output_transcription.text,
                            final=bool(content.output_transcription.finished),
                            level="success",
                        )

                    if content.interrupted and stream_sid:
                        assistant_speaking = False
                        assistant_last_output_at = time.monotonic()
                        awaiting_model_response = False
                        awaiting_model_since = None
                        awaiting_model_retry_count = 0
                        awaiting_manual_turn = False
                        await _send_twilio_event({"event": "clear", "streamSid": stream_sid})
                        await _append_call_trace(
                            current_call_sid,
                            event_type="interrupted",
                            text="Model response interrupted by activity.",
                            level="warning",
                        )

                    if not (content.model_turn and content.model_turn.parts):
                        if content.turn_complete:
                            reason = (
                                str(content.turn_complete_reason.value)
                                if content.turn_complete_reason
                                else "unknown"
                            )
                            await _append_call_trace(
                                current_call_sid,
                                event_type="turn_complete",
                                text=f"reason={reason}",
                                level="info",
                            )
                            assistant_speaking = False
                            assistant_last_output_at = time.monotonic()
                            awaiting_model_response = False
                            awaiting_model_since = None
                            awaiting_model_retry_count = 0
                            awaiting_manual_turn = False
                        continue

                    for part in content.model_turn.parts:
                        if part.text:
                            assistant_speaking = True
                            assistant_last_output_at = time.monotonic()
                            awaiting_model_response = False
                            awaiting_model_since = None
                            awaiting_model_retry_count = 0
                            awaiting_manual_turn = False
                            await _append_call_trace(
                                current_call_sid,
                                event_type="assistant_text",
                                text=part.text,
                                level="success",
                            )

                        inline = part.inline_data
                        if not inline or not inline.data:
                            continue

                        assistant_speaking = True
                        assistant_last_output_at = time.monotonic()
                        awaiting_model_response = False
                        awaiting_model_since = None
                        awaiting_model_retry_count = 0
                        awaiting_manual_turn = False
                        try:
                            pcm_bytes = (
                                base64.b64decode(inline.data.encode("ascii"), validate=False)
                                if isinstance(inline.data, str)
                                else bytes(inline.data)
                            )
                            source_rate = _extract_audio_rate(inline.mime_type, default=24000)
                            if source_rate != 8000:
                                pcm8, out_resample_state = audioop.ratecv(
                                    pcm_bytes,
                                    2,
                                    1,
                                    source_rate,
                                    8000,
                                    out_resample_state,
                                )
                            else:
                                pcm8 = pcm_bytes
                            ulaw = audioop.lin2ulaw(pcm8, 2)
                        except Exception:
                            continue

                        if not stream_sid:
                            continue

                        for frame in _chunk_bytes(ulaw, _TWILIO_FRAME_BYTES):
                            await _send_twilio_event(
                                {
                                    "event": "media",
                                    "streamSid": stream_sid,
                                    "media": {
                                        "payload": base64.b64encode(frame).decode("ascii"),
                                    },
                                }
                            )

                    if content.turn_complete:
                        reason = (
                            str(content.turn_complete_reason.value)
                            if content.turn_complete_reason
                            else "unknown"
                        )
                        await _append_call_trace(
                            current_call_sid,
                            event_type="turn_complete",
                            text=f"reason={reason}",
                            level="info",
                        )
                        assistant_speaking = False
                        assistant_last_output_at = time.monotonic()
                        awaiting_model_response = False
                        awaiting_model_since = None
                        awaiting_model_retry_count = 0
                        awaiting_manual_turn = False

            await asyncio.gather(twilio_to_live(), live_to_twilio(), turn_watchdog())
    except WebSocketDisconnect:
        stream_done.set()
        await _append_call_trace(current_call_sid, event_type="stream_disconnect", level="warning")
        await _mark_stream_inactive(current_call_sid)
        logger.info("Twilio media stream disconnected by client.")
    except Exception as exc:
        stream_done.set()
        await _append_call_trace(
            current_call_sid,
            event_type="stream_error",
            text=str(exc),
            level="error",
        )
        await _mark_stream_inactive(current_call_sid)
        logger.exception("Twilio media stream bridge failed: %s", exc)
    finally:
        stream_done.set()
        await _mark_stream_inactive(current_call_sid)
        try:
            await websocket.close()
        except Exception:
            pass


@router.post("/voice/status", response_model=ResponseBase[dict])
async def voice_status_callback(
    request: Request,
    CallSid: Optional[str] = Form(None),  # noqa: N803
    CallStatus: Optional[str] = Form(None),  # noqa: N803
    To: Optional[str] = Form(None),  # noqa: N803
    From: Optional[str] = Form(None),  # noqa: N803
    Duration: Optional[str] = Form(None),  # noqa: N803
):
    await _verify_webhook_or_raise(request)
    normalized_status = (CallStatus or "").strip().lower()
    if normalized_status in {"completed", "canceled", "failed", "busy", "no-answer"}:
        await twilio_voice_agent_service.clear_session((CallSid or "").strip())
    logger.info(
        "Twilio status callback. CallSid=%s status=%s From=%s To=%s Duration=%s",
        CallSid,
        CallStatus,
        From,
        To,
        Duration,
    )
    return ResponseBase(
        success=True,
        data={
            "call_sid": CallSid,
            "status": CallStatus,
            "from": From,
            "to": To,
            "duration": Duration,
        },
    )


@router.get("/voice/trace", response_model=ResponseBase[dict])
async def get_voice_trace(
    _auth: None = Depends(require_api_key),
    call_sid: str = Query(..., min_length=1, description="Twilio call SID"),
    since: int = Query(0, ge=0, description="Return events with seq > since"),
):
    events, last_seq = await _read_call_trace(call_sid, since)
    return ResponseBase(
        success=True,
        data={
            "call_sid": call_sid,
            "since": since,
            "last_seq": last_seq,
            "events": events,
        },
    )


@router.get("/voice/trace/latest", response_model=ResponseBase[dict])
async def get_latest_voice_trace_call_sid(
    _auth: None = Depends(require_api_key),
):
    latest_call_sid = await _read_latest_trace_call_sid()
    return ResponseBase(
        success=True,
        data={
            "call_sid": latest_call_sid,
        },
    )


@router.post("/voice/trace/inject-audio", response_model=ResponseBase[dict])
async def inject_voice_trace_audio(
    payload: TwilioManualAudioInjectRequest,
    _auth: None = Depends(require_api_key),
):
    call_sid = payload.call_sid.strip()
    if not call_sid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="call_sid is required.")

    is_active = await _is_stream_active(call_sid)
    if not is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Call stream is not active. Connect an inbound call first.",
        )

    encoded = payload.audio_base64.strip()
    try:
        padding = (-len(encoded)) % 4
        if padding:
            encoded += "=" * padding
        audio_bytes = base64.b64decode(encoded.encode("ascii"), validate=False)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid audio_base64 payload.") from exc

    if not audio_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Decoded audio payload is empty.")

    # PCM16 alignment guard.
    if len(audio_bytes) % 2 != 0:
        audio_bytes = audio_bytes[:-1]
    if not audio_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Decoded audio payload is invalid.")

    stats = _pcm16_audio_stats(audio_bytes, sample_rate=16000)
    queue_size = await _enqueue_manual_audio(call_sid, audio_bytes)
    await _append_call_trace(
        call_sid,
        event_type="manual_audio_queued",
        text=(
            f"bytes={stats['bytes']} duration_ms={stats['duration_ms']} rms={stats['rms']} "
            f"peak={stats['peak']} queue={queue_size}"
        ),
        level="info",
    )
    return ResponseBase(
        success=True,
        data={
            "call_sid": call_sid,
            "bytes": stats["bytes"],
            "duration_ms": stats["duration_ms"],
            "rms": stats["rms"],
            "peak": stats["peak"],
            "queue_size": queue_size,
            "mime_type": payload.mime_type,
        },
    )


@router.get("/voice/trace/active", response_model=ResponseBase[dict])
async def get_active_voice_trace_calls(
    _auth: None = Depends(require_api_key),
):
    active_calls = await _list_active_stream_calls()
    return ResponseBase(
        success=True,
        data={
            "active_calls": active_calls,
            "count": len(active_calls),
        },
    )
