import asyncio
import audioop
import base64
import json
import logging
import re
import time
from collections import deque
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import Response
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_api_key
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.model_defaults import require_generate_model, require_live_model
from app.repositories.call_repository import CallRepository
from app.schemas.base import ResponseBase
from app.schemas.twilio import TwilioTokenResponse
from app.services.chat_service import ChatService
from app.services.live_gateway import (
    infer_provider_from_model,
    normalize_provider,
    provider_available,
    resolve_live_provider,
)
from app.services.llm.factory import LLMFactory
from app.services.prompt_runtime_resolver import PromptRuntimeConfig, resolve_prompt_runtime
from app.services.prompt_service import PromptService
from app.services.test_session_service import TestSessionService
from app.services.twilio.live_config import _build_gemini_live_config, _use_manual_vad_control
from app.services.twilio.normalizers import (
    _ELEVENLABS_VOICE_ID_PATTERN,
    _TWILIO_SUPPORTED_TTS_PROVIDERS,
    _match_case_insensitive_voice,
    _normalize_e164_number,
    _normalize_gemini_live_voice_name,
    _normalize_prompt_code_token,
    _normalize_twilio_tts_provider,
    _normalize_twilio_voice_route,
    _normalize_voice_engine,
    _normalize_voice_name_token,
    _resolve_twilio_inbound_voice_route,
)
from app.services.twilio.pending_overrides import (
    _PENDING_PROMPT_TTL_SECONDS,
    _consume_pending_inbound_override_for_number,
    _set_pending_inbound_override_for_number,
)
from app.services.twilio.stream_runtime_store import (
    _chunk_bytes,
    _drain_manual_audio,
    _enqueue_manual_audio,
    _extract_audio_rate,
    _is_stream_active,
    _list_active_stream_calls,
    _mark_stream_active,
    _mark_stream_inactive,
    _pcm16_audio_stats,
)
from app.services.twilio.trace_store import (
    _append_call_trace,
    _read_call_trace,
    _read_latest_trace_call_sid,
)
from app.services.twilio.twiml_builders import (
    _build_twilio_conversation_relay_twiml,
    _build_twilio_media_stream_twiml,
    _candidate_websocket_signature_urls,
    _extract_stream_custom_parameters,
    _verify_websocket_or_close,
)
from app.services.twilio.voice_catalog import (
    _extract_twilio_conversationrelay_default_voice_settings,
    _extract_twilio_google_voice_names,
    _extract_twilio_tts_voice_ids,
    _load_official_gemini_voices,
    _load_twilio_conversationrelay_default_voice_settings,
    _load_twilio_conversationrelay_voice_catalog,
)
from app.services.twilio_voice_agent_service import twilio_voice_agent_service
from app.services.twilio_webcall_service import TwilioWebCallService
from app.utils.datetime_utils import now_tokyo_naive
from app.utils.twilio_security import verify_twilio_webhook_request

router = APIRouter()
logger = logging.getLogger(__name__)
_TWILIO_FRAME_BYTES = 160  # 20ms at 8kHz G.711 mu-law
_TWILIO_FALLBACK_OPENING = "いつもお世話になっております。光洲産業の自動受付AIです。本日はどのようなご用件でしょうか。"
_VAD_RMS_THRESHOLD = 55
_VAD_SILENCE_END_MS = 1100
_VAD_NOISE_MULTIPLIER = 1.9
_VAD_MAX_TURN_MS = 6000
_VAD_ADAPTIVE_THRESHOLD_MAX = 420
_VAD_ADAPTIVE_SMOOTHING = 0.2
_VAD_START_CONSEC_FRAMES = 3
_ASSISTANT_OUTPUT_LOCK_TIMEOUT_MS = 7000
_VAD_PRE_ROLL_FRAMES = 15  # 15 * 20ms = 300ms
_MANUAL_INJECT_MEDIA_SUPPRESS_MS = 8000
_OPENING_STARTUP_SUPPRESS_MS = 2200
_TWILIO_CONVERSATIONRELAY_MAX_HISTORY_MESSAGES = 24
_CONVERSATIONRELAY_SUPPORTED_DEBUG_MESSAGE_TYPES = {
    "setup",
    "prompt",
    "interrupt",
    "dtmf",
    "error",
}
_TWILIO_CLOSING_REQUIRED_ALL = ("ご利用ありがとうございます",)
_TWILIO_CLOSING_REQUIRED_ANY = ("承りました", "承知いたしました", "承知しました")
_ECHO_COMPARE_NORMALIZER = re.compile(r"[\s\u3000。、，,．.!！?？・:：\"'「」『』（）()\-ー]")
__all__ = (
    "_build_gemini_live_config",
    "_build_twilio_conversation_relay_twiml",
    "_build_twilio_media_stream_twiml",
    "_candidate_websocket_signature_urls",
    "_consume_pending_inbound_override_for_number",
    "_extract_stream_custom_parameters",
    "_extract_twilio_conversationrelay_default_voice_settings",
    "_extract_twilio_google_voice_names",
    "_extract_twilio_tts_voice_ids",
    "_is_auto_closing_reply",
    "_load_official_gemini_voices",
    "_normalize_twilio_conversationrelay_voice_id",
    "_normalize_twilio_google_voice_id",
    "_resolve_twilio_conversationrelay_default_voice",
    "_resolve_twilio_inbound_voice_route",
    "_set_pending_inbound_override_for_number",
    "_use_manual_vad_control",
)


class TwilioManualAudioInjectRequest(BaseModel):
    call_sid: str = Field(min_length=1)
    audio_base64: str = Field(min_length=1, description="PCM16 mono audio (16kHz) base64 payload.")
    mime_type: str = Field(default="audio/pcm;rate=16000")


class TwilioPrepareIncomingOverrideRequest(BaseModel):
    to_number: str = Field(min_length=1, description="Target Twilio inbound number in E.164 format.")
    prompt_code: str | None = Field(default=None, min_length=1, max_length=64)
    voice_route: str | None = Field(default=None, min_length=1, max_length=64)
    voice_engine: str | None = Field(default="gemini", min_length=1, max_length=32)
    tts_provider: str | None = Field(default=None, min_length=1, max_length=32)
    voice_name: str | None = Field(default=None, min_length=1, max_length=128)


def _resolve_gemini_live_model(candidate_model: str | None) -> str:
    return require_live_model(
        candidate_model or settings.default_live_model,
        source="Prompt llm_model",
    )


def _build_test_session_service(db: AsyncSession) -> TestSessionService:
    chat_service = ChatService(db)
    return TestSessionService(
        db,
        call_repo=chat_service.call_repo,
        appointment_repo=chat_service.appointment_repo,
        prompt_service=chat_service.prompt_service,
        extract_appointment=chat_service.extract_appointment,
    )


def _extract_opening_sentence(system_instruction: str | None) -> str | None:
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
                    return first_sentence
    return None


def _build_twilio_opening_text(system_instruction: str | None) -> str:
    return _extract_opening_sentence(system_instruction) or _TWILIO_FALLBACK_OPENING


def _normalize_echo_candidate(text: str | None) -> str:
    return _ECHO_COMPARE_NORMALIZER.sub("", (text or "").strip())


def _looks_like_opening_echo(user_text: str | None, opening_text: str | None) -> bool:
    user_token = _normalize_echo_candidate(user_text)
    opening_token = _normalize_echo_candidate(opening_text)
    if len(user_token) < 8 or len(opening_token) < 12:
        return False
    return user_token in opening_token or opening_token.startswith(user_token)


def _build_twilio_session_instruction(system_instruction: str | None, *, opening_text: str | None) -> str | None:
    base_instruction = (system_instruction or "").strip()
    played_opening = (opening_text or "").strip()
    if not played_opening:
        return base_instruction or None
    suffix = (
        "\n\n重要: 通話接続直後の冒頭挨拶はTwilio側で再生済みです。"
        f"再生済みの挨拶: 「{played_opening}」"
        "最初のユーザー発話以降は、この挨拶を繰り返さず、直ちに用件ヒアリングを継続してください。"
        "発話本文以外の説明・段取り・思考過程・英語見出しは出力しないでください。"
    )
    if not base_instruction:
        return suffix.strip()
    return f"{base_instruction}{suffix}"


