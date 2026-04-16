"""
Helpers for bootstrapping a bidirectional Twilio Media Streams session.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from fastapi import WebSocket, WebSocketDisconnect

from app.services.twilio.normalizers import _normalize_voice_name_token
from app.services.twilio.twiml_builders import _extract_stream_custom_parameters


@dataclass(frozen=True)
class TwilioMediaStreamBootstrap:
    initial_payload: dict[str, object]
    stream_sid: str | None
    call_sid: str | None
    prompt_code: str | None
    voice_name: str | None
    from_number: str | None
    to_number: str | None


async def receive_twilio_media_stream_start(
    websocket: WebSocket,
    *,
    prompt_code: str | None,
    voice_name: str | None,
) -> TwilioMediaStreamBootstrap | None:
    prompt_code_from_stream = (prompt_code or "").strip() or None
    voice_name_from_stream = _normalize_voice_name_token(voice_name)

    while True:
        try:
            raw = await websocket.receive_text()
        except WebSocketDisconnect:
            return None

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue

        event_type = str(payload.get("event") or "").strip().lower()
        if event_type in {"connected", "mark"}:
            continue
        if event_type == "stop":
            try:
                await websocket.close()
            except Exception:
                pass
            return None
        if event_type != "start":
            continue

        start_payload = payload.get("start") or {}
        stream_sid: str | None = None
        call_sid: str | None = None
        if isinstance(start_payload, dict):
            stream_sid = str(start_payload.get("streamSid") or payload.get("streamSid") or "").strip() or None
            call_sid = str(start_payload.get("callSid") or payload.get("callSid") or "").strip() or None

        custom_parameters = _extract_stream_custom_parameters(payload)
        prompt_code_from_stream = custom_parameters.get("prompt_code") or prompt_code_from_stream
        voice_name_from_stream = _normalize_voice_name_token(
            custom_parameters.get("voice_name") or voice_name_from_stream
        )
        from_number_from_stream = (custom_parameters.get("from") or "").strip() or None
        to_number_from_stream = (custom_parameters.get("to") or "").strip() or None

        return TwilioMediaStreamBootstrap(
            initial_payload=payload,
            stream_sid=stream_sid,
            call_sid=call_sid,
            prompt_code=prompt_code_from_stream,
            voice_name=voice_name_from_stream,
            from_number=from_number_from_stream,
            to_number=to_number_from_stream,
        )
