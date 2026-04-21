import base64

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.api.deps import require_api_key
from app.core.config import settings
from app.schemas.base import ResponseBase
from app.services.twilio.debug_audio_runtime import (
    _build_twilio_inbound_debug_capture,
    _PCM16K_RESAMPLED_DEBUG_VARIANT,
)
from app.services.twilio.stream_runtime_store import (
    _enqueue_manual_audio,
    _is_stream_active,
    _list_active_stream_calls,
    _pcm16_audio_stats,
)
from app.services.twilio.trace_diagnostics import build_twilio_trace_diagnostic
from app.services.twilio.trace_store import (
    _append_call_trace,
    _read_call_trace,
    _read_latest_trace_call_sid,
)

router = APIRouter()


class TwilioManualAudioInjectRequest(BaseModel):
    call_sid: str = Field(min_length=1)
    audio_base64: str = Field(
        min_length=1,
        description="PCM16 mono audio (16kHz) base64 payload.",
    )
    mime_type: str = Field(default="audio/pcm;rate=16000")


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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inbound debug audio not found.",
        )
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid audio_base64 payload.",
        ) from exc

    if not audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Decoded audio payload is empty.",
        )

    if len(audio_bytes) % 2 != 0:
        audio_bytes = audio_bytes[:-1]
    if not audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Decoded audio payload is invalid.",
        )

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
