"""
Pluggable runtime-state backends for Twilio voice bridges.

This module keeps the current default in-memory behavior, but introduces
explicit store boundaries so a Redis-backed implementation can be added
without changing the realtime bridge orchestration code.
"""
from __future__ import annotations

import asyncio
import base64
import json
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Protocol

from app.core.config import settings

_TRACE_MAX_CALLS = 200
_TRACE_MAX_EVENTS_PER_CALL = 300
_REDIS_PREFIX = "llm_voice_agent:twilio"


class TwilioTraceStore(Protocol):
    async def append_event(
        self,
        call_sid: str | None,
        *,
        event_type: str,
        text: str | None = None,
        final: bool | None = None,
        level: str = "info",
    ) -> None: ...

    async def read_events(self, call_sid: str, since: int) -> tuple[list[dict[str, object]], int]: ...

    async def read_latest_call_sid(self) -> str | None: ...


class TwilioStreamRuntimeStore(Protocol):
    async def mark_active(self, call_sid: str | None) -> None: ...

    async def mark_inactive(self, call_sid: str | None) -> None: ...

    async def is_active(self, call_sid: str | None) -> bool: ...

    async def enqueue_manual_audio(self, call_sid: str, audio_bytes: bytes) -> int: ...

    async def drain_manual_audio(self, call_sid: str | None) -> list[bytes]: ...

    async def list_active_calls(self) -> list[str]: ...


