from fastapi import APIRouter

from app.schemas.tts import TtsRequest, TtsResponse
from app.services.tts_service import tts_service

router = APIRouter()


@router.post("", response_model=TtsResponse, summary="文本转语音（OpenAI TTS）")
async def synthesize_speech(payload: TtsRequest) -> TtsResponse:
    return await tts_service.synthesize(payload)
