from __future__ import annotations

import asyncio

import pytest

from app.services.twilio.business_close_service import TwilioBusinessCloseService
from app.services.twilio.media_stream_state import TwilioMediaStreamState


@pytest.mark.asyncio
async def test_business_close_service_registers_reply_and_closes_after_playback():
    trace_events: list[tuple[str, str | None, str]] = []
    finalize_calls: list[str] = []
    close_calls: list[str] = []
    stream_done = asyncio.Event()
    state = TwilioMediaStreamState()

    async def append_trace(call_sid, *, event_type, text=None, level="info", final=None):
        trace_events.append((event_type, text, level))

    async def finalize_bound_call(*, trigger: str, run_extraction: bool = True):
        finalize_calls.append(trigger)

    async def close_websocket():
        close_calls.append("close")

    service = TwilioBusinessCloseService(
        state=state,
        append_trace=append_trace,
        finalize_bound_call=finalize_bound_call,
        close_websocket=close_websocket,
        stream_done=stream_done,
    )

    service.register_completed_assistant_reply(
        text="通話を終了します。",
        should_close_after_playback=True,
    )
    closed = await service.maybe_close_after_playback(current_call_sid="CA-close")

    assert closed is True
    assert stream_done.is_set() is True
    assert state.close_after_turn_complete is False
    assert trace_events == [("auto_finalize_triggered", "通話を終了します。", "success")]
    assert finalize_calls == ["closing_phrase"]
    assert close_calls == ["close"]


@pytest.mark.asyncio
async def test_business_close_service_skips_when_no_close_flag():
    trace_events: list[tuple[str, str | None, str]] = []
    finalize_calls: list[str] = []
    close_calls: list[str] = []
    stream_done = asyncio.Event()
    state = TwilioMediaStreamState()

    async def append_trace(call_sid, *, event_type, text=None, level="info", final=None):
        trace_events.append((event_type, text, level))

    async def finalize_bound_call(*, trigger: str, run_extraction: bool = True):
        finalize_calls.append(trigger)

    async def close_websocket():
        close_calls.append("close")

    service = TwilioBusinessCloseService(
        state=state,
        append_trace=append_trace,
        finalize_bound_call=finalize_bound_call,
        close_websocket=close_websocket,
        stream_done=stream_done,
    )

    closed = await service.maybe_close_after_playback(current_call_sid="CA-close")

    assert closed is False
    assert stream_done.is_set() is False
    assert trace_events == []
    assert finalize_calls == []
    assert close_calls == []
