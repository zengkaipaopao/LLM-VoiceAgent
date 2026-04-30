"""
Realtime websocket gateway with provider-aware routing.
"""
import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query, WebSocket, status
from google import genai
from google.genai import types

from app.api.deps import require_api_key, verify_websocket_api_key
from app.core.config import settings
from app.core.model_defaults import require_live_model
from app.schemas.base import ResponseBase
from app.schemas.live import LiveAuthTokenRequest, LiveAuthTokenResponse
from app.services.live_gateway import (
    BrowserLiveWebSocketBridge,
    BrowserLiveWebSocketParams,
    build_browser_live_connect_config,
    normalize_modalities_for_model,
    parse_modalities,
    resolve_system_instruction,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/auth-token",
    response_model=ResponseBase[LiveAuthTokenResponse],
)
async def create_live_auth_token(
    payload: LiveAuthTokenRequest,
    _auth: None = Depends(require_api_key),
):
    resolved_system_instruction, prompt_notice, prompt_voice, prompt_model = await resolve_system_instruction(
        system_instruction=payload.system_instruction,
        template_code=payload.template_code,
    )
    if prompt_notice:
        logger.info("Live auth token prompt notice: %s", prompt_notice)

    selected_model = require_live_model(
        payload.model or prompt_model or settings.default_live_model,
        source="Voice test model",
    )
    selected_modalities, _ = normalize_modalities_for_model(
        selected_model,
        payload.modalities or parse_modalities(settings.default_live_modalities),
    )
    requested_voice = (payload.voice or "").strip() or None
    selected_voice = requested_voice or prompt_voice or (settings.default_live_voice or "").strip() or None

    constrained_config = build_browser_live_connect_config(
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

    await BrowserLiveWebSocketBridge().handle(
        websocket,
        BrowserLiveWebSocketParams(
            provider=provider,
            model=model,
            modalities=modalities,
            voice=voice,
            template_code=template_code,
            system_instruction=system_instruction,
        ),
    )
