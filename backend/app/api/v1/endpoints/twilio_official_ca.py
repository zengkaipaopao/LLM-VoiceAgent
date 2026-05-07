from fastapi import APIRouter, Query, WebSocket

from app.services.twilio.media_stream_bootstrap import receive_twilio_media_stream_start
from app.services.twilio.official_conversational_agents import (
    bridge_twilio_to_official_conversational_agents,
)
from app.services.twilio.twiml_builders import _verify_websocket_or_close

router = APIRouter()


@router.websocket(
    "/voice/stream/official-ca",
    name="twilio_voice_official_conversational_agents_stream",
)
async def twilio_voice_official_conversational_agents_stream(
    websocket: WebSocket,
    prompt_code: str | None = Query(default=None),
    voice_name: str | None = Query(default=None),
):
    if not await _verify_websocket_or_close(websocket):
        return
    await websocket.accept()
    bootstrap = await receive_twilio_media_stream_start(
        websocket,
        prompt_code=prompt_code,
        voice_name=voice_name,
    )
    if bootstrap is None:
        return
    await bridge_twilio_to_official_conversational_agents(
        websocket=websocket,
        bootstrap=bootstrap,
    )