@dataclass
class InMemoryTwilioTraceStore:
    max_calls: int = _TRACE_MAX_CALLS
    max_events_per_call: int = _TRACE_MAX_EVENTS_PER_CALL
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    _events: dict[str, deque[dict[str, object]]] = field(default_factory=dict, init=False)
    _seq: dict[str, int] = field(default_factory=dict, init=False)
    _call_order: deque[str] = field(default_factory=deque, init=False)

    async def append_event(
        self,
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
        async with self._lock:
            if sid not in self._events:
                self._events[sid] = deque(maxlen=self.max_events_per_call)
                self._call_order.append(sid)
                while len(self._call_order) > self.max_calls:
                    stale = self._call_order.popleft()
                    self._events.pop(stale, None)
                    self._seq.pop(stale, None)

            next_seq = self._seq.get(sid, 0) + 1
            self._seq[sid] = next_seq
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
            self._events[sid].append(payload)

    async def read_events(self, call_sid: str, since: int) -> tuple[list[dict[str, object]], int]:
        sid = (call_sid or "").strip()
        if not sid:
            return [], 0

        async with self._lock:
            events = list(self._events.get(sid, []))
            last_seq = self._seq.get(sid, 0)

        if since > 0:
            events = [item for item in events if int(item.get("seq", 0)) > since]
        return events, last_seq

    async def read_latest_call_sid(self) -> str | None:
        async with self._lock:
            if not self._call_order:
                return None
            return self._call_order[-1]


@dataclass
class InMemoryTwilioStreamRuntimeStore:
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    _manual_audio_queues: dict[str, deque[bytes]] = field(default_factory=dict, init=False)
    _active_stream_calls: set[str] = field(default_factory=set, init=False)

    async def mark_active(self, call_sid: str | None) -> None:
        sid = (call_sid or "").strip()
        if not sid:
            return
        async with self._lock:
            self._active_stream_calls.add(sid)
            self._manual_audio_queues.setdefault(sid, deque())

    async def mark_inactive(self, call_sid: str | None) -> None:
        sid = (call_sid or "").strip()
        if not sid:
            return
        async with self._lock:
            self._active_stream_calls.discard(sid)
            self._manual_audio_queues.pop(sid, None)

    async def is_active(self, call_sid: str | None) -> bool:
        sid = (call_sid or "").strip()
        if not sid:
            return False
        async with self._lock:
            return sid in self._active_stream_calls

    async def enqueue_manual_audio(self, call_sid: str, audio_bytes: bytes) -> int:
        sid = call_sid.strip()
        async with self._lock:
            queue = self._manual_audio_queues.setdefault(sid, deque())
            queue.append(audio_bytes)
            return len(queue)

    async def drain_manual_audio(self, call_sid: str | None) -> list[bytes]:
        sid = (call_sid or "").strip()
        if not sid:
            return []
        async with self._lock:
            queue = self._manual_audio_queues.get(sid)
            if not queue:
                return []
            items = list(queue)
            queue.clear()
            return items

    async def list_active_calls(self) -> list[str]:
        async with self._lock:
            return sorted(self._active_stream_calls)


def _decode_redis_text(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


_redis_client = None


def _get_redis_client():
    global _redis_client
    if _redis_client is None:
        try:
            import redis.asyncio as redis_asyncio
        except ImportError as exc:  # pragma: no cover - import path validated in runtime.
            raise RuntimeError("Redis backend selected but the 'redis' package is not installed.") from exc

        redis_url = (settings.redis_url or "").strip()
        if not redis_url:
            raise RuntimeError("Redis backend selected but REDIS_URL is not configured.")
        _redis_client = redis_asyncio.from_url(redis_url, decode_responses=False)
    return _redis_client


@dataclass
class RedisTwilioTraceStore:
    prefix: str = _REDIS_PREFIX
    max_calls: int = _TRACE_MAX_CALLS
    max_events_per_call: int = _TRACE_MAX_EVENTS_PER_CALL

    def _events_key(self, call_sid: str) -> str:
        return f"{self.prefix}:trace:{call_sid}:events"

    def _seq_key(self, call_sid: str) -> str:
        return f"{self.prefix}:trace:{call_sid}:seq"

    @property
    def _order_key(self) -> str:
        return f"{self.prefix}:trace:calls"

    async def append_event(
        self,
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
        client = _get_redis_client()
        next_seq = int(await client.incr(self._seq_key(sid)))
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

        encoded = json.dumps(payload, ensure_ascii=False)
        pipe = client.pipeline()
        pipe.rpush(self._events_key(sid), encoded)
        pipe.ltrim(self._events_key(sid), -self.max_events_per_call, -1)
        pipe.zadd(self._order_key, {sid: payload["ts"]})
        pipe.zcard(self._order_key)
        _, _, _, call_count = await pipe.execute()

        stale_count = max(0, int(call_count) - self.max_calls)
        if stale_count <= 0:
            return

        stale_sids = await client.zrange(self._order_key, 0, stale_count - 1)
        if not stale_sids:
            return

        cleanup = client.pipeline()
        for stale_sid in stale_sids:
            stale = _decode_redis_text(stale_sid)
            cleanup.zrem(self._order_key, stale)
            cleanup.delete(self._events_key(stale))
            cleanup.delete(self._seq_key(stale))
        await cleanup.execute()

    async def read_events(self, call_sid: str, since: int) -> tuple[list[dict[str, object]], int]:
        sid = (call_sid or "").strip()
        if not sid:
            return [], 0

        client = _get_redis_client()
        raw_events = await client.lrange(self._events_key(sid), 0, -1)
        raw_last_seq = await client.get(self._seq_key(sid))
        events = [json.loads(_decode_redis_text(item)) for item in raw_events]
        last_seq = int(_decode_redis_text(raw_last_seq)) if raw_last_seq is not None else 0

        if since > 0:
            events = [item for item in events if int(item.get("seq", 0)) > since]
        return events, last_seq

    async def read_latest_call_sid(self) -> str | None:
        client = _get_redis_client()
        latest = await client.zrevrange(self._order_key, 0, 0)
        if not latest:
            return None
        return _decode_redis_text(latest[0])


@dataclass
class RedisTwilioStreamRuntimeStore:
    prefix: str = _REDIS_PREFIX

    @property
    def _active_calls_key(self) -> str:
        return f"{self.prefix}:streams:active"

    def _manual_audio_key(self, call_sid: str) -> str:
        return f"{self.prefix}:streams:{call_sid}:manual_audio"

    async def mark_active(self, call_sid: str | None) -> None:
        sid = (call_sid or "").strip()
        if not sid:
            return
        client = _get_redis_client()
        await client.sadd(self._active_calls_key, sid)

    async def mark_inactive(self, call_sid: str | None) -> None:
        sid = (call_sid or "").strip()
        if not sid:
            return
        client = _get_redis_client()
        pipe = client.pipeline()
        pipe.srem(self._active_calls_key, sid)
        pipe.delete(self._manual_audio_key(sid))
        await pipe.execute()

    async def is_active(self, call_sid: str | None) -> bool:
        sid = (call_sid or "").strip()
        if not sid:
            return False
        client = _get_redis_client()
        return bool(await client.sismember(self._active_calls_key, sid))

    async def enqueue_manual_audio(self, call_sid: str, audio_bytes: bytes) -> int:
        sid = call_sid.strip()
        client = _get_redis_client()
        encoded = base64.b64encode(audio_bytes).decode("ascii")
        pipe = client.pipeline()
        pipe.rpush(self._manual_audio_key(sid), encoded)
        pipe.llen(self._manual_audio_key(sid))
        _, queue_len = await pipe.execute()
        return int(queue_len)

    async def drain_manual_audio(self, call_sid: str | None) -> list[bytes]:
        sid = (call_sid or "").strip()
        if not sid:
            return []
        client = _get_redis_client()
        pipe = client.pipeline()
        pipe.lrange(self._manual_audio_key(sid), 0, -1)
        pipe.delete(self._manual_audio_key(sid))
        raw_items, _ = await pipe.execute()
        if not raw_items:
            return []
        return [base64.b64decode(_decode_redis_text(item).encode("ascii")) for item in raw_items]

    async def list_active_calls(self) -> list[str]:
        client = _get_redis_client()
        members = await client.smembers(self._active_calls_key)
        return sorted(_decode_redis_text(item) for item in members)


_memory_trace_store = InMemoryTwilioTraceStore()
_memory_stream_runtime_store = InMemoryTwilioStreamRuntimeStore()
_redis_trace_store = RedisTwilioTraceStore()
_redis_stream_runtime_store = RedisTwilioStreamRuntimeStore()


def _selected_backend_name() -> str:
    return (settings.twilio_runtime_store_backend or "memory").strip().lower() or "memory"


def get_twilio_trace_store() -> TwilioTraceStore:
    backend = _selected_backend_name()
    if backend == "memory":
        return _memory_trace_store
    if backend == "redis":
        return _redis_trace_store
    raise RuntimeError(f"Unsupported Twilio runtime store backend: {backend}")


def get_twilio_stream_runtime_store() -> TwilioStreamRuntimeStore:
    backend = _selected_backend_name()
    if backend == "memory":
        return _memory_stream_runtime_store
    if backend == "redis":
        return _redis_stream_runtime_store
    raise RuntimeError(f"Unsupported Twilio runtime store backend: {backend}")
