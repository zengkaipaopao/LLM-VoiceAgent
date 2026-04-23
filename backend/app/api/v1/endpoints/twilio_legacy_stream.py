import asyncio
import base64
import json
import logging
import time
from collections import deque

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from google.genai import types

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.model_defaults import require_live_model
from app.exceptions import BusinessException
from app.repositories.call_repository import CallRepository
from app.services.google_genai_client import create_google_genai_client
from app.services.live_gateway import provider_available, resolve_live_provider
from app.services.twilio.audio_codec import TwilioMediaAudioCodec
from app.services.twilio.debug_audio_runtime import (
    _build_twilio_inbound_debug_capture,
    _FOLLOWUP_PCM16K_RESAMPLED_DEBUG_VARIANT,
    _FOLLOWUP_PCM8K_RAW_DEBUG_VARIANT,
    _PCM16K_RESAMPLED_DEBUG_VARIANT,
    _PCM8K_RAW_DEBUG_VARIANT,
)
from app.services.twilio.live_config import (
    _build_gemini_live_config,
    _resolve_media_stream_bridge_profile,
    _use_manual_vad_control,
    _validate_twilio_activity_mode,
    _validate_twilio_media_stream_bridge_profile,
)
from app.services.twilio.media_stream_bootstrap import receive_twilio_media_stream_start
from app.services.twilio.media_stream_state import (
    AssistantPlaybackOverlapBuffer,
    TwilioMediaStreamState,
)
from app.services.twilio.incoming_route_runtime import build_official_demo_runtime, is_official_demo_route
from app.services.twilio.normalizers import _normalize_gemini_live_voice_name
from app.services.twilio.prompt_runtime_helpers import (
    _build_test_session_service,
    _build_twilio_session_instruction,
    _is_auto_closing_reply,
    _resolve_gemini_live_model,
    _resolve_prompt_runtime,
)
from app.services.twilio.stream_runtime_store import _mark_stream_active, _mark_stream_inactive
from app.services.twilio.trace_store import _append_call_trace
from app.services.twilio.twiml_builders import _verify_websocket_or_close
from app.utils.datetime_utils import now_tokyo_naive

router = APIRouter()
logger = logging.getLogger(__name__)

