"""Application service for Twilio voice trace endpoints."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.twilio.audio_lab import (
    decode_audio_base64_payload,
    evaluate_audio_with_gemini_live,
    prepare_audio_lab_variants,
)
from app.services.twilio.debug_audio_runtime import (
    _PCM16K_RESAMPLED_DEBUG_VARIANT,
    _build_twilio_inbound_debug_capture,
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


class TwilioTraceConflictError(Exception):
    """Raised when the trace operation targets a currently inactive stream."""


class TwilioTraceService:
    """Coordinate trace reads, diagnostics, audio lab, and manual audio injection."""

    async def get_trace(self, *, call_sid: str, since: int) -> dict[str, Any]:
        events, last_seq = await _read_call_trace(call_sid, since)
        return {
            "call_sid": call_sid,
            "since": since,
            "last_seq": last_seq,
            "events": events,
        }

    async def get_latest_call_sid(self) -> dict[str, Any]:
        return {"call_sid": await _read_latest_trace_call_sid()}

    async def get_diagnostics(self, *, call_sid: str) -> dict[str, Any]:
        events, last_seq = await _read_call_trace(call_sid, 0)
        stream_active = await _is_stream_active(call_sid)
        diagnostic = build_twilio_trace_diagnostic(
            call_sid=call_sid,
            events=events,
            stream_active=stream_active,
        )
        return {
            **diagnostic,
            "last_seq": last_seq,
            "stream_active": stream_active,
        }

    def prepare_audio_lab(self, *, audio_base64: str, sample_rate: int) -> dict[str, Any]:
        audio_bytes = decode_audio_base64_payload(audio_base64)
        variants = prepare_audio_lab_variants(
            audio_bytes=audio_bytes,
            sample_rate=sample_rate,
        )
        return {
            "sample_rate": sample_rate,
            "variants": [variant.to_payload() for variant in variants],
        }

    async def evaluate_audio_lab(
        self,
        *,
        db: AsyncSession,
        audio_base64: str,
        sample_rate: int,
        prompt_code: str | None,
        voice_name: str | None,
        opening_already_played: bool,
        variant_id: str | None,
    ) -> dict[str, Any]:
        audio_bytes = decode_audio_base64_payload(audio_base64)
        result = await evaluate_audio_with_gemini_live(
            db=db,
            audio_bytes=audio_bytes,
            sample_rate=sample_rate,
            prompt_code=prompt_code,
            voice_name=voice_name,
            opening_already_played=opening_already_played,
        )
        return {
            "variant_id": variant_id,
            **result,
        }

    def resolve_inbound_audio_path(
        self,
        *,
        call_sid: str,
        variant: str = _PCM16K_RESAMPLED_DEBUG_VARIANT,
    ) -> Path:
        capture = _build_twilio_inbound_debug_capture(variant)
        return capture.build_output_path(
            output_dir=settings.twilio_media_stream_debug_inbound_wav_dir,
            call_sid=call_sid,
        )

    async def inject_audio(
        self,
        *,
        call_sid: str,
        audio_base64: str,
        mime_type: str,
    ) -> dict[str, Any]:
        normalized_call_sid = call_sid.strip()
        if not normalized_call_sid:
            raise ValueError("call_sid is required.")

        is_active = await _is_stream_active(normalized_call_sid)
        if not is_active:
            raise TwilioTraceConflictError(
                "Call stream is not active. Connect an inbound call first."
            )

        try:
            audio_bytes = decode_audio_base64_payload(audio_base64)
        except Exception as exc:
            raise ValueError("Invalid audio_base64 payload.") from exc

        stats = _pcm16_audio_stats(audio_bytes, sample_rate=16000)
        queue_size = await _enqueue_manual_audio(normalized_call_sid, audio_bytes)
        await _append_call_trace(
            normalized_call_sid,
            event_type="manual_audio_queued",
            text=(
                f"bytes={stats['bytes']} duration_ms={stats['duration_ms']} "
                f"rms={stats['rms']} peak={stats['peak']} queue={queue_size}"
            ),
            level="info",
        )
        return {
            "call_sid": normalized_call_sid,
            "bytes": stats["bytes"],
            "duration_ms": stats["duration_ms"],
            "rms": stats["rms"],
            "peak": stats["peak"],
            "queue_size": queue_size,
            "mime_type": mime_type,
        }

    async def get_active_calls(self) -> dict[str, Any]:
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
        return {
            "active_calls": ordered_active_calls,
            "active_call_details": active_call_details,
            "latest_call_sid": ordered_active_calls[0] if ordered_active_calls else None,
            "count": len(ordered_active_calls),
        }


__all__ = [
    "TwilioTraceConflictError",
    "TwilioTraceService",
]
