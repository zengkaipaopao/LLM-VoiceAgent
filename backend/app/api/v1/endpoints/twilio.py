import asyncio
import base64
import json
import logging
import re
import time
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
from fastapi.responses import FileResponse, Response
from google.genai import types
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_api_key
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.model_defaults import require_live_model, resolve_vertex_live_model
from app.exceptions import BusinessException
from app.repositories.call_repository import CallRepository
from app.schemas.base import ResponseBase
from app.schemas.twilio import TwilioTokenResponse
from app.services.chat_service import ChatService
from app.services.google_genai_client import create_google_genai_client
from app.services.live_gateway import (
    provider_available,
    resolve_live_provider,
)
from app.services.prompt_runtime_resolver import PromptRuntimeConfig, resolve_prompt_runtime
from app.services.prompt_service import PromptService
from app.services.test_session_service import TestSessionService
from app.services.twilio.audio_codec import TwilioMediaAudioCodec
from app.services.twilio.debug_audio_capture import RollingPcmCapture
from app.services.twilio.live_config import (
    _build_gemini_live_config,
    _use_manual_vad_control,
    _validate_twilio_activity_mode,
)
from app.services.twilio.media_stream_bootstrap import receive_twilio_media_stream_start
from app.services.twilio.media_stream_state import (
    AssistantPlaybackOverlapBuffer,
    TwilioMediaStreamState,
)
from app.services.twilio.official_conversational_agents import (
    bridge_twilio_to_official_conversational_agents,
    build_official_conversational_agents_config,
    build_official_conversational_agents_stream_parameters,
)
from app.services.twilio.normalizers import (
    _normalize_e164_number,
    _normalize_gemini_live_voice_name,
    _normalize_prompt_code_token,
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
    _enqueue_manual_audio,
    _is_stream_active,
    _list_active_stream_calls,
    _mark_stream_active,
    _mark_stream_inactive,
    _pcm16_audio_stats,
)
from app.services.twilio.trace_diagnostics import build_twilio_trace_diagnostic
from app.services.twilio.trace_store import (
    _append_call_trace,
    _read_call_trace,
    _read_latest_trace_call_sid,
)
from app.services.twilio.twiml_builders import (
    _build_twilio_media_stream_twiml,
    _candidate_websocket_signature_urls,
    _extract_stream_custom_parameters,
    _verify_websocket_or_close,
)
from app.services.twilio.voice_catalog import (
    _extract_twilio_google_voice_names,
    _extract_twilio_tts_voice_ids,
    _load_official_gemini_voices,
)
from app.services.twilio_voice_agent_service import twilio_voice_agent_service
from app.services.twilio_webcall_service import TwilioWebCallService
from app.utils.datetime_utils import now_tokyo_naive
from app.utils.twilio_security import verify_twilio_webhook_request

router = APIRouter()
logger = logging.getLogger(__name__)
_TWILIO_FRAME_BYTES = 160  # 20ms at 8kHz G.711 mu-law
_MEDIA_STATS_INTERVAL_SECONDS = 2.0
_TWILIO_CLOSING_REQUIRED_ALL = ("ご利用ありがとうございます",)
_TWILIO_CLOSING_REQUIRED_ANY = ("承りました", "承知いたしました", "承知しました")
_PCM8K_RAW_DEBUG_VARIANT = "pcm8k_raw"
_PCM16K_RESAMPLED_DEBUG_VARIANT = "pcm16k_resampled"
_PCM8K_RAW_DEBUG_ARTIFACT = "inbound-pcm8k-raw"
_PCM16K_RESAMPLED_DEBUG_ARTIFACT = "inbound-pcm16k-resampled"
_FOLLOWUP_PCM8K_RAW_DEBUG_VARIANT = "followup_pcm8k_raw"
_FOLLOWUP_PCM16K_RESAMPLED_DEBUG_VARIANT = "followup_pcm16k_resampled"
_FOLLOWUP_PCM8K_RAW_DEBUG_ARTIFACT = "followup-pcm8k-raw"
_FOLLOWUP_PCM16K_RESAMPLED_DEBUG_ARTIFACT = "followup-pcm16k-resampled"
_FOLLOWUP_PROBE_RMS_THRESHOLD = 100
_FOLLOWUP_PROBE_MIN_HITS = 2
_DUPLEX_OVERLAP_RMS_THRESHOLD = 180
_DUPLEX_OVERLAP_TRACE_INTERVAL_SECONDS = 1.5
_UPSTREAM_AUDIO_STREAM_END_EVENT = "audio_stream_end_sent"
_OFFICIAL_DEMO_TEMPLATE_CODE = "official_demo_baseline"
__all__ = (
    "_build_gemini_live_config",
    "_build_twilio_media_stream_twiml",
    "_candidate_websocket_signature_urls",
    "_consume_pending_inbound_override_for_number",
    "_extract_stream_custom_parameters",
    "_extract_twilio_google_voice_names",
    "_extract_twilio_tts_voice_ids",
    "_is_auto_closing_reply",
    "_load_official_gemini_voices",
    "_resolve_twilio_inbound_voice_route",
    "_set_pending_inbound_override_for_number",
    "_use_manual_vad_control",
    "_validate_twilio_activity_mode",
)


def _build_debug_capture(*, sample_rate: int, artifact_key: str) -> RollingPcmCapture:
    duration_seconds = max(1, settings.twilio_media_stream_debug_inbound_wav_seconds)
    return RollingPcmCapture(
        sample_rate=sample_rate,
        duration_seconds=duration_seconds,
        artifact_key=artifact_key,
    )


def _build_twilio_inbound_debug_capture(variant: str) -> RollingPcmCapture:
    normalized_variant = (variant or "").strip().lower()
    if normalized_variant == _PCM8K_RAW_DEBUG_VARIANT:
        return _build_debug_capture(sample_rate=8000, artifact_key=_PCM8K_RAW_DEBUG_ARTIFACT)
    if normalized_variant == _PCM16K_RESAMPLED_DEBUG_VARIANT:
        return _build_debug_capture(sample_rate=16000, artifact_key=_PCM16K_RESAMPLED_DEBUG_ARTIFACT)
    if normalized_variant == _FOLLOWUP_PCM8K_RAW_DEBUG_VARIANT:
        return _build_debug_capture(sample_rate=8000, artifact_key=_FOLLOWUP_PCM8K_RAW_DEBUG_ARTIFACT)
    if normalized_variant == _FOLLOWUP_PCM16K_RESAMPLED_DEBUG_VARIANT:
        return _build_debug_capture(
            sample_rate=16000,
            artifact_key=_FOLLOWUP_PCM16K_RESAMPLED_DEBUG_ARTIFACT,
        )
    raise ValueError(f"Unsupported inbound debug audio variant: {variant}")


