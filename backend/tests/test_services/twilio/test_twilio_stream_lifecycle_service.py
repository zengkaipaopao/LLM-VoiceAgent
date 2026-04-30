from __future__ import annotations

import asyncio

import pytest

from app.services.twilio.stream_lifecycle_service import TwilioStreamLifecycleService


class _DummyObserver:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def disarm_followup_probe(self, reason: str) -> None:
        self.calls.append(("disarm", reason))

    async def persist_inbound_debug_wav(self, trigger: str) -> None:
        self.calls.append(("persist", trigger))


@pytest.mark.asyncio
async def test_stream_lifecycle_service_handles_stream_stop_in_order():
    observer = _DummyObserver()
    trace_events: list[tuple[str, str | None, str]] = []
    finalize_calls: list[str] = []
    inactive_calls: list[str | None] = []
    close_calls: list[str] = []
    close_input_calls: list[str] = []
    stream_done = asyncio.Event()

    async def append_trace(call_sid, *, event_type, text=None, level="info", final=None):
        trace_events.append((event_type, text, level))

    async def finalize_bound_call(*, trigger: str, run_extraction: bool = True):
        finalize_calls.append(trigger)

    async def mark_stream_inactive(call_sid: str | None):
        inactive_calls.append(call_sid)

    async def close_websocket():
        close_calls.append("close")

    async def close_realtime_audio_input():
        close_input_calls.append("closed")

    service = TwilioStreamLifecycleService(
        observer=observer,
        append_trace=append_trace,
        finalize_bound_call=finalize_bound_call,
        mark_stream_inactive=mark_stream_inactive,
        close_websocket=close_websocket,
        stream_done=stream_done,
    )

    await service.handle_stream_stop(
        current_call_sid="CA-stop",
        close_realtime_audio_input=close_realtime_audio_input,
    )

    assert stream_done.is_set() is True
    assert close_input_calls == ["closed"]
    assert trace_events == [("stream_stop", None, "info")]
    assert observer.calls == [("disarm", "stream_stop"), ("persist", "stream_stop")]
    assert finalize_calls == ["stream_stop"]
    assert inactive_calls == ["CA-stop"]
    assert close_calls == []


@pytest.mark.asyncio
async def test_stream_lifecycle_service_handles_finally_without_finalize():
    observer = _DummyObserver()
    finalize_calls: list[str] = []
    inactive_calls: list[str | None] = []
    close_calls: list[str] = []
    stream_done = asyncio.Event()

    async def append_trace(call_sid, *, event_type, text=None, level="info", final=None):
        return None

    async def finalize_bound_call(*, trigger: str, run_extraction: bool = True):
        finalize_calls.append(trigger)

    async def mark_stream_inactive(call_sid: str | None):
        inactive_calls.append(call_sid)

    async def close_websocket():
        close_calls.append("close")

    service = TwilioStreamLifecycleService(
        observer=observer,
        append_trace=append_trace,
        finalize_bound_call=finalize_bound_call,
        mark_stream_inactive=mark_stream_inactive,
        close_websocket=close_websocket,
        stream_done=stream_done,
    )

    await service.handle_finally(
        current_call_sid="CA-finally",
    )

    assert stream_done.is_set() is True
    assert observer.calls == [("disarm", "stream_finally"), ("persist", "stream_finally")]
    assert finalize_calls == []
    assert inactive_calls == ["CA-finally"]
    assert close_calls == ["close"]
