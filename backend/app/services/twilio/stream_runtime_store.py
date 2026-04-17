import re

from app.services.twilio.audio_codec import compute_pcm16_stats, pcm16_bytes_to_samples
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
    return compute_pcm16_stats(pcm16_bytes_to_samples(audio_bytes), sample_rate=sample_rate)


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
