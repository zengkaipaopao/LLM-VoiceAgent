from __future__ import annotations

import json

import pytest

from app.services.twilio.assistant_playback_policy import AssistantPlaybackPolicyService
from app.services.twilio.audio_codec import TwilioMediaAudioCodec
from app.services.twilio.media_stream_state import TwilioMediaStreamState
from app.services.twilio.twilio_playback_adapter import TwilioPlaybackAdapter


class _DummyWebSocket:
    def __init__(self) -> None:
        self.sent_text: list[str] = []

    async def send_text(self, text: str) -> None:
        self.sent_text.append(text)


@pytest.mark.asyncio
async def test_playback_policy_handles_model_interrupted_and_clears_playback():
    websocket = _DummyWebSocket()
    trace_events: list[tuple[str, str | None, str]] = []
    state = TwilioMediaStreamState(
        pending_playback_mark="assistant-turn-1",
        assistant_playback_pending=True,
        assistant_speaking=True,
        model_turn_sent_audio=True,
    )
    codec = TwilioMediaAudioCodec()
    codec.encode_model_audio(b"\x01\x02" * 480, mime_type="audio/pcm;rate=24000")
    playback = TwilioPlaybackAdapter(websocket=websocket, stream_sid="MZ123")
    service = AssistantPlaybackPolicyService(
        state=state,
        codec=codec,
        playback=playback,
        append_trace=lambda call_sid, *, event_type, text=None, level="info", final=None: trace_events.append((event_type, text, level)) or _async_none(),
    )

    await service.handle_model_interrupted(
        current_call_sid="CA123",
    )

    payloads = [json.loads(item) for item in websocket.sent_text]
    assert payloads == [{"event": "clear", "streamSid": "MZ123"}]
    assert trace_events == [("interrupted", "Model response interrupted by activity.", "warning")]
    assert state.assistant_speaking is False


@pytest.mark.asyncio
async def test_playback_policy_reports_dropped_audio_after_local_interrupt_once():
    websocket = _DummyWebSocket()
    trace_events: list[tuple[str, str | None, str]] = []
    state = TwilioMediaStreamState()
    playback = TwilioPlaybackAdapter(websocket=websocket, stream_sid="MZ123")
    service = AssistantPlaybackPolicyService(
        state=state,
        codec=TwilioMediaAudioCodec(),
        playback=playback,
        append_trace=lambda call_sid, *, event_type, text=None, level="info", final=None: trace_events.append((event_type, text, level)) or _async_none(),
    )
    service.assistant_turn_locally_interrupted = True

    first = await service.should_drop_assistant_audio(current_call_sid="CA123")
    second = await service.should_drop_assistant_audio(current_call_sid="CA123")

    assert first is True
    assert second is True
    assert trace_events == [
        (
            "assistant_audio_dropped_after_local_barge_in",
            "Dropping remaining assistant audio for interrupted turn.",
            "warning",
        )
    ]


@pytest.mark.asyncio
async def test_playback_policy_handles_turn_complete_with_tail_flush_and_mark():
    websocket = _DummyWebSocket()
    trace_events: list[tuple[str, str | None, str]] = []
    state = TwilioMediaStreamState()
    codec = TwilioMediaAudioCodec()
    playback = TwilioPlaybackAdapter(websocket=websocket, stream_sid="MZ456")
    service = AssistantPlaybackPolicyService(
        state=state,
        codec=codec,
        playback=playback,
        append_trace=lambda call_sid, *, event_type, text=None, level="info", final=None: trace_events.append((event_type, text, level)) or _async_none(),
    )

    codec.encode_model_audio(b"\x01\x02" * 480, mime_type="audio/pcm;rate=24000")
    state.mark_model_audio_sent()

    closed = await service.handle_turn_complete(
        current_call_sid="CA456",
        reason="stop",
        close_after_playback_if_needed=_async_false,
    )

    payloads = [json.loads(item) for item in websocket.sent_text]
    assert closed is False
    assert payloads[-1] == {
        "event": "mark",
        "streamSid": "MZ456",
        "mark": {"name": "assistant-turn-1"},
    }
    event_types = [event[0] for event in trace_events]
    assert event_types[-2:] == ["playback_mark_sent", "turn_complete"]
    assert state.pending_playback_mark == "assistant-turn-1"
    assert state.assistant_playback_pending is True


async def _async_false() -> bool:
    return False


async def _async_none() -> None:
    return None
