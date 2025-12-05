from __future__ import annotations

import json
import logging
from uuid import uuid4

import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.repositories.appointments import appointment_repository
from app.schemas.appointments import AppointmentCreateRequest, AppointmentRecord

logger = logging.getLogger(__name__)


class AppointmentService:
    _model = "gpt-4o-mini"

    def list_records(self) -> list[AppointmentRecord]:
        return appointment_repository.list()

    async def create_from_conversation(self, payload: AppointmentCreateRequest) -> AppointmentRecord:
        if not payload.messages:
            raise HTTPException(status_code=400, detail="会话内容不能为空")
        summary = await self._summarize(payload)
        record = AppointmentRecord(id=str(uuid4()), **summary)
        return appointment_repository.append(record)

    async def _summarize(self, payload: AppointmentCreateRequest) -> dict[str, str]:
        if not settings.openai_api_key:
            raise HTTPException(status_code=503, detail="未配置 OpenAI API Key")

        conversation_text = "\n".join(
            f"[{msg.timestamp or '--'}][{msg.role}] {msg.text}" for msg in payload.messages
        )

        system_prompt = (
            "あなたは通話内容から予約記録を作成するアシスタントです。"
            "出力は JSON で、keys: timestamp, caller_name, company, appointment, "
            "category, amount, address, summary, raw_messages。"
            "情報が不明な場合は '未提供' を記載してください。"
            "summary は丁寧な日本語で 1-2 文。timestamp は ISO8601 (JST)。"
            "raw_messages には会話ログをそのまま結合してください。"
        )
        user_prompt = f"会話ログ:\n{conversation_text}\n\nJSONのみで回答してください。"

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                },
            )

        if response.is_error:
            logger.error("Appointment summary failed: %s", response.text)
            raise HTTPException(status_code=502, detail="生成预约记录失败，请稍后再试。")

        try:
            data = response.json()["choices"][0]["message"]["content"]
            parsed = json.loads(data)
        except (KeyError, json.JSONDecodeError) as exc:
            logger.exception("Invalid summary payload: %s", exc)
            raise HTTPException(status_code=502, detail="解析预约摘要失败。") from exc

        defaults = {
            "timestamp": payload.messages[-1].timestamp or payload.messages[0].timestamp or "",
            "caller_name": "未提供",
            "company": "未提供",
            "appointment": "未提供",
            "category": "未提供",
            "amount": "未提供",
            "address": "未提供",
            "summary": "未提供",
            "raw_messages": conversation_text,
        }
        defaults.update({k: v for k, v in parsed.items() if isinstance(v, str)})
        if not defaults["timestamp"]:
            defaults["timestamp"] = payload.messages[-1].timestamp or payload.messages[0].timestamp or ""
        return defaults


appointment_service = AppointmentService()
