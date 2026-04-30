from fastapi import APIRouter, Query, WebSocket

from app.services.twilio.media_stream_websocket_service import TwilioMediaStreamWebSocketService
from app.services.twilio.twiml_builders import _verify_websocket_or_close

router = APIRouter()
media_stream_websocket_service = TwilioMediaStreamWebSocketService()


@router.websocket("/voice/stream", name="twilio_voice_media_stream")
async def twilio_voice_media_stream(
    websocket: WebSocket,
    prompt_code: str | None = Query(default=None),
    voice_name: str | None = Query(default=None),
):
    if not await _verify_websocket_or_close(websocket):
        return
    await websocket.accept()
    await media_stream_websocket_service.run(
        websocket=websocket,
        prompt_code=prompt_code,
        voice_name=voice_name,
    )
