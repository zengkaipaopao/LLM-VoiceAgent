import asyncio
import audioop
import re
from collections import deque

_AUDIO_RATE_PATTERN = re.compile(r"rate=(\d+)")

_manual_audio_lock = asyncio.Lock()
_manual_audio_queues: dict[str, deque[bytes]] = {}
_active_stream_calls: set[str] = set()


async def _mark_stream_active(call_sid: str | None) -> None:
    sid = (call_sid or "").strip()
    if not sid:
        return
    async with _manual_audio_lock:
        _active_stream_calls.add(sid)
        _manual_audio_queues.setdefault(sid, deque())


async def _mark_stream_inactive(call_sid: str | None) -> None:
    sid = (call_sid or "").strip()
    if not sid:
        return
    async with _manual_audio_lock:
        _active_stream_calls.discard(sid)
        _manual_audio_queues.pop(sid, None)


async def _is_stream_active(call_sid: str | None) -> bool:
    sid = (call_sid or "").strip()
    if not sid:
        return False
    async with _manual_audio_lock:
        return sid in _active_stream_calls


async def _enqueue_manual_audio(call_sid: str, audio_bytes: bytes) -> int:
    sid = call_sid.strip()
    async with _manual_audio_lock:
        queue = _manual_audio_queues.setdefault(sid, deque())
        queue.append(audio_bytes)
        return len(queue)


async def _drain_manual_audio(call_sid: str | None) -> list[bytes]:
    sid = (call_sid or "").strip()
    if not sid:
        return []
    async with _manual_audio_lock:
        queue = _manual_audio_queues.get(sid)
        if not queue:
            return []
        items = list(queue)
        queue.clear()
        return items


async def _list_active_stream_calls() -> list[str]:
    async with _manual_audio_lock:
        return sorted(_active_stream_calls)


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
