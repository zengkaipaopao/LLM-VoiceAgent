from __future__ import annotations

import asyncio
import base64
import json
from types import SimpleNamespace

import pytest

from app.services.twilio.audio_codec import TwilioMediaAudioCodec
from app.services.twilio.gemini_live_receive_adapter import (
    GeminiAssistantAudioEvent,
    GeminiAssistantMetaTextEvent,
    GeminiInputTranscriptEvent,
    GeminiInterruptedEvent,
    GeminiLiveReceiveAdapter,
    GeminiLiveSetupCompleteEvent,
    GeminiOutputTranscriptEvent,
    GeminiTurnCompleteEvent,
)
from app.services.twilio.gemini_live_session_adapter import GeminiLiveSessionAdapter
from app.services.twilio.twilio_ingress_adapter import (
    TwilioIngressAdapter,
    TwilioMarkEvent,
    TwilioMediaDecodeErrorEvent,
    TwilioMediaEvent,
    TwilioMediaTrackIgnoredEvent,
    TwilioStartEvent,
    TwilioStopEvent,
)
from app.services.twilio.twilio_playback_adapter import TwilioPlaybackAdapter


class _DummyRealtimeSession:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def send_realtime_input(self, **kwargs) -> None:
        self.calls.append(kwargs)


class _DummyReceiveSession:
    def __init__(self, messages: list[object]) -> None:
        self.messages = list(messages)

    async def receive(self):
        for message in self.messages:
            yield message


class _DummyWebSocket:
    def __init__(self) -> None:
        self.sent_text: list[str] = []
        self.received_text: list[str] = []

    async def send_text(self, text: str) -> None:
        self.sent_text.append(text)

    async def receive_text(self) -> str:
        if not self.received_text:
            raise RuntimeError("no inbound messages queued")
        return self.received_text.pop(0)


@pytest.mark.asyncio
async def test_gemini_live_session_adapter_sends_activity_audio_and_stream_end():
    session = _DummyRealtimeSession()
    codec = TwilioMediaAudioCodec(input_batch_ms=20)
    adapter = GeminiLiveSessionAdapter(
        session=session,
        codec=codec,
        manual_activity_control=False,
        queue_maxsize=8,
    )

    sender_task = asyncio.create_task(adapter.run_sender())
    await adapter.queue_activity_start()
    await adapter.queue_pcm16k_payload(b"\x01\x02" * 320)
    await adapter.flush_pending_audio()
    await adapter.queue_activity_end()
    await adapter.close_input()
    await sender_task

    assert session.calls[0]["activity_start"] is not None
    assert session.calls[1]["audio"].mime_type == "audio/pcm;rate=16000"
    assert session.calls[1]["audio"].data == (b"\x01\x02" * 320)
    assert session.calls[2]["activity_end"] is not None
    assert session.calls[3]["audio_stream_end"] is True


@pytest.mark.asyncio
async def test_gemini_live_session_adapter_skips_audio_stream_end_for_manual_activity():
    session = _DummyRealtimeSession()
    codec = TwilioMediaAudioCodec(input_batch_ms=20)
    adapter = GeminiLiveSessionAdapter(
        session=session,
        codec=codec,
        manual_activity_control=True,
        queue_maxsize=8,
    )

    sender_task = asyncio.create_task(adapter.run_sender())
    await adapter.close_input()
    await sender_task

    assert session.calls == []


@pytest.mark.asyncio
async def test_twilio_playback_adapter_serializes_media_mark_and_clear():
    websocket = _DummyWebSocket()
    adapter = TwilioPlaybackAdapter(websocket=websocket, stream_sid="MZ123")

    await adapter.send_media_frames([b"\x01\x02", b"\x03\x04"])
    await adapter.send_mark("assistant-turn-1")
    await adapter.send_clear()

    payloads = [json.loads(item) for item in websocket.sent_text]

    assert payloads[0]["event"] == "media"
    assert payloads[0]["streamSid"] == "MZ123"
    assert payloads[0]["media"]["payload"] == base64.b64encode(b"\x01\x02").decode("ascii")
    assert payloads[1]["media"]["payload"] == base64.b64encode(b"\x03\x04").decode("ascii")
    assert payloads[2] == {
        "event": "mark",
        "streamSid": "MZ123",
        "mark": {"name": "assistant-turn-1"},
    }
    assert payloads[3] == {"event": "clear", "streamSid": "MZ123"}