_TWILIO_FRAME_BYTES = 160  # 20ms at 8kHz G.711 mu-law
_MEDIA_STATS_INTERVAL_SECONDS = 2.0
_FOLLOWUP_PROBE_RMS_THRESHOLD = 100
_FOLLOWUP_PROBE_MIN_HITS = 2
_DUPLEX_OVERLAP_RMS_THRESHOLD = 180
_DUPLEX_OVERLAP_TRACE_INTERVAL_SECONDS = 1.5
_MANUAL_ACTIVITY_PROGRESS_TRACE_INTERVAL_SECONDS = 0.75
_MANUAL_ACTIVITY_SILENCE_RESET_TRACE_MS = 200
_TWILIO_MEDIA_FRAME_MS = 20
_LIVE_AUDIO_STREAM_END = object()
_LIVE_ACTIVITY_START = object()
_LIVE_ACTIVITY_END = object()
_LIVE_AUDIO_QUEUE_MAXSIZE = 64


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
        if is_official_demo_route(voice_route_from_stream):
            runtime = build_official_demo_runtime()
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
        logger.warning(
            "Twilio media stream unavailable. provider=%s reason=%s",
            selected_provider,
            reason,
        )
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
        _validate_twilio_media_stream_bridge_profile()
    except ValueError as exc:
        await _append_call_trace(
            current_call_sid,
            event_type="configuration_error",
            text=str(exc),
            level="error",
        )
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=str(exc)[:120])
        return

    bridge_profile = _resolve_media_stream_bridge_profile()
    requested_manual_vad = _use_manual_vad_control()
    manual_vad = requested_manual_vad and bridge_profile == "legacy_manual"
    cx_agent_studio_bridge = bridge_profile == "cx_agent_studio"
    auto_vad_prefix_padding_ms = 20 if cx_agent_studio_bridge and not manual_vad else settings.twilio_gemini_prefix_padding_ms
    auto_vad_silence_duration_ms = 100 if cx_agent_studio_bridge and not manual_vad else settings.twilio_gemini_silence_duration_ms
    input_noise_gate_enabled = (
        False if cx_agent_studio_bridge else settings.twilio_media_stream_input_noise_gate_enabled
    )
    twilio_session_instruction = _build_twilio_session_instruction(
        runtime.system_instruction,
        opening_text=None,
    )
    live_config = _build_gemini_live_config(
        model=selected_model,
        system_instruction=twilio_session_instruction,
        voice_name=selected_voice,
        manual_vad=manual_vad,
        media_stream_bridge_profile=bridge_profile,
    )
    client = create_google_genai_client()

    twilio_started = asyncio.Event()
    live_setup_complete = asyncio.Event()
    stream_done = asyncio.Event()
    state = TwilioMediaStreamState()
    live_audio_queue: asyncio.Queue[bytes | object] = asyncio.Queue(maxsize=_LIVE_AUDIO_QUEUE_MAXSIZE)
    codec = TwilioMediaAudioCodec(
        input_batch_ms=settings.twilio_media_stream_inbound_batch_ms,
        twilio_frame_bytes=_TWILIO_FRAME_BYTES,
        input_noise_gate_enabled=input_noise_gate_enabled,
        input_noise_gate_open_rms=settings.twilio_media_stream_input_noise_gate_open_rms,
        input_noise_gate_close_rms=settings.twilio_media_stream_input_noise_gate_close_rms,
        input_noise_gate_hold_ms=settings.twilio_media_stream_input_noise_gate_hold_ms,
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
    playback_overlap_buffer = AssistantPlaybackOverlapBuffer(
        sample_rate=16000,
        max_buffer_ms=settings.twilio_media_stream_playback_overlap_buffer_ms,
        trigger_rms=settings.twilio_media_stream_playback_clear_rms,
        min_hits=settings.twilio_media_stream_playback_clear_min_hits,
    )
    local_clear_sent_for_mark: str | None = None
    manual_activity_active = False
    manual_activity_hits = 0
    manual_silence_hits = 0
    manual_activity_started_at = 0.0
    manual_activity_last_trace_at = 0.0
    manual_activity_peak_raw_rms = 0
    manual_activity_lowest_conditioned_rms = 0
    manual_activity_last_raw_rms = 0
    manual_activity_last_conditioned_rms = 0
    manual_prefix_frames = deque[
        bytes
    ](maxlen=max(1, int(settings.twilio_gemini_prefix_padding_ms / _TWILIO_MEDIA_FRAME_MS)))
    manual_start_rms = max(
        int(settings.twilio_media_stream_upstream_activity_rms or 0),
        _FOLLOWUP_PROBE_RMS_THRESHOLD,
    )
    # 电话链路的条件化噪声底通常会维持在 80~100 左右；如果 end threshold 过低，
    # activityEnd 很容易永远发不出去，导致 Gemini Live 一直不提交后续 turn。
    manual_end_rms = max(
        _FOLLOWUP_PROBE_RMS_THRESHOLD,
        min(140, max(manual_start_rms, int(manual_start_rms * 1.1))),
    )
    manual_start_hits_required = 2
    manual_barge_rms = max(900, _DUPLEX_OVERLAP_RMS_THRESHOLD * 4)
    manual_barge_hits_required = 4
    manual_silence_hits_required = max(
        2,
        int(max(0, settings.twilio_gemini_silence_duration_ms) / _TWILIO_MEDIA_FRAME_MS),
    )

    def _reset_manual_activity_runtime() -> None:
        nonlocal manual_activity_started_at
        nonlocal manual_activity_last_trace_at
        nonlocal manual_activity_peak_raw_rms
        nonlocal manual_activity_lowest_conditioned_rms
        nonlocal manual_activity_last_raw_rms
        nonlocal manual_activity_last_conditioned_rms

        manual_activity_started_at = 0.0
        manual_activity_last_trace_at = 0.0
        manual_activity_peak_raw_rms = 0
        manual_activity_lowest_conditioned_rms = 0
        manual_activity_last_raw_rms = 0
        manual_activity_last_conditioned_rms = 0

    def _manual_activity_elapsed_ms(*, now_ts: float | None = None) -> int:
        if manual_activity_started_at <= 0.0:
            return 0
        current_ts = time.monotonic() if now_ts is None else now_ts
        return max(0, int((current_ts - manual_activity_started_at) * 1000))

    def _record_manual_activity_frame(
        *,
        now_ts: float,
        raw_rms: int,
        conditioned_rms: int,
    ) -> None:
        nonlocal manual_activity_peak_raw_rms
        nonlocal manual_activity_lowest_conditioned_rms
        nonlocal manual_activity_last_raw_rms
        nonlocal manual_activity_last_conditioned_rms
        nonlocal manual_activity_started_at

        if manual_activity_started_at <= 0.0:
            manual_activity_started_at = now_ts
        manual_activity_last_raw_rms = max(0, int(raw_rms))
        manual_activity_last_conditioned_rms = max(0, int(conditioned_rms))
        manual_activity_peak_raw_rms = max(manual_activity_peak_raw_rms, manual_activity_last_raw_rms)
        if manual_activity_lowest_conditioned_rms == 0:
            manual_activity_lowest_conditioned_rms = manual_activity_last_conditioned_rms
        else:
            manual_activity_lowest_conditioned_rms = min(
                manual_activity_lowest_conditioned_rms,
                manual_activity_last_conditioned_rms,
            )

    async def _append_manual_activity_trace(
        *,
        event_type: str,
        reason: str,
        level: str = "info",
        now_ts: float | None = None,
        silence_ms: int | None = None,
    ) -> None:
        if not current_call_sid or manual_activity_started_at <= 0.0:
            return
        resolved_now = time.monotonic() if now_ts is None else now_ts
        resolved_silence_ms = (
            manual_silence_hits * _TWILIO_MEDIA_FRAME_MS if silence_ms is None else max(0, silence_ms)
        )
        await _append_call_trace(
            current_call_sid,
            event_type=event_type,
            text=(
                f"reason={reason} elapsed_ms={_manual_activity_elapsed_ms(now_ts=resolved_now)} "
                f"silence_ms={resolved_silence_ms} silence_target_ms="
                f"{manual_silence_hits_required * _TWILIO_MEDIA_FRAME_MS} "
                f"last_raw_rms={manual_activity_last_raw_rms} "
                f"last_conditioned_rms={manual_activity_last_conditioned_rms} "
                f"peak_raw_rms={manual_activity_peak_raw_rms} "
                f"lowest_conditioned_rms={manual_activity_lowest_conditioned_rms} "
                f"end_rms={manual_end_rms}"
            ),
            level=level,
        )

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
                if manual_vad and manual_activity_active:
                    await _append_manual_activity_trace(
                        event_type="manual_activity_end_overdue",
                        reason=f"{trigger}_no_input_transcript",
                        level="warning",
                    )
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

    async def _clear_playback_for_local_barge_in(
        *,
        now_ts: float,
        rms: int,
        conditioned_rms: int,
    ) -> None:
        nonlocal local_clear_sent_for_mark
        if not stream_sid:
            return
        pending_mark = state.pending_playback_mark
        if not pending_mark or local_clear_sent_for_mark == pending_mark:
            return
        buffered_overlap_audio = playback_overlap_buffer.drain()
        local_clear_sent_for_mark = pending_mark
        state.interrupt(now=now_ts, preserve_pending_mark=True)
        codec.clear_outbound_audio()
        await _disarm_followup_probe(reason="local_barge_in_clear")
        await _send_twilio_event({"event": "clear", "streamSid": stream_sid})
        if buffered_overlap_audio:
            await _queue_pcm16k_payload(buffered_overlap_audio)
        await _append_call_trace(
            current_call_sid,
            event_type="local_barge_in_clear_sent",
            text=(
                f"pending_mark={pending_mark} rms={rms} "
                f"conditioned_rms={conditioned_rms} "
                f"replayed_ms={int(len(buffered_overlap_audio) / 32)}"
            ),
            level="warning",
        )

    try:
        async with client.aio.live.connect(model=selected_model, config=live_config) as session:
            logger.info(
                "Twilio media stream connected. provider=%s model=%s voice=%s prompt=%s notice=%s activity_mode=%s bridge_profile=%s",
                selected_provider,
                selected_model,
                selected_voice,
                runtime.template_code,
                runtime_notice,
                "manual" if manual_vad else "auto",
                bridge_profile,
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
                            f"voice={selected_voice} activity_mode={'manual' if manual_vad else 'auto'} "
                            f"bridge_profile={bridge_profile}"
                        ),
                        level="success",
                    )
                effective_activity_handling = (
                    "client_owned"
                    if manual_vad
                    else (
                        "start_of_activity_interrupts"
                        if cx_agent_studio_bridge
                        else (settings.twilio_gemini_activity_handling or "-")
                    )
                )
                effective_turn_coverage = (
                    "client_owned"
                    if manual_vad
                    else (
                        "all_input"
                        if cx_agent_studio_bridge
                        else (settings.twilio_gemini_turn_coverage or "-")
                    )
                )
                interruption_source = (
                    "model_or_local_barge_in"
                    if cx_agent_studio_bridge and not manual_vad
                    else "model_only"
                )
                local_overlap_gate = (
                    "on" if cx_agent_studio_bridge and not manual_vad else "off"
                )
                await _append_call_trace(
                    current_call_sid,
                    event_type="live_runtime_config",
                    text=(
                        f"backend={settings.google_genai_backend_mode} "
                        f"modalities={','.join(live_config.response_modalities or [])} "
                        "session_mode=thin_bridge_realtime "
                        f"route={voice_route_from_stream or 'media_stream_live'} "
                        f"bridge_profile={bridge_profile} "
                        f"requested_activity_mode={'manual' if requested_manual_vad else 'auto'} "
                        f"activity_mode={'manual_explicit_boundaries' if manual_vad else 'auto_server_vad'} "
                        f"activity_handling={effective_activity_handling} "
                        f"turn_coverage={effective_turn_coverage} "
                        f"prefix_padding_ms={auto_vad_prefix_padding_ms} "
                        f"silence_duration_ms={auto_vad_silence_duration_ms} "
                        f"manual_start_rms={manual_start_rms} "
                        f"manual_end_rms={manual_end_rms} "
                        f"manual_barge_rms={manual_barge_rms} "
                        f"input_gate={'on' if input_noise_gate_enabled else 'off'} "
                        f"input_gate_open_rms={settings.twilio_media_stream_input_noise_gate_open_rms} "
                        f"input_gate_close_rms={settings.twilio_media_stream_input_noise_gate_close_rms} "
                        "manual_start_signal=raw_rms "
                        "manual_end_signal=conditioned_rms "
                        f"local_overlap_gate={local_overlap_gate} "
                        f"local_turn_segmentation={'minimal_manual_activity_boundaries' if manual_vad else 'off'} "
                        f"interruption_source={interruption_source} "
                        "upstream_send_loop=queued "
                        "outbound_frame_ms=20 "
                        "outbound_tail_padding=on "
                        f"batch_ms={settings.twilio_media_stream_inbound_batch_ms}"
                    ),
                    level="info",
                )

            async def _queue_realtime_audio(audio_bytes: bytes) -> None:
                if audio_bytes:
                    await live_audio_queue.put(audio_bytes)

            async def _queue_realtime_activity_start() -> None:
                await live_audio_queue.put(_LIVE_ACTIVITY_START)

            async def _queue_realtime_activity_end() -> None:
                await live_audio_queue.put(_LIVE_ACTIVITY_END)

            async def _queue_pcm16k_payload(audio_bytes: bytes) -> None:
                for batch in codec.queue_inbound_audio(audio_bytes):
                    await _queue_realtime_audio(batch)

            async def _send_manual_activity_end(*, reason: str, silence_ms: int | None = None) -> None:
                nonlocal manual_activity_active
                nonlocal manual_activity_hits
                nonlocal manual_silence_hits
                if not manual_vad or not manual_activity_active:
                    manual_activity_hits = 0
                    manual_silence_hits = 0
                    manual_prefix_frames.clear()
                    _reset_manual_activity_runtime()
                    return
                await _flush_realtime_audio_buffer()
                await _queue_realtime_activity_end()
                await _append_manual_activity_trace(
                    event_type="manual_activity_end_sent",
                    reason=reason,
                    silence_ms=silence_ms,
                )
                manual_activity_active = False
                manual_activity_hits = 0
                manual_silence_hits = 0
                manual_prefix_frames.clear()
                _reset_manual_activity_runtime()

            async def _flush_realtime_audio_buffer() -> None:
                pending_audio = codec.flush_inbound_audio()
                if pending_audio:
                    await _queue_realtime_audio(pending_audio)

            async def _start_manual_activity(
                *,
                now_ts: float,
                mode: str,
                threshold: int,
                raw_rms: int,
                conditioned_rms: int,
                prefix_payload: bytes,
            ) -> None:
                nonlocal manual_activity_active
                nonlocal manual_activity_hits
                nonlocal manual_silence_hits
                nonlocal manual_activity_started_at
                nonlocal manual_activity_last_trace_at
                nonlocal manual_activity_peak_raw_rms
                nonlocal manual_activity_lowest_conditioned_rms
                nonlocal manual_activity_last_raw_rms
                nonlocal manual_activity_last_conditioned_rms

                manual_activity_active = True
                manual_activity_hits = 0
                manual_silence_hits = 0
                manual_activity_started_at = now_ts
                manual_activity_last_trace_at = now_ts
                manual_activity_peak_raw_rms = max(0, int(raw_rms))
                manual_activity_lowest_conditioned_rms = max(0, int(conditioned_rms))
                manual_activity_last_raw_rms = max(0, int(raw_rms))
                manual_activity_last_conditioned_rms = max(0, int(conditioned_rms))
                await _queue_realtime_activity_start()
                if prefix_payload:
                    await _queue_pcm16k_payload(prefix_payload)
                await _append_call_trace(
                    current_call_sid,
                    event_type="manual_activity_start_sent",
                    text=(
                        f"raw_rms={raw_rms} conditioned_rms={conditioned_rms} "
                        f"threshold={threshold} end_threshold={manual_end_rms} "
                        f"prefix_ms={settings.twilio_gemini_prefix_padding_ms} mode={mode}"
                    ),
                    level="info",
                )

            async def _close_realtime_audio_input() -> None:
                await _flush_realtime_audio_buffer()
                if manual_vad and manual_activity_active:
                    await _send_manual_activity_end(reason="stream_close")
                await live_audio_queue.put(_LIVE_AUDIO_STREAM_END)

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

            async def live_audio_sender() -> None:
                while True:
                    queued = await live_audio_queue.get()
                    if queued is _LIVE_ACTIVITY_START:
                        await session.send_realtime_input(activity_start=types.ActivityStart())
                        continue
                    if queued is _LIVE_ACTIVITY_END:
                        await session.send_realtime_input(activity_end=types.ActivityEnd())
                        continue
                    if queued is _LIVE_AUDIO_STREAM_END:
                        if not manual_vad:
                            await session.send_realtime_input(audio_stream_end=True)
                        return
                    await session.send_realtime_input(
                        audio=types.Blob(data=queued, mime_type="audio/pcm;rate=16000")
                    )

            async def twilio_to_live() -> None:
                nonlocal stream_sid
                nonlocal current_call_sid
                nonlocal followup_probe_armed
                nonlocal followup_probe_detection_hits
                nonlocal followup_probe_capture_started
                nonlocal followup_probe_capture_started_at
                nonlocal last_duplex_overlap_trace_at
                nonlocal manual_activity_active
                nonlocal manual_activity_hits
                nonlocal manual_silence_hits
                nonlocal manual_activity_last_trace_at
                nonlocal local_clear_sent_for_mark
                try:
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
                                replay_after_clear = local_clear_sent_for_mark == mark_name
                                buffered_overlap_audio = (
                                    playback_overlap_buffer.drain() if replay_after_clear else b""
                                )
                                local_clear_sent_for_mark = None
                                if not replay_after_clear:
                                    playback_overlap_buffer.reset()
                                if buffered_overlap_audio:
                                    await _queue_pcm16k_payload(buffered_overlap_audio)
                                await _append_call_trace(
                                    current_call_sid,
                                    event_type="playback_complete",
                                    text=mark_name or "assistant_audio",
                                    level="success",
                                )
                                if buffered_overlap_audio:
                                    await _append_call_trace(
                                        current_call_sid,
                                        event_type="local_barge_in_buffer_replayed",
                                        text=(
                                            f"mark={mark_name} replayed_ms="
                                            f"{int(len(buffered_overlap_audio) / 32)}"
                                        ),
                                        level="info",
                                    )
                                if await _close_after_playback_if_needed():
                                    return
                                await _arm_followup_probe(trigger=mark_name or "assistant_audio")
                            continue

                        if event_type == "start":
                            start = payload.get("start") or {}
                            stream_sid = (
                                str(start.get("streamSid") or payload.get("streamSid") or "").strip()
                                or None
                            )
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
                                if (
                                    now_ts - state.last_decode_error_at
                                ) >= _MEDIA_STATS_INTERVAL_SECONDS:
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
                            inbound_debug_captures[_PCM16K_RESAMPLED_DEBUG_VARIANT].append(
                                decoded_audio.pcm16k
                            )
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
                            playback_locked = state.assistant_speaking or state.assistant_playback_pending
                            hold_for_local_overlap_gate = False
                            if (
                                cx_agent_studio_bridge
                                and not manual_vad
                                and playback_locked
                            ):
                                # For the CX-style bridge, overlap frames are held locally first.
                                # We only forward them upstream after a real barge-in is confirmed
                                # and Twilio playback has been cleared.
                                hold_for_local_overlap_gate = True
                                if playback_overlap_buffer.observe(
                                    pcm16k=decoded_audio.pcm16k,
                                    conditioned_rms=decoded_audio.conditioned_rms,
                                ):
                                    await _clear_playback_for_local_barge_in(
                                        now_ts=now_ts,
                                        rms=decoded_audio.rms,
                                        conditioned_rms=decoded_audio.conditioned_rms,
                                    )
                            elif not playback_locked:
                                playback_overlap_buffer.reset()
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
                                        and all(
                                            capture.is_full
                                            for capture in followup_debug_captures.values()
                                        )
                                    ):
                                        await _persist_followup_debug_wav(
                                            trigger="followup_probe_full"
                                        )
                                        followup_probe_armed = False
                                        followup_probe_detection_hits = 0
                                        followup_probe_capture_started = False
                                        followup_probe_capture_started_at = 0.0
                            if manual_vad:
                                if playback_locked and not manual_activity_active:
                                    if decoded_audio.rms >= manual_barge_rms:
                                        manual_prefix_frames.append(decoded_audio.pcm16k)
                                        manual_activity_hits += 1
                                    else:
                                        manual_activity_hits = 0
                                        manual_prefix_frames.clear()

                                    if manual_activity_hits >= manual_barge_hits_required:
                                        prefix_payload = b"".join(manual_prefix_frames)
                                        manual_prefix_frames.clear()
                                        await _start_manual_activity(
                                            now_ts=now_ts,
                                            mode="barge_in_during_playback",
                                            threshold=manual_barge_rms,
                                            raw_rms=decoded_audio.rms,
                                            conditioned_rms=decoded_audio.conditioned_rms,
                                            prefix_payload=prefix_payload,
                                        )
                                elif not playback_locked and not manual_activity_active:
                                    manual_prefix_frames.append(decoded_audio.pcm16k)
                                    if decoded_audio.rms >= manual_start_rms:
                                        manual_activity_hits += 1
                                    else:
                                        manual_activity_hits = 0

                                    if manual_activity_hits >= manual_start_hits_required:
                                        prefix_payload = b"".join(manual_prefix_frames)
                                        manual_prefix_frames.clear()
                                        await _start_manual_activity(
                                            now_ts=now_ts,
                                            mode="normal_after_playback",
                                            threshold=manual_start_rms,
                                            raw_rms=decoded_audio.rms,
                                            conditioned_rms=decoded_audio.conditioned_rms,
                                            prefix_payload=prefix_payload,
                                        )
                                elif manual_activity_active:
                                    await _queue_pcm16k_payload(decoded_audio.pcm16k)
                                    _record_manual_activity_frame(
                                        now_ts=now_ts,
                                        raw_rms=decoded_audio.rms,
                                        conditioned_rms=decoded_audio.conditioned_rms,
                                    )
                                    if decoded_audio.conditioned_rms >= manual_end_rms:
                                        silence_ms_before_reset = (
                                            manual_silence_hits * _TWILIO_MEDIA_FRAME_MS
                                        )
                                        if (
                                            manual_silence_hits > 0
                                            and silence_ms_before_reset
                                            >= _MANUAL_ACTIVITY_SILENCE_RESET_TRACE_MS
                                        ):
                                            await _append_manual_activity_trace(
                                                event_type="manual_activity_silence_reset",
                                                reason="voice_energy_resumed_before_timeout",
                                                now_ts=now_ts,
                                                silence_ms=silence_ms_before_reset,
                                            )
                                        manual_silence_hits = 0
                                    else:
                                        manual_silence_hits += 1
                                    if (
                                        (now_ts - manual_activity_last_trace_at)
                                        >= _MANUAL_ACTIVITY_PROGRESS_TRACE_INTERVAL_SECONDS
                                    ):
                                        manual_activity_last_trace_at = now_ts
                                        await _append_manual_activity_trace(
                                            event_type="manual_activity_progress",
                                            reason="awaiting_end_boundary",
                                            now_ts=now_ts,
                                        )
                                    if manual_silence_hits >= manual_silence_hits_required:
                                        await _send_manual_activity_end(
                                            reason="silence_timeout",
                                            silence_ms=manual_silence_hits * _TWILIO_MEDIA_FRAME_MS,
                                        )
                                else:
                                    manual_activity_hits = 0
                                    manual_silence_hits = 0
                                    manual_prefix_frames.clear()
                                    _reset_manual_activity_runtime()
                            else:
                                if not hold_for_local_overlap_gate:
                                    for batch in codec.queue_inbound_audio(decoded_audio.pcm16k):
                                        await _queue_realtime_audio(batch)
                            if (now_ts - state.last_media_stats_at) >= _MEDIA_STATS_INTERVAL_SECONDS:
                                state.last_media_stats_at = now_ts
                                buffer_ms = int(codec.pending_inbound_bytes / 32)
                                await _append_call_trace(
                                    current_call_sid,
                                    event_type="media_stats",
                                    text=(
                                        f"frames={state.media_frames} rms={decoded_audio.rms} "
                                        f"conditioned_rms={decoded_audio.conditioned_rms} "
                                        f"buffer_ms={buffer_ms} mode=thin_bridge_stream"
                                    ),
                                    level="info",
                                )
                            continue

                        if event_type == "stop":
                            try:
                                await _close_realtime_audio_input()
                            except Exception:
                                pass
                            await _append_call_trace(
                                current_call_sid, event_type="stream_stop", level="info"
                            )
                            await _disarm_followup_probe(reason="stream_stop")
                            await _persist_inbound_debug_wav(trigger="stream_stop")
                            await _finalize_bound_call(trigger="stream_stop", run_extraction=True)
                            await _mark_stream_inactive(current_call_sid)
                            stream_done.set()
                            return
                except WebSocketDisconnect:
                    try:
                        await _close_realtime_audio_input()
                    except Exception:
                        pass
                    raise

            async def live_to_twilio() -> None:
                nonlocal followup_probe_transcript_observed
                nonlocal manual_activity_active
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
                        state.interrupt(
                            now=time.monotonic(),
                            preserve_pending_mark=bool(state.pending_playback_mark),
                        )
                        codec.clear_outbound_audio()
                        await _disarm_followup_probe(reason="interrupted")
                        await _send_twilio_event({"event": "clear", "streamSid": stream_sid})
                        await _append_call_trace(
                            current_call_sid,
                            event_type="interrupted",
                            text="Model response interrupted by activity.",
                            level="warning",
                        )
                        playback_overlap_buffer.reset()
                        local_clear_sent_for_mark = None

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
                            if manual_vad and manual_activity_active:
                                await _send_manual_activity_end(reason="assistant_response_started")
                            playback_overlap_buffer.reset()
                            local_clear_sent_for_mark = None
                            state.note_assistant_activity(now=time.monotonic(), speaking=True)
                            if not state.model_turn_sent_audio:
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

                            if frames:
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
                        if stream_sid:
                            tail_frames = codec.flush_outbound_audio(pad_to_frame=True)
                            if tail_frames:
                                await _append_call_trace(
                                    current_call_sid,
                                    event_type="assistant_audio_tail_flushed",
                                    text=(
                                        f"frames={len(tail_frames)} "
                                        f"payload_bytes={sum(len(frame) for frame in tail_frames)}"
                                    ),
                                    level="info",
                                )
                                state.mark_model_audio_sent()
                                for frame in tail_frames:
                                    await _send_twilio_event(
                                        {
                                            "event": "media",
                                            "streamSid": stream_sid,
                                            "media": {
                                                "payload": base64.b64encode(frame).decode("ascii"),
                                            },
                                        }
                                    )
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

            await asyncio.gather(live_audio_sender(), twilio_to_live(), live_to_twilio())
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
