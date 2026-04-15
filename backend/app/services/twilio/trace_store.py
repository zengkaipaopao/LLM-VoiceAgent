import asyncio
import time
from collections import deque

_TRACE_MAX_CALLS = 200
_TRACE_MAX_EVENTS_PER_CALL = 300

_trace_lock = asyncio.Lock()
_trace_events: dict[str, deque[dict[str, object]]] = {}
_trace_seq: dict[str, int] = {}
_trace_call_order: deque[str] = deque()


async def _append_call_trace(
    call_sid: str | None,
    *,
    event_type: str,
    text: str | None = None,
    final: bool | None = None,
    level: str = "info",
) -> None:
    sid = (call_sid or "").strip()
    if not sid:
        return

    snippet = (text or "").strip()
    async with _trace_lock:
        if sid not in _trace_events:
            _trace_events[sid] = deque(maxlen=_TRACE_MAX_EVENTS_PER_CALL)
            _trace_call_order.append(sid)
            while len(_trace_call_order) > _TRACE_MAX_CALLS:
                stale = _trace_call_order.popleft()
                _trace_events.pop(stale, None)
                _trace_seq.pop(stale, None)

        next_seq = _trace_seq.get(sid, 0) + 1
        _trace_seq[sid] = next_seq
        payload: dict[str, object] = {
            "seq": next_seq,
            "ts": int(time.time() * 1000),
            "type": event_type,
            "level": level,
        }
        if snippet:
            payload["text"] = snippet
        if final is not None:
            payload["final"] = final
        _trace_events[sid].append(payload)


async def _read_call_trace(call_sid: str, since: int) -> tuple[list[dict[str, object]], int]:
    sid = (call_sid or "").strip()
    if not sid:
        return [], 0

    async with _trace_lock:
        events = list(_trace_events.get(sid, []))
        last_seq = _trace_seq.get(sid, 0)

    if since > 0:
        events = [item for item in events if int(item.get("seq", 0)) > since]
    return events, last_seq


async def _read_latest_trace_call_sid() -> str | None:
    async with _trace_lock:
        if not _trace_call_order:
            return None
        return _trace_call_order[-1]