def _resolve_twilio_generate_provider(provider: str | None, model: str | None) -> str:
    explicit = normalize_provider(provider) if provider else ""
    inferred = infer_provider_from_model(model) or ""
    fallback = normalize_provider(settings.default_llm_provider)
    return explicit or inferred or fallback or "gemini"


def _resolve_twilio_conversationrelay_tts_provider(
    explicit_provider: str | None,
    *,
    prompt_voice_provider: str | None = None,
    prompt_voice_id: str | None = None,
    default_provider: str | None = None,
) -> str:
    resolved_explicit = _normalize_twilio_tts_provider(explicit_provider)
    if resolved_explicit:
        return resolved_explicit

    resolved_prompt_provider = _normalize_twilio_tts_provider(prompt_voice_provider)
    if resolved_prompt_provider:
        return resolved_prompt_provider

    prompt_voice_token = (prompt_voice_id or "").strip()
    if prompt_voice_token:
        if _ELEVENLABS_VOICE_ID_PATTERN.fullmatch(prompt_voice_token):
            return "ElevenLabs"
        if "-Chirp3-HD-" in prompt_voice_token or prompt_voice_token.startswith("Google."):
            return "Google"
        if prompt_voice_token.startswith("Amazon.") or prompt_voice_token.startswith("Amazon Polly."):
            return "Amazon"

    resolved_default = _normalize_twilio_tts_provider(default_provider)
    if resolved_default:
        return resolved_default
    return "ElevenLabs"


def _normalize_twilio_google_voice_id(voice_name: str | None, *, language_code: str) -> str:
    token = (voice_name or "").strip()
    normalized_language = (language_code or "ja-JP").strip() or "ja-JP"
    default_voice = f"{normalized_language}-Chirp3-HD-Aoede"
    if not token:
        return default_voice
    if token.startswith("Google."):
        return token.replace("Google.", "", 1).strip() or default_voice
    if "-Chirp3-HD-" in token:
        return token
    short_name = _normalize_voice_name_token(token)
    if short_name:
        return f"{normalized_language}-Chirp3-HD-{short_name}"
    return default_voice


def _normalize_twilio_conversationrelay_voice_id(
    voice_name: str | None,
    *,
    tts_provider: str,
    language_code: str,
    supported_voices: list[str],
    default_voice: str,
) -> str:
    token = (voice_name or "").strip()
    if not token:
        return default_voice

    normalized_provider = _normalize_twilio_tts_provider(tts_provider) or "ElevenLabs"

    if normalized_provider == "Google":
        if token.startswith("Google."):
            token = token.replace("Google.", "", 1).strip()
        exact_match = _match_case_insensitive_voice(token, supported_voices)
        if exact_match:
            return exact_match
        short_name = _normalize_voice_name_token(token)
        if short_name:
            for official_voice in supported_voices:
                if official_voice.lower().endswith(f"-chirp3-hd-{short_name.lower()}"):
                    return official_voice
        return default_voice

    if normalized_provider == "Amazon":
        for prefix in ("Amazon Polly.", "Amazon."):
            if token.startswith(prefix):
                token = token.replace(prefix, "", 1).strip()
                break
        return _match_case_insensitive_voice(token, supported_voices) or default_voice

    if token.startswith("ElevenLabs."):
        token = token.replace("ElevenLabs.", "", 1).strip()
    exact_match = _match_case_insensitive_voice(token, supported_voices)
    if exact_match:
        return exact_match
    if _ELEVENLABS_VOICE_ID_PATTERN.fullmatch(token):
        return token
    return default_voice


def _resolve_twilio_conversationrelay_default_voice(
    *,
    tts_provider: str,
    language_code: str,
    supported_voices: list[str],
    default_voice: str,
) -> str:
    configured_voice = (settings.twilio_default_conversationrelay_voice or "").strip()
    if not configured_voice:
        return default_voice
    return _normalize_twilio_conversationrelay_voice_id(
        configured_voice,
        tts_provider=tts_provider,
        language_code=language_code,
        supported_voices=supported_voices,
        default_voice=default_voice,
    )


def _is_auto_closing_reply(text: str | None) -> bool:
    candidate = (text or "").strip()
    if not candidate:
        return False
    if candidate.endswith(("?", "？")):
        return False
    return all(token in candidate for token in _TWILIO_CLOSING_REQUIRED_ALL) and any(
        token in candidate for token in _TWILIO_CLOSING_REQUIRED_ANY
    )


async def _resolve_prompt_runtime(
    *,
    db: AsyncSession,
    prompt_code: str | None,
    model_capability: str = "any",
) -> PromptRuntimeConfig:
    effective_code = (settings.twilio_default_prompt_code or "").strip() or "general_appointment"
    fallback_instruction = (
        "あなたは日本語のコールセンター受付AIです。"
        "丁寧に自然な会話を行い、推測せず不足情報は確認質問してください。"
        "最初の発話は必ず次の一文で開始してください。"
        "「いつもお世話になっております。光洲産業の自動受付AIです。"
        "本日はどのようなご用件でしょうか。」"
    )
    prompt_service = PromptService(db)
    requested_code = (prompt_code or "").strip() or effective_code
    return await resolve_prompt_runtime(
        prompt_service,
        template_code=requested_code,
        default_code=effective_code,
        fallback_code="general_appointment",
        render_system_instruction=True,
        fallback_instruction=fallback_instruction,
        missing_notice=(
            f"Prompt template '{requested_code}' not found or inactive. "
            "Applied fallback runtime instruction."
        ),
        model_capability=model_capability,
    )


async def _resolve_twilio_incoming_prompt_code(
    *,
    db: AsyncSession,
    prompt_code: str | None,
    to_number: str | None,
) -> str | None:
    from_request = _normalize_prompt_code_token(prompt_code)
    if from_request:
        return from_request

    prompt_service = PromptService(db)
    normalized_to = _normalize_e164_number(to_number)
    if normalized_to:
        template = await prompt_service.find_template_by_twilio_inbound_number(normalized_to)
        if template:
            return template.code
        mapped = _normalize_prompt_code_token(settings.twilio_incoming_prompt_mapping.get(normalized_to))
        if mapped:
            return mapped

    default_template = await prompt_service.get_twilio_incoming_default_template()
    if default_template:
        return default_template.code

    return _normalize_prompt_code_token(settings.twilio_default_prompt_code)


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
    Twilio ConversationRelay-compatible Google voice options loaded from official Twilio docs.
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


@router.get("/voice/conversationrelay/voices", response_model=ResponseBase[dict])
async def list_conversationrelay_voice_catalog(
    force_refresh: bool = Query(default=False, description="Force refresh from official source."),
    tts_provider: str | None = Query(
        default=None,
        description="Twilio ConversationRelay TTS provider: Google, Amazon, or ElevenLabs.",
    ),
):
    language_code = (settings.twilio_agent_language or "ja-JP").strip() or "ja-JP"
    defaults_by_language, default_source, default_fetched_at = await _load_twilio_conversationrelay_default_voice_settings(
        force_refresh=force_refresh,
    )
    language_defaults = defaults_by_language.get(language_code) or {}
    default_provider = (
        _normalize_twilio_tts_provider(language_defaults.get("tts_provider"))
        or "ElevenLabs"
    )
    provider, voices, source, default_voice, fetched_at = await _load_twilio_conversationrelay_voice_catalog(
        provider=tts_provider or default_provider,
        language_code=language_code,
        force_refresh=force_refresh,
    )
    default_voice = _resolve_twilio_conversationrelay_default_voice(
        tts_provider=provider,
        language_code=language_code,
        supported_voices=voices,
        default_voice=default_voice,
    )
    return ResponseBase(
        success=True,
        data={
            "provider": provider,
            "providers": list(_TWILIO_SUPPORTED_TTS_PROVIDERS),
            "language": language_code,
            "source": source,
            "fetched_at": int(fetched_at or default_fetched_at),
            "voices": voices,
            "default_voice": default_voice,
            "default_provider": default_provider,
            "default_source": default_source,
        },
    )


