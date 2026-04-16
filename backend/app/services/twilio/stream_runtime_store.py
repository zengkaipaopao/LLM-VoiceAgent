import audioop
import re

from app.services.twilio.runtime_backends import get_twilio_stream_runtime_store

_AUDIO_RATE_PATTERN = re.compile(r"rate=(\d+)")


async def _mark_stream_active(call_sid: str | None) -> None:
    await get_twilio_stream_runtime_store().mark_active(call_sid)


async def _mark_stream_inactive(call_sid: str | None) -> None:
    await get_twilio_stream_runtime_store().mark_inactive(call_sid)


async def _is_stream_active(call_sid: str | None) -> bool:
    return await get_twilio_stream_runtime_store().is_active(call_sid)


async def _enqueue_manual_audio(call_sid: str, audio_bytes: bytes) -> int:
    return await get_twilio_stream_runtime_store().enqueue_manual_audio(call_sid, audio_bytes)


async def _drain_manual_audio(call_sid: str | None) -> list[bytes]:
    return await get_twilio_stream_runtime_store().drain_manual_audio(call_sid)


async def _list_active_stream_calls() -> list[str]:
    return await get_twilio_stream_runtime_store().list_active_calls()


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


def _chunk_bytes(buffer: bytes, chunk_size: int) -> list[bytes]:
    if not buffer or chunk_size <= 0:
        return []
    return [buffer[index : index + chunk_size] for index in range(0, len(buffer), chunk_size)]


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
