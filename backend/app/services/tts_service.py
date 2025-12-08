from __future__ import annotations

import base64
import logging
from threading import Lock
from typing import Optional

import httpx
from fastapi import HTTPException
from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials as ServiceAccountCredentials

from app.core.config import settings
from app.schemas.tts import TtsRequest, TtsResponse

logger = logging.getLogger(__name__)


class TtsService:
    _openai_endpoint = "https://api.openai.com/v1/audio/speech"
    _google_endpoint = "https://texttospeech.googleapis.com/v1/text:synthesize"
    _google_scopes = ("https://www.googleapis.com/auth/cloud-platform",)

    def __init__(self) -> None:
        self._google_credentials: Optional[ServiceAccountCredentials] = None
        self._credentials_lock = Lock()

    async def synthesize(self, payload: TtsRequest) -> TtsResponse:
        if payload.provider == "google":
            return await self._synthesize_with_google(payload)
        return await self._synthesize_with_openai(payload)

    async def _synthesize_with_openai(self, payload: TtsRequest) -> TtsResponse:
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
                self._openai_endpoint,
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

    async def _synthesize_with_google(self, payload: TtsRequest) -> TtsResponse:
        token = self._get_google_access_token()
        audio_encoding = self._map_audio_encoding(payload.format)
        request_body = {
            "input": {"text": payload.text},
            "voice": {
                "languageCode": payload.language_code or "ja-JP",
                "name": payload.voice or "ja-JP-Wavenet-A",
            },
            "audioConfig": {
                "audioEncoding": audio_encoding,
            },
        }
        audio_config = request_body["audioConfig"]
        if payload.speaking_rate is not None:
            audio_config["speakingRate"] = payload.speaking_rate
        if payload.pitch is not None:
            audio_config["pitch"] = payload.pitch

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                self._google_endpoint,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}",
                },
                json=request_body,
            )

        if response.is_error:
            logger.error("Google TTS synthesis failed: %s", response.text)
            raise HTTPException(status_code=response.status_code, detail="生成语音失败，请稍后再试。")

        data = response.json()
        audio_content = data.get("audioContent")
        if not audio_content:
            raise HTTPException(status_code=502, detail="Google TTS 返回内容为空。")

        content_type = self._map_content_type(payload.format)
        return TtsResponse(audio_base64=audio_content, content_type=content_type)

    def _get_google_access_token(self) -> str:
        if settings.google_tts_credentials_path:
            with self._credentials_lock:
                if self._google_credentials is None:
                    try:
                        self._google_credentials = ServiceAccountCredentials.from_service_account_file(
                            settings.google_tts_credentials_path,
                            scopes=self._google_scopes,
                        )
                    except Exception as exc:
                        logger.exception("加载 Google TTS 凭证失败: %s", exc)
                        raise HTTPException(status_code=503, detail="读取 Google TTS 凭证失败。") from exc
                credentials = self._google_credentials
                if not credentials.valid or credentials.expired or not credentials.token:
                    try:
                        credentials.refresh(Request())
                    except Exception as exc:
                        logger.exception("刷新 Google TTS token 失败: %s", exc)
                        raise HTTPException(status_code=503, detail="刷新 Google TTS 凭证失败。") from exc
                if not credentials.token:
                    raise HTTPException(status_code=503, detail="无法获取 Google TTS 访问令牌。")
                return credentials.token

        if settings.google_tts_access_token:
            return settings.google_tts_access_token

        raise HTTPException(status_code=503, detail="未配置 Google TTS 凭证。")

    @staticmethod
    def _map_audio_encoding(fmt: str) -> str:
        normalized = fmt.lower()
        if normalized in {"wav", "pcm", "linear16"}:
            return "LINEAR16"
        if normalized in {"ogg", "opus"}:
            return "OGG_OPUS"
        return "MP3"

    @staticmethod
    def _map_content_type(fmt: str) -> str:
        normalized = fmt.lower()
        if normalized in {"wav", "pcm", "linear16"}:
            return "audio/wav"
        if normalized in {"ogg", "opus"}:
            return "audio/ogg"
        return "audio/mpeg"


tts_service = TtsService()
