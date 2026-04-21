from __future__ import annotations

import asyncio
import audioop
import base64
import json
import logging
import uuid
from dataclasses import dataclass

import google.auth
import websockets
from fastapi import WebSocket, status
from google.auth.transport import requests as google_auth_requests
from starlette.websockets import WebSocketState
from starlette.websockets import WebSocketDisconnect
from websockets.protocol import State as WebsocketProtocolState

from app.core.config import settings
from app.services.twilio.debug_audio_capture import RollingPcmCapture
from app.services.twilio.media_stream_bootstrap import TwilioMediaStreamBootstrap
from app.services.twilio.trace_store import _append_call_trace

logger = logging.getLogger(__name__)

_TWILIO_AUDIO_SAMPLING_RATE = 8000
_AGENT_AUDIO_SAMPLING_RATE = 16000
_AGENT_AUDIO_ENCODING = "LINEAR16"
_TWILIO_FRAME_BYTES = 160
_VA_ENDPOINT_TEMPLATES = {
    "wss": "wss://{hostname}/ws/google.cloud.ces.v1.SessionService/BidiRunSession/locations/{location}",
}
_VA_HOSTNAME_MAP = {
    "dev": "autopush-ces.sandbox.googleapis.com",
    "prod": "ces.googleapis.com",
}
_PCM8K_RAW_DEBUG_VARIANT = "pcm8k_raw"
_PCM16K_RESAMPLED_DEBUG_VARIANT = "pcm16k_resampled"
_PCM8K_RAW_DEBUG_ARTIFACT = "inbound-pcm8k-raw"
_PCM16K_RESAMPLED_DEBUG_ARTIFACT = "inbound-pcm16k-resampled"


@dataclass(frozen=True)
class OfficialConversationalAgentsConfig:
    agent_id: str
    deployment_id: str | None
    environment: str
    location: str
    session_id: str
    virtual_agent_endpoint: str
    kickstart_text: str | None


def _extract_parent_app_from_deployment_id(deployment_id: str | None) -> str | None:
    token = (deployment_id or "").strip()
    if not token:
        return None
    marker = "/deployments/"
    if marker not in token:
        return None
    return token.split(marker, 1)[0].strip() or None


def _looks_like_official_ca_app_resource(resource_name: str | None) -> bool:
    token = (resource_name or "").strip()
    return bool(token) and "/apps/" in token and "/deployments/" not in token


def _looks_like_official_ca_deployment_resource(resource_name: str | None) -> bool:
    token = (resource_name or "").strip()
    return bool(token) and "/apps/" in token and "/deployments/" in token


def _looks_like_legacy_agent_resource(resource_name: str | None) -> bool:
    token = (resource_name or "").strip()
    return bool(token) and "/agents/" in token


def _extract_location_from_resource_name(resource_name: str | None) -> str | None:
    token = (resource_name or "").strip()
    if not token:
        return None
    parts = token.split("/")
    try:
        location_index = parts.index("locations")
    except ValueError:
        return None
    if location_index + 1 >= len(parts):
        return None
    return parts[location_index + 1].strip() or None


def _extract_project_id_from_resource_name(resource_name: str | None) -> str | None:
    token = (resource_name or "").strip()
    if not token:
        return None
    parts = token.split("/")
    if len(parts) >= 2 and parts[0] == "projects":
        return parts[1].strip() or None
    return None


def _build_virtual_agent_endpoint(*, location: str, environment: str) -> str:
    normalized_environment = (environment or "prod").strip().lower() or "prod"
    hostname = _VA_HOSTNAME_MAP.get(normalized_environment)
    if not hostname:
        raise ValueError(
            "TWILIO_OFFICIAL_CA_ENVIRONMENT 必须是 'dev' 或 'prod'。"
        )
    if not location:
        raise ValueError("Conversational Agents location 不能为空。")
    return _VA_ENDPOINT_TEMPLATES["wss"].format(hostname=hostname, location=location)