@pytest.mark.asyncio
async def test_twilio_ingress_adapter_parses_start_mark_media_and_stop():
    websocket = _DummyWebSocket()
    codec = TwilioMediaAudioCodec(input_batch_ms=20)
    adapter = TwilioIngressAdapter(websocket=websocket, codec=codec)
    ulaw_payload = base64.b64encode(b"\xff" * 160).decode("ascii")
    websocket.received_text = [
        json.dumps({"event": "connected"}),
        json.dumps({"event": "start", "start": {"streamSid": "MZ1", "callSid": "CA1"}}),
        json.dumps({"event": "mark", "mark": {"name": "assistant-turn-1"}}),
        json.dumps({"event": "media", "media": {"track": "inbound", "payload": ulaw_payload}}),
        json.dumps({"event": "stop"}),
    ]

    start_event = await adapter.receive_event()
    mark_event = await adapter.receive_event()
    media_event = await adapter.receive_event()
    stop_event = await adapter.receive_event()

    assert isinstance(start_event, TwilioStartEvent)
    assert start_event.stream_sid == "MZ1"
    assert start_event.call_sid == "CA1"
    assert isinstance(mark_event, TwilioMarkEvent)
    assert mark_event.mark_name == "assistant-turn-1"
    assert isinstance(media_event, TwilioMediaEvent)
    assert media_event.decoded_audio.pcm8k != b""
    assert media_event.decoded_audio.pcm16k != b""
    assert isinstance(stop_event, TwilioStopEvent)


@pytest.mark.asyncio
async def test_twilio_ingress_adapter_reports_ignored_track_and_decode_error(monkeypatch):
    websocket = _DummyWebSocket()
    codec = TwilioMediaAudioCodec(input_batch_ms=20)
    adapter = TwilioIngressAdapter(websocket=websocket, codec=codec)
    monkeypatch.setattr(codec, "decode_twilio_payload", lambda _payload: (_ for _ in ()).throw(ValueError("boom")))
    websocket.received_text = [
        json.dumps({"event": "media", "media": {"track": "outbound", "payload": "abc"}}),
        json.dumps({"event": "media", "media": {"track": "inbound", "payload": "abc"}}),
    ]

    ignored_event = await adapter.receive_event()
    error_event = await adapter.receive_event()

    assert isinstance(ignored_event, TwilioMediaTrackIgnoredEvent)
    assert ignored_event.track == "outbound"
    assert isinstance(error_event, TwilioMediaDecodeErrorEvent)


@pytest.mark.asyncio
async def test_gemini_live_receive_adapter_yields_structured_events():
    audio_payload = base64.b64encode(b"\x01\x02\x03\x04").decode("ascii")
    session = _DummyReceiveSession(
        [
            SimpleNamespace(
                setup_complete=SimpleNamespace(session_id="session-1"),
                server_content=SimpleNamespace(
                    input_transcription=SimpleNamespace(text="こんにちは", finished=True),
                    output_transcription=SimpleNamespace(text="承知しました", finished=False),
                    interrupted=True,
                    model_turn=SimpleNamespace(
                        parts=[
                            SimpleNamespace(text="meta"),
                            SimpleNamespace(
                                text=None,
                                inline_data=SimpleNamespace(
                                    data=audio_payload,
                                    mime_type="audio/pcm;rate=24000",
                                ),
                            ),
                        ]
                    ),
                    turn_complete=True,
                    turn_complete_reason=SimpleNamespace(value="stop"),
                ),
            )
        ]
    )
    adapter = GeminiLiveReceiveAdapter(session=session)

    events = [event async for event in adapter.receive_events()]

    assert isinstance(events[0], GeminiLiveSetupCompleteEvent)
    assert events[0].session_id == "session-1"
    assert isinstance(events[1], GeminiInputTranscriptEvent)
    assert events[1].text == "こんにちは"
    assert events[1].final is True
    assert isinstance(events[2], GeminiOutputTranscriptEvent)
    assert events[2].text == "承知しました"
    assert events[2].final is False
    assert isinstance(events[3], GeminiInterruptedEvent)
    assert isinstance(events[4], GeminiAssistantMetaTextEvent)
    assert events[4].text == "meta"
    assert isinstance(events[5], GeminiAssistantAudioEvent)
    assert events[5].pcm_bytes == b"\x01\x02\x03\x04"
    assert events[5].mime_type == "audio/pcm;rate=24000"
    assert isinstance(events[6], GeminiTurnCompleteEvent)
    assert events[6].reason == "stop"
