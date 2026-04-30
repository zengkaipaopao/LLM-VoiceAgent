"""Runtime bridge for browser websocket <-> Gemini Live sessions."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

from fastapi import WebSocket, status
from google import genai
from google.genai import types
from starlette.websockets import WebSocketDisconnect, WebSocketState

from app.core.config import settings
from app.core.model_defaults import require_live_model
from app.services.live_gateway.browser_realtime import (
    build_live_config,
    decode_audio_chunk,
    encode_audio_chunk,
    normalize_modalities_for_model,
    parse_modalities,
    resolve_system_instruction,
)
from app.services.live_gateway.provider_resolver import (
    provider_available,
    resolve_live_provider,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BrowserLiveWebSocketParams:
    provider: str | None = None
    model: str | None = None
    modalities: str | None = None
    voice: str | None = None
    template_code: str | None = None
    system_instruction: str | None = None


class BrowserLiveWebSocketBridge:
    """Own the long-running browser Live websocket bridge loops."""

    async def handle(
        self,
        websocket: WebSocket,
        params: BrowserLiveWebSocketParams,
    ) -> None:
        resolved_system_instruction, prompt_notice, prompt_voice, prompt_model = (
            await resolve_system_instruction(
                system_instruction=params.system_instruction,
                template_code=params.template_code,
            )
        )
        try:
            selected_model = require_live_model(
                params.model or prompt_model or settings.default_live_model,
                source="Voice test model",
            )
        except ValueError as exc:
            await websocket.send_json(
                {
                    "type": "error",
                    "error": str(exc),
                }
            )
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        selected_provider = resolve_live_provider(params.provider, selected_model)
        available, reason = provider_available(selected_provider)
        if not available:
            await websocket.send_json(
                {
                    "type": "error",
                    "error": reason or f"Live provider '{selected_provider}' is unavailable.",
                    "provider": selected_provider,
                }
            )
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        if selected_provider != "gemini":
            await websocket.send_json(
                {
                    "type": "error",
                    "error": (
                        f"Live provider '{selected_provider}' is reserved "
                        "but not implemented in this build."
                    ),
                    "provider": selected_provider,
                }
            )
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        requested_modalities = parse_modalities(
            params.modalities or settings.default_live_modalities
        )
        selected_modalities, modality_notice = normalize_modalities_for_model(
            selected_model,
            requested_modalities,
        )
        requested_voice = (params.voice or "").strip() or None
        selected_voice = (
            requested_voice
            or prompt_voice
            or (settings.default_live_voice or "").strip()
            or None
        )
        prompt_voice_notice = None
        if not requested_voice and prompt_voice:
            prompt_voice_notice = f"Using prompt voice_id: {prompt_voice}"

        send_lock = asyncio.Lock()
        client = genai.Client(api_key=settings.google_api_key)
        live_config = build_live_config(
            modalities=selected_modalities,
            voice_name=selected_voice,
            system_instruction=resolved_system_instruction,
        )

        try:
            async with client.aio.live.connect(model=selected_model, config=live_config) as session:
                await _safe_send_json(
                    websocket,
                    send_lock,
                    {
                        "type": "connected",
                        "provider": selected_provider,
                        "model": selected_model,
                        "modalities": selected_modalities,
                        "voice": selected_voice,
                        "template_code": (params.template_code or "").strip() or None,
                    },
                )
                await self._send_startup_warnings(
                    websocket=websocket,
                    send_lock=send_lock,
                    modality_notice=modality_notice,
                    prompt_notice=prompt_notice,
                    prompt_voice_notice=prompt_voice_notice,
                )

                await asyncio.gather(
                    self._client_to_live(
                        websocket=websocket,
                        send_lock=send_lock,
                        session=session,
                    ),
                    self._live_to_client(
                        websocket=websocket,
                        send_lock=send_lock,
                        session=session,
                    ),
                )

        except WebSocketDisconnect:
            logger.info("Live websocket disconnected by client.")
        except Exception as exc:
            logger.exception("Live websocket error: %s", exc)
            if websocket.client_state == WebSocketState.CONNECTED:
                await _safe_send_json(
                    websocket,
                    send_lock,
                    {"type": "error", "error": "Live websocket processing failed."},
                )
                await websocket.close(code=status.WS_1011_INTERNAL_ERROR)

    async def _send_startup_warnings(
        self,
        *,
        websocket: WebSocket,
        send_lock: asyncio.Lock,
        modality_notice: str | None,
        prompt_notice: str | None,
        prompt_voice_notice: str | None,
    ) -> None:
        for notice in (modality_notice, prompt_notice, prompt_voice_notice):
            if notice:
                await _safe_send_json(
                    websocket,
                    send_lock,
                    {"type": "warning", "message": notice},
                )

    async def _client_to_live(
        self,
        *,
        websocket: WebSocket,
        send_lock: asyncio.Lock,
        session: Any,
    ) -> None:
        while True:
            text_message = await websocket.receive_text()
            try:
                payload = json.loads(text_message)
            except json.JSONDecodeError:
                await _safe_send_json(
                    websocket,
                    send_lock,
                    {"type": "warning", "message": "Invalid JSON payload ignored."},
                )
                continue

            event_type = str(payload.get("type", "")).strip().lower()
            if event_type == "text":
                await self._handle_text_input(
                    websocket=websocket,
                    send_lock=send_lock,
                    session=session,
                    payload=payload,
                )
                continue

            if event_type == "audio_chunk":
                await self._handle_audio_chunk(
                    websocket=websocket,
                    send_lock=send_lock,
                    session=session,
                    payload=payload,
                )
                continue

            if event_type == "audio_end":
                await _safe_forward_realtime_input(
                    session=session,
                    websocket=websocket,
                    lock=send_lock,
                    input_name="audio_end",
                    audio_stream_end=True,
                )
                continue

            if event_type == "activity_end":
                await _safe_forward_realtime_input(
                    session=session,
                    websocket=websocket,
                    lock=send_lock,
                    input_name="activity_end",
                    activity_end=types.ActivityEnd(),
                )
                continue

            if event_type == "activity_start":
                await _safe_send_json(
                    websocket,
                    send_lock,
                    {
                        "type": "warning",
                        "message": "Ignored activity_start: this endpoint only uses explicit activity_end boundaries.",
                    },
                )
                continue

            if event_type == "ping":
                await _safe_send_json(websocket, send_lock, {"type": "pong"})
                continue

            if event_type == "close":
                try:
                    await session.close()
                except Exception as exc:
                    logger.warning("Live session close failed: %s", exc)
                return

            await _safe_send_json(
                websocket,
                send_lock,
                {"type": "warning", "message": f"Unsupported event type: {event_type}"},
            )

    async def _handle_text_input(
        self,
        *,
        websocket: WebSocket,
        send_lock: asyncio.Lock,
        session: Any,
        payload: dict[str, Any],
    ) -> None:
        text = str(payload.get("text", "")).strip()
        if not text:
            return
        accepted = await _safe_forward_realtime_input(
            session=session,
            websocket=websocket,
            lock=send_lock,
            input_name="text",
            text=text,
        )
        if accepted:
            await _safe_forward_realtime_input(
                session=session,
                websocket=websocket,
                lock=send_lock,
                input_name="text_activity_end",
                activity_end=types.ActivityEnd(),
            )

    async def _handle_audio_chunk(
        self,
        *,
        websocket: WebSocket,
        send_lock: asyncio.Lock,
        session: Any,
        payload: dict[str, Any],
    ) -> None:
        encoded = payload.get("data")
        if not isinstance(encoded, str) or not encoded.strip():
            return
        mime_type = str(payload.get("mime_type") or "audio/pcm;rate=16000")
        try:
            audio_bytes = decode_audio_chunk(encoded)
        except Exception:
            await _safe_send_json(
                websocket,
                send_lock,
                {"type": "warning", "message": "Invalid audio chunk payload."},
            )
            return
        await _safe_forward_realtime_input(
            session=session,
            websocket=websocket,
            lock=send_lock,
            input_name="audio_chunk",
            audio=types.Blob(data=audio_bytes, mime_type=mime_type),
        )

    async def _live_to_client(
        self,
        *,
        websocket: WebSocket,
        send_lock: asyncio.Lock,
        session: Any,
    ) -> None:
        try:
            async for message in session.receive():
                await self._forward_live_message(
                    websocket=websocket,
                    send_lock=send_lock,
                    message=message,
                )
        except Exception as exc:
            logger.warning("Live receive loop closed: %s", exc)
            await _safe_send_json(
                websocket,
                send_lock,
                {"type": "warning", "message": "Live receive loop closed."},
            )

    async def _forward_live_message(
        self,
        *,
        websocket: WebSocket,
        send_lock: asyncio.Lock,
        message: Any,
    ) -> None:
        if message.setup_complete:
            await _safe_send_json(
                websocket,
                send_lock,
                {
                    "type": "session_ready",
                    "session_id": message.setup_complete.session_id,
                },
            )

        if message.usage_metadata:
            usage = message.usage_metadata
            await _safe_send_json(
                websocket,
                send_lock,
                {
                    "type": "usage",
                    "total_tokens": usage.total_token_count,
                    "prompt_tokens": usage.prompt_token_count,
                    "response_tokens": usage.response_token_count,
                },
            )

        if message.server_content:
            await self._forward_server_content(
                websocket=websocket,
                send_lock=send_lock,
                content=message.server_content,
            )

        if message.tool_call and message.tool_call.function_calls:
            await _safe_send_json(
                websocket,
                send_lock,
                {
                    "type": "tool_call",
                    "calls": [
                        {
                            "id": call.id,
                            "name": call.name,
                            "args": call.args,
                        }
                        for call in message.tool_call.function_calls
                    ],
                },
            )

        if message.go_away:
            await _safe_send_json(
                websocket,
                send_lock,
                {
                    "type": "go_away",
                    "time_left": message.go_away.time_left,
                },
            )

    async def _forward_server_content(
        self,
        *,
        websocket: WebSocket,
        send_lock: asyncio.Lock,
        content: Any,
    ) -> None:
        if content.input_transcription and content.input_transcription.text:
            await _safe_send_json(
                websocket,
                send_lock,
                {
                    "type": "input_transcript",
                    "text": content.input_transcription.text,
                    "final": bool(content.input_transcription.finished),
                },
            )

        if content.output_transcription and content.output_transcription.text:
            await _safe_send_json(
                websocket,
                send_lock,
                {
                    "type": "output_transcript",
                    "text": content.output_transcription.text,
                    "final": bool(content.output_transcription.finished),
                },
            )

        if content.model_turn and content.model_turn.parts:
            for part in content.model_turn.parts:
                if part.text:
                    await _safe_send_json(
                        websocket,
                        send_lock,
                        {
                            "type": "text",
                            "text": part.text,
                        },
                    )

                if part.inline_data and part.inline_data.data:
                    encoded_chunk = encode_audio_chunk(part.inline_data.data)
                    if encoded_chunk:
                        await _safe_send_json(
                            websocket,
                            send_lock,
                            {
                                "type": "audio_chunk",
                                "mime_type": (
                                    part.inline_data.mime_type or "audio/pcm;rate=24000"
                                ),
                                "data": encoded_chunk,
                            },
                        )

        if content.interrupted:
            await _safe_send_json(
                websocket,
                send_lock,
                {"type": "interrupted"},
            )

        if content.turn_complete:
            reason = (
                str(content.turn_complete_reason.value)
                if content.turn_complete_reason
                else None
            )
            await _safe_send_json(
                websocket,
                send_lock,
                {"type": "turn_complete", "reason": reason},
            )


async def _safe_send_json(
    websocket: WebSocket,
    lock: asyncio.Lock,
    payload: dict[str, Any],
) -> None:
    async with lock:
        await websocket.send_json(payload)


async def _safe_forward_realtime_input(
    *,
    session: Any,
    websocket: WebSocket,
    lock: asyncio.Lock,
    input_name: str,
    **kwargs: Any,
) -> bool:
    try:
        await session.send_realtime_input(**kwargs)
        return True
    except Exception as exc:
        logger.warning("Live input rejected (%s): %s", input_name, exc)
        await _safe_send_json(
            websocket,
            lock,
            {"type": "warning", "message": f"Live input rejected ({input_name})."},
        )
        return False