def build_official_conversational_agents_config() -> OfficialConversationalAgentsConfig:
    configured_agent_id = (settings.twilio_official_ca_agent_id or "").strip()
    deployment_id = (settings.twilio_official_ca_deployment_id or "").strip() or None
    if deployment_id and not _looks_like_official_ca_deployment_resource(deployment_id):
        raise ValueError(
            "TWILIO_OFFICIAL_CA_DEPLOYMENT_ID 必须是官方 Conversational Agents 的 deployment 资源名，"
            "格式类似 projects/<project>/locations/<region>/apps/<app-id>/deployments/<deployment-id>。"
        )
    if configured_agent_id and _looks_like_legacy_agent_resource(configured_agent_id):
        raise ValueError(
            "TWILIO_OFFICIAL_CA_AGENT_ID 当前是旧的 '/agents/' 资源名。"
            "官方 Twilio adapter 使用的是 Conversational Agents app/deployment 资源，"
            "请改用 TWILIO_OFFICIAL_CA_DEPLOYMENT_ID，或至少提供 "
            "projects/<project>/locations/<region>/apps/<app-id> 形式的 app 资源名。"
        )
    if configured_agent_id and not _looks_like_official_ca_app_resource(configured_agent_id):
        raise ValueError(
            "TWILIO_OFFICIAL_CA_AGENT_ID 必须是官方 Conversational Agents app 资源名，"
            "格式类似 projects/<project>/locations/<region>/apps/<app-id>。"
        )
    agent_id = configured_agent_id or _extract_parent_app_from_deployment_id(deployment_id)
    if not agent_id:
        raise ValueError(
            "官方 Conversational Agents 基线未配置。请设置 "
            "TWILIO_OFFICIAL_CA_DEPLOYMENT_ID，或显式设置 TWILIO_OFFICIAL_CA_AGENT_ID。"
        )

    location = _extract_location_from_resource_name(agent_id)
    if not location:
        raise ValueError(
            "无法从 Conversational Agents 资源名中解析 location。"
            "请检查 TWILIO_OFFICIAL_CA_AGENT_ID / DEPLOYMENT_ID。"
        )
    if location == "global":
        raise ValueError(
            "官方 Conversational Agents Twilio 适配链路通常要求区域化 location，"
            "不能使用 global。请在 Google 控制台的 Deployment / Connect platform 页面复制 "
            "projects/<project>/locations/<region>/apps/<app-id>/deployments/<deployment-id>。"
        )

    session_id = f"{agent_id}/sessions/{uuid.uuid4()}"
    environment = (settings.twilio_official_ca_environment or "prod").strip().lower() or "prod"
    virtual_agent_endpoint = _build_virtual_agent_endpoint(location=location, environment=environment)
    kickstart_text = (settings.twilio_official_ca_kickstart_text or "").strip() or None
    return OfficialConversationalAgentsConfig(
        agent_id=agent_id,
        deployment_id=deployment_id,
        environment=environment,
        location=location,
        session_id=session_id,
        virtual_agent_endpoint=virtual_agent_endpoint,
        kickstart_text=kickstart_text,
    )


def build_official_conversational_agents_stream_parameters(
    config: OfficialConversationalAgentsConfig,
) -> dict[str, str]:
    parameters = {
        "ca_session_id": config.session_id,
        "ca_virtual_agent_endpoint": config.virtual_agent_endpoint,
        "ca_environment": config.environment,
        "ca_agent_id": config.agent_id,
    }
    if config.deployment_id:
        parameters["ca_deployment_id"] = config.deployment_id
    return parameters


def _build_debug_capture(*, sample_rate: int, artifact_key: str) -> RollingPcmCapture:
    duration_seconds = max(1, settings.twilio_media_stream_debug_inbound_wav_seconds)
    return RollingPcmCapture(
        sample_rate=sample_rate,
        duration_seconds=duration_seconds,
        artifact_key=artifact_key,
    )


def _build_inbound_debug_captures() -> dict[str, RollingPcmCapture]:
    return {
        _PCM8K_RAW_DEBUG_VARIANT: _build_debug_capture(
            sample_rate=8000,
            artifact_key=_PCM8K_RAW_DEBUG_ARTIFACT,
        ),
        _PCM16K_RESAMPLED_DEBUG_VARIANT: _build_debug_capture(
            sample_rate=16000,
            artifact_key=_PCM16K_RESAMPLED_DEBUG_ARTIFACT,
        ),
    }


