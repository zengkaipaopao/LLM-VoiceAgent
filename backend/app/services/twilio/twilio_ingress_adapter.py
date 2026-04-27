from __future__ import annotations

import json
from dataclasses import dataclass

from fastapi import WebSocket

from app.services.twilio.audio_codec import (
    DecodedTwilioInboundAudio,
    TwilioMediaAudioCodec,
)


@dataclass(slots=True)
class TwilioStartEvent:
    stream_sid: str | None
    call_sid: str | None


@dataclass(slots=True)
class TwilioMarkEvent:
    mark_name: str


@dataclass(slots=True)
class TwilioMediaEvent:
    decoded_audio: DecodedTwilioInboundAudio


@dataclass(slots=True)
class TwilioMediaTrackIgnoredEvent:
    track: str


@dataclass(slots=True)
class TwilioMediaDecodeErrorEvent:
    error: Exception


@dataclass(slots=True)
class TwilioStopEvent:
    pass


TwilioIngressEvent = (
    TwilioStartEvent
    | TwilioMarkEvent
    | TwilioMediaEvent
    | TwilioMediaTrackIgnoredEvent
    | TwilioMediaDecodeErrorEvent
    | TwilioStopEvent
)


@dataclass(slots=True)
class TwilioIngressAdapter:
    websocket: WebSocket
    codec: TwilioMediaAudioCodec

    async def receive_event(self) -> TwilioIngressEvent:
        while True:
            raw = await self.websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue

            event_type = str(payload.get("event") or "").strip().lower()
            if event_type == "connected":
                continue

            if event_type == "mark":
                mark_payload = payload.get("mark") or {}
                if isinstance(mark_payload, dict):
                    mark_name = str(mark_payload.get("name") or "").strip()
                else:
                    mark_name = ""
                return TwilioMarkEvent(mark_name=mark_name)

            if event_type == "start":
                start = payload.get("start") or {}
                stream_sid = (
                    str(start.get("streamSid") or payload.get("streamSid") or "").strip() or None
                )
                call_sid = str(start.get("callSid") or payload.get("callSid") or "").strip() or None
                return TwilioStartEvent(stream_sid=stream_sid, call_sid=call_sid)

            if event_type == "media":
                media = payload.get("media") or {}
                track = str(media.get("track") or "").strip().lower()
                if track and "inbound" not in track:
                    return TwilioMediaTrackIgnoredEvent(track=track)
                encoded = media.get("payload")
                if not isinstance(encoded, str) or not encoded.strip():
                    continue
                try:
                    decoded_audio = self.codec.decode_twilio_payload(encoded)
                except Exception as exc:
                    return TwilioMediaDecodeErrorEvent(error=exc)
                return TwilioMediaEvent(decoded_audio=decoded_audio)

            if event_type == "stop":
                return TwilioStopEvent()