@router.post("/voice/incoming/prepare", response_model=ResponseBase[dict])
async def prepare_incoming_voice_override(
    payload: TwilioPrepareIncomingOverrideRequest,
    _auth: None = Depends(require_api_key),
):
    normalized_number = _normalize_e164_number(payload.to_number)
    if not normalized_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="to_number must be a valid E.164 phone number.",
        )

    queued = await _set_pending_inbound_override_for_number(
        number=normalized_number,
        prompt_code=payload.prompt_code,
        voice_route=payload.voice_route,
        voice_engine=payload.voice_engine,
        tts_provider=payload.tts_provider,
        voice_name=payload.voice_name,
    )
    if not queued:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one of prompt_code, voice_route, voice_engine, or voice_name is required.",
        )

    prompt_token = _normalize_prompt_code_token(payload.prompt_code)
    resolved_route = _normalize_twilio_voice_route(payload.voice_route)
    resolved_engine = _normalize_voice_engine(payload.voice_engine)
    normalized_tts_provider = _normalize_twilio_tts_provider(payload.tts_provider)
    normalized_voice = _normalize_voice_name_token(payload.voice_name)
    logger.info(
        (
            "Prepared pending inbound override. "
            "to=%s prompt_code=%s voice_route=%s voice_engine=%s "
            "tts_provider=%s voice_name=%s ttl_seconds=%s"
        ),
        normalized_number,
        prompt_token,
        resolved_route,
        resolved_engine,
        normalized_tts_provider,
        normalized_voice,
        int(_PENDING_PROMPT_TTL_SECONDS),
    )
    return ResponseBase(
        success=True,
        data={
            "to_number": normalized_number,
            "prompt_code": prompt_token,
            "voice_route": resolved_route,
            "voice_engine": resolved_engine,
            "tts_provider": normalized_tts_provider,
            "voice_name": normalized_voice,
            "expires_in_seconds": int(_PENDING_PROMPT_TTL_SECONDS),
        },
    )


