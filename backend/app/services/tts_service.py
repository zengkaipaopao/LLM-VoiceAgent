from __future__ import annotations

import base64
import logging

import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.schemas.tts import TtsRequest, TtsResponse

logger = logging.getLogger(__name__)


class TtsService:
    _endpoint = "https://api.openai.com/v1/audio/speech"

    async def synthesize(self, payload: TtsRequest) -> TtsResponse:
        if not settings.openai_api_key:
            raise HTTPException(status_code=503, detail="未配置 OpenAI API Key")

        request_body = {
            "model": payload.model,
            "voice": payload.voice,
            "input": payload.text,
            "format": payload.format,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                self._endpoint,
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json=request_body,
            )

        if response.is_error:
            logger.error("TTS synthesis failed: %s", response.text)
            raise HTTPException(status_code=response.status_code, detail="生成语音失败，请稍后再试。")

        audio_base64 = base64.b64encode(response.content).decode("utf-8")
        content_type = response.headers.get("content-type") or f"audio/{payload.format}"
        return TtsResponse(audio_base64=audio_base64, content_type=content_type)


tts_service = TtsService()
