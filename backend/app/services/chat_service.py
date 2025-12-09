import asyncio
from typing import Sequence

import logging
from anthropic import AsyncAnthropic
from app.core.config import settings
from app.core.utils import split_models
from app.schemas.chat import ChatRequest, ChatResponse
from google import generativeai as genai  # type: ignore
from openai import AsyncOpenAI


logger = logging.getLogger(__name__)


class ChatService:
    def __init__(self) -> None:
        self._openai_client: AsyncOpenAI | None = (
            AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        )
        self._anthropic_client: AsyncAnthropic | None = (
            AsyncAnthropic(api_key=settings.claude_api_key) if settings.claude_api_key else None
        )
        if settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)

    async def chat(self, payload: ChatRequest) -> ChatResponse:
        model_id = payload.model_id
        messages = payload.messages
        try:
            if model_id in split_models(settings.openai_models) and self._openai_client:
                reply = await self._chat_openai(model_id, messages)
            elif model_id in split_models(settings.gemini_models or settings.gemini_model) and settings.gemini_api_key:
                reply = await self._chat_gemini(model_id, messages)
            elif model_id in split_models(settings.claude_models) and self._anthropic_client:
                reply = await self._chat_claude(model_id, messages)
            else:
                reply = "未配置可用的模型或 API Key。"
        except Exception as exc:  # noqa: BLE001
            logger.exception("LLM 调用失败 model_id=%s", model_id)
            reply = f"LLM 调用失败: {type(exc).__name__}. 请检查配额/密钥后重试。"
        return ChatResponse(model_id=model_id, reply=reply)

    async def _chat_openai(self, model_id: str, messages: Sequence) -> str:
        assert self._openai_client
        formatted = [{"role": m.role, "content": m.content} for m in messages]
        response = await self._openai_client.chat.completions.create(
            model=model_id,
            messages=formatted,  # type: ignore[arg-type]
        )
        return response.choices[0].message.content or ""

    async def _chat_gemini(self, model_id: str, messages: Sequence) -> str:
        # google-generativeai 是同步 API，放到线程池
        contents = "\n".join([f"{m.role}: {m.content}" for m in messages])

        def _call() -> str:
            model = genai.GenerativeModel(model_id)
            resp = model.generate_content(contents)
            return resp.text or ""

        return await asyncio.to_thread(_call)

    async def _chat_claude(self, model_id: str, messages: Sequence) -> str:
        assert self._anthropic_client
        formatted = [{"role": m.role, "content": m.content} for m in messages]
        resp = await self._anthropic_client.messages.create(
            model=model_id,
            max_tokens=256,
            messages=formatted,  # type: ignore[arg-type]
        )
        # Anthropic 结构中 content 是列表
        if resp.content and hasattr(resp.content[0], "text"):
            return resp.content[0].text
        return ""


chat_service = ChatService()