async def _persist_inbound_debug_wav(
    *,
    call_sid: str | None,
    captures: dict[str, RollingPcmCapture],
    trigger: str,
) -> None:
    if not settings.twilio_media_stream_debug_inbound_wav_enabled:
        return
    if not call_sid:
        return

    saved_audio_items = []
    for variant, capture in captures.items():
        if not capture.has_audio():
            continue
        saved_audio = await asyncio.to_thread(
            capture.save_wav,
            output_dir=settings.twilio_media_stream_debug_inbound_wav_dir,
            call_sid=call_sid,
        )
        if saved_audio:
            saved_audio_items.append((variant, saved_audio))

    if not saved_audio_items:
        await _append_call_trace(
            call_sid,
            event_type="inbound_debug_wav_skipped",
            text=f"trigger={trigger} reason=no_inbound_audio",
            level="info",
        )
        return

    await _append_call_trace(
        call_sid,
        event_type="inbound_debug_wav_saved",
        text=" ; ".join(
            [
                (
                    f"trigger={trigger} variant={variant} duration_ms={saved_audio.duration_ms} "
                    f"sample_rate={saved_audio.sample_rate} bytes={saved_audio.bytes} "
                    f"path={saved_audio.path}"
                )
                for variant, saved_audio in saved_audio_items
            ]
        ),
        level="success",
    )


def _get_adc_access_token_and_principal() -> tuple[str, str]:
    import os
    if settings.google_application_credentials:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_application_credentials
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    auth_request = google_auth_requests.Request()
    credentials.refresh(auth_request)
    token = (credentials.token or "").strip()
    if not token:
        raise RuntimeError("Google ADC 未返回可用 access token。")
    principal = (
        getattr(credentials, "service_account_email", None)
        or getattr(credentials, "_service_account_email", None)
        or credentials.__class__.__name__
    )
    return token, str(principal).strip()


def _build_va_config_message(session_id: str, deployment_id: str | None) -> dict[str, object]:
    payload: dict[str, object] = {
        "config": {
            "session": session_id,
            "inputAudioConfig": {
                "audioEncoding": _AGENT_AUDIO_ENCODING,
                "sampleRateHertz": _AGENT_AUDIO_SAMPLING_RATE,
            },
            "outputAudioConfig": {
                "audioEncoding": _AGENT_AUDIO_ENCODING,
                "sampleRateHertz": _AGENT_AUDIO_SAMPLING_RATE,
            },
        }
    }
    if deployment_id:
        payload["config"]["deployment"] = deployment_id
    return payload


def _extract_custom_parameter(
    bootstrap: TwilioMediaStreamBootstrap,
    key: str,
) -> str | None:
    return (bootstrap.custom_parameters.get(key) or "").strip() or None


