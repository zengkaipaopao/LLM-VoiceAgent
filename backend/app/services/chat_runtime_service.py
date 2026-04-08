"""
Shared chat runtime helpers for call lookup, prompt runtime resolution, and turn persistence.
"""
from __future__ import annotations

from typing import Any, Callable, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.call import Call
from app.repositories.call_repository import CallRepository
from app.schemas.chat import ChatRequest
from app.services.llm.factory import LLMFactory
from app.services.prompt_runtime_resolver import resolve_prompt_runtime
from app.services.prompt_service import PromptService
from app.utils.datetime_utils import now_tokyo_naive

NormalizeMessagesFn = Callable[[Any], list[dict[str, str]]]


class ChatRuntimeService:
    """Encapsulate runtime setup and persistence for chat turns."""

    def __init__(
        self,
        db: AsyncSession,
        *,
        call_repo: CallRepository | None = None,
        prompt_service: PromptService | None = None,
        normalize_messages: NormalizeMessagesFn | None = None,
    ) -> None:
        self.db = db
        self.call_repo = call_repo or CallRepository(db)
        self.prompt_service = prompt_service or PromptService(db)
        self.normalize_messages = normalize_messages or (lambda raw: raw if isinstance(raw, list) else [])

    async def get_or_create_call(self, call_id: Optional[UUID] = None) -> Call:
        if call_id:
            call = await self.call_repo.get(call_id)
            if not call:
                raise ValueError(f"Call {call_id} not found")
            return call

        return await self.call_repo.create(
            {
                "direction": "inbound",
                "counterpart": "chat_user",
                "status": "ongoing",
                "handler_type": "ai",
            }
        )

    async def setup_chat_context(self, request: ChatRequest, call: Call) -> dict[str, Any]:
        extra_data = call.extra_data or {}
        if request.template_code and request.template_code != "general_appointment":
            resolved_template_code = request.template_code
        else:
            resolved_template_code = extra_data.get("template_code", request.template_code)

        runtime = await resolve_prompt_runtime(
            self.prompt_service,
            template_code=resolved_template_code,
            default_code=resolved_template_code,
            render_system_instruction=True,
        )
        template = runtime.template

        llm_provider = (
            request.provider
            or extra_data.get("llm_provider")
            or runtime.llm_provider
            or "gemini"
        )
        llm_model = (
            request.model
            or extra_data.get("llm_model")
            or runtime.llm_model
            or settings.default_llm_model
        )

        llm_service = LLMFactory.create(
            provider=llm_provider,
            api_key=settings.google_api_key,
            model=llm_model,
        )

        messages = self.normalize_messages(extra_data.get("messages"))

        system_prompt = runtime.system_instruction or ""
        if not system_prompt:
            system_prompt = f"""
            You are an AI assistant for appointment booking.
            Current time: {now_tokyo_naive().isoformat()}
            User wants to book an appointment.
            Extract: name, time, purpose.
            """

        if not messages:
            messages.append({"role": "system", "content": system_prompt})

        return {
            "template": template,
            "llm_service": llm_service,
            "messages": messages,
            "system_prompt": system_prompt,
            "template_code": resolved_template_code,
            "llm_provider": llm_provider,
            "llm_model": llm_model,
        }

    async def persist_turn(
        self,
        *,
        call: Call,
        user_message: str,
        assistant_message: str,
        context: dict[str, Any],
        messages: list[dict[str, str]],
        quota_notice_reason: str | None,
        refresh_call: bool = True,
    ) -> None:
        extra_data = dict(call.extra_data or {})
        extra_data["messages"] = self.normalize_messages(messages)
        extra_data["template_code"] = context["template_code"]
        extra_data["llm_provider"] = context["llm_provider"]
        extra_data["llm_model"] = context["llm_model"]
        if quota_notice_reason:
            extra_data["llm_quota_notice"] = {
                "reason": quota_notice_reason,
                "timestamp": now_tokyo_naive().isoformat(),
            }
        else:
            extra_data.pop("llm_quota_notice", None)

        transcript_update = call.transcript or ""
        transcript_update += (
            f"\n\n用户: {user_message}\n助手: {assistant_message}"
            if transcript_update
            else f"用户: {user_message}\n助手: {assistant_message}"
        )

        call.extra_data = extra_data
        call.transcript = transcript_update

        await self.db.commit()
        if refresh_call:
            await self.db.refresh(call)
