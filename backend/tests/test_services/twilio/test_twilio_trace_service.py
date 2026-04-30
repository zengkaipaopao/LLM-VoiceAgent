import base64
from unittest.mock import AsyncMock

import pytest

from app.services.twilio.trace_service import (
    TwilioTraceConflictError,
    TwilioTraceService,
)


@pytest.mark.asyncio
async def test_get_active_calls_orders_by_latest_event(monkeypatch):
    async def list_active_calls():
        return ["CA_old", "CA_new"]

    async def read_call_trace(call_sid, _since):
        if call_sid == "CA_old":
            return ([{"type": "old", "ts": 100, "text": "old"}], 1)
        return ([{"type": "new", "ts": 200, "text": "new"}], 2)

    monkeypatch.setattr(
        "app.services.twilio.trace_service._list_active_stream_calls",
        list_active_calls,
    )
    monkeypatch.setattr(
        "app.services.twilio.trace_service._read_call_trace",
        read_call_trace,
    )

    result = await TwilioTraceService().get_active_calls()

    assert result["active_calls"] == ["CA_new", "CA_old"]
    assert result["latest_call_sid"] == "CA_new"
    assert result["count"] == 2
    assert result["active_call_details"][0]["last_event_type"] == "new"


@pytest.mark.asyncio
async def test_inject_audio_rejects_inactive_stream(monkeypatch):
    monkeypatch.setattr(
        "app.services.twilio.trace_service._is_stream_active",
        AsyncMock(return_value=False),
    )

    with pytest.raises(TwilioTraceConflictError):
        await TwilioTraceService().inject_audio(
            call_sid="CA123",
            audio_base64=base64.b64encode(b"\x00\x00").decode("ascii"),
            mime_type="audio/pcm;rate=16000",
        )


@pytest.mark.asyncio
async def test_inject_audio_enqueues_and_traces_pcm16(monkeypatch):
    enqueue = AsyncMock(return_value=3)
    append_trace = AsyncMock()
    monkeypatch.setattr(
        "app.services.twilio.trace_service._is_stream_active",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        "app.services.twilio.trace_service._enqueue_manual_audio",
        enqueue,
    )
    monkeypatch.setattr(
        "app.services.twilio.trace_service._append_call_trace",
        append_trace,
    )

    result = await TwilioTraceService().inject_audio(
        call_sid=" CA123 ",
        audio_base64=base64.b64encode(b"\x01\x00\x02\x00").decode("ascii"),
        mime_type="audio/pcm;rate=16000",
    )

    assert result["call_sid"] == "CA123"
    assert result["bytes"] == 4
    assert result["queue_size"] == 3
    assert result["mime_type"] == "audio/pcm;rate=16000"
    enqueue.assert_awaited_once_with("CA123", b"\x01\x00\x02\x00")
    append_trace.assert_awaited_once()
    assert append_trace.await_args.kwargs["event_type"] == "manual_audio_queued"


def test_prepare_audio_lab_returns_payload_variants():
    audio_base64 = base64.b64encode(b"\x00\x00" * 160).decode("ascii")

    result = TwilioTraceService().prepare_audio_lab(
        audio_base64=audio_base64,
        sample_rate=16000,
    )

    assert result["sample_rate"] == 16000
    assert [item["id"] for item in result["variants"]] == [
        "original_recording",
        "twilio_preview",
        "gemini_preview",
    ]