async def bridge_twilio_to_official_conversational_agents(
    *,
    websocket: WebSocket,
    bootstrap: TwilioMediaStreamBootstrap,
) -> None:
    current_call_sid = bootstrap.call_sid
    stream_sid = bootstrap.stream_sid
    session_id = _extract_custom_parameter(bootstrap, "ca_session_id")
    deployment_id = _extract_custom_parameter(bootstrap, "ca_deployment_id")
    virtual_agent_endpoint = _extract_custom_parameter(bootstrap, "ca_virtual_agent_endpoint")
    environment = _extract_custom_parameter(bootstrap, "ca_environment") or "prod"
    agent_id = _extract_custom_parameter(bootstrap, "ca_agent_id")

    if not session_id or not virtual_agent_endpoint:
        await _append_call_trace(
            current_call_sid,
            event_type="configuration_error",
            text="官方 Conversational Agents 基线缺少 session_id 或 virtual_agent_endpoint。",
            level="error",
        )
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    project_id = _extract_project_id_from_resource_name(session_id)
    if not project_id:
        await _append_call_trace(
            current_call_sid,
            event_type="configuration_error",
            text="无法从官方 Conversational Agents session_id 解析 project_id。",
            level="error",
        )
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await _append_call_trace(
        current_call_sid,
        event_type="stream_start",
        text=(
            "prompt=official_conversational_agents "
            "route=official_conversational_agents "
            f"environment={environment}"
        ),
        level="success",
    )
    await _append_call_trace(
        current_call_sid,
        event_type="official_ca_runtime",
        text=(
            f"session_id={session_id} "
            f"deployment_id={deployment_id or '-'} "
            f"agent_id={agent_id or '-'} "
            f"endpoint={virtual_agent_endpoint}"
        ),
        level="info",
    )

    try:
        access_token, adc_principal = await asyncio.to_thread(_get_adc_access_token_and_principal)
    except Exception as exc:
        await _append_call_trace(
            current_call_sid,
            event_type="official_ca_auth_error",
            text=str(exc),
            level="error",
        )
        await websocket.close(code=1011, reason=str(exc)[:120])
        return
    await _append_call_trace(
        current_call_sid,
        event_type="official_ca_auth_context",
        text=f"adc_principal={adc_principal}",
        level="info",
    )

    inbound_debug_captures = _build_inbound_debug_captures()
    send_lock = asyncio.Lock()
    stop_event = asyncio.Event()
    ratecv_state_to_va = None
    ratecv_state_to_twilio = None
    va_ws = None

    async def _send_twilio_event(payload: dict[str, object]) -> None:
        async with send_lock:
            await websocket.send_text(json.dumps(payload))

    async def forward_twilio_to_va() -> None:
        nonlocal va_ws
        nonlocal stream_sid
        nonlocal ratecv_state_to_va
        try:
            while not stop_event.is_set():
                raw = await websocket.receive_text()
                payload = json.loads(raw)
                event_type = str(payload.get("event") or "").strip().lower()

                if event_type == "connected":
                    continue
                if event_type == "start":
                    start = payload.get("start") or {}
                    if isinstance(start, dict):
                        stream_sid = (
                            str(start.get("streamSid") or payload.get("streamSid") or "").strip() or stream_sid
                        )
                    continue
                if event_type == "mark":
                    mark_payload = payload.get("mark") or {}
                    mark_name = (
                        str(mark_payload.get("name") or "").strip()
                        if isinstance(mark_payload, dict)
                        else ""
                    )
                    if mark_name:
                        await _append_call_trace(
                            current_call_sid,
                            event_type="playback_mark",
                            text=mark_name,
                            level="info",
                        )
                    continue
                if event_type == "stop":
                    await _append_call_trace(current_call_sid, event_type="stream_stop", level="info")
                    stop_event.set()
                    if va_ws and va_ws.state != WebsocketProtocolState.CLOSED:
                        await va_ws.close()
                    return
                if event_type != "media":
                    continue

                media = payload.get("media") or {}
                encoded = media.get("payload")
                if not isinstance(encoded, str) or not encoded.strip():
                    continue

                audio_chunk = base64.b64decode(encoded)
                linear_audio = audioop.ulaw2lin(audio_chunk, 2)
                inbound_debug_captures[_PCM8K_RAW_DEBUG_VARIANT].append(linear_audio)
                resampled_linear_audio, ratecv_state_to_va = audioop.ratecv(
                    linear_audio,
                    2,
                    1,
                    _TWILIO_AUDIO_SAMPLING_RATE,
                    _AGENT_AUDIO_SAMPLING_RATE,
                    ratecv_state_to_va,
                )
                inbound_debug_captures[_PCM16K_RESAMPLED_DEBUG_VARIANT].append(
                    resampled_linear_audio
                )
                base64_pcm_payload = base64.b64encode(resampled_linear_audio).decode("utf-8")
                await va_ws.send(json.dumps({"realtimeInput": {"audio": base64_pcm_payload}}))
        except WebSocketDisconnect:
            stop_event.set()
            if va_ws and va_ws.state != WebsocketProtocolState.CLOSED:
                await va_ws.close()
            return

    async def forward_va_to_twilio() -> None:
        nonlocal ratecv_state_to_twilio
        assistant_started = False
        try:
            while not stop_event.is_set():
                va_response = await va_ws.recv()
                va_data = json.loads(va_response)

                session_output = va_data.get("sessionOutput")
                if isinstance(session_output, dict):
                    session_text = str(session_output.get("text") or "").strip()
                    if session_text:
                        await _append_call_trace(
                            current_call_sid,
                            event_type="assistant_text",
                            text=session_text,
                            level="success",
                        )

                    audio_b64 = session_output.get("audio")
                    if isinstance(audio_b64, str) and audio_b64.strip():
                        va_audio = base64.b64decode(audio_b64)
                        pcm_8khz_data, ratecv_state_to_twilio = audioop.ratecv(
                            va_audio,
                            2,
                            1,
                            _AGENT_AUDIO_SAMPLING_RATE,
                            _TWILIO_AUDIO_SAMPLING_RATE,
                            ratecv_state_to_twilio,
                        )
                        mulaw_audio = audioop.lin2ulaw(pcm_8khz_data, 2)
                        if not assistant_started:
                            assistant_started = True
                            await _append_call_trace(
                                current_call_sid,
                                event_type="assistant_audio_started",
                                text="audio/linear16",
                                level="success",
                            )
                        for index in range(0, len(mulaw_audio), _TWILIO_FRAME_BYTES):
                            encoded_va_audio = base64.b64encode(
                                mulaw_audio[index : index + _TWILIO_FRAME_BYTES]
                            ).decode("utf-8")
                            await _send_twilio_event(
                                {
                                    "event": "media",
                                    "streamSid": stream_sid,
                                    "media": {"payload": encoded_va_audio, "track": "outbound"},
                                }
                            )
                        await _append_call_trace(
                            current_call_sid,
                            event_type="assistant_audio_forwarded",
                            text=f"bytes={len(va_audio)}",
                            level="info",
                        )
                    continue

                if "endSession" in va_data:
                    await _append_call_trace(
                        current_call_sid,
                        event_type="official_ca_end_session",
                        text="Virtual agent requested session close.",
                        level="warning",
                    )
                    stop_event.set()
                    if websocket.client_state != WebSocketState.DISCONNECTED:
                        await websocket.close()
                    return
        except websockets.exceptions.ConnectionClosed:
            if stop_event.is_set():
                return
            raise

    auth_headers = {
        "Authorization": f"Bearer {access_token}",
        "X-Goog-User-Project": project_id,
    }

    try:
        va_ws = await websockets.connect(
            virtual_agent_endpoint,
            max_size=2**22,
            additional_headers=auth_headers,
        )
        await _append_call_trace(
            current_call_sid,
            event_type="official_ca_session_connected",
            text=f"project_id={project_id}",
            level="success",
        )
        await va_ws.send(json.dumps(_build_va_config_message(session_id, deployment_id)))
        await _append_call_trace(
            current_call_sid,
            event_type="official_ca_config_sent",
            text=f"deployment_id={deployment_id or '-'}",
            level="info",
        )

        kickstart_text = _extract_custom_parameter(bootstrap, "ca_kickstart_text")
        if kickstart_text:
            await va_ws.send(json.dumps({"realtimeInput": {"text": kickstart_text}}))
            await _append_call_trace(
                current_call_sid,
                event_type="official_ca_kickstart_sent",
                text=kickstart_text,
                level="info",
            )

        async with asyncio.TaskGroup() as task_group:
            task_group.create_task(forward_twilio_to_va())
            task_group.create_task(forward_va_to_twilio())
    except Exception as exc:
        await _append_call_trace(
            current_call_sid,
            event_type="official_ca_bridge_error",
            text=str(exc),
            level="error",
        )
        logger.exception("Official Conversational Agents bridge failed")
    finally:
        stop_event.set()
        try:
            await _persist_inbound_debug_wav(
                call_sid=current_call_sid,
                captures=inbound_debug_captures,
                trigger="stream_stop",
            )
        except Exception:
            logger.exception("Failed to persist official CA inbound debug audio")
        if va_ws and va_ws.state != WebsocketProtocolState.CLOSED:
            await va_ws.close()
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close()