class TwilioManualAudioInjectRequest(BaseModel):
    call_sid: str = Field(min_length=1)
    audio_base64: str = Field(min_length=1, description="PCM16 mono audio (16kHz) base64 payload.")
    mime_type: str = Field(default="audio/pcm;rate=16000")


class TwilioPrepareIncomingOverrideRequest(BaseModel):
    to_number: str = Field(min_length=1, description="Target Twilio inbound number in E.164 format.")
    prompt_code: str | None = Field(default=None, min_length=1, max_length=64)
    voice_route: str | None = Field(default=None, min_length=1, max_length=64)
    voice_engine: str | None = Field(default="gemini", min_length=1, max_length=32)
    voice_name: str | None = Field(default=None, min_length=1, max_length=128)


def _resolve_gemini_live_model(candidate_model: str | None) -> str:
    resolved = require_live_model(
        candidate_model or settings.default_live_model,
        source="Prompt llm_model",
    )
    if settings.google_vertex_enabled:
        return resolve_vertex_live_model(
            resolved,
            fallback_model=settings.default_live_model,
        )
    return resolved


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


def _require_opening_sentence(*, system_instruction: str | None, template_code: str) -> str:
    opening_text = _extract_opening_sentence(system_instruction)
    if opening_text:
        return opening_text
    raise BusinessException(
        f"Twilio prompt template '{template_code}' must define the first assistant utterance in system prompt."
    )


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
    effective_code = (settings.twilio_default_prompt_code or "").strip()
    prompt_service = PromptService(db)
    requested_code = (prompt_code or "").strip() or effective_code
    if not requested_code:
        raise BusinessException("TWILIO_DEFAULT_PROMPT_CODE is not configured.")

    runtime = await resolve_prompt_runtime(
        prompt_service,
        template_code=requested_code,
        default_code=requested_code,
        fallback_code=None,
        render_system_instruction=True,
        fallback_instruction=None,
        missing_notice=f"Prompt template '{requested_code}' not found or inactive.",
        model_capability=model_capability,
    )
    if runtime.template is None:
        raise BusinessException(f"Prompt template '{requested_code}' not found or inactive.")
    if not (runtime.system_instruction or "").strip():
        raise BusinessException(
            f"Prompt template '{runtime.template_code}' has empty system prompt."
        )
    return runtime


def _is_official_demo_route(route_value: str | None) -> bool:
    return (route_value or "").strip().lower() == "official_demo_live"


def _is_official_conversational_agents_route(route_value: str | None) -> bool:
    return (route_value or "").strip().lower() == "official_conversational_agents"


