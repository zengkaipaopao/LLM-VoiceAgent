from __future__ import annotations

import asyncio

import pytest

from app.services.twilio.audio_codec import DecodedTwilioInboundAudio, TwilioMediaAudioCodec
from app.services.twilio.gemini_live_session_adapter import GeminiLiveSessionAdapter
from app.services.twilio.manual_activity_bridge_service import (
    TwilioManualActivityBridgeService,
)
from app.services.twilio.manual_activity_controller import TwilioManualActivityController


class _DummyRealtimeSession:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def send_realtime_input(self, **kwargs) -> None:
        self.calls.append(kwargs)


def _build_service() -> tuple[
    TwilioManualActivityBridgeService,
    _DummyRealtimeSession,
    list[tuple[str, str | None, str]],
]:
    session = _DummyRealtimeSession()
    codec = TwilioMediaAudioCodec(input_batch_ms=20)
    live_input = GeminiLiveSessionAdapter(
        session=session,
        codec=codec,
        manual_activity_control=True,
        queue_maxsize=8,
    )
    trace_events: list[tuple[str, str | None, str]] = []

    async def append_trace(
        call_sid,
        *,
        event_type,
        text=None,
        level="info",
        final=None,
    ):
        trace_events.append((event_type, text, level))

    controller = TwilioManualActivityController(
        frame_ms=20,
        prefix_padding_ms=40,
        start_rms=100,
        end_rms=90,
        start_hits_required=2,
        barge_rms=900,
        barge_hits_required=2,
        silence_hits_required=2,
        silence_reset_trace_ms=40,
        progress_trace_interval_seconds=10.0,
    )
    service = TwilioManualActivityBridgeService(
        controller=controller,
        live_input=live_input,
        append_trace=append_trace,
    )
    return service, session, trace_events


def _decoded_frame(*, rms: int, conditioned_rms: int) -> DecodedTwilioInboundAudio:
    pcm16k = b"\x01\x02" * 320
    return DecodedTwilioInboundAudio(
        pcm8k=b"\x7f" * 160,
        pcm16k=pcm16k,
        rms=rms,
        conditioned_rms=conditioned_rms,
    )


@pytest.mark.asyncio
async def test_manual_activity_bridge_starts_and_closes_input_with_explicit_end():
    service, session, trace_events = _build_service()
    sender_task = asyncio.create_task(service.live_input.run_sender())

    await service.handle_media_frame(
        current_call_sid="CA123",
        decoded_audio=_decoded_frame(rms=120, conditioned_rms=120),
        now_ts=1.0,
        playback_locked=False,
        legacy_manual_vad=False,
        half_duplex_manual_turn_control=False,
    )
    await service.handle_media_frame(
        current_call_sid="CA123",
        decoded_audio=_decoded_frame(rms=130, conditioned_rms=130),
        now_ts=1.02,
        playback_locked=False,
        legacy_manual_vad=False,
        half_duplex_manual_turn_control=False,
    )
    await service.close_input(current_call_sid="CA123")
    await sender_task

    assert service.active is False
    assert session.calls[0]["activity_start"] is not None
    assert session.calls[-1]["activity_end"] is not None
    assert [event[0] for event in trace_events] == [
        "manual_activity_start_sent",
        "manual_activity_end_sent",
    ]


@pytest.mark.asyncio
async def test_manual_activity_bridge_ends_turn_after_silence_timeout():
    service, session, trace_events = _build_service()
    sender_task = asyncio.create_task(service.live_input.run_sender())

    await service.handle_media_frame(
        current_call_sid="CA456",
        decoded_audio=_decoded_frame(rms=120, conditioned_rms=120),
        now_ts=2.0,
        playback_locked=False,
        legacy_manual_vad=False,
        half_duplex_manual_turn_control=False,
    )
    await service.handle_media_frame(
        current_call_sid="CA456",
        decoded_audio=_decoded_frame(rms=140, conditioned_rms=140),
        now_ts=2.02,
        playback_locked=False,
        legacy_manual_vad=False,
        half_duplex_manual_turn_control=False,
    )
    await service.handle_media_frame(
        current_call_sid="CA456",
        decoded_audio=_decoded_frame(rms=60, conditioned_rms=60),
        now_ts=2.04,
        playback_locked=False,
        legacy_manual_vad=False,
        half_duplex_manual_turn_control=False,
    )
    await service.handle_media_frame(
        current_call_sid="CA456",
        decoded_audio=_decoded_frame(rms=50, conditioned_rms=50),
        now_ts=2.06,
        playback_locked=False,
        legacy_manual_vad=False,
        half_duplex_manual_turn_control=False,
    )
    await service.close_input(current_call_sid="CA456")
    await sender_task

    assert service.active is False
    assert session.calls[0]["activity_start"] is not None
    assert session.calls[-1]["activity_end"] is not None
    assert [event[0] for event in trace_events] == [
        "manual_activity_start_sent",
        "manual_activity_end_sent",
    ]
    assert "reason=silence_timeout" in (trace_events[-1][1] or "")
    assert "silence_ms=40" in (trace_events[-1][1] or "")
