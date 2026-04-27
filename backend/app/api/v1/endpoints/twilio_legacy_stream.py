import logging

from fastapi import APIRouter, Query, WebSocket, status

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.model_defaults import require_live_model
from app.exceptions import BusinessException
from app.services.live_gateway import provider_available, resolve_live_provider
from app.services.twilio.incoming_route_runtime import build_official_demo_runtime, is_official_demo_route
from app.services.twilio.live_config import (
    _build_gemini_live_config,
    _resolve_media_stream_bridge_profile,
    _use_manual_vad_control,
    _validate_twilio_activity_mode,
    _validate_twilio_media_stream_bridge_profile,
)
from app.services.twilio.media_stream_bootstrap import receive_twilio_media_stream_start
from app.services.twilio.media_stream_bridge_service import (
    TwilioMediaStreamBridgeContext,
    run_twilio_media_stream_bridge,
)
from app.services.twilio.media_stream_runtime import build_twilio_media_stream_runtime_config
from app.services.twilio.normalizers import _normalize_gemini_live_voice_name
from app.services.twilio.prompt_runtime_helpers import (
    _build_twilio_session_instruction,
    _resolve_gemini_live_model,
    _resolve_prompt_runtime,
)
from app.services.twilio.trace_store import _append_call_trace
from app.services.twilio.twiml_builders import _verify_websocket_or_close

router = APIRouter()
logger = logging.getLogger(__name__)


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
    bridge_runtime = build_twilio_media_stream_runtime_config(
        bridge_profile=bridge_profile,
        requested_manual_vad=requested_manual_vad,
        duplex_overlap_rms_threshold=180,
        followup_probe_rms_threshold=100,
        twilio_media_frame_ms=20,
    )
    twilio_session_instruction = _build_twilio_session_instruction(
        runtime.system_instruction,
        opening_text=None,
    )
    live_config = _build_gemini_live_config(
        model=selected_model,
        system_instruction=twilio_session_instruction,
        voice_name=selected_voice,
        manual_vad=bridge_runtime.legacy_manual_vad,
        media_stream_bridge_profile=bridge_profile,
    )

    await run_twilio_media_stream_bridge(
        TwilioMediaStreamBridgeContext(
            websocket=websocket,
            stream_sid=stream_sid,
            current_call_sid=current_call_sid,
            voice_route_from_stream=voice_route_from_stream,
            from_number_from_stream=from_number_from_stream,
            to_number_from_stream=to_number_from_stream,
            runtime=runtime,
            runtime_notice=runtime_notice,
            requested_model=requested_model,
            selected_model=selected_model,
            selected_provider=selected_provider,
            selected_voice=selected_voice,
            bridge_profile=bridge_profile,
            requested_manual_vad=requested_manual_vad,
            bridge_runtime=bridge_runtime,
            live_config=live_config,
        )
    )