def _build_official_demo_runtime() -> PromptRuntimeConfig:
    system_instruction = (settings.twilio_official_demo_instruction or "").strip()
    if not system_instruction:
        raise BusinessException(
            "TWILIO_OFFICIAL_DEMO_INSTRUCTION is required for the official baseline demo route."
        )

    configured_model = (settings.twilio_official_demo_model or settings.default_live_model).strip()
    if not configured_model:
        raise BusinessException(
            "TWILIO_OFFICIAL_DEMO_MODEL or DEFAULT_LIVE_MODEL must be configured."
        )

    configured_voice = (
        settings.twilio_official_demo_voice
        or settings.default_live_voice
        or "Aoede"
    ).strip() or "Aoede"

    return PromptRuntimeConfig(
        template=None,
        template_code=_OFFICIAL_DEMO_TEMPLATE_CODE,
        template_name="Official Demo Baseline",
        system_instruction=system_instruction,
        llm_provider="gemini",
        llm_model=configured_model,
        temperature=float(settings.llm_temperature),
        max_tokens=int(settings.llm_max_tokens),
        voice_provider="gemini",
        voice_id=configured_voice,
        notice="Loaded official baseline Twilio demo runtime.",
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
    normalized_voice = _normalize_voice_name_token(payload.voice_name)
    logger.info(
        (
            "Prepared pending inbound override. "
            "to=%s prompt_code=%s voice_route=%s voice_engine=%s voice_name=%s ttl_seconds=%s"
        ),
        normalized_number,
        prompt_token,
        resolved_route,
        resolved_engine,
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
    voice_name: Optional[str] = Form(None),
):
    await _verify_webhook_or_raise(request)
    service = TwilioWebCallService()
    queued_override = await _set_pending_inbound_override_for_number(
        number=To,
        prompt_code=prompt_code,
        voice_route=voice_route,
        voice_engine=voice_engine,
        voice_name=voice_name,
    )
    if queued_override:
        logger.info(
            (
                "Queued pending inbound override for outbound->inbound bridge. "
                "to=%s prompt_code=%s voice_route=%s voice_engine=%s voice_name=%s"
            ),
            _normalize_e164_number(To),
            _normalize_prompt_code_token(prompt_code),
            _normalize_twilio_voice_route(voice_route),
            _normalize_voice_engine(voice_engine),
            _normalize_voice_name_token(voice_name),
        )
    xml = service.build_outbound_twiml(To or "")
    logger.info(
        (
            "Twilio TwiML app webhook called. "
            "CallSid=%s From=%s To=%s prompt_code=%s voice_route=%s voice_engine=%s voice_name=%s"
        ),
        CallSid,
        From,
        To,
        prompt_code,
        voice_route,
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
    voice_route: Optional[str] = Query(
        default=None,
        description=(
            "Inbound AI voice route: gather or official_conversational_agents. "
            "Legacy aliases media_stream_live and official_demo_live are normalized "
            "to official_conversational_agents."
        ),
    ),
    voice_engine: Optional[str] = Query(
        default=None,
        description="Inbound AI voice engine: twilio or gemini.",
    ),
    voice_name: Optional[str] = Query(
        default=None,
        description="Optional Gemini Live voice override.",
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
    pending_voice_name = pending_override.get("voice_name") if pending_override else None
    mode_value = ((mode or settings.twilio_incoming_default_mode or "agent").strip().lower())
    effective_route = voice_route or pending_route
    effective_engine = voice_engine or pending_engine
    route_value = _resolve_twilio_inbound_voice_route(
        voice_route=effective_route,
        voice_engine=effective_engine,
    )
    effective_prompt = prompt_code or pending_prompt
    resolved_prompt_code: str | None
    if _is_official_demo_route(route_value):
        resolved_prompt_code = _OFFICIAL_DEMO_TEMPLATE_CODE
    else:
        resolved_prompt_code = await _resolve_twilio_incoming_prompt_code(
            db=db,
            prompt_code=effective_prompt,
            to_number=To,
        )
    xml: str
    if route_value not in {
        "gather",
        "media_stream_live",
        "official_demo_live",
        "official_conversational_agents",
    }:
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
        if _is_official_conversational_agents_route(route_value):
            try:
                official_ca_config = build_official_conversational_agents_config()
            except ValueError as exc:
                logger.warning(
                    "Twilio inbound official Conversational Agents configuration invalid. error=%s",
                    exc,
                )
                xml = twilio_voice_agent_service.build_hangup_twiml(
                    say_text=(
                        "官方 Conversational Agents 基线未正确配置。"
                        "请检查后端 TWILIO_OFFICIAL_CA_* 配置后重试。"
                    ),
                    language=settings.twilio_agent_language,
                )
                return Response(content=xml, media_type="application/xml")

            extra_parameters = build_official_conversational_agents_stream_parameters(
                official_ca_config
            )
            if official_ca_config.kickstart_text:
                extra_parameters["ca_kickstart_text"] = official_ca_config.kickstart_text
            xml = _build_twilio_media_stream_twiml(
                request=request,
                prompt_code=_OFFICIAL_DEMO_TEMPLATE_CODE,
                from_number=From,
                to_number=To,
                voice_name=None,
                route_name=route_value,
                websocket_endpoint_name="twilio_voice_official_conversational_agents_stream",
                extra_parameters=extra_parameters,
            )
        elif route_value in {"media_stream_live", "official_demo_live"}:
            try:
                if _is_official_demo_route(route_value):
                    runtime = _build_official_demo_runtime()
                else:
                    runtime = await _resolve_prompt_runtime(
                        db=db,
                        prompt_code=resolved_prompt_code,
                        model_capability="live",
                    )
            except BusinessException as exc:
                logger.warning(
                    "Twilio inbound media stream prompt configuration invalid. prompt=%s error=%s",
                    resolved_prompt_code,
                    exc,
                )
                xml = twilio_voice_agent_service.build_hangup_twiml(
                    say_text=(
                        "当前电话 Prompt 或官方基线 Demo 配置无效。"
                        "请检查 Prompt 管理或官方 Demo 环境变量后重试。"
                    ),
                    language=settings.twilio_agent_language,
                )
                return Response(content=xml, media_type="application/xml")
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
                route_name=route_value,
            )
        else:
            try:
                runtime = await _resolve_prompt_runtime(
                    db=db,
                    prompt_code=resolved_prompt_code,
                    model_capability="generate",
                )
                opening_text = _require_opening_sentence(
                    system_instruction=runtime.system_instruction,
                    template_code=runtime.template_code,
                )
            except BusinessException as exc:
                logger.warning(
                    "Twilio gather prompt configuration invalid. prompt=%s error=%s",
                    resolved_prompt_code,
                    exc,
                )
                xml = twilio_voice_agent_service.build_hangup_twiml(
                    say_text="当前电话 Prompt 未正确配置。请在 Prompt 管理中修正模板后重试。",
                    language=settings.twilio_agent_language,
                )
                return Response(content=xml, media_type="application/xml")
            turn_url = str(request.url_for("twilio_voice_agent_turn"))
            action_url = twilio_voice_agent_service.build_turn_action_url(turn_url, runtime.template_code)
            call_sid = (CallSid or "").strip()
            if call_sid:
                await twilio_voice_agent_service.ensure_session(
                    db=db,
                    call_sid=call_sid,
                    prompt_code=runtime.template_code,
                )
            xml = twilio_voice_agent_service.build_gather_twiml(
                say_text=opening_text,
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
                "CallSid=%s To=%s prompt_code=%s voice_route=%s voice_engine=%s voice_name=%s"
            ),
            CallSid,
            _normalize_e164_number(To),
            pending_prompt,
            pending_route,
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

    try:
        reply = await twilio_voice_agent_service.generate_reply(
            db=db,
            call_sid=call_sid,
            prompt_code=resolved_prompt_code,
            user_text=user_text,
        )
    except BusinessException as exc:
        logger.warning(
            "Twilio gather turn prompt configuration invalid. call_sid=%s prompt=%s error=%s",
            call_sid,
            resolved_prompt_code,
            exc,
        )
        xml = twilio_voice_agent_service.build_hangup_twiml(
            say_text="当前电话 Prompt 未正确配置。请在 Prompt 管理中修正模板后重试。",
            language=settings.twilio_agent_language,
        )
        return Response(content=xml, media_type="application/xml")
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
    if not await _verify_websocket_or_close(websocket):
        return
    await websocket.accept()
    bootstrap = await receive_twilio_media_stream_start(
        websocket,
        prompt_code=prompt_code,
        voice_name=voice_name,
    )
    if bootstrap is None:
        return

    stream_sid = bootstrap.stream_sid
    current_call_sid = bootstrap.call_sid
    prompt_code_from_stream = bootstrap.prompt_code
    voice_route_from_stream = bootstrap.voice_route
    voice_name_from_stream = bootstrap.voice_name
    from_number_from_stream = bootstrap.from_number
    to_number_from_stream = bootstrap.to_number

    runtime_notice = None
    try:
        if _is_official_demo_route(voice_route_from_stream):
            runtime = _build_official_demo_runtime()
            runtime_notice = runtime.notice
        else:
            async with AsyncSessionLocal() as db:
                runtime = await _resolve_prompt_runtime(
                    db=db,
                    prompt_code=prompt_code_from_stream,
                    model_capability="live",
                )
                runtime_notice = runtime.notice
    except BusinessException as exc:
        await _append_call_trace(
            current_call_sid,
            event_type="configuration_error",
            text=str(exc),
            level="error",
        )
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=str(exc)[:120])
        return

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
    requested_model = require_live_model(
        runtime.llm_model or settings.default_live_model,
        source="Prompt llm_model",
    )
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
    try:
        _validate_twilio_activity_mode()
    except ValueError as exc:
        await _append_call_trace(
            current_call_sid,
            event_type="configuration_error",
            text=str(exc),
            level="error",
        )
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=str(exc)[:120])
        return

    twilio_session_instruction = _build_twilio_session_instruction(
        runtime.system_instruction,
        opening_text=None,
    )
    live_config = _build_gemini_live_config(
        model=selected_model,
        system_instruction=twilio_session_instruction,
        voice_name=selected_voice,
        manual_vad=False,
    )
    client = create_google_genai_client()

    twilio_started = asyncio.Event()
    live_setup_complete = asyncio.Event()
    stream_done = asyncio.Event()
    state = TwilioMediaStreamState()
    codec = TwilioMediaAudioCodec(
        input_batch_ms=settings.twilio_media_stream_inbound_batch_ms,
        twilio_frame_bytes=_TWILIO_FRAME_BYTES,
        input_noise_gate_enabled=settings.twilio_media_stream_input_noise_gate_enabled,
        input_noise_gate_open_rms=settings.twilio_media_stream_input_noise_gate_open_rms,
        input_noise_gate_close_rms=settings.twilio_media_stream_input_noise_gate_close_rms,
        input_noise_gate_hold_ms=settings.twilio_media_stream_input_noise_gate_hold_ms,
    )
    playback_overlap_buffer = AssistantPlaybackOverlapBuffer(
        sample_rate=16000,
        max_buffer_ms=settings.twilio_media_stream_playback_overlap_buffer_ms,
        trigger_rms=settings.twilio_media_stream_playback_clear_rms,
        min_hits=settings.twilio_media_stream_playback_clear_min_hits,
    )
    inbound_debug_captures = {
        _PCM8K_RAW_DEBUG_VARIANT: _build_twilio_inbound_debug_capture(_PCM8K_RAW_DEBUG_VARIANT),
        _PCM16K_RESAMPLED_DEBUG_VARIANT: _build_twilio_inbound_debug_capture(
            _PCM16K_RESAMPLED_DEBUG_VARIANT
        ),
    }
    followup_debug_captures = {
        _FOLLOWUP_PCM8K_RAW_DEBUG_VARIANT: _build_twilio_inbound_debug_capture(
            _FOLLOWUP_PCM8K_RAW_DEBUG_VARIANT
        ),
        _FOLLOWUP_PCM16K_RESAMPLED_DEBUG_VARIANT: _build_twilio_inbound_debug_capture(
            _FOLLOWUP_PCM16K_RESAMPLED_DEBUG_VARIANT
        ),
    }
    send_lock = asyncio.Lock()
    finalize_lock = asyncio.Lock()
    inbound_debug_capture_lock = asyncio.Lock()
    followup_debug_capture_lock = asyncio.Lock()
    bound_call_id = None
    bound_call_finalized = False
    inbound_debug_capture_saved_variants: set[str] = set()
    followup_probe_armed = False
    followup_probe_started_at = 0.0
    followup_probe_detection_hits = 0
    followup_probe_capture_started = False
    followup_probe_capture_saved = False
    followup_probe_capture_started_at = 0.0
    followup_probe_transcript_observed = False
    last_duplex_overlap_trace_at = 0.0
    playback_pending_barge_in_hits = 0
    local_clear_sent_for_mark: str | None = None
    upstream_pause_started_at: float | None = None
    upstream_audio_stream_closed = False
    upstream_input_segment_active = False
    suppress_assistant_audio_until_turn_complete = False

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

    async def _persist_inbound_debug_wav(*, trigger: str) -> None:
        nonlocal inbound_debug_capture_saved_variants
        if not settings.twilio_media_stream_debug_inbound_wav_enabled:
            return
        if not current_call_sid:
            return

        async with inbound_debug_capture_lock:
            remaining_variants = [
                variant
                for variant, capture in inbound_debug_captures.items()
                if variant not in inbound_debug_capture_saved_variants and capture.has_audio()
            ]
            if not remaining_variants:
                if (
                    not inbound_debug_capture_saved_variants
                    and not any(capture.has_audio() for capture in inbound_debug_captures.values())
                ):
                    inbound_debug_capture_saved_variants = set(inbound_debug_captures.keys())
                    await _append_call_trace(
                        current_call_sid,
                        event_type="inbound_debug_wav_skipped",
                        text=f"trigger={trigger} reason=no_inbound_audio",
                        level="info",
                    )
                return

            saved_audio_items = []
            try:
                for variant in remaining_variants:
                    capture = inbound_debug_captures[variant]
                    saved_audio = await asyncio.to_thread(
                        capture.save_wav,
                        output_dir=settings.twilio_media_stream_debug_inbound_wav_dir,
                        call_sid=current_call_sid,
                    )
                    if saved_audio:
                        inbound_debug_capture_saved_variants.add(variant)
                        saved_audio_items.append((variant, saved_audio))
            except Exception as exc:
                logger.warning(
                    "Failed to persist Twilio inbound debug audio. call_sid=%s trigger=%s error=%s",
                    current_call_sid,
                    trigger,
                    exc,
                )
                await _append_call_trace(
                    current_call_sid,
                    event_type="inbound_debug_wav_error",
                    text=f"trigger={trigger} error={exc}",
                    level="warning",
                )
                return

            if not saved_audio_items:
                await _append_call_trace(
                    current_call_sid,
                    event_type="inbound_debug_wav_skipped",
                    text=f"trigger={trigger} reason=empty_capture",
                    level="info",
                )
                return

            await _append_call_trace(
                current_call_sid,
                event_type="inbound_debug_wav_saved",
                text=" ; ".join(
                    [
                        (
                            f"trigger={trigger} variant={variant} duration_ms={saved_audio.duration_ms} "
                            f"sample_rate={saved_audio.sample_rate} bytes={saved_audio.bytes} "
                            f"path={saved_audio.path}"
                        )
                        for variant, saved_audio in saved_audio_items
                    ]
                ),
                level="success",
            )

    def _reset_followup_probe_captures() -> None:
        for capture in followup_debug_captures.values():
            capture.reset()

    async def _persist_followup_debug_wav(*, trigger: str) -> None:
        nonlocal followup_probe_capture_saved
        nonlocal followup_probe_transcript_observed
        if not settings.twilio_media_stream_debug_inbound_wav_enabled:
            return
        if not current_call_sid:
            return

        async with followup_debug_capture_lock:
            saved_audio_items = []
            try:
                for variant, capture in followup_debug_captures.items():
                    if not capture.has_audio():
                        continue
                    saved_audio = await asyncio.to_thread(
                        capture.save_wav,
                        output_dir=settings.twilio_media_stream_debug_inbound_wav_dir,
                        call_sid=current_call_sid,
                    )
                    if saved_audio:
                        saved_audio_items.append((variant, saved_audio))
            except Exception as exc:
                logger.warning(
                    "Failed to persist Twilio follow-up debug audio. call_sid=%s trigger=%s error=%s",
                    current_call_sid,
                    trigger,
                    exc,
                )
                await _append_call_trace(
                    current_call_sid,
                    event_type="followup_debug_wav_error",
                    text=f"trigger={trigger} error={exc}",
                    level="warning",
                )
                return

            if not saved_audio_items:
                return

            followup_probe_capture_saved = True
            await _append_call_trace(
                current_call_sid,
                event_type="followup_debug_wav_saved",
                text=" ; ".join(
                    [
                        (
                            f"trigger={trigger} variant={variant} duration_ms={saved_audio.duration_ms} "
                            f"sample_rate={saved_audio.sample_rate} bytes={saved_audio.bytes} "
                            f"path={saved_audio.path}"
                        )
                        for variant, saved_audio in saved_audio_items
                    ]
                ),
                level="success",
            )
            if not followup_probe_transcript_observed:
                await _append_call_trace(
                    current_call_sid,
                    event_type="gemini_turn_detection_stalled",
                    text=(
                        f"trigger={trigger} capture_seconds="
                        f"{settings.twilio_media_stream_debug_inbound_wav_seconds} "
                        "followup_audio_detected_but_no_new_input_transcript"
                    ),
                    level="warning",
                )

    async def _arm_followup_probe(*, trigger: str) -> None:
        nonlocal followup_probe_armed
        nonlocal followup_probe_started_at
        nonlocal followup_probe_detection_hits
        nonlocal followup_probe_capture_started
        nonlocal followup_probe_capture_saved
        nonlocal followup_probe_capture_started_at
        nonlocal followup_probe_transcript_observed

        followup_probe_armed = True
        followup_probe_started_at = time.monotonic()
        followup_probe_detection_hits = 0
        followup_probe_capture_started = False
        followup_probe_capture_saved = False
        followup_probe_capture_started_at = 0.0
        followup_probe_transcript_observed = False
        _reset_followup_probe_captures()
        await _append_call_trace(
            current_call_sid,
            event_type="followup_probe_armed",
            text=f"trigger={trigger} rms_threshold={_FOLLOWUP_PROBE_RMS_THRESHOLD}",
            level="info",
        )

    async def _disarm_followup_probe(*, reason: str) -> None:
        nonlocal followup_probe_armed
        nonlocal followup_probe_detection_hits
        nonlocal followup_probe_capture_started
        nonlocal followup_probe_capture_started_at
        nonlocal followup_probe_transcript_observed
        if followup_probe_capture_started and not followup_probe_capture_saved:
            await _persist_followup_debug_wav(trigger=reason)
        followup_probe_armed = False
        followup_probe_detection_hits = 0
        followup_probe_capture_started = False
        followup_probe_capture_started_at = 0.0
        followup_probe_transcript_observed = False

    try:
        async with client.aio.live.connect(model=selected_model, config=live_config) as session:
            logger.info(
                "Twilio media stream connected. provider=%s model=%s voice=%s prompt=%s notice=%s activity_mode=%s",
                selected_provider,
                selected_model,
                selected_voice,
                runtime.template_code,
                runtime_notice,
                "auto",
            )
            if current_call_sid:
                await _mark_stream_active(current_call_sid)
                twilio_started.set()
                await _ensure_bound_call_id()
                if selected_model != requested_model:
                    await _append_call_trace(
                        current_call_sid,
                        event_type="live_model_resolved",
                        text=f"requested={requested_model} resolved={selected_model}",
                        level="warning",
                    )
                await _append_call_trace(
                    current_call_sid,
                    event_type="stream_start",
                    text=(
                        f"prompt={runtime.template_code or '-'} "
                        f"route={voice_route_from_stream or 'media_stream_live'} "
                        f"voice={selected_voice} activity_mode=auto"
                    ),
                    level="success",
                )
                await _append_call_trace(
                    current_call_sid,
                    event_type="live_runtime_config",
                    text=(
                        f"backend={settings.google_genai_backend_mode} "
                        f"modalities={','.join(live_config.response_modalities or [])} "
                        "session_mode=pure_realtime "
                        f"route={voice_route_from_stream or 'media_stream_live'} "
                        f"activity_handling={settings.twilio_gemini_activity_handling} "
                        f"turn_coverage={settings.twilio_gemini_turn_coverage} "
                        f"prefix_padding_ms={settings.twilio_gemini_prefix_padding_ms} "
                        f"silence_duration_ms={settings.twilio_gemini_silence_duration_ms} "
                        "input_gate="
                        f"{'on' if settings.twilio_media_stream_input_noise_gate_enabled else 'off'} "
                        f"gate_open_rms={settings.twilio_media_stream_input_noise_gate_open_rms} "
                        f"gate_close_rms={settings.twilio_media_stream_input_noise_gate_close_rms} "
                        f"gate_hold_ms={settings.twilio_media_stream_input_noise_gate_hold_ms} "
                        f"playback_clear_rms={settings.twilio_media_stream_playback_clear_rms} "
                        f"playback_clear_hits={settings.twilio_media_stream_playback_clear_min_hits} "
                        f"playback_overlap_buffer_ms={settings.twilio_media_stream_playback_overlap_buffer_ms} "
                        f"upstream_activity_rms={settings.twilio_media_stream_upstream_activity_rms} "
                        f"pause_flush_s={settings.twilio_media_stream_pause_flush_seconds} "
                        f"batch_ms={settings.twilio_media_stream_inbound_batch_ms}"
                    ),
                    level="info",
                )

            async def _send_realtime_audio(audio_bytes: bytes) -> None:
                if not audio_bytes:
                    return
                await session.send_realtime_input(
                    audio=types.Blob(data=audio_bytes, mime_type="audio/pcm;rate=16000")
                )

            async def _flush_realtime_audio_buffer() -> None:
                pending_audio = codec.flush_inbound_audio()
                if pending_audio:
                    await _send_realtime_audio(pending_audio)

            async def _close_realtime_input_segment(*, reason: str, conditioned_rms: int | None = None) -> None:
                nonlocal upstream_pause_started_at
                nonlocal upstream_audio_stream_closed
                nonlocal upstream_input_segment_active
                if upstream_audio_stream_closed and not upstream_input_segment_active:
                    return
                await _flush_realtime_audio_buffer()
                await session.send_realtime_input(audio_stream_end=True)
                upstream_audio_stream_closed = True
                upstream_input_segment_active = False
                upstream_pause_started_at = None
                text = f"reason={reason}"
                if conditioned_rms is not None:
                    text = f"{text} conditioned_rms={conditioned_rms}"
                await _append_call_trace(
                    current_call_sid,
                    event_type=_UPSTREAM_AUDIO_STREAM_END_EVENT,
                    text=text,
                    level="info",
                )

            async def _close_after_playback_if_needed() -> bool:
                if not state.close_after_turn_complete:
                    return False
                state.close_after_turn_complete = False
                await _append_call_trace(
                    current_call_sid,
                    event_type="auto_finalize_triggered",
                    text=state.last_completed_assistant_text,
                    level="success",
                )
                await _finalize_bound_call(trigger="closing_phrase", run_extraction=True)
                stream_done.set()
                try:
                    await websocket.close()
                except Exception:
                    pass
                return True

            async def twilio_to_live() -> None:
                nonlocal stream_sid
                nonlocal current_call_sid
                nonlocal followup_probe_armed
                nonlocal followup_probe_detection_hits
                nonlocal followup_probe_capture_started
                nonlocal followup_probe_capture_started_at
                nonlocal last_duplex_overlap_trace_at
                nonlocal playback_pending_barge_in_hits
                nonlocal local_clear_sent_for_mark
                nonlocal upstream_pause_started_at
                nonlocal upstream_audio_stream_closed
                nonlocal upstream_input_segment_active
                nonlocal suppress_assistant_audio_until_turn_complete
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
                        if state.confirm_playback_mark(mark_name):
                            playback_pending_barge_in_hits = 0
                            local_clear_sent_for_mark = None
                            suppress_assistant_audio_until_turn_complete = False
                            playback_overlap_buffer.reset()
                            await _append_call_trace(
                                current_call_sid,
                                event_type="playback_complete",
                                text=mark_name or "assistant_audio",
                                level="success",
                            )
                            if await _close_after_playback_if_needed():
                                return
                            await _arm_followup_probe(trigger=mark_name or "assistant_audio")
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
                            if not state.logged_non_inbound_track:
                                state.logged_non_inbound_track = True
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
                            decoded_audio = codec.decode_twilio_payload(encoded)
                        except Exception:
                            state.decode_fail_count += 1
                            now_ts = time.monotonic()
                            if (now_ts - state.last_decode_error_at) >= _MEDIA_STATS_INTERVAL_SECONDS:
                                state.last_decode_error_at = now_ts
                                await _append_call_trace(
                                    current_call_sid,
                                    event_type="media_decode_error",
                                    text=f"count={state.decode_fail_count}",
                                    level="warning",
                                )
                            continue

                        now_ts = time.monotonic()
                        state.media_frames += 1
                        inbound_debug_captures[_PCM8K_RAW_DEBUG_VARIANT].append(decoded_audio.pcm8k)
                        inbound_debug_captures[_PCM16K_RESAMPLED_DEBUG_VARIANT].append(decoded_audio.pcm16k)
                        if (
                            (state.assistant_speaking or state.assistant_playback_pending)
                            and decoded_audio.rms >= _DUPLEX_OVERLAP_RMS_THRESHOLD
                            and (now_ts - last_duplex_overlap_trace_at)
                            >= _DUPLEX_OVERLAP_TRACE_INTERVAL_SECONDS
                        ):
                            last_duplex_overlap_trace_at = now_ts
                            assistant_phase = (
                                "speaking_and_pending"
                                if state.assistant_speaking and state.assistant_playback_pending
                                else "speaking"
                                if state.assistant_speaking
                                else "playback_pending"
                            )
                            await _append_call_trace(
                                current_call_sid,
                                event_type="duplex_overlap_detected",
                                text=(
                                    f"rms={decoded_audio.rms} assistant_phase={assistant_phase} "
                                    f"pending_mark={state.pending_playback_mark or '-'}"
                                ),
                                level="warning",
                            )
                        if followup_probe_armed:
                            if not followup_probe_capture_started:
                                if decoded_audio.rms >= _FOLLOWUP_PROBE_RMS_THRESHOLD:
                                    followup_probe_detection_hits += 1
                                else:
                                    followup_probe_detection_hits = 0
                                if followup_probe_detection_hits >= _FOLLOWUP_PROBE_MIN_HITS:
                                    followup_probe_capture_started = True
                                    followup_probe_capture_started_at = now_ts
                                    await _append_call_trace(
                                        current_call_sid,
                                        event_type="followup_probe_speech_detected",
                                        text=(
                                            f"rms={decoded_audio.rms} after_ms="
                                            f"{int((now_ts - followup_probe_started_at) * 1000)}"
                                        ),
                                        level="warning",
                                    )
                            if followup_probe_capture_started:
                                followup_debug_captures[_FOLLOWUP_PCM8K_RAW_DEBUG_VARIANT].append(
                                    decoded_audio.pcm8k
                                )
                                followup_debug_captures[
                                    _FOLLOWUP_PCM16K_RESAMPLED_DEBUG_VARIANT
                                ].append(decoded_audio.pcm16k)
                                if (
                                    not followup_probe_capture_saved
                                    and all(capture.is_full for capture in followup_debug_captures.values())
                                ):
                                    await _persist_followup_debug_wav(trigger="followup_probe_full")
                                    followup_probe_armed = False
                                    followup_probe_detection_hits = 0
                                    followup_probe_capture_started = False
                                    followup_probe_capture_started_at = 0.0
                        assistant_active = state.assistant_speaking or state.assistant_playback_pending
                        if assistant_active:
                            pending_mark = (
                                state.pending_playback_mark
                                or ("assistant-speaking" if state.assistant_speaking else "assistant_audio")
                            )
                            barge_in_ready = playback_overlap_buffer.observe(
                                pcm16k=decoded_audio.pcm16k,
                                conditioned_rms=decoded_audio.conditioned_rms,
                            )
                            if stream_sid and barge_in_ready and local_clear_sent_for_mark != pending_mark:
                                local_clear_sent_for_mark = pending_mark
                                playback_pending_barge_in_hits = 0
                                suppress_assistant_audio_until_turn_complete = True
                                state.interrupt(now=now_ts)
                                await _disarm_followup_probe(reason="local_barge_in")
                                await _send_twilio_event({"event": "clear", "streamSid": stream_sid})
                                await _append_call_trace(
                                    current_call_sid,
                                    event_type="local_barge_in_clear_sent",
                                    text=(
                                        f"pending_mark={pending_mark} "
                                        f"conditioned_rms={decoded_audio.conditioned_rms}"
                                    ),
                                    level="warning",
                                )
                                buffered_overlap_audio = playback_overlap_buffer.drain()
                                upstream_pause_started_at = None
                                upstream_input_segment_active = True
                                if upstream_audio_stream_closed:
                                    upstream_audio_stream_closed = False
                                    await _append_call_trace(
                                        current_call_sid,
                                        event_type="audio_stream_resumed",
                                        text=f"conditioned_rms={decoded_audio.conditioned_rms}",
                                        level="info",
                                    )
                                for batch in codec.queue_inbound_audio(buffered_overlap_audio):
                                    await _send_realtime_audio(batch)
                            else:
                                playback_pending_barge_in_hits = 0
                                continue
                        else:
                            playback_pending_barge_in_hits = 0
                            playback_overlap_buffer.reset()

                        has_effective_activity = (
                            decoded_audio.conditioned_rms
                            >= settings.twilio_media_stream_upstream_activity_rms
                        )
                        if has_effective_activity:
                            upstream_pause_started_at = None
                            if not upstream_input_segment_active:
                                upstream_input_segment_active = True
                            if upstream_audio_stream_closed:
                                upstream_audio_stream_closed = False
                                await _append_call_trace(
                                    current_call_sid,
                                    event_type="audio_stream_resumed",
                                    text=f"conditioned_rms={decoded_audio.conditioned_rms}",
                                    level="info",
                                )
                            for batch in codec.queue_inbound_audio(decoded_audio.pcm16k):
                                await _send_realtime_audio(batch)
                        elif upstream_input_segment_active:
                            for batch in codec.queue_inbound_audio(decoded_audio.pcm16k):
                                await _send_realtime_audio(batch)
                            if upstream_pause_started_at is None:
                                upstream_pause_started_at = now_ts
                            if (
                                not upstream_audio_stream_closed
                                and (now_ts - upstream_pause_started_at)
                                >= settings.twilio_media_stream_pause_flush_seconds
                            ):
                                silence_ms = int((now_ts - upstream_pause_started_at) * 1000)
                                await _close_realtime_input_segment(
                                    reason=f"silence_timeout silence_ms={silence_ms}",
                                    conditioned_rms=decoded_audio.conditioned_rms,
                                )
                        else:
                            upstream_pause_started_at = None
                        if (now_ts - state.last_media_stats_at) >= _MEDIA_STATS_INTERVAL_SECONDS:
                            state.last_media_stats_at = now_ts
                            buffer_ms = int(codec.pending_inbound_bytes / 32)
                            await _append_call_trace(
                                current_call_sid,
                                event_type="media_stats",
                                text=(
                                    f"frames={state.media_frames} rms={decoded_audio.rms} "
                                    f"conditioned_rms={decoded_audio.conditioned_rms} "
                                    f"buffer_ms={buffer_ms} mode=auto_stream"
                                ),
                                level="info",
                            )
                        continue

                    if event_type == "stop":
                        try:
                            await _flush_realtime_audio_buffer()
                            await session.send_realtime_input(audio_stream_end=True)
                        except Exception:
                            pass
                        await _append_call_trace(current_call_sid, event_type="stream_stop", level="info")
                        await _disarm_followup_probe(reason="stream_stop")
                        await _persist_inbound_debug_wav(trigger="stream_stop")
                        await _finalize_bound_call(trigger="stream_stop", run_extraction=True)
                        await _mark_stream_inactive(current_call_sid)
                        stream_done.set()
                        return

            async def live_to_twilio() -> None:
                nonlocal followup_probe_transcript_observed
                nonlocal suppress_assistant_audio_until_turn_complete
                nonlocal local_clear_sent_for_mark
                await twilio_started.wait()
                async for message in session.receive():
                    if message.setup_complete:
                        if not state.live_setup_complete:
                            state.mark_live_setup_complete()
                            live_setup_complete.set()
                            await _append_call_trace(
                                current_call_sid,
                                event_type="live_setup_complete",
                                text=f"session_id={message.setup_complete.session_id or '-'}",
                                level="success",
                            )
                            await _append_call_trace(
                                current_call_sid,
                                event_type="session_mode",
                                text="pure_realtime input=RealtimeInput only explicit_client_content=disabled",
                                level="info",
                            )

                    content = message.server_content
                    if not content:
                        continue

                    if content.input_transcription and content.input_transcription.text:
                        state.assistant_last_output_at = time.monotonic()
                        if followup_probe_started_at > 0.0:
                            followup_probe_transcript_observed = True
                        await _append_call_trace(
                            current_call_sid,
                            event_type="input_transcript",
                            text=content.input_transcription.text,
                            final=bool(content.input_transcription.finished),
                            level="info",
                        )
                        if content.input_transcription.finished:
                            await _disarm_followup_probe(reason="input_transcript_finished")
                            await _append_bound_messages(
                                [{"role": "user", "content": content.input_transcription.text}]
                            )

                    if content.output_transcription and content.output_transcription.text:
                        state.assistant_last_output_at = time.monotonic()
                        await _append_call_trace(
                            current_call_sid,
                            event_type="output_transcript",
                            text=content.output_transcription.text,
                            final=bool(content.output_transcription.finished),
                            level="success",
                        )
                        if content.output_transcription.finished:
                            state.last_completed_assistant_text = content.output_transcription.text
                            state.close_after_turn_complete = _is_auto_closing_reply(
                                state.last_completed_assistant_text
                            )
                            await _append_bound_messages(
                                [{"role": "assistant", "content": content.output_transcription.text}]
                            )

                    if content.interrupted and stream_sid:
                        suppress_assistant_audio_until_turn_complete = False
                        local_clear_sent_for_mark = None
                        playback_overlap_buffer.reset()
                        state.interrupt(now=time.monotonic())
                        await _disarm_followup_probe(reason="interrupted")
                        await _send_twilio_event({"event": "clear", "streamSid": stream_sid})
                        await _append_call_trace(
                            current_call_sid,
                            event_type="interrupted",
                            text="Model response interrupted by activity.",
                            level="warning",
                        )

                    if content.model_turn and content.model_turn.parts:
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

                            if followup_probe_armed:
                                await _disarm_followup_probe(reason="assistant_response_started")
                            state.note_assistant_activity(now=time.monotonic(), speaking=True)
                            if suppress_assistant_audio_until_turn_complete:
                                continue
                            if not state.model_turn_sent_audio:
                                await _close_realtime_input_segment(reason="assistant_response_started")
                                await _append_call_trace(
                                    current_call_sid,
                                    event_type="assistant_audio_started",
                                    text=inline.mime_type or "audio/pcm",
                                    level="success",
                                )
                            try:
                                pcm_bytes = (
                                    base64.b64decode(inline.data.encode("ascii"), validate=False)
                                    if isinstance(inline.data, str)
                                    else bytes(inline.data)
                                )
                                frames = codec.encode_model_audio(
                                    pcm_bytes,
                                    mime_type=inline.mime_type,
                                )
                            except Exception as exc:
                                await _append_call_trace(
                                    current_call_sid,
                                    event_type="assistant_audio_encode_error",
                                    text=str(exc),
                                    level="warning",
                                )
                                continue

                            if not stream_sid:
                                continue

                            if not frames:
                                await _append_call_trace(
                                    current_call_sid,
                                    event_type="assistant_audio_empty",
                                    text=(
                                        f"mime_type={inline.mime_type or 'audio/pcm'} "
                                        f"source_bytes={len(pcm_bytes)}"
                                    ),
                                    level="warning",
                                )
                                continue

                            await _append_call_trace(
                                current_call_sid,
                                event_type="assistant_audio_forwarded",
                                text=(
                                    f"mime_type={inline.mime_type or 'audio/pcm'} "
                                    f"source_bytes={len(pcm_bytes)} frames={len(frames)} "
                                    f"payload_bytes={sum(len(frame) for frame in frames)}"
                                ),
                                level="info",
                            )
                            state.mark_model_audio_sent()
                            for frame in frames:
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
                        if suppress_assistant_audio_until_turn_complete:
                            suppress_assistant_audio_until_turn_complete = False
                            local_clear_sent_for_mark = None
                        playback_overlap_buffer.reset()
                        if stream_sid and state.model_turn_sent_audio and not state.pending_playback_mark:
                            playback_mark = state.next_playback_mark()
                            await _send_twilio_event(
                                {
                                    "event": "mark",
                                    "streamSid": stream_sid,
                                    "mark": {"name": playback_mark},
                                }
                            )
                            await _append_call_trace(
                                current_call_sid,
                                event_type="playback_mark_sent",
                                text=playback_mark,
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
                        if not state.model_turn_sent_audio:
                            await _append_call_trace(
                                current_call_sid,
                                event_type="assistant_turn_without_audio",
                                text="Gemini Live completed a turn without emitting audio parts.",
                                level="warning",
                            )
                        state.finalize_turn_playback_state(now=time.monotonic())
                        if await _close_after_playback_if_needed():
                            return

            await asyncio.gather(twilio_to_live(), live_to_twilio())
    except WebSocketDisconnect:
        stream_done.set()
        await _append_call_trace(current_call_sid, event_type="stream_disconnect", level="warning")
        await _disarm_followup_probe(reason="websocket_disconnect")
        await _persist_inbound_debug_wav(trigger="websocket_disconnect")
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
        await _disarm_followup_probe(reason="stream_error")
        await _persist_inbound_debug_wav(trigger="stream_error")
        try:
            await _finalize_bound_call(trigger="stream_error", run_extraction=True)
        except Exception:
            pass
        await _mark_stream_inactive(current_call_sid)
        logger.exception("Twilio media stream bridge failed: %s", exc)
    finally:
        stream_done.set()
        await _disarm_followup_probe(reason="stream_finally")
        await _persist_inbound_debug_wav(trigger="stream_finally")
        await _mark_stream_inactive(current_call_sid)
        try:
            await websocket.close()
        except Exception:
            pass


@router.websocket(
    "/voice/stream/official-ca",
    name="twilio_voice_official_conversational_agents_stream",
)
async def twilio_voice_official_conversational_agents_stream(
    websocket: WebSocket,
    prompt_code: str | None = Query(default=None),
    voice_name: str | None = Query(default=None),
):
    if not await _verify_websocket_or_close(websocket):
        return
    await websocket.accept()
    bootstrap = await receive_twilio_media_stream_start(
        websocket,
        prompt_code=prompt_code,
        voice_name=voice_name,
    )
    if bootstrap is None:
        return
    await bridge_twilio_to_official_conversational_agents(
        websocket=websocket,
        bootstrap=bootstrap,
    )


@router.post("/voice/stream/status", response_model=ResponseBase[dict], name="twilio_voice_stream_status_callback")
async def twilio_voice_stream_status_callback(
    request: Request,
    AccountSid: Optional[str] = Form(None),  # noqa: N803
    CallSid: Optional[str] = Form(None),  # noqa: N803
    StreamSid: Optional[str] = Form(None),  # noqa: N803
    StreamName: Optional[str] = Form(None),  # noqa: N803
    StreamEvent: Optional[str] = Form(None),  # noqa: N803
    StreamError: Optional[str] = Form(None),  # noqa: N803
    Timestamp: Optional[str] = Form(None),  # noqa: N803
):
    await _verify_webhook_or_raise(request)

    stream_event = (StreamEvent or "").strip() or "-"
    stream_error = (StreamError or "").strip()
    level = "info"
    if stream_event == "stream-started":
        level = "success"
    elif stream_event == "stream-stopped":
        level = "warning"
    elif stream_event == "stream-error":
        level = "error"

    await _append_call_trace(
        (CallSid or "").strip() or None,
        event_type="media_stream_status",
        text=(
            f"event={stream_event} stream_sid={(StreamSid or '').strip() or '-'} "
            f"stream_name={(StreamName or '').strip() or '-'} "
            f"timestamp={(Timestamp or '').strip() or '-'} "
            f"account_sid={(AccountSid or '').strip() or '-'}"
            + (f" error={stream_error}" if stream_error else "")
        ),
        level=level,
    )
    return ResponseBase(success=True, data={"ok": True})


@router.post("/voice/status", response_model=ResponseBase[dict])
async def voice_status_callback(
    request: Request,
    CallSid: Optional[str] = Form(None),  # noqa: N803
    CallStatus: Optional[str] = Form(None),  # noqa: N803
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
        if (ErrorCode or "").strip() or (ErrorMessage or "").strip():
            await _append_call_trace(
                CallSid,
                event_type="call_status_error",
                text=(
                    f"code={(ErrorCode or '').strip() or '-'} "
                    f"message={(ErrorMessage or '').strip() or '-'}"
                ),
                level="error",
            )
    logger.info(
        "Twilio status callback. CallSid=%s status=%s From=%s To=%s Duration=%s ErrorCode=%s ErrorMessage=%s",
        CallSid,
        CallStatus,
        From,
        To,
        Duration,
        ErrorCode,
        ErrorMessage,
    )
    return ResponseBase(
        success=True,
        data={
            "call_sid": CallSid,
            "status": CallStatus,
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


@router.get("/voice/trace/diagnostics", response_model=ResponseBase[dict])
async def get_voice_trace_diagnostics(
    _auth: None = Depends(require_api_key),
    call_sid: str = Query(..., min_length=1, description="Twilio call SID"),
):
    events, last_seq = await _read_call_trace(call_sid, 0)
    stream_active = await _is_stream_active(call_sid)
    diagnostic = build_twilio_trace_diagnostic(
        call_sid=call_sid,
        events=events,
        stream_active=stream_active,
    )
    return ResponseBase(
        success=True,
        data={
            **diagnostic,
            "last_seq": last_seq,
            "stream_active": stream_active,
        },
    )


@router.get("/voice/trace/inbound-audio", name="twilio_voice_trace_inbound_audio")
async def get_voice_trace_inbound_audio(
    _auth: None = Depends(require_api_key),
    call_sid: str = Query(..., min_length=1, description="Twilio call SID"),
    variant: str = Query(
        _PCM16K_RESAMPLED_DEBUG_VARIANT,
        description=(
            "Debug audio variant: pcm8k_raw, pcm16k_resampled, "
            "followup_pcm8k_raw, or followup_pcm16k_resampled"
        ),
    ),
):
    try:
        capture = _build_twilio_inbound_debug_capture(variant)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    wav_path = capture.build_output_path(
        output_dir=settings.twilio_media_stream_debug_inbound_wav_dir,
        call_sid=call_sid,
    )
    if not wav_path.exists() or not wav_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inbound debug audio not found.")
    return FileResponse(
        path=str(wav_path),
        media_type="audio/wav",
        filename=wav_path.name,
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
    active_call_details: list[dict[str, object]] = []
    for call_sid in active_calls:
        events, last_seq = await _read_call_trace(call_sid, 0)
        last_event = events[-1] if events else {}
        active_call_details.append(
            {
                "call_sid": call_sid,
                "last_seq": last_seq,
                "event_count": len(events),
                "last_event_type": str(last_event.get("type") or "").strip(),
                "last_event_ts": int(last_event.get("ts") or 0),
                "last_event_text": str(last_event.get("text") or "").strip(),
            }
        )

    active_call_details.sort(
        key=lambda item: (
            int(item.get("last_event_ts") or 0),
            int(item.get("last_seq") or 0),
            str(item.get("call_sid") or ""),
        ),
        reverse=True,
    )
    ordered_active_calls = [str(item["call_sid"]) for item in active_call_details]
    return ResponseBase(
        success=True,
        data={
            "active_calls": ordered_active_calls,
            "active_call_details": active_call_details,
            "latest_call_sid": ordered_active_calls[0] if ordered_active_calls else None,
            "count": len(ordered_active_calls),
        },
    )
