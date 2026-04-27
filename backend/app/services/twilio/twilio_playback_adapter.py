from __future__ import annotations

import asyncio
import base64
import json
from dataclasses import dataclass, field

from fastapi import WebSocket


@dataclass(slots=True)
class TwilioPlaybackAdapter:
    websocket: WebSocket
    stream_sid: str | None = None
    _send_lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)

    def bind_stream_sid(self, stream_sid: str | None) -> None:
        self.stream_sid = stream_sid or None

    @property
    def active(self) -> bool:
        return bool(self.stream_sid)

    async def send_event(self, payload: dict[str, object]) -> None:
        async with self._send_lock:
            await self.websocket.send_text(json.dumps(payload))

    async def send_clear(self) -> bool:
        if not self.stream_sid:
            return False
        await self.send_event({"event": "clear", "streamSid": self.stream_sid})
        return True

    async def send_mark(self, mark_name: str) -> bool:
        if not self.stream_sid:
            return False
        await self.send_event(
            {
                "event": "mark",
                "streamSid": self.stream_sid,
                "mark": {"name": mark_name},
            }
        )
        return True

    async def send_media_frames(self, frames: list[bytes]) -> int:
        if not self.stream_sid or not frames:
            return 0
        for frame in frames:
            await self.send_event(
                {
                    "event": "media",
                    "streamSid": self.stream_sid,
                    "media": {
                        "payload": base64.b64encode(frame).decode("ascii"),
                    },
                }
            )
        return len(frames)
