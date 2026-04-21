import asyncio
import base64
import json
import logging
import time

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
from app.services.twilio.live_config import _build_gemini_live_config, _validate_twilio_activity_mode
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
_UPSTREAM_AUDIO_STREAM_END_EVENT = "audio_stream_end_sent"


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
