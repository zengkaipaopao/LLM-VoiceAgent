from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Protocol

from google.genai import types

from app.services.twilio.audio_codec import TwilioMediaAudioCodec

_LIVE_AUDIO_STREAM_END = object()
_LIVE_ACTIVITY_START = object()
_LIVE_ACTIVITY_END = object()


class GeminiRealtimeSession(Protocol):
    async def send_realtime_input(
        self,
        *,
        media: object | None = None,
        audio: object | None = None,
        audio_stream_end: bool | None = None,
        video: object | None = None,
        text: str | None = None,
        activity_start: object | None = None,
        activity_end: object | None = None,
    ) -> None: ...


@dataclass(slots=True)
class GeminiLiveSessionAdapter:
    session: GeminiRealtimeSession
    codec: TwilioMediaAudioCodec
    manual_activity_control: bool
    queue_maxsize: int = 64
    _queue: asyncio.Queue[bytes | object] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._queue = asyncio.Queue(maxsize=max(1, self.queue_maxsize))

    async def queue_audio(self, audio_bytes: bytes) -> None:
        if audio_bytes:
            await self._queue.put(audio_bytes)

    async def queue_activity_start(self) -> None:
        await self._queue.put(_LIVE_ACTIVITY_START)

    async def queue_activity_end(self) -> None:
        await self._queue.put(_LIVE_ACTIVITY_END)

    async def queue_pcm16k_payload(self, audio_bytes: bytes) -> None:
        for batch in self.codec.queue_inbound_audio(audio_bytes):
            await self.queue_audio(batch)

    async def flush_pending_audio(self) -> None:
        pending_audio = self.codec.flush_inbound_audio()
        if pending_audio:
            await self.queue_audio(pending_audio)

    async def close_input(self) -> None:
        await self.flush_pending_audio()
        await self._queue.put(_LIVE_AUDIO_STREAM_END)

    async def run_sender(self) -> None:
        while True:
            queued = await self._queue.get()
            if queued is _LIVE_ACTIVITY_START:
                await self.session.send_realtime_input(activity_start=types.ActivityStart())
                continue
            if queued is _LIVE_ACTIVITY_END:
                await self.session.send_realtime_input(activity_end=types.ActivityEnd())
                continue
            if queued is _LIVE_AUDIO_STREAM_END:
                if not self.manual_activity_control:
                    await self.session.send_realtime_input(audio_stream_end=True)
                return
            await self.session.send_realtime_input(
                audio=types.Blob(data=queued, mime_type="audio/pcm;rate=16000")
            )
