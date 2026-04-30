from unittest.mock import AsyncMock

import pytest

from app.services.twilio.status_service import (
    TwilioStatusService,
    TwilioStreamStatusPayload,
    TwilioVoiceStatusPayload,
)


@pytest.mark.asyncio
async def test_stream_status_appends_success_trace(monkeypatch):
    append_trace = AsyncMock()
    monkeypatch.setattr("app.services.twilio.status_service._append_call_trace", append_trace)

    result = await TwilioStatusService().handle_stream_status(
        TwilioStreamStatusPayload(
            call_sid="CA123",
            stream_sid="MZ123",
            stream_name="main",
            stream_event="stream-started",
            timestamp="2026-04-30T00:00:00Z",
            account_sid="AC123",
        )
    )

    assert result == {"ok": True}
    append_trace.assert_awaited_once()
    assert append_trace.await_args.kwargs["event_type"] == "media_stream_status"
    assert append_trace.await_args.kwargs["level"] == "success"


@pytest.mark.asyncio
async def test_voice_terminal_status_clears_and_finalizes(monkeypatch):
    service = TwilioStatusService()
    clear_session = AsyncMock()
    finalize = AsyncMock()
    monkeypatch.setattr(
        "app.services.twilio.status_service.twilio_voice_agent_service.clear_session",
        clear_session,
    )
    monkeypatch.setattr(service, "_finalize_bound_test_session", finalize)

    result = await service.handle_voice_status(
        TwilioVoiceStatusPayload(call_sid="CA123", call_status="completed")
    )

    assert result["call_sid"] == "CA123"
    clear_session.assert_awaited_once_with("CA123")
    finalize.assert_awaited_once_with("CA123")


@pytest.mark.asyncio
async def test_voice_status_error_appends_error_trace(monkeypatch):
    append_trace = AsyncMock()
    monkeypatch.setattr("app.services.twilio.status_service._append_call_trace", append_trace)

    await TwilioStatusService().handle_voice_status(
        TwilioVoiceStatusPayload(
            call_sid="CA123",
            call_status="in-progress",
            error_code="123",
            error_message="boom",
        )
    )

    append_trace.assert_awaited_once()
    assert append_trace.await_args.kwargs["event_type"] == "call_status_error"
    assert append_trace.await_args.kwargs["level"] == "error"
