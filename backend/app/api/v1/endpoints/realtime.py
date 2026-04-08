"""
Realtime websocket gateway with provider-aware routing.
"""
import asyncio
import base64
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from google import genai
from google.genai import types
from starlette.websockets import WebSocketState

from app.api.deps import require_api_key, verify_websocket_api_key
from app.core.config import settings
from app.core.model_defaults import require_live_model
from app.core.database import AsyncSessionLocal
from app.schemas.base import ResponseBase
from app.schemas.live import LiveAuthTokenRequest, LiveAuthTokenResponse
from app.services.live_gateway import provider_available, resolve_live_provider
from app.services.prompt_runtime_resolver import resolve_prompt_runtime
from app.services.prompt_service import PromptService

router = APIRouter()
logger = logging.getLogger(__name__)

ALLOWED_MODALITIES = {"AUDIO", "TEXT"}


def _parse_modalities(raw_value: str | None) -> list[str]:
    if not raw_value:
        return ["AUDIO"]

    modalities = [item.strip().upper() for item in raw_value.split(",") if item.strip()]
    filtered = [item for item in modalities if item in ALLOWED_MODALITIES]
    if not filtered:
        return ["AUDIO"]
    return list(dict.fromkeys(filtered))


def _normalize_modalities_for_model(
    model: str,
    modalities: list[str],
) -> tuple[list[str], str | None]:
    """
    Keep a conservative compatibility guard for preview models.
    """
    normalized_model = model.lower()
    if "gemini-3.1-flash-live-preview" in normalized_model and modalities != ["AUDIO"]:
        return ["AUDIO"], "This preview model currently runs in AUDIO-only mode in this test tab."
    return modalities, None


def _encode_audio_chunk(data: Any) -> str | None:
    if data is None:
        return None
    if isinstance(data, bytes | bytearray | memoryview):
        return base64.b64encode(bytes(data)).decode("ascii")
    if isinstance(data, str):
        return data
    return None


def _decode_audio_chunk(encoded: str) -> bytes:
    return base64.b64decode(encoded.encode("ascii"), validate=True)


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


def _build_live_config(
    *,
    modalities: list[str],
    voice_name: str | None,
    system_instruction: str | None,
) -> types.LiveConnectConfig:
    config_payload: dict[str, Any] = {
        "response_modalities": modalities,
        "input_audio_transcription": {},
        "output_audio_transcription": {},
    }

    if "AUDIO" in modalities and voice_name:
        config_payload["speech_config"] = {
            "voice_config": {
                "prebuilt_voice_config": {
                    "voice_name": voice_name,
                }
            }
        }

    if system_instruction:
        config_payload["system_instruction"] = system_instruction

    # Keep browser direct mode simple: the client streams microphone audio continuously,
    # while Gemini Live owns turn detection. Explicit activity tuning is necessary here
    # because the default preview-model behavior is too conservative for multi-turn browser
    # conversations over a long-running audio stream.
    config_payload["realtime_input_config"] = types.RealtimeInputConfig(
        automatic_activity_detection=types.AutomaticActivityDetection(
            disabled=False,
            start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_HIGH,
            end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_HIGH,
            prefix_padding_ms=40,
            silence_duration_ms=200,
        )
        ,
        activity_handling=types.ActivityHandling.START_OF_ACTIVITY_INTERRUPTS,
        turn_coverage=types.TurnCoverage.TURN_INCLUDES_ONLY_ACTIVITY,
    )

    return types.LiveConnectConfig(**config_payload)


def _build_browser_live_connect_config(
    *,
    modalities: list[str],
    voice_name: str | None,
    system_instruction: str | None,
) -> types.LiveConnectConfig:
    config_payload: dict[str, Any] = {
        "response_modalities": modalities,
        "input_audio_transcription": {},
        "output_audio_transcription": {},
    }

    if "AUDIO" in modalities and voice_name:
        config_payload["speech_config"] = {
            "voice_config": {
                "prebuilt_voice_config": {
                    "voice_name": voice_name,
                }
            }
        }

    if system_instruction:
        config_payload["system_instruction"] = system_instruction

    return types.LiveConnectConfig(**config_payload)


async def _resolve_system_instruction(
    *,
    system_instruction: str | None,
    template_code: str | None,
) -> tuple[str | None, str | None, str | None, str | None]:
    manual_instruction = (system_instruction or "").strip()
    if manual_instruction:
        return manual_instruction, None, None, None

    code = (template_code or "").strip()
    if not code:
        return None, None, None, None

    async with AsyncSessionLocal() as db:
        prompt_service = PromptService(db)
        runtime = await resolve_prompt_runtime(
            prompt_service,
            template_code=code,
            default_code=code,
            render_system_instruction=True,
            missing_notice=f"Prompt template '{code}' not found or inactive.",
        )
        if not runtime.template:
            return None, f"Prompt template '{code}' not found or inactive.", None, None

        return runtime.system_instruction, runtime.notice, runtime.voice_id, runtime.llm_model


