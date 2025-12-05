import json
import logging
from typing import Any

import httpx
from fastapi import HTTPException
from pydantic import ValidationError

from app.core.config import settings
from app.schemas.realtime import RealtimeSessionDTO, RealtimeSessionRequest, RealtimeSessionResponse


logger = logging.getLogger(__name__)


class RealtimeService:
    _endpoint = "https://api.openai.com/v1/realtime/sessions"

    async def create_session(self, payload: RealtimeSessionRequest) -> RealtimeSessionDTO:
        if not settings.openai_api_key:
            raise HTTPException(status_code=503, detail="未配置 OpenAI API Key")

        body: dict[str, Any] = {
            "model": payload.model or settings.openai_realtime_model,
            "voice": payload.voice or settings.openai_realtime_voice,
            "instructions": payload.instructions or settings.openai_realtime_instructions,
        }
        if payload.sip:
            body["sip"] = payload.sip

        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                self._endpoint,
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json",
                    "OpenAI-Beta": "realtime=v1",
                },
                json=body,
            )

        payload_text = response.text
        try:
            payload_data = response.json()
        except json.JSONDecodeError:
            payload_data = None

        if response.is_error:
            message = (
                payload_data.get("error", {}).get("message")
                if isinstance(payload_data, dict)
                else payload_text
            )
            logger.warning("Realtime session creation failed: %s", message)
            raise HTTPException(status_code=response.status_code, detail=f"Realtime 会话创建失败：{message}")

        try:
            session = RealtimeSessionResponse(**payload_data)  # type: ignore[arg-type]
        except ValidationError as exc:  # noqa: BLE001
            logger.exception("Realtime session payload validation failed: %s", exc)
            raise HTTPException(status_code=502, detail="Realtime 响应格式异常，请稍后重试。") from exc

        return RealtimeSessionDTO(
            session_id=session.id,
            model=session.model,
            expires_at=session.expires_at,
            client_secret=session.client_secret.value,
            websocket_url=session.websocket_url,
            rtc_configuration=session.rtc_configuration,
        )


realtime_service = RealtimeService()
