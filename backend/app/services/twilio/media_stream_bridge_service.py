from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

from fastapi import WebSocket, WebSocketDisconnect
from google.genai import types

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.repositories.call_repository import CallRepository
from app.services.google_genai_client import create_google_genai_client
from app.services.prompt_runtime_resolver import PromptRuntimeConfig
from app.services.twilio.business_close_service import TwilioBusinessCloseService
from app.services.twilio.assistant_playback_policy import AssistantPlaybackPolicyService
from app.services.twilio.audio_codec import TwilioMediaAudioCodec
from app.services.twilio.debug_audio_runtime import (
    _FOLLOWUP_PCM16K_RESAMPLED_DEBUG_VARIANT,
    _FOLLOWUP_PCM8K_RAW_DEBUG_VARIANT,
    _PCM16K_RESAMPLED_DEBUG_VARIANT,
    _PCM8K_RAW_DEBUG_VARIANT,
    _build_twilio_inbound_debug_capture,
)
from app.services.twilio.gemini_live_receive_adapter import (
    GeminiAssistantAudioEvent,
    GeminiAssistantMetaTextEvent,
    GeminiInputTranscriptEvent,
    GeminiInterruptedEvent,
    GeminiLiveReceiveAdapter,
    GeminiLiveSetupCompleteEvent,
    GeminiOutputTranscriptEvent,
    GeminiTurnCompleteEvent,
)
from app.services.twilio.gemini_live_session_adapter import GeminiLiveSessionAdapter
from app.services.twilio.manual_activity_bridge_service import (
    TwilioManualActivityBridgeService,
)
from app.services.twilio.manual_activity_controller import TwilioManualActivityController
from app.services.twilio.media_stream_observer import TwilioMediaStreamObserver
from app.services.twilio.media_stream_observer_bridge_service import (
    TwilioMediaStreamObserverBridgeService,
)
from app.services.twilio.media_stream_runtime import TwilioMediaStreamRuntimeConfig
from app.services.twilio.media_stream_state import TwilioMediaStreamState
from app.services.twilio.stream_lifecycle_service import TwilioStreamLifecycleService
from app.services.twilio.twilio_playback_adapter import TwilioPlaybackAdapter
from app.services.twilio.twilio_ingress_adapter import (
    TwilioIngressAdapter,
    TwilioMarkEvent,
    TwilioMediaDecodeErrorEvent,
    TwilioMediaEvent,
    TwilioMediaTrackIgnoredEvent,
    TwilioStartEvent,
    TwilioStopEvent,
)
from app.services.twilio.prompt_runtime_helpers import (
    _build_test_session_service,
    _is_auto_closing_reply,
)
from app.services.twilio.stream_runtime_store import _mark_stream_active, _mark_stream_inactive
from app.services.twilio.trace_store import _append_call_trace
from app.utils.datetime_utils import now_tokyo_naive

logger = logging.getLogger(__name__)

_TWILIO_FRAME_BYTES = 160
_MEDIA_STATS_INTERVAL_SECONDS = 2.0
_FOLLOWUP_PROBE_RMS_THRESHOLD = 100
_FOLLOWUP_PROBE_MIN_HITS = 2
_DUPLEX_OVERLAP_RMS_THRESHOLD = 180
_DUPLEX_OVERLAP_TRACE_INTERVAL_SECONDS = 1.5
_MANUAL_ACTIVITY_PROGRESS_TRACE_INTERVAL_SECONDS = 0.75
_MANUAL_ACTIVITY_SILENCE_RESET_TRACE_MS = 200
_TWILIO_MEDIA_FRAME_MS = 20
_LIVE_AUDIO_QUEUE_MAXSIZE = 64


@dataclass(slots=True)
class TwilioMediaStreamBridgeContext:
    websocket: WebSocket
    stream_sid: str | None
    current_call_sid: str | None
    voice_route_from_stream: str | None
    from_number_from_stream: str | None
    to_number_from_stream: str | None
    runtime: PromptRuntimeConfig
    runtime_notice: str | None
    requested_model: str
    selected_model: str
    selected_provider: str
    selected_voice: str
    bridge_profile: str
    requested_manual_vad: bool
    bridge_runtime: TwilioMediaStreamRuntimeConfig
    live_config: types.LiveConnectConfig


