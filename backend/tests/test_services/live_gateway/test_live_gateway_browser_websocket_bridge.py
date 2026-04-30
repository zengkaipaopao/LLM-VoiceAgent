import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.live_gateway.browser_websocket_bridge import BrowserLiveWebSocketBridge


class _FakeWebSocket:
    def __init__(self):
        self.sent: list[dict] = []

    async def send_json(self, payload):
        self.sent.append(payload)


@pytest.mark.asyncio
async def test_handle_text_input_sends_text_and_activity_end():
    websocket = _FakeWebSocket()
    session = SimpleNamespace(send_realtime_input=AsyncMock())

    await BrowserLiveWebSocketBridge()._handle_text_input(
        websocket=websocket,
        send_lock=asyncio.Lock(),
        session=session,
        payload={"text": "こんにちは"},
    )

    assert session.send_realtime_input.await_count == 2
    assert session.send_realtime_input.await_args_list[0].kwargs == {"text": "こんにちは"}
    assert "activity_end" in session.send_realtime_input.await_args_list[1].kwargs


@pytest.mark.asyncio
async def test_handle_audio_chunk_rejects_invalid_payload_with_warning():
    websocket = _FakeWebSocket()
    session = SimpleNamespace(send_realtime_input=AsyncMock())

    await BrowserLiveWebSocketBridge()._handle_audio_chunk(
        websocket=websocket,
        send_lock=asyncio.Lock(),
        session=session,
        payload={"data": "not base64!!"},
    )

    session.send_realtime_input.assert_not_awaited()
    assert websocket.sent == [
        {"type": "warning", "message": "Invalid audio chunk payload."}
    ]


@pytest.mark.asyncio
async def test_forward_server_content_maps_transcripts_text_audio_and_turn_events():
    websocket = _FakeWebSocket()
    content = SimpleNamespace(
        input_transcription=SimpleNamespace(text="ユーザー", finished=True),
        output_transcription=SimpleNamespace(text="AI", finished=False),
        model_turn=SimpleNamespace(
            parts=[
                SimpleNamespace(text="hello", inline_data=None),
                SimpleNamespace(
                    text=None,
                    inline_data=SimpleNamespace(
                        data=b"abc",
                        mime_type="audio/pcm;rate=24000",
                    ),
                ),
            ]
        ),
        interrupted=True,
        turn_complete=True,
        turn_complete_reason=SimpleNamespace(value="STOP"),
    )

    await BrowserLiveWebSocketBridge()._forward_server_content(
        websocket=websocket,
        send_lock=asyncio.Lock(),
        content=content,
    )

    assert websocket.sent == [
        {"type": "input_transcript", "text": "ユーザー", "final": True},
        {"type": "output_transcript", "text": "AI", "final": False},
        {"type": "text", "text": "hello"},
        {
            "type": "audio_chunk",
            "mime_type": "audio/pcm;rate=24000",
            "data": "YWJj",
        },
        {"type": "interrupted"},
        {"type": "turn_complete", "reason": "STOP"},
    ]