@router.post(
    "/auth-token",
    response_model=ResponseBase[LiveAuthTokenResponse],
)
async def create_live_auth_token(
    payload: LiveAuthTokenRequest,
    _auth: None = Depends(require_api_key),
):
    resolved_system_instruction, prompt_notice, prompt_voice, prompt_model = await _resolve_system_instruction(
        system_instruction=payload.system_instruction,
        template_code=payload.template_code,
    )
    if prompt_notice:
        logger.info("Live auth token prompt notice: %s", prompt_notice)

    selected_model = require_live_model(
        payload.model or prompt_model or settings.default_live_model,
        source="Voice test model",
    )
    selected_modalities, _ = _normalize_modalities_for_model(
        selected_model,
        payload.modalities or _parse_modalities(settings.default_live_modalities),
    )
    requested_voice = (payload.voice or "").strip() or None
    selected_voice = requested_voice or prompt_voice or (settings.default_live_voice or "").strip() or None

    constrained_config = _build_browser_live_connect_config(
        modalities=selected_modalities,
        voice_name=selected_voice,
        system_instruction=resolved_system_instruction,
    )
    auth_client = genai.Client(
        api_key=settings.google_api_key,
        http_options={"api_version": "v1alpha"},
    )
    auth_token = auth_client.auth_tokens.create(
        config=types.CreateAuthTokenConfig(
            uses=1,
            new_session_expire_time=datetime.now(UTC) + timedelta(minutes=5),
            expire_time=datetime.now(UTC) + timedelta(minutes=30),
            live_connect_constraints=types.LiveConnectConstraints(
                model=selected_model,
                config=constrained_config,
            ),
            lock_additional_fields=[],
        )
    )

    return ResponseBase(
        success=True,
        data=LiveAuthTokenResponse(
            auth_token=auth_token.name or "",
            model=selected_model,
            modalities=selected_modalities,
            voice=selected_voice,
            template_code=(payload.template_code or "").strip() or None,
            system_instruction=resolved_system_instruction,
            display_endpoint=(
                "Gemini Live client-to-server (ephemeral token, direct browser connection)"
            ),
        ),
    )


@router.websocket("/ws")
async def live_websocket(
    websocket: WebSocket,
    provider: str | None = Query(
        default=None,
        description=(
            "Realtime provider, e.g. gemini/openai. "
            "Optional; inferred from model when omitted."
        ),
    ),
    model: str | None = Query(
        default=None,
        description="Realtime model. Defaults to settings.default_live_model.",
    ),
    modalities: str | None = Query(
        default=None,
        description="Comma-separated response modalities, e.g. AUDIO or AUDIO,TEXT.",
    ),
    voice: str | None = Query(
        default=None,
        description="Optional prebuilt voice name used for audio output.",
    ),
    template_code: str | None = Query(
        default=None,
        description="Prompt template code. Used when system_instruction is not provided.",
    ),
    system_instruction: str | None = Query(default=None),
):
    """
    Bidirectional websocket bridge:
    frontend <-> backend websocket <-> provider live session.
    """
    await websocket.accept()

    is_authorized, auth_error = verify_websocket_api_key(websocket)
    if not is_authorized:
        await websocket.send_json(
            {
                "type": "error",
                "error": auth_error or "Unauthorized websocket request.",
            }
        )
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    resolved_system_instruction, prompt_notice, prompt_voice, prompt_model = await _resolve_system_instruction(
        system_instruction=system_instruction,
        template_code=template_code,
    )
    try:
        selected_model = require_live_model(
            model or prompt_model or settings.default_live_model,
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

    selected_provider = resolve_live_provider(provider, selected_model)
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

    requested_modalities = _parse_modalities(modalities or settings.default_live_modalities)
    selected_modalities, modality_notice = _normalize_modalities_for_model(
        selected_model,
        requested_modalities,
    )
    requested_voice = (voice or "").strip() or None
    selected_voice = requested_voice or prompt_voice or (settings.default_live_voice or "").strip() or None
    prompt_voice_notice = None
    if not requested_voice and prompt_voice:
        prompt_voice_notice = f"Using prompt voice_id: {prompt_voice}"

    send_lock = asyncio.Lock()
    client = genai.Client(api_key=settings.google_api_key)
    live_config = _build_live_config(
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
                    "template_code": (template_code or "").strip() or None,
                },
            )
            if modality_notice:
                await _safe_send_json(
                    websocket,
                    send_lock,
                    {"type": "warning", "message": modality_notice},
                )
            if prompt_notice:
                await _safe_send_json(
                    websocket,
                    send_lock,
                    {"type": "warning", "message": prompt_notice},
                )
            if prompt_voice_notice:
                await _safe_send_json(
                    websocket,
                    send_lock,
                    {"type": "warning", "message": prompt_voice_notice},
                )

            async def client_to_live() -> None:
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
                        text = str(payload.get("text", "")).strip()
                        if text:
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
                        continue

                    if event_type == "audio_chunk":
                        encoded = payload.get("data")
                        if not isinstance(encoded, str) or not encoded.strip():
                            continue
                        mime_type = str(payload.get("mime_type") or "audio/pcm;rate=16000")
                        try:
                            audio_bytes = _decode_audio_chunk(encoded)
                        except Exception:
                            await _safe_send_json(
                                websocket,
                                send_lock,
                                {"type": "warning", "message": "Invalid audio chunk payload."},
                            )
                            continue
                        await _safe_forward_realtime_input(
                            session=session,
                            websocket=websocket,
                            lock=send_lock,
                            input_name="audio_chunk",
                            audio=types.Blob(data=audio_bytes, mime_type=mime_type),
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

            async def live_to_client() -> None:
                try:
                    async for message in session.receive():
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
                            content = message.server_content

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
                                        encoded_chunk = _encode_audio_chunk(part.inline_data.data)
                                        if encoded_chunk:
                                            await _safe_send_json(
                                                websocket,
                                                send_lock,
                                                {
                                                    "type": "audio_chunk",
                                                    "mime_type": (
                                                        part.inline_data.mime_type
                                                        or "audio/pcm;rate=24000"
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
                except Exception as exc:
                    logger.warning("Live receive loop closed: %s", exc)
                    await _safe_send_json(
                        websocket,
                        send_lock,
                        {"type": "warning", "message": "Live receive loop closed."},
                    )

            await asyncio.gather(client_to_live(), live_to_client())

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