async def run_twilio_media_stream_bridge(context: TwilioMediaStreamBridgeContext) -> None:
    websocket = context.websocket
    stream_sid = context.stream_sid
    current_call_sid = context.current_call_sid
    bridge_profile_contract = context.bridge_runtime.bridge_profile_contract
    legacy_manual_vad = context.bridge_runtime.legacy_manual_vad
    half_duplex_manual_turn_control = context.bridge_runtime.half_duplex_manual_turn_control
    manual_activity_control = context.bridge_runtime.manual_activity_control

    client = create_google_genai_client()
    twilio_started = asyncio.Event()
    live_setup_complete = asyncio.Event()
    stream_done = asyncio.Event()
    state = TwilioMediaStreamState()
    codec = TwilioMediaAudioCodec(
        input_batch_ms=context.bridge_runtime.inbound_batch_ms,
        twilio_frame_bytes=_TWILIO_FRAME_BYTES,
        input_noise_gate_enabled=context.bridge_runtime.input_noise_gate_enabled,
        input_noise_gate_open_rms=context.bridge_runtime.input_gate_open_rms,
        input_noise_gate_close_rms=context.bridge_runtime.input_gate_close_rms,
        input_noise_gate_hold_ms=context.bridge_runtime.input_noise_gate_hold_ms,
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
    finalize_lock = asyncio.Lock()
    bound_call_id = None
    bound_call_finalized = False
    playback = TwilioPlaybackAdapter(websocket=websocket, stream_sid=stream_sid)
    ingress = TwilioIngressAdapter(websocket=websocket, codec=codec)
    observer = TwilioMediaStreamObserver(
        call_sid=current_call_sid,
        debug_wav_enabled=settings.twilio_media_stream_debug_inbound_wav_enabled,
        debug_output_dir=settings.twilio_media_stream_debug_inbound_wav_dir,
        followup_capture_seconds=settings.twilio_media_stream_debug_inbound_wav_seconds,
        followup_rms_threshold=_FOLLOWUP_PROBE_RMS_THRESHOLD,
        followup_min_hits=_FOLLOWUP_PROBE_MIN_HITS,
        inbound_debug_captures=inbound_debug_captures,
        followup_debug_captures=followup_debug_captures,
    )
    last_duplex_overlap_trace_at = 0.0
    manual_activity_controller = TwilioManualActivityController(
        frame_ms=_TWILIO_MEDIA_FRAME_MS,
        prefix_padding_ms=context.bridge_runtime.effective_prefix_padding_ms,
        start_rms=context.bridge_runtime.manual_start_rms,
        end_rms=context.bridge_runtime.manual_end_rms,
        start_hits_required=context.bridge_runtime.manual_start_hits_required,
        barge_rms=context.bridge_runtime.manual_barge_rms,
        barge_hits_required=context.bridge_runtime.manual_barge_hits_required,
        silence_hits_required=context.bridge_runtime.manual_silence_hits_required,
        silence_reset_trace_ms=_MANUAL_ACTIVITY_SILENCE_RESET_TRACE_MS,
        progress_trace_interval_seconds=_MANUAL_ACTIVITY_PROGRESS_TRACE_INTERVAL_SECONDS,
    )

    async def _append_manual_activity_trace(
        *,
        event_type: str,
        reason: str,
        level: str = "info",
        now_ts: float | None = None,
        silence_ms: int | None = None,
    ) -> None:
        if not current_call_sid:
            return
        trace_text = manual_activity_controller.build_trace_text(
            reason=reason,
            now_ts=now_ts,
            silence_ms=silence_ms,
        )
        if not trace_text:
            return
        await _append_call_trace(
            current_call_sid,
            event_type=event_type,
            text=trace_text,
            level=level,
        )

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
                extra_data["template_code"] = context.runtime.template_code
                extra_data["llm_provider"] = context.selected_provider
                extra_data["llm_model"] = context.selected_model
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
                    "counterpart": (context.from_number_from_stream or current_call_sid),
                    "caller_name": context.from_number_from_stream or "Twilio Caller",
                    "status": "ongoing",
                    "handler_type": "ai",
                    "is_answered": True,
                    "started_at": started_at,
                    "answered_at": started_at,
                    "prompt_id": context.runtime.template.id if context.runtime.template else None,
                    "sip_call_id": current_call_sid,
                    "sip_from": context.from_number_from_stream,
                    "sip_to": context.to_number_from_stream,
                    "extra_data": {
                        "source": "twilio_media_stream",
                        "transport": "twilio",
                        "template_code": context.runtime.template_code,
                        "llm_provider": context.selected_provider,
                        "llm_model": context.selected_model,
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
                template_code=context.runtime.template_code,
                provider=context.selected_provider,
                model=context.selected_model,
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
                        template_code=context.runtime.template_code,
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

    async def _on_assistant_response_started(
        observer_bridge: TwilioMediaStreamObserverBridgeService,
        manual_activity: TwilioManualActivityBridgeService,
    ) -> None:
        # TODO(media-stream-v2): 把 assistant_response_started 的跨层协调
        # 从 bridge service 继续抽成独立 orchestration service，
        # 避免 observer bridge / manual activity bridge / playback policy 在这里重新汇合。
        if observer_bridge.followup_probe_armed:
            await observer_bridge.disarm_followup_probe("assistant_response_started")
        if manual_activity_control and manual_activity.active:
            await manual_activity.send_end(
                current_call_sid=current_call_sid,
                reason="assistant_response_started",
            )

    playback_policy = AssistantPlaybackPolicyService(
        state=state,
        codec=codec,
        playback=playback,
        append_trace=_append_call_trace,
    )
    observer_bridge = TwilioMediaStreamObserverBridgeService(
        observer=observer,
        append_trace=_append_call_trace,
        append_manual_activity_trace=_append_manual_activity_trace,
        manual_activity_control=manual_activity_control,
        manual_activity_active_getter=lambda: manual_activity_controller.active,
    )
    business_close = TwilioBusinessCloseService(
        state=state,
        append_trace=_append_call_trace,
        finalize_bound_call=_finalize_bound_call,
        close_websocket=websocket.close,
        stream_done=stream_done,
    )

    lifecycle = TwilioStreamLifecycleService(
        observer=observer_bridge,
        append_trace=_append_call_trace,
        finalize_bound_call=_finalize_bound_call,
        mark_stream_inactive=_mark_stream_inactive,
        close_websocket=websocket.close,
        stream_done=stream_done,
    )

    try:
        async with client.aio.live.connect(model=context.selected_model, config=context.live_config) as session:
            logger.info(
                "Twilio media stream connected. provider=%s model=%s voice=%s prompt=%s notice=%s activity_mode=%s bridge_profile=%s",
                context.selected_provider,
                context.selected_model,
                context.selected_voice,
                context.runtime.template_code,
                context.runtime_notice,
                context.bridge_runtime.activity_mode_log_label,
                context.bridge_profile,
            )
            if current_call_sid:
                await _mark_stream_active(current_call_sid)
                twilio_started.set()
                await _ensure_bound_call_id()
                if context.selected_model != context.requested_model:
                    await _append_call_trace(
                        current_call_sid,
                        event_type="live_model_resolved",
                        text=f"requested={context.requested_model} resolved={context.selected_model}",
                        level="warning",
                    )
                await _append_call_trace(
                    current_call_sid,
                    event_type="stream_start",
                    text=(
                        f"prompt={context.runtime.template_code or '-'} "
                        f"route={context.voice_route_from_stream or 'media_stream_live'} "
                        f"voice={context.selected_voice} activity_mode={context.bridge_runtime.activity_mode_log_label} "
                        f"bridge_profile={context.bridge_profile}"
                    ),
                    level="success",
                )
                await _append_call_trace(
                    current_call_sid,
                    event_type="live_runtime_config",
                    text=(
                        f"backend={settings.google_genai_backend_mode} "
                        f"modalities={','.join(context.live_config.response_modalities or [])} "
                        "session_mode=thin_bridge_realtime "
                        f"route={context.voice_route_from_stream or 'media_stream_live'} "
                        f"bridge_profile={context.bridge_profile} "
                        f"turn_owner={bridge_profile_contract.turn_owner} "
                        f"duplex_mode={bridge_profile_contract.duplex_mode} "
                        f"overlap_policy={bridge_profile_contract.overlap_policy} "
                        f"requested_activity_mode={'manual' if context.requested_manual_vad else 'auto'} "
                        f"activity_mode={context.bridge_runtime.trace_activity_mode} "
                        f"activity_handling={context.bridge_runtime.effective_activity_handling} "
                        f"turn_coverage={context.bridge_runtime.effective_turn_coverage} "
                        f"prefix_padding_ms={context.bridge_runtime.effective_prefix_padding_ms} "
                        f"silence_duration_ms={context.bridge_runtime.effective_silence_duration_ms} "
                        f"manual_start_rms={manual_activity_controller.start_rms} "
                        f"manual_end_rms={manual_activity_controller.end_rms} "
                        f"manual_barge_rms={manual_activity_controller.barge_rms} "
                        f"input_gate={'on' if context.bridge_runtime.input_noise_gate_enabled else 'off'} "
                        f"input_gate_open_rms={context.bridge_runtime.input_gate_open_rms} "
                        f"input_gate_close_rms={context.bridge_runtime.input_gate_close_rms} "
                        f"input_gate_hold_ms={context.bridge_runtime.input_noise_gate_hold_ms} "
                        "manual_start_signal=raw_rms "
                        "manual_end_signal=conditioned_rms "
                        f"local_overlap_gate={context.bridge_runtime.local_overlap_gate} "
                        f"local_turn_segmentation={context.bridge_runtime.local_turn_segmentation} "
                        f"interruption_source={context.bridge_runtime.interruption_source} "
                        "upstream_send_loop=queued "
                        "outbound_frame_ms=20 "
                        "outbound_tail_padding=on "
                        f"batch_ms={context.bridge_runtime.inbound_batch_ms}"
                    ),
                    level="info",
                )

            live_input = GeminiLiveSessionAdapter(
                session=session,
                codec=codec,
                manual_activity_control=manual_activity_control,
                queue_maxsize=_LIVE_AUDIO_QUEUE_MAXSIZE,
            )
            manual_activity = TwilioManualActivityBridgeService(
                controller=manual_activity_controller,
                live_input=live_input,
                append_trace=_append_call_trace,
            )
            live_receive = GeminiLiveReceiveAdapter(session=session)

            async def _close_realtime_audio_input() -> None:
                if manual_activity_control:
                    await manual_activity.close_input(current_call_sid=current_call_sid)
                    return
                await live_input.close_input()

            async def _close_after_playback_if_needed() -> bool:
                return await business_close.maybe_close_after_playback(
                    current_call_sid=current_call_sid,
                )

            async def live_audio_sender() -> None:
                await live_input.run_sender()

            async def twilio_to_live() -> None:
                nonlocal stream_sid
                nonlocal current_call_sid
                nonlocal last_duplex_overlap_trace_at
                try:
                    while True:
                        event = await ingress.receive_event()

                        if isinstance(event, TwilioMarkEvent):
                            mark_name = event.mark_name
                            if await playback_policy.handle_playback_mark(
                                current_call_sid=current_call_sid,
                                mark_name=mark_name,
                                arm_followup_probe=observer_bridge.arm_followup_probe,
                                close_after_playback_if_needed=_close_after_playback_if_needed,
                            ):
                                if stream_done.is_set():
                                    return
                            continue

                        if isinstance(event, TwilioStartEvent):
                            stream_sid = event.stream_sid
                            playback.bind_stream_sid(stream_sid)
                            current_call_sid = event.call_sid
                            observer_bridge.bind_call_sid(current_call_sid)
                            await _mark_stream_active(current_call_sid)
                            twilio_started.set()
                            await _ensure_bound_call_id()
                            continue

                        if isinstance(event, TwilioMediaTrackIgnoredEvent):
                            if not state.logged_non_inbound_track:
                                state.logged_non_inbound_track = True
                                await _append_call_trace(
                                    current_call_sid,
                                    event_type="media_track_ignored",
                                    text=f"track={event.track}",
                                    level="info",
                                )
                            continue

                        if isinstance(event, TwilioMediaDecodeErrorEvent):
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

                        if isinstance(event, TwilioMediaEvent):
                            decoded_audio = event.decoded_audio

                            now_ts = time.monotonic()
                            state.media_frames += 1
                            observer_bridge.append_inbound_audio(
                                pcm8k=decoded_audio.pcm8k,
                                pcm16k=decoded_audio.pcm16k,
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
                            await observer_bridge.observe_followup_audio(
                                now_ts=now_ts,
                                rms=decoded_audio.rms,
                                pcm8k=decoded_audio.pcm8k,
                                pcm16k=decoded_audio.pcm16k,
                            )
                            if manual_activity_control:
                                await manual_activity.handle_media_frame(
                                    current_call_sid=current_call_sid,
                                    decoded_audio=decoded_audio,
                                    now_ts=now_ts,
                                    playback_locked=playback_locked,
                                    legacy_manual_vad=legacy_manual_vad,
                                    half_duplex_manual_turn_control=half_duplex_manual_turn_control,
                                )
                            else:
                                if not (half_duplex_manual_turn_control and playback_locked):
                                    await live_input.queue_pcm16k_payload(decoded_audio.pcm16k)
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

                        if isinstance(event, TwilioStopEvent):
                            await lifecycle.handle_stream_stop(
                                current_call_sid=current_call_sid,
                                close_realtime_audio_input=_close_realtime_audio_input,
                            )
                            return
                except WebSocketDisconnect:
                    try:
                        await _close_realtime_audio_input()
                    except Exception:
                        pass
                    raise

            async def live_to_twilio() -> None:
                await twilio_started.wait()
                async for event in live_receive.receive_events():
                    if isinstance(event, GeminiLiveSetupCompleteEvent):
                        if not state.live_setup_complete:
                            state.mark_live_setup_complete()
                            live_setup_complete.set()
                            await _append_call_trace(
                                current_call_sid,
                                event_type="live_setup_complete",
                                text=f"session_id={event.session_id or '-'}",
                                level="success",
                            )
                            await _append_call_trace(
                                current_call_sid,
                                event_type="session_mode",
                                text="pure_realtime input=RealtimeInput only explicit_client_content=disabled",
                                level="info",
                            )
                        continue

                    if isinstance(event, GeminiInputTranscriptEvent):
                        state.assistant_last_output_at = time.monotonic()
                        observer_bridge.note_followup_transcript_observed()
                        await _append_call_trace(
                            current_call_sid,
                            event_type="input_transcript",
                            text=event.text,
                            final=event.final,
                            level="info",
                        )
                        if event.final:
                            await observer_bridge.disarm_followup_probe("input_transcript_finished")
                            await _append_bound_messages([{"role": "user", "content": event.text}])
                        continue

                    if isinstance(event, GeminiOutputTranscriptEvent):
                        state.assistant_last_output_at = time.monotonic()
                        await _append_call_trace(
                            current_call_sid,
                            event_type="output_transcript",
                            text=event.text,
                            final=event.final,
                            level="success",
                        )
                        if event.final:
                            business_close.register_completed_assistant_reply(
                                text=event.text,
                                should_close_after_playback=_is_auto_closing_reply(
                                    event.text
                                ),
                            )
                            await _append_bound_messages([{"role": "assistant", "content": event.text}])
                        continue

                    if isinstance(event, GeminiInterruptedEvent) and playback.active:
                        await observer_bridge.disarm_followup_probe("interrupted")
                        await playback_policy.handle_model_interrupted(
                            current_call_sid=current_call_sid,
                        )
                        continue

                    if isinstance(event, GeminiAssistantMetaTextEvent):
                        await _append_call_trace(
                            current_call_sid,
                            event_type="assistant_meta_text",
                            text=event.text,
                            level="info",
                        )
                        continue

                    if isinstance(event, GeminiAssistantAudioEvent):
                        if await playback_policy.should_drop_assistant_audio(
                            current_call_sid=current_call_sid,
                        ):
                            continue
                        await _on_assistant_response_started(observer_bridge, manual_activity)
                        await playback_policy.handle_assistant_audio(
                            current_call_sid=current_call_sid,
                            mime_type=event.mime_type,
                            pcm_bytes=event.pcm_bytes,
                        )
                        continue

                    if isinstance(event, GeminiTurnCompleteEvent):
                        # TODO(media-stream-v2): turn_complete 后的业务关闭、followup probe、
                        # playback 完结和后续 turn 预备仍然由 bridge 串联，后续应继续下沉成
                        # 明确的 turn-transition orchestration，减少事件分支里的样板协调代码。
                        if await playback_policy.handle_turn_complete(
                            current_call_sid=current_call_sid,
                            reason=event.reason,
                            close_after_playback_if_needed=_close_after_playback_if_needed,
                        ):
                            return

            await asyncio.gather(live_audio_sender(), twilio_to_live(), live_to_twilio())
    except WebSocketDisconnect:
        await lifecycle.handle_websocket_disconnect(
            current_call_sid=current_call_sid,
        )
        logger.info("Twilio media stream disconnected by client.")
    except Exception as exc:
        await lifecycle.handle_stream_error(
            current_call_sid=current_call_sid,
            error_text=str(exc),
        )
        logger.exception("Twilio media stream bridge failed: %s", exc)
    finally:
        await lifecycle.handle_finally(
            current_call_sid=current_call_sid,
        )