@router.post("/voice/twiml")
async def twiml_app_voice_webhook(
    request: Request,
    To: Optional[str] = Form(None),  # noqa: N803 (Twilio form field casing)
    From: Optional[str] = Form(None),  # noqa: N803
    CallSid: Optional[str] = Form(None),  # noqa: N803
    prompt_code: Optional[str] = Form(None),
    voice_route: Optional[str] = Form(None),
    voice_engine: Optional[str] = Form(None),
    tts_provider: Optional[str] = Form(None),
    voice_name: Optional[str] = Form(None),
):
    await _verify_webhook_or_raise(request)
    service = TwilioWebCallService()
    queued_override = await _set_pending_inbound_override_for_number(
        number=To,
        prompt_code=prompt_code,
        voice_route=voice_route,
        voice_engine=voice_engine,
        tts_provider=tts_provider,
        voice_name=voice_name,
    )
    if queued_override:
        logger.info(
            (
                "Queued pending inbound override for outbound->inbound bridge. "
                "to=%s prompt_code=%s voice_route=%s voice_engine=%s "
                "tts_provider=%s voice_name=%s"
            ),
            _normalize_e164_number(To),
            _normalize_prompt_code_token(prompt_code),
            _normalize_twilio_voice_route(voice_route),
            _normalize_voice_engine(voice_engine),
            _normalize_twilio_tts_provider(tts_provider),
            _normalize_voice_name_token(voice_name),
        )
    xml = service.build_outbound_twiml(To or "")
    logger.info(
        (
            "Twilio TwiML app webhook called. "
            "CallSid=%s From=%s To=%s prompt_code=%s voice_route=%s "
            "voice_engine=%s tts_provider=%s voice_name=%s"
        ),
        CallSid,
        From,
        To,
        prompt_code,
        voice_route,
        voice_engine,
        tts_provider,
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
    voice_route: Optional[str] = Query(
        default=None,
        description="Inbound AI voice route: gather, conversationrelay_generate, or media_stream_live.",
    ),
    voice_engine: Optional[str] = Query(
        default=None,
        description="Inbound AI voice engine: twilio or gemini.",
    ),
    tts_provider: Optional[str] = Query(
        default=None,
        description="Twilio ConversationRelay TTS provider override: Google, Amazon, or ElevenLabs.",
    ),
    voice_name: Optional[str] = Query(
        default=None,
        description="Optional Twilio ConversationRelay voice override.",
    ),
    To: Optional[str] = Form(None),  # noqa: N803
    From: Optional[str] = Form(None),  # noqa: N803
    CallSid: Optional[str] = Form(None),  # noqa: N803
):
    await _verify_webhook_or_raise(request)
    service = TwilioWebCallService()
    pending_override = await _consume_pending_inbound_override_for_number(To)
    pending_prompt = pending_override.get("prompt_code") if pending_override else None
    pending_route = pending_override.get("voice_route") if pending_override else None
    pending_engine = pending_override.get("voice_engine") if pending_override else None
    pending_tts_provider = pending_override.get("tts_provider") if pending_override else None
    pending_voice_name = pending_override.get("voice_name") if pending_override else None
    effective_prompt = prompt_code or pending_prompt
    resolved_prompt_code = await _resolve_twilio_incoming_prompt_code(
        db=db,
        prompt_code=effective_prompt,
        to_number=To,
    )
    mode_value = ((mode or settings.twilio_incoming_default_mode or "agent").strip().lower())
    effective_route = voice_route or pending_route
    effective_engine = voice_engine or pending_engine
    route_value = _resolve_twilio_inbound_voice_route(
        voice_route=effective_route,
        voice_engine=effective_engine,
    )
    xml: str
    if route_value not in {"gather", "conversationrelay_generate", "media_stream_live"}:
        logger.warning(
            "Twilio inbound voice route invalid. route=%s engine=%s call_sid=%s to=%s",
            effective_route,
            effective_engine,
            CallSid,
            To,
        )
        xml = twilio_voice_agent_service.build_hangup_twiml(
            say_text="音声エンジン設定が不正です。設定を確認してください。",
            language=settings.twilio_agent_language,
        )
        return Response(content=xml, media_type="application/xml")

    if mode_value == "agent":
        if route_value == "conversationrelay_generate":
            runtime = await _resolve_prompt_runtime(
                db=db,
                prompt_code=resolved_prompt_code,
                model_capability="generate",
            )
            try:
                selected_model = require_generate_model(
                    runtime.llm_model,
                    source="Prompt llm_model",
                )
            except ValueError as exc:
                logger.warning(
                    "Twilio inbound prompt model incompatible with ConversationRelay. prompt=%s error=%s",
                    resolved_prompt_code,
                    exc,
                )
                xml = twilio_voice_agent_service.build_hangup_twiml(
                    say_text=(
                        "現在の Prompt モデルは電話テストに利用できません。"
                        "Twilio ConversationRelay では文字生成に対応したモデルを選択してください。"
                    ),
                    language=settings.twilio_agent_language,
                )
                return Response(content=xml, media_type="application/xml")

            selected_provider = _resolve_twilio_generate_provider(runtime.llm_provider, selected_model)
            if selected_provider != "gemini" or not (settings.google_api_key or "").strip():
                logger.warning(
                    "Twilio inbound requested unsupported ConversationRelay provider. provider=%s prompt=%s",
                    selected_provider,
                    resolved_prompt_code,
                )
                xml = twilio_voice_agent_service.build_hangup_twiml(
                    say_text="現在この電話テスト用 AI エンジンは利用できません。設定を確認してください。",
                    language=settings.twilio_agent_language,
                )
                return Response(content=xml, media_type="application/xml")

            language_code = (settings.twilio_agent_language or "ja-JP").strip() or "ja-JP"
            defaults_by_language, _, _ = await _load_twilio_conversationrelay_default_voice_settings()
            language_defaults = defaults_by_language.get(language_code) or {}
            selected_tts_provider = _resolve_twilio_conversationrelay_tts_provider(
                tts_provider or pending_tts_provider,
                prompt_voice_provider=runtime.voice_provider,
                prompt_voice_id=runtime.voice_id,
                default_provider=language_defaults.get("tts_provider"),
            )
            _, supported_voices, _, default_voice, _ = await _load_twilio_conversationrelay_voice_catalog(
                provider=selected_tts_provider,
                language_code=language_code,
            )
            default_voice = _resolve_twilio_conversationrelay_default_voice(
                tts_provider=selected_tts_provider,
                language_code=language_code,
                supported_voices=supported_voices,
                default_voice=default_voice,
            )
            selected_voice_override = _normalize_voice_name_token(voice_name or pending_voice_name)
            resolved_conversation_relay_voice = _normalize_twilio_conversationrelay_voice_id(
                selected_voice_override or runtime.voice_id,
                tts_provider=selected_tts_provider,
                language_code=language_code,
                supported_voices=supported_voices,
                default_voice=default_voice,
            )
            opening_text = _build_twilio_opening_text(runtime.system_instruction)
            xml = _build_twilio_conversation_relay_twiml(
                request=request,
                prompt_code=runtime.template_code,
                from_number=From,
                to_number=To,
                tts_provider=selected_tts_provider,
                voice_name=resolved_conversation_relay_voice,
                opening_text=opening_text,
            )
        elif route_value == "media_stream_live":
            runtime = await _resolve_prompt_runtime(
                db=db,
                prompt_code=resolved_prompt_code,
                model_capability="live",
            )
            try:
                selected_model = _resolve_gemini_live_model(runtime.llm_model)
            except ValueError as exc:
                logger.warning(
                    "Twilio inbound prompt model incompatible with media stream live. prompt=%s error=%s",
                    resolved_prompt_code,
                    exc,
                )
                xml = twilio_voice_agent_service.build_hangup_twiml(
                    say_text=(
                        "当前 Prompt 模型不能用于 Twilio Media Streams。"
                        "请切换到 Gemini Live / Native Audio 模型后再测试。"
                    ),
                    language=settings.twilio_agent_language,
                )
                return Response(content=xml, media_type="application/xml")

            selected_provider = resolve_live_provider(runtime.llm_provider, selected_model)
            available, reason = provider_available(selected_provider)
            if selected_provider != "gemini" or not available:
                logger.warning(
                    "Twilio inbound media stream provider unavailable. provider=%s prompt=%s reason=%s",
                    selected_provider,
                    resolved_prompt_code,
                    reason,
                )
                xml = twilio_voice_agent_service.build_hangup_twiml(
                    say_text="当前电话音频桥接不可用。请检查 Gemini Live 配置后重试。",
                    language=settings.twilio_agent_language,
                )
                return Response(content=xml, media_type="application/xml")

            selected_voice_override = _normalize_voice_name_token(voice_name or pending_voice_name)
            requested_live_voice = selected_voice_override or runtime.voice_id
            resolved_live_voice = _normalize_gemini_live_voice_name(
                requested_live_voice,
                voice_provider=runtime.voice_provider,
                default_voice=settings.default_live_voice or "Aoede",
            )
            if (requested_live_voice or "").strip() and resolved_live_voice != requested_live_voice:
                logger.info(
                    "Normalized Twilio media stream voice for Gemini Live. requested=%s resolved=%s prompt=%s provider=%s",
                    requested_live_voice,
                    resolved_live_voice,
                    runtime.template_code,
                    runtime.voice_provider,
                )
            xml = _build_twilio_media_stream_twiml(
                request=request,
                prompt_code=runtime.template_code,
                from_number=From,
                to_number=To,
                voice_name=resolved_live_voice,
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
            "CallSid=%s From=%s To=%s mode=%s route=%s engine=%s identity=%s prompt_code=%s"
        ),
        CallSid,
        From,
        To,
        mode_value,
        route_value,
        effective_engine,
        identity,
        resolved_prompt_code,
    )
    if pending_override and not any(
        [
            (prompt_code or "").strip(),
            (voice_route or "").strip(),
            (voice_engine or "").strip(),
            (voice_name or "").strip(),
        ]
    ):
        logger.info(
            (
                "Applied pending inbound override for inbound call. "
                "CallSid=%s To=%s prompt_code=%s voice_route=%s voice_engine=%s "
                "tts_provider=%s voice_name=%s"
            ),
            CallSid,
            _normalize_e164_number(To),
            pending_prompt,
            pending_route,
            pending_engine,
            pending_tts_provider,
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


@router.websocket("/voice/conversationrelay", name="twilio_voice_conversation_relay")
async def twilio_voice_conversation_relay(websocket: WebSocket):
    if not await _verify_websocket_or_close(websocket):
        return
    await websocket.accept()

    current_call_sid: str | None = None
    current_session_id: str | None = None
    current_from_number: str | None = None
    current_to_number: str | None = None
    current_prompt_code: str | None = None
    current_tts_provider: str | None = None
    current_voice_name: str | None = None
    runtime: PromptRuntimeConfig | None = None
    selected_provider: str | None = None
    selected_model: str | None = None
    session_instruction: str | None = None
    opening_text: str | None = None
    bound_call_id = None
    bound_call_finalized = False
    history: list[dict[str, str]] = []
    prompt_chunks: list[str] = []
    response_task: asyncio.Task[None] | None = None
    finalize_lock = asyncio.Lock()
    send_lock = asyncio.Lock()

    async def _send_relay_message(payload: dict[str, object]) -> None:
        async with send_lock:
            await websocket.send_text(json.dumps(payload))

    async def _ensure_bound_call_id():
        nonlocal bound_call_id
        if bound_call_id is not None:
            return bound_call_id
        if not current_call_sid or runtime is None or selected_model is None or selected_provider is None:
            return None

        async with AsyncSessionLocal() as db:
            call_repo = CallRepository(db)
            existing_call = await call_repo.get_by_sip_call_id(current_call_sid)
            if existing_call:
                extra_data = dict(existing_call.extra_data or {})
                extra_data.setdefault("source", "twilio_conversationrelay")
                extra_data.setdefault("transport", "twilio")
                extra_data["template_code"] = runtime.template_code
                extra_data["llm_provider"] = selected_provider
                extra_data["llm_model"] = selected_model
                extra_data["twilio_call_sid"] = current_call_sid
                if current_session_id:
                    extra_data["twilio_conversationrelay_session_id"] = current_session_id
                if current_voice_name:
                    extra_data["twilio_voice_name"] = current_voice_name
                if current_tts_provider:
                    extra_data["twilio_tts_provider"] = current_tts_provider
                existing_call.extra_data = extra_data
                await db.commit()
                await db.refresh(existing_call)
                bound_call_id = existing_call.id
                return bound_call_id

            started_at = now_tokyo_naive()
            created_call = await call_repo.create(
                {
                    "direction": "inbound",
                    "counterpart": (current_from_number or current_call_sid),
                    "caller_name": current_from_number or "Twilio Caller",
                    "status": "ongoing",
                    "handler_type": "ai",
                    "is_answered": True,
                    "started_at": started_at,
                    "answered_at": started_at,
                    "prompt_id": runtime.template.id if runtime.template else None,
                    "sip_call_id": current_call_sid,
                    "sip_from": current_from_number,
                    "sip_to": current_to_number,
                    "extra_data": {
                        "source": "twilio_conversationrelay",
                        "transport": "twilio",
                        "template_code": runtime.template_code,
                        "llm_provider": selected_provider,
                        "llm_model": selected_model,
                        "twilio_call_sid": current_call_sid,
                        "twilio_conversationrelay_session_id": current_session_id,
                        "twilio_tts_provider": current_tts_provider,
                        "twilio_voice_name": current_voice_name,
                        "messages": [],
                    },
                    "summary": "Twilio ConversationRelay call",
                }
            )
            bound_call_id = created_call.id
            return bound_call_id

    async def _append_bound_messages(messages: list[dict[str, str]]) -> None:
        call_id = await _ensure_bound_call_id()
        if not call_id or not messages:
            return
        async with AsyncSessionLocal() as db:
            service = _build_test_session_service(db)
            await service.append_test_session_messages(
                call_id=call_id,
                messages=messages,
                template_code=runtime.template_code if runtime else current_prompt_code,
                provider=selected_provider,
                model=selected_model,
            )

    async def _finalize_bound_call(*, trigger: str, run_extraction: bool = True) -> None:
        nonlocal bound_call_finalized
        call_id = await _ensure_bound_call_id()
        if not call_id:
            return
        async with finalize_lock:
            if bound_call_finalized:
                return
            try:
                async with AsyncSessionLocal() as db:
                    service = _build_test_session_service(db)
                    result = await service.finalize_test_session(
                        call_id=call_id,
                        template_code=runtime.template_code if runtime else current_prompt_code,
                        run_extraction=run_extraction,
                    )
            except Exception as exc:
                logger.warning(
                    "Failed to finalize Twilio ConversationRelay bound call. call_sid=%s trigger=%s error=%s",
                    current_call_sid,
                    trigger,
                    exc,
                )
                await _append_call_trace(
                    current_call_sid,
                    event_type="call_finalize_error",
                    text=str(exc),
                    level="warning",
                )
                return
            bound_call_finalized = True
            await _append_call_trace(
                current_call_sid,
                event_type="call_finalized",
                text=f"trigger={trigger} appointment_id={result.appointment_id or '-'}",
                level="success",
            )

    async def _cancel_response_task(*, reason: str) -> None:
        nonlocal response_task
        task = response_task
        if not task or task.done():
            response_task = None
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.warning("ConversationRelay generation cancellation failed: %s", exc)
        response_task = None
        await _append_call_trace(
            current_call_sid,
            event_type="generation_cancelled",
            text=reason,
            level="warning",
        )

    async def _stream_assistant_reply(user_text: str) -> None:
        if runtime is None or selected_provider is None or selected_model is None:
            return

        llm_service = LLMFactory.create(
            provider=selected_provider,
            api_key=settings.google_api_key,
            model=selected_model,
        )
        messages = [{"role": "system", "content": session_instruction or runtime.system_instruction or ""}, *history]
        pending_chunk: str | None = None
        response_chunks: list[str] = []

        try:
            async for chunk in llm_service.chat_stream(
                messages=messages,
                temperature=float(runtime.temperature),
                max_tokens=int(runtime.max_tokens),
            ):
                if not chunk:
                    continue
                response_chunks.append(chunk)
                if pending_chunk is not None:
                    await _send_relay_message({"type": "text", "token": pending_chunk, "last": False})
                pending_chunk = chunk

            full_text = "".join(response_chunks).strip()
            if not full_text:
                full_text = "申し訳ありません。現在応答を生成できません。少し時間をおいてお試しください。"
            if pending_chunk is None:
                pending_chunk = full_text
            await _send_relay_message({"type": "text", "token": pending_chunk, "last": True})

            history.append({"role": "assistant", "content": full_text})
            if len(history) > _TWILIO_CONVERSATIONRELAY_MAX_HISTORY_MESSAGES:
                del history[:-_TWILIO_CONVERSATIONRELAY_MAX_HISTORY_MESSAGES]

            await _append_call_trace(
                current_call_sid,
                event_type="output_transcript",
                text=full_text,
                final=True,
                level="success",
            )
            await _append_bound_messages([{"role": "assistant", "content": full_text}])

            if _is_auto_closing_reply(full_text):
                await _append_call_trace(
                    current_call_sid,
                    event_type="auto_finalize_triggered",
                    text=full_text,
                    level="success",
                )
                await _finalize_bound_call(trigger="closing_phrase", run_extraction=True)
                await _send_relay_message(
                    {
                        "type": "end",
                        "handoffData": json.dumps(
                            {"reasonCode": "closing-phrase", "reason": "AI closing phrase detected"},
                            ensure_ascii=False,
                        ),
                    }
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("ConversationRelay generation failed: %s", exc)
            fallback_text = "申し訳ありません。現在応答を生成できません。少し時間をおいてお試しください。"
            await _append_call_trace(
                current_call_sid,
                event_type="generation_error",
                text=str(exc),
                level="error",
            )
            await _send_relay_message({"type": "text", "token": fallback_text, "last": True})
            history.append({"role": "assistant", "content": fallback_text})
            if len(history) > _TWILIO_CONVERSATIONRELAY_MAX_HISTORY_MESSAGES:
                del history[:-_TWILIO_CONVERSATIONRELAY_MAX_HISTORY_MESSAGES]
            await _append_call_trace(
                current_call_sid,
                event_type="output_transcript",
                text=fallback_text,
                final=True,
                level="warning",
            )
            await _append_bound_messages([{"role": "assistant", "content": fallback_text}])

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue

            message_type = str(payload.get("type") or "").strip()
            if not message_type:
                continue

            if message_type == "setup":
                current_session_id = str(payload.get("sessionId") or "").strip() or None
                current_call_sid = str(payload.get("callSid") or "").strip() or None
                current_from_number = str(payload.get("from") or "").strip() or None
                current_to_number = str(payload.get("to") or "").strip() or None
                custom_parameters = payload.get("customParameters") or {}
                if not isinstance(custom_parameters, dict):
                    custom_parameters = {}
                current_prompt_code = (
                    _normalize_prompt_code_token(custom_parameters.get("prompt_code"))
                    or settings.twilio_default_prompt_code
                    or "base_appointment"
                )
                current_tts_provider = _resolve_twilio_conversationrelay_tts_provider(
                    custom_parameters.get("tts_provider")
                )

                async with AsyncSessionLocal() as db:
                    runtime = await _resolve_prompt_runtime(
                        db=db,
                        prompt_code=current_prompt_code,
                        model_capability="generate",
                    )

                selected_model = require_generate_model(
                    runtime.llm_model,
                    source="Prompt llm_model",
                )
                selected_provider = _resolve_twilio_generate_provider(runtime.llm_provider, selected_model)
                if selected_provider != "gemini":
                    raise RuntimeError(
                        f"ConversationRelay currently supports gemini generate models only. provider={selected_provider}"
                    )
                language_code = (settings.twilio_agent_language or "ja-JP").strip() or "ja-JP"
                defaults_by_language, _, _ = await _load_twilio_conversationrelay_default_voice_settings()
                language_defaults = defaults_by_language.get(language_code) or {}
                current_tts_provider = _resolve_twilio_conversationrelay_tts_provider(
                    current_tts_provider,
                    prompt_voice_provider=runtime.voice_provider,
                    prompt_voice_id=runtime.voice_id,
                    default_provider=language_defaults.get("tts_provider"),
                )
                _, supported_voices, _, default_voice, _ = await _load_twilio_conversationrelay_voice_catalog(
                    provider=current_tts_provider,
                    language_code=language_code,
                )
                default_voice = _resolve_twilio_conversationrelay_default_voice(
                    tts_provider=current_tts_provider,
                    language_code=language_code,
                    supported_voices=supported_voices,
                    default_voice=default_voice,
                )
                current_voice_name = _normalize_twilio_conversationrelay_voice_id(
                    custom_parameters.get("voice_name") or runtime.voice_id,
                    tts_provider=current_tts_provider,
                    language_code=language_code,
                    supported_voices=supported_voices,
                    default_voice=default_voice,
                )
                opening_text = _build_twilio_opening_text(runtime.system_instruction)
                session_instruction = _build_twilio_session_instruction(
                    runtime.system_instruction,
                    opening_text=opening_text,
                )
                history = [{"role": "assistant", "content": opening_text}]
                await _mark_stream_active(current_call_sid)
                await _ensure_bound_call_id()
                await _append_call_trace(
                    current_call_sid,
                    event_type="conversationrelay_setup",
                    text=(
                        f"prompt={runtime.template_code} tts_provider={current_tts_provider} "
                        f"voice={current_voice_name} model={selected_model} provider={selected_provider}"
                    ),
                    level="success",
                )
                await _append_call_trace(
                    current_call_sid,
                    event_type="output_transcript",
                    text=opening_text,
                    final=True,
                    level="success",
                )
                await _append_bound_messages([{"role": "assistant", "content": opening_text}])
                continue

            if message_type == "prompt":
                voice_prompt = str(payload.get("voicePrompt") or "").strip()
                if voice_prompt:
                    prompt_chunks.append(voice_prompt)
                is_last = bool(payload.get("last", False))
                if not is_last:
                    continue

                user_text = "".join(prompt_chunks).strip()
                prompt_chunks.clear()
                if not user_text:
                    continue
                if len(history) <= 1 and _looks_like_opening_echo(user_text, opening_text):
                    await _append_call_trace(
                        current_call_sid,
                        event_type="ignored_opening_echo",
                        text=user_text,
                        final=True,
                        level="warning",
                    )
                    continue

                await _cancel_response_task(reason="new_prompt")
                history.append({"role": "user", "content": user_text})
                if len(history) > _TWILIO_CONVERSATIONRELAY_MAX_HISTORY_MESSAGES:
                    del history[:-_TWILIO_CONVERSATIONRELAY_MAX_HISTORY_MESSAGES]
                await _append_call_trace(
                    current_call_sid,
                    event_type="input_transcript",
                    text=user_text,
                    final=True,
                    level="info",
                )
                await _append_bound_messages([{"role": "user", "content": user_text}])
                response_task = asyncio.create_task(_stream_assistant_reply(user_text))
                continue

            if message_type == "interrupt":
                await _append_call_trace(
                    current_call_sid,
                    event_type="interrupted",
                    text=str(payload.get("utteranceUntilInterrupt") or "").strip() or "Caller interrupted TTS.",
                    level="warning",
                )
                await _cancel_response_task(reason="interrupt")
                continue

            if message_type == "dtmf":
                await _append_call_trace(
                    current_call_sid,
                    event_type="dtmf",
                    text=str(payload.get("digit") or "").strip() or "-",
                    level="info",
                )
                continue

            if message_type == "error":
                await _append_call_trace(
                    current_call_sid,
                    event_type="conversationrelay_error",
                    text=str(payload.get("description") or "").strip() or "Unknown ConversationRelay error.",
                    level="error",
                )
                continue

            if message_type in _CONVERSATIONRELAY_SUPPORTED_DEBUG_MESSAGE_TYPES:
                continue

            await _append_call_trace(
                current_call_sid,
                event_type="conversationrelay_event",
                text=f"type={message_type}",
                level="info",
            )
    except WebSocketDisconnect:
        await _cancel_response_task(reason="websocket_disconnect")
        await _append_call_trace(current_call_sid, event_type="stream_disconnect", level="warning")
        try:
            await _finalize_bound_call(trigger="websocket_disconnect", run_extraction=True)
        except Exception:
            pass
    except Exception as exc:
        await _cancel_response_task(reason="conversationrelay_error")
        await _append_call_trace(
            current_call_sid,
            event_type="stream_error",
            text=str(exc),
            level="error",
        )
        try:
            await _finalize_bound_call(trigger="stream_error", run_extraction=True)
        except Exception:
            pass
        logger.exception("Twilio ConversationRelay bridge failed: %s", exc)
    finally:
        await _mark_stream_inactive(current_call_sid)
        try:
            await websocket.close()
        except Exception:
            pass


@router.websocket("/voice/stream", name="twilio_voice_media_stream")
async def twilio_voice_media_stream(
    websocket: WebSocket,
    prompt_code: str | None = Query(default=None),
    voice_name: str | None = Query(default=None),
):
    await websocket.accept()
    initial_payload: dict[str, object] | None = None
    stream_sid: str | None = None
    current_call_sid: str | None = None
    prompt_code_from_stream = (prompt_code or "").strip() or None
    voice_name_from_stream = _normalize_voice_name_token(voice_name)
    from_number_from_stream: str | None = None
    to_number_from_stream: str | None = None

    while initial_payload is None:
        try:
            raw = await websocket.receive_text()
        except WebSocketDisconnect:
            return

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue

        event_type = str(payload.get("event") or "").strip().lower()
        if event_type in {"connected", "mark"}:
            continue
        if event_type == "stop":
            try:
                await websocket.close()
            except Exception:
                pass
            return
        if event_type != "start":
            continue

        initial_payload = payload
        start_payload = payload.get("start") or {}
        if isinstance(start_payload, dict):
            stream_sid = str(start_payload.get("streamSid") or payload.get("streamSid") or "").strip() or None
            current_call_sid = str(start_payload.get("callSid") or payload.get("callSid") or "").strip() or None
        custom_parameters = _extract_stream_custom_parameters(payload)
        prompt_code_from_stream = custom_parameters.get("prompt_code") or prompt_code_from_stream
        voice_name_from_stream = _normalize_voice_name_token(
            custom_parameters.get("voice_name") or voice_name_from_stream
        )
        from_number_from_stream = (custom_parameters.get("from") or "").strip() or None
        to_number_from_stream = (custom_parameters.get("to") or "").strip() or None

    runtime_notice = None
    async with AsyncSessionLocal() as db:
        runtime = await _resolve_prompt_runtime(db=db, prompt_code=prompt_code_from_stream)
        runtime_notice = runtime.notice

    try:
        selected_model = _resolve_gemini_live_model(runtime.llm_model)
    except ValueError as exc:
        logger.warning(
            "Twilio media stream prompt model incompatible with live engine. prompt=%s error=%s",
            runtime.template_code,
            exc,
        )
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=str(exc)[:120])
        return
    selected_provider = resolve_live_provider(runtime.llm_provider, selected_model)
    available, reason = provider_available(selected_provider)
    if selected_provider != "gemini":
        logger.warning(
            "Twilio media stream provider unsupported. provider=%s model=%s prompt=%s",
            selected_provider,
            selected_model,
            runtime.template_code,
        )
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    if not available:
        logger.warning("Twilio media stream unavailable. provider=%s reason=%s", selected_provider, reason)
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    requested_live_voice = (
        voice_name_from_stream or runtime.voice_id or settings.default_live_voice or "Aoede"
    ).strip() or "Aoede"
    if voice_name_from_stream:
        logger.info(
            "Applying Twilio media stream voice override. prompt=%s override=%s",
            runtime.template_code,
            voice_name_from_stream,
        )
    selected_voice = _normalize_gemini_live_voice_name(
        requested_live_voice,
        voice_provider=runtime.voice_provider,
        default_voice=settings.default_live_voice or "Aoede",
    )
    if selected_voice != requested_live_voice:
        logger.info(
            "Resolved Gemini Live voice for Twilio media stream. requested=%s resolved=%s prompt=%s provider=%s",
            requested_live_voice,
            selected_voice,
            runtime.template_code,
            runtime.voice_provider,
        )
    manual_vad_control = _use_manual_vad_control()
    opening_text = _build_twilio_opening_text(runtime.system_instruction)
    twilio_session_instruction = _build_twilio_session_instruction(runtime.system_instruction, opening_text=None)
    live_config = _build_gemini_live_config(
        model=selected_model,
        system_instruction=twilio_session_instruction,
        voice_name=selected_voice,
        manual_vad=manual_vad_control,
    )
    client = genai.Client(api_key=settings.google_api_key)

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
    finalize_lock = asyncio.Lock()
    bound_call_id = None
    bound_call_finalized = False
    last_completed_assistant_text: str | None = None
    close_after_turn_complete = False
    manual_activity_started = False
    assistant_playback_pending = False
    pending_playback_mark: str | None = None
    outbound_mark_counter = 0
    model_turn_sent_audio = False

    async def _send_twilio_event(payload: dict[str, object]) -> None:
        async with send_lock:
            await websocket.send_text(json.dumps(payload))

    async def _ensure_bound_call_id():
        nonlocal bound_call_id
        if bound_call_id is not None:
            return bound_call_id
        if not current_call_sid:
            return None

        async with AsyncSessionLocal() as db:
            call_repo = CallRepository(db)
            existing_call = await call_repo.get_by_sip_call_id(current_call_sid)
            if existing_call:
                extra_data = dict(existing_call.extra_data or {})
                extra_data.setdefault("source", "twilio_media_stream")
                extra_data.setdefault("transport", "twilio")
                extra_data["template_code"] = runtime.template_code
                extra_data["llm_provider"] = selected_provider
                extra_data["llm_model"] = selected_model
                extra_data["twilio_call_sid"] = current_call_sid
                if stream_sid:
                    extra_data["twilio_stream_sid"] = stream_sid
                existing_call.extra_data = extra_data
                await db.commit()
                await db.refresh(existing_call)
                bound_call_id = existing_call.id
                return bound_call_id

            started_at = now_tokyo_naive()
            created_call = await call_repo.create(
                {
                    "direction": "inbound",
                    "counterpart": (from_number_from_stream or current_call_sid),
                    "caller_name": from_number_from_stream or "Twilio Caller",
                    "status": "ongoing",
                    "handler_type": "ai",
                    "is_answered": True,
                    "started_at": started_at,
                    "answered_at": started_at,
                    "prompt_id": runtime.template.id if runtime.template else None,
                    "sip_call_id": current_call_sid,
                    "sip_from": from_number_from_stream,
                    "sip_to": to_number_from_stream,
                    "extra_data": {
                        "source": "twilio_media_stream",
                        "transport": "twilio",
                        "template_code": runtime.template_code,
                        "llm_provider": selected_provider,
                        "llm_model": selected_model,
                        "twilio_call_sid": current_call_sid,
                        "twilio_stream_sid": stream_sid,
                        "messages": [],
                    },
                    "summary": "Twilio media stream call",
                }
            )
            bound_call_id = created_call.id
            return bound_call_id

    async def _append_bound_messages(messages: list[dict[str, str]]) -> None:
        call_id = await _ensure_bound_call_id()
        if not call_id or not messages:
            return
        async with AsyncSessionLocal() as db:
            service = _build_test_session_service(db)
            await service.append_test_session_messages(
                call_id=call_id,
                messages=messages,
                template_code=runtime.template_code,
                provider=selected_provider,
                model=selected_model,
            )

    async def _finalize_bound_call(*, trigger: str, run_extraction: bool = True) -> None:
        nonlocal bound_call_finalized
        call_id = await _ensure_bound_call_id()
        if not call_id:
            return
        async with finalize_lock:
            if bound_call_finalized:
                return
            try:
                async with AsyncSessionLocal() as db:
                    service = _build_test_session_service(db)
                    result = await service.finalize_test_session(
                        call_id=call_id,
                        template_code=runtime.template_code,
                        run_extraction=run_extraction,
                    )
            except Exception as exc:
                logger.warning(
                    "Failed to finalize Twilio media stream bound call. call_sid=%s trigger=%s error=%s",
                    current_call_sid,
                    trigger,
                    exc,
                )
                await _append_call_trace(
                    current_call_sid,
                    event_type="call_finalize_error",
                    text=str(exc),
                    level="warning",
                )
                return
            bound_call_finalized = True
            await _append_call_trace(
                current_call_sid,
                event_type="call_finalized",
                text=f"trigger={trigger} appointment_id={result.appointment_id or '-'}",
                level="success",
            )

    try:
        async with client.aio.live.connect(model=selected_model, config=live_config) as session:
            logger.info(
                "Twilio media stream connected. provider=%s model=%s voice=%s prompt=%s notice=%s activity_mode=%s",
                selected_provider,
                selected_model,
                selected_voice,
                runtime.template_code,
                runtime_notice,
                "manual" if manual_vad_control else "auto",
            )
            if current_call_sid:
                await _mark_stream_active(current_call_sid)
                twilio_started.set()
                await _ensure_bound_call_id()
                await _append_call_trace(
                    current_call_sid,
                    event_type="stream_start",
                    text=(
                        f"prompt={runtime.template_code or '-'} voice={selected_voice} "
                        f"activity_mode={'manual' if manual_vad_control else 'auto'}"
                    ),
                    level="success",
                )
                opening_suppress_until = time.monotonic() + (_OPENING_STARTUP_SUPPRESS_MS / 1000.0)
                await _append_call_trace(
                    current_call_sid,
                    event_type="opening_turn_requested",
                    text=f"Requested Gemini Live opening greeting: {opening_text}",
                    level="info",
                )
                try:
                    await session.send_realtime_input(
                        text=(
                            "通話が接続されました。"
                            "次の一文を日本語で自然に一度だけ話してください。"
                            f"「{opening_text}」"
                            "この一文以外はまだ話さず、その後は相手の返答を待ってください。"
                        )
                    )
                    await session.send_realtime_input(activity_end=types.ActivityEnd())
                except Exception as exc:
                    await _append_call_trace(
                        current_call_sid,
                        event_type="opening_turn_request_failed",
                        text=str(exc),
                        level="warning",
                    )

            async def twilio_to_live() -> None:
                nonlocal stream_sid
                nonlocal current_call_sid
                nonlocal in_resample_state
                nonlocal assistant_speaking
                nonlocal assistant_playback_pending
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
                nonlocal manual_activity_started
                nonlocal pending_playback_mark
                while True:
                    raw = await websocket.receive_text()
                    try:
                        payload = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    event_type = str(payload.get("event") or "").strip().lower()
                    if event_type == "connected":
                        continue

                    if event_type == "mark":
                        mark_payload = payload.get("mark") or {}
                        if isinstance(mark_payload, dict):
                            mark_name = str(mark_payload.get("name") or "").strip()
                        else:
                            mark_name = ""
                        if mark_name:
                            await _append_call_trace(
                                current_call_sid,
                                event_type="playback_mark",
                                text=mark_name,
                                level="info",
                            )
                        if pending_playback_mark and mark_name == pending_playback_mark:
                            pending_playback_mark = None
                            assistant_playback_pending = False
                            assistant_speaking = False
                            await _append_call_trace(
                                current_call_sid,
                                event_type="playback_complete",
                                text=mark_name or "assistant_audio",
                                level="success",
                            )
                        continue

                    if event_type == "start":
                        start = payload.get("start") or {}
                        stream_sid = str(start.get("streamSid") or payload.get("streamSid") or "").strip() or None
                        current_call_sid = (
                            str(start.get("callSid") or payload.get("callSid") or "").strip() or None
                        )
                        await _mark_stream_active(current_call_sid)
                        twilio_started.set()
                        await _ensure_bound_call_id()
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

                        if assistant_playback_pending:
                            voice_frame_streak = 0
                            pre_roll_frames.clear()
                            if (now_ts - last_media_stats_at) >= 2.0:
                                last_media_stats_at = now_ts
                                await _append_call_trace(
                                    current_call_sid,
                                    event_type="media_stats",
                                    text=(
                                        f"frames={media_frames} rms={rms} threshold={adaptive_threshold} "
                                        "mode=playback_pending"
                                    ),
                                    level="info",
                                )
                            continue

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
                                if not manual_activity_started:
                                    await session.send_realtime_input(activity_start=types.ActivityStart())
                                    manual_activity_started = True
                                for segment in injected_segments:
                                    for packet in _chunk_bytes(segment, 640):
                                        await session.send_realtime_input(
                                            audio=types.Blob(data=packet, mime_type="audio/pcm;rate=16000")
                                        )
                                await session.send_realtime_input(activity_end=types.ActivityEnd())
                                manual_activity_started = False
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
                                    manual_activity_started = False
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
                                if not manual_activity_started:
                                    await session.send_realtime_input(activity_start=types.ActivityStart())
                                    manual_activity_started = True
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
                                manual_activity_started = False
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
                                manual_activity_started = False
                                awaiting_model_response = False
                                awaiting_model_since = None
                                awaiting_model_retry_count = 0
                                awaiting_manual_turn = False
                            if not manual_vad_control:
                                await session.send_realtime_input(audio_stream_end=True)
                        except Exception:
                            pass
                        await _append_call_trace(current_call_sid, event_type="stream_stop", level="info")
                        await _finalize_bound_call(trigger="stream_stop", run_extraction=True)
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
                nonlocal manual_activity_started
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
                                if not manual_activity_started:
                                    await session.send_realtime_input(activity_start=types.ActivityStart())
                                    manual_activity_started = True
                                for segment in injected_segments:
                                    for packet in _chunk_bytes(segment, 640):
                                        await session.send_realtime_input(
                                            audio=types.Blob(data=packet, mime_type="audio/pcm;rate=16000")
                                        )
                                await session.send_realtime_input(activity_end=types.ActivityEnd())
                                manual_activity_started = False
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
                                    manual_activity_started = False
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
                                manual_activity_started = False
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
                        manual_activity_started = False
                        awaiting_model_response = True
                        awaiting_model_since = now_ts
                        awaiting_model_retry_count = 0
                        awaiting_manual_turn = False
                    except Exception:
                        return

            async def live_to_twilio() -> None:
                nonlocal out_resample_state
                nonlocal assistant_speaking
                nonlocal assistant_playback_pending
                nonlocal assistant_last_output_at
                nonlocal awaiting_model_response
                nonlocal awaiting_model_since
                nonlocal awaiting_model_retry_count
                nonlocal awaiting_manual_turn
                nonlocal last_completed_assistant_text
                nonlocal close_after_turn_complete
                nonlocal pending_playback_mark
                nonlocal outbound_mark_counter
                nonlocal model_turn_sent_audio
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
                        if content.input_transcription.finished:
                            await _append_bound_messages(
                                [{"role": "user", "content": content.input_transcription.text}]
                            )

                    if content.output_transcription and content.output_transcription.text:
                        opening_suppress_until = None
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
                        if content.output_transcription.finished:
                            last_completed_assistant_text = content.output_transcription.text
                            close_after_turn_complete = _is_auto_closing_reply(last_completed_assistant_text)
                            await _append_bound_messages(
                                [{"role": "assistant", "content": content.output_transcription.text}]
                            )

                    if content.interrupted and stream_sid:
                        assistant_speaking = False
                        assistant_playback_pending = False
                        opening_suppress_until = None
                        assistant_last_output_at = time.monotonic()
                        awaiting_model_response = False
                        awaiting_model_since = None
                        awaiting_model_retry_count = 0
                        awaiting_manual_turn = False
                        pending_playback_mark = None
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
                            assistant_playback_pending = pending_playback_mark is not None
                            assistant_speaking = False
                            assistant_last_output_at = time.monotonic()
                            awaiting_model_response = False
                            awaiting_model_since = None
                            awaiting_model_retry_count = 0
                            awaiting_manual_turn = False
                            if close_after_turn_complete:
                                await _append_call_trace(
                                    current_call_sid,
                                    event_type="auto_finalize_triggered",
                                    text=last_completed_assistant_text,
                                    level="success",
                                )
                                await _finalize_bound_call(trigger="closing_phrase", run_extraction=True)
                                stream_done.set()
                                try:
                                    await websocket.close()
                                except Exception:
                                    pass
                                return
                        continue

                    for part in content.model_turn.parts:
                        if part.text:
                            await _append_call_trace(
                                current_call_sid,
                                event_type="assistant_meta_text",
                                text=part.text,
                                level="info",
                            )
                            continue

                        inline = part.inline_data
                        if not inline or not inline.data:
                            continue

                        assistant_speaking = True
                        opening_suppress_until = None
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

                        model_turn_sent_audio = True
                        assistant_playback_pending = True
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
                        if stream_sid and model_turn_sent_audio:
                            outbound_mark_counter += 1
                            pending_playback_mark = f"assistant-turn-{outbound_mark_counter}"
                            await _send_twilio_event(
                                {
                                    "event": "mark",
                                    "streamSid": stream_sid,
                                    "mark": {"name": pending_playback_mark},
                                }
                            )
                            await _append_call_trace(
                                current_call_sid,
                                event_type="playback_mark_sent",
                                text=pending_playback_mark,
                                level="info",
                            )
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
                        # Keep inbound listening closed until Twilio confirms playback completion.
                        assistant_playback_pending = pending_playback_mark is not None
                        assistant_speaking = False
                        assistant_last_output_at = time.monotonic()
                        awaiting_model_response = False
                        awaiting_model_since = None
                        awaiting_model_retry_count = 0
                        awaiting_manual_turn = False
                        model_turn_sent_audio = False
                        if close_after_turn_complete:
                            await _append_call_trace(
                                current_call_sid,
                                event_type="auto_finalize_triggered",
                                text=last_completed_assistant_text,
                                level="success",
                            )
                            await _finalize_bound_call(trigger="closing_phrase", run_extraction=True)
                            stream_done.set()
                            try:
                                await websocket.close()
                            except Exception:
                                pass
                            return

            await asyncio.gather(twilio_to_live(), live_to_twilio(), turn_watchdog())
    except WebSocketDisconnect:
        stream_done.set()
        await _append_call_trace(current_call_sid, event_type="stream_disconnect", level="warning")
        try:
            await _finalize_bound_call(trigger="websocket_disconnect", run_extraction=True)
        except Exception:
            pass
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
        try:
            await _finalize_bound_call(trigger="stream_error", run_extraction=True)
        except Exception:
            pass
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
    SessionId: Optional[str] = Form(None),  # noqa: N803
    SessionStatus: Optional[str] = Form(None),  # noqa: N803
    SessionDuration: Optional[str] = Form(None),  # noqa: N803
    HandoffData: Optional[str] = Form(None),  # noqa: N803
    ErrorCode: Optional[str] = Form(None),  # noqa: N803
    ErrorMessage: Optional[str] = Form(None),  # noqa: N803
    To: Optional[str] = Form(None),  # noqa: N803
    From: Optional[str] = Form(None),  # noqa: N803
    Duration: Optional[str] = Form(None),  # noqa: N803
):
    await _verify_webhook_or_raise(request)
    normalized_status = (CallStatus or "").strip().lower()
    if normalized_status in {"completed", "canceled", "failed", "busy", "no-answer"}:
        await twilio_voice_agent_service.clear_session((CallSid or "").strip())
        if (CallSid or "").strip():
            try:
                async with AsyncSessionLocal() as db:
                    call_repo = CallRepository(db)
                    existing_call = await call_repo.get_by_sip_call_id((CallSid or "").strip())
                    if existing_call:
                        service = _build_test_session_service(db)
                        await service.finalize_test_session(
                            call_id=existing_call.id,
                            template_code=(existing_call.extra_data or {}).get("template_code"),
                            run_extraction=True,
                        )
            except Exception as exc:
                logger.warning("Failed to finalize Twilio call on status callback. call_sid=%s error=%s", CallSid, exc)
    if (CallSid or "").strip():
        if (SessionStatus or "").strip():
            await _append_call_trace(
                CallSid,
                event_type="conversationrelay_session_status",
                text=(
                    f"session_status={(SessionStatus or '').strip()} "
                    f"session_id={(SessionId or '').strip() or '-'} "
                    f"duration={(SessionDuration or '').strip() or '-'}"
                ),
                level="info",
            )
        if (ErrorCode or "").strip() or (ErrorMessage or "").strip():
            await _append_call_trace(
                CallSid,
                event_type="conversationrelay_session_error",
                text=(
                    f"code={(ErrorCode or '').strip() or '-'} "
                    f"message={(ErrorMessage or '').strip() or '-'}"
                ),
                level="error",
            )
    logger.info(
        (
            "Twilio status callback. CallSid=%s status=%s session_status=%s "
            "session_id=%s From=%s To=%s Duration=%s SessionDuration=%s ErrorCode=%s ErrorMessage=%s"
        ),
        CallSid,
        CallStatus,
        SessionStatus,
        SessionId,
        From,
        To,
        Duration,
        SessionDuration,
        ErrorCode,
        ErrorMessage,
    )
    return ResponseBase(
        success=True,
        data={
            "call_sid": CallSid,
            "status": CallStatus,
            "session_id": SessionId,
            "session_status": SessionStatus,
            "session_duration": SessionDuration,
            "handoff_data": HandoffData,
            "error_code": ErrorCode,
            "error_message": ErrorMessage,
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
